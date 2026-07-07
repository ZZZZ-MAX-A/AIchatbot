from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ENTRY = REPO_ROOT / "src" / "plugins" / "ai_chat" / "__init__.py"
OWNER_READ_RUNTIME = REPO_ROOT / "src" / "plugins" / "ai_chat" / "owner_read_runtime.py"


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

    def test_main_agent_qq_entry_is_feature_gated_and_read_only(self):
        source = PLUGIN_ENTRY.read_text(encoding="utf-8")

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
        self.assertIn("OwnerAgentContext", source)
        self.assertIn("run_owner_agent_task_command", source)
        self.assertIn("format_owner_agent_task_read", source)
        self.assertIn("execute_owner_agent_task_command", source)
        self.assertIn("create_owner_agent_approval_request", source)
        self.assertIn("OwnerReadRuntime", source)
        self.assertIn("run_owner_read_command", source)
        self.assertIn("owner_read_runtime_from_event", source)
        self.assertIn("/agent 审批演练 <目标>", source)
        self.assertIn("create_read_only_main_agent_runtime_handler", source)
        self.assertIn("RuntimeIntent.MAIN_AGENT", source)
        self.assertNotIn("enable_agent_shell", source)
        self.assertNotIn("enable_agent_local_write", source)

    def test_memory_rag_runner_uses_configured_owner_check(self):
        source = PLUGIN_ENTRY.read_text(encoding="utf-8")

        self.assertIn("is_owner=is_owner(config, event)", source)
        self.assertNotIn("is_owner=is_owner(event)", source)

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
