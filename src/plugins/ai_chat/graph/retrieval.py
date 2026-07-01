from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias


class MemoryRetrievalAction(str, Enum):
    STATUS = "status"
    QUERY = "query"
    REBUILD = "rebuild"


class MemoryRetrievalNode(str, Enum):
    VALIDATE_RETRIEVAL_REQUEST = "validate_retrieval_request"
    EXECUTE_RETRIEVAL_OPERATION = "execute_retrieval_operation"
    RENDER_RETRIEVAL_REPLY = "render_retrieval_reply"


MEMORY_RETRIEVAL_NODE_SEQUENCE: tuple[MemoryRetrievalNode, ...] = (
    MemoryRetrievalNode.VALIDATE_RETRIEVAL_REQUEST,
    MemoryRetrievalNode.EXECUTE_RETRIEVAL_OPERATION,
    MemoryRetrievalNode.RENDER_RETRIEVAL_REPLY,
)


@dataclass
class MemoryRetrievalState:
    action: MemoryRetrievalAction
    query: str = ""
    is_owner: bool = False
    reply_text: str = ""
    metadata: dict[str, object] = field(default_factory=dict)
    error: str = ""


@dataclass(frozen=True)
class MemoryRetrievalGraphResult:
    reply_text: str
    error: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryRetrievalGraphExecution:
    state: MemoryRetrievalState
    result: MemoryRetrievalGraphResult
    node_trace: tuple[MemoryRetrievalNode, ...]


MemoryRetrievalHandler: TypeAlias = Callable[
    [MemoryRetrievalState],
    MemoryRetrievalState | Awaitable[MemoryRetrievalState],
]


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


class MemoryRetrievalGraphRunner:
    """Executable MemoryRAG retrieval graph boundary for owner debug commands."""

    def __init__(
        self,
        *,
        validate_retrieval_request: MemoryRetrievalHandler | None = None,
        execute_retrieval_operation: MemoryRetrievalHandler | None = None,
        render_retrieval_reply: MemoryRetrievalHandler | None = None,
    ) -> None:
        self.validate_retrieval_request = validate_retrieval_request
        self.execute_retrieval_operation = execute_retrieval_operation
        self.render_retrieval_reply = render_retrieval_reply

    async def run(self, state: MemoryRetrievalState) -> MemoryRetrievalGraphExecution:
        node_trace: list[MemoryRetrievalNode] = []
        current = state

        for node in MEMORY_RETRIEVAL_NODE_SEQUENCE:
            node_trace.append(node)
            if (
                node == MemoryRetrievalNode.VALIDATE_RETRIEVAL_REQUEST
                and self.validate_retrieval_request is not None
            ):
                current = await _maybe_await(self.validate_retrieval_request(current))
            elif (
                node == MemoryRetrievalNode.EXECUTE_RETRIEVAL_OPERATION
                and self.execute_retrieval_operation is not None
            ):
                current = await _maybe_await(self.execute_retrieval_operation(current))
            elif (
                node == MemoryRetrievalNode.RENDER_RETRIEVAL_REPLY
                and self.render_retrieval_reply is not None
            ):
                current = await _maybe_await(self.render_retrieval_reply(current))

            if current.error:
                break

        result = MemoryRetrievalGraphResult(
            reply_text=current.reply_text,
            error=current.error,
            metadata=dict(current.metadata),
        )
        return MemoryRetrievalGraphExecution(current, result, tuple(node_trace))
