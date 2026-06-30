from __future__ import annotations

from dataclasses import dataclass, field, replace

from .documents import (
    find_rag_document,
    get_rag_document,
    list_rag_documents,
    soft_delete_rag_document,
    soft_delete_rag_documents,
    upsert_rag_document,
)
from .embeddings import get_rag_embedding, upsert_rag_embedding
from .memory_sources import manual_memory_document_fields, session_summary_document_fields
from .providers import EmbeddingProvider
from .schema import (
    NAMESPACE_SEMANTIC_MEMORY,
    SOURCE_MANUAL_FACT,
    SOURCE_MANUAL_PREFERENCE,
    SOURCE_SESSION_SUMMARY,
    VISIBILITY_OWNER_ONLY,
    RagDocument,
    RagSearchResult,
)
from .search import search_rag_documents


MEMORY_SOURCE_TYPES = {
    SOURCE_MANUAL_FACT,
    SOURCE_MANUAL_PREFERENCE,
    SOURCE_SESSION_SUMMARY,
}


@dataclass
class MemoryRagIndexStats:
    scanned_manual_memories: int = 0
    scanned_session_summaries: int = 0
    created_documents: int = 0
    updated_documents: int = 0
    reactivated_documents: int = 0
    unchanged_documents: int = 0
    embeddings_created: int = 0
    embeddings_updated: int = 0
    embeddings_skipped: int = 0
    soft_deleted_documents: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def as_dict(self) -> dict[str, int | list[str]]:
        return {
            "scanned_manual_memories": self.scanned_manual_memories,
            "scanned_session_summaries": self.scanned_session_summaries,
            "created_documents": self.created_documents,
            "updated_documents": self.updated_documents,
            "reactivated_documents": self.reactivated_documents,
            "unchanged_documents": self.unchanged_documents,
            "embeddings_created": self.embeddings_created,
            "embeddings_updated": self.embeddings_updated,
            "embeddings_skipped": self.embeddings_skipped,
            "soft_deleted_documents": self.soft_deleted_documents,
            "errors": list(self.errors),
        }


def rebuild_memory_rag_index(
    *,
    embedder: EmbeddingProvider,
    include_manual_facts: bool = True,
    include_manual_preferences: bool = True,
    include_session_summaries: bool = True,
) -> MemoryRagIndexStats:
    from ..manual_memory import MANUAL_FACT_TYPE, MANUAL_PREFERENCE_TYPE, list_manual_memories
    from ..summaries import list_session_summaries

    stats = MemoryRagIndexStats()
    active_document_ids: set[int] = set()
    included_source_types: set[str] = set()

    if include_manual_facts:
        included_source_types.add(SOURCE_MANUAL_FACT)
    if include_manual_preferences:
        included_source_types.add(SOURCE_MANUAL_PREFERENCE)
    if include_session_summaries:
        included_source_types.add(SOURCE_SESSION_SUMMARY)

    if include_manual_facts or include_manual_preferences:
        for memory in list_manual_memories(limit=None):
            if memory.memory_type == MANUAL_FACT_TYPE and not include_manual_facts:
                continue
            if memory.memory_type == MANUAL_PREFERENCE_TYPE and not include_manual_preferences:
                continue
            stats.scanned_manual_memories += 1
            document_id = index_manual_memory(memory, embedder=embedder, stats=stats)
            if document_id is not None:
                active_document_ids.add(document_id)

    if include_session_summaries:
        for summary in list_session_summaries(limit=None):
            stats.scanned_session_summaries += 1
            document_id = index_session_summary(summary, embedder=embedder, stats=stats)
            if document_id is not None:
                active_document_ids.add(document_id)

    _soft_delete_stale_memory_documents(stats, active_document_ids, included_source_types)
    return stats


def sync_manual_memory_by_id(
    memory_id: int,
    *,
    embedder: EmbeddingProvider,
) -> int | None:
    from ..manual_memory import get_manual_memory

    memory = get_manual_memory(memory_id)
    if memory is None:
        soft_delete_manual_memory_documents(memory_id)
        return None
    return index_manual_memory(memory, embedder=embedder)


def sync_session_summary_by_id(
    summary_id: int,
    *,
    embedder: EmbeddingProvider,
) -> int | None:
    from ..summaries import get_session_summary

    summary = get_session_summary(summary_id)
    if summary is None:
        soft_delete_session_summary_document(summary_id)
        return None
    return index_session_summary(summary, embedder=embedder)


def index_manual_memory(
    memory,
    *,
    embedder: EmbeddingProvider,
    stats: MemoryRagIndexStats | None = None,
) -> int | None:
    return _index_memory_document(
        fields=manual_memory_document_fields(memory),
        embedder=embedder,
        stats=stats,
    )


def index_session_summary(
    summary,
    *,
    embedder: EmbeddingProvider,
    stats: MemoryRagIndexStats | None = None,
) -> int | None:
    return _index_memory_document(
        fields=session_summary_document_fields(summary),
        embedder=embedder,
        stats=stats,
    )


def soft_delete_manual_memory_documents(memory_id: int) -> int:
    deleted = 0
    for source_type in (SOURCE_MANUAL_FACT, SOURCE_MANUAL_PREFERENCE):
        deleted += soft_delete_rag_documents(
            namespace=NAMESPACE_SEMANTIC_MEMORY,
            source_type=source_type,
            source_id=str(memory_id),
        )
    return deleted


