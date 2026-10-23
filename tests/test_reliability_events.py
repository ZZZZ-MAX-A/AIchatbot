from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from pure_ai_chat_loader import load_reliability_event_modules


RUNTIME_A = "11111111-1111-4111-8111-111111111111"
RUNTIME_B = "22222222-2222-4222-8222-222222222222"
RUNTIME_C = "33333333-3333-4333-8333-333333333333"


def at(hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 7, 18, hour, minute, second, tzinfo=UTC)


class ReliabilityEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_reliability_event_modules()
        cls.database = cls.modules["database"]
        cls.reliability = cls.modules["reliability_events"]

    def temp_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "chatbot.db"
        patcher = patch.object(self.database, "DATABASE_PATH", db_path)
        return temp_dir, db_path, patcher

    def event(
        self,
        *,
        code: str = "request_timeout",
        outcome: str = "failed",
        category: str | None = "network",
        occurred_at: datetime | None = None,
        runtime_id: str = RUNTIME_A,
        component: str = "sticker_classifier",
        operation: str = "classify_intent",
    ):
        return self.reliability.create_reliability_event(
            component=component,
            operation=operation,
            category=category,
            code=code,
            outcome=outcome,
            occurred_at=occurred_at or at(10),
            runtime_id=runtime_id,
        )

    def test_contract_accepts_registered_failure_and_success(self):
        failure = self.event()
        success = self.event(
            code="operation_succeeded",
            outcome="succeeded",
            category=None,
        )

        self.assertEqual(failure.category.value, "network")
        self.assertEqual(failure.code, "request_timeout")
        self.assertEqual(success.outcome.value, "succeeded")
        self.assertIsNone(success.category)

    def test_encyclopedia_statuses_persist_by_persona_without_query_content(self):
        temp_dir, db_path, patcher = self.temp_database()
        with temp_dir, patcher:
            self.database.ensure_database()
            for role in ("aike", "linyin"):
                for status in (
                    "found", "partial", "not_found", "no_content", "planner_timeout", "lookup_timeout",
                    "planner_empty_response", "planner_response_truncated", "planner_invalid_response",
                    "planner_error", "lookup_error", "invalid_arguments", "source_unavailable",
                ):
                    self.assertTrue(self.reliability.record_encyclopedia_observation_safely(
                        {"encyclopedia_status": status, "query": "PRIVATE-QUERY", "results": "PRIVATE-PAGE", "account": "PRIVATE-ID"}, role,
                    ))
            self.assertFalse(self.reliability.record_encyclopedia_observation_safely({"encyclopedia_status": "found"}, "PRIVATE-ID"))
            self.assertFalse(self.reliability.record_encyclopedia_observation_safely({"encyclopedia_status": "PRIVATE-ERROR"}, "aike"))
            for status in ("disabled", "not_needed", "not_requested", "skipped"):
                self.assertFalse(self.reliability.record_encyclopedia_observation_safely({"encyclopedia_status": status}, "aike"))
            with self.database.connect() as connection:
                rows = connection.execute("SELECT component, operation, code, outcome FROM reliability_event_buckets").fetchall()
            self.assertEqual(len(rows), 26)
            self.assertEqual({row[1] for row in rows}, {"aike_query", "linyin_query"})
            self.assertNotIn("PRIVATE", str(rows))

    def test_encyclopedia_recorder_storage_failure_does_not_interrupt_chat(self):
        with patch.object(self.reliability, "record_reliability_event", side_effect=RuntimeError("database offline")):
            self.assertFalse(self.reliability.record_encyclopedia_observation_safely({"encyclopedia_status": "lookup_timeout"}, "linyin"))

    def create_legacy_reliability_table(self, connection):
        connection.execute("""CREATE TABLE reliability_event_buckets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, schema_version INTEGER NOT NULL,
            bucket_start TEXT NOT NULL, runtime_id TEXT NOT NULL, component TEXT NOT NULL,
            operation TEXT NOT NULL, category TEXT NOT NULL, code TEXT NOT NULL,
            outcome TEXT NOT NULL, occurrence_count INTEGER NOT NULL,
            first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
            CHECK (component = 'chat_llm' AND operation = 'generate_reply'),
            UNIQUE (bucket_start, runtime_id, component, operation, category, code, outcome)
        )""")
        connection.execute("CREATE INDEX idx_reliability_event_buckets_window ON reliability_event_buckets (last_seen_at, component, operation)")
        connection.execute("""INSERT INTO reliability_event_buckets VALUES
            (71, 1, ?, ?, 'chat_llm', 'generate_reply', 'network', 'request_timeout', 'failed', 9, ?, ?)""",
            (at(10).isoformat(), RUNTIME_A, at(10).isoformat(), at(10, 4).isoformat()))
        connection.execute("UPDATE sqlite_sequence SET seq = 400 WHERE name = 'reliability_event_buckets'")

    def test_legacy_diagnostic_schema_upgrade_preserves_rows_sequence_and_is_idempotent(self):
        temp_dir, _db_path, patcher = self.temp_database()
        with temp_dir, patcher:
            with self.database.connect() as connection:
                self.create_legacy_reliability_table(connection)
                before = tuple(connection.execute("SELECT * FROM reliability_event_buckets").fetchone())
                connection.execute("CREATE TABLE untouched_memory (content TEXT)")
                connection.execute("INSERT INTO untouched_memory VALUES ('test-private-text')")
            self.database.ensure_database()
            with self.database.connect() as connection:
                self.assertEqual(tuple(connection.execute("SELECT * FROM reliability_event_buckets").fetchone()), before)
                self.assertEqual(connection.execute("SELECT seq FROM sqlite_sequence WHERE name = 'reliability_event_buckets'").fetchone()[0], 400)
                self.assertEqual(connection.execute("SELECT content FROM untouched_memory").fetchone()[0], "test-private-text")
                statements = []
                connection.set_trace_callback(statements.append)
                self.database._ensure_reliability_event_schema(connection)
                self.assertFalse(any("ALTER TABLE" in statement for statement in statements))
                indexes = {row[1] for row in connection.execute("PRAGMA index_list(reliability_event_buckets)")}
                self.assertIn("idx_reliability_event_buckets_window", indexes)
                self.assertIn("idx_reliability_event_buckets_runtime", indexes)
            self.assertTrue(self.reliability.record_encyclopedia_observation_safely({"encyclopedia_status": "found"}, "linyin"))
            with self.database.connect() as connection:
                self.assertEqual(connection.execute("SELECT MAX(id) FROM reliability_event_buckets").fetchone()[0], 401)

    def test_legacy_upgrade_rolls_back_if_copy_fails(self):
        temp_dir, _db_path, patcher = self.temp_database()
        with temp_dir, patcher:
            with self.database.connect() as connection:
                self.create_legacy_reliability_table(connection)
                connection.execute("UPDATE reliability_event_buckets SET code = 'old_unknown_code'")
                before_sql = connection.execute("SELECT sql FROM sqlite_master WHERE name = 'reliability_event_buckets'").fetchone()[0]
                with self.assertRaises(sqlite3.IntegrityError):
                    self.database._ensure_reliability_event_schema(connection)
                self.assertEqual(connection.execute("SELECT sql FROM sqlite_master WHERE name = 'reliability_event_buckets'").fetchone()[0], before_sql)
                self.assertEqual(connection.execute("SELECT id, code FROM reliability_event_buckets").fetchone()[:], (71, "old_unknown_code"))
                self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name = 'reliability_event_buckets_previous'").fetchone())

    def test_contract_rejects_unknown_or_mismatched_values(self):
        invalid_cases = (
            {"component": "user:12345", "operation": "classify_intent"},
            {"component": "sticker_classifier", "operation": "D:/private/file"},
            {"category": "model", "code": "request_timeout"},
            {"category": "network", "code": "unknown_exception"},
            {
                "category": None,
                "code": "operation_succeeded",
                "outcome": "failed",
            },
            {"runtime_id": "not-a-runtime-id"},
        )

        for changes in invalid_cases:
            kwargs = {
                "component": "sticker_classifier",
                "operation": "classify_intent",
                "category": "network",
                "code": "request_timeout",
                "outcome": "failed",
                "occurred_at": at(10),
                "runtime_id": RUNTIME_A,
            }
            kwargs.update(changes)
            with self.subTest(changes=changes):
                with self.assertRaises(self.reliability.ReliabilityEventContractError):
                    self.reliability.create_reliability_event(**kwargs)

    def test_contract_rejects_naive_timestamp_and_extra_field(self):
        with self.assertRaises(self.reliability.ReliabilityEventContractError):
            self.reliability.create_reliability_event(
                component="main_llm",
                operation="plan_action",
                category=None,
                code="operation_succeeded",
                outcome="succeeded",
                occurred_at=datetime(2026, 7, 18, 10, 0, 0),
                runtime_id=RUNTIME_A,
            )
        with self.assertRaises(TypeError):
            self.reliability.create_reliability_event(
                component="main_llm",
                operation="plan_action",
                category=None,
                code="operation_succeeded",
                outcome="succeeded",
                occurred_at=at(10),
                runtime_id=RUNTIME_A,
                message="private user text",
            )

    def test_five_minute_bucket_deduplicates_without_losing_count(self):
        temp_dir, _db_path, patcher = self.temp_database()
        with temp_dir, patcher:
            for occurred_at in (at(10, 1), at(10, 2), at(10, 6)):
                self.reliability.record_reliability_event(
                    self.event(occurred_at=occurred_at)
                )
            with self.database.connect() as connection:
                rows = connection.execute(
                    "SELECT * FROM reliability_event_buckets ORDER BY bucket_start"
                ).fetchall()
            summary = self.reliability.read_reliability_trend(
                window_hours=24,
                now=at(11),
            )

        self.assertEqual(len(rows), 2)
        self.assertEqual([row["occurrence_count"] for row in rows], [2, 1])
        self.assertEqual(summary.failure_occurrence_count, 3)
        self.assertEqual(summary.items[0].occurrence_count, 3)

    def test_recovery_and_recurring_are_derived_from_event_order(self):
        temp_dir, _db_path, patcher = self.temp_database()
        with temp_dir, patcher:
            self.reliability.record_reliability_event(self.event(occurred_at=at(10, 0)))
            self.reliability.record_reliability_event(
                self.event(
                    code="operation_succeeded",
                    outcome="succeeded",
                    category=None,
                    occurred_at=at(10, 6),
                )
            )
            recovered = self.reliability.read_reliability_trend(now=at(10, 7))
            self.reliability.record_reliability_event(self.event(occurred_at=at(10, 11)))
            recurring = self.reliability.read_reliability_trend(now=at(10, 12))
            self.reliability.record_reliability_event(
                self.event(
                    code="operation_succeeded",
                    outcome="succeeded",
                    category=None,
                    occurred_at=at(10, 16),
                )
            )
            recovered_again = self.reliability.read_reliability_trend(now=at(10, 17))

        self.assertEqual(recovered.items[0].recovery_state.value, "recovered")
        self.assertEqual(recurring.items[0].recovery_state.value, "recurring")
        self.assertEqual(recovered_again.items[0].recovery_state.value, "recovered")

    def test_skipped_event_does_not_recover_failure(self):
        temp_dir, _db_path, patcher = self.temp_database()
        with temp_dir, patcher:
            self.reliability.record_reliability_event(self.event(occurred_at=at(10)))
            self.reliability.record_reliability_event(
                self.event(
                    code="operation_skipped",
                    outcome="skipped",
                    category=None,
                    occurred_at=at(10, 6),
                )
            )
            summary = self.reliability.read_reliability_trend(now=at(10, 7))

        self.assertEqual(summary.items[0].recovery_state.value, "unresolved")
        self.assertIsNone(summary.items[0].last_success_at)

    def test_lifecycle_marks_only_unclosed_previous_runtime_as_suspected(self):
        temp_dir, _db_path, patcher = self.temp_database()
        with temp_dir, patcher:
            first = self.reliability.begin_runtime_lifecycle(
                runtime_id=RUNTIME_A,
                occurred_at=at(9),
            )
            second = self.reliability.begin_runtime_lifecycle(
                runtime_id=RUNTIME_B,
                occurred_at=at(10),
            )
            self.reliability.finish_runtime_lifecycle(
                runtime_id=RUNTIME_B,
                occurred_at=at(11),
            )
            third = self.reliability.begin_runtime_lifecycle(
                runtime_id=RUNTIME_C,
                occurred_at=at(12),
            )
            with self.database.connect() as connection:
                suspected = connection.execute(
                    """
                    SELECT runtime_id, occurrence_count
                    FROM reliability_event_buckets
                    WHERE code = 'suspected_abnormal_exit'
                    """
                ).fetchall()

        self.assertIsNone(first.suspected_previous_runtime_id)
        self.assertEqual(second.suspected_previous_runtime_id, RUNTIME_A)
        self.assertIsNone(third.suspected_previous_runtime_id)
        self.assertEqual([(row["runtime_id"], row["occurrence_count"]) for row in suspected], [(RUNTIME_A, 1)])

    def test_table_has_only_reviewed_low_sensitivity_columns(self):
        temp_dir, db_path, patcher = self.temp_database()
        with temp_dir, patcher:
            self.database.ensure_database()
            connection = sqlite3.connect(db_path)
            try:
                columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(reliability_event_buckets)"
                    )
                }
            finally:
                connection.close()

        self.assertEqual(
            columns,
            {
                "id",
                "schema_version",
                "bucket_start",
                "runtime_id",
                "component",
                "operation",
                "category",
                "code",
                "outcome",
                "occurrence_count",
                "first_seen_at",
                "last_seen_at",
            },
        )
        forbidden_fragments = {
            "user",
            "qq",
            "session",
            "message",
            "content",
            "path",
            "url",
            "key",
            "stack",
            "exception",
            "metadata",
        }
        self.assertFalse(columns & forbidden_fragments)

    def test_database_checks_reject_unregistered_direct_sql_values(self):
        temp_dir, _db_path, patcher = self.temp_database()
        with temp_dir, patcher:
            self.database.ensure_database()
            with self.assertRaises(sqlite3.IntegrityError):
                with self.database.connect() as connection:
                    connection.execute(
                        """
                        INSERT INTO reliability_event_buckets (
                            schema_version, bucket_start, runtime_id,
                            component, operation, category, code, outcome,
                            occurrence_count, first_seen_at, last_seen_at
                        )
                        VALUES (1, ?, ?, ?, ?, '', 'operation_succeeded',
                                'succeeded', 1, ?, ?)
                        """,
                        (
                            at(10).isoformat(),
                            RUNTIME_A,
                            "user:12345",
                            "D:/private/file",
                            at(10).isoformat(),
                            at(10).isoformat(),
                        ),
                    )

    def test_safe_recorder_never_raises_into_business_path(self):
        with patch.object(
            self.reliability,
            "record_reliability_event",
            side_effect=RuntimeError("database unavailable with private details"),
        ):
            recorded = self.reliability.record_failure_safely(
                "main_llm",
                "plan_action",
                RuntimeError("api_key=secret https://private.invalid"),
            )

        self.assertFalse(recorded)

    def test_raw_error_text_is_classified_in_memory_but_never_persisted(self):
        temp_dir, db_path, patcher = self.temp_database()
        secret = "api_key=sk-private-secret https://private.invalid user=12345"
        with temp_dir, patcher:
            recorded = self.reliability.record_failure_safely(
                "main_llm",
                "plan_action",
                RuntimeError(f"request timeout {secret}"),
                occurred_at=at(10),
                runtime_id=RUNTIME_A,
            )
            raw_database = db_path.read_bytes()
            with self.database.connect() as connection:
                row = connection.execute(
                    "SELECT component, operation, category, code, outcome "
                    "FROM reliability_event_buckets"
                ).fetchone()

        self.assertTrue(recorded)
        self.assertNotIn(secret.encode("utf-8"), raw_database)
        self.assertNotIn(b"sk-private-secret", raw_database)
        self.assertEqual(
            tuple(row),
            ("main_llm", "plan_action", "network", "request_timeout", "failed"),
        )

    def test_no_failure_trend_report_is_read_only_and_does_not_claim_uptime(self):
        temp_dir, _db_path, patcher = self.temp_database()
        with temp_dir, patcher:
            self.database.ensure_database()
            recent = self.reliability.read_reliability_trend(
                window_hours=24,
                now=at(12),
            )
            weekly = self.reliability.read_reliability_trend(
                window_hours=24 * 7,
                now=at(12),
            )
            report = self.reliability.format_reliability_trend_report(recent, weekly)

        self.assertIn("结构化故障趋势（只读）", report)
        self.assertIn("当前窗口内未发现结构化失败或降级事件", report)
        self.assertIn("不等于已证明系统持续在线", report)
        self.assertIn("未调用 Main LLM、Tavily、RAG 或外部模型", report)

    def test_failure_trend_report_shows_group_and_recovery_without_sensitive_values(self):
        temp_dir, _db_path, patcher = self.temp_database()
        with temp_dir, patcher:
            self.reliability.record_failure_safely(
                "sticker_classifier",
                "classify_intent",
                RuntimeError("request timeout api_key=sk-secret https://private.invalid"),
                occurred_at=at(10),
                runtime_id=RUNTIME_A,
            )
            self.reliability.record_success_safely(
                "sticker_classifier",
                "classify_intent",
                occurred_at=at(10, 6),
                runtime_id=RUNTIME_A,
            )
            recent = self.reliability.read_reliability_trend(
                window_hours=24,
                now=at(12),
            )
            weekly = self.reliability.read_reliability_trend(
                window_hours=24 * 7,
                now=at(12),
            )
            report = self.reliability.format_reliability_trend_report(recent, weekly)

        self.assertIn("sticker_classifier / classify_intent", report)
        self.assertIn("网络问题 / request_timeout", report)
        self.assertIn("已恢复", report)
        self.assertNotIn(RUNTIME_A, report)
        self.assertNotIn("sk-secret", report)
        self.assertNotIn("private.invalid", report)

    def test_lifecycle_trend_keeps_success_as_insufficient_evidence_without_displaying_recovery(self):
        temp_dir, _db_path, patcher = self.temp_database()
        with temp_dir, patcher:
            self.reliability.begin_runtime_lifecycle(
                runtime_id=RUNTIME_A,
                occurred_at=at(9),
            )
            self.reliability.begin_runtime_lifecycle(
                runtime_id=RUNTIME_B,
                occurred_at=at(10),
            )
            recent = self.reliability.read_reliability_trend(
                window_hours=24,
                now=at(12),
            )
            weekly = self.reliability.read_reliability_trend(
                window_hours=168,
                now=at(12),
            )
            report = self.reliability.format_reliability_trend_report(recent, weekly)

        self.assertIn("suspected_abnormal_exit", report)
        self.assertIn("证据不足", report)
        self.assertNotIn("最近成功", report)


if __name__ == "__main__":
    unittest.main()
