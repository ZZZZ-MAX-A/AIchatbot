from __future__ import annotations

from threading import RLock
from datetime import datetime, timezone

from .memory_time import message_time_context, parse_memory_time


Message = dict[str, str]


class EphemeralPersonaHistory:
    """Process-local short-term history for isolated Persona V2 trials.

    No method in this class opens the project database or writes to disk.
    Restarting the bot intentionally discards all routed-persona history.
    """

    def __init__(self) -> None:
        self._messages: dict[str, list[Message]] = {}
        self._lock = RLock()

    def build_history(
        self,
        session_key: str,
        max_messages: int,
        system_contexts: list[str] | None = None,
    ) -> list[Message]:
        history = [
            {"role": "system", "content": context}
            for context in (system_contexts or [])
            if context
        ]
        if max_messages <= 0:
            return history
        with self._lock:
            messages = [dict(item) for item in self._messages.get(session_key, ())]
        now = datetime.now(timezone.utc)
        history.extend({"role": item["role"], "content": message_time_context(item, now=now) + "\n" + item["content"]}
                       for item in messages[-max_messages:])
        return history

    def append_turn(
        self,
        session_key: str,
        user_content: str,
        assistant_content: str,
        max_messages: int,
        *,
        user_occurred_at: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        instant = parse_memory_time(user_occurred_at)
        turn = [
            {"role": "user", "content": user_content.strip(), "created_at": now,
             "occurred_at": instant.isoformat() if instant else "", "time_kind": "platform_sent" if instant else ""},
            {"role": "assistant", "content": assistant_content.strip(), "created_at": now},
        ]
        with self._lock:
            messages = self._messages.setdefault(session_key, [])
            messages.extend(turn)
            if max_messages > 0 and len(messages) > max_messages:
                del messages[:-max_messages]

    def mark_assistant_sent(self, session_key: str, content: str, *, sent_at: str | None = None) -> None:
        instant = parse_memory_time(sent_at) or datetime.now(timezone.utc)
        with self._lock:
            messages = self._messages.get(session_key, ())
            if messages and messages[-1]["role"] == "assistant" and messages[-1]["content"] == content.strip():
                message = messages[-1]
                if message.get("time_kind") != "reply_sent":
                    message.update(occurred_at=instant.astimezone(timezone.utc).isoformat(timespec="seconds"), time_kind="reply_sent")

    def clear(self, session_key: str) -> None:
        with self._lock:
            self._messages.pop(session_key, None)

    def clear_all(self) -> None:
        with self._lock:
            self._messages.clear()

    def message_count(self, session_key: str) -> int:
        with self._lock:
            return len(self._messages.get(session_key, ()))


ephemeral_persona_history = EphemeralPersonaHistory()
