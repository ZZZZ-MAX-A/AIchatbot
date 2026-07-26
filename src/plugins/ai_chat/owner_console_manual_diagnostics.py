from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, replace
from typing import Any, Callable

from .database import connect_read_only, utc_now
from .owner_console_main_llm_contract import (
    MAIN_LLM_CONTRACT_ACTION_HEADER,
    MAIN_LLM_CONTRACT_CONFIRMATION,
    MAIN_LLM_CONTRACT_LATENCY_ATTENTION_MS,
    MAIN_LLM_CONTRACT_PROBE_ID,
    MAIN_LLM_CONTRACT_VERSION,
    MAIN_LLM_CONTRACT_WORKFLOW,
    MainLlmContractEvidence,
    MainLlmContractExecutor,
    MainLlmContractFailure,
)
from .owner_console_cloud_vision import (
    CLOUD_VISION_ACTION_HEADER,
    CLOUD_VISION_CONFIRMATION,
    CLOUD_VISION_LATENCY_ATTENTION_MS,
    CLOUD_VISION_REFERENCE_PREVIEW_ACTION_HEADER,
    CLOUD_VISION_RESPONSE_QUALITY_ACCEPT_ACTION_HEADER,
    CLOUD_VISION_RESPONSE_QUALITY_ACCEPT_CONFIRMATION,
    CLOUD_VISION_RESPONSE_QUALITY_REJECT_ACTION_HEADER,
    CLOUD_VISION_RESPONSE_QUALITY_REJECT_CONFIRMATION,
    CLOUD_VISION_WORKFLOW,
    CloudVisionEvidence,
    CloudVisionExecutor,
    CloudVisionFailure,
)
from .owner_console_tts_synthesis import (
    TTS_AUDIO_PREVIEW_ACTION_HEADER,
    TTS_AUDIO_QUALITY_ACCEPT_ACTION_HEADER,
    TTS_AUDIO_QUALITY_ACCEPT_CONFIRMATION,
    TTS_AUDIO_QUALITY_REJECT_ACTION_HEADER,
    TTS_AUDIO_QUALITY_REJECT_CONFIRMATION,
    TTS_SYNTHESIS_ACTION_HEADER,
    TTS_SYNTHESIS_CONFIRMATION,
    TTS_SYNTHESIS_FIXED_TEXT,
    TTS_SYNTHESIS_LATENCY_ATTENTION_MS,
    TTS_SYNTHESIS_STARTUP_ATTENTION_MS,
    TTS_SYNTHESIS_WORKFLOW,
    TtsAudioPreviewStore,
    TtsSynthesisEvidence,
    TtsSynthesisExecutor,
    TtsSynthesisFailure,
)
from .owner_console_vision_inference import (
    VISION_FIXED_CONTRACT_VERSION,
    VISION_INFERENCE_ACTION_HEADER,
    VISION_INFERENCE_CONFIRMATION,
    VISION_INFERENCE_LATENCY_ATTENTION_MS,
    VISION_INFERENCE_WORKFLOW,
    VISION_REFERENCE_PREVIEW_ACTION_HEADER,
    VISION_REFERENCE_STICKER_ID,
    VISION_RESPONSE_QUALITY_ACCEPT_ACTION_HEADER,
    VISION_RESPONSE_QUALITY_ACCEPT_CONFIRMATION,
    VISION_RESPONSE_QUALITY_REJECT_ACTION_HEADER,
    VISION_RESPONSE_QUALITY_REJECT_CONFIRMATION,
    VISION_STARTUP_ATTENTION_MS,
    VisionInferenceEvidence,
    VisionInferenceExecutor,
    VisionInferenceFailure,
    VisionReferenceAsset,
    _load_registered_reference_asset,
)
from .rag.embeddings import deserialize_embedding
from .rag.providers import OllamaEmbeddingProvider, build_embedding_provider
from .rag.schema import (
    NAMESPACE_PROJECT_DOCS,
    NAMESPACE_SEMANTIC_MEMORY,
    SOURCE_MANUAL_FACT,
    SOURCE_MANUAL_PREFERENCE,
    SOURCE_PROJECT_DOC,
    SOURCE_SESSION_SUMMARY,
    VISIBILITY_OWNER_ONLY,
    VISIBILITY_PROJECT_OWNER,
    VISIBILITY_PUBLIC,
)


PROJECT_DOC_RAG_PROBE_WORKFLOW = "project_doc_rag_fixed_retrieval"
PROJECT_DOC_RAG_PROBE_QUERY = (
    "P2.49 Owner Console 手动诊断工作流 ProjectDocRAG 固定检索"
)
PROJECT_DOC_RAG_PROBE_EXPECTED_SOURCE_ID = (
    "docs/owner-console-manual-diagnostics-design.md"
)
PROJECT_DOC_RAG_PROBE_TOP_K = 5
PROJECT_DOC_RAG_PROBE_CONFIRMATION = "run_registered_project_doc_rag_probe"
PROJECT_DOC_RAG_PROBE_ACTION_HEADER = "manual-project-doc-rag-probe-v1"
MEMORY_RAG_CONSISTENCY_WORKFLOW = "memory_rag_index_consistency"
MEMORY_RAG_CONSISTENCY_CONFIRMATION = "run_registered_memory_rag_consistency"
MEMORY_RAG_CONSISTENCY_ACTION_HEADER = "manual-memory-rag-consistency-v1"


@dataclass(frozen=True)
class ProjectDocRagIndexCounts:
    document_count: int
    embedding_count: int


@dataclass(frozen=True)
class ProjectDocRagProbeHit:
    source_id: str
    chunk_index: int
    score: float


@dataclass(frozen=True)
class ProjectDocRagProbeEvidence:
    document_count: int
    embedding_count: int
    result_count: int
    expected_document_matched: bool
    top_score: float
    elapsed_ms: int
    runtime_feature_enabled: bool = False


@dataclass(frozen=True)
class MemoryRagConsistencyEvidence:
    manual_fact_documents: int
    manual_preference_documents: int
    session_summary_documents: int
    active_document_count: int
    valid_embedding_count: int
    missing_embedding_count: int
    missing_manual_fact_embeddings: int
    missing_manual_preference_embeddings: int
    missing_session_summary_embeddings: int
    active_documents_missing_source: int
    source_records_missing_document: int
    inactive_document_embedding_count: int
    runtime_feature_enabled: bool
    elapsed_ms: int


@dataclass(frozen=True)
class OwnerConsoleMemoryRagConsistencyRun:
    run_id: int
    workflow: str
    status: str
    outcome: str
    stage: str
    code: str
    code_label: str
    started_at: str
    finished_at: str
    attempt_count: int
    manual_fact_documents: int
    manual_preference_documents: int
    session_summary_documents: int
    active_document_count: int
    valid_embedding_count: int
    missing_embedding_count: int
    missing_manual_fact_embeddings: int
    missing_manual_preference_embeddings: int
    missing_session_summary_embeddings: int
    active_documents_missing_source: int
    source_records_missing_document: int
    inactive_document_embedding_count: int
    runtime_feature_enabled: bool
    elapsed_ms: int
    owner_triggered: bool = True
    memory_content_read: bool = False
    private_memory_query_executed: bool = False
    embedding_called: bool = False
    index_rebuild_executed: bool = False
    database_write_allowed: bool = False
    llm_called: bool = False
    dev_context_called: bool = False
    automatic_retry: bool = False


@dataclass(frozen=True)
class OwnerConsoleMainLlmContractRun:
    run_id: int
    workflow: str
    status: str
    outcome: str
    stage: str
    code: str
    code_label: str
    started_at: str
    finished_at: str
    attempt_count: int
    configured_model: str
    runtime_feature_enabled: bool
    contract_version: str
    probe_id: str
    contract_valid: bool
    usage_metadata_available: bool
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    tool_calls_present: bool
    elapsed_ms: int
    owner_triggered: bool = True
    llm_called: bool = False
    tool_definitions_sent: bool = False
    tool_execution_allowed: bool = False
    client_automatic_retry: bool = False
    chat_history_read: bool = False
    chat_history_written: bool = False
    agent_task_written: bool = False
    approval_written: bool = False
    reliability_event_written: bool = False
    database_write_allowed: bool = False
    memory_rag_called: bool = False
    project_doc_rag_called: bool = False
    dev_context_called: bool = False
    combined_rag_called: bool = False
    tavily_called: bool = False
    tts_called: bool = False
    vision_called: bool = False
    qq_write_executed: bool = False
    prompt_exposed: bool = False
    response_content_exposed: bool = False


@dataclass(frozen=True)
class OwnerConsoleTtsSynthesisRun:
    run_id: int
    workflow: str
    status: str
    outcome: str
    stage: str
    code: str
    code_label: str
    started_at: str
    finished_at: str
    attempt_count: int
    runtime_feature_enabled: bool
    service_health_checked: bool
    service_healthy: bool
    model_loaded_before: bool
    runtime_imported_before: bool
    model_load_may_have_occurred: bool
    configured_voice_present: bool
    tts_called: bool
    output_contract_valid: bool
    output_file_created: bool
    output_bytes: int
    output_duration_ms: int
    output_retained: bool
    partial_artifact_state: str
    health_elapsed_ms: int
    synthesis_elapsed_ms: int
    elapsed_ms: int
    fixed_text: str
    technical_outcome: str
    technical_code: str
    audio_preview_available: bool
    audio_quality_review_required: bool
    audio_quality_reviewed: bool
    audio_quality_accepted: bool | None
    audio_reviewed_at: str
    owner_triggered: bool = True
    service_preexisting: bool = False
    service_start_attempted: bool = False
    service_started: bool = False
    service_owned_by_diagnostic: bool = False
    service_stop_attempted: bool = False
    service_stopped: bool = False
    segment_directory_retained: bool = False
    artifact_cleanup_attempted: bool = False
    artifact_cleanup_succeeded: bool = False
    startup_elapsed_ms: int = 0
    cleanup_elapsed_ms: int = 0
    automatic_retry: bool = False
    qq_write_executed: bool = False
    reliability_event_written: bool = False
    database_write_allowed: bool = False
    local_file_write_expected: bool = True
    cleanup_executed: bool = False
    chat_history_read: bool = False
    memory_rag_called: bool = False
    project_doc_rag_called: bool = False
    dev_context_called: bool = False
    combined_rag_called: bool = False
    main_llm_called: bool = False
    vision_called: bool = False
    prompt_exposed: bool = False
    response_content_exposed: bool = False
    output_path_exposed: bool = False
    fixed_text_exposed: bool = True
    audio_preview_persisted: bool = False
    audio_preview_path_exposed: bool = False
    audio_review_action_executed: bool = False


