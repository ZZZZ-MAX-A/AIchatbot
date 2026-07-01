from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias


class DevContextNode(str, Enum):
    VALIDATE_CONTEXT_REQUEST = "validate_context_request"
    RETRIEVE_COMBINED_CONTEXT = "retrieve_combined_context"
    RENDER_CONTEXT_ARTIFACT = "render_context_artifact"


DEV_CONTEXT_NODE_SEQUENCE: tuple[DevContextNode, ...] = (
    DevContextNode.VALIDATE_CONTEXT_REQUEST,
    DevContextNode.RETRIEVE_COMBINED_CONTEXT,
    DevContextNode.RENDER_CONTEXT_ARTIFACT,
)


@dataclass
class DevContextState:
    query: str
    is_owner: bool = False
    context_text: str = ""
    project_result_count: int = 0
    memory_result_count: int = 0
    metadata: dict[str, object] = field(default_factory=dict)
    error: str = ""


@dataclass(frozen=True)
class DevContextGraphResult:
    context_text: str
    project_result_count: int = 0
    memory_result_count: int = 0
    error: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class DevContextGraphExecution:
    state: DevContextState
    result: DevContextGraphResult
    node_trace: tuple[DevContextNode, ...]


DevContextHandler: TypeAlias = Callable[
    [DevContextState],
    DevContextState | Awaitable[DevContextState],
]


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


class DevContextGraphRunner:
    """Executable dev-side context recovery boundary for future MainAgentGraph use."""

    def __init__(
        self,
        *,
        validate_context_request: DevContextHandler | None = None,
        retrieve_combined_context: DevContextHandler | None = None,
        render_context_artifact: DevContextHandler | None = None,
    ) -> None:
        self.validate_context_request = validate_context_request
        self.retrieve_combined_context = retrieve_combined_context
        self.render_context_artifact = render_context_artifact

    async def run(self, state: DevContextState) -> DevContextGraphExecution:
        node_trace: list[DevContextNode] = []
        current = state

        for node in DEV_CONTEXT_NODE_SEQUENCE:
            node_trace.append(node)
            if node == DevContextNode.VALIDATE_CONTEXT_REQUEST and self.validate_context_request is not None:
                current = await _maybe_await(self.validate_context_request(current))
            elif node == DevContextNode.RETRIEVE_COMBINED_CONTEXT and self.retrieve_combined_context is not None:
                current = await _maybe_await(self.retrieve_combined_context(current))
            elif node == DevContextNode.RENDER_CONTEXT_ARTIFACT and self.render_context_artifact is not None:
                current = await _maybe_await(self.render_context_artifact(current))

            if current.error:
                break

        result = DevContextGraphResult(
            context_text=current.context_text,
            project_result_count=current.project_result_count,
            memory_result_count=current.memory_result_count,
            error=current.error,
            metadata=dict(current.metadata),
        )
        return DevContextGraphExecution(current, result, tuple(node_trace))
