from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from pure_ai_chat_loader import load_external_read_status_module


class ExternalReadStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.status = load_external_read_status_module()

    def database(self):
        temp_dir = tempfile.TemporaryDirectory()
        path = Path(temp_dir.name) / "chatbot.db"
        connection = sqlite3.connect(path)
        connection.execute(
            """
            CREATE TABLE agent_tasks (
                id INTEGER PRIMARY KEY,
                session_key TEXT NOT NULL,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                result TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        return temp_dir, path, connection

    def test_latest_snapshot_reads_only_matching_owner_external_task_metadata(self):
        temp_dir, path, connection = self.database()
        safe_result = "\n".join(
            [
                "外部只读查询已完成。",
                "Provider：tavily。",
                "结果数：3。",
                "来源主机数：2。",
                "丢弃结果数：1。",
                "外部请求：1。",
                "状态类别：completed。",
                "错误类别：none。",
            ]
        )
        with temp_dir:
            connection.executemany(
                """
                INSERT INTO agent_tasks
                    (id, session_key, user_id, title, status, result, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (1, "private:10001", "10001", "外部只读查询报告", "done", safe_result, "2026-07-12T01:00:00+00:00"),
                    (2, "private:other", "other", "外部只读查询报告", "done", "query=must-not-leak", "2026-07-12T02:00:00+00:00"),
                    (3, "private:10001", "10001", "其他任务", "done", "result body", "2026-07-12T03:00:00+00:00"),
                ),
            )
            connection.commit()
            connection.close()

            snapshot = self.status.latest_external_read_task_snapshot(
                session_key="private:10001",
                user_id="10001",
                database_path=path,
            )

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.task_id, 1)
        self.assertEqual(snapshot.provider_name, "tavily")
        self.assertEqual(snapshot.result_count, 3)
        self.assertEqual(snapshot.source_host_count, 2)
        self.assertEqual(snapshot.dropped_result_count, 1)
        self.assertEqual(snapshot.external_request_count, 1)
        self.assertEqual(snapshot.status_category, "completed")
        lines = "\n".join(self.status.external_read_task_snapshot_lines(snapshot))
        self.assertIn("最近正式任务：#1", lines)
        self.assertIn("最近 Provider：tavily", lines)
        self.assertNotIn("must-not-leak", lines)
        self.assertNotIn("query=", lines)

    def test_failed_snapshot_exposes_only_safe_error_category(self):
        temp_dir, path, connection = self.database()
        result = (
            "ExternalReadPolicyError: external_read_report execution failed "
            "(rate_limited)."
        )
        with temp_dir:
            connection.execute(
                """
                INSERT INTO agent_tasks
                    (id, session_key, user_id, title, status, result, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (4, "private:10001", "10001", "外部只读查询报告", "failed", result, "2026-07-12T04:00:00+00:00"),
            )
            connection.commit()
            connection.close()

            snapshot = self.status.latest_external_read_task_snapshot(
                session_key="private:10001",
                user_id="10001",
                database_path=path,
            )

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.task_status, "failed")
        self.assertEqual(snapshot.error_category, "rate_limited")
        lines = "\n".join(self.status.external_read_task_snapshot_lines(snapshot))
        self.assertIn("最近错误类别：rate_limited", lines)

    def test_compacted_work_result_still_parses_safe_metadata(self):
        temp_dir, path, connection = self.database()
        result = (
            "外部只读查询已完成。 Provider：tavily。 结果数：3。 "
            "来源主机数：2。 丢弃结果数：1。 外部请求：1。 "
            "状态类别：completed。 错误类别：none。"
        )
        with temp_dir:
            connection.execute(
                """
                INSERT INTO agent_tasks
                    (id, session_key, user_id, title, status, result, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    6,
                    "private:10001",
                    "10001",
                    "外部只读查询报告",
                    "done",
                    result,
                    "2026-07-12T05:00:00+00:00",
                ),
            )
            connection.commit()
            connection.close()

            snapshot = self.status.latest_external_read_task_snapshot(
                session_key="private:10001",
                user_id="10001",
                database_path=path,
            )

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.provider_name, "tavily")
        self.assertEqual(snapshot.result_count, 3)
        self.assertEqual(snapshot.external_request_count, 1)
        self.assertEqual(snapshot.status_category, "completed")
        self.assertEqual(snapshot.error_category, "none")

    def test_missing_or_invalid_database_returns_no_safe_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.db"
            invalid = Path(directory) / "invalid.db"
            sqlite3.connect(invalid).close()

            self.assertIsNone(
                self.status.latest_external_read_task_snapshot(
                    session_key="private:10001",
                    user_id="10001",
                    database_path=missing,
                )
            )
            self.assertIsNone(
                self.status.latest_external_read_task_snapshot(
                    session_key="private:10001",
                    user_id="10001",
                    database_path=invalid,
                )
            )
            self.assertEqual(
                self.status.external_read_task_snapshot_lines(None),
                ["最近正式任务：无可用安全元数据"],
            )

    def test_corrupt_status_and_timestamp_are_never_echoed(self):
        temp_dir, path, connection = self.database()
        with temp_dir:
            connection.execute(
                """
                INSERT INTO agent_tasks
                    (id, session_key, user_id, title, status, result, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    5,
                    "private:10001",
                    "10001",
                    "外部只读查询报告",
                    "query=must-not-leak",
                    "Provider：tavily。",
                    "Authorization: Bearer must-not-leak",
                ),
            )
            connection.commit()
            connection.close()

            snapshot = self.status.latest_external_read_task_snapshot(
                session_key="private:10001",
                user_id="10001",
                database_path=path,
            )

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.task_status, "unknown")
        self.assertEqual(snapshot.updated_at, "")
        lines = "\n".join(self.status.external_read_task_snapshot_lines(snapshot))
        self.assertNotIn("must-not-leak", lines)
        self.assertNotIn("Authorization", lines)


if __name__ == "__main__":
    unittest.main()
