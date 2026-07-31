from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from pure_ai_chat_loader import REPO_ROOT


PERSONA_CARD_ROOT = Path("prompts/persona-cards")
ALLOWED_EXACT_PATHS = frozenset(
    {
        "prompts/persona-cards/README.md",
        "prompts/persona-cards/private/.gitkeep",
    }
)


def _is_allowed_public_template(path: str) -> bool:
    candidate = Path(path)
    if candidate.parent.as_posix() != "prompts/persona-cards/public":
        return False
    return candidate.name.endswith((".example.md", ".example.auto-reply.json"))


def _tracked_persona_card_paths(repo_root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "--", PERSONA_CARD_ROOT.as_posix()],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()]


class PersonaCardPrivacyContractTests(unittest.TestCase):
    def test_git_tracks_only_documentation_and_desensitized_examples(self):
        disallowed = [
            path
            for path in _tracked_persona_card_paths(REPO_ROOT)
            if path not in ALLOWED_EXACT_PATHS and not _is_allowed_public_template(path)
        ]
        self.assertEqual(
            disallowed,
            [],
            "Real persona cards and their auto-reply profiles must remain local and untracked.",
        )


if __name__ == "__main__":
    unittest.main()
