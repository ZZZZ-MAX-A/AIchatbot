from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module, load_pure_graph_modules


class EncyclopediaGraphTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        ensure_ai_chat_packages()
        cls.service_module = load_module("src.plugins.ai_chat.encyclopedia", AI_CHAT_ROOT / "encyclopedia.py")
        cls.graph = load_module("src.plugins.ai_chat.graph.encyclopedia", AI_CHAT_ROOT / "graph/encyclopedia.py")
        cls.llm = load_module("src.plugins.ai_chat.llm", AI_CHAT_ROOT / "llm.py")
        cls.config_module = load_module("src.plugins.ai_chat.config", AI_CHAT_ROOT / "config.py")
        cls.policy = load_module("src.plugins.ai_chat.encyclopedia_capabilities", AI_CHAT_ROOT / "encyclopedia_capabilities.py")

    def config(self, **overrides):
        values = {
            "AIKE_LLM_API_KEY": "test-aike", "AIKE_LLM_MODEL": "fast-planner",
            "AIKE_LLM_BASE_URL": "https://planner.invalid/v1",
            "ENABLE_PERSONA_LLM_ROUTING": "true", "PERSONA_LLM_ROLE_CARD_KEYS": "linyin",
            "PERSONA_LLM_API_KEY": "test-linyin", "PERSONA_LLM_MODEL": "slow-persona",
            "PERSONA_LLM_BASE_URL": "https://persona.invalid/v1",
            "ENABLE_LINYIN_ENCYCLOPEDIA": "true", "LINYIN_ENCYCLOPEDIA_AUTO": "true",
        }
        values.update(overrides)
        return self.config_module.load_config(values)

    @staticmethod
    def evidence():
        return {"status": "found", "results": [{"title": "公共人物", "content": "公共作品中的人物。", "url": "https://example.invalid/page"}], "cache_hit": False}

    def fake_client(self, calls, responses):
        class Client:
            def __init__(self, **options):
                self.options = options
                self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
            async def create(self, **request):
                calls.append((deepcopy(self.options), deepcopy(request)))
                if not responses:
                    raise AssertionError("Unexpected additional model call")
                message = responses.pop(0)
                if isinstance(message, BaseException):
                    raise message
                return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=getattr(message, "finish_reason", "stop"))], usage=getattr(message, "usage", None))
            async def close(self):
                pass
        return Client

    async def invoke(self, config, text, *, role="linyin", responses=None, history=None, observation=None, **kwargs):
        calls = []
        observation = {} if observation is None else observation
        service = SimpleNamespace(lookup=AsyncMock(return_value=self.evidence()))
        original_runner = self.graph.EncyclopediaGraphRunner
        def runner(**options):
            return original_runner(registry=self.graph.create_chat_tool_registry(service), **options)
        with (
            patch.object(self.llm, "AsyncOpenAI", self.fake_client(calls, list(responses or [SimpleNamespace(content="角色回复", tool_calls=[])]))),
            patch.object(self.llm, "EncyclopediaGraphRunner", side_effect=runner),
            patch.object(self.llm, "load_system_prompt", return_value="system"),
            patch.object(self.llm, "load_base_chat_prompt", return_value="base"),
            patch.object(self.llm, "load_persona_prompt", return_value="PRIVATE-ROLE-CARD"),
            patch.object(self.llm, "load_world_card_prompt", return_value="PRIVATE-WORLD"),
        ):
            reply = await self.llm.ask_llm(config, history or [], text, role_card_key=role, tool_observation=observation, **kwargs)
        return reply, calls, observation, service

    async def test_aike_model_tool_runs_registered_subgraph_then_final_reply(self):
        tool = SimpleNamespace(id="call-1", function=SimpleNamespace(name="lookup_unknown_slang", arguments=json.dumps({"candidate_terms": ["公共人物"], "query": "private sentence", "context_hint": "private context"})))
        reply, calls, obs, service = await self.invoke(self.config(), "这个角色是谁", role="aike", responses=[SimpleNamespace(content=None, tool_calls=[tool]), SimpleNamespace(content="爱可回复", tool_calls=[])])
        self.assertEqual(reply, "爱可回复")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1]["tool_choice"], "auto")
        self.assertEqual(calls[1][1]["tool_choice"], "none")
        self.assertIn("execute_public_encyclopedia", obs["encyclopedia_node_trace"])
        self.assertEqual(obs["encyclopedia_chat_requests"], 2)
        self.assertEqual(obs["encyclopedia_tool_statuses"], ["found"])
        self.assertTrue(obs["encyclopedia_evidence_provided"])
        service.lookup.assert_awaited_once_with({"candidate_terms": ["公共人物"]})
        self.assertEqual(calls[1][1]["messages"][-1]["role"], "tool")

    async def test_linyin_explicit_query_uses_one_persona_request_without_planner(self):
        _, calls, obs, service = await self.invoke(self.config(), "查一下初音未来")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]["model"], "slow-persona")
        self.assertNotIn("tools", calls[0][1])
        service.lookup.assert_awaited_once_with({"candidate_terms": ["初音未来"]})
        self.assertEqual(obs["encyclopedia_status"], "found")
        self.assertEqual(calls[0][1]["messages"][-1]["content"], "查一下初音未来")

    async def test_acceptance_questions_query_both_personas_before_one_reply(self):
        questions = [
            ("（你朝爱可微微一笑）爱可知不知道超时空辉夜姬", "超时空辉夜姬"),
            ("没有就考考凛音（你微微一笑）那凛音知道尼古猫猫吗？", "尼古猫猫"),
            ("凛音知道超时空辉夜姬的故事吗？", "超时空辉夜姬"),
            ("那凛音知道洛琪希吗？", "洛琪希"),
            ("凛音知道沃雅妮莎吗？", "沃雅妮莎"),
            ("那凛音知道奥黛塔吗", "奥黛塔"),
            ("爱可知道牛来吗", "牛来"),
            ("你听过《超辉夜姬！》吗？", "超辉夜姬！"),
        ]
        for role in ("aike", "linyin"):
            for text, term in questions:
                with self.subTest(role=role, text=text):
                    _, calls, obs, service = await self.invoke(self.config(), text, role=role)
                    service.lookup.assert_awaited_once_with({"candidate_terms": [term]})
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(calls[0][1]["model"], "slow-persona" if role == "linyin" else "fast-planner")
                    self.assertNotIn("tools", calls[0][1])
                    self.assertEqual(calls[0][1]["messages"][-1], {"role": "user", "content": text})
                    self.assertEqual(obs["encyclopedia_status"], "found")
                    self.assertEqual(obs["encyclopedia_trigger"], "direct_question")
                    self.assertEqual(obs["encyclopedia_plan_ms"], 0)
                    self.assertEqual(obs["encyclopedia_chat_requests"], 1)
                    self.assertFalse(obs["encyclopedia_planner_used"])
                    self.assertTrue(obs["encyclopedia_lookup_attempted"])
                    self.assertEqual(obs["encyclopedia_evidence_provided_count"], 1)
                    messages = calls[0][1]["messages"]
                    self.assertTrue(any(message["role"] == "system" and "应利用资料自然回答" in message["content"] for message in messages))
                    self.assertTrue(any(message["role"] == "user" and "公共作品中的人物" in message["content"] for message in messages))

    async def test_aike_short_lookup_also_avoids_duplicate_tool_request(self):
        _, calls, obs, service = await self.invoke(self.config(), "查一下初音未来", role="aike")
        self.assertEqual(len(calls), 1)
        self.assertNotIn("tools", calls[0][1])
        self.assertEqual(obs["encyclopedia_trigger"], "direct_command")
        service.lookup.assert_awaited_once_with({"candidate_terms": ["初音未来"]})

    async def test_explicit_only_mode_recognizes_knowledge_questions(self):
        _, calls, obs, service = await self.invoke(self.config(LINYIN_ENCYCLOPEDIA_AUTO="false"), "凛音知道沃雅妮莎吗？")
        self.assertEqual(len(calls), 1)
        self.assertEqual(obs["encyclopedia_status"], "found")
        service.lookup.assert_awaited_once_with({"candidate_terms": ["沃雅妮莎"]})

    async def test_direct_questions_respect_disabled_and_proactive_boundaries(self):
        for role in ("aike", "linyin"):
            for options in ({"allow_encyclopedia": False}, {}):
                config = self.config() if options else self.config(ENABLE_UNKNOWN_SLANG_TOOL="false")
                _, calls, obs, service = await self.invoke(config, "你知道沃雅妮莎吗？", role=role, **options)
                self.assertEqual(len(calls), 1)
                self.assertEqual(obs["encyclopedia_status"], "disabled")
                service.lookup.assert_not_awaited()

    async def test_scene_lookup_uses_owner_question_and_preserves_actor_context(self):
        actor_prompt = "PRIVATE-CONTINUITY and scene instructions"
        _, calls, obs, service = await self.invoke(self.config(), actor_prompt, encyclopedia_query_text="凛音知道沃雅妮莎吗？")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]["messages"][-1]["content"], actor_prompt)
        service.lookup.assert_awaited_once_with({"candidate_terms": ["沃雅妮莎"]})
        self.assertNotIn("PRIVATE", json.dumps(obs))

    async def test_direct_extraction_does_not_search_private_or_contextual_questions(self):
        for text in (
            "你知道我今天怎么了吗？", "你知道现在几点吗？", "你听过这个专名吗",
            "你知道那个朋友吗？", "你知道我同事小王吗？", "凛音知道主人住址吗？",
            "你知道123456789吗？", "你知道token:secret吗？", "你知道https://example.invalid吗？",
            "（未闭合的私人动作爱可知道牛来吗", "我问完工作情况。你知道牛来吗？",
            "你知道如何使用牛来吗？", "凛音知道今天是什么日子吗？",
        ):
            with self.subTest(text=text):
                self.assertEqual(self.graph.direct_lookup_terms(text), [])

    async def test_linyin_automatic_query_plans_without_private_history_then_calls_persona_once(self):
        history = [{"role": "user", "content": "PRIVATE-MEMORY"}]
        responses = [SimpleNamespace(content=json.dumps({"needed": True, "candidate_terms": ["公共人物"]}), tool_calls=[]), SimpleNamespace(content="凛音回复", tool_calls=[])]
        _, calls, obs, service = await self.invoke(self.config(), "你听过这个专名吗", responses=responses, history=history)
        self.assertEqual([call[1]["model"] for call in calls], ["fast-planner", "slow-persona"])
        planner_text = json.dumps(calls[0][1], ensure_ascii=False)
        for marker in ("PRIVATE-ROLE-CARD", "PRIVATE-WORLD", "PRIVATE-MEMORY"):
            self.assertNotIn(marker, planner_text)
        self.assertEqual(calls[0][0]["max_retries"], 0)
        self.assertEqual(calls[0][1]["response_format"], {"type": "json_object"})
        self.assertNotIn("tools", calls[0][1])
        self.assertEqual(obs["encyclopedia_mode"], "prefetch")
        self.assertTrue(obs["encyclopedia_planner_used"])
        self.assertTrue(obs["encyclopedia_plan_needed"])
        self.assertEqual(obs["encyclopedia_chat_requests"], 1)
        self.assertEqual(history, [{"role": "user", "content": "PRIVATE-MEMORY"}])
        service.lookup.assert_awaited_once()

    async def test_deepseek_planner_disables_thinking_only_for_planning_request(self):
        for config in (
            self.config(AIKE_LLM_MODEL="deepseek-v4-flash"),
            self.config(AIKE_LLM_MODEL="future-alias", AIKE_LLM_BASE_URL="https://api.deepseek.com/v1"),
        ):
            with self.subTest(model=config.aike_llm_model):
                responses = [SimpleNamespace(content='{"needed":true,"candidate_terms":["新海天"]}', tool_calls=[]),
                             SimpleNamespace(content="凛音回复", tool_calls=[])]
                _, calls, obs, service = await self.invoke(config,
                    "（你抚摸凛音的头）嗯，就这么抱着吧，凛音再问一遍你知道新海天是谁吗？", responses=responses)
                self.assertEqual(calls[0][1]["extra_body"], {"thinking": {"type": "disabled"}})
                self.assertEqual(calls[0][1]["max_tokens"], 512)
                self.assertNotIn("reasoning_effort", calls[0][1])
                self.assertNotIn("extra_body", calls[1][1])
                self.assertEqual(obs["encyclopedia_runs"][0]["planner"]["thinking_mode"], "disabled")
                self.assertEqual(obs["encyclopedia_status"], "found")
                service.lookup.assert_awaited_once_with({"candidate_terms": ["新海天"]})

    async def test_non_deepseek_planner_omits_vendor_thinking_parameter(self):
        responses = [SimpleNamespace(content='{"needed":false,"candidate_terms":[]}', tool_calls=[]),
                     SimpleNamespace(content="角色回复", tool_calls=[])]
        _, calls, obs, _ = await self.invoke(self.config(), "今天工作有些累", responses=responses)
        self.assertNotIn("extra_body", calls[0][1])
        self.assertEqual(obs["encyclopedia_runs"][0]["planner"]["thinking_mode"], "unspecified")

    async def test_deepseek_tool_followup_preserves_exact_reasoning_without_history_or_log_storage(self):
        reasoning = "PRIVATE-REASONING\n  保留原始空白  "
        tool = SimpleNamespace(id="call-1", function=SimpleNamespace(name="lookup_unknown_slang",
                               arguments=json.dumps({"candidate_terms": ["公共人物"]})))
        history = [{"role": "assistant", "content": "之前的正常回复"}]
        before = deepcopy(history)
        reply, calls, obs, service = await self.invoke(self.config(AIKE_LLM_MODEL="deepseek-v4-flash", AIKE_LLM_REASONING_EFFORT="max"),
            "先问一个公共角色", role="aike", history=history, responses=[
                SimpleNamespace(content=None, reasoning_content=reasoning, tool_calls=[tool]),
                SimpleNamespace(content="爱可最终回复", reasoning_content="PRIVATE-FINAL-REASONING", tool_calls=[]),
            ])
        followup = [message for message in calls[1][1]["messages"] if message.get("tool_calls")]
        self.assertEqual(len(followup), 1)
        self.assertEqual(followup[0]["reasoning_content"], reasoning)
        self.assertTrue(all(call[1]["reasoning_effort"] == "max" for call in calls))
        self.assertEqual(followup[0]["tool_calls"][0]["id"], "call-1")
        self.assertEqual(calls[1][1]["messages"][-1]["role"], "tool")
        self.assertEqual([call[1]["tool_choice"] for call in calls], ["auto", "none"])
        self.assertTrue(all("extra_body" not in call[1] for call in calls))
        self.assertEqual(reply, "爱可最终回复")
        self.assertEqual(history, before)
        self.assertNotIn("PRIVATE", json.dumps(obs))
        service.lookup.assert_awaited_once_with({"candidate_terms": ["公共人物"]})
        log_module = load_module("src.plugins.ai_chat.encyclopedia_observability", AI_CHAT_ROOT / "encyclopedia_observability.py")
        self.assertNotIn("PRIVATE", json.dumps(log_module.build_encyclopedia_turn_log(obs, "aike", reply=reply)))

    async def test_tool_failure_still_returns_original_deepseek_reasoning_to_model(self):
        tool = SimpleNamespace(id="call-1", function=SimpleNamespace(name="lookup_unknown_slang",
                               arguments=json.dumps({"candidate_terms": ["公共人物"]})))
        with patch.object(self, "evidence", return_value={"status": "source_unavailable", "results": []}):
            _, calls, obs, _ = await self.invoke(self.config(AIKE_LLM_MODEL="deepseek-v4-flash"),
                "先问一个公共角色", role="aike", responses=[
                    SimpleNamespace(content="", reasoning_content="PRIVATE-REASONING", tool_calls=[tool]),
                    SimpleNamespace(content="如实说明失败", tool_calls=[]),
                ])
        assistant = [message for message in calls[1][1]["messages"] if message.get("tool_calls")][0]
        self.assertEqual(assistant["reasoning_content"], "PRIVATE-REASONING")
        self.assertEqual(obs["encyclopedia_status"], "source_unavailable")
        self.assertNotIn("PRIVATE", json.dumps(obs))

    async def test_reasoning_serialisation_handles_missing_empty_and_non_deepseek_fields(self):
        for reasoning, expected in ((None, False), ("", True), ("思考", True), ({"private": "data"}, False)):
            with self.subTest(reasoning=reasoning):
                message = SimpleNamespace(content="", reasoning_content=reasoning, tool_calls=[])
                result = self.llm._assistant_message_with_tool_calls(message, include_reasoning=True)
                self.assertEqual("reasoning_content" in result, expected)
        missing = self.llm._assistant_message_with_tool_calls(SimpleNamespace(content="", tool_calls=[]), include_reasoning=True)
        self.assertNotIn("reasoning_content", missing)
        non_deepseek = self.llm._assistant_message_with_tool_calls(SimpleNamespace(content="", reasoning_content="思考", tool_calls=[]))
        self.assertNotIn("reasoning_content", non_deepseek)

    async def test_linyin_planner_declines_and_still_has_only_one_persona_request(self):
        responses = [SimpleNamespace(content='{"needed":false,"candidate_terms":[]}', tool_calls=[]), SimpleNamespace(content="陪伴回复", tool_calls=[])]
        _, calls, obs, service = await self.invoke(self.config(), "今天工作有些累", responses=responses)
        self.assertEqual(len(calls), 2)
        self.assertEqual(obs["encyclopedia_status"], "not_needed")
        self.assertTrue(obs["encyclopedia_planner_used"])
        self.assertFalse(obs["encyclopedia_plan_needed"])
        self.assertFalse(obs["encyclopedia_lookup_attempted"])
        service.lookup.assert_not_awaited()

    async def test_greeting_disabled_and_explicit_only_skip_auto_planner(self):
        for config, text in ((self.config(), "早安！"), (self.config(ENABLE_UNKNOWN_SLANG_TOOL="false"), "复杂专名"), (self.config(LINYIN_ENCYCLOPEDIA_AUTO="false"), "今天工作有些累")):
            _, calls, obs, service = await self.invoke(config, text)
            self.assertEqual(len(calls), 1)
            service.lookup.assert_not_awaited()
            self.assertIn(obs["encyclopedia_status"], {"skipped", "disabled"})

    async def test_scene_override_does_not_restore_double_linyin_call(self):
        _, calls, obs, _ = await self.invoke(self.config(), "查一下初音未来", completion_route="legacy")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]["model"], "fast-planner")
        self.assertNotIn("tools", calls[0][1])
        self.assertEqual(obs["encyclopedia_mode"], "prefetch")

    async def test_proactive_scene_is_not_allowed_to_query(self):
        _, calls, obs, service = await self.invoke(self.config(), "复杂专名", allow_encyclopedia=False)
        self.assertEqual(len(calls), 1)
        self.assertEqual(obs["encyclopedia_status"], "disabled")
        service.lookup.assert_not_awaited()

    async def test_invalid_plan_continues_persona_reply_with_failure_state(self):
        responses = [SimpleNamespace(content="bad JSON", tool_calls=[]), SimpleNamespace(content="继续回复", tool_calls=[])]
        reply, calls, obs, service = await self.invoke(self.config(), "复杂专名", responses=responses)
        self.assertEqual(reply, "继续回复")
        self.assertEqual(len(calls), 2)
        self.assertEqual(obs["encyclopedia_status"], "planner_invalid_response")
        self.assertIn("不能声称已核实", json.dumps(calls[-1][1], ensure_ascii=False))
        service.lookup.assert_not_awaited()

    async def test_planner_invalid_empty_and_truncated_output_remain_observable(self):
        cases = [
            (None, "stop", "planner_empty_response"),
            ('{"needed":true}', "length", "planner_response_truncated"),
            ('{"needed":"true","candidate_terms":["词条"]}', "stop", "planner_invalid_response"),
            ('{"needed":true,"candidate_terms":[]}', "stop", "planner_invalid_response"),
            ('{"needed":false,"candidate_terms":["词条"]}', "stop", "planner_invalid_response"),
            ('{"needed":false,"candidate_terms":[],"extra":"private"}', "stop", "planner_invalid_response"),
        ]
        for content, finish_reason, status in cases:
            with self.subTest(status=status, content=content):
                responses = [SimpleNamespace(content=content, finish_reason=finish_reason), SimpleNamespace(content="继续回复", tool_calls=[])]
                reply, calls, obs, service = await self.invoke(self.config(), "复杂专名", responses=responses)
                self.assertEqual(reply, "继续回复")
                self.assertEqual(len(calls), 2)
                self.assertEqual(obs["encyclopedia_status"], status)
                service.lookup.assert_not_awaited()
                self.assertNotIn("private", json.dumps(obs))

    async def test_direct_lookup_failure_still_generates_one_persona_reply(self):
        for role in ("aike", "linyin"):
            with self.subTest(role=role), patch.object(self, "evidence", return_value={"status": "source_unavailable", "results": []}):
                reply, calls, obs, service = await self.invoke(self.config(), "你知道牛来吗？", role=role)
                self.assertEqual(reply, "角色回复")
                self.assertEqual(len(calls), 1)
                self.assertNotIn("tools", calls[0][1])
                self.assertEqual(obs["encyclopedia_status"], "source_unavailable")
                service.lookup.assert_awaited_once()

    async def test_chat_failure_preserves_completed_lookup_observation(self):
        observation = {}
        with self.assertRaises(RuntimeError):
            await self.invoke(self.config(), "凛音知道牛来吗？", observation=observation, responses=[RuntimeError("PRIVATE-MODEL-ERROR")])
        self.assertEqual(observation["encyclopedia_status"], "found")
        self.assertTrue(observation["encyclopedia_evidence_provided"])
        self.assertEqual(observation["encyclopedia_chat_requests"], 1)
        self.assertNotIn("PRIVATE", json.dumps(observation))

    async def test_multiple_tools_preserve_prior_evidence_when_later_arguments_fail(self):
        first = SimpleNamespace(id="call-1", function=SimpleNamespace(name="lookup_unknown_slang", arguments=json.dumps({"candidate_terms": ["公共人物"]})))
        invalid = SimpleNamespace(id="call-2", function=SimpleNamespace(name="lookup_unknown_slang", arguments=json.dumps({"candidate_terms": []})))
        _, _, observation, service = await self.invoke(self.config(), "这个角色是谁", role="aike", responses=[SimpleNamespace(content=None, tool_calls=[first, invalid]), SimpleNamespace(content="回复", tool_calls=[])])
        self.assertEqual(observation["encyclopedia_tool_statuses"], ["found", "invalid_arguments"])
        self.assertTrue(observation["encyclopedia_lookup_attempted"])
        self.assertEqual(observation["encyclopedia_evidence_provided_count"], 1)
        service.lookup.assert_awaited_once()

    async def test_lookup_error_does_not_abort_graph(self):
        service = SimpleNamespace(lookup=AsyncMock(side_effect=RuntimeError("private error details")))
        runner = self.graph.EncyclopediaGraphRunner(registry=self.graph.create_chat_tool_registry(service))
        execution = await runner.run(arguments={"candidate_terms": ["公共词条"]})
        self.assertEqual(execution.observation["encyclopedia_status"], "lookup_error")
        self.assertNotIn("private", json.dumps(execution.observation))

    async def test_planner_provider_error_retains_safe_failure_code(self):
        runner = self.graph.EncyclopediaGraphRunner()
        planner = AsyncMock(side_effect=RuntimeError("403 PRIVATE-PLANNER-ERROR"))
        execution = await runner.run(text="复杂专名", planner=planner)
        self.assertEqual(execution.observation["encyclopedia_status"], "planner_error")
        self.assertEqual(execution.observation["encyclopedia_failure_code"], "authorization_failed")
        self.assertNotIn("PRIVATE", json.dumps(execution.observation))

    async def test_lookup_and_planner_have_whole_operation_timeout(self):
        cancelled = []
        async def slow(*args):
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.append(True)
        service = SimpleNamespace(lookup=slow)
        runner = self.graph.EncyclopediaGraphRunner(registry=self.graph.create_chat_tool_registry(service))
        runner.lookup_timeout_seconds = 0.01
        execution = await runner.run(arguments={"candidate_terms": ["词条"]})
        self.assertEqual(execution.observation["encyclopedia_status"], "lookup_timeout")
        runner.plan_timeout_seconds = 0.01
        execution = await runner.run(text="复杂专名", planner=slow)
        self.assertEqual(execution.observation["encyclopedia_status"], "planner_timeout")
        self.assertEqual(len(cancelled), 2)

    async def test_array_schema_validation_rejects_malformed_arguments(self):
        registry = self.graph.create_chat_tool_registry(SimpleNamespace(lookup=AsyncMock()))
        for arguments in ({"candidate_terms": "wrong"}, {"candidate_terms": []}, {"candidate_terms": [1]}, {"candidate_terms": ["a"], "path": "local-file"}):
            with self.assertRaises(ValueError):
                registry.validate_arguments("lookup_unknown_slang", arguments)
        self.assertEqual(registry.visible_tool_names(), ["lookup_unknown_slang"])

    async def test_public_cache_reuses_evidence_without_query_or_mutable_aliasing(self):
        service = self.service_module.EncyclopediaService()
        with patch.object(self.service_module, "_lookup_unknown_slang", AsyncMock(return_value=self.evidence())) as lookup:
            first = await service.lookup({"candidate_terms": ["词条"], "query": "private"})
            first["results"][0]["content"] = "changed"
            second = await service.lookup({"candidate_terms": ["词条"], "query": "different"})
        lookup.assert_awaited_once_with({"candidate_terms": ["词条"]})
        self.assertTrue(second["cache_hit"])
        self.assertEqual(second["results"][0]["content"], "公共作品中的人物。")

    async def test_page_without_content_is_not_usable_evidence(self):
        pages = self.service_module._extract_pages({"query": {"pages": {"1": {"title": "词条", "extract": ""}}}}, "词条")
        self.assertEqual(pages, [])

    async def test_empty_exact_page_falls_back_to_search_and_reports_no_content(self):
        client = SimpleNamespace()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        class Context:
            async def __aenter__(self):
                return client
            async def __aexit__(self, *args):
                return False
        empty = {"query": {"pages": {"1": {"title": "词条", "extract": ""}}}}
        request = AsyncMock(side_effect=[empty, ["词条", [], [], []]])
        with patch.object(self.service_module.httpx, "AsyncClient", return_value=Context()), patch.object(self.service_module, "_moegirl_request", request):
            result = await self.service_module._lookup_unknown_slang({"candidate_terms": ["词条"]})
        self.assertEqual(result["status"], "no_content")
        self.assertEqual(request.await_args_list[1].args[1]["action"], "opensearch")

    async def test_lookup_total_content_budget_and_fixed_external_endpoint(self):
        request = AsyncMock(side_effect=[{"query": {"pages": {str(index): {"title": str(index), "extract": "x" * 6000}}}} for index in range(3)])
        class Context:
            async def __aenter__(self):
                return SimpleNamespace()
            async def __aexit__(self, *args):
                return False
        with patch.object(self.service_module.httpx, "AsyncClient", return_value=Context()), patch.object(self.service_module, "_moegirl_request", request):
            result = await self.service_module._lookup_unknown_slang({"candidate_terms": ["a", "b", "c"]})
        self.assertLessEqual(sum(len(page["content"]) for page in result["results"]), 8000)
        self.assertEqual(result["status"], "found")

    async def test_bad_timeout_configuration_disables_query_instead_of_waiting(self):
        _, calls, obs, service = await self.invoke(self.config(ENCYCLOPEDIA_PLAN_TIMEOUT_SECONDS="bad"), "复杂专名")
        self.assertEqual(len(calls), 1)
        self.assertEqual(obs["encyclopedia_status"], "disabled")
        service.lookup.assert_not_awaited()

    async def test_complex_explicit_query_requires_public_keyword_plan(self):
        self.assertEqual(self.graph.direct_lookup_terms("查一下初音未来的生日是什么时候"), [])
        self.assertEqual(self.graph.direct_lookup_terms("查一下我今天说的那个人"), [])
        self.assertEqual(self.graph.direct_lookup_terms("查一下初音未来"), ["初音未来"])

    async def test_out_of_range_budgets_report_incomplete_policy(self):
        for values in ({"ENCYCLOPEDIA_PLAN_TIMEOUT_SECONDS": "99"}, {"ENCYCLOPEDIA_LOOKUP_TIMEOUT_SECONDS": "0"}):
            policy = self.policy.resolve_encyclopedia_policy(self.config(**values), "linyin")
            self.assertFalse(policy.planner_ready)

    async def test_current_message_is_the_only_planner_input_in_scene(self):
        responses = [SimpleNamespace(content='{"needed":false,"candidate_terms":[]}', tool_calls=[]), SimpleNamespace(content="角色回复", tool_calls=[])]
        _, calls, _, _ = await self.invoke(self.config(), "PRIVATE-CONTINUITY with public scene", encyclopedia_query_text="公共人物在什么作品里", responses=responses)
        self.assertEqual(calls[0][1]["messages"][-1]["content"], "公共人物在什么作品里")
        self.assertNotIn("PRIVATE-CONTINUITY", json.dumps(calls[0][1]))

    async def test_private_identifiers_are_not_external_search_terms(self):
        result = self.service_module._normalise_tool_terms({"candidate_terms": ["123456789", "token:secret", "初音未来"]})
        self.assertEqual(result, ["初音未来"])

    async def test_ollama_uses_prefetch_and_keeps_final_persona_contract(self):
        config = self.config(PERSONA_LLM_PROVIDER="ollama", PERSONA_LLM_API_KEY="")
        captured = []
        async def local(route, messages, **kwargs):
            captured.extend(messages)
            return "本地角色回复"
        with patch.object(self.llm, "_ask_ollama", side_effect=local):
            _, calls, obs, _ = await self.invoke(config, "查一下初音未来")
        self.assertEqual(calls, [])
        self.assertIn("动作描写", captured[-2]["content"])
        self.assertEqual(obs["encyclopedia_status"], "found")
        self.assertTrue(any("本轮公共百科资料" in message["content"] for message in captured))


class EncyclopediaChatGraphArtifactTests(unittest.TestCase):
    def test_outer_chatgraph_exposes_subgraph_observations(self):
        modules = load_pure_graph_modules()
        from test_graph_runners import ChatGraphRunnerTests
        fixture = ChatGraphRunnerTests()
        fixture.setUpClass()
        state = fixture.make_chat_state()
        observation = {"encyclopedia_status": "found", "encyclopedia_node_trace": ("execute_public_encyclopedia",)}
        async def call(_):
            return modules["contracts"].ChatRuntimeResult(reply="reply", stored_assistant="reply", tool_observation=observation)
        execution = asyncio.run(modules["chat"].ChatGraphRunner(call).run(state))
        self.assertEqual(execution.state.runtime.artifacts["encyclopedia_graph"], observation)
        self.assertEqual(execution.result.reply, "reply")


if __name__ == "__main__":
    unittest.main()
