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
        cls.system_report = load_module(
            "src.plugins.ai_chat.system_diagnostics_report",
            AI_CHAT_ROOT / "system_diagnostics_report.py",
        )

    def system_payload(self, *, report_text: str | None = None):
        payload = self.system_report.build_system_diagnostics_overview(
            self.system_report.SystemDiagnosticsOverviewEvidence(
                core=self.system_report.CoreZoneEvidence(database_ok=True),
                chat=self.system_report.ChatZoneEvidence(
                    enabled=True,
                    model_configured=True,
                    recent_observation_present=False,
                    recent_error=False,
                ),
                main_agent=self.system_report.MainAgentZoneEvidence(
                    enabled=True,
                    owner_only=True,
                    group_allowed=False,
                    development_report_registered=True,
                    system_report_registered=True,
                    owner_write_registered=True,
                    owner_write_requires_approval=True,
                    owner_write_resume_enabled=True,
                ),
                memory_rag=self.system_report.MemoryRagZoneEvidence(
                    memory_rag_enabled=False,
                    memory_rag_inject_in_chat=False,
                    project_doc_rag_enabled=True,
                    storage_ok=None,
                ),
                vision=self.system_report.VisionZoneEvidence(
                    enabled=False,
                    service_ok=None,
                    model_exists=None,
                    recent_usage_present=False,
                ),
                voice=self.system_report.VoiceZoneEvidence(
                    enabled=False,
                    service_ok=None,
                    model_loaded=None,
                ),
                local_probe_count=1,
            )
        )
        if report_text is None:
            return payload
        return self.system_report.SystemDiagnosticsReportPayload(
            scope=payload.scope,
            overall_status=payload.overall_status,
            zones=payload.zones,
            primary_recommended_scope=payload.primary_recommended_scope,
            local_probe_count=payload.local_probe_count,
            external_request_count=payload.external_request_count,
            deep_probe_count=payload.deep_probe_count,
            repair_action_count=payload.repair_action_count,
            high_risk_boundary_ok=payload.high_risk_boundary_ok,
            report_text=report_text,
        )

    def vision_payload(self, *, report_text: str | None = None):
        payload = self.system_report.build_vision_diagnostics_report(
            self.system_report.VisionZoneEvidence(
                enabled=True,
                service_ok=True,
                model_exists=True,
                recent_usage_present=True,
                recent_error_count=1,
            ),
            local_probe_count=1,
        )
        if report_text is None:
            return payload
        return self.system_report.VisionDiagnosticsReportPayload(
            scope=payload.scope,
            zone_status=payload.zone_status,
            fault_layer=payload.fault_layer,
            recommended_scope=payload.recommended_scope,
            local_probe_count=payload.local_probe_count,
            external_request_count=payload.external_request_count,
            deep_probe_count=payload.deep_probe_count,
            repair_action_count=payload.repair_action_count,
            report_text=report_text,
        )

    def voice_payload(self, *, report_text: str | None = None):
        payload = self.system_report.build_voice_diagnostics_report(
            self.system_report.VoiceZoneEvidence(
                enabled=True,
                service_ok=True,
                model_loaded=True,
                service_is_loopback=True,
                service_reachable=True,
                language="zh",
                recent_candidate_present=True,
                recent_generation_observation_present=False,
                recent_send_observation_present=False,
            ),
            local_probe_count=1,
        )
        if report_text is None:
            return payload
        return self.system_report.VoiceDiagnosticsReportPayload(
            scope=payload.scope,
            zone_status=payload.zone_status,
            fault_layer=payload.fault_layer,
            recommended_scope=payload.recommended_scope,
            local_probe_count=payload.local_probe_count,
            external_request_count=payload.external_request_count,
            deep_probe_count=payload.deep_probe_count,
            repair_action_count=payload.repair_action_count,
            report_text=report_text,
        )

    def memory_rag_payload(self, *, report_text: str | None = None):
        payload = self.system_report.build_memory_rag_diagnostics_report(
            self.system_report.MemoryRagZoneEvidence(
                memory_rag_enabled=True,
                memory_rag_inject_in_chat=True,
                project_doc_rag_enabled=True,
                storage_ok=True,
                document_count=10,
                embedding_count=8,
                pending_count=2,
                recent_observation_present=True,
                recent_attempted=True,
                recent_result_count=1,
            ),
            local_probe_count=1,
        )
        if report_text is None:
            return payload
        return self.system_report.MemoryRagDiagnosticsReportPayload(
            scope=payload.scope,
            zone_status=payload.zone_status,
            fault_layer=payload.fault_layer,
            recommended_scope=payload.recommended_scope,
            local_probe_count=payload.local_probe_count,
            external_request_count=payload.external_request_count,
            deep_probe_count=payload.deep_probe_count,
            repair_action_count=payload.repair_action_count,
            report_text=report_text,
        )

    def make_runtime(self, executor, system_executor=None):
        if system_executor is None:
            system_executor = lambda _scope: self.system_payload()
        return self.work_runtime.OwnerAgentWorkRuntime(
            context=self.work_runtime.OwnerAgentWorkContext(
                session_key="private:10001",
                user_id="10001",
            ),
            development_context_report_executor=executor,
            system_diagnostics_report_executor=system_executor,
        )

    def test_registry_exposes_two_read_only_formal_work_types(self):
        runtime = self.make_runtime(lambda _query: "project docs: 0\nmemories: 0")

        self.assertEqual(
            runtime.registered_work_types,
            (
                self.work_runtime.DEVELOPMENT_CONTEXT_REPORT_WORK_TYPE,
                self.work_runtime.SYSTEM_DIAGNOSTICS_REPORT_WORK_TYPE,
            ),
        )
        development_spec = runtime.work_spec(
            self.work_runtime.DEVELOPMENT_CONTEXT_REPORT_WORK_TYPE
        )
        diagnostics_spec = runtime.work_spec(
            self.work_runtime.SYSTEM_DIAGNOSTICS_REPORT_WORK_TYPE
        )
        self.assertEqual(development_spec.display_name, "研发上下文报告")
        self.assertEqual(diagnostics_spec.display_name, "系统诊断报告")
        self.assertEqual(development_spec.risk_level, "read_local")
        self.assertEqual(diagnostics_spec.risk_level, "read_local")
        self.assertFalse(development_spec.requires_approval)
        self.assertFalse(diagnostics_spec.requires_approval)
        self.assertEqual(diagnostics_spec.required_arguments, ("scope",))
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

    def test_system_diagnostics_command_parser_is_strict_and_normalizes_scopes(self):
        parse = self.work_runtime.parse_system_diagnostics_report_command

        self.assertEqual(parse("执行系统诊断任务"), "overview")
        self.assertEqual(parse("执行系统诊断任务：概览"), "overview")
        self.assertEqual(parse("执行系统诊断任务: overview"), "overview")
        self.assertEqual(parse("执行系统诊断任务：视觉"), "vision")
        self.assertEqual(parse("执行系统诊断任务：语音"), "voice")
        self.assertEqual(parse("执行系统诊断任务：记忆与RAG"), "memory_rag")
        self.assertEqual(
            parse("执行系统诊断任务：任意外部网址"),
            self.work_runtime.SYSTEM_DIAGNOSTICS_UNSUPPORTED_SCOPE,
        )
        self.assertEqual(
            parse("执行系统诊断任务："),
            self.work_runtime.SYSTEM_DIAGNOSTICS_UNSUPPORTED_SCOPE,
        )
        self.assertIsNone(parse("查 执行系统诊断任务"))
        self.assertIsNone(parse("执行一次系统诊断任务"))

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

    def test_system_overview_is_ephemeral_while_task_keeps_only_safe_counts(self):
        temp_dir, patcher = self.temp_database()
        calls: list[str] = []

        def executor(scope: str):
            calls.append(scope)
            return self.system_payload(
                report_text="\n".join(
                    [
                        "系统诊断：正常",
                        "正常：核心运行、聊天、MainAgent。",
                        "PRIVATE_TOKEN=must-not-leak",
                        "D:\\private\\diagnostic.log",
                    ]
                )
            )

        with temp_dir, patcher:
            execution = asyncio.run(
                self.make_runtime(
                    lambda _query: "project docs: 0\nmemories: 0",
                    executor,
                ).execute(
                    work_type=self.work_runtime.SYSTEM_DIAGNOSTICS_REPORT_WORK_TYPE,
                    query="overview",
                )
            )
            assert execution.task is not None
            events = self.agent_tasks.list_agent_task_events(execution.task.id)
            reply = self.work_runtime.format_owner_agent_work_execution(execution)

        self.assertEqual(calls, ["overview"])
        self.assertEqual(execution.outcome, "completed")
        self.assertEqual(execution.task.status, self.agent_tasks.AGENT_TASK_DONE)
        self.assertIn("系统诊断概览已完成", execution.task.result)
        self.assertIn("总体状态：正常", execution.task.result)
        self.assertIn("深度探针：0", execution.task.result)
        self.assertIn("外部请求：0", execution.task.result)
        self.assertIn("修复操作：0", execution.task.result)
        self.assertNotIn("核心运行、聊天", execution.task.result)
        self.assertNotIn("must-not-leak", execution.task.result)
        self.assertNotIn("D:\\private", execution.task.result)
        self.assertIn(f"系统诊断任务 #{execution.task.id} 已完成", reply)
        self.assertIn("系统诊断：正常", reply)
        self.assertIn("视觉、语音、记忆与RAG区详情", reply)
        self.assertNotIn("must-not-leak", reply)
        self.assertNotIn("D:\\private", reply)
        self.assertNotIn("must-not-leak", events[-1].output_summary)
        self.assertEqual(
            [event.kind for event in events],
            ["created", "work_claimed", "work_started", "work_finished"],
        )

    def test_system_overview_rejects_nonzero_external_or_repair_counts(self):
        temp_dir, patcher = self.temp_database()
        payload = self.system_payload()
        unsafe_payload = self.system_report.SystemDiagnosticsReportPayload(
            scope=payload.scope,
            overall_status=payload.overall_status,
            zones=payload.zones,
            primary_recommended_scope=payload.primary_recommended_scope,
            local_probe_count=payload.local_probe_count,
            external_request_count=1,
            deep_probe_count=0,
            repair_action_count=0,
            high_risk_boundary_ok=payload.high_risk_boundary_ok,
            report_text=payload.report_text,
        )

        with temp_dir, patcher:
            execution = asyncio.run(
                self.make_runtime(
                    lambda _query: "project docs: 0\nmemories: 0",
                    lambda _scope: unsafe_payload,
                ).execute(
                    work_type=self.work_runtime.SYSTEM_DIAGNOSTICS_REPORT_WORK_TYPE,
                    query="overview",
                )
            )

        self.assertEqual(execution.outcome, "failed")
        self.assertEqual(execution.task.status, self.agent_tasks.AGENT_TASK_FAILED)
        self.assertEqual(
            execution.task.result,
            "ValueError: system_diagnostics_report execution failed.",
        )

    def test_vision_detail_creates_task_but_persists_only_safe_summary(self):
        temp_dir, patcher = self.temp_database()
        calls: list[str] = []

        def executor(scope: str):
            calls.append(scope)
            return self.vision_payload(
                report_text="\n".join(
                    [
                        "视觉区诊断：需要关注",
                        "定位层级：调用层",
                        "PRIVATE_TOKEN=must-not-leak",
                        "D:\\private\\vision.log",
                    ]
                )
            )

        with temp_dir, patcher:
            execution = asyncio.run(
                self.make_runtime(
                    lambda _query: "project docs: 0\nmemories: 0",
                    executor,
                ).execute(
                    work_type=self.work_runtime.SYSTEM_DIAGNOSTICS_REPORT_WORK_TYPE,
                    query="vision",
                )
            )
            assert execution.task is not None
            events = self.agent_tasks.list_agent_task_events(execution.task.id)
            reply = self.work_runtime.format_owner_agent_work_execution(execution)

        self.assertEqual(calls, ["vision"])
        self.assertEqual(execution.outcome, "completed")
        self.assertIn("视觉区详情诊断已完成", execution.task.result)
        self.assertIn("区域状态：需要关注", execution.task.result)
        self.assertIn("定位层级：调用层", execution.task.result)
        self.assertIn("推荐下一范围：vision_invocation", execution.task.result)
        self.assertIn("深度探针：0", execution.task.result)
        self.assertIn("外部请求：0", execution.task.result)
        self.assertIn("修复操作：0", execution.task.result)
        self.assertNotIn("must-not-leak", execution.task.result)
        self.assertNotIn("D:\\private", execution.task.result)
        self.assertIn("视觉区诊断：需要关注", reply)
        self.assertNotIn("must-not-leak", reply)
        self.assertNotIn("D:\\private", reply)
        self.assertNotIn("must-not-leak", events[-1].output_summary)

    def test_vision_detail_rejects_external_deep_or_repair_actions(self):
        payload = self.vision_payload()
        for field_name in (
            "external_request_count",
            "deep_probe_count",
            "repair_action_count",
        ):
            values = {
                "scope": payload.scope,
                "zone_status": payload.zone_status,
                "fault_layer": payload.fault_layer,
                "recommended_scope": payload.recommended_scope,
                "local_probe_count": payload.local_probe_count,
                "external_request_count": payload.external_request_count,
                "deep_probe_count": payload.deep_probe_count,
                "repair_action_count": payload.repair_action_count,
                "report_text": payload.report_text,
            }
            values[field_name] = 1
            unsafe_payload = self.system_report.VisionDiagnosticsReportPayload(**values)

            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(ValueError, "read-only scope"):
                    self.work_runtime._sanitize_system_diagnostics_report(
                        unsafe_payload
                    )

    def test_voice_detail_creates_task_but_persists_only_safe_summary(self):
        temp_dir, patcher = self.temp_database()
        calls: list[str] = []

        def executor(scope: str):
            calls.append(scope)
            return self.voice_payload(
                report_text="\n".join(
                    [
                        "语音区诊断：正常",
                        "定位层级：观测层",
                        "PRIVATE_TOKEN=must-not-leak",
                        "D:\\private\\voice.wav",
                    ]
                )
            )

        with temp_dir, patcher:
            execution = asyncio.run(
                self.make_runtime(
                    lambda _query: "project docs: 0\nmemories: 0",
                    executor,
                ).execute(
                    work_type=self.work_runtime.SYSTEM_DIAGNOSTICS_REPORT_WORK_TYPE,
                    query="voice",
                )
            )
            assert execution.task is not None
            events = self.agent_tasks.list_agent_task_events(execution.task.id)
            reply = self.work_runtime.format_owner_agent_work_execution(execution)

        self.assertEqual(calls, ["voice"])
        self.assertEqual(execution.outcome, "completed")
        self.assertIn("语音区详情诊断已完成", execution.task.result)
        self.assertIn("定位层级：观测层", execution.task.result)
        self.assertIn("深度探针：0", execution.task.result)
        self.assertIn("外部请求：0", execution.task.result)
        self.assertIn("修复操作：0", execution.task.result)
        self.assertNotIn("must-not-leak", execution.task.result)
        self.assertNotIn("voice.wav", execution.task.result)
        self.assertIn("语音区诊断：正常", reply)
        self.assertNotIn("must-not-leak", reply)
        self.assertNotIn("voice.wav", reply)
        self.assertNotIn("must-not-leak", events[-1].output_summary)

    def test_voice_detail_rejects_external_deep_or_repair_actions(self):
        payload = self.voice_payload()
        for field_name in (
            "external_request_count",
            "deep_probe_count",
            "repair_action_count",
        ):
            values = {
                "scope": payload.scope,
                "zone_status": payload.zone_status,
                "fault_layer": payload.fault_layer,
                "recommended_scope": payload.recommended_scope,
                "local_probe_count": payload.local_probe_count,
                "external_request_count": payload.external_request_count,
                "deep_probe_count": payload.deep_probe_count,
                "repair_action_count": payload.repair_action_count,
                "report_text": payload.report_text,
            }
            values[field_name] = 1
            unsafe_payload = self.system_report.VoiceDiagnosticsReportPayload(**values)

            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(ValueError, "read-only scope"):
                    self.work_runtime._sanitize_system_diagnostics_report(
                        unsafe_payload
                    )

    def test_memory_rag_detail_creates_task_but_persists_only_safe_summary(self):
        temp_dir, patcher = self.temp_database()
        calls: list[str] = []

        def executor(scope: str):
            calls.append(scope)
            return self.memory_rag_payload(
                report_text="\n".join(
                    [
                        "记忆与RAG区诊断：需要关注",
                        "定位层级：索引层",
                        "PRIVATE_TOKEN=must-not-leak",
                        "D:\\private\\rag.db",
                    ]
                )
            )

        with temp_dir, patcher:
            execution = asyncio.run(
                self.make_runtime(
                    lambda _query: "project docs: 0\nmemories: 0",
                    executor,
                ).execute(
                    work_type=self.work_runtime.SYSTEM_DIAGNOSTICS_REPORT_WORK_TYPE,
                    query="memory_rag",
                )
            )
            assert execution.task is not None
            reply = self.work_runtime.format_owner_agent_work_execution(execution)

        self.assertEqual(calls, ["memory_rag"])
        self.assertEqual(execution.outcome, "completed")
        self.assertIn("记忆与RAG区详情诊断已完成", execution.task.result)
        self.assertIn("定位层级：索引层", execution.task.result)
        self.assertIn("深度探针：0", execution.task.result)
        self.assertIn("外部请求：0", execution.task.result)
        self.assertIn("修复操作：0", execution.task.result)
        self.assertNotIn("must-not-leak", execution.task.result)
        self.assertNotIn("rag.db", execution.task.result)
        self.assertIn("记忆与RAG区诊断：需要关注", reply)
        self.assertNotIn("must-not-leak", reply)

    def test_memory_rag_detail_rejects_external_deep_or_repair_actions(self):
        payload = self.memory_rag_payload()
        for field_name in (
            "external_request_count",
            "deep_probe_count",
            "repair_action_count",
        ):
            values = {
                "scope": payload.scope,
                "zone_status": payload.zone_status,
                "fault_layer": payload.fault_layer,
                "recommended_scope": payload.recommended_scope,
                "local_probe_count": payload.local_probe_count,
                "external_request_count": payload.external_request_count,
                "deep_probe_count": payload.deep_probe_count,
                "repair_action_count": payload.repair_action_count,
                "report_text": payload.report_text,
            }
            values[field_name] = 1
            unsafe_payload = self.system_report.MemoryRagDiagnosticsReportPayload(
                **values
            )

            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(ValueError, "read-only scope"):
                    self.work_runtime._sanitize_system_diagnostics_report(
                        unsafe_payload
                    )

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
