from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from typing import Any

from .database import connect, ensure_database, utc_now
from .graph.tool_registry import (
    ToolContext,
    ToolArgumentError,
    ToolResult,
    ToolRegistry,
    create_default_main_agent_tool_registry,
)


AGENT_TASK_PENDING = "pending"
AGENT_TASK_DONE = "done"
AGENT_TASK_FAILED = "failed"
AGENT_TASK_CANCELLED = "cancelled"
AGENT_TASK_STATUSES = {
    AGENT_TASK_PENDING,
    AGENT_TASK_DONE,
    AGENT_TASK_FAILED,
    AGENT_TASK_CANCELLED,
}
AGENT_TASK_COMMAND_CREATE = "create"
AGENT_TASK_COMMAND_STATUS = "status"
AGENT_TASK_COMMAND_DETAIL = "detail"
AGENT_TASK_COMMAND_CANCEL = "cancel"
AGENT_TASK_COMMAND_APPROVAL_STATUS = "approval_status"
AGENT_TASK_COMMAND_APPROVAL_DETAIL = "approval_detail"
AGENT_TASK_COMMAND_APPROVAL_APPROVE = "approval_approve"
AGENT_TASK_COMMAND_APPROVAL_REJECT = "approval_reject"
AGENT_TASK_COMMAND_APPROVAL_DRILL = "approval_drill"
AGENT_APPROVAL_PENDING = "pending"
AGENT_APPROVAL_APPROVED = "approved"
AGENT_APPROVAL_REJECTED = "rejected"
AGENT_APPROVAL_EXPIRED = "expired"
AGENT_APPROVAL_STATUSES = {
    AGENT_APPROVAL_PENDING,
    AGENT_APPROVAL_APPROVED,
    AGENT_APPROVAL_REJECTED,
    AGENT_APPROVAL_EXPIRED,
}
DRY_RUN_WRITE_FILE_TOOL_NAME = "dry_run_write_file"

_CREATE_PREFIXES = (
    "任务",
    "创建任务",
    "新增任务",
    "添加任务",
    "记录任务",
    "记一个任务",
    "记下一个任务",
    "帮我记一个任务",
    "帮我记录一个任务",
    "帮我新增一个任务",
    "帮我添加一个任务",
    "新增待办",
    "添加待办",
    "记录待办",
    "new task",
    "add task",
    "create task",
    "todo",
    "task",
)
_CREATE_WRAPPED_SUFFIXES = (
    "加入任务",
    "加入待办",
    "加到任务",
    "加到待办",
    "添加到任务",
    "添加到待办",
    "放进任务",
    "放进待办",
    "记成任务",
    "作为任务",
)
_CREATE_SEPARATORS = (" ", "：", ":", "，", ",", "-", "—")
_WRAPPING_QUOTES = (
    ("“", "”"),
    ("‘", "’"),
    ('"', '"'),
    ("'", "'"),
    ("`", "`"),
)


@dataclass(frozen=True)
class AgentTask:
    id: int
    session_key: str
    user_id: str
    title: str
    goal: str
    status: str
    result: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class AgentTaskEvent:
    id: int
    task_id: int
    step_index: int
    kind: str
    tool_name: str
    input_json: str
    output_summary: str
    status: str
    error: str
    created_at: str


@dataclass(frozen=True)
class AgentApproval:
    id: int
    task_id: int
    task_title: str
    tool_name: str
    tool_input_json: str
    risk_level: str
    reason: str
    status: str
    created_at: str
    expires_at: str
    decided_at: str


