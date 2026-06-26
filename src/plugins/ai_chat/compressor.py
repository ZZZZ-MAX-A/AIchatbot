from dataclasses import dataclass
from typing import Any

from .config import AiChatConfig
from .database import connect, ensure_database
from .gap_scene_summaries import clear_gap_scene_summaries
from .llm import summarize_messages
from .summaries import add_summary


@dataclass(frozen=True)
class CompressionResult:
    compressed: bool
    reason: str
    summary_id: int | None = None
    source_message_count: int = 0


def _message_count(session_key: str) -> int:
    ensure_database()
    with connect() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS message_count FROM messages WHERE session_key = ?",
            (session_key,),
        ).fetchone()
    return int(row["message_count"])


def _oldest_messages(session_key: str, limit: int) -> list[Any]:
    ensure_database()
    with connect() as connection:
        return connection.execute(
            """
            SELECT
                id,
                message_type,
                user_id,
                group_id,
                role,
                content
            FROM messages
            WHERE session_key = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (session_key, limit),
        ).fetchall()


def _delete_message_range(session_key: str, start_id: int, end_id: int) -> int:
    ensure_database()
    with connect() as connection:
        cursor = connection.execute(
            """
            DELETE FROM messages
            WHERE session_key = ?
              AND id >= ?
              AND id <= ?
            """,
            (session_key, start_id, end_id),
        )
        return int(cursor.rowcount)


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


async def compress_session(
    config: AiChatConfig,
    session_key: str,
    force: bool = False,
) -> CompressionResult:
    if not force and not config.enable_memory_compression:
        return CompressionResult(False, "自动压缩未启用")

    total = _message_count(session_key)
    if not force and total <= config.max_stored_messages_per_session:
        return CompressionResult(False, "消息数量未超过压缩阈值")

    keep_recent = 0 if force else max(config.summary_keep_recent_messages, 0)
    compressible_count = total - keep_recent
    if compressible_count <= 0:
        return CompressionResult(False, "可压缩消息不足")
    min_source_messages = max(config.summary_min_source_messages, 0)
    if min_source_messages and compressible_count < min_source_messages:
        return CompressionResult(
            False,
            f"可压缩消息 {compressible_count} 条，少于最低摘要门槛 {min_source_messages} 条",
            source_message_count=compressible_count,
        )

    if force:
        batch_size = compressible_count
    else:
        batch_size = config.summary_batch_messages if config.summary_batch_messages > 0 else compressible_count
        batch_size = min(batch_size, compressible_count)
    if min_source_messages and batch_size < min_source_messages:
        return CompressionResult(
            False,
            f"本批可压缩消息 {batch_size} 条，少于最低摘要门槛 {min_source_messages} 条",
            source_message_count=batch_size,
        )
    rows = _oldest_messages(session_key, batch_size)
    if not rows:
        return CompressionResult(False, "没有可压缩消息")

    message_text = _format_messages(rows, config.bot_owner_qq)
    summary = await summarize_messages(config, message_text)
    if not summary:
        return CompressionResult(False, "摘要为空")

    first = rows[0]
    last = rows[-1]
    message_type = str(first["message_type"])
    group_id = str(first["group_id"]) if first["group_id"] is not None else None
    user_id = str(first["user_id"]) if message_type == "private" else None

    summary_id = add_summary(
        session_key=session_key,
        message_type=message_type,
        user_id=user_id,
        group_id=group_id,
        summary=summary,
        message_start_id=int(first["id"]),
        message_end_id=int(last["id"]),
        source_message_count=len(rows),
    )
    deleted_count = _delete_message_range(session_key, int(first["id"]), int(last["id"]))
    clear_gap_scene_summaries(session_key)

    return CompressionResult(
        compressed=True,
        reason=f"已压缩 {deleted_count} 条旧消息",
        summary_id=summary_id,
        source_message_count=deleted_count,
    )
