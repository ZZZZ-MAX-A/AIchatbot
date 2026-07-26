from __future__ import annotations

import json
import types
import unittest

import httpx

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module


class OwnerConsoleCloudVisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.config = load_module(
            "src.plugins.ai_chat.config",
            AI_CHAT_ROOT / "config.py",
        )
        cls.module = load_module(
            "src.plugins.ai_chat.owner_console_cloud_vision",
            AI_CHAT_ROOT / "owner_console_cloud_vision.py",
        )

    @staticmethod
    def configured():
        return types.SimpleNamespace(
            vision_provider="aliyun_bailian",
            vision_cloud_model="qwen3.7-flash",
            aliyun_bailian_base_url=(
                "https://ws-owner123.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
            ),
            aliyun_bailian_api_key="owner-cloud-secret",
            vision_timeout_seconds=60,
            vision_max_image_bytes=1_000_000,
        )

    @staticmethod
    def reference():
        return types.SimpleNamespace(
            sticker_id="aike_affection_005",
            content=b"\x89PNG\r\n\x1a\n" + b"unit-reference",
            media_type="image/png",
            width=500,
            height=500,
        )

    def test_executor_uses_fixed_prompt_model_and_sanitized_result(self):
        captured: dict[str, object] = {"calls": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["calls"] = int(captured["calls"]) + 1
            payload = json.loads(request.content.decode("utf-8"))
            captured["payload"] = payload
            return httpx.Response(
                200,
                json={
                    "model": "qwen3.7-flash",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": (
                                    "</think>角色双手捧着爱心，周围有多颗红心，"
                                    "表达出浓烈的爱意和兴奋。"
                                ),
                            }
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 30,
                        "completion_tokens": 20,
                        "total_tokens": 50,
                    },
                },
            )

        executor = self.module.CloudVisionExecutor(
            config_provider=self.configured,
            reference_loader=self.reference,
            transport=httpx.MockTransport(handler),
        )
        result = executor()

        self.assertEqual(captured["calls"], 1)
        payload = captured["payload"]
        self.assertEqual(payload["model"], "qwen3.7-flash")
        self.assertEqual(
            payload["messages"][0]["content"][1]["text"],
            self.module.CLOUD_VISION_FIXED_PROMPT,
        )
        self.assertFalse(payload["enable_thinking"])
        self.assertNotIn("tools", payload)
        self.assertTrue(result.response_cleanup_applied)
        self.assertFalse(result.response_preview.startswith("</think>"))
        self.assertTrue(result.external_image_upload_executed)
        self.assertEqual(result.request_count, 1)
        self.assertFalse(result.client_automatic_retry)

    def test_reference_failure_stops_before_transport(self):
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(500)

        executor = self.module.CloudVisionExecutor(
            config_provider=self.configured,
            reference_loader=lambda: (_ for _ in ()).throw(ValueError("drift")),
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaises(self.module.CloudVisionFailure) as caught:
            executor()

        self.assertEqual(calls, 0)
        self.assertEqual(
            caught.exception.code,
            "cloud_vision_reference_asset_unavailable",
        )
        self.assertFalse(caught.exception.external_image_upload_executed)

    def test_provider_failure_reports_upload_without_exposing_secret_body(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                401,
                text="owner-cloud-secret provider detail",
            )

        executor = self.module.CloudVisionExecutor(
            config_provider=self.configured,
            reference_loader=self.reference,
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaises(self.module.CloudVisionFailure) as caught:
            executor()

        self.assertEqual(
            caught.exception.code,
            "cloud_vision_authentication_failed",
        )
        self.assertTrue(caught.exception.external_image_upload_executed)
        self.assertTrue(caught.exception.cloud_vision_called)
        self.assertEqual(caught.exception.request_count, 1)
        self.assertNotIn("owner-cloud-secret", caught.exception.code_label)
        self.assertNotIn("provider detail", caught.exception.code_label)


if __name__ == "__main__":
    unittest.main()