def soft_delete_session_summary_document(summary_id: int) -> int:
    return soft_delete_rag_documents(
        namespace=NAMESPACE_SEMANTIC_MEMORY,
        source_type=SOURCE_SESSION_SUMMARY,
        source_id=str(summary_id),
    )


def soft_delete_session_summary_documents_for_session(session_key: str) -> int:
    return soft_delete_rag_documents(
        namespace=NAMESPACE_SEMANTIC_MEMORY,
        source_type=SOURCE_SESSION_SUMMARY,
        session_key=session_key,
    )


def soft_delete_all_session_summary_documents() -> int:
    return soft_delete_rag_documents(
        namespace=NAMESPACE_SEMANTIC_MEMORY,
        source_type=SOURCE_SESSION_SUMMARY,
    )


def retrieve_memory(
    *,
    query: str,
    embedder: EmbeddingProvider,
    is_owner: bool,
    top_k: int = 5,
    min_score: float = 0.55,
    max_context_chars: int = 1600,
    source_types: set[str] | None = None,
) -> list[RagSearchResult]:
    if not is_owner or not query.strip() or top_k <= 0 or max_context_chars <= 0:
        return []

    allowed_source_types = source_types or MEMORY_SOURCE_TYPES
    query_embedding = embedder.embed(query)
    results = search_rag_documents(
        query_embedding=query_embedding,
        namespace=NAMESPACE_SEMANTIC_MEMORY,
        provider=embedder.provider,
        model=embedder.model,
        source_types=allowed_source_types,
        min_score=min_score,
        top_k=top_k,
    )
    visible = [result for result in results if memory_document_visible(result.document, is_owner=is_owner)]
    return trim_results_to_context_chars(visible, max_context_chars)


def memory_document_visible(document: RagDocument, *, is_owner: bool) -> bool:
    if document.visibility == VISIBILITY_OWNER_ONLY:
        return is_owner
    return False


def trim_results_to_context_chars(
    results: list[RagSearchResult],
    max_context_chars: int,
) -> list[RagSearchResult]:
    if max_context_chars <= 0:
        return []

    trimmed: list[RagSearchResult] = []
    used = 0
    for result in results:
        content = result.document.content
        remaining = max_context_chars - used
        if remaining <= 0:
            break
        if len(content) > remaining:
            document = replace(result.document, content=content[:remaining].rstrip())
            trimmed.append(RagSearchResult(document=document, score=result.score))
            break
        trimmed.append(result)
        used += len(content)
    return trimmed


def format_memory_results(results: list[RagSearchResult]) -> str:
    if not results:
        return "No matching memory documents found."

    lines: list[str] = []
    for index, result in enumerate(results, start=1):
        document = result.document
        lines.append(
            f"[{index}] {document.title} "
            f"(score={result.score:.3f}, source={document.source_type}:{document.source_id})"
        )
        lines.append(document.content)
        lines.append("")
    return "\n".join(lines).strip()


def _index_memory_document(
    *,
    fields: dict[str, str | int],
    embedder: EmbeddingProvider,
    stats: MemoryRagIndexStats | None = None,
) -> int | None:
    before = find_rag_document(
        namespace=str(fields["namespace"]),
        source_type=str(fields["source_type"]),
        source_id=str(fields["source_id"]),
        chunk_index=int(fields["chunk_index"]),
        include_deleted=True,
    )
    document_id = upsert_rag_document(**fields)
    after = get_rag_document(document_id)
    if after is None:
        if stats is not None:
            stats.errors.append(f"{fields['title']}: indexed document disappeared after upsert")
        return None

    if stats is not None:
        _record_document_change(stats, before, after)
    _sync_memory_embedding(stats, after, embedder)
    return document_id


def _record_document_change(
    stats: MemoryRagIndexStats,
    before: RagDocument | None,
    after: RagDocument,
) -> None:
    if before is None:
        stats.created_documents += 1
    elif before.deleted_at:
        stats.reactivated_documents += 1
    elif (
        before.content_hash != after.content_hash
        or before.source_version != after.source_version
        or before.title != after.title
    ):
        stats.updated_documents += 1
    else:
        stats.unchanged_documents += 1


def _sync_memory_embedding(
    stats: MemoryRagIndexStats | None,
    document: RagDocument,
    embedder: EmbeddingProvider,
) -> None:
    existing = get_rag_embedding(
        document_id=document.id,
        provider=embedder.provider,
        model=embedder.model,
    )
    if existing is not None and existing.content_hash == document.content_hash:
        if stats is not None:
            stats.embeddings_skipped += 1
        return

    try:
        vector = embedder.embed(document.content)
    except Exception as exc:
        if stats is not None:
            stats.errors.append(f"{document.title}: embedding failed: {exc}")
        return

    upsert_rag_embedding(
        document_id=document.id,
        provider=embedder.provider,
        model=embedder.model,
        embedding=vector,
        content_hash=document.content_hash,
    )
    if stats is not None:
        if existing is None:
            stats.embeddings_created += 1
        else:
            stats.embeddings_updated += 1


def _soft_delete_stale_memory_documents(
    stats: MemoryRagIndexStats,
    active_document_ids: set[int],
    included_source_types: set[str],
) -> None:
    if not included_source_types:
        return

    for source_type in included_source_types:
        existing_documents = list_rag_documents(
            namespace=NAMESPACE_SEMANTIC_MEMORY,
            source_type=source_type,
            include_deleted=False,
            limit=None,
        )
        for document in existing_documents:
            if document.id in active_document_ids:
                continue
            if soft_delete_rag_document(document.id):
                stats.soft_deleted_documents += 1
