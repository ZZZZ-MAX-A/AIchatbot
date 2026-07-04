from __future__ import annotations

import inspect
import json
import re
from collections.abc import Awaitable, Callable
from typing import TypeAlias

from ..policy.engine import PolicyDecisionType, ToolPolicyInput, decide_tool_policy
from ..policy.risk import RiskLevel
from .main_agent import (
    MainAgentAction,
    MainAgentActionRequestError,
    MainAgentGraphRunner,
    MainAgentHandler,
    MainAgentState,
    MainAgentToolName,
    apply_action_request_to_state,
    dev_context_tool_action_json,
    parse_main_agent_action_request,
)
from .main_agent_llm import MainAgentLLMCall, create_main_agent_call_handler
from .runtime import RuntimeResponse
from .state import ActorRole, RuntimeState, SessionType
from .tool_registry import (
    ToolContext,
    ToolExecutionError,
    ToolExecutor,
    ToolRegistry,
    create_default_main_agent_tool_registry,
)


ReadOnlyDevContextTool: TypeAlias = Callable[[str, bool], str | Awaitable[str]]
OwnerReadCommandTool: TypeAlias = Callable[[str, ToolContext], str | Awaitable[str]]
OwnerWriteCommandTool: TypeAlias = Callable[[str, ToolContext], str]
AgentTaskReadTool: TypeAlias = Callable[
    [str, str, ToolContext],
    str | Awaitable[str],
]
AgentTaskCommandTool: TypeAlias = Callable[
    [str, str, str, ToolContext],
    str | Awaitable[str],
]
ToolRiskResolver: TypeAlias = Callable[[MainAgentState], RiskLevel]
ApprovalRequestHandler: TypeAlias = Callable[
    [MainAgentState, RiskLevel, str],
    str | Awaitable[str],
]

OWNER_READ_COMMAND_TOOL_NAME = "owner_read_command"
OWNER_WRITE_COMMAND_TOOL_NAME = "owner_write_command"
AGENT_TASK_READ_TOOL_NAME = "agent_task_read"
AGENT_TASK_COMMAND_TOOL_NAME = "agent_task_command"
OWNER_READ_COMMANDS: tuple[str, ...] = (
    "bot_status",
    "diagnostics",
    "config_status",
    "vision_status",
    "recent_errors",
    "image_cache_status",
    "memory_status",
    "rag_status",
    "summary_status",
    "view_summaries",
    "view_gap_scene_summaries",
    "view_long_term_memory",
    "view_persona",
    "role_card_list",
    "tts_status",
    "group_whitelist",
    "private_whitelist",
    "blacklist",
    "access_overview",
    "model_config_status",
    "rag_index_detail",
    "main_agent_observations",
)
AGENT_TASK_READ_COMMANDS: tuple[str, ...] = (
    "list_tasks",
    "task_detail",
    "list_approvals",
    "approval_detail",
)
AGENT_TASK_COMMANDS: tuple[str, ...] = (
    "create_task",
    "cancel_task",
    "approve_approval",
    "reject_approval",
    "create_approval_drill",
)
OWNER_WRITE_COMMANDS: tuple[str, ...] = (
    "clear_image_cache",
    "clear_error_log",
)


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


def create_read_only_main_agent_runner(
    *,
    retrieve_dev_context: ReadOnlyDevContextTool,
    execute_owner_read_command: OwnerReadCommandTool | None = None,
    execute_owner_write_command: OwnerWriteCommandTool | None = None,
    execute_agent_task_read: AgentTaskReadTool | None = None,
    execute_agent_task_command: AgentTaskCommandTool | None = None,
    request_approval: ApprovalRequestHandler | None = None,
    llm_call: MainAgentLLMCall | None = None,
    call_main_agent: MainAgentHandler | None = None,
    summarize_tool_result: MainAgentHandler | None = None,
    render_mode: str = "raw",
) -> MainAgentGraphRunner:
    tool_registry = create_read_only_main_agent_tool_registry(
        retrieve_dev_context,
        execute_owner_read_command=execute_owner_read_command,
        execute_owner_write_command=execute_owner_write_command,
        execute_agent_task_read=execute_agent_task_read,
        execute_agent_task_command=execute_agent_task_command,
    )
    agent_call = call_main_agent
    if agent_call is None and llm_call is not None:
        agent_call = create_main_agent_call_handler(llm_call, tool_registry=tool_registry)
    if agent_call is None:
        agent_call = call_dev_context_stub_agent
    agent_call = create_semantic_first_main_agent_planner(tool_registry, agent_call)

    render_agent_response = (
        render_concise_read_only_agent_response
        if render_mode == "concise"
        else render_read_only_agent_response
    )
    if summarize_tool_result is not None:
        render_agent_response = create_tool_summary_renderer(
            summarize_tool_result,
            fallback_renderer=render_agent_response,
        )

    return MainAgentGraphRunner(
        validate_agent_request=validate_read_only_agent_request,
        build_agent_context=create_read_only_agent_context_builder(tool_registry),
        call_main_agent=agent_call,
        validate_action_request=create_main_agent_action_validator(tool_registry),
        check_tool_policy=create_tool_policy_checker(
            risk_level_for_tool=lambda state: tool_registry.require(state.requested_tool).risk_level,
            enable_local_write=execute_owner_write_command is not None,
            request_approval=request_approval,
        ),
        execute_tool=create_tool_registry_executor(tool_registry),
        render_agent_response=render_agent_response,
    )


