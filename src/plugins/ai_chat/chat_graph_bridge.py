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


@dataclass(frozen=True)
class ChatGraphTailResult:
    execution: ChatGraphExecution
    runtime_result: ChatRuntimeResult


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
    captured_result: ChatRuntimeResult | None = None

    async def graph_call(chat_state: ChatState) -> ChatRuntimeResult | None:
        nonlocal captured_result
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

    execution = await ChatGraphRunner(
        graph_call,
        persist_turn=graph_persist,
    ).run(prepared)
    if captured_result is None:
        return None
    return ChatGraphTailResult(
        execution=execution,
        runtime_result=captured_result,
    )
