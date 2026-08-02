from __future__ import annotations

import asyncio
import json
import unittest
from datetime import date

from pure_ai_chat_loader import load_tavily_search_modules


class FakeTavilyTransport:
    def __init__(self, *responses) -> None:
        self.responses = list(responses)
        self.calls = []

    async def post_json(
        self,
        endpoint,
        *,
        headers,
        json_body,
        timeout_seconds,
        max_response_bytes,
    ):
        self.calls.append(
            {
                "endpoint": endpoint,
                "headers": headers,
                "body": json_body,
                "timeout_seconds": timeout_seconds,
                "max_response_bytes": max_response_bytes,
            }
        )
        if not self.responses:
            raise AssertionError("unexpected Tavily transport call")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class CoordinatedTavilyTransport(FakeTavilyTransport):
    def __init__(self, *responses) -> None:
        super().__init__(*responses)
        self._both_started = asyncio.Event()

    async def post_json(self, endpoint, **kwargs):
        self.calls.append(
            {
                "endpoint": endpoint,
                "headers": kwargs["headers"],
                "body": kwargs["json_body"],
                "timeout_seconds": kwargs["timeout_seconds"],
                "max_response_bytes": kwargs["max_response_bytes"],
            }
        )
        if len(self.calls) == 2:
            self._both_started.set()
        await asyncio.wait_for(self._both_started.wait(), timeout=0.5)
        if not self.responses:
            raise AssertionError("unexpected Tavily transport call")
        return self.responses.pop(0)


