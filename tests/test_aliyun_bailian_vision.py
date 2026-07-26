from __future__ import annotations

import base64
import json
import types
import unittest

import httpx

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module


PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z6Sg"
    "AAAAASUVORK5CYII="
)


class AliyunBailianVisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.module = load_module(
            "src.plugins.ai_chat.aliyun_bailian_vision",
            AI_CHAT_ROOT / "aliyun_bailian_vision.py",
        )

    @staticmethod
    def config(**overrides):
        values = {
            "vision_provider": "aliyun_bailian",
            "vision_cloud_model": "qwen3.7-flash",
            "aliyun_bailian_base_url": (
                "https://ws-unit123.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
            ),
            "aliyun_bailian_api_key": "unit-secret-key",
            "vision_timeout_seconds": 180,
            "vision_max_image_bytes": 1024,
        }
        values.update(overrides)
        return types.SimpleNamespace(**values)

    @staticmethod
    def response_payload(
        *,
        content: str = "</think>这是一张可爱的卡通人物图片，角色双手捧着爱心。",
        model: str = "qwen3.7-flash",
    ) -> dict[str, object]:
        return {
            "model": model,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": content,
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 12,
                "total_tokens": 32,
            },
        }

    def test_success_uses_fixed_contract_once_and_cleans_think_close(self):
        captured: dict[str, object] = {"request_count": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request_count"] = int(captured["request_count"]) + 1
            captured["url"] = str(request.url)
            captured["authorization"] = request.headers.get("authorization")
            captured["payload"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json=self.response_payload())

        result = self.module.request_aliyun_bailian_vision(
            self.config(),
            PNG_BASE64,
            "请描述这张图片。",
            transport=httpx.MockTransport(handler),
        )

        self.assertEqual(captured["request_count"], 1)
        self.assertEqual(
            captured["url"],
            "https://ws-unit123.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions",
        )
        self.assertEqual(captured["authorization"], "Bearer unit-secret-key")
        payload = captured["payload"]
        self.assertEqual(payload["model"], "qwen3.7-flash")
        self.assertEqual(payload["max_tokens"], 256)
        self.assertEqual(payload["temperature"], 0)
        self.assertFalse(payload["enable_thinking"])
        self.assertNotIn("tools", payload)
        image_url = payload["messages"][0]["content"][0]["image_url"]["url"]
        self.assertTrue(image_url.startswith("data:image/png;base64,"))
        self.assertTrue(result.response_cleanup_applied)
        self.assertFalse(result.content.startswith("</think>"))
        self.assertEqual(result.total_tokens, 32)
        self.assertEqual(result.request_count, 1)
        self.assertFalse(result.client_automatic_retry)
        self.assertNotIn("unit-secret-key", repr(result))
        self.assertNotIn(image_url, repr(result))

    def test_complete_leading_think_block_is_removed_but_body_marker_is_preserved(self):
        clean = self.module.clean_bailian_response_content

        self.assertEqual(
            clean("<think>内部推理</think>这是明确可见的中文图片描述。"),
            ("这是明确可见的中文图片描述。", True),
        )
        self.assertEqual(
            clean("这是普通正文，包含 </think> 字样但不在开头。"),
            ("这是普通正文，包含 </think> 字样但不在开头。", False),
        )

    def test_missing_or_invalid_configuration_fails_before_transport(self):
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(500)

        transport = httpx.MockTransport(handler)
        invalid_configs = (
            self.config(aliyun_bailian_api_key=""),
            self.config(aliyun_bailian_base_url="https://example.test/v1"),
            self.config(vision_provider="ollama"),
            self.config(vision_cloud_model="qwen3.7-plus"),
        )
        for config in invalid_configs:
            with self.assertRaises(self.module.AliyunBailianVisionError):
                self.module.request_aliyun_bailian_vision(
                    config,
                    PNG_BASE64,
                    "请描述这张图片。",
                    transport=transport,
                )

        self.assertEqual(calls, 0)

    def test_authentication_failure_does_not_expose_provider_body_or_key(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                401,
                text="invalid unit-secret-key at private-provider-endpoint",
            )

        with self.assertRaises(self.module.AliyunBailianVisionError) as caught:
            self.module.request_aliyun_bailian_vision(
                self.config(),
                PNG_BASE64,
                "请描述这张图片。",
                transport=httpx.MockTransport(handler),
            )

        self.assertEqual(caught.exception.code, "cloud_vision_authentication_failed")
        self.assertNotIn("unit-secret-key", str(caught.exception))
        self.assertNotIn("private-provider-endpoint", str(caught.exception))

    def test_timeout_is_fixed_and_not_retried(self):
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            raise httpx.ReadTimeout("secret timeout detail", request=request)

        with self.assertRaises(self.module.AliyunBailianVisionError) as caught:
            self.module.request_aliyun_bailian_vision(
                self.config(),
                PNG_BASE64,
                "请描述这张图片。",
                transport=httpx.MockTransport(handler),
            )

        self.assertEqual(calls, 1)
        self.assertEqual(caught.exception.code, "cloud_vision_request_timeout")
        self.assertNotIn("secret timeout detail", str(caught.exception))

    def test_invalid_image_and_response_contracts_fail_closed(self):
        calls = 0

        def success_handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, json=self.response_payload())

        with self.assertRaises(self.module.AliyunBailianVisionError):
            self.module.request_aliyun_bailian_vision(
                self.config(),
                base64.b64encode(b"not-an-image").decode("ascii"),
                "请描述这张图片。",
                transport=httpx.MockTransport(success_handler),
            )
        self.assertEqual(calls, 0)

        payloads = (
            self.response_payload(content="短"),
            self.response_payload(model="qwen3.7-plus"),
            {
                **self.response_payload(),
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 12,
                    "total_tokens": 99,
                },
            },
        )
        for payload in payloads:
            with self.assertRaises(self.module.AliyunBailianVisionError):
                self.module.request_aliyun_bailian_vision(
                    self.config(),
                    PNG_BASE64,
                    "请描述这张图片。",
                    transport=httpx.MockTransport(
                        lambda request, value=payload: httpx.Response(200, json=value)
                    ),
                )

    def test_tool_calls_are_rejected(self):
        payload = self.response_payload()
        payload["choices"][0]["message"]["tool_calls"] = [{"id": "unsafe"}]

        with self.assertRaises(self.module.AliyunBailianVisionError) as caught:
            self.module.request_aliyun_bailian_vision(
                self.config(),
                PNG_BASE64,
                "请描述这张图片。",
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, json=payload)
                ),
            )

        self.assertEqual(caught.exception.code, "cloud_vision_tool_call_rejected")


if __name__ == "__main__":
    unittest.main()
