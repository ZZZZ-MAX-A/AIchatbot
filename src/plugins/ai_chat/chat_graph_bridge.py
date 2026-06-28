from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeAlias

from .chat_contracts import ChatOptions, ChatPromptContext, ChatRequest, ChatRuntimeResult, ChatTurn, ChatUserContent
from .graph.adapters import chat_state_with_prompt_context, persisted_turn_from_chat_turn
from .graph.chat import ChatGraphExecution, ChatGraphRunner, ChatState


ChatGraphAgentCall: TypeAlias = Callable[
    [ChatState],
    ChatRuntimeResult | None | Awaitable[ChatRuntimeResult | None],
]
ChatGraphSessionAgentCall: TypeAlias = Callable[
    [ChatState, ChatPromptContext, ChatUserContent],
    ChatRuntimeResult | None | Awaitable[ChatRuntimeResult | None],
]
ChatGraphStateCall: TypeAlias = Callable[[ChatState], ChatState | Awaitable[ChatState]]
ChatGraphPromptCall: TypeAlias = Callable[
    [ChatState],
    "ChatGraphPromptBundle | None | Awaitable[ChatGraphPromptBundle | None]",
]


class ChatGraphSessionCommittedError(RuntimeError):
    """Raised when the chat agent may already have produced side effects."""


@dataclass(frozen=True)
class ChatGraphTailResult:
    execution: ChatGraphExecution
    runtime_result: ChatRuntimeResult


@dataclass(frozen=True)
class ChatGraphPromptBundle:
    state: ChatState
    prompt_context: ChatPromptContext
    user_content: ChatUserContent


@dataclass(frozen=True)
class ChatGraphSessionResult:
    execution: ChatGraphExecution
    runtime_result: ChatRuntimeResult
    prompt_context: ChatPromptContext
    user_content: ChatUserContent


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def run_chat_graph_tail(
    state: ChatState,
    *,
    request: ChatRequest,
    options: ChatOptions,
    prompt_context: ChatPromptContext,
    user_content: ChatUserContent,
    message_type: str,
    call_chat_agent: ChatGraphAgentCall,
    llm_user_content: str = "",
) -> ChatGraphTailResult | None:
    prepared = chat_state_with_prompt_context(
        state,
        prompt_context,
        user_content,
        llm_user_content=llm_user_content,
    )
    agent_started = False
    captured_result: ChatRuntimeResult | None = None

    async def graph_call(chat_state: ChatState) -> ChatRuntimeResult | None:
        nonlocal agent_started
        nonlocal captured_result
        agent_started = True
        result = await _maybe_await(call_chat_agent(chat_state))
        captured_result = result
        return result

    async def graph_persist(_: ChatState, result: ChatRuntimeResult):
        turn = ChatTurn(
            stored_user=user_content.stored,
            stored_assistant=result.stored_assistant,
        )
        return persisted_turn_from_chat_turn(
            request,
            prompt_context,
            turn,
            message_type=message_type,
        )

    try:
        execution = await ChatGraphRunner(
            graph_call,
            persist_turn=graph_persist,
        ).run(prepared)
    except Exception as exc:
        if agent_started:
            raise ChatGraphSessionCommittedError("chat graph failed after chat agent started") from exc
        raise
    if captured_result is None:
        return None
    return ChatGraphTailResult(
        execution=execution,
        runtime_result=captured_result,
    )


async def run_chat_graph_session(
    state: ChatState,
    *,
    request: ChatRequest,
    options: ChatOptions,
    message_type: str,
    call_chat_agent: ChatGraphSessionAgentCall,
    build_prompt_context: ChatGraphPromptCall,
    resolve_image_context: ChatGraphStateCall | None = None,
) -> ChatGraphSessionResult | None:
    prompt_bundle: ChatGraphPromptBundle | None = None
    agent_started = False
    captured_result: ChatRuntimeResult | None = None

    async def graph_resolve_image_context(chat_state: ChatState) -> ChatState:
        if resolve_image_context is None:
            return chat_state
        return await _maybe_await(resolve_image_context(chat_state))

    async def graph_build_prompt_context(chat_state: ChatState) -> ChatState:
        nonlocal prompt_bundle
        prompt_bundle = await _maybe_await(build_prompt_context(chat_state))
        if prompt_bundle is None:
            return chat_state
        return prompt_bundle.state

    async def graph_call(chat_state: ChatState) -> ChatRuntimeResult | None:
        nonlocal agent_started
        nonlocal captured_result
        if prompt_bundle is None or not prompt_bundle.user_content.for_llm:
            return None
        agent_started = True
        result = await _maybe_await(
            call_chat_agent(
                chat_state,
                prompt_bundle.prompt_context,
                prompt_bundle.user_content,
            )
        )
        captured_result = result
        return result

    async def graph_persist(_: ChatState, result: ChatRuntimeResult):
        if prompt_bundle is None:
            return None
        turn = ChatTurn(
            stored_user=prompt_bundle.user_content.stored,
            stored_assistant=result.stored_assistant,
        )
        return persisted_turn_from_chat_turn(
            request,
            prompt_bundle.prompt_context,
            turn,
            message_type=message_type,
        )

    try:
        execution = await ChatGraphRunner(
            graph_call,
            resolve_image_context=graph_resolve_image_context,
            build_prompt_context=graph_build_prompt_context,
            persist_turn=graph_persist,
        ).run(state)
    except Exception as exc:
        if agent_started:
            raise ChatGraphSessionCommittedError("chat graph failed after chat agent started") from exc
        raise
    if captured_result is None or prompt_bundle is None:
        return None
    return ChatGraphSessionResult(
        execution=execution,
        runtime_result=captured_result,
        prompt_context=prompt_bundle.prompt_context,
        user_content=prompt_bundle.user_content,
    )
