"""RAG storage, indexing, and retrieval helpers."""

from .schema import (
    NAMESPACE_PROJECT_DOCS,
    NAMESPACE_SEMANTIC_MEMORY,
    SOURCE_MANUAL_FACT,
    SOURCE_MANUAL_PREFERENCE,
    SOURCE_PROJECT_DOC,
    SOURCE_SESSION_SUMMARY,
    VISIBILITY_GROUP,
    VISIBILITY_OWNER_ONLY,
    VISIBILITY_PROJECT_OWNER,
    VISIBILITY_PUBLIC,
    VISIBILITY_SUBJECT_ONLY,
    RagDocument,
    RagSearchResult,
)
from .project_index import ProjectDocIndexStats, rebuild_project_doc_index, retrieve_project_docs
from .memory_index import MemoryRagIndexStats, rebuild_memory_rag_index, retrieve_memory
from .combined import CombinedRagResults, format_combined_rag_results, retrieve_combined_rag

__all__ = [
    "NAMESPACE_PROJECT_DOCS",
    "NAMESPACE_SEMANTIC_MEMORY",
    "SOURCE_MANUAL_FACT",
    "SOURCE_MANUAL_PREFERENCE",
    "SOURCE_PROJECT_DOC",
    "SOURCE_SESSION_SUMMARY",
    "VISIBILITY_GROUP",
    "VISIBILITY_OWNER_ONLY",
    "VISIBILITY_PROJECT_OWNER",
    "VISIBILITY_PUBLIC",
    "VISIBILITY_SUBJECT_ONLY",
    "RagDocument",
    "RagSearchResult",
    "ProjectDocIndexStats",
    "rebuild_project_doc_index",
    "retrieve_project_docs",
    "MemoryRagIndexStats",
    "rebuild_memory_rag_index",
    "retrieve_memory",
    "CombinedRagResults",
    "format_combined_rag_results",
    "retrieve_combined_rag",
]
