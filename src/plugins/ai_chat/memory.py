from collections import defaultdict, deque
from typing import Deque


Message = dict[str, str]
_sessions: dict[str, Deque[Message]] = defaultdict(deque)


def build_history(session_key: str, max_messages: int) -> list[Message]:
    history = list(_sessions[session_key])
    if max_messages <= 0:
        return []
    return history[-max_messages:]


def append_message(session_key: str, role: str, content: str, max_messages: int) -> None:
    messages = _sessions[session_key]
    messages.append({"role": role, "content": content})
    limit = max(max_messages, 1)
    while len(messages) > limit:
        messages.popleft()


def clear_session(session_key: str) -> None:
    _sessions.pop(session_key, None)
