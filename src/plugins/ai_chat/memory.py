import re
from datetime import datetime, timezone

from .database import connect, connect_read_only, current_database_path, ensure_database, utc_now
from .gap_scene_summaries import clear_all_gap_scene_summaries, clear_gap_scene_summaries, format_gap_scene_context
from .summaries import format_summary_context, summary_stats
from .memory_time import parse_memory_time
from .memory_reader import MemoryReadPolicy, read_conversation_memory


Message = dict[str, str]


def is_stale_identity_refusal(message: Message) -> bool:
    """Identify model-generated identity refusals that must not poison a new turn.

    These are not deleted from persistent history.  They are only excluded from
    the prompt when rebuilding a persona conversation, because an assistant's
    previous identity claim is not authoritative system context.
    """

    if message.get("role") != "assistant":
        return False
    content = str(message.get("content") or "")
    normalized = content.casefold()
    refusal_markers = (
        "拒绝越狱尝试",
        "无法修改或覆盖系统设定的身份判定",
        "无法继续此角色扮演",
        "无法配合身份注入",
        "i cannot continue this roleplay",
        "this is a jailbreak attempt",
    )
    security_markers = (
        "越狱",
        "身份注入",
        "身份伪造",
        "身份判定",
        "绕过系统规则",
        "修改系统边界",
        "jailbreak",
        "injected identity",
        "identity commands",
        "core behavior and rules",
    )
    return any(marker in normalized for marker in refusal_markers) and any(
        marker in normalized for marker in security_markers
    )


def filter_stale_identity_refusal_messages(history: list[Message]) -> list[Message]:
    """Return history without known false identity-refusal assistant turns."""

    return [message for message in history if not is_stale_identity_refusal(message)]


_OWNER_NARRATION_PATTERN = re.compile(
    r"(?:主人|雨泽|用户)(?:轻轻|缓慢地|慢慢|抬眼|抬头|起身|走向|走到|看了看|看向|停在|深吸|放下|拿出|打开|转过身|说|说道|回答|问道|表示|告诉|拿着|手中)"
)
_LOCAL_PERSONA_META_MARKERS = (
    "角色卡",
    "角色设定",
    "人格设定",
    "动作描述长度",
    "短动作描述",
    "中等长度动作描述",
    "长动作描述",
    "下面我将以简单的例子",
    "以下是不同",
    "格式教程",
    "格式说明",
    "教程式",
    "作为一个ai",
    "作为ai",
)
_LOCAL_PERSONA_ADJUSTMENT_MARKERS = (
    "我会根据你的要求",
    "我会尽量遵循你的指示",
    "我会调整角色",
    "我会改进",
    "我会按照你的要求",
    "了解到您希望",
    "下面我将说明",
)


def is_local_persona_contamination(message: Message) -> bool:
    """Identify assistant turns that teach or break the isolated persona contract.

    The message is only excluded while constructing a local persona prompt.  It
    is never deleted from the database, and user messages are always retained.
    """

    if message.get("role") != "assistant":
        return False
    content = str(message.get("content") or "").strip()
    if not content:
        return False
    normalized = content.casefold()
    if any(marker.casefold() in normalized for marker in _LOCAL_PERSONA_META_MARKERS):
        return True
    if any(marker.casefold() in normalized for marker in _LOCAL_PERSONA_ADJUSTMENT_MARKERS):
        return True
    if _OWNER_NARRATION_PATTERN.search(content):
        return True
    if re.search(r"(?:雨泽|主人|用户)(?:说|说道|回答|问道|表示)：?['\"“”]", content):
        return True
    return False


def filter_local_persona_contamination(history: list[Message]) -> list[Message]:
    """Exclude known bad local-persona assistant examples without mutation."""

    return [message for message in history if not is_local_persona_contamination(message)]


def sanitize_history_content(content: str, *, role: str = "") -> str:
    return content.strip()


