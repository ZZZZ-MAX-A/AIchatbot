from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .database import DATABASE_PATH


EXTERNAL_READ_TASK_TITLE = "外部只读查询报告"

_PROVIDER_PATTERN = re.compile(r"^Provider：([a-z][a-z0-9_]{0,31})。$")
_COUNT_PATTERNS = {
    "result_count": re.compile(r"^结果数：(\d+)。$"),
    "source_host_count": re.compile(r"^来源主机数：(\d+)。$"),
    "dropped_result_count": re.compile(r"^丢弃结果数：(\d+)。$"),
    "external_request_count": re.compile(r"^外部请求：(\d+)。$"),
}
_STATUS_PATTERN = re.compile(r"^状态类别：(completed|no_results)。$")
_ERROR_PATTERN = re.compile(r"^错误类别：([a-z][a-z0-9_]{0,63})。$")
_FAILED_ERROR_PATTERN = re.compile(
    r"^ExternalReadPolicyError: external_read_report execution failed "
    r"\(([a-z][a-z0-9_]{0,63})\)\.$"
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
    external_request_count: int | None = None
    status_category: str = ""
    error_category: str = ""
    updated_at: str = ""


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


def _snapshot_from_row(row: sqlite3.Row) -> ExternalReadTaskSnapshot:
    fields: dict[str, object] = {}
    result = str(row["result"] or "")
    metadata_lines: list[str] = []
    for line in result.splitlines():
        metadata_lines.extend(
            f"{part.strip()}。"
            for part in line.split("。")
            if part.strip()
        )
    for line in metadata_lines:
        provider_match = _PROVIDER_PATTERN.fullmatch(line)
        if provider_match is not None:
            fields["provider_name"] = provider_match.group(1)
            continue
        status_match = _STATUS_PATTERN.fullmatch(line)
        if status_match is not None:
            fields["status_category"] = status_match.group(1)
            continue
        error_match = _ERROR_PATTERN.fullmatch(line)
        if error_match is not None:
            fields["error_category"] = error_match.group(1)
            continue
        for field_name, pattern in _COUNT_PATTERNS.items():
            matched = pattern.fullmatch(line)
            if matched is not None:
                fields[field_name] = _safe_int(matched.group(1))
                break

    if not fields.get("error_category"):
        failed_match = _FAILED_ERROR_PATTERN.fullmatch(result.strip())
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
        ("外部请求", snapshot.external_request_count),
        ("状态类别", snapshot.status_category),
        ("错误类别", snapshot.error_category),
        ("更新时间", snapshot.updated_at),
    )
    for label, value in optional_lines:
        if value not in {None, ""}:
            lines.append(f"最近{label}：{value}")
    return lines
