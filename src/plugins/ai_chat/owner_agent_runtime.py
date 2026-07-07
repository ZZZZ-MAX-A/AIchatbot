from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .agent_tasks import (
    AGENT_APPROVAL_APPROVED,
    AGENT_APPROVAL_PENDING,
    AGENT_TASK_COMMAND_APPROVAL_APPROVE,
    AGENT_TASK_COMMAND_APPROVAL_DETAIL,
    AGENT_TASK_COMMAND_APPROVAL_DRILL,
    AGENT_TASK_COMMAND_APPROVAL_REJECT,
    AGENT_TASK_COMMAND_APPROVAL_STATUS,
    AGENT_TASK_COMMAND_CANCEL,
    AGENT_TASK_COMMAND_CREATE,
    AGENT_TASK_COMMAND_DETAIL,
    AGENT_TASK_COMMAND_NEXT_STEP,
    AGENT_TASK_COMMAND_STATUS,
    AGENT_TASK_COMMAND_WORKBENCH,
    cancel_agent_task,
    create_agent_approval_drill_reply,
    create_agent_approval_request_reply,
    create_agent_task,
    decide_agent_approval,
    format_agent_approval_decision,
    format_agent_approval_detail,
    format_agent_approval_list,
    format_agent_task_cancelled,
    format_agent_task_created,
    format_agent_task_detail,
    format_agent_task_list,
    format_agent_task_next_step,
    format_agent_task_workbench,
    get_agent_approval,
    get_agent_task,
    is_implicit_latest_agent_reference,
    is_latest_agent_reference,
    list_agent_approvals,
    list_agent_task_events,
    list_agent_tasks,
    parse_agent_task_command,
    parse_agent_task_id,
    resume_agent_approval,
)


@dataclass(frozen=True)
class OwnerAgentContext:
    session_key: str
    user_id: str


ApprovalResumeRegistryFactory = Callable[[], Any]


def latest_agent_approval_id(context: OwnerAgentContext) -> int | None:
    approvals = list_agent_approvals(
        session_key=context.session_key,
        user_id=context.user_id,
        limit=1,
    )
    return approvals[0].id if approvals else None


def latest_agent_task_id(context: OwnerAgentContext) -> int | None:
    tasks = list_agent_tasks(
        session_key=context.session_key,
        user_id=context.user_id,
        limit=1,
    )
    return tasks[0].id if tasks else None


def resolve_agent_approval_id_for_decision(
    context: OwnerAgentContext,
    reference: str,
    *,
    verb: str,
) -> tuple[int | None, str | None]:
    stripped_reference = reference.strip()
    if is_implicit_latest_agent_reference(stripped_reference):
        approvals = list_agent_approvals(
            session_key=context.session_key,
            user_id=context.user_id,
            status=AGENT_APPROVAL_PENDING,
            limit=2,
        )
        if not approvals:
            return None, (
                "当前会话没有待审批项。\n"
                f"如果要操作历史审批，请使用：/agent {verb} <审批ID>"
            )
        if len(approvals) > 1:
            ids = "、".join(f"#{approval.id}" for approval in approvals)
            return None, (
                f"当前会话有多个待审批项：{ids}。\n"
                f"请明确指定审批 ID：/agent {verb} <审批ID>"
            )
        return approvals[0].id, None

    approval_id = parse_agent_task_id(stripped_reference)
    if approval_id is None and (
        not stripped_reference or is_latest_agent_reference(stripped_reference)
    ):
        approval_id = latest_agent_approval_id(context)
    if approval_id is None:
        return None, f"请提供审批 ID，或使用：/agent {verb} 最新"
    return approval_id, None


def _resume_after_approval(
    context: OwnerAgentContext,
    *,
    approval_id: int,
    approval_resume_tool_registry_factory: ApprovalResumeRegistryFactory,
) -> str:
    _, resumed, resume_text = resume_agent_approval(
        approval_id=approval_id,
        session_key=context.session_key,
        user_id=context.user_id,
        tool_registry=approval_resume_tool_registry_factory(),
    )
    return resume_text if resumed or resume_text else ""


def _format_approval_decision_reply(
    context: OwnerAgentContext,
    *,
    approval_id: int,
    approved: bool,
    approval_resume_tool_registry_factory: ApprovalResumeRegistryFactory,
) -> str:
    approval, changed = decide_agent_approval(
        approval_id=approval_id,
        session_key=context.session_key,
        user_id=context.user_id,
        approved=approved,
    )
    if approval is None:
        return f"未找到当前会话中的 Agent 审批 #{approval_id}。"
    reply = format_agent_approval_decision(approval, changed=changed)
    if approved and approval.status == AGENT_APPROVAL_APPROVED:
        resume_text = _resume_after_approval(
            context,
            approval_id=approval.id,
            approval_resume_tool_registry_factory=approval_resume_tool_registry_factory,
        )
        if resume_text:
            reply = f"{reply}\n\n{resume_text}"
    return reply


