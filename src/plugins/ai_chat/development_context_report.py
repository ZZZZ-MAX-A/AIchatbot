from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


DEVELOPMENT_CONTEXT_REPORT_SOURCE_LIMIT = 4200
DEVELOPMENT_CONTEXT_REPORT_RESPONSE_LIMIT = 2400
DEVELOPMENT_CONTEXT_REPORT_MAX_ITEMS = 4
DEVELOPMENT_CONTEXT_REPORT_ITEM_LIMIT = 240
DEVELOPMENT_CONTEXT_REPORT_SECTION_LIMIT = 80


@dataclass(frozen=True)
class DevelopmentContextReportSections:
    current_stage: str
    completed_items: tuple[str, ...]
    pending_items: tuple[str, ...]
    safety_boundaries: tuple[str, ...]
    recommended_next_steps: tuple[str, ...]
    evidence_limits: tuple[str, ...]


@dataclass(frozen=True)
class DevelopmentContextReportPayload:
    project_result_count: int
    memory_result_count: int
    report_text: str
    summary_mode: str


class DevelopmentContextReportFormatError(ValueError):
    """Raised when a bounded report summary does not match the fixed contract."""


_DEVELOPMENT_CONTEXT_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
        "[已脱敏邮箱]",
    ),
    (re.compile(r"\b1[3-9]\d{9}\b"), "[已脱敏手机号]"),
    (re.compile(r"\b\d{17}[\dXx]\b|\b\d{15}\b"), "[已脱敏证件号]"),
    (re.compile(r"\b\d{13,19}\b"), "[已脱敏长号码]"),
    (re.compile(r"(?i)\b(?:sk-|ak-)[A-Za-z0-9_-]{8,}\b"), "[已脱敏密钥]"),
    (
        re.compile(
            r"(?i)(?:[A-Za-z0-9_]*(?:api[_-]?key|token|password|passwd|secret)"
            r"[A-Za-z0-9_]*)\s*[:=：]\s*\S+"
        ),
        "[已脱敏密钥]",
    ),
    (re.compile(r"(?i)https?://\S+"), "[已脱敏链接]"),
    (
        re.compile(r"(?i)\b[A-Z]:[\\/](?:[^\\/\s]+[\\/])*[^\\/\s]*"),
        "[已省略本地路径]",
    ),
    (
        re.compile(
            r"(?i)\b(?:docs|src|tests|scripts|web|config|logs|data)"
            r"[\\/][^\s，。；：]+"
        ),
        "[已省略仓库路径]",
    ),
    (re.compile(r"(?i)(?<![\w.])\.env(?:\.[A-Za-z0-9_.-]+)?"), "[已省略环境文件]"),
)


def redact_development_context_sensitive_text(text: str) -> str:
    redacted = text
    for pattern, replacement in _DEVELOPMENT_CONTEXT_REDACTIONS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _sanitize_report_source_content(value: object) -> str:
    text = str(value).strip()
    normalized = "\n".join(
        "".join(" " if ord(character) < 32 else character for character in line).rstrip()
        for line in text.splitlines()
    ).strip()
    return redact_development_context_sensitive_text(normalized)


def _normalize_single_line(value: object, *, limit: int) -> str:
    if not isinstance(value, str):
        raise DevelopmentContextReportFormatError("report field must be text")
    without_controls = "".join(
        " " if ord(character) < 32 else character for character in value
    )
    compact = " ".join(without_controls.split())
    if not compact:
        raise DevelopmentContextReportFormatError("report field must be non-empty")
    return compact[:limit].rstrip()


