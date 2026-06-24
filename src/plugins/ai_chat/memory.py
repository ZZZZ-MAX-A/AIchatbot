from .database import connect, ensure_database, utc_now
from .summaries import format_summary_context, summary_stats


Message = dict[str, str]


def build_history(
    session_key: str,
    max_messages: int,
    max_summaries: int = 0,
    system_contexts: list[str] | None = None,
) -> list[Message]:
    history: list[Message] = []
    for context in system_contexts or []:
        if context:
            history.append({"role": "system", "content": context})

    summary_context = format_summary_context(session_key, max_summaries)
    if summary_context:
        history.append({"role": "system", "content": summary_context})

    if max_messages <= 0:
        return history
    ensure_database()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT role, content
            FROM messages
            WHERE session_key = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_key, max_messages),
        ).fetchall()
    history.extend(
        {"role": str(row["role"]), "content": str(row["content"])}
        for row in reversed(rows)
    )
    return history


def append_message(
    session_key: str,
    role: str,
    content: str,
    message_type: str,
    user_id: str,
    group_id: str | None = None,
) -> None:
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
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_key, message_type, user_id, group_id, role, content, utc_now()),
        )


def clear_session(session_key: str) -> None:
    ensure_database()
    with connect() as connection:
        connection.execute("DELETE FROM messages WHERE session_key = ?", (session_key,))


def clear_all_sessions() -> None:
    ensure_database()
    with connect() as connection:
        connection.execute("DELETE FROM messages")


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
