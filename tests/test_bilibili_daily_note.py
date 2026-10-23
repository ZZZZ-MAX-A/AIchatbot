from __future__ import annotations

from contextlib import closing, redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import MagicMock, patch

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module
from src.bilibili_daily_note import BilibiliDailyNoteStore
from src.bilibili_history import HistoryScope, HistorySnapshot
from src.bilibili_browse import validate_summary
from src.bilibili_connector import BilibiliConnectorError


NOW = datetime(2026, 10, 22, 14, 0, tzinfo=timezone.utc)
BV = "BV1xx411c7mD"
OTHER_BV = "BV1yy411c7mD"


def report(bvid=BV, *, recommended=False, reviewed_at=NOW):
    return {"mode": "preview", "status": "ok", "results": [{
        "bvid": bvid, "title": "合成测试视频", "reviewed_at": reviewed_at.isoformat(),
        "status": "summarized" if recommended else "not_recommended", "draft": "UNSENT_DRAFT",
        "evidence": {"basis": "subtitles", "partial": False,
                     "pages": [{"page": 1, "status": "available", "identity_verified": True}],
                     "segments": [{"id": "S1", "page": 1, "text": "这段字幕解释了测试主题"}]},
        "summary": {"content_alignment": "consistent", "alignment_reason": "合成标题与字幕主题一致",
                    "worth_sharing": recommended, "why_share": "这句话只是发送候选，不是已发送的消息",
                    "viewing_impression": "我更喜欢贴近日常的部分，暂时没有特别想分享的内容",
                    "claims": [{"text": "解释了测试主题", "segment_id": "S1", "quote": "解释了测试主题"}]},
    }]}


class DailyNoteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_ai_chat_packages()
        cls.context = load_module("src.plugins.ai_chat.bilibili_context", AI_CHAT_ROOT / "bilibili_context.py")

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.store = BilibiliDailyNoteStore(self.root / "private" / "daily-note.sqlite3")
        self.scope = HistoryScope("synthetic-owner-persona-scope")
        self.config = NS(bilibili_background_max_tokens=1200, bilibili_background_qq_ratio=0.20,
                         bilibili_history_rag_enabled=True)
        self.history = [{"role": "system", "content": "QQ_PERSONA_AND_SUMMARY"},
                        {"role": "user", "content": "QQ_ORIGINAL " * 1500},
                        {"role": "assistant", "content": "QQ_REPLY"}]

    def read(self, **kwargs):
        return self.store.read_today(self.scope, now=kwargs.get("now", NOW))

    def test_missing_read_does_not_create_storage(self):
        self.assertIsNone(self.read())
        self.assertFalse(self.store.path.parent.exists())

    def test_unshared_and_shareable_reviews_both_enter_journal_without_fake_messages(self):
        first = self.store.update(self.scope, report(), now=NOW)
        self.assertEqual(first["verified_videos"], 1)
        self.store.update(self.scope, report(OTHER_BV, recommended=True), now=NOW)
        note = self.read()
        self.assertEqual(note["verified_videos"], 2)
        self.assertIn("解释了测试主题", note["text"])
        self.assertIn("我的感想", note["text"])
        self.assertIn("这次没有推荐分享", note["text"])
        self.assertNotIn("UNSENT_DRAFT", json.dumps(note))
        with closing(sqlite3.connect(self.store.path)) as c:
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(tables, {"daily_note"})
        self.assertFalse((self.store.path.parent / "history.db").exists())

    def test_reprocessing_same_video_is_idempotent_and_does_not_replace_newer_review(self):
        self.store.update(self.scope, report(), now=NOW)
        newer = report(reviewed_at=NOW + timedelta(minutes=1))
        newer["results"][0]["summary"]["viewing_impression"] = "NEWER_IMPRESSION"
        self.store.update(self.scope, newer, now=NOW + timedelta(minutes=1))
        self.store.update(self.scope, report(), now=NOW + timedelta(minutes=2))
        note = self.read()
        self.assertEqual(note["verified_videos"], 1)
        self.assertIn("NEWER_IMPRESSION", note["text"])

    def test_beijing_midnight_expires_without_new_browse_and_next_write_replaces_old_day(self):
        before = datetime(2026, 10, 22, 15, 59, tzinfo=timezone.utc)
        after = datetime(2026, 10, 22, 16, 0, tzinfo=timezone.utc)
        self.store.update(self.scope, report(reviewed_at=before), now=before)
        original = self.store.path.read_bytes()
        self.assertIsNone(self.read(now=after))
        self.assertEqual(self.store.path.read_bytes(), original)
        self.store.update(self.scope, report(OTHER_BV, reviewed_at=after), now=after)
        note = self.read(now=after)
        self.assertEqual(note["day"], "2026-10-23")
        self.assertEqual([i["bvid"] for i in note["items"]], [OTHER_BV])
        with closing(sqlite3.connect(self.store.path)) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM daily_note").fetchone()[0], 1)

    def test_no_new_successes_next_day_cannot_reuse_old_content(self):
        self.store.update(self.scope, report(), now=NOW)
        tomorrow = NOW + timedelta(days=1)
        self.store.update(self.scope, {"mode": "preview", "results": []}, now=tomorrow)
        note = self.read(now=tomorrow)
        self.assertEqual(note["verified_videos"], 0)
        self.assertEqual(note["text"], "")

    def test_scope_isolation(self):
        self.store.update(self.scope, report(), now=NOW)
        self.assertIsNone(self.store.read_today(HistoryScope("another-owner"), now=NOW))

    def test_metadata_failed_unverified_or_unsupported_reviews_never_become_experiences(self):
        mutations = [
            lambda r: r.update(status="metadata_only"),
            lambda r: r.update(status="summary_error"),
            lambda r: r.update(status="source_error"),
            lambda r: r["evidence"]["pages"][0].update(identity_verified=False),
            lambda r: r["evidence"]["segments"][0].update(page=2),
            lambda r: r["summary"]["claims"][0].update(quote="未出现在字幕里的内容"),
            lambda r: r["summary"].update(content_alignment="mismatch", worth_sharing=False, claims=[]),
            lambda r: r.update(reviewed_at=NOW.replace(tzinfo=None).isoformat()),
            lambda r: r.update(reviewed_at=(NOW + timedelta(days=1)).isoformat()),
            lambda r: r.update(reviewed_at=(NOW - timedelta(days=1)).isoformat()),
        ]
        for mutation in mutations:
            sample = report()
            mutation(sample["results"][0])
            with self.subTest(mutation=mutation):
                result = self.store.update(self.scope, sample, now=NOW)
                self.assertEqual(result["accepted_results"], 0)
        self.assertEqual(self.read()["verified_videos"], 0)

    def test_inspection_and_withdrawn_reports_are_ignored(self):
        for fields in ({"mode": "inspect"}, {"withdrawal_reason": "unreliable"}):
            self.assertEqual(self.store.update(self.scope, {**report(), **fields}, now=NOW)["status"], "ignored")
        self.assertFalse(self.store.path.exists())

    def test_missing_impression_does_not_relabel_draft_as_personal_feeling(self):
        sample = report()
        del sample["results"][0]["summary"]["viewing_impression"]
        self.store.update(self.scope, sample, now=NOW)
        self.assertNotIn("我的感想", self.read()["text"])
        self.assertNotIn("这句话只是发送候选", self.read()["text"])

    def test_impression_validation_and_partial_reading(self):
        sample = report()
        sample["results"][0]["evidence"]["partial"] = True
        self.store.update(self.scope, sample, now=NOW)
        self.assertIn("未覆盖部分", self.read()["text"])
        for value in (None, 123, "感" * 101):
            summary = {**sample["results"][0]["summary"], "viewing_impression": value}
            with self.assertRaises(BilibiliConnectorError):
                validate_summary(summary, sample["results"][0]["evidence"])

    def test_local_short_note_is_bounded_when_today_has_many_reviews(self):
        for n in range(12):
            sample = report(f"BV{n:010d}")
            sample["results"][0]["summary"]["viewing_impression"] = "合成感想" * 20
            self.store.update(self.scope, sample, now=NOW)
        note = self.read()
        self.assertEqual(note["verified_videos"], 12)
        self.assertLessEqual(len(note["text"]), 600)
        self.assertLess(note["shown_videos"], 12)

    def test_diary_only_qq_background_uses_existing_budget_without_rag_or_message_rounds(self):
        self.store.update(self.scope, report(), now=NOW)
        before = deepcopy(self.history)
        factory = MagicMock(side_effect=AssertionError("journal must not query embeddings"))
        text, status = self.context.build_background(HistorySnapshot(), self.config, self.history, "今天看了什么",
            now=NOW, daily_note=self.read(), embedder_factory=factory)
        payload = json.loads(text.split("\n", 1)[1])
        self.assertIn("我的感想", payload["viewing_today"]["text"])
        self.assertIn("不是私信", payload["viewing_today"]["basis"])
        self.assertEqual(payload["recent"], [])
        self.assertEqual(payload["recalled"], [])
        self.assertEqual(status["recent_rounds"], 0)
        self.assertTrue(status["daily_note_included"])
        self.assertLessEqual(status["estimated_tokens"], status["budget_estimated_tokens"])
        self.assertLessEqual(status["daily_note_estimated_tokens"], 320)
        self.assertEqual(self.history, before)
        factory.assert_not_called()

    def test_expired_note_not_injected_even_if_supplied_directly(self):
        self.store.update(self.scope, report(), now=NOW)
        text, status = self.context.build_background(HistorySnapshot(), self.config, self.history, "today",
            now=NOW + timedelta(days=1), daily_note=self.read())
        self.assertEqual(text, "")
        self.assertFalse(status["daily_note_included"])

    def test_zero_or_tiny_budget_keeps_qq_history_intact(self):
        self.store.update(self.scope, report(), now=NOW)
        for cap in (0, 5, 80):
            self.config.bilibili_background_max_tokens = cap
            text, _ = self.context.build_background(HistorySnapshot(), self.config, self.history, "today",
                now=NOW, daily_note=self.read())
            self.assertEqual(text, "")
            self.assertEqual(self.context.inject_background(self.history, text), self.history)

    def test_cli_updates_note_without_extra_model_calls_and_journal_failure_is_nonfatal(self):
        script = Path(__file__).resolve().parents[1] / "scripts/bilibili_browse.py"
        spec = importlib.util.spec_from_file_location("bilibili_daily_cli_test", script)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        for fail in (False, True):
            sample = {**report(), "sources": {}, "candidates": [], "usage": [], "diagnostics": {},
                      "messages_sent": 0, "errors": []}
            writer = MagicMock()
            writer.update.return_value = {"status": "updated"}
            if fail:
                writer.update.side_effect = RuntimeError("PRIVATE_STORAGE_DETAILS")
            model = MagicMock()
            with patch.object(cli.BindingStore, "load"), patch.object(cli.CredentialStore, "load"), \
                 patch.object(cli, "BilibiliClient"), patch.object(cli, "BrowseClient"), \
                 patch.object(cli, "preview", return_value=sample), \
                 patch.object(cli, "save_report", return_value=(Path("fixture.json"), Path("fixture.md"))), \
                 patch("src.bilibili_persona.load_persona_configuration"), \
                 patch("src.bilibili_persona.persona_settings", return_value=("role", NS(), False)), \
                 patch("src.bilibili_persona.PersonaModel", return_value=model), \
                 patch("src.bilibili_daily_note.BilibiliDailyNoteWriter", return_value=writer), \
                 redirect_stdout(io.StringIO()) as output:
                result = cli.main(["preview", "--without-qq-memory", "--subtitle-transport", "api"])
            self.assertEqual(result, 0)
            writer.update.assert_called_once_with(sample)
            self.assertEqual(sample["daily_note"]["status"], "unavailable" if fail else "updated")
            self.assertNotIn("PRIVATE_STORAGE_DETAILS", output.getvalue())
            model.ask.assert_not_called()


if __name__ == "__main__":
    unittest.main()