def parse_agent_task_command(query: str) -> tuple[str, str] | None:
    stripped = query.strip()
    lowered = stripped.lower()
    if not stripped:
        return None
    if lowered in {"审批状态", "审批列表", "approvals", "approval status", "approval list"}:
        return (AGENT_TASK_COMMAND_APPROVAL_STATUS, "")
    if lowered in {"审批演练", "模拟审批", "approval drill"}:
        return (AGENT_TASK_COMMAND_APPROVAL_DRILL, "")
    for prefix in ("审批演练 ", "模拟审批 ", "approval drill "):
        if lowered.startswith(prefix.lower()):
            return (AGENT_TASK_COMMAND_APPROVAL_DRILL, stripped[len(prefix):].strip())
    if lowered in {"审批详情", "查看审批", "approval detail"}:
        return (AGENT_TASK_COMMAND_APPROVAL_DETAIL, "")
    for prefix in ("审批详情 ", "查看审批 ", "approval detail "):
        if lowered.startswith(prefix.lower()):
            return (AGENT_TASK_COMMAND_APPROVAL_DETAIL, stripped[len(prefix):].strip())
    if lowered in {"确认", "确认审批", "approve", "approve approval"}:
        return (AGENT_TASK_COMMAND_APPROVAL_APPROVE, "")
    for prefix in ("确认审批 ", "确认 ", "approve approval ", "approve "):
        if lowered.startswith(prefix.lower()):
            return (AGENT_TASK_COMMAND_APPROVAL_APPROVE, stripped[len(prefix):].strip())
    if lowered in {"拒绝", "拒绝审批", "reject", "reject approval"}:
        return (AGENT_TASK_COMMAND_APPROVAL_REJECT, "")
    for prefix in ("拒绝审批 ", "拒绝 ", "reject approval ", "reject "):
        if lowered.startswith(prefix.lower()):
            return (AGENT_TASK_COMMAND_APPROVAL_REJECT, stripped[len(prefix):].strip())
    if lowered in {"任务状态", "任务列表", "查看任务", "tasks", "task status", "task list"}:
        return (AGENT_TASK_COMMAND_STATUS, "")
    if lowered in {"任务详情", "任务事件", "task detail", "task events"}:
        return (AGENT_TASK_COMMAND_DETAIL, "")
    for prefix in ("任务详情 ", "查看任务 ", "任务事件 ", "task detail ", "task events "):
        if lowered.startswith(prefix.lower()):
            return (AGENT_TASK_COMMAND_DETAIL, stripped[len(prefix):].strip())
    if lowered in {"取消任务", "cancel task"}:
        return (AGENT_TASK_COMMAND_CANCEL, "")
    for prefix in ("取消任务 ", "cancel task "):
        if lowered.startswith(prefix.lower()):
            return (AGENT_TASK_COMMAND_CANCEL, stripped[len(prefix):].strip())
    goal = _parse_create_goal(stripped)
    if goal is not None:
        return (AGENT_TASK_COMMAND_CREATE, goal)
    return None


def _parse_create_goal(stripped: str) -> str | None:
    lowered = stripped.lower()
    for prefix in _CREATE_PREFIXES:
        prefix_lowered = prefix.lower()
        if lowered == prefix_lowered:
            return ""
        if not lowered.startswith(prefix_lowered):
            continue
        rest = stripped[len(prefix):]
        if rest[:1] not in _CREATE_SEPARATORS:
            continue
        return _clean_task_goal(rest)

    if stripped.startswith("把"):
        body = stripped[1:].strip()
        lowered_body = body.lower()
        for suffix in _CREATE_WRAPPED_SUFFIXES:
            if lowered_body.endswith(suffix.lower()):
                goal = body[: -len(suffix)].strip()
                if goal.endswith("先"):
                    goal = goal[:-1].strip()
                return _clean_task_goal(goal)
    return None


def _clean_task_goal(value: str) -> str:
    cleaned = value.strip()
    while cleaned[:1] in _CREATE_SEPARATORS:
        cleaned = cleaned[1:].strip()
    for left, right in _WRAPPING_QUOTES:
        if cleaned.startswith(left) and cleaned.endswith(right) and len(cleaned) >= 2:
            cleaned = cleaned[len(left): -len(right)].strip()
            break
    return cleaned


def parse_agent_task_id(value: str) -> int | None:
    stripped = value.strip()
    if stripped.startswith("#"):
        stripped = stripped[1:].strip()
    if not stripped.isdecimal():
        return None
    task_id = int(stripped)
    return task_id if task_id > 0 else None


def is_latest_agent_reference(value: str) -> bool:
    return value.strip().lower() in {"最新", "最近", "最后", "last", "latest", "newest"}


def _task_from_row(row: Any) -> AgentTask:
    return AgentTask(
        id=int(row["id"]),
        session_key=str(row["session_key"]),
        user_id=str(row["user_id"]),
        title=str(row["title"]),
        goal=str(row["goal"]),
        status=str(row["status"]),
        result=str(row["result"] or ""),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _event_from_row(row: Any) -> AgentTaskEvent:
    return AgentTaskEvent(
        id=int(row["id"]),
        task_id=int(row["task_id"]),
        step_index=int(row["step_index"]),
        kind=str(row["kind"]),
        tool_name=str(row["tool_name"] or ""),
        input_json=str(row["input_json"] or ""),
        output_summary=str(row["output_summary"] or ""),
        status=str(row["status"]),
        error=str(row["error"] or ""),
        created_at=str(row["created_at"]),
    )


def _approval_from_row(row: Any) -> AgentApproval:
    return AgentApproval(
        id=int(row["id"]),
        task_id=int(row["task_id"]),
        task_title=str(row["task_title"] or ""),
        tool_name=str(row["tool_name"]),
        tool_input_json=str(row["tool_input_json"]),
        risk_level=str(row["risk_level"]),
        reason=str(row["reason"]),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        expires_at=str(row["expires_at"] or ""),
        decided_at=str(row["decided_at"] or ""),
    )


def make_agent_task_title(goal: str, *, limit: int = 32) -> str:
    compact = " ".join(goal.strip().split())
    if not compact:
        return "未命名任务"
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def create_agent_task(
    *,
    session_key: str,
    user_id: str,
    goal: str,
    title: str | None = None,
) -> int:
    stripped_goal = goal.strip()
    if not stripped_goal:
        raise ValueError("agent task goal must be non-empty")

    ensure_database()
    now = utc_now()
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO agent_tasks (
                session_key,
                user_id,
                title,
                goal,
                status,
                result,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_key,
                user_id,
                (title or make_agent_task_title(stripped_goal)).strip(),
                stripped_goal,
                AGENT_TASK_PENDING,
                None,
                now,
                now,
            ),
        )
        task_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO agent_task_events (
                task_id,
                step_index,
                kind,
                tool_name,
                input_json,
                output_summary,
                status,
                error,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                0,
                "created",
                None,
                None,
                "任务已创建，等待后续审批和执行链路。",
                AGENT_TASK_PENDING,
                None,
                now,
            ),
        )
        return task_id


