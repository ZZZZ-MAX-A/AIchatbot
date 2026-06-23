from .database import connect, ensure_database, utc_now
from .summaries import format_summary_context, summary_stats


Message = dict[str, str]


def build_history(
    session_key: str,
    max_messages: int,
    max_summaries: int = 0,
    long_term_context: str = "",
) -> list[Message]:
    history: list[Message] = []
    if long_term_context:
        history.append({"role": "system", "content": long_term_context})

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
        memory_row = connection.execute(
            """
            SELECT
                COUNT(*) AS long_term_memory_count
            FROM long_term_memories
            """
        ).fetchone()
        embedding_row = connection.execute(
            """
            SELECT
                COUNT(*) AS embedding_count
            FROM memory_embeddings
            """
        ).fetchone()
    summaries = summary_stats()
    return {
        "message_count": int(row["message_count"]),
        "session_count": int(row["session_count"]),
        "long_term_memory_count": int(memory_row["long_term_memory_count"]),
        "embedding_count": int(embedding_row["embedding_count"]),
        "summary_count": summaries["summary_count"],
        "summarized_message_count": summaries["summarized_message_count"],
    }
