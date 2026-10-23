from __future__ import annotations

import json
import os
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx

from pure_ai_chat_loader import (
    AI_CHAT_ROOT,
    ensure_ai_chat_packages,
    load_legacy_diagnostics_modules,
    load_module,
)


def configured_chat(config_module, **overrides):
    values = {
        "AIKE_LLM_API_KEY": "TEST-AIKE-CREDENTIAL",
        "AIKE_LLM_BASE_URL": "https://user:pass@aike.example/v1?token=hidden",
        "AIKE_LLM_MODEL": "aike-model",
        "AIKE_LLM_TIMEOUT_SECONDS": "60",
        "ENABLE_CHAT_GRAPH_RUNTIME": "true",
        "CHAT_LLM_API_KEY": "TEST-UNUSED-CREDENTIAL",
        "CHAT_LLM_BASE_URL": "https://unused.example/v1",
        "CHAT_LLM_MODEL": "unused-model",
        "CHAT_LLM_TIMEOUT_SECONDS": "777",
        "ENABLE_PERSONA_LLM_ROUTING": "true",
        "PERSONA_LLM_ROLE_CARD_KEYS": "linyin",
        "PERSONA_LLM_API_KEY": "TEST-PERSONA-CREDENTIAL",
        "PERSONA_LLM_BASE_URL": "https://persona.example/v1",
        "PERSONA_LLM_MODEL": "persona-model",
        "PERSONA_LLM_TIMEOUT_SECONDS": "90",
        "SUMMARY_LLM_API_KEY": "TEST-SUMMARY-CREDENTIAL",
        "SUMMARY_LLM_BASE_URL": "https://summary.example/v1",
        "SUMMARY_LLM_MODEL": "summary-model",
        "MAIN_LLM_API_KEY": "TEST-MAIN-CREDENTIAL",
        "MAIN_LLM_BASE_URL": "https://main.example/v1",
        "MAIN_LLM_MODEL": "main-model",
        "ENABLE_UNKNOWN_SLANG_TOOL": "false",
        "ENABLE_VISION": "false",
        "BOT_OWNER_QQ": "10001",
    }
    values.update(overrides)
    with patch.dict(os.environ, values, clear=True):
        return config_module.load_config()


class UnifiedChatRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_ai_chat_packages()
        cls.config_module = load_module("src.plugins.ai_chat.config", AI_CHAT_ROOT / "config.py")
        cls.routes = load_module("src.plugins.ai_chat.completion_routes", AI_CHAT_ROOT / "completion_routes.py")
        cls.llm = load_module("src.plugins.ai_chat.llm", AI_CHAT_ROOT / "llm.py")
        cls.console = load_module("src.plugins.ai_chat.owner_console_read_runtime", AI_CHAT_ROOT / "owner_console_read_runtime.py")
        cls.models = load_module("src.plugins.ai_chat.lc.models", AI_CHAT_ROOT / "lc" / "models.py")

    def test_route_module_import_has_no_runtime_side_effects(self):
        code = (
            "import importlib.util,sys; "
            f"spec=importlib.util.spec_from_file_location('route_test', {str(AI_CHAT_ROOT / 'completion_routes.py')!r}); "
            "module=importlib.util.module_from_spec(spec);sys.modules['route_test']=module; "
            "spec.loader.exec_module(module); "
            "assert not any(name in sys.modules for name in "
            "['nonebot','openai','httpx','sqlite3','dotenv','src.plugins.ai_chat.config'])"
        )
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_llm_exports_the_shared_resolvers_for_existing_callers(self):
        self.assertIs(self.llm.resolve_chat_completion_route, self.routes.resolve_chat_completion_route)
        self.assertIs(self.llm.resolve_summary_completion_route, self.routes.resolve_summary_completion_route)
        self.assertIs(self.llm.ChatCompletionRoute, self.routes.ChatCompletionRoute)

    def test_chatgraph_toggle_preserves_the_route_matrix(self):
        for role, override, expected in [
            ("", "auto", "legacy"),
            ("aike", "auto", "legacy"),
            ("linyin", "auto", "persona"),
            ("other", "auto", "legacy"),
            ("linyin", "legacy", "legacy"),
        ]:
            with self.subTest(role=role, override=override):
                routes = [
                    self.routes.resolve_chat_completion_route(
                        configured_chat(self.config_module, ENABLE_CHAT_GRAPH_RUNTIME=flag),
                        role,
                        completion_route=override,
                    )
                    for flag in ("true", "false")
                ]
                self.assertEqual(routes[0], routes[1])
                self.assertEqual(routes[0].source, expected)
                self.assertNotEqual(routes[0].model, "unused-model")

    def test_scenehub_linyin_override_keeps_default_route(self):
        scene = load_module("src.plugins.ai_chat.scene_actor_profile", AI_CHAT_ROOT / "scene_actor_profile.py")
        with patch.object(scene, "load_linyin_deepseek_group_style_examples", return_value=scene.SceneStyleExamples("missing")):
            profile = scene.build_scene_actor_profile("linyin")
        config = configured_chat(self.config_module)
        private = self.routes.resolve_chat_completion_route(config, "linyin")
        group = self.routes.resolve_chat_completion_route(config, "linyin", completion_route=profile.completion_route)
        self.assertEqual(private.model, "persona-model")
        self.assertEqual(group.model, "aike-model")
        self.assertEqual(profile.reasoning_effort, "low")

    def test_incomplete_persona_cannot_fall_back_to_aike_or_chat_fields(self):
        config = configured_chat(self.config_module, PERSONA_LLM_API_KEY="")
        with self.assertRaisesRegex(RuntimeError, "PERSONA_LLM_API_KEY"):
            self.routes.resolve_chat_completion_route(config, "linyin")

    def test_default_route_reports_all_missing_configuration_names(self):
        config = configured_chat(self.config_module, AIKE_LLM_API_KEY=" ", AIKE_LLM_BASE_URL="", AIKE_LLM_MODEL="")
        route = self.routes.resolve_chat_completion_route(config)
        self.assertFalse(route.configured)
        self.assertEqual(set(route.configuration_errors), {"AIKE_LLM_API_KEY", "AIKE_LLM_BASE_URL", "AIKE_LLM_MODEL"})
        self.assertNotIn("TEST-UNUSED-CREDENTIAL", repr(route))

    def test_summary_stays_independent_of_role_and_chatgraph(self):
        for flag in ("true", "false"):
            config = configured_chat(self.config_module, ENABLE_CHAT_GRAPH_RUNTIME=flag, SUMMARY_LLM_API_KEY="")
            for role in ("", "aike", "linyin"):
                route = self.routes.resolve_summary_completion_route(config, role)
                self.assertEqual(route.model, "summary-model")
                self.assertEqual(route.api_key, "")
                self.assertEqual(route.source, "summary")

    def test_console_default_snapshot_ignores_active_card_and_graph_flag(self):
        for flag in ("true", "false"):
            config = configured_chat(self.config_module, ENABLE_CHAT_GRAPH_RUNTIME=flag, CHAT_LLM_API_KEY="")
            snapshot = self.console.build_owner_console_settings_snapshot(config, active_role_card_key="linyin")
            route = self.routes.resolve_chat_completion_route(config)
            self.assertEqual(snapshot.chat_model.model_name, route.model)
            self.assertEqual(snapshot.chat_model.timeout_seconds, route.timeout_seconds)
            self.assertEqual(snapshot.chat_model.base_url_redacted, "https://aike.example/v1")
            self.assertTrue(snapshot.chat_model.api_key_configured)
            self.assertEqual(snapshot.main_agent_model.model_name, "main-model")
            encoded = json.dumps(self.console.owner_console_to_jsonable(snapshot))
            for secret in ("TEST-AIKE-CREDENTIAL", "TEST-PERSONA-CREDENTIAL", "user:pass", "token=hidden"):
                self.assertNotIn(secret, encoded)

    def test_langchain_adapter_uses_same_role_and_scene_route(self):
        config = configured_chat(self.config_module)
        for override, model in (("auto", "persona-model"), ("legacy", "aike-model")):
            with self.subTest(override=override), patch.object(self.models, "_chat_openai", return_value="model") as factory:
                self.models.build_chat_llm(config, "linyin", completion_route=override)
                self.assertEqual(factory.call_args.kwargs["model"], model)

    def test_langchain_adapter_explicitly_rejects_native_ollama(self):
        config = configured_chat(self.config_module, PERSONA_LLM_PROVIDER="ollama", PERSONA_LLM_API_KEY="")
        with patch.object(self.models, "_chat_openai") as factory:
            with self.assertRaisesRegex(RuntimeError, "native Ollama"):
                self.models.build_chat_llm(config, "linyin")
        factory.assert_not_called()


class UnifiedChatProbeTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.diagnostics = load_legacy_diagnostics_modules()["diagnostics"]
        cls.config_module = load_module("src.plugins.ai_chat.config", AI_CHAT_ROOT / "config.py")
        cls.llm = load_module("src.plugins.ai_chat.llm", AI_CHAT_ROOT / "llm.py")

    def fake_openai(self, calls, *, content="OK", error=None):
        class Client:
            def __init__(self, **kwargs):
                calls.append({"client": kwargs})
                self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                calls.append({"closed": True})

            async def create(self, **kwargs):
                calls.append({"request": kwargs})
                if error:
                    raise error
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason="stop")])
        return Client

    async def test_calls_probes_and_reports_agree_for_each_effective_route(self):
        for graph in ("true", "false"):
            for role, override, model in (("aike", "auto", "aike-model"), ("linyin", "auto", "persona-model"), ("linyin", "legacy", "aike-model")):
                with self.subTest(graph=graph, role=role, override=override):
                    config = configured_chat(self.config_module, ENABLE_CHAT_GRAPH_RUNTIME=graph, CHAT_LLM_API_KEY="")
                    actual, probe = [], []
                    with (
                        patch.object(self.llm, "AsyncOpenAI", self.fake_openai(actual)),
                        patch.object(self.llm, "load_system_prompt", return_value="system"),
                        patch.object(self.llm, "load_base_chat_prompt", return_value="base"),
                        patch.object(self.llm, "load_world_card_prompt", return_value="world"),
                        patch.object(self.llm, "load_persona_prompt", return_value="persona"),
                    ):
                        await self.llm.ask_llm(config, [], "test", role_card_key=role, completion_route=override)
                    with patch.object(self.diagnostics, "AsyncOpenAI", self.fake_openai(probe)):
                        result = await self.diagnostics.check_chat_api(config, role, completion_route=override)
                    self.assertTrue(result.ok, result.detail)
                    self.assertEqual(actual[1]["request"]["model"], model)
                    self.assertEqual(probe[1]["request"]["model"], model)
                    self.assertEqual(actual[0]["client"]["base_url"], probe[0]["client"]["base_url"])
                    self.assertEqual(actual[0]["client"]["api_key"], probe[0]["client"]["api_key"])
                    self.assertEqual(probe[0]["client"]["max_retries"], 0)
                    self.assertNotIn("tools", probe[1]["request"])
                    self.assertEqual(probe[1]["request"]["messages"][-1]["content"], self.diagnostics.CHAT_TEST_USER_PROMPT)
                    report = self.diagnostics.format_config_status(config)
                    self.assertIn("模型：aike-model", report)
                    self.assertNotIn("unused-model", report)
                    self.assertTrue(self.diagnostics._chat_route_ready(config))
                    self.assertFalse(any("默认聊天路由配置不完整" in warning for warning in self.diagnostics.config_warnings(config)))

    async def test_invalid_config_is_reported_without_a_network_call(self):
        for overrides, role, expected in [
            ({"AIKE_LLM_API_KEY": ""}, "", "AIKE_LLM_API_KEY"),
            ({"AIKE_LLM_BASE_URL": ""}, "", "AIKE_LLM_BASE_URL"),
            ({"PERSONA_LLM_API_KEY": ""}, "linyin", "PERSONA_LLM_API_KEY"),
            ({"PERSONA_LLM_PROVIDER": "unsupported"}, "linyin", "PERSONA_LLM_PROVIDER"),
        ]:
            with self.subTest(overrides=overrides):
                config = configured_chat(self.config_module, **overrides)
                with patch.object(self.diagnostics, "AsyncOpenAI") as network:
                    result = await self.diagnostics.check_chat_api(config, role)
                network.assert_not_called()
                self.assertFalse(result.ok)
                self.assertIn(expected, result.detail)
                details = self.diagnostics.format_config_detail_status(config, "模型")
                self.assertNotIn("unused-model", details)
                self.assertNotIn("TEST-PERSONA-CREDENTIAL", details)

    async def test_probe_failure_does_not_try_an_alternate_endpoint(self):
        calls = []
        with patch.object(self.diagnostics, "AsyncOpenAI", self.fake_openai(calls, error=RuntimeError("test failure"))):
            result = await self.diagnostics.check_chat_api(configured_chat(self.config_module), "linyin")
        self.assertFalse(result.ok)
        self.assertEqual(len([call for call in calls if "client" in call]), 1)
        self.assertEqual(calls[0]["client"]["base_url"], "https://persona.example/v1")
        self.assertEqual(calls[-1], {"closed": True})

    async def test_empty_probe_response_is_unhealthy(self):
        with patch.object(self.diagnostics, "AsyncOpenAI", self.fake_openai([], content="")):
            result = await self.diagnostics.check_chat_api(configured_chat(self.config_module))
        self.assertFalse(result.ok)
        self.assertIn("返回空内容", result.detail)

    async def test_native_ollama_probe_uses_the_native_endpoint_without_a_key(self):
        requests = []
        def handle(request):
            requests.append(request)
            return httpx.Response(200, json={"message": {"content": "OK"}})
        real_client = httpx.AsyncClient
        config = configured_chat(self.config_module, PERSONA_LLM_PROVIDER="ollama", PERSONA_LLM_API_KEY="", PERSONA_LLM_BASE_URL="http://127.0.0.1:11434")
        with (
            patch.object(self.diagnostics.httpx, "AsyncClient", side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs)),
            patch.object(self.diagnostics, "AsyncOpenAI") as openai_client,
        ):
            result = await self.diagnostics.check_chat_api(config, "linyin")
        self.assertTrue(result.ok, result.detail)
        openai_client.assert_not_called()
        self.assertEqual(str(requests[0].url), "http://127.0.0.1:11434/api/chat")
        payload = json.loads(requests[0].content)
        self.assertEqual(payload["model"], "persona-model")
        self.assertEqual(payload["keep_alive"], 0)
        self.assertLessEqual(payload["options"]["num_predict"], 32)


if __name__ == "__main__":
    unittest.main()