def get_agent_task(
    task_id: int,
    *,
    session_key: str | None = None,
    user_id: str | None = None,
) -> AgentTask | None:
    ensure_database()
    clauses = ["id = ?"]
    params: list[object] = [task_id]
    if session_key:
        clauses.append("session_key = ?")
        params.append(session_key)
    if user_id:
        clauses.append("user_id = ?")
        params.append(user_id)
    with connect() as connection:
        row = connection.execute(
            f"""
            SELECT id, session_key, user_id, title, goal, status, result, created_at, updated_at
            FROM agent_tasks
            WHERE {' AND '.join(clauses)}
            """,
            tuple(params),
        ).fetchone()
    return _task_from_row(row) if row else None


def list_agent_tasks(
    *,
    session_key: str | None = None,
    user_id: str | None = None,
    status: str | None = None,
    limit: int = 5,
) -> list[AgentTask]:
    ensure_database()
    clauses: list[str] = []
    params: list[object] = []
    if session_key:
        clauses.append("session_key = ?")
        params.append(session_key)
    if user_id:
        clauses.append("user_id = ?")
        params.append(user_id)
    if status:
        normalized_status = status.strip().lower()
        if normalized_status not in AGENT_TASK_STATUSES:
            raise ValueError(f"unsupported agent task status: {status}")
        clauses.append("status = ?")
        params.append(normalized_status)
    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, limit))

    with connect() as connection:
        rows = connection.execute(
            f"""
            SELECT id, session_key, user_id, title, goal, status, result, created_at, updated_at
            FROM agent_tasks
            {where_clause}
            ORDER BY id DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
    return [_task_from_row(row) for row in rows]


def list_agent_task_events(task_id: int, *, limit: int = 10) -> list[AgentTaskEvent]:
    ensure_database()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, task_id, step_index, kind, tool_name, input_json,
                   output_summary, status, error, created_at
            FROM agent_task_events
            WHERE task_id = ?
            ORDER BY step_index ASC, id ASC
            LIMIT ?
            """,
            (task_id, max(1, limit)),
        ).fetchall()
    return [_event_from_row(row) for row in rows]


def create_agent_approval(
    *,
    task_id: int,
    tool_name: str,
    tool_input_json: str,
    risk_level: str,
    reason: str,
    expires_at: str | None = None,
) -> int:
    ensure_database()
    now = utc_now()
    stripped_tool_name = tool_name.strip()
    stripped_tool_input_json = tool_input_json.strip()
    stripped_risk_level = risk_level.strip()
    stripped_reason = reason.strip()
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO agent_approvals (
                task_id,
                tool_name,
                tool_input_json,
                risk_level,
                reason,
                status,
                created_at,
                expires_at,
                decided_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                stripped_tool_name,
                stripped_tool_input_json,
                stripped_risk_level,
                stripped_reason,
                AGENT_APPROVAL_PENDING,
                now,
                expires_at,
                None,
            ),
        )
        approval_id = int(cursor.lastrowid)
        connection.execute(
            """
            UPDATE agent_tasks
            SET updated_at = ?
            WHERE id = ?
            """,
            (now, task_id),
        )
        step_row = connection.execute(
            """
            SELECT COALESCE(MAX(step_index), -1) + 1 AS next_step
            FROM agent_task_events
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()
        next_step = int(step_row["next_step"])
        event_input_json = json.dumps(
            {
                "approval_id": approval_id,
                "tool_input": stripped_tool_input_json,
                "risk_level": stripped_risk_level,
                "reason": stripped_reason,
            },
            ensure_ascii=False,
        )
        connection.execute(
            """
            INSERT INTO agent_task_events (
                task_id,
                step_index,
                kind,
                tool_name,
                input_json,
                output_summary,
                status,
                error,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                next_step,
                "approval_requested",
                stripped_tool_name,
                event_input_json,
                f"Agent 请求审批 #{approval_id}，等待主人确认；确认后仅已注册且启用审批恢复的工具会受控恢复。",
                AGENT_TASK_PENDING,
                None,
                now,
            ),
        )
        return approval_id


