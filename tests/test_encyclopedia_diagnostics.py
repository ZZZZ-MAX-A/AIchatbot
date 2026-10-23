from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from openai import AsyncOpenAI as RealAsyncOpenAI

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module
import test_encyclopedia_graph as graph_tests


class EncyclopediaDetailedDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        ensure_ai_chat_packages()
        cls.diagnostics = load_module("src.plugins.ai_chat.encyclopedia_diagnostics", AI_CHAT_ROOT / "encyclopedia_diagnostics.py")
        cls.logs = load_module("src.plugins.ai_chat.encyclopedia_observability", AI_CHAT_ROOT / "encyclopedia_observability.py")
        graph_tests.EncyclopediaGraphTests.setUpClass()

    def fixture(self):
        return graph_tests.EncyclopediaGraphTests()

    async def run_source(self, terms, handler, *, timeout=None, service=None, sink=None):
        fixture = self.fixture()
        module = fixture.service_module
        service = service or module.EncyclopediaService()
        runner = fixture.graph.EncyclopediaGraphRunner(registry=fixture.graph.create_chat_tool_registry(service))
        if timeout is not None:
            runner.lookup_timeout_seconds = timeout
        real_client = httpx.AsyncClient
        def client(**options):
            return real_client(transport=httpx.MockTransport(handler), **options)
        with patch.object(module.httpx, "AsyncClient", side_effect=client):
            return await runner.run(arguments={"candidate_terms": terms}, diagnostic_runs=sink)

    async def test_truncated_planner_exposes_usage_without_saving_reasoning_or_message(self):
        fixture = self.fixture()
        usage = SimpleNamespace(prompt_tokens=300, completion_tokens=512, total_tokens=812,
                                completion_tokens_details=SimpleNamespace(reasoning_tokens=512))
        responses = [SimpleNamespace(content="", reasoning_content="PRIVATE-REASONING", finish_reason="length", usage=usage),
                     SimpleNamespace(content="继续回复", tool_calls=[])]
        _, calls, obs, service = await fixture.invoke(fixture.config(), "夸奖以后再问一个公共角色", responses=responses)
        row = self.logs.build_encyclopedia_turn_log(obs, "linyin", reply="继续回复")
        plan = row["query_runs"][0]["planner"]
        self.assertEqual(row["status"], "planner_response_truncated")
        self.assertEqual(plan["finish_reason"], "length")
        self.assertEqual(plan["completion_tokens"], 512)
        self.assertEqual(plan["reasoning_tokens"], 512)
        self.assertEqual(plan["content_chars"], 0)
        self.assertEqual(plan["reasoning_chars"], len("PRIVATE-REASONING"))
        self.assertFalse(plan["json_valid"])
        self.assertEqual(plan["validation"], "length_limit")
        self.assertEqual(plan["sdk_max_retries"], 0)
        self.assertEqual(len(calls), 2)
        service.lookup.assert_not_awaited()
        self.assertNotIn("PRIVATE", json.dumps(obs))

    async def test_deepseek_nonthinking_setting_is_serialised_in_actual_sdk_request(self):
        fixture = self.fixture()
        requests = []
        def handler(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={
                "id": "test-response", "object": "chat.completion", "created": 0, "model": "deepseek-v4-flash",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant",
                              "content": '{"needed":true,"candidate_terms":["新海天"]}'}}],
                "usage": {"prompt_tokens": 300, "completion_tokens": 25, "total_tokens": 325,
                          "completion_tokens_details": {"reasoning_tokens": 0}},
            })
        def client(**options):
            return RealAsyncOpenAI(**options, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        with self.diagnostics.capture_query(8, 8) as diagnostics, patch.object(fixture.llm, "AsyncOpenAI", side_effect=client):
            plan = await fixture.llm._plan_public_encyclopedia(fixture.config(AIKE_LLM_MODEL="deepseek-v4-flash"),
                "（你抚摸凛音的头）嗯，就这么抱着吧，凛音再问一遍你知道新海天是谁吗？")
        self.assertEqual(plan, {"needed": True, "candidate_terms": ["新海天"]})
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["thinking"], {"type": "disabled"})
        self.assertNotIn("extra_body", requests[0])
        self.assertEqual(requests[0]["response_format"], {"type": "json_object"})
        self.assertEqual(requests[0]["max_tokens"], 512)
        safe = self.diagnostics.sanitise_query_runs([diagnostics])[0]
        self.assertEqual(safe["planner"]["thinking_mode"], "disabled")
        self.assertEqual(safe["planner"]["reasoning_tokens"], 0)
        self.assertEqual(safe["planner"]["validation"], "valid")

    async def test_valid_json_with_length_finish_is_visible_without_changing_policy(self):
        fixture = self.fixture()
        responses = [SimpleNamespace(content='{"needed":true,"candidate_terms":["公共词条"]}', finish_reason="length"),
                     SimpleNamespace(content="回复", tool_calls=[])]
        _, _, obs, service = await fixture.invoke(fixture.config(), "先聊两句再问公共词条", responses=responses)
        plan = self.logs.build_encyclopedia_turn_log(obs, "linyin", reply="回复")["query_runs"][0]["planner"]
        self.assertTrue(plan["json_valid"])
        self.assertEqual(plan["validation"], "length_limit")
        self.assertIsNone(plan["reasoning_tokens"])
        service.lookup.assert_not_awaited()

    async def test_invalid_json_has_safe_parse_position(self):
        fixture = self.fixture()
        responses = [SimpleNamespace(content='{"needed":\nPRIVATE-INVALID}', finish_reason="stop"),
                     SimpleNamespace(content="回复", tool_calls=[])]
        _, _, obs, _ = await fixture.invoke(fixture.config(), "先聊两句再问公共词条", responses=responses)
        plan = self.logs.build_encyclopedia_turn_log(obs, "linyin", reply="回复")["query_runs"][0]["planner"]
        self.assertEqual(plan["validation"], "invalid_json")
        self.assertEqual(plan["json_error_line"], 2)
        self.assertFalse(plan["json_valid"])
        self.assertNotIn("PRIVATE", json.dumps(obs))

    async def test_exact_search_and_page_requests_are_separate_and_cache_has_no_stale_requests(self):
        seen = []
        def handler(request):
            seen.append(request.url.params["action"])
            if len(seen) == 1:
                return httpx.Response(200, json={"query": {"pages": {"-1": {"missing": ""}}}})
            if len(seen) == 2:
                return httpx.Response(200, json=["词条", ["规范名称"], [], []])
            return httpx.Response(200, json={"query": {"pages": {"1": {"title": "规范名称", "extract": "公共正文"}}}})
        service = self.fixture().service_module.EncyclopediaService()
        first = await self.run_source(["公共别名"], handler, service=service)
        second = await self.run_source(["公共别名"], handler, service=service)
        run = first.observation["encyclopedia_runs"][0]
        self.assertEqual([event["phase"] for event in run["requests"]], ["exact", "search", "search_page"])
        self.assertEqual([event["http_status"] for event in run["requests"]], [200, 200, 200])
        self.assertEqual(run["requests"][0]["usable_pages"], 0)
        self.assertEqual(run["requests"][1]["search_results"], 1)
        self.assertEqual(run["requests"][2]["usable_pages"], 1)
        self.assertEqual(run["evidence_collected"], 1)
        cached = second.observation["encyclopedia_runs"][0]
        self.assertEqual(cached["cache"], "hit")
        self.assertEqual(cached["requests"], [])
        self.assertEqual(run["candidates"], cached["candidates"])
        self.assertNotIn("公共别名", json.dumps(run, ensure_ascii=False))
        self.assertEqual(len(seen), 3)

    async def test_deadline_keeps_earlier_evidence_and_inflight_transport_stage_visible(self):
        seen = []
        async def handler(request):
            seen.append(True)
            if len(seen) == 1:
                return httpx.Response(200, json={"query": {"pages": {"1": {"title": "词条一", "extract": "已经取得的正文"}}}})
            await request.extensions["trace"]("http11.receive_response_headers.started", {"PRIVATE": "PRIVATE-DATA"})
            await asyncio.sleep(10)
        execution = await self.run_source(["词条一", "词条二"], handler, timeout=0.03)
        run = execution.observation["encyclopedia_runs"][0]
        self.assertEqual(execution.observation["encyclopedia_status"], "lookup_timeout")
        self.assertEqual(run["timeout_origin"], "lookup_deadline")
        self.assertEqual(run["evidence_collected"], 1)
        self.assertEqual(run["requests"][1]["outcome"], "cancelled")
        self.assertEqual(run["requests"][1]["candidate_index"], 2)
        self.assertEqual(run["requests"][1]["transport_phase"], "receive_headers")
        self.assertNotIn("results", execution.evidence)
        self.assertNotIn("PRIVATE", json.dumps(run))

    async def test_read_timeout_and_http_error_are_distinct_from_total_budget_cancellation(self):
        def read_timeout(request):
            raise httpx.ReadTimeout("PRIVATE-URL", request=request)
        execution = await self.run_source(["公共词条"], read_timeout)
        run = execution.observation["encyclopedia_runs"][0]
        self.assertEqual(execution.observation["encyclopedia_status"], "source_unavailable")
        self.assertEqual(run["timeout_origin"], "none")
        self.assertEqual(run["requests"][0]["error_type"], "ReadTimeout")
        execution = await self.run_source(["公共词条"], lambda _: httpx.Response(503, text="PRIVATE-BODY"))
        event = execution.observation["encyclopedia_runs"][0]["requests"][0]
        self.assertEqual(event["http_status"], 503)
        self.assertEqual(event["error_type"], "HTTPStatusError")
        self.assertNotIn("PRIVATE", json.dumps(execution.observation))

    async def test_transport_failure_is_not_overwritten_by_connection_cleanup(self):
        async def handler(request):
            trace = request.extensions["trace"]
            await trace("http11.receive_response_body.started", {})
            await trace("http11.receive_response_body.failed", {"exception": "PRIVATE-ERROR"})
            await trace("http11.response_closed.started", {})
            raise httpx.ReadTimeout("PRIVATE-ERROR", request=request)
        execution = await self.run_source(["公共词条"], handler)
        event = execution.observation["encyclopedia_runs"][0]["requests"][0]
        self.assertEqual(event["transport_phase"], "receive_body")
        self.assertEqual(event["transport_failure_phase"], "receive_body")
        self.assertNotIn("PRIVATE", json.dumps(event))

    async def test_inner_timeout_is_not_mislabelled_as_graph_deadline(self):
        fixture = self.fixture()
        service = SimpleNamespace(lookup=AsyncMock(side_effect=TimeoutError("PRIVATE-INNER")))
        runner = fixture.graph.EncyclopediaGraphRunner(registry=fixture.graph.create_chat_tool_registry(service))
        execution = await runner.run(arguments={"candidate_terms": ["公共词条"]})
        self.assertEqual(execution.observation["encyclopedia_status"], "lookup_timeout")
        self.assertEqual(execution.observation["encyclopedia_runs"][0]["timeout_origin"], "operation_timeout")

    async def test_html_instead_of_json_and_mediawiki_api_error_are_visible(self):
        cases = [
            (httpx.Response(200, text="<html>PRIVATE-BODY</html>", headers={"content-type": "text/html"}), "invalid_json", "html", ""),
            (httpx.Response(200, json={"error": {"code": "ratelimited", "info": "PRIVATE-INFO"}}), "api_error", "json", "ratelimited"),
        ]
        for response, kind, content_type, api_error in cases:
            execution = await self.run_source(["公共词条"], lambda _: response)
            safe = self.diagnostics.sanitise_query_runs(execution.observation["encyclopedia_runs"])[0]
            self.assertEqual(safe["requests"][0]["response_kind"], kind)
            self.assertEqual(safe["requests"][0]["content_type"], content_type)
            self.assertEqual(safe["requests"][0]["api_error"], api_error)
            self.assertNotIn("PRIVATE", json.dumps(safe))

    async def test_concurrent_queries_do_not_share_diagnostics(self):
        async def lookup(arguments):
            term = arguments["candidate_terms"][0]
            await asyncio.sleep(0)
            self.diagnostics.current_query()["evidence_collected"] = 1 if term == "词条一" else 2
            return {"status": "found", "results": []}
        fixture = self.fixture()
        runner = fixture.graph.EncyclopediaGraphRunner(registry=fixture.graph.create_chat_tool_registry(SimpleNamespace(lookup=lookup)))
        first, second = await asyncio.gather(runner.run(arguments={"candidate_terms": ["词条一"]}),
                                             runner.run(arguments={"candidate_terms": ["词条二"]}))
        self.assertEqual(first.observation["encyclopedia_runs"][0]["evidence_collected"], 1)
        self.assertEqual(second.observation["encyclopedia_runs"][0]["evidence_collected"], 2)
        self.assertIsNone(self.diagnostics.current_query())

    async def test_external_cancellation_preserves_sink_without_calling_it_a_deadline(self):
        started = asyncio.Event()
        async def handler(request):
            started.set()
            await asyncio.sleep(10)
        sink = []
        task = asyncio.create_task(self.run_source(["公共词条"], handler, sink=sink))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(sink[0]["outcome"], "cancelled")
        self.assertEqual(sink[0]["timeout_origin"], "none")
        self.assertEqual(sink[0]["requests"][0]["outcome"], "cancelled")

    async def test_model_request_finish_reason_and_tool_choice_are_recorded(self):
        fixture = self.fixture()
        responses = [SimpleNamespace(content="PRIVATE-REPLY", finish_reason="length", tool_calls=[])]
        _, calls, obs, _ = await fixture.invoke(fixture.config(), "先问一个角色的背景", role="aike", responses=responses)
        row = self.logs.build_encyclopedia_turn_log(obs, "aike", reply="PRIVATE-REPLY")
        self.assertEqual(row["model_requests"][0]["finish_reason"], "length")
        self.assertEqual(row["model_requests"][0]["tool_choice"], "auto")
        self.assertEqual(row["model_requests"][0]["tool_calls"], 0)
        self.assertNotIn("PRIVATE", json.dumps(row))
        self.assertEqual(len(calls), 1)

    async def test_planner_cancelled_by_budget_is_not_reported_as_declining_lookup(self):
        fixture = self.fixture()
        started = asyncio.Event()
        async def slow(**_):
            started.set()
            await asyncio.sleep(10)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=slow)), close=AsyncMock())
        runner = fixture.graph.EncyclopediaGraphRunner()
        runner.plan_timeout_seconds = 0.02
        with patch.object(fixture.llm, "AsyncOpenAI", return_value=client):
            execution = await runner.run(text="复杂公共角色问句", planner=lambda text: fixture.llm._plan_public_encyclopedia(fixture.config(), text))
        self.assertTrue(started.is_set())
        run = execution.observation["encyclopedia_runs"][0]
        self.assertEqual(run["timeout_origin"], "plan_deadline")
        self.assertEqual(run["planner"]["validation"], "cancelled")
        self.assertIsNone(execution.observation["encyclopedia_plan_needed"])
        client.close.assert_awaited_once()

    async def test_multiple_tools_keep_independent_runs_and_final_reply_metadata(self):
        fixture = self.fixture()
        tools = [SimpleNamespace(id=f"call-{index}", function=SimpleNamespace(
            name="lookup_unknown_slang", arguments=json.dumps({"candidate_terms": [term]})))
            for index, term in enumerate(["词条一", "词条二"])]
        _, calls, obs, _ = await fixture.invoke(fixture.config(), "先问两个公共词条", role="aike", responses=[
            SimpleNamespace(content=None, tool_calls=tools, finish_reason="tool_calls"),
            SimpleNamespace(content="角色回复", tool_calls=[], finish_reason="stop"),
        ])
        row = self.logs.build_encyclopedia_turn_log(obs, "aike", reply="角色回复")
        self.assertEqual(len(row["query_runs"]), 2)
        self.assertNotEqual(row["query_runs"][0]["candidates"], row["query_runs"][1]["candidates"])
        self.assertEqual([item["tool_choice"] for item in row["model_requests"]], ["auto", "none"])
        self.assertEqual([item["finish_reason"] for item in row["model_requests"]], ["tool_calls", "stop"])
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
