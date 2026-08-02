from __future__ import annotations

import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PATH = PROJECT_ROOT / "src" / "plugins" / "ai_chat" / "__init__.py"


class ExplicitMainAgentExternalReadQQBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PLUGIN_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    @classmethod
    def function_source(cls, name: str) -> str:
        node = next(
            item
            for item in cls.tree.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == name
        )
        return ast.get_source_segment(cls.source, node) or ""

    def test_ordinary_chat_never_calls_main_agent_or_external_read_preflight(self):
        source = self.function_source("handle_chat")

        self.assertIn("await run_chat_via_root_graph(", source)
        self.assertNotIn("run_owner_autonomous_external_read", source)
        self.assertNotIn("execute_external_read_for_event", source)
        self.assertNotIn("create_main_agent", source)

    def test_no_ordinary_chat_external_read_preflight_function_exists(self):
        function_names = {
            item.name
            for item in self.tree.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        self.assertNotIn("run_owner_autonomous_external_read", function_names)
        self.assertNotIn("create_external_read_main_agent_tool_registry", self.source)

    def test_external_tool_reuses_registered_task_runtime(self):
        source = self.function_source("execute_external_read_for_event")

        self.assertIn("prepare_external_read_command", source)
        self.assertIn("factory.execute_external_read_report", source)
        self.assertIn("format_owner_agent_work_execution", source)

    def test_explicit_main_agent_planner_uses_trusted_temporal_query(self):
        source = self.function_source("run_main_agent_qq_command")

        self.assertIn("rewrite_external_read_temporal_query", source)
        self.assertIn("normalize_main_agent_query(planner_query)", source)
        self.assertIn("trusted_temporal_query = temporal_query", source)
        self.assertIn("trusted_temporal_query=trusted_temporal_query", source)
        self.assertIn("temporal_source_query=query", source)

    def test_external_read_execution_no_longer_blocks_vague_recency(self):
        source = self.function_source("execute_external_read_for_event")

        self.assertNotIn("external_read_time_window_requires_clarification", source)
        self.assertIn("factory.execute_external_read_report", source)

    def test_trusted_window_is_bound_into_the_configured_executor(self):
        factory_source = self.function_source("owner_runtime_factory")
        configured_source = self.function_source(
            "_configured_external_read_report_for_event"
        )

        self.assertIn("trusted_external_read_temporal_query", factory_source)
        self.assertIn("trusted_temporal_query=trusted_external_read_temporal_query", factory_source)
        self.assertIn("trusted_temporal_query=trusted_temporal_query", configured_source)

    def test_external_read_is_registered_only_inside_explicit_main_agent_path(self):
        source = self.function_source("run_main_agent_qq_command")

        self.assertIn("execute_external_read=", source)
        self.assertIn("isinstance(event, PrivateMessageEvent)", source)
        self.assertIn("is_owner(config, event)", source)
        self.assertIn("config.enable_agent_web", source)
        self.assertIn("EXTERNAL_READ_TOOL_NAME", source)


if __name__ == "__main__":
    unittest.main()
