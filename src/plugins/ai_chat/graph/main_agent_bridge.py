from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Callable
from typing import TypeAlias

from ..policy.engine import ToolPolicyInput, decide_tool_policy
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


ReadOnlyDevContextTool: TypeAlias = Callable[[str, bool], str | Awaitable[str]]


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


def create_read_only_main_agent_runner(
    *,
    retrieve_dev_context: ReadOnlyDevContextTool,
    llm_call: MainAgentLLMCall | None = None,
    call_main_agent: MainAgentHandler | None = None,
    summarize_tool_result: MainAgentHandler | None = None,
    render_mode: str = "raw",
) -> MainAgentGraphRunner:
    agent_call = call_main_agent
    if agent_call is None and llm_call is not None:
        agent_call = create_main_agent_call_handler(llm_call)
    if agent_call is None:
        agent_call = call_dev_context_stub_agent

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
        build_agent_context=build_read_only_agent_context,
        call_main_agent=agent_call,
        validate_action_request=validate_main_agent_action_request,
        check_tool_policy=check_read_only_tool_policy,
        execute_tool=create_read_only_tool_executor(retrieve_dev_context),
        render_agent_response=render_agent_response,
    )


def create_read_only_main_agent_runtime_handler(
    *,
    retrieve_dev_context: ReadOnlyDevContextTool,
    llm_call: MainAgentLLMCall | None = None,
    call_main_agent: MainAgentHandler | None = None,
    summarize_tool_result: MainAgentHandler | None = None,
    render_mode: str = "raw",
):
    runner = create_read_only_main_agent_runner(
        retrieve_dev_context=retrieve_dev_context,
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
    state.metadata["mode"] = "read_only"
    state.metadata["allowed_tools"] = [MainAgentToolName.DEV_CONTEXT.value]
    state.metadata.setdefault(
        "agent_context",
        "\n".join(
            [
                "MainAgentGraph read-only local test mode.",
                "Allowed tools: dev_context.",
                "Disallowed: shell, file writes, QQ sends, external writes.",
            ]
        ),
    )
    return state


def call_dev_context_stub_agent(state: MainAgentState) -> MainAgentState:
    state.raw_action_request = dev_context_tool_action_json(
        state.query,
        reason="recover dev-side project context",
    )
    return state


def validate_main_agent_action_request(state: MainAgentState) -> MainAgentState:
    try:
        action_request = parse_main_agent_action_request(state.raw_action_request)
    except MainAgentActionRequestError as exc:
        state.response_text = f"MainAgentGraph rejected: {exc}"
        state.error = "invalid_action_request"
        return state
    return apply_action_request_to_state(state, action_request)


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


def create_read_only_tool_executor(
    retrieve_dev_context: ReadOnlyDevContextTool,
) -> MainAgentHandler:
    async def execute_tool(state: MainAgentState) -> MainAgentState:
        if state.action != MainAgentAction.TOOL_REQUEST.value:
            return state
        if state.requested_tool != MainAgentToolName.DEV_CONTEXT.value:
            state.response_text = f"MainAgentGraph rejected: unregistered tool {state.requested_tool}"
            state.error = "unknown_tool"
            return state

        try:
            state.tool_result = str(
                await _maybe_await(retrieve_dev_context(state.tool_query, state.is_owner))
            )
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
