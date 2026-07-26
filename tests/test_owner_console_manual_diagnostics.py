from __future__ import annotations

import io
import json
import re
import sys
import tempfile
import threading
import unittest
import wave
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from pure_ai_chat_loader import (
    AI_CHAT_ROOT,
    ensure_ai_chat_packages,
    load_legacy_memory_modules,
    load_module,
)


class OwnerConsoleManualDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.memory_modules = load_legacy_memory_modules()
        cls.database = cls.memory_modules["database"]
        cls.fastapi = load_module(
            "src.plugins.ai_chat.owner_console_fastapi_app",
            AI_CHAT_ROOT / "owner_console_fastapi_app.py",
        )
        cls.manual = sys.modules[
            "src.plugins.ai_chat.owner_console_manual_diagnostics"
        ]

    def memory_evidence(self, **overrides):
        values = {
            "manual_fact_documents": 10,
            "manual_preference_documents": 3,
            "session_summary_documents": 24,
            "active_document_count": 37,
            "valid_embedding_count": 35,
            "missing_embedding_count": 2,
            "missing_manual_fact_embeddings": 2,
            "missing_manual_preference_embeddings": 0,
            "missing_session_summary_embeddings": 0,
            "active_documents_missing_source": 0,
            "source_records_missing_document": 0,
            "inactive_document_embedding_count": 5,
            "runtime_feature_enabled": False,
            "elapsed_ms": 4,
        }
        values.update(overrides)
        return self.manual.MemoryRagConsistencyEvidence(**values)

    def main_llm_evidence(self, **overrides):
        values = {
            "configured_model": "main-test-model",
            "runtime_feature_enabled": True,
            "contract_valid": True,
            "usage_metadata_available": True,
            "input_tokens": 51,
            "output_tokens": 42,
            "total_tokens": 93,
            "tool_calls_present": False,
            "elapsed_ms": 125,
        }
        values.update(overrides)
        return self.manual.MainLlmContractEvidence(**values)

    def tts_evidence(self, **overrides):
        values = {
            "runtime_feature_enabled": True,
            "service_health_checked": True,
            "service_healthy": True,
            "service_preexisting": True,
            "service_start_attempted": False,
            "service_started": False,
            "service_owned_by_diagnostic": False,
            "service_stop_attempted": False,
            "service_stopped": False,
            "model_loaded_before": False,
            "runtime_imported_before": False,
            "model_load_may_have_occurred": True,
            "configured_voice_present": True,
            "tts_called": True,
            "output_contract_valid": True,
            "output_file_created": True,
            "output_bytes": 32044,
            "output_duration_ms": 1000,
            "output_retained": False,
            "segment_directory_retained": False,
            "artifact_cleanup_attempted": True,
            "artifact_cleanup_succeeded": True,
            "partial_artifact_state": "artifacts_removed",
            "startup_elapsed_ms": 0,
            "health_elapsed_ms": 12,
            "synthesis_elapsed_ms": 1988,
            "cleanup_elapsed_ms": 2,
            "elapsed_ms": 2000,
        }
        values.update(overrides)
        return self.manual.TtsSynthesisEvidence(**values)

    @staticmethod
    def tts_preview_bytes() -> bytes:
        stream = io.BytesIO()
        with wave.open(stream, "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(16_000)
            writer.writeframes(b"\x00" * 32_000)
        return stream.getvalue()

    def tts_preview_executor(self, store, **overrides):
        def execute():
            store.publish(self.tts_preview_bytes())
            return self.tts_evidence(**overrides)

        return execute

    def vision_evidence(self, **overrides):
        values = {
            "runtime_feature_enabled": True,
            "configured_model": "vision-test-model",
            "fixed_image_contract": "vision.sticker.v1",
            "fixed_image_bytes": 162977,
            "fixed_image_contract_valid": True,
            "reference_sticker_id": "aike_affection_005",
            "registered_reference_asset_read": True,
            "expected_answer_disclosed_in_prompt": False,
            "service_tags_checked": True,
            "service_healthy": True,
            "service_preexisting": True,
            "service_start_attempted": False,
            "service_started": False,
            "service_owned_by_diagnostic": False,
            "service_ownership_basis": "none",
            "service_stop_attempted": False,
            "service_stopped": False,
            "model_available": True,
            "model_residency_checked": True,
            "model_loaded_before": False,
            "keep_alive_zero_used": True,
            "vision_called": True,
            "response_contract_valid": True,
            "response_mode": "natural_text",
            "structured_output_requested": False,
            "semantic_contract_automatically_validated": False,
            "owner_visual_judgment_required": True,
            "response_preview": (
                "一名黑白双色头发的Q版人物抱着一个大爱心，"
                "周围漂浮着多个粉红色爱心。"
            ),
            "response_description": (
                "一名黑白双色头发的Q版人物抱着一个大爱心，"
                "周围漂浮着多个粉红色爱心。"
            ),
            "response_content_exposed_to_owner": True,
            "usage_metadata_available": True,
            "input_tokens": 72,
            "output_tokens": 28,
            "total_tokens": 100,
            "model_cleanup_required": True,
            "model_cleanup_verified": True,
            "model_cleanup_poll_count": 1,
            "startup_elapsed_ms": 0,
            "discovery_elapsed_ms": 5,
            "residency_elapsed_ms": 3,
            "inference_elapsed_ms": 1200,
            "cleanup_elapsed_ms": 2,
            "elapsed_ms": 1210,
        }
        values.update(overrides)
        return self.manual.VisionInferenceEvidence(**values)

    def vision_reference_asset(self):
        return self.manual.VisionReferenceAsset(
            sticker_id="aike_affection_005",
            content=b"\x89PNG\r\n\x1a\nfixed-owner-preview",
            media_type="image/png",
            width=500,
            height=500,
        )

    def cloud_vision_evidence(self, **overrides):
        values = {
            "runtime_feature_enabled": True,
            "provider": "aliyun_bailian",
            "region": "cn-beijing",
            "configured_model": "qwen3.7-flash",
            "returned_model": "qwen3.7-flash",
            "endpoint_contract_valid": True,
            "workspace_configured": True,
            "credentials_configured": True,
            "fixed_image_contract": "vision.sticker.v1",
            "fixed_image_bytes": 162977,
            "fixed_image_contract_valid": True,
            "reference_sticker_id": "aike_affection_005",
            "registered_reference_asset_read": True,
            "external_image_upload_planned": True,
            "external_image_upload_executed": True,
            "provider_side_persistence_controlled_by_app": False,
            "cloud_vision_called": True,
            "request_count": 1,
            "client_automatic_retry": False,
            "tool_definitions_sent": False,
            "thinking_enabled": False,
            "response_mode": "natural_text",
            "structured_output_requested": False,
            "semantic_contract_automatically_validated": False,
            "owner_visual_judgment_required": True,
            "response_contract_valid": True,
            "response_preview": "角色捧着红色爱心，表达浓烈的爱意与兴奋。",
            "response_description": "角色捧着红色爱心，表达浓烈的爱意与兴奋。",
            "response_cleanup_applied": True,
            "input_tokens": 316,
            "output_tokens": 98,
            "total_tokens": 414,
            "request_elapsed_ms": 1578,
        }
        values.update(overrides)
        return self.manual.CloudVisionEvidence(**values)

    def test_metadata_search_uses_read_only_database_and_never_selects_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "chatbot.db"
            with patch.object(self.database, "DATABASE_PATH", db_path):
                self.database.ensure_database()
                now = self.database.utc_now()
                with self.database.connect() as connection:
                    rows = [
                        (
                            self.manual.PROJECT_DOC_RAG_PROBE_EXPECTED_SOURCE_ID,
                            "expected",
                            json.dumps([1.0, 0.0]),
                        ),
                        ("docs/another.md", "other", json.dumps([0.0, 1.0])),
                    ]
                    for index, (source_id, title, vector) in enumerate(rows):
                        cursor = connection.execute(
                            """
                            INSERT INTO rag_documents (
                                namespace, source_type, source_id, source_version,
                                visibility, title, content, content_hash, chunk_index,
                                created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                "project_docs",
                                "project_doc",
                                source_id,
                                "v1",
                                "project_owner",
                                title,
                                "private-to-the-probe-content",
                                f"hash-{index}",
                                0,
                                now,
                                now,
                            ),
                        )
                        connection.execute(
                            """
                            INSERT INTO rag_embeddings (
                                document_id, embedding_provider, embedding_model,
                                embedding_dimension, embedding, content_hash, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                int(cursor.lastrowid),
                                "ollama",
                                "bge-m3",
                                2,
                                vector,
                                f"hash-{index}",
                                now,
                            ),
                        )
                with self.database.connect() as connection:
                    connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                before = db_path.stat()

                counts = self.manual.read_project_doc_rag_index_counts(
                    provider="ollama",
                    model="bge-m3",
                )
                hits = self.manual.search_project_doc_rag_metadata_read_only(
                    query_embedding=[1.0, 0.0],
                    provider="ollama",
                    model="bge-m3",
                    top_k=2,
                )

                after = db_path.stat()

        self.assertEqual(counts.document_count, 2)
        self.assertEqual(counts.embedding_count, 2)
        self.assertEqual(
            hits[0].source_id,
            self.manual.PROJECT_DOC_RAG_PROBE_EXPECTED_SOURCE_ID,
        )
        self.assertFalse(hasattr(hits[0], "content"))
        self.assertEqual(before.st_size, after.st_size)
        self.assertEqual(before.st_mtime_ns, after.st_mtime_ns)

    def test_explicit_probe_runs_once_when_runtime_project_rag_is_disabled(self):
        calls: list[str] = []
        manual = self.manual

        class FakeEmbedder(manual.OllamaEmbeddingProvider):
            def __init__(self) -> None:
                self.model = "bge-m3"
                self.base_url = "http://127.0.0.1:11434"
                self.timeout_seconds = 1
                self.expected_dimension = 2

            def embed_once(self, text: str) -> list[float]:
                calls.append(text)
                return [1.0, 0.0]

        executor = manual.ProjectDocRagProbeExecutor(
            config_provider=lambda: SimpleNamespace(enable_project_doc_rag=False),
            embedder_factory=lambda _config: FakeEmbedder(),
            count_reader=lambda **_kwargs: manual.ProjectDocRagIndexCounts(2, 2),
            searcher=lambda **_kwargs: [
                manual.ProjectDocRagProbeHit(
                    manual.PROJECT_DOC_RAG_PROBE_EXPECTED_SOURCE_ID,
                    0,
                    0.91,
                ),
            ],
        )

        evidence = executor()

        self.assertEqual(calls, [manual.PROJECT_DOC_RAG_PROBE_QUERY])
        self.assertEqual(evidence.result_count, 1)
        self.assertTrue(evidence.expected_document_matched)
        self.assertEqual(evidence.top_score, 0.91)
        self.assertFalse(evidence.runtime_feature_enabled)

    def test_memory_consistency_reads_only_counts_without_private_content_or_writes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "chatbot.db"
            with patch.object(self.database, "DATABASE_PATH", db_path):
                self.database.ensure_database()
                now = self.database.utc_now()
                with self.database.connect() as connection:
                    manual_rows = [
                        ("fact", "private-fact-a"),
                        ("fact", "private-fact-b"),
                        ("preference_summary", "private-preference"),
                    ]
                    source_ids: list[tuple[int, str, str]] = []
                    for memory_type, content in manual_rows:
                        cursor = connection.execute(
                            """
                            INSERT INTO long_term_memories (
                                subject_type, subject_id, memory_type, content,
                                confidence, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            ("user", "owner", memory_type, content, 1.0, now, now),
                        )
                        source_type = (
                            "manual_preference"
                            if memory_type == "preference_summary"
                            else "manual_fact"
                        )
                        source_ids.append((int(cursor.lastrowid), source_type, content))
                    summary_cursor = connection.execute(
                        """
                        INSERT INTO session_summaries (
                            session_key, message_type, user_id, group_id, summary,
                            message_start_id, message_end_id, source_message_count,
                            created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        ("private-session", "private", "owner", None,
                         "private-summary", 1, 1, 1, now),
                    )
                    source_ids.append(
                        (int(summary_cursor.lastrowid), "session_summary", "private-summary")
                    )

                    document_ids: list[int] = []
                    for index, (source_id, source_type, private_content) in enumerate(source_ids):
                        cursor = connection.execute(
                            """
                            INSERT INTO rag_documents (
                                namespace, source_type, source_id, source_version,
                                visibility, title, content, content_hash, chunk_index,
                                created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                "semantic_memory", source_type, str(source_id), "v1",
                                "owner_only", "private-title", private_content,
                                f"hash-{index}", 0, now, now,
                            ),
                        )
                        document_ids.append(int(cursor.lastrowid))
                    for index, document_id in enumerate(document_ids[1:], start=1):
                        connection.execute(
                            """
                            INSERT INTO rag_embeddings (
                                document_id, embedding_provider, embedding_model,
                                embedding_dimension, embedding, content_hash, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (document_id, "ollama", "bge-m3", 2, "[1,0]",
                             f"hash-{index}", now),
                        )
                    inactive = connection.execute(
                        """
                        INSERT INTO rag_documents (
                            namespace, source_type, source_id, source_version,
                            visibility, title, content, content_hash, chunk_index,
                            created_at, updated_at, deleted_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "semantic_memory", "manual_fact", "historical", "v1",
                            "owner_only", "private-title", "private-deleted-content",
                            "inactive-hash", 0, now, now, now,
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO rag_embeddings (
                            document_id, embedding_provider, embedding_model,
                            embedding_dimension, embedding, content_hash, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (int(inactive.lastrowid), "ollama", "bge-m3", 2,
                         "[1,0]", "inactive-hash", now),
                    )
                with self.database.connect() as connection:
                    connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                before = db_path.stat()
                statements: list[str] = []
                original_connect_read_only = self.database.connect_read_only

                @contextmanager
                def traced_read_only():
                    with original_connect_read_only() as connection:
                        connection.set_trace_callback(statements.append)
                        yield connection

                with patch.object(
                    self.manual,
                    "connect_read_only",
                    traced_read_only,
                ):
                    evidence = self.manual.read_memory_rag_consistency(
                        provider="ollama",
                        model="bge-m3",
                        include_manual_facts=True,
                        include_manual_preferences=True,
                        include_session_summaries=True,
                        runtime_feature_enabled=False,
                    )
                after = db_path.stat()

        self.assertEqual(evidence.active_document_count, 4)
        self.assertEqual(evidence.valid_embedding_count, 3)
        self.assertEqual(evidence.missing_embedding_count, 1)
        self.assertEqual(evidence.missing_manual_fact_embeddings, 1)
        self.assertEqual(evidence.active_documents_missing_source, 0)
        self.assertEqual(evidence.source_records_missing_document, 0)
        self.assertEqual(evidence.inactive_document_embedding_count, 1)
        self.assertEqual(before.st_size, after.st_size)
        self.assertEqual(before.st_mtime_ns, after.st_mtime_ns)
        selected_sql = "\n".join(
            statement for statement in statements
            if statement.lstrip().upper().startswith("SELECT")
        )
        self.assertIsNone(re.search(r"\bcontent\b", selected_sql, re.IGNORECASE))
        self.assertIsNone(re.search(r"\bsummary\b", selected_sql, re.IGNORECASE))

    def test_memory_executor_uses_provider_identity_without_embedding_call(self):
        manual = self.manual
        calls: list[dict[str, object]] = []

        class ProviderIdentityOnly:
            provider = "ollama"
            model = "bge-m3"

            def embed(self, _text):
                raise AssertionError("embedding must not be called")

            def embed_once(self, _text):
                raise AssertionError("embedding must not be called")

        executor = manual.MemoryRagConsistencyExecutor(
            config_provider=lambda: SimpleNamespace(
                enable_memory_rag=False,
                memory_rag_include_manual_facts=True,
                memory_rag_include_manual_preferences=True,
                memory_rag_include_session_summaries=True,
            ),
            reader=lambda **kwargs: (
                calls.append(kwargs) or self.memory_evidence()
            ),
        )
        with patch.object(
            manual,
            "build_embedding_provider",
            return_value=ProviderIdentityOnly(),
        ):
            evidence = executor()

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["provider"], "ollama")
        self.assertEqual(calls[0]["model"], "bge-m3")
        self.assertFalse(evidence.runtime_feature_enabled)

    def test_memory_gap_is_attention_and_source_mismatch_takes_precedence(self):
        manual = self.manual
        runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            memory_rag_consistency_enabled=True,
            memory_rag_consistency_executor=self.memory_evidence,
        )

        result = runtime.run_memory_rag_consistency()

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.outcome, "attention")
        self.assertEqual(result.code, "memory_rag_active_embedding_gap")
        self.assertEqual(result.attempt_count, 1)
        self.assertFalse(result.embedding_called)
        self.assertFalse(result.memory_content_read)
        self.assertFalse(result.private_memory_query_executed)
        self.assertFalse(result.automatic_retry)
        self.assertIs(runtime.build_snapshot().memory_rag_consistency_latest_run, result)

        mismatch_runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            memory_rag_consistency_enabled=True,
            memory_rag_consistency_executor=lambda: self.memory_evidence(
                active_documents_missing_source=1,
            ),
        )
        mismatch = mismatch_runtime.run_memory_rag_consistency()
        self.assertEqual(mismatch.outcome, "attention")
        self.assertEqual(mismatch.code, "memory_rag_source_mismatch")

    def test_runtime_rejects_concurrency_without_queueing_or_retrying(self):
        entered = threading.Event()
        release = threading.Event()
        manual = self.manual

        def blocking_executor():
            entered.set()
            release.wait(timeout=2)
            return manual.ProjectDocRagProbeEvidence(2, 2, 1, True, 0.9, 10)

        runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=True,
            project_doc_rag_probe_executor=blocking_executor,
            memory_rag_consistency_enabled=True,
            memory_rag_consistency_executor=self.memory_evidence,
        )
        completed: list[object] = []
        thread = threading.Thread(
            target=lambda: completed.append(runtime.run_project_doc_rag_probe())
        )
        thread.start()
        self.assertTrue(entered.wait(timeout=1))

        with self.assertRaises(manual.OwnerConsoleManualDiagnosticBusy):
            runtime.run_memory_rag_consistency()

        release.set()
        thread.join(timeout=2)
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].attempt_count, 1)
        self.assertFalse(completed[0].automatic_retry)

    def test_main_llm_contract_runtime_distinguishes_success_and_attention(self):
        manual = self.manual
        runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            main_llm_contract_enabled=True,
            main_llm_contract_executor=self.main_llm_evidence,
        )

        succeeded = runtime.run_main_llm_contract()

        self.assertEqual(succeeded.outcome, "succeeded")
        self.assertEqual(succeeded.code, "main_llm_contract_succeeded")
        self.assertEqual(succeeded.attempt_count, 1)
        self.assertTrue(succeeded.llm_called)
        self.assertTrue(succeeded.contract_valid)
        self.assertFalse(succeeded.tool_definitions_sent)
        self.assertFalse(succeeded.tool_execution_allowed)
        self.assertFalse(succeeded.client_automatic_retry)
        self.assertFalse(succeeded.database_write_allowed)
        self.assertFalse(succeeded.reliability_event_written)
        self.assertIs(runtime.build_snapshot().main_llm_contract_latest_run, succeeded)

        usage_runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            main_llm_contract_enabled=True,
            main_llm_contract_executor=lambda: self.main_llm_evidence(
                usage_metadata_available=False,
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
            ),
        )
        usage_attention = usage_runtime.run_main_llm_contract()
        self.assertEqual(usage_attention.outcome, "attention")
        self.assertEqual(usage_attention.code, "main_llm_usage_unavailable")

        mismatch_runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            main_llm_contract_enabled=True,
            main_llm_contract_executor=lambda: self.main_llm_evidence(
                contract_valid=False,
            ),
        )
        mismatch = mismatch_runtime.run_main_llm_contract()
        self.assertEqual(mismatch.outcome, "attention")
        self.assertEqual(mismatch.code, "main_llm_contract_mismatch")

    def test_main_llm_contract_shares_global_lock_with_other_workflows(self):
        entered = threading.Event()
        release = threading.Event()
        manual = self.manual

        def blocking_main_llm():
            entered.set()
            release.wait(timeout=2)
            return self.main_llm_evidence()

        runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            memory_rag_consistency_enabled=True,
            memory_rag_consistency_executor=self.memory_evidence,
            main_llm_contract_enabled=True,
            main_llm_contract_executor=blocking_main_llm,
        )
        completed: list[object] = []
        thread = threading.Thread(
            target=lambda: completed.append(runtime.run_main_llm_contract())
        )
        thread.start()
        self.assertTrue(entered.wait(timeout=1))

        with self.assertRaises(manual.OwnerConsoleManualDiagnosticBusy):
            runtime.run_memory_rag_consistency()

        release.set()
        thread.join(timeout=2)
        self.assertEqual(len(completed), 1)

    def test_tts_runtime_reports_success_attention_and_safe_failure(self):
        manual = self.manual
        store = manual.TtsAudioPreviewStore()
        runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            tts_synthesis_enabled=True,
            tts_synthesis_executor=self.tts_preview_executor(store),
            tts_audio_preview_store=store,
        )

        pending_review = runtime.run_tts_synthesis()

        self.assertEqual(pending_review.outcome, "attention")
        self.assertEqual(pending_review.stage, "owner_audio_review")
        self.assertEqual(pending_review.code, "tts_audio_quality_review_required")
        self.assertEqual(pending_review.technical_outcome, "succeeded")
        self.assertEqual(pending_review.technical_code, "tts_managed_lifecycle_succeeded")
        self.assertEqual(pending_review.fixed_text, "这是一次固定语音合成检查。")
        self.assertTrue(pending_review.audio_preview_available)
        self.assertTrue(pending_review.audio_quality_review_required)
        self.assertFalse(pending_review.audio_quality_reviewed)
        self.assertIsNone(pending_review.audio_quality_accepted)
        self.assertEqual(
            runtime.read_tts_audio_preview(pending_review.run_id),
            self.tts_preview_bytes(),
        )
        self.assertEqual(pending_review.attempt_count, 1)
        self.assertTrue(pending_review.tts_called)
        self.assertTrue(pending_review.output_contract_valid)
        self.assertFalse(pending_review.runtime_imported_before)
        self.assertTrue(pending_review.local_file_write_expected)
        self.assertFalse(pending_review.service_started)
        self.assertFalse(pending_review.automatic_retry)
        self.assertFalse(pending_review.qq_write_executed)
        self.assertFalse(pending_review.reliability_event_written)
        self.assertFalse(pending_review.database_write_allowed)
        self.assertTrue(pending_review.service_preexisting)
        self.assertFalse(pending_review.output_retained)
        self.assertFalse(pending_review.segment_directory_retained)
        self.assertTrue(pending_review.artifact_cleanup_succeeded)
        self.assertTrue(pending_review.cleanup_executed)

        succeeded = runtime.review_tts_audio_quality(
            pending_review.run_id,
            accepted=True,
        )
        self.assertEqual(succeeded.outcome, "succeeded")
        self.assertEqual(succeeded.stage, "result_validation")
        self.assertEqual(succeeded.code, "tts_managed_lifecycle_succeeded")
        self.assertTrue(succeeded.audio_quality_reviewed)
        self.assertTrue(succeeded.audio_quality_accepted)
        self.assertTrue(succeeded.audio_review_action_executed)
        self.assertFalse(succeeded.audio_preview_available)
        self.assertTrue(succeeded.audio_reviewed_at)
        with self.assertRaises(manual.OwnerConsoleTtsAudioReviewUnavailable):
            runtime.read_tts_audio_preview(succeeded.run_id)
        snapshot = runtime.build_snapshot()
        self.assertTrue(snapshot.tts_synthesis_enabled)
        self.assertIn("tts_managed_lifecycle", snapshot.supported_workflows)
        self.assertIs(snapshot.tts_synthesis_latest_run, succeeded)

        reject_store = manual.TtsAudioPreviewStore()
        reject_runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            tts_synthesis_enabled=True,
            tts_synthesis_executor=self.tts_preview_executor(reject_store),
            tts_audio_preview_store=reject_store,
        )
        rejected_pending = reject_runtime.run_tts_synthesis()
        rejected = reject_runtime.review_tts_audio_quality(
            rejected_pending.run_id,
            accepted=False,
        )
        self.assertEqual(rejected.outcome, "failed")
        self.assertEqual(rejected.stage, "owner_audio_review")
        self.assertEqual(rejected.code, "tts_audio_quality_rejected")
        self.assertTrue(rejected.audio_quality_reviewed)
        self.assertFalse(rejected.audio_quality_accepted)

        attention_store = manual.TtsAudioPreviewStore()
        attention_runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            tts_synthesis_enabled=True,
            tts_synthesis_executor=self.tts_preview_executor(
                attention_store,
                synthesis_elapsed_ms=120_001,
                elapsed_ms=120_010,
            ),
            tts_audio_preview_store=attention_store,
        )
        attention_pending = attention_runtime.run_tts_synthesis()
        self.assertEqual(attention_pending.code, "tts_audio_quality_review_required")
        self.assertEqual(attention_pending.technical_code, "tts_synthesis_latency_attention")
        attention = attention_runtime.review_tts_audio_quality(
            attention_pending.run_id,
            accepted=True,
        )
        self.assertEqual(attention.outcome, "attention")
        self.assertEqual(attention.code, "tts_synthesis_latency_attention")

        attention_cases = (
            (
                {"artifact_cleanup_succeeded": False},
                "tts_artifact_cleanup_incomplete",
            ),
            (
                {
                    "service_preexisting": False,
                    "service_start_attempted": True,
                    "service_started": True,
                    "service_owned_by_diagnostic": True,
                    "service_stop_attempted": True,
                    "service_stopped": False,
                },
                "tts_managed_service_stop_incomplete",
            ),
            (
                {
                    "service_preexisting": False,
                    "service_start_attempted": True,
                    "service_started": True,
                    "service_owned_by_diagnostic": True,
                    "service_stop_attempted": True,
                    "service_stopped": True,
                    "startup_elapsed_ms": 30_001,
                },
                "tts_startup_latency_attention",
            ),
        )
        for overrides, expected_code in attention_cases:
            with self.subTest(expected_code=expected_code):
                attention_store = manual.TtsAudioPreviewStore()
                attention_runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
                    manual_diagnostic_actions_enabled=True,
                    project_doc_rag_probe_enabled=False,
                    project_doc_rag_probe_executor=lambda: None,
                    tts_synthesis_enabled=True,
                    tts_synthesis_executor=self.tts_preview_executor(
                        attention_store,
                        **overrides,
                    ),
                    tts_audio_preview_store=attention_store,
                )
                attention_pending = attention_runtime.run_tts_synthesis()
                self.assertEqual(
                    attention_pending.technical_code,
                    expected_code,
                )
                attention = attention_runtime.review_tts_audio_quality(
                    attention_pending.run_id,
                    accepted=True,
                )
                self.assertEqual(attention.outcome, "attention")
                self.assertEqual(attention.code, expected_code)

        unavailable_runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            tts_synthesis_enabled=True,
            tts_synthesis_executor=self.tts_evidence,
        )
        unavailable = unavailable_runtime.run_tts_synthesis()
        self.assertEqual(unavailable.outcome, "failed")
        self.assertEqual(unavailable.code, "tts_audio_preview_unavailable")

        failure_runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            tts_synthesis_enabled=True,
            tts_synthesis_executor=lambda: (_ for _ in ()).throw(
                manual.TtsSynthesisFailure(
                    stage="model_synthesis",
                    code="tts_synthesis_failed",
                    code_label="TTS 服务未能完成固定合成",
                    runtime_feature_enabled=True,
                    service_health_checked=True,
                    service_healthy=True,
                    model_loaded_before=False,
                    configured_voice_present=True,
                    tts_called=True,
                    artifact_cleanup_attempted=True,
                    artifact_cleanup_succeeded=True,
                    partial_artifact_state="failed_artifacts_removed",
                    elapsed_ms=8,
                )
            ),
        )
        failed = failure_runtime.run_tts_synthesis()
        self.assertEqual(failed.outcome, "failed")
        self.assertEqual(failed.code, "tts_synthesis_failed")
        self.assertTrue(failed.model_load_may_have_occurred)
        self.assertEqual(failed.partial_artifact_state, "failed_artifacts_removed")
        self.assertTrue(failed.cleanup_executed)

    def test_tts_shares_global_lock_with_every_other_manual_workflow(self):
        entered = threading.Event()
        release = threading.Event()
        manual = self.manual

        def blocking_tts():
            entered.set()
            release.wait(timeout=2)
            return self.tts_evidence()

        runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=True,
            project_doc_rag_probe_executor=lambda: manual.ProjectDocRagProbeEvidence(
                2, 2, 1, True, 0.9, 10
            ),
            memory_rag_consistency_enabled=True,
            memory_rag_consistency_executor=self.memory_evidence,
            main_llm_contract_enabled=True,
            main_llm_contract_executor=self.main_llm_evidence,
            tts_synthesis_enabled=True,
            tts_synthesis_executor=blocking_tts,
        )
        completed: list[object] = []
        thread = threading.Thread(
            target=lambda: completed.append(runtime.run_tts_synthesis())
        )
        thread.start()
        self.assertTrue(entered.wait(timeout=1))

        for action in (
            runtime.run_project_doc_rag_probe,
            runtime.run_memory_rag_consistency,
            runtime.run_main_llm_contract,
        ):
            with self.subTest(action=action.__name__):
                with self.assertRaises(manual.OwnerConsoleManualDiagnosticBusy):
                    action()

        release.set()
        thread.join(timeout=2)
        self.assertEqual(len(completed), 1)

    def test_memory_fastapi_action_requires_fixed_security_contract(self):
        manual = self.manual
        runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            memory_rag_consistency_enabled=True,
            memory_rag_consistency_executor=self.memory_evidence,
        )
        app = self.fastapi.create_owner_console_fastapi_app(
            manual_diagnostics_runtime=runtime,
            action_session_token="test-action-session",
        )
        client = TestClient(app, base_url="http://127.0.0.1:8090")
        state = client.get("/api/v1/owner-console/manual-diagnostics")
        self.assertTrue(state.json()["data"]["memory_rag_consistency_enabled"])

        path = "/api/v1/owner-console/manual-diagnostics/memory-rag-consistency"
        confirmation = {"confirmation": "run_registered_memory_rag_consistency"}
        action_header = "manual-memory-rag-consistency-v1"
        self.assertEqual(
            client.post(
                path,
                headers={"X-Owner-Console-Action": action_header},
                json=confirmation,
            ).status_code,
            403,
        )
        headers = {
            "Origin": "http://127.0.0.1:8090",
            "X-Owner-Console-Action": action_header,
        }
        self.assertEqual(
            client.post(
                path,
                headers=headers,
                json={"confirmation": "anything-else"},
            ).status_code,
            400,
        )
        response = client.post(path, headers=headers, json=confirmation)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["outcome"], "attention")
        self.assertEqual(
            payload["data"]["code"],
            "memory_rag_active_embedding_gap",
        )
        self.assertFalse(payload["data"]["memory_content_read"])
        self.assertFalse(payload["data"]["embedding_called"])
        rendered = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("private-fact", rendered)
        self.assertNotIn("private-summary", rendered)

    def test_main_llm_fastapi_action_uses_fixed_security_contract_and_safe_result(self):
        manual = self.manual
        runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            main_llm_contract_enabled=True,
            main_llm_contract_executor=self.main_llm_evidence,
        )
        app = self.fastapi.create_owner_console_fastapi_app(
            manual_diagnostics_runtime=runtime,
            action_session_token="test-action-session",
        )
        client = TestClient(app, base_url="http://127.0.0.1:8090")
        state = client.get("/api/v1/owner-console/manual-diagnostics")
        state_data = state.json()["data"]
        self.assertTrue(state_data["main_llm_contract_enabled"])
        self.assertIn("main_llm_fixed_contract", state_data["supported_workflows"])

        path = "/api/v1/owner-console/manual-diagnostics/main-llm-contract"
        confirmation = {"confirmation": "run_registered_main_llm_contract"}
        action_header = "manual-main-llm-contract-v1"
        self.assertEqual(
            client.post(
                path,
                headers={"X-Owner-Console-Action": action_header},
                json=confirmation,
            ).status_code,
            403,
        )
        headers = {
            "Origin": "http://127.0.0.1:8090",
            "X-Owner-Console-Action": action_header,
        }
        self.assertEqual(
            client.post(
                path,
                headers=headers,
                json={**confirmation, "prompt": "forbidden"},
            ).status_code,
            400,
        )
        response = client.post(path, headers=headers, json=confirmation)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        result = payload["data"]
        self.assertEqual(result["outcome"], "succeeded")
        self.assertEqual(result["code"], "main_llm_contract_succeeded")
        self.assertEqual(result["attempt_count"], 1)
        self.assertTrue(result["llm_called"])
        self.assertFalse(result["tool_definitions_sent"])
        self.assertFalse(result["tool_execution_allowed"])
        self.assertFalse(result["client_automatic_retry"])
        self.assertFalse(result["database_write_allowed"])
        self.assertFalse(result["reliability_event_written"])
        rendered = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("amber-17", rendered)
        self.assertNotIn("test-key", rendered)
        self.assertNotIn("main.example", rendered)

    def test_tts_fastapi_action_preview_and_owner_quality_review_are_fixed(self):
        manual = self.manual
        store = manual.TtsAudioPreviewStore()
        runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            tts_synthesis_enabled=True,
            tts_synthesis_executor=self.tts_preview_executor(store),
            tts_audio_preview_store=store,
        )
        app = self.fastapi.create_owner_console_fastapi_app(
            manual_diagnostics_runtime=runtime,
            action_session_token="test-action-session",
        )
        client = TestClient(app, base_url="http://127.0.0.1:8090")
        state = client.get("/api/v1/owner-console/manual-diagnostics").json()[
            "data"
        ]
        self.assertTrue(state["tts_synthesis_enabled"])
        self.assertIn("tts_managed_lifecycle", state["supported_workflows"])

        path = "/api/v1/owner-console/manual-diagnostics/tts-synthesis"
        confirmation = {"confirmation": "run_registered_tts_synthesis"}
        action_header = "manual-tts-synthesis-v1"
        self.assertEqual(
            client.post(
                path,
                headers={"X-Owner-Console-Action": action_header},
                json=confirmation,
            ).status_code,
            403,
        )
        headers = {
            "Origin": "http://127.0.0.1:8090",
            "X-Owner-Console-Action": action_header,
        }
        self.assertEqual(
            client.post(
                path,
                headers={**headers, "X-Owner-Console-Action": "wrong"},
                json=confirmation,
            ).status_code,
            403,
        )
        for bad_body in (
            {**confirmation, "text": "forbidden"},
            {"confirmation": "wrong"},
        ):
            with self.subTest(body=bad_body):
                self.assertEqual(
                    client.post(path, headers=headers, json=bad_body).status_code,
                    400,
                )
        self.assertEqual(
            client.post(
                path,
                headers={**headers, "Content-Type": "text/plain"},
                content='{"confirmation":"run_registered_tts_synthesis"}',
            ).status_code,
            400,
        )

        response = client.post(path, headers=headers, json=confirmation)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        result = payload["data"]
        self.assertFalse(payload["read_only"])
        self.assertTrue(payload["manual_runtime_action"])
        self.assertFalse(payload["configuration_write_enabled"])
        self.assertFalse(payload["business_data_write_enabled"])
        self.assertEqual(result["workflow"], "tts_managed_lifecycle")
        self.assertEqual(result["outcome"], "attention")
        self.assertEqual(result["stage"], "owner_audio_review")
        self.assertEqual(result["code"], "tts_audio_quality_review_required")
        self.assertEqual(result["technical_code"], "tts_managed_lifecycle_succeeded")
        self.assertEqual(result["fixed_text"], "这是一次固定语音合成检查。")
        self.assertTrue(result["audio_preview_available"])
        self.assertTrue(result["audio_quality_review_required"])
        self.assertEqual(result["attempt_count"], 1)
        self.assertTrue(result["tts_called"])
        self.assertTrue(result["local_file_write_expected"])
        self.assertTrue(result["service_preexisting"])
        self.assertFalse(result["service_start_attempted"])
        self.assertFalse(result["service_started"])
        self.assertFalse(result["service_owned_by_diagnostic"])
        self.assertFalse(result["service_stop_attempted"])
        self.assertFalse(result["service_stopped"])
        self.assertFalse(result["automatic_retry"])
        self.assertFalse(result["qq_write_executed"])
        self.assertFalse(result["reliability_event_written"])
        self.assertFalse(result["database_write_allowed"])
        self.assertTrue(result["artifact_cleanup_attempted"])
        self.assertTrue(result["artifact_cleanup_succeeded"])
        self.assertTrue(result["cleanup_executed"])
        for forbidden_key in (
            "audio_path",
            "output_path",
            "text",
            "prompt",
            "error",
            "service_url",
            "voice_id",
        ):
            self.assertNotIn(forbidden_key, result)

        preview_path = (
            "/api/v1/owner-console/manual-diagnostics/tts-synthesis"
            f"/audio-preview/{result['run_id']}"
        )
        self.assertEqual(client.get(preview_path).status_code, 403)
        preview_response = client.get(
            preview_path,
            headers={
                "X-Owner-Console-Action": "manual-tts-audio-preview-v1"
            },
        )
        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(
            preview_response.headers["content-type"].split(";", 1)[0],
            "audio/wav",
        )
        self.assertEqual(preview_response.headers["cache-control"], "no-store, max-age=0")
        self.assertEqual(preview_response.content, self.tts_preview_bytes())
        self.assertEqual(
            client.get(
                preview_path.replace(
                    f"/{result['run_id']}",
                    f"/{result['run_id'] + 1}",
                ),
                headers={
                    "X-Owner-Console-Action": "manual-tts-audio-preview-v1"
                },
            ).status_code,
            409,
        )

        accept_path = (
            "/api/v1/owner-console/manual-diagnostics/tts-synthesis"
            "/audio-quality/accept"
        )
        accept_headers = {
            "Origin": "http://127.0.0.1:8090",
            "X-Owner-Console-Action": "manual-tts-audio-quality-accept-v1",
        }
        accept_body = {
            "confirmation": "accept_latest_tts_audio_quality",
            "run_id": result["run_id"],
        }
        self.assertEqual(
            client.post(
                accept_path,
                headers=accept_headers,
                json={**accept_body, "accepted": True},
            ).status_code,
            400,
        )
        accepted_response = client.post(
            accept_path,
            headers=accept_headers,
            json=accept_body,
        )
        self.assertEqual(accepted_response.status_code, 200)
        accepted = accepted_response.json()["data"]
        self.assertEqual(accepted["outcome"], "succeeded")
        self.assertEqual(accepted["code"], "tts_managed_lifecycle_succeeded")
        self.assertTrue(accepted["audio_quality_reviewed"])
        self.assertTrue(accepted["audio_quality_accepted"])
        self.assertFalse(accepted["audio_preview_available"])
        self.assertEqual(
            client.get(
                preview_path,
                headers={
                    "X-Owner-Console-Action": "manual-tts-audio-preview-v1"
                },
            ).status_code,
            409,
        )

        reject_path = accept_path.replace("/accept", "/reject")
        self.assertEqual(
            client.post(
                reject_path,
                headers={
                    "Origin": "http://127.0.0.1:8090",
                    "X-Owner-Console-Action": "manual-tts-audio-quality-reject-v1",
                },
                json={
                    "confirmation": "reject_latest_tts_audio_quality",
                    "run_id": result["run_id"],
                },
            ).status_code,
            409,
        )

        runtime._probe_running = True
        try:
            self.assertEqual(
                client.post(path, headers=headers, json=confirmation).status_code,
                409,
            )
        finally:
            runtime._probe_running = False

    def test_vision_runtime_requires_owner_review_and_restores_technical_result(self):
        manual = self.manual
        runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            vision_inference_enabled=True,
            vision_inference_executor=self.vision_evidence,
            vision_reference_loader=self.vision_reference_asset,
        )

        pending = runtime.run_vision_inference()

        self.assertEqual(pending.outcome, "attention")
        self.assertEqual(pending.stage, "owner_visual_review")
        self.assertEqual(
            pending.code,
            "vision_response_quality_review_required",
        )
        self.assertEqual(pending.technical_outcome, "succeeded")
        self.assertEqual(
            pending.technical_code,
            "vision_managed_lifecycle_succeeded",
        )
        self.assertTrue(pending.visual_quality_review_required)
        self.assertTrue(pending.reference_preview_available)
        self.assertTrue(pending.vision_called)
        self.assertTrue(pending.response_contract_valid)
        self.assertEqual(pending.response_mode, "natural_text")
        self.assertFalse(pending.structured_output_requested)
        self.assertFalse(pending.semantic_contract_automatically_validated)
        self.assertTrue(pending.owner_visual_judgment_required)
        self.assertTrue(pending.model_cleanup_verified)
        self.assertIn("黑白双色头发", pending.response_description)
        self.assertTrue(pending.response_content_exposed_to_owner)
        self.assertFalse(pending.expected_answer_disclosed_in_prompt)
        self.assertEqual(
            runtime.read_vision_reference_preview(),
            self.vision_reference_asset().content,
        )

        succeeded = runtime.review_vision_response_quality(
            pending.run_id,
            accepted=True,
        )
        self.assertEqual(succeeded.outcome, "succeeded")
        self.assertEqual(succeeded.code, "vision_managed_lifecycle_succeeded")
        self.assertTrue(succeeded.visual_quality_reviewed)
        self.assertTrue(succeeded.visual_quality_accepted)
        self.assertTrue(succeeded.visual_review_action_executed)
        self.assertTrue(succeeded.reference_image_exposed_to_owner)
        self.assertFalse(succeeded.client_automatic_retry)
        self.assertFalse(succeeded.tool_definitions_sent)
        self.assertFalse(succeeded.database_write_allowed)
        self.assertFalse(succeeded.project_file_write_allowed)
        self.assertFalse(succeeded.project_artifact_write_expected)
        self.assertTrue(succeeded.external_runtime_local_write_possible)
        self.assertFalse(succeeded.model_pull_allowed)
        snapshot = runtime.build_snapshot()
        self.assertTrue(snapshot.vision_inference_enabled)
        self.assertIn("vision_managed_lifecycle", snapshot.supported_workflows)
        self.assertIs(snapshot.vision_inference_latest_run, succeeded)
        with self.assertRaises(manual.OwnerConsoleVisionReviewUnavailable):
            runtime.review_vision_response_quality(
                pending.run_id,
                accepted=True,
            )

        mismatch_runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            vision_inference_enabled=True,
            vision_inference_executor=lambda: self.vision_evidence(
                response_contract_valid=False
            ),
        )
        mismatch = mismatch_runtime.run_vision_inference()
        self.assertEqual(mismatch.outcome, "failed")
        self.assertEqual(mismatch.code, "vision_response_contract_mismatch")

        cleanup_runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            vision_inference_enabled=True,
            vision_inference_executor=lambda: self.vision_evidence(
                model_cleanup_verified=False
            ),
        )
        cleanup = cleanup_runtime.run_vision_inference()
        self.assertEqual(cleanup.outcome, "attention")
        self.assertEqual(
            cleanup.code,
            "vision_response_quality_review_required",
        )
        cleanup = cleanup_runtime.review_vision_response_quality(
            cleanup.run_id,
            accepted=True,
        )
        self.assertEqual(cleanup.outcome, "attention")
        self.assertEqual(cleanup.code, "vision_model_cleanup_incomplete")

        reject_runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            vision_inference_enabled=True,
            vision_inference_executor=self.vision_evidence,
            vision_reference_loader=self.vision_reference_asset,
        )
        rejected = reject_runtime.run_vision_inference()
        rejected = reject_runtime.review_vision_response_quality(
            rejected.run_id,
            accepted=False,
        )
        self.assertEqual(rejected.outcome, "failed")
        self.assertEqual(rejected.stage, "owner_visual_review")
        self.assertEqual(rejected.code, "vision_response_quality_rejected")
        self.assertFalse(rejected.visual_quality_accepted)

        failure_runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            vision_inference_enabled=True,
            vision_inference_executor=lambda: (_ for _ in ()).throw(
                manual.VisionInferenceFailure(
                    stage="service_start",
                    code="vision_service_start_failed",
                    code_label="无法启动受管理 Ollama 服务",
                    configured_model="vision-test-model",
                    service_start_attempted=True,
                    elapsed_ms=7,
                )
            ),
        )
        failed = failure_runtime.run_vision_inference()
        self.assertEqual(failed.outcome, "failed")
        self.assertEqual(failed.code, "vision_service_start_failed")
        self.assertFalse(failed.vision_called)

    def test_vision_shares_global_lock_with_all_existing_manual_workflows(self):
        entered = threading.Event()
        release = threading.Event()
        manual = self.manual

        def blocking_vision():
            entered.set()
            release.wait(timeout=2)
            return self.vision_evidence()

        runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=True,
            project_doc_rag_probe_executor=lambda: manual.ProjectDocRagProbeEvidence(
                2, 2, 1, True, 0.9, 10
            ),
            memory_rag_consistency_enabled=True,
            memory_rag_consistency_executor=self.memory_evidence,
            main_llm_contract_enabled=True,
            main_llm_contract_executor=self.main_llm_evidence,
            tts_synthesis_enabled=True,
            tts_synthesis_executor=self.tts_evidence,
            vision_inference_enabled=True,
            vision_inference_executor=blocking_vision,
        )
        completed = []
        thread = threading.Thread(
            target=lambda: completed.append(runtime.run_vision_inference())
        )
        thread.start()
        self.assertTrue(entered.wait(timeout=1))

        for action in (
            runtime.run_project_doc_rag_probe,
            runtime.run_memory_rag_consistency,
            runtime.run_main_llm_contract,
            runtime.run_tts_synthesis,
        ):
            with self.subTest(action=action.__name__):
                with self.assertRaises(manual.OwnerConsoleManualDiagnosticBusy):
                    action()

        release.set()
        thread.join(timeout=2)
        self.assertEqual(len(completed), 1)

    def test_vision_fastapi_action_uses_fixed_security_contract_and_safe_result(self):
        manual = self.manual
        runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            vision_inference_enabled=True,
            vision_inference_executor=self.vision_evidence,
            vision_reference_loader=self.vision_reference_asset,
        )
        app = self.fastapi.create_owner_console_fastapi_app(
            manual_diagnostics_runtime=runtime,
            action_session_token="test-action-session",
        )
        client = TestClient(app, base_url="http://127.0.0.1:8090")
        state = client.get("/api/v1/owner-console/manual-diagnostics").json()[
            "data"
        ]
        self.assertTrue(state["vision_inference_enabled"])
        self.assertIn("vision_managed_lifecycle", state["supported_workflows"])

        path = "/api/v1/owner-console/manual-diagnostics/vision-inference"
        confirmation = {"confirmation": "run_registered_vision_inference"}
        action_header = "manual-vision-inference-v1"
        self.assertEqual(
            client.post(
                path,
                headers={"X-Owner-Console-Action": action_header},
                json=confirmation,
            ).status_code,
            403,
        )
        headers = {
            "Origin": "http://127.0.0.1:8090",
            "X-Owner-Console-Action": action_header,
        }
        for bad_body in (
            {**confirmation, "image": "forbidden"},
            {**confirmation, "prompt": "forbidden"},
            {"confirmation": "wrong"},
        ):
            with self.subTest(body=bad_body):
                self.assertEqual(
                    client.post(path, headers=headers, json=bad_body).status_code,
                    400,
                )

        response = client.post(path, headers=headers, json=confirmation)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        result = payload["data"]
        self.assertFalse(payload["read_only"])
        self.assertTrue(payload["manual_runtime_action"])
        self.assertEqual(result["workflow"], "vision_managed_lifecycle")
        self.assertEqual(result["outcome"], "attention")
        self.assertEqual(result["stage"], "owner_visual_review")
        self.assertEqual(
            result["code"],
            "vision_response_quality_review_required",
        )
        self.assertTrue(result["vision_called"])
        self.assertTrue(result["response_contract_valid"])
        self.assertEqual(result["reference_sticker_id"], "aike_affection_005")
        self.assertIn("黑白双色头发", result["response_description"])
        self.assertTrue(result["response_content_exposed_to_owner"])
        self.assertTrue(result["visual_quality_review_required"])
        self.assertFalse(result["client_automatic_retry"])
        self.assertFalse(result["tool_definitions_sent"])
        self.assertFalse(result["database_write_allowed"])
        self.assertFalse(result["project_artifact_write_expected"])
        self.assertTrue(result["external_runtime_local_write_possible"])
        self.assertFalse(result["model_pull_allowed"])
        for forbidden_key in (
            "prompt",
            "image",
            "images",
            "base64",
            "response",
            "service_url",
            "model_path",
            "digest",
            "error",
        ):
            self.assertNotIn(forbidden_key, result)

        preview_path = (
            "/api/v1/owner-console/manual-diagnostics/"
            "vision-inference/reference-preview"
        )
        self.assertEqual(client.get(preview_path).status_code, 403)
        preview = client.get(
            preview_path,
            headers={
                "X-Owner-Console-Action": (
                    "manual-vision-reference-preview-v1"
                )
            },
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.headers["content-type"], "image/png")
        self.assertEqual(
            preview.headers["cache-control"],
            "no-store, max-age=0",
        )
        self.assertEqual(preview.content, self.vision_reference_asset().content)

        accept_path = (
            "/api/v1/owner-console/manual-diagnostics/"
            "vision-inference/response-quality/accept"
        )
        accepted_response = client.post(
            accept_path,
            headers={
                "Origin": "http://127.0.0.1:8090",
                "X-Owner-Console-Action": (
                    "manual-vision-response-quality-accept-v1"
                ),
            },
            json={
                "confirmation": "accept_latest_vision_response_quality",
                "run_id": result["run_id"],
            },
        )
        self.assertEqual(accepted_response.status_code, 200)
        accepted = accepted_response.json()["data"]
        self.assertEqual(accepted["outcome"], "succeeded")
        self.assertTrue(accepted["visual_quality_reviewed"])
        self.assertTrue(accepted["visual_quality_accepted"])
        self.assertTrue(accepted["visual_review_action_executed"])

        self.assertEqual(
            client.post(
                accept_path,
                headers={
                    "Origin": "http://127.0.0.1:8090",
                    "X-Owner-Console-Action": (
                        "manual-vision-response-quality-accept-v1"
                    ),
                },
                json={
                    "confirmation": (
                        "accept_latest_vision_response_quality"
                    ),
                    "run_id": result["run_id"],
                },
            ).status_code,
            409,
        )

        runtime._probe_running = True
        try:
            self.assertEqual(
                client.post(path, headers=headers, json=confirmation).status_code,
                409,
            )
        finally:
            runtime._probe_running = False

    def test_fastapi_action_requires_same_origin_cookie_header_and_confirmation(self):
        manual = self.manual
        runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=True,
            project_doc_rag_probe_executor=lambda: manual.ProjectDocRagProbeEvidence(
                1601,
                1601,
                5,
                True,
                0.91,
                900,
            ),
        )
        app = self.fastapi.create_owner_console_fastapi_app(
            manual_diagnostics_runtime=runtime,
            action_session_token="test-action-session",
        )
        client = TestClient(app, base_url="http://127.0.0.1:8090")
        state_response = client.get(
            "/api/v1/owner-console/manual-diagnostics"
        )
        self.assertEqual(state_response.status_code, 200)
        self.assertTrue(
            state_response.json()["data"]["project_doc_rag_probe_enabled"]
        )
        self.assertIn("owner_console_action_session", client.cookies)

        path = "/api/v1/owner-console/manual-diagnostics/project-doc-rag"
        required_headers = {
            "Origin": "http://127.0.0.1:8090",
            "X-Owner-Console-Action": "manual-project-doc-rag-probe-v1",
        }
        missing_origin = client.post(
            path,
            headers={"X-Owner-Console-Action": "manual-project-doc-rag-probe-v1"},
            json={"confirmation": "run_registered_project_doc_rag_probe"},
        )
        self.assertEqual(missing_origin.status_code, 403)

        invalid_confirmation = client.post(
            path,
            headers=required_headers,
            json={"confirmation": "anything-else"},
        )
        self.assertEqual(invalid_confirmation.status_code, 400)

        response = client.post(
            path,
            headers=required_headers,
            json={"confirmation": "run_registered_project_doc_rag_probe"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["read_only"])
        self.assertTrue(payload["manual_runtime_action"])
        self.assertFalse(payload["web_write_enabled"])
        self.assertFalse(payload["configuration_write_enabled"])
        self.assertFalse(payload["business_data_write_enabled"])
        self.assertEqual(payload["data"]["attempt_count"], 1)
        self.assertFalse(payload["data"]["runtime_feature_enabled"])
        self.assertEqual(
            payload["data"]["code"],
            "project_doc_rag_probe_succeeded",
        )
        rendered = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn(manual.PROJECT_DOC_RAG_PROBE_QUERY, rendered)
        self.assertNotIn("private-to-the-probe-content", rendered)

    def test_cloud_vision_fastapi_routes_use_fixed_security_contract_without_reruns(self):
        manual = self.manual
        executor_calls: list[int] = []

        def execute_cloud_vision():
            executor_calls.append(len(executor_calls) + 1)
            return self.cloud_vision_evidence()

        runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            vision_inference_enabled=False,
            cloud_vision_enabled=True,
            cloud_vision_executor=execute_cloud_vision,
            cloud_vision_reference_loader=self.vision_reference_asset,
        )
        app = self.fastapi.create_owner_console_fastapi_app(
            manual_diagnostics_runtime=runtime,
            action_session_token="test-action-session",
        )
        client = TestClient(app, base_url="http://127.0.0.1:8090")
        path = (
            "/api/v1/owner-console/manual-diagnostics/"
            "cloud-vision-fixed-description"
        )
        confirmation = {
            "confirmation": "run_registered_cloud_vision_fixed_description"
        }
        headers = {
            "Origin": "http://127.0.0.1:8090",
            "X-Owner-Console-Action": (
                "manual-cloud-vision-fixed-description-v1"
            ),
        }

        self.assertEqual(
            client.post(path, headers=headers, json=confirmation).status_code,
            403,
        )
        self.assertEqual(executor_calls, [])

        state = client.get(
            "/api/v1/owner-console/manual-diagnostics"
        ).json()["data"]
        self.assertTrue(state["cloud_vision_enabled"])
        self.assertFalse(state["vision_inference_enabled"])
        self.assertIn("owner_console_action_session", client.cookies)

        self.assertEqual(
            client.post(
                path,
                headers={
                    "X-Owner-Console-Action": (
                        "manual-cloud-vision-fixed-description-v1"
                    )
                },
                json=confirmation,
            ).status_code,
            403,
        )
        self.assertEqual(
            client.post(
                path,
                headers={
                    "Origin": "http://127.0.0.1:8090",
                    "X-Owner-Console-Action": "wrong-action",
                },
                json=confirmation,
            ).status_code,
            403,
        )
        for bad_body in (
            {"confirmation": "wrong"},
            {**confirmation, "image": "forbidden"},
            {**confirmation, "prompt": "forbidden"},
        ):
            with self.subTest(body=bad_body):
                self.assertEqual(
                    client.post(path, headers=headers, json=bad_body).status_code,
                    400,
                )
        self.assertEqual(executor_calls, [])

        first_response = client.post(path, headers=headers, json=confirmation)
        self.assertEqual(first_response.status_code, 200)
        first = first_response.json()["data"]
        self.assertEqual(executor_calls, [1])
        self.assertEqual(first["workflow"], "cloud_vision_fixed_description")
        self.assertEqual(first["stage"], "owner_visual_review")
        self.assertEqual(first["request_count"], 1)
        self.assertTrue(first["external_image_upload_executed"])
        self.assertFalse(first["local_vision_called"])

        preview_path = f"{path}/reference-preview"
        self.assertEqual(client.get(preview_path).status_code, 403)
        preview = client.get(
            preview_path,
            headers={
                "X-Owner-Console-Action": (
                    "manual-cloud-vision-reference-preview-v1"
                )
            },
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.headers["content-type"], "image/png")
        self.assertEqual(preview.headers["cache-control"], "no-store, max-age=0")
        self.assertEqual(preview.content, self.vision_reference_asset().content)
        self.assertEqual(executor_calls, [1])

        accept_path = f"{path}/response-quality/accept"
        accept_body = {
            "confirmation": "accept_latest_cloud_vision_response_quality",
            "run_id": first["run_id"],
        }
        self.assertEqual(
            client.post(accept_path, json=accept_body).status_code,
            403,
        )
        accepted_response = client.post(
            accept_path,
            headers={
                "Origin": "http://127.0.0.1:8090",
                "X-Owner-Console-Action": (
                    "manual-cloud-vision-response-quality-accept-v1"
                ),
            },
            json=accept_body,
        )
        self.assertEqual(accepted_response.status_code, 200)
        accepted = accepted_response.json()["data"]
        self.assertTrue(accepted["visual_quality_reviewed"])
        self.assertTrue(accepted["visual_quality_accepted"])
        self.assertEqual(executor_calls, [1])

        second_response = client.post(path, headers=headers, json=confirmation)
        self.assertEqual(second_response.status_code, 200)
        second = second_response.json()["data"]
        self.assertEqual(executor_calls, [1, 2])

        reject_path = f"{path}/response-quality/reject"
        rejected_response = client.post(
            reject_path,
            headers={
                "Origin": "http://127.0.0.1:8090",
                "X-Owner-Console-Action": (
                    "manual-cloud-vision-response-quality-reject-v1"
                ),
            },
            json={
                "confirmation": "reject_latest_cloud_vision_response_quality",
                "run_id": second["run_id"],
            },
        )
        self.assertEqual(rejected_response.status_code, 200)
        rejected = rejected_response.json()["data"]
        self.assertTrue(rejected["visual_quality_reviewed"])
        self.assertFalse(rejected["visual_quality_accepted"])
        self.assertEqual(executor_calls, [1, 2])

    def test_cloud_vision_replaces_local_ui_workflow_and_requires_owner_review(self):
        manual = self.manual
        runtime = manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True,
            project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None,
            vision_inference_enabled=False,
            cloud_vision_enabled=True,
            cloud_vision_executor=self.cloud_vision_evidence,
            cloud_vision_reference_loader=self.vision_reference_asset,
        )

        snapshot = runtime.build_snapshot()
        self.assertFalse(snapshot.vision_inference_enabled)
        self.assertTrue(snapshot.cloud_vision_enabled)
        self.assertEqual(
            snapshot.supported_workflows,
            ["cloud_vision_fixed_description"],
        )

        result = runtime.run_cloud_vision_fixed_description()
        self.assertEqual(result.outcome, "attention")
        self.assertEqual(result.stage, "owner_visual_review")
        self.assertEqual(
            result.code,
            "cloud_vision_response_quality_review_required",
        )
        self.assertTrue(result.external_image_upload_executed)
        self.assertTrue(result.response_cleanup_applied)
        self.assertEqual(result.request_count, 1)
        self.assertFalse(result.client_automatic_retry)
        self.assertFalse(result.local_vision_called)
        self.assertEqual(
            runtime.read_cloud_vision_reference_preview(),
            self.vision_reference_asset().content,
        )

        accepted = runtime.review_cloud_vision_response_quality(
            result.run_id,
            accepted=True,
        )
        self.assertEqual(accepted.outcome, "succeeded")
        self.assertEqual(
            accepted.code,
            "cloud_vision_fixed_description_succeeded",
        )
        self.assertTrue(accepted.visual_quality_reviewed)
        self.assertTrue(accepted.visual_quality_accepted)
        with self.assertRaises(manual.OwnerConsoleCloudVisionReviewUnavailable):
            runtime.review_cloud_vision_response_quality(
                result.run_id,
                accepted=True,
            )


if __name__ == "__main__":
    unittest.main()
