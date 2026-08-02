from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Callable

from .access_store import add_item, remove_item
from .agent_tasks import (
    AGENT_APPROVAL_PENDING,
    AgentApproval,
    decide_agent_approval,
    get_agent_approval,
    get_agent_task,
    resume_agent_approval,
)
from .database import utc_now
from .graph.tool_registry import (
    ToolContext,
    ToolRegistry,
    ToolSpec,
    create_default_main_agent_tool_registry,
)
from .manual_memory import (
    MANUAL_FACT_TYPE,
    MANUAL_PREFERENCE_TYPE,
    add_manual_memory,
)
from .owner_console_read_models import (
    OwnerConsoleApprovalActionability,
    OwnerConsoleContext,
)
from .owner_console_read_runtime import build_tool_input_preview
from .owner_write_runtime import OwnerWriteRuntime, run_owner_write_command
from .policy.risk import RiskLevel
from .role_cards import select_role_card
from .summaries import clear_session_summaries, delete_session_summary


OWNER_CONSOLE_APPROVAL_ACTIONS_ENABLED_ENV = "OWNER_CONSOLE_APPROVAL_ACTIONS_ENABLED"
OWNER_CONSOLE_APPROVAL_APPROVE_ACTION_HEADER = "approval-approve-v1"
OWNER_CONSOLE_APPROVAL_REJECT_ACTION_HEADER = "approval-reject-v1"
OWNER_CONSOLE_APPROVAL_APPROVE_CONFIRMATION = "approve_registered_pending_approval"
OWNER_CONSOLE_APPROVAL_REJECT_CONFIRMATION = "reject_registered_pending_approval"
OWNER_CONSOLE_APPROVAL_PREVIEW_LIMIT = 800
OWNER_WRITE_COMMAND_TOOL_NAME = "owner_write_command"
DOCUMENT_ARTIFACT_COMMANDS = (
    "create_txt_document",
    "create_word_document",
    "create_presentation",
)
OWNER_CONSOLE_ERROR_LOG_PATH = (
    Path(__file__).resolve().parents[3] / "logs" / "ai_chat_error.log"
)

# clear_image_cache is process-local to the QQ Bot and cannot be truthfully
# executed by the separate Owner Console process. External writes are excluded
# from the registry entirely. Every command below has a process-independent,
# fixed local implementation.
OWNER_CONSOLE_WEB_RESUMABLE_COMMANDS = frozenset(
    {
        "clear_error_log",
        "select_persona",
        "add_fact_memory",
        "add_preference_memory",
        "clear_session_summaries",
        "delete_session_summary",
        "allow_group",
        "deny_group",
        "allow_private",
        "deny_private",
        "block_user",
        "unblock_user",
        *DOCUMENT_ARTIFACT_COMMANDS,
    }
)


class OwnerConsoleApprovalActionError(RuntimeError):
    code = "internal_error"
    status_code = 500


class OwnerConsoleApprovalActionDisabled(OwnerConsoleApprovalActionError):
    code = "forbidden"
    status_code = 403


class OwnerConsoleApprovalActionForbidden(OwnerConsoleApprovalActionError):
    code = "forbidden"
    status_code = 403


class OwnerConsoleApprovalActionNotFound(OwnerConsoleApprovalActionError):
    code = "not_found"
    status_code = 404


class OwnerConsoleApprovalActionConflict(OwnerConsoleApprovalActionError):
    code = "conflict"
    status_code = 409


@dataclass(frozen=True)
class OwnerConsoleApprovalActionResult:
    generated_at: str
    approval_id: int
    task_id: int
    decision: str
    decision_changed: bool
    resume_attempted: bool
    resume_executed: bool
    task_status: str
    outcome: str
    code: str
    safe_message: str


def _approval_arguments(approval: AgentApproval) -> dict[str, Any] | None:
    try:
        value = json.loads(approval.tool_input_json)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _owner_write_command(approval: AgentApproval) -> str:
    arguments = _approval_arguments(approval)
    if arguments is None:
        return ""
    return str(arguments.get("command") or "").strip()


def _approval_expiration_state(approval: AgentApproval) -> str:
    value = approval.expires_at.strip()
    if not value:
        return "active"
    try:
        expires_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "invalid"
    if expires_at.tzinfo is None:
        return "invalid"
    return "expired" if expires_at.astimezone(UTC) <= datetime.now(UTC) else "active"


def _subject_label(subject_type: str, subject_id: str) -> str:
    return f"用户 {subject_id}" if subject_type == "user" else f"{subject_type} {subject_id}"


def _clear_error_log() -> str:
    if not OWNER_CONSOLE_ERROR_LOG_PATH.exists():
        return "错误日志不存在。"
    OWNER_CONSOLE_ERROR_LOG_PATH.write_text("", encoding="utf-8")
    return "已清空错误日志。"


