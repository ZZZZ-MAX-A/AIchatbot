from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from pure_ai_chat_loader import (
    AI_CHAT_ROOT,
    load_sticker_approval_module,
    load_sticker_preview_module,
)


class StickerPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.approval = load_sticker_approval_module()
        cls.preview = load_sticker_preview_module()

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

    def write_candidate(self, *, animated: bool = False) -> Path:
        if not animated:
            path = self.inbox / "private-static.png"
            Image.new("RGBA", (64, 64), "red").save(path, format="PNG")
            return path
        path = self.inbox / "private-animation.gif"
        frames = [Image.new("RGBA", (64, 64), color) for color in ("red", "blue")]
        frames[0].save(
            path,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=[100, 200],
            loop=0,
        )
        return path

    def approve(self, source: Path, *, sticker_id: str = "aike_preview_001"):
        source_hash = self.sha256(source)
        candidate_id = f"candidate_{source_hash[:12]}"
        payload = {
            "schema_version": 1,
            "draft_revision": 1,
            "drafts": [
                {
                    "candidate_id": candidate_id,
                    "source_sha256": source_hash,
                    "sticker_id": sticker_id,
                    "persona_key": "aike",
                    "moods": ["happy"],
                    "intensity": "medium",
                    "actions": ["smile"],
                    "usage_tags": ["general_reaction"],
                    "scope": "owner_private",
                    "owner_confirmed": True,
                }
            ],
        }
        (self.reports / "approval-drafts.json").write_text(
            json.dumps(payload),
            encoding="utf-8",
        )
        return self.approval.approve_sticker_candidate(
            self.root,
            candidate_id,
            source_hash[:12],
            now=datetime(2026, 7, 13, 17, 30, tzinfo=timezone.utc),
        )

    def assert_error_code(self, expected: str, callback) -> None:
        with self.assertRaises(self.preview.StickerPreviewError) as raised:
            callback()
        self.assertEqual(raised.exception.code, expected)

    def test_enabled_static_asset_is_revalidated_for_preview(self):
        self.approve(self.write_candidate())

        asset = self.preview.resolve_sticker_preview_asset(
            self.root,
            "aike_preview_001",
        )

        self.assertEqual(asset.sticker_id, "aike_preview_001")
        self.assertTrue(asset.file_path.is_file())
        self.assertFalse(asset.animated)
        self.assertEqual(asset.frame_count, 1)
        self.assertEqual(asset.duration_ms, 0)
        self.assertEqual(len(asset.short_sha256), 12)

    def test_enabled_dynamic_asset_is_revalidated_for_preview(self):
        self.approve(self.write_candidate(animated=True))

        asset = self.preview.resolve_sticker_preview_asset(
            self.root,
            "aike_preview_001",
        )

        self.assertTrue(asset.animated)
        self.assertEqual(asset.frame_count, 2)
        self.assertEqual(asset.duration_ms, 300)
        self.assertEqual(asset.media_type, "image/gif")

    def test_disabled_asset_is_never_returned_for_preview(self):
        result = self.approve(self.write_candidate())
        self.approval.revoke_sticker_approval(
            self.root,
            result.sticker_id,
            result.short_sha256,
        )

        self.assert_error_code(
            "sticker_disabled",
            lambda: self.preview.resolve_sticker_preview_asset(
                self.root,
                result.sticker_id,
            ),
        )

    def test_unknown_invalid_and_tampered_assets_fail_closed(self):
        self.approve(self.write_candidate())
        cases = (
            ("../private-static.png", "invalid_sticker_id"),
            ("aike_missing_001", "sticker_not_found"),
        )
        for sticker_id, expected in cases:
            with self.subTest(expected=expected):
                self.assert_error_code(
                    expected,
                    lambda sticker_id=sticker_id: self.preview.resolve_sticker_preview_asset(
                        self.root,
                        sticker_id,
                    ),
                )

        approved = self.root / "approved" / "aike_preview_001.png"
        Image.new("RGBA", (64, 64), "black").save(approved, format="PNG")
        self.assert_error_code(
            "library_validation_failed",
            lambda: self.preview.resolve_sticker_preview_asset(
                self.root,
                "aike_preview_001",
            ),
        )

    def test_preview_module_has_no_network_database_or_sender_dependency(self):
        source = (AI_CHAT_ROOT / "sticker_preview.py").read_text(encoding="utf-8").lower()
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

    def test_qq_preview_is_exact_owner_private_single_send_and_no_retry(self):
        source = (AI_CHAT_ROOT / "__init__.py").read_text(encoding="utf-8")
        declaration = source.index('sticker_preview_cmd = on_command(')
        handler = source.index("@sticker_preview_cmd.handle()")
        handler_end = source.index("@help_cmd.handle()", handler)
        block = source[handler:handler_end]

        self.assertIn('"表情预览"', source[declaration:handler])
        self.assertIn("await require_owner(event, matcher)", block)
        self.assertIn("isinstance(event, PrivateMessageEvent)", block)
        self.assertIn("if not config.enable_local_stickers", block)
        self.assertIn("if len(tokens) != 1", block)
        self.assertIn("resolve_sticker_preview_asset", block)
        self.assertIn("check_sticker_preview_cooldown", block)
        self.assertIn('"send_private_msg"', block)
        self.assertIn("MessageSegment.image(str(asset.file_path))", block)
        self.assertEqual(block.count("await bot.call_api("), 1)
        self.assertIn("未重试、未改发其他图片", block)
        for forbidden in (
            "ask_llm",
            "run_main_agent",
            "Tavily",
            "while ",
            "for asset",
            "random",
        ):
            self.assertNotIn(forbidden, block)


if __name__ == "__main__":
    unittest.main()