def create_read_only_main_agent_runtime_handler(
    *,
    retrieve_dev_context: ReadOnlyDevContextTool,
    execute_owner_read_command: OwnerReadCommandTool | None = None,
    execute_owner_write_command: OwnerWriteCommandTool | None = None,
    execute_agent_task_read: AgentTaskReadTool | None = None,
    execute_agent_task_command: AgentTaskCommandTool | None = None,
    request_approval: ApprovalRequestHandler | None = None,
    llm_call: MainAgentLLMCall | None = None,
    call_main_agent: MainAgentHandler | None = None,
    summarize_tool_result: MainAgentHandler | None = None,
    render_mode: str = "raw",
):
    runner = create_read_only_main_agent_runner(
        retrieve_dev_context=retrieve_dev_context,
        execute_owner_read_command=execute_owner_read_command,
        execute_owner_write_command=execute_owner_write_command,
        execute_agent_task_read=execute_agent_task_read,
        execute_agent_task_command=execute_agent_task_command,
        request_approval=request_approval,
        llm_call=llm_call,
        call_main_agent=call_main_agent,
        summarize_tool_result=summarize_tool_result,
        render_mode=render_mode,
    )

    async def handle_main_agent(state: RuntimeState) -> RuntimeResponse:
        main_state = MainAgentState(
            query=state.event.plain_text,
            is_owner=state.actor.role == ActorRole.OWNER,
            is_group=state.session.session_type == SessionType.GROUP,
            metadata={
                "message_id": state.event.message_id,
                "raw_text": state.event.raw_text,
                "session_key": state.session.session_key,
                "session_type": state.session.session_type.value,
                "user_id": state.actor.user_id,
                "actor_role": state.actor.role.value,
                "group_id": state.session.group_id or "",
            },
        )
        execution = await runner.run(main_state)
        state.response = execution.result.response_text
        state.error = execution.result.error or None
        state.artifacts["main_agent_graph"] = {
            "node_trace": tuple(node.value for node in execution.node_trace),
            "action": execution.result.action,
            "requested_tool": execution.result.requested_tool,
            "tool_result": execution.result.tool_result,
            "policy_decision": execution.result.policy_decision,
            "error": execution.result.error,
            "metadata": execution.result.metadata,
        }
        return RuntimeResponse(
            execution.result.response_text,
            should_reply=bool(execution.result.response_text),
        )

    return handle_main_agent


def validate_read_only_agent_request(state: MainAgentState) -> MainAgentState:
    if not state.is_owner:
        state.response_text = "MainAgentGraph rejected: owner access is required."
        state.error = "permission_denied"
    elif state.is_group:
        state.response_text = "MainAgentGraph rejected: the first read-only version is private-only."
        state.error = "group_denied"
    elif not state.query.strip():
        state.response_text = "Please provide a MainAgentGraph query."
        state.error = "validation_failed"
    return state


def build_read_only_agent_context(state: MainAgentState) -> MainAgentState:
    return create_read_only_agent_context_builder(
        create_default_main_agent_tool_registry()
    )(state)


def create_read_only_agent_context_builder(tool_registry: ToolRegistry) -> MainAgentHandler:
    def build_context(state: MainAgentState) -> MainAgentState:
        visible_tools = tool_registry.visible_tool_names()
        state.metadata["mode"] = "read_only"
        state.metadata["allowed_tools"] = visible_tools
        state.metadata.setdefault(
            "agent_context",
            "\n".join(
                [
                    "MainAgentGraph read-only local test mode.",
                    f"Allowed tools: {', '.join(visible_tools)}.",
                    "Disallowed: shell, file writes, QQ sends, external writes.",
                ]
            ),
        )
        return state

    return build_context


