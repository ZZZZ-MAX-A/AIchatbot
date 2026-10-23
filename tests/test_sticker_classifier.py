from __future__ import annotations

import asyncio
import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from openai import AsyncOpenAI as RealAsyncOpenAI

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

    def test_owner_corrected_moods_and_thinking_scene_survive_contract_parsing(self):
        for mood, intensity, scene in [('proud', 'soft', 'praise_received'),
                                       ('flustered', 'strong', 'unexpected_statement'),
                                       ('neutral', 'soft', 'thinking')]:
            with self.subTest(mood=mood, scene=scene):
                parsed = self.module.parse_sticker_classifier_response(
                    self.response(mood=mood, intensity=intensity, scene=scene))
                self.assertEqual(parsed.status, 'requested')
                self.assertEqual((parsed.intent.mood, parsed.intent.intensity, parsed.intent.scene),
                                 (mood, intensity, scene))

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
        empty_user = asyncio.run(
            self.module.classify_sticker_intent(
                self.settings(),
                "",
                "回复",
                transport=transport,
            )
        )
        wrong_type = asyncio.run(
            self.module.classify_sticker_intent(
                self.settings(),
                None,
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
        self.assertEqual(empty_user.status, "input_invalid")
        self.assertEqual(wrong_type.status, "input_invalid")
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

    def test_attachment_status_text_distinguishes_empty_image_from_rate_gates(self):
        format_status = self.module.format_remote_sticker_attachment_status
        self.assertEqual(
            format_status("preflight_blocked", "empty_user_text"),
            "纯图片无文本，已在本地跳过；未调用分类模型，未发送表情",
        )
        for reason in (
            "cooldown",
            "message_gap",
            "hourly_cap",
            "preflight_unavailable",
        ):
            with self.subTest(reason=reason):
                self.assertEqual(
                    format_status("preflight_blocked", reason),
                    "频率门控中，未调用分类模型",
                )
        self.assertEqual(format_status("sent", "empty_user_text"), "已发送")
        self.assertEqual(
            format_status("future_status", "future_reason"),
            "未发送（future_status）",
        )

    def test_chat_integration_source_keeps_remote_classifier_after_text_send(self):
        plugin = (AI_CHAT_ROOT / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("schedule_remote_sticker_classifier_shadow", plugin)
        scheduler_start = plugin.index("def schedule_remote_sticker_classifier_shadow(")
        scheduler_end = plugin.index("async def generate_chat_text_response(", scheduler_start)
        scheduler = plugin[scheduler_start:scheduler_end]
        self.assertIn("isinstance(event, PrivateMessageEvent)", scheduler)
        self.assertIn("is_owner(config, event)", scheduler)
        empty_text_gate = scheduler.index(
            "if isinstance(user_text, str) and not user_text.strip():"
        )
        preflight = scheduler.index("_chat_sticker_selection_runtime.preflight(")
        classifier_call = scheduler.index("classification = await classify_sticker_intent(")
        self.assertLess(empty_text_gate, preflight)
        self.assertLess(preflight, classifier_call)
        empty_text_block = scheduler[empty_text_gate:preflight]
        self.assertIn('save_status("skipped", "empty_user_text")', empty_text_block)
        self.assertIn("return", empty_text_block)
        self.assertNotIn("classify_sticker_intent", empty_text_block)
        self.assertNotIn("_record_remote_sticker_classifier_reliability", empty_text_block)
        self.assertNotIn("_maybe_send_remote_sticker_attachment", empty_text_block)
        self.assertIn('"preflight_blocked"', scheduler)
        self.assertIn('save_status("skipped", "preflight_unavailable")', scheduler)
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
            text_send = block.index("await send_chat_reply_bubbles(")
            classify = block.index("schedule_chat_reply_sticker(")
            self.assertLess(text_send, classify)

        config_source = Path(AI_CHAT_ROOT / "config.py").read_text(encoding="utf-8")
        self.assertIn("sticker_classifier_api_key: str = field(repr=False)", config_source)

    def test_complete_code_fence_is_normalized_but_surrounding_prose_is_rejected(self):
        parsed = self.module.parse_sticker_classifier_response("\ufeff```json\n" + self.response() + "\n```")
        self.assertEqual(parsed.status, "requested")
        self.assertTrue(parsed.normalized_code_fence)
        self.assertGreater(parsed.response_chars, 0)
        for content in ("Here is JSON: " + self.response(), "```json\n" + self.response() + "\n```\nextra"):
            self.assertEqual(self.module.parse_sticker_classifier_response(content).status, "json_invalid")

    def test_duplicate_nonfinite_and_extreme_numeric_fields_are_rejected(self):
        for content in (
            self.response().replace('"attach": true', '"attach": false, "attach": true'),
            self.response(confidence=float('nan')),
            self.response(confidence=float('inf')),
            self.response(confidence=10 ** 350),
        ):
            with self.subTest(content=content[:20]):
                self.assertEqual(self.module.parse_sticker_classifier_response(content).status, "contract_invalid")

    def test_actual_combinations_constrain_prompt_and_reject_unavailable_intents(self):
        options = (("happy", "medium", "general_reaction"),)
        captured = []
        async def transport(settings, messages):
            captured.append(messages)
            return self.response()
        result = asyncio.run(self.module.classify_sticker_intent(
            self.settings(), "用户", "回复", transport=transport, available_combinations=options,
        ))
        self.assertEqual(result.status, "unsupported_combination")
        self.assertIsNone(result.intent)
        self.assertIn('"scenes":["general_reaction"]', captured[0][0]['content'])
        self.assertEqual(set(json.loads(captured[0][1]['content'])), {"user_message", "assistant_reply"})

    def test_empty_library_skips_request_and_does_not_force_any_image(self):
        transport = AsyncMock()
        result = asyncio.run(self.module.classify_sticker_intent(
            self.settings(), "用户", "回复", transport=transport, available_combinations=(),
        ))
        self.assertEqual(result.status, "no_available_stickers")
        transport.assert_not_called()

    def test_finish_reason_distinguishes_truncation_and_filter_without_parsing_partial_result(self):
        for reason, expected in [("length", "response_truncated"), ("content_filter", "response_filtered"), ("stop", "requested")]:
            async def transport(settings, messages):
                return self.module.StickerClassifierResponse(self.response(), reason)
            result = asyncio.run(self.module.classify_sticker_intent(self.settings(), "用户", "回复", transport=transport))
            self.assertEqual(result.status, expected)
            self.assertEqual(result.finish_reason, reason)
            self.assertGreater(result.response_chars, 0)
            self.assertNotIn('"attach"', repr(result))

    def test_arbitrary_finish_reason_is_not_retained_in_diagnostics(self):
        async def transport(settings, messages):
            return self.module.StickerClassifierResponse("", "private output detail")
        result = asyncio.run(self.module.classify_sticker_intent(self.settings(), "用户", "回复", transport=transport))
        self.assertEqual(result.finish_reason, "unknown")
        self.assertNotIn("private output detail", repr(result))

    def test_request_budget_applies_even_when_transport_ignores_sdk_timeout(self):
        cancelled = []
        async def transport(settings, messages):
            try:
                await asyncio.sleep(30)
            finally:
                cancelled.append(True)
        result = asyncio.run(self.module.classify_sticker_intent(self.settings(timeout_seconds=1), "用户", "回复", transport=transport))
        self.assertEqual(result.status, "timeout")
        self.assertEqual(cancelled, [True])
        self.assertTrue(result.diagnostics.request_started)
        self.assertEqual(result.diagnostics.max_tokens, 500)
        self.assertEqual(result.diagnostics.timeout_ms, 1000)
        self.assertGreaterEqual(result.diagnostics.elapsed_ms, 900)
        self.assertIsNone(result.diagnostics.completion_tokens)

    def test_actual_sdk_preserves_usage_for_truncation_success_and_missing_fields(self):
        async def run_case(mode):
            payloads = []
            response = {
                'id': 'unit', 'object': 'chat.completion', 'created': 0, 'model': 'deepseek-v4-flash',
                'choices': [{'index': 0, 'finish_reason': 'length' if mode == 'truncated' else 'stop',
                             'message': {'role': 'assistant', 'content': '' if mode == 'truncated' else self.response(),
                                         'reasoning_content': 'PRIVATE-REASONING'}}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 500, 'total_tokens': 600,
                          'completion_tokens_details': {'reasoning_tokens': 500}},
            }
            if mode == 'missing':
                response.pop('usage')
                response['choices'][0]['message'].pop('reasoning_content')
            if mode == 'zero':
                response['usage']['completion_tokens_details']['reasoning_tokens'] = 0
                response['choices'][0]['message']['reasoning_content'] = ''
            if mode == 'no_choices':
                response['choices'] = []
            def handler(request):
                payloads.append(json.loads(request.content))
                return httpx.Response(200, json=response)
            def client(**options):
                return RealAsyncOpenAI(**options, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
            with patch.object(self.module, 'AsyncOpenAI', side_effect=client):
                result = await self.module.classify_sticker_intent(self.settings(), 'PRIVATE-USER', 'PRIVATE-REPLY')
            self.assertEqual(len(payloads), 1)
            self.assertEqual(payloads[0]['max_tokens'], 500)
            self.assertNotIn('thinking', payloads[0])
            self.assertNotIn('reasoning_effort', payloads[0])
            self.assertEqual(payloads[0]['response_format'], {'type': 'json_object'})
            diagnostics = result.diagnostics
            self.assertTrue(diagnostics.request_started)
            self.assertEqual(diagnostics.max_tokens, 500)
            self.assertEqual(diagnostics.timeout_ms, 8000)
            self.assertGreaterEqual(diagnostics.elapsed_ms, 0)
            if mode == 'missing':
                self.assertIsNone(diagnostics.completion_tokens)
                self.assertIsNone(diagnostics.reasoning_tokens)
                self.assertIsNone(diagnostics.reasoning_chars)
            else:
                self.assertEqual(diagnostics.prompt_tokens, 100)
                self.assertEqual(diagnostics.completion_tokens, 500)
                self.assertEqual(diagnostics.total_tokens, 600)
                self.assertEqual(diagnostics.reasoning_tokens, 0 if mode == 'zero' else 500)
                self.assertEqual(diagnostics.reasoning_chars,
                                 None if mode == 'no_choices' else 0 if mode == 'zero' else len('PRIVATE-REASONING'))
            self.assertEqual(result.status, 'response_truncated' if mode == 'truncated'
                             else 'empty_response' if mode == 'no_choices' else 'requested')
            if mode == 'truncated':
                self.assertEqual(result.response_chars, 0)
                self.assertIsNone(result.intent)
            rendered = self.module.format_sticker_classifier_diagnostics(diagnostics)
            for private in ('PRIVATE-REASONING', 'PRIVATE-USER', 'PRIVATE-REPLY', 'classifier-secret'):
                self.assertNotIn(private, repr(result))
                self.assertNotIn(private, rendered)
        for mode in ('truncated', 'success', 'missing', 'zero', 'no_choices'):
            with self.subTest(mode=mode):
                asyncio.run(run_case(mode))

    def test_invalid_usage_values_are_not_retained_or_rendered(self):
        async def transport(settings, messages):
            return self.module.StickerClassifierResponse(self.response(), 'stop',
                diagnostics=self.module.StickerClassifierDiagnostics(
                    prompt_tokens='PRIVATE-USAGE', completion_tokens=-1, total_tokens=True,
                    reasoning_tokens=1.5, reasoning_chars=10**20))
        result = asyncio.run(self.module.classify_sticker_intent(
            self.settings(), '用户', '回复', transport=transport))
        for name in ('prompt_tokens', 'completion_tokens', 'total_tokens', 'reasoning_tokens', 'reasoning_chars'):
            self.assertIsNone(getattr(result.diagnostics, name))
        self.assertNotIn('PRIVATE-USAGE', repr(result))

    def test_status_distinguishes_missing_zero_and_request_not_run(self):
        self.assertIn('未调用分类模型', self.module.format_sticker_classifier_diagnostics(None))
        self.assertIn('未调用分类模型', self.module.format_sticker_classifier_diagnostics(
            self.module.StickerClassifierDiagnostics()))
        diagnostics = self.module.StickerClassifierDiagnostics(
            request_started=True, max_tokens=500, timeout_ms=8000, elapsed_ms=25,
            completion_tokens=500, reasoning_tokens=0, reasoning_chars=0)
        text = self.module.format_sticker_classifier_diagnostics(diagnostics)
        self.assertIn('输入 未提供 / 输出 500 / 总计 未提供', text)
        self.assertIn('思考 token：0；思考内容：0 字符', text)
        self.assertIn('服务端默认', text)
        result = asyncio.run(self.module.classify_sticker_intent(
            self.settings(enabled=False), '用户', '回复', transport=AsyncMock()))
        self.assertFalse(result.diagnostics.request_started)

    def test_transport_failure_retains_request_settings_without_inventing_usage(self):
        async def transport(settings, messages):
            raise RuntimeError('PRIVATE-ERROR')
        result = asyncio.run(self.module.classify_sticker_intent(
            self.settings(), '用户', '回复', transport=transport))
        self.assertEqual(result.status, 'unavailable')
        self.assertEqual(result.diagnostics.max_tokens, 500)
        self.assertGreaterEqual(result.diagnostics.elapsed_ms, 0)
        self.assertIsNone(result.diagnostics.reasoning_tokens)
        self.assertNotIn('PRIVATE-ERROR', repr(result))

    def test_sdk_client_is_closed_on_success_error_and_cancellation(self):
        async def run_case(mode):
            entered = asyncio.Event()
            async def create(**kwargs):
                entered.set()
                if mode == "error":
                    raise TimeoutError("private service error")
                if mode == "cancel":
                    await asyncio.Event().wait()
                return SimpleNamespace(choices=[SimpleNamespace(
                    message=SimpleNamespace(content=self.response()), finish_reason="stop",
                )])
            client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)), close=AsyncMock())
            with patch.object(self.module, "AsyncOpenAI", return_value=client):
                task = asyncio.create_task(self.module._openai_compatible_transport(self.settings(), []))
                await entered.wait()
                if mode == "cancel":
                    task.cancel()
                try:
                    await task
                except (TimeoutError, asyncio.CancelledError):
                    pass
            client.close.assert_awaited_once()
        for mode in ("success", "error", "cancel"):
            asyncio.run(run_case(mode))


if __name__ == "__main__":
    unittest.main()