def get_agent_approval(
    approval_id: int,
    *,
    session_key: str | None = None,
    user_id: str | None = None,
) -> AgentApproval | None:
    ensure_database()
    clauses = ["a.id = ?"]
    params: list[object] = [approval_id]
    if session_key:
        clauses.append("t.session_key = ?")
        params.append(session_key)
    if user_id:
        clauses.append("t.user_id = ?")
        params.append(user_id)
    with connect() as connection:
        row = connection.execute(
            f"""
            SELECT a.id, a.task_id, t.title AS task_title, a.tool_name,
                   a.tool_input_json, a.risk_level, a.reason, a.status,
                   a.created_at, a.expires_at, a.decided_at
            FROM agent_approvals AS a
            JOIN agent_tasks AS t ON t.id = a.task_id
            WHERE {' AND '.join(clauses)}
            """,
            tuple(params),
        ).fetchone()
    return _approval_from_row(row) if row else None


def list_agent_approvals(
    *,
    session_key: str | None = None,
    user_id: str | None = None,
    status: str | None = None,
    limit: int = 5,
) -> list[AgentApproval]:
    ensure_database()
    clauses: list[str] = []
    params: list[object] = []
    if session_key:
        clauses.append("t.session_key = ?")
        params.append(session_key)
    if user_id:
        clauses.append("t.user_id = ?")
        params.append(user_id)
    if status:
        normalized_status = status.strip().lower()
        if normalized_status not in AGENT_APPROVAL_STATUSES:
            raise ValueError(f"unsupported agent approval status: {status}")
        clauses.append("a.status = ?")
        params.append(normalized_status)
    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, limit))

    with connect() as connection:
        rows = connection.execute(
            f"""
            SELECT a.id, a.task_id, t.title AS task_title, a.tool_name,
                   a.tool_input_json, a.risk_level, a.reason, a.status,
                   a.created_at, a.expires_at, a.decided_at
            FROM agent_approvals AS a
            JOIN agent_tasks AS t ON t.id = a.task_id
            {where_clause}
            ORDER BY a.id DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
    return [_approval_from_row(row) for row in rows]


def decide_agent_approval(
    *,
    approval_id: int,
    session_key: str,
    user_id: str,
    approved: bool,
) -> tuple[AgentApproval | None, bool]:
    ensure_database()
    now = utc_now()
    next_status = AGENT_APPROVAL_APPROVED if approved else AGENT_APPROVAL_REJECTED
    event_kind = "approval_approved" if approved else "approval_rejected"
    decision_text = "确认" if approved else "拒绝"

    with connect() as connection:
        row = connection.execute(
            """
            SELECT a.id, a.task_id, t.title AS task_title, a.tool_name,
                   a.tool_input_json, a.risk_level, a.reason, a.status,
                   a.created_at, a.expires_at, a.decided_at
            FROM agent_approvals AS a
            JOIN agent_tasks AS t ON t.id = a.task_id
            WHERE a.id = ? AND t.session_key = ? AND t.user_id = ?
            """,
            (approval_id, session_key, user_id),
        ).fetchone()
        if row is None:
            return None, False

        approval = _approval_from_row(row)
        if approval.status != AGENT_APPROVAL_PENDING:
            return approval, False

        connection.execute(
            """
            UPDATE agent_approvals
            SET status = ?, decided_at = ?
            WHERE id = ?
            """,
            (next_status, now, approval_id),
        )
        connection.execute(
            """
            UPDATE agent_tasks
            SET updated_at = ?
            WHERE id = ?
            """,
            (now, approval.task_id),
        )
        step_row = connection.execute(
            """
            SELECT COALESCE(MAX(step_index), -1) + 1 AS next_step
            FROM agent_task_events
            WHERE task_id = ?
            """,
            (approval.task_id,),
        ).fetchone()
        next_step = int(step_row["next_step"])
        event_input_json = json.dumps(
            {
                "approval_id": approval.id,
                "approval_status": next_status,
                "tool_input": approval.tool_input_json,
            },
            ensure_ascii=False,
        )
        connection.execute(
            """
            INSERT INTO agent_task_events (
                task_id,
                step_index,
                kind,
                tool_name,
                input_json,
                output_summary,
                status,
                error,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                approval.task_id,
                next_step,
                event_kind,
                approval.tool_name,
                event_input_json,
                f"主人{decision_text}审批 #{approval.id}；仅已注册且启用审批恢复的工具会受控恢复。",
                AGENT_TASK_PENDING,
                None,
                now,
            ),
        )

    updated = get_agent_approval(
        approval_id,
        session_key=session_key,
        user_id=user_id,
    )
    return updated, True


