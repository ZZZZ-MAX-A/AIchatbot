from __future__ import annotations

from contextlib import closing
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module
from src.bilibili_connector import BilibiliBinding, BindingStore
from src.bilibili_history import BilibiliHistoryStore, HistoryScope
from src.bilibili_history_bridge import BilibiliHistoryWriter, import_sent_reports
from src.bilibili_memory import mapping_data, pin_mapping, resolve_memory_scope


NOW = datetime(2026, 10, 22, 14, 0, tzinfo=timezone.utc)
BV = "BV1xx411c7mD"


class FakeEmbedder:
    provider = "test"
    model = "test-vector"

    def __init__(self):
        self.calls = []

    def embed(self, text):
        self.calls.append(text)
        return [1.0, 0.0]


class BilibiliHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_ai_chat_packages()
        cls.context = load_module("src.plugins.ai_chat.bilibili_context", AI_CHAT_ROOT / "bilibili_context.py")
        cls.scopes = load_module("src.plugins.ai_chat.persona_scope", AI_CHAT_ROOT / "persona_scope.py")

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.home = self.root / "private"
        self.binding = BilibiliBinding("aike", "aike", "101", "202")
        self.config = NS(bot_owner_qq="11111", persona_routing=self.scopes.PersonaRoutingSettings(
            bindings=(self.scopes.PersonaBinding("33333", "aike", "aike"),)),
            memory_rag_embedding_provider="test", memory_rag_embedding_model="test-vector",
            memory_rag_min_score=0.50, memory_rag_top_k=1, memory_rag_max_context_chars=10,
            bilibili_background_max_tokens=6000, bilibili_background_qq_ratio=1.0,
            bilibili_history_enabled=True, bilibili_history_rag_enabled=True)
        self.qq_scope = resolve_memory_scope(self.binding, self.config, self.root)
        self.scope = HistoryScope.from_mapping(mapping_data(self.binding, self.qq_scope))
        self.store = BilibiliHistoryStore(self.home / "history.db")
        self.embedder = FakeEmbedder()
        self.qq_history = [
            {"role": "system", "content": "QQ_SUMMARY_AND_PERSONA_MARKER"},
            {"role": "user", "content": "QQ_HOT_ORIGINAL " * 3000},
            {"role": "assistant", "content": "QQ_HOT_REPLY"},
        ]

    def add(self, number, role="assistant", *, round_key=None, content=None, scope=None):
        return self.store.record_message(
            scope or self.scope, message_key=f"message-{number}", round_key=round_key or f"round-{number}",
            role=role, content=content or f"BILIBILI_ORIGINAL_{number}",
            occurred_at=f"2026-10-21T12:{number:02d}:00+00:00", time_kind="platform_sent",
            bvid=BV, video_title="Synthetic video",
        )

    def snapshot(self):
        return self.store.snapshot(self.scope, provider="test", model="test-vector")

    def build(self, snapshot=None, query="earlier video", **kwargs):
        return self.context.build_background(snapshot or self.snapshot(), self.config, self.qq_history,
                                             query, embedder_factory=lambda _: self.embedder, now=NOW, **kwargs)

    def bind(self):
        BindingStore(self.home / "binding.json").save(self.binding)
        pin_mapping(self.binding, self.qq_scope, self.home / "memory-binding.json")
        return NS(chat_type="private", configuration_error="", bot_self_id="33333", persona_id="aike",
                  role_card_key="aike", runtime_session_key=self.qq_scope.session)

    def test_missing_read_does_not_create_a_store(self):
        self.assertEqual(self.snapshot().status, "missing")
        self.assertFalse(self.home.exists())
        self.assertIsNone(self.store.get_message(self.scope, "missing"))

    def test_latest_three_rounds_keep_both_speakers_not_just_three_messages(self):
        for n in range(1, 9):
            self.add(n, "user" if n % 2 else "assistant", round_key=f"round-{(n + 1) // 2}")
        snapshot = self.snapshot()
        self.assertEqual([m.id for m in snapshot.recent], list(range(3, 9)))
        text, status = self.build(snapshot)
        self.assertEqual(status["recent_rounds"], 3)
        self.assertEqual(status["recent_messages"], 6)
        self.assertNotIn("BILIBILI_ORIGINAL_1", text)
        self.assertFalse(self.embedder.calls)

    def test_outbound_share_is_one_round_without_inventing_owner_text(self):
        self.add(1)
        text, status = self.build()
        self.assertEqual(status["recent_rounds"], 1)
        self.assertIn('"speaker":"aike"', text)
        self.assertNotIn('"speaker":"owner"', text)

    def test_original_text_is_durable_and_duplicate_delivery_is_idempotent(self):
        original = "FULL_TEXT_MARKER " * 5000
        first = self.add(1, content=original)
        self.assertEqual(self.add(1, content=original), first)
        self.assertEqual(self.store.get_message(self.scope, "message-1").content, original)
        with self.assertRaises(ValueError):
            self.add(1, content="changed text")

    def test_old_imports_sort_by_source_time_not_insertion_order(self):
        for n in (9, 8, 7, 1):
            self.add(n)
        self.assertEqual([m.content for m in self.snapshot().recent],
                         ["BILIBILI_ORIGINAL_7", "BILIBILI_ORIGINAL_8", "BILIBILI_ORIGINAL_9"])

    def test_timestamps_show_source_beijing_time_and_recompute_elapsed(self):
        self.add(1)
        text, _ = self.build()
        self.assertIn("消息发送时间", text)
        self.assertIn("2026-10-21 20:01:00", text)
        self.assertIn("1天1小时前", text)
        later = self.context._entry(self.snapshot().recent[0], 100, datetime(2026, 10, 23, 14, tzinfo=timezone.utc))
        self.assertIn("2天1小时前", later["time"])

    def test_unknown_and_confirmation_times_are_not_presented_as_delivery(self):
        self.store.record_message(self.scope, message_key="unknown", round_key="unknown", role="user", content="original")
        with self.assertRaises(ValueError):
            self.store.record_message(self.scope, message_key="bad", round_key="bad", role="user", content="bad",
                                      occurred_at="2026-10-22T01:00:00")
        text, _ = self.build()
        self.assertIn("原发送时间未知", text)
        message = replace(self.snapshot().recent[0], time_kind="send_confirmed", occurred_at=NOW.isoformat())
        self.assertIn("非阅读确认", self.context._entry(message, 100, NOW)["time"])

    def test_own_rag_returns_five_older_messages_independent_of_qq_top_k(self):
        for n in range(1, 13):
            self.add(n)
        self.store.index_pending(self.scope, self.embedder)
        self.embedder.calls.clear()
        text, status = self.build()
        self.assertEqual(status["recent_rounds"], 3)
        self.assertEqual(status["recalled_messages"], 5)
        self.assertEqual(status["retrieval_status"], "matched")
        payload = json.loads(text.split("\n", 1)[1])
        recent = {m["text"] for m in payload["recent"]}
        recalled = {m["text"] for m in payload["recalled"]}
        self.assertFalse(recent & recalled)
        self.assertEqual(len(self.embedder.calls), 1)
        self.assertEqual(self.config.memory_rag_top_k, 1)
        self.assertEqual(self.config.memory_rag_max_context_chars, 10)

    def test_other_scope_filtered_before_top_k(self):
        mapping = mapping_data(self.binding, self.qq_scope)
        mapping["qq_owner_uid"] = "99999"
        other = HistoryScope.from_mapping(mapping)
        for n in range(1, 9):
            self.add(n)
        self.add(20, content="OTHER_OWNER_SECRET", scope=other)
        self.store.index_pending(self.scope, self.embedder)
        self.store.index_pending(other, self.embedder)
        text, _ = self.build()
        self.assertNotIn("OTHER_OWNER_SECRET", text)
        self.assertEqual(len(self.snapshot().candidates), 8)

    def test_deleted_or_tampered_source_cannot_reappear_via_old_index(self):
        for n in range(1, 8):
            self.add(n)
        self.store.index_pending(self.scope, self.embedder)
        self.store.retract(self.scope, "message-1")
        with closing(sqlite3.connect(self.store.path)) as c, c:
            c.execute("UPDATE bili_messages SET content='MODIFIED_SOURCE' WHERE message_key='message-2'")
        self.assertNotIn(1, [m.id for m, _ in self.snapshot().candidates])
        self.assertNotIn(2, [m.id for m, _ in self.snapshot().candidates])
        with self.assertRaises(ValueError):
            self.add(1)

    def test_invalid_vectors_are_skipped_and_failed_index_preserves_original(self):
        self.add(1)
        broken = NS(provider="test", model="test-vector", embed=Mock(return_value=[float("nan")]))
        self.assertEqual(self.store.index_pending(self.scope, broken), {"indexed": 0, "failed": 1})
        self.assertEqual(self.snapshot().unindexed_messages, 1)
        self.assertEqual(self.store.get_message(self.scope, "message-1").content, "BILIBILI_ORIGINAL_1")

    def test_no_match_does_not_fill_with_unrelated_old_messages(self):
        for n in range(1, 8):
            self.add(n)
        self.store.index_pending(self.scope, self.embedder)
        self.embedder.embed = Mock(return_value=[0.0, 1.0])
        text, status = self.build()
        self.assertEqual(status["retrieval_status"], "no_match")
        self.assertEqual(status["recalled_messages"], 0)
        self.assertNotIn("BILIBILI_ORIGINAL_1", text)

    def test_zero_or_wrong_dimension_queries_do_not_match_even_at_zero_threshold(self):
        for n in range(1, 8):
            self.add(n)
        self.store.index_pending(self.scope, self.embedder)
        self.config.memory_rag_min_score = 0.0
        for vector in ([0.0, 0.0], [1.0, 0.0, 0.0], [True, False]):
            self.embedder.embed = Mock(return_value=vector)
            _, status = self.build()
            self.assertEqual(status["recalled_messages"], 0)

    def test_zero_budget_skips_retrieval_and_keeps_qq_unchanged(self):
        for n in range(1, 8):
            self.add(n)
        self.store.index_pending(self.scope, self.embedder)
        self.embedder.calls.clear()
        self.config.bilibili_background_max_tokens = 0
        text, status = self.build()
        self.assertEqual(text, "")
        self.assertEqual(status["status"], "budget_exhausted")
        self.assertFalse(self.embedder.calls)
        self.assertEqual(self.context.inject_background(self.qq_history, text), self.qq_history)

    def test_provider_error_keeps_recent_and_does_not_leak_private_exception(self):
        for n in range(1, 8):
            self.add(n)
        self.store.index_pending(self.scope, self.embedder)
        self.embedder.embed = Mock(side_effect=RuntimeError("PRIVATE_PROVIDER_PAYLOAD"))
        text, status = self.build()
        self.assertEqual(status["retrieval_status"], "unavailable")
        self.assertEqual(status["recent_rounds"], 3)
        self.assertNotIn("PRIVATE_PROVIDER_PAYLOAD", text + json.dumps(status))
        self.embedder.embed.assert_called_once()

    def test_budget_includes_wrapper_and_time_and_never_changes_archive(self):
        for n in range(1, 9):
            self.add(n, content=f"MESSAGE_{n}:" + "完整原文" * 3000)
        self.config.bilibili_background_max_tokens = 500
        self.config.bilibili_background_qq_ratio = 0.20
        text, status = self.build()
        self.assertLessEqual(self.context.estimate_tokens(text), 500)
        self.assertEqual(status["recent_rounds"], 3)
        self.assertTrue(json.loads(text.split("\n", 1)[1])["recent"][0]["truncated"])
        self.assertGreater(len(self.store.get_message(self.scope, "message-8").content), 10000)

    def test_qq_ratio_limits_background_without_using_role_card_size(self):
        self.add(1)
        original = [{"role": "system", "content": "PERSONA" * 100000}, {"role": "user", "content": "hello"}]
        self.config.bilibili_background_qq_ratio = 0.20
        text, status = self.context.build_background(self.snapshot(), self.config, original, "hi", now=NOW)
        self.assertEqual(text, "")
        self.assertEqual(status["status"], "budget_exhausted")
        self.assertLess(status["budget_estimated_tokens"], 5)

    def test_qq_messages_remain_in_same_order_with_background_before_hot_history(self):
        self.add(1)
        text, _ = self.build()
        before = json.dumps(self.qq_history)
        injected = self.context.inject_background(self.qq_history, text)
        self.assertEqual(injected[0], self.qq_history[0])
        self.assertEqual(injected[1]["content"], text)
        self.assertEqual(injected[2:], self.qq_history[1:])
        self.assertEqual(json.dumps(self.qq_history), before)

    def test_snapshot_reads_and_context_search_are_read_only(self):
        for n in range(1, 7):
            self.add(n)
        self.store.index_pending(self.scope, self.embedder)
        before = self.store.path.read_bytes()
        snapshot = self.snapshot()
        with patch.object(self.store, "_write_connection", side_effect=AssertionError("must not write")):
            self.build(snapshot)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertFalse(self.qq_scope.database.exists())

    def test_pinned_qq_adapter_requires_matching_owner_bot_persona_session(self):
        conversation = self.bind()
        self.add(1)
        kwargs = dict(conversation=conversation, owner_id="11111", history=self.qq_history, query="hello",
                      root=self.root, home=self.home)
        output, status = self.context.qq_bilibili_background(self.config, **kwargs)
        self.assertEqual(status["status"], "included")
        self.assertEqual(output[2:], self.qq_history[1:])
        for field, value in (("chat_type", "group"), ("bot_self_id", "other-bot"), ("persona_id", "other-persona"),
                             ("role_card_key", "other-card"), ("runtime_session_key", "other-session")):
            changed = NS(**{**vars(conversation), field: value})
            output, status = self.context.qq_bilibili_background(self.config, **{**kwargs, "conversation": changed})
            self.assertEqual(output, self.qq_history)
            self.assertNotEqual(status["status"], "included")
        output, _ = self.context.qq_bilibili_background(self.config, **{**kwargs, "owner_id": "99999"})
        self.assertEqual(output, self.qq_history)
        self.assertFalse(self.qq_scope.database.exists())

    def test_missing_binding_or_corrupt_store_does_not_break_qq(self):
        conversation = self.bind()
        self.add(1)
        self.store.path.write_bytes(b"corrupt sqlite")
        output, status = self.context.qq_bilibili_background(
            self.config, conversation=conversation, owner_id="11111", history=self.qq_history,
            query="hello", root=self.root, home=self.home)
        self.assertEqual(output, self.qq_history)
        self.assertEqual(status, {"status": "unavailable"})

    def test_daily_note_coexists_with_three_rounds_and_five_recalled_messages(self):
        from src.bilibili_daily_note import BilibiliDailyNoteStore
        from test_bilibili_daily_note import report
        for n in range(1, 12):
            self.add(n)
        self.store.index_pending(self.scope, self.embedder)
        diary = BilibiliDailyNoteStore(self.home / "daily-note.sqlite3")
        diary.update(self.scope, report(), now=NOW)
        text, status = self.build(daily_note=diary.read_today(self.scope, now=NOW))
        payload = json.loads(text.split("\n", 1)[1])
        self.assertEqual(status["recent_rounds"], 3)
        self.assertEqual(status["recalled_messages"], 5)
        self.assertTrue(status["daily_note_included"])
        self.assertIn("我的感想", payload["viewing_today"]["text"])
        self.assertLessEqual(status["estimated_tokens"], status["budget_estimated_tokens"])
        self.assertEqual(self.config.memory_rag_top_k, 1)

    def test_pinned_adapter_reads_diary_without_creating_chat_store_or_leaking_to_other_scopes(self):
        from src.bilibili_daily_note import BilibiliDailyNoteStore
        from test_bilibili_daily_note import report
        conversation = self.bind()
        diary = BilibiliDailyNoteStore(self.home / "daily-note.sqlite3")
        diary.update(self.scope, report(), now=NOW)
        kwargs = dict(conversation=conversation, owner_id="11111", history=self.qq_history, query="今天看了什么",
                      root=self.root, home=self.home)
        before = diary.path.read_bytes()
        with patch.object(self.context, "datetime") as clock:
            clock.now.return_value = NOW
            output, status = self.context.qq_bilibili_background(self.config, **kwargs)
            self.assertTrue(status["daily_note_included"])
            self.assertEqual(status["recent_messages"], 0)
            self.assertEqual(output[2:], self.qq_history[1:])
            self.assertIn("我的感想", output[1]["content"])
            for field, value in (("chat_type", "group"), ("bot_self_id", "other-bot"),
                                 ("persona_id", "other-persona"), ("runtime_session_key", "other-session")):
                changed = NS(**{**vars(conversation), field: value})
                protected, _ = self.context.qq_bilibili_background(self.config, **{**kwargs, "conversation": changed})
                self.assertEqual(protected, self.qq_history)
            protected, _ = self.context.qq_bilibili_background(self.config, **{**kwargs, "owner_id": "99999"})
            self.assertEqual(protected, self.qq_history)
        self.assertEqual(diary.path.read_bytes(), before)
        self.assertFalse(self.store.path.exists())
        self.assertFalse(self.qq_scope.database.exists())

    def test_corrupt_daily_note_does_not_remove_existing_private_message_background(self):
        conversation = self.bind()
        self.add(1)
        (self.home / "daily-note.sqlite3").write_bytes(b"private corrupt note details")
        output, status = self.context.qq_bilibili_background(
            self.config, conversation=conversation, owner_id="11111", history=self.qq_history,
            query="hello", root=self.root, home=self.home)
        self.assertEqual(status["status"], "included")
        self.assertEqual(status["daily_note_status"], "unavailable")
        self.assertIn("BILIBILI_ORIGINAL_1", output[1]["content"])
        self.assertNotIn("private corrupt note details", json.dumps(status) + output[1]["content"])

    def test_writer_rejects_another_owner_and_preserves_round_for_reply(self):
        self.bind()
        writer = BilibiliHistoryWriter(self.binding, self.config, root=self.root, home=self.home)
        with self.assertRaises(Exception):
            writer.record_owner_message(sender_mid="999", message_id="1", text="OTHER_OWNER", sent_at=NOW.isoformat())
        writer.record_owner_message(sender_mid="202", message_id="1", text="OWNER_MESSAGE", sent_at=NOW.isoformat())
        writer.record_sent_reply(receiver_mid="202", message_id="2", round_key="owner:1", text="AIKE_REPLY", confirmed_at=NOW.isoformat())
        self.assertEqual(len({m.round_key for m in self.snapshot().recent}), 1)
        self.assertEqual(len(self.snapshot().recent), 2)

    def test_successful_report_import_requires_matching_ledger_and_keeps_original_draft(self):
        self.bind()
        writer = BilibiliHistoryWriter(self.binding, self.config, root=self.root, home=self.home)
        reports = self.home / "previews"
        reports.mkdir()
        ledger = self.home / "deliveries.sqlite3"
        key = hashlib.sha256(json.dumps(["101", "202", "explicit", "video-share-v1:" + BV], ensure_ascii=False).encode()).hexdigest()
        with closing(sqlite3.connect(ledger)) as c, c:
            c.execute("CREATE TABLE deliveries(delivery_key TEXT,request_id TEXT,state TEXT,created_at INTEGER,code INTEGER)")
            c.execute("INSERT INTO deliveries VALUES(?, 'sent-request','sent',1792670400,0)", (key,))
        report = {"status": "ok", "results": [{"bvid": BV, "title": "Synthetic video", "draft": "ORIGINAL_SENT_WORDING"}],
                  "delivery": {"status": "sent", "platform_accepted": True, "business_code": 0, "bvid": BV, "request_id": "sent-request"}}
        report_path = reports / "fixture.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        before = report_path.read_bytes()
        self.assertEqual(import_sent_reports(writer, reports, ledger)["imported"], 1)
        message = self.store.get_message(self.scope, "out:sent-request")
        self.assertEqual(message.content, "ORIGINAL_SENT_WORDING")
        self.assertEqual(message.time_kind, "send_attempt")
        self.assertEqual(import_sent_reports(writer, reports, ledger)["already_saved"], 1)
        self.assertEqual(report_path.read_bytes(), before)
        report["delivery"]["request_id"] = "not-sent-request"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        self.assertEqual(import_sent_reports(writer, reports, ledger)["imported"], 0)
        for malformed in (None, [], {"delivery": None}, {"delivery": []}):
            report_path.write_text(json.dumps(malformed), encoding="utf-8")
            self.assertEqual(import_sent_reports(writer, reports, ledger)["skipped"], 1)


if __name__ == "__main__":
    unittest.main()
