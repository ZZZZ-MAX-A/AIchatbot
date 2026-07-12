from __future__ import annotations

import re
import unittest

from pure_ai_chat_loader import REPO_ROOT


class AikeRoleCardContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = REPO_ROOT / "prompts" / "persona-cards" / "aike.md"
        cls.content = cls.path.read_text(encoding="utf-8")

    def test_aike_appearance_and_default_reply_length_are_explicit(self):
        self.assertIn("身高约 155 厘米", self.content)
        self.assertIn("胸围约 B 罩杯", self.content)
        self.assertIn("默认写得稍长一些，使用 2 到 3 句完整回复", self.content)
        self.assertIn("默认回复稍长一些，通常为 2 到 3 句", self.content)

    def test_parenthetical_self_reference_uses_character_name(self):
        self.assertIn("括号内凡指代角色自身", self.content)
        self.assertIn("一律写“爱可”或“爱可的”", self.content)
        parenthetical_descriptions = re.findall(r"（[^）]+）", self.content)
        self.assertGreaterEqual(len(parenthetical_descriptions), 10)
        for description in parenthetical_descriptions:
            with self.subTest(description=description):
                self.assertNotRegex(description, r"我|我的|我们")

    def test_dialogue_examples_include_parenthetical_action_descriptions(self):
        example_replies = [
            line
            for line in self.content.splitlines()
            if line.startswith("爱可：")
        ]
        self.assertGreaterEqual(len(example_replies), 10)
        for reply in example_replies:
            with self.subTest(reply=reply):
                self.assertIn("（爱可", reply)


if __name__ == "__main__":
    unittest.main()