def create_read_only_main_agent_tool_registry(
    retrieve_dev_context: ReadOnlyDevContextTool,
    *,
    execute_owner_read_command: OwnerReadCommandTool | None = None,
    execute_owner_write_command: OwnerWriteCommandTool | None = None,
    execute_agent_task_read: AgentTaskReadTool | None = None,
    execute_agent_task_command: AgentTaskCommandTool | None = None,
) -> ToolRegistry:
    registry = create_default_main_agent_tool_registry()
    spec = registry.require(MainAgentToolName.DEV_CONTEXT.value)

    async def execute_dev_context(arguments, context: ToolContext):
        return str(
            await _maybe_await(
                retrieve_dev_context(str(arguments["query"]).strip(), context.is_owner)
            )
        )

    specs = [
        type(spec)(
            name=spec.name,
            description=spec.description,
            risk_level=spec.risk_level,
            required_arguments=spec.required_arguments,
            optional_arguments=spec.optional_arguments,
            executor=execute_dev_context,
            enabled=spec.enabled,
            llm_visible=spec.llm_visible,
            requires_approval=spec.requires_approval,
            approval_resume_enabled=spec.approval_resume_enabled,
        )
    ]
    if execute_owner_read_command is not None:
        specs.append(
            type(spec)(
                name=OWNER_READ_COMMAND_TOOL_NAME,
                description=(
                    "Run a read-only owner QQ management command. "
                    "Use arguments.command as one of: "
                    f"{', '.join(OWNER_READ_COMMANDS)}. "
                    "This is for diagnostics/status only and never clears, deletes, "
                    "writes, sends extra QQ messages, or changes configuration."
                ),
                risk_level=RiskLevel.READ_LOCAL,
                required_arguments=("command",),
                optional_arguments=("query",),
                executor=create_owner_read_command_executor(execute_owner_read_command),
                enabled=True,
                llm_visible=True,
                requires_approval=False,
                approval_resume_enabled=False,
            )
        )
    if execute_agent_task_read is not None:
        specs.append(
            type(spec)(
                name=AGENT_TASK_READ_TOOL_NAME,
                description=(
                    "Read MainAgent task and approval records. "
                    "Use arguments.command as one of: "
                    f"{', '.join(AGENT_TASK_READ_COMMANDS)}. "
                    "Optional arguments.reference may be an id or latest. "
                    "This never creates, approves, rejects, resumes, cancels, "
                    "or executes tasks."
                ),
                risk_level=RiskLevel.READ_LOCAL,
                required_arguments=("command",),
                optional_arguments=("reference",),
                executor=create_agent_task_read_executor(execute_agent_task_read),
                enabled=True,
                llm_visible=True,
                requires_approval=False,
                approval_resume_enabled=False,
            )
        )
    if execute_agent_task_command is not None:
        specs.append(
            type(spec)(
                name=AGENT_TASK_COMMAND_TOOL_NAME,
                description=(
                    "Run deterministic MainAgent task/approval control-plane commands. "
                    "Use arguments.command as one of: "
                    f"{', '.join(AGENT_TASK_COMMANDS)}. "
                    "This may create/cancel local task records or approve/reject existing "
                    "approval records; approval itself is scoped to owner private chat."
                ),
                risk_level=RiskLevel.INTERNAL,
                required_arguments=("command",),
                optional_arguments=("reference", "goal", "query"),
                executor=create_agent_task_command_executor(execute_agent_task_command),
                enabled=True,
                llm_visible=False,
                requires_approval=False,
                approval_resume_enabled=False,
            )
        )
    if execute_owner_write_command is not None:
        specs.append(
            type(spec)(
                name=OWNER_WRITE_COMMAND_TOOL_NAME,
                description=(
                    "Request approval for a side-effecting owner QQ management command. "
                    "Use arguments.command as one of: "
                    f"{', '.join(OWNER_WRITE_COMMANDS)}. "
                    "This tool must stop for owner approval before execution."
                ),
                risk_level=RiskLevel.WRITE_LOCAL,
                required_arguments=("command",),
                optional_arguments=("query",),
                executor=create_owner_write_command_executor(execute_owner_write_command),
                enabled=True,
                llm_visible=True,
                requires_approval=True,
                approval_resume_enabled=True,
            )
        )
    return ToolRegistry(specs)


def create_owner_read_command_executor(
    execute_owner_read_command: OwnerReadCommandTool,
) -> ToolExecutor:
    async def execute_owner_read(arguments, context: ToolContext):
        command = str(arguments["command"]).strip()
        if command not in OWNER_READ_COMMANDS:
            allowed = ", ".join(OWNER_READ_COMMANDS)
            raise ToolExecutionError(
                f"unsupported owner read command: {command}; allowed: {allowed}"
            )
        return str(await _maybe_await(execute_owner_read_command(command, context)))

    return execute_owner_read


