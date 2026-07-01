from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from typing import TypeAlias


class MainAgentNode(str, Enum):
    VALIDATE_AGENT_REQUEST = "validate_agent_request"
    BUILD_AGENT_CONTEXT = "build_agent_context"
    CALL_MAIN_AGENT = "call_main_agent"
    PLAN_READ_ONLY_TOOL = "plan_read_only_tool"
    VALIDATE_ACTION_REQUEST = "validate_action_request"
    CHECK_TOOL_POLICY = "check_tool_policy"
    EXECUTE_TOOL = "execute_tool"
    RENDER_AGENT_RESPONSE = "render_agent_response"


MAIN_AGENT_NODE_SEQUENCE: tuple[MainAgentNode, ...] = (
    MainAgentNode.VALIDATE_AGENT_REQUEST,
    MainAgentNode.BUILD_AGENT_CONTEXT,
    MainAgentNode.CALL_MAIN_AGENT,
    MainAgentNode.VALIDATE_ACTION_REQUEST,
    MainAgentNode.CHECK_TOOL_POLICY,
    MainAgentNode.EXECUTE_TOOL,
    MainAgentNode.RENDER_AGENT_RESPONSE,
)


class MainAgentAction(str, Enum):
    FINAL_ANSWER = "final_answer"
    TOOL_REQUEST = "tool_request"
    ASK_OWNER = "ask_owner"
    STOP = "stop"


class MainAgentToolName(str, Enum):
    DEV_CONTEXT = "dev_context"


@dataclass(frozen=True)
class MainAgentActionRequest:
    action: MainAgentAction
    content: str = ""
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


class MainAgentActionRequestError(ValueError):
    """Raised when a MainAgent action request is malformed or unsupported."""


@dataclass
class MainAgentState:
    query: str
    is_owner: bool = False
    is_group: bool = False
    raw_action_request: object = ""
    action_request: MainAgentActionRequest | None = None
    action: str = ""
    requested_tool: str = ""
    tool_query: str = ""
    tool_result: str = ""
    response_text: str = ""
    policy_decision: str = ""
    policy_reason: str = ""
    metadata: dict[str, object] = field(default_factory=dict)
    error: str = ""


@dataclass(frozen=True)
class MainAgentGraphResult:
    response_text: str
    action: str = ""
    requested_tool: str = ""
    tool_result: str = ""
    policy_decision: str = ""
    policy_reason: str = ""
    error: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class MainAgentGraphExecution:
    state: MainAgentState
    result: MainAgentGraphResult
    node_trace: tuple[MainAgentNode, ...]


MainAgentHandler: TypeAlias = Callable[
    [MainAgentState],
    MainAgentState | Awaitable[MainAgentState],
]


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


def parse_main_agent_action_request(raw: object) -> MainAgentActionRequest:
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MainAgentActionRequestError("action request must be valid JSON") from exc
    else:
        payload = raw

    if not isinstance(payload, dict):
        raise MainAgentActionRequestError("action request must be a JSON object")

    action_value = payload.get("action")
    if not isinstance(action_value, str) or not action_value.strip():
        raise MainAgentActionRequestError("action request requires a non-empty action")

    try:
        action = MainAgentAction(action_value.strip())
    except ValueError as exc:
        raise MainAgentActionRequestError(f"unsupported action: {action_value}") from exc

    content = _optional_string(payload.get("content"), "content")
    reason = _optional_string(payload.get("reason"), "reason")
    tool_name = _optional_string(payload.get("tool_name"), "tool_name")
    arguments_value = payload.get("arguments", {})
    if arguments_value is None:
        arguments_value = {}
    if not isinstance(arguments_value, dict):
        raise MainAgentActionRequestError("arguments must be an object")
    arguments = dict(arguments_value)

    if action == MainAgentAction.FINAL_ANSWER and not content.strip():
        raise MainAgentActionRequestError("final_answer requires content")
    if action == MainAgentAction.ASK_OWNER and not content.strip():
        raise MainAgentActionRequestError("ask_owner requires content")
    if action == MainAgentAction.TOOL_REQUEST:
        if not tool_name.strip():
            raise MainAgentActionRequestError("tool_request requires tool_name")
        if tool_name.strip() != MainAgentToolName.DEV_CONTEXT.value:
            raise MainAgentActionRequestError(f"unsupported tool: {tool_name}")
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            raise MainAgentActionRequestError("dev_context tool requires arguments.query")
    elif tool_name:
        raise MainAgentActionRequestError(f"{action.value} must not include tool_name")

    return MainAgentActionRequest(
        action=action,
        content=content.strip(),
        tool_name=tool_name.strip(),
        arguments=arguments,
        reason=reason.strip(),
    )