def resume_agent_approval(
    *,
    approval_id: int,
    session_key: str,
    user_id: str,
    tool_registry: ToolRegistry | None = None,
) -> tuple[AgentApproval | None, bool, str]:
    approval = get_agent_approval(
        approval_id,
        session_key=session_key,
        user_id=user_id,
    )
    if approval is None:
        return None, False, "Agent approval was not found in the current session."
    if approval.status != AGENT_APPROVAL_APPROVED:
        return approval, False, "Agent approval is not approved; resume skipped."
    registry = tool_registry or create_default_main_agent_tool_registry(
        include_dry_run_tools=True
    )
    try:
        spec = registry.require(approval.tool_name)
    except ToolArgumentError as exc:
        return approval, False, f"Agent approval tool is not registered: {exc}"
    if not spec.approval_resume_enabled:
        return approval, False, (
            f"Agent approval #{approval.id} uses {approval.tool_name}; "
            "this tool is not enabled for approval resume."
        )

    ensure_database()
    with connect() as connection:
        if _has_agent_task_event(
            connection,
            task_id=approval.task_id,
            kind="tool_resume_finished",
            tool_name=approval.tool_name,
            approval_id=approval.id,
        ):
            return approval, False, (
                f"Agent approval #{approval.id} approval resume was already completed."
            )

        now = utc_now()
        started_step = _next_agent_task_step(connection, approval.task_id)
        resume_arguments = _approval_tool_arguments_for_resume(approval, registry)
        started_input_json = json.dumps(
            {
                "approval_id": approval.id,
                "tool_arguments": resume_arguments,
            },
            ensure_ascii=False,
        )
        _insert_agent_task_event(
            connection,
            task_id=approval.task_id,
            step_index=started_step,
            kind="tool_resume_started",
            tool_name=approval.tool_name,
            input_json=started_input_json,
            output_summary=f"Starting approval resume for approval #{approval.id}.",
            status=AGENT_TASK_PENDING,
            error=None,
            created_at=now,
        )

        try:
            tool_result = _execute_registered_resume_tool(
                registry,
                approval,
                resume_arguments,
                session_key=session_key,
                user_id=user_id,
            )
        except Exception as exc:
            failed_step = _next_agent_task_step(connection, approval.task_id)
            _insert_agent_task_event(
                connection,
                task_id=approval.task_id,
                step_index=failed_step,
                kind="tool_resume_failed",
                tool_name=approval.tool_name,
                input_json=started_input_json,
                output_summary="Approval resume failed.",
                status=AGENT_TASK_FAILED,
                error=str(exc),
                created_at=utc_now(),
            )
            connection.execute(
                """
                UPDATE agent_tasks
                SET status = ?, result = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    AGENT_TASK_FAILED,
                    f"Approval resume failed: {exc}",
                    utc_now(),
                    approval.task_id,
                ),
            )
            return approval, False, f"Approval resume failed: {exc}"

        finished_step = _next_agent_task_step(connection, approval.task_id)
        result_text = tool_result.text.strip()
        result_metadata = dict(tool_result.metadata)
        finished_input_json = json.dumps(
            {
                "approval_id": approval.id,
                "tool_arguments": resume_arguments,
                "tool_result_metadata": result_metadata,
            },
            ensure_ascii=False,
        )
        _insert_agent_task_event(
            connection,
            task_id=approval.task_id,
            step_index=finished_step,
            kind="tool_resume_finished",
            tool_name=approval.tool_name,
            input_json=finished_input_json,
            output_summary=result_text,
            status=AGENT_TASK_DONE,
            error=None,
            created_at=utc_now(),
        )
        connection.execute(
            """
            UPDATE agent_tasks
            SET status = ?, result = ?, updated_at = ?
            WHERE id = ?
            """,
            (AGENT_TASK_DONE, result_text, utc_now(), approval.task_id),
        )
        return approval, True, format_agent_approval_dry_run_resume(approval, result_text)


def resume_agent_approval_dry_run(
    *,
    approval_id: int,
    session_key: str,
    user_id: str,
) -> tuple[AgentApproval | None, bool, str]:
    return resume_agent_approval(
        approval_id=approval_id,
        session_key=session_key,
        user_id=user_id,
    )


def _approval_tool_arguments_for_resume(
    approval: AgentApproval,
    registry: ToolRegistry,
) -> dict[str, Any]:
    try:
        payload = json.loads(approval.tool_input_json)
    except json.JSONDecodeError as exc:
        raise ValueError("approval tool_input_json must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("approval tool_input_json must be a JSON object")

    if approval.tool_name != DRY_RUN_WRITE_FILE_TOOL_NAME:
        return registry.validate_arguments(approval.tool_name, dict(payload))

    path_value = payload.get("path") or "docs/version-runlog.md"
    summary_value = payload.get("content_summary") or payload.get("goal") or approval.reason
    path = str(path_value).strip()
    content_summary = str(summary_value).strip()
    if not path:
        raise ValueError("dry-run approval requires a non-empty path")
    if not content_summary:
        raise ValueError("dry-run approval requires a non-empty content_summary")
    return registry.validate_arguments(
        approval.tool_name,
        {"path": path, "content_summary": content_summary},
    )


def _execute_registered_resume_tool(
    registry: ToolRegistry,
    approval: AgentApproval,
    arguments: dict[str, Any],
    *,
    session_key: str,
    user_id: str,
) -> ToolResult:
    spec = registry.require(approval.tool_name)
    validated = registry.validate_arguments(approval.tool_name, dict(arguments))
    if spec.executor is None:
        raise RuntimeError(f"tool has no executor: {approval.tool_name}")
    value = spec.executor(
        validated,
        ToolContext(
            query=approval.reason,
            is_owner=True,
            is_group=False,
            metadata={
                "approval_id": approval.id,
                "task_id": approval.task_id,
                "session_key": session_key,
                "user_id": user_id,
                "resume_mode": "approval_resume",
                "resume_tool_name": approval.tool_name,
            },
        ),
    )
    if inspect.isawaitable(value):
        raise RuntimeError("async approval resume tools are not supported yet")
    if isinstance(value, ToolResult):
        return value
    return ToolResult(text=str(value))


def _next_agent_task_step(connection: Any, task_id: int) -> int:
    step_row = connection.execute(
        """
        SELECT COALESCE(MAX(step_index), -1) + 1 AS next_step
        FROM agent_task_events
        WHERE task_id = ?
        """,
        (task_id,),
    ).fetchone()
    return int(step_row["next_step"])


def _insert_agent_task_event(
    connection: Any,
    *,
    task_id: int,
    step_index: int,
    kind: str,
    tool_name: str | None,
    input_json: str | None,
    output_summary: str,
    status: str,
    error: str | None,
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO agent_task_events (
            task_id,
            step_index,
            kind,
            tool_name,
            input_json,
            output_summary,
            status,
            error,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            step_index,
            kind,
            tool_name,
            input_json,
            output_summary,
            status,
            error,
            created_at,
        ),
    )


def _has_agent_task_event(
    connection: Any,
    *,
    task_id: int,
    kind: str,
    tool_name: str,
    approval_id: int,
) -> bool:
    rows = connection.execute(
        """
        SELECT input_json
        FROM agent_task_events
        WHERE task_id = ? AND kind = ? AND tool_name = ?
        """,
        (task_id, kind, tool_name),
    ).fetchall()
    for row in rows:
        try:
            payload = json.loads(str(row["input_json"] or "{}"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("approval_id") == approval_id:
            return True
    return False


def cancel_agent_task(
    *,
    task_id: int,
    session_key: str,
    user_id: str,
) -> tuple[AgentTask | None, bool]:
    ensure_database()
    now = utc_now()
    with connect() as connection:
        row = connection.execute(
            """
            SELECT id, session_key, user_id, title, goal, status, result, created_at, updated_at
            FROM agent_tasks
            WHERE id = ? AND session_key = ? AND user_id = ?
            """,
            (task_id, session_key, user_id),
        ).fetchone()
        if row is None:
            return None, False

        task = _task_from_row(row)
        if task.status != AGENT_TASK_PENDING:
            return task, False

        connection.execute(
            """
            UPDATE agent_tasks
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (AGENT_TASK_CANCELLED, now, task_id),
        )
        step_row = connection.execute(
            """
            SELECT COALESCE(MAX(step_index), -1) + 1 AS next_step
            FROM agent_task_events
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()
        next_step = int(step_row["next_step"])
        connection.execute(
            """
            INSERT INTO agent_task_events (
                task_id,
                step_index,
                kind,
                tool_name,
                input_json,
                output_summary,
                status,
                error,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                next_step,
                "cancelled",
                None,
                None,
                "主人取消任务；未执行任何工具。",
                AGENT_TASK_CANCELLED,
                None,
                now,
            ),
        )

    task = get_agent_task(task_id, session_key=session_key, user_id=user_id)
    return task, True


