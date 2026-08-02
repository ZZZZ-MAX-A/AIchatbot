from __future__ import annotations

import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

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
            persona_llm_api_key="grok-secret",
            persona_llm_base_url="https://grok.example/v1",
        )

        route = self.vision.resolve_vision_provider_route(config, "linyin")

        self.assertEqual(route.provider, "persona_grok")
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
            "PERSONA_LLM_BASE_URL",
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
                self.vision._grok_chat_vision(route, image_base64)
            )

        self.assertIn("左上", description)
        self.assertEqual(calls[0]["client"]["max_retries"], 0)
        request = calls[1]["request"]
        self.assertEqual(request["model"], "grok-4.5")
        image_part = request["messages"][1]["content"][1]
        self.assertEqual(image_part["image_url"]["detail"], "high")
        self.assertTrue(
            image_part["image_url"]["url"].startswith(
                "data:image/png;base64,"
            )
        )

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