@dataclass(frozen=True)
class OwnerConsoleVisionInferenceRun:
    run_id: int
    workflow: str
    status: str
    outcome: str
    stage: str
    code: str
    code_label: str
    started_at: str
    finished_at: str
    attempt_count: int
    configured_model: str
    runtime_feature_enabled: bool
    fixed_image_contract: str
    fixed_image_bytes: int
    fixed_image_contract_valid: bool
    reference_sticker_id: str
    registered_reference_asset_read: bool
    expected_answer_disclosed_in_prompt: bool
    service_tags_checked: bool
    service_healthy: bool
    service_preexisting: bool
    service_start_attempted: bool
    service_started: bool
    service_owned_by_diagnostic: bool
    service_ownership_basis: str
    service_stop_attempted: bool
    service_stopped: bool
    model_available: bool
    model_residency_checked: bool
    model_loaded_before: bool
    keep_alive_zero_used: bool
    vision_called: bool
    response_contract_valid: bool
    response_mode: str
    structured_output_requested: bool
    semantic_contract_automatically_validated: bool
    owner_visual_judgment_required: bool
    response_preview: str
    response_description: str
    response_content_exposed_to_owner: bool
    usage_metadata_available: bool
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    model_cleanup_required: bool
    model_cleanup_verified: bool
    model_cleanup_poll_count: int
    startup_elapsed_ms: int
    discovery_elapsed_ms: int
    residency_elapsed_ms: int
    inference_elapsed_ms: int
    cleanup_elapsed_ms: int
    elapsed_ms: int
    technical_outcome: str = ""
    technical_code: str = ""
    reference_preview_available: bool = False
    visual_quality_review_required: bool = False
    visual_quality_reviewed: bool = False
    visual_quality_accepted: bool | None = None
    visual_reviewed_at: str = ""
    visual_review_action_executed: bool = False
    response_preview_persisted: bool = False
    response_preview_path_exposed: bool = False
    reference_image_exposed_to_owner: bool = False
    owner_triggered: bool = True
    client_automatic_retry: bool = False
    tool_definitions_sent: bool = False
    qq_write_executed: bool = False
    reliability_event_written: bool = False
    database_write_allowed: bool = False
    project_file_write_allowed: bool = False
    project_artifact_write_expected: bool = False
    external_runtime_local_write_possible: bool = True
    model_pull_allowed: bool = False
    chat_history_read: bool = False
    memory_rag_called: bool = False
    project_doc_rag_called: bool = False
    dev_context_called: bool = False
    combined_rag_called: bool = False
    main_llm_called: bool = False
    tts_called: bool = False
    image_content_exposed: bool = False
    response_content_exposed: bool = False


@dataclass(frozen=True)
class OwnerConsoleCloudVisionRun:
    run_id: int
    workflow: str
    status: str
    outcome: str
    stage: str
    code: str
    code_label: str
    started_at: str
    finished_at: str
    attempt_count: int
    provider: str
    region: str
    configured_model: str
    returned_model: str
    runtime_feature_enabled: bool
    endpoint_contract_valid: bool
    workspace_configured: bool
    credentials_configured: bool
    fixed_image_contract: str
    fixed_image_bytes: int
    fixed_image_contract_valid: bool
    reference_sticker_id: str
    registered_reference_asset_read: bool
    external_image_upload_planned: bool
    external_image_upload_executed: bool
    provider_side_persistence_controlled_by_app: bool
    cloud_vision_called: bool
    request_count: int
    client_automatic_retry: bool
    tool_definitions_sent: bool
    thinking_enabled: bool
    response_mode: str
    structured_output_requested: bool
    semantic_contract_automatically_validated: bool
    owner_visual_judgment_required: bool
    response_contract_valid: bool
    response_preview: str
    response_description: str
    response_cleanup_applied: bool
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_elapsed_ms: int
    technical_outcome: str = ""
    technical_code: str = ""
    reference_preview_available: bool = False
    visual_quality_review_required: bool = False
    visual_quality_reviewed: bool = False
    visual_quality_accepted: bool | None = None
    visual_reviewed_at: str = ""
    visual_review_action_executed: bool = False
    owner_triggered: bool = True
    api_key_exposed: bool = False
    workspace_id_exposed: bool = False
    image_base64_exposed: bool = False
    response_preview_persisted: bool = False
    local_gpu_model_loaded: bool = False
    database_write_allowed: bool = False
    project_artifact_write_expected: bool = False
    reliability_event_written: bool = False
    qq_write_executed: bool = False
    chat_history_written: bool = False
    agent_task_written: bool = False
    approval_written: bool = False
    memory_rag_called: bool = False
    project_doc_rag_called: bool = False
    dev_context_called: bool = False
    combined_rag_called: bool = False
    main_llm_called: bool = False
    tts_called: bool = False
    local_vision_called: bool = False


@dataclass(frozen=True)
class OwnerConsoleManualDiagnosticRun:
    run_id: int
    workflow: str
    status: str
    outcome: str
    stage: str
    code: str
    code_label: str
    started_at: str
    finished_at: str
    attempt_count: int
    document_count: int
    embedding_count: int
    result_count: int
    expected_document_matched: bool
    top_score: float
    elapsed_ms: int
    runtime_feature_enabled: bool
    owner_triggered: bool = True
    query_text_exposed: bool = False
    result_content_exposed: bool = False
    index_rebuild_executed: bool = False
    database_write_allowed: bool = False
    llm_called: bool = False
    dev_context_called: bool = False
    automatic_retry: bool = False


@dataclass(frozen=True)
class OwnerConsoleManualDiagnosticsSnapshot:
    generated_at: str
    manual_diagnostic_actions_enabled: bool
    project_doc_rag_probe_enabled: bool
    memory_rag_consistency_enabled: bool
    main_llm_contract_enabled: bool
    tts_synthesis_enabled: bool
    vision_inference_enabled: bool
    cloud_vision_enabled: bool
    cloud_vision_workspace_configured: bool
    cloud_vision_credentials_configured: bool
    automatic_diagnostics_enabled: bool
    configuration_write_enabled: bool
    business_data_write_enabled: bool
    supported_workflows: list[str]
    latest_run: (
        OwnerConsoleManualDiagnosticRun
        | OwnerConsoleMemoryRagConsistencyRun
        | OwnerConsoleMainLlmContractRun
        | OwnerConsoleTtsSynthesisRun
        | OwnerConsoleVisionInferenceRun
        | OwnerConsoleCloudVisionRun
        | None
    )
    project_doc_rag_latest_run: OwnerConsoleManualDiagnosticRun | None
    memory_rag_consistency_latest_run: OwnerConsoleMemoryRagConsistencyRun | None
    main_llm_contract_latest_run: OwnerConsoleMainLlmContractRun | None
    tts_synthesis_latest_run: OwnerConsoleTtsSynthesisRun | None
    vision_inference_latest_run: OwnerConsoleVisionInferenceRun | None
    cloud_vision_latest_run: OwnerConsoleCloudVisionRun | None


class OwnerConsoleManualDiagnosticDisabled(RuntimeError):
    pass


class OwnerConsoleManualDiagnosticBusy(RuntimeError):
    pass


class OwnerConsoleTtsAudioReviewUnavailable(RuntimeError):
    pass


class OwnerConsoleVisionReviewUnavailable(RuntimeError):
    pass


class OwnerConsoleCloudVisionReviewUnavailable(RuntimeError):
    pass


class ProjectDocRagProbeFailure(RuntimeError):
    def __init__(
        self,
        *,
        stage: str,
        code: str,
        code_label: str,
        document_count: int = 0,
        embedding_count: int = 0,
        result_count: int = 0,
        expected_document_matched: bool = False,
        top_score: float = 0.0,
        elapsed_ms: int = 0,
        runtime_feature_enabled: bool = False,
    ) -> None:
        super().__init__(code)
        self.stage = stage
        self.code = code
        self.code_label = code_label
        self.document_count = document_count
        self.embedding_count = embedding_count
        self.result_count = result_count
        self.expected_document_matched = expected_document_matched
        self.top_score = top_score
        self.elapsed_ms = elapsed_ms
        self.runtime_feature_enabled = runtime_feature_enabled


class MemoryRagConsistencyFailure(RuntimeError):
    pass


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return dot / (left_norm * right_norm)


def read_project_doc_rag_index_counts(
    *,
    provider: str,
    model: str,
) -> ProjectDocRagIndexCounts:
    """Read ProjectDocRAG counts without schema creation or a writable connection."""

    with connect_read_only() as connection:
        document_count = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM rag_documents
                WHERE namespace = ?
                  AND source_type = ?
                  AND deleted_at IS NULL
                """,
                (NAMESPACE_PROJECT_DOCS, SOURCE_PROJECT_DOC),
            ).fetchone()[0]
        )
        embedding_count = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM rag_documents d
                JOIN rag_embeddings e ON e.document_id = d.id
                WHERE d.namespace = ?
                  AND d.source_type = ?
                  AND d.deleted_at IS NULL
                  AND e.embedding_provider = ?
                  AND e.embedding_model = ?
                  AND e.content_hash = d.content_hash
                """,
                (NAMESPACE_PROJECT_DOCS, SOURCE_PROJECT_DOC, provider, model),
            ).fetchone()[0]
        )
    return ProjectDocRagIndexCounts(
        document_count=document_count,
        embedding_count=embedding_count,
    )


def search_project_doc_rag_metadata_read_only(
    *,
    query_embedding: list[float],
    provider: str,
    model: str,
    top_k: int = PROJECT_DOC_RAG_PROBE_TOP_K,
) -> list[ProjectDocRagProbeHit]:
    """Search only safe ProjectDocRAG metadata; document content is never selected."""

    if top_k <= 0:
        return []
    with connect_read_only() as connection:
        rows = connection.execute(
            """
            SELECT
                d.source_id,
                d.chunk_index,
                e.embedding
            FROM rag_documents d
            JOIN rag_embeddings e ON e.document_id = d.id
            WHERE d.namespace = ?
              AND d.source_type = ?
              AND d.deleted_at IS NULL
              AND d.visibility IN (?, ?, ?)
              AND e.embedding_provider = ?
              AND e.embedding_model = ?
              AND e.content_hash = d.content_hash
            """,
            (
                NAMESPACE_PROJECT_DOCS,
                SOURCE_PROJECT_DOC,
                VISIBILITY_PUBLIC,
                VISIBILITY_OWNER_ONLY,
                VISIBILITY_PROJECT_OWNER,
                provider,
                model,
            ),
        ).fetchall()

    hits = [
        ProjectDocRagProbeHit(
            source_id=str(row["source_id"]),
            chunk_index=int(row["chunk_index"]),
            score=_cosine_similarity(
                query_embedding,
                deserialize_embedding(str(row["embedding"])),
            ),
        )
        for row in rows
    ]
    hits.sort(key=lambda item: (-item.score, item.source_id, item.chunk_index))
    return hits[:top_k]


