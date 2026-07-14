from __future__ import annotations

import json
import unittest

from pure_ai_chat_loader import AI_CHAT_ROOT, load_sticker_intent_module


class StickerIntentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_sticker_intent_module()

    def marker(self, **overrides: object) -> str:
        payload: dict[str, object] = {
            "attach": True,
            "mood": "playful",
            "intensity": "medium",
            "scene": "acting_cute",
            "confidence": 0.91,
        }
        payload.update(overrides)
        return (
            self.module.STICKER_INTENT_START
            + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            + self.module.STICKER_INTENT_END
        )

    def test_valid_final_marker_is_stripped_and_parsed(self):
        extraction = self.module.extract_sticker_intent(
            "（爱可轻轻眨眼。）狗修金，爱可知道啦。\n" + self.marker()
        )

        self.assertEqual(extraction.status, "requested")
        self.assertEqual(extraction.visible_reply, "（爱可轻轻眨眼。）狗修金，爱可知道啦。")
        self.assertEqual(extraction.intent.mood, "playful")
        self.assertEqual(extraction.intent.intensity, "medium")
        self.assertEqual(extraction.intent.scene, "acting_cute")
        self.assertEqual(extraction.intent.confidence, 0.91)
        self.assertNotIn("STICKER_INTENT", extraction.visible_reply)

    def test_attach_false_is_stripped_without_creating_intent(self):
        extraction = self.module.extract_sticker_intent(
            "普通事实回答。\n" + self.marker(attach=False, confidence=0.2)
        )

        self.assertEqual(extraction.visible_reply, "普通事实回答。")
        self.assertIsNone(extraction.intent)
        self.assertEqual(extraction.status, "not_requested")

    def test_absent_marker_keeps_reply_unchanged(self):
        extraction = self.module.extract_sticker_intent("  正常回复。  ")
        self.assertEqual(extraction.visible_reply, "正常回复。")
        self.assertIsNone(extraction.intent)
        self.assertEqual(extraction.status, "marker_absent")

    def test_malformed_unknown_extra_or_nonfinal_marker_never_leaks(self):
        cases = (
            "正文\n[[STICKER_INTENT]]not-json[[/STICKER_INTENT]]",
            "正文\n" + self.marker(mood="unknown"),
            "正文\n" + self.marker(sticker_id="private_path"),
            "正文\n" + self.marker() + "\n额外文字",
            "正文\n[[/STICKER_INTENT]]",
        )
        for content in cases:
            with self.subTest(content=content[-40:]):
                extraction = self.module.extract_sticker_intent(content)
                self.assertEqual(extraction.visible_reply, "正文")
                self.assertIsNone(extraction.intent)
                self.assertNotIn("STICKER_INTENT", extraction.visible_reply)
                self.assertNotIn("private_path", extraction.visible_reply)

    def test_invalid_confidence_and_boolean_number_are_rejected(self):
        for confidence in (-0.1, 1.1, True, "0.9"):
            with self.subTest(confidence=confidence):
                extraction = self.module.extract_sticker_intent(
                    "正文\n" + self.marker(confidence=confidence)
                )
                self.assertIsNone(extraction.intent)
                self.assertEqual(extraction.status, "contract_invalid")

    def test_system_context_has_finite_contract_and_no_sticker_identifier_authority(self):
        prompt = self.module.STICKER_INTENT_SYSTEM_CONTEXT
        self.assertIn("attach", prompt)
        self.assertIn("mood", prompt)
        self.assertIn("intensity", prompt)
        self.assertIn("scene", prompt)
        self.assertIn("confidence", prompt)
        self.assertIn("不能选择 sticker ID、文件名、路径或 URL", prompt)
        self.assertIn("普通事实回答", prompt)
        self.assertIn("本地策略仍可能", prompt)

    def test_chat_integration_strips_before_storage_and_shadow_never_sends(self):
        plugin = (AI_CHAT_ROOT / "__init__.py").read_text(encoding="utf-8")
        llm_call = plugin.index("reply = await ask_llm(")
        extraction = plugin.index("extracted_intent = extract_sticker_intent(reply)", llm_call)
        result = plugin.index("result = ChatRuntimeResult(", extraction)
        shadow = plugin.index("await evaluate_chat_sticker_intent_shadow(", result)
        self.assertLess(llm_call, extraction)
        self.assertLess(extraction, result)
        self.assertLess(result, shadow)
        result_block = plugin[result:shadow]
        self.assertIn("reply=reply", result_block)
        self.assertIn("stored_assistant=reply", result_block)

        shadow_start = plugin.index("async def evaluate_chat_sticker_intent_shadow(")
        shadow_end = plugin.index("def remote_sticker_classifier_settings(", shadow_start)
        shadow_block = plugin[shadow_start:shadow_end]
        for forbidden in (
            "MessageSegment.image",
            "send_private_msg",
            "bot.call_api",
            "commit_sent",
            "Tavily",
        ):
            self.assertNotIn(forbidden, shadow_block)

        status_start = plugin.index("@sticker_intent_status_cmd.handle()")
        status_end = plugin.index("@help_cmd.handle()", status_start)
        status_block = plugin[status_start:status_end]
        self.assertIn("await require_owner(event, matcher)", status_block)
        self.assertIn("isinstance(event, PrivateMessageEvent)", status_block)
        self.assertIn("只观察，不发送", status_block)
        self.assertIn("自动附带：关闭", status_block)
        self.assertNotIn("MessageSegment.image", status_block)


if __name__ == "__main__":
    unittest.main()
