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

    def external_payload(self, **overrides):
        values = {
            "provider_name": "fake_search",
            "result_count": 1,
            "source_host_count": 1,
            "dropped_result_count": 0,
            "external_request_count": 1,
            "response_truncated": False,
            "status_category": "completed",
            "error_category": "none",
            "report_text": "外部只读查询结果：\n1. 安全标题\n   安全摘要\n   来源：example.com",
        }
        values.update(overrides)
        return self.work_runtime.ExternalReadReportPayload(**values)

    def make_runtime(
        self,
        executor,
        system_executor=None,
        external_executor=None,
    ):
        if system_executor is None:
            system_executor = lambda _scope: self.system_payload()
        return self.work_runtime.OwnerAgentWorkRuntime(
            context=self.work_runtime.OwnerAgentWorkContext(
                session_key="private:10001",
                user_id="10001",
            ),
            development_context_report_executor=executor,
            system_diagnostics_report_executor=system_executor,
            external_read_report_executor=external_executor,
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

    def test_external_read_work_is_registered_only_when_executor_is_injected(self):
        runtime = self.make_runtime(
            lambda _query: "project docs: 0\nmemories: 0",
            external_executor=lambda _query: self.external_payload(),
        )

        self.assertEqual(
            runtime.registered_work_types,
            (
                self.work_runtime.DEVELOPMENT_CONTEXT_REPORT_WORK_TYPE,
                self.work_runtime.SYSTEM_DIAGNOSTICS_REPORT_WORK_TYPE,
                self.work_runtime.EXTERNAL_READ_REPORT_WORK_TYPE,
            ),
        )
        spec = runtime.work_spec(self.work_runtime.EXTERNAL_READ_REPORT_WORK_TYPE)
        self.assertEqual(spec.display_name, "外部只读查询报告")
        self.assertEqual(spec.risk_level, "read_external")
        self.assertEqual(spec.required_arguments, ("query",))
        self.assertFalse(spec.requires_approval)

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

    def test_external_read_command_parser_requires_the_exact_formal_prefix(self):
        parse = self.work_runtime.parse_external_read_report_command

        self.assertEqual(
            parse("执行外部只读查询：Python 3.14 发布信息"),
            "Python 3.14 发布信息",
        )
        self.assertEqual(parse("执行外部只读查询: public release"), "public release")
        self.assertEqual(parse("执行外部只读查询"), "")
        self.assertIsNone(parse("外部查询：Python 3.14 发布信息"))
        self.assertIsNone(parse("执行外部只读查询 Python 3.14 发布信息"))
        self.assertIsNone(parse("查一下今天的新闻"))

    def test_external_read_command_gate_checks_access_switch_provider_and_query(self):
        prepare = self.work_runtime.prepare_external_read_command
        base = {
            "is_private_session": True,
            "owner_authorized": True,
            "feature_enabled": True,
            "executor_configured": True,
        }

        cases = (
            ({**base, "is_private_session": False}, "只允许主人私聊"),
            ({**base, "owner_authorized": False}, "需要主人权限"),
            ({**base, "feature_enabled": False}, "ENABLE_AGENT_WEB=false"),
            ({**base, "executor_configured": False}, "provider 尚未配置"),
        )
        for arguments, expected in cases:
            with self.subTest(expected=expected):
                decision = prepare("公开信息", **arguments)
                self.assertFalse(decision.allowed)
                self.assertIn(expected, decision.reply_text)

        invalid = prepare("https://example.com/private", **base)
        self.assertFalse(invalid.allowed)
        self.assertIn("invalid_query", invalid.reply_text)
        self.assertNotIn("example.com", invalid.reply_text)

        sensitive = prepare("API_KEY=must-not-leak", **base)
        self.assertFalse(sensitive.allowed)
        self.assertIn("sensitive_query", sensitive.reply_text)
        self.assertNotIn("must-not-leak", sensitive.reply_text)

        allowed = prepare("  Python   3.14\x00 发布信息  ", **base)
        self.assertTrue(allowed.allowed)
        self.assertEqual(allowed.normalized_query, "Python 3.14 发布信息")
        self.assertEqual(allowed.reply_text, "")

    def test_external_read_disabled_gate_precedes_query_validation(self):
        decision = self.work_runtime.prepare_external_read_command(
            "API_KEY=must-not-leak",
            is_private_session=True,
            owner_authorized=True,
            feature_enabled=False,
            executor_configured=True,
        )

        self.assertFalse(decision.allowed)
        self.assertIn("ENABLE_AGENT_WEB=false", decision.reply_text)
        self.assertNotIn("sensitive_query", decision.reply_text)
        self.assertNotIn("must-not-leak", decision.reply_text)

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

    def test_voice_on_demand_startup_layer_completes_formal_work_task(self):
        temp_dir, patcher = self.temp_database()
        payload = self.system_report.build_voice_diagnostics_report(
            self.system_report.VoiceZoneEvidence(
                enabled=True,
                service_ok=False,
                model_loaded=None,
                auto_start_enabled=True,
                service_is_loopback=True,
                service_reachable=False,
                recent_candidate_present=False,
                recent_generation_observation_present=False,
                recent_send_observation_present=False,
            ),
            local_probe_count=1,
        )

        with temp_dir, patcher:
            execution = asyncio.run(
                self.make_runtime(
                    lambda _query: "project docs: 0\nmemories: 0",
                    lambda _scope: payload,
                ).execute(
                    work_type=self.work_runtime.SYSTEM_DIAGNOSTICS_REPORT_WORK_TYPE,
                    query="voice",
                )
            )
            assert execution.task is not None
            reply = self.work_runtime.format_owner_agent_work_execution(execution)

        self.assertEqual(execution.outcome, "completed")
        self.assertEqual(execution.task.status, self.agent_tasks.AGENT_TASK_DONE)
        self.assertIn("语音区详情诊断已完成", execution.task.result)
        self.assertIn("区域状态：正常", execution.task.result)
        self.assertIn("定位层级：启动策略层", execution.task.result)
        self.assertIn("语音区诊断：正常", reply)
        self.assertIn("按需冷启动待机设计", reply)

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

    def test_external_read_work_keeps_query_and_result_details_ephemeral(self):
        temp_dir, patcher = self.temp_database()
        calls: list[str] = []
        query = "查询 Python 3.14 的公开发布信息"

        async def executor(value: str):
            calls.append(value)
            return self.external_payload(
                report_text="\n".join(
                    [
                        "外部只读查询结果：",
                        "1. Python 3.14 released",
                        "   This is a sanitized public snippet.",
                        "   来源：docs.python.org",
                    ]
                )
            )

        with temp_dir, patcher:
            execution = asyncio.run(
                self.make_runtime(
                    lambda _query: "project docs: 0\nmemories: 0",
                    external_executor=executor,
                ).execute(
                    work_type=self.work_runtime.EXTERNAL_READ_REPORT_WORK_TYPE,
                    query=query,
                )
            )
            assert execution.task is not None
            events = self.agent_tasks.list_agent_task_events(execution.task.id)
            reply = self.work_runtime.format_owner_agent_work_execution(execution)

        self.assertEqual(calls, [query])
        self.assertEqual(execution.outcome, "completed")
        self.assertEqual(execution.task.status, self.agent_tasks.AGENT_TASK_DONE)
        self.assertEqual(
            [event.kind for event in events],
            ["created", "work_claimed", "work_started", "work_finished"],
        )
        persisted = "\n".join(
            [
                execution.task.title,
                execution.task.goal,
                execution.task.result,
                *(
                    f"{event.input_json}\n{event.output_summary}\n{event.error}"
                    for event in events
                ),
            ]
        )
        self.assertNotIn(query, persisted)
        self.assertNotIn("Python 3.14 released", persisted)
        self.assertNotIn("sanitized public snippet", persisted)
        self.assertNotIn("docs.python.org", persisted)
        self.assertIn("原文未持久化", execution.task.goal)
        self.assertIn("Provider：fake_search", execution.task.result)
        self.assertIn("外部请求：1", execution.task.result)
        self.assertIn("Python 3.14 released", reply)
        self.assertIn("docs.python.org", reply)
        self.assertIn("外部只读查询任务", reply)
        self.assertIn("单次固定 provider 外部读取", reply)

    def test_external_read_no_results_is_a_completed_task(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            execution = asyncio.run(
                self.make_runtime(
                    lambda _query: "project docs: 0\nmemories: 0",
                    external_executor=lambda _query: self.external_payload(
                        result_count=0,
                        source_host_count=0,
                        status_category="no_results",
                        report_text="结果：未找到可用公开结果。\n本次未扩大查询，也未自动重试。",
                    ),
                ).execute(
                    work_type=self.work_runtime.EXTERNAL_READ_REPORT_WORK_TYPE,
                    query="一个没有公开结果的问题",
                )
            )

        self.assertEqual(execution.outcome, "completed")
        self.assertEqual(execution.task.status, self.agent_tasks.AGENT_TASK_DONE)
        self.assertIn("结果数：0", execution.task.result)
        self.assertIn("状态类别：no_results", execution.task.result)
        self.assertIn("未找到可用公开结果", execution.response_text)

    def test_external_read_sanitizer_rejects_invalid_counts_and_categories(self):
        invalid_payloads = (
            self.external_payload(external_request_count=0),
            self.external_payload(external_request_count=2),
            self.external_payload(result_count=-1),
            self.external_payload(result_count=True),
            self.external_payload(result_count=4),
            self.external_payload(source_host_count=2),
            self.external_payload(dropped_result_count=-1),
            self.external_payload(response_truncated=1),
            self.external_payload(provider_name="fake-search"),
            self.external_payload(provider_name=True),
            self.external_payload(status_category="failed"),
            self.external_payload(status_category=None),
            self.external_payload(error_category="provider_unavailable"),
            self.external_payload(error_category=None),
            self.external_payload(result_count=0, source_host_count=0),
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    self.work_runtime._sanitize_external_read_report(payload)

    def test_external_read_response_redacts_links_paths_and_secrets(self):
        sanitized = self.work_runtime._sanitize_external_read_report(
            self.external_payload(
                report_text=(
                    "详情 https://example.com/private?q=secret "
                    "D:\\private\\note.txt API_KEY=must-not-leak"
                )
            )
        )

        self.assertNotIn("https://", sanitized.response_text)
        self.assertNotIn("D:\\private", sanitized.response_text)
        self.assertNotIn("must-not-leak", sanitized.response_text)
        self.assertIn("[已脱敏链接]", sanitized.response_text)

    def test_external_read_executor_failure_never_persists_raw_exception(self):
        temp_dir, patcher = self.temp_database()

        def executor(_query: str):
            raise RuntimeError("Authorization: Bearer must-not-leak")

        with temp_dir, patcher:
            execution = asyncio.run(
                self.make_runtime(
                    lambda _query: "project docs: 0\nmemories: 0",
                    external_executor=executor,
                ).execute(
                    work_type=self.work_runtime.EXTERNAL_READ_REPORT_WORK_TYPE,
                    query="公开信息",
                )
            )
            assert execution.task is not None
            events = self.agent_tasks.list_agent_task_events(execution.task.id)

        self.assertEqual(execution.outcome, "failed")
        self.assertEqual(
            execution.task.result,
            "RuntimeError: external_read_report execution failed.",
        )
        self.assertNotIn("must-not-leak", execution.task.result)
        self.assertEqual(events[-1].kind, "work_failed")
        self.assertNotIn("must-not-leak", events[-1].error)

    def test_external_read_policy_failure_returns_localized_safe_reply(self):
        temp_dir, patcher = self.temp_database()

        def executor(_query: str):
            raise self.work_runtime.ExternalReadPolicyError(
                self.work_runtime.ExternalReadPolicyCategory.REQUEST_TIMEOUT,
                "Authorization: Bearer must-not-leak",
            )

        with temp_dir, patcher:
            execution = asyncio.run(
                self.make_runtime(
                    lambda _query: "project docs: 0\nmemories: 0",
                    external_executor=executor,
                ).execute(
                    work_type=self.work_runtime.EXTERNAL_READ_REPORT_WORK_TYPE,
                    query="公开信息",
                )
            )
            assert execution.task is not None
            events = self.agent_tasks.list_agent_task_events(execution.task.id)

        self.assertEqual(execution.outcome, "failed")
        self.assertIn("固定搜索 provider 请求超时", execution.response_text)
        self.assertIn("未自动重试", execution.response_text)
        self.assertIn("request_timeout", execution.task.result)
        self.assertNotIn("must-not-leak", execution.response_text)
        self.assertNotIn("must-not-leak", execution.task.result)
        self.assertNotIn("must-not-leak", events[-1].error)

    def test_external_read_auth_and_rate_limit_errors_have_distinct_safe_replies(self):
        cases = (
            (
                self.work_runtime.ExternalReadPolicyCategory.AUTHENTICATION_FAILED,
                "凭据未通过鉴权",
            ),
            (
                self.work_runtime.ExternalReadPolicyCategory.RATE_LIMITED,
                "当前返回限流",
            ),
        )

        for category, expected in cases:
            with self.subTest(category=category):
                error = self.work_runtime.ExternalReadPolicyError(
                    category,
                    "Authorization: Bearer must-not-leak",
                )
                reply = self.work_runtime.format_external_read_policy_error(error)
                self.assertIn(expected, reply)
                self.assertIn("未自动重试", reply)
                self.assertNotIn("must-not-leak", reply)

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
