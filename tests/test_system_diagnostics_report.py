from __future__ import annotations

import unittest

from pure_ai_chat_loader import AI_CHAT_ROOT, load_module


class SystemDiagnosticsReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = load_module(
            "src.plugins.ai_chat.system_diagnostics_report",
            AI_CHAT_ROOT / "system_diagnostics_report.py",
        )

    def evidence(
        self,
        *,
        database_ok=True,
        chat_enabled=True,
        chat_model_configured=True,
        chat_observed=True,
        chat_error=False,
        main_agent_enabled=True,
        owner_only=True,
        group_allowed=False,
        development_registered=True,
        system_registered=True,
        high_risk=(),
        memory_enabled=True,
        memory_inject=True,
        project_enabled=True,
        storage_ok=True,
        documents=10,
        embeddings=10,
        pending=0,
        memory_observed=True,
        memory_error=False,
        vision_enabled=True,
        vision_service_ok=True,
        vision_model_exists=True,
        vision_used=True,
        vision_errors=0,
        vision_low_quality=0,
        voice_enabled=False,
        voice_service_ok=None,
        voice_model_loaded=None,
        local_probes=2,
    ):
        return self.report.SystemDiagnosticsOverviewEvidence(
            core=self.report.CoreZoneEvidence(database_ok=database_ok),
            chat=self.report.ChatZoneEvidence(
                enabled=chat_enabled,
                model_configured=chat_model_configured,
                recent_observation_present=chat_observed,
                recent_error=chat_error,
            ),
            main_agent=self.report.MainAgentZoneEvidence(
                enabled=main_agent_enabled,
                owner_only=owner_only,
                group_allowed=group_allowed,
                development_report_registered=development_registered,
                system_report_registered=system_registered,
                owner_write_registered=True,
                owner_write_requires_approval=True,
                owner_write_resume_enabled=True,
                enabled_high_risk_capabilities=tuple(high_risk),
            ),
            memory_rag=self.report.MemoryRagZoneEvidence(
                memory_rag_enabled=memory_enabled,
                memory_rag_inject_in_chat=memory_inject,
                project_doc_rag_enabled=project_enabled,
                storage_ok=storage_ok,
                document_count=documents,
                embedding_count=embeddings,
                pending_count=pending,
                recent_observation_present=memory_observed,
                recent_error=memory_error,
            ),
            vision=self.report.VisionZoneEvidence(
                enabled=vision_enabled,
                service_ok=vision_service_ok,
                model_exists=vision_model_exists,
                recent_usage_present=vision_used,
                recent_error_count=vision_errors,
                recent_low_quality_count=vision_low_quality,
            ),
            voice=self.report.VoiceZoneEvidence(
                enabled=voice_enabled,
                service_ok=voice_service_ok,
                model_loaded=voice_model_loaded,
            ),
            local_probe_count=local_probes,
        )

    def zone(self, payload, zone_name):
        return next(zone for zone in payload.zones if zone.zone == zone_name)

    def vision_evidence(
        self,
        *,
        enabled=True,
        service_ok=True,
        model_exists=True,
        recent_usage_present=True,
        recent_error_count=0,
        recent_low_quality_count=0,
    ):
        return self.report.VisionZoneEvidence(
            enabled=enabled,
            service_ok=service_ok,
            model_exists=model_exists,
            recent_usage_present=recent_usage_present,
            recent_error_count=recent_error_count,
            recent_low_quality_count=recent_low_quality_count,
        )

    def test_normal_overview_groups_zones_and_stays_short(self):
        payload = self.report.build_system_diagnostics_overview(self.evidence())

        self.assertEqual(payload.scope, "overview")
        self.assertEqual(payload.overall_status, self.report.STATUS_NORMAL)
        self.assertEqual(payload.status_counts[self.report.STATUS_NORMAL], 5)
        self.assertEqual(payload.status_counts[self.report.STATUS_OFF_BY_DESIGN], 1)
        self.assertEqual(payload.primary_recommended_scope, "")
        self.assertIn("系统诊断：正常", payload.report_text)
        self.assertIn("正常：核心运行、聊天、MainAgent、记忆与RAG、视觉。", payload.report_text)
        self.assertIn("按设计关闭：语音。", payload.report_text)
        self.assertIn("未发现需要深入排查的大区", payload.report_text)
        self.assertIn("未执行模型推理、embedding/RAG 召回、外部请求", payload.report_text)
        self.assertNotIn("需关注区域：", payload.report_text)
        self.assertLessEqual(
            len(payload.report_text),
            self.report.SYSTEM_DIAGNOSTICS_OVERVIEW_RESPONSE_LIMIT,
        )

    def test_off_by_design_does_not_degrade_overall_status(self):
        payload = self.report.build_system_diagnostics_overview(
            self.evidence(
                chat_enabled=False,
                memory_enabled=False,
                project_enabled=False,
                vision_enabled=False,
                vision_service_ok=None,
                vision_model_exists=None,
                vision_used=False,
                voice_enabled=False,
            )
        )

        self.assertEqual(payload.overall_status, self.report.STATUS_NORMAL)
        self.assertEqual(payload.status_counts[self.report.STATUS_OFF_BY_DESIGN], 4)
        self.assertNotIn("建议优先排查", payload.report_text)

    def test_recent_vision_error_highlights_only_vision_and_recommends_one_zone(self):
        payload = self.report.build_system_diagnostics_overview(
            self.evidence(vision_errors=1)
        )

        vision = self.zone(payload, self.report.ZONE_VISION)
        self.assertEqual(vision.status, self.report.STATUS_ATTENTION)
        self.assertEqual(payload.overall_status, self.report.STATUS_ATTENTION)
        self.assertEqual(payload.primary_recommended_scope, self.report.ZONE_VISION)
        self.assertIn("视觉（需要关注）", payload.report_text)
        self.assertIn("服务在线、模型可用，但最近视觉使用记录了错误", payload.report_text)
        self.assertIn("建议优先排查：视觉区", payload.report_text)
        self.assertIn("/agent 执行系统诊断任务：视觉", payload.report_text)
        self.assertIn("本次未自动创建区域详情任务", payload.report_text)
        self.assertNotIn("视觉上下文", payload.report_text)
        self.assertNotIn("图片缓存", payload.report_text)

    def test_no_recent_vision_usage_is_neutral(self):
        payload = self.report.build_system_diagnostics_overview(
            self.evidence(vision_used=False)
        )

        vision = self.zone(payload, self.report.ZONE_VISION)
        self.assertEqual(vision.status, self.report.STATUS_NORMAL)
        self.assertIn("暂无近期使用证据", vision.headline)
        self.assertEqual(payload.overall_status, self.report.STATUS_NORMAL)

    def test_upstream_vision_failure_does_not_dump_downstream_evidence(self):
        payload = self.report.build_system_diagnostics_overview(
            self.evidence(
                vision_service_ok=False,
                vision_model_exists=False,
                vision_errors=2,
                vision_low_quality=3,
            )
        )

        vision = self.zone(payload, self.report.ZONE_VISION)
        self.assertEqual(vision.status, self.report.STATUS_DEGRADED)
        self.assertEqual(vision.headline, "视觉已开启，但 Ollama 服务不可用。")
        self.assertNotIn("低质量", payload.report_text)
        self.assertNotIn("最近视觉使用", payload.report_text)

    def test_core_error_has_priority_over_other_attention(self):
        payload = self.report.build_system_diagnostics_overview(
            self.evidence(database_ok=False, vision_errors=1, pending=2)
        )

        self.assertEqual(payload.overall_status, self.report.STATUS_ERROR)
        self.assertEqual(payload.primary_recommended_scope, self.report.ZONE_CORE)
        self.assertIn("数据库只读检查失败", payload.report_text)
        self.assertIn("建议优先排查：核心运行区", payload.report_text)
        self.assertIn("该区域详情尚未注册", payload.report_text)

    def test_memory_pending_is_attention_without_running_retrieval(self):
        payload = self.report.build_system_diagnostics_overview(
            self.evidence(pending=3)
        )

        memory = self.zone(payload, self.report.ZONE_MEMORY_RAG)
        self.assertEqual(memory.status, self.report.STATUS_ATTENTION)
        self.assertIn("3 条待索引", memory.headline)
        self.assertEqual(payload.external_request_count, 0)
        self.assertEqual(payload.deep_probe_count, 0)
        self.assertEqual(payload.repair_action_count, 0)

    def test_high_risk_flag_is_visible_as_main_agent_attention(self):
        payload = self.report.build_system_diagnostics_overview(
            self.evidence(high_risk=("Agent Web", "Shell"))
        )

        main_agent = self.zone(payload, self.report.ZONE_MAIN_AGENT)
        self.assertEqual(main_agent.status, self.report.STATUS_ATTENTION)
        self.assertFalse(payload.high_risk_boundary_ok)
        self.assertIn("Agent Web、Shell", main_agent.headline)
        self.assertIn("存在开启项", payload.report_text)

    def test_missing_registered_work_type_is_degraded(self):
        payload = self.report.build_system_diagnostics_overview(
            self.evidence(system_registered=False)
        )

        main_agent = self.zone(payload, self.report.ZONE_MAIN_AGENT)
        self.assertEqual(main_agent.status, self.report.STATUS_DEGRADED)
        self.assertIn("system_diagnostics_report", main_agent.headline)

    def test_owner_write_must_keep_approval_and_controlled_resume(self):
        evidence = self.evidence()
        unsafe_main_agent = self.report.MainAgentZoneEvidence(
            enabled=True,
            owner_only=True,
            group_allowed=False,
            development_report_registered=True,
            system_report_registered=True,
            owner_write_registered=True,
            owner_write_requires_approval=False,
            owner_write_resume_enabled=True,
        )
        payload = self.report.build_system_diagnostics_overview(
            self.report.SystemDiagnosticsOverviewEvidence(
                core=evidence.core,
                chat=evidence.chat,
                main_agent=unsafe_main_agent,
                memory_rag=evidence.memory_rag,
                vision=evidence.vision,
                voice=evidence.voice,
                local_probe_count=evidence.local_probe_count,
            )
        )

        main_agent = self.zone(payload, self.report.ZONE_MAIN_AGENT)
        self.assertEqual(main_agent.status, self.report.STATUS_ERROR)
        self.assertIn("未保持审批和受控恢复边界", main_agent.headline)

    def test_remote_or_unchecked_local_service_is_unknown_not_healthy(self):
        payload = self.report.build_system_diagnostics_overview(
            self.evidence(
                vision_service_ok=None,
                vision_model_exists=None,
                vision_used=False,
            )
        )

        vision = self.zone(payload, self.report.ZONE_VISION)
        self.assertEqual(vision.status, self.report.STATUS_UNKNOWN)
        self.assertEqual(payload.overall_status, self.report.STATUS_ATTENTION)
        self.assertIn("未确认本地 Ollama 状态", payload.report_text)

    def test_negative_probe_count_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "local probe count"):
            self.report.build_system_diagnostics_overview(
                self.evidence(local_probes=-1)
            )

    def test_vision_detail_disabled_stops_at_configuration(self):
        payload = self.report.build_vision_diagnostics_report(
            self.vision_evidence(
                enabled=False,
                service_ok=False,
                model_exists=False,
                recent_error_count=2,
            )
        )

        self.assertEqual(payload.scope, "vision")
        self.assertEqual(payload.zone_status.status, self.report.STATUS_OFF_BY_DESIGN)
        self.assertEqual(payload.fault_layer, self.report.VISION_LAYER_CONFIGURATION)
        self.assertEqual(payload.recommended_scope, "")
        self.assertIn("功能配置：关闭", payload.report_text)
        self.assertNotIn("- Ollama 服务", payload.report_text)
        self.assertNotIn("- 视觉模型", payload.report_text)
        self.assertNotIn("- 最近使用", payload.report_text)

    def test_vision_detail_remote_or_unchecked_service_stops_as_unknown(self):
        payload = self.report.build_vision_diagnostics_report(
            self.vision_evidence(
                service_ok=None,
                model_exists=True,
                recent_error_count=3,
            ),
            local_probe_count=0,
        )

        self.assertEqual(payload.zone_status.status, self.report.STATUS_UNKNOWN)
        self.assertEqual(payload.fault_layer, self.report.VISION_LAYER_SERVICE)
        self.assertIn("只允许检查本机 loopback 地址", payload.report_text)
        self.assertNotIn("- 视觉模型", payload.report_text)
        self.assertNotIn("- 最近使用", payload.report_text)

    def test_vision_detail_ollama_down_stops_before_model_and_usage(self):
        payload = self.report.build_vision_diagnostics_report(
            self.vision_evidence(
                service_ok=False,
                model_exists=False,
                recent_error_count=4,
            ),
            local_probe_count=1,
        )

        self.assertEqual(payload.zone_status.status, self.report.STATUS_DEGRADED)
        self.assertEqual(payload.fault_layer, self.report.VISION_LAYER_SERVICE)
        self.assertIn("Ollama 服务：不可用", payload.report_text)
        self.assertNotIn("- 视觉模型", payload.report_text)
        self.assertNotIn("- 最近使用", payload.report_text)

    def test_vision_detail_missing_model_stops_before_recent_usage(self):
        payload = self.report.build_vision_diagnostics_report(
            self.vision_evidence(
                model_exists=False,
                recent_error_count=2,
            ),
            local_probe_count=1,
        )

        self.assertEqual(payload.zone_status.status, self.report.STATUS_DEGRADED)
        self.assertEqual(payload.fault_layer, self.report.VISION_LAYER_MODEL)
        self.assertIn("Ollama 服务：在线", payload.report_text)
        self.assertIn("视觉模型：不可用", payload.report_text)
        self.assertNotIn("- 最近使用", payload.report_text)
        self.assertIn("本次不拉取模型", payload.report_text)

    def test_vision_detail_recent_error_recommends_unregistered_invocation_scope(self):
        payload = self.report.build_vision_diagnostics_report(
            self.vision_evidence(recent_error_count=1),
            local_probe_count=1,
        )

        self.assertEqual(payload.zone_status.status, self.report.STATUS_ATTENTION)
        self.assertEqual(payload.fault_layer, self.report.VISION_LAYER_INVOCATION)
        self.assertEqual(payload.recommended_scope, "vision_invocation")
        self.assertIn("最近使用：记录到错误", payload.report_text)
        self.assertIn("建议下一范围：vision_invocation", payload.report_text)
        self.assertIn("尚未注册", payload.report_text)
        self.assertEqual(payload.deep_probe_count, 0)

    def test_vision_detail_low_quality_recommends_unregistered_inference_scope(self):
        payload = self.report.build_vision_diagnostics_report(
            self.vision_evidence(recent_low_quality_count=1),
            local_probe_count=1,
        )

        self.assertEqual(payload.zone_status.status, self.report.STATUS_ATTENTION)
        self.assertEqual(payload.fault_layer, self.report.VISION_LAYER_QUALITY)
        self.assertEqual(payload.recommended_scope, "vision_inference")
        self.assertIn("最近使用：记录到低质量结果", payload.report_text)
        self.assertIn("建议下一范围：vision_inference", payload.report_text)

    def test_vision_detail_no_recent_use_is_neutral_not_end_to_end_proof(self):
        payload = self.report.build_vision_diagnostics_report(
            self.vision_evidence(recent_usage_present=False),
            local_probe_count=1,
        )

        self.assertEqual(payload.zone_status.status, self.report.STATUS_NORMAL)
        self.assertEqual(payload.fault_layer, self.report.VISION_LAYER_OBSERVATION)
        self.assertEqual(payload.recommended_scope, "")
        self.assertIn("暂无近期使用证据", payload.report_text)
        self.assertIn("不等于已完成端到端验证", payload.report_text)

    def test_vision_detail_recent_success_is_normal_and_bounded(self):
        payload = self.report.build_vision_diagnostics_report(
            self.vision_evidence(),
            local_probe_count=1,
        )

        self.assertEqual(payload.zone_status.status, self.report.STATUS_NORMAL)
        self.assertEqual(payload.fault_layer, self.report.VISION_LAYER_NONE)
        self.assertEqual(payload.recommended_scope, "")
        self.assertIn("未记录错误或低质量结果", payload.report_text)
        self.assertIn("未执行真实视觉推理、测试图片、外部请求", payload.report_text)
        self.assertNotIn("VISION_OLLAMA_BASE_URL", payload.report_text)
        self.assertNotIn("diagnostic.log", payload.report_text)
        self.assertLessEqual(
            len(payload.report_text),
            self.report.SYSTEM_DIAGNOSTICS_VISION_RESPONSE_LIMIT,
        )

    def test_vision_detail_rejects_negative_counts(self):
        with self.assertRaisesRegex(ValueError, "vision diagnostics count"):
            self.report.build_vision_diagnostics_report(
                self.vision_evidence(recent_error_count=-1)
            )

    def test_only_loopback_service_urls_are_allowed_for_overview_probes(self):
        self.assertTrue(self.report.is_loopback_service_url("http://127.0.0.1:11434"))
        self.assertTrue(self.report.is_loopback_service_url("http://localhost:7861/health"))
        self.assertTrue(self.report.is_loopback_service_url("http://[::1]:11434"))
        self.assertFalse(self.report.is_loopback_service_url("https://example.com/api"))
        self.assertFalse(self.report.is_loopback_service_url("http://192.168.1.5:11434"))
        self.assertFalse(self.report.is_loopback_service_url("not-a-url"))


if __name__ == "__main__":
    unittest.main()
