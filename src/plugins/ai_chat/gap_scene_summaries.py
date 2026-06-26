from dataclasses import dataclass
from typing import Any

from .config import AiChatConfig
from .database import connect, ensure_database, utc_now
from .llm import summarize_gap_scene_messages


GAP_SCENE_SUMMARY_UPDATE_STEP = 20


@dataclass(frozen=True)
class GapSceneSummary:
    id: int
    session_key: str
    slot: int
    summary: str
    message_start_id: int
    message_end_id: int
    source_message_count: int
    created_at: str
    updated_at: str


def _gap_summary_from_row(row: Any) -> GapSceneSummary:
    return GapSceneSummary(
        id=int(row["id"]),
        session_key=str(row["session_key"]),
        slot=int(row["slot"]),
        summary=str(row["summary"]),
        message_start_id=int(row["message_start_id"]),
        message_end_id=int(row["message_end_id"]),
        source_message_count=int(row["source_message_count"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def list_gap_scene_summaries(session_key: str, limit: int = 2) -> list[GapSceneSummary]:
    if limit <= 0:
        return []
    ensure_database()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                session_key,
                slot,
                summary,
                message_start_id,
                message_end_id,
                source_message_count,
                created_at,
                updated_at
            FROM gap_scene_summaries
            WHERE session_key = ?
            ORDER BY slot ASC
            LIMIT ?
            """,
            (session_key, limit),
        ).fetchall()
    return [_gap_summary_from_row(row) for row in rows]


def get_gap_scene_summary(session_key: str, slot: int) -> GapSceneSummary | None:
    ensure_database()
    with connect() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                session_key,
                slot,
                summary,
                message_start_id,
                message_end_id,
                source_message_count,
                created_at,
                updated_at
            FROM gap_scene_summaries
            WHERE session_key = ?
              AND slot = ?
            """,
            (session_key, slot),
        ).fetchone()
    return _gap_summary_from_row(row) if row else None


def upsert_gap_scene_summary(
    session_key: str,
    slot: int,
    summary: str,
    message_start_id: int,
    message_end_id: int,
    source_message_count: int,
) -> int:
    ensure_database()
    now = utc_now()
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO gap_scene_summaries (
                session_key,
                slot,
                summary,
                message_start_id,
                message_end_id,
                source_message_count,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_key, slot) DO UPDATE SET
                summary = excluded.summary,
                message_start_id = excluded.message_start_id,
                message_end_id = excluded.message_end_id,
                source_message_count = excluded.source_message_count,
                updated_at = excluded.updated_at
            """,
            (
                session_key,
                slot,
                summary,
                message_start_id,
                message_end_id,
                source_message_count,
                now,
                now,
            ),
        )
        return int(cursor.lastrowid)


def clear_gap_scene_summaries(session_key: str) -> int:
    ensure_database()
    with connect() as connection:
        cursor = connection.execute(
            "DELETE FROM gap_scene_summaries WHERE session_key = ?",
            (session_key,),
        )
        return int(cursor.rowcount)


def clear_all_gap_scene_summaries() -> int:
    ensure_database()
    with connect() as connection:
        cursor = connection.execute("DELETE FROM gap_scene_summaries")
        return int(cursor.rowcount)


def delete_gap_scene_slots(session_key: str, slots: list[int]) -> int:
    if not slots:
        return 0
    ensure_database()
    placeholders = ", ".join("?" for _ in slots)
    with connect() as connection:
        cursor = connection.execute(
            f"""
            DELETE FROM gap_scene_summaries
            WHERE session_key = ?
              AND slot IN ({placeholders})
            """,
            (session_key, *slots),
        )
        return int(cursor.rowcount)


def gap_scene_summary_stats(session_key: str | None = None) -> dict[str, int]:
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
                COALESCE(SUM(source_message_count), 0) AS source_message_count
            FROM gap_scene_summaries
            {where_clause}
            """,
            params,
        ).fetchone()
    return {
        "summary_count": int(row["summary_count"]),
        "source_message_count": int(row["source_message_count"]),
    }


def format_gap_scene_context(session_key: str, limit: int) -> str:
    summaries = list_gap_scene_summaries(session_key, limit)
    if not summaries:
        return ""
    lines = [
        "以下是当前会话中间空窗的临时场景状态摘要。",
        "它只用于补足正式摘要之后、最近原文之前的不可见消息；不要把它当作长期记忆或角色规则：",
    ]
    for summary in summaries:
        lines.append(
            f"空窗摘要 {summary.slot}，覆盖 {summary.source_message_count} 条消息：\n"
            f"{summary.summary}"
        )
    return "\n".join(lines)


def _message_count(session_key: str) -> int:
    ensure_database()
    with connect() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS message_count FROM messages WHERE session_key = ?",
            (session_key,),
        ).fetchone()
    return int(row["message_count"])


