from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
LINYIN_DEEPSEEK_GROUP_STYLE_PATH = (
    PROJECT_ROOT
    / "prompts"
    / "style-examples"
    / "private"
    / "linyin-group-deepseek.md"
)
MAX_STYLE_EXAMPLE_FILE_BYTES = 16_384
MAX_STYLE_EXAMPLE_CHARS = 4_000
_STYLE_EXAMPLE_STATUSES = frozenset(
    {
        "not_applicable",
        "loaded",
        "missing",
        "empty",
        "too_large",
        "unreadable",
    }
)


@dataclass(frozen=True)
class SceneStyleExamples:
    status: str
    content: str = field(default="", repr=False)
    char_count: int = 0


@dataclass(frozen=True)
class SceneActorProfile:
    completion_route: str
    reasoning_effort: str | None
    style_examples: SceneStyleExamples


def load_linyin_deepseek_group_style_examples(
    path: Path | None = None,
) -> SceneStyleExamples:
    style_path = path or LINYIN_DEEPSEEK_GROUP_STYLE_PATH
    try:
        if not style_path.is_file():
            return SceneStyleExamples("missing")
        if style_path.stat().st_size > MAX_STYLE_EXAMPLE_FILE_BYTES:
            return SceneStyleExamples("too_large")
        content = style_path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return SceneStyleExamples("unreadable")
    if not content:
        return SceneStyleExamples("empty")
    if len(content) > MAX_STYLE_EXAMPLE_CHARS:
        return SceneStyleExamples("too_large")
    return SceneStyleExamples("loaded", content, len(content))


def build_scene_actor_profile(
    speaker: str,
    *,
    style_path: Path | None = None,
) -> SceneActorProfile:
    """Select the SceneHub-only route without changing private-chat routing."""

    if str(speaker).strip().lower() == "linyin":
        return SceneActorProfile(
            completion_route="legacy",
            reasoning_effort="low",
            style_examples=load_linyin_deepseek_group_style_examples(style_path),
        )
    return SceneActorProfile(
        completion_route="auto",
        reasoning_effort=None,
        style_examples=SceneStyleExamples("not_applicable"),
    )


def format_scene_style_example_log_fields(
    status: object,
    char_count: object,
) -> str:
    normalized_status = str(status).strip().lower()
    if normalized_status not in _STYLE_EXAMPLE_STATUSES:
        normalized_status = "unreadable"
    try:
        normalized_chars = int(char_count)
    except (TypeError, ValueError):
        normalized_chars = 0
    normalized_chars = max(0, min(normalized_chars, MAX_STYLE_EXAMPLE_CHARS))
    return (
        f"style_examples={normalized_status} "
        f"style_example_chars={normalized_chars}"
    )
