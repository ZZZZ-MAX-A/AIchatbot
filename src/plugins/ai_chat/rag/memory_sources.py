from __future__ import annotations

from .schema import (
    NAMESPACE_SEMANTIC_MEMORY,
    SOURCE_MANUAL_FACT,
    SOURCE_MANUAL_PREFERENCE,
    SOURCE_SESSION_SUMMARY,
    VISIBILITY_OWNER_ONLY,
)


def manual_memory_source_type(memory_type: str) -> str:
    if memory_type == "preference_summary":
        return SOURCE_MANUAL_PREFERENCE
    return SOURCE_MANUAL_FACT


def manual_memory_document_fields(memory) -> dict[str, str | int]:
    source_type = manual_memory_source_type(str(memory.memory_type))
    return {
        "namespace": NAMESPACE_SEMANTIC_MEMORY,
        "source_type": source_type,
        "source_id": str(memory.id),
        "title": f"{source_type} {memory.id}",
        "content": str(memory.content),
        "visibility": VISIBILITY_OWNER_ONLY,
        "subject_type": str(memory.subject_type),
        "subject_id": str(memory.subject_id),
        "source_version": str(memory.updated_at),
        "chunk_index": 0,
    }


def session_summary_document_fields(summary) -> dict[str, str | int]:
    return {
        "namespace": NAMESPACE_SEMANTIC_MEMORY,
        "source_type": SOURCE_SESSION_SUMMARY,
        "source_id": str(summary.id),
        "title": f"session_summary {summary.id}",
        "content": str(summary.summary),
        "visibility": VISIBILITY_OWNER_ONLY,
        "session_key": str(summary.session_key),
        "source_version": str(summary.created_at),
        "chunk_index": 0,
    }