def agent_task_status_label(status: str) -> str:
    labels = {
        AGENT_TASK_PENDING: "待处理",
        AGENT_TASK_DONE: "已完成",
        AGENT_TASK_FAILED: "失败",
        AGENT_TASK_CANCELLED: "已取消",
    }
    return labels.get(status, status)


def agent_approval_status_label(status: str) -> str:
    labels = {
        AGENT_APPROVAL_PENDING: "待审批",
        AGENT_APPROVAL_APPROVED: "已确认",
        AGENT_APPROVAL_REJECTED: "已拒绝",
        AGENT_APPROVAL_EXPIRED: "已过期",
    }
    return labels.get(status, status)


def _shorten_text(value: str, *, limit: int = 240) -> str:
    compact = " ".join(value.strip().split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def format_agent_task_created(task: AgentTask) -> str:
    return "\n".join(
        [
            f"已创建只读 Agent 任务 #{task.id}：{task.title}",
            f"状态：{agent_task_status_label(task.status)}",
            "当前版本只允许已注册且启用审批恢复的工具在确认后受控恢复；不执行任意 shell、真实写文件或数据库写入。",
            "后续需要审批流和执行边界后，才会进入任务执行阶段。",
        ]
    )


def format_agent_approval_dry_run_resume(approval: AgentApproval, result_text: str) -> str:
    if approval.tool_name != DRY_RUN_WRITE_FILE_TOOL_NAME:
        return "\n".join(
            [
                f"Approval resume completed for Agent approval #{approval.id}.",
                f"Task ID: #{approval.task_id}",
                f"Tool: {approval.tool_name}",
                "",
                result_text.strip(),
            ]
        ).strip()
    return "\n".join(
        [
            f"Dry-run resume completed for Agent approval #{approval.id}.",
            f"Task ID: #{approval.task_id}",
            f"Tool: {approval.tool_name}",
            "Side effect: none",
            "",
            result_text.strip(),
        ]
    ).strip()


def format_agent_task_cancelled(task: AgentTask, *, changed: bool) -> str:
    if changed:
        return "\n".join(
            [
                f"已取消 Agent 任务 #{task.id}：{task.title}",
                "当前版本只允许已注册且启用审批恢复的工具在确认后受控恢复；不执行任意 shell、真实写文件或数据库写入。",
            ]
        )
    return "\n".join(
        [
            f"Agent 任务 #{task.id} 当前状态：{agent_task_status_label(task.status)}",
            "只有待处理任务可以取消。",
        ]
    )


def format_agent_task_detail(task: AgentTask, events: list[AgentTaskEvent]) -> str:
    lines = [
        f"Agent 任务 #{task.id}：{task.title}",
        f"状态：{agent_task_status_label(task.status)}",
        f"目标：{task.goal}",
        f"创建：{task.created_at}",
        f"更新：{task.updated_at}",
    ]
    if task.result:
        lines.append(f"结果：{task.result}")
    lines.append("")
    lines.append("事件：")
    if events:
        for event in events:
            summary = event.output_summary or event.kind
            lines.append(
                f"- {event.step_index}. {event.kind} [{agent_task_status_label(event.status)}] {summary}"
            )
    else:
        lines.append("- 暂无事件。")
    lines.append("")
    lines.append("当前版本只允许已注册且启用审批恢复的工具在确认后受控恢复；不执行任意 shell、真实写文件或数据库写入。")
    return "\n".join(lines)


def format_agent_task_list(tasks: list[AgentTask]) -> str:
    if not tasks:
        return "Agent 任务状态：\n暂无任务。"
    lines = ["Agent 任务状态："]
    for task in tasks:
        lines.append(f"任务ID：#{task.id} [{agent_task_status_label(task.status)}] {task.title}")
    lines.append("")
    lines.append("可用 /agent 任务详情 最新 查看最近任务。")
    lines.append("当前版本只允许已注册且启用审批恢复的工具在确认后受控恢复；不执行任意 shell、真实写文件或数据库写入。")
    return "\n".join(lines)


def format_agent_approval_list(approvals: list[AgentApproval]) -> str:
    if not approvals:
        return "Agent 审批状态：\n暂无待查看审批。"
    lines = ["Agent 审批状态："]
    for approval in approvals:
        lines.append(
            f"审批ID：#{approval.id} [{agent_approval_status_label(approval.status)}] "
            f"任务ID：#{approval.task_id} {approval.tool_name} / {approval.risk_level}"
        )
    lines.append("")
    lines.append("可用 /agent 审批详情 最新、/agent 确认 最新 或 /agent 拒绝 最新 操作最近审批。")
    lines.append("当前版本仅允许已注册且启用审批恢复的工具在确认后受控恢复。")
    return "\n".join(lines)


def format_agent_approval_detail(approval: AgentApproval) -> str:
    lines = [
        f"Agent 审批 #{approval.id}",
        f"审批ID：#{approval.id}",
        f"状态：{agent_approval_status_label(approval.status)}",
        f"任务ID：#{approval.task_id}",
        f"任务：{approval.task_title}",
        f"工具：{approval.tool_name}",
        f"风险：{approval.risk_level}",
        f"原因：{approval.reason}",
        f"输入摘要：{_shorten_text(approval.tool_input_json)}",
        f"创建：{approval.created_at}",
    ]
    if approval.expires_at:
        lines.append(f"过期：{approval.expires_at}")
    if approval.decided_at:
        lines.append(f"决定：{approval.decided_at}")
    lines.append("")
    lines.append("当前版本仅允许已注册且启用审批恢复的工具在确认后受控恢复。")
    return "\n".join(lines)


def format_agent_approval_requested(approval: AgentApproval) -> str:
    return "\n".join(
        [
            f"Agent 请求审批 #{approval.id}",
            f"审批ID：#{approval.id}",
            f"任务ID：#{approval.task_id}",
            f"任务：{approval.task_title}",
            f"工具：{approval.tool_name}",
            f"风险：{approval.risk_level}",
            f"原因：{approval.reason}",
            f"输入摘要：{_shorten_text(approval.tool_input_json)}",
            "",
            "回复：",
            f"/agent 确认 {approval.id}",
            f"/agent 拒绝 {approval.id}",
            "也可以直接回复：/agent 确认 最新 或 /agent 拒绝 最新",
            "",
            "当前版本确认后仅已注册且启用审批恢复的工具会受控恢复。",
        ]
    )


def create_agent_approval_request_reply(
    *,
    task_id: int,
    session_key: str,
    user_id: str,
    tool_name: str,
    tool_input_json: str,
    risk_level: str,
    reason: str,
    expires_at: str | None = None,
) -> str:
    approval_id = create_agent_approval(
        task_id=task_id,
        tool_name=tool_name,
        tool_input_json=tool_input_json,
        risk_level=risk_level,
        reason=reason,
        expires_at=expires_at,
    )
    approval = get_agent_approval(
        approval_id,
        session_key=session_key,
        user_id=user_id,
    )
    if approval is None:
        raise RuntimeError(f"created agent approval #{approval_id} was not found")
    return format_agent_approval_requested(approval)


def create_agent_approval_drill_reply(
    *,
    session_key: str,
    user_id: str,
    goal: str,
) -> str:
    stripped_goal = goal.strip()
    if not stripped_goal:
        raise ValueError("agent approval drill goal must be non-empty")

    task_id = create_agent_task(
        session_key=session_key,
        user_id=user_id,
        goal=f"审批演练：{stripped_goal}",
        title=make_agent_task_title(f"审批演练：{stripped_goal}"),
    )
    tool_input_json = json.dumps(
        {
            "dry_run": True,
            "goal": stripped_goal,
            "path": "docs/version-runlog.md",
            "content_summary": stripped_goal,
            "would_write": False,
            "note": "Route B approval drill only; no file, shell, database, or QQ side effect.",
        },
        ensure_ascii=False,
    )
    approval_reply = create_agent_approval_request_reply(
        task_id=task_id,
        session_key=session_key,
        user_id=user_id,
        tool_name="dry_run_write_file",
        tool_input_json=tool_input_json,
        risk_level="write_local",
        reason="Route B 审批演练：模拟本地写入审批，不执行任何写入。",
    )
    return "\n".join(
        [
            f"已创建 Route B 审批演练任务 #{task_id}。",
            f"任务ID：#{task_id}",
            "这是 dry-run，不会写文件、执行 shell、写数据库业务数据或发送额外 QQ 消息。",
            "不用手动找编号：可以直接用 /agent 审批详情 最新、/agent 确认 最新、/agent 任务详情 最新。",
            "",
            approval_reply,
        ]
    )


def format_agent_approval_decision(approval: AgentApproval, *, changed: bool) -> str:
    if changed:
        action = "确认" if approval.status == AGENT_APPROVAL_APPROVED else "拒绝"
        return "\n".join(
            [
                f"已{action} Agent 审批 #{approval.id}。",
                f"审批ID：#{approval.id}",
                f"状态：{agent_approval_status_label(approval.status)}",
                f"任务ID：#{approval.task_id}",
                f"任务：{approval.task_title}",
                "当前版本仅允许已注册且启用审批恢复的工具受控恢复。",
            ]
        )
    return "\n".join(
        [
            f"Agent 审批 #{approval.id} 当前状态：{agent_approval_status_label(approval.status)}",
            "只有待审批记录可以确认或拒绝。",
            "当前版本仅允许已注册且启用审批恢复的工具受控恢复。",
        ]
    )