def create_agent_task_read_executor(
    execute_agent_task_read: AgentTaskReadTool,
) -> ToolExecutor:
    async def execute_task_read(arguments, context: ToolContext):
        command = str(arguments["command"]).strip()
        if command not in AGENT_TASK_READ_COMMANDS:
            allowed = ", ".join(AGENT_TASK_READ_COMMANDS)
            raise ToolExecutionError(
                f"unsupported agent task read command: {command}; allowed: {allowed}"
            )
        reference = str(arguments.get("reference") or "").strip()
        return str(await _maybe_await(execute_agent_task_read(command, reference, context)))

    return execute_task_read


def create_agent_task_command_executor(
    execute_agent_task_command: AgentTaskCommandTool,
) -> ToolExecutor:
    async def execute_task_command(arguments, context: ToolContext):
        command = str(arguments["command"]).strip()
        if command not in AGENT_TASK_COMMANDS:
            allowed = ", ".join(AGENT_TASK_COMMANDS)
            raise ToolExecutionError(
                f"unsupported agent task command: {command}; allowed: {allowed}"
            )
        reference = str(arguments.get("reference") or "").strip()
        goal = str(arguments.get("goal") or "").strip()
        return str(
            await _maybe_await(
                execute_agent_task_command(command, reference, goal, context)
            )
        )

    return execute_task_command


def create_owner_write_command_executor(
    execute_owner_write_command: OwnerWriteCommandTool,
) -> ToolExecutor:
    def execute_owner_write(arguments, context: ToolContext):
        command = str(arguments["command"]).strip()
        if command not in OWNER_WRITE_COMMANDS:
            allowed = ", ".join(OWNER_WRITE_COMMANDS)
            raise ToolExecutionError(
                f"unsupported owner write command: {command}; allowed: {allowed}"
            )
        return execute_owner_write_command(command, context)

    return execute_owner_write


def create_default_main_agent_planner(tool_registry: ToolRegistry) -> MainAgentHandler:
    return create_semantic_first_main_agent_planner(tool_registry, call_dev_context_stub_agent)


def create_semantic_first_main_agent_planner(
    tool_registry: ToolRegistry,
    fallback: MainAgentHandler,
) -> MainAgentHandler:
    async def plan(state: MainAgentState) -> MainAgentState:
        planned = plan_semantic_read_tool_request(tool_registry, state)
        if planned:
            return state
        return await _maybe_await(fallback(state))

    return plan


def plan_semantic_read_tool_request(
    tool_registry: ToolRegistry,
    state: MainAgentState,
) -> bool:
    if tool_registry.get(AGENT_TASK_COMMAND_TOOL_NAME) is not None:
        task_command = classify_agent_task_command(state.query)
        if task_command:
            command, reference, goal = task_command
            state.raw_action_request = agent_task_command_action_json(
                command,
                reference=reference,
                goal=goal,
                query=state.query,
                reason="semantic MainAgent task or approval control command",
            )
            return True
    if tool_registry.get(AGENT_TASK_READ_TOOL_NAME) is not None:
        task_command = classify_agent_task_read_command(state.query)
        if task_command:
            command, reference = task_command
            state.raw_action_request = agent_task_read_action_json(
                command,
                reference=reference,
                reason="semantic MainAgent task or approval read-only command",
            )
            return True
    if tool_registry.get(OWNER_READ_COMMAND_TOOL_NAME) is not None:
        command = classify_owner_read_command(state.query)
        if command:
            state.raw_action_request = owner_read_command_action_json(
                command,
                query=state.query,
                reason="semantic owner read-only QQ management command",
            )
            return True
    if tool_registry.get(OWNER_WRITE_COMMAND_TOOL_NAME) is not None:
        command = classify_owner_write_command(state.query)
        if command:
            state.raw_action_request = owner_write_command_action_json(
                command,
                query=state.query,
                reason="semantic owner side-effect QQ management command",
            )
            return True
    return False


def agent_task_read_action_json(
    command: str,
    *,
    reference: str = "",
    reason: str = "",
) -> str:
    arguments = {"command": command}
    if reference.strip():
        arguments["reference"] = reference.strip()
    return json.dumps(
        {
            "action": MainAgentAction.TOOL_REQUEST.value,
            "tool_name": AGENT_TASK_READ_TOOL_NAME,
            "arguments": arguments,
            "reason": reason,
        },
        ensure_ascii=False,
    )


