from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from pure_ai_chat_loader import ensure_ai_chat_packages, load_module, AI_CHAT_ROOT


class TopicSceneSwitchUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.mod = load_module(
            "src.plugins.ai_chat.topic_scene_switch",
            AI_CHAT_ROOT / "topic_scene_switch.py",
        )

    def setUp(self) -> None:
        self.mod.clear_topic_switch_runtime_for_tests()

    def test_detect_hard_triggers(self):
        for text in ["换个话题", " 新开一段 ", "先到这里。", "聊点别的！"]:
            intent = self.mod.detect_topic_switch_intent(text)
            self.assertIsNotNone(intent, text)

    def test_reject_embedded_trigger_in_long_line(self):
        text = "你刚才说换个话题，但我们还是继续刚才的姿势。"
        self.assertIsNone(self.mod.detect_topic_switch_intent(text))

    def test_format_prefix(self):
        body = "主人结束了一段亲密场景，无新的长期约定。"
        formatted = self.mod.format_topic_scene_summary(body)
        self.assertTrue(formatted.startswith(self.mod.TOPIC_SCENE_SUMMARY_PREFIX))
        self.assertIn(body, formatted)

    def test_hint_consume_counts_down(self):
        key = "persona:test:private:1"
        self.mod.mark_topic_switch_hint(key, turns=2)
        first = self.mod.consume_topic_switch_hint(key)
        second = self.mod.consume_topic_switch_hint(key)
        third = self.mod.consume_topic_switch_hint(key)
        self.assertTrue(first)
        self.assertTrue(second)
        self.assertEqual(third, "")

    def test_switch_summarize_failed_does_not_clear(self):
        # Lightweight structural test with mocks; skip if DB helpers unavailable.
        async def _run():
            config = type(
                "C",
                (),
                {
                    "enable_topic_scene_switch": True,
                    "topic_scene_switch_private_only": True,
                    "topic_scene_min_source_messages": 1,
                    "topic_scene_hint_turns": 3,
                    "bot_owner_qq": "1",
                },
            )()
            rows = [
                {
                    "id": 1,
                    "message_type": "private",
                    "user_id": "1",
                    "group_id": None,
                    "role": "user",
                    "content": "你好",
                },
                {
                    "id": 2,
                    "message_type": "private",
                    "user_id": "1",
                    "group_id": None,
                    "role": "assistant",
                    "content": "我在",
                },
            ]
            with patch.object(self.mod, "_list_session_messages", return_value=rows), patch.object(
                self.mod,
                "summarize_topic_scene_messages",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ), patch.object(self.mod, "clear_session") as clear_mock:
                result = await self.mod.switch_topic_scene(config, "sess-a")
            self.assertFalse(result.ok)
            self.assertEqual(result.reason_code, "summarize_failed")
            self.assertFalse(result.cleared_messages)
            clear_mock.assert_not_called()

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
