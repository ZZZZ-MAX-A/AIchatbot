from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_DOC_INCLUDE_PATTERNS: tuple[str, ...] = (
    "README.md",
    "docs/**/*.md",
    "prompts/base/**/*.json",
    "prompts/persona-cards/public/**/*.md",
)
PROJECT_DOC_EXCLUDED_PARTS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "data",
        "docs-archive",
        "logs",
        "prompts/persona-cards/private",
        "temp_audio",
        "tools",
        "tts-validation",
        "voice-samples",
        "__pycache__",
    }
)
PROJECT_DOC_EXCLUDED_SUFFIXES: tuple[str, ...] = (
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
)


@dataclass(frozen=True)
class ProjectDocChunk:
    source_id: str
    title: str
    content: str
    chunk_index: int
    source_version: str


def markdown_heading_title(line: str) -> str:
    stripped = line.strip()
    if not stripped.startswith("#"):
        return ""
    return stripped.lstrip("#").strip()


def chunk_markdown_document(
    *,
    path: Path,
    text: str,
    root: Path,
    max_chars: int = 1800,
) -> list[ProjectDocChunk]:
    relative = path.relative_to(root).as_posix()
    source_version = str(int(path.stat().st_mtime)) if path.exists() else ""
    chunks: list[ProjectDocChunk] = []
    current_title = relative
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        content = "\n".join(buffer).strip()
        if not content:
            buffer = []
            return
        chunk_index = len(chunks)
        chunks.append(
            ProjectDocChunk(
                source_id=relative,
                title=current_title,
                content=content,
                chunk_index=chunk_index,
                source_version=source_version,
            )
        )
        buffer = []

    for line in text.splitlines():
        heading = markdown_heading_title(line)
        would_exceed = sum(len(item) + 1 for item in buffer) + len(line) > max_chars
        if heading and buffer:
            flush()
            current_title = f"{relative}#{heading}"
        elif would_exceed and buffer:
            flush()
        if heading:
            current_title = f"{relative}#{heading}"
        buffer.append(line)

    flush()
    return chunks


def _relative_parts(path: Path, root: Path) -> tuple[str, ...]:
    return path.relative_to(root).as_posix().split("/")


def should_index_project_document(path: Path, root: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    relative = path.relative_to(root).as_posix()
    if path.name.startswith(".env") or any(part.startswith(".") for part in _relative_parts(path, root)):
        return False
    if relative in {"pyproject.toml"}:
        return False
    if path.suffix.lower() in PROJECT_DOC_EXCLUDED_SUFFIXES:
        return False
    for excluded in PROJECT_DOC_EXCLUDED_PARTS:
        if relative == excluded or relative.startswith(f"{excluded}/"):
            return False
    return True


def iter_project_document_files(root: Path) -> list[Path]:
    root = root.resolve()
    seen: set[Path] = set()
    files: list[Path] = []
    for pattern in PROJECT_DOC_INCLUDE_PATTERNS:
        for path in sorted(root.glob(pattern)):
            if not should_index_project_document(path, root):
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(path)
    return files


def iter_project_markdown_files(root: Path) -> list[Path]:
    return iter_project_document_files(root)
