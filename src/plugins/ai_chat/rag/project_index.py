from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from .documents import (
    find_rag_document,
    get_rag_document,
    list_rag_documents,
    soft_delete_rag_document,
    upsert_rag_document,
)
from .embeddings import get_rag_embedding, upsert_rag_embedding
from .project_docs import (
    CURRENT_DEVELOPMENT_STATUS_SOURCE_ID,
    chunk_markdown_document,
    iter_project_document_files,
)
from .providers import EmbeddingProvider
from .schema import (
    NAMESPACE_PROJECT_DOCS,
    SOURCE_PROJECT_DOC,
    VISIBILITY_OWNER_ONLY,
    VISIBILITY_PROJECT_OWNER,
    VISIBILITY_PUBLIC,
    RagDocument,
    RagSearchResult,
)
from .search import search_rag_documents
from ..reliability_events import record_failure_safely, record_success_safely


CURRENT_STATUS_ANCHOR_MAX_CHARS = 1200


@dataclass
class ProjectDocIndexStats:
    scanned_files: int = 0
    chunks_seen: int = 0
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
            "scanned_files": self.scanned_files,
            "chunks_seen": self.chunks_seen,
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


def rebuild_project_doc_index(
    *,
    root: Path,
    embedder: EmbeddingProvider,
    max_chars: int = 1800,
) -> ProjectDocIndexStats:
    try:
        stats = _rebuild_project_doc_index(
            root=root,
            embedder=embedder,
            max_chars=max_chars,
        )
    except Exception as exc:
        record_failure_safely("project_doc_rag", "rebuild_index", exc)
        raise
    if stats.has_errors:
        record_failure_safely(
            "project_doc_rag",
            "rebuild_index",
            stats.errors[0],
        )
    else:
        record_success_safely("project_doc_rag", "rebuild_index")
    return stats


def _rebuild_project_doc_index(
    *,
    root: Path,
    embedder: EmbeddingProvider,
    max_chars: int = 1800,
) -> ProjectDocIndexStats:
    root = root.resolve()
    stats = ProjectDocIndexStats()
    active_document_ids: set[int] = set()

    for path in iter_project_document_files(root):
        stats.scanned_files += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            chunks = chunk_markdown_document(path=path, text=text, root=root, max_chars=max_chars)
        except OSError as exc:
            stats.errors.append(f"{path}: {exc}")
            continue

        for chunk in chunks:
            stats.chunks_seen += 1
            before = find_rag_document(
                namespace=NAMESPACE_PROJECT_DOCS,
                source_type=SOURCE_PROJECT_DOC,
                source_id=chunk.source_id,
                chunk_index=chunk.chunk_index,
                include_deleted=True,
            )
            document_id = upsert_rag_document(
                namespace=NAMESPACE_PROJECT_DOCS,
                source_type=SOURCE_PROJECT_DOC,
                source_id=chunk.source_id,
                source_version=chunk.source_version,
                title=chunk.title,
                content=chunk.content,
                visibility=VISIBILITY_PROJECT_OWNER,
                chunk_index=chunk.chunk_index,
            )
            active_document_ids.add(document_id)

            after = get_rag_document(document_id)
            if after is None:
                stats.errors.append(f"{chunk.title}: indexed document disappeared after upsert")
                continue

            _record_document_change(stats, before, after)
            _sync_project_doc_embedding(stats, after, embedder)

    _soft_delete_stale_project_doc_chunks(stats, active_document_ids)
    return stats


def retrieve_project_docs(
    *,
    query: str,
    embedder: EmbeddingProvider,
    is_owner: bool,
    top_k: int = 4,
    min_score: float = 0.50,
    max_context_chars: int = 2000,
) -> list[RagSearchResult]:
    if not query.strip() or top_k <= 0 or max_context_chars <= 0:
        return []

    query_embedding = embedder.embed(query)
    results = search_rag_documents(
        query_embedding=query_embedding,
        namespace=NAMESPACE_PROJECT_DOCS,
        provider=embedder.provider,
        model=embedder.model,
        source_types={SOURCE_PROJECT_DOC},
        min_score=min_score,
        top_k=top_k,
    )
    visible = [result for result in results if project_doc_visible(result.document, is_owner=is_owner)]
    return trim_results_to_context_chars(visible, max_context_chars)


