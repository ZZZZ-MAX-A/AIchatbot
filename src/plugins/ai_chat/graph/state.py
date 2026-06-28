from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ActorRole(str, Enum):
    OWNER = "owner"
    WHITELISTED = "whitelisted"
    USER = "user"
    BLOCKED = "blocked"


class SessionType(str, Enum):
    PRIVATE = "private"
    GROUP = "group"


class RuntimeIntent(str, Enum):
    CHAT = "chat"
    MAIN_AGENT = "main_agent"
    VOICE = "voice"
    VISION = "vision"
    MEMORY_ADMIN = "memory_admin"
    DIAGNOSTICS = "diagnostics"
    OWNER_NOTIFICATION = "owner_notification"
    ADMIN_COMMAND = "admin_command"
    IGNORE = "ignore"


@dataclass(frozen=True)
class ActorContext:
    user_id: str
    role: ActorRole


@dataclass(frozen=True)
class SessionContext:
    session_type: SessionType
    session_key: str
    group_id: str = ""


@dataclass(frozen=True)
class EventContext:
    message_id: str
    raw_text: str
    plain_text: str
    has_image: bool = False


@dataclass
class RuntimeState:
    event: EventContext
    actor: ActorContext
    session: SessionContext
    intent: RuntimeIntent | None = None
    task_id: int | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)
    tool_events: list[dict[str, Any]] = field(default_factory=list)
    response: str | None = None
    error: str | None = None

