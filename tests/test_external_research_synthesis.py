from __future__ import annotations

import asyncio
import unittest
from datetime import date

from pure_ai_chat_loader import load_tavily_search_modules


class FakeLlmCall:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls = []

    async def __call__(self, messages):
        self.calls.append(messages)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeHttpError(RuntimeError):
    def __init__(self, status_code: int, *, body=None) -> None:
        super().__init__("provider detail must not be persisted")
        self.status_code = status_code
        self.body = body


class ExternalResearchSynthesisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        modules = load_tavily_search_modules()
        cls.search = modules["search"]
        cls.synthesis = modules["synthesis"]

    def result(
        self,
        title,
        host,
        *,
        score,
        raw_content,
        published_at="",
        date_evidence_strength="none",
        evidence_role="direct_answer",
        snippet=None,
    ):
        return self.search.SanitizedExternalSearchResult(
            title=title,
            snippet=snippet if snippet is not None else f"{title} 摘要",
            source_host=host,
            source_url=f"https://{host}/{title.lower()}",
            published_at=published_at,
            raw_content=raw_content,
            score=score,
            date_evidence_strength=date_evidence_strength,
            evidence_role=evidence_role,
        )

    def test_evidence_selection_prefers_distinct_hosts_and_enforces_budget(self):
        results = (
            self.result("A", "one.example", score=0.99, raw_content="甲" * 5000),
            self.result("B", "one.example", score=0.98, raw_content="乙" * 5000),
            self.result("C", "two.example", score=0.97, raw_content="丙" * 5000),
            self.result("D", "three.example", score=0.96, raw_content="丁" * 5000),
        )

        evidence = self.synthesis.select_external_research_evidence(
            results,
            query="公开信息",
        )

        self.assertEqual(
            [item.source_host for item in evidence],
            ["one.example", "two.example", "three.example", "one.example"],
        )
        self.assertLessEqual(sum(len(item.content) for item in evidence), 12000)
        self.assertTrue(all(len(item.content) <= 3500 for item in evidence))
        self.assertEqual([item.citation_index for item in evidence], [1, 2, 3, 4])
        self.assertTrue(evidence[0].content.startswith("相关语义片段：A 摘要"))
        self.assertEqual(evidence[0].fallback_summary, "A 摘要")

    def test_injection_suspected_result_never_enters_synthesis_evidence(self):
        result = self.search.SanitizedExternalSearchResult(
            title="Unsafe",
            snippet="外部结果正文已省略。",
            source_host="unsafe.example",
            source_url="https://unsafe.example/a",
            raw_content="",
            score=1.0,
            injection_suspected=True,
        )

        evidence = self.synthesis.select_external_research_evidence(
            (result,),
            query="公开问题",
        )

        self.assertEqual(evidence, ())

    def test_one_zero_tool_call_returns_bounded_text_with_valid_citations(self):
        evidence = self.synthesis.select_external_research_evidence(
            (
                self.result(
                    "A",
                    "one.example",
                    score=0.9,
                    raw_content="可核对事实。",
                    evidence_role="reported_candidate",
                ),
            ),
            query="公开问题",
        )
        llm = FakeLlmCall(
            {"content": "直接回答：这是可核对结论。[1]\n不确定性：只有一个来源。"}
        )

        result = asyncio.run(
            self.synthesis.synthesize_external_research_answer(
                "公开问题",
                evidence,
                llm,
            )
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.request_count, 1)
        self.assertEqual(result.error_category, "none")
        self.assertEqual(result.citation_indices, (1,))
        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(
            [message["role"] for message in llm.calls[0]],
            ["system", "user"],
        )
        self.assertNotIn("tools", repr(llm.calls[0]).lower())
        self.assertIn("[1]", result.answer_text)
        self.assertIn("证据角色：reported_candidate", llm.calls[0][1]["content"])
        self.assertIn("先直接回答用户要求的实体或事实", llm.calls[0][0]["content"])
        self.assertIn("通常写 800–1800 字", llm.calls[0][0]["content"])
        self.assertIn("不要固定使用", llm.calls[0][0]["content"])

    def test_current_status_scene_adds_lifecycle_baseline_guidance(self):
        evidence = self.synthesis.select_external_research_evidence(
            (
                self.result(
                    "当前版本",
                    "example.com",
                    score=0.9,
                    raw_content="",
                    evidence_role="context",
                ),
                self.result(
                    "后续候选",
                    "example.org",
                    score=0.8,
                    raw_content="",
                    evidence_role="reported_candidate",
                ),
            ),
            query="下一个版本是什么",
        )

        messages = self.synthesis.build_external_research_messages(
            "下一个版本是什么",
            evidence,
            trusted_current_date=date(2026, 7, 31),
            scene="current_status",
        )
        user_message = messages[1]["content"]

        self.assertIn("业务场景：current_status", user_message)
        self.assertIn("先依据 context 证据建立", user_message)
        self.assertIn("已经上线或事件日期已经过去的对象不得称为“下一个”", user_message)
        self.assertIn("无法确认真正的下一个对象", user_message)

    def test_current_status_evidence_coverage_requires_both_search_stages(self):
        baseline = self.synthesis.ExternalResearchEvidence(
            citation_index=1,
            title="当前版本",
            source_host="example.com",
            source_url="https://example.com/current",
            published_at="2026-07-20",
            content="当前版本已经上线。",
            fallback_summary="当前版本已经上线。",
            score=0.9,
            search_stage="primary",
            evidence_role="context",
        )
        candidate = self.synthesis.ExternalResearchEvidence(
            citation_index=2,
            title="后续候选",
            source_host="example.org",
            source_url="https://example.org/next",
            published_at="2026-07-28",
            content="后续候选仍待确认。",
            fallback_summary="后续候选仍待确认。",
            score=0.8,
            search_stage="secondary",
            evidence_role="reported_candidate",
        )

        self.assertFalse(
            self.synthesis.current_status_evidence_coverage((candidate,)).complete
        )
        self.assertFalse(
            self.synthesis.current_status_evidence_coverage((baseline,)).complete
        )
        self.assertTrue(
            self.synthesis.current_status_evidence_coverage(
                (baseline, candidate)
            ).complete
        )

    def test_current_status_default_fallback_never_exposes_orphan_candidate(self):
        evidence = (
            self.synthesis.ExternalResearchEvidence(
                citation_index=1,
                title="旧版本角色报道",
                source_host="gnn.gamer.com.tw",
                source_url="https://gnn.gamer.com.tw/detail.php",
                published_at="2026-07-10",
                content="吉尔伽美什是雷属性五星角色。",
                fallback_summary="吉尔伽美什是雷属性五星角色。",
                score=0.9,
                search_stage="secondary",
                evidence_role="reported_candidate",
            ),
        )

        response = self.synthesis.format_external_research_default_response(
            evidence=evidence,
            synthesis=self.synthesis.ExternalResearchSynthesis(
                status="not_run_incomplete_evidence",
                request_count=0,
            ),
            query="星铁下一个版本有哪些角色",
            search_stage_count=2,
            scene="current_status",
            current_status_requires_candidate=True,
        )

        self.assertIn("没有找到可验证的当前状态基线", response)
        self.assertIn("无法可靠判断真正的下一个", response)
        self.assertNotIn("吉尔伽美什", response)

    def test_invalid_scene_is_rejected_before_synthesis_call(self):
        llm = FakeLlmCall("不应调用")

        with self.assertRaisesRegex(ValueError, "scene is invalid"):
            asyncio.run(
                self.synthesis.synthesize_external_research_answer(
                    "公开问题",
                    (),
                    llm,
                    scene="must-not-leak",
                )
            )

        self.assertEqual(llm.calls, [])

    def test_synthesis_call_uses_smaller_budget_than_retrieval_evidence(self):
        evidence = self.synthesis.select_external_research_evidence(
            tuple(
                self.result(
                    f"Evidence {index}",
                    f"source-{index}.example",
                    score=1.0 - index / 100,
                    raw_content="",
                    snippet=(f"GPT-5.6 对比 GPT-5.5 证据 {index}。" + "甲" * 900),
                )
                for index in range(10)
            ),
            query="GPT-5.6 比 GPT-5.5 提升了哪些地方",
        )
        llm = FakeLlmCall("直接回答：有多项提升。[1]")

        result = asyncio.run(
            self.synthesis.synthesize_external_research_answer(
                "GPT-5.6 比 GPT-5.5 提升了哪些地方",
                evidence,
                llm,
            )
        )

        self.assertEqual(len(evidence), 10)
        self.assertEqual(result.status, "completed")
        self.assertEqual(len(llm.calls), 1)
        user_message = llm.calls[0][1]["content"]
        self.assertIn("[4] 标题", user_message)
        self.assertNotIn("[5] 标题", user_message)
        self.assertLessEqual(len(user_message), 6500)

    def test_synthesis_rejects_uncorrected_past_date_as_upcoming(self):
        evidence = self.synthesis.select_external_research_evidence(
            (
                self.result(
                    "旧版本预告",
                    "example.com",
                    score=0.9,
                    raw_content="",
                    published_at="2026-07-01",
                    snippet="4.4 版本原计划于 2026 年 7 月 15 日上线。",
                ),
            ),
            query="下一个版本是什么",
        )
        llm = FakeLlmCall("4.4 版本即将于 7 月 15 日上线。[1]")

        result = asyncio.run(
            self.synthesis.synthesize_external_research_answer(
                "下一个版本是什么",
                evidence,
                llm,
                trusted_current_date=date(2026, 7, 31),
            )
        )

        self.assertEqual(result.status, "invalid_response")
        self.assertEqual(result.error_category, "response_contract_invalid")

    def test_synthesis_accepts_explicit_time_correction_for_past_plan(self):
        evidence = self.synthesis.select_external_research_evidence(
            (
                self.result(
                    "旧版本预告",
                    "example.com",
                    score=0.9,
                    raw_content="",
                    published_at="2026-07-01",
                    snippet="4.4 版本原计划于 2026 年 7 月 15 日上线。",
                ),
            ),
            query="下一个版本是什么",
        )
        llm = FakeLlmCall(
            "原报道计划于 7 月 15 日上线，该日期现已过去，"
            "但本次证据无法确认是否按期上线。[1]"
        )

        result = asyncio.run(
            self.synthesis.synthesize_external_research_answer(
                "下一个版本是什么",
                evidence,
                llm,
                trusted_current_date=date(2026, 7, 31),
            )
        )

        self.assertEqual(result.status, "completed")
        self.assertIn("日期现已过去", result.answer_text)

    def test_synthesis_budget_prioritizes_official_query_focused_evidence(self):
        evidence = self.synthesis.select_external_research_evidence(
            (
                *(
                    self.result(
                        f"媒体背景 {index}",
                        f"media-{index}.example",
                        score=0.99 - index / 100,
                        raw_content="",
                        evidence_role="context",
                        snippet="页面导航。与问题关系较弱的背景资料。",
                    )
                    for index in range(6)
                ),
                self.result(
                    "Official release notes",
                    "openai.com",
                    score=0.60,
                    raw_content="",
                    evidence_role="official_confirmation",
                    snippet=(
                        "Navigation. GPT-5.6 improved coding performance compared with "
                        "GPT-5.5. More navigation."
                    ),
                ),
            ),
            query="GPT-5.6 比 GPT-5.5 提升了哪些地方",
        )
        llm = FakeLlmCall("直接回答：编程性能有所提升。[7]")

        result = asyncio.run(
            self.synthesis.synthesize_external_research_answer(
                "GPT-5.6 比 GPT-5.5 提升了哪些地方",
                evidence,
                llm,
            )
        )

        self.assertEqual(result.status, "completed")
        user_message = llm.calls[0][1]["content"]
        self.assertIn("[7] 标题：Official release notes", user_message)
        self.assertIn("improved coding performance", user_message)
        self.assertNotIn("[5] 标题：媒体背景", user_message)

    def test_synthesis_neutralizes_unrequested_sensitive_technical_detail(self):
        evidence = self.synthesis.select_external_research_evidence(
            (
                self.result(
                    "Model comparison",
                    "openai.com",
                    score=0.9,
                    raw_content="",
                    evidence_role="official_confirmation",
                    snippet=(
                        "GPT-5.6 improved overall performance. "
                        "ExploitBench autonomous attack details were also evaluated."
                    ),
                ),
            ),
            query="GPT-5.6 比 GPT-5.5 提升了哪些地方",
        )
        llm = FakeLlmCall("直接回答：总体性能有所提升。[1]")

        asyncio.run(
            self.synthesis.synthesize_external_research_answer(
                "GPT-5.6 比 GPT-5.5 提升了哪些地方",
                evidence,
                llm,
            )
        )

        user_message = llm.calls[0][1]["content"]
        self.assertIn("improved overall performance", user_message)
        self.assertIn("具体操作性细节未送入综合模型", user_message)
        self.assertNotIn("autonomous attack", user_message)

    def test_invalid_or_failed_model_response_is_safe_and_never_retried(self):
        evidence = self.synthesis.select_external_research_evidence(
            (
                self.result(
                    "A",
                    "one.example",
                    score=0.9,
                    raw_content="可核对事实。",
                ),
            ),
            query="公开问题",
        )
        cases = (
            ("无引用回答", "invalid_response", "response_contract_invalid"),
            ("错误编号 [2]", "invalid_response", "response_contract_invalid"),
            ('{"action":"tool_request","tool_name":"web"} [1]', "invalid_response", "response_contract_invalid"),
            (TimeoutError("must-not-leak"), "call_failed", "timeout"),
            (FakeHttpError(401), "call_failed", "authentication_failed"),
            (FakeHttpError(429), "call_failed", "rate_limited"),
            (FakeHttpError(400), "call_failed", "request_rejected"),
            (
                FakeHttpError(
                    400,
                    body={"error": {"code": "context_length_exceeded"}},
                ),
                "call_failed",
                "request_too_large",
            ),
            (
                FakeHttpError(
                    400,
                    body={"error": {"code": "content_filter"}},
                ),
                "call_failed",
                "content_policy_rejected",
            ),
            (ConnectionError("must-not-leak"), "call_failed", "connection_failed"),
            (RuntimeError("Authorization: Bearer must-not-leak"), "call_failed", "unexpected_failure"),
        )
        for response, status, category in cases:
            with self.subTest(status=status, category=category):
                llm = FakeLlmCall(response)
                result = asyncio.run(
                    self.synthesis.synthesize_external_research_answer(
                        "公开问题",
                        evidence,
                        llm,
                    )
                )
                self.assertEqual(result.status, status)
                self.assertEqual(result.error_category, category)
                self.assertEqual(result.request_count, 1)
                self.assertEqual(len(llm.calls), 1)
                self.assertNotIn("must-not-leak", repr(result))

    def test_success_formatter_shows_only_sources_actually_cited(self):
        evidence = self.synthesis.select_external_research_evidence(
            (
                self.result("A", "one.example", score=0.9, raw_content="正文甲。"),
                self.result("B", "two.example", score=0.8, raw_content="正文乙。"),
            ),
            query="公开问题",
        )
        synthesis = self.synthesis.ExternalResearchSynthesis(
            status="completed",
            request_count=1,
            answer_text="结论只由第一条支持。[1]",
            citation_indices=(1,),
        )

        response = self.synthesis.format_external_research_response(
            provider_name="tavily",
            evidence=evidence,
            synthesis=synthesis,
            query="公开问题",
        )

        self.assertIn("https://one.example/a", response)
        self.assertNotIn("https://two.example/b", response)

    def test_default_response_prioritizes_answer_and_hides_evidence_chrome(self):
        evidence = self.synthesis.select_external_research_evidence(
            (
                self.result("萍乡美食", "jx.people.com.cn", score=0.9, raw_content=""),
                self.result("传统小吃", "www.ly.com", score=0.8, raw_content=""),
            ),
            query="萍乡有什么特色美食",
        )
        synthesis = self.synthesis.ExternalResearchSynthesis(
            status="completed",
            request_count=1,
            answer_text=(
                "直接回答：萍乡可以重点尝试莲花血鸭、萍乡小炒肉和搓菜炒粉。[1]\n\n"
                "如果喜欢传统小吃，还可以留意手工挂面和老月饼。[2]"
            ),
            citation_indices=(1, 2),
        )

        response = self.synthesis.format_external_research_default_response(
            evidence=evidence,
            synthesis=synthesis,
            query="萍乡有什么特色美食",
        )

        self.assertTrue(response.startswith("萍乡可以重点尝试"))
        self.assertIn("手工挂面和老月饼", response)
        self.assertNotIn("直接回答：", response)
        self.assertNotIn("[1]", response)
        self.assertNotIn("来源", response)
        self.assertNotIn("Provider", response)
        self.assertNotIn("https://", response)

    def test_default_fallback_keeps_useful_highlights_but_hides_sources(self):
        evidence = self.synthesis.select_external_research_evidence(
            (
                self.result(
                    "萍乡美食",
                    "jx.people.com.cn",
                    score=0.9,
                    raw_content="",
                    snippet="莲花血鸭、搓菜炒粉和萍乡小炒肉是当地代表性美食。",
                ),
            ),
            query="萍乡有什么特色美食",
        )

        response = self.synthesis.format_external_research_default_response(
            evidence=evidence,
            synthesis=self.synthesis.ExternalResearchSynthesis(
                status="call_failed",
                request_count=1,
                error_category="request_rejected",
            ),
            query="萍乡有什么特色美食",
        )

        self.assertIn("莲花血鸭", response)
        self.assertIn("尚未形成完整综合结论", response)
        self.assertNotIn("jx.people.com.cn", response)
        self.assertNotIn("request_rejected", response)

    def test_official_content_strong_label_is_explicit_in_prompt_and_response(self):
        evidence = self.synthesis.select_external_research_evidence(
            (
                self.result(
                    "Official release",
                    "openai.com",
                    score=0.9,
                    raw_content="Official evidence.",
                    published_at="2026-07-12",
                    date_evidence_strength="official_content_strong",
                ),
            ),
            query="2026-06-28 至 2026-07-28 的模型发布",
        )
        messages = self.synthesis.build_external_research_messages(
            "2026-06-28 至 2026-07-28 的模型发布",
            evidence,
        )
        response = self.synthesis.format_external_research_response(
            provider_name="tavily",
            evidence=evidence,
            synthesis=self.synthesis.ExternalResearchSynthesis(
                status="completed",
                request_count=1,
                answer_text="直接回答：有一项官方发布。[1]",
                citation_indices=(1,),
            ),
            query="2026-06-28 至 2026-07-28 的模型发布",
        )

        self.assertIn("official content strong evidence", messages[1]["content"])
        self.assertIn("固定官方域名正文的唯一窗口内完整日期", response)

    def test_call_failure_and_contract_failure_have_distinct_fallback_messages(self):
        evidence = self.synthesis.select_external_research_evidence(
            (self.result("A", "one.example", score=0.9, raw_content="网页导航噪音。"),),
            query="公开问题",
        )
        call_failed = self.synthesis.format_external_research_response(
            provider_name="tavily",
            evidence=evidence,
            synthesis=self.synthesis.ExternalResearchSynthesis(
                status="call_failed",
                request_count=1,
                error_category="timeout",
            ),
            query="公开问题",
        )
        invalid = self.synthesis.format_external_research_response(
            provider_name="tavily",
            evidence=evidence,
            synthesis=self.synthesis.ExternalResearchSynthesis(
                status="invalid_response",
                request_count=1,
                error_category="response_contract_invalid",
            ),
            query="公开问题",
        )

        self.assertIn("隔离综合模型调用失败", call_failed)
        self.assertIn("综合回复未通过本地引用合同", invalid)
        self.assertIn("综合失败类别：timeout", call_failed)
        self.assertIn("要点：A 摘要", call_failed)
        self.assertNotIn("网页导航噪音", call_failed)

    def test_failed_synthesis_shows_only_three_query_focused_highlights(self):
        results = [
            self.result(
                "媒体比较一",
                "media-one.example",
                score=0.99,
                raw_content="",
                evidence_role="reported_candidate",
                snippet=(
                    "新闻 体育 娱乐 财经 汽车。"
                    "GPT-5.6 相比 GPT-5.5 在网络安全长周期任务上更强。"
                    "页面导航与推荐阅读。"
                ),
            ),
            self.result(
                "媒体比较二",
                "media-two.example",
                score=0.98,
                raw_content="",
                evidence_role="reported_candidate",
                snippet="GPT-5.6 的文档、表格和 PPT 任务精度有所提升。",
            ),
            self.result(
                "官方说明",
                "openai.com",
                score=0.70,
                raw_content="",
                evidence_role="official_confirmation",
                snippet="GPT-5.6 相比 GPT-5.5 在递归改进评估中提升 16.2 分。",
            ),
            *[
                self.result(
                    f"低优先级 {index}",
                    f"low-{index}.example",
                    score=0.60 - index / 100,
                    raw_content="",
                    evidence_role="context",
                    snippet=f"与比较问题关系较弱的背景资料 {index}。",
                )
                for index in range(5)
            ],
        ]
        evidence = self.synthesis.select_external_research_evidence(
            tuple(results),
            query="GPT-5.6 比 GPT-5.5 提升了哪些地方",
        )

        response = self.synthesis.format_external_research_response(
            provider_name="tavily",
            evidence=evidence,
            synthesis=self.synthesis.ExternalResearchSynthesis(
                status="call_failed",
                request_count=1,
                error_category="connection_failed",
            ),
            query="GPT-5.6 比 GPT-5.5 提升了哪些地方",
        )

        self.assertEqual(response.count("\n要点："), 3)
        self.assertIn("综合失败类别：connection_failed", response)
        self.assertIn("其余 5 条证据未展开", response)
        self.assertIn("https://openai.com/", response)
        self.assertIn("网络安全长周期任务上更强", response)
        self.assertNotIn("新闻 体育 娱乐 财经 汽车", response)
        self.assertNotIn("https://low-4.example/", response)

    def test_failed_synthesis_marks_english_fallback_without_second_translation(self):
        evidence = self.synthesis.select_external_research_evidence(
            (
                self.result(
                    "Official comparison",
                    "openai.com",
                    score=0.9,
                    raw_content="",
                    evidence_role="official_confirmation",
                    snippet=(
                        "GPT-5.6 improved coding and document tasks compared with GPT-5.5."
                    ),
                ),
            ),
            query="GPT-5.6 比 GPT-5.5 提升了哪些地方",
        )

        response = self.synthesis.format_external_research_response(
            provider_name="tavily",
            evidence=evidence,
            synthesis=self.synthesis.ExternalResearchSynthesis(
                status="call_failed",
                request_count=1,
                error_category="request_rejected",
            ),
            query="GPT-5.6 比 GPT-5.5 提升了哪些地方",
        )

        self.assertIn("部分来源摘要为英文", response)
        self.assertIn("本地不会追加模型翻译", response)


if __name__ == "__main__":
    unittest.main()
