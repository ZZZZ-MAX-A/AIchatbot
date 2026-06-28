from __future__ import annotations

from dataclasses import dataclass


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


@dataclass(frozen=True)
class ChatUserContent:
    original: str
    for_llm: str
    stored: str


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


@dataclass(frozen=True)
class ChatRuntimeResult:
    reply: str
    stored_assistant: str
    voice_text: str | None = None
