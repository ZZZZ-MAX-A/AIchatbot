from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .chat import ChatState


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
