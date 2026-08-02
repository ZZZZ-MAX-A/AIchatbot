from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .database import DATABASE_PATH, utc_now


EXTERNAL_READ_TASK_TITLE = "外部只读查询报告"

_PROVIDER_PATTERN = re.compile(r"^Provider：([a-z][a-z0-9_]{0,31})。$")
_COUNT_PATTERNS = {
    "result_count": re.compile(r"^结果数：(\d+)。$"),
    "source_host_count": re.compile(r"^来源主机数：(\d+)。$"),
    "dropped_result_count": re.compile(r"^丢弃结果数：(\d+)。$"),
    "provider_candidate_count": re.compile(r"^Provider候选数：(\d+)。$"),
    "official_content_strong_count": re.compile(r"^官方正文强日期数：(\d+)。$"),
    "search_stage_count": re.compile(r"^检索阶段数：(\d+)。$"),
    "official_stage_candidate_count": re.compile(r"^(?:官方|第一)阶段候选数：(\d+)。$"),
    "official_stage_result_count": re.compile(r"^(?:官方|第一)阶段合格数：(\d+)。$"),
    "media_stage_candidate_count": re.compile(r"^(?:媒体|第二)阶段候选数：(\d+)。$"),
    "media_stage_result_count": re.compile(r"^(?:媒体|第二)阶段合格数：(\d+)。$"),
    "dropped_missing_date_count": re.compile(r"^日期缺失丢弃：(\d+)。$"),
    "dropped_outside_window_count": re.compile(r"^窗口外丢弃：(\d+)。$"),
    "dropped_weak_only_count": re.compile(r"^仅弱日期丢弃：(\d+)。$"),
    "dropped_conflicting_date_count": re.compile(r"^日期冲突丢弃：(\d+)。$"),
    "dropped_injection_count": re.compile(r"^注入嫌疑丢弃：(\d+)。$"),
    "dropped_sanitization_count": re.compile(r"^清洗去重丢弃：(\d+)。$"),
    "dropped_source_policy_count": re.compile(r"^来源策略丢弃：(\d+)。$"),
    "external_request_count": re.compile(r"^外部请求：(\d+)。$"),
    "provider_request_count": re.compile(r"^Provider请求：(\d+)。$"),
    "synthesis_request_count": re.compile(r"^综合请求：(\d+)。$"),
}
_STATUS_PATTERN = re.compile(
    r"^状态类别：(completed|no_results|synthesis_fallback)。$"
)
_SYNTHESIS_STATUS_PATTERN = re.compile(
    r"^综合状态：(completed|call_failed|invalid_response|not_configured|"
    r"not_run_no_evidence|not_run_incomplete_evidence)。$"
)
_SYNTHESIS_ERROR_PATTERN = re.compile(
    r"^综合错误：(none|timeout|authentication_failed|rate_limited|"
    r"request_rejected|request_too_large|content_policy_rejected|"
    r"provider_unavailable|connection_failed|"
    r"unexpected_failure|response_contract_invalid)。$"
)
_OWNER_QUALITY_PATTERN = re.compile(
    r"^主人质量：(owner_quality_pending|owner_accepted|owner_rejected|"
    r"not_applicable)。$",
    re.MULTILINE,
)
_PLANNING_MODE_PATTERN = re.compile(r"^规划模式：(main_agent|legacy_fixed)。$")
_SCENE_PATTERN = re.compile(
    r"^业务场景：(general_lookup|official_update|current_status|technical_docs|"
    r"news_summary|recommendation|comparison)。$"
)
_PRIMARY_SOURCE_SCOPE_PATTERN = re.compile(
    r"^第一阶段来源：(official|general|news)。$"
)
_SECONDARY_SOURCE_SCOPE_PATTERN = re.compile(
    r"^第二阶段来源：(none|official|general|news)。$"
)
_SECONDARY_MODE_PATTERN = re.compile(
    r"^第二阶段条件：(none|if_no_results|always)。$"
)
_ERROR_PATTERN = re.compile(r"^错误类别：([a-z][a-z0-9_]{0,63})。$")
_FAILED_SEARCH_STAGE_PATTERN = re.compile(
    r"^失败检索阶段：(official|media_fallback|primary|secondary)。$"
)
_FAILED_ERROR_PATTERN = re.compile(
    r"ExternalReadPolicyError: external_read_report execution failed "
    r"\(([a-z][a-z0-9_]{0,63})\)\."
)
_TASK_STATUSES = frozenset({"pending", "running", "done", "failed", "cancelled"})


