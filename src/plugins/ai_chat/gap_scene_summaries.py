from .memory_time import message_time_context, summary_time_context, source_time_range
from dataclasses import dataclass
from typing import Any

from .config import AiChatConfig
from .database import connect, current_persona_memory_id, ensure_database, utc_now


GAP_SCENE_SLOT = 1
GAP_SCENE_FIRST_WRITE_COUNT = 25
GAP_SCENE_SUMMARY_UPDATE_STEP = 20
GAP_SCENE_MAX_CATCH_UP_WRITES = 6


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
    source_start_at: str | None = None
    source_end_at: str | None = None


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
        source_start_at=row["source_start_at"] if "source_start_at" in row.keys() else None,
        source_end_at=row["source_end_at"] if "source_end_at" in row.keys() else None,
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
                updated_at, source_start_at, source_end_at
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
                updated_at, source_start_at, source_end_at
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
    source_start_at: str | None = None,
    source_end_at: str | None = None,
) -> int:
    ensure_database()
    now = utc_now()
    with connect() as connection:
        if source_start_at is None or source_end_at is None:
            rows = connection.execute(
                "SELECT id, created_at, occurred_at FROM messages WHERE session_key = ? AND id BETWEEN ? AND ? ORDER BY id",
                (session_key, message_start_id, message_end_id),
            ).fetchall()
            start, end = source_time_range(rows)
            source_start_at = source_start_at or (start if rows and rows[0]["id"] == message_start_id else None)
            source_end_at = source_end_at or (end if rows and rows[-1]["id"] == message_end_id else None)
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
                updated_at, source_start_at, source_end_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_key, slot) DO UPDATE SET
                summary = excluded.summary,
                message_start_id = excluded.message_start_id,
                message_end_id = excluded.message_end_id,
                source_message_count = excluded.source_message_count,
                updated_at = excluded.updated_at,
                source_start_at = excluded.source_start_at,
                source_end_at = excluded.source_end_at
            """,
            (
                session_key,
                slot,
                summary,
                message_start_id,
                message_end_id,
                source_message_count,
                now,
                now, source_start_at, source_end_at,
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
    if limit <= 0:
        return ""
    summaries = list_gap_scene_summaries(session_key, 1)
    if not summaries:
        return ""
    summary = summaries[0]
    return "\n".join(
        [
            "以下是当前会话的当前场状态卡。",
            "它只用于补足正式摘要之后、最近原文之前的不可见消息；不要把它当作长期记忆或角色规则：",
            summary_time_context(summary, live=True),
            f"当前场状态卡，覆盖 {summary.source_message_count} 条消息：\n{summary.summary}",
        ]
    )


def next_gap_scene_take_count(has_card: bool, uncovered_count: int) -> int:
    if uncovered_count <= 0:
        return 0
    if not has_card:
        if uncovered_count < GAP_SCENE_FIRST_WRITE_COUNT:
            return 0
        return GAP_SCENE_FIRST_WRITE_COUNT
    if uncovered_count < GAP_SCENE_SUMMARY_UPDATE_STEP:
        return 0
    return GAP_SCENE_SUMMARY_UPDATE_STEP


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
                content, created_at, occurred_at, time_kind
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
        lines.append(f"{message_time_context(row)} {role}: {row['content']}")
    return "\n".join(lines)


def _uncovered_overflow_rows(
    overflow_rows: list[Any],
    existing: GapSceneSummary | None,
) -> list[Any]:
    if existing is None:
        return list(overflow_rows)
    end_id = int(existing.message_end_id)
    return [row for row in overflow_rows if int(row["id"]) > end_id]


def _card_overlaps_overflow(existing: GapSceneSummary, overflow_rows: list[Any]) -> bool:
    if not overflow_rows:
        return False
    overflow_start = int(overflow_rows[0]["id"])
    overflow_end = int(overflow_rows[-1]["id"])
    return not (
        int(existing.message_end_id) < overflow_start
        or int(existing.message_start_id) > overflow_end
    )


def _build_gap_scene_payload(
    existing: GapSceneSummary | None,
    rows: list[Any],
    owner_qq: str,
) -> str:
    original = _format_messages(rows, owner_qq)
    if existing is None:
        return f"【新露出的原文】\n{original}"
    return (
        "【当前状态卡】\n"
        f"{summary_time_context(existing, live=True)}\n{existing.summary.strip()}\n\n"
        "【新露出的原文】\n"
        f"{original}"
    )


async def _generate_gap_scene_summary(
    config: AiChatConfig,
    message_text: str,
    role_card_key: str,
) -> str:
    # The Owner Console imports this module only for read-only summary counts.
    # Keep the OpenAI SDK out of that backend until the QQ runtime actually
    # needs to generate a new gap-scene summary.
    from .llm import is_usable_summary, summarize_gap_scene_messages

    summary = await summarize_gap_scene_messages(
        config,
        message_text,
        role_card_key=role_card_key,
    )
    return summary if is_usable_summary(summary) else ""


async def _write_live_gap_card(
    config: AiChatConfig,
    session_key: str,
    existing: GapSceneSummary | None,
    take_rows: list[Any],
) -> bool:
    if not take_rows:
        return False
    payload = _build_gap_scene_payload(existing, take_rows, config.bot_owner_qq)
    summary = await _generate_gap_scene_summary(
        config,
        payload,
        current_persona_memory_id(),
    )
    if not summary:
        return False

    if existing is None:
        start_id = int(take_rows[0]["id"])
        source_count = len(take_rows)
    else:
        start_id = int(existing.message_start_id)
        source_count = int(existing.source_message_count) + len(take_rows)

    upsert_gap_scene_summary(
        session_key=session_key,
        slot=GAP_SCENE_SLOT,
        summary=summary,
        message_start_id=start_id,
        message_end_id=int(take_rows[-1]["id"]),
        source_message_count=source_count,
    )
    return True


async def ensure_gap_scene_summaries(config: AiChatConfig, session_key: str) -> None:
    if not config.enable_gap_scene_summaries:
        clear_gap_scene_summaries(session_key)
        return

    short_window = max(config.max_context_messages, 0)
    total = _message_count(session_key)
    delete_gap_scene_slots(session_key, [2])

    if short_window <= 0 or total <= short_window:
        clear_gap_scene_summaries(session_key)
        return

    overflow_count = total - short_window
    overflow_rows = _message_window(session_key, 0, overflow_count)
    if not overflow_rows:
        clear_gap_scene_summaries(session_key)
        return

    existing = get_gap_scene_summary(session_key, GAP_SCENE_SLOT)
    if existing is not None and not _card_overlaps_overflow(existing, overflow_rows):
        delete_gap_scene_slots(session_key, [GAP_SCENE_SLOT])
        existing = None

    for _ in range(GAP_SCENE_MAX_CATCH_UP_WRITES):
        existing = get_gap_scene_summary(session_key, GAP_SCENE_SLOT)
        uncovered = _uncovered_overflow_rows(overflow_rows, existing)
        take_count = next_gap_scene_take_count(existing is not None, len(uncovered))
        if take_count <= 0:
            return
        wrote = await _write_live_gap_card(
            config,
            session_key,
            existing,
            uncovered[:take_count],
        )
        if not wrote:
            return
