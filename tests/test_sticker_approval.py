from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from pure_ai_chat_loader import (
    AI_CHAT_ROOT,
    load_sticker_approval_module,
    load_sticker_library_module,
)


class StickerApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.library = load_sticker_library_module()
        cls.approval = load_sticker_approval_module()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name) / "stickers"
        self.inbox = self.root / "inbox"
        self.reports = self.root / "reports"
        self.inbox.mkdir(parents=True)
        self.reports.mkdir()

    @staticmethod
    def sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def write_png(self, *, metadata: bool = False) -> Path:
        path = self.inbox / "owner-private-name.png"
        pnginfo = None
        if metadata:
            pnginfo = PngInfo()
            pnginfo.add_text("Comment", "must not survive normalization")
        Image.new("RGBA", (64, 64), (255, 120, 160, 200)).save(
            path,
            format="PNG",
            pnginfo=pnginfo,
        )
        return path

    def write_gif(self) -> Path:
        path = self.inbox / "owner-private-animation.gif"
        frames = [
            Image.new("RGBA", (64, 64), color)
            for color in ("red", "green", "blue")
        ]
        frames[0].save(
            path,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=[100, 200, 300],
            loop=0,
        )
        return path

    def draft_entry(self, source: Path, **overrides: object) -> dict[str, object]:
        source_sha256 = self.sha256(source)
        payload: dict[str, object] = {
            "candidate_id": f"candidate_{source_sha256[:12]}",
            "source_sha256": source_sha256,
            "sticker_id": "aike_sticker_001",
            "persona_key": "aike",
            "moods": ["playful"],
            "intensity": "medium",
            "actions": ["act_cute"],
            "usage_tags": ["acting_cute", "general_reaction"],
            "scope": "owner_private",
            "owner_confirmed": True,
        }
        payload.update(overrides)
        return payload

    def write_drafts(self, entries: list[object]) -> None:
        payload = {
            "schema_version": 1,
            "draft_revision": 1,
            "drafts": entries,
        }
        (self.reports / "approval-drafts.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

    def approve(self, source: Path):
        entry = self.draft_entry(source)
        self.write_drafts([entry])
        candidate_id = str(entry["candidate_id"])
        return self.approval.approve_sticker_candidate(
            self.root,
            candidate_id,
            candidate_id.removeprefix("candidate_"),
            now=datetime(2026, 7, 13, 16, 0, tzinfo=timezone.utc),
        )

    def assert_error_code(self, expected: str, callback) -> None:
        with self.assertRaises(self.approval.StickerApprovalError) as raised:
            callback()
        self.assertEqual(raised.exception.code, expected)

    def test_static_approval_strips_metadata_and_writes_schema_v2_atomically(self):
        source = self.write_png(metadata=True)

        result = self.approve(source)

        self.assertEqual(result.sticker_id, "aike_sticker_001")
        self.assertEqual(result.library_revision, 1)
        self.assertFalse(result.animated)
        self.assertTrue(source.exists())
        approved = self.root / "approved" / "aike_sticker_001.png"
        self.assertTrue(approved.is_file())
        info = self.library.inspect_sticker_image(approved)
        self.assertFalse(info.metadata_present)
        manifest = json.loads((self.root / "library.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(manifest["library_revision"], 1)
        self.assertNotIn(str(source), json.dumps(manifest))
        loaded = self.library.load_approved_sticker_library(self.root)
        asset = loaded.enabled_asset("aike_sticker_001")
        self.assertIsNotNone(asset)
        self.assertEqual(asset.intensity, "medium")
        self.assertEqual(asset.actions, ("act_cute",))
        self.assertEqual(asset.source_sha256, self.sha256(source))

    def test_dynamic_gif_approval_preserves_animation_and_total_duration(self):
        source = self.write_gif()

        result = self.approve(source)

        self.assertTrue(result.animated)
        self.assertEqual(result.frame_count, 3)
        self.assertEqual(result.duration_ms, 600)
        approved = self.root / "approved" / "aike_sticker_001.gif"
        info = self.library.inspect_sticker_image(approved)
        self.assertTrue(info.animated)
        self.assertEqual(info.frame_count, 3)
        self.assertEqual(info.duration_ms, 600)
        loaded = self.library.load_approved_sticker_library(self.root)
        self.assertEqual(loaded.approved_count, 1)

    def test_wrong_confirmation_performs_no_write(self):
        source = self.write_png()
        entry = self.draft_entry(source)
        self.write_drafts([entry])

        self.assert_error_code(
            "approval_confirmation_mismatch",
            lambda: self.approval.approve_sticker_candidate(
                self.root,
                str(entry["candidate_id"]),
                "000000000000",
            ),
        )

        self.assertFalse((self.root / "approved").exists())
        self.assertFalse((self.root / "library.json").exists())

    def test_candidate_changed_after_draft_is_rejected_without_approved_file(self):
        source = self.write_png()
        entry = self.draft_entry(source)
        self.write_drafts([entry])
        Image.new("RGBA", (64, 64), "black").save(source, format="PNG")

        self.assert_error_code(
            "candidate_validation_failed",
            lambda: self.approval.approve_sticker_candidate(
                self.root,
                str(entry["candidate_id"]),
                str(entry["candidate_id"]).removeprefix("candidate_"),
            ),
        )

        self.assertFalse((self.root / "approved").exists())
        self.assertFalse((self.root / "library.json").exists())

    def test_manifest_write_failure_removes_new_approved_file(self):
        source = self.write_png()
        entry = self.draft_entry(source)
        self.write_drafts([entry])

        with patch.object(
            self.approval,
            "_atomic_replace_bytes",
            side_effect=self.approval.StickerApprovalError("injected_failure"),
        ):
            self.assert_error_code(
                "injected_failure",
                lambda: self.approval.approve_sticker_candidate(
                    self.root,
                    str(entry["candidate_id"]),
                    str(entry["candidate_id"]).removeprefix("candidate_"),
                ),
            )

        approved = self.root / "approved"
        self.assertEqual(list(approved.iterdir()), [])
        self.assertFalse((self.root / "library.json").exists())

    def test_duplicate_approval_is_rejected_without_revision_change(self):
        source = self.write_png()
        self.approve(source)

        self.assert_error_code(
            "sticker_id_already_exists",
            lambda: self.approval.approve_sticker_candidate(
                self.root,
                f"candidate_{self.sha256(source)[:12]}",
                self.sha256(source)[:12],
            ),
        )

        manifest = json.loads((self.root / "library.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["library_revision"], 1)
        self.assertEqual(len(manifest["stickers"]), 1)

    def test_revocation_requires_final_hash_and_only_disables_entry(self):
        source = self.write_png()
        result = self.approve(source)
        manifest_path = self.root / "library.json"
        approved = self.root / "approved" / "aike_sticker_001.png"

        self.assert_error_code(
            "revocation_confirmation_mismatch",
            lambda: self.approval.revoke_sticker_approval(
                self.root,
                result.sticker_id,
                "000000000000",
            ),
        )
        self.assertTrue(approved.exists())
        self.assertEqual(
            json.loads(manifest_path.read_text(encoding="utf-8"))["library_revision"],
            1,
        )

        revoked = self.approval.revoke_sticker_approval(
            self.root,
            result.sticker_id,
            result.short_sha256,
        )

        self.assertEqual(revoked.library_revision, 2)
        self.assertTrue(approved.exists())
        loaded = self.library.load_approved_sticker_library(self.root)
        self.assertEqual(loaded.approved_count, 0)
        self.assertEqual(loaded.disabled_count, 1)

    def test_unconfirmed_invalid_and_duplicate_drafts_fail_closed(self):
        source = self.write_png()
        cases = (
            ([self.draft_entry(source, owner_confirmed=False)], "owner_confirmation_required"),
            ([self.draft_entry(source, actions=["private_path"])], "invalid_actions"),
            (
                [self.draft_entry(source), self.draft_entry(source)],
                "duplicate_draft_candidate",
            ),
        )
        for entries, expected in cases:
            with self.subTest(expected=expected):
                self.write_drafts(entries)
                self.assert_error_code(
                    expected,
                    lambda: self.approval.load_sticker_approval_drafts(self.root),
                )

    def test_draft_report_exposes_no_full_hash_path_or_file_name(self):
        source = self.write_png()
        entry = self.draft_entry(source)
        self.write_drafts([entry])

        draft_set = self.approval.load_sticker_approval_drafts(self.root)
        formatted = self.approval.format_sticker_approval_drafts(draft_set)

        self.assertIn(str(entry["candidate_id"]), formatted)
        self.assertIn("aike_sticker_001", formatted)
        self.assertNotIn(str(entry["source_sha256"]), formatted)
        self.assertNotIn(source.name, formatted)
        self.assertNotIn(str(source), formatted)

    def test_approval_module_has_no_network_database_or_send_dependency(self):
        source = (AI_CHAT_ROOT / "sticker_approval.py").read_text(encoding="utf-8").lower()
        for forbidden in (
            "httpx",
            "tavily",
            "sqlite",
            "database",
            "nonebot",
            "messagesegment",
            "send_private_msg",
            "ask_llm",
            "mainagent",
        ):
            self.assertNotIn(forbidden, source)

    def test_qq_a3_commands_are_exact_owner_private_and_do_not_send_images(self):
        source = (AI_CHAT_ROOT / "__init__.py").read_text(encoding="utf-8")
        declarations = source[source.index('sticker_drafts_cmd = on_command(') : source.index('help_cmd = on_command(')]
        self.assertIn('"表情草稿"', declarations)
        self.assertIn('"表情批准"', declarations)
        self.assertIn('"表情撤销"', declarations)

        handlers = (
            ("@sticker_drafts_cmd.handle()", "@sticker_approve_cmd.handle()"),
            ("@sticker_approve_cmd.handle()", "@sticker_revoke_cmd.handle()"),
            ("@sticker_revoke_cmd.handle()", "def sticker_preview_error_text"),
        )
        for start_marker, end_marker in handlers:
            with self.subTest(handler=start_marker):
                block = source[source.index(start_marker) : source.index(end_marker)]
                self.assertIn("await require_owner(event, matcher)", block)
                self.assertIn("isinstance(event, PrivateMessageEvent)", block)
                self.assertIn("if not config.enable_local_stickers", block)
                for forbidden in (
                    "MessageSegment.image",
                    "send_private_msg",
                    "ask_llm",
                    "run_main_agent",
                    "Tavily",
                ):
                    self.assertNotIn(forbidden, block)

        approve_block = source[
            source.index("@sticker_approve_cmd.handle()") : source.index(
                "@sticker_revoke_cmd.handle()"
            )
        ]
        self.assertIn("if len(tokens) != 2", approve_block)
        self.assertIn("approve_sticker_candidate", approve_block)
        self.assertIn("asyncio.to_thread", approve_block)
        self.assertIn("未发送图片、未开启自动触发", approve_block)

        revoke_block = source[
            source.index("@sticker_revoke_cmd.handle()") : source.index(
                "def sticker_preview_error_text"
            )
        ]
        self.assertIn("if len(tokens) != 2", revoke_block)
        self.assertIn("revoke_sticker_approval", revoke_block)
        self.assertIn("disabled", revoke_block)

    def test_qq_a3_error_messages_distinguish_safe_failure_categories(self):
        source = (AI_CHAT_ROOT / "__init__.py").read_text(encoding="utf-8")
        self.assertIn(
            '"该候选已经批准，正式库未重复写入。"',
            source,
        )
        self.assertIn(
            '"表情批准失败：确认短哈希格式错误或与候选不一致。"',
            source,
        )
        self.assertIn(
            '"表情撤销失败：必须提供正式文件的正确 12 位短哈希。"',
            source,
        )
        self.assertNotIn("str(exc)", source[source.index("def sticker_approval_error_text") :])


if __name__ == "__main__":
    unittest.main()
