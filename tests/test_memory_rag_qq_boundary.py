from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ENTRY = REPO_ROOT / "src" / "plugins" / "ai_chat" / "__init__.py"


class MemoryRagQqBoundaryTests(unittest.TestCase):
    def test_qq_plugin_registers_only_memory_rag_debug_commands(self):
        source = PLUGIN_ENTRY.read_text(encoding="utf-8")

        self.assertIn('on_command("RAG状态"', source)
        self.assertIn('on_command("记忆检索"', source)
        self.assertIn('on_command(\n    "重建记忆索引"', source)
        self.assertNotIn('on_command("项目文档检索"', source)
        self.assertNotIn('on_command("重建项目文档索引"', source)
        self.assertNotIn('on_command("查看召回"', source)

    def test_qq_plugin_does_not_call_project_doc_retrieval(self):
        source = PLUGIN_ENTRY.read_text(encoding="utf-8")

        self.assertIn("from .rag.memory_index import rebuild_memory_rag_index, retrieve_memory", source)
        self.assertNotIn("retrieve_project_docs", source)
        self.assertNotIn("rebuild_project_doc_index", source)
        self.assertNotIn("SOURCE_PROJECT_DOC", source)

    def test_memory_rag_runner_uses_configured_owner_check(self):
        source = PLUGIN_ENTRY.read_text(encoding="utf-8")

        self.assertIn("is_owner=is_owner(config, event)", source)
        self.assertNotIn("is_owner=is_owner(event)", source)


if __name__ == "__main__":
    unittest.main()