def format_owner_agent_task_read(
    context: OwnerAgentContext,
    command: str,
    reference: str,
) -> str:
    if command == "next_step":
        return format_agent_task_next_step(
            session_key=context.session_key,
            user_id=context.user_id,
        )
    if command == "workbench":
        return format_agent_task_workbench(
            session_key=context.session_key,
            user_id=context.user_id,
        )
    if command == "list_tasks":
        tasks = list_agent_tasks(
            session_key=context.session_key,
            user_id=context.user_id,
        )
        return format_agent_task_list(tasks)
    if command == "list_approvals":
        approvals = list_agent_approvals(
            session_key=context.session_key,
            user_id=context.user_id,
        )
        return format_agent_approval_list(approvals)
    if command == "task_detail":
        task_id = parse_agent_task_id(reference)
        if task_id is None and (not reference or is_latest_agent_reference(reference)):
            task_id = latest_agent_task_id(context)
        if task_id is None:
            return "请提供任务 ID，或使用：/agent 最新任务详情"
        task = get_agent_task(
            task_id,
            session_key=context.session_key,
            user_id=context.user_id,
        )
        if task is None:
            return f"未找到当前会话中的 Agent 任务 #{task_id}。"
        events = list_agent_task_events(task.id)
        approvals = list_agent_approvals(
            session_key=context.session_key,
            user_id=context.user_id,
            task_id=task.id,
        )
        return format_agent_task_detail(task, events, approvals)
    if command == "approval_detail":
        approval_id = parse_agent_task_id(reference)
        if approval_id is None and (not reference or is_latest_agent_reference(reference)):
            approval_id = latest_agent_approval_id(context)
        if approval_id is None:
            return "请提供审批 ID，或使用：/agent 最新审批详情"
        approval = get_agent_approval(
            approval_id,
            session_key=context.session_key,
            user_id=context.user_id,
        )
        if approval is None:
            return f"未找到当前会话中的 Agent 审批 #{approval_id}。"
        task = get_agent_task(
            approval.task_id,
            session_key=context.session_key,
            user_id=context.user_id,
        )
        events = list_agent_task_events(approval.task_id, limit=5)
        return format_agent_approval_detail(approval, task=task, events=events)
    raise RuntimeError(f"unsupported agent task read command: {command}")


def run_owner_agent_task_command(
    context: OwnerAgentContext,
    query: str,
    *,
    approval_resume_tool_registry_factory: ApprovalResumeRegistryFactory,
) -> str | None:
    parsed = parse_agent_task_command(query)
    if parsed is None:
        return None

    action, goal = parsed
    if action == AGENT_TASK_COMMAND_APPROVAL_STATUS:
        approvals = list_agent_approvals(
            session_key=context.session_key,
            user_id=context.user_id,
        )
        return format_agent_approval_list(approvals)

    if action == AGENT_TASK_COMMAND_NEXT_STEP:
        return format_agent_task_next_step(
            session_key=context.session_key,
            user_id=context.user_id,
        )

    if action == AGENT_TASK_COMMAND_WORKBENCH:
        return format_agent_task_workbench(
            session_key=context.session_key,
            user_id=context.user_id,
        )

    if action == AGENT_TASK_COMMAND_APPROVAL_DRILL:
        if not goal:
            return (
                "请提供审批演练目标：/agent 审批演练 <目标>\n"
                "该命令只创建 dry-run 任务和审批请求，不执行任何工具。"
            )
        return create_agent_approval_drill_reply(
            session_key=context.session_key,
            user_id=context.user_id,
            goal=goal,
        )

    if action == AGENT_TASK_COMMAND_APPROVAL_DETAIL:
        approval_id = parse_agent_task_id(goal)
        if approval_id is None and is_latest_agent_reference(goal):
            approval_id = latest_agent_approval_id(context)
        if approval_id is None:
            return "请提供审批 ID：/agent 审批详情 <审批ID>\n也可以用：/agent 审批详情 最新"
        return format_owner_agent_task_read(
            context,
            "approval_detail",
            str(approval_id),
        )

    if action in {
        AGENT_TASK_COMMAND_APPROVAL_APPROVE,
        AGENT_TASK_COMMAND_APPROVAL_REJECT,
    }:
        approved = action == AGENT_TASK_COMMAND_APPROVAL_APPROVE
        verb = "确认" if approved else "拒绝"
        approval_id, resolve_error = resolve_agent_approval_id_for_decision(
            context,
            goal,
            verb=verb,
        )
        if resolve_error:
            return resolve_error
        return _format_approval_decision_reply(
            context,
            approval_id=approval_id,
            approved=approved,
            approval_resume_tool_registry_factory=approval_resume_tool_registry_factory,
        )

    if action == AGENT_TASK_COMMAND_STATUS:
        tasks = list_agent_tasks(
            session_key=context.session_key,
            user_id=context.user_id,
        )
        return format_agent_task_list(tasks)

    if action == AGENT_TASK_COMMAND_DETAIL:
        task_id = parse_agent_task_id(goal)
        if task_id is None and is_latest_agent_reference(goal):
            task_id = latest_agent_task_id(context)
        if task_id is None:
            return "请提供任务 ID：/agent 任务详情 <任务ID>\n也可以用：/agent 任务详情 最新"
        return format_owner_agent_task_read(
            context,
            "task_detail",
            str(task_id),
        )

    if action == AGENT_TASK_COMMAND_CANCEL:
        task_id = parse_agent_task_id(goal)
        if task_id is None:
            return "请提供任务 ID：/agent 取消任务 <任务ID>"
        task, changed = cancel_agent_task(
            task_id=task_id,
            session_key=context.session_key,
            user_id=context.user_id,
        )
        if task is None:
            return f"未找到当前会话中的 Agent 任务 #{task_id}。"
        return format_agent_task_cancelled(task, changed=changed)

    if action == AGENT_TASK_COMMAND_CREATE:
        if not goal:
            return (
                "请提供任务目标：/agent 任务 <目标>\n"
                "当前版本只允许已注册且启用审批恢复的工具在确认后受控恢复；"
                "不执行任意 shell、任意真实写文件或未注册数据库写入。"
            )
        task_id = create_agent_task(
            session_key=context.session_key,
            user_id=context.user_id,
            goal=goal,
        )
        task = get_agent_task(task_id)
        if task is None:
            return "Agent 任务创建失败：任务记录未找到。"
        return format_agent_task_created(task)

    return None


