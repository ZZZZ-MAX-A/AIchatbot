from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TypeAlias

from ..chat_contracts import ChatOptions, ChatRuntimeResult
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


@dataclass(frozen=True)
class ChatGraphExecution:
    state: ChatState
    result: ChatGraphResult
    node_trace: tuple[ChatNode, ...]


ChatAgentHandler: TypeAlias = Callable[
    [ChatState],
    ChatRuntimeResult | None | Awaitable[ChatRuntimeResult | None],
]
ChatPersistHandler: TypeAlias = Callable[
    [ChatState, ChatRuntimeResult],
    PersistedTurn | None | Awaitable[PersistedTurn | None],
]
ChatStateHandler: TypeAlias = Callable[[ChatState], ChatState | Awaitable[ChatState]]
ChatRuntimeStateHandler: TypeAlias = Callable[
    [ChatState, ChatRuntimeResult],
    ChatState | Awaitable[ChatState],
]


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


def chat_options_from_state(state: ChatState) -> ChatOptions:
    return ChatOptions(
        semantic_voice=state.mode == ChatMode.SEMANTIC_VOICE,
        semantic_goal=state.semantic_goal,
        tts_refresh_cache=state.tts_refresh_cache,
        preserve_original=state.preserve_original,
    )


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


class ChatGraphRunner:
    """Executable chat graph boundary with injected side-effect handlers."""

    def __init__(
        self,
        call_chat_agent: ChatAgentHandler,
        *,
        resolve_image_context: ChatStateHandler | None = None,
        build_prompt_context: ChatStateHandler | None = None,
        persist_turn: ChatPersistHandler | None = None,
        update_trial_accounting: ChatRuntimeStateHandler | None = None,
        update_tts_candidate: ChatRuntimeStateHandler | None = None,
        schedule_compression: ChatRuntimeStateHandler | None = None,
    ) -> None:
        self.call_chat_agent = call_chat_agent
        self.resolve_image_context = resolve_image_context
        self.build_prompt_context = build_prompt_context
        self.persist_turn = persist_turn
        self.update_trial_accounting = update_trial_accounting
        self.update_tts_candidate = update_tts_candidate
        self.schedule_compression = schedule_compression

    async def run(self, state: ChatState) -> ChatGraphExecution:
        node_trace: list[ChatNode] = []
        current = state
        runtime_result: ChatRuntimeResult | None = None
        persisted_turn = state.persisted_turn
        options = chat_options_from_state(state)

        for node in CHAT_NODE_SEQUENCE:
            node_trace.append(node)
            if node == ChatNode.VALIDATE_INPUT:
                if not (current.text or current.user_content or current.llm_user_content or current.vision.has_image):
                    current = self._with_graph_artifact(
                        current,
                        node_trace,
                        status="invalid",
                        error="chat input is empty",
                    )
                    result = ChatGraphResult(reply="", should_reply_text=False)
                    return ChatGraphExecution(current, result, tuple(node_trace))
            elif node == ChatNode.RESOLVE_IMAGE_CONTEXT:
                if self.resolve_image_context is not None:
                    current = await _maybe_await(self.resolve_image_context(current))
            elif node == ChatNode.BUILD_PROMPT_CONTEXT:
                if self.build_prompt_context is not None:
                    current = await _maybe_await(self.build_prompt_context(current))
            elif node == ChatNode.CALL_CHAT_AGENT:
                runtime_result = await _maybe_await(self.call_chat_agent(current))
            elif node == ChatNode.PERSIST_TURN:
                if runtime_result is not None and self.persist_turn is not None:
                    persisted_turn = await _maybe_await(self.persist_turn(current, runtime_result))
            elif node == ChatNode.UPDATE_TRIAL_ACCOUNTING:
                if runtime_result is not None and self.update_trial_accounting is not None:
                    current = await _maybe_await(self.update_trial_accounting(current, runtime_result))
            elif node == ChatNode.UPDATE_TTS_CANDIDATE:
                if runtime_result is not None and self.update_tts_candidate is not None:
                    current = await _maybe_await(self.update_tts_candidate(current, runtime_result))
            elif node == ChatNode.SCHEDULE_COMPRESSION:
                if runtime_result is not None and self.schedule_compression is not None:
                    current = await _maybe_await(self.schedule_compression(current, runtime_result))
            elif node == ChatNode.RENDER_RESPONSE:
                if runtime_result is None:
                    current = self._with_graph_artifact(
                        current,
                        node_trace,
                        status="error",
                        error="chat agent did not return a result",
                    )
                    result = ChatGraphResult(reply="", should_reply_text=False)
                    return ChatGraphExecution(current, result, tuple(node_trace))
                current = self._apply_runtime_result(
                    current,
                    runtime_result,
                    options,
                    persisted_turn=persisted_turn,
                )

        current = self._with_graph_artifact(current, node_trace, status="complete")
        result = ChatGraphResult(
            reply=current.reply,
            should_reply_text=current.should_reply_text,
            voice_text=current.voice_text,
            persisted_turn=current.persisted_turn,
        )
        return ChatGraphExecution(current, result, tuple(node_trace))

    def _apply_runtime_result(
        self,
        state: ChatState,
        result: ChatRuntimeResult,
        options: ChatOptions,
        *,
        persisted_turn: PersistedTurn | None,
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

    def _with_graph_artifact(
        self,
        state: ChatState,
        node_trace: list[ChatNode],
        *,
        status: str,
        error: str = "",
    ) -> ChatState:
        artifacts = dict(state.runtime.artifacts)
        artifacts["chat_graph"] = {
            "node_trace": tuple(node.value for node in node_trace),
            "status": status,
        }
        runtime = replace(
            state.runtime,
            artifacts=artifacts,
            error=error or state.runtime.error,
        )
        return replace(state, runtime=runtime)