@dataclass(frozen=True)
class ExternalReadTaskSnapshot:
    task_id: int
    task_status: str
    provider_name: str = ""
    result_count: int | None = None
    source_host_count: int | None = None
    dropped_result_count: int | None = None
    provider_candidate_count: int | None = None
    official_content_strong_count: int | None = None
    failed_search_stage: str = ""
    search_stage_count: int | None = None
    official_stage_candidate_count: int | None = None
    official_stage_result_count: int | None = None
    media_stage_candidate_count: int | None = None
    media_stage_result_count: int | None = None
    planning_mode: str = ""
    scene: str = ""
    primary_source_scope: str = ""
    secondary_source_scope: str = ""
    secondary_mode: str = ""
    dropped_missing_date_count: int | None = None
    dropped_outside_window_count: int | None = None
    dropped_weak_only_count: int | None = None
    dropped_conflicting_date_count: int | None = None
    dropped_injection_count: int | None = None
    dropped_sanitization_count: int | None = None
    dropped_source_policy_count: int | None = None
    external_request_count: int | None = None
    provider_request_count: int | None = None
    synthesis_request_count: int | None = None
    synthesis_status: str = ""
    synthesis_error_category: str = ""
    owner_quality_status: str = ""
    status_category: str = ""
    error_category: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class ExternalReadQualityReviewCommand:
    accepted: bool
    task_id: int | None


@dataclass(frozen=True)
class ExternalReadQualityReviewResult:
    task_id: int
    status: str
    changed: bool


def parse_external_read_quality_review_command(
    query: str,
) -> ExternalReadQualityReviewCommand | None:
    if not isinstance(query, str):
        return None
    stripped = query.strip()
    for prefix, accepted in (
        ("接受联网结果", True),
        ("拒绝联网结果", False),
    ):
        if stripped == prefix:
            return ExternalReadQualityReviewCommand(accepted=accepted, task_id=None)
        if not stripped.startswith(f"{prefix} "):
            continue
        task_text = stripped[len(prefix):].strip()
        if task_text.startswith("#"):
            task_text = task_text[1:].strip()
        task_id = int(task_text) if task_text.isdecimal() else None
        if task_id is not None and task_id <= 0:
            task_id = None
        return ExternalReadQualityReviewCommand(
            accepted=accepted,
            task_id=task_id,
        )
    return None


def _safe_int(value: str) -> int | None:
    parsed = int(value)
    return parsed if 0 <= parsed <= 1_000_000 else None


def _safe_updated_at(value: object) -> str:
    if not isinstance(value, str) or len(value) > 64:
        return ""
    try:
        return datetime.fromisoformat(value).isoformat(timespec="seconds")
    except ValueError:
        return ""


def _metadata_sentences(result: str) -> list[str]:
    sentences: list[str] = []
    for line in result.splitlines():
        sentences.extend(
            f"{part.strip()}。"
            for part in line.split("。")
            if part.strip()
        )
    return sentences


