from __future__ import annotations

from .memory_index import (
    soft_delete_all_session_summary_documents,
    soft_delete_manual_memory_documents,
    soft_delete_session_summary_document,
    soft_delete_session_summary_documents_for_session,
    sync_manual_memory_by_id,
    sync_session_summary_by_id,
)
from .providers import build_embedding_provider


def _memory_rag_embedder_or_none():
    try:
        from ..config import load_config

        config = load_config()
    except Exception:
        return None

    if not config.enable_memory_rag:
        return None

    try:
        return build_embedding_provider(config)
    except Exception:
        return None


def sync_manual_memory_after_write(memory_id: int) -> None:
    embedder = _memory_rag_embedder_or_none()
    if embedder is None:
        return
    sync_manual_memory_by_id(memory_id, embedder=embedder)


def sync_manual_memory_after_delete(memory_id: int) -> None:
    soft_delete_manual_memory_documents(memory_id)


def sync_session_summary_after_write(summary_id: int) -> None:
    embedder = _memory_rag_embedder_or_none()
    if embedder is None:
        return
    sync_session_summary_by_id(summary_id, embedder=embedder)


def sync_session_summary_after_delete(summary_id: int) -> None:
    soft_delete_session_summary_document(summary_id)


def sync_session_summaries_after_clear_session(session_key: str) -> None:
    soft_delete_session_summary_documents_for_session(session_key)


def sync_session_summaries_after_clear_all() -> None:
    soft_delete_all_session_summary_documents()
