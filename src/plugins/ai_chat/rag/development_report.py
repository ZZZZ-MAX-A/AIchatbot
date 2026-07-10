from __future__ import annotations

from collections.abc import Iterable, Sequence

from ..development_context_report import DEVELOPMENT_CONTEXT_REPORT_SOURCE_LIMIT
from .combined import CombinedRagResults
from .memory_index import trim_results_to_context_chars as trim_memory_results
from .project_docs import CURRENT_DEVELOPMENT_STATUS_SOURCE_ID
from .project_index import (
    CURRENT_STATUS_ANCHOR_MAX_CHARS,
    trim_project_documents_to_context_chars,
    trim_results_to_context_chars as trim_project_results,
)
from .schema import RagDocument, RagSearchResult


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
