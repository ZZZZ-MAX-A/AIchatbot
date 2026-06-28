from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class VoiceMode(str, Enum):
    DIRECT_TEXT = "direct_text"
    LAST_REPLY = "last_reply"
    SEMANTIC_REPLY = "semantic_reply"


class VoiceNode(str, Enum):
    PARSE_VOICE_INTENT = "parse_voice_intent"
    CHECK_VOICE_POLICY = "check_voice_policy"
    SELECT_TEXT_SOURCE = "select_text_source"
    MAYBE_CALL_CHAT_AGENT = "maybe_call_chat_agent"
    ADAPT_SPEECH_TEXT = "adapt_speech_text"
    CHECK_TTS_HEALTH = "check_tts_health"
    GENERATE_TTS = "generate_tts"
    SEND_PRIVATE_RECORD = "send_private_record"


VOICE_NODE_SEQUENCE: tuple[VoiceNode, ...] = (
    VoiceNode.PARSE_VOICE_INTENT,
    VoiceNode.CHECK_VOICE_POLICY,
    VoiceNode.SELECT_TEXT_SOURCE,
    VoiceNode.MAYBE_CALL_CHAT_AGENT,
    VoiceNode.ADAPT_SPEECH_TEXT,
    VoiceNode.CHECK_TTS_HEALTH,
    VoiceNode.GENERATE_TTS,
    VoiceNode.SEND_PRIVATE_RECORD,
)


@dataclass
class VoiceState:
    mode: VoiceMode
    source_text: str = ""
    adapted_text: str = ""
    voice_text: str = ""
    audio_path: Path | None = None
    duration_seconds: float = 0.0
    refresh_cache: bool = False
    error: str = ""


@dataclass(frozen=True)
class VoiceArtifact:
    audio_path: Path
    duration_seconds: float
    voice_text: str