def agent_task_command_action_json(
    command: str,
    *,
    reference: str = "",
    goal: str = "",
    query: str = "",
    reason: str = "",
) -> str:
    arguments = {"command": command}
    if reference.strip():
        arguments["reference"] = reference.strip()
    if goal.strip():
        arguments["goal"] = goal.strip()
    if query.strip():
        arguments["query"] = query.strip()
    return json.dumps(
        {
            "action": MainAgentAction.TOOL_REQUEST.value,
            "tool_name": AGENT_TASK_COMMAND_TOOL_NAME,
            "arguments": arguments,
            "reason": reason,
        },
        ensure_ascii=False,
    )


def owner_read_command_action_json(
    command: str,
    *,
    query: str = "",
    reason: str = "",
) -> str:
    arguments = {"command": command}
    if query.strip():
        arguments["query"] = query.strip()
    return json.dumps(
        {
            "action": MainAgentAction.TOOL_REQUEST.value,
            "tool_name": OWNER_READ_COMMAND_TOOL_NAME,
            "arguments": arguments,
            "reason": reason,
        },
        ensure_ascii=False,
    )


def owner_write_command_action_json(
    command: str,
    *,
    query: str = "",
    reason: str = "",
) -> str:
    arguments = {"command": command}
    if query.strip():
        arguments["query"] = query.strip()
    return json.dumps(
        {
            "action": MainAgentAction.TOOL_REQUEST.value,
            "tool_name": OWNER_WRITE_COMMAND_TOOL_NAME,
            "arguments": arguments,
            "reason": reason,
        },
        ensure_ascii=False,
    )


def call_dev_context_stub_agent(state: MainAgentState) -> MainAgentState:
    state.raw_action_request = dev_context_tool_action_json(
        state.query,
        reason="recover dev-side project context",
    )
    return state


def classify_owner_read_command(query: str) -> str:
    normalized = query.strip().lower()
    compact = re.sub(r"\s+", "", normalized)
    if not compact:
        return ""
    if any(
        marker in compact
        for marker in (
            "清空",
            "删除",
            "加入",
            "移出",
            "选择",
            "切换",
            "启用",
            "禁用",
            "添加",
            "压缩",
            "重建",
            "clear",
            "delete",
            "remove",
            "add",
            "select",
            "switch",
            "enable",
            "disable",
            "rebuild",
        )
    ):
        return ""

    if any(marker in compact for marker in ("整体状态", "机器人状态", "botstatus", "状态总览")):
        return "bot_status"
    if any(marker in compact for marker in ("最近错误", "报错", "错误日志", "recenterror", "recenterrors")):
        return "recent_errors"
    if (
        "配置状态" in compact
        or "configstatus" in compact
        or ("配置" in compact and any(marker in compact for marker in ("看", "查", "状态", "当前", "现在")))
    ):
        return "config_status"
    if any(marker in compact for marker in ("视觉状态", "识图", "ollama", "visionstatus")):
        return "vision_status"
    if any(marker in compact for marker in ("图片缓存状态", "图片缓存", "imagecachestatus")):
        return "image_cache_status"
    if any(marker in compact for marker in ("记忆状态", "memory状态", "memorystatus")):
        return "memory_status"
    if any(marker in compact for marker in ("rag状态", "ragstatus")):
        return "rag_status"
    if any(marker in compact for marker in ("摘要状态", "summarystatus")):
        return "summary_status"
    if any(marker in compact for marker in ("查看摘要", "最近摘要", "会话摘要", "summaries")):
        return "view_summaries"
    if any(marker in compact for marker in ("空窗摘要", "gapscene", "gapscenesummaries")):
        return "view_gap_scene_summaries"
    if any(marker in compact for marker in ("长期记忆", "长记忆", "longtermmemory", "longtermmemories")):
        return "view_long_term_memory"
    if any(marker in compact for marker in ("角色卡列表", "可选角色卡", "有哪些角色卡", "rolecardlist")):
        return "role_card_list"
    if any(marker in compact for marker in ("角色卡", "persona", "rolecard")):
        return "view_persona"
    if any(marker in compact for marker in ("语音状态", "tts状态", "ttsstatus", "语音模块")):
        return "tts_status"
    if any(marker in compact for marker in ("访问控制", "权限状态", "权限总览", "accessoverview", "accessstatus")):
        return "access_overview"
    if any(
        marker in compact
        for marker in (
            "模型配置",
            "模型状态",
            "主模型",
            "聊天模型",
            "mainagent模型",
            "mainllm",
            "chatllm",
            "modelconfig",
        )
    ):
        return "model_config_status"
    if any(
        marker in compact
        for marker in (
            "项目文档索引",
            "记忆索引",
            "索引详情",
            "rag索引",
            "rag详情",
            "indexdetail",
        )
    ):
        return "rag_index_detail"
    if any(
        marker in compact
        for marker in (
            "agent观测",
            "agent失败",
            "agent错误",
            "mainagent观测",
            "mainagent失败",
            "mainagent错误",
            "最近失败",
            "toolsummary失败",
            "llm失败",
        )
    ):
        return "main_agent_observations"
    if any(marker in compact for marker in ("群白名单", "群列表", "groupwhitelist")):
        return "group_whitelist"
    if any(marker in compact for marker in ("私聊白名单", "私聊名单", "privatewhitelist")):
        return "private_whitelist"
    if any(marker in compact for marker in ("黑名单", "blacklist")):
        return "blacklist"
    if any(marker in compact for marker in ("诊断", "体检", "自检", "diagnostics", "diagnose")):
        return "diagnostics"
    return ""


