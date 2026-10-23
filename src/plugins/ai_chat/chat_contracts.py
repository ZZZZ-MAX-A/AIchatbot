from __future__ import annotations

from dataclasses import dataclass, field

from .sticker_intent import StickerIntent


@dataclass(frozen=True)
class ChatImageContext:
    urls: list[str]
    has_context: bool
    should_continue: bool = True


@dataclass(frozen=True)
class ChatPromptContext:
    history: list[dict[str, str]]
    user_id: str
    group_id: str | None
    semantic_memory_query: str = ""
    semantic_memory_result_count: int = 0
    semantic_memory_context_chars: int = 0
    semantic_memory_error: str = ""
    semantic_memory_hits: tuple[dict[str, object], ...] = ()
    bilibili_memory_status: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ChatUserContent:
    original: str
    for_llm: str
    stored: str
    vision_failed: bool = False


@dataclass(frozen=True)
class ChatTurn:
    stored_user: str
    stored_assistant: str


@dataclass(frozen=True)
class ChatOptions:
    silent_limit_rejection: bool = False
    semantic_voice: bool = False
    semantic_goal: str = ""
    tts_refresh_cache: bool = False
    preserve_original: bool = False
    tts_language: str = "zh"


@dataclass(frozen=True)
class ChatRequest:
    key: str
    text: str
    image_context: ChatImageContext
    persona_id: str = ""
    role_card_key: str = ""
    persistent_memory_enabled: bool = True
    persona_memory_enabled: bool = False
    tts_enabled: bool = True


@dataclass(frozen=True)
class ChatRuntimeResult:
    reply: str
    stored_assistant: str
    voice_text: str | None = None
    sticker_intent: StickerIntent | None = None
    time_observation: dict[str, object] | None = None
    interaction_success_eligible: bool = True
    tool_observation: dict[str, object] | None = None
    assistant_sent_at: str | None = None
