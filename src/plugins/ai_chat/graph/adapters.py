from __future__ import annotations

from dataclasses import replace

from ..chat_contracts import (
    ChatImageContext,
    ChatOptions,
    ChatPromptContext,
    ChatRequest,
    ChatRuntimeResult,
    ChatTurn,
    ChatUserContent,
)
from .chat import ChatGraphResult, ChatMode, ChatState, initial_chat_state
from .memory import PersistedTurn
from .state import (
    ActorContext,
    ActorRole,
    EventContext,
    RuntimeIntent,
    RuntimeState,
    SessionContext,
    SessionType,
)
from .vision import VisionContext


MAIN_AGENT_COMMAND_PREFIXES: tuple[str, ...] = ("/agent", "/main-agent")


def parse_main_agent_command_text(
    text: str,
    *,
    prefixes: tuple[str, ...] = MAIN_AGENT_COMMAND_PREFIXES,
) -> str | None:
    stripped = text.strip()
    for prefix in prefixes:
        if stripped == prefix:
            return ""
        if stripped.startswith(prefix):
            suffix = stripped[len(prefix) :]
            if suffix and suffix[0].isspace():
                return suffix.strip()
    return None


def runtime_state_from_main_agent_command(
    raw_text: str,
    *,
    user_id: str,
    actor_role: ActorRole,
    session_type: SessionType,
    session_key: str,
    group_id: str | None = None,
    message_id: str = "",
) -> RuntimeState | None:
    query = parse_main_agent_command_text(raw_text)
    if query is None:
        return None
    return RuntimeState(
        event=EventContext(
            message_id=message_id,
            raw_text=raw_text,
            plain_text=query,
            has_image=False,
        ),
        actor=ActorContext(user_id=user_id, role=actor_role),
        session=SessionContext(
            session_type=session_type,
            session_key=session_key,
            group_id=group_id or "",
        ),
        intent=RuntimeIntent.MAIN_AGENT,
        artifacts={"main_agent_command": {"prefixes": MAIN_AGENT_COMMAND_PREFIXES}},
    )


def chat_mode_from_options(options: ChatOptions) -> ChatMode:
    if options.semantic_voice:
        return ChatMode.SEMANTIC_VOICE
    return ChatMode.TEXT


def vision_context_from_image_context(
    image_context: ChatImageContext,
    *,
    descriptions: list[str] | None = None,
    context_text: str = "",
    error: str = "",
) -> VisionContext:
    return VisionContext(
        has_image=bool(image_context.urls) or image_context.has_context,
        has_image_context=image_context.has_context,
        image_urls=list(image_context.urls),
        descriptions=list(descriptions or []),
        context_text=context_text,
        error=error,
    )


def runtime_state_from_chat_request(
    request: ChatRequest,
    *,
    user_id: str,
    actor_role: ActorRole,
    session_type: SessionType,
    group_id: str | None = None,
    message_id: str = "",
    raw_text: str | None = None,
    intent: RuntimeIntent = RuntimeIntent.CHAT,
    task_id: int | None = None,
) -> RuntimeState:
    return RuntimeState(
        event=EventContext(
            message_id=message_id,
            raw_text=request.text if raw_text is None else raw_text,
            plain_text=request.text,
            has_image=request.image_context.has_context,
        ),
        actor=ActorContext(user_id=user_id, role=actor_role),
        session=SessionContext(
            session_type=session_type,
            session_key=request.key,
            group_id=group_id or "",
        ),
        intent=intent,
        task_id=task_id,
        artifacts={
            "legacy_chat_request": {
                "image_urls": tuple(request.image_context.urls),
                "has_image_context": request.image_context.has_context,
            }
        },
    )


def chat_state_from_chat_request(
    runtime: RuntimeState,
    request: ChatRequest,
    options: ChatOptions,
) -> ChatState:
    state = initial_chat_state(
        runtime,
        mode=chat_mode_from_options(options),
        semantic_goal=options.semantic_goal,
        preserve_original=options.preserve_original,
        tts_refresh_cache=options.tts_refresh_cache,
    )
    state.text = request.text
    state.vision = vision_context_from_image_context(request.image_context)
    return state


def chat_state_with_prompt_context(
    state: ChatState,
    prompt_context: ChatPromptContext,
    user_content: ChatUserContent,
    *,
    llm_user_content: str = "",
) -> ChatState:
    history = list(prompt_context.history)
    memory = replace(
        state.memory,
        history=history,
        semantic_memory_error=prompt_context.semantic_memory_error,
        semantic_memory_result_count=prompt_context.semantic_memory_result_count,
        semantic_memory_hits=list(prompt_context.semantic_memory_hits),
    )
    return replace(
        state,
        memory=memory,
        history=history,
        original_user_content=user_content.original,
        user_content=user_content.for_llm,
        llm_user_content=llm_user_content or user_content.for_llm,
    )


def chat_state_with_vision_result(
    state: ChatState,
    *,
    descriptions: list[str],
    context_text: str = "",
    error: str = "",
) -> ChatState:
    vision = replace(
        state.vision,
        descriptions=list(descriptions),
        context_text=context_text,
        error=error,
    )
    return replace(state, vision=vision)


def persisted_turn_from_chat_turn(
    request: ChatRequest,
    prompt_context: ChatPromptContext,
    turn: ChatTurn,
    *,
    message_type: str,
) -> PersistedTurn:
    return PersistedTurn(
        session_key=request.key,
        user_content=turn.stored_user,
        assistant_content=turn.stored_assistant,
        message_type=message_type,
        user_id=prompt_context.user_id,
        group_id=prompt_context.group_id,
    )


def chat_graph_result_from_runtime_result(
    result: ChatRuntimeResult,
    options: ChatOptions,
    *,
    persisted_turn: PersistedTurn | None = None,
) -> ChatGraphResult:
    return ChatGraphResult(
        reply=result.reply,
        should_reply_text=not options.semantic_voice,
        voice_text=result.voice_text or "",
        persisted_turn=persisted_turn,
    )


def chat_state_with_runtime_result(
    state: ChatState,
    result: ChatRuntimeResult,
    options: ChatOptions,
    *,
    persisted_turn: PersistedTurn | None = None,
) -> ChatState:
    runtime = replace(state.runtime, response=result.reply)
    return replace(
        state,
        runtime=runtime,
        reply=result.reply,
        voice_text=result.voice_text or "",
        persisted_turn=persisted_turn,
        should_reply_text=not options.semantic_voice,
    )
