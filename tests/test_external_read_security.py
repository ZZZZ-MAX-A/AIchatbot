from __future__ import annotations

import unittest
from datetime import date

from pure_ai_chat_loader import load_external_read_security_module


class ExternalReadSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.security = load_external_read_security_module()

    def assert_policy_error(self, category, callback) -> None:
        with self.assertRaises(self.security.ExternalReadPolicyError) as raised:
            callback()
        self.assertEqual(raised.exception.category, category)

    def test_query_normalizes_whitespace_and_control_characters(self):
        query = self.security.normalize_external_read_query(
            "  Python\nasyncio\t在 2026 年的公开资料  "
        )

        self.assertEqual(query, "Python asyncio 在 2026 年的公开资料")

    def test_query_rejects_empty_non_text_and_over_limit_values(self):
        invalid = self.security.ExternalReadPolicyCategory.INVALID_QUERY
        cases = (
            "",
            " \n\t ",
            "a" * (self.security.EXTERNAL_READ_MAX_QUERY_CHARS + 1),
            None,
        )
        for value in cases:
            with self.subTest(value_type=type(value).__name__):
                self.assert_policy_error(
                    invalid,
                    lambda value=value: self.security.normalize_external_read_query(value),
                )

    def test_query_rejects_urls_local_paths_and_secrets(self):
        cases = (
            ("查询 https://example.com/private", "invalid_query"),
            ("读取 file:///etc/passwd", "invalid_query"),
            (r"分析 D:\AIchatbot\.env", "sensitive_query"),
            (r"读取 \\server\share\secret.txt", "sensitive_query"),
            ("读取 /etc/passwd", "sensitive_query"),
            ("api_key=super-secret-value", "sensitive_query"),
            ("API key = super-secret-value", "sensitive_query"),
            ("token=super-secret-value", "sensitive_query"),
            ("Authorization: Bearer abcdefghijklmnop", "sensitive_query"),
            ("Cookie: session=abcdef", "sensitive_query"),
            ("检查 sk-abcdefghijklmnop", "sensitive_query"),
            (
                "检查 eyJabcdefghijk.abcdefghijklmnop.qrstuvwxyzABCDE",
                "sensitive_query",
            ),
        )
        for query, category in cases:
            with self.subTest(query=query):
                self.assert_policy_error(
                    self.security.ExternalReadPolicyCategory(category),
                    lambda query=query: self.security.normalize_external_read_query(query),
                )

    def test_query_rejects_high_confidence_personal_data_but_not_plain_identifiers(self):
        sensitive = self.security.ExternalReadPolicyCategory.SENSITIVE_QUERY
        rejected = (
            "查询邮箱 owner@example.com 的公开记录",
            "查询手机号：13800138000",
            "查询电话 +86 13900139000",
            "查询 QQ号：123456789",
            "查询身份证号：11010519491231002X",
        )
        for query in rejected:
            with self.subTest(query=query):
                self.assert_policy_error(
                    sensitive,
                    lambda query=query: self.security.normalize_external_read_query(query),
                )

        accepted = (
            "RFC 9110 的缓存语义",
            "CVE-2026-12345 修复状态",
            "产品型号 123456789",
        )
        for query in accepted:
            with self.subTest(query=query):
                self.assertEqual(
                    self.security.normalize_external_read_query(query),
                    query,
                )

    def test_endpoint_accepts_only_exact_allowlisted_https_host(self):
        endpoint = self.security.validate_external_read_endpoint(
            "https://search.example.com/v1/search",
            allowed_hosts=("SEARCH.EXAMPLE.COM.",),
        )

        self.assertEqual(endpoint.source_host, "search.example.com")
        self.assertEqual(endpoint.base_url, "https://search.example.com/v1/search")

    def test_endpoint_rejects_unsafe_shapes(self):
        unsafe = self.security.ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT
        cases = (
            "http://search.example.com/v1/search",
            "https://user:pass@search.example.com/v1/search",
            "https://search.example.com:8443/v1/search",
            "https://search.example.com/v1/search?token=secret",
            "https://search.example.com/v1/search#fragment",
            "https://evil.example.com/v1/search",
            "https://search.example.com.evil.test/v1/search",
            "https://search.example.com\\@evil.test/v1/search",
            "https://search.example.com/v1/\nsearch",
            "not a URL",
            "",
        )
        for endpoint in cases:
            with self.subTest(endpoint=endpoint):
                self.assert_policy_error(
                    unsafe,
                    lambda endpoint=endpoint: self.security.validate_external_read_endpoint(
                        endpoint,
                        allowed_hosts=("search.example.com",),
                    ),
                )

    def test_endpoint_rejects_allowlisted_non_public_ip_literal(self):
        self.assert_policy_error(
            self.security.ExternalReadPolicyCategory.UNSAFE_RESOLVED_ADDRESS,
            lambda: self.security.validate_external_read_endpoint(
                "https://127.0.0.1/search",
                allowed_hosts=("127.0.0.1",),
            ),
        )

    def test_resolved_addresses_accept_only_public_ipv4_and_ipv6(self):
        addresses = self.security.validate_external_read_addresses(
            ("8.8.8.8", "2606:4700:4700::1111", "8.8.8.8")
        )

        self.assertEqual(addresses, ("8.8.8.8", "2606:4700:4700::1111"))

    def test_resolved_addresses_reject_private_reserved_and_metadata_ranges(self):
        unsafe = self.security.ExternalReadPolicyCategory.UNSAFE_RESOLVED_ADDRESS
        addresses = (
            "127.0.0.1",
            "0.0.0.0",
            "10.0.0.1",
            "172.16.0.1",
            "192.168.1.1",
            "169.254.169.254",
            "100.64.0.1",
            "224.0.0.1",
            "255.255.255.255",
            "::1",
            "::",
            "fe80::1",
            "fc00::1",
            "ff02::1",
        )
        for address in addresses:
            with self.subTest(address=address):
                self.assert_policy_error(
                    unsafe,
                    lambda address=address: self.security.validate_external_read_addresses(
                        (address,)
                    ),
                )

    def test_resolved_addresses_reject_empty_and_invalid_results(self):
        unsafe = self.security.ExternalReadPolicyCategory.UNSAFE_RESOLVED_ADDRESS
        for addresses in ((), ("not-an-ip",)):
            with self.subTest(addresses=addresses):
                self.assert_policy_error(
                    unsafe,
                    lambda addresses=addresses: self.security.validate_external_read_addresses(
                        addresses
                    ),
                )

    def test_default_budget_matches_first_external_read_contract(self):
        budget = self.security.ExternalReadBudget()

        self.assertEqual(budget.max_results, 10)
        self.assertEqual(budget.max_response_bytes, 262_144)
        self.assertEqual(budget.timeout_seconds, 10)
        self.assertEqual(budget.external_request_count, 1)
        self.assertEqual(budget.redirect_count, 0)
        self.assertEqual(budget.retry_count, 0)

    def test_budget_rejects_expansion_and_non_integer_values(self):
        invalid = self.security.ExternalReadPolicyCategory.INVALID_BUDGET
        cases = (
            {"max_results": 0},
            {"max_results": 11},
            {"max_results": True},
            {"max_response_bytes": 0},
            {"max_response_bytes": 262_145},
            {"timeout_seconds": 0},
            {"timeout_seconds": 16},
            {"external_request_count": 2},
            {"redirect_count": 1},
            {"retry_count": 1},
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                self.assert_policy_error(
                    invalid,
                    lambda arguments=arguments: self.security.ExternalReadBudget(**arguments),
                )

    def test_temporal_query_rewrites_previous_month_to_trusted_absolute_range(self):
        temporal = self.security.rewrite_external_read_temporal_query(
            "查找当前日期往前一个月的重要模型发布",
            reference_date=date(2026, 7, 28),
        )

        self.assertEqual(temporal.time_window.start_iso, "2026-06-28")
        self.assertEqual(temporal.time_window.end_iso, "2026-07-28")
        self.assertIn("2026-06-28 至 2026-07-28", temporal.query)
        self.assertIn("可信日期范围", temporal.query)
        self.assertNotIn("官方网站、官方博客和官方公告", temporal.query)
        self.assertNotIn("当前日期往前一个月", temporal.query)
        self.assertEqual(
            temporal.search_question,
            "查找2026-06-28 至 2026-07-28的重要模型发布",
        )

    def test_temporal_query_clamps_previous_month_at_month_end(self):
        temporal = self.security.rewrite_external_read_temporal_query(
            "最近一个月的公开公告",
            reference_date=date(2026, 3, 31),
        )

        self.assertEqual(temporal.time_window.start_iso, "2026-02-28")
        self.assertEqual(temporal.time_window.end_iso, "2026-03-31")

    def test_temporal_query_resolves_current_periods_and_today(self):
        cases = (
            ("本月公告", "2026-07-01", "2026-07-28"),
            ("本周公告", "2026-07-27", "2026-07-28"),
            ("今天公告", "2026-07-28", "2026-07-28"),
        )
        for query, start_date, end_date in cases:
            with self.subTest(query=query):
                temporal = self.security.rewrite_external_read_temporal_query(
                    query,
                    reference_date=date(2026, 7, 28),
                )
                self.assertEqual(temporal.time_window.start_iso, start_date)
                self.assertEqual(temporal.time_window.end_iso, end_date)

    def test_temporal_query_accepts_an_explicit_absolute_date_range(self):
        temporal = self.security.rewrite_external_read_temporal_query(
            "查询 2026-06-28 至 2026-07-28 的模型发布",
            reference_date=date(2026, 7, 28),
        )

        self.assertEqual(temporal.time_window.start_iso, "2026-06-28")
        self.assertEqual(temporal.time_window.end_iso, "2026-07-28")
        self.assertEqual(temporal.time_window.kind, "absolute_range")
        self.assertIn("可信日期范围：2026-06-28 至 2026-07-28", temporal.query)

    def test_main_agent_search_plan_limits_queries_and_controls_source_policy(self):
        plan = self.security.ExternalReadSearchPlan(
            primary_query="萍乡 热门 小吃 推荐",
            primary_source_scope="general",
            primary_evidence_role="recommendation",
        )

        self.assertEqual(plan.primary_query, "萍乡 热门 小吃 推荐")
        self.assertEqual(plan.primary_evidence_role, "recommendation")
        self.assertEqual(plan.secondary_mode, "none")
        self.assertEqual(plan.scene, "general_lookup")

        news_plan = self.security.ExternalReadSearchPlan(
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
        self.assertEqual(news_plan.primary_time_range, "week")
        self.assertEqual(news_plan.secondary_time_range, "month")
        self.assertEqual(news_plan.secondary_evidence_role, "reported_candidate")

        with self.assertRaises(self.security.ExternalReadPolicyError):
            self.security.ExternalReadSearchPlan(
                primary_query="查" * 51,
                primary_source_scope="general",
            )
        with self.assertRaises(self.security.ExternalReadPolicyError):
            self.security.ExternalReadSearchPlan(
                primary_query="萍乡小吃",
                primary_source_scope="official",
                secondary_query="萍乡美食",
                secondary_source_scope="general",
                secondary_mode="none",
            )
        for invalid_plan in (
            {"primary_time_range": "quarter"},
            {"primary_evidence_role": "authority"},
            {"scene": "shopping"},
            {
                "secondary_query": "第二条",
                "secondary_source_scope": "news",
                "secondary_time_range": "quarter",
                "secondary_mode": "always",
            },
        ):
            with self.subTest(invalid_plan=invalid_plan):
                with self.assertRaises(self.security.ExternalReadPolicyError):
                    self.security.ExternalReadSearchPlan(
                        primary_query="第一条",
                        primary_source_scope="news",
                        **invalid_plan,
                    )

    def test_scene_inference_covers_first_business_scenes(self):
        cases = {
            "原神下一个版本角色是谁": "current_status",
            "Claude 最近有什么更新": "official_update",
            "FastAPI 官方文档中的 lifespan 怎么使用": "technical_docs",
            "最近一周 AI 行业有什么新闻": "news_summary",
            "萍乡有什么美食推荐": "recommendation",
            "Claude 和 Gemini 有什么区别": "comparison",
            "解释量子计算": "general_lookup",
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertEqual(
                    self.security.infer_external_read_scene(query),
                    expected,
                )

    def test_current_status_scene_builds_two_stage_lifecycle_plan(self):
        plan = self.security.adapt_external_read_scene_plan(
            self.security.ExternalReadSearchPlan(
                primary_query="原神 下一个版本 角色",
                primary_source_scope="official",
            ),
            source_query="原神下一个版本的角色是谁",
        )

        self.assertEqual(plan.scene, "current_status")
        self.assertEqual(plan.primary_query, "原神 当前已上线版本 角色")
        self.assertEqual(plan.primary_source_scope, "general")
        self.assertEqual(plan.primary_evidence_role, "context")
        self.assertEqual(plan.secondary_query, "原神 下一个版本 角色")
        self.assertEqual(plan.secondary_source_scope, "news")
        self.assertEqual(plan.secondary_time_range, "month")
        self.assertEqual(plan.secondary_evidence_role, "reported_candidate")
        self.assertEqual(plan.secondary_mode, "always")

    def test_current_status_scene_preserves_explicit_official_only_scope(self):
        plan = self.security.adapt_external_read_scene_plan(
            self.security.ExternalReadSearchPlan(
                primary_query="原神 下一个版本 角色",
                primary_source_scope="general",
            ),
            source_query="只看官方：原神下一个版本的角色是谁",
        )

        self.assertEqual(plan.scene, "current_status")
        self.assertEqual(plan.primary_source_scope, "official")
        self.assertEqual(plan.primary_evidence_role, "context")
        self.assertEqual(plan.secondary_source_scope, "official")
        self.assertEqual(plan.secondary_evidence_role, "official_confirmation")
        self.assertEqual(plan.secondary_mode, "always")

    def test_current_status_scene_standardizes_existing_two_query_plan(self):
        plan = self.security.adapt_external_read_scene_plan(
            self.security.ExternalReadSearchPlan(
                primary_query="原神最新版本角色预告",
                primary_source_scope="official",
                primary_time_range="month",
                primary_evidence_role="official_confirmation",
                secondary_query="原神下一个版本角色",
                secondary_source_scope="news",
                secondary_time_range="month",
                secondary_evidence_role="official_confirmation",
                secondary_mode="if_no_results",
            ),
            source_query="原神下一个版本的角色是谁",
        )

        self.assertEqual(plan.primary_query, "原神当前已上线版本角色")
        self.assertEqual(plan.primary_source_scope, "general")
        self.assertEqual(plan.primary_time_range, "")
        self.assertEqual(plan.primary_evidence_role, "context")
        self.assertEqual(plan.secondary_query, "原神下一个版本角色")
        self.assertEqual(plan.secondary_source_scope, "news")
        self.assertEqual(plan.secondary_time_range, "month")
        self.assertEqual(plan.secondary_evidence_role, "reported_candidate")
        self.assertEqual(plan.secondary_mode, "always")

    def test_temporal_query_rejects_invalid_or_reversed_absolute_date_ranges(self):
        invalid = self.security.ExternalReadPolicyCategory.INVALID_QUERY
        for query in (
            "查询 2026-06-31 至 2026-07-28 的模型发布",
            "查询 2026-07-29 至 2026-07-28 的模型发布",
        ):
            with self.subTest(query=query):
                self.assert_policy_error(
                    invalid,
                    lambda query=query: self.security.rewrite_external_read_temporal_query(
                        query,
                        reference_date=date(2026, 7, 28),
                    ),
                )

    def test_vague_recency_defaults_to_rolling_month_without_clarification(self):
        for query in (
            "最近有什么模型发布",
            "近期有哪些多模态模型发布",
            "recently released models",
        ):
            with self.subTest(query=query):
                self.assertFalse(
                    self.security.external_read_time_window_requires_clarification(
                        query,
                        reference_date=date(2026, 7, 28),
                    )
                )
                temporal = self.security.rewrite_external_read_temporal_query(
                    query,
                    reference_date=date(2026, 7, 28),
                )
                self.assertEqual(temporal.time_window.start_iso, "2026-06-28")
                self.assertEqual(temporal.time_window.end_iso, "2026-07-28")
                self.assertEqual(temporal.time_window.kind, "auto_recent_month")

        for query in (
            "最近一周有什么模型发布",
            "最近一个月有什么模型发布",
            "查询 2026-06-28 至 2026-07-28 的模型发布",
        ):
            with self.subTest(query=query):
                self.assertFalse(
                    self.security.external_read_time_window_requires_clarification(
                        query,
                        reference_date=date(2026, 7, 28),
                    )
                )

    def test_recent_plan_reserves_one_broader_fallback_query(self):
        weekly = self.security.rewrite_external_read_temporal_query(
            "最近一周 Claude 有什么更新",
            reference_date=date(2026, 7, 31),
        )
        plan = self.security.adapt_recent_external_read_search_plan(
            self.security.ExternalReadSearchPlan(
                primary_query="Claude 最近一周更新",
                primary_source_scope="official",
                primary_evidence_role="official_confirmation",
            ),
            source_query="最近一周 Claude 有什么更新",
            time_window=weekly.time_window,
        )

        self.assertEqual(plan.primary_time_range, "week")
        self.assertEqual(plan.secondary_mode, "if_no_results")
        self.assertEqual(plan.secondary_time_range, "six_months")
        self.assertEqual(plan.secondary_query, "Claude 更新")
        self.assertEqual(plan.secondary_source_scope, "general")
        self.assertEqual(plan.secondary_evidence_role, "reported_candidate")
        secondary_window = self.security.resolve_external_read_secondary_time_window(
            primary_time_window=weekly.time_window,
            search_plan=plan,
            reference_date=date(2026, 7, 31),
        )
        self.assertEqual(secondary_window.start_iso, "2026-01-31")
        self.assertEqual(secondary_window.end_iso, "2026-07-31")
        self.assertEqual(secondary_window.kind, "nearest_available_fallback")

    def test_vague_recent_plan_defaults_month_then_six_months(self):
        recent = self.security.rewrite_external_read_temporal_query(
            "Claude 最近有什么更新",
            reference_date=date(2026, 7, 31),
        )
        plan = self.security.adapt_recent_external_read_search_plan(
            self.security.ExternalReadSearchPlan(
                primary_query="Claude 模型更新",
                primary_source_scope="official",
            ),
            source_query="Claude 最近有什么更新",
            time_window=recent.time_window,
        )

        self.assertEqual(plan.primary_time_range, "month")
        self.assertEqual(plan.secondary_time_range, "six_months")
        self.assertEqual(plan.secondary_source_scope, "general")
        self.assertEqual(plan.secondary_evidence_role, "reported_candidate")
        self.assertEqual(plan.secondary_mode, "if_no_results")

    def test_recent_official_only_request_keeps_official_fallback_scope(self):
        recent = self.security.rewrite_external_read_temporal_query(
            "最近一周只看官方更新",
            reference_date=date(2026, 7, 31),
        )
        plan = self.security.adapt_recent_external_read_search_plan(
            self.security.ExternalReadSearchPlan(
                primary_query="Claude 官方更新",
                primary_source_scope="official",
                primary_evidence_role="official_confirmation",
            ),
            source_query="最近一周只看官方更新",
            time_window=recent.time_window,
        )

        self.assertEqual(plan.secondary_time_range, "six_months")
        self.assertEqual(plan.secondary_source_scope, "official")
        self.assertEqual(plan.secondary_evidence_role, "official_confirmation")

    def test_six_month_window_clips_to_calendar_month_end(self):
        window = self.security.external_read_time_window_for_range(
            "six_months",
            reference_date=date(2025, 8, 31),
        )

        self.assertEqual(window.start_iso, "2025-02-28")
        self.assertEqual(window.end_iso, "2025-08-31")

    def test_explicit_six_month_query_uses_six_months_without_widening(self):
        for query in (
            "帮我查看最近半年 Claude 的更新",
            "过去六个月有哪些模型发布",
            "updates from the past six months",
        ):
            with self.subTest(query=query):
                temporal = self.security.rewrite_external_read_temporal_query(
                    query,
                    reference_date=date(2026, 7, 31),
                )
                plan = self.security.adapt_recent_external_read_search_plan(
                    self.security.ExternalReadSearchPlan(
                        primary_query="Claude 模型更新",
                        primary_source_scope="general",
                    ),
                    source_query=query,
                    time_window=temporal.time_window,
                )

                self.assertEqual(temporal.time_window.start_iso, "2026-01-31")
                self.assertEqual(temporal.time_window.end_iso, "2026-07-31")
                self.assertEqual(plan.primary_time_range, "six_months")
                self.assertEqual(plan.secondary_mode, "none")

    def test_temporal_query_keeps_non_temporal_query_unchanged(self):
        temporal = self.security.rewrite_external_read_temporal_query(
            "解释 Python 生成器原理",
            reference_date=date(2026, 7, 28),
        )

        self.assertEqual(temporal.query, "解释 Python 生成器原理")
        self.assertEqual(temporal.search_question, "解释 Python 生成器原理")
        self.assertIsNone(temporal.time_window)

    def test_temporal_query_still_rejects_sensitive_input_and_rewrite_overflow(self):
        for query in (
            "最近一个月查看 https://example.com",
            r"最近一个月读取 D:\AIchatbot\.env",
            "最近一个月 api_key=super-secret-value",
        ):
            with self.subTest(query=query):
                with self.assertRaises(self.security.ExternalReadPolicyError):
                    self.security.rewrite_external_read_temporal_query(
                        query,
                        reference_date=date(2026, 7, 28),
                    )
        with self.assertRaises(self.security.ExternalReadPolicyError) as raised:
            self.security.rewrite_external_read_temporal_query(
                "最近一个月" + "模型" * 125,
                reference_date=date(2026, 7, 28),
            )
        self.assertEqual(
            raised.exception.category,
            self.security.ExternalReadPolicyCategory.INVALID_QUERY,
        )


if __name__ == "__main__":
    unittest.main()