def retrieve_current_development_status(
    *,
    is_owner: bool,
    max_context_chars: int = CURRENT_STATUS_ANCHOR_MAX_CHARS,
) -> list[RagDocument]:
    """Read the one registered current-state anchor from ProjectDocRAG."""

    if not is_owner or max_context_chars <= 0:
        return []
    documents = list_rag_documents(
        namespace=NAMESPACE_PROJECT_DOCS,
        source_type=SOURCE_PROJECT_DOC,
        source_id=CURRENT_DEVELOPMENT_STATUS_SOURCE_ID,
        include_deleted=False,
        limit=None,
    )
    visible = [
        document
        for document in documents
        if project_doc_visible(document, is_owner=is_owner)
    ]
    ordered = sorted(visible, key=lambda document: document.chunk_index)
    return trim_project_documents_to_context_chars(ordered, max_context_chars)


def project_doc_visible(document: RagDocument, *, is_owner: bool) -> bool:
    if document.visibility == VISIBILITY_PUBLIC:
        return True
    if document.visibility in {VISIBILITY_OWNER_ONLY, VISIBILITY_PROJECT_OWNER}:
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


def trim_project_documents_to_context_chars(
    documents: list[RagDocument],
    max_context_chars: int,
) -> list[RagDocument]:
    if max_context_chars <= 0:
        return []

    trimmed: list[RagDocument] = []
    used = 0
    for document in documents:
        remaining = max_context_chars - used
        if remaining <= 0:
            break
        content = document.content
        if len(content) > remaining:
            trimmed.append(replace(document, content=content[:remaining].rstrip()))
            break
        trimmed.append(document)
        used += len(content)
    return trimmed


def format_project_doc_results(results: list[RagSearchResult]) -> str:
    if not results:
        return "ProjectDocRAG 暂无匹配项目文档。"

    lines: list[str] = ["ProjectDocRAG 项目文档召回："]
    for index, result in enumerate(results, start=1):
        document = result.document
        lines.append(f"{index}. {document.title}")
        lines.append(f"   路径：{document.source_id}")
        lines.append(f"   相似度：{result.score:.3f}，片段：{document.chunk_index}")
        lines.append(document.content)
        lines.append("")
    return "\n".join(lines).strip()


def _record_document_change(
    stats: ProjectDocIndexStats,
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


def _sync_project_doc_embedding(
    stats: ProjectDocIndexStats,
    document: RagDocument,
    embedder: EmbeddingProvider,
) -> None:
    existing = get_rag_embedding(
        document_id=document.id,
        provider=embedder.provider,
        model=embedder.model,
    )
    if existing is not None and existing.content_hash == document.content_hash:
        stats.embeddings_skipped += 1
        return

    try:
        vector = embedder.embed(document.content)
    except Exception as exc:
        stats.errors.append(f"{document.title}: embedding failed: {exc}")
        return

    upsert_rag_embedding(
        document_id=document.id,
        provider=embedder.provider,
        model=embedder.model,
        embedding=vector,
        content_hash=document.content_hash,
    )
    if existing is None:
        stats.embeddings_created += 1
    else:
        stats.embeddings_updated += 1


def _soft_delete_stale_project_doc_chunks(
    stats: ProjectDocIndexStats,
    active_document_ids: set[int],
) -> None:
    existing_documents = list_rag_documents(
        namespace=NAMESPACE_PROJECT_DOCS,
        source_type=SOURCE_PROJECT_DOC,
        include_deleted=False,
        limit=None,
    )
    for document in existing_documents:
        if document.id in active_document_ids:
            continue
        if soft_delete_rag_document(document.id):
            stats.soft_deleted_documents += 1
