from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module


class PersonaLlmRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.module = load_module(
            "src.plugins.ai_chat.llm",
            AI_CHAT_ROOT / "llm.py",
        )

    @staticmethod
    def config(**overrides):
        values = {
            "openai_api_key": "deepseek-secret",
            "openai_base_url": "https://api.deepseek.example/v1",
            "openai_model": "deepseek-model",
            "ai_timeout_seconds": 60,
            "enable_persona_llm_routing": False,
            "persona_llm_role_card_keys": frozenset(),
            "persona_llm_api_key": "",
            "persona_llm_base_url": "",
            "persona_llm_model": "",
            "persona_llm_timeout_seconds": 60,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_legacy_and_non_allowlisted_personas_keep_deepseek(self):
        config = self.config(
            enable_persona_llm_routing=True,
            persona_llm_role_card_keys=frozenset({"linyin"}),
            persona_llm_api_key="grok-secret",
            persona_llm_base_url="https://grok.example/v1",
            persona_llm_model="grok-4.5",
        )

        legacy = self.module.resolve_chat_completion_route(config, "")
        aike = self.module.resolve_chat_completion_route(config, "aike")

        self.assertEqual(legacy.source, "legacy")
        self.assertEqual(legacy.model, "deepseek-model")
        self.assertEqual(aike.source, "legacy")
        self.assertEqual(aike.model, "deepseek-model")

    def test_allowlisted_linyin_role_card_uses_grok(self):
        config = self.config(
            enable_persona_llm_routing=True,
            persona_llm_role_card_keys=frozenset({"linyin"}),
            persona_llm_api_key="grok-secret",
            persona_llm_base_url="https://grok.example/v1",
            persona_llm_model="grok-4.5",
            persona_llm_timeout_seconds=90,
        )

        route = self.module.resolve_chat_completion_route(config, "linyin")

        self.assertEqual(route.source, "persona")
        self.assertEqual(route.base_url, "https://grok.example/v1")
        self.assertEqual(route.model, "grok-4.5")
        self.assertEqual(route.timeout_seconds, 90)
        self.assertNotIn("grok-secret", repr(route))

    def test_incomplete_enabled_route_fails_closed(self):
        config = self.config(
            enable_persona_llm_routing=True,
            persona_llm_role_card_keys=frozenset({"linyin"}),
            persona_llm_api_key="grok-secret",
            persona_llm_base_url="",
            persona_llm_model="grok-4.5",
        )

        with self.assertRaisesRegex(RuntimeError, "PERSONA_LLM_BASE_URL"):
            self.module.resolve_chat_completion_route(config, "linyin")


class PersonaLlmCallTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.module = load_module(
            "src.plugins.ai_chat.llm",
            AI_CHAT_ROOT / "llm.py",
        )

    async def test_ask_llm_sends_linyin_to_the_persona_endpoint(self):
        calls: list[dict[str, object]] = []

        class FakeCompletions:
            async def create(self, **kwargs):
                calls.append({"request": kwargs})
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content="凛音测试回复")
                        )
                    ]
                )

        class FakeClient:
            def __init__(self, **kwargs):
                calls.append({"client": kwargs})
                self.chat = SimpleNamespace(completions=FakeCompletions())

        config = SimpleNamespace(
            openai_api_key="deepseek-secret",
            openai_base_url="https://api.deepseek.example/v1",
            openai_model="deepseek-model",
            ai_timeout_seconds=60,
            ai_temperature=0.7,
            enable_persona_llm_routing=True,
            persona_llm_role_card_keys=frozenset({"linyin"}),
            persona_llm_api_key="grok-secret",
            persona_llm_base_url="https://grok.example/v1",
            persona_llm_model="grok-4.5",
            persona_llm_timeout_seconds=90,
        )

        with (
            patch.object(self.module, "AsyncOpenAI", FakeClient),
            patch.object(self.module, "load_system_prompt", return_value="system"),
            patch.object(self.module, "load_base_chat_prompt", return_value="base"),
            patch.object(
                self.module,
                "load_world_card_prompt",
                return_value="shared world",
            ),
            patch.object(
                self.module,
                "load_persona_prompt",
                return_value="linyin persona",
            ),
        ):
            reply = await self.module.ask_llm(
                config,
                [{"role": "assistant", "content": "history"}],
                "主人消息",
                role_card_key="linyin",
            )

        self.assertEqual(reply, "凛音测试回复")
        self.assertEqual(
            calls[0],
            {
                "client": {
                    "api_key": "grok-secret",
                    "base_url": "https://grok.example/v1",
                    "timeout": 90,
                }
            },
        )
        request = calls[1]["request"]
        self.assertEqual(request["model"], "grok-4.5")
        self.assertEqual(request["temperature"], 0.7)
        self.assertEqual(
            request["messages"][:4],
            [
                {"role": "system", "content": "system"},
                {"role": "system", "content": "base"},
                {"role": "system", "content": "shared world"},
                {"role": "system", "content": "linyin persona"},
            ],
        )
        self.assertEqual(request["messages"][-1]["content"], "主人消息")

    async def test_scene_only_call_limits_do_not_change_default_call_contract(self):
        calls: list[dict[str, object]] = []

        class FakeCompletions:
            async def create(self, **kwargs):
                calls.append({"request": kwargs})
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="短回复"))]
                )

        class FakeClient:
            def __init__(self, **kwargs):
                calls.append({"client": kwargs})
                self.chat = SimpleNamespace(completions=FakeCompletions())

        config = SimpleNamespace(
            openai_api_key="legacy-secret",
            openai_base_url="https://legacy.example/v1",
            openai_model="legacy-model",
            ai_timeout_seconds=60,
            ai_temperature=0.7,
            enable_persona_llm_routing=False,
            persona_llm_role_card_keys=frozenset(),
            persona_llm_api_key="",
            persona_llm_base_url="",
            persona_llm_model="",
            persona_llm_timeout_seconds=60,
        )
        with (
            patch.object(self.module, "AsyncOpenAI", FakeClient),
            patch.object(self.module, "load_system_prompt", return_value="system"),
            patch.object(self.module, "load_base_chat_prompt", return_value="base"),
            patch.object(self.module, "load_world_card_prompt", return_value=""),
            patch.object(self.module, "load_persona_prompt", return_value="aike persona"),
        ):
            await self.module.ask_llm(
                config,
                [],
                "主人消息",
                role_card_key="aike",
                max_tokens=120,
                max_retries=0,
            )

        self.assertEqual(calls[0]["client"]["max_retries"], 0)
        self.assertEqual(calls[1]["request"]["max_tokens"], 120)

    async def test_scene_linyin_can_use_deepseek_without_losing_persona_prompts(self):
        calls: list[dict[str, object]] = []

        class FakeCompletions:
            async def create(self, **kwargs):
                calls.append({"request": kwargs})
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(message=SimpleNamespace(content="凛音群聊回复"))
                    ]
                )

        class FakeClient:
            def __init__(self, **kwargs):
                calls.append({"client": kwargs})
                self.chat = SimpleNamespace(completions=FakeCompletions())

        config = SimpleNamespace(
            openai_api_key="deepseek-secret",
            openai_base_url="https://api.deepseek.example/v1",
            openai_model="deepseek-v4-flash",
            ai_timeout_seconds=60,
            ai_temperature=0.7,
            enable_persona_llm_routing=True,
            persona_llm_role_card_keys=frozenset({"linyin"}),
            persona_llm_api_key="grok-secret",
            persona_llm_base_url="https://grok.example/v1",
            persona_llm_model="grok-4.5",
            persona_llm_timeout_seconds=90,
        )
        with (
            patch.object(self.module, "AsyncOpenAI", FakeClient),
            patch.object(self.module, "load_system_prompt", return_value="system"),
            patch.object(self.module, "load_base_chat_prompt", return_value="base"),
            patch.object(
                self.module,
                "load_world_card_prompt",
                return_value="shared world",
            ),
            patch.object(
                self.module,
                "load_persona_prompt",
                return_value="linyin persona",
            ),
        ):
            reply = await self.module.ask_llm(
                config,
                [],
                "主人群聊消息",
                extra_system_context="group rules and style examples",
                role_card_key="linyin",
                max_retries=0,
                completion_route="legacy",
                reasoning_effort="low",
            )

        self.assertEqual(reply, "凛音群聊回复")
        self.assertEqual(
            calls[0],
            {
                "client": {
                    "api_key": "deepseek-secret",
                    "base_url": "https://api.deepseek.example/v1",
                    "timeout": 60,
                    "max_retries": 0,
                }
            },
        )
        request = calls[1]["request"]
        self.assertEqual(request["model"], "deepseek-v4-flash")
        self.assertEqual(request["reasoning_effort"], "low")
        self.assertEqual(
            request["messages"][:5],
            [
                {"role": "system", "content": "system"},
                {"role": "system", "content": "base"},
                {"role": "system", "content": "shared world"},
                {"role": "system", "content": "linyin persona"},
                {"role": "system", "content": "group rules and style examples"},
            ],
        )

    async def test_invalid_completion_route_is_rejected_before_network_call(self):
        config = PersonaLlmRoutingTests.config()

        with self.assertRaisesRegex(ValueError, "completion_route"):
            await self.module.ask_llm(
                config,
                [],
                "message",
                completion_route="persona",
            )

    async def test_invalid_reasoning_effort_is_rejected_before_network_call(self):
        config = PersonaLlmRoutingTests.config()

        with self.assertRaisesRegex(ValueError, "reasoning_effort"):
            await self.module.ask_llm(
                config,
                [],
                "message",
                reasoning_effort="xhigh",
            )


if __name__ == "__main__":
    unittest.main()
