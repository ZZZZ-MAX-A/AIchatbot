from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

from pure_ai_chat_loader import REPO_ROOT


spec = importlib.util.spec_from_file_location(
    "repository_privacy_check", REPO_ROOT / "scripts/check_repository_privacy.py"
)
privacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(privacy)


class RepositoryPrivacyTests(unittest.TestCase):
    def test_local_directories_and_private_cards_are_blocked(self):
        for path in [
            ".env", "config/runtime.env", "tmp/persona-copy.md", "output/chat.md",
            "data/chatbot.db", "logs/bot.log", "backups/card.md",
            "prompts/persona-cards/public/aike.md",
            "prompts/persona-cards/private/aike.md",
            "prompts/world-cards/private/world.md", "prompts/style-examples/aike.md",
        ]:
            with self.subTest(path=path):
                self.assertTrue(privacy.protected_path(path))
        for path in [
            ".env.example", "config/.env.example", "data/.gitkeep", "logs/.gitkeep",
            "prompts/persona-cards/README.md", "prompts/persona-cards/private/.gitkeep",
            "prompts/persona-cards/public/default.example.md",
            "prompts/world-cards/private/.gitkeep",
        ]:
            with self.subTest(path=path):
                self.assertFalse(privacy.protected_path(path))

    def test_detects_sensitive_content_without_returning_values(self):
        value = b"1234567890"
        findings = privacy.content_findings(
            "docs/example.md", b"owner=" + value,
            {"BOT_OWNER_QQ": value}, set(), set(),
        )
        self.assertTrue(findings)
        self.assertNotIn(value.decode(), repr(findings))
        self.assertEqual(privacy.content_findings(
            "docs/example.md", b"owner=912345678900", {"BOT_OWNER_QQ": value}, set(), set(),
        ), [])
        self.assertTrue(privacy.content_findings(
            "docs/example.md", b"synthetic private passage",
            {}, set(), {b"synthetic private passage"},
        ))

    def test_reads_staged_version_and_blocks_force_added_private_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
            git("init", "-q")
            (root / ".env").write_text("BOT_OWNER_QQ=1234567890\n", encoding="utf-8")
            (root / "example.md").write_text("owner=1234567890", encoding="utf-8")
            git("add", "example.md")
            (root / "example.md").write_text("owner=1000000001", encoding="utf-8")
            self.assertTrue(privacy.check_repository(root))
            self.assertEqual(privacy.check_repository(root, staged=False), [])
            git("add", "example.md")
            self.assertEqual(privacy.check_repository(root), [])
            (root / ".gitignore").write_text("tmp/\n", encoding="utf-8")
            (root / "tmp").mkdir()
            (root / "tmp/private.md").write_text("private", encoding="utf-8")
            git("add", "-f", "tmp/private.md")
            self.assertIn(("tmp/private.md", "protected local file"), privacy.check_repository(root))

    def test_tracked_working_files_are_desensitized(self):
        self.assertEqual(privacy.check_repository(REPO_ROOT, staged=False), [])

    def test_git_ignores_temporary_private_copies(self):
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "tmp/private-card.md", "output/private-export.md"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(result.stdout.splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
