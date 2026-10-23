"""Resolve source time at retrieval, without embedding relative ages or reindexing."""
from types import SimpleNamespace
import sqlite3

from ..database import connect_read_only
from ..memory_time import summary_time_context, time_label
from .schema import SOURCE_MANUAL_FACT, SOURCE_MANUAL_PREFERENCE, SOURCE_SESSION_SUMMARY


def memory_document_time_context(document) -> str:
    source_type = getattr(document, "source_type", "")
    version = getattr(document, "source_version", "")
    row = None
    try:
        if source_type == SOURCE_SESSION_SUMMARY:
            with connect_read_only() as connection:
                row = connection.execute(
                    "SELECT * FROM session_summaries WHERE id = ? AND session_key = ?",
                    (document.source_id, document.session_key),
                ).fetchone()
            if row is not None:
                return summary_time_context(SimpleNamespace(**dict(row)))
            return summary_time_context(SimpleNamespace(created_at=version))
        if source_type in {SOURCE_MANUAL_FACT, SOURCE_MANUAL_PREFERENCE}:
            with connect_read_only() as connection:
                row = connection.execute("SELECT created_at, updated_at FROM long_term_memories WHERE id = ?",
                                         (document.source_id,)).fetchone()
    except sqlite3.Error:
        # Older read-only stores may not have the new range fields yet.
        if source_type == SOURCE_SESSION_SUMMARY:
            return summary_time_context(SimpleNamespace(created_at=version))
    if source_type in {SOURCE_MANUAL_FACT, SOURCE_MANUAL_PREFERENCE}:
        created = row["created_at"] if row is not None else None
        # The indexed content belongs to source_version, even if the original
        # has since been edited. Do not give stale content a newer timestamp.
        stale = row is not None and row["updated_at"] != version
        state = "；原记忆已有更新，本条为旧版检索内容" if stale else ""
        return f"[记忆创建时间：{time_label(created)}；本版维护时间：{time_label(version)}{state}；不代表事实发生时间]"
    return "[原记忆时间：未知]"