def _snapshot_from_row(row: sqlite3.Row) -> ExternalReadTaskSnapshot:
    fields: dict[str, object] = {}
    result = str(row["result"] or "")
    for line in _metadata_sentences(result):
        provider_match = _PROVIDER_PATTERN.fullmatch(line)
        if provider_match is not None:
            fields["provider_name"] = provider_match.group(1)
            continue
        status_match = _STATUS_PATTERN.fullmatch(line)
        if status_match is not None:
            fields["status_category"] = status_match.group(1)
            continue
        synthesis_match = _SYNTHESIS_STATUS_PATTERN.fullmatch(line)
        if synthesis_match is not None:
            fields["synthesis_status"] = synthesis_match.group(1)
            continue
        synthesis_error_match = _SYNTHESIS_ERROR_PATTERN.fullmatch(line)
        if synthesis_error_match is not None:
            fields["synthesis_error_category"] = synthesis_error_match.group(1)
            continue
        quality_match = _OWNER_QUALITY_PATTERN.fullmatch(line)
        if quality_match is not None:
            fields["owner_quality_status"] = quality_match.group(1)
            continue
        error_match = _ERROR_PATTERN.fullmatch(line)
        if error_match is not None:
            fields["error_category"] = error_match.group(1)
            continue
        failed_stage_match = _FAILED_SEARCH_STAGE_PATTERN.fullmatch(line)
        if failed_stage_match is not None:
            fields["failed_search_stage"] = failed_stage_match.group(1)
            continue
        for field_name, pattern in (
            ("planning_mode", _PLANNING_MODE_PATTERN),
            ("scene", _SCENE_PATTERN),
            ("primary_source_scope", _PRIMARY_SOURCE_SCOPE_PATTERN),
            ("secondary_source_scope", _SECONDARY_SOURCE_SCOPE_PATTERN),
            ("secondary_mode", _SECONDARY_MODE_PATTERN),
        ):
            matched = pattern.fullmatch(line)
            if matched is not None:
                fields[field_name] = matched.group(1)
                break
        else:
            matched = None
        if matched is not None:
            continue
        for field_name, pattern in _COUNT_PATTERNS.items():
            matched = pattern.fullmatch(line)
            if matched is not None:
                fields[field_name] = _safe_int(matched.group(1))
                break

    if not fields.get("error_category"):
        failed_match = _FAILED_ERROR_PATTERN.search(result)
        if failed_match is not None:
            fields["error_category"] = failed_match.group(1)

    return ExternalReadTaskSnapshot(
        task_id=int(row["id"]),
        task_status=(
            str(row["status"])
            if str(row["status"]) in _TASK_STATUSES
            else "unknown"
        ),
        updated_at=_safe_updated_at(row["updated_at"]),
        **fields,
    )