def classify_owner_write_command(query: str) -> str:
    normalized = query.strip().lower()
    compact = re.sub(r"\s+", "", normalized)
    if not compact:
        return ""
    if any(marker in compact for marker in ("清空图片缓存", "清理图片缓存", "清除图片缓存", "clearimagecache")):
        return "clear_image_cache"
    if any(marker in compact for marker in ("清空错误日志", "清理错误日志", "清除错误日志", "clearerrorlog")):
        return "clear_error_log"
    return ""


def classify_agent_task_command(query: str) -> tuple[str, str, str] | None:
    normalized = query.strip().lower()
    compact = re.sub(r"\s+", "", normalized)
    if not compact:
        return None

    reference = classify_task_reference(query)
    mentions_approval = any(marker in compact for marker in ("审批", "审核", "approval"))
    mentions_task = any(marker in compact for marker in ("任务", "待办", "task", "todo"))

    if mentions_approval and any(
        marker in compact
        for marker in ("确认", "同意", "通过", "批准", "approveapproval", "approve")
    ):
        return ("approve_approval", reference or "latest", "")
    if mentions_approval and any(
        marker in compact
        for marker in ("拒绝", "驳回", "否决", "rejectapproval", "reject")
    ):
        return ("reject_approval", reference or "latest", "")
    if mentions_task and any(marker in compact for marker in ("取消", "撤销", "cancel")):
        return ("cancel_task", reference or "latest", "")

    drill_goal = extract_semantic_goal_after_markers(
        query,
        (
            "帮我创建审批演练",
            "创建审批演练",
            "审批演练",
            "模拟审批",
            "approval drill",
        ),
    )
    if drill_goal is not None:
        return ("create_approval_drill", "", drill_goal)

    task_goal = extract_semantic_task_goal(query)
    if task_goal is not None:
        return ("create_task", "", task_goal)
    return None


def extract_semantic_task_goal(query: str) -> str | None:
    compact = re.sub(r"\s+", "", query.strip().lower())
    if not any(marker in compact for marker in ("任务", "待办", "task", "todo")):
        return None

    suffix_match = re.search(
        r"^(?:帮我)?(?:把)?(.+?)(?:加入|加到|添加到|放进|记成|作为)(?:任务|待办)$",
        query.strip(),
        re.IGNORECASE,
    )
    if suffix_match:
        goal = _strip_wrapping_punctuation(suffix_match.group(1))
        return goal or None

    return extract_semantic_goal_after_markers(
        query,
        (
            "帮我创建一个任务",
            "帮我创建任务",
            "帮我新增一个任务",
            "帮我新增任务",
            "帮我添加一个任务",
            "帮我添加任务",
            "帮我记录一个任务",
            "帮我记录任务",
            "帮我记一个任务",
            "帮我记下一个任务",
            "创建一个任务",
            "创建任务",
            "新增一个任务",
            "新增任务",
            "添加一个任务",
            "添加任务",
            "记录一个任务",
            "记录任务",
            "记一个任务",
            "记下一个任务",
            "新增待办",
            "添加待办",
            "记录待办",
            "new task",
            "add task",
            "create task",
            "todo",
        ),
    )


def extract_semantic_goal_after_markers(
    query: str,
    markers: tuple[str, ...],
) -> str | None:
    stripped = query.strip()
    lowered = stripped.lower()
    for marker in sorted(markers, key=len, reverse=True):
        marker_lower = marker.lower()
        if lowered == marker_lower:
            return ""
        if lowered.startswith(marker_lower):
            return _strip_wrapping_punctuation(stripped[len(marker):])
    return None


