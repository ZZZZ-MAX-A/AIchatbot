from __future__ import annotations

import inspect
import json
import re
from collections.abc import Awaitable, Callable
from typing import TypeAlias

from ..document_artifacts import (
    DOCUMENT_ARTIFACT_COMMANDS,
    DOCUMENT_ARTIFACT_MAX_CONTENT_CHARS,
    DOCUMENT_ARTIFACT_MAX_SLIDES,
    DOCUMENT_ARTIFACT_MAX_TITLE_CHARS,
    presentation_slide_count,
)
from ..failure_diagnostics import format_failure_user_message
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
DOCUMENT_DELIVERY_TOOL_NAME = "document_delivery_command"
AGENT_TASK_READ_TOOL_NAME = "agent_task_read"
AGENT_TASK_COMMAND_TOOL_NAME = "agent_task_command"
OWNER_READ_COMMANDS: tuple[str, ...] = (
    "bot_status",
    "ops_health",
    "vision_troubleshoot",
    "memory_rag_troubleshoot",
    "diagnostics",
    "config_status",
    "vision_status",
    "recent_errors",
    "image_cache_status",
    "memory_status",
    "memory_retrieval",
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
    "root_graph_observations",
)
AGENT_TASK_READ_COMMANDS: tuple[str, ...] = (
    "next_step",
    "workbench",
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
)
DOCUMENT_DELIVERY_COMMANDS: tuple[str, ...] = (
    "create_and_send_txt_document",
    "create_and_send_word_document",
    "create_and_send_presentation",
)
DOCUMENT_INTERNAL_SCAFFOLD_MARKERS: tuple[str, ...] = (
    "Read-only project context:",
    "Runtime metadata (not user content",
    "MainAgentGraph read-only local test mode.",
    "MainAgent runtime metadata; this is not user-provided document content.",
    "Allowed tools:",
    "Registered visible tools:",
    "Disallowed: shell, file writes, QQ sends, external writes.",
    "Owner query (the only user instruction",
    "User query:\n",
    "Return the ActionRequest JSON object now.",
)
ACCESS_WRITE_COMMANDS: tuple[str, ...] = (
    "allow_group",
    "deny_group",
    "allow_private",
    "deny_private",
    "block_user",
    "unblock_user",
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
    execute_document_delivery_command: OwnerWriteCommandTool | None = None,
    execute_agent_task_read: AgentTaskReadTool | None = None,
    execute_agent_task_command: AgentTaskCommandTool | None = None,
    request_approval: ApprovalRequestHandler | None = None,
    llm_call: MainAgentLLMCall | None = None,
    call_main_agent: MainAgentHandler | None = None,
    summarize_tool_result: MainAgentHandler | None = None,
    render_mode: str = "raw",
    tool_registry: ToolRegistry | None = None,
    enable_external_write: bool = False,
) -> MainAgentGraphRunner:
    active_tool_registry = tool_registry or create_read_only_main_agent_tool_registry(
        retrieve_dev_context,
        execute_owner_read_command=execute_owner_read_command,
        execute_owner_write_command=execute_owner_write_command,
        execute_document_delivery_command=execute_document_delivery_command,
        execute_agent_task_read=execute_agent_task_read,
        execute_agent_task_command=execute_agent_task_command,
    )
    agent_call = call_main_agent
    if agent_call is None and llm_call is not None:
        agent_call = create_main_agent_call_handler(
            llm_call,
            tool_registry=active_tool_registry,
        )
    if agent_call is None:
        agent_call = call_safe_no_llm_fallback_agent
    agent_call = create_semantic_first_main_agent_planner(active_tool_registry, agent_call)

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
        build_agent_context=create_read_only_agent_context_builder(active_tool_registry),
        call_main_agent=agent_call,
        validate_action_request=create_main_agent_action_validator(active_tool_registry),
        check_tool_policy=create_tool_policy_checker(
            risk_level_for_tool=lambda state: active_tool_registry.require(
                state.requested_tool
            ).risk_level,
            enable_local_write=any(
                spec.risk_level == RiskLevel.WRITE_LOCAL
                for spec in active_tool_registry.visible_specs()
            ),
            enable_external_write=enable_external_write,
            request_approval=request_approval,
        ),
        execute_tool=create_tool_registry_executor(active_tool_registry),
        render_agent_response=render_agent_response,
    )


