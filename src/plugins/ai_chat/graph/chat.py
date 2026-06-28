from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .memory import MemoryContext, PersistedTurn
from .state import RuntimeState
from .vision import VisionContext


class ChatMode(str, Enum):
    TEXT = "text"
    SEMANTIC_VOICE = "semantic_voice"


class ChatNode(str, Enum):
    VALIDATE_INPUT = "validate_input"
    RESOLVE_IMAGE_CONTEXT = "resolve_image_context"
    PREPARE_MEMORY = "prepare_memory"
    BUILD_PROMPT_CONTEXT = "build_prompt_context"
    CALL_CHAT_AGENT = "call_chat_agent"
    MAYBE_VOICE_RESPONSE = "maybe_voice_response"
    PERSIST_TURN = "persist_turn"
    UPDATE_TRIAL_ACCOUNTING = "update_trial_accounting"
    UPDATE_TTS_CANDIDATE = "update_tts_candidate"
    SCHEDULE_COMPRESSION = "schedule_compression"
    RENDER_RESPONSE = "render_response"


CHAT_NODE_SEQUENCE: tuple[ChatNode, ...] = (
    ChatNode.VALIDATE_INPUT,
    ChatNode.RESOLVE_IMAGE_CONTEXT,
    ChatNode.PREPARE_MEMORY,
    ChatNode.BUILD_PROMPT_CONTEXT,
    ChatNode.CALL_CHAT_AGENT,
    ChatNode.MAYBE_VOICE_RESPONSE,
    ChatNode.PERSIST_TURN,
    ChatNode.UPDATE_TRIAL_ACCOUNTING,
    ChatNode.UPDATE_TTS_CANDIDATE,
    ChatNode.SCHEDULE_COMPRESSION,
    ChatNode.RENDER_RESPONSE,
)


@dataclass
class ChatState:
    runtime: RuntimeState
    mode: ChatMode = ChatMode.TEXT
    text: str = ""
    semantic_goal: str = ""
    preserve_original: bool = False
    tts_refresh_cache: bool = False
    vision: VisionContext = field(default_factory=VisionContext)
    memory: MemoryContext = field(default_factory=MemoryContext)
    system_contexts: list[str] = field(default_factory=list)
    history: list[dict[str, str]] = field(default_factory=list)
    original_user_content: str = ""
    user_content: str = ""
    llm_user_content: str = ""
    reply: str = ""
    voice_text: str = ""
    persisted_turn: PersistedTurn | None = None
    should_reply_text: bool = True


@dataclass(frozen=True)
class ChatGraphResult:
    reply: str
    should_reply_text: bool
    voice_text: str = ""
    persisted_turn: PersistedTurn | None = None


def initial_chat_state(
    runtime: RuntimeState,
    *,
    mode: ChatMode = ChatMode.TEXT,
    semantic_goal: str = "",
    preserve_original: bool = False,
    tts_refresh_cache: bool = False,
) -> ChatState:
    return ChatState(
        runtime=runtime,
        mode=mode,
        text=runtime.event.plain_text,
        semantic_goal=semantic_goal,
        preserve_original=preserve_original,
        tts_refresh_cache=tts_refresh_cache,
    )
