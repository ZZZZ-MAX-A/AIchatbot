from dataclasses import dataclass
from typing import Any

from .database import connect, ensure_database, utc_now


@dataclass(frozen=True)
class SessionSummary:
    id: int
    session_key: str
    summary: str
    message_start_id: int
    message_end_id: int
    source_message_count: int
    created_at: str


def _summary_from_row(row: Any) -> SessionSummary:
    return SessionSummary(
        id=int(row["id"]),
        session_key=str(row["session_key"]),
        summary=str(row["summary"]),
        message_start_id=int(row["message_start_id"]),
        message_end_id=int(row["message_end_id"]),
        source_message_count=int(row["source_message_count"]),
        created_at=str(row["created_at"]),
    )


def add_summary(
    session_key: str,
    message_type: str,
    user_id: str | None,
    group_id: str | None,
    summary: str,
    message_start_id: int,
    message_end_id: int,
    source_message_count: int,
) -> int:
    ensure_database()
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO session_summaries (
                session_key,
                message_type,
                user_id,
                group_id,
                summary,
                message_start_id,
                message_end_id,
                source_message_count,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_key,
                message_type,
                user_id,
                group_id,
                summary,
                message_start_id,
                message_end_id,
                source_message_count,
                utc_now(),
            ),
        )
        return int(cursor.lastrowid)


def recent_summaries(session_key: str, limit: int) -> list[SessionSummary]:
    if limit <= 0:
        return []
    ensure_database()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                session_key,
                summary,
                message_start_id,
                message_end_id,
                source_message_count,
                created_at
            FROM session_summaries
            WHERE session_key = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_key, limit),
        ).fetchall()
    return [_summary_from_row(row) for row in reversed(rows)]


def clear_session_summaries(session_key: str) -> int:
    ensure_database()
    with connect() as connection:
        cursor = connection.execute(
            "DELETE FROM session_summaries WHERE session_key = ?",
            (session_key,),
        )
        return int(cursor.rowcount)


def clear_all_summaries() -> int:
    ensure_database()
    with connect() as connection:
        cursor = connection.execute("DELETE FROM session_summaries")
        return int(cursor.rowcount)


def summary_stats(session_key: str | None = None) -> dict[str, int]:
    ensure_database()
    if session_key:
        where_clause = "WHERE session_key = ?"
        params = (session_key,)
    else:
        where_clause = ""
        params = ()

    with connect() as connection:
        row = connection.execute(
            f"""
            SELECT
                COUNT(*) AS summary_count,
                COALESCE(SUM(source_message_count), 0) AS summarized_message_count
            FROM session_summaries
            {where_clause}
            """,
            params,
        ).fetchone()
    return {
        "summary_count": int(row["summary_count"]),
        "summarized_message_count": int(row["summarized_message_count"]),
    }


def format_summary_context(session_key: str, limit: int) -> str:
    summaries = recent_summaries(session_key, limit)
    if not summaries:
        return ""
    lines = ["以下是当前会话较早内容的客观摘要："]
    for index, summary in enumerate(summaries, start=1):
        lines.append(f"{index}. {summary.summary}")
    return "\n".join(lines)

