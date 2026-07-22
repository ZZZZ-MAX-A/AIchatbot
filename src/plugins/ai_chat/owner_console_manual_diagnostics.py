from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
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
    automatic_diagnostics_enabled: bool
    configuration_write_enabled: bool
    business_data_write_enabled: bool
    supported_workflows: list[str]
    latest_run: (
        OwnerConsoleManualDiagnosticRun
        | OwnerConsoleMemoryRagConsistencyRun
        | OwnerConsoleMainLlmContractRun
        | None
    )
    project_doc_rag_latest_run: OwnerConsoleManualDiagnosticRun | None
    memory_rag_consistency_latest_run: OwnerConsoleMemoryRagConsistencyRun | None
    main_llm_contract_latest_run: OwnerConsoleMainLlmContractRun | None


class OwnerConsoleManualDiagnosticDisabled(RuntimeError):
    pass


class OwnerConsoleManualDiagnosticBusy(RuntimeError):
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
    ) -> None:
        self._manual_enabled = bool(manual_diagnostic_actions_enabled)
        self._project_probe_enabled = bool(project_doc_rag_probe_enabled)
        self._project_probe_executor = project_doc_rag_probe_executor
        self._memory_consistency_enabled = bool(memory_rag_consistency_enabled)
        self._memory_consistency_executor = memory_rag_consistency_executor
        self._main_llm_contract_enabled = bool(main_llm_contract_enabled)
        self._main_llm_contract_executor = main_llm_contract_executor
        self._state_lock = threading.Lock()
        self._probe_running = False
        self._run_sequence = 0
        self._latest_run: (
            OwnerConsoleManualDiagnosticRun
            | OwnerConsoleMemoryRagConsistencyRun
            | OwnerConsoleMainLlmContractRun
            | None
        ) = None
        self._latest_project_run: OwnerConsoleManualDiagnosticRun | None = None
        self._latest_memory_run: OwnerConsoleMemoryRagConsistencyRun | None = None
        self._latest_main_llm_run: OwnerConsoleMainLlmContractRun | None = None

    def build_snapshot(self) -> OwnerConsoleManualDiagnosticsSnapshot:
        with self._state_lock:
            latest_run = self._latest_run
            latest_project_run = self._latest_project_run
            latest_memory_run = self._latest_memory_run
            latest_main_llm_run = self._latest_main_llm_run
        project_enabled = self._manual_enabled and self._project_probe_enabled
        memory_enabled = self._manual_enabled and self._memory_consistency_enabled
        main_llm_enabled = self._manual_enabled and self._main_llm_contract_enabled
        supported_workflows: list[str] = []
        if project_enabled:
            supported_workflows.append(PROJECT_DOC_RAG_PROBE_WORKFLOW)
        if memory_enabled:
            supported_workflows.append(MEMORY_RAG_CONSISTENCY_WORKFLOW)
        if main_llm_enabled:
            supported_workflows.append(MAIN_LLM_CONTRACT_WORKFLOW)
        return OwnerConsoleManualDiagnosticsSnapshot(
            generated_at=utc_now(),
            manual_diagnostic_actions_enabled=self._manual_enabled,
            project_doc_rag_probe_enabled=project_enabled,
            memory_rag_consistency_enabled=memory_enabled,
            main_llm_contract_enabled=main_llm_enabled,
            automatic_diagnostics_enabled=False,
            configuration_write_enabled=False,
            business_data_write_enabled=False,
            supported_workflows=supported_workflows,
            latest_run=latest_run,
            project_doc_rag_latest_run=latest_project_run,
            memory_rag_consistency_latest_run=latest_memory_run,
            main_llm_contract_latest_run=latest_main_llm_run,
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


def create_owner_console_manual_diagnostics_runtime(
    *,
    config_provider: Callable[[], Any],
    manual_diagnostic_actions_enabled: bool,
    project_doc_rag_probe_enabled: bool,
    memory_rag_consistency_enabled: bool = False,
    main_llm_contract_enabled: bool = False,
) -> OwnerConsoleManualDiagnosticsRuntime:
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
    )