def latest_external_read_task_snapshot(
    *,
    session_key: str,
    user_id: str,
    database_path: Path = DATABASE_PATH,
) -> ExternalReadTaskSnapshot | None:
    if not database_path.is_file():
        return None
    uri = f"{database_path.resolve().as_uri()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=2)
        connection.row_factory = sqlite3.Row
        try:
            cursor = connection.execute(
                """
                SELECT id, status, result, updated_at
                FROM agent_tasks
                WHERE session_key = ? AND user_id = ? AND title = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (session_key, user_id, EXTERNAL_READ_TASK_TITLE),
            )
            try:
                row = cursor.fetchone()
            finally:
                cursor.close()
        finally:
            connection.close()
    except (OSError, sqlite3.Error):
        return None
    return _snapshot_from_row(row) if row is not None else None


def review_external_read_task_quality(
    *,
    task_id: int,
    session_key: str,
    user_id: str,
    accepted: bool,
    database_path: Path = DATABASE_PATH,
) -> ExternalReadQualityReviewResult:
    if not isinstance(task_id, int) or isinstance(task_id, bool) or task_id <= 0:
        raise ValueError("external read quality review task id is invalid")
    target_status = "owner_accepted" if accepted else "owner_rejected"
    if not database_path.is_file():
        return ExternalReadQualityReviewResult(task_id, "not_found", False)
    try:
        connection = sqlite3.connect(database_path, timeout=2)
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                """
                SELECT id, status, result
                FROM agent_tasks
                WHERE id = ? AND session_key = ? AND user_id = ? AND title = ?
                """,
                (task_id, session_key, user_id, EXTERNAL_READ_TASK_TITLE),
            ).fetchone()
            if row is None:
                return ExternalReadQualityReviewResult(task_id, "not_found", False)
            result = str(row["result"] or "")
            existing_status = ""
            for sentence in _metadata_sentences(result):
                existing = _OWNER_QUALITY_PATTERN.fullmatch(sentence)
                if existing is not None:
                    existing_status = existing.group(1)
                    break
            if existing_status in {"owner_accepted", "owner_rejected"}:
                return ExternalReadQualityReviewResult(
                    task_id,
                    existing_status,
                    False,
                )
            if (
                str(row["status"]) != "done"
                or existing_status != "owner_quality_pending"
            ):
                return ExternalReadQualityReviewResult(task_id, "not_reviewable", False)
            updated_result = result.replace(
                f"主人质量：{existing_status}。",
                f"主人质量：{target_status}。",
                count=1,
            )
            cursor = connection.execute(
                """
                UPDATE agent_tasks
                SET result = ?, updated_at = ?
                WHERE id = ? AND session_key = ? AND user_id = ?
                  AND status = 'done' AND result = ?
                """,
                (
                    updated_result,
                    utc_now(),
                    task_id,
                    session_key,
                    user_id,
                    result,
                ),
            )
            connection.commit()
            changed = cursor.rowcount == 1
        finally:
            connection.close()
    except (OSError, sqlite3.Error):
        return ExternalReadQualityReviewResult(task_id, "unavailable", False)
    return ExternalReadQualityReviewResult(
        task_id,
        target_status if changed else "conflict",
        changed,
    )


def external_read_task_snapshot_lines(
    snapshot: ExternalReadTaskSnapshot | None,
) -> list[str]:
    if snapshot is None:
        return ["最近正式任务：无可用安全元数据"]
    lines = [
        f"最近正式任务：#{snapshot.task_id}",
        f"最近任务状态：{snapshot.task_status}",
    ]
    optional_lines = (
        (" Provider", snapshot.provider_name),
        ("结果数", snapshot.result_count),
        ("来源数", snapshot.source_host_count),
        ("丢弃数", snapshot.dropped_result_count),
        (" Provider 候选数", snapshot.provider_candidate_count),
        ("官方正文强日期数", snapshot.official_content_strong_count),
        ("失败检索阶段", snapshot.failed_search_stage),
        ("检索阶段数", snapshot.search_stage_count),
        ("规划模式", snapshot.planning_mode),
        ("业务场景", snapshot.scene),
        ("第一阶段来源", snapshot.primary_source_scope),
        ("第二阶段来源", snapshot.secondary_source_scope),
        ("第二阶段条件", snapshot.secondary_mode),
        ("第一阶段候选数", snapshot.official_stage_candidate_count),
        ("第一阶段合格数", snapshot.official_stage_result_count),
        ("第二阶段候选数", snapshot.media_stage_candidate_count),
        ("第二阶段合格数", snapshot.media_stage_result_count),
        ("日期缺失丢弃", snapshot.dropped_missing_date_count),
        ("窗口外丢弃", snapshot.dropped_outside_window_count),
        ("仅弱日期丢弃", snapshot.dropped_weak_only_count),
        ("日期冲突丢弃", snapshot.dropped_conflicting_date_count),
        ("注入嫌疑丢弃", snapshot.dropped_injection_count),
        ("清洗去重丢弃", snapshot.dropped_sanitization_count),
        ("来源策略丢弃", snapshot.dropped_source_policy_count),
        ("外部请求", snapshot.external_request_count),
        (" Provider 请求", snapshot.provider_request_count),
        ("综合请求", snapshot.synthesis_request_count),
        ("综合状态", snapshot.synthesis_status),
        ("综合错误", snapshot.synthesis_error_category),
        ("主人质量", snapshot.owner_quality_status),
        ("状态类别", snapshot.status_category),
        ("错误类别", snapshot.error_category),
        ("更新时间", snapshot.updated_at),
    )
    for label, value in optional_lines:
        if value not in {None, ""}:
            lines.append(f"最近{label}：{value}")
    return lines