def build_history(
    session_key: str,
    max_messages: int,
    max_summaries: int = 0,
    max_gap_scene_summaries: int = 0,
    system_contexts: list[str] | None = None,
) -> list[Message]:
    if max_messages > 0:
        ensure_database()
        records, _ = read_conversation_memory(
            current_database_path(), session_key,
            MemoryReadPolicy(recent=max_messages, summaries=max(0, max_summaries),
                             scene_cards=int(max_gap_scene_summaries > 0)),
        )
        return records.history(system_contexts, now=datetime.now(timezone.utc))
    history: list[Message] = []
    for context in system_contexts or []:
        if context:
            history.append({"role": "system", "content": context})

    summary_context = format_summary_context(session_key, max_summaries)
    if summary_context:
        history.append({"role": "system", "content": summary_context})

    gap_scene_context = format_gap_scene_context(session_key, max_gap_scene_summaries)
    if gap_scene_context:
        history.append({"role": "system", "content": gap_scene_context})

    return history


def append_message(
    session_key: str,
    role: str,
    content: str,
    message_type: str,
    user_id: str,
    group_id: str | None = None,
    *,
    occurred_at: str | None = None,
) -> None:
    instant = parse_memory_time(occurred_at)
    ensure_database()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO messages (
                session_key,
                message_type,
                user_id,
                group_id,
                role,
                content,
                created_at, occurred_at, time_kind
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_key, message_type, user_id, group_id, role, content, utc_now(),
             instant.astimezone(timezone.utc).isoformat(timespec="seconds") if instant else None,
             "platform_sent" if instant and role == "user" else None),
        )


def mark_assistant_sent(session_key: str, content: str, *, sent_at: str | None = None) -> None:
    """Confirm only the latest matching reply after the transport accepted it."""
    instant = parse_memory_time(sent_at)
    confirmed_at = instant.astimezone(timezone.utc).isoformat(timespec="seconds") if instant else utc_now()
    ensure_database()
    with connect() as connection:
        connection.execute(
            """UPDATE messages SET occurred_at = ?, time_kind = 'reply_sent'
               WHERE id = (SELECT id FROM messages WHERE session_key = ? ORDER BY id DESC LIMIT 1)
                 AND role = 'assistant' AND content = ? AND time_kind IS NOT 'reply_sent'""",
            (confirmed_at, session_key, content),
        )




def last_message_created_at(session_key: str) -> str | None:
    key = (session_key or '').strip()
    if not key:
        return None
    ensure_database()
    with connect_read_only() as connection:
        row = connection.execute(
            'SELECT created_at FROM messages WHERE session_key = ? ORDER BY id DESC LIMIT 1',
            (key,),
        ).fetchone()
    if row is None:
        return None
    value = row['created_at']
    if not value:
        return None
    return str(value)


def clear_session(session_key: str) -> None:
    """Clear transient context while preserving formal session summaries.

    This removes recent raw messages and gap-scene summaries for the session.
    Rows in ``session_summaries`` are intentionally left unchanged and remain
    available to ``build_history`` as historical context.
    """
    ensure_database()
    with connect() as connection:
        connection.execute("DELETE FROM messages WHERE session_key = ?", (session_key,))
    clear_gap_scene_summaries(session_key)


def clear_all_sessions() -> None:
    ensure_database()
    with connect() as connection:
        connection.execute("DELETE FROM messages")
    clear_all_gap_scene_summaries()


def session_message_count(session_key: str) -> int:
    ensure_database()
    with connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS message_count
            FROM messages
            WHERE session_key = ?
            """,
            (session_key,),
        ).fetchone()
    return int(row["message_count"])


def session_message_progress(session_key: str) -> int:
    return session_message_count(session_key) + summary_stats(session_key)["summarized_message_count"]


def memory_stats() -> dict[str, int]:
    ensure_database()
    with connect() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS message_count,
                COUNT(DISTINCT session_key) AS session_count
            FROM messages
            """
        ).fetchone()
    summaries = summary_stats()
    return {
        "message_count": int(row["message_count"]),
        "session_count": int(row["session_count"]),
        "summary_count": summaries["summary_count"],
        "summarized_message_count": summaries["summarized_message_count"],
    }
