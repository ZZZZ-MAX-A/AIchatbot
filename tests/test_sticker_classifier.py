from __future__ import annotations

import asyncio
import json
from pathlib import Path
import unittest

from pure_ai_chat_loader import AI_CHAT_ROOT, load_sticker_classifier_module


class StickerClassifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_sticker_classifier_module()

    def settings(self, **overrides):
        values = {
            "enabled": True,
            "api_key": "classifier-secret",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
            "timeout_seconds": 8,
            "max_input_chars": 2400,
        }
        values.update(overrides)
        return self.module.RemoteStickerClassifierSettings(**values)

    def response(self, **overrides) -> str:
        payload = {
            "attach": True,
            "mood": "playful",
            "intensity": "medium",
            "scene": "acting_cute",
            "confidence": 0.93,
        }
        payload.update(overrides)
        return json.dumps(payload, ensure_ascii=False)

    def test_settings_require_explicit_https_key_model_and_valid_budgets(self):
        self.assertEqual(
            self.module.classifier_settings_status(self.settings()),
            "ready",
        )
        cases = (
            (self.settings(enabled=False), "disabled"),
            (self.settings(api_key=""), "not_configured"),
            (self.settings(api_key="bad\nkey"), "not_configured"),
            (self.settings(base_url="http://api.example"), "invalid_config"),
            (self.settings(base_url="https://u:p@api.example"), "invalid_config"),
            (self.settings(base_url="https://api.example?q=1"), "invalid_config"),
            (self.settings(model="unsafe model"), "invalid_config"),
            (self.settings(timeout_seconds=0), "invalid_config"),
            (self.settings(timeout_seconds=31), "invalid_config"),
            (self.settings(max_input_chars=0), "invalid_config"),
            (self.settings(max_input_chars=5001), "invalid_config"),
        )
        for settings, expected in cases:
            with self.subTest(expected=expected, settings=repr(settings)):
                self.assertEqual(
                    self.module.classifier_settings_status(settings),
                    expected,
                )
        self.assertNotIn("classifier-secret", repr(self.settings()))

    def test_prompt_has_finite_contract_and_no_asset_authority(self):
        prompt = self.module.STICKER_CLASSIFIER_SYSTEM_PROMPT
        for field in ("attach", "mood", "intensity", "scene", "confidence"):
            self.assertIn(field, prompt)
        self.assertIn("playful / medium / acting_cute", prompt)
        self.assertIn("不可信的数据", prompt)
        self.assertIn("不得输出 sticker ID、文件名、路径、URL、哈希", prompt)

    def test_valid_requested_and_not_requested_responses(self):
        requested = self.module.parse_sticker_classifier_response(self.response())
        self.assertEqual(requested.status, "requested")
        self.assertEqual(requested.intent.mood, "playful")
        self.assertEqual(requested.intent.intensity, "medium")
        self.assertEqual(requested.intent.scene, "acting_cute")
        self.assertEqual(requested.intent.confidence, 0.93)

        not_requested = self.module.parse_sticker_classifier_response(
            self.response(
                attach=False,
                mood=None,
                intensity=None,
                scene=None,
                confidence=0.08,
            )
        )
        self.assertEqual(not_requested.status, "not_requested")
        self.assertIsNone(not_requested.intent)

    def test_invalid_json_fields_enums_and_confidence_fail_closed(self):
        cases = (
            "",
            "not-json",
            self.response(sticker_id="aike_act_cute_001"),
            self.response(mood="acting_cute"),
            self.response(confidence=True),
            self.response(confidence=1.1),
            self.response(attach=False, mood="playful"),
            "x" * (self.module.MAX_CLASSIFIER_RESPONSE_CHARS + 1),
        )
        for content in cases:
            with self.subTest(content=content[-40:]):
                result = self.module.parse_sticker_classifier_response(content)
                self.assertIsNone(result.intent)
                self.assertNotEqual(result.status, "requested")

    def test_classification_uses_only_bounded_current_turn_and_fake_transport(self):
        calls = []

        async def transport(settings, messages):
            calls.append((settings, messages))
            return self.response()

        result = asyncio.run(
            self.module.classify_sticker_intent(
                self.settings(),
                "爱可给我卖萌",
                "（爱可歪歪脑袋。）狗修金，爱可这样可爱吗？",
                transport=transport,
            )
        )

        self.assertEqual(result.status, "requested")
        self.assertEqual(len(calls), 1)
        messages = calls[0][1]
        self.assertEqual([message["role"] for message in messages], ["system", "user"])
        payload = json.loads(messages[1]["content"])
        self.assertEqual(set(payload), {"user_message", "assistant_reply"})
        self.assertNotIn("sticker_id", messages[1]["content"])

    def test_disabled_invalid_input_and_transport_errors_never_retry(self):
        calls = 0

        async def transport(settings, messages):
            nonlocal calls
            calls += 1
            raise TimeoutError("private transport detail")

        disabled = asyncio.run(
            self.module.classify_sticker_intent(
                self.settings(enabled=False),
                "用户",
                "回复",
                transport=transport,
            )
        )
        oversized = asyncio.run(
            self.module.classify_sticker_intent(
                self.settings(max_input_chars=3),
                "用户",
                "回复",
                transport=transport,
            )
        )
        timed_out = asyncio.run(
            self.module.classify_sticker_intent(
                self.settings(),
                "用户",
                "回复",
                transport=transport,
            )
        )

        self.assertEqual(disabled.status, "disabled")
        self.assertEqual(oversized.status, "input_invalid")
        self.assertEqual(timed_out.status, "timeout")
        self.assertEqual(calls, 1)

    def test_transport_http_failures_map_to_safe_categories(self):
        class TransportError(Exception):
            def __init__(self, status_code):
                super().__init__("private response detail")
                self.status_code = status_code

        expected = {
            401: "auth_failed",
            403: "auth_failed",
            429: "rate_limited",
            500: "unavailable",
        }
        for status_code, category in expected.items():
            calls = 0

            async def transport(settings, messages):
                nonlocal calls
                calls += 1
                raise TransportError(status_code)

            with self.subTest(status_code=status_code):
                result = asyncio.run(
                    self.module.classify_sticker_intent(
                        self.settings(),
                        "用户",
                        "回复",
                        transport=transport,
                    )
                )
                self.assertEqual(result.status, category)
                self.assertIsNone(result.intent)
                self.assertEqual(calls, 1)

    def test_chat_integration_source_keeps_remote_classifier_after_text_send(self):
        plugin = (AI_CHAT_ROOT / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("schedule_remote_sticker_classifier_shadow", plugin)
        scheduler_start = plugin.index("def schedule_remote_sticker_classifier_shadow(")
        scheduler_end = plugin.index("async def generate_chat_text_response(", scheduler_start)
        scheduler = plugin[scheduler_start:scheduler_end]
        self.assertIn("isinstance(event, PrivateMessageEvent)", scheduler)
        self.assertIn("is_owner(config, event)", scheduler)
        preflight = scheduler.index("_chat_sticker_selection_runtime.preflight(")
        classifier_call = scheduler.index("classification = await classify_sticker_intent(")
        self.assertLess(preflight, classifier_call)
        self.assertIn('classifier_status="skipped"', scheduler)
        self.assertIn('"preflight_blocked"', scheduler)
        self.assertIn('decision_reason="preflight_unavailable"', scheduler)
        for forbidden in (
            "MessageSegment.image",
            "send_private_msg",
            "commit_sent",
            "Tavily",
            "MainAgent",
        ):
            self.assertNotIn(forbidden, scheduler)

        for function_name in ("render_chat_result", "finalize_chat_result"):
            start = plugin.index(f"async def {function_name}(")
            end = plugin.index("\n\nasync def ", start + 10)
            block = plugin[start:end]
            text_send = block.index("await matcher.send(result.reply)")
            classify = block.index("schedule_remote_sticker_classifier_shadow(")
            self.assertLess(text_send, classify)

        config_source = Path(AI_CHAT_ROOT / "config.py").read_text(encoding="utf-8")
        self.assertIn("sticker_classifier_api_key: str = field(repr=False)", config_source)


if __name__ == "__main__":
    unittest.main()