class FakeSynthesisCall:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls = []

    async def __call__(self, messages):
        self.calls.append(messages)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class TavilyExternalReadExecutorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_tavily_search_modules()
        cls.tavily = cls.modules["tavily"]
        cls.executor_module = cls.modules["tavily_executor"]

    def response(self, body: str):
        return self.tavily.TavilyHttpResponse(
            status_code=200,
            content_type="application/json",
            body=body.encode("utf-8"),
        )

    def test_fixed_executor_maps_search_and_synthesis_to_ephemeral_payload(self):
        transport = FakeTavilyTransport(
            self.response(
                '{"results": ['
                '{"title": "Python 官方文档", '
                '"url": "https://docs.python.org/zh-cn/3/", '
                '"content": "Python 3 中文官方资料。", '
                '"score": 0.99, "raw_content": "Python 3 是官方维护的语言文档。"}'
                ']}'
            )
        )
        synthesis = FakeSynthesisCall(
            "直接回答：Python 官方文档可作为主要核对入口。[1]\n"
            "不确定性：当前证据只覆盖文档首页。"
        )
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            timeout_seconds=7,
            transport=transport,
            synthesis_call=synthesis,
        )

        payload = asyncio.run(executor("  Python 3 中文官方文档  "))

        self.assertEqual(len(transport.calls), 1)
        call = transport.calls[0]
        self.assertEqual(call["timeout_seconds"], 7)
        self.assertEqual(call["body"]["search_depth"], "advanced")
        self.assertEqual(call["body"]["chunks_per_source"], 2)
        self.assertEqual(call["body"]["max_results"], 10)
        self.assertFalse(call["body"]["include_answer"])
        self.assertFalse(call["body"]["include_raw_content"])
        self.assertFalse(call["body"]["include_images"])
        self.assertTrue(call["body"]["include_usage"])
        self.assertEqual(len(synthesis.calls), 1)
        self.assertEqual(payload.provider_name, "tavily")
        self.assertEqual(payload.result_count, 1)
        self.assertEqual(payload.source_host_count, 1)
        self.assertEqual(payload.external_request_count, 1)
        self.assertEqual(payload.provider_request_count, 1)
        self.assertEqual(payload.search_stage_count, 1)
        self.assertEqual(payload.official_stage_candidate_count, 1)
        self.assertEqual(payload.official_stage_result_count, 1)
        self.assertEqual(payload.media_stage_candidate_count, 0)
        self.assertEqual(payload.media_stage_result_count, 0)
        self.assertEqual(payload.synthesis_request_count, 1)
        self.assertEqual(payload.synthesis_status, "completed")
        self.assertEqual(payload.synthesis_error_category, "none")
        self.assertEqual(payload.owner_quality_status, "owner_quality_pending")
        self.assertEqual(payload.status_category, "completed")
        self.assertEqual(payload.error_category, "none")
        self.assertIn("Python 官方文档可作为主要核对入口", payload.report_text)
        self.assertNotIn("[1]", payload.report_text)
        self.assertNotIn("https://", payload.report_text)
        self.assertNotIn("Provider", payload.report_text)
        self.assertIn("https://docs.python.org/zh-cn/3/", payload.detail_text)
        self.assertNotIn("tvly-unit-secret", payload.detail_text)
        self.assertIn("来源 [1]", payload.detail_text)
        self.assertIn("Tavily 1 次", payload.detail_text)

    def test_main_agent_general_plan_uses_one_short_query_without_official_retry(self):
        transport = FakeTavilyTransport(
            self.response(
                '{"results":[{"title":"萍乡小吃推荐",'
                '"url":"https://travel.example/pingxiang",'
                '"content":"莲花血鸭、萍乡炒粉等本地小吃。"}]}'
            )
        )
        synthesis = FakeSynthesisCall("直接回答：可优先了解莲花血鸭和萍乡炒粉。[1]")
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
            synthesis_call=synthesis,
        )
        plan = self.modules["security"].ExternalReadSearchPlan(
            primary_query="萍乡 热门 小吃 推荐",
            primary_source_scope="general",
        )

        payload = asyncio.run(executor("萍乡热门的小吃有哪些", search_plan=plan))

        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(transport.calls[0]["body"]["query"], "萍乡 热门 小吃 推荐")
        self.assertLessEqual(len(transport.calls[0]["body"]["query"]), 50)
        self.assertNotIn("topic", transport.calls[0]["body"])
        self.assertEqual(payload.result_count, 1)
        self.assertEqual(payload.search_stage_count, 1)
        self.assertIn("莲花血鸭和萍乡炒粉", payload.report_text)
        self.assertNotIn("检索规划", payload.report_text)
        self.assertIn("检索规划：MainAgent；第一查询来源范围：general", payload.detail_text)
        self.assertIn("深度：advanced", payload.detail_text)
        self.assertIn("未执行第二阶段", payload.detail_text)

    def test_main_agent_official_plan_does_not_auto_run_media_when_unplanned(self):
        transport = FakeTavilyTransport(
            self.response(
                '{"results":[{"title":"媒体预测",'
                '"url":"https://example.com/prediction",'
                '"content":"第三方预测内容。"}]}'
            )
        )
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
            synthesis_call=FakeSynthesisCall("不应调用"),
        )
        plan = self.modules["security"].ExternalReadSearchPlan(
            primary_query="某政策 官方发布全文",
            primary_source_scope="official",
        )

        payload = asyncio.run(executor("查询某政策官方发布全文", search_plan=plan))

        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(payload.result_count, 0)
        self.assertEqual(payload.search_stage_count, 1)
        self.assertEqual(payload.dropped_source_policy_count, 1)

    def test_current_status_scene_adds_current_baseline_and_next_candidate(self):
        transport = CoordinatedTavilyTransport(
            self.response(
                '{"results":[{"title":"当前已上线版本",'
                '"url":"https://example.com/current",'
                '"content":"当前版本已经上线。",'
                '"published_date":"2026-07-20"}]}'
            ),
            self.response(
                '{"results":[{"title":"后续版本预告",'
                '"url":"https://example.org/next",'
                '"content":"后续版本仍处于预告阶段。",'
                '"published_date":"2026-07-28"}]}'
            ),
        )
        synthesis = FakeSynthesisCall(
            "当前已上线版本是 4.4；后续候选为 4.5，但仍需等待正式上线。[1][2]"
        )
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
            synthesis_call=synthesis,
            today_provider=lambda: date(2026, 7, 31),
        )
        plan = self.modules["security"].ExternalReadSearchPlan(
            primary_query="星铁 下一个版本 角色",
            primary_source_scope="official",
        )

        payload = asyncio.run(
            executor("星铁下一个版本有哪些角色", search_plan=plan)
        )

        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(
            {call["body"]["query"] for call in transport.calls},
            {"星铁 当前已上线版本 角色", "星铁 下一个版本 角色"},
        )
        self.assertEqual(payload.scene, "current_status")
        self.assertEqual(payload.primary_source_scope, "general")
        self.assertEqual(payload.secondary_source_scope, "news")
        self.assertEqual(payload.secondary_mode, "always")
        prompt = synthesis.calls[0][1]["content"]
        self.assertIn("业务场景：current_status", prompt)
        self.assertIn("证据角色：context", prompt)
        self.assertIn("证据角色：reported_candidate", prompt)

    def test_main_agent_can_plan_two_complementary_queries(self):
        transport = CoordinatedTavilyTransport(
            self.response(
                '{"results":[{"title":"7.0前瞻预告",'
                '"url":"https://genshin.hoyoverse.com/version",'
                '"content":"官方确认下一版本。"}]}'
            ),
            self.response(
                '{"results":[{"title":"新角色资料",'
                '"url":"https://example.com/characters",'
                '"content":"补充角色信息。"}]}'
            ),
        )
        synthesis = FakeSynthesisCall("直接回答：下一版本及角色已有两项证据。[1][2]")
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
            synthesis_call=synthesis,
        )
        plan = self.modules["security"].ExternalReadSearchPlan(
            primary_query="原神最新版本角色预告",
            primary_source_scope="news",
            primary_time_range="week",
            primary_evidence_role="official_confirmation",
            secondary_query="原神下一个版本角色",
            secondary_source_scope="news",
            secondary_time_range="month",
            secondary_evidence_role="reported_candidate",
            secondary_mode="always",
        )

        payload = asyncio.run(executor("原神下一个版本的角色是谁", search_plan=plan))

        self.assertEqual(len(transport.calls), 2)
        self.assertTrue(all(len(call["body"]["query"]) <= 50 for call in transport.calls))
        self.assertEqual(
            {call["body"]["query"] for call in transport.calls},
            {"原神当前已上线版本角色", "原神下一个版本角色"},
        )
        calls_by_query = {call["body"]["query"]: call for call in transport.calls}
        baseline_call = calls_by_query["原神当前已上线版本角色"]["body"]
        candidate_call = calls_by_query["原神下一个版本角色"]["body"]
        self.assertEqual(baseline_call["search_depth"], "advanced")
        self.assertNotIn("topic", baseline_call)
        self.assertNotIn("time_range", baseline_call)
        self.assertEqual(candidate_call["search_depth"], "basic")
        self.assertEqual(candidate_call["topic"], "news")
        self.assertEqual(candidate_call["time_range"], "month")
        self.assertTrue(all(call["body"]["max_results"] == 10 for call in transport.calls))
        self.assertEqual(baseline_call["chunks_per_source"], 2)
        self.assertNotIn("chunks_per_source", candidate_call)
        self.assertEqual(payload.result_count, 2)
        self.assertEqual(payload.official_stage_result_count, 1)
        self.assertEqual(payload.media_stage_result_count, 1)
        self.assertEqual(payload.dropped_source_policy_count, 0)
        self.assertIn("下一版本及角色已有两项证据", payload.report_text)
        self.assertNotIn("检索规划", payload.report_text)
        self.assertIn("第一查询来源范围：general；深度：advanced；时间范围：none", payload.detail_text)
        self.assertIn("第二查询来源范围：news；深度：basic；时间范围：month", payload.detail_text)
        self.assertIn("执行条件：always", payload.detail_text)
        self.assertIn("检索阶段：primary", synthesis.calls[0][1]["content"])
        self.assertIn("检索阶段：secondary", synthesis.calls[0][1]["content"])
        self.assertIn("证据角色：context", synthesis.calls[0][1]["content"])
        self.assertIn("证据角色：reported_candidate", synthesis.calls[0][1]["content"])

    def test_current_status_missing_baseline_skips_synthesis_and_hides_candidate(self):
        transport = FakeTavilyTransport(
            self.response('{"results":[]}'),
            self.response(
                '{"results":[{"title":"旧版本角色报道",'
                '"url":"https://gnn.gamer.com.tw/detail.php",'
                '"content":"吉尔伽美什是雷属性五星角色。",'
                '"published_date":"2026-07-10"}]}'
            ),
        )
        synthesis = FakeSynthesisCall("不应调用")
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
            synthesis_call=synthesis,
            today_provider=lambda: date(2026, 7, 31),
        )
        plan = self.modules["security"].ExternalReadSearchPlan(
            primary_query="星铁 当前版本 官方",
            primary_source_scope="official",
            primary_time_range="month",
            primary_evidence_role="context",
            secondary_query="星铁 下一个版本 角色",
            secondary_source_scope="news",
            secondary_time_range="month",
            secondary_evidence_role="official_confirmation",
            secondary_mode="always",
            scene="current_status",
        )

        payload = asyncio.run(
            executor("星铁当前版本和下一个版本有哪些角色", search_plan=plan)
        )

        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(synthesis.calls, [])
        self.assertEqual(payload.result_count, 1)
        self.assertEqual(payload.official_stage_result_count, 0)
        self.assertEqual(payload.media_stage_result_count, 1)
        self.assertEqual(payload.primary_source_scope, "general")
        self.assertEqual(payload.secondary_source_scope, "news")
        self.assertEqual(payload.synthesis_request_count, 0)
        self.assertEqual(
            payload.synthesis_status,
            "not_run_incomplete_evidence",
        )
        self.assertIn("没有找到可验证的当前状态基线", payload.report_text)
        self.assertIn("无法可靠判断真正的下一个", payload.report_text)
        self.assertNotIn("吉尔伽美什", payload.report_text)
        self.assertIn("吉尔伽美什", payload.detail_text)
        self.assertIn("当前状态证据不完整，未调用隔离综合", payload.detail_text)
        self.assertIn("第二查询来源范围：news", payload.detail_text)
        self.assertIn("证据角色：reported_candidate", payload.detail_text)

    def test_two_full_stages_deduplicate_before_reporting_stage_results(self):
        primary_results = [
            {
                "title": f"第一查询结果 {index}",
                "url": f"https://primary-{index}.example/item",
                "content": f"第一查询证据 {index}。",
            }
            for index in range(10)
        ]
        secondary_results = [
            {
                "title": "第二查询重复结果",
                "url": "https://primary-0.example/item",
                "content": "与第一查询重复的 URL。",
            },
            *[
                {
                    "title": f"第二查询结果 {index}",
                    "url": f"https://secondary-{index}.example/item",
                    "content": f"第二查询证据 {index}。",
                }
                for index in range(1, 10)
            ],
        ]
        transport = CoordinatedTavilyTransport(
            self.response(json.dumps({"results": primary_results}, ensure_ascii=False)),
            self.response(json.dumps({"results": secondary_results}, ensure_ascii=False)),
        )
        synthesis = FakeSynthesisCall("直接回答：两条查询均返回了可用证据。[1]")
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
            synthesis_call=synthesis,
        )
        plan = self.modules["security"].ExternalReadSearchPlan(
            primary_query="原神最新版本角色预告",
            primary_source_scope="news",
            primary_time_range="week",
            primary_evidence_role="official_confirmation",
            secondary_query="原神下一个版本角色",
            secondary_source_scope="news",
            secondary_time_range="month",
            secondary_evidence_role="reported_candidate",
            secondary_mode="always",
        )

        payload = asyncio.run(
            executor("原神下一个版本的角色是谁", search_plan=plan)
        )

        self.assertEqual(payload.provider_candidate_count, 20)
        self.assertEqual(payload.result_count, 19)
        self.assertEqual(payload.dropped_result_count, 1)
        self.assertEqual(payload.dropped_sanitization_count, 1)
        self.assertEqual(payload.official_stage_candidate_count, 10)
        self.assertEqual(payload.media_stage_candidate_count, 10)
        self.assertEqual(
            payload.official_stage_result_count + payload.media_stage_result_count,
            payload.result_count,
        )

    def test_no_results_runs_media_stage_once_then_stops_without_synthesis(self):
        transport = FakeTavilyTransport(
            self.response('{"results": []}'),
            self.response('{"results": []}'),
        )
        synthesis = FakeSynthesisCall("不应调用")
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
            synthesis_call=synthesis,
        )

        payload = asyncio.run(executor("公开天气信息"))

        self.assertEqual(len(transport.calls), 2)
        self.assertNotIn("topic", transport.calls[0]["body"])
        self.assertEqual(transport.calls[1]["body"]["topic"], "news")
        self.assertEqual(payload.result_count, 0)
        self.assertEqual(payload.status_category, "no_results")
        self.assertEqual(payload.external_request_count, 2)
        self.assertEqual(payload.provider_request_count, 2)
        self.assertEqual(payload.search_stage_count, 2)
        self.assertEqual(payload.synthesis_request_count, 0)
        self.assertEqual(payload.synthesis_status, "not_run_no_evidence")
        self.assertEqual(payload.synthesis_error_category, "none")
        self.assertEqual(payload.owner_quality_status, "not_applicable")
        self.assertEqual(synthesis.calls, [])
        self.assertIn("这次两阶段搜索", payload.report_text)
        self.assertNotIn("Tavily", payload.report_text)
        self.assertIn("本次两阶段搜索", payload.detail_text)
        self.assertIn("Tavily 2 次", payload.detail_text)

    def test_invalid_synthesis_falls_back_to_numbered_sources_without_retry(self):
        transport = FakeTavilyTransport(
            self.response('{"results": []}'),
            self.response(
                '{"results": [{"title":"公开资料",'
                '"url":"https://example.com/a?tracking=1",'
                '"content":"摘要。","raw_content":"正文证据。","score":0.9}]}'
            )
        )
        synthesis = FakeSynthesisCall("没有任何引用的断言")
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
            synthesis_call=synthesis,
        )

        payload = asyncio.run(executor("公开问题"))

        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(len(synthesis.calls), 1)
        self.assertEqual(payload.synthesis_status, "invalid_response")
        self.assertEqual(
            payload.synthesis_error_category,
            "response_contract_invalid",
        )
        self.assertEqual(payload.synthesis_request_count, 1)
        self.assertIn("回答综合步骤没有完成", payload.report_text)
        self.assertNotIn("https://", payload.report_text)
        self.assertIn("综合回复未通过本地引用合同", payload.detail_text)
        self.assertIn("https://example.com/a", payload.detail_text)
        self.assertNotIn("tracking=1", payload.detail_text)
        self.assertIn("官方来源阶段无合格证据", payload.detail_text)
        self.assertEqual(payload.search_stage_count, 2)
        self.assertEqual(payload.media_stage_result_count, 1)

    def test_factory_rejects_missing_key_and_unsafe_budget_before_network(self):
        transport = FakeTavilyTransport(self.response('{"results": []}'))
        with self.assertRaises(ValueError):
            self.executor_module.create_tavily_external_read_executor(
                api_key="",
                transport=transport,
            )
        with self.assertRaises(self.modules["security"].ExternalReadPolicyError):
            self.executor_module.create_tavily_external_read_executor(
                api_key="tvly-unit-secret",
                timeout_seconds=16,
                transport=transport,
            )
        self.assertEqual(transport.calls, [])

    def test_executor_repr_does_not_expose_api_key(self):
        transport = FakeTavilyTransport(self.response('{"results": []}'))
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
        )

        self.assertNotIn("tvly-unit-secret", repr(executor))

    def test_configured_factory_stays_absent_while_feature_is_disabled(self):
        transport = FakeTavilyTransport(self.response('{"results": []}'))

        executor = self.executor_module.create_configured_tavily_external_read_executor(
            feature_enabled=False,
            api_key="tvly-unit-secret",
            timeout_seconds=99,
            transport=transport,
        )

        self.assertIsNone(executor)
        self.assertEqual(transport.calls, [])

    def test_configured_factory_fails_closed_for_invalid_key_or_budget(self):
        transport = FakeTavilyTransport(self.response('{"results": []}'))

        missing_key = self.executor_module.create_configured_tavily_external_read_executor(
            feature_enabled=True,
            api_key="",
            timeout_seconds=10,
            transport=transport,
        )
        invalid_budget = self.executor_module.create_configured_tavily_external_read_executor(
            feature_enabled=True,
            api_key="tvly-unit-secret",
            timeout_seconds=16,
            transport=transport,
        )

        self.assertIsNone(missing_key)
        self.assertIsNone(invalid_budget)
        self.assertEqual(transport.calls, [])

    def test_configured_factory_builds_only_with_all_required_gates(self):
        transport = FakeTavilyTransport(self.response('{"results": []}'))

        executor = self.executor_module.create_configured_tavily_external_read_executor(
            feature_enabled=True,
            api_key="tvly-unit-secret",
            timeout_seconds=10,
            transport=transport,
        )

        self.assertIsInstance(executor, self.executor_module.TavilyExternalReadExecutor)
        self.assertEqual(transport.calls, [])

    def test_temporal_query_passes_absolute_window_and_filters_old_evidence(self):
        transport = FakeTavilyTransport(
            self.response(
                '{"results": ['
                '{"title":"Official July release","url":"https://openai.com/release",'
                '"content":"New model released.","raw_content":"Official details.",'
                '"published_date":"2026-07-10","score":0.9},'
                '{"title":"Old February release","url":"https://openai.com/old",'
                '"content":"Old model.","published_date":"2026-02-05","score":0.99},'
                '{"title":"Undated timeline","url":"https://openai.com/timeline",'
                '"content":"Rolling timeline without a reliable date.","score":0.8}'
                ']}'
            )
        )
        synthesis = FakeSynthesisCall("直接回答：窗口内有一项官方发布。[1]")
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
            synthesis_call=synthesis,
            today_provider=lambda: date(2026, 7, 28),
        )

        payload = asyncio.run(executor("当前日期往前一个月有哪些模型发布"))

        body = transport.calls[0]["body"]
        self.assertNotIn("topic", body)
        self.assertEqual(body["start_date"], "2026-06-28")
        self.assertEqual(body["end_date"], "2026-07-28")
        self.assertEqual(body["max_results"], 10)
        self.assertEqual(len(synthesis.calls), 1)
        synthesis_prompt = synthesis.calls[0][1]["content"]
        self.assertIn("2026-06-28 至 2026-07-28", synthesis_prompt)
        self.assertIn("可信当前日期：2026-07-28", synthesis_prompt)
        self.assertIn("Official July release", synthesis_prompt)
        self.assertNotIn("Old February release", synthesis_prompt)
        self.assertNotIn("Undated timeline", synthesis_prompt)
        self.assertEqual(payload.result_count, 1)
        self.assertEqual(payload.dropped_result_count, 2)
        self.assertEqual(payload.provider_candidate_count, 3)
        self.assertEqual(payload.dropped_missing_date_count, 1)
        self.assertEqual(payload.dropped_outside_window_count, 1)
        self.assertEqual(payload.dropped_weak_only_count, 0)
        self.assertEqual(payload.dropped_conflicting_date_count, 0)
        self.assertEqual(payload.dropped_injection_count, 0)
        self.assertEqual(payload.dropped_sanitization_count, 0)
        self.assertEqual(payload.dropped_source_policy_count, 0)
        self.assertEqual(payload.official_content_strong_count, 0)
        self.assertEqual(payload.owner_quality_status, "owner_quality_pending")

    def test_temporal_query_keeps_strict_official_english_content_date(self):
        transport = FakeTavilyTransport(
            self.response(
                '{"results": ['
                '{"title":"OpenAI releases Model X","url":"https://openai.com/model-x",'
                '"content":"The model became available July 12, 2026."},'
                '{"title":"Undated one","url":"https://one.example/a",'
                '"content":"No complete publication date."},'
                '{"title":"Undated two","url":"https://two.example/a",'
                '"content":"No complete publication date."},'
                '{"title":"Undated three","url":"https://three.example/a",'
                '"content":"No complete publication date."},'
                '{"title":"Undated four","url":"https://four.example/a",'
                '"content":"No complete publication date."}'
                ']}'
            )
        )
        synthesis = FakeSynthesisCall("直接回答：窗口内有一项官方发布。[1]")
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
            synthesis_call=synthesis,
            today_provider=lambda: date(2026, 7, 28),
        )

        payload = asyncio.run(executor("当前日期往前一个月有哪些模型发布"))

        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(len(synthesis.calls), 1)
        self.assertEqual(payload.provider_candidate_count, 5)
        self.assertEqual(payload.result_count, 1)
        self.assertEqual(payload.dropped_result_count, 4)
        self.assertEqual(payload.dropped_missing_date_count, 0)
        self.assertEqual(payload.dropped_source_policy_count, 4)
        self.assertEqual(payload.dropped_weak_only_count, 0)
        self.assertEqual(payload.official_content_strong_count, 1)
        synthesis_prompt = synthesis.calls[0][1]["content"]
        self.assertIn("official content strong evidence", synthesis_prompt)
        self.assertIn("发布日期：2026-07-12", synthesis_prompt)

    def test_trusted_planner_window_survives_main_agent_query_restatement(self):
        transport = FakeTavilyTransport(
            self.response(
                '{"results": ['
                '{"title":"Official July release","url":"https://openai.com/release",'
                '"content":"New model released.","published_date":"2026-07-10"},'
                '{"title":"Old January release","url":"https://openai.com/old",'
                '"content":"Old model.","published_date":"2026-01-05"}'
                ']}'
            )
        )
        synthesis = FakeSynthesisCall("直接回答：窗口内有一项官方发布。[1]")
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
            synthesis_call=synthesis,
            today_provider=lambda: date(2026, 7, 28),
        )
        trusted = self.modules["security"].rewrite_external_read_temporal_query(
            "当前日期往前一个月有哪些模型发布",
            reference_date=date(2026, 7, 28),
        )

        payload = asyncio.run(
            executor(
                "MainAgent 重述后只说查询模型发布，没有保留相对时间关键词",
                trusted_temporal_query=trusted,
            )
        )

        body = transport.calls[0]["body"]
        self.assertNotIn("topic", body)
        self.assertEqual(body["start_date"], "2026-06-28")
        self.assertEqual(body["end_date"], "2026-07-28")
        self.assertIn("2026-06-28 至 2026-07-28", body["query"])
        self.assertNotIn("没有保留相对时间关键词", body["query"])
        self.assertEqual(payload.result_count, 1)
        self.assertEqual(payload.dropped_result_count, 1)
        self.assertEqual(payload.provider_candidate_count, 2)
        self.assertEqual(payload.dropped_outside_window_count, 1)
        self.assertNotIn("Old January release", payload.report_text)
        self.assertEqual(len(synthesis.calls), 1)

    def test_temporal_query_stops_when_no_date_qualified_evidence(self):
        transport = FakeTavilyTransport(
            self.response(
                '{"results": ['
                '{"title":"Old February release","url":"https://example.com/old",'
                '"content":"Old model.","published_date":"2025-02-05"},'
                '{"title":"Weak July mention","url":"https://example.org/timeline",'
                '"content":"A model appeared on 2026-07-12."}'
                ']}'
            ),
            self.response(
                '{"results": ['
                '{"title":"Old February release","url":"https://example.com/old",'
                '"content":"Old model.","published_date":"2025-02-05"},'
                '{"title":"Weak July mention","url":"https://example.org/timeline",'
                '"content":"A model appeared on 2026-07-12."}'
                ']}'
            )
        )
        synthesis = FakeSynthesisCall("不应调用")
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
            synthesis_call=synthesis,
            today_provider=lambda: date(2026, 7, 28),
        )

        payload = asyncio.run(executor("最近一个月有哪些模型发布"))

        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(synthesis.calls, [])
        self.assertEqual(payload.result_count, 0)
        self.assertEqual(payload.dropped_result_count, 4)
        self.assertEqual(payload.provider_candidate_count, 4)
        self.assertEqual(payload.dropped_outside_window_count, 1)
        self.assertEqual(payload.dropped_weak_only_count, 1)
        self.assertEqual(payload.dropped_source_policy_count, 2)
        self.assertEqual(payload.search_stage_count, 2)
        self.assertEqual(payload.status_category, "no_results")
        self.assertEqual(payload.synthesis_request_count, 0)
        self.assertEqual(payload.owner_quality_status, "not_applicable")
        self.assertIn("2026-06-28 至 2026-07-28", payload.report_text)
        self.assertNotIn("本次未扩大查询，也未自动重试", payload.report_text)
        self.assertIn("已使用第二次查询扩大到 2026-01-28 至 2026-07-28", payload.detail_text)
        self.assertNotIn("Old February release", payload.detail_text)

    def test_media_fallback_keeps_same_question_and_window_but_changes_source_stage(self):
        transport = FakeTavilyTransport(
            self.response(
                '{"results":[{"title":"Independent preview",'
                '"url":"https://example.com/preview",'
                '"content":"No official evidence.",'
                '"published_date":"2026-07-11"}]}'
            ),
            self.response(
                '{"results":[{"title":"Reuters release report",'
                '"url":"https://www.reuters.com/technology/release",'
                '"content":"A release was reported.",'
                '"published_date":"2026-07-12"}]}'
            ),
        )
        synthesis = FakeSynthesisCall("直接回答：可靠媒体报道了一项发布。[1]")
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
            synthesis_call=synthesis,
            today_provider=lambda: date(2026, 7, 28),
        )

        payload = asyncio.run(executor("当前日期往前一个月有哪些模型发布"))

        self.assertEqual(len(transport.calls), 2)
        official_body = transport.calls[0]["body"]
        media_body = transport.calls[1]["body"]
        self.assertNotIn("topic", official_body)
        self.assertEqual(media_body["topic"], "news")
        self.assertEqual(official_body["start_date"], "2026-06-28")
        self.assertEqual(official_body["end_date"], "2026-07-28")
        self.assertIn("2026-06-28 至 2026-07-28", official_body["query"])
        self.assertEqual(media_body["start_date"], "2026-01-28")
        self.assertEqual(media_body["end_date"], "2026-07-28")
        self.assertIn("有哪些模型发布", media_body["query"])
        self.assertNotIn("2026-06-28 至 2026-07-28", media_body["query"])
        self.assertLessEqual(len(official_body["query"]), 50)
        self.assertLessEqual(len(media_body["query"]), 50)
        self.assertNotIn("仅检索第一方", official_body["query"])
        self.assertNotIn("可靠独立媒体", media_body["query"])
        self.assertNotIn("Independent preview", media_body["query"])
        self.assertEqual(payload.search_stage_count, 2)
        self.assertEqual(payload.official_stage_candidate_count, 1)
        self.assertEqual(payload.official_stage_result_count, 0)
        self.assertEqual(payload.media_stage_candidate_count, 1)
        self.assertEqual(payload.media_stage_result_count, 1)
        self.assertEqual(payload.dropped_source_policy_count, 1)
        self.assertEqual(payload.synthesis_request_count, 1)
        self.assertNotIn("媒体补充证据", payload.report_text)
        self.assertIn("媒体补充证据不能自动视为发布方官方确认", payload.detail_text)
        self.assertIn("检索阶段：media_fallback", synthesis.calls[0][1]["content"])
        self.assertIn("最近可确认结果扩窗", synthesis.calls[0][1]["content"])

    def test_vague_recent_query_defaults_month_then_falls_back_to_six_months(self):
        transport = FakeTavilyTransport(
            self.response('{"results": []}'),
            self.response(
                '{"results":[{"title":"Claude model update",'
                '"url":"https://www.anthropic.com/news/model-update",'
                '"content":"Anthropic announced a Claude model update.",'
                '"published_date":"2026-05-15"}]}'
            ),
        )
        synthesis = FakeSynthesisCall(
            "最近一个月内没有找到更新；扩大范围后，最近可确认的是 5 月 15 日发布。[1]"
        )
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
            synthesis_call=synthesis,
            today_provider=lambda: date(2026, 7, 31),
        )
        plan = self.modules["security"].ExternalReadSearchPlan(
            primary_query="Claude 模型更新",
            primary_source_scope="official",
            primary_evidence_role="official_confirmation",
        )

        payload = asyncio.run(
            executor(
                "帮我看一下 Claude 模型最近有什么更新",
                search_plan=plan,
            )
        )

        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(
            transport.calls[0]["body"]["start_date"],
            "2026-06-30",
        )
        self.assertEqual(
            transport.calls[1]["body"]["start_date"],
            "2026-01-31",
        )
        self.assertEqual(transport.calls[1]["body"]["end_date"], "2026-07-31")
        self.assertNotIn("topic", transport.calls[1]["body"])
        self.assertEqual(transport.calls[1]["body"]["search_depth"], "advanced")
        self.assertEqual(payload.secondary_source_scope, "general")
        self.assertEqual(payload.search_stage_count, 2)
        self.assertEqual(payload.synthesis_status, "completed")
        self.assertIn("最近一个月内没有找到更新", payload.report_text)
        synthesis_prompt = synthesis.calls[0][1]["content"]
        self.assertIn("可信当前日期：2026-07-31", synthesis_prompt)
        self.assertIn("主请求时间范围：2026-06-30 至 2026-07-31", synthesis_prompt)
        self.assertIn("第二查询时间范围：2026-01-31 至 2026-07-31", synthesis_prompt)
        self.assertIn("最近可确认结果扩窗", synthesis_prompt)

    def test_official_recent_zero_results_uses_general_reported_fallback(self):
        transport = FakeTavilyTransport(
            self.response(
                '{"results":[{"title":"Third-party Claude weekly report",'
                '"url":"https://example.com/claude-weekly",'
                '"content":"A dated third-party report.",'
                '"published_date":"2026-07-28"}]}'
            ),
            self.response(
                '{"results":[{"title":"Claude product update report",'
                '"url":"https://example.org/claude-update",'
                '"content":"An independently reported Claude update.",'
                '"published_date":"2026-05-15"}]}'
            ),
        )
        synthesis = FakeSynthesisCall(
            "原时间范围内没有官方确认；扩大到六个月后找到一项公开报道。[1]"
        )
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
            synthesis_call=synthesis,
            today_provider=lambda: date(2026, 7, 31),
        )
        plan = self.modules["security"].ExternalReadSearchPlan(
            primary_query="Claude 模型更新",
            primary_source_scope="official",
            primary_evidence_role="direct_answer",
        )

        payload = asyncio.run(
            executor(
                "帮我看一下最近一周 Claude 有什么更新",
                search_plan=plan,
            )
        )

        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(transport.calls[0]["body"]["start_date"], "2026-07-24")
        self.assertEqual(transport.calls[1]["body"]["start_date"], "2026-01-31")
        self.assertNotIn("topic", transport.calls[1]["body"])
        self.assertEqual(transport.calls[1]["body"]["search_depth"], "advanced")
        self.assertEqual(payload.result_count, 1)
        self.assertEqual(payload.dropped_source_policy_count, 1)
        self.assertEqual(payload.secondary_source_scope, "general")
        self.assertEqual(payload.synthesis_status, "completed")
        self.assertIn("证据角色：reported_candidate", synthesis.calls[0][1]["content"])

    def test_official_stage_timeout_fails_without_media_fallback(self):
        transport = FakeTavilyTransport(TimeoutError("fake timeout"))
        synthesis = FakeSynthesisCall("不应调用")
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
            synthesis_call=synthesis,
        )

        with self.assertRaises(
            self.modules["security"].ExternalReadStagePolicyError
        ) as raised:
            asyncio.run(executor("公开模型发布"))

        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(synthesis.calls, [])
        self.assertEqual(raised.exception.search_stage, "official")
        self.assertEqual(raised.exception.provider_request_count, 1)
        self.assertEqual(raised.exception.synthesis_request_count, 0)

    def test_official_stage_oversize_reports_safe_stage_context(self):
        transport = FakeTavilyTransport(
            self.tavily.TavilyHttpResponse(
                status_code=200,
                content_type="application/json",
                body=b"x" * 262_145,
            )
        )
        synthesis = FakeSynthesisCall("不应调用")
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
            synthesis_call=synthesis,
        )

        with self.assertRaises(
            self.modules["security"].ExternalReadStagePolicyError
        ) as raised:
            asyncio.run(executor("公开模型发布"))

        self.assertEqual(raised.exception.category.value, "response_too_large")
        self.assertEqual(raised.exception.search_stage, "official")
        self.assertEqual(raised.exception.provider_request_count, 1)
        self.assertEqual(raised.exception.synthesis_request_count, 0)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(synthesis.calls, [])

    def test_media_stage_oversize_reports_two_provider_requests(self):
        transport = FakeTavilyTransport(
            self.response(
                '{"results":[{"title":"Independent preview",'
                '"url":"https://example.com/preview",'
                '"content":"No official evidence."}]}'
            ),
            self.tavily.TavilyHttpResponse(
                status_code=200,
                content_type="application/json",
                body=b"x" * 262_145,
            ),
        )
        synthesis = FakeSynthesisCall("不应调用")
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
            synthesis_call=synthesis,
        )

        with self.assertRaises(
            self.modules["security"].ExternalReadStagePolicyError
        ) as raised:
            asyncio.run(executor("公开模型发布"))

        self.assertEqual(raised.exception.category.value, "response_too_large")
        self.assertEqual(raised.exception.search_stage, "media_fallback")
        self.assertEqual(raised.exception.provider_request_count, 2)
        self.assertEqual(raised.exception.synthesis_request_count, 0)
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(synthesis.calls, [])


if __name__ == "__main__":
    unittest.main()
