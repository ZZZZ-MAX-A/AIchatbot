from dataclasses import dataclass
from typing import Any, Iterable

from .database import connect, ensure_database, utc_now
from .memory_reader import manual_context_text, read_manual_rows


MANUAL_FACT_TYPE = "fact_summary"
MANUAL_PREFERENCE_TYPE = "preference_summary"
MANUAL_MEMORY_TYPES = {MANUAL_FACT_TYPE, MANUAL_PREFERENCE_TYPE}


@dataclass(frozen=True)
class ManualMemory:
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
        "fact": MANUAL_FACT_TYPE,
        "facts": MANUAL_FACT_TYPE,
        "fact_summary": MANUAL_FACT_TYPE,
        "事实": MANUAL_FACT_TYPE,
        "事实摘要": MANUAL_FACT_TYPE,
        "preference": MANUAL_PREFERENCE_TYPE,
        "preferences": MANUAL_PREFERENCE_TYPE,
        "preference_summary": MANUAL_PREFERENCE_TYPE,
        "偏好": MANUAL_PREFERENCE_TYPE,
        "偏好摘要": MANUAL_PREFERENCE_TYPE,
    }
    return aliases.get(normalized, MANUAL_FACT_TYPE)


def memory_type_label(value: str) -> str:
    labels = {
        MANUAL_FACT_TYPE: "事实摘要",
        MANUAL_PREFERENCE_TYPE: "偏好摘要",
    }
    return labels.get(value, "事实摘要")


def _memory_from_row(row: Any) -> ManualMemory:
    return ManualMemory(
        id=int(row["id"]),
        subject_type=str(row["subject_type"]),
        subject_id=str(row["subject_id"]),
        memory_type=str(row["memory_type"]),
        content=str(row["content"]),
        confidence=float(row["confidence"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def add_manual_memory(
    subject_type: str,
    subject_id: str,
    content: str,
    memory_type: str = MANUAL_FACT_TYPE,
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
        memory_id = int(cursor.lastrowid)
    try:
        from .rag.runtime_sync import sync_manual_memory_after_write

        sync_manual_memory_after_write(memory_id)
    except Exception:
        pass
    return memory_id


def get_manual_memory(memory_id: int) -> ManualMemory | None:
    ensure_database()
    with connect() as connection:
        row = connection.execute(
            """
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
            WHERE id = ?
            """,
            (memory_id,),
        ).fetchone()
    return _memory_from_row(row) if row else None


def list_manual_memories(
    subject_type: str | None = None,
    subject_id: str | None = None,
    limit: int | None = 20,
) -> list[ManualMemory]:
    ensure_database()
    with connect() as connection:
        rows = read_manual_rows(connection, subject_type=subject_type, subject_id=subject_id, limit=limit)
    return [_memory_from_row(row) for row in rows]


def delete_manual_memory(memory_id: int) -> bool:
    ensure_database()
    with connect() as connection:
        cursor = connection.execute(
            "DELETE FROM long_term_memories WHERE id = ?",
            (memory_id,),
        )
        deleted = int(cursor.rowcount) > 0
    if deleted:
        try:
            from .rag.runtime_sync import sync_manual_memory_after_delete

            sync_manual_memory_after_delete(memory_id)
        except Exception:
            pass
    return deleted


def manual_memory_stats() -> dict[str, int]:
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


def format_manual_memory_context(
    subjects: Iterable[tuple[str, str]],
    limit: int,
) -> str:
    if limit <= 0:
        return ""

    seen: set[tuple[str, str]] = set()
    memories: list[ManualMemory] = []
    for subject_type, subject_id in subjects:
        key = (subject_type, subject_id)
        if key in seen:
            continue
        seen.add(key)
        remaining = limit - len(memories)
        if remaining <= 0:
            break
        memories.extend(list_manual_memories(subject_type, subject_id, remaining))

    return manual_context_text([vars(memory) for memory in memories[:limit]])