def read_memory_rag_consistency(
    *,
    provider: str,
    model: str,
    include_manual_facts: bool,
    include_manual_preferences: bool,
    include_session_summaries: bool,
    runtime_feature_enabled: bool,
) -> MemoryRagConsistencyEvidence:
    """Read MemoryRAG integrity counters without selecting private content."""

    started = time.monotonic()
    with connect_read_only() as connection:
        source_rows = connection.execute(
            """
            SELECT source_type, COUNT(*) AS item_count
            FROM rag_documents
            WHERE namespace = ?
              AND deleted_at IS NULL
              AND source_type IN (?, ?, ?)
            GROUP BY source_type
            """,
            (
                NAMESPACE_SEMANTIC_MEMORY,
                SOURCE_MANUAL_FACT,
                SOURCE_MANUAL_PREFERENCE,
                SOURCE_SESSION_SUMMARY,
            ),
        ).fetchall()
        source_counts = {
            str(row["source_type"]): int(row["item_count"])
            for row in source_rows
        }
        active_document_count = sum(source_counts.values())
        valid_embedding_count = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM rag_documents d
                JOIN rag_embeddings e ON e.document_id = d.id
                WHERE d.namespace = ?
                  AND d.deleted_at IS NULL
                  AND d.source_type IN (?, ?, ?)
                  AND e.embedding_provider = ?
                  AND e.embedding_model = ?
                  AND e.content_hash = d.content_hash
                """,
                (
                    NAMESPACE_SEMANTIC_MEMORY,
                    SOURCE_MANUAL_FACT,
                    SOURCE_MANUAL_PREFERENCE,
                    SOURCE_SESSION_SUMMARY,
                    provider,
                    model,
                ),
            ).fetchone()[0]
        )
        missing_rows = connection.execute(
            """
            SELECT d.source_type, COUNT(*) AS item_count
            FROM rag_documents d
            WHERE d.namespace = ?
              AND d.deleted_at IS NULL
              AND d.source_type IN (?, ?, ?)
              AND NOT EXISTS (
                  SELECT 1
                  FROM rag_embeddings e
                  WHERE e.document_id = d.id
                    AND e.embedding_provider = ?
                    AND e.embedding_model = ?
                    AND e.content_hash = d.content_hash
              )
            GROUP BY d.source_type
            """,
            (
                NAMESPACE_SEMANTIC_MEMORY,
                SOURCE_MANUAL_FACT,
                SOURCE_MANUAL_PREFERENCE,
                SOURCE_SESSION_SUMMARY,
                provider,
                model,
            ),
        ).fetchall()
        missing_counts = {
            str(row["source_type"]): int(row["item_count"])
            for row in missing_rows
        }
        active_documents_missing_source = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM rag_documents d
                LEFT JOIN long_term_memories m
                  ON d.source_type IN (?, ?)
                 AND d.source_id = CAST(m.id AS TEXT)
                LEFT JOIN session_summaries s
                  ON d.source_type = ?
                 AND d.source_id = CAST(s.id AS TEXT)
                WHERE d.namespace = ?
                  AND d.deleted_at IS NULL
                  AND (
                      (d.source_type IN (?, ?) AND m.id IS NULL)
                      OR (d.source_type = ? AND s.id IS NULL)
                  )
                """,
                (
                    SOURCE_MANUAL_FACT,
                    SOURCE_MANUAL_PREFERENCE,
                    SOURCE_SESSION_SUMMARY,
                    NAMESPACE_SEMANTIC_MEMORY,
                    SOURCE_MANUAL_FACT,
                    SOURCE_MANUAL_PREFERENCE,
                    SOURCE_SESSION_SUMMARY,
                ),
            ).fetchone()[0]
        )
        manual_sources_missing_document = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM long_term_memories m
                WHERE (
                    (? AND m.memory_type != 'preference_summary')
                    OR (? AND m.memory_type = 'preference_summary')
                )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM rag_documents d
                      WHERE d.namespace = ?
                        AND d.deleted_at IS NULL
                        AND d.source_id = CAST(m.id AS TEXT)
                        AND d.source_type = CASE
                            WHEN m.memory_type = 'preference_summary'
                            THEN ? ELSE ? END
                  )
                """,
                (
                    include_manual_facts,
                    include_manual_preferences,
                    NAMESPACE_SEMANTIC_MEMORY,
                    SOURCE_MANUAL_PREFERENCE,
                    SOURCE_MANUAL_FACT,
                ),
            ).fetchone()[0]
        )
        summary_sources_missing_document = 0
        if include_session_summaries:
            summary_sources_missing_document = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM session_summaries s
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM rag_documents d
                        WHERE d.namespace = ?
                          AND d.deleted_at IS NULL
                          AND d.source_type = ?
                          AND d.source_id = CAST(s.id AS TEXT)
                    )
                    """,
                    (NAMESPACE_SEMANTIC_MEMORY, SOURCE_SESSION_SUMMARY),
                ).fetchone()[0]
            )
        inactive_document_embedding_count = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM rag_embeddings e
                JOIN rag_documents d ON d.id = e.document_id
                WHERE d.namespace = ?
                  AND d.deleted_at IS NOT NULL
                  AND e.embedding_provider = ?
                  AND e.embedding_model = ?
                """,
                (NAMESPACE_SEMANTIC_MEMORY, provider, model),
            ).fetchone()[0]
        )

    return MemoryRagConsistencyEvidence(
        manual_fact_documents=source_counts.get(SOURCE_MANUAL_FACT, 0),
        manual_preference_documents=source_counts.get(
            SOURCE_MANUAL_PREFERENCE,
            0,
        ),
        session_summary_documents=source_counts.get(SOURCE_SESSION_SUMMARY, 0),
        active_document_count=active_document_count,
        valid_embedding_count=valid_embedding_count,
        missing_embedding_count=sum(missing_counts.values()),
        missing_manual_fact_embeddings=missing_counts.get(SOURCE_MANUAL_FACT, 0),
        missing_manual_preference_embeddings=missing_counts.get(
            SOURCE_MANUAL_PREFERENCE,
            0,
        ),
        missing_session_summary_embeddings=missing_counts.get(
            SOURCE_SESSION_SUMMARY,
            0,
        ),
        active_documents_missing_source=active_documents_missing_source,
        source_records_missing_document=(
            manual_sources_missing_document + summary_sources_missing_document
        ),
        inactive_document_embedding_count=inactive_document_embedding_count,
        runtime_feature_enabled=runtime_feature_enabled,
        elapsed_ms=max(int((time.monotonic() - started) * 1000), 0),
    )


class MemoryRagConsistencyExecutor:
    def __init__(
        self,
        *,
        config_provider: Callable[[], Any],
        reader: Callable[..., MemoryRagConsistencyEvidence] = (
            read_memory_rag_consistency
        ),
    ) -> None:
        self._config_provider = config_provider
        self._reader = reader

    def __call__(self) -> MemoryRagConsistencyEvidence:
        config = self._config_provider()
        try:
            embedder = build_embedding_provider(config)
            return self._reader(
                provider=embedder.provider,
                model=embedder.model,
                include_manual_facts=bool(
                    getattr(config, "memory_rag_include_manual_facts", False)
                ),
                include_manual_preferences=bool(
                    getattr(
                        config,
                        "memory_rag_include_manual_preferences",
                        False,
                    )
                ),
                include_session_summaries=bool(
                    getattr(
                        config,
                        "memory_rag_include_session_summaries",
                        False,
                    )
                ),
                runtime_feature_enabled=bool(
                    getattr(config, "enable_memory_rag", False)
                ),
            )
        except Exception as exc:
            raise MemoryRagConsistencyFailure(
                "memory RAG consistency read failed"
            ) from exc


class ProjectDocRagProbeExecutor:
    def __init__(
        self,
        *,
        config_provider: Callable[[], Any],
        embedder_factory: Callable[[Any], Any] = build_embedding_provider,
        count_reader: Callable[..., ProjectDocRagIndexCounts] = (
            read_project_doc_rag_index_counts
        ),
        searcher: Callable[..., list[ProjectDocRagProbeHit]] = (
            search_project_doc_rag_metadata_read_only
        ),
    ) -> None:
        self._config_provider = config_provider
        self._embedder_factory = embedder_factory
        self._count_reader = count_reader
        self._searcher = searcher

    def __call__(self) -> ProjectDocRagProbeEvidence:
        started = time.monotonic()
        config = self._config_provider()
        runtime_feature_enabled = bool(
            getattr(config, "enable_project_doc_rag", False)
        )

        embedder = self._embedder_factory(config)
        if not isinstance(embedder, OllamaEmbeddingProvider):
            raise ProjectDocRagProbeFailure(
                stage="preflight",
                code="unsupported_embedding_provider",
                code_label="当前 embedding provider 不在首阶段允许范围内",
                runtime_feature_enabled=runtime_feature_enabled,
            )

        try:
            counts = self._count_reader(
                provider=embedder.provider,
                model=embedder.model,
            )
        except Exception as exc:
            raise ProjectDocRagProbeFailure(
                stage="index_preflight",
                code="project_doc_index_unavailable",
                code_label="无法以只读方式检查项目文档索引",
                runtime_feature_enabled=runtime_feature_enabled,
            ) from exc
        if counts.document_count <= 0:
            raise ProjectDocRagProbeFailure(
                stage="index_preflight",
                code="project_doc_index_empty",
                code_label="项目文档索引当前没有活动文档",
                runtime_feature_enabled=runtime_feature_enabled,
            )
        if counts.document_count != counts.embedding_count:
            raise ProjectDocRagProbeFailure(
                stage="index_preflight",
                code="project_doc_index_incomplete",
                code_label="项目文档与有效向量数量不一致",
                document_count=counts.document_count,
                embedding_count=counts.embedding_count,
                runtime_feature_enabled=runtime_feature_enabled,
            )

        try:
            query_embedding = embedder.embed_once(PROJECT_DOC_RAG_PROBE_QUERY)
        except Exception as exc:
            raise ProjectDocRagProbeFailure(
                stage="query_embedding",
                code="query_embedding_failed",
                code_label="固定诊断问题未能生成查询向量",
                document_count=counts.document_count,
                embedding_count=counts.embedding_count,
                runtime_feature_enabled=runtime_feature_enabled,
            ) from exc

        try:
            hits = self._searcher(
                query_embedding=query_embedding,
                provider=embedder.provider,
                model=embedder.model,
                top_k=PROJECT_DOC_RAG_PROBE_TOP_K,
            )
        except Exception as exc:
            raise ProjectDocRagProbeFailure(
                stage="retrieval",
                code="retrieval_execution_failed",
                code_label="固定项目文档检索未能完成",
                document_count=counts.document_count,
                embedding_count=counts.embedding_count,
                runtime_feature_enabled=runtime_feature_enabled,
            ) from exc

        matched = any(
            hit.source_id == PROJECT_DOC_RAG_PROBE_EXPECTED_SOURCE_ID
            for hit in hits
        )
        if not matched:
            raise ProjectDocRagProbeFailure(
                stage="result_validation",
                code="expected_document_not_retrieved",
                code_label="固定目标文档没有进入前五项结果",
                document_count=counts.document_count,
                embedding_count=counts.embedding_count,
                result_count=len(hits),
                top_score=round(hits[0].score, 3) if hits else 0.0,
                elapsed_ms=max(int((time.monotonic() - started) * 1000), 0),
                runtime_feature_enabled=runtime_feature_enabled,
            )

        elapsed_ms = max(int((time.monotonic() - started) * 1000), 0)
        return ProjectDocRagProbeEvidence(
            document_count=counts.document_count,
            embedding_count=counts.embedding_count,
            result_count=len(hits),
            expected_document_matched=True,
            top_score=round(hits[0].score, 3) if hits else 0.0,
            elapsed_ms=elapsed_ms,
            runtime_feature_enabled=runtime_feature_enabled,
        )


class OwnerConsoleManualDiagnosticsRuntime:
    def __init__(
        self,
        *,
        manual_diagnostic_actions_enabled: bool,
        project_doc_rag_probe_enabled: bool,
        project_doc_rag_probe_executor: Callable[[], ProjectDocRagProbeEvidence],
        memory_rag_consistency_enabled: bool = False,
        memory_rag_consistency_executor: (
            Callable[[], MemoryRagConsistencyEvidence] | None
        ) = None,
        main_llm_contract_enabled: bool = False,
        main_llm_contract_executor: (
            Callable[[], MainLlmContractEvidence] | None
        ) = None,
        tts_synthesis_enabled: bool = False,
        tts_synthesis_executor: Callable[[], TtsSynthesisEvidence] | None = None,
        tts_audio_preview_store: TtsAudioPreviewStore | None = None,
        vision_inference_enabled: bool = False,
        vision_inference_executor: (
            Callable[[], VisionInferenceEvidence] | None
        ) = None,
        vision_reference_loader: (
            Callable[[], VisionReferenceAsset] | None
        ) = None,
        cloud_vision_enabled: bool = False,
        cloud_vision_executor: Callable[[], CloudVisionEvidence] | None = None,
        cloud_vision_reference_loader: (
            Callable[[], VisionReferenceAsset] | None
        ) = None,
    ) -> None:
        self._manual_enabled = bool(manual_diagnostic_actions_enabled)
        self._project_probe_enabled = bool(project_doc_rag_probe_enabled)
        self._project_probe_executor = project_doc_rag_probe_executor
        self._memory_consistency_enabled = bool(memory_rag_consistency_enabled)
        self._memory_consistency_executor = memory_rag_consistency_executor
        self._main_llm_contract_enabled = bool(main_llm_contract_enabled)
        self._main_llm_contract_executor = main_llm_contract_executor
        self._tts_synthesis_enabled = bool(tts_synthesis_enabled)
        self._tts_synthesis_executor = tts_synthesis_executor
        self._tts_audio_preview_store = tts_audio_preview_store
        self._vision_inference_enabled = bool(vision_inference_enabled)
        self._vision_inference_executor = vision_inference_executor
        self._vision_reference_loader = vision_reference_loader
        self._cloud_vision_enabled = bool(cloud_vision_enabled)
        self._cloud_vision_executor = cloud_vision_executor
        self._cloud_vision_reference_loader = cloud_vision_reference_loader
        self._state_lock = threading.Lock()
        self._probe_running = False
        self._run_sequence = 0
        self._latest_run: (
            OwnerConsoleManualDiagnosticRun
            | OwnerConsoleMemoryRagConsistencyRun
            | OwnerConsoleMainLlmContractRun
            | OwnerConsoleTtsSynthesisRun
            | OwnerConsoleVisionInferenceRun
            | OwnerConsoleCloudVisionRun
            | None
        ) = None
        self._latest_project_run: OwnerConsoleManualDiagnosticRun | None = None
        self._latest_memory_run: OwnerConsoleMemoryRagConsistencyRun | None = None
        self._latest_main_llm_run: OwnerConsoleMainLlmContractRun | None = None
        self._latest_tts_run: OwnerConsoleTtsSynthesisRun | None = None
        self._latest_tts_technical_result: tuple[str, str, str] | None = None
        self._latest_vision_run: OwnerConsoleVisionInferenceRun | None = None
        self._latest_vision_technical_result: tuple[str, str, str] | None = None
        self._latest_cloud_vision_run: OwnerConsoleCloudVisionRun | None = None
        self._latest_cloud_vision_technical_result: tuple[str, str, str] | None = None

    def build_snapshot(self) -> OwnerConsoleManualDiagnosticsSnapshot:
        with self._state_lock:
            latest_run = self._latest_run
            latest_project_run = self._latest_project_run
            latest_memory_run = self._latest_memory_run
            latest_main_llm_run = self._latest_main_llm_run
            latest_tts_run = self._latest_tts_run
            latest_vision_run = self._latest_vision_run
            latest_cloud_vision_run = self._latest_cloud_vision_run
        project_enabled = self._manual_enabled and self._project_probe_enabled
        memory_enabled = self._manual_enabled and self._memory_consistency_enabled
        main_llm_enabled = self._manual_enabled and self._main_llm_contract_enabled
        tts_enabled = self._manual_enabled and self._tts_synthesis_enabled
        vision_enabled = self._manual_enabled and self._vision_inference_enabled
        cloud_vision_enabled = self._manual_enabled and self._cloud_vision_enabled
        supported_workflows: list[str] = []
        if project_enabled:
            supported_workflows.append(PROJECT_DOC_RAG_PROBE_WORKFLOW)
        if memory_enabled:
            supported_workflows.append(MEMORY_RAG_CONSISTENCY_WORKFLOW)
        if main_llm_enabled:
            supported_workflows.append(MAIN_LLM_CONTRACT_WORKFLOW)
        if tts_enabled:
            supported_workflows.append(TTS_SYNTHESIS_WORKFLOW)
        if vision_enabled:
            supported_workflows.append(VISION_INFERENCE_WORKFLOW)
        if cloud_vision_enabled:
            supported_workflows.append(CLOUD_VISION_WORKFLOW)
        cloud_config = None
        if cloud_vision_enabled and self._cloud_vision_executor is not None:
            cloud_config = getattr(self._cloud_vision_executor, "_config_provider", None)
        workspace_configured = False
        credentials_configured = False
        if callable(cloud_config):
            try:
                config = cloud_config()
            except Exception:
                config = None
            if config is not None:
                workspace_configured = bool(
                    str(getattr(config, "aliyun_bailian_base_url", "") or "").strip()
                )
                credentials_configured = bool(
                    str(getattr(config, "aliyun_bailian_api_key", "") or "").strip()
                )
        return OwnerConsoleManualDiagnosticsSnapshot(
            generated_at=utc_now(),
            manual_diagnostic_actions_enabled=self._manual_enabled,
            project_doc_rag_probe_enabled=project_enabled,
            memory_rag_consistency_enabled=memory_enabled,
            main_llm_contract_enabled=main_llm_enabled,
            tts_synthesis_enabled=tts_enabled,
            vision_inference_enabled=vision_enabled,
            cloud_vision_enabled=cloud_vision_enabled,
            cloud_vision_workspace_configured=workspace_configured,
            cloud_vision_credentials_configured=credentials_configured,
            automatic_diagnostics_enabled=False,
            configuration_write_enabled=False,
            business_data_write_enabled=False,
            supported_workflows=supported_workflows,
            latest_run=latest_run,
            project_doc_rag_latest_run=latest_project_run,
            memory_rag_consistency_latest_run=latest_memory_run,
            main_llm_contract_latest_run=latest_main_llm_run,
            tts_synthesis_latest_run=latest_tts_run,
            vision_inference_latest_run=latest_vision_run,
            cloud_vision_latest_run=latest_cloud_vision_run,
        )

    def run_project_doc_rag_probe(self) -> OwnerConsoleManualDiagnosticRun:
        if not self._manual_enabled or not self._project_probe_enabled:
            raise OwnerConsoleManualDiagnosticDisabled(
                "project document RAG manual probe is disabled"
            )

        started_at = utc_now()
        with self._state_lock:
            if self._probe_running:
                raise OwnerConsoleManualDiagnosticBusy(
                    "another manual diagnostic is already running"
                )
            self._probe_running = True
            self._run_sequence += 1
            run_id = self._run_sequence
            running = OwnerConsoleManualDiagnosticRun(
                run_id=run_id,
                workflow=PROJECT_DOC_RAG_PROBE_WORKFLOW,
                status="running",
                outcome="pending",
                stage="preflight",
                code="manual_probe_running",
                code_label="手动检查正在执行",
                started_at=started_at,
                finished_at="",
                attempt_count=1,
                document_count=0,
                embedding_count=0,
                result_count=0,
                expected_document_matched=False,
                top_score=0.0,
                elapsed_ms=0,
                runtime_feature_enabled=False,
            )
            self._latest_run = running
            self._latest_project_run = running

        try:
            evidence = self._project_probe_executor()
            completed = OwnerConsoleManualDiagnosticRun(
                run_id=run_id,
                workflow=PROJECT_DOC_RAG_PROBE_WORKFLOW,
                status="completed",
                outcome="succeeded",
                stage="result_validation",
                code="project_doc_rag_probe_succeeded",
                code_label="固定项目文档真实检索通过",
                started_at=started_at,
                finished_at=utc_now(),
                attempt_count=1,
                document_count=evidence.document_count,
                embedding_count=evidence.embedding_count,
                result_count=evidence.result_count,
                expected_document_matched=evidence.expected_document_matched,
                top_score=evidence.top_score,
                elapsed_ms=evidence.elapsed_ms,
                runtime_feature_enabled=evidence.runtime_feature_enabled,
            )
        except ProjectDocRagProbeFailure as exc:
            completed = OwnerConsoleManualDiagnosticRun(
                run_id=run_id,
                workflow=PROJECT_DOC_RAG_PROBE_WORKFLOW,
                status="completed",
                outcome="failed",
                stage=exc.stage,
                code=exc.code,
                code_label=exc.code_label,
                started_at=started_at,
                finished_at=utc_now(),
                attempt_count=1,
                document_count=exc.document_count,
                embedding_count=exc.embedding_count,
                result_count=exc.result_count,
                expected_document_matched=exc.expected_document_matched,
                top_score=exc.top_score,
                elapsed_ms=exc.elapsed_ms,
                runtime_feature_enabled=exc.runtime_feature_enabled,
            )
        except Exception:
            completed = OwnerConsoleManualDiagnosticRun(
                run_id=run_id,
                workflow=PROJECT_DOC_RAG_PROBE_WORKFLOW,
                status="completed",
                outcome="failed",
                stage="unexpected",
                code="unexpected_probe_failure",
                code_label="手动检查遇到未归类的运行失败",
                started_at=started_at,
                finished_at=utc_now(),
                attempt_count=1,
                document_count=0,
                embedding_count=0,
                result_count=0,
                expected_document_matched=False,
                top_score=0.0,
                elapsed_ms=0,
                runtime_feature_enabled=False,
            )
        finally:
            with self._state_lock:
                self._probe_running = False

        with self._state_lock:
            self._latest_run = completed
            self._latest_project_run = completed
        return completed

    def run_memory_rag_consistency(
        self,
    ) -> OwnerConsoleMemoryRagConsistencyRun:
        if not self._manual_enabled or not self._memory_consistency_enabled:
            raise OwnerConsoleManualDiagnosticDisabled(
                "MemoryRAG consistency diagnostic is disabled"
            )
        if self._memory_consistency_executor is None:
            raise OwnerConsoleManualDiagnosticDisabled(
                "MemoryRAG consistency diagnostic executor is unavailable"
            )

        started_at = utc_now()
        with self._state_lock:
            if self._probe_running:
                raise OwnerConsoleManualDiagnosticBusy(
                    "another manual diagnostic is already running"
                )
            self._probe_running = True
            self._run_sequence += 1
            run_id = self._run_sequence
            running = OwnerConsoleMemoryRagConsistencyRun(
                run_id=run_id,
                workflow=MEMORY_RAG_CONSISTENCY_WORKFLOW,
                status="running",
                outcome="pending",
                stage="requested",
                code="manual_consistency_running",
                code_label="MemoryRAG 索引一致性检查正在执行",
                started_at=started_at,
                finished_at="",
                attempt_count=1,
                manual_fact_documents=0,
                manual_preference_documents=0,
                session_summary_documents=0,
                active_document_count=0,
                valid_embedding_count=0,
                missing_embedding_count=0,
                missing_manual_fact_embeddings=0,
                missing_manual_preference_embeddings=0,
                missing_session_summary_embeddings=0,
                active_documents_missing_source=0,
                source_records_missing_document=0,
                inactive_document_embedding_count=0,
                runtime_feature_enabled=False,
                elapsed_ms=0,
            )
            self._latest_run = running
            self._latest_memory_run = running

        try:
            evidence = self._memory_consistency_executor()
            source_mismatch_count = (
                evidence.active_documents_missing_source
                + evidence.source_records_missing_document
            )
            if source_mismatch_count > 0:
                outcome = "attention"
                code = "memory_rag_source_mismatch"
                code_label = (
                    f"{source_mismatch_count} 个 MemoryRAG 来源映射需要关注"
                )
            elif evidence.missing_embedding_count > 0:
                outcome = "attention"
                code = "memory_rag_active_embedding_gap"
                code_label = (
                    f"{evidence.missing_embedding_count} 个活动记忆文档"
                    "缺少当前有效向量"
                )
            elif evidence.active_document_count <= 0:
                outcome = "attention"
                code = "memory_rag_index_empty"
                code_label = "MemoryRAG 当前没有活动文档"
            else:
                outcome = "succeeded"
                code = "memory_rag_consistency_succeeded"
                code_label = "MemoryRAG 索引一致性检查通过"

            completed = OwnerConsoleMemoryRagConsistencyRun(
                run_id=run_id,
                workflow=MEMORY_RAG_CONSISTENCY_WORKFLOW,
                status="completed",
                outcome=outcome,
                stage="result_validation",
                code=code,
                code_label=code_label,
                started_at=started_at,
                finished_at=utc_now(),
                attempt_count=1,
                manual_fact_documents=evidence.manual_fact_documents,
                manual_preference_documents=(
                    evidence.manual_preference_documents
                ),
                session_summary_documents=evidence.session_summary_documents,
                active_document_count=evidence.active_document_count,
                valid_embedding_count=evidence.valid_embedding_count,
                missing_embedding_count=evidence.missing_embedding_count,
                missing_manual_fact_embeddings=(
                    evidence.missing_manual_fact_embeddings
                ),
                missing_manual_preference_embeddings=(
                    evidence.missing_manual_preference_embeddings
                ),
                missing_session_summary_embeddings=(
                    evidence.missing_session_summary_embeddings
                ),
                active_documents_missing_source=(
                    evidence.active_documents_missing_source
                ),
                source_records_missing_document=(
                    evidence.source_records_missing_document
                ),
                inactive_document_embedding_count=(
                    evidence.inactive_document_embedding_count
                ),
                runtime_feature_enabled=evidence.runtime_feature_enabled,
                elapsed_ms=evidence.elapsed_ms,
            )
        except Exception:
            completed = OwnerConsoleMemoryRagConsistencyRun(
                run_id=run_id,
                workflow=MEMORY_RAG_CONSISTENCY_WORKFLOW,
                status="completed",
                outcome="failed",
                stage="consistency_read",
                code="memory_rag_consistency_unavailable",
                code_label="无法以只读方式检查 MemoryRAG 索引一致性",
                started_at=started_at,
                finished_at=utc_now(),
                attempt_count=1,
                manual_fact_documents=0,
                manual_preference_documents=0,
                session_summary_documents=0,
                active_document_count=0,
                valid_embedding_count=0,
                missing_embedding_count=0,
                missing_manual_fact_embeddings=0,
                missing_manual_preference_embeddings=0,
                missing_session_summary_embeddings=0,
                active_documents_missing_source=0,
                source_records_missing_document=0,
                inactive_document_embedding_count=0,
                runtime_feature_enabled=False,
                elapsed_ms=0,
            )
        finally:
            with self._state_lock:
                self._probe_running = False

        with self._state_lock:
            self._latest_run = completed
            self._latest_memory_run = completed
        return completed

    def run_main_llm_contract(self) -> OwnerConsoleMainLlmContractRun:
        if not self._manual_enabled or not self._main_llm_contract_enabled:
            raise OwnerConsoleManualDiagnosticDisabled(
                "Main LLM contract diagnostic is disabled"
            )
        if self._main_llm_contract_executor is None:
            raise OwnerConsoleManualDiagnosticDisabled(
                "Main LLM contract diagnostic executor is unavailable"
            )

        started_at = utc_now()
        with self._state_lock:
            if self._probe_running:
                raise OwnerConsoleManualDiagnosticBusy(
                    "another manual diagnostic is already running"
                )
            self._probe_running = True
            self._run_sequence += 1
            run_id = self._run_sequence
            running = OwnerConsoleMainLlmContractRun(
                run_id=run_id,
                workflow=MAIN_LLM_CONTRACT_WORKFLOW,
                status="running",
                outcome="pending",
                stage="requested",
                code="manual_main_llm_contract_running",
                code_label="Main LLM 固定合同正在执行",
                started_at=started_at,
                finished_at="",
                attempt_count=1,
                configured_model="",
                runtime_feature_enabled=False,
                contract_version=MAIN_LLM_CONTRACT_VERSION,
                probe_id=MAIN_LLM_CONTRACT_PROBE_ID,
                contract_valid=False,
                usage_metadata_available=False,
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                tool_calls_present=False,
                elapsed_ms=0,
            )
            self._latest_run = running
            self._latest_main_llm_run = running

        try:
            evidence = self._main_llm_contract_executor()
            if not evidence.contract_valid or evidence.tool_calls_present:
                outcome = "attention"
                code = "main_llm_contract_mismatch"
                code_label = "Main LLM 已响应，但固定回答合同需要关注"
            elif not evidence.usage_metadata_available:
                outcome = "attention"
                code = "main_llm_usage_unavailable"
                code_label = "Main LLM 固定回答通过，但 token 计数不可验证"
            elif evidence.elapsed_ms > MAIN_LLM_CONTRACT_LATENCY_ATTENTION_MS:
                outcome = "attention"
                code = "main_llm_latency_attention"
                code_label = "Main LLM 固定回答通过，但响应延迟需要关注"
            else:
                outcome = "succeeded"
                code = "main_llm_contract_succeeded"
                code_label = "Main LLM 固定问题回答与运行合同通过"
            completed = OwnerConsoleMainLlmContractRun(
                run_id=run_id,
                workflow=MAIN_LLM_CONTRACT_WORKFLOW,
                status="completed",
                outcome=outcome,
                stage="result_validation",
                code=code,
                code_label=code_label,
                started_at=started_at,
                finished_at=utc_now(),
                attempt_count=1,
                configured_model=evidence.configured_model,
                runtime_feature_enabled=evidence.runtime_feature_enabled,
                contract_version=MAIN_LLM_CONTRACT_VERSION,
                probe_id=MAIN_LLM_CONTRACT_PROBE_ID,
                contract_valid=evidence.contract_valid,
                usage_metadata_available=evidence.usage_metadata_available,
                input_tokens=evidence.input_tokens,
                output_tokens=evidence.output_tokens,
                total_tokens=evidence.total_tokens,
                tool_calls_present=evidence.tool_calls_present,
                elapsed_ms=evidence.elapsed_ms,
                llm_called=True,
            )
        except MainLlmContractFailure as exc:
            completed = OwnerConsoleMainLlmContractRun(
                run_id=run_id,
                workflow=MAIN_LLM_CONTRACT_WORKFLOW,
                status="completed",
                outcome="failed",
                stage=exc.stage,
                code=exc.code,
                code_label=exc.code_label,
                started_at=started_at,
                finished_at=utc_now(),
                attempt_count=1,
                configured_model=exc.configured_model,
                runtime_feature_enabled=exc.runtime_feature_enabled,
                contract_version=MAIN_LLM_CONTRACT_VERSION,
                probe_id=MAIN_LLM_CONTRACT_PROBE_ID,
                contract_valid=False,
                usage_metadata_available=False,
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                tool_calls_present=False,
                elapsed_ms=exc.elapsed_ms,
                llm_called=exc.llm_called,
            )
        except Exception:
            completed = OwnerConsoleMainLlmContractRun(
                run_id=run_id,
                workflow=MAIN_LLM_CONTRACT_WORKFLOW,
                status="completed",
                outcome="failed",
                stage="unexpected",
                code="unexpected_probe_failure",
                code_label="Main LLM 固定回答遇到未归类的运行失败",
                started_at=started_at,
                finished_at=utc_now(),
                attempt_count=1,
                configured_model="",
                runtime_feature_enabled=False,
                contract_version=MAIN_LLM_CONTRACT_VERSION,
                probe_id=MAIN_LLM_CONTRACT_PROBE_ID,
                contract_valid=False,
                usage_metadata_available=False,
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                tool_calls_present=False,
                elapsed_ms=0,
            )
        finally:
            with self._state_lock:
                self._probe_running = False

        with self._state_lock:
            self._latest_run = completed
            self._latest_main_llm_run = completed
        return completed

    def run_tts_synthesis(self) -> OwnerConsoleTtsSynthesisRun:
        if not self._manual_enabled or not self._tts_synthesis_enabled:
            raise OwnerConsoleManualDiagnosticDisabled(
                "TTS synthesis diagnostic is disabled"
            )
        if self._tts_synthesis_executor is None:
            raise OwnerConsoleManualDiagnosticDisabled(
                "TTS synthesis diagnostic executor is unavailable"
            )

        started_at = utc_now()
        technical_result: tuple[str, str, str] | None = None
        with self._state_lock:
            if self._probe_running:
                raise OwnerConsoleManualDiagnosticBusy(
                    "another manual diagnostic is already running"
                )
            self._probe_running = True
            if self._tts_audio_preview_store is not None:
                self._tts_audio_preview_store.clear()
            self._latest_tts_technical_result = None
            self._run_sequence += 1
            run_id = self._run_sequence
            running = OwnerConsoleTtsSynthesisRun(
                run_id=run_id,
                workflow=TTS_SYNTHESIS_WORKFLOW,
                status="running",
                outcome="pending",
                stage="requested",
                code="manual_tts_synthesis_running",
                code_label="TTS 固定合成正在执行",
                started_at=started_at,
                finished_at="",
                attempt_count=1,
                runtime_feature_enabled=False,
                service_health_checked=False,
                service_healthy=False,
                model_loaded_before=False,
                runtime_imported_before=False,
                model_load_may_have_occurred=False,
                configured_voice_present=False,
                tts_called=False,
                output_contract_valid=False,
                output_file_created=False,
                output_bytes=0,
                output_duration_ms=0,
                output_retained=False,
                partial_artifact_state="none_before_post",
                health_elapsed_ms=0,
                synthesis_elapsed_ms=0,
                elapsed_ms=0,
                fixed_text=TTS_SYNTHESIS_FIXED_TEXT,
                technical_outcome="pending",
                technical_code="manual_tts_synthesis_running",
                audio_preview_available=False,
                audio_quality_review_required=False,
                audio_quality_reviewed=False,
                audio_quality_accepted=None,
                audio_reviewed_at="",
            )
            self._latest_run = running
            self._latest_tts_run = running

        try:
            evidence = self._tts_synthesis_executor()
            if not evidence.artifact_cleanup_succeeded:
                technical_outcome = "attention"
                technical_code = "tts_artifact_cleanup_incomplete"
                technical_code_label = "TTS 固定合成通过，但本次产物清理不完整"
            elif (
                evidence.service_owned_by_diagnostic
                and not evidence.service_stopped
            ):
                technical_outcome = "attention"
                technical_code = "tts_managed_service_stop_incomplete"
                technical_code_label = "TTS 固定合成通过，但受管理服务未完全停止"
            elif evidence.startup_elapsed_ms > TTS_SYNTHESIS_STARTUP_ATTENTION_MS:
                technical_outcome = "attention"
                technical_code = "tts_startup_latency_attention"
                technical_code_label = "TTS 固定合成通过，但服务启动延迟需要关注"
            elif evidence.synthesis_elapsed_ms > TTS_SYNTHESIS_LATENCY_ATTENTION_MS:
                technical_outcome = "attention"
                technical_code = "tts_synthesis_latency_attention"
                technical_code_label = "TTS 固定合成通过，但模型合成延迟需要关注"
            else:
                technical_outcome = "succeeded"
                technical_code = "tts_managed_lifecycle_succeeded"
                technical_code_label = "TTS 启动、固定合成和清理合同通过"
            technical_result = (
                technical_outcome,
                technical_code,
                technical_code_label,
            )
            preview_available = bool(
                self._tts_audio_preview_store is not None
                and self._tts_audio_preview_store.bind(run_id)
            )
            if preview_available:
                outcome = "attention"
                stage = "owner_audio_review"
                code = "tts_audio_quality_review_required"
                code_label = "TTS 技术合同通过，等待主人试听确认"
            else:
                outcome = "failed"
                stage = "owner_audio_review"
                code = "tts_audio_preview_unavailable"
                code_label = "TTS 技术合同通过，但临时试听不可用"
            completed = OwnerConsoleTtsSynthesisRun(
                run_id=run_id,
                workflow=TTS_SYNTHESIS_WORKFLOW,
                status="completed",
                outcome=outcome,
                stage=stage,
                code=code,
                code_label=code_label,
                started_at=started_at,
                finished_at=utc_now(),
                attempt_count=1,
                runtime_feature_enabled=evidence.runtime_feature_enabled,
                service_health_checked=evidence.service_health_checked,
                service_healthy=evidence.service_healthy,
                model_loaded_before=evidence.model_loaded_before,
                runtime_imported_before=evidence.runtime_imported_before,
                model_load_may_have_occurred=(
                    evidence.model_load_may_have_occurred
                ),
                configured_voice_present=evidence.configured_voice_present,
                tts_called=evidence.tts_called,
                output_contract_valid=evidence.output_contract_valid,
                output_file_created=evidence.output_file_created,
                output_bytes=evidence.output_bytes,
                output_duration_ms=evidence.output_duration_ms,
                output_retained=evidence.output_retained,
                partial_artifact_state=evidence.partial_artifact_state,
                health_elapsed_ms=evidence.health_elapsed_ms,
                synthesis_elapsed_ms=evidence.synthesis_elapsed_ms,
                elapsed_ms=evidence.elapsed_ms,
                fixed_text=TTS_SYNTHESIS_FIXED_TEXT,
                technical_outcome=technical_outcome,
                technical_code=technical_code,
                audio_preview_available=preview_available,
                audio_quality_review_required=preview_available,
                audio_quality_reviewed=False,
                audio_quality_accepted=None,
                audio_reviewed_at="",
                service_preexisting=evidence.service_preexisting,
                service_start_attempted=evidence.service_start_attempted,
                service_started=evidence.service_started,
                service_owned_by_diagnostic=evidence.service_owned_by_diagnostic,
                service_stop_attempted=evidence.service_stop_attempted,
                service_stopped=evidence.service_stopped,
                segment_directory_retained=evidence.segment_directory_retained,
                artifact_cleanup_attempted=evidence.artifact_cleanup_attempted,
                artifact_cleanup_succeeded=evidence.artifact_cleanup_succeeded,
                startup_elapsed_ms=evidence.startup_elapsed_ms,
                cleanup_elapsed_ms=evidence.cleanup_elapsed_ms,
                cleanup_executed=evidence.artifact_cleanup_attempted,
            )
        except TtsSynthesisFailure as exc:
            completed = OwnerConsoleTtsSynthesisRun(
                run_id=run_id,
                workflow=TTS_SYNTHESIS_WORKFLOW,
                status="completed",
                outcome="failed",
                stage=exc.stage,
                code=exc.code,
                code_label=exc.code_label,
                started_at=started_at,
                finished_at=utc_now(),
                attempt_count=1,
                runtime_feature_enabled=exc.runtime_feature_enabled,
                service_health_checked=exc.service_health_checked,
                service_healthy=exc.service_healthy,
                model_loaded_before=exc.model_loaded_before,
                runtime_imported_before=exc.runtime_imported_before,
                model_load_may_have_occurred=(
                    exc.tts_called and not exc.model_loaded_before
                ),
                configured_voice_present=exc.configured_voice_present,
                tts_called=exc.tts_called,
                output_contract_valid=False,
                output_file_created=exc.output_file_created,
                output_bytes=0,
                output_duration_ms=0,
                output_retained=exc.output_retained,
                partial_artifact_state=exc.partial_artifact_state,
                health_elapsed_ms=exc.health_elapsed_ms,
                synthesis_elapsed_ms=exc.synthesis_elapsed_ms,
                elapsed_ms=exc.elapsed_ms,
                fixed_text=TTS_SYNTHESIS_FIXED_TEXT,
                technical_outcome="failed",
                technical_code=exc.code,
                audio_preview_available=False,
                audio_quality_review_required=False,
                audio_quality_reviewed=False,
                audio_quality_accepted=None,
                audio_reviewed_at="",
                service_preexisting=exc.service_preexisting,
                service_start_attempted=exc.service_start_attempted,
                service_started=exc.service_started,
                service_owned_by_diagnostic=exc.service_owned_by_diagnostic,
                service_stop_attempted=exc.service_stop_attempted,
                service_stopped=exc.service_stopped,
                segment_directory_retained=exc.segment_directory_retained,
                artifact_cleanup_attempted=exc.artifact_cleanup_attempted,
                artifact_cleanup_succeeded=exc.artifact_cleanup_succeeded,
                startup_elapsed_ms=exc.startup_elapsed_ms,
                cleanup_elapsed_ms=exc.cleanup_elapsed_ms,
                cleanup_executed=exc.artifact_cleanup_attempted,
            )
        except Exception:
            completed = OwnerConsoleTtsSynthesisRun(
                run_id=run_id,
                workflow=TTS_SYNTHESIS_WORKFLOW,
                status="completed",
                outcome="failed",
                stage="unexpected",
                code="tts_unexpected_probe_failure",
                code_label="TTS 固定合成遇到未归类的运行失败",
                started_at=started_at,
                finished_at=utc_now(),
                attempt_count=1,
                runtime_feature_enabled=False,
                service_health_checked=False,
                service_healthy=False,
                model_loaded_before=False,
                runtime_imported_before=False,
                model_load_may_have_occurred=False,
                configured_voice_present=False,
                tts_called=False,
                output_contract_valid=False,
                output_file_created=False,
                output_bytes=0,
                output_duration_ms=0,
                output_retained=False,
                partial_artifact_state="none_before_post",
                health_elapsed_ms=0,
                synthesis_elapsed_ms=0,
                elapsed_ms=0,
                fixed_text=TTS_SYNTHESIS_FIXED_TEXT,
                technical_outcome="failed",
                technical_code="tts_unexpected_probe_failure",
                audio_preview_available=False,
                audio_quality_review_required=False,
                audio_quality_reviewed=False,
                audio_quality_accepted=None,
                audio_reviewed_at="",
            )
        finally:
            with self._state_lock:
                self._probe_running = False

        with self._state_lock:
            self._latest_run = completed
            self._latest_tts_run = completed
            self._latest_tts_technical_result = (
                technical_result
                if completed.audio_quality_review_required
                else None
            )
        return completed

    def read_tts_audio_preview(self, run_id: int) -> bytes:
        if not self._manual_enabled or not self._tts_synthesis_enabled:
            raise OwnerConsoleManualDiagnosticDisabled(
                "TTS synthesis diagnostic is disabled"
            )
        with self._state_lock:
            if self._probe_running:
                raise OwnerConsoleManualDiagnosticBusy(
                    "another manual diagnostic is already running"
                )
            latest = self._latest_tts_run
            if (
                self._tts_audio_preview_store is None
                or latest is None
                or latest.run_id != run_id
                or not latest.audio_preview_available
                or not latest.audio_quality_review_required
            ):
                raise OwnerConsoleTtsAudioReviewUnavailable(
                    "TTS audio preview is unavailable"
                )
            content = self._tts_audio_preview_store.read(run_id)
            if content is None:
                raise OwnerConsoleTtsAudioReviewUnavailable(
                    "TTS audio preview is unavailable"
                )
            return content

    def review_tts_audio_quality(
        self,
        run_id: int,
        *,
        accepted: bool,
    ) -> OwnerConsoleTtsSynthesisRun:
        if not self._manual_enabled or not self._tts_synthesis_enabled:
            raise OwnerConsoleManualDiagnosticDisabled(
                "TTS synthesis diagnostic is disabled"
            )
        if type(accepted) is not bool:
            raise OwnerConsoleTtsAudioReviewUnavailable(
                "TTS audio review decision is invalid"
            )
        with self._state_lock:
            if self._probe_running:
                raise OwnerConsoleManualDiagnosticBusy(
                    "another manual diagnostic is already running"
                )
            latest = self._latest_tts_run
            technical = self._latest_tts_technical_result
            if (
                self._tts_audio_preview_store is None
                or latest is None
                or latest.run_id != run_id
                or not latest.audio_preview_available
                or not latest.audio_quality_review_required
                or technical is None
                or self._tts_audio_preview_store.read(run_id) is None
            ):
                raise OwnerConsoleTtsAudioReviewUnavailable(
                    "TTS audio review is unavailable"
                )
            reviewed_at = utc_now()
            if accepted:
                outcome, code, code_label = technical
                stage = "result_validation"
            else:
                outcome = "failed"
                stage = "owner_audio_review"
                code = "tts_audio_quality_rejected"
                code_label = "TTS 技术合同通过，但主人听检不合格"
            completed = replace(
                latest,
                outcome=outcome,
                stage=stage,
                code=code,
                code_label=code_label,
                audio_preview_available=False,
                audio_quality_review_required=False,
                audio_quality_reviewed=True,
                audio_quality_accepted=accepted,
                audio_reviewed_at=reviewed_at,
                audio_review_action_executed=True,
            )
            self._tts_audio_preview_store.clear(run_id)
            self._latest_tts_technical_result = None
            self._latest_run = completed
            self._latest_tts_run = completed
            return completed

    def run_vision_inference(self) -> OwnerConsoleVisionInferenceRun:
        if not self._manual_enabled or not self._vision_inference_enabled:
            raise OwnerConsoleManualDiagnosticDisabled(
                "vision inference diagnostic is disabled"
            )
        if self._vision_inference_executor is None:
            raise OwnerConsoleManualDiagnosticDisabled(
                "vision inference diagnostic executor is unavailable"
            )

        started_at = utc_now()
        with self._state_lock:
            if self._probe_running:
                raise OwnerConsoleManualDiagnosticBusy(
                    "another manual diagnostic is already running"
                )
            self._probe_running = True
            self._latest_vision_technical_result = None
            self._run_sequence += 1
            run_id = self._run_sequence

            def build_run(
                *,
                status: str,
                outcome: str,
                stage: str,
                code: str,
                code_label: str,
                source: object | None = None,
            ) -> OwnerConsoleVisionInferenceRun:
                def value(name: str, default: object) -> object:
                    return getattr(source, name, default)

                return OwnerConsoleVisionInferenceRun(
                    run_id=run_id,
                    workflow=VISION_INFERENCE_WORKFLOW,
                    status=status,
                    outcome=outcome,
                    stage=stage,
                    code=code,
                    code_label=code_label,
                    started_at=started_at,
                    finished_at="" if status == "running" else utc_now(),
                    attempt_count=1,
                    configured_model=str(value("configured_model", "")),
                    runtime_feature_enabled=bool(
                        value("runtime_feature_enabled", False)
                    ),
                    fixed_image_contract=str(
                        value(
                            "fixed_image_contract",
                            VISION_FIXED_CONTRACT_VERSION,
                        )
                    ),
                    fixed_image_bytes=int(value("fixed_image_bytes", 0)),
                    fixed_image_contract_valid=bool(
                        value("fixed_image_contract_valid", False)
                    ),
                    reference_sticker_id=str(
                        value(
                            "reference_sticker_id",
                            VISION_REFERENCE_STICKER_ID,
                        )
                    ),
                    registered_reference_asset_read=bool(
                        value("registered_reference_asset_read", False)
                    ),
                    expected_answer_disclosed_in_prompt=bool(
                        value("expected_answer_disclosed_in_prompt", False)
                    ),
                    service_tags_checked=bool(
                        value("service_tags_checked", False)
                    ),
                    service_healthy=bool(value("service_healthy", False)),
                    service_preexisting=bool(
                        value("service_preexisting", False)
                    ),
                    service_start_attempted=bool(
                        value("service_start_attempted", False)
                    ),
                    service_started=bool(value("service_started", False)),
                    service_owned_by_diagnostic=bool(
                        value("service_owned_by_diagnostic", False)
                    ),
                    service_ownership_basis=str(
                        value("service_ownership_basis", "none")
                    ),
                    service_stop_attempted=bool(
                        value("service_stop_attempted", False)
                    ),
                    service_stopped=bool(value("service_stopped", False)),
                    model_available=bool(value("model_available", False)),
                    model_residency_checked=bool(
                        value("model_residency_checked", False)
                    ),
                    model_loaded_before=bool(
                        value("model_loaded_before", False)
                    ),
                    keep_alive_zero_used=bool(
                        value("keep_alive_zero_used", False)
                    ),
                    vision_called=bool(value("vision_called", False)),
                    response_contract_valid=bool(
                        value("response_contract_valid", False)
                    ),
                    response_mode=str(
                        value("response_mode", "natural_text")
                    ),
                    structured_output_requested=bool(
                        value("structured_output_requested", False)
                    ),
                    semantic_contract_automatically_validated=bool(
                        value(
                            "semantic_contract_automatically_validated",
                            False,
                        )
                    ),
                    owner_visual_judgment_required=bool(
                        value("owner_visual_judgment_required", True)
                    ),
                    response_preview=str(value("response_preview", "")),
                    response_description=str(
                        value("response_description", "")
                    ),
                    response_content_exposed_to_owner=bool(
                        value("response_content_exposed_to_owner", False)
                    ),
                    usage_metadata_available=bool(
                        value("usage_metadata_available", False)
                    ),
                    input_tokens=value("input_tokens", None),
                    output_tokens=value("output_tokens", None),
                    total_tokens=value("total_tokens", None),
                    model_cleanup_required=bool(
                        value("model_cleanup_required", False)
                    ),
                    model_cleanup_verified=bool(
                        value("model_cleanup_verified", False)
                    ),
                    model_cleanup_poll_count=int(
                        value("model_cleanup_poll_count", 0)
                    ),
                    startup_elapsed_ms=int(
                        value("startup_elapsed_ms", 0)
                    ),
                    discovery_elapsed_ms=int(
                        value("discovery_elapsed_ms", 0)
                    ),
                    residency_elapsed_ms=int(
                        value("residency_elapsed_ms", 0)
                    ),
                    inference_elapsed_ms=int(
                        value("inference_elapsed_ms", 0)
                    ),
                    cleanup_elapsed_ms=int(
                        value("cleanup_elapsed_ms", 0)
                    ),
                    elapsed_ms=int(value("elapsed_ms", 0)),
                )

            running = build_run(
                status="running",
                outcome="pending",
                stage="requested",
                code="manual_vision_inference_running",
                code_label="视觉固定图片诊断正在执行",
            )
            self._latest_run = running
            self._latest_vision_run = running

        technical_result: tuple[str, str, str] | None = None
        try:
            evidence = self._vision_inference_executor()
            if not evidence.fixed_image_contract_valid:
                outcome = "failed"
                code = "vision_fixed_image_contract_invalid"
                code_label = "视觉固定图片合同无效"
            elif not evidence.service_healthy:
                outcome = "failed"
                code = "vision_service_contract_invalid"
                code_label = "Ollama 服务状态无法证明可用"
            elif not evidence.service_preexisting and (
                not evidence.service_started
                or not evidence.service_owned_by_diagnostic
            ):
                outcome = "failed"
                code = "vision_service_ownership_ambiguous"
                code_label = "视觉诊断无法证明新服务所有权"
            elif not evidence.model_available or not evidence.model_residency_checked:
                outcome = "failed"
                code = "vision_model_residency_unavailable"
                code_label = "视觉模型可用性或驻留状态无法验证"
            elif not evidence.vision_called or not evidence.response_contract_valid:
                outcome = "failed"
                code = "vision_response_contract_mismatch"
                code_label = "视觉回答没有满足自然文本基础合同"
            elif (
                evidence.model_cleanup_required
                and not evidence.model_cleanup_verified
            ):
                outcome = "attention"
                code = "vision_model_cleanup_incomplete"
                code_label = "视觉基础回复合同通过，但本次模型资源收口不完整"
            elif (
                evidence.service_owned_by_diagnostic
                and not evidence.service_stopped
            ):
                outcome = "attention"
                code = "vision_managed_service_stop_incomplete"
                code_label = "视觉基础回复合同通过，但受管理服务未完全停止"
            elif not evidence.usage_metadata_available:
                outcome = "attention"
                code = "vision_usage_metadata_unavailable"
                code_label = "视觉基础回复合同通过，但 token 计数不可验证"
            elif evidence.startup_elapsed_ms > VISION_STARTUP_ATTENTION_MS:
                outcome = "attention"
                code = "vision_startup_latency_attention"
                code_label = "视觉基础回复合同通过，但服务启动延迟需要关注"
            elif (
                evidence.inference_elapsed_ms
                > VISION_INFERENCE_LATENCY_ATTENTION_MS
            ):
                outcome = "attention"
                code = "vision_inference_latency_attention"
                code_label = "视觉基础回复合同通过，但模型推理延迟需要关注"
            else:
                outcome = "succeeded"
                code = "vision_managed_lifecycle_succeeded"
                code_label = "视觉服务、自然回复和资源收口技术合同通过"
            technical_result = (outcome, code, code_label)
            if outcome == "failed":
                stage = "result_validation"
                review_required = False
            elif evidence.response_preview and evidence.response_description:
                outcome = "attention"
                stage = "owner_visual_review"
                code = "vision_response_quality_review_required"
                code_label = "视觉技术合同通过，等待主人检查实际图片描述"
                review_required = True
            else:
                outcome = "failed"
                stage = "owner_visual_review"
                code = "vision_response_preview_unavailable"
                code_label = "视觉技术合同通过，但实际回复预览不可用"
                review_required = False
            completed = build_run(
                status="completed",
                outcome=outcome,
                stage=stage,
                code=code,
                code_label=code_label,
                source=evidence,
            )
            completed = replace(
                completed,
                technical_outcome=technical_result[0],
                technical_code=technical_result[1],
                reference_preview_available=True,
                visual_quality_review_required=review_required,
            )
        except VisionInferenceFailure as exc:
            completed = build_run(
                status="completed",
                outcome="failed",
                stage=exc.stage,
                code=exc.code,
                code_label=exc.code_label,
                source=exc,
            )
            completed = replace(
                completed,
                technical_outcome="failed",
                technical_code=exc.code,
                reference_preview_available=bool(
                    getattr(exc, "registered_reference_asset_read", False)
                ),
            )
        except Exception:
            completed = build_run(
                status="completed",
                outcome="failed",
                stage="unexpected",
                code="vision_unexpected_probe_failure",
                code_label="视觉固定诊断遇到未归类的运行失败",
            )
        finally:
            with self._state_lock:
                self._probe_running = False

        with self._state_lock:
            self._latest_run = completed
            self._latest_vision_run = completed
            self._latest_vision_technical_result = (
                technical_result
                if completed.visual_quality_review_required
                else None
            )
        return completed

    def read_vision_reference_preview(self) -> bytes:
        if not self._manual_enabled or not self._vision_inference_enabled:
            raise OwnerConsoleManualDiagnosticDisabled(
                "vision inference diagnostic is disabled"
            )
        with self._state_lock:
            if self._probe_running:
                raise OwnerConsoleManualDiagnosticBusy(
                    "another manual diagnostic is already running"
                )
            latest = self._latest_vision_run
            if (
                self._vision_reference_loader is None
                or latest is None
                or not latest.reference_preview_available
            ):
                raise OwnerConsoleVisionReviewUnavailable(
                    "vision reference preview is unavailable"
                )
        try:
            asset = self._vision_reference_loader()
        except Exception as exc:
            raise OwnerConsoleVisionReviewUnavailable(
                "vision reference preview is unavailable"
            ) from exc
        return asset.content

    def review_vision_response_quality(
        self,
        run_id: int,
        *,
        accepted: bool,
    ) -> OwnerConsoleVisionInferenceRun:
        if not self._manual_enabled or not self._vision_inference_enabled:
            raise OwnerConsoleManualDiagnosticDisabled(
                "vision inference diagnostic is disabled"
            )
        if type(accepted) is not bool:
            raise OwnerConsoleVisionReviewUnavailable(
                "vision response review decision is invalid"
            )
        with self._state_lock:
            if self._probe_running:
                raise OwnerConsoleManualDiagnosticBusy(
                    "another manual diagnostic is already running"
                )
            latest = self._latest_vision_run
            technical = self._latest_vision_technical_result
            if (
                latest is None
                or latest.run_id != run_id
                or not latest.visual_quality_review_required
                or not latest.reference_preview_available
                or not latest.response_preview
                or not latest.response_description
                or technical is None
            ):
                raise OwnerConsoleVisionReviewUnavailable(
                    "vision response review is unavailable"
                )
            reviewed_at = utc_now()
            if accepted:
                outcome, code, code_label = technical
                stage = "result_validation"
            else:
                outcome = "failed"
                stage = "owner_visual_review"
                code = "vision_response_quality_rejected"
                code_label = "视觉技术合同通过，但主人检查实际描述不合格"
            completed = replace(
                latest,
                outcome=outcome,
                stage=stage,
                code=code,
                code_label=code_label,
                visual_quality_review_required=False,
                visual_quality_reviewed=True,
                visual_quality_accepted=accepted,
                visual_reviewed_at=reviewed_at,
                visual_review_action_executed=True,
                reference_image_exposed_to_owner=True,
            )
            self._latest_vision_technical_result = None
            self._latest_run = completed
            self._latest_vision_run = completed
            return completed

    def run_cloud_vision_fixed_description(self) -> OwnerConsoleCloudVisionRun:
        if not self._manual_enabled or not self._cloud_vision_enabled:
            raise OwnerConsoleManualDiagnosticDisabled(
                "cloud vision diagnostic is disabled"
            )
        if self._cloud_vision_executor is None:
            raise OwnerConsoleManualDiagnosticDisabled(
                "cloud vision diagnostic executor is unavailable"
            )

        started_at = utc_now()
        with self._state_lock:
            if self._probe_running:
                raise OwnerConsoleManualDiagnosticBusy(
                    "another manual diagnostic is already running"
                )
            self._probe_running = True
            self._latest_cloud_vision_technical_result = None
            self._run_sequence += 1
            run_id = self._run_sequence

            def build_run(
                *,
                status: str,
                outcome: str,
                stage: str,
                code: str,
                code_label: str,
                source: object | None = None,
            ) -> OwnerConsoleCloudVisionRun:
                def value(name: str, default: object) -> object:
                    return getattr(source, name, default)

                return OwnerConsoleCloudVisionRun(
                    run_id=run_id,
                    workflow=CLOUD_VISION_WORKFLOW,
                    status=status,
                    outcome=outcome,
                    stage=stage,
                    code=code,
                    code_label=code_label,
                    started_at=started_at,
                    finished_at="" if status == "running" else utc_now(),
                    attempt_count=1,
                    provider=str(value("provider", "aliyun_bailian")),
                    region=str(value("region", "cn-beijing")),
                    configured_model=str(value("configured_model", "qwen3.7-flash")),
                    returned_model=str(value("returned_model", "")),
                    runtime_feature_enabled=bool(
                        value("runtime_feature_enabled", False)
                    ),
                    endpoint_contract_valid=bool(
                        value("endpoint_contract_valid", False)
                    ),
                    workspace_configured=bool(
                        value("workspace_configured", False)
                    ),
                    credentials_configured=bool(
                        value("credentials_configured", False)
                    ),
                    fixed_image_contract=str(
                        value("fixed_image_contract", VISION_FIXED_CONTRACT_VERSION)
                    ),
                    fixed_image_bytes=int(value("fixed_image_bytes", 0)),
                    fixed_image_contract_valid=bool(
                        value("fixed_image_contract_valid", False)
                    ),
                    reference_sticker_id=str(
                        value("reference_sticker_id", VISION_REFERENCE_STICKER_ID)
                    ),
                    registered_reference_asset_read=bool(
                        value("registered_reference_asset_read", False)
                    ),
                    external_image_upload_planned=bool(
                        value("external_image_upload_planned", True)
                    ),
                    external_image_upload_executed=bool(
                        value("external_image_upload_executed", False)
                    ),
                    provider_side_persistence_controlled_by_app=bool(
                        value(
                            "provider_side_persistence_controlled_by_app",
                            False,
                        )
                    ),
                    cloud_vision_called=bool(value("cloud_vision_called", False)),
                    request_count=int(value("request_count", 0)),
                    client_automatic_retry=bool(
                        value("client_automatic_retry", False)
                    ),
                    tool_definitions_sent=bool(
                        value("tool_definitions_sent", False)
                    ),
                    thinking_enabled=bool(value("thinking_enabled", False)),
                    response_mode=str(value("response_mode", "natural_text")),
                    structured_output_requested=bool(
                        value("structured_output_requested", False)
                    ),
                    semantic_contract_automatically_validated=bool(
                        value("semantic_contract_automatically_validated", False)
                    ),
                    owner_visual_judgment_required=bool(
                        value("owner_visual_judgment_required", True)
                    ),
                    response_contract_valid=bool(
                        value("response_contract_valid", False)
                    ),
                    response_preview=str(value("response_preview", "")),
                    response_description=str(value("response_description", "")),
                    response_cleanup_applied=bool(
                        value("response_cleanup_applied", False)
                    ),
                    input_tokens=int(value("input_tokens", 0)),
                    output_tokens=int(value("output_tokens", 0)),
                    total_tokens=int(value("total_tokens", 0)),
                    request_elapsed_ms=int(value("request_elapsed_ms", 0)),
                )

            running = build_run(
                status="running",
                outcome="pending",
                stage="requested",
                code="manual_cloud_vision_running",
                code_label="阿里云百炼固定视觉诊断正在执行",
            )
            self._latest_run = running
            self._latest_cloud_vision_run = running

        technical_result: tuple[str, str, str] | None = None
        try:
            evidence = self._cloud_vision_executor()
            if not evidence.response_contract_valid or not evidence.cloud_vision_called:
                technical_result = (
                    "failed",
                    "cloud_vision_response_contract_mismatch",
                    "百炼视觉响应没有满足固定基础合同",
                )
            elif evidence.request_elapsed_ms > CLOUD_VISION_LATENCY_ATTENTION_MS:
                technical_result = (
                    "attention",
                    "cloud_vision_latency_attention",
                    "百炼视觉基础合同通过，但请求延迟需要关注",
                )
            else:
                technical_result = (
                    "succeeded",
                    "cloud_vision_fixed_description_succeeded",
                    "百炼视觉请求与基础回复合同通过",
                )
            technical_outcome, technical_code, technical_label = technical_result
            if technical_outcome == "failed":
                completed = build_run(
                    status="completed",
                    outcome=technical_outcome,
                    stage="result_validation",
                    code=technical_code,
                    code_label=technical_label,
                    source=evidence,
                )
                review_required = False
            elif evidence.response_preview and evidence.response_description:
                completed = build_run(
                    status="completed",
                    outcome="attention",
                    stage="owner_visual_review",
                    code="cloud_vision_response_quality_review_required",
                    code_label="百炼视觉基础合同通过，等待主人检查图片描述",
                    source=evidence,
                )
                review_required = True
            else:
                completed = build_run(
                    status="completed",
                    outcome="failed",
                    stage="owner_visual_review",
                    code="cloud_vision_response_preview_unavailable",
                    code_label="百炼视觉基础合同通过，但回复预览不可用",
                    source=evidence,
                )
                review_required = False
            completed = replace(
                completed,
                technical_outcome=technical_outcome,
                technical_code=technical_code,
                reference_preview_available=True,
                visual_quality_review_required=review_required,
            )
        except CloudVisionFailure as exc:
            completed = build_run(
                status="completed",
                outcome="failed",
                stage=exc.stage,
                code=exc.code,
                code_label=exc.code_label,
                source=exc,
            )
            completed = replace(
                completed,
                technical_outcome="failed",
                technical_code=exc.code,
                reference_preview_available=bool(
                    getattr(exc, "registered_reference_asset_read", False)
                ),
            )
        except Exception:
            completed = build_run(
                status="completed",
                outcome="failed",
                stage="unexpected",
                code="cloud_vision_unexpected_failure",
                code_label="阿里云百炼固定视觉诊断遇到未归类失败",
            )
        finally:
            with self._state_lock:
                self._probe_running = False

        with self._state_lock:
            self._latest_run = completed
            self._latest_cloud_vision_run = completed
            self._latest_cloud_vision_technical_result = (
                technical_result
                if completed.visual_quality_review_required
                else None
            )
        return completed

    def read_cloud_vision_reference_preview(self) -> bytes:
        if not self._manual_enabled or not self._cloud_vision_enabled:
            raise OwnerConsoleManualDiagnosticDisabled(
                "cloud vision diagnostic is disabled"
            )
        with self._state_lock:
            if self._probe_running:
                raise OwnerConsoleManualDiagnosticBusy(
                    "another manual diagnostic is already running"
                )
            latest = self._latest_cloud_vision_run
            if (
                self._cloud_vision_reference_loader is None
                or latest is None
                or not latest.reference_preview_available
            ):
                raise OwnerConsoleCloudVisionReviewUnavailable(
                    "cloud vision reference preview is unavailable"
                )
        try:
            asset = self._cloud_vision_reference_loader()
        except Exception as exc:
            raise OwnerConsoleCloudVisionReviewUnavailable(
                "cloud vision reference preview is unavailable"
            ) from exc
        return asset.content

    def review_cloud_vision_response_quality(
        self,
        run_id: int,
        *,
        accepted: bool,
    ) -> OwnerConsoleCloudVisionRun:
        if not self._manual_enabled or not self._cloud_vision_enabled:
            raise OwnerConsoleManualDiagnosticDisabled(
                "cloud vision diagnostic is disabled"
            )
        if type(accepted) is not bool:
            raise OwnerConsoleCloudVisionReviewUnavailable(
                "cloud vision response review decision is invalid"
            )
        with self._state_lock:
            if self._probe_running:
                raise OwnerConsoleManualDiagnosticBusy(
                    "another manual diagnostic is already running"
                )
            latest = self._latest_cloud_vision_run
            technical = self._latest_cloud_vision_technical_result
            if (
                latest is None
                or latest.run_id != run_id
                or not latest.visual_quality_review_required
                or not latest.reference_preview_available
                or not latest.response_preview
                or not latest.response_description
                or technical is None
            ):
                raise OwnerConsoleCloudVisionReviewUnavailable(
                    "cloud vision response review is unavailable"
                )
            reviewed_at = utc_now()
            if accepted:
                outcome, code, code_label = technical
                stage = "result_validation"
            else:
                outcome = "failed"
                stage = "owner_visual_review"
                code = "cloud_vision_response_quality_rejected"
                code_label = "百炼视觉技术合同通过，但主人检查描述不合格"
            completed = replace(
                latest,
                outcome=outcome,
                stage=stage,
                code=code,
                code_label=code_label,
                visual_quality_review_required=False,
                visual_quality_reviewed=True,
                visual_quality_accepted=accepted,
                visual_reviewed_at=reviewed_at,
                visual_review_action_executed=True,
            )
            self._latest_cloud_vision_technical_result = None
            self._latest_run = completed
            self._latest_cloud_vision_run = completed
            return completed


def create_owner_console_manual_diagnostics_runtime(
    *,
    config_provider: Callable[[], Any],
    manual_diagnostic_actions_enabled: bool,
    project_doc_rag_probe_enabled: bool,
    memory_rag_consistency_enabled: bool = False,
    main_llm_contract_enabled: bool = False,
    tts_synthesis_enabled: bool = False,
    vision_inference_enabled: bool = False,
    cloud_vision_enabled: bool = False,
) -> OwnerConsoleManualDiagnosticsRuntime:
    tts_audio_preview_store = TtsAudioPreviewStore()
    return OwnerConsoleManualDiagnosticsRuntime(
        manual_diagnostic_actions_enabled=manual_diagnostic_actions_enabled,
        project_doc_rag_probe_enabled=project_doc_rag_probe_enabled,
        project_doc_rag_probe_executor=ProjectDocRagProbeExecutor(
            config_provider=config_provider,
        ),
        memory_rag_consistency_enabled=memory_rag_consistency_enabled,
        memory_rag_consistency_executor=MemoryRagConsistencyExecutor(
            config_provider=config_provider,
        ),
        main_llm_contract_enabled=main_llm_contract_enabled,
        main_llm_contract_executor=MainLlmContractExecutor(
            config_provider=config_provider,
        ),
        tts_synthesis_enabled=tts_synthesis_enabled,
        tts_synthesis_executor=TtsSynthesisExecutor(
            config_provider=config_provider,
            preview_store=tts_audio_preview_store,
        ),
        tts_audio_preview_store=tts_audio_preview_store,
        vision_inference_enabled=vision_inference_enabled,
        vision_inference_executor=VisionInferenceExecutor(
            config_provider=config_provider,
        ),
        vision_reference_loader=_load_registered_reference_asset,
        cloud_vision_enabled=cloud_vision_enabled,
        cloud_vision_executor=CloudVisionExecutor(
            config_provider=config_provider,
        ),
        cloud_vision_reference_loader=_load_registered_reference_asset,
    )
