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
    message_type: str = ""
    user_id: str = ""
    group_id: str = ""


def _summary_from_row(row: Any) -> SessionSummary:
    return SessionSummary(
        id=int(row["id"]),
        session_key=str(row["session_key"]),
        summary=str(row["summary"]),
        message_start_id=int(row["message_start_id"]),
        message_end_id=int(row["message_end_id"]),
        source_message_count=int(row["source_message_count"]),
        created_at=str(row["created_at"]),
        message_type=str(row["message_type"]) if "message_type" in row.keys() else "",
        user_id=str(row["user_id"]) if "user_id" in row.keys() and row["user_id"] is not None else "",
        group_id=str(row["group_id"]) if "group_id" in row.keys() and row["group_id"] is not None else "",
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
        summary_id = int(cursor.lastrowid)
    try:
        from .rag.runtime_sync import sync_session_summary_after_write

        sync_session_summary_after_write(summary_id)
    except Exception:
        pass
    return summary_id


def get_session_summary(summary_id: int, session_key: str | None = None) -> SessionSummary | None:
    ensure_database()
    clauses = ["id = ?"]
    params: list[object] = [summary_id]
    if session_key is not None:
        clauses.append("session_key = ?")
        params.append(session_key)

    with connect() as connection:
        row = connection.execute(
            f"""
            SELECT
                id,
                session_key,
                message_type,
                user_id,
                group_id,
                summary,
                message_start_id,
                message_end_id,
                source_message_count,
                created_at
            FROM session_summaries
            WHERE {' AND '.join(clauses)}
            """,
            tuple(params),
        ).fetchone()
    return _summary_from_row(row) if row else None


def list_session_summaries(
    session_key: str | None = None,
    limit: int | None = 100,
) -> list[SessionSummary]:
    ensure_database()
    clauses: list[str] = []
    params: list[object] = []
    if session_key is not None:
        clauses.append("session_key = ?")
        params.append(session_key)
    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit_clause = ""
    if limit is not None:
        limit_clause = "LIMIT ?"
        params.append(limit)

    with connect() as connection:
        rows = connection.execute(
            f"""
            SELECT
                id,
                session_key,
                message_type,
                user_id,
                group_id,
                summary,
                message_start_id,
                message_end_id,
                source_message_count,
                created_at
            FROM session_summaries
            {where_clause}
            ORDER BY id DESC
            {limit_clause}
            """,
            tuple(params),
        ).fetchall()
    return [_summary_from_row(row) for row in rows]


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
                message_type,
                user_id,
                group_id,
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
        deleted_count = int(cursor.rowcount)
    if deleted_count:
        try:
            from .rag.runtime_sync import sync_session_summaries_after_clear_session

            sync_session_summaries_after_clear_session(session_key)
        except Exception:
            pass
    return deleted_count


def delete_session_summary(session_key: str, summary_id: int) -> bool:
    ensure_database()
    with connect() as connection:
        cursor = connection.execute(
            """
            DELETE FROM session_summaries
            WHERE session_key = ?
              AND id = ?
            """,
            (session_key, summary_id),
        )
        deleted = int(cursor.rowcount) > 0
    if deleted:
        try:
            from .rag.runtime_sync import sync_session_summary_after_delete

            sync_session_summary_after_delete(summary_id)
        except Exception:
            pass
    return deleted


def clear_all_summaries() -> int:
    ensure_database()
    with connect() as connection:
        cursor = connection.execute("DELETE FROM session_summaries")
        deleted_count = int(cursor.rowcount)
    if deleted_count:
        try:
            from .rag.runtime_sync import sync_session_summaries_after_clear_all

            sync_session_summaries_after_clear_all()
        except Exception:
            pass
    return deleted_count


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
