from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .state import RuntimeIntent, RuntimeState


class RootNode(str, Enum):
    NORMALIZE_EVENT = "normalize_event"
    LOAD_ACTOR_CONTEXT = "load_actor_context"
    HARD_POLICY_GATE = "hard_policy_gate"
    ROUTE_INTENT = "route_intent"
    DISPATCH_CAPABILITY = "dispatch_capability"
    RENDER_RESPONSE = "render_response"


ROOT_NODE_SEQUENCE: tuple[RootNode, ...] = (
    RootNode.NORMALIZE_EVENT,
    RootNode.LOAD_ACTOR_CONTEXT,
    RootNode.HARD_POLICY_GATE,
    RootNode.ROUTE_INTENT,
    RootNode.DISPATCH_CAPABILITY,
    RootNode.RENDER_RESPONSE,
)


@dataclass(frozen=True)
class RouteDecision:
    intent: RuntimeIntent
    reason: str = ""


def route_from_explicit_intent(state: RuntimeState) -> RouteDecision:
    if state.intent is None:
        return RouteDecision(RuntimeIntent.IGNORE, "intent is not set")
    return RouteDecision(state.intent, "explicit runtime intent")
