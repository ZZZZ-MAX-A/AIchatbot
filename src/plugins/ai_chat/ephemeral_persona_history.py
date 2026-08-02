from __future__ import annotations

from threading import RLock


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
            messages = list(self._messages.get(session_key, ()))
        history.extend(messages[-max_messages:])
        return history

    def append_turn(
        self,
        session_key: str,
        user_content: str,
        assistant_content: str,
        max_messages: int,
    ) -> None:
        turn = [
            {"role": "user", "content": user_content.strip()},
            {"role": "assistant", "content": assistant_content.strip()},
        ]
        with self._lock:
            messages = self._messages.setdefault(session_key, [])
            messages.extend(turn)
            if max_messages > 0 and len(messages) > max_messages:
                del messages[:-max_messages]

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
