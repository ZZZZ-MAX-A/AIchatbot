from __future__ import annotations

import base64
import json
import unittest

from pure_ai_chat_loader import AI_CHAT_ROOT, load_sticker_labeling_module


class StickerLabelingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_sticker_labeling_module()
        cls.sheet = cls.module.StickerContactSheet(
            png_bytes=b"\x89PNG\r\n\x1a\nunit",
            frame_indices=(0, 2, 4),
            source_frame_count=5,
            width=256,
            height=256,
        )

    @staticmethod
    def response(**overrides: object) -> str:
        payload: dict[str, object] = {
            "moods": ["shy", "embarrassed"],
            "intensity": "medium",
            "actions": ["blush", "look_away"],
            "suggested_scenes": ["praise_received", "affection", "teasing"],
            "confidence": {"mood": 0.91, "intensity": 0.82, "scene": 0.76},
            "ambiguous": False,
        }
        payload.update(overrides)
        return json.dumps(payload)

    def assert_error_code(self, expected: str, callback) -> None:
        with self.assertRaises(self.module.StickerLabelingError) as raised:
            callback()
        self.assertEqual(raised.exception.code, expected)

    def test_high_confidence_suggestion_still_waits_for_owner_confirmation(self):
        suggestion = self.module.parse_sticker_label_suggestion(self.response())

        self.assertEqual(suggestion.moods, ("shy", "embarrassed"))
        self.assertEqual(suggestion.intensity, "medium")
        self.assertEqual(suggestion.actions, ("blush", "look_away"))
        self.assertEqual(suggestion.review_status, "suggested")
        self.assertFalse(suggestion.needs_owner_review)
        formatted = self.module.format_sticker_label_suggestion(suggestion)
        self.assertIn("高置信度待主人确认", formatted)
        self.assertIn("未写入正式标签", formatted)

    def test_low_confidence_mixed_or_ambiguous_suggestion_requires_owner_review(self):
        cases = (
            {"confidence": {"mood": 0.84, "intensity": 0.90, "scene": 0.90}},
            {"confidence": {"mood": 0.90, "intensity": 0.74, "scene": 0.90}},
            {"confidence": {"mood": 0.90, "intensity": 0.90, "scene": 0.69}},
            {"moods": ["mixed"], "ambiguous": True},
            {"ambiguous": True},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                suggestion = self.module.parse_sticker_label_suggestion(
                    self.response(**overrides)
                )
                self.assertTrue(suggestion.needs_owner_review)
                self.assertEqual(suggestion.review_status, "needs_owner_review")

    def test_unknown_labels_duplicates_and_invalid_confidence_are_rejected(self):
        cases = (
            ({"moods": ["unknown"]}, "invalid_moods"),
            ({"actions": ["blush", "blush"]}, "invalid_actions"),
            ({"suggested_scenes": ["private_path"]}, "invalid_suggested_scenes"),
            ({"intensity": "extreme"}, "invalid_intensity"),
            (
                {"confidence": {"mood": 1.1, "intensity": 0.8, "scene": 0.8}},
                "invalid_mood_confidence",
            ),
            ({"ambiguous": "false"}, "invalid_ambiguous"),
        )
        for overrides, expected in cases:
            with self.subTest(expected=expected):
                self.assert_error_code(
                    expected,
                    lambda overrides=overrides: self.module.parse_sticker_label_suggestion(
                        self.response(**overrides)
                    ),
                )

    def test_json_fence_is_tolerated_but_extra_text_is_rejected(self):
        fenced = f"```json\n{self.response()}\n```"
        suggestion = self.module.parse_sticker_label_suggestion(fenced)
        self.assertEqual(suggestion.intensity, "medium")
        self.assert_error_code(
            "label_response_invalid_json",
            lambda: self.module.parse_sticker_label_suggestion(
                "analysis: " + self.response()
            ),
        )

    def test_fake_local_vision_call_receives_png_and_fixed_prompt(self):
        captured: dict[str, object] = {}

        def fake_call(config, image_base64: str, prompt: str) -> str:
            captured["config"] = config
            captured["image"] = base64.b64decode(image_base64)
            captured["prompt"] = prompt
            return self.response()

        config = object()
        suggestion = self.module.analyze_sticker_contact_sheet(
            config,
            self.sheet,
            vision_call=fake_call,
        )

        self.assertIs(captured["config"], config)
        self.assertEqual(captured["image"], self.sheet.png_bytes)
        self.assertIn("只输出一个 JSON", captured["prompt"])
        self.assertNotIn("explicit_sticker_request", captured["prompt"])
        self.assertEqual(suggestion.moods[0], "shy")

    def test_owner_calibrated_labels_and_visual_rules_are_fixed(self):
        self.assertTrue(
            {
                "attentive",
                "curious",
                "dizzy",
                "expectant",
                "hurt",
                "playful",
                "pleading",
                "resigned",
            }
            <= self.module.ALLOWED_STICKER_MOODS
        )
        self.assertTrue(
            {
                "act_cute",
                "drink_milk_tea",
                "drive",
                "exclamation_mark",
                "get_hit",
                "hands_together",
                "lick",
                "lie_flat",
                "offer_cake",
                "offer_gift",
                "peek",
                "show_heart",
                "soul_leave_body",
                "sway",
                "take_notes",
                "take_photo",
                "type_angrily",
            }
            <= self.module.ALLOWED_STICKER_ACTIONS
        )
        self.assertTrue(
            {
                "acting_cute",
                "attention_seeking",
                "checking_reaction",
                "continue_speaking",
                "departure",
                "giving_up",
                "holding_grudge",
                "joining_chat",
                "listening",
                "pleasing",
                "recording",
                "remembering",
                "request",
                "setback",
                "sharing_snack",
            }
            <= self.module.ALLOWED_STICKER_SCENES
        )
        prompt = self.module.STICKER_LABELING_PROMPT
        self.assertIn("仅凭张大嘴不能判断为 yawn", prompt)
        self.assertIn("第 3、4 类探头画面应允许归入相同场景", prompt)
        self.assertIn("这类含义允许覆盖“撒娇”和“拜托”", prompt)
        self.assertIn("不得作为不确定时的默认答案", prompt)
        self.assertIn("即“请继续说下去”", prompt)
        self.assertIn("表示拍照记录", prompt)
        self.assertIn("用于生日祝福和共同分享", prompt)
        self.assertIn("普通倾听/“我记住了”", prompt)
        self.assertIn("握方向盘表达出发", prompt)
        self.assertIn("螺旋眼并摇晃", prompt)
        self.assertIn("不得只根据键盘本身推断生气", prompt)

        suggestion = self.module.parse_sticker_label_suggestion(
            self.response(
                moods=["playful"],
                actions=["act_cute"],
                suggested_scenes=["acting_cute"],
            )
        )
        self.assertEqual(suggestion.moods, ("playful",))
        self.assertEqual(suggestion.actions, ("act_cute",))
        self.assertEqual(suggestion.suggested_scenes, ("acting_cute",))

    def test_vision_failure_and_non_string_response_fail_closed(self):
        def failing_call(_config, _image: str, _prompt: str) -> str:
            raise RuntimeError("private local path")

        self.assert_error_code(
            "label_vision_unavailable",
            lambda: self.module.analyze_sticker_contact_sheet(
                object(),
                self.sheet,
                vision_call=failing_call,
            ),
        )
        self.assert_error_code(
            "label_response_invalid_type",
            lambda: self.module.analyze_sticker_contact_sheet(
                object(),
                self.sheet,
                vision_call=lambda *_args: object(),
            ),
        )

    def test_labeling_module_has_no_database_tavily_or_write_dependency(self):
        source = (AI_CHAT_ROOT / "sticker_labeling.py").read_text(encoding="utf-8").lower()
        for forbidden in (
            "tavily",
            "sqlite",
            "database",
            "nonebot",
            "send_private_msg",
            "messagesegment",
            "write_text",
            "write_bytes",
            "library.json",
            "unlink",
            "replace(",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