def _parse_items(value: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise DevelopmentContextReportFormatError(f"{field_name} must be a list")
    items = tuple(
        _normalize_single_line(item, limit=DEVELOPMENT_CONTEXT_REPORT_ITEM_LIMIT)
        for item in value[:DEVELOPMENT_CONTEXT_REPORT_MAX_ITEMS]
    )
    if not items:
        raise DevelopmentContextReportFormatError(f"{field_name} must not be empty")
    return items


def parse_development_context_report_json(raw_text: str) -> DevelopmentContextReportSections:
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise DevelopmentContextReportFormatError("report summary must be non-empty")
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise DevelopmentContextReportFormatError("report summary must be JSON") from exc
    if not isinstance(payload, Mapping):
        raise DevelopmentContextReportFormatError("report summary must be an object")

    expected_fields = {
        "current_stage",
        "completed_items",
        "pending_items",
        "safety_boundaries",
        "recommended_next_steps",
        "evidence_limits",
    }
    if set(payload) != expected_fields:
        raise DevelopmentContextReportFormatError("report summary fields do not match contract")

    return DevelopmentContextReportSections(
        current_stage=_normalize_single_line(
            payload["current_stage"],
            limit=DEVELOPMENT_CONTEXT_REPORT_ITEM_LIMIT,
        ),
        completed_items=_parse_items(
            payload["completed_items"],
            field_name="completed_items",
        ),
        pending_items=_parse_items(
            payload["pending_items"],
            field_name="pending_items",
        ),
        safety_boundaries=_parse_items(
            payload["safety_boundaries"],
            field_name="safety_boundaries",
        ),
        recommended_next_steps=_parse_items(
            payload["recommended_next_steps"],
            field_name="recommended_next_steps",
        ),
        evidence_limits=_parse_items(
            payload["evidence_limits"],
            field_name="evidence_limits",
        ),
    )


def _bounded_section_title(raw_title: object) -> str:
    if not isinstance(raw_title, str) or "#" not in raw_title:
        return ""
    heading = raw_title.rsplit("#", 1)[-1]
    try:
        return _normalize_single_line(
            heading,
            limit=DEVELOPMENT_CONTEXT_REPORT_SECTION_LIMIT,
        )
    except DevelopmentContextReportFormatError:
        return ""


def relevant_project_section_titles(project_docs: Sequence[object]) -> tuple[str, ...]:
    headings: list[str] = []
    for result in project_docs:
        document = getattr(result, "document", None)
        heading = _bounded_section_title(getattr(document, "title", ""))
        if not heading or heading in headings:
            continue
        headings.append(heading)
        if len(headings) >= DEVELOPMENT_CONTEXT_REPORT_MAX_ITEMS:
            break
    return tuple(headings)


def build_development_context_report_source(
    *,
    project_docs: Sequence[object],
    memories: Sequence[object],
) -> str:
    """Build bounded LLM-only source text without paths or retrieval metadata."""

    blocks: list[str] = []
    for index, result in enumerate(project_docs, start=1):
        document = getattr(result, "document", None)
        content = _sanitize_report_source_content(getattr(document, "content", ""))
        if not content:
            continue
        heading = _bounded_section_title(getattr(document, "title", ""))
        label = f"项目文档片段 {index}"
        if heading:
            label += f"（章节：{heading}）"
        blocks.append(f"{label}：\n{content}")

    for index, result in enumerate(memories, start=1):
        document = getattr(result, "document", None)
        content = _sanitize_report_source_content(getattr(document, "content", ""))
        if content:
            blocks.append(f"开发侧记忆片段 {index}：\n{content}")

    source = "\n\n".join(blocks).strip()
    return source[:DEVELOPMENT_CONTEXT_REPORT_SOURCE_LIMIT].rstrip()


def fallback_development_context_report_sections(
    *,
    project_result_count: int,
    memory_result_count: int,
    relevant_sections: Sequence[str] = (),
) -> DevelopmentContextReportSections:
    if project_result_count or memory_result_count:
        current_stage = "只读研发上下文检索已完成；受限结构化总结未启用或不可用。"
        completed = (
            f"已召回 {project_result_count} 个项目文档片段和 {memory_result_count} 条开发侧记忆。",
        )
        pending = ("当前回退结果不从原始片段推断具体未完成事项。",)
        next_steps = ("缩小问题范围后重新执行，或查看相关设计章节确认具体状态。",)
    else:
        current_stage = "只读研发上下文检索已完成，但没有召回可用于总结的内容。"
        completed = ("DevContextGraph 已完成本次只读检索。",)
        pending = ("当前没有足够证据判断具体完成项或未完成项。",)
        next_steps = ("先确认 ProjectDocRAG 索引状态，再用更具体的问题重新执行。",)

    evidence = ["未保存或返回原始 RAG 片段、来源路径及异常文本。"]
    if relevant_sections:
        evidence.append(
            "相关章节：" + "、".join(str(item) for item in relevant_sections)
        )
    return DevelopmentContextReportSections(
        current_stage=current_stage,
        completed_items=completed,
        pending_items=pending,
        safety_boundaries=(
            "本任务只读，不执行 shell、文件写入、Web 写操作、自动重试或额外 QQ 发送。",
        ),
        recommended_next_steps=next_steps,
        evidence_limits=tuple(evidence),
    )


def format_development_context_report_sections(
    sections: DevelopmentContextReportSections,
) -> str:
    lines = ["当前阶段：", sections.current_stage]
    groups = (
        ("已完成事项：", sections.completed_items),
        ("未完成事项：", sections.pending_items),
        ("当前安全边界：", sections.safety_boundaries),
        ("推荐下一步：", sections.recommended_next_steps),
        ("证据与限制：", sections.evidence_limits),
    )
    for heading, items in groups:
        lines.extend(["", heading])
        lines.extend(f"- {item}" for item in items)
    return "\n".join(lines).strip()[:DEVELOPMENT_CONTEXT_REPORT_RESPONSE_LIMIT].rstrip()


def combined_results_lists(results: Any) -> tuple[Sequence[object], Sequence[object]]:
    if results is None:
        return (), ()
    project_docs = getattr(results, "project_docs", ())
    memories = getattr(results, "memories", ())
    if not isinstance(project_docs, Sequence) or isinstance(project_docs, (str, bytes)):
        project_docs = ()
    if not isinstance(memories, Sequence) or isinstance(memories, (str, bytes)):
        memories = ()
    return project_docs, memories
