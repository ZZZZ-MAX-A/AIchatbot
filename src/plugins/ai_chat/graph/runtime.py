from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeAlias

from .root import (
    ROOT_NODE_SEQUENCE,
    RootNode,
    RootPolicyDecision,
    RouteDecision,
    evaluate_hard_policy,
    route_from_explicit_intent,
    runtime_context_level_for_intent,
)
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
        passthrough_exceptions: tuple[type[BaseException], ...] = (),
    ) -> None:
        self.handlers = dict(handlers or {})
        self.passthrough_exceptions = passthrough_exceptions

    async def run(self, state: RuntimeState) -> RuntimeResponse:
        node_trace: list[RootNode] = []
        route = RouteDecision(RuntimeIntent.IGNORE, "route was not evaluated")
        policy = RootPolicyDecision(
            decision="allow",
            reason="policy was not evaluated",
            allow_dispatch=True,
        )
        context_level = "minimal_context"
        response: RuntimeResponse | None = None
        dispatched = False
        dispatch_error = ""
        error_source = ""

        for node in ROOT_NODE_SEQUENCE:
            node_trace.append(node)
            if node == RootNode.NORMALIZE_EVENT:
                self._record_normalized_artifact(state)
            elif node == RootNode.LOAD_ACTOR_CONTEXT:
                self._record_actor_artifact(state)
            elif node == RootNode.HARD_POLICY_GATE:
                policy = evaluate_hard_policy(state)
                self._record_policy_artifact(state, policy)
            elif node == RootNode.ROUTE_INTENT:
                route = route_from_explicit_intent(state)
                if not policy.allow_dispatch:
                    route = RouteDecision(RuntimeIntent.IGNORE, policy.reason)
                self._record_route_artifact(state, route, dispatched=False)
            elif node == RootNode.BUILD_RUNTIME_CONTEXT:
                context_level = runtime_context_level_for_intent(route.intent)
                self._record_context_artifact(state, route, context_level)
            elif node == RootNode.DISPATCH_CAPABILITY:
                if policy.allow_dispatch:
                    try:
                        response, dispatched = await self._dispatch(state, route)
                    except self.passthrough_exceptions:
                        raise
                    except Exception as exc:
                        dispatch_error = f"{type(exc).__name__}: {exc}"
                        error_source = "dispatch_exception"
                        state.error = dispatch_error
                        response = RuntimeResponse(
                            f"Agent Runtime error: {dispatch_error}",
                            should_reply=True,
                        )
                        dispatched = False
                else:
                    state.error = policy.error or state.error
                    if state.error:
                        error_source = "policy"
                    response = RuntimeResponse(
                        policy.response_text,
                        should_reply=policy.should_reply,
                    )
                self._record_route_artifact(state, route, dispatched=dispatched)
            elif node == RootNode.COMMIT_SIDE_EFFECTS:
                self._record_commit_artifact(state, route, response, dispatched)
            elif node == RootNode.RENDER_RESPONSE and response is None:
                response = RuntimeResponse("", should_reply=False)

        final_response = response or RuntimeResponse("", should_reply=False)
        state.response = final_response.text
        if dispatch_error:
            state.error = dispatch_error
        if state.error and not error_source:
            error_source = "handler" if dispatched else "runtime"
        self._record_error_artifact(
            state,
            route,
            dispatched,
            policy=policy,
            response=final_response,
            source=error_source,
        )
        self._record_artifact(
            state,
            node_trace,
            route,
            dispatched,
            policy=policy,
            context_level=context_level,
            response=final_response,
        )
        return final_response

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
        *,
        policy: RootPolicyDecision,
        context_level: str,
        response: RuntimeResponse,
    ) -> None:
        state.artifacts["root_graph"] = {
            "node_trace": tuple(node.value for node in node_trace),
            "route": route.intent.value,
            "reason": route.reason,
            "dispatched": dispatched,
            "policy_decision": policy.decision,
            "context_level": context_level,
            "should_reply": response.should_reply,
            "error": state.error or "",
        }

    def _record_error_artifact(
        self,
        state: RuntimeState,
        route: RouteDecision,
        dispatched: bool,
        *,
        policy: RootPolicyDecision,
        response: RuntimeResponse,
        source: str,
    ) -> None:
        if not state.error:
            return
        state.artifacts["error"] = {
            "source": source or "runtime",
            "message": state.error,
            "route": route.intent.value,
            "policy_decision": policy.decision,
            "dispatched": dispatched,
            "should_reply": response.should_reply,
            "response_text_set": bool(response.text),
        }

    def _record_normalized_artifact(self, state: RuntimeState) -> None:
        state.artifacts["normalized_event"] = {
            "message_id": state.event.message_id,
            "has_plain_text": bool(state.event.plain_text.strip()),
            "has_image": state.event.has_image,
            "session_key": state.session.session_key,
        }

    def _record_actor_artifact(self, state: RuntimeState) -> None:
        state.artifacts["actor_context"] = {
            "user_id": state.actor.user_id,
            "role": state.actor.role.value,
            "session_type": state.session.session_type.value,
            "group_id": state.session.group_id,
        }

    def _record_policy_artifact(
        self,
        state: RuntimeState,
        policy: RootPolicyDecision,
    ) -> None:
        state.artifacts["policy"] = {
            "decision": policy.decision,
            "reason": policy.reason,
            "actor_role": state.actor.role.value,
            "allow_dispatch": policy.allow_dispatch,
            "allow_chat": policy.allow_dispatch and state.intent == RuntimeIntent.CHAT,
            "allow_main_agent": policy.allow_dispatch
            and state.intent == RuntimeIntent.MAIN_AGENT,
            "should_reply": policy.should_reply,
            "error": policy.error,
        }

    def _record_route_artifact(
        self,
        state: RuntimeState,
        route: RouteDecision,
        *,
        dispatched: bool,
    ) -> None:
        selected_handler = ""
        if route.intent in self.handlers:
            selected_handler = route.intent.value
        elif route.intent == RuntimeIntent.IGNORE:
            selected_handler = "ignore"
        elif state.response:
            selected_handler = "existing_response"
        state.artifacts["route"] = {
            "intent": route.intent.value,
            "reason": route.reason,
            "selected_handler": selected_handler,
            "dispatched": dispatched,
        }

    def _record_context_artifact(
        self,
        state: RuntimeState,
        route: RouteDecision,
        context_level: str,
    ) -> None:
        state.artifacts["context"] = {
            "context_level": context_level,
            "memory_rag_enabled": route.intent == RuntimeIntent.CHAT,
            "project_doc_rag_enabled": False,
            "project_doc_rag_scope": "dev_context_tool_only"
            if route.intent == RuntimeIntent.MAIN_AGENT
            else "",
            "vision_used": state.event.has_image and route.intent == RuntimeIntent.CHAT,
        }

    def _record_commit_artifact(
        self,
        state: RuntimeState,
        route: RouteDecision,
        response: RuntimeResponse | None,
        dispatched: bool,
    ) -> None:
        main_agent_artifact = state.artifacts.get("main_agent_graph")
        chat_artifact = state.artifacts.get("chat_graph")
        chat_commit = state.artifacts.get("chat_commit")
        if not isinstance(chat_commit, dict):
            chat_commit = {}
        chat_runtime = state.artifacts.get("chat_runtime")
        if not isinstance(chat_runtime, dict):
            chat_runtime = {}
        state.artifacts["commit"] = {
            "handler_dispatched": dispatched,
            "response_text_set": bool(response and response.text),
            "should_reply": bool(response and response.should_reply),
            "chat_graph_completed": isinstance(chat_artifact, dict)
            and chat_artifact.get("status") == "complete",
            "chat_reply_sent": bool(chat_commit.get("qq_reply_sent")),
            "chat_voice_sent": bool(chat_commit.get("voice_response_sent")),
            "chat_persisted": bool(chat_commit.get("persisted_turn_saved")),
            "chat_trial_updated": bool(chat_commit.get("trial_updated")),
            "chat_compression_scheduled": bool(
                chat_commit.get("compression_scheduled")
            ),
            "chat_tts_candidate_updated": bool(
                chat_commit.get("tts_candidate_updated")
            ),
            "chat_image_context_deferred": bool(
                chat_commit.get("image_context_deferred")
                or chat_runtime.get("stage") == "image_context_deferred"
            ),
            "chat_runtime_stage": str(chat_runtime.get("stage") or ""),
            "main_agent_dispatched": route.intent == RuntimeIntent.MAIN_AGENT and dispatched,
            "approval_created": isinstance(main_agent_artifact, dict)
            and main_agent_artifact.get("error") == "approval_required",
        }


class AgentRuntime:
    """Runtime boundary for RootGraph integration."""

    def __init__(self, root_runner: RootGraphRunner | None = None) -> None:
        self.root_runner = root_runner or RootGraphRunner()

    async def run(self, state: RuntimeState) -> RuntimeResponse:
        return await self.root_runner.run(state)
