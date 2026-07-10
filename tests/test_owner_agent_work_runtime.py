from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pure_ai_chat_loader import AI_CHAT_ROOT, load_legacy_memory_modules, load_module


class TempDatabaseMixin:
    def temp_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "chatbot.db"
        patcher = patch.object(self.database, "DATABASE_PATH", db_path)
        return temp_dir, patcher


class OwnerAgentWorkRuntimeTests(TempDatabaseMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.memory_modules = load_legacy_memory_modules()
        cls.database = cls.memory_modules["database"]
        cls.agent_tasks = cls.memory_modules["agent_tasks"]
        cls.work_runtime = load_module(
            "src.plugins.ai_chat.owner_agent_work_runtime",
            AI_CHAT_ROOT / "owner_agent_work_runtime.py",
        )

    def make_runtime(self, executor):
        return self.work_runtime.OwnerAgentWorkRuntime(
            context=self.work_runtime.OwnerAgentWorkContext(
                session_key="private:10001",
                user_id="10001",
            ),
            development_context_report_executor=executor,
        )

    def test_registry_only_exposes_development_context_report(self):
        runtime = self.make_runtime(lambda _query: "project docs: 0\nmemories: 0")

        self.assertEqual(
            runtime.registered_work_types,
            (self.work_runtime.DEVELOPMENT_CONTEXT_REPORT_WORK_TYPE,),
        )
        spec = runtime.work_spec(
            self.work_runtime.DEVELOPMENT_CONTEXT_REPORT_WORK_TYPE
        )
        self.assertEqual(spec.display_name, "研发上下文报告")
        self.assertEqual(spec.risk_level, "read_local")
        self.assertFalse(spec.requires_approval)
        with self.assertRaisesRegex(ValueError, "unsupported owner agent work type"):
            runtime.work_spec("shell")

    def test_explicit_command_parser_is_strict_and_never_matches_todo_commands(self):
        parse = self.work_runtime.parse_development_context_report_command

        self.assertEqual(
            parse("执行研发上下文任务：恢复 Owner Console 当前开发状态"),
            "恢复 Owner Console 当前开发状态",
        )
        self.assertEqual(
            parse("执行研发上下文任务: 总结审批恢复边界"),
            "总结审批恢复边界",
        )
        self.assertEqual(parse("执行研发上下文任务"), "")
        self.assertIsNone(parse("任务 恢复 Owner Console 当前开发状态"))
        self.assertIsNone(parse("查 执行研发上下文任务：恢复当前状态"))

    def test_successful_work_persists_only_safe_context_report_summary(self):
        temp_dir, patcher = self.temp_database()
        calls: list[str] = []

        async def executor(query: str) -> str:
            calls.append(query)
            return "\n".join(
                [
                    "project docs: 2",
                    "memories: 1",
                    "raw RAG chunk must not be persisted",
                    "D:\\private\\database\\path must not be persisted",
                ]
            )

        with temp_dir, patcher:
            execution = asyncio.run(
                self.make_runtime(executor).execute(
                    work_type=self.work_runtime.DEVELOPMENT_CONTEXT_REPORT_WORK_TYPE,
                    query="恢复 Owner Console 当前开发状态",
                )
            )
            assert execution.task is not None
            events = self.agent_tasks.list_agent_task_events(execution.task.id)
            reply = self.work_runtime.format_owner_agent_work_execution(execution)

        self.assertEqual(calls, ["恢复 Owner Console 当前开发状态"])
        self.assertEqual(execution.outcome, "completed")
        self.assertEqual(execution.task.status, self.agent_tasks.AGENT_TASK_DONE)
        self.assertIn("项目文档命中：2", execution.task.result)
        self.assertIn("开发侧记忆命中：1", execution.task.result)
        self.assertNotIn("raw RAG chunk", execution.task.result)
        self.assertNotIn("D:\\private", execution.task.result)
        self.assertEqual(
            [event.kind for event in events],
            ["created", "work_claimed", "work_started", "work_finished"],
        )
        self.assertNotIn("raw RAG chunk", events[-1].output_summary)
        self.assertNotIn("D:\\private", events[-1].output_summary)
        self.assertIn(f"研发上下文任务 #{execution.task.id} 已完成", reply)
        self.assertIn(f"/agent 任务详情 {execution.task.id}", reply)
        self.assertNotIn("raw RAG chunk", reply)
        self.assertNotIn("D:\\private", reply)

    def test_structured_report_is_ephemeral_while_task_keeps_only_safe_metadata(self):
        temp_dir, patcher = self.temp_database()

        def executor(_query: str):
            return self.work_runtime.DevelopmentContextReportPayload(
                project_result_count=4,
                memory_result_count=0,
                report_text="\n".join(
                    [
                        "当前阶段：",
                        "P2.43 已完成。",
                        "推荐下一步：",
                        "- 设计 P2.44。",
                        "PRIVATE_TOKEN=must-not-leak",
                        "owner@example.com 13800138000",
                        "docs/private-plan.md",
                    ]
                ),
                summary_mode="bounded_llm",
                current_status_anchor_included=True,
                retrieval_warning_count=1,
            )

        with temp_dir, patcher:
            execution = asyncio.run(
                self.make_runtime(executor).execute(
                    work_type=self.work_runtime.DEVELOPMENT_CONTEXT_REPORT_WORK_TYPE,
                    query="恢复当前开发状态和下一步",
                )
            )
            assert execution.task is not None
            events = self.agent_tasks.list_agent_task_events(execution.task.id)
            reply = self.work_runtime.format_owner_agent_work_execution(execution)

        self.assertEqual(execution.outcome, "completed")
        self.assertIn("项目文档命中：4", execution.task.result)
        self.assertIn("当前状态锚点：已加载", execution.task.result)
        self.assertIn("检索警告：1", execution.task.result)
        self.assertIn("受限主模型结构化总结", execution.task.result)
        self.assertIn("P2.43 已完成", reply)
        self.assertIn("设计 P2.44", reply)
        self.assertNotIn("P2.43 已完成", execution.task.result)
        self.assertNotIn("设计 P2.44", execution.task.result)
        self.assertNotIn("current_status_anchor", execution.task.result)
        self.assertNotIn("must-not-leak", reply)
        self.assertNotIn("owner@example.com", reply)
        self.assertNotIn("13800138000", reply)
        self.assertNotIn("docs/private-plan.md", reply)
        self.assertNotIn("must-not-leak", events[-1].output_summary)
        self.assertNotIn("P2.43 已完成", events[-1].output_summary)

    def test_invalid_or_unregistered_work_never_creates_a_task(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            runtime = self.make_runtime(lambda _query: "project docs: 0\nmemories: 0")
            with self.assertRaisesRegex(ValueError, "work query must be non-empty"):
                asyncio.run(
                    runtime.execute(
                        work_type=self.work_runtime.DEVELOPMENT_CONTEXT_REPORT_WORK_TYPE,
                        query=" \x00 ",
                    )
                )
            with self.assertRaisesRegex(ValueError, "unsupported owner agent work type"):
                asyncio.run(runtime.execute(work_type="shell", query="whoami"))
            task_count = self.agent_tasks.count_agent_tasks(
                session_key="private:10001",
                user_id="10001",
            )

        self.assertEqual(task_count, 0)

    def test_executor_failure_uses_safe_error_category_without_raw_exception_text(self):
        temp_dir, patcher = self.temp_database()

        def executor(_query: str) -> str:
            raise RuntimeError("PRIVATE_TOKEN=not-for-task-result")

        with temp_dir, patcher:
            execution = asyncio.run(
                self.make_runtime(executor).execute(
                    work_type=self.work_runtime.DEVELOPMENT_CONTEXT_REPORT_WORK_TYPE,
                    query="验证失败边界",
                )
            )
            assert execution.task is not None
            events = self.agent_tasks.list_agent_task_events(execution.task.id)

        self.assertEqual(execution.outcome, "failed")
        self.assertEqual(execution.task.status, self.agent_tasks.AGENT_TASK_FAILED)
        self.assertEqual(
            execution.task.result,
            "RuntimeError: development_context_report execution failed.",
        )
        self.assertNotIn("PRIVATE_TOKEN", execution.task.result)
        self.assertEqual(events[-1].kind, "work_failed")
        self.assertNotIn("PRIVATE_TOKEN", events[-1].error)