def execute_owner_agent_task_command(
    context: OwnerAgentContext,
    command: str,
    reference: str,
    goal: str,
    *,
    approval_resume_tool_registry_factory: ApprovalResumeRegistryFactory,
) -> str:
    if command == "create_task":
        if not goal:
            return "请提供任务目标：/agent 帮我创建一个任务：<目标>"
        task_id = create_agent_task(
            session_key=context.session_key,
            user_id=context.user_id,
            goal=goal,
        )
        task = get_agent_task(task_id)
        if task is None:
            return "Agent 任务创建失败：任务记录未找到。"
        return format_agent_task_created(task)

    if command == "create_approval_drill":
        if not goal:
            return "请提供审批演练目标：/agent 创建审批演练：<目标>"
        return create_agent_approval_drill_reply(
            session_key=context.session_key,
            user_id=context.user_id,
            goal=goal,
        )

    if command == "cancel_task":
        task_id = parse_agent_task_id(reference)
        if task_id is None and (not reference or is_latest_agent_reference(reference)):
            task_id = latest_agent_task_id(context)
        if task_id is None:
            return "请提供任务 ID，或使用：/agent 取消最新任务"
        task, changed = cancel_agent_task(
            task_id=task_id,
            session_key=context.session_key,
            user_id=context.user_id,
        )
        if task is None:
            return f"未找到当前会话中的 Agent 任务 #{task_id}。"
        return format_agent_task_cancelled(task, changed=changed)

    if command in {"approve_approval", "reject_approval"}:
        approved = command == "approve_approval"
        verb = "确认" if approved else "拒绝"
        approval_id, resolve_error = resolve_agent_approval_id_for_decision(
            context,
            reference,
            verb=verb,
        )
        if resolve_error:
            return resolve_error
        return _format_approval_decision_reply(
            context,
            approval_id=approval_id,
            approved=approved,
            approval_resume_tool_registry_factory=approval_resume_tool_registry_factory,
        )

    raise RuntimeError(f"unsupported agent task command: {command}")


def create_owner_agent_approval_request(
    context: OwnerAgentContext,
    *,
    query: str,
    requested_tool: str,
    arguments: dict[str, Any],
    risk_level: Any,
    policy_reason: str,
) -> str:
    command = str(arguments.get("command") or requested_tool).strip()
    goal = f"语义主人管理审批：{command}"
    if query.strip():
        goal = f"{goal} / {query.strip()}"
    task_id = create_agent_task(
        session_key=context.session_key,
        user_id=context.user_id,
        goal=goal,
    )
    risk_text = str(getattr(risk_level, "value", risk_level))
    return create_agent_approval_request_reply(
        task_id=task_id,
        session_key=context.session_key,
        user_id=context.user_id,
        tool_name=requested_tool,
        tool_input_json=json.dumps(dict(arguments), ensure_ascii=False),
        risk_level=risk_text,
        reason=policy_reason or "owner write command requires approval",
    )
