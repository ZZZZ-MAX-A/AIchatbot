from __future__ import annotations

import json
import re
import sys
import tempfile
import threading
import unittest
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


if __name__ == "__main__":
    unittest.main()