def create_read_only_main_agent_runtime_handler(
    *,
    retrieve_dev_context: ReadOnlyDevContextTool,
    execute_owner_read_command: OwnerReadCommandTool | None = None,
    execute_owner_write_command: OwnerWriteCommandTool | None = None,
    execute_document_delivery_command: OwnerWriteCommandTool | None = None,
    execute_agent_task_read: AgentTaskReadTool | None = None,
    execute_agent_task_command: AgentTaskCommandTool | None = None,
    request_approval: ApprovalRequestHandler | None = None,
    llm_call: MainAgentLLMCall | None = None,
    call_main_agent: MainAgentHandler | None = None,
    summarize_tool_result: MainAgentHandler | None = None,
    render_mode: str = "raw",
    tool_registry: ToolRegistry | None = None,
    enable_external_write: bool = False,
):
    runner = create_read_only_main_agent_runner(
        retrieve_dev_context=retrieve_dev_context,
        execute_owner_read_command=execute_owner_read_command,
        execute_owner_write_command=execute_owner_write_command,
        execute_document_delivery_command=execute_document_delivery_command,
        execute_agent_task_read=execute_agent_task_read,
        execute_agent_task_command=execute_agent_task_command,
        request_approval=request_approval,
        llm_call=llm_call,
        call_main_agent=call_main_agent,
        summarize_tool_result=summarize_tool_result,
        render_mode=render_mode,
        tool_registry=tool_registry,
        enable_external_write=enable_external_write,
    )

    async def handle_main_agent(state: RuntimeState) -> RuntimeResponse:
        command_artifact = state.artifacts.get("main_agent_command", {})
        if not isinstance(command_artifact, dict):
            command_artifact = {}
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
                "explicit_dev_context": bool(
                    command_artifact.get("explicit_dev_context")
                ),
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
        has_external_document_delivery = tool_registry.get(DOCUMENT_DELIVERY_TOOL_NAME) is not None
        state.metadata["mode"] = "read_only"
        state.metadata["allowed_tools"] = visible_tools
        state.metadata.setdefault(
            "agent_context",
            "\n".join(
                [
                    "MainAgent runtime metadata; this is not user-provided document content.",
                    f"Registered visible tools: {', '.join(visible_tools)}.",
                    "Use the owner query as the only user instruction.",
                    "Never copy these metadata labels, tool lists, or safety text into a document title or body.",
                    (
                        "Document delivery is available only through the explicit approval-gated "
                        "document_delivery_command."
                        if has_external_document_delivery
                        else "Document delivery is not currently registered."
                    ),
                    "Disallowed: shell, arbitrary paths, project-file writes, and unregistered external actions.",
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
    execute_document_delivery_command: OwnerWriteCommandTool | None = None,
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
                    "select_persona also requires arguments.target. "
                    "add_fact_memory and add_preference_memory also require arguments.content. "
                    "delete_session_summary also requires arguments.summary_id. "
                    "access-control commands also require numeric arguments.target. "
                    "create_txt_document, create_word_document, and create_presentation "
                    "require arguments.title and arguments.content. Generate complete "
                    "document content before requesting the tool; use Markdown-style "
                    "headings and bullets, with '## ' headings as slide boundaries for PPT. "
                    "For PPT, do not create a separate cover section because the renderer "
                    "adds the title slide; keep at most 12 content slides and at most 6 "
                    "non-empty body lines per slide. The hard limit is 20 total slides "
                    "including automatic continuation slides and the title slide. Start "
                    "PPT content directly with '## ' sections, not a repeated '# ' title. "
                    "Build a coherent story; each slide should communicate one main idea "
                    "with 3-5 concise bullets rather than generic filler. "
                    "Artifacts are created only in the fixed ignored workspace and are not "
                    "sent through QQ. "
                    "This tool must stop for owner approval before execution."
                ),
                risk_level=RiskLevel.WRITE_LOCAL,
                required_arguments=("command",),
                optional_arguments=(
                    "query",
                    "target",
                    "title",
                    "content",
                    "summary_id",
                ),
                executor=create_owner_write_command_executor(execute_owner_write_command),
                enabled=True,
                llm_visible=True,
                requires_approval=True,
                approval_resume_enabled=True,
            )
        )
    if execute_document_delivery_command is not None:
        specs.append(
            type(spec)(
                name=DOCUMENT_DELIVERY_TOOL_NAME,
                description=(
                    "Create one TXT, Word, or PowerPoint artifact in the fixed ignored "
                    "workspace and send it once to the current owner private QQ chat after "
                    "approval. Use arguments.command as one of: "
                    f"{', '.join(DOCUMENT_DELIVERY_COMMANDS)}. "
                    "Requires arguments.title and arguments.content. This is an external "
                    "write: no group, no non-owner, no arbitrary recipient, no path, no retry. "
                    "For PPT, the renderer adds the title slide: do not add a separate cover "
                    "section, keep at most 12 '## ' content sections and at most 6 non-empty "
                    "body lines per section. The hard limit is 20 total rendered slides, "
                    "including continuation slides created after every 8 body lines. Start "
                    "content directly with '## ' sections, never repeat the deck title as "
                    "'# '. Use a coherent overview-to-capabilities-to-boundaries-to-next-steps "
                    "story, one main idea and 3-5 concise bullets per slide."
                ),
                risk_level=RiskLevel.WRITE_EXTERNAL,
                required_arguments=("command",),
                optional_arguments=("query", "title", "content"),
                executor=create_document_delivery_command_executor(
                    execute_document_delivery_command
                ),
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
        argument_error = owner_write_argument_error(dict(arguments))
        if argument_error:
            raise ToolExecutionError(argument_error)
        metadata = dict(context.metadata)
        metadata["tool_arguments"] = dict(arguments)
        next_context = ToolContext(
            query=context.query,
            is_owner=context.is_owner,
            is_group=context.is_group,
            metadata=metadata,
        )
        return execute_owner_write_command(command, next_context)

    return execute_owner_write


def create_document_delivery_command_executor(
    execute_document_delivery_command: OwnerWriteCommandTool,
) -> ToolExecutor:
    def execute_delivery(arguments, context: ToolContext):
        command = str(arguments["command"]).strip()
        if command not in DOCUMENT_DELIVERY_COMMANDS:
            allowed = ", ".join(DOCUMENT_DELIVERY_COMMANDS)
            raise ToolExecutionError(
                f"unsupported document delivery command: {command}; allowed: {allowed}"
            )
        render_command = command.replace("create_and_send_", "create_", 1)
        argument_error = owner_write_argument_error(
            {
                "command": render_command,
                "title": arguments.get("title"),
                "content": arguments.get("content"),
            }
        )
        if argument_error:
            raise ToolExecutionError(argument_error)
        metadata = dict(context.metadata)
        metadata["tool_arguments"] = dict(arguments)
        next_context = ToolContext(
            query=context.query,
            is_owner=context.is_owner,
            is_group=context.is_group,
            metadata=metadata,
        )
        return execute_document_delivery_command(command, next_context)

    return execute_delivery


def create_default_main_agent_planner(tool_registry: ToolRegistry) -> MainAgentHandler:
    return create_semantic_first_main_agent_planner(
        tool_registry,
        call_safe_no_llm_fallback_agent,
    )


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
    if (
        tool_registry.get(DOCUMENT_DELIVERY_TOOL_NAME) is not None
        and document_request_references_missing_prior_content(state.query)
    ):
        state.raw_action_request = ask_owner_action_json(
            "MainAgent 不读取上一条 QQ 消息作为文档正文。请在同一条 "
            "/agent 请求中粘贴完整正文，或只给出主题并明确让 "
            "MainAgent 自行撰写。本次未创建审批、未生成文件、未发送 QQ。",
            reason="document request references unavailable prior-message content",
        )
        return True
    if (
        is_document_artifact_request(state.query)
        and (
            tool_registry.get(DOCUMENT_DELIVERY_TOOL_NAME) is not None
            or tool_registry.get(OWNER_WRITE_COMMAND_TOOL_NAME) is not None
        )
    ):
        # Document outlines naturally contain words such as "status", "task", and
        # "next step". They belong to the requested body and must not be consumed by
        # deterministic management classifiers before the document-capable Main LLM.
        return False
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
            tool_query = (
                extract_owner_memory_retrieval_query(state.query)
                if command == "memory_retrieval"
                else state.query
            )
            state.raw_action_request = owner_read_command_action_json(
                command,
                query=tool_query,
                reason="semantic owner read-only QQ management command",
            )
            return True
    if tool_registry.get(OWNER_WRITE_COMMAND_TOOL_NAME) is not None:
        need_argument_message = owner_write_need_argument_message(state.query)
        if need_argument_message:
            state.raw_action_request = ask_owner_action_json(
                need_argument_message,
                reason="semantic owner write command needs an explicit argument",
            )
            return True
        command = classify_owner_write_command(state.query)
        if command:
            target = extract_owner_write_command_target(command, state.query)
            content = extract_owner_write_command_content(command, state.query)
            summary_id = extract_owner_write_command_summary_id(command, state.query)
            state.raw_action_request = owner_write_command_action_json(
                command,
                query=state.query,
                target=target,
                content=content,
                summary_id=summary_id,
                reason="semantic owner side-effect QQ management command",
            )
            return True
    if (
        bool(state.metadata.get("explicit_dev_context"))
        and tool_registry.get(MainAgentToolName.DEV_CONTEXT.value) is not None
    ):
        state.raw_action_request = dev_context_tool_action_json(
            state.query,
            reason="explicit owner development-context query",
        )
        return True
    return False


def is_document_artifact_request(query: str) -> bool:
    stripped = query.strip()
    if not stripped:
        return False
    compact = re.sub(r"\s+", "", stripped.lower())
    mentions_document = any(
        marker in compact
        for marker in ("word", "docx", "ppt", "pptx", "txt", "文档", "幻灯片")
    )
    requests_creation = any(
        marker in compact
        for marker in (
            "生成",
            "写一份",
            "写个",
            "撰写",
            "制作",
            "create",
            "generate",
            "write",
        )
    )
    return mentions_document and requests_creation


def document_request_references_missing_prior_content(query: str) -> bool:
    stripped = query.strip()
    if not stripped:
        return False
    compact = re.sub(r"\s+", "", stripped.lower())
    references_prior_content = any(
        marker in compact
        for marker in (
            "我刚才提供",
            "刚才提供",
            "上一条内容",
            "上一条消息",
            "上面的内容",
            "上述内容",
            "之前提供",
            "previouscontent",
            "previousmessage",
            "abovecontent",
        )
    )
    if not (is_document_artifact_request(stripped) and references_prior_content):
        return False
    # A genuinely inlined document is normally long and multiline. Short, single-line
    # references are always treated as missing history instead of being guessed.
    return len(stripped) < 500 or "\n" not in stripped


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
    target: str = "",
    title: str = "",
    content: str = "",
    summary_id: str = "",
    reason: str = "",
) -> str:
    arguments = {"command": command}
    if query.strip():
        arguments["query"] = query.strip()
    if target.strip():
        arguments["target"] = target.strip()
    if title.strip():
        arguments["title"] = title.strip()
    if content.strip():
        arguments["content"] = content.strip()
    if summary_id.strip():
        arguments["summary_id"] = summary_id.strip()
    return json.dumps(
        {
            "action": MainAgentAction.TOOL_REQUEST.value,
            "tool_name": OWNER_WRITE_COMMAND_TOOL_NAME,
            "arguments": arguments,
            "reason": reason,
        },
        ensure_ascii=False,
    )


def ask_owner_action_json(content: str, *, reason: str = "") -> str:
    return json.dumps(
        {
            "action": MainAgentAction.ASK_OWNER.value,
            "content": content.strip(),
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


def call_safe_no_llm_fallback_agent(state: MainAgentState) -> MainAgentState:
    if bool(state.metadata.get("explicit_dev_context")):
        return call_dev_context_stub_agent(state)
    state.raw_action_request = ask_owner_action_json(
        (
            "我还不能确定你的主要目的。\n"
            "你可以重新发送一条完整命令，例如：\n"
            "- 系统概览：/agent 执行系统诊断任务\n"
            "- 视觉状态：/agent 查看视觉状态\n"
            "- 语音状态：/agent 语音状态怎么样\n"
            "- MemoryRAG 状态：/agent RAG 状态\n"
            "- 研发资料：/agent 查 <问题>\n"
            "- 任务与审批：/agent 任务状态\n"
            "本次没有执行工具，没有查询 RAG，也没有修改任何状态。"
        ),
        reason="no deterministic route matched and Main LLM is unavailable",
    )
    return state


def classify_owner_read_command(query: str) -> str:
    normalized = query.strip().lower()
    compact = re.sub(r"\s+", "", normalized)
    if not compact:
        return ""
    if is_owner_write_intent_query(query):
        return ""
    if is_owner_memory_rag_troubleshoot_query(compact):
        return "memory_rag_troubleshoot"
    if is_owner_memory_retrieval_query(query, compact):
        return "memory_retrieval"
    if any(
        marker in compact
        for marker in (
            "清空",
            "删除",
            "加入",
            "移出",
            "允许",
            "拉黑",
            "解除拉黑",
            "放进",
            "踢出",
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
    if is_owner_vision_troubleshoot_query(compact):
        return "vision_troubleshoot"
    if is_owner_ops_health_query(compact):
        return "ops_health"
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
    if is_owner_voice_status_query(compact):
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
            "rootgraph观测",
            "rootgraph最近观测",
            "rootgraph最新观测",
            "rootgraph状态",
            "rootgraph最近状态",
            "rootgraph最新状态",
            "rootgraph路由",
            "rootgraph最近路由",
            "rootgraph最新路由",
            "rootgraph提交",
            "rootgraph最近提交",
            "rootgraph最新提交",
            "rootgraphcommit",
            "rootgraphruntime",
            "普通聊天观测",
            "聊天观测",
            "聊天路由",
            "聊天提交",
            "chatruntime",
            "chatcommit",
            "chatroute",
        )
    ):
        return "root_graph_observations"
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


def is_owner_voice_status_query(compact: str) -> bool:
    voice_markers = ("语音", "tts", "indextts2")
    if not any(marker in compact for marker in voice_markers):
        return False
    direct_status_markers = (
        "语音状态",
        "tts状态",
        "ttsstatus",
        "语音模块",
        "检查tts",
        "查看tts",
        "看看tts",
        "是否正常",
        "正常吗",
        "是否在线",
        "在线吗",
        "是不是挂了",
        "是否挂了",
        "加载了吗",
        "是否加载",
        "是不是没加载",
        "是否异常",
        "有没有异常",
    )
    return any(marker in compact for marker in direct_status_markers)


def is_owner_ops_health_query(compact: str) -> bool:
    broad_markers = (
        "综合诊断",
        "聚合诊断",
        "合并诊断",
        "整体诊断",
        "全局诊断",
        "系统诊断",
        "健康检查",
        "健康状态",
        "健康自检",
        "可靠性巡检",
        "周期巡检",
        "定期巡检",
        "opshealth",
        "healthcheck",
    )
    if any(marker in compact for marker in broad_markers):
        return True

    vision_markers = ("视觉", "识图", "图片", "qwen", "qwen2.5", "vision")
    rag_markers = ("rag", "记忆", "embedding", "bge", "bge-m3", "memory")
    error_markers = ("错误", "报错", "失败", "问题", "异常")
    check_markers = ("诊断", "检查", "自检", "状态", "看看", "看一下")

    has_vision = any(marker in compact for marker in vision_markers)
    has_rag = any(marker in compact for marker in rag_markers)
    has_error = any(marker in compact for marker in error_markers)
    has_check = any(marker in compact for marker in check_markers)

    if has_vision and has_rag:
        return True
    if "ollama" in compact and (has_rag or has_vision or has_error or has_check):
        return True
    return (has_vision or has_rag) and has_error and has_check


def is_owner_vision_troubleshoot_query(compact: str) -> bool:
    vision_markers = ("视觉", "识图", "图片识别", "图片看", "看图", "vision", "image")
    rag_markers = ("rag", "记忆", "embedding", "bge", "memory")
    troubleshoot_markers = (
        "完整排查",
        "排查",
        "排障",
        "诊断",
        "为什么",
        "失败",
        "异常",
        "问题",
        "不能识别",
        "识别不了",
        "看不懂",
        "troubleshoot",
        "diagnose",
        "failed",
        "error",
    )
    return (
        any(marker in compact for marker in vision_markers)
        and any(marker in compact for marker in troubleshoot_markers)
        and not any(marker in compact for marker in rag_markers)
    )


def is_owner_memory_rag_troubleshoot_query(compact: str) -> bool:
    memory_markers = (
        "memoryrag",
        "rag",
        "记忆检索",
        "检索记忆",
        "记忆召回",
        "召回记忆",
        "语义记忆",
        "长期记忆",
        "记忆索引",
        "embedding",
        "向量",
        "索引",
        "memory",
    )
    vision_markers = ("视觉", "识图", "图片", "看图", "vision", "image")
    troubleshoot_markers = (
        "完整排查",
        "排查",
        "排障",
        "诊断",
        "为什么",
        "失败",
        "异常",
        "问题",
        "不能检索",
        "检索不到",
        "没有召回",
        "召回不到",
        "搜不到",
        "查不到",
        "troubleshoot",
        "diagnose",
        "failed",
        "error",
    )
    return (
        any(marker in compact for marker in memory_markers)
        and any(marker in compact for marker in troubleshoot_markers)
        and not any(marker in compact for marker in vision_markers)
    )


def is_owner_memory_retrieval_query(query: str, compact: str) -> bool:
    if any(
        marker in compact
        for marker in (
            "记忆检索",
            "检索记忆",
            "搜索记忆",
            "查找记忆",
            "memoryretrieval",
            "memorysearch",
        )
    ):
        return True
    if any(
        marker in compact
        for marker in ("记忆里有没有", "记忆中有没有", "记忆里是否有", "记忆中是否有")
    ):
        return True
    return bool(
        re.search(
            r"^(?:帮我)?(?:查|找|检索|搜索)(?:一下)?(?:长期)?记忆(?:里|中)?[：:，,\s]+.+",
            query.strip(),
            re.IGNORECASE,
        )
    )


def extract_owner_memory_retrieval_query(query: str) -> str:
    markers = (
        "帮我查一下记忆里有没有",
        "帮我查一下记忆中有没有",
        "查一下记忆里有没有",
        "查一下记忆中有没有",
        "帮我检索记忆",
        "帮我搜索记忆",
        "帮我查找记忆",
        "帮我查记忆",
        "记忆检索",
        "检索记忆",
        "搜索记忆",
        "查找记忆",
        "查记忆",
        "memory retrieval",
        "memory search",
    )
    goal = extract_semantic_goal_after_markers(query, markers)
    if goal is not None:
        return goal
    match = re.search(
        r"(?:记忆里|记忆中|长期记忆里|长期记忆中)(?:有没有|是否有|有无)(.+)",
        query.strip(),
        re.IGNORECASE,
    )
    if match:
        return _strip_wrapping_punctuation(match.group(1))
    return query.strip()


def classify_owner_write_command(query: str) -> str:
    normalized = query.strip().lower()
    compact = re.sub(r"\s+", "", normalized)
    if not compact:
        return ""
    if any(marker in compact for marker in ("清空图片缓存", "清理图片缓存", "清除图片缓存", "clearimagecache")):
        return "clear_image_cache"
    if any(marker in compact for marker in ("清空错误日志", "清理错误日志", "清除错误日志", "clearerrorlog")):
        return "clear_error_log"
    if any(
        marker in compact
        for marker in (
            "清空当前摘要",
            "清除当前摘要",
            "清理当前摘要",
            "清空当前对话摘要",
            "清空当前会话摘要",
            "clearsessionsummaries",
            "clearcurrentsummaries",
        )
    ):
        return "clear_session_summaries"
    if extract_owner_delete_summary_id(query):
        return "delete_session_summary"
    access_command = classify_owner_access_write_command(query)
    if access_command:
        return access_command
    if extract_owner_fact_memory_content(query):
        return "add_fact_memory"
    if extract_owner_preference_memory_content(query):
        return "add_preference_memory"
    if extract_owner_persona_target(query):
        return "select_persona"
    return ""


def owner_write_need_argument_message(query: str) -> str:
    if is_disallowed_owner_write_intent(query):
        return (
            "这个 /agent 写操作当前不开放。\n"
            "当前只支持审批门控的单步主人管理写命令；不支持清空全部上下文、清空全部摘要或删除长期记忆。\n"
            "当前尚未创建审批，也没有执行任何清理、删除或修改。"
        )
    if is_owner_delete_summary_intent(query) and not extract_owner_delete_summary_id(query):
        return (
            "删除当前会话摘要需要明确的数字摘要 ID。\n"
            "请先用 /agent 查看摘要 找到要删除的 ID，然后发送：/agent 删除摘要 <摘要ID>。\n"
            "当前尚未创建审批，也没有删除任何摘要。"
        )
    if is_owner_select_persona_intent(query) and not extract_owner_persona_target(query):
        return (
            "选择角色卡需要明确的角色卡 key。\n"
            "请先用 /agent 角色卡列表 查看可选项，然后发送：/agent 选择角色卡 <key>。\n"
            "当前尚未创建审批，也没有切换角色卡。"
        )
    if is_owner_fact_memory_write_intent(query) and not extract_owner_fact_memory_content(query):
        return (
            "添加事实记忆需要明确的记忆内容。\n"
            "请发送：/agent 添加事实记忆 <内容>。\n"
            "当前尚未创建审批，也没有写入长期记忆。"
        )
    if (
        is_owner_preference_memory_write_intent(query)
        and not extract_owner_preference_memory_content(query)
    ):
        return (
            "添加偏好记忆需要明确的记忆内容。\n"
            "请发送：/agent 添加偏好记忆 <内容>。\n"
            "当前尚未创建审批，也没有写入长期记忆。"
        )
    access_command = classify_owner_access_write_intent(query)
    if access_command and not extract_owner_access_target(access_command, query):
        return (
            f"{access_command} 需要明确的数字 target。\n"
            "请用数字 QQ 号或群号重新发送，例如：/agent 把群 <群号> 加入群白名单。\n"
            "当前尚未创建审批，也没有修改动态名单。"
        )
    return ""


def is_owner_write_intent_query(query: str) -> bool:
    return bool(
        classify_owner_write_command(query)
        or is_owner_delete_summary_intent(query)
        or is_owner_select_persona_intent(query)
        or is_owner_fact_memory_write_intent(query)
        or is_owner_preference_memory_write_intent(query)
        or classify_owner_access_write_intent(query)
        or is_disallowed_owner_write_intent(query)
    )


def is_disallowed_owner_write_intent(query: str) -> bool:
    compact = re.sub(r"\s+", "", query.strip().lower())
    if not compact:
        return False
    return any(
        marker in compact
        for marker in (
            "清空全部上下文",
            "清空所有上下文",
            "清除全部上下文",
            "清除所有上下文",
            "删除全部上下文",
            "删除所有上下文",
            "清空全部摘要",
            "清空所有摘要",
            "清除全部摘要",
            "清除所有摘要",
            "删除全部摘要",
            "删除所有摘要",
            "清空长期记忆",
            "删除长期记忆",
            "删除事实记忆",
            "删除偏好记忆",
            "clearallcontext",
            "clearallcontexts",
            "deleteallcontext",
            "deleteallcontexts",
            "clearallsummaries",
            "deleteallsummaries",
            "deletememory",
            "deletelongtermmemory",
            "重启tts",
            "重启语音服务",
            "自动修好语音",
            "修复语音服务",
            "重新下载模型",
            "下载模型",
            "修改语音配置",
            "改一下语音配置",
            "清理语音缓存",
            "清空语音缓存",
        )
    )


def is_owner_delete_summary_intent(query: str) -> bool:
    stripped = query.strip()
    if not stripped:
        return False
    compact = re.sub(r"\s+", "", stripped.lower())
    if any(marker in compact for marker in ("全部摘要", "所有摘要", "allsummaries")):
        return False
    if "摘要" in compact and any(marker in compact for marker in ("删除", "删掉")):
        return True
    if "summary" in compact and any(marker in compact for marker in ("delete", "remove")):
        return True
    return False


def owner_write_argument_error(arguments: dict[str, object]) -> str:
    command = str(arguments.get("command") or "").strip()
    document_command = (
        command.replace("create_and_send_", "create_", 1)
        if command in DOCUMENT_DELIVERY_COMMANDS
        else command
    )
    if document_command in DOCUMENT_ARTIFACT_COMMANDS:
        title_value = arguments.get("title")
        content_value = arguments.get("content")
        if title_value is None:
            return f"{document_command} 需要明确的 title。"
        if content_value is None:
            return f"{document_command} 需要完整的 content。"
        if not isinstance(title_value, str):
            return f"{document_command} 需要字符串 title。"
        if not isinstance(content_value, str):
            return f"{document_command} 需要字符串 content。"
        title = title_value.strip()
        content = content_value.strip()
        if not title:
            return f"{document_command} 需要明确的 title。"
        if (
            len(title) > DOCUMENT_ARTIFACT_MAX_TITLE_CHARS
            or "\n" in title
            or "\r" in title
            or any(ord(character) < 32 for character in title)
        ):
            return f"{document_command} 的 title 无效或过长。"
        if not content:
            return f"{document_command} 需要完整的 content。"
        if len(content) > DOCUMENT_ARTIFACT_MAX_CONTENT_CHARS or any(
            ord(character) < 32 and character not in "\n\t\r"
            for character in content
        ):
            return f"{document_command} 的 content 超出长度上限。"
        if any(marker in content for marker in DOCUMENT_INTERNAL_SCAFFOLD_MARKERS):
            return (
                f"{document_command} 的 content 包含 MainAgent 内部上下文包装文本，"
                "已在审批前拒绝。请让 MainAgent 根据主题生成正文，或在同一条 "
                "/agent 请求中粘贴完整正文；不能引用“刚才/上面”的消息。"
            )
        if (
            document_command == "create_presentation"
            and presentation_slide_count(content) > DOCUMENT_ARTIFACT_MAX_SLIDES
        ):
            return (
                "create_presentation 按最终分页规则会超过 20 张幻灯片，"
                "已在审批前拒绝。请减少 `##` 章节或每节正文行；"
                "标题页由渲染器自动生成，不要另建“封面”章节。"
            )
    if command == "select_persona" and not str(arguments.get("target") or "").strip():
        return "select_persona 需要明确的角色卡 key：/agent 选择角色卡 <key>。"
    if command in {"add_fact_memory", "add_preference_memory"} and not str(
        arguments.get("content") or ""
    ).strip():
        return f"{command} 需要明确的记忆内容。"
    if command == "delete_session_summary":
        summary_id = str(arguments.get("summary_id") or "").strip()
        if not summary_id.isdigit():
            return (
                "delete_session_summary 需要明确的数字 summary_id。\n"
                "请先用 /agent 查看摘要 找到要删除的 ID，然后发送：/agent 删除摘要 <摘要ID>。\n"
                "当前尚未创建审批，也没有删除任何摘要。"
            )
    if command in ACCESS_WRITE_COMMANDS:
        target = str(arguments.get("target") or "").strip()
        if not target.isdigit():
            return f"{command} 需要明确的数字 target。"
    return ""


def extract_owner_write_command_target(command: str, query: str) -> str:
    if command == "select_persona":
        return extract_owner_persona_target(query) or ""
    if command in ACCESS_WRITE_COMMANDS:
        return extract_owner_access_target(command, query) or ""
    return ""


def extract_owner_write_command_content(command: str, query: str) -> str:
    if command == "add_fact_memory":
        return extract_owner_fact_memory_content(query) or ""
    if command == "add_preference_memory":
        return extract_owner_preference_memory_content(query) or ""
    return ""


def extract_owner_write_command_summary_id(command: str, query: str) -> str:
    if command == "delete_session_summary":
        return extract_owner_delete_summary_id(query) or ""
    return ""


def extract_owner_delete_summary_id(query: str) -> str:
    stripped = query.strip()
    if not stripped:
        return ""
    markers = (
        "帮我删除当前会话摘要",
        "帮我删除当前摘要",
        "帮我删除摘要",
        "帮我删掉当前会话摘要",
        "帮我删掉当前摘要",
        "帮我删掉摘要",
        "删除当前会话摘要",
        "删除当前摘要",
        "删除摘要",
        "删掉当前会话摘要",
        "删掉当前摘要",
        "删掉摘要",
        "delete session summary",
        "delete summary",
        "remove session summary",
        "remove summary",
    )
    goal = extract_semantic_goal_after_markers(stripped, markers)
    if goal is not None:
        match = re.search(r"(?:id\s*)?#?\s*(\d+)\b", goal, re.IGNORECASE)
        return match.group(1) if match else ""
    match = re.search(
        r"^(?:帮我)?(?:把)?(?:当前会话)?摘要\s*(?:id\s*)?#?\s*(\d+)\s*(?:删除|删掉)$",
        stripped,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    return ""


ACCESS_WRITE_MARKERS_BY_COMMAND = {
    "allow_group": (
        "帮我加入群白名单",
        "帮我添加群白名单",
        "帮我允许群",
        "帮我启用群",
        "加入群白名单",
        "添加群白名单",
        "允许群",
        "启用群",
        "allow group",
        "enable group",
    ),
    "deny_group": (
        "帮我移出群白名单",
        "帮我删除群白名单",
        "帮我禁用群",
        "移出群白名单",
        "删除群白名单",
        "禁用群",
        "deny group",
        "disable group",
        "remove group whitelist",
    ),
    "allow_private": (
        "帮我加入私聊白名单",
        "帮我添加私聊白名单",
        "帮我允许私聊",
        "加入私聊白名单",
        "添加私聊白名单",
        "允许私聊",
        "allow private",
        "allow user",
    ),
    "deny_private": (
        "帮我移出私聊白名单",
        "帮我删除私聊白名单",
        "帮我禁用私聊",
        "移出私聊白名单",
        "删除私聊白名单",
        "禁用私聊",
        "deny private",
        "remove private whitelist",
    ),
    "block_user": (
        "帮我加入黑名单",
        "帮我添加黑名单",
        "帮我拉黑用户",
        "帮我拉黑",
        "加入黑名单",
        "添加黑名单",
        "拉黑用户",
        "拉黑",
        "block user",
        "block",
    ),
    "unblock_user": (
        "帮我移出黑名单",
        "帮我删除黑名单",
        "帮我解除拉黑",
        "帮我取消拉黑",
        "移出黑名单",
        "删除黑名单",
        "解除拉黑",
        "取消拉黑",
        "unblock user",
        "unblock",
    ),
}


def classify_owner_access_write_command(query: str) -> str:
    for command in ACCESS_WRITE_COMMANDS:
        if extract_owner_access_target(command, query):
            return command
    return ""


def classify_owner_access_write_intent(query: str) -> str:
    compact = re.sub(r"\s+", "", query.strip().lower())
    if not compact:
        return ""
    compact_markers_by_command = {
        "allow_group": ("加入群白名单", "添加群白名单", "允许群", "启用群", "允许本群", "启用本群"),
        "deny_group": ("移出群白名单", "删除群白名单", "禁用群", "停用群", "禁用本群", "停用本群"),
        "allow_private": ("加入私聊白名单", "添加私聊白名单", "允许私聊", "启用私聊"),
        "deny_private": ("移出私聊白名单", "删除私聊白名单", "禁用私聊", "停用私聊"),
        "block_user": ("加入黑名单", "添加黑名单", "拉黑用户", "拉黑"),
        "unblock_user": ("移出黑名单", "删除黑名单", "解除拉黑", "取消拉黑"),
    }
    for command, markers in compact_markers_by_command.items():
        if any(marker in compact for marker in markers):
            return command
    for command, markers in ACCESS_WRITE_MARKERS_BY_COMMAND.items():
        if extract_semantic_goal_after_markers(query, markers) is not None:
            return command
    return ""


def extract_owner_access_target(command: str, query: str) -> str:
    markers = ACCESS_WRITE_MARKERS_BY_COMMAND.get(command, ())
    goal = extract_semantic_goal_after_markers(query, markers)
    if goal is not None:
        return extract_numeric_target(goal)

    stripped = query.strip()
    patterns_by_command = {
        "allow_group": (
            r"^(?:帮我)?(?:把|将)?(?:群|群号|group)?\s*(\d+)\s*(?:加入|添加到|加入到|放进|拉进|允许|启用)(?:群)?白名单$",
            r"^(?:帮我)?(?:把|将)?(?:群|群号|group)?\s*(\d+)\s*(?:允许|启用)$",
        ),
        "deny_group": (
            r"^(?:帮我)?(?:把|将)?(?:群|群号|group)?\s*(\d+)\s*(?:移出|删除)(?:群)?白名单$",
            r"^(?:帮我)?(?:把|将)?(?:群|群号|group)?\s*(\d+)\s*(?:禁用|停用)$",
        ),
        "allow_private": (
            r"^(?:帮我)?(?:把|将)?(?:用户|qq|qq号|user)?\s*(\d+)\s*(?:加入|添加到|加入到|放进|拉进|允许)(?:私聊)?白名单$",
            r"^(?:帮我)?(?:把|将)?(?:用户|qq|qq号|user)?\s*(\d+)\s*(?:允许|启用)私聊$",
        ),
        "deny_private": (
            r"^(?:帮我)?(?:把|将)?(?:用户|qq|qq号|user)?\s*(\d+)\s*(?:移出|删除)(?:私聊)?白名单$",
            r"^(?:帮我)?(?:把|将)?(?:用户|qq|qq号|user)?\s*(\d+)\s*(?:禁用|停用)私聊$",
        ),
        "block_user": (
            r"^(?:帮我)?(?:把|将)?(?:用户|qq|qq号|user)?\s*(\d+)\s*(?:加入|添加到|加入到|放进)?黑名单$",
            r"^(?:帮我)?(?:把|将)?(?:用户|qq|qq号|user)?\s*(\d+)\s*(?:拉黑|屏蔽)$",
        ),
        "unblock_user": (
            r"^(?:帮我)?(?:把|将)?(?:用户|qq|qq号|user)?\s*(\d+)\s*(?:移出|删除)黑名单$",
            r"^(?:帮我)?(?:把|将)?(?:用户|qq|qq号|user)?\s*(\d+)\s*(?:解除拉黑|取消拉黑|取消屏蔽)$",
        ),
    }
    for pattern in patterns_by_command.get(command, ()):
        match = re.search(pattern, stripped, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def extract_numeric_target(value: str) -> str:
    match = re.search(r"(?:id|qq|qq号|群|群号|用户|user|group|#)?\s*[:：#]?\s*(\d+)", value, re.IGNORECASE)
    return match.group(1) if match else ""


OWNER_PERSONA_TARGET_MARKERS = (
    "帮我选择角色卡",
    "帮我切换角色卡",
    "帮我切到角色卡",
    "帮我换成角色卡",
    "帮我使用角色卡",
    "帮我启用角色卡",
    "选择角色卡",
    "切换角色卡",
    "切到角色卡",
    "换成角色卡",
    "使用角色卡",
    "启用角色卡",
    "select persona",
    "select role card",
    "switch persona",
    "switch role card",
    "use persona",
    "use role card",
)

OWNER_FACT_MEMORY_CONTENT_MARKERS = (
    "帮我添加事实记忆",
    "帮我新增事实记忆",
    "帮我记录事实记忆",
    "帮我记一条事实记忆",
    "帮我记一个事实记忆",
    "添加事实记忆",
    "新增事实记忆",
    "记录事实记忆",
    "记一条事实记忆",
    "记一个事实记忆",
    "添加事实摘要",
    "add fact memory",
    "add fact",
)

OWNER_PREFERENCE_MEMORY_CONTENT_MARKERS = (
    "帮我添加偏好记忆",
    "帮我新增偏好记忆",
    "帮我记录偏好记忆",
    "帮我记一条偏好记忆",
    "帮我记一个偏好记忆",
    "添加偏好记忆",
    "新增偏好记忆",
    "记录偏好记忆",
    "记一条偏好记忆",
    "记一个偏好记忆",
    "添加偏好摘要",
    "add preference memory",
    "add preference",
)


def is_owner_select_persona_intent(query: str) -> bool:
    return extract_semantic_goal_after_markers(
        query,
        OWNER_PERSONA_TARGET_MARKERS,
    ) is not None or bool(
        re.search(
            r"^(?:帮我)?(?:把)?角色卡(?:切换|切|换|选择|设置)(?:成|为|到)?.*$",
            query.strip(),
            re.IGNORECASE,
        )
    )


def extract_owner_persona_target(query: str) -> str:
    goal = extract_semantic_goal_after_markers(query, OWNER_PERSONA_TARGET_MARKERS)
    if goal is not None:
        return goal
    match = re.search(
        r"^(?:帮我)?(?:把)?角色卡(?:切换|切|换|选择|设置)(?:成|为|到)?(.+)$",
        query.strip(),
        re.IGNORECASE,
    )
    if match:
        return _strip_wrapping_punctuation(match.group(1))
    return ""


def is_owner_fact_memory_write_intent(query: str) -> bool:
    return extract_semantic_goal_after_markers(
        query,
        OWNER_FACT_MEMORY_CONTENT_MARKERS,
    ) is not None or bool(
        re.search(
            r"^(?:帮我)?把.+?(?:添加到|加入|记到|写入)(?:事实记忆|长期事实记忆)$",
            query.strip(),
            re.IGNORECASE,
        )
    )


def extract_owner_fact_memory_content(query: str) -> str:
    goal = extract_semantic_goal_after_markers(query, OWNER_FACT_MEMORY_CONTENT_MARKERS)
    if goal is not None:
        return goal
    match = re.search(
        r"^(?:帮我)?把(.+?)(?:添加到|加入|记到|写入)(?:事实记忆|长期事实记忆)$",
        query.strip(),
        re.IGNORECASE,
    )
    if match:
        return _strip_wrapping_punctuation(match.group(1))
    return ""


def is_owner_preference_memory_write_intent(query: str) -> bool:
    return extract_semantic_goal_after_markers(
        query,
        OWNER_PREFERENCE_MEMORY_CONTENT_MARKERS,
    ) is not None or bool(
        re.search(
            r"^(?:帮我)?把.+?(?:添加到|加入|记到|写入)(?:偏好记忆|长期偏好记忆)$",
            query.strip(),
            re.IGNORECASE,
        )
    )


def extract_owner_preference_memory_content(query: str) -> str:
    goal = extract_semantic_goal_after_markers(query, OWNER_PREFERENCE_MEMORY_CONTENT_MARKERS)
    if goal is not None:
        return goal
    match = re.search(
        r"^(?:帮我)?把(.+?)(?:添加到|加入|记到|写入)(?:偏好记忆|长期偏好记忆)$",
        query.strip(),
        re.IGNORECASE,
    )
    if match:
        return _strip_wrapping_punctuation(match.group(1))
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

    if any(
        marker in compact
        for marker in (
            "任务工作台",
            "任务看板",
            "任务摘要",
            "任务索引",
            "协作台",
            "工作台",
            "看板",
            "workbench",
            "dashboard",
            "taskdashboard",
            "taskworkbench",
        )
    ):
        return ("workbench", "")
    if any(
        marker in compact
        for marker in (
            "下一步",
            "接下来",
            "接下来该做什么",
            "现在卡在哪",
            "卡在哪",
            "待我确认",
            "待确认",
            "whatnext",
            "nextstep",
            "blocked",
        )
    ):
        return ("next_step", "")
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
        if (
            action_request.action == MainAgentAction.TOOL_REQUEST
            and action_request.tool_name == OWNER_WRITE_COMMAND_TOOL_NAME
        ):
            argument_error = owner_write_argument_error(action_request.arguments)
            if argument_error:
                state.response_text = argument_error
                state.error = "need_argument"
                return state
        if (
            action_request.action == MainAgentAction.TOOL_REQUEST
            and action_request.tool_name == DOCUMENT_DELIVERY_TOOL_NAME
        ):
            command = str(action_request.arguments.get("command") or "").strip()
            render_command = command.replace("create_and_send_", "create_", 1)
            argument_error = owner_write_argument_error(
                {
                    "command": render_command,
                    "title": action_request.arguments.get("title"),
                    "content": action_request.arguments.get("content"),
                }
            )
            if command not in DOCUMENT_DELIVERY_COMMANDS:
                argument_error = f"不支持的文档发送 command：{command}。"
            if argument_error:
                state.response_text = argument_error
                state.error = "need_argument"
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
            state.response_text = (
                "MainAgentGraph tool failed: "
                + format_failure_user_message(exc, component="工具执行")
            )
            state.error = "tool_execution_failed"
        except Exception as exc:
            state.response_text = (
                "MainAgentGraph read-only tool failed: "
                + format_failure_user_message(exc, component="只读工具执行")
            )
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
