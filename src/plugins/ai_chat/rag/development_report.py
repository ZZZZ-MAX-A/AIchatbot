from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from ..development_context_report import DEVELOPMENT_CONTEXT_REPORT_SOURCE_LIMIT
from .combined import CombinedRagResults
from .memory_index import (
    MEMORY_SOURCE_TYPES,
    memory_document_visible,
    trim_results_to_context_chars as trim_memory_results,
)
from .project_docs import CURRENT_DEVELOPMENT_STATUS_SOURCE_ID
from .project_index import (
    CURRENT_STATUS_ANCHOR_MAX_CHARS,
    project_doc_visible,
    retrieve_current_development_status,
    trim_project_documents_to_context_chars,
    trim_results_to_context_chars as trim_project_results,
)
from .providers import EmbeddingProvider
from .schema import (
    NAMESPACE_PROJECT_DOCS,
    NAMESPACE_SEMANTIC_MEMORY,
    SOURCE_PROJECT_DOC,
    RagDocument,
    RagSearchResult,
)
from .search import search_rag_documents


DEVELOPMENT_REPORT_PROJECT_RESULT_LIMIT = 3
DEVELOPMENT_REPORT_PROJECT_CANDIDATE_MIN = 12
DEVELOPMENT_REPORT_PROJECT_CANDIDATE_MAX = 32
DEVELOPMENT_REPORT_PROJECT_CANDIDATE_MULTIPLIER = 4
DEVELOPMENT_REPORT_PROJECT_MAX_PER_SOURCE = 1

DEVELOPMENT_REPORT_PROJECT_MAX_CHARS = 1800
DEVELOPMENT_REPORT_MEMORY_MAX_CHARS = 800
DEVELOPMENT_REPORT_FORMAT_RESERVE_CHARS = 400
DEVELOPMENT_REPORT_EVIDENCE_MAX_CHARS = (
    CURRENT_STATUS_ANCHOR_MAX_CHARS
    + DEVELOPMENT_REPORT_PROJECT_MAX_CHARS
    + DEVELOPMENT_REPORT_MEMORY_MAX_CHARS
)

CURRENT_STATUS_ANCHOR_MISSING = "current_status_anchor_missing"
CURRENT_STATUS_ANCHOR_FAILED = "current_status_anchor_failed"
QUERY_EMBEDDING_FAILED = "query_embedding_failed"
PROJECT_RETRIEVAL_FAILED = "project_retrieval_failed"
MEMORY_RETRIEVAL_FAILED = "memory_retrieval_failed"

DevelopmentReportErrorCallback = Callable[[Exception, str], None]


@dataclass(frozen=True)
class DevelopmentReportRagExecution:
    results: CombinedRagResults
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def execution_failed(self) -> bool:
        return bool(self.errors and not self.results.has_results)


if (
    DEVELOPMENT_REPORT_EVIDENCE_MAX_CHARS
    + DEVELOPMENT_REPORT_FORMAT_RESERVE_CHARS
    != DEVELOPMENT_CONTEXT_REPORT_SOURCE_LIMIT
):
    raise RuntimeError("development report evidence budgets must match source limit")


def development_report_candidate_top_k(
    requested_results: int = DEVELOPMENT_REPORT_PROJECT_RESULT_LIMIT,
) -> int:
    if requested_results <= 0:
        return 0
    expanded = max(
        DEVELOPMENT_REPORT_PROJECT_CANDIDATE_MIN,
        requested_results * DEVELOPMENT_REPORT_PROJECT_CANDIDATE_MULTIPLIER,
    )
    return min(expanded, DEVELOPMENT_REPORT_PROJECT_CANDIDATE_MAX)


