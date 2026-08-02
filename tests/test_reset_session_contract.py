import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ENTRY = REPO_ROOT / "src" / "plugins" / "ai_chat" / "__init__.py"


class ResetSessionContractTests(unittest.TestCase):
    def test_reset_reply_accurately_describes_preserved_history_summaries(self):
        source = PLUGIN_ENTRY.read_text(encoding="utf-8")

        self.assertNotIn('matcher.finish("已清空当前会话上下文。")', source)
        self.assertIn("已清除当前会话的近期原始消息和空窗摘要", source)
        self.assertIn("历史会话摘要已保留，并会继续用于后续对话", source)


if __name__ == "__main__":
    unittest.main()