def _message_window(session_key: str, offset: int, limit: int) -> list[Any]:
    ensure_database()
    with connect() as connection:
        return connection.execute(
            """
            SELECT
                id,
                role,
                user_id,
                content
            FROM messages
            WHERE session_key = ?
            ORDER BY id ASC
            LIMIT ?
            OFFSET ?
            """,
            (session_key, limit, offset),
        ).fetchall()


def _format_messages(rows: list[Any], owner_qq: str) -> str:
    lines: list[str] = []
    for row in rows:
        if row["role"] != "user":
            role = "AI"
        elif owner_qq and str(row["user_id"]) == owner_qq:
            role = "主人"
        else:
            role = "用户"
        lines.append(f"{role}: {row['content']}")
    return "\n".join(lines)


def _should_update(existing: GapSceneSummary | None, desired_count: int, final_count: int) -> bool:
    if existing is None:
        return True
    if desired_count == final_count and existing.source_message_count != final_count:
        return True
    return desired_count - existing.source_message_count >= GAP_SCENE_SUMMARY_UPDATE_STEP


async def _ensure_slot(
    config: AiChatConfig,
    session_key: str,
    slot: int,
    offset: int,
    limit: int,
    final_count: int,
) -> None:
    if limit <= 0:
        delete_gap_scene_slots(session_key, [slot])
        return

    existing = get_gap_scene_summary(session_key, slot)
    if not _should_update(existing, limit, final_count):
        return

    rows = _message_window(session_key, offset, limit)
    if not rows:
        delete_gap_scene_slots(session_key, [slot])
        return

    message_text = _format_messages(rows, config.bot_owner_qq)
    summary = await summarize_gap_scene_messages(config, message_text)
    if not summary:
        return

    upsert_gap_scene_summary(
        session_key=session_key,
        slot=slot,
        summary=summary,
        message_start_id=int(rows[0]["id"]),
        message_end_id=int(rows[-1]["id"]),
        source_message_count=len(rows),
    )


async def ensure_gap_scene_summaries(config: AiChatConfig, session_key: str) -> None:
    if not config.enable_gap_scene_summaries:
        clear_gap_scene_summaries(session_key)
        return

    short_window = max(config.max_context_messages, 0)
    threshold_1 = max(config.gap_scene_summary_1_threshold, short_window)
    threshold_2 = max(config.gap_scene_summary_2_threshold, threshold_1)
    total = _message_count(session_key)

    if short_window <= 0 or total <= threshold_1:
        clear_gap_scene_summaries(session_key)
        return

    if total <= threshold_2:
        await _ensure_slot(
            config=config,
            session_key=session_key,
            slot=1,
            offset=0,
            limit=max(total - short_window, 0),
            final_count=max(threshold_2 - short_window, 1),
        )
        delete_gap_scene_slots(session_key, [2])
        return

    await _ensure_slot(
        config=config,
        session_key=session_key,
        slot=1,
        offset=0,
        limit=max(threshold_2 - short_window, 0),
        final_count=max(threshold_2 - short_window, 1),
    )
    await _ensure_slot(
        config=config,
        session_key=session_key,
        slot=2,
        offset=max(threshold_2 - short_window, 0),
        limit=max(total - threshold_2, 0),
        final_count=max(config.max_stored_messages_per_session - threshold_2, 1),
    )
