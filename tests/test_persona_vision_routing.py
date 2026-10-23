from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from openai import AsyncOpenAI as RealAsyncOpenAI

from pure_ai_chat_loader import AI_CHAT_ROOT, load_legacy_media_modules


class PersonaVisionRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_legacy_media_modules()
        cls.vision = cls.modules["vision"]

    @staticmethod
    def config(**overrides):
        values = {
            "enable_persona_vision_routing": False,
            "persona_vision_role_card_keys": frozenset(),
            "persona_vision_api_key": "",
            "persona_vision_base_url": "",
            "persona_vision_model": "",
            "persona_vision_timeout_seconds": 90,
            "persona_vision_private_image_wait_seconds": -1,
            "vision_private_image_wait_seconds": 5,
            "persona_llm_api_key": "",
            "persona_llm_base_url": "",
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_aike_and_disabled_routes_stay_on_bailian(self):
        config = self.config(
            enable_persona_vision_routing=True,
            persona_vision_role_card_keys=frozenset({"linyin"}),
            persona_vision_model="grok-4.5",
            persona_llm_api_key="grok-secret",
            persona_llm_base_url="https://grok.example/v1",
        )

        aike = self.vision.resolve_vision_provider_route(config, "aike")
        legacy = self.vision.resolve_vision_provider_route(config, "")

        self.assertEqual(aike.provider, "aliyun_bailian")
        self.assertEqual(legacy.provider, "aliyun_bailian")

    def test_linyin_uses_the_explicit_grok_vision_route(self):
        config = self.config(
            enable_persona_vision_routing=True,
            persona_vision_role_card_keys=frozenset({"linyin"}),
            persona_vision_model="grok-4.5",
            persona_vision_timeout_seconds=80,
            persona_vision_api_key="grok-secret",
            persona_vision_base_url="https://grok.example/v1",
            persona_llm_api_key="",
            persona_llm_base_url="http://127.0.0.1:11434",
        )

        route = self.vision.resolve_vision_provider_route(config, "linyin")

        self.assertEqual(route.provider, "persona_grok")
        self.assertEqual(route.base_url, "https://grok.example/v1")
        self.assertEqual(route.model, "grok-4.5")
        self.assertEqual(route.timeout_seconds, 80)
        self.assertNotIn("grok-secret", repr(route))

    def test_linyin_can_use_a_longer_private_image_wait_without_changing_aike(self):
        config = self.config(
            persona_vision_role_card_keys=frozenset({"linyin"}),
            persona_vision_private_image_wait_seconds=12,
            vision_private_image_wait_seconds=5,
        )

        self.assertEqual(
            self.vision.resolve_private_image_wait_seconds(config, "linyin"),
            12,
        )
        self.assertEqual(
            self.vision.resolve_private_image_wait_seconds(config, "aike"),
            5,
        )
        self.assertEqual(
            self.vision.resolve_private_image_wait_seconds(config, ""),
            5,
        )

    def test_persona_private_image_wait_falls_back_when_unset(self):
        config = self.config(
            persona_vision_role_card_keys=frozenset({"linyin"}),
            persona_vision_private_image_wait_seconds=-1,
            vision_private_image_wait_seconds=5,
        )

        self.assertEqual(
            self.vision.resolve_private_image_wait_seconds(config, "linyin"),
            5,
        )

    def test_incomplete_linyin_route_fails_closed(self):
        config = self.config(
            enable_persona_vision_routing=True,
            persona_vision_role_card_keys=frozenset({"linyin"}),
            persona_vision_model="grok-4.5",
            persona_llm_api_key="grok-secret",
        )

        with self.assertRaisesRegex(
            self.vision.VisionError,
            "PERSONA_VISION_BASE_URL",
        ):
            self.vision.resolve_vision_provider_route(config, "linyin")

    def test_grok_multimodal_request_uses_high_detail_and_no_retry(self):
        calls: list[dict[str, object]] = []

        class FakeCompletions:
            async def create(self, **kwargs):
                calls.append({"request": kwargs})
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content="图片左上为红色，右上为蓝色。"
                            )
                        )
                    ]
                )

        class FakeClient:
            def __init__(self, **kwargs):
                calls.append({"client": kwargs})
                self.chat = SimpleNamespace(completions=FakeCompletions())

        route = self.vision.VisionProviderRoute(
            provider="persona_grok",
            api_key="grok-secret",
            base_url="https://grok.example/v1",
            model="grok-4.5",
            timeout_seconds=90,
        )
        image_base64 = self.vision.diagnostic_vision_image_base64()

        with patch.object(self.vision, "AsyncOpenAI", FakeClient):
            description = asyncio.run(
                self.vision._openai_chat_vision(route, image_base64)
            )

        self.assertIn("左上", description)
        self.assertEqual(calls[0]["client"]["max_retries"], 0)
        request = calls[1]["request"]
        self.assertEqual(request["model"], "grok-4.5")
        self.assertEqual(request["max_tokens"], 400)
        self.assertNotIn("reasoning_effort", request)
        image_part = request["messages"][1]["content"][1]
        self.assertEqual(image_part["image_url"]["detail"], "high")
        self.assertTrue(
            image_part["image_url"]["url"].startswith(
                "data:image/png;base64,"
            )
        )

    def test_deepseek_vision_sends_real_sdk_payload_and_records_selected_route(self):
        calls = []
        image = self.vision.diagnostic_vision_image_base64()
        config = self.config(
            enable_vision=True, vision_max_images=1, vision_timeout_seconds=60,
            vision_max_image_bytes=5242880, vision_trusted_local_roots=(),
            enable_persona_vision_routing=True, persona_vision_role_card_keys={"linyin"},
            persona_vision_api_key="TEST-DS-KEY", persona_vision_base_url="https://api.deepseek.com",
            persona_vision_model="deepseek-flash", persona_vision_timeout_seconds=60,
            persona_vision_max_tokens=4096, persona_vision_reasoning_effort="high",
            persona_llm_api_key="TEST-GROK-KEY", persona_llm_base_url="https://grok.example/v1",
        )

        def handler(request):
            calls.append(request)
            return httpx.Response(200, json={
                "id": "vision-test", "object": "chat.completion", "created": 1,
                "model": "deepseek-flash", "choices": [{"index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "左上红色、右上蓝色、左下绿色、右下白色。",
                                "reasoning_content": "PRIVATE-REASONING"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300,
                          "completion_tokens_details": {"reasoning_tokens": 170}},
            })

        def client(**options):
            self.assertEqual(options["max_retries"], 0)
            self.assertEqual(options["timeout"], 60)
            return RealAsyncOpenAI(**options, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

        observability = sys.modules["src.plugins.ai_chat.vision_observability"]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "vision.log"
            with (patch.object(self.vision, "AsyncOpenAI", side_effect=client),
                  patch.object(self.vision, "_bailian_chat_vision") as bailian,
                  patch.object(self.vision, "observe_vision_infer_safely"),
                  patch.object(observability, "VISION_LOG_PATH", path)):
                result = asyncio.run(self.vision.describe_images(
                    config, ["data:image/png;base64," + image], role_card_key="linyin"))
            self.assertEqual(result, ["左上红色、右上蓝色、左下绿色、右下白色。"])
            bailian.assert_not_called()
            row, = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        request, = calls
        self.assertEqual(request.url.host, "api.deepseek.com")
        self.assertEqual(request.url.path, "/chat/completions")
        self.assertEqual(request.headers["authorization"], "Bearer TEST-DS-KEY")
        payload = json.loads(request.content)
        self.assertEqual(payload["model"], "deepseek-flash")
        self.assertEqual(payload["max_tokens"], 4096)
        self.assertEqual(payload["reasoning_effort"], "high")
        self.assertEqual([message["role"] for message in payload["messages"]], ["system", "user"])
        image_part = payload["messages"][1]["content"][1]["image_url"]
        self.assertEqual(image_part["detail"], "high")
        self.assertEqual(base64.b64decode(image_part["url"].split(",", 1)[1]), base64.b64decode(image))
        self.assertEqual(row["persona"], "linyin")
        self.assertEqual(row["provider"], "persona_deepseek")
        self.assertEqual(row["requested_model"], row["returned_model"])
        self.assertEqual(row["reasoning_effort"], "high")
        self.assertEqual(row["max_tokens"], 4096)
        self.assertEqual(row["reasoning_tokens"], 170)
        self.assertEqual(row["status"], "succeeded")
        self.assertNotIn("PRIVATE", json.dumps(row))

    def test_deepseek_failure_does_not_fall_back_to_grok_or_bailian(self):
        calls = []
        config = self.config(
            enable_persona_vision_routing=True, persona_vision_role_card_keys={"linyin"},
            persona_vision_api_key="TEST-DS-KEY", persona_vision_base_url="https://api.deepseek.com",
            persona_vision_model="deepseek-flash",
            persona_llm_api_key="TEST-GROK-KEY", persona_llm_base_url="https://grok.example/v1",
        )

        def handler(request):
            calls.append(request.url.host)
            return httpx.Response(429, json={"error": {"message": "PRIVATE-ERROR", "type": "rate_limit_error"}})

        def client(**options):
            return RealAsyncOpenAI(**options, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

        with (patch.object(self.vision, "AsyncOpenAI", side_effect=client),
              patch.object(self.vision, "_bailian_chat_vision") as bailian):
            with self.assertRaisesRegex(self.vision.VisionError, "DeepSeek视觉请求失败.*HTTP 429") as caught:
                asyncio.run(self.vision._describe_image_base64(
                    config, self.vision.diagnostic_vision_image_base64(), role_card_key="linyin"))
        self.assertEqual(calls, ["api.deepseek.com"])
        bailian.assert_not_called()
        self.assertNotIn("PRIVATE-ERROR", str(caught.exception))

    def test_deepseek_blank_credentials_never_use_persona_chat_credentials(self):
        config = self.config(
            enable_persona_vision_routing=True, persona_vision_role_card_keys={"linyin"},
            persona_vision_model="deepseek-flash", persona_vision_base_url="https://api.deepseek.com",
            persona_llm_api_key="TEST-GROK-KEY", persona_llm_base_url="https://grok.example/v1",
        )
        with self.assertRaisesRegex(self.vision.VisionError, "PERSONA_VISION_API_KEY"):
            self.vision.resolve_vision_provider_route(config, "linyin")

    def test_deepseek_rejects_invalid_output_budget_and_effort(self):
        for overrides, field in (({"persona_vision_max_tokens": 0}, "PERSONA_VISION_MAX_TOKENS"),
                                 ({"persona_vision_reasoning_effort": "invalid"}, "PERSONA_VISION_REASONING_EFFORT")):
            with self.subTest(field=field):
                config = self.config(
                    enable_persona_vision_routing=True, persona_vision_role_card_keys={"linyin"},
                    persona_vision_api_key="TEST-DS-KEY", persona_vision_base_url="https://api.deepseek.com",
                    persona_vision_model="deepseek-flash", **overrides,
                )
                with self.assertRaisesRegex(self.vision.VisionError, field):
                    self.vision.resolve_vision_provider_route(config, "linyin")

    def test_describe_images_forwards_only_the_explicit_role_card_key(self):
        config = SimpleNamespace(
            enable_vision=True,
            vision_max_images=1,
            vision_timeout_seconds=30,
            vision_max_image_bytes=1024,
            vision_trusted_local_roots=(),
        )
        describe = AsyncMock(return_value="Grok图片摘要")
        with (
            patch.object(
                self.vision,
                "_image_url_to_base64",
                AsyncMock(return_value="AAAA"),
            ),
            patch.object(self.vision, "_describe_image_base64", describe),
            patch.object(self.vision, "observe_vision_infer_safely"),
        ):
            descriptions = asyncio.run(
                self.vision.describe_images(
                    config,
                    ["https://example.test/a.png"],
                    role_card_key="linyin",
                )
            )

        self.assertEqual(descriptions, ["Grok图片摘要"])
        describe.assert_awaited_once_with(
            config,
            "AAAA",
            role_card_key="linyin",
        )

    def test_chat_runtime_passes_the_request_role_card_to_vision(self):
        plugin_source = (AI_CHAT_ROOT / "__init__.py").read_text(encoding="utf-8")

        self.assertIn(
            "role_card_key=request.role_card_key,",
            plugin_source,
        )


if __name__ == "__main__":
    unittest.main()
