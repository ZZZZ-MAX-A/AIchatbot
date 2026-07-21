from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from ..config import AiChatConfig
from ..graph.main_agent import MainAgentState
from ..graph.main_agent_llm import (
    MainAgentLLMCall,
    create_main_agent_call_handler,
    create_main_agent_tool_summary_handler,
)
from ..graph.tool_registry import ToolRegistry
from .models import build_main_llm


class MainAgentLLMInvocationError(RuntimeError):
    """Raised when a configured Main LLM object cannot be invoked."""


MainAgentLLMResultObserver = Callable[[Exception | None], None]


async def _maybe_await(value: object) -> object:
    if inspect.isawaitable(value):
        return await value
    return value


async def invoke_main_llm(
    llm: Any,
    messages: Sequence[Mapping[str, str]],
) -> object:
    payload = tuple(dict(message) for message in messages)

    ainvoke = getattr(llm, "ainvoke", None)
    if callable(ainvoke):
        return await _maybe_await(ainvoke(payload))

    invoke = getattr(llm, "invoke", None)
    if callable(invoke):
        return await _maybe_await(invoke(payload))

    if callable(llm):
        return await _maybe_await(llm(payload))

    raise MainAgentLLMInvocationError("main llm object is not invokable")


def create_main_llm_call(
    config: AiChatConfig,
    *,
    llm: Any | None = None,
) -> MainAgentLLMCall:
    model = llm if llm is not None else build_main_llm(config)

    async def call(messages: Sequence[Mapping[str, str]]) -> object:
        return await invoke_main_llm(model, messages)

    return call


def create_main_agent_lc_call_handler(
    config: AiChatConfig,
    *,
    llm: Any | None = None,
    context_metadata_key: str = "agent_context",
    tool_registry: ToolRegistry | None = None,
    result_observer: MainAgentLLMResultObserver | None = None,
) -> Callable[[MainAgentState], Awaitable[MainAgentState]]:
    return create_main_agent_call_handler(
        create_main_llm_call(config, llm=llm),
        context_metadata_key=context_metadata_key,
        tool_registry=tool_registry,
        result_observer=result_observer,
    )


def create_main_agent_tool_summary_lc_handler(
    config: AiChatConfig,
    *,
    llm: Any | None = None,
    context_metadata_key: str = "agent_context",
) -> Callable[[MainAgentState], Awaitable[MainAgentState]]:
    return create_main_agent_tool_summary_handler(
        create_main_llm_call(config, llm=llm),
        context_metadata_key=context_metadata_key,
    )
