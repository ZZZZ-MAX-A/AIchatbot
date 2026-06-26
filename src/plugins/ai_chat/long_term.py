from dataclasses import dataclass
from typing import Any, Iterable

from .database import connect, ensure_database, utc_now


LONG_TERM_FACT_TYPE = "fact_summary"
LONG_TERM_PREFERENCE_TYPE = "preference_summary"
LONG_TERM_MEMORY_TYPES = {LONG_TERM_FACT_TYPE, LONG_TERM_PREFERENCE_TYPE}


@dataclass(frozen=True)
class LongTermMemory:
    id: int
    subject_type: str
    subject_id: str
    memory_type: str
    content: str
    confidence: float
    created_at: str
    updated_at: str


def normalize_memory_type(value: str) -> str:
    normalized = value.strip().lower()
    aliases = {
        "fact": LONG_TERM_FACT_TYPE,
        "facts": LONG_TERM_FACT_TYPE,
        "fact_summary": LONG_TERM_FACT_TYPE,
        "事实": LONG_TERM_FACT_TYPE,
        "事实摘要": LONG_TERM_FACT_TYPE,
        "preference": LONG_TERM_PREFERENCE_TYPE,
        "preferences": LONG_TERM_PREFERENCE_TYPE,
        "preference_summary": LONG_TERM_PREFERENCE_TYPE,
        "偏好": LONG_TERM_PREFERENCE_TYPE,
        "偏好摘要": LONG_TERM_PREFERENCE_TYPE,
    }
    return aliases.get(normalized, LONG_TERM_FACT_TYPE)


def memory_type_label(value: str) -> str:
    labels = {
        LONG_TERM_FACT_TYPE: "事实摘要",
        LONG_TERM_PREFERENCE_TYPE: "偏好摘要",
    }
    return labels.get(value, "事实摘要")


def _memory_from_row(row: Any) -> LongTermMemory:
    return LongTermMemory(
        id=int(row["id"]),
        subject_type=str(row["subject_type"]),
        subject_id=str(row["subject_id"]),
        memory_type=str(row["memory_type"]),
        content=str(row["content"]),
        confidence=float(row["confidence"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def add_long_term_memory(
    subject_type: str,
    subject_id: str,
    content: str,
    memory_type: str = LONG_TERM_FACT_TYPE,
    source_session_key: str | None = None,
    confidence: float = 1.0,
) -> int:
    ensure_database()
    now = utc_now()
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO long_term_memories (
                subject_type,
                subject_id,
                memory_type,
                content,
                source_session_key,
                confidence,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                subject_type,
                subject_id,
                normalize_memory_type(memory_type),
                content.strip(),
                source_session_key,
                confidence,
                now,
                now,
            ),
        )
        return int(cursor.lastrowid)


def list_long_term_memories(
    subject_type: str | None = None,
    subject_id: str | None = None,
    limit: int = 20,
) -> list[LongTermMemory]:
    ensure_database()
    clauses: list[str] = []
    params: list[object] = []
    if subject_type:
        clauses.append("subject_type = ?")
        params.append(subject_type)
    if subject_id:
        clauses.append("subject_id = ?")
        params.append(subject_id)
    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    with connect() as connection:
        rows = connection.execute(
            f"""
            SELECT
                id,
                subject_type,
                subject_id,
                memory_type,
                content,
                confidence,
                created_at,
                updated_at
            FROM long_term_memories
            {where_clause}
            ORDER BY id DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
    return [_memory_from_row(row) for row in rows]


def delete_long_term_memory(memory_id: int) -> bool:
    ensure_database()
    with connect() as connection:
        cursor = connection.execute(
            "DELETE FROM long_term_memories WHERE id = ?",
            (memory_id,),
        )
        return int(cursor.rowcount) > 0


def clear_long_term_memories(subject_type: str, subject_id: str) -> int:
    ensure_database()
    with connect() as connection:
        cursor = connection.execute(
            """
            DELETE FROM long_term_memories
            WHERE subject_type = ?
              AND subject_id = ?
            """,
            (subject_type, subject_id),
        )
        return int(cursor.rowcount)


def count_long_term_memories(subject_type: str, subject_id: str) -> int:
    ensure_database()
    with connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS memory_count
            FROM long_term_memories
            WHERE subject_type = ?
              AND subject_id = ?
            """,
            (subject_type, subject_id),
        ).fetchone()
    return int(row["memory_count"])


def long_term_memory_stats() -> dict[str, int]:
    ensure_database()
    with connect() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS memory_count,
                COUNT(DISTINCT subject_type || ':' || subject_id) AS subject_count
            FROM long_term_memories
            """
        ).fetchone()
    return {
        "memory_count": int(row["memory_count"]),
        "subject_count": int(row["subject_count"]),
    }


def format_long_term_context(
    subjects: Iterable[tuple[str, str]],
    limit: int,
) -> str:
    if limit <= 0:
        return ""

    seen: set[tuple[str, str]] = set()
    memories: list[LongTermMemory] = []
    for subject_type, subject_id in subjects:
        key = (subject_type, subject_id)
        if key in seen:
            continue
        seen.add(key)
        remaining = limit - len(memories)
        if remaining <= 0:
            break
        memories.extend(list_long_term_memories(subject_type, subject_id, remaining))

    if not memories:
        return ""

    lines = [
        "以下是主人手动维护的长期记忆摘要。",
        "这些内容不是 AI 自动提取的；仅在与当前问题相关时参考，不要强行提起，也不要编造额外事实。",
    ]
    for memory in memories[:limit]:
        lines.append(f"- {memory_type_label(memory.memory_type)}：{memory.content}")
    return "\n".join(lines)
