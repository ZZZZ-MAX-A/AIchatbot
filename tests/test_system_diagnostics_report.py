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

    def voice_evidence(
        self,
        *,
        enabled=True,
        service_is_loopback=True,
        service_reachable=True,
        service_ok=True,
        model_loaded=True,
        language="zh",
        recent_candidate_present=True,
        recent_generation_observation_present=False,
        recent_send_observation_present=False,
    ):
        return self.report.VoiceZoneEvidence(
            enabled=enabled,
            service_ok=service_ok,
            model_loaded=model_loaded,
            service_is_loopback=service_is_loopback,
            service_reachable=service_reachable,
            language=language,
            recent_candidate_present=recent_candidate_present,
            recent_generation_observation_present=(
                recent_generation_observation_present
            ),
            recent_send_observation_present=recent_send_observation_present,
        )

    def memory_evidence(
        self,
        *,
        memory_rag_enabled=True,
        memory_rag_inject_in_chat=True,
        project_doc_rag_enabled=True,
        storage_ok=True,
        document_count=10,
        embedding_count=10,
        pending_count=0,
        recent_observation_present=True,
        recent_error=False,
        recent_attempted=True,
        recent_result_count=1,
    ):
        return self.report.MemoryRagZoneEvidence(
            memory_rag_enabled=memory_rag_enabled,
            memory_rag_inject_in_chat=memory_rag_inject_in_chat,
            project_doc_rag_enabled=project_doc_rag_enabled,
            storage_ok=storage_ok,
            document_count=document_count,
            embedding_count=embedding_count,
            pending_count=pending_count,
            recent_observation_present=recent_observation_present,
            recent_error=recent_error,
            recent_attempted=recent_attempted,
            recent_result_count=recent_result_count,
        )

    def overview_with_zone_evidence(
        self,
        *,
        vision=None,
        voice=None,
        memory_rag=None,
    ):
        baseline = self.evidence()
        return self.report.SystemDiagnosticsOverviewEvidence(
            core=baseline.core,
            chat=baseline.chat,
            main_agent=baseline.main_agent,
            memory_rag=memory_rag or baseline.memory_rag,
            vision=vision or baseline.vision,
            voice=voice or baseline.voice,
            local_probe_count=baseline.local_probe_count,
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

    def test_voice_problem_recommends_registered_voice_detail(self):
        payload = self.report.build_system_diagnostics_overview(
            self.evidence(
                voice_enabled=True,
                voice_service_ok=False,
                voice_model_loaded=None,
            )
        )

        self.assertEqual(payload.primary_recommended_scope, self.report.ZONE_VOICE)
        self.assertIn("建议优先排查：语音区", payload.report_text)
        self.assertIn("/agent 执行系统诊断任务：语音", payload.report_text)
        self.assertIn("本次未自动创建区域详情任务", payload.report_text)

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
        self.assertIn("/agent 执行系统诊断任务：记忆与RAG", payload.report_text)
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

    def test_voice_detail_disabled_stops_at_configuration(self):
        payload = self.report.build_voice_diagnostics_report(
            self.voice_evidence(enabled=False, service_ok=False, model_loaded=False)
        )

        self.assertEqual(payload.scope, "voice")
        self.assertEqual(payload.zone_status.status, self.report.STATUS_OFF_BY_DESIGN)
        self.assertEqual(payload.fault_layer, self.report.VOICE_LAYER_CONFIGURATION)
        self.assertNotIn("- 本地服务", payload.report_text)
        self.assertNotIn("- IndexTTS2", payload.report_text)

    def test_voice_detail_remote_endpoint_is_not_probed_or_marked_healthy(self):
        payload = self.report.build_voice_diagnostics_report(
            self.voice_evidence(
                service_is_loopback=False,
                service_reachable=None,
                service_ok=None,
                model_loaded=None,
            )
        )

        self.assertEqual(payload.zone_status.status, self.report.STATUS_UNKNOWN)
        self.assertEqual(payload.fault_layer, self.report.VOICE_LAYER_ENDPOINT)
        self.assertIn("非本机地址，本次未主动访问", payload.report_text)
        self.assertIn("未验证健康接口、IndexTTS2、语言和运行观测", payload.report_text)
        self.assertNotIn("- IndexTTS2", payload.report_text)

    def test_voice_detail_service_failure_stops_before_model(self):
        payload = self.report.build_voice_diagnostics_report(
            self.voice_evidence(
                service_reachable=False,
                service_ok=False,
                model_loaded=False,
            ),
            local_probe_count=1,
        )

        self.assertEqual(payload.zone_status.status, self.report.STATUS_DEGRADED)
        self.assertEqual(payload.fault_layer, self.report.VOICE_LAYER_SERVICE)
        self.assertIn("本地服务：不可用", payload.report_text)
        self.assertIn("健康接口：未继续检查（本地服务不可达）", payload.report_text)
        self.assertIn("IndexTTS2：未继续判断（本地服务不可达）", payload.report_text)
        self.assertIn("语言：未继续判断（本地服务不可达）", payload.report_text)
        self.assertIn("最近生成观测：未继续判断（本地服务不可达）", payload.report_text)
        self.assertIn("最近发送观测：未继续判断（本地服务不可达）", payload.report_text)

    def test_voice_detail_unloaded_model_stops_before_observations(self):
        payload = self.report.build_voice_diagnostics_report(
            self.voice_evidence(model_loaded=False),
            local_probe_count=1,
        )

        self.assertEqual(payload.zone_status.status, self.report.STATUS_ATTENTION)
        self.assertEqual(payload.fault_layer, self.report.VOICE_LAYER_MODEL)
        self.assertIn("IndexTTS2：未加载", payload.report_text)
        self.assertIn("最近生成观测：未继续判断（模型加载状态未通过）", payload.report_text)
        self.assertIn("最近发送观测：未继续判断（模型加载状态未通过）", payload.report_text)
        self.assertIn("本次不加载或下载模型", payload.report_text)

    def test_voice_detail_without_send_observation_is_not_end_to_end_proof(self):
        payload = self.report.build_voice_diagnostics_report(
            self.voice_evidence(),
            local_probe_count=1,
        )

        self.assertEqual(payload.zone_status.status, self.report.STATUS_NORMAL)
        self.assertEqual(payload.fault_layer, self.report.VOICE_LAYER_OBSERVATION)
        self.assertIn("最近语音候选：存在", payload.report_text)
        self.assertIn("最近生成观测：暂无结构化成功证据", payload.report_text)
        self.assertIn("最近发送观测：暂无结构化成功证据", payload.report_text)
        self.assertIn("不等于已完成端到端验证", payload.report_text)

    def test_voice_detail_recent_safe_send_observation_is_normal_and_bounded(self):
        payload = self.report.build_voice_diagnostics_report(
            self.voice_evidence(
                recent_generation_observation_present=True,
                recent_send_observation_present=True,
            ),
            local_probe_count=1,
        )

        self.assertEqual(payload.zone_status.status, self.report.STATUS_NORMAL)
        self.assertEqual(payload.fault_layer, self.report.VOICE_LAYER_NONE)
        self.assertIn("最近发送观测：存在安全成功证据", payload.report_text)
        self.assertIn("未生成测试语音、创建音频文件、发送 QQ", payload.report_text)
        self.assertEqual(payload.external_request_count, 0)
        self.assertEqual(payload.deep_probe_count, 0)
        self.assertEqual(payload.repair_action_count, 0)
        self.assertLessEqual(
            len(payload.report_text),
            self.report.SYSTEM_DIAGNOSTICS_VOICE_RESPONSE_LIMIT,
        )

    def test_voice_detail_rejects_negative_probe_count(self):
        with self.assertRaisesRegex(ValueError, "voice diagnostics count"):
            self.report.build_voice_diagnostics_report(
                self.voice_evidence(),
                local_probe_count=-1,
            )

    def test_memory_rag_detail_disabled_stops_at_configuration(self):
        payload = self.report.build_memory_rag_diagnostics_report(
            self.memory_evidence(
                memory_rag_enabled=False,
                memory_rag_inject_in_chat=False,
                project_doc_rag_enabled=False,
                storage_ok=None,
                document_count=0,
                embedding_count=0,
                recent_observation_present=False,
                recent_attempted=False,
                recent_result_count=0,
            )
        )

        self.assertEqual(payload.scope, "memory_rag")
        self.assertEqual(payload.zone_status.status, self.report.STATUS_OFF_BY_DESIGN)
        self.assertEqual(
            payload.fault_layer,
            self.report.MEMORY_RAG_LAYER_CONFIGURATION,
        )
        self.assertNotIn("活动文档", payload.report_text)

    def test_memory_rag_detail_storage_failure_stops_before_index(self):
        payload = self.report.build_memory_rag_diagnostics_report(
            self.memory_evidence(storage_ok=False),
            local_probe_count=1,
        )

        self.assertEqual(payload.zone_status.status, self.report.STATUS_DEGRADED)
        self.assertEqual(payload.fault_layer, self.report.MEMORY_RAG_LAYER_STORAGE)
        self.assertIn("本地索引统计：读取失败", payload.report_text)
        self.assertNotIn("缺少向量的活动文档", payload.report_text)

    def test_memory_rag_detail_pending_items_are_reported_without_rebuild(self):
        payload = self.report.build_memory_rag_diagnostics_report(
            self.memory_evidence(pending_count=2),
            local_probe_count=1,
        )

        self.assertEqual(payload.zone_status.status, self.report.STATUS_ATTENTION)
        self.assertEqual(payload.fault_layer, self.report.MEMORY_RAG_LAYER_INDEX)
        self.assertIn("待索引内容：2", payload.report_text)
        self.assertIn("只报告现象，不执行 embedding 或重建", payload.report_text)
        self.assertIn("未执行 embedding 自检、语义召回", payload.report_text)

    def test_memory_rag_detail_missing_vectors_are_reported(self):
        payload = self.report.build_memory_rag_diagnostics_report(
            self.memory_evidence(document_count=10, embedding_count=8),
            local_probe_count=1,
        )

        self.assertEqual(payload.fault_layer, self.report.MEMORY_RAG_LAYER_INDEX)
        self.assertIn("缺少向量的活动文档：2", payload.report_text)
        self.assertEqual(payload.repair_action_count, 0)

    def test_memory_rag_detail_recent_error_stops_at_runtime_observation(self):
        payload = self.report.build_memory_rag_diagnostics_report(
            self.memory_evidence(recent_error=True),
            local_probe_count=1,
        )

        self.assertEqual(payload.fault_layer, self.report.MEMORY_RAG_LAYER_RUNTIME)
        self.assertIn("最近运行观测：记录到错误", payload.report_text)

    def test_memory_rag_detail_without_recent_use_is_not_retrieval_proof(self):
        payload = self.report.build_memory_rag_diagnostics_report(
            self.memory_evidence(
                recent_observation_present=False,
                recent_attempted=False,
                recent_result_count=0,
            ),
            local_probe_count=1,
        )

        self.assertEqual(payload.zone_status.status, self.report.STATUS_NORMAL)
        self.assertEqual(payload.fault_layer, self.report.MEMORY_RAG_LAYER_OBSERVATION)
        self.assertIn("最近运行观测：暂无", payload.report_text)
        self.assertIn("不等于已完成语义召回验证", payload.report_text)

    def test_memory_rag_detail_recent_hits_are_normal_and_bounded(self):
        payload = self.report.build_memory_rag_diagnostics_report(
            self.memory_evidence(recent_result_count=2),
            local_probe_count=1,
        )

        self.assertEqual(payload.zone_status.status, self.report.STATUS_NORMAL)
        self.assertEqual(payload.fault_layer, self.report.MEMORY_RAG_LAYER_NONE)
        self.assertIn("尝试召回=是，结果数=2", payload.report_text)
        self.assertEqual(payload.external_request_count, 0)
        self.assertEqual(payload.deep_probe_count, 0)
        self.assertEqual(payload.repair_action_count, 0)
        self.assertLessEqual(
            len(payload.report_text),
            self.report.SYSTEM_DIAGNOSTICS_MEMORY_RAG_RESPONSE_LIMIT,
        )

    def test_memory_rag_detail_rejects_negative_counts(self):
        with self.assertRaisesRegex(ValueError, "memory RAG diagnostics count"):
            self.report.build_memory_rag_diagnostics_report(
                self.memory_evidence(recent_result_count=-1),
                local_probe_count=1,
            )

    def test_overview_and_vision_detail_keep_the_same_zone_status(self):
        scenarios = {
            "off_by_design": self.vision_evidence(enabled=False),
            "service_unknown": self.vision_evidence(service_ok=None),
            "service_degraded": self.vision_evidence(service_ok=False),
            "model_degraded": self.vision_evidence(model_exists=False),
            "recent_error": self.vision_evidence(recent_error_count=1),
            "low_quality": self.vision_evidence(recent_low_quality_count=1),
            "no_recent_use": self.vision_evidence(recent_usage_present=False),
            "normal": self.vision_evidence(),
        }

        for name, evidence in scenarios.items():
            with self.subTest(name=name):
                overview = self.report.build_system_diagnostics_overview(
                    self.overview_with_zone_evidence(vision=evidence)
                )
                detail = self.report.build_vision_diagnostics_report(evidence)
                self.assertEqual(
                    self.zone(overview, self.report.ZONE_VISION).status,
                    detail.zone_status.status,
                )

    def test_overview_and_voice_detail_keep_the_same_zone_status(self):
        scenarios = {
            "off_by_design": self.voice_evidence(enabled=False),
            "remote_unverified": self.voice_evidence(
                service_is_loopback=False,
                service_reachable=None,
                service_ok=None,
                model_loaded=None,
            ),
            "service_degraded": self.voice_evidence(
                service_reachable=False,
                service_ok=False,
                model_loaded=None,
            ),
            "model_attention": self.voice_evidence(model_loaded=False),
            "no_send_observation": self.voice_evidence(),
            "safe_send_observation": self.voice_evidence(
                recent_generation_observation_present=True,
                recent_send_observation_present=True,
            ),
        }

        for name, evidence in scenarios.items():
            with self.subTest(name=name):
                overview = self.report.build_system_diagnostics_overview(
                    self.overview_with_zone_evidence(voice=evidence)
                )
                detail = self.report.build_voice_diagnostics_report(evidence)
                self.assertEqual(
                    self.zone(overview, self.report.ZONE_VOICE).status,
                    detail.zone_status.status,
                )

    def test_overview_and_memory_rag_detail_keep_the_same_zone_status(self):
        scenarios = {
            "off_by_design": self.memory_evidence(
                memory_rag_enabled=False,
                memory_rag_inject_in_chat=False,
                project_doc_rag_enabled=False,
                storage_ok=None,
                document_count=0,
                embedding_count=0,
                recent_observation_present=False,
                recent_attempted=False,
                recent_result_count=0,
            ),
            "storage_unknown": self.memory_evidence(storage_ok=None),
            "storage_degraded": self.memory_evidence(storage_ok=False),
            "pending": self.memory_evidence(pending_count=2),
            "missing_vectors": self.memory_evidence(
                document_count=10,
                embedding_count=8,
            ),
            "recent_error": self.memory_evidence(recent_error=True),
            "no_recent_use": self.memory_evidence(
                recent_observation_present=False,
                recent_attempted=False,
                recent_result_count=0,
            ),
            "normal": self.memory_evidence(),
        }

        for name, evidence in scenarios.items():
            with self.subTest(name=name):
                overview = self.report.build_system_diagnostics_overview(
                    self.overview_with_zone_evidence(memory_rag=evidence)
                )
                detail = self.report.build_memory_rag_diagnostics_report(evidence)
                self.assertEqual(
                    self.zone(overview, self.report.ZONE_MEMORY_RAG).status,
                    detail.zone_status.status,
                )

    def test_registered_detail_reports_keep_the_shared_usefulness_contract(self):
        reports = (
            self.report.build_vision_diagnostics_report(
                self.vision_evidence(recent_usage_present=False),
                local_probe_count=1,
            ).report_text,
            self.report.build_voice_diagnostics_report(
                self.voice_evidence(),
                local_probe_count=1,
            ).report_text,
            self.report.build_memory_rag_diagnostics_report(
                self.memory_evidence(
                    recent_observation_present=False,
                    recent_attempted=False,
                    recent_result_count=0,
                ),
                local_probe_count=1,
            ).report_text,
        )

        for report_text in reports:
            with self.subTest(report_text=report_text.splitlines()[0]):
                self.assertIn("定位层级：", report_text)
                self.assertIn("状态链：", report_text)
                self.assertIn("初步判断：", report_text)
                self.assertIn("建议下一范围：", report_text)
                self.assertIn("本次使用被动证据", report_text)
                self.assertRegex(report_text, "未执行|未生成")
                self.assertNotIn("爱可", report_text)
                self.assertNotIn("（认真", report_text)

    def test_only_loopback_service_urls_are_allowed_for_overview_probes(self):
        self.assertTrue(self.report.is_loopback_service_url("http://127.0.0.1:11434"))
        self.assertTrue(self.report.is_loopback_service_url("http://localhost:7861/health"))
        self.assertTrue(self.report.is_loopback_service_url("http://[::1]:11434"))
        self.assertFalse(self.report.is_loopback_service_url("https://example.com/api"))
        self.assertFalse(self.report.is_loopback_service_url("http://192.168.1.5:11434"))
        self.assertFalse(self.report.is_loopback_service_url("not-a-url"))


if __name__ == "__main__":
    unittest.main()
