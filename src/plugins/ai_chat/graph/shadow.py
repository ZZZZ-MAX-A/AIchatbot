from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .chat import ChatState


SHADOW_CHAT_STAGES: tuple[str, ...] = (
    "request",
    "vision",
    "prompt",
    "result",
    "finalizing",
)
KNOWN_PRODUCTION_ROUTES = frozenset({"legacy_chat_runtime", "root_graph_chat"})
PROMPT_READY_STAGES = frozenset({"prompt", "result", "finalizing"})
RESULT_READY_STAGES = frozenset({"result", "finalizing"})


@dataclass(frozen=True)
class ShadowChatSnapshot:
    stage: str
    production_route: str
    session_key: str
    session_type: str
    group_id: str
    user_id: str
    actor_role: str
    intent: str
    mode: str
    message_id: str
    has_image: bool
    has_image_context: bool
    image_url_count: int
    image_description_count: int
    history_count: int
    system_context_count: int
    has_user_content: bool
    user_content_chars: int
    llm_user_content_chars: int
    has_reply: bool
    reply_chars: int
    should_reply_text: bool
    has_voice_text: bool
    has_persisted_turn: bool
    has_error: bool
    tool_event_count: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ShadowChatValidation:
    stage: str
    is_valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def shadow_chat_snapshot_from_state(state: ChatState) -> ShadowChatSnapshot:
    runtime = state.runtime
    shadow_artifact = runtime.artifacts.get("shadow_chat", {})
    intent = runtime.intent.value if runtime.intent is not None else ""
    return ShadowChatSnapshot(
        stage=str(shadow_artifact.get("stage", "")),
        production_route=str(shadow_artifact.get("production_route", "")),
        session_key=runtime.session.session_key,
        session_type=runtime.session.session_type.value,
        group_id=runtime.session.group_id,
        user_id=runtime.actor.user_id,
        actor_role=runtime.actor.role.value,
        intent=intent,
        mode=state.mode.value,
        message_id=runtime.event.message_id,
        has_image=runtime.event.has_image,
        has_image_context=state.vision.has_image_context,
        image_url_count=len(state.vision.image_urls),
        image_description_count=len(state.vision.descriptions),
        history_count=len(state.history),
        system_context_count=len(state.system_contexts),
        has_user_content=bool(state.user_content),
        user_content_chars=len(state.user_content),
        llm_user_content_chars=len(state.llm_user_content),
        has_reply=bool(state.reply),
        reply_chars=len(state.reply),
        should_reply_text=state.should_reply_text,
        has_voice_text=bool(state.voice_text),
        has_persisted_turn=state.persisted_turn is not None,
        has_error=bool(runtime.error),
        tool_event_count=len(runtime.tool_events),
    )


def validate_shadow_chat_snapshot(snapshot: ShadowChatSnapshot) -> ShadowChatValidation:
    errors: list[str] = []
    warnings: list[str] = []

    if snapshot.stage not in SHADOW_CHAT_STAGES:
        errors.append("unknown shadow stage")
    if not snapshot.production_route:
        errors.append("missing production route")
    elif snapshot.production_route not in KNOWN_PRODUCTION_ROUTES:
        warnings.append("unexpected production route")
    if not snapshot.session_key:
        errors.append("missing session key")
    if snapshot.session_type not in {"private", "group"}:
        errors.append("invalid session type")
    if snapshot.session_type == "group" and not snapshot.group_id:
        errors.append("missing group id for group session")
    if not snapshot.user_id:
        errors.append("missing user id")
    if not snapshot.actor_role:
        errors.append("missing actor role")
    if snapshot.intent != "chat":
        warnings.append("unexpected runtime intent")
    if snapshot.has_error:
        warnings.append("runtime state has error")
    if snapshot.tool_event_count:
        warnings.append("shadow chat unexpectedly contains tool events")
    if snapshot.has_image_context and snapshot.image_url_count == 0 and snapshot.image_description_count == 0:
        warnings.append("image context has no urls or descriptions")

    if snapshot.stage in PROMPT_READY_STAGES:
        if snapshot.history_count <= 0:
            errors.append("prompt-ready stage has no history")
        if not snapshot.has_user_content:
            errors.append("prompt-ready stage has no user content")
        if snapshot.llm_user_content_chars <= 0:
            errors.append("prompt-ready stage has no llm user content")

    if snapshot.stage in RESULT_READY_STAGES:
        if not snapshot.has_reply:
            errors.append("result-ready stage has no reply")
        if snapshot.reply_chars <= 0:
            errors.append("result-ready stage has empty reply")
        if not snapshot.has_persisted_turn:
            errors.append("result-ready stage has no persisted turn")
        if not snapshot.should_reply_text and not snapshot.has_voice_text:
            errors.append("non-text result has no voice text")

    return ShadowChatValidation(
        stage=snapshot.stage,
        is_valid=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
