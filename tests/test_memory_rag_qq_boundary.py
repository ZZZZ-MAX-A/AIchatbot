from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ENTRY = REPO_ROOT / "src" / "plugins" / "ai_chat" / "__init__.py"
OWNER_RUNTIME_FACTORY = REPO_ROOT / "src" / "plugins" / "ai_chat" / "owner_runtime_factory.py"
OWNER_AGENT_WORK_RUNTIME = REPO_ROOT / "src" / "plugins" / "ai_chat" / "owner_agent_work_runtime.py"
SYSTEM_DIAGNOSTICS_REPORT = REPO_ROOT / "src" / "plugins" / "ai_chat" / "system_diagnostics_report.py"
OWNER_READ_RUNTIME = REPO_ROOT / "src" / "plugins" / "ai_chat" / "owner_read_runtime.py"
OWNER_WRITE_RUNTIME = REPO_ROOT / "src" / "plugins" / "ai_chat" / "owner_write_runtime.py"
MAIN_AGENT_BRIDGE = REPO_ROOT / "src" / "plugins" / "ai_chat" / "graph" / "main_agent_bridge.py"


class MemoryRagQqBoundaryTests(unittest.TestCase):
    def test_qq_plugin_registers_memory_rag_debug_and_gated_agent_commands(self):
        source = PLUGIN_ENTRY.read_text(encoding="utf-8")

        self.assertIn('aliases={"rag_status"}', source)
        self.assertIn('aliases={"memory_retrieval"}', source)
        self.assertIn('aliases={"rebuild_memory_rag_index"}', source)
        self.assertIn('on_command("agent", aliases={"main-agent"}', source)
        self.assertNotIn("project_doc_retrieval_cmd", source)
        self.assertNotIn("rebuild_project_doc_index_cmd", source)

    def test_qq_plugin_project_docs_stay_behind_agent_dev_context_boundary(self):
        source = PLUGIN_ENTRY.read_text(encoding="utf-8")

        self.assertIn("from .rag.memory_index import rebuild_memory_rag_index, retrieve_memory", source)
        self.assertIn("from .rag.combined import format_combined_rag_results, retrieve_combined_rag", source)
        self.assertIn("run_dev_context_graph_for_main_agent", source)
        self.assertNotIn("retrieve_project_docs", source)
        self.assertNotIn("rebuild_project_doc_index", source)
        self.assertNotIn("SOURCE_PROJECT_DOC", source)

    def test_current_state_strategy_is_enabled_only_for_formal_development_report(self):
        source = PLUGIN_ENTRY.read_text(encoding="utf-8")
        formal_start = source.index("async def run_development_context_report_for_event(")
        formal_end = source.index("\ndef owner_runtime_factory()", formal_start)
        generic_start = source.index("async def run_main_agent_qq_command(")
        generic_end = source.index("\n@main_agent_cmd.handle()", generic_start)

        self.assertIn(
            "use_development_report_evidence=True",
            source[formal_start:formal_end],
        )
        self.assertNotIn(
            "use_development_report_evidence=True",
            source[generic_start:generic_end],
        )
        self.assertEqual(source.count("use_development_report_evidence=True"), 1)

    def test_main_agent_qq_entry_is_feature_gated_and_read_only(self):
        source = PLUGIN_ENTRY.read_text(encoding="utf-8")
        factory_source = OWNER_RUNTIME_FACTORY.read_text(encoding="utf-8")

        self.assertIn("if not config.enable_main_agent:", source)
        self.assertIn("if config.main_agent_use_llm:", source)
        self.assertIn("create_main_agent_lc_call_handler(config)", source)
        self.assertIn("create_main_agent_tool_summary_lc_handler(config)", source)
        self.assertIn("主模型 Key", source)
        self.assertNotIn("主模型接口：", source)
        self.assertIn("main_agent_tool_status_reply", source)
        self.assertIn("/agent 工具状态", source)
        self.assertIn("owner_write_command", source)
        self.assertIn("approval_resume_enabled=true", source)
        self.assertIn("run_main_agent_task_command", source)
        self.assertIn("run_main_agent_explicit_work_command", source)
        self.assertIn("/agent 执行系统诊断任务：语音", source)
        self.assertIn("/agent 执行系统诊断任务：记忆与RAG", source)
        self.assertIn("is_explicit_main_agent_dev_context_query", source)
        self.assertIn('command_artifact["explicit_dev_context"]', source)
        self.assertIn("parse_development_context_report_command", source)
        self.assertIn("parse_system_diagnostics_report_command", source)
        self.assertIn("parse_external_read_report_command", source)
        self.assertIn("prepare_external_read_command", source)
        self.assertIn("factory.external_read_report_for_event is not None", source)
        self.assertIn("def _configured_external_read_report_for_event():", source)
        self.assertIn("if not config.enable_agent_web:", source)
        self.assertIn("create_configured_tavily_external_read_executor", source)
        self.assertIn("api_key=config.tavily_api_key", source)
        self.assertIn("timeout_seconds=config.tavily_timeout_seconds", source)
        self.assertIn(
            "external_read_report_for_event=_configured_external_read_report_for_event()",
            source,
        )
        external_factory_start = source.index(
            "def _configured_external_read_report_for_event():"
        )
        owner_factory_start = source.index(
            "\ndef owner_runtime_factory()",
            external_factory_start,
        )
        external_factory_source = source[external_factory_start:owner_factory_start]
        self.assertLess(
            external_factory_source.index("if not config.enable_agent_web:"),
            external_factory_source.index("from .tavily_external_read import"),
        )
        self.assertIn("except ImportError:", external_factory_source)
        self.assertNotIn("tavily_external_read", source[:external_factory_start])
        self.assertIn("execute_system_diagnostics_report", factory_source)
        self.assertIn("execute_external_read_report", factory_source)
        self.assertIn("/agent 执行外部只读查询：<问题>", source)
        self.assertIn("/agent 联网状态（纯本地，不发起外部请求）", source)
        self.assertIn("def external_read_status_reply(event: MessageEvent) -> str:", source)
        self.assertIn('if query.strip() in {"联网状态", "外部只读查询状态"}:', source)
        self.assertIn("本状态查询不访问 Tavily、不消耗 credit", source)
        self.assertIn('package_version("httpx")', source)
        self.assertIn('package_version("httpcore")', source)
        self.assertIn("HTTP 栈兼容性", source)
        self.assertIn("latest_external_read_task_snapshot", source)
        self.assertIn("external_read_task_snapshot_lines", source)
        self.assertIn("if not isinstance(event, PrivateMessageEvent):", source)
        self.assertIn("if not is_owner(config, event):", source)
        self.assertIn("OwnerRuntimeFactory", source)
        self.assertIn("owner_runtime_factory", source)
        self.assertIn("run_read_command", source)
        self.assertIn("run_write_command", source)
        self.assertIn("OwnerAgentContext", factory_source)
        self.assertIn("run_owner_agent_task_command", factory_source)
        self.assertIn("execute_development_context_report", factory_source)
        self.assertIn("format_owner_agent_task_read", factory_source)
        self.assertIn("execute_owner_agent_task_command", factory_source)
        self.assertIn("create_owner_agent_approval_request", factory_source)
        self.assertIn("OwnerReadRuntime", factory_source)
        self.assertIn("run_owner_read_command", factory_source)
        self.assertIn("OwnerWriteRuntime", factory_source)
        self.assertIn("run_owner_write_command", factory_source)
        self.assertNotIn("owner_read_runtime_from_event", source)
        self.assertIn("/agent 审批演练 <目标>", source)
        self.assertIn("create_read_only_main_agent_runtime_handler", source)
        self.assertIn("RuntimeIntent.MAIN_AGENT", source)
        system_start = source.index("def _collect_system_memory_rag_evidence(")
        vision_start = source.index(
            "async def _collect_system_vision_evidence(",
            system_start,
        )
        voice_start = source.index(
            "async def _collect_system_voice_evidence(",
            vision_start,
        )
        runner_start = source.index(
            "async def run_system_diagnostics_report_for_event(",
            voice_start,
        )
        system_end = source.index("\ndef owner_runtime_factory()", system_start)
        system_source = source[system_start:system_end]
        memory_collector_source = source[system_start:vision_start]
        vision_collector_source = source[vision_start:voice_start]
        voice_collector_source = source[voice_start:runner_start]
        runner_source = source[runner_start:system_end]
        self.assertIn("config.enable_agent_shell", system_source)
        self.assertIn("config.enable_agent_local_write", system_source)
        self.assertIn("config.enable_agent_external_write", system_source)
        self.assertIn("config.enable_agent_web", system_source)
        self.assertIn("asyncio.to_thread(check_ollama, config)", system_source)
        self.assertIn("build_vision_diagnostics_report", system_source)
        self.assertIn("build_voice_diagnostics_report", system_source)
        self.assertIn("build_memory_rag_diagnostics_report", system_source)
        self.assertIn("SYSTEM_DIAGNOSTICS_VISION_SCOPE", system_source)
        self.assertIn("SYSTEM_DIAGNOSTICS_VOICE_SCOPE", system_source)
        self.assertIn("SYSTEM_DIAGNOSTICS_MEMORY_RAG_SCOPE", system_source)
        self.assertIn("memory_rag_storage_stats(ensure_schema=False)", system_source)
        self.assertNotIn("check_embedding_provider", system_source)
        self.assertNotIn("run_dev_context_graph_for_main_agent", system_source)
        self.assertNotIn("call_main_llm", system_source)
        self.assertNotIn("describe_images", system_source)
        self.assertNotIn("_system_database_read_probe", vision_collector_source)
        self.assertNotIn("memory_rag_storage_stats", vision_collector_source)
        self.assertNotIn("tts_health_snapshot", vision_collector_source)
        self.assertIn("memory_rag_storage_stats(ensure_schema=False)", memory_collector_source)
        self.assertNotIn("check_embedding_provider", memory_collector_source)
        self.assertNotIn("retrieve_memory", memory_collector_source)
        self.assertNotIn("rebuild_memory_rag_index", memory_collector_source)
        self.assertNotIn("_system_database_read_probe", memory_collector_source)
        self.assertNotIn("check_ollama", memory_collector_source)
        self.assertNotIn("tts_health_snapshot", memory_collector_source)
        self.assertIn("tts_health_snapshot", voice_collector_source)
        self.assertIn("auto_start_enabled=config.tts_auto_start", voice_collector_source)
        self.assertIn("voice_runtime_status_label", source)
        self.assertNotIn("check_ollama", voice_collector_source)
        self.assertNotIn("describe_images", voice_collector_source)
        self.assertNotIn("run_voice_graph_intent", voice_collector_source)
        self.assertNotIn("memory_rag_storage_stats", voice_collector_source)
        self.assertLess(
            runner_source.index("if scope == SYSTEM_DIAGNOSTICS_MEMORY_RAG_SCOPE:"),
            runner_source.index("if scope == SYSTEM_DIAGNOSTICS_VOICE_SCOPE:"),
        )
        self.assertLess(
            runner_source.index("if scope == SYSTEM_DIAGNOSTICS_VOICE_SCOPE:"),
            runner_source.index("_collect_system_vision_evidence"),
        )
        self.assertLess(
            runner_source.index("if scope == SYSTEM_DIAGNOSTICS_VISION_SCOPE:"),
            runner_source.index("database_ok = _system_database_read_probe()"),
        )
        self.assertNotIn("access_operations = {", source)
        write_runtime_source = OWNER_WRITE_RUNTIME.read_text(encoding="utf-8")
        self.assertIn('if command == "clear_image_cache":', write_runtime_source)
        self.assertIn('if command == "select_persona":', write_runtime_source)
        self.assertIn('if command in {"add_fact_memory", "add_preference_memory"}:', write_runtime_source)
        self.assertIn("delete_session_summary requires numeric summary_id", write_runtime_source)
        work_runtime_source = OWNER_AGENT_WORK_RUNTIME.read_text(encoding="utf-8")
        self.assertIn("DEVELOPMENT_CONTEXT_REPORT_COMMAND_PREFIX", work_runtime_source)
        self.assertIn("parse_development_context_report_command", work_runtime_source)
        self.assertIn("parse_system_diagnostics_report_command", work_runtime_source)
        self.assertIn("SYSTEM_DIAGNOSTICS_REPORT_WORK_TYPE", work_runtime_source)
        self.assertIn("format_owner_agent_work_execution", work_runtime_source)
        self.assertNotIn("nonebot", work_runtime_source)
        self.assertNotIn("owner_write_runtime", work_runtime_source)
        system_report_source = SYSTEM_DIAGNOSTICS_REPORT.read_text(encoding="utf-8")
        self.assertIn("SYSTEM_DIAGNOSTICS_OVERVIEW_RESPONSE_LIMIT = 1200", system_report_source)
        self.assertIn("SYSTEM_DIAGNOSTICS_VISION_RESPONSE_LIMIT = 1800", system_report_source)
        self.assertNotIn("httpx", system_report_source)
        self.assertNotIn("openai", system_report_source.lower())

    def test_memory_rag_runner_uses_configured_owner_check(self):
        source = PLUGIN_ENTRY.read_text(encoding="utf-8")

        self.assertIn("is_owner=is_owner(config, event)", source)
        self.assertNotIn("is_owner=is_owner(event)", source)

    def test_external_read_strict_entry_is_not_registered_for_main_llm(self):
        bridge_source = MAIN_AGENT_BRIDGE.read_text(encoding="utf-8")

        self.assertNotIn("external_read_report", bridge_source)
        self.assertNotIn("execute_external_search", bridge_source)

    def test_memory_rag_status_includes_embedding_self_check(self):
        source = PLUGIN_ENTRY.read_text(encoding="utf-8")

        self.assertIn("check_embedding_provider", source)
        self.assertIn("memory_rag_embedding_check_snapshot", source)
        self.assertIn('"embedding_check": memory_rag_embedding_check_snapshot()', source)
        self.assertIn("Embedding 自检", source)

    def test_agent_owner_read_includes_aggregate_ops_health(self):
        source = PLUGIN_ENTRY.read_text(encoding="utf-8")
        runtime_source = OWNER_READ_RUNTIME.read_text(encoding="utf-8")

        self.assertIn("agent_ops_health_reply", source)
        self.assertIn('if command == "ops_health":', runtime_source)
        self.assertIn("Agent 聚合诊断", source)
        self.assertIn("视觉/Ollama、MemoryRAG/Embedding", source)

    def test_agent_owner_read_includes_read_only_vision_troubleshoot(self):
        source = PLUGIN_ENTRY.read_text(encoding="utf-8")
        runtime_source = OWNER_READ_RUNTIME.read_text(encoding="utf-8")

        self.assertIn("agent_vision_troubleshoot_reply", source)
        self.assertIn('if command == "vision_troubleshoot":', runtime_source)
        self.assertIn("run_diagnostics_graph(event, DiagnosticsView.VISION)", source)
        self.assertIn("run_diagnostics_graph(event, DiagnosticsView.IMAGE_CACHE)", source)
        self.assertIn("recent_root_graph_chat_observation_lines()[:16]", source)
        self.assertIn("recent_main_agent_observation_lines(limit=5)", source)
        self.assertIn("只读保证：未清理缓存、未修改配置、未写入数据库、未发送额外 QQ 消息。", source)
        self.assertIn("/agent 完整排查图片识别问题", source)

    def test_agent_owner_read_includes_read_only_memory_rag_troubleshoot(self):
        source = PLUGIN_ENTRY.read_text(encoding="utf-8")
        runtime_source = OWNER_READ_RUNTIME.read_text(encoding="utf-8")

        self.assertIn("agent_memory_rag_troubleshoot_reply", source)
        self.assertIn('if command == "memory_rag_troubleshoot":', runtime_source)
        self.assertIn("run_memory_retrieval_graph(event, MemoryRetrievalAction.STATUS)", source)
        self.assertIn("rag_index_detail_lines()", source)
        self.assertIn("memory_rag_troubleshoot_findings", source)
        self.assertIn("RootGraph MemoryRAG 观测", source)
        self.assertIn("只读保证：未重建索引、未写入记忆、未删除文档、未修改配置、未写入数据库、未发送额外 QQ 消息。", source)
        self.assertIn("/agent 完整排查记忆检索问题", source)

    def test_root_graph_observation_includes_structured_error_artifact(self):
        source = PLUGIN_ENTRY.read_text(encoding="utf-8")

        self.assertIn('error_artifact = _artifact_dict(runtime, "error")', source)
        self.assertIn('"error_artifact": error_artifact', source)
        self.assertIn('error_artifact = observation.get("error_artifact", {})', source)
        self.assertIn("source={error_artifact.get('source', '') or '-'}", source)
        self.assertIn("Error message：{error_message}", source)

    def test_root_graph_observation_includes_vision_detail(self):
        source = PLUGIN_ENTRY.read_text(encoding="utf-8")

        self.assertIn("update_runtime_image_context_commit(current_runtime, image_context)", source)
        self.assertIn("update_chat_image_description_commit", source)
        self.assertIn("Vision detail：", source)
        self.assertIn("image_context_url_count", source)
        self.assertIn("vision_low_quality_count", source)
        self.assertIn("vision_num_ctx", source)


if __name__ == "__main__":
    unittest.main()