def _optional_string(value: object, field_name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise MainAgentActionRequestError(f"{field_name} must be a string")
    return value


def apply_action_request_to_state(
    state: MainAgentState,
    action_request: MainAgentActionRequest,
) -> MainAgentState:
    state.action_request = action_request
    state.action = action_request.action.value
    state.requested_tool = ""
    state.tool_query = ""

    if action_request.action == MainAgentAction.FINAL_ANSWER:
        state.response_text = action_request.content
    elif action_request.action == MainAgentAction.ASK_OWNER:
        state.response_text = action_request.content
    elif action_request.action == MainAgentAction.STOP:
        state.response_text = action_request.content or action_request.reason
    elif action_request.action == MainAgentAction.TOOL_REQUEST:
        state.requested_tool = action_request.tool_name
        state.tool_query = str(action_request.arguments["query"]).strip()
    return state


def dev_context_tool_action_json(query: str, *, reason: str = "") -> str:
    return json.dumps(
        {
            "action": MainAgentAction.TOOL_REQUEST.value,
            "tool_name": MainAgentToolName.DEV_CONTEXT.value,
            "arguments": {"query": query},
            "reason": reason,
        },
        ensure_ascii=False,
    )


class MainAgentGraphRunner:
    """Conservative MainAgentGraph boundary with read-only tool execution."""

    def __init__(
        self,
        *,
        validate_agent_request: MainAgentHandler | None = None,
        build_agent_context: MainAgentHandler | None = None,
        call_main_agent: MainAgentHandler | None = None,
        plan_read_only_tool: MainAgentHandler | None = None,
        validate_action_request: MainAgentHandler | None = None,
        check_tool_policy: MainAgentHandler | None = None,
        execute_tool: MainAgentHandler | None = None,
        render_agent_response: MainAgentHandler | None = None,
    ) -> None:
        self.validate_agent_request = validate_agent_request
        self.build_agent_context = build_agent_context
        self.call_main_agent = call_main_agent
        self.plan_read_only_tool = plan_read_only_tool
        self.validate_action_request = validate_action_request
        self.check_tool_policy = check_tool_policy
        self.execute_tool = execute_tool
        self.render_agent_response = render_agent_response

    async def run(self, state: MainAgentState) -> MainAgentGraphExecution:
        node_trace: list[MainAgentNode] = []
        current = state

        for node in MAIN_AGENT_NODE_SEQUENCE:
            node_trace.append(node)
            if node == MainAgentNode.VALIDATE_AGENT_REQUEST and self.validate_agent_request is not None:
                current = await _maybe_await(self.validate_agent_request(current))
            elif node == MainAgentNode.BUILD_AGENT_CONTEXT and self.build_agent_context is not None:
                current = await _maybe_await(self.build_agent_context(current))
            elif node == MainAgentNode.CALL_MAIN_AGENT:
                if self.call_main_agent is not None:
                    current = await _maybe_await(self.call_main_agent(current))
                elif self.plan_read_only_tool is not None:
                    current = await _maybe_await(self.plan_read_only_tool(current))
            elif node == MainAgentNode.VALIDATE_ACTION_REQUEST and self.validate_action_request is not None:
                current = await _maybe_await(self.validate_action_request(current))
            elif node == MainAgentNode.CHECK_TOOL_POLICY and self.check_tool_policy is not None:
                current = await _maybe_await(self.check_tool_policy(current))
            elif node == MainAgentNode.EXECUTE_TOOL and self.execute_tool is not None:
                current = await _maybe_await(self.execute_tool(current))
            elif node == MainAgentNode.RENDER_AGENT_RESPONSE and self.render_agent_response is not None:
                current = await _maybe_await(self.render_agent_response(current))

            if current.error:
                break

        result = MainAgentGraphResult(
            response_text=current.response_text,
            action=current.action,
            requested_tool=current.requested_tool,
            tool_result=current.tool_result,
            policy_decision=current.policy_decision,
            policy_reason=current.policy_reason,
            error=current.error,
            metadata=dict(current.metadata),
        )
        return MainAgentGraphExecution(current, result, tuple(node_trace))