def retrieve_development_report_rag(
    *,
    query: str,
    embedder: EmbeddingProvider,
    is_owner: bool,
    project_min_score: float = 0.50,
    memory_top_k: int = 5,
    memory_min_score: float = 0.55,
    on_error: DevelopmentReportErrorCallback | None = None,
) -> DevelopmentReportRagExecution:
    """Retrieve fixed-anchor and diverse semantic evidence for the formal report only."""

    if not is_owner or not query.strip():
        return DevelopmentReportRagExecution(
            results=CombinedRagResults(project_docs=[], memories=[]),
        )

    warnings: list[str] = []
    errors: list[str] = []

    def record_error(exc: Exception, category: str) -> None:
        errors.append(category)
        if on_error is None:
            return
        try:
            on_error(exc, category)
        except Exception:
            # Observability must never replace the safe retrieval outcome.
            pass

    try:
        current_status_docs = retrieve_current_development_status(is_owner=is_owner)
    except Exception as exc:
        current_status_docs = []
        record_error(exc, CURRENT_STATUS_ANCHOR_FAILED)
    else:
        if not current_status_docs:
            warnings.append(CURRENT_STATUS_ANCHOR_MISSING)

    try:
        query_embedding = embedder.embed(query)
    except Exception as exc:
        record_error(exc, QUERY_EMBEDDING_FAILED)
        return DevelopmentReportRagExecution(
            results=build_development_report_evidence(
                current_status_docs=current_status_docs,
                project_candidates=[],
                memories=[],
            ),
            warnings=tuple(warnings),
            errors=tuple(errors),
        )

    project_candidates: list[RagSearchResult] = []
    try:
        raw_project_results = search_rag_documents(
            query_embedding=query_embedding,
            namespace=NAMESPACE_PROJECT_DOCS,
            provider=embedder.provider,
            model=embedder.model,
            source_types={SOURCE_PROJECT_DOC},
            min_score=project_min_score,
            top_k=development_report_candidate_top_k(),
        )
        project_candidates = [
            result
            for result in raw_project_results
            if project_doc_visible(result.document, is_owner=is_owner)
        ]
    except Exception as exc:
        record_error(exc, PROJECT_RETRIEVAL_FAILED)

    memories: list[RagSearchResult] = []
    if memory_top_k > 0:
        try:
            raw_memory_results = search_rag_documents(
                query_embedding=query_embedding,
                namespace=NAMESPACE_SEMANTIC_MEMORY,
                provider=embedder.provider,
                model=embedder.model,
                source_types=MEMORY_SOURCE_TYPES,
                min_score=memory_min_score,
                top_k=memory_top_k,
            )
            memories = [
                result
                for result in raw_memory_results
                if memory_document_visible(result.document, is_owner=is_owner)
            ]
        except Exception as exc:
            record_error(exc, MEMORY_RETRIEVAL_FAILED)

    return DevelopmentReportRagExecution(
        results=build_development_report_evidence(
            current_status_docs=current_status_docs,
            project_candidates=project_candidates,
            memories=memories,
        ),
        warnings=tuple(warnings),
        errors=tuple(errors),
    )


def select_development_report_project_results(
    candidates: Sequence[RagSearchResult],
    *,
    excluded_source_ids: Iterable[str] = (),
) -> list[RagSearchResult]:
    excluded = {CURRENT_DEVELOPMENT_STATUS_SOURCE_ID}
    excluded.update(str(source_id).strip() for source_id in excluded_source_ids)
    source_counts: dict[str, int] = {}
    selected: list[RagSearchResult] = []

    for candidate in candidates:
        source_id = candidate.document.source_id.strip()
        if not source_id or source_id in excluded:
            continue
        if source_counts.get(source_id, 0) >= DEVELOPMENT_REPORT_PROJECT_MAX_PER_SOURCE:
            continue
        selected.append(candidate)
        source_counts[source_id] = source_counts.get(source_id, 0) + 1
        if len(selected) >= DEVELOPMENT_REPORT_PROJECT_RESULT_LIMIT:
            break
    return selected


def build_development_report_evidence(
    *,
    current_status_docs: Sequence[RagDocument],
    project_candidates: Sequence[RagSearchResult],
    memories: Sequence[RagSearchResult],
) -> CombinedRagResults:
    anchor_documents = trim_project_documents_to_context_chars(
        list(current_status_docs),
        CURRENT_STATUS_ANCHOR_MAX_CHARS,
    )
    excluded_source_ids = {
        document.source_id for document in anchor_documents if document.source_id
    }
    diverse_projects = select_development_report_project_results(
        project_candidates,
        excluded_source_ids=excluded_source_ids,
    )
    project_results = trim_project_results(
        diverse_projects,
        DEVELOPMENT_REPORT_PROJECT_MAX_CHARS,
    )
    memory_results = trim_memory_results(
        list(memories),
        DEVELOPMENT_REPORT_MEMORY_MAX_CHARS,
    )
    return CombinedRagResults(
        current_status_docs=anchor_documents,
        project_docs=project_results,
        memories=memory_results,
    )


def development_report_evidence_content_chars(results: CombinedRagResults) -> int:
    return sum(
        len(document.content) for document in results.current_status_docs
    ) + sum(
        len(result.document.content) for result in results.project_docs
    ) + sum(
        len(result.document.content) for result in results.memories
    )
