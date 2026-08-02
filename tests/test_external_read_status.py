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

    def test_synthesis_error_parser_accepts_specific_safe_rejection_categories(self):
        for category in ("request_too_large", "content_policy_rejected"):
            with self.subTest(category=category):
                match = self.status._SYNTHESIS_ERROR_PATTERN.fullmatch(
                    f"综合错误：{category}。"
                )
                self.assertIsNotNone(match)
                self.assertEqual(match.group(1), category)

    def test_synthesis_status_parser_accepts_incomplete_scene_evidence(self):
        match = self.status._SYNTHESIS_STATUS_PATTERN.fullmatch(
            "综合状态：not_run_incomplete_evidence。"
        )

        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "not_run_incomplete_evidence")

    def test_latest_snapshot_reads_only_matching_owner_external_task_metadata(self):
        temp_dir, path, connection = self.database()
        safe_result = "\n".join(
            [
                "外部只读查询已完成。",
                "Provider：tavily。",
                "结果数：3。",
                "来源主机数：2。",
                "丢弃结果数：1。",
                "Provider候选数：4。",
                "官方正文强日期数：1。",
                "检索阶段数：1。",
                "规划模式：main_agent。",
                "业务场景：recommendation。",
                "第一阶段来源：general。",
                "第二阶段来源：none。",
                "第二阶段条件：none。",
                "官方阶段候选数：4。",
                "官方阶段合格数：3。",
                "媒体阶段候选数：0。",
                "媒体阶段合格数：0。",
                "日期缺失丢弃：1。",
                "窗口外丢弃：0。",
                "仅弱日期丢弃：0。",
                "日期冲突丢弃：0。",
                "注入嫌疑丢弃：0。",
                "清洗去重丢弃：0。",
                "来源策略丢弃：0。",
                "外部请求：1。",
                "Provider请求：1。",
                "综合请求：1。",
                "综合状态：completed。",
                "综合错误：none。",
                "主人质量：owner_quality_pending。",
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
        self.assertEqual(snapshot.provider_candidate_count, 4)
        self.assertEqual(snapshot.official_content_strong_count, 1)
        self.assertEqual(snapshot.search_stage_count, 1)
        self.assertEqual(snapshot.planning_mode, "main_agent")
        self.assertEqual(snapshot.scene, "recommendation")
        self.assertEqual(snapshot.primary_source_scope, "general")
        self.assertEqual(snapshot.secondary_source_scope, "none")
        self.assertEqual(snapshot.secondary_mode, "none")
        self.assertEqual(snapshot.official_stage_candidate_count, 4)
        self.assertEqual(snapshot.official_stage_result_count, 3)
        self.assertEqual(snapshot.media_stage_candidate_count, 0)
        self.assertEqual(snapshot.media_stage_result_count, 0)
        self.assertEqual(snapshot.dropped_missing_date_count, 1)
        self.assertEqual(snapshot.dropped_outside_window_count, 0)
        self.assertEqual(snapshot.dropped_weak_only_count, 0)
        self.assertEqual(snapshot.dropped_conflicting_date_count, 0)
        self.assertEqual(snapshot.dropped_injection_count, 0)
        self.assertEqual(snapshot.dropped_sanitization_count, 0)
        self.assertEqual(snapshot.dropped_source_policy_count, 0)
        self.assertEqual(snapshot.external_request_count, 1)
        self.assertEqual(snapshot.provider_request_count, 1)
        self.assertEqual(snapshot.synthesis_request_count, 1)
        self.assertEqual(snapshot.synthesis_status, "completed")
        self.assertEqual(snapshot.synthesis_error_category, "none")
        self.assertEqual(snapshot.owner_quality_status, "owner_quality_pending")
        self.assertEqual(snapshot.status_category, "completed")
        lines = "\n".join(self.status.external_read_task_snapshot_lines(snapshot))
        self.assertIn("最近正式任务：#1", lines)
        self.assertIn("最近 Provider：tavily", lines)
        self.assertIn("最近 Provider 候选数：4", lines)
        self.assertIn("最近官方正文强日期数：1", lines)
        self.assertIn("最近检索阶段数：1", lines)
        self.assertIn("最近业务场景：recommendation", lines)
        self.assertIn("最近第一阶段合格数：3", lines)
        self.assertIn("最近来源策略丢弃：0", lines)
        self.assertIn("最近日期缺失丢弃：1", lines)
        self.assertNotIn("must-not-leak", lines)
        self.assertNotIn("query=", lines)

    def test_owner_can_accept_or_reject_only_pending_owned_completed_result(self):
        temp_dir, path, connection = self.database()
        pending = (
            "外部只读查询已完成。 Provider：tavily。 结果数：3。 "
            "主人质量：owner_quality_pending。"
        )
        with temp_dir:
            connection.executemany(
                """
                INSERT INTO agent_tasks
                    (id, session_key, user_id, title, status, result, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (7, "private:10001", "10001", "外部只读查询报告", "done", pending, "2026-07-12T06:00:00+00:00"),
                    (8, "private:other", "other", "外部只读查询报告", "done", pending, "2026-07-12T06:00:00+00:00"),
                ),
            )
            connection.commit()
            connection.close()

            accepted = self.status.review_external_read_task_quality(
                task_id=7,
                session_key="private:10001",
                user_id="10001",
                accepted=True,
                database_path=path,
            )
            repeated = self.status.review_external_read_task_quality(
                task_id=7,
                session_key="private:10001",
                user_id="10001",
                accepted=False,
                database_path=path,
            )
            foreign = self.status.review_external_read_task_quality(
                task_id=8,
                session_key="private:10001",
                user_id="10001",
                accepted=False,
                database_path=path,
            )
            snapshot = self.status.latest_external_read_task_snapshot(
                session_key="private:10001",
                user_id="10001",
                database_path=path,
            )

        self.assertEqual(accepted.status, "owner_accepted")
        self.assertTrue(accepted.changed)
        self.assertEqual(repeated.status, "owner_accepted")
        self.assertFalse(repeated.changed)
        self.assertEqual(foreign.status, "not_found")
        self.assertEqual(snapshot.owner_quality_status, "owner_accepted")

    def test_quality_review_command_parser_is_strict(self):
        accepted = self.status.parse_external_read_quality_review_command(
            "接受联网结果 #42"
        )
        rejected = self.status.parse_external_read_quality_review_command(
            "拒绝联网结果 43"
        )

        self.assertEqual((accepted.accepted, accepted.task_id), (True, 42))
        self.assertEqual((rejected.accepted, rejected.task_id), (False, 43))
        self.assertIsNone(
            self.status.parse_external_read_quality_review_command("接受这个结果")
        )

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

    def test_failed_snapshot_exposes_safe_stage_and_request_counts(self):
        temp_dir, path, connection = self.database()
        result = (
            "失败检索阶段：media_fallback。检索阶段数：2。外部请求：2。"
            "Provider请求：2。综合请求：0。"
            "ExternalReadPolicyError: external_read_report execution failed "
            "(response_too_large)."
        )
        with temp_dir:
            connection.execute(
                """
                INSERT INTO agent_tasks
                    (id, session_key, user_id, title, status, result, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (5, "private:10001", "10001", "外部只读查询报告", "failed", result, "2026-07-30T06:19:40+00:00"),
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
        self.assertEqual(snapshot.error_category, "response_too_large")
        self.assertEqual(snapshot.failed_search_stage, "media_fallback")
        self.assertEqual(snapshot.search_stage_count, 2)
        self.assertEqual(snapshot.external_request_count, 2)
        self.assertEqual(snapshot.provider_request_count, 2)
        self.assertEqual(snapshot.synthesis_request_count, 0)
        lines = "\n".join(self.status.external_read_task_snapshot_lines(snapshot))
        self.assertIn("最近失败检索阶段：media_fallback", lines)
        self.assertIn("最近 Provider 请求：2", lines)
        self.assertIn("最近综合请求：0", lines)

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
        self.assertIsNone(snapshot.provider_candidate_count)
        self.assertIsNone(snapshot.official_content_strong_count)
        self.assertIsNone(snapshot.search_stage_count)
        self.assertEqual(snapshot.scene, "")
        self.assertIsNone(snapshot.official_stage_candidate_count)
        self.assertIsNone(snapshot.official_stage_result_count)
        self.assertIsNone(snapshot.media_stage_candidate_count)
        self.assertIsNone(snapshot.media_stage_result_count)
        self.assertIsNone(snapshot.dropped_missing_date_count)
        self.assertIsNone(snapshot.dropped_outside_window_count)
        self.assertIsNone(snapshot.dropped_weak_only_count)
        self.assertIsNone(snapshot.dropped_conflicting_date_count)
        self.assertIsNone(snapshot.dropped_injection_count)
        self.assertIsNone(snapshot.dropped_sanitization_count)
        self.assertIsNone(snapshot.dropped_source_policy_count)

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