def _execute_owner_console_local_write(command: str, context: ToolContext) -> str:
    if command not in OWNER_CONSOLE_WEB_RESUMABLE_COMMANDS:
        raise RuntimeError("owner_console_command_not_web_resumable")
    if command in DOCUMENT_ARTIFACT_COMMANDS:
        from .document_artifacts import (
            DocumentArtifactError,
            create_document_artifact,
        )

        arguments = context.metadata.get("tool_arguments", {})
        if not isinstance(arguments, dict):
            raise RuntimeError("document_artifact_arguments_unavailable")
        try:
            result = create_document_artifact(
                command,
                arguments.get("title"),
                arguments.get("content"),
            )
        except DocumentArtifactError as exc:
            raise RuntimeError(f"document_artifact_{exc.code}") from exc
        count_label = {
            "create_txt_document": "正文字符",
            "create_word_document": "非空段落",
            "create_presentation": "幻灯片",
        }[command]
        return "\n".join(
            [
                f"{result.format_label} 文档已生成。",
                f"Artifact ID：{result.artifact_id}",
                f"文件：{result.relative_file}",
                f"大小：{result.bytes} bytes",
                f"{count_label}：{result.item_count}",
                f"SHA-256 短哈希：{result.short_sha256}",
                "未修改项目源码或配置；未通过 QQ 发送文件。",
            ]
        )

    runtime = OwnerWriteRuntime(
        clear_error_log=_clear_error_log,
        add_access_item=add_item,
        remove_access_item=remove_item,
        select_role_card=select_role_card,
        add_manual_memory=add_manual_memory,
        subject_label=_subject_label,
        clear_session_summaries=clear_session_summaries,
        delete_session_summary=delete_session_summary,
        fact_memory_type=MANUAL_FACT_TYPE,
        preference_memory_type=MANUAL_PREFERENCE_TYPE,
    )
    return run_owner_write_command(runtime, command, context)


def _owner_console_write_executor(
    arguments: dict[str, Any],
    context: ToolContext,
) -> str:
    command = str(arguments["command"]).strip()
    if command not in OWNER_CONSOLE_WEB_RESUMABLE_COMMANDS:
        raise RuntimeError("owner_console_command_not_web_resumable")
    metadata = dict(context.metadata)
    metadata["tool_arguments"] = dict(arguments)
    return _execute_owner_console_local_write(
        command,
        ToolContext(
            query=context.query,
            is_owner=context.is_owner,
            is_group=context.is_group,
            metadata=metadata,
        ),
    )


def create_owner_console_approval_resume_registry() -> ToolRegistry:
    registry = create_default_main_agent_tool_registry(include_dry_run_tools=True)
    registry.register(
        ToolSpec(
            name=OWNER_WRITE_COMMAND_TOOL_NAME,
            description="Resume a fixed local owner command after web approval.",
            risk_level=RiskLevel.WRITE_LOCAL,
            required_arguments=("command",),
            optional_arguments=("query", "target", "title", "content", "summary_id"),
            executor=_owner_console_write_executor,
            enabled=True,
            llm_visible=False,
            requires_approval=True,
            approval_resume_enabled=True,
        )
    )
    return registry


