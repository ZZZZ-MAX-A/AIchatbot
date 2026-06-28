from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeAlias

from .root import ROOT_NODE_SEQUENCE, RootNode, RouteDecision, route_from_explicit_intent
from .state import RuntimeIntent, RuntimeState


@dataclass(frozen=True)
class RuntimeResponse:
    text: str
    should_reply: bool = True


RuntimeHandler: TypeAlias = Callable[[RuntimeState], RuntimeResponse | Awaitable[RuntimeResponse]]


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


class RootGraphRunner:
    """Executable root graph boundary for routing runtime intents."""

    def __init__(
        self,
        handlers: dict[RuntimeIntent, RuntimeHandler] | None = None,
    ) -> None:
        self.handlers = dict(handlers or {})

    async def run(self, state: RuntimeState) -> RuntimeResponse:
        node_trace: list[RootNode] = []
        route = RouteDecision(RuntimeIntent.IGNORE, "route was not evaluated")
        response: RuntimeResponse | None = None
        dispatched = False

        for node in ROOT_NODE_SEQUENCE:
            node_trace.append(node)
            if node == RootNode.ROUTE_INTENT:
                route = route_from_explicit_intent(state)
            elif node == RootNode.DISPATCH_CAPABILITY:
                response, dispatched = await self._dispatch(state, route)
            elif node == RootNode.RENDER_RESPONSE and response is None:
                response = RuntimeResponse("", should_reply=False)

        self._record_artifact(state, node_trace, route, dispatched)
        return response or RuntimeResponse("", should_reply=False)

    async def _dispatch(
        self,
        state: RuntimeState,
        route: RouteDecision,
    ) -> tuple[RuntimeResponse, bool]:
        if route.intent == RuntimeIntent.IGNORE:
            return RuntimeResponse("", should_reply=False), False

        handler = self.handlers.get(route.intent)
        if handler is not None:
            return await _maybe_await(handler(state)), True

        if state.response:
            return RuntimeResponse(state.response), False
        return RuntimeResponse("Agent Runtime is not enabled.", should_reply=False), False

    def _record_artifact(
        self,
        state: RuntimeState,
        node_trace: list[RootNode],
        route: RouteDecision,
        dispatched: bool,
    ) -> None:
        state.artifacts["root_graph"] = {
            "node_trace": tuple(node.value for node in node_trace),
            "route": route.intent.value,
            "reason": route.reason,
            "dispatched": dispatched,
        }


class AgentRuntime:
    """Runtime boundary for RootGraph integration."""

    def __init__(self, root_runner: RootGraphRunner | None = None) -> None:
        self.root_runner = root_runner or RootGraphRunner()

    async def run(self, state: RuntimeState) -> RuntimeResponse:
        return await self.root_runner.run(state)
