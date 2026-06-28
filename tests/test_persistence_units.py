from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pure_ai_chat_loader import load_legacy_memory_modules, load_legacy_operation_modules


class TempDatabaseMixin:
    def temp_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "chatbot.db"
        patcher = patch.object(self.database, "DATABASE_PATH", db_path)
        return temp_dir, patcher


class DatabaseSchemaUnitTests(TempDatabaseMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.memory_modules = load_legacy_memory_modules()
        cls.database = cls.memory_modules["database"]

    def test_ensure_database_creates_expected_tables_and_schema_version(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            self.database.ensure_database()
            with self.database.connect() as connection:
                table_rows = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
                schema_row = connection.execute(
                    "SELECT value FROM schema_meta WHERE key = 'schema_version'"
                ).fetchone()

        table_names = {str(row["name"]) for row in table_rows}
        self.assertIn("messages", table_names)
        self.assertIn("long_term_memories", table_names)
        self.assertIn("session_summaries", table_names)
        self.assertIn("gap_scene_summaries", table_names)
        self.assertIn("private_trials", table_names)
        self.assertEqual(schema_row["value"], self.database.SCHEMA_VERSION)


class TrialPersistenceUnitTests(TempDatabaseMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.memory_modules = load_legacy_memory_modules()
        cls.operation_modules = load_legacy_operation_modules()
        cls.database = cls.memory_modules["database"]
        cls.trials = cls.operation_modules["trials"]

    def test_private_trial_counts_round_trip_in_temp_database(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            self.assertEqual(self.trials.private_trial_used("10001"), 0)
            self.assertTrue(self.trials.can_use_private_trial("10001", 2))

            self.trials.increment_private_trial("10001")
            self.trials.increment_private_trial("10001")
            self.trials.increment_private_trial("20002")

            self.assertEqual(self.trials.private_trial_used("10001"), 2)
            self.assertFalse(self.trials.can_use_private_trial("10001", 2))
            self.assertEqual(
                self.trials.trial_stats(),
                {"trial_user_count": 2, "trial_message_count": 3},
            )


class SummaryPersistenceUnitTests(TempDatabaseMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.memory_modules = load_legacy_memory_modules()
        cls.database = cls.memory_modules["database"]
        cls.summaries = cls.memory_modules["summaries"]

    def add_summary(self, session_key: str, text: str, count: int = 2) -> int:
        return self.summaries.add_summary(
            session_key=session_key,
            message_type="private",
            user_id="10001",
            group_id=None,
            summary=text,
            message_start_id=1,
            message_end_id=count,
            source_message_count=count,
        )

    def test_session_summaries_round_trip_stats_delete_and_clear(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            first_id = self.add_summary("private:10001", "first", 2)
            second_id = self.add_summary("private:10001", "second", 3)
            self.add_summary("private:20002", "other", 4)

            recent = self.summaries.recent_summaries("private:10001", 2)
            scoped_stats = self.summaries.summary_stats("private:10001")
            all_stats = self.summaries.summary_stats()
            deleted = self.summaries.delete_session_summary("private:10001", first_id)
            missing_deleted = self.summaries.delete_session_summary("private:10001", first_id)
            remaining_after_delete = self.summaries.recent_summaries("private:10001", 5)
            cleared = self.summaries.clear_session_summaries("private:10001")
            all_cleared = self.summaries.clear_all_summaries()

        self.assertEqual([summary.summary for summary in recent], ["first", "second"])
        self.assertEqual(recent[0].id, first_id)
        self.assertEqual(recent[1].id, second_id)
        self.assertEqual(scoped_stats, {"summary_count": 2, "summarized_message_count": 5})
        self.assertEqual(all_stats, {"summary_count": 3, "summarized_message_count": 9})
        self.assertTrue(deleted)
        self.assertFalse(missing_deleted)
        self.assertEqual([summary.summary for summary in remaining_after_delete], ["second"])
        self.assertEqual(cleared, 1)
        self.assertEqual(all_cleared, 1)


class ManualMemoryPersistenceUnitTests(TempDatabaseMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.memory_modules = load_legacy_memory_modules()
        cls.database = cls.memory_modules["database"]
        cls.manual_memory = cls.memory_modules["manual_memory"]

    def test_manual_memories_round_trip_filters_stats_and_delete(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            fact_id = self.manual_memory.add_manual_memory(
                "private",
                "10001",
                "fact memory",
                memory_type="fact",
                source_session_key="private:10001",
                confidence=0.8,
            )
            preference_id = self.manual_memory.add_manual_memory(
                "private",
                "10001",
                "preference memory",
                memory_type="preferences",
            )
            self.manual_memory.add_manual_memory("group", "42", "group memory")

            private_memories = self.manual_memory.list_manual_memories("private", "10001", limit=10)
            fact_only = [memory for memory in private_memories if memory.id == fact_id][0]
            stats = self.manual_memory.manual_memory_stats()
            deleted = self.manual_memory.delete_manual_memory(preference_id)
            missing_deleted = self.manual_memory.delete_manual_memory(preference_id)
            remaining = self.manual_memory.list_manual_memories("private", "10001", limit=10)

        self.assertEqual([memory.content for memory in private_memories], ["preference memory", "fact memory"])
        self.assertEqual(fact_only.memory_type, self.manual_memory.MANUAL_FACT_TYPE)
        self.assertEqual(fact_only.confidence, 0.8)
        self.assertEqual(stats, {"memory_count": 3, "subject_count": 2})
        self.assertTrue(deleted)
        self.assertFalse(missing_deleted)
        self.assertEqual([memory.content for memory in remaining], ["fact memory"])


class MessageHistoryPersistenceUnitTests(TempDatabaseMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.memory_modules = load_legacy_memory_modules()
        cls.database = cls.memory_modules["database"]
        cls.memory = cls.memory_modules["memory"]

    def test_messages_append_build_history_count_stats_and_clear(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            self.memory.append_message("private:10001", "user", " first ", "private", "10001")
            self.memory.append_message("private:10001", "assistant", "second", "private", "10001")
            self.memory.append_message("private:10001", "user", "third", "private", "10001")
            self.memory.append_message("private:20002", "user", "other", "private", "20002")

            history = self.memory.build_history(
                "private:10001",
                max_messages=2,
                system_contexts=["system context"],
            )
            count = self.memory.session_message_count("private:10001")
            stats = self.memory.memory_stats()
            self.memory.clear_session("private:10001")
            count_after_clear = self.memory.session_message_count("private:10001")
            self.memory.clear_all_sessions()
            stats_after_clear_all = self.memory.memory_stats()

        self.assertEqual(
            history,
            [
                {"role": "system", "content": "system context"},
                {"role": "assistant", "content": "second"},
                {"role": "user", "content": "third"},
            ],
        )
        self.assertEqual(count, 3)
        self.assertEqual(stats["message_count"], 4)
        self.assertEqual(stats["session_count"], 2)
        self.assertEqual(count_after_clear, 0)
        self.assertEqual(stats_after_clear_all["message_count"], 0)
        self.assertEqual(stats_after_clear_all["session_count"], 0)


if __name__ == "__main__":
    unittest.main()
