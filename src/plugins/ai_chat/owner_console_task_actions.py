from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from .agent_tasks import (
    AGENT_APPROVAL_PENDING,
    AGENT_TASK_PENDING,
    cancel_agent_task,
    get_agent_task,
    list_agent_approvals,
)
from .database import utc_now
from .owner_console_read_runtime import OwnerConsoleContext


OWNER_CONSOLE_TASK_ACTIONS_ENABLED_ENV = "OWNER_CONSOLE_TASK_ACTIONS_ENABLED"
OWNER_CONSOLE_TASK_CANCEL_ACTION_HEADER = "task-cancel-v1"
OWNER_CONSOLE_TASK_CANCEL_CONFIRMATION = "cancel_single_pending_task"


class OwnerConsoleTaskActionError(RuntimeError):
    code = "internal_error"
    status_code = 500


class OwnerConsoleTaskActionDisabled(OwnerConsoleTaskActionError):
    code = "forbidden"
    status_code = 403


class OwnerConsoleTaskActionNotFound(OwnerConsoleTaskActionError):
    code = "not_found"
    status_code = 404


class OwnerConsoleTaskActionConflict(OwnerConsoleTaskActionError):
    code = "conflict"
    status_code = 409


@dataclass(frozen=True)
class OwnerConsoleTaskActionResult:
    generated_at: str
    task_id: int
    previous_status: str
    task_status: str
    status_changed: bool
    tool_executed: bool
    approval_resumed: bool
    outcome: str
    code: str
    safe_message: str


class OwnerConsoleTaskActionRuntime:
    def __init__(self, *, enabled: bool = False) -> None:
        self.enabled = bool(enabled)
        self._lock = Lock()

    def cancel(
        self,
        context: OwnerConsoleContext,
        *,
        task_id: int,
    ) -> OwnerConsoleTaskActionResult:
        if not self.enabled:
            raise OwnerConsoleTaskActionDisabled("web task actions are disabled")

        with self._lock:
            task = get_agent_task(
                task_id,
                session_key=context.session_key,
                user_id=context.user_id,
            )
            if task is None:
                raise OwnerConsoleTaskActionNotFound(
                    "owner console task was not found"
                )
            if task.status != AGENT_TASK_PENDING:
                raise OwnerConsoleTaskActionConflict(
                    "only a pending task can be cancelled"
                )
            pending_approvals = list_agent_approvals(
                session_key=context.session_key,
                user_id=context.user_id,
                task_id=task.id,
                status=AGENT_APPROVAL_PENDING,
                limit=1,
            )
            if pending_approvals:
                raise OwnerConsoleTaskActionConflict(
                    "task has a pending approval that must be decided first"
                )

            cancelled, changed = cancel_agent_task(
                task_id=task.id,
                session_key=context.session_key,
                user_id=context.user_id,
            )
            if cancelled is None:
                raise OwnerConsoleTaskActionNotFound(
                    "owner console task was not found"
                )
            if not changed:
                raise OwnerConsoleTaskActionConflict(
                    "task state changed or a pending approval now exists"
                )

            return OwnerConsoleTaskActionResult(
                generated_at=utc_now(),
                task_id=cancelled.id,
                previous_status=task.status,
                task_status=cancelled.status,
                status_changed=True,
                tool_executed=False,
                approval_resumed=False,
                outcome="cancelled",
                code="task_cancelled",
                safe_message="任务已取消并收口；未执行原工具，也未恢复任何审批。",
            )
