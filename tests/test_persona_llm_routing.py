from __future__ import annotations

import json
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
            "aike_llm_api_key": "deepseek-secret",
            "aike_llm_base_url": "https://api.deepseek.example/v1",
            "aike_llm_model": "deepseek-model",
            "aike_llm_timeout_seconds": 60,
            "enable_persona_llm_routing": False,
            "persona_llm_role_card_keys": frozenset(),
            "persona_llm_provider": "openai",
            "persona_llm_api_key": "",
            "persona_llm_base_url": "",
            "persona_llm_model": "",
            "persona_llm_timeout_seconds": 60,
            "persona_llm_num_ctx": 4096,
            "persona_llm_max_tokens": 640,
            "persona_llm_keep_alive_seconds": 0,
            "summary_llm_api_key": "summary-secret",
            "summary_llm_base_url": "https://summary.example/v1",
            "summary_llm_model": "summary-model",
            "summary_llm_timeout_seconds": 45,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_legacy_and_non_allowlisted_personas_keep_deepseek(self):
        config = PersonaLlmRoutingTests.config(
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

    def test_allowlisted_persona_can_use_local_ollama_without_api_key(self):
        config = self.config(
            enable_persona_llm_routing=True,
            persona_llm_role_card_keys=frozenset({"private-card"}),
            persona_llm_provider="ollama",
            persona_llm_base_url="http://127.0.0.1:11434",
            persona_llm_model="dolphin3:8b",
        )

        route = self.module.resolve_chat_completion_route(config, "private-card")

        self.assertEqual(route.source, "persona")
        self.assertEqual(route.provider, "ollama")
        self.assertEqual(route.api_key, "")
        self.assertEqual(route.num_ctx, 4096)
        self.assertEqual(route.max_tokens, 640)
        self.assertEqual(route.keep_alive_seconds, 0)

    def test_aike_summary_route_does_not_fall_back_to_chat_key(self):
        config = self.config(
            summary_llm_api_key="",
            enable_persona_llm_routing=True,
            persona_llm_role_card_keys=frozenset({"aike"}),
            persona_llm_api_key="persona-secret",
            persona_llm_base_url="https://persona.example/v1",
            persona_llm_model="persona-model",
        )

        route = self.module.resolve_summary_completion_route(config, "aike")

        self.assertEqual(route.source, "summary")
        self.assertEqual(route.api_key, "")
        self.assertNotEqual(route.api_key, config.aike_llm_api_key)
        self.assertNotEqual(route.api_key, config.persona_llm_api_key)


class PersonaLlmCallTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.module = load_module(
            "src.plugins.ai_chat.llm",
            AI_CHAT_ROOT / "llm.py",
        )

    async def test_aike_max_reaches_actual_sdk_request_body(self):
        requests = []
        original_client = self.module.AsyncOpenAI

        def handler(request):
            requests.append(json.loads(request.content))
            return self.module.httpx.Response(200, json={
                "id": "unit", "object": "chat.completion", "created": 0,
                "model": "deepseek-v4-flash",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": "爱可回复"}}],
            })

        def client(**options):
            return original_client(**options, http_client=self.module.httpx.AsyncClient(
                transport=self.module.httpx.MockTransport(handler)))

        config = PersonaLlmRoutingTests.config(
            aike_llm_base_url="https://api.deepseek.com", aike_llm_model="deepseek-v4-flash",
            aike_llm_reasoning_effort="max", ai_temperature=0.7, enable_unknown_slang_tool=False,
        )
        with (
            patch.object(self.module, "AsyncOpenAI", side_effect=client),
            patch.object(self.module, "load_system_prompt", return_value="system"),
            patch.object(self.module, "load_base_chat_prompt", return_value="base"),
            patch.object(self.module, "load_world_card_prompt", return_value=""),
            patch.object(self.module, "load_persona_prompt", return_value="aike persona"),
        ):
            reply = await self.module.ask_llm(config, [], "主人消息", role_card_key="aike")
        self.assertEqual(reply, "爱可回复")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["reasoning_effort"], "max")
        self.assertNotIn("thinking", requests[0])

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
            aike_llm_api_key="deepseek-secret",
            aike_llm_reasoning_effort="max",
            aike_llm_base_url="https://api.deepseek.example/v1",
            aike_llm_model="deepseek-model",
            aike_llm_timeout_seconds=60,
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
        self.assertNotIn("reasoning_effort", request)
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

    async def test_ask_llm_uses_native_ollama_and_unloads_after_reply(self):
        captured: dict[str, object] = {}

        def handler(request):
            captured["url"] = str(request.url)
            captured["payload"] = json.loads(request.content)
            return self.module.httpx.Response(
                200,
                json={
                    "message": {
                        "role": "assistant",
                        "content": "local reply",
                    }
                },
            )

        client = self.module.httpx.AsyncClient(
            transport=self.module.httpx.MockTransport(handler)
        )
        config = PersonaLlmRoutingTests.config(
            ai_temperature=0.7,
            enable_persona_llm_routing=True,
            persona_llm_role_card_keys=frozenset({"private-card"}),
            persona_llm_provider="ollama",
            persona_llm_api_key="",
            persona_llm_base_url="http://127.0.0.1:11434",
            persona_llm_model="dolphin3:8b",
            persona_llm_timeout_seconds=90,
            persona_llm_num_ctx=4096,
            persona_llm_max_tokens=640,
            persona_llm_keep_alive_seconds=0,
        )

        with (
            patch.object(self.module.httpx, "AsyncClient", return_value=client),
            patch.object(self.module, "load_system_prompt", return_value="system"),
            patch.object(self.module, "load_base_chat_prompt", return_value="base"),
            patch.object(self.module, "load_world_card_prompt", return_value=""),
            patch.object(
                self.module,
                "load_persona_prompt",
                return_value="private persona",
            ),
        ):
            reply = await self.module.ask_llm(
                config,
                [],
                "hello",
                role_card_key="private-card",
            )

        self.assertEqual(reply, "local reply")
        self.assertEqual(captured["url"], "http://127.0.0.1:11434/api/chat")
        payload = captured["payload"]
        self.assertEqual(payload["model"], "dolphin3:8b")
        self.assertEqual(payload["keep_alive"], 0)
        self.assertEqual(payload["options"]["num_ctx"], 4096)
        self.assertEqual(payload["options"]["num_predict"], 640)
        self.assertIn("动作描写", payload["messages"][-2]["content"])
        self.assertEqual(payload["messages"][-1]["content"], "hello")

    async def test_ollama_persona_filters_bad_assistant_examples_before_request(self):
        captured: dict[str, object] = {}

        def handler(request):
            captured["payload"] = json.loads(request.content)
            return self.module.httpx.Response(
                200,
                json={"message": {"role": "assistant", "content": "ok"}},
            )

        client = self.module.httpx.AsyncClient(
            transport=self.module.httpx.MockTransport(handler)
        )
        config = PersonaLlmRoutingTests.config(
            ai_temperature=0.7,
            enable_persona_llm_routing=True,
            persona_llm_role_card_keys=frozenset({"linyin"}),
            persona_llm_provider="ollama",
            persona_llm_base_url="http://127.0.0.1:11434",
            persona_llm_model="dolphin3:8b",
            persona_llm_timeout_seconds=90,
        )
        history = [
            {"role": "user", "content": "你是凛音，不是我"},
            {"role": "assistant", "content": "主人抬眼看了看，说：“我知道。”"},
            {"role": "assistant", "content": "（她抬眼，目光平静地停在你身上。）……主人。"},
        ]

        with (
            patch.object(self.module.httpx, "AsyncClient", return_value=client),
            patch.object(self.module, "load_system_prompt", return_value="system"),
            patch.object(self.module, "load_base_chat_prompt", return_value="base"),
            patch.object(self.module, "load_world_card_prompt", return_value=""),
            patch.object(self.module, "load_persona_prompt", return_value="persona"),
        ):
            await self.module.ask_llm(config, history, "继续当前对话", role_card_key="linyin")

        contents = [message["content"] for message in captured["payload"]["messages"]]
        self.assertNotIn("主人抬眼看了看", contents)
        self.assertIn("（她抬眼，目光平静地停在你身上。）……主人。", contents)

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
            aike_llm_api_key="legacy-secret",
            aike_llm_base_url="https://legacy.example/v1",
            aike_llm_model="legacy-model",
            aike_llm_timeout_seconds=60,
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
            aike_llm_api_key="deepseek-secret",
            aike_llm_reasoning_effort="max",
            aike_llm_base_url="https://api.deepseek.example/v1",
            aike_llm_model="deepseek-v4-flash",
            aike_llm_timeout_seconds=60,
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

    async def test_summary_detail_preserves_complete_model_refusal(self):
        refusal = "抱歉，我无法总结这些内容，因为当前请求不适合摘要。"

        class FakeCompletions:
            async def create(self, **kwargs):
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content=refusal),
                        )
                    ]
                )

        class FakeClient:
            def __init__(self, **kwargs):
                self.chat = SimpleNamespace(completions=FakeCompletions())

        with patch.object(self.module, "AsyncOpenAI", FakeClient):
            result = await self.module.summarize_messages_with_detail(
                PersonaLlmRoutingTests.config(),
                "messages to summarize",
            )

        self.assertFalse(result.succeeded)
        self.assertEqual(result.summary, "")
        self.assertEqual(result.failure_detail, refusal)

    async def test_summary_detail_uses_shared_summary_endpoint_for_linyin(self):
        calls: list[dict[str, object]] = []

        class FakeCompletions:
            async def create(self, **kwargs):
                calls.append({"request": kwargs})
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content="场景在室内，双方已确认继续当前安排，下一步等待主人决定。"
                            )
                        )
                    ]
                )

        class FakeClient:
            def __init__(self, **kwargs):
                calls.append({"client": kwargs})
                self.chat = SimpleNamespace(completions=FakeCompletions())

        with patch.object(self.module, "AsyncOpenAI", FakeClient):
            result = await self.module.summarize_messages_with_detail(
                PersonaLlmRoutingTests.config(),
                "messages to summarize",
                role_card_key="linyin",
            )

        self.assertTrue(result.succeeded)
        self.assertEqual(
            calls[0]["client"],
            {
                "api_key": "summary-secret",
                "base_url": "https://summary.example/v1",
                "timeout": 45,
            },
        )
        self.assertEqual(calls[1]["request"]["model"], "summary-model")

    async def test_summary_detail_preserves_sanitized_request_error(self):
        class FakeCompletions:
            async def create(self, **kwargs):
                raise RuntimeError(
                    "request failed api_key=secret-value "
                    "https://provider.example/v1"
                )

        class FakeClient:
            def __init__(self, **kwargs):
                self.chat = SimpleNamespace(completions=FakeCompletions())

        with patch.object(self.module, "AsyncOpenAI", FakeClient):
            result = await self.module.summarize_messages_with_detail(
                PersonaLlmRoutingTests.config(),
                "messages to summarize",
            )

        self.assertFalse(result.succeeded)
        self.assertIn("RuntimeError", result.failure_detail)
        self.assertIn("request failed", result.failure_detail)
        self.assertNotIn("secret-value", result.failure_detail)
        self.assertNotIn("https://provider.example/v1", result.failure_detail)

    def test_usable_summary_rejects_refusals(self):
        self.assertFalse(self.module.is_usable_summary(""))
        self.assertFalse(self.module.is_usable_summary("抱歉，我无法总结这些内容。"))
        self.assertFalse(self.module.is_usable_summary("I cannot assist with that."))
        self.assertTrue(self.module.is_usable_summary("场景在室内，双方已确认继续，未决是主人下一句。"))
        self.assertEqual(self.module.usable_summary_text("抱歉，我无法处理这类内容。"), "")



    def test_all_personas_use_shared_summary_route_and_format(self):
        config = PersonaLlmRoutingTests.config(
            enable_persona_llm_routing=True,
            persona_llm_role_card_keys=frozenset({"linyin"}),
            persona_llm_api_key="grok-secret",
            persona_llm_base_url="https://grok.example/v1",
            persona_llm_model="grok-4.5",
            persona_llm_timeout_seconds=90,
        )
        routes = [
            self.module.resolve_summary_completion_route(config, role_card_key)
            for role_card_key in ("", "aike", "linyin")
        ]
        for route in routes:
            self.assertEqual(route.source, "summary")
            self.assertEqual(route.api_key, "summary-secret")
            self.assertEqual(route.base_url, "https://summary.example/v1")
            self.assertEqual(route.model, "summary-model")
            self.assertEqual(route.timeout_seconds, 45)

        official_prompts = [
            self.module._summary_system_prompt("official", role_card_key)
            for role_card_key in ("", "aike", "linyin")
        ]
        self.assertEqual(official_prompts[0], official_prompts[1])
        self.assertEqual(official_prompts[1], official_prompts[2])
        for field_name in ("场景位置", "场景类型", "已确认事实", "人物状态", "未决 / 现在该怎么接"):
            self.assertIn(field_name, official_prompts[0])

        gap_prompts = [
            self.module._summary_system_prompt("gap", role_card_key)
            for role_card_key in ("", "aike", "linyin")
        ]
        self.assertEqual(gap_prompts[0], gap_prompts[1])
        self.assertEqual(gap_prompts[1], gap_prompts[2])
        self.assertIn("当前状态卡", gap_prompts[0])

if __name__ == "__main__":
    unittest.main()
