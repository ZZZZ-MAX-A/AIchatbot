from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .state import ActorRole, RuntimeIntent, RuntimeState, SessionType


class RootNode(str, Enum):
    NORMALIZE_EVENT = "normalize_event"
    LOAD_ACTOR_CONTEXT = "load_actor_context"
    HARD_POLICY_GATE = "hard_policy_gate"
    ROUTE_INTENT = "route_intent"
    BUILD_RUNTIME_CONTEXT = "build_runtime_context"
    DISPATCH_CAPABILITY = "dispatch_capability"
    COMMIT_SIDE_EFFECTS = "commit_side_effects"
    RENDER_RESPONSE = "render_response"


ROOT_NODE_SEQUENCE: tuple[RootNode, ...] = (
    RootNode.NORMALIZE_EVENT,
    RootNode.LOAD_ACTOR_CONTEXT,
    RootNode.HARD_POLICY_GATE,
    RootNode.ROUTE_INTENT,
    RootNode.BUILD_RUNTIME_CONTEXT,
    RootNode.DISPATCH_CAPABILITY,
    RootNode.COMMIT_SIDE_EFFECTS,
    RootNode.RENDER_RESPONSE,
)


@dataclass(frozen=True)
class RouteDecision:
    intent: RuntimeIntent
    reason: str = ""


@dataclass(frozen=True)
class RootPolicyDecision:
    decision: str
    reason: str
    allow_dispatch: bool
    should_reply: bool = True
    response_text: str = ""
    error: str = ""


CHAT_ACCESS_POLICY_ARTIFACT = "chat_access_policy"


def route_from_explicit_intent(state: RuntimeState) -> RouteDecision:
    if state.intent is None:
        return RouteDecision(RuntimeIntent.IGNORE, "intent is not set")
    return RouteDecision(state.intent, "explicit runtime intent")


def _chat_access_policy_decision(state: RuntimeState) -> RootPolicyDecision | None:
    if state.intent != RuntimeIntent.CHAT:
        return None
    artifact = state.artifacts.get(CHAT_ACCESS_POLICY_ARTIFACT)
    if not isinstance(artifact, dict):
        return None
    if artifact.get("allow_dispatch") is not False:
        return None
    decision = str(artifact.get("decision") or "denied")
    reason = str(artifact.get("reason") or "chat access policy denied dispatch")
    return RootPolicyDecision(
        decision=decision,
        reason=reason,
        allow_dispatch=False,
        should_reply=bool(artifact.get("should_reply", False)),
        response_text=str(artifact.get("response_text") or ""),
        error=str(artifact.get("error") or decision),
    )


def evaluate_hard_policy(state: RuntimeState) -> RootPolicyDecision:
    if state.actor.role == ActorRole.BLOCKED:
        return RootPolicyDecision(
            decision="blocked",
            reason="actor is blocked",
            allow_dispatch=False,
            should_reply=False,
            error="permission_denied",
        )
    if state.intent is None:
        return RootPolicyDecision(
            decision="ignore",
            reason="intent is not set",
            allow_dispatch=False,
            should_reply=False,
        )
    chat_policy = _chat_access_policy_decision(state)
    if chat_policy is not None:
        return chat_policy
    if state.intent == RuntimeIntent.MAIN_AGENT:
        if state.actor.role != ActorRole.OWNER:
            return RootPolicyDecision(
                decision="denied",
                reason="main_agent requires owner access",
                allow_dispatch=False,
                should_reply=True,
                response_text="RootGraph rejected: owner access is required for MainAgent.",
                error="permission_denied",
            )
        if state.session.session_type == SessionType.GROUP:
            return RootPolicyDecision(
                decision="denied",
                reason="main_agent is private-only",
                allow_dispatch=False,
                should_reply=True,
                response_text="RootGraph rejected: MainAgent is private-only.",
                error="group_denied",
            )
    return RootPolicyDecision(
        decision="allow",
        reason="policy allows dispatch",
        allow_dispatch=True,
        should_reply=True,
    )


def runtime_context_level_for_intent(intent: RuntimeIntent) -> str:
    if intent == RuntimeIntent.CHAT:
        return "chat_context"
    if intent == RuntimeIntent.MAIN_AGENT:
        return "minimal_context"
    return "minimal_context"
