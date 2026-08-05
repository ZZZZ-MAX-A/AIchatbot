from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module


class WorldCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.module = load_module(
            "src.plugins.ai_chat.world_cards",
            AI_CHAT_ROOT / "world_cards.py",
        )

    def test_aike_and_linyin_load_the_same_private_world_card(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "aike-linyin.md"
            path.write_text("# Shared\nfirst formal meeting", encoding="utf-8")
            mapping = {"aike": path, "linyin": path}
            with patch.object(self.module, "_WORLD_CARD_BY_ROLE_CARD_KEY", mapping):
                aike = self.module.load_world_card_prompt("aike")
                linyin = self.module.load_world_card_prompt("linyin")

        self.assertEqual(aike, linyin)
        self.assertIn("first formal meeting", aike)
        self.assertIn("不得用它改变角色卡的语言风格或私聊表达方式", aike)

    def test_unmapped_persona_does_not_load_another_world_card(self):
        with patch.object(
            self.module,
            "_WORLD_CARD_BY_ROLE_CARD_KEY",
            {"aike": Path("unused.md")},
        ):
            self.assertEqual(self.module.load_world_card_prompt("other"), "")
            self.assertEqual(self.module.load_world_card_prompt(""), "")

    def test_missing_world_card_is_safely_empty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing.md"
            mapping = {"aike": missing, "linyin": missing}
            with patch.object(self.module, "_WORLD_CARD_BY_ROLE_CARD_KEY", mapping):
                self.assertEqual(self.module.load_world_card_prompt("aike"), "")
                self.assertEqual(self.module.load_world_card_prompt("linyin"), "")


if __name__ == "__main__":
    unittest.main()
