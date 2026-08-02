from __future__ import annotations

from collections import OrderedDict
from threading import Lock


EXTERNAL_READ_EPHEMERAL_DETAIL_LIMIT = 20

_DETAILS: OrderedDict[tuple[str, str, int], str] = OrderedDict()
_DETAILS_LOCK = Lock()


def remember_external_read_ephemeral_detail(
    *,
    session_key: str,
    user_id: str,
    task_id: int,
    detail_text: str,
) -> None:
    """Keep bounded external evidence details in memory for the current process only."""
    if not session_key or not user_id or task_id <= 0:
        raise ValueError("external read ephemeral detail identity is invalid")
    normalized = str(detail_text).strip()
    if not normalized:
        return
    key = (session_key, user_id, task_id)
    with _DETAILS_LOCK:
        _DETAILS.pop(key, None)
        _DETAILS[key] = normalized
        while len(_DETAILS) > EXTERNAL_READ_EPHEMERAL_DETAIL_LIMIT:
            _DETAILS.popitem(last=False)


def get_external_read_ephemeral_detail(
    *,
    session_key: str,
    user_id: str,
    task_id: int,
) -> str | None:
    key = (session_key, user_id, task_id)
    with _DETAILS_LOCK:
        detail = _DETAILS.get(key)
        if detail is not None:
            _DETAILS.move_to_end(key)
        return detail


def clear_external_read_ephemeral_details_for_tests() -> None:
    with _DETAILS_LOCK:
        _DETAILS.clear()