@dataclass
class OwnerConsoleApprovalActionRuntime:
    enabled: bool
    registry_factory: Callable[[], ToolRegistry] = create_owner_console_approval_resume_registry
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def actionability(self, approval: AgentApproval) -> OwnerConsoleApprovalActionability:
        if approval.status != AGENT_APPROVAL_PENDING:
            return OwnerConsoleApprovalActionability(
                can_approve=False,
                can_reject=False,
                resume_enabled=False,
                blocked_reason="approval is not pending",
                future_operation_only=False,
            )
        if not self.enabled:
            return OwnerConsoleApprovalActionability(
                can_approve=False,
                can_reject=False,
                resume_enabled=False,
                blocked_reason="web approval actions are disabled",
                future_operation_only=False,
            )
        expiration_state = _approval_expiration_state(approval)
        if expiration_state != "active":
            return OwnerConsoleApprovalActionability(
                can_approve=False,
                can_reject=True,
                resume_enabled=False,
                blocked_reason=(
                    "approval has expired; web approval is blocked"
                    if expiration_state == "expired"
                    else "approval expiration is invalid; web approval is blocked"
                ),
                future_operation_only=False,
            )

        preview = build_tool_input_preview(
            approval.tool_input_json,
            limit=OWNER_CONSOLE_APPROVAL_PREVIEW_LIMIT,
        )
        if preview.redacted:
            return OwnerConsoleApprovalActionability(
                can_approve=False,
                can_reject=True,
                resume_enabled=False,
                blocked_reason="sensitive tool input is redacted; web approval is blocked",
                future_operation_only=False,
            )
        if preview.truncated:
            return OwnerConsoleApprovalActionability(
                can_approve=False,
                can_reject=True,
                resume_enabled=False,
                blocked_reason="tool input preview is truncated; web approval is blocked",
                future_operation_only=False,
            )
        if approval.risk_level.strip().lower() == RiskLevel.WRITE_EXTERNAL.value:
            return OwnerConsoleApprovalActionability(
                can_approve=False,
                can_reject=True,
                resume_enabled=False,
                blocked_reason="external writes are not available through web approval",
                future_operation_only=False,
            )

        registry = self.registry_factory()
        try:
            spec = registry.require(approval.tool_name)
        except Exception:
            return OwnerConsoleApprovalActionability(
                can_approve=False,
                can_reject=True,
                resume_enabled=False,
                blocked_reason="tool is not registered for Owner Console resume",
                future_operation_only=False,
            )
        if not spec.approval_resume_enabled:
            return OwnerConsoleApprovalActionability(
                can_approve=False,
                can_reject=True,
                resume_enabled=False,
                blocked_reason="tool is not enabled for approval resume",
                future_operation_only=False,
            )
        if spec.risk_level != RiskLevel.WRITE_LOCAL:
            return OwnerConsoleApprovalActionability(
                can_approve=False,
                can_reject=True,
                resume_enabled=False,
                blocked_reason="external writes are not available through web approval",
                future_operation_only=False,
            )
        if (
            approval.tool_name == OWNER_WRITE_COMMAND_TOOL_NAME
            and _owner_write_command(approval) not in OWNER_CONSOLE_WEB_RESUMABLE_COMMANDS
        ):
            return OwnerConsoleApprovalActionability(
                can_approve=False,
                can_reject=True,
                resume_enabled=False,
                blocked_reason=(
                    "this local command depends on the QQ Bot process and cannot "
                    "be resumed by Owner Console"
                ),
                future_operation_only=False,
            )
        try:
            arguments = _approval_arguments(approval)
            if arguments is None:
                raise ValueError("invalid tool input")
            registry.validate_arguments(approval.tool_name, arguments)
        except Exception:
            return OwnerConsoleApprovalActionability(
                can_approve=False,
                can_reject=True,
                resume_enabled=False,
                blocked_reason="saved tool input does not match the registered contract",
                future_operation_only=False,
            )
        return OwnerConsoleApprovalActionability(
            can_approve=True,
            can_reject=True,
            resume_enabled=True,
            blocked_reason="",
            future_operation_only=False,
        )

    def decide(
        self,
        context: OwnerConsoleContext,
        *,
        approval_id: int,
        approved: bool,
    ) -> OwnerConsoleApprovalActionResult:
        if not self.enabled:
            raise OwnerConsoleApprovalActionDisabled("web approval actions are disabled")
        with self._lock:
            approval = get_agent_approval(
                approval_id,
                session_key=context.session_key,
                user_id=context.user_id,
            )
            if approval is None:
                raise OwnerConsoleApprovalActionNotFound(
                    "owner console approval was not found"
                )
            actionability = self.actionability(approval)
            allowed = actionability.can_approve if approved else actionability.can_reject
            if not allowed:
                if approval.status != AGENT_APPROVAL_PENDING:
                    raise OwnerConsoleApprovalActionConflict("approval is no longer pending")
                raise OwnerConsoleApprovalActionForbidden(
                    actionability.blocked_reason or "approval action is not allowed"
                )

            decided, changed = decide_agent_approval(
                approval_id=approval_id,
                session_key=context.session_key,
                user_id=context.user_id,
                approved=approved,
            )
            if decided is None:
                raise OwnerConsoleApprovalActionNotFound(
                    "owner console approval was not found"
                )
            if not changed:
                raise OwnerConsoleApprovalActionConflict(
                    "approval was already decided by another request"
                )

            resume_attempted = approved
            resume_executed = False
            safe_message = "审批已拒绝；对应工具未执行。"
            outcome = "rejected"
            code = "approval_rejected"
            if approved:
                _, resume_executed, resume_message = resume_agent_approval(
                    approval_id=approval_id,
                    session_key=context.session_key,
                    user_id=context.user_id,
                    tool_registry=self.registry_factory(),
                )
                safe_message = resume_message or "审批已批准，但工具未执行。"
                outcome = "succeeded" if resume_executed else "failed"
                code = (
                    "approval_resume_succeeded"
                    if resume_executed
                    else "approval_resume_not_executed"
                )

            task = get_agent_task(
                decided.task_id,
                session_key=context.session_key,
                user_id=context.user_id,
            )
            return OwnerConsoleApprovalActionResult(
                generated_at=utc_now(),
                approval_id=decided.id,
                task_id=decided.task_id,
                decision="approved" if approved else "rejected",
                decision_changed=True,
                resume_attempted=resume_attempted,
                resume_executed=resume_executed,
                task_status=task.status if task is not None else "unknown",
                outcome=outcome,
                code=code,
                safe_message=safe_message,
            )
