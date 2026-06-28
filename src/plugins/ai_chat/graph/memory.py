from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MemoryNode(str, Enum):
    ENSURE_GAP_SCENE = "ensure_gap_scene"
    BUILD_HISTORY = "build_history"
    BUILD_MANUAL_MEMORY_CONTEXT = "build_manual_memory_context"
    SAVE_USER_MESSAGE = "save_user_message"
    SAVE_ASSISTANT_MESSAGE = "save_assistant_message"
    SCHEDULE_COMPRESSION = "schedule_compression"


MEMORY_CONTEXT_NODE_SEQUENCE: tuple[MemoryNode, ...] = (
    MemoryNode.ENSURE_GAP_SCENE,
    MemoryNode.BUILD_MANUAL_MEMORY_CONTEXT,
    MemoryNode.BUILD_HISTORY,
)


MEMORY_PERSIST_NODE_SEQUENCE: tuple[MemoryNode, ...] = (
    MemoryNode.SAVE_USER_MESSAGE,
    MemoryNode.SAVE_ASSISTANT_MESSAGE,
    MemoryNode.SCHEDULE_COMPRESSION,
)


@dataclass
class MemoryContext:
    system_contexts: list[str] = field(default_factory=list)
    history: list[dict[str, str]] = field(default_factory=list)
    manual_long_term_context: str = ""
    rule_reminder_context: str = ""
    gap_scene_error: str = ""


@dataclass(frozen=True)
class PersistedTurn:
    session_key: str
    user_content: str
    assistant_content: str
    message_type: str
    user_id: str
    group_id: str | None = None
