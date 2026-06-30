from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TypeAlias


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
    semantic_goal: str = ""
    preserve_original: bool = False
    language: str = "zh"
    sent: bool = False
    error: str = ""


@dataclass(frozen=True)
class VoiceArtifact:
    audio_path: Path
    duration_seconds: float
    voice_text: str


@dataclass(frozen=True)
class VoiceGraphResult:
    sent: bool
    audio_path: Path | None = None
    duration_seconds: float = 0.0
    voice_text: str = ""
    error: str = ""


@dataclass(frozen=True)
class VoiceGraphExecution:
    state: VoiceState
    result: VoiceGraphResult
    node_trace: tuple[VoiceNode, ...]


VoiceStateHandler: TypeAlias = Callable[[VoiceState], VoiceState | Awaitable[VoiceState]]


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


class VoiceGraphRunner:
    """Executable voice graph boundary with injected side-effect handlers."""

    def __init__(
        self,
        *,
        check_voice_policy: VoiceStateHandler | None = None,
        select_text_source: VoiceStateHandler | None = None,
        maybe_call_chat_agent: VoiceStateHandler | None = None,
        adapt_speech_text: VoiceStateHandler | None = None,
        check_tts_health: VoiceStateHandler | None = None,
        generate_tts: VoiceStateHandler | None = None,
        send_private_record: VoiceStateHandler | None = None,
    ) -> None:
        self.check_voice_policy = check_voice_policy
        self.select_text_source = select_text_source
        self.maybe_call_chat_agent = maybe_call_chat_agent
        self.adapt_speech_text = adapt_speech_text
        self.check_tts_health = check_tts_health
        self.generate_tts = generate_tts
        self.send_private_record = send_private_record

    async def run(self, state: VoiceState) -> VoiceGraphExecution:
        node_trace: list[VoiceNode] = []
        current = state

        for node in VOICE_NODE_SEQUENCE:
            node_trace.append(node)
            if node == VoiceNode.CHECK_VOICE_POLICY and self.check_voice_policy is not None:
                current = await _maybe_await(self.check_voice_policy(current))
            elif node == VoiceNode.SELECT_TEXT_SOURCE and self.select_text_source is not None:
                current = await _maybe_await(self.select_text_source(current))
            elif node == VoiceNode.MAYBE_CALL_CHAT_AGENT and self.maybe_call_chat_agent is not None:
                current = await _maybe_await(self.maybe_call_chat_agent(current))
            elif node == VoiceNode.ADAPT_SPEECH_TEXT and self.adapt_speech_text is not None:
                current = await _maybe_await(self.adapt_speech_text(current))
            elif node == VoiceNode.CHECK_TTS_HEALTH and self.check_tts_health is not None:
                current = await _maybe_await(self.check_tts_health(current))
            elif node == VoiceNode.GENERATE_TTS and self.generate_tts is not None:
                current = await _maybe_await(self.generate_tts(current))
            elif node == VoiceNode.SEND_PRIVATE_RECORD and self.send_private_record is not None:
                current = await _maybe_await(self.send_private_record(current))

            if current.error:
                break

        result = VoiceGraphResult(
            sent=current.sent,
            audio_path=current.audio_path,
            duration_seconds=current.duration_seconds,
            voice_text=current.voice_text or current.adapted_text or current.source_text,
            error=current.error,
        )
        return VoiceGraphExecution(current, result, tuple(node_trace))
