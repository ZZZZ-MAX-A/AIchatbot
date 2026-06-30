from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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


def iter_project_markdown_files(root: Path) -> list[Path]:
    candidates = [root / "README.md"]
    docs_dir = root / "docs"
    if docs_dir.exists():
        candidates.extend(sorted(docs_dir.glob("*.md")))
    return [path for path in candidates if path.exists() and path.is_file()]
