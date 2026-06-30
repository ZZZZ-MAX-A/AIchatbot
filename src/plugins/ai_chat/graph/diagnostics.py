from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeAlias


class DiagnosticsNode(str, Enum):
    READ_CONFIG_SNAPSHOT = "read_config_snapshot"
    READ_RUNTIME_FLAGS = "read_runtime_flags"
    CHECK_TTS_HEALTH = "check_tts_health"
    READ_RECENT_ERRORS = "read_recent_errors"
    READ_MEMORY_STATS = "read_memory_stats"
    READ_IMAGE_CACHE_STATS = "read_image_cache_stats"
    RENDER_DIAGNOSTIC_REPLY = "render_diagnostic_reply"


class DiagnosticsView(str, Enum):
    FULL = "full"
    CONFIG = "config"
    VISION = "vision"
    RECENT_ERRORS = "recent_errors"
    IMAGE_CACHE = "image_cache"
    MEMORY = "memory"
    TTS = "tts"


DIAGNOSTICS_NODE_SEQUENCE: tuple[DiagnosticsNode, ...] = (
    DiagnosticsNode.READ_CONFIG_SNAPSHOT,
    DiagnosticsNode.READ_RUNTIME_FLAGS,
    DiagnosticsNode.CHECK_TTS_HEALTH,
    DiagnosticsNode.READ_RECENT_ERRORS,
    DiagnosticsNode.READ_MEMORY_STATS,
    DiagnosticsNode.READ_IMAGE_CACHE_STATS,
    DiagnosticsNode.RENDER_DIAGNOSTIC_REPLY,
)


@dataclass
class DiagnosticsState:
    view: DiagnosticsView = DiagnosticsView.FULL
    requester_id: str = ""
    session_key: str = ""
    config_snapshot: dict[str, Any] = field(default_factory=dict)
    runtime_flags: dict[str, Any] = field(default_factory=dict)
    tts_health: dict[str, Any] = field(default_factory=dict)
    recent_errors: tuple[str, ...] = ()
    memory_stats: dict[str, Any] = field(default_factory=dict)
    image_cache_stats: dict[str, int] = field(default_factory=dict)
    reply_text: str = ""
    error: str = ""


@dataclass(frozen=True)
class DiagnosticsGraphResult:
    reply_text: str
    error: str = ""
    should_reply: bool = True


@dataclass(frozen=True)
class DiagnosticsGraphExecution:
    state: DiagnosticsState
    result: DiagnosticsGraphResult
    node_trace: tuple[DiagnosticsNode, ...]


DiagnosticsStateHandler: TypeAlias = Callable[
    [DiagnosticsState],
    DiagnosticsState | Awaitable[DiagnosticsState],
]


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


class DiagnosticsGraphRunner:
    """Executable diagnostics graph boundary with injected read-only handlers."""

    def __init__(
        self,
        *,
        read_config_snapshot: DiagnosticsStateHandler | None = None,
        read_runtime_flags: DiagnosticsStateHandler | None = None,
        check_tts_health: DiagnosticsStateHandler | None = None,
        read_recent_errors: DiagnosticsStateHandler | None = None,
        read_memory_stats: DiagnosticsStateHandler | None = None,
        read_image_cache_stats: DiagnosticsStateHandler | None = None,
        render_diagnostic_reply: DiagnosticsStateHandler | None = None,
    ) -> None:
        self.read_config_snapshot = read_config_snapshot
        self.read_runtime_flags = read_runtime_flags
        self.check_tts_health = check_tts_health
        self.read_recent_errors = read_recent_errors
        self.read_memory_stats = read_memory_stats
        self.read_image_cache_stats = read_image_cache_stats
        self.render_diagnostic_reply = render_diagnostic_reply

    async def run(self, state: DiagnosticsState) -> DiagnosticsGraphExecution:
        node_trace: list[DiagnosticsNode] = []
        current = state

        for node in DIAGNOSTICS_NODE_SEQUENCE:
            node_trace.append(node)
            if node == DiagnosticsNode.READ_CONFIG_SNAPSHOT and self.read_config_snapshot is not None:
                current = await _maybe_await(self.read_config_snapshot(current))
            elif node == DiagnosticsNode.READ_RUNTIME_FLAGS and self.read_runtime_flags is not None:
                current = await _maybe_await(self.read_runtime_flags(current))
            elif node == DiagnosticsNode.CHECK_TTS_HEALTH and self.check_tts_health is not None:
                current = await _maybe_await(self.check_tts_health(current))
            elif node == DiagnosticsNode.READ_RECENT_ERRORS and self.read_recent_errors is not None:
                current = await _maybe_await(self.read_recent_errors(current))
            elif node == DiagnosticsNode.READ_MEMORY_STATS and self.read_memory_stats is not None:
                current = await _maybe_await(self.read_memory_stats(current))
            elif node == DiagnosticsNode.READ_IMAGE_CACHE_STATS and self.read_image_cache_stats is not None:
                current = await _maybe_await(self.read_image_cache_stats(current))
            elif node == DiagnosticsNode.RENDER_DIAGNOSTIC_REPLY and self.render_diagnostic_reply is not None:
                current = await _maybe_await(self.render_diagnostic_reply(current))

            if current.error:
                break

        result = DiagnosticsGraphResult(
            reply_text=current.reply_text,
            error=current.error,
            should_reply=not bool(current.error) or bool(current.reply_text),
        )
        return DiagnosticsGraphExecution(current, result, tuple(node_trace))