def _strip_wrapping_punctuation(value: str) -> str:
    stripped = value.strip()
    while stripped and stripped[0] in " ：:，,。.-—":
        stripped = stripped[1:].strip()
    pairs = (("“", "”"), ("‘", "’"), ('"', '"'), ("'", "'"), ("`", "`"))
    changed = True
    while changed and len(stripped) >= 2:
        changed = False
        for left, right in pairs:
            if stripped.startswith(left) and stripped.endswith(right):
                stripped = stripped[len(left) : -len(right)].strip()
                changed = True
    return stripped


def classify_agent_task_read_command(query: str) -> tuple[str, str] | None:
    normalized = query.strip().lower()
    compact = re.sub(r"\s+", "", normalized)
    if not compact:
        return None

    reference = classify_task_reference(query)
    asks_detail = any(marker in compact for marker in ("详情", "详细", "事件", "最新", "最近", "detail", "events"))
    asks_list = any(
        marker in compact
        for marker in ("列表", "状态", "有哪些", "有没有", "当前", "现在", "任务卡", "任务表", "list", "status")
    )
    mentions_approval = any(marker in compact for marker in ("审批", "审核", "approval", "approvals"))
    mentions_task = any(marker in compact for marker in ("任务", "待办", "task", "todo"))

    if mentions_approval:
        if asks_detail:
            return ("approval_detail", reference or "latest")
        if asks_list or any(marker in compact for marker in ("待审批", "待审核")):
            return ("list_approvals", "")
    if mentions_task:
        if asks_detail:
            return ("task_detail", reference or "latest")
        if asks_list:
            return ("list_tasks", "")
    return None


def classify_task_reference(query: str) -> str:
    compact = re.sub(r"\s+", "", query.strip().lower())
    if any(marker in compact for marker in ("最新", "最近", "last", "latest")):
        return "latest"
    match = re.search(r"(?:#|id[:：]?|编号[:：]?)(\d+)", query, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"\b(\d{1,9})\b", query)
    if match:
        return match.group(1)
    return ""


def validate_main_agent_action_request(state: MainAgentState) -> MainAgentState:
    return create_main_agent_action_validator(create_default_main_agent_tool_registry())(state)


def create_main_agent_action_validator(tool_registry: ToolRegistry) -> MainAgentHandler:
    def validate_action_request(state: MainAgentState) -> MainAgentState:
        try:
            action_request = parse_main_agent_action_request(
                state.raw_action_request,
                tool_registry=tool_registry,
            )
        except MainAgentActionRequestError as exc:
            state.response_text = f"MainAgentGraph rejected: {exc}"
            state.error = "invalid_action_request"
            return state
        return apply_action_request_to_state(state, action_request)

    return validate_action_request


def check_read_only_tool_policy(state: MainAgentState) -> MainAgentState:
    if state.action != MainAgentAction.TOOL_REQUEST.value:
        return state

    decision = decide_tool_policy(
        ToolPolicyInput(
            risk_level=RiskLevel.INTERNAL,
            is_owner=state.is_owner,
            is_group=state.is_group,
        )
    )
    state.policy_decision = decision.type.value
    state.policy_reason = decision.reason
    if not decision.allowed:
        state.response_text = f"MainAgentGraph rejected: {decision.reason}"
        state.error = "policy_denied"
    return state


def create_tool_policy_checker(
    *,
    risk_level_for_tool: ToolRiskResolver,
    request_approval: ApprovalRequestHandler | None = None,
    enable_external_read: bool = False,
    enable_local_write: bool = False,
    enable_external_write: bool = False,
) -> MainAgentHandler:
    async def check_tool_policy(state: MainAgentState) -> MainAgentState:
        if state.action != MainAgentAction.TOOL_REQUEST.value:
            return state

        risk_level = risk_level_for_tool(state)
        decision = decide_tool_policy(
            ToolPolicyInput(
                risk_level=risk_level,
                is_owner=state.is_owner,
                is_group=state.is_group,
                enable_external_read=enable_external_read,
                enable_local_write=enable_local_write,
                enable_external_write=enable_external_write,
            )
        )
        state.policy_decision = decision.type.value
        state.policy_reason = decision.reason
        state.metadata["risk_level"] = risk_level.value

        if decision.allowed:
            return state

        if decision.type == PolicyDecisionType.REQUIRE_APPROVAL:
            state.metadata["approval_required"] = True
            state.metadata["approval_tool_name"] = state.requested_tool
            state.metadata["approval_reason"] = decision.reason
            if request_approval is not None:
                state.response_text = str(
                    await _maybe_await(request_approval(state, risk_level, decision.reason))
                )
            else:
                state.response_text = (
                    "MainAgentGraph approval required: "
                    f"{decision.reason or risk_level.value}"
                )
            state.error = "approval_required"
            return state

        state.response_text = f"MainAgentGraph rejected: {decision.reason}"
        state.error = "policy_denied"
        return state

    return check_tool_policy


