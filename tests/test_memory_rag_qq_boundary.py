from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ENTRY = REPO_ROOT / "src" / "plugins" / "ai_chat" / "__init__.py"


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
        self.assertIn("run_main_agent_task_command", source)
        self.assertIn("parse_agent_task_command(query)", source)
        self.assertIn("cancel_agent_task", source)
        self.assertIn("create_agent_approval_drill_reply", source)
        self.assertIn("/agent 审批演练 <目标>", source)
        self.assertIn("format_agent_task_detail", source)
        self.assertIn("list_agent_approvals", source)
        self.assertIn("format_agent_approval_detail", source)
        self.assertIn("create_read_only_main_agent_runtime_handler", source)
        self.assertIn("RuntimeIntent.MAIN_AGENT", source)
        self.assertNotIn("enable_agent_shell", source)
        self.assertNotIn("enable_agent_local_write", source)

    def test_memory_rag_runner_uses_configured_owner_check(self):
        source = PLUGIN_ENTRY.read_text(encoding="utf-8")

        self.assertIn("is_owner=is_owner(config, event)", source)
        self.assertNotIn("is_owner=is_owner(event)", source)


if __name__ == "__main__":
    unittest.main()
