from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias


class MemoryNode(str, Enum):
    ENSURE_GAP_SCENE = "ensure_gap_scene"
    BUILD_HISTORY = "build_history"
    BUILD_MANUAL_MEMORY_CONTEXT = "build_manual_memory_context"
    SAVE_USER_MESSAGE = "save_user_message"
    SAVE_ASSISTANT_MESSAGE = "save_assistant_message"
    SCHEDULE_COMPRESSION = "schedule_compression"


MEMORY_CONTEXT_NODE_SEQUENCE: tuple[MemoryNode, ...] = (
    MemoryNode.ENSURE_GAP_SCENE,
    MemoryNode.BUILD_MANUAL_MEMORY_CONTEXT,
    MemoryNode.BUILD_HISTORY,
)


MEMORY_PERSIST_NODE_SEQUENCE: tuple[MemoryNode, ...] = (
    MemoryNode.SAVE_USER_MESSAGE,
    MemoryNode.SAVE_ASSISTANT_MESSAGE,
    MemoryNode.SCHEDULE_COMPRESSION,
)


@dataclass
class MemoryContext:
    session_key: str = ""
    message_type: str = ""
    user_id: str = ""
    group_id: str | None = None
    system_contexts: list[str] = field(default_factory=list)
    history: list[dict[str, str]] = field(default_factory=list)
    manual_long_term_context: str = ""
    rule_reminder_context: str = ""
    gap_scene_error: str = ""
    error: str = ""


@dataclass(frozen=True)
class MemoryContextGraphResult:
    history: tuple[dict[str, str], ...]
    system_contexts: tuple[str, ...]
    manual_long_term_context: str = ""
    rule_reminder_context: str = ""
    gap_scene_error: str = ""
    error: str = ""


@dataclass(frozen=True)
class MemoryContextGraphExecution:
    state: MemoryContext
    result: MemoryContextGraphResult
    node_trace: tuple[MemoryNode, ...]


@dataclass(frozen=True)
class PersistedTurn:
    session_key: str
    user_content: str
    assistant_content: str
    message_type: str
    user_id: str
    group_id: str | None = None


@dataclass
class MemoryPersistState:
    session_key: str = ""
    user_content: str = ""
    assistant_content: str = ""
    message_type: str = ""
    user_id: str = ""
    group_id: str | None = None
    user_saved: bool = False
    assistant_saved: bool = False
    compression_scheduled: bool = False
    error: str = ""


@dataclass(frozen=True)
class MemoryPersistGraphResult:
    user_saved: bool
    assistant_saved: bool
    compression_scheduled: bool
    error: str = ""


@dataclass(frozen=True)
class MemoryPersistGraphExecution:
    state: MemoryPersistState
    result: MemoryPersistGraphResult
    node_trace: tuple[MemoryNode, ...]


MemoryContextHandler: TypeAlias = Callable[
    [MemoryContext],
    MemoryContext | Awaitable[MemoryContext],
]
MemoryPersistHandler: TypeAlias = Callable[
    [MemoryPersistState],
    MemoryPersistState | Awaitable[MemoryPersistState],
]


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


class MemoryContextGraphRunner:
    """Executable memory context graph boundary with injected read handlers."""

    def __init__(
        self,
        *,
        ensure_gap_scene: MemoryContextHandler | None = None,
        build_manual_memory_context: MemoryContextHandler | None = None,
        build_history: MemoryContextHandler | None = None,
    ) -> None:
        self.ensure_gap_scene = ensure_gap_scene
        self.build_manual_memory_context = build_manual_memory_context
        self.build_history = build_history

    async def run(self, state: MemoryContext) -> MemoryContextGraphExecution:
        node_trace: list[MemoryNode] = []
        current = state

        for node in MEMORY_CONTEXT_NODE_SEQUENCE:
            node_trace.append(node)
            if node == MemoryNode.ENSURE_GAP_SCENE and self.ensure_gap_scene is not None:
                current = await _maybe_await(self.ensure_gap_scene(current))
            elif (
                node == MemoryNode.BUILD_MANUAL_MEMORY_CONTEXT
                and self.build_manual_memory_context is not None
            ):
                current = await _maybe_await(self.build_manual_memory_context(current))
            elif node == MemoryNode.BUILD_HISTORY and self.build_history is not None:
                current = await _maybe_await(self.build_history(current))

            if current.error:
                break

        result = MemoryContextGraphResult(
            history=tuple(current.history),
            system_contexts=tuple(current.system_contexts),
            manual_long_term_context=current.manual_long_term_context,
            rule_reminder_context=current.rule_reminder_context,
            gap_scene_error=current.gap_scene_error,
            error=current.error,
        )
        return MemoryContextGraphExecution(current, result, tuple(node_trace))


class MemoryPersistGraphRunner:
    """Executable memory persistence graph boundary with injected write handlers."""

    def __init__(
        self,
        *,
        save_user_message: MemoryPersistHandler | None = None,
        save_assistant_message: MemoryPersistHandler | None = None,
        schedule_compression: MemoryPersistHandler | None = None,
    ) -> None:
        self.save_user_message = save_user_message
        self.save_assistant_message = save_assistant_message
        self.schedule_compression = schedule_compression

    async def run(self, state: MemoryPersistState) -> MemoryPersistGraphExecution:
        node_trace: list[MemoryNode] = []
        current = state

        for node in MEMORY_PERSIST_NODE_SEQUENCE:
            node_trace.append(node)
            if node == MemoryNode.SAVE_USER_MESSAGE and self.save_user_message is not None:
                current = await _maybe_await(self.save_user_message(current))
            elif (
                node == MemoryNode.SAVE_ASSISTANT_MESSAGE
                and self.save_assistant_message is not None
            ):
                current = await _maybe_await(self.save_assistant_message(current))
            elif node == MemoryNode.SCHEDULE_COMPRESSION and self.schedule_compression is not None:
                current = await _maybe_await(self.schedule_compression(current))

            if current.error:
                break

        result = MemoryPersistGraphResult(
            user_saved=current.user_saved,
            assistant_saved=current.assistant_saved,
            compression_scheduled=current.compression_scheduled,
            error=current.error,
        )
        return MemoryPersistGraphExecution(current, result, tuple(node_trace))
