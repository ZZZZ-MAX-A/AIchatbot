from __future__ import annotations

from dataclasses import dataclass


NAMESPACE_SEMANTIC_MEMORY = "semantic_memory"
NAMESPACE_PROJECT_DOCS = "project_docs"

SOURCE_MANUAL_FACT = "manual_fact"
SOURCE_MANUAL_PREFERENCE = "manual_preference"
SOURCE_SESSION_SUMMARY = "session_summary"
SOURCE_PROJECT_DOC = "project_doc"

VISIBILITY_OWNER_ONLY = "owner_only"
VISIBILITY_SUBJECT_ONLY = "subject_only"
VISIBILITY_GROUP = "group"
VISIBILITY_PROJECT_OWNER = "project_owner"
VISIBILITY_PUBLIC = "public"


@dataclass(frozen=True)
class RagDocument:
    id: int
    namespace: str
    source_type: str
    source_id: str
    source_version: str
    subject_type: str
    subject_id: str
    session_key: str
    message_type: str
    user_id: str
    group_id: str
    visibility: str
    title: str
    content: str
    content_hash: str
    chunk_index: int
    created_at: str
    updated_at: str
    deleted_at: str


@dataclass(frozen=True)
class RagSearchResult:
    document: RagDocument
    score: float
