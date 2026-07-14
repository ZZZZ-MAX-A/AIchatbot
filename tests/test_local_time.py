from __future__ import annotations

from datetime import datetime, timezone
import unittest

from pure_ai_chat_loader import AI_CHAT_ROOT, load_local_time_module


class LocalTimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.local_time = load_local_time_module()

    @staticmethod
    def fixed_shanghai_time() -> datetime:
        return datetime.fromisoformat("2026-07-12T10:30:45+08:00")

    def test_explicit_date_weekday_time_and_year_questions_are_deterministic(self):
        cases = {
            "今天星期几？": "今天是星期日。",
            "今天是周几呀": "今天是星期日。",
            "请问今日礼拜几": "今天是星期日。",
            "今天几月几日？": "今天是 2026 年 7 月 12 日。",
            "今天是几号": "今天是 2026 年 7 月 12 日。",
            "爱可记得今天几号吗": "今天是 2026 年 7 月 12 日。",
            "那爱可还记得今天几号嘛": "今天是 2026 年 7 月 12 日。",
            "（你抚摸爱可湿润的地方）爱可记得今天几号吗": (
                "今天是 2026 年 7 月 12 日。"
            ),
            "(轻轻抱住爱可) 你还记得今天几号吗": (
                "今天是 2026 年 7 月 12 日。"
            ),
            "今天几月几日，星期几": "今天是 2026 年 7 月 12 日，星期日。",
            "现在几点了": "现在是 10:30。",
            "请问当前是什么时间": "现在是 10:30。",
            "现在是哪一年": "今年是 2026 年。",
        }

        for question, expected in cases.items():
            with self.subTest(question=question):
                self.assertEqual(
                    self.local_time.resolve_local_time_reply(
                        question,
                        clock=self.fixed_shanghai_time,
                    ),
                    expected,
                )

    def test_clock_is_read_once_and_converted_to_shanghai_before_formatting(self):
        calls = 0

        def utc_clock() -> datetime:
            nonlocal calls
            calls += 1
            return datetime(2026, 7, 12, 18, 5, tzinfo=timezone.utc)

        reply = self.local_time.resolve_local_time_reply(
            "今天几月几日星期几",
            clock=utc_clock,
        )

        self.assertEqual(calls, 1)
        self.assertEqual(reply, "今天是 2026 年 7 月 13 日，星期一。")

    def test_non_time_chat_commands_and_broader_questions_are_not_intercepted(self):
        messages = (
            "你好",
            "明天星期几",
            "今天星期几适合出门吗",
            "如果我问你今天星期几会怎样",
            "爱可记得今天几号适合出门吗",
            "（你问爱可今天几号）继续刚才的话题",
            "（没有闭合爱可记得今天几号吗",
            "/agent 执行外部只读查询：今天星期几",
            "/状态",
            "2026 年 7 月 12 日是星期几",
        )
        for message in messages:
            with self.subTest(message=message):
                self.assertIsNone(
                    self.local_time.resolve_local_time_reply(
                        message,
                        clock=self.fixed_shanghai_time,
                    )
                )

    def test_timezone_and_clock_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "unsupported bot timezone"):
            self.local_time.resolve_local_time_reply(
                "今天星期几",
                timezone_name="UTC",
                clock=self.fixed_shanghai_time,
            )
        with self.assertRaisesRegex(ValueError, "aware datetime"):
            self.local_time.resolve_local_time_reply(
                "今天星期几",
                clock=lambda: datetime(2026, 7, 12, 10, 30),
            )

    def test_trusted_context_drives_chat_agent_and_valid_reply_keeps_persona(self):
        cases = (
            ("今天星期几", "今天是星期日呀，想稍微休息一下吗？", True),
            ("今天几月几日", "今天是 2026 年 7 月 12 日哦。", True),
            (
                "今天几月几日星期几",
                "今天是 7 月 12 日，星期天呀。",
                True,
            ),
            ("现在几点", "现在是上午 10 点 30 分。", True),
            ("现在是哪一年", "今年是 2026 年呢。", True),
            ("今天星期几", "今天是星期六。", False),
            ("今天几月几日", "今天是 7 月 11 日。", False),
            ("今天几月几日", "不是 7 月 11 日，是 7 月 12 日。", False),
            (
                "爱可记得今天几号吗",
                "现在是2025年5月24日，星期六。",
                False,
            ),
            ("今天几月几日星期几", "今天是 7 月 12 日，星期六。", False),
            ("现在几点", "现在是 10:31。", False),
            ("现在是哪一年", "今年是 2025 年。", False),
        )
        for question, candidate, expected in cases:
            with self.subTest(question=question, candidate=candidate):
                resolution = self.local_time.resolve_local_time_request(
                    question,
                    clock=self.fixed_shanghai_time,
                )
                self.assertIsNotNone(resolution)
                self.assertEqual(
                    self.local_time.validate_local_time_chat_reply(
                        resolution,
                        candidate,
                    ),
                    expected,
                )
                finalized = self.local_time.finalize_local_time_chat_reply(
                    resolution,
                    candidate,
                )
                self.assertEqual(
                    finalized,
                    candidate if expected else resolution.deterministic_reply,
                )

        resolution = self.local_time.resolve_local_time_request(
            "今天星期几",
            clock=self.fixed_shanghai_time,
        )
        self.assertIn("[可信本地时间事实]", resolution.trusted_context)
        self.assertIn("当前日期：2026-07-12", resolution.trusted_context)
        self.assertIn("当前星期：星期日", resolution.trusted_context)
        self.assertIn("保持当前角色卡", resolution.trusted_context)
        self.assertIn("忽略它们", resolution.trusted_context)
        self.assertIn("不要只输出裸事实", resolution.trusted_context)
        self.assertNotIn("今天星期几", resolution.trusted_context)

        original_history = [
            {"role": "system", "content": "existing context"},
            {"role": "assistant", "content": "earlier reply"},
        ]
        injected = self.local_time.history_with_trusted_local_time_context(
            original_history,
            resolution,
        )
        self.assertEqual(
            original_history,
            [
                {"role": "system", "content": "existing context"},
                {"role": "assistant", "content": "earlier reply"},
            ],
        )
        self.assertIsNot(injected, original_history)
        self.assertEqual(injected[:-1], original_history)
        self.assertEqual(injected[-1]["role"], "system")
        self.assertEqual(injected[-1]["content"], resolution.trusted_context)

    def test_empty_or_overlong_chat_reply_uses_deterministic_fallback(self):
        resolution = self.local_time.resolve_local_time_request(
            "今天星期几",
            clock=self.fixed_shanghai_time,
        )
        self.assertEqual(
            self.local_time.finalize_local_time_chat_reply(resolution, ""),
            "今天是星期日。",
        )
        self.assertEqual(
            self.local_time.finalize_local_time_chat_reply(
                resolution,
                "今天是星期日。" + ("好" * 600),
            ),
            "今天是星期日。",
        )

    def test_local_time_boundary_precedes_llm_and_has_no_network_or_rag_dependency(self):
        plugin_source = (AI_CHAT_ROOT / "__init__.py").read_text(encoding="utf-8")
        function_start = plugin_source.index("async def generate_chat_text_response(")
        local_time_call = plugin_source.index(
            "local_time_request = resolve_local_time_request(",
            function_start,
        )
        llm_call = plugin_source.index("reply = await ask_llm(", function_start)
        self.assertLess(local_time_call, llm_call)
        self.assertIn(
            "llm_history = history_with_trusted_local_time_context(",
            plugin_source[local_time_call:llm_call],
        )
        self.assertIn(
            "reply = finalize_local_time_chat_reply(local_time_request, reply)",
            plugin_source[llm_call:],
        )
        self.assertIn(
            "fallback = local_time_request.deterministic_reply",
            plugin_source[llm_call:],
        )
        self.assertIn(
            "llm_user_text(event, user_content.for_llm)",
            plugin_source[llm_call:],
        )

        source = (AI_CHAT_ROOT / "local_time.py").read_text(encoding="utf-8").lower()
        for forbidden in (
            "tavily",
            "httpx",
            "external_search",
            "retrieve_memory",
            "project_doc",
            "ask_llm",
            "mainagent",
            "nonebot",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
