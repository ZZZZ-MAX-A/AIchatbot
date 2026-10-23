from __future__ import annotations

from contextlib import ExitStack, closing
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import sqlite3
import tempfile
from threading import Barrier, Event
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pure_ai_chat_loader import AI_CHAT_ROOT, load_legacy_memory_modules, load_module


class MemoryMaintenanceScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = load_legacy_memory_modules()
        cls.db = cls.modules["database"]
        cls.config_module = load_module("src.plugins.ai_chat.config", AI_CHAT_ROOT / "config.py")
        cls.maintenance = load_module("src.plugins.ai_chat.memory_maintenance", AI_CHAT_ROOT / "memory_maintenance.py")
        cls.persona_db = load_module("src.plugins.ai_chat.persona_memory_scope", AI_CHAT_ROOT / "persona_memory_scope.py")
        cls.api = load_module("src.plugins.ai_chat.owner_console_fastapi_app", AI_CHAT_ROOT / "owner_console_fastapi_app.py")
        cls.manual = load_module("src.plugins.ai_chat.owner_console_manual_diagnostics", AI_CHAT_ROOT / "owner_console_manual_diagnostics.py")
        cls.documents = load_module("src.plugins.ai_chat.rag.documents", AI_CHAT_ROOT / "rag/documents.py")
        cls.read_runtime = load_module("src.plugins.ai_chat.owner_console_read_runtime", AI_CHAT_ROOT / "owner_console_read_runtime.py")

    def config(self, **overrides):
        values = {
            "BOT_PERSONA_BINDINGS": "2000000001=aike:aike;3000000001=linyin:linyin",
            "ENABLE_PERSONA_ROUTING_V2": "true", "ENABLE_PERSONA_MEMORY_V2": "true",
            "PERSONA_ROUTING_V2_BOT_IDS": "3000000001", "PERSONA_MEMORY_V2_BOT_IDS": "3000000001",
            "ENABLE_MEMORY_RAG": "true", "MEMORY_RAG_INCLUDE_MANUAL_FACTS": "true",
        }
        values.update(overrides)
        return self.config_module.load_config(values)

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(self.db, "DATABASE_PATH", root / "default.db"))
        self.stack.enter_context(patch.object(self.persona_db, "PERSONA_MEMORY_DIR", root / "personas"))
        self.stack.enter_context(patch.object(self.maintenance, "role_card_by_key", side_effect=lambda key: object() if key in {"aike", "linyin"} else None))
        self.cfg = self.config()
        self.stack.enter_context(patch.object(self.api, "load_config", side_effect=lambda: self.cfg))
        self.targets = [self.maintenance.resolve_memory_maintenance_scope(self.cfg, account)
                        for account in ("2000000001", "3000000001")]
        for count, target in enumerate(self.targets, 1):
            with self.db.database_path_scope(target.path):
                self.db.ensure_database()
                for i in range(count):
                    self.modules["memory"].append_message(
                        f"{target.session_namespace if target.storage == 'persona_database' else ''}private:10001",
                        "user", "PRIVATE_CONTENT_SENTINEL", "private", "10001")
                self.documents.upsert_rag_document(namespace="project_doc", source_type="project_file",
                    source_id="shared", title="private project", content="PRIVATE_PROJECT_SENTINEL", visibility="owner_private")
                for i in range(count):
                    self.documents.upsert_rag_document(namespace="semantic_memory", source_type="manual_fact",
                        source_id=str(i + 1), title="private fact", content="PRIVATE_RAG_SENTINEL", visibility="owner_private")
        self.runtime = self.manual.OwnerConsoleManualDiagnosticsRuntime(
            manual_diagnostic_actions_enabled=True, project_doc_rag_probe_enabled=False,
            project_doc_rag_probe_executor=lambda: None, memory_rag_consistency_enabled=True,
            memory_rag_consistency_executor=self.manual.MemoryRagConsistencyExecutor(config_provider=lambda: self.cfg),
        )
        self.client = TestClient(self.api.create_owner_console_fastapi_app(
            manual_diagnostics_runtime=self.runtime, action_session_token="test-memory-session"),
            base_url="http://127.0.0.1:8090")
        self.client.cookies.set(self.api.OWNER_CONSOLE_ACTION_COOKIE, "test-memory-session")

    def query(self, target):
        return {"bot_self_id": target.bot_self_id, "scope_revision": target.revision}

    def run_check(self, target):
        return self.client.post("/api/v1/owner-console/manual-diagnostics/memory-rag-consistency",
            params=self.query(target), headers={"Origin": "http://127.0.0.1:8090",
            self.api.OWNER_CONSOLE_ACTION_HEADER: self.api.MEMORY_RAG_CONSISTENCY_ACTION_HEADER},
            json={"confirmation": self.api.MEMORY_RAG_CONSISTENCY_CONFIRMATION})

    def test_each_account_reads_only_its_library_without_project_document_counts(self):
        for count, target in enumerate(self.targets, 1):
            result = self.client.get("/api/v1/owner-console/memory", params=self.query(target))
            self.assertEqual(result.status_code, 200)
            data = result.json()["data"]
            self.assertEqual(data["memory_scope"], target.as_dict())
            self.assertEqual(data["counts"]["message_count"], count)
            self.assertEqual(data["counts"]["rag_document_count"], count)
            for sentinel in ("PRIVATE_CONTENT_SENTINEL", "PRIVATE_PROJECT_SENTINEL", "PRIVATE_RAG_SENTINEL"):
                self.assertNotIn(sentinel, result.text)
        self.assertEqual(self.db.current_database_path(), self.db.DATABASE_PATH)

    def test_consistency_results_remain_per_account_and_revision(self):
        results = [self.run_check(target) for target in self.targets]
        for count, (target, result) in enumerate(zip(self.targets, results), 1):
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()["data"]["active_document_count"], count)
            snapshot = self.client.get("/api/v1/owner-console/manual-diagnostics", params=self.query(target)).json()["data"]
            latest = snapshot["memory_rag_consistency_latest_run"]
            self.assertEqual(latest["memory_scope"], target.as_dict())
            self.assertEqual(latest["active_document_count"], count)
        self.cfg = self.config(MEMORY_RAG_EMBEDDING_MODEL="different-index-model")
        fresh = self.maintenance.resolve_memory_maintenance_scope(self.cfg, self.targets[0].bot_self_id)
        self.assertIsNone(self.runtime.build_snapshot(memory_scope=fresh).memory_rag_consistency_latest_run)

    def test_diagnostic_memory_evidence_follows_account_and_keeps_other_sections_on_missing_library(self):
        for count, target in enumerate(self.targets, 1):
            result = self.client.get("/api/v1/owner-console/diagnostics", params=self.query(target))
            self.assertEqual(result.status_code, 200)
            section = result.json()["data"]["memory"]
            self.assertTrue(section["ok"])
            self.assertIn(f"message_count={count}", section["display_lines"])
            self.assertIn(f"memory_database={target.database}", section["display_lines"])
            self.assertIn(f"memory_scope_revision={target.revision}", section["display_lines"])
        self.targets[1].path.unlink()
        result = self.client.get("/api/v1/owner-console/diagnostics", params=self.query(self.targets[1]))
        self.assertEqual(result.status_code, 200)
        data = result.json()["data"]
        self.assertFalse(data["memory"]["ok"])
        self.assertTrue(data["vision"]["ok"])
        self.assertFalse(any(line.startswith("message_count=") for line in data["memory"]["display_lines"]))
        self.assertFalse(self.targets[1].path.exists())

    def test_unbound_default_diagnostic_does_not_open_a_library(self):
        self.cfg = self.config(BOT_PERSONA_BINDINGS="3000000001=linyin:linyin")
        with patch.object(self.db, "connect_read_only", side_effect=AssertionError("must not read")):
            result = self.client.get("/api/v1/owner-console/diagnostics")
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()["data"]["memory"]["ok"])

    def test_explicitly_unselected_diagnostic_keeps_other_sections_without_default_read(self):
        with patch.object(self.db, "connect_read_only", side_effect=AssertionError("must not read")):
            result = self.client.get("/api/v1/owner-console/diagnostics?skip_memory=true")
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()["data"]["memory"]["ok"])
        self.assertTrue(result.json()["data"]["vision"]["ok"])
        for query in ("skip_memory=false", "skip_memory=true&skip_memory=true", "skip_memory=true&database=other.db"):
            self.assertEqual(self.client.get("/api/v1/owner-console/diagnostics?" + query).status_code, 400)

    def test_concurrent_statistics_keep_task_local_database_contexts(self):
        barrier = Barrier(2, timeout=10)
        original = self.read_runtime.read_memory_maintenance_counts
        def concurrent_counts():
            barrier.wait()
            return original()
        with patch.object(self.read_runtime, "read_memory_maintenance_counts", side_effect=concurrent_counts), ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.client.get, "/api/v1/owner-console/memory", params=self.query(t)) for t in self.targets]
            for count, future in enumerate(futures, 1):
                result = future.result(timeout=15)
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json()["data"]["counts"]["message_count"], count)
        self.assertEqual(self.db.current_database_path(), self.db.DATABASE_PATH)

    def test_memory_check_preserves_global_mutex_without_cross_account_results(self):
        started, release = Event(), Event()
        executor = self.runtime._memory_consistency_executor
        def blocked():
            started.set()
            if not release.wait(10):
                raise RuntimeError("test timeout")
            return executor()
        with patch.object(self.runtime, "_memory_consistency_executor", side_effect=blocked), ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.run_check, self.targets[0])
            try:
                self.assertTrue(started.wait(10))
                other = self.client.get("/api/v1/owner-console/manual-diagnostics", params=self.query(self.targets[1])).json()["data"]
                self.assertIsNone(other["memory_rag_consistency_latest_run"])
                self.assertEqual(self.run_check(self.targets[1]).status_code, 409)
            finally:
                release.set()
            result = first.result(timeout=15)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()["data"]["active_document_count"], 1)
        self.assertEqual(self.db.current_database_path(), self.db.DATABASE_PATH)

    def test_stale_binding_and_index_configuration_reject_before_any_read(self):
        for overrides in ({"BOT_PERSONA_BINDINGS": "2000000001=aike:aike;3000000001=new_persona:linyin"},
                          {"MEMORY_RAG_EMBEDDING_MODEL": "changed-model"},
                          {"MEMORY_RAG_EMBEDDING_BASE_URL": "http://127.0.0.1:11435"},
                          {"ENABLE_MEMORY_RAG": "false"},
                          {"ENABLE_PERSONA_MEMORY_V2": "false"}):
            with self.subTest(overrides=overrides):
                self.cfg = self.config(**overrides)
                with patch.object(self.db, "connect_read_only", side_effect=AssertionError("must not open DB")):
                    self.assertEqual(self.run_check(self.targets[1]).status_code, 409)
                    self.assertEqual(self.client.get("/api/v1/owner-console/memory", params=self.query(self.targets[1])).status_code, 409)

    def test_unknown_partial_duplicate_or_path_requests_have_no_fallback(self):
        for params, status in (({"bot_self_id": "unbound", "scope_revision": "bad"}, 404),
            ({"bot_self_id": self.targets[0].bot_self_id}, 400),
            ({**self.query(self.targets[0]), "database": "other.db"}, 400),
            ([("bot_self_id", self.targets[0].bot_self_id), ("bot_self_id", self.targets[1].bot_self_id), ("scope_revision", self.targets[0].revision)], 400)):
            with self.subTest(params=params), patch.object(self.db, "connect_read_only", side_effect=AssertionError("must not read")):
                for route in ("memory", "diagnostics", "manual-diagnostics"):
                    self.assertEqual(self.client.get(f"/api/v1/owner-console/{route}", params=params).status_code, status)

    def test_missing_or_incomplete_library_does_not_create_migrate_or_borrow(self):
        target = self.targets[1]
        target.path.unlink()
        self.assertEqual(self.client.get("/api/v1/owner-console/memory", params=self.query(target)).status_code, 409)

        self.assertFalse(target.path.exists())
        target.path.touch()
        with patch.object(self.db, "ensure_database", side_effect=AssertionError("must not migrate")):
            result = self.client.get("/api/v1/owner-console/memory", params=self.query(target))
            self.assertEqual(result.status_code, 409)
        with closing(sqlite3.connect(target.path)) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0], 0)

    def test_link_boundary_is_rejected_before_opening_any_database(self):
        target = self.targets[1]
        with patch.object(Path, "is_symlink", return_value=True), patch.object(self.db, "connect_read_only", side_effect=AssertionError("must not open DB")):
            self.assertEqual(self.client.get("/api/v1/owner-console/memory", params=self.query(target)).status_code, 409)

    def test_stats_and_consistency_use_read_only_sql_and_leave_databases_unchanged(self):
        before = [hashlib.sha256(t.path.read_bytes()).hexdigest() for t in self.targets]
        statements = []
        original = self.db.connect_read_only
        from contextlib import contextmanager
        @contextmanager
        def traced():
            with original() as con:
                con.set_trace_callback(statements.append)
                yield con
        with patch.object(self.db, "connect_read_only", traced), patch.object(self.manual, "connect_read_only", traced), patch.object(self.db, "ensure_database", side_effect=AssertionError("must not initialize")):
            for target in self.targets:
                self.assertEqual(self.client.get("/api/v1/owner-console/memory", params=self.query(target)).status_code, 200)
                self.assertEqual(self.run_check(target).status_code, 200)
        self.assertEqual(before, [hashlib.sha256(t.path.read_bytes()).hexdigest() for t in self.targets])
        for sql in statements:
            self.assertTrue(sql.lstrip().upper().startswith(("SELECT", "PRAGMA")))
            self.assertNotIn("PRIVATE_", sql)

    def test_role_card_failure_and_unconfigured_default_fail_closed(self):
        with patch.object(self.maintenance, "role_card_by_key", return_value=None), patch.object(self.db, "connect_read_only", side_effect=AssertionError("must not read")):
            self.assertEqual(self.run_check(self.targets[0]).status_code, 409)
        self.cfg = self.config(BOT_PERSONA_BINDINGS="3000000001=linyin:linyin")
        self.assertEqual(self.client.get("/api/v1/owner-console/memory").status_code, 409)

    def test_scopes_restore_after_exceptions_and_cannot_redirect_through_a_link(self):
        target = self.targets[1]
        with self.assertRaises(RuntimeError):
            with self.maintenance.memory_maintenance_database_scope(self.cfg, target):
                self.assertEqual(self.db.current_database_path(), target.path)
                raise RuntimeError("test failure")
        self.assertEqual(self.db.current_database_path(), self.db.DATABASE_PATH)
        target.path.unlink()
        try:
            target.path.symlink_to(self.targets[0].path)
        except OSError:
            self.skipTest("file links unavailable on this host")
        self.assertEqual(self.client.get("/api/v1/owner-console/memory", params=self.query(target)).status_code, 409)
