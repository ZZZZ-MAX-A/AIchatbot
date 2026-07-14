from __future__ import annotations

import asyncio
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
    load_sticker_attachment_module,
)


class StickerAttachmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.approval = load_sticker_approval_module()
        cls.module = load_sticker_attachment_module()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name) / "stickers"
        self.inbox = self.root / "inbox"
        self.reports = self.root / "reports"
        self.inbox.mkdir(parents=True)
        self.reports.mkdir()

    def approve(self, sticker_id: str = "aike_act_cute_001"):
        source = self.inbox / "private-animation.gif"
        frames = [Image.new("RGBA", (64, 64), color) for color in ("red", "blue")]
        frames[0].save(
            source,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=[100, 200],
            loop=0,
        )
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        candidate_id = f"candidate_{source_hash[:12]}"
        (self.reports / "approval-drafts.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "draft_revision": 1,
                    "drafts": [
                        {
                            "candidate_id": candidate_id,
                            "source_sha256": source_hash,
                            "sticker_id": sticker_id,
                            "persona_key": "aike",
                            "moods": ["playful"],
                            "intensity": "medium",
                            "actions": ["act_cute"],
                            "usage_tags": ["acting_cute"],
                            "scope": "owner_private",
                            "owner_confirmed": True,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.approval.approve_sticker_candidate(
            self.root,
            candidate_id,
            source_hash[:12],
            now=datetime(2026, 7, 14, tzinfo=timezone.utc),
        )

    def test_success_revalidates_and_calls_sender_exactly_once(self):
        self.approve()
        calls = []

        async def sender(user_id, file_path):
            calls.append((user_id, file_path))

        result = asyncio.run(
            self.module.send_selected_sticker_attachment(
                self.root,
                "aike_act_cute_001",
                10001,
                limits=self.approval.StickerLimits(),
                sender=sender,
            )
        )

        self.assertTrue(result.sent)
        self.assertEqual(result.status, "sent")
        self.assertEqual(result.sticker_id, "aike_act_cute_001")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 10001)
        self.assertTrue(calls[0][1].is_file())

    def test_send_failure_is_not_retried(self):
        self.approve()
        calls = 0

        async def sender(user_id, file_path):
            nonlocal calls
            calls += 1
            raise RuntimeError("private onebot detail")

        result = asyncio.run(
            self.module.send_selected_sticker_attachment(
                self.root,
                "aike_act_cute_001",
                10001,
                limits=self.approval.StickerLimits(),
                sender=sender,
            )
        )

        self.assertFalse(result.sent)
        self.assertEqual(result.status, "send_failed")
        self.assertEqual(calls, 1)

    def test_invalid_recipient_unknown_disabled_or_tampered_never_sends(self):
        self.approve()
        calls = 0

        async def sender(user_id, file_path):
            nonlocal calls
            calls += 1

        invalid_recipient = asyncio.run(
            self.module.send_selected_sticker_attachment(
                self.root,
                "aike_act_cute_001",
                0,
                limits=self.approval.StickerLimits(),
                sender=sender,
            )
        )
        unknown = asyncio.run(
            self.module.send_selected_sticker_attachment(
                self.root,
                "missing",
                10001,
                limits=self.approval.StickerLimits(),
                sender=sender,
            )
        )
        approved = next((self.root / "approved").iterdir())
        approved.write_bytes(b"tampered")
        tampered = asyncio.run(
            self.module.send_selected_sticker_attachment(
                self.root,
                "aike_act_cute_001",
                10001,
                limits=self.approval.StickerLimits(),
                sender=sender,
            )
        )

        self.assertEqual(invalid_recipient.status, "invalid_recipient")
        self.assertEqual(unknown.status, "asset_sticker_not_found")
        self.assertIn(
            tampered.status,
            {"asset_library_validation_failed", "asset_asset_validation_failed"},
        )
        self.assertEqual(calls, 0)

    def test_module_has_no_nonebot_network_database_or_model_dependency(self):
        source = (AI_CHAT_ROOT / "sticker_attachment.py").read_text(
            encoding="utf-8"
        ).lower()
        for forbidden in (
            "nonebot",
            "messagesegment",
            "send_private_msg",
            "httpx",
            "openai",
            "tavily",
            "sqlite",
            "database",
            "ask_llm",
        ):
            self.assertNotIn(forbidden, source)

    def test_b2_runtime_is_owner_private_single_send_and_commits_after_success(self):
        source = (AI_CHAT_ROOT / "__init__.py").read_text(encoding="utf-8")
        sender_start = source.index("async def _maybe_send_remote_sticker_attachment(")
        sender_end = source.index("def schedule_remote_sticker_classifier_shadow(", sender_start)
        sender = source[sender_start:sender_end]

        self.assertIn("if not config.enable_chat_sticker_attachments", sender)
        self.assertIn("_chat_sticker_attachments_suspended", sender)
        self.assertIn("send_selected_sticker_attachment(", sender)
        self.assertIn('"send_private_msg"', sender)
        self.assertIn("MessageSegment.image(str(file_path))", sender)
        self.assertEqual(sender.count("await bot.call_api("), 1)
        send_call = sender.index("send_result = await send_selected_sticker_attachment(")
        sent_gate = sender.index("if not send_result.sent:", send_call)
        commit = sender.index("_chat_sticker_selection_runtime.commit_sent(", sent_gate)
        self.assertLess(send_call, sent_gate)
        self.assertLess(sent_gate, commit)
        for forbidden in ("while ", "retry", "Tavily", "ask_llm"):
            self.assertNotIn(forbidden, sender)

        scheduler_start = source.index("def schedule_remote_sticker_classifier_shadow(")
        scheduler_end = source.index("async def generate_chat_text_response(", scheduler_start)
        scheduler = source[scheduler_start:scheduler_end]
        self.assertIn("isinstance(event, PrivateMessageEvent)", scheduler)
        self.assertIn("is_owner(config, event)", scheduler)

        for function_name in ("render_chat_result", "finalize_chat_result"):
            start = source.index(f"async def {function_name}(")
            end = source.index("\n\nasync def ", start + 10)
            block = source[start:end]
            self.assertLess(
                block.index("await matcher.send(result.reply)"),
                block.index("schedule_remote_sticker_classifier_shadow("),
            )


if __name__ == "__main__":
    unittest.main()