def create_read_only_tool_executor(
    retrieve_dev_context: ReadOnlyDevContextTool,
) -> MainAgentHandler:
    return create_tool_registry_executor(
        create_read_only_main_agent_tool_registry(retrieve_dev_context)
    )


def create_tool_registry_executor(tool_registry: ToolRegistry) -> MainAgentHandler:
    async def execute_tool(state: MainAgentState) -> MainAgentState:
        if state.action != MainAgentAction.TOOL_REQUEST.value:
            return state

        try:
            arguments = state.metadata.get("tool_arguments", {})
            if not isinstance(arguments, dict):
                arguments = {}
            result = await tool_registry.execute(
                state.requested_tool,
                dict(arguments),
                ToolContext(
                    query=state.query,
                    is_owner=state.is_owner,
                    is_group=state.is_group,
                    metadata=dict(state.metadata),
                ),
            )
            state.tool_result = result.text
            if result.metadata:
                state.metadata["tool_result_metadata"] = dict(result.metadata)
        except ToolExecutionError as exc:
            state.response_text = f"MainAgentGraph tool failed: {exc}"
            state.error = "tool_execution_failed"
        except Exception as exc:
            state.response_text = f"MainAgentGraph read-only tool failed: {exc}"
            state.error = "tool_execution_failed"
        return state

    return execute_tool


def render_read_only_agent_response(state: MainAgentState) -> MainAgentState:
    if state.action != MainAgentAction.TOOL_REQUEST.value:
        return state
    state.response_text = "\n".join(
        [
            "MainAgentGraph read-only tool result:",
            f"tool: {state.requested_tool}",
            f"policy: {state.policy_decision}",
            "",
            state.tool_result,
        ]
    ).strip()
    return state


def render_concise_read_only_agent_response(state: MainAgentState) -> MainAgentState:
    if state.action != MainAgentAction.TOOL_REQUEST.value:
        return state
    if state.requested_tool != MainAgentToolName.DEV_CONTEXT.value:
        state.response_text = state.tool_result.strip()
        return state
    state.response_text = format_concise_dev_context_result(
        state.tool_result,
        tool_name=state.requested_tool,
        policy_decision=state.policy_decision,
        query=state.tool_query,
    )
    return state


def create_tool_summary_renderer(
    summarize_tool_result: MainAgentHandler,
    *,
    fallback_renderer: MainAgentHandler,
) -> MainAgentHandler:
    async def render_with_tool_summary(state: MainAgentState) -> MainAgentState:
        if state.action != MainAgentAction.TOOL_REQUEST.value:
            return state
        if state.requested_tool != MainAgentToolName.DEV_CONTEXT.value:
            return await _maybe_await(fallback_renderer(state))
        try:
            state = await _maybe_await(summarize_tool_result(state))
        except Exception as exc:
            state.metadata["tool_summary_error"] = str(exc)
            state.metadata["tool_summary_error_type"] = type(exc).__name__
            state = await _maybe_await(fallback_renderer(state))
        if not state.response_text:
            state = await _maybe_await(fallback_renderer(state))
        return state

    return render_with_tool_summary


def format_concise_dev_context_result(
    tool_result: str,
    *,
    tool_name: str,
    policy_decision: str,
    query: str,
) -> str:
    project_count = _first_count(tool_result, ("project docs:", "项目文档命中："))
    memory_count = _first_count(tool_result, ("memories:", "记忆命中："))
    titles = _numbered_titles(tool_result, limit=3)

    lines = [
        "MainAgentGraph read-only summary:",
        f"tool: {tool_name}",
        f"policy: {policy_decision}",
        f"query: {query}",
    ]
    if project_count is not None:
        lines.append(f"project docs: {project_count}")
    if memory_count is not None:
        lines.append(f"memories: {memory_count}")
    if titles:
        lines.append("")
        lines.append("top matches:")
        lines.extend(f"{index}. {title}" for index, title in enumerate(titles, 1))
    lines.append("")
    lines.append("Use /agent-debug <query> for raw dev_context output.")
    return "\n".join(lines).strip()


def _first_count(text: str, labels: tuple[str, ...]) -> int | None:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*(\d+)", text)
        if match:
            return int(match.group(1))
    return None


def _numbered_titles(text: str, *, limit: int) -> list[str]:
    titles: list[str] = []
    for line in text.splitlines():
        match = re.match(r"\s*\d+\.\s+(.+)", line)
        if not match:
            continue
        title = match.group(1).strip()
        if title and title not in titles:
            titles.append(title)
        if len(titles) >= limit:
            break
    return titles
