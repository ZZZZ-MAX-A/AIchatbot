"""Check staged Git content (or tracked working files) without printing secrets.

Usage before committing: python scripts/check_repository_privacy.py
Review working files: python scripts/check_repository_privacy.py --tracked-worktree
Only local configuration and files are read; no network or Git writes occur.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import subprocess


KEY_PATTERN = re.compile(
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    rb"|gh[pousr]_[A-Za-z0-9]{30,}"
    rb"|github_pat_[A-Za-z0-9_]{40,}"
    rb"|sk-[A-Za-z0-9_-]{32,}"
)
IDENTIFIER_KEYS = frozenset({
    "BOT_OWNER_QQ", "SHARED_SCENE_GROUP_ID",
    "SHARED_SCENE_AIKE_BOT_ID", "SHARED_SCENE_LINYIN_BOT_ID",
})


def protected_path(path: str) -> bool:
    candidate = PurePosixPath(path)
    if candidate.name == ".env" or (
        candidate.name.endswith(".env") and candidate.name != ".env.example"
    ):
        return True
    if path.startswith(("tmp/", "output/", "backups/", "logs/", "data/")):
        return path not in {"data/.gitkeep", "logs/.gitkeep"}
    if path.startswith("prompts/style-examples/"):
        return True
    if path.startswith("prompts/world-cards/"):
        return path not in {
            "prompts/world-cards/README.md",
            "prompts/world-cards/private/.gitkeep",
        }
    if path.startswith("prompts/persona-cards/"):
        return not (
            path in {
                "prompts/persona-cards/README.md",
                "prompts/persona-cards/private/.gitkeep",
            }
            or (
                candidate.parent.as_posix() == "prompts/persona-cards/public"
                and candidate.name.endswith((".example.md", ".example.auto-reply.json"))
            )
        )
    return False


def local_sensitive_values(repo_root: Path) -> dict[str, bytes]:
    config = repo_root / ".env"
    if not config.is_file():
        return {}
    values = {}
    for line in config.read_text(encoding="utf-8-sig").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if (
            key in IDENTIFIER_KEYS and len(value) >= 5
            or re.search(r"API_KEY|TOKEN|SECRET|PASSWORD", key) and len(value) >= 8
        ):
            values[key] = value.encode("utf-8")
    return values


def private_fingerprints(repo_root: Path) -> tuple[set[bytes], set[bytes]]:
    hashes, fragments = set(), set()
    for directory in ("persona-cards", "world-cards", "style-examples"):
        for path in (repo_root / "prompts" / directory).rglob("*"):
            if not path.is_file() or not protected_path(path.relative_to(repo_root).as_posix()):
                continue
            data = path.read_bytes()
            if data:
                hashes.add(hashlib.sha256(data).digest())
            for line in data.replace(b"\r\n", b"\n").splitlines():
                line = line.strip()
                if len(line.decode("utf-8", errors="replace")) >= 60:
                    fragments.add(line)
    return hashes, fragments


def content_findings(
    path: str,
    data: bytes,
    values: dict[str, bytes],
    hashes: set[bytes],
    fragments: set[bytes],
) -> list[str]:
    reasons = []
    if protected_path(path):
        reasons.append("protected local file")
    if KEY_PATTERN.search(data):
        reasons.append("credential pattern")
    for key, value in values.items():
        pattern = (
            rb"(?<!\d)" + re.escape(value) + rb"(?!\d)"
            if key in IDENTIFIER_KEYS and value.isdigit() else re.escape(value)
        )
        if re.search(pattern, data):
            reasons.append(f"local configuration value: {key}")
    if hashlib.sha256(data).digest() in hashes:
        reasons.append("private file copy")
    elif any(fragment in data.replace(b"\r\n", b"\n") for fragment in fragments):
        reasons.append("private text fragment")
    return reasons


def check_repository(repo_root: Path, *, staged: bool = True) -> list[tuple[str, str]]:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    args = (
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"]
        if staged else ["git", "ls-files", "-z"]
    )
    paths = subprocess.check_output(args, cwd=repo_root, env=env).split(b"\0")
    values = local_sensitive_values(repo_root)
    hashes, fragments = private_fingerprints(repo_root)
    findings = []
    for raw_path in paths:
        if not raw_path:
            continue
        path = raw_path.decode("utf-8")
        if staged:
            # Inspect the index, including force-added ignored files, rather
            # than a possibly sanitized working copy of the same file.
            data = subprocess.check_output(["git", "show", f":{path}"], cwd=repo_root, env=env)
        else:
            file = repo_root / path
            if not file.is_file():
                continue
            data = file.read_bytes()
        findings.extend((path, reason) for reason in content_findings(path, data, values, hashes, fragments))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracked-worktree", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    findings = check_repository(root, staged=not args.tracked_worktree)
    for path, reason in findings:
        print(f"BLOCKED {path}: {reason}")
    if findings:
        print(f"Privacy check failed: {len(findings)} findings. Secret values are omitted.")
        return 1
    print("Privacy check passed (tracked working files)." if args.tracked_worktree else "Privacy check passed (staged changes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
