from __future__ import annotations

import unittest
from unittest.mock import patch

from pure_ai_chat_loader import load_legacy_memory_modules


class MemoryPureUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_legacy_memory_modules()
        cls.memory = cls.modules["memory"]

    def test_sanitize_history_content_strips_outer_whitespace(self):
        self.assertEqual(self.memory.sanitize_history_content("  hello\n"), "hello")

    def test_build_history_uses_contexts_without_database_when_message_limit_is_zero(self):
        with (
            patch.object(self.memory, "format_summary_context", return_value="summary context") as summaries,
            patch.object(self.memory, "format_gap_scene_context", return_value="gap context") as gap_summaries,
            patch.object(self.memory, "ensure_database", side_effect=AssertionError("database touched")),
        ):
            history = self.memory.build_history(
                "private:10001",
                max_messages=0,
                max_summaries=2,
                max_gap_scene_summaries=1,
                system_contexts=["system context", ""],
            )

        self.assertEqual(
            history,
            [
                {"role": "system", "content": "system context"},
                {"role": "system", "content": "summary context"},
                {"role": "system", "content": "gap context"},
            ],
        )
        summaries.assert_called_once_with("private:10001", 2)
        gap_summaries.assert_called_once_with("private:10001", 1)

    def test_session_message_progress_combines_raw_and_summarized_counts(self):
        with (
            patch.object(self.memory, "session_message_count", return_value=7),
            patch.object(self.memory, "summary_stats", return_value={"summarized_message_count": 5}),
        ):
            progress = self.memory.session_message_progress("private:10001")

        self.assertEqual(progress, 12)


class ManualMemoryPureUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_legacy_memory_modules()
        cls.manual_memory = cls.modules["manual_memory"]

    def make_memory(self, memory_id: int, memory_type: str, content: str):
        return self.manual_memory.ManualMemory(
            id=memory_id,
            subject_type="private",
            subject_id="10001",
            memory_type=memory_type,
            content=content,
            confidence=1.0,
            created_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-01T00:00:00+00:00",
        )

    def test_normalize_memory_type_accepts_public_aliases_and_defaults_to_fact(self):
        self.assertEqual(
            self.manual_memory.normalize_memory_type(" fact "),
            self.manual_memory.MANUAL_FACT_TYPE,
        )
        self.assertEqual(
            self.manual_memory.normalize_memory_type("preferences"),
            self.manual_memory.MANUAL_PREFERENCE_TYPE,
        )
        self.assertEqual(
            self.manual_memory.normalize_memory_type("unknown"),
            self.manual_memory.MANUAL_FACT_TYPE,
        )

    def test_memory_from_row_converts_database_values_to_dataclass_types(self):
        row = {
            "id": "42",
            "subject_type": "private",
            "subject_id": 10001,
            "memory_type": self.manual_memory.MANUAL_FACT_TYPE,
            "content": "remember this",
            "confidence": "0.75",
            "created_at": "created",
            "updated_at": "updated",
        }

        memory = self.manual_memory._memory_from_row(row)

        self.assertEqual(memory.id, 42)
        self.assertEqual(memory.subject_id, "10001")
        self.assertEqual(memory.confidence, 0.75)
        self.assertEqual(memory.content, "remember this")

    def test_format_manual_memory_context_respects_limit_and_deduplicates_subjects(self):
        memories = [
            self.make_memory(1, self.manual_memory.MANUAL_FACT_TYPE, "fact one"),
            self.make_memory(2, self.manual_memory.MANUAL_PREFERENCE_TYPE, "preference one"),
        ]
        calls = []

        def fake_list(subject_type: str, subject_id: str, limit: int):
            calls.append((subject_type, subject_id, limit))
            return memories[:limit]

        with patch.object(self.manual_memory, "list_manual_memories", side_effect=fake_list):
            context = self.manual_memory.format_manual_memory_context(
                [
                    ("private", "10001"),
                    ("private", "10001"),
                    ("group", "42"),
                ],
                limit=2,
            )

        self.assertEqual(calls, [("private", "10001", 2)])
        self.assertIn("fact one", context)
        self.assertIn("preference one", context)

    def test_format_manual_memory_context_short_circuits_when_limit_is_zero(self):
        with patch.object(self.manual_memory, "list_manual_memories") as list_memories:
            context = self.manual_memory.format_manual_memory_context([("private", "10001")], limit=0)

        self.assertEqual(context, "")
        list_memories.assert_not_called()


class SummaryPureUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_legacy_memory_modules()
        cls.summaries = cls.modules["summaries"]
        cls.gap_scene_summaries = cls.modules["gap_scene_summaries"]

    def test_summary_from_row_converts_database_values(self):
        summary = self.summaries._summary_from_row(
            {
                "id": "1",
                "session_key": "private:10001",
                "summary": "older context",
                "message_start_id": "10",
                "message_end_id": "15",
                "source_message_count": "6",
                "created_at": "created",
            }
        )

        self.assertEqual(summary.id, 1)
        self.assertEqual(summary.message_start_id, 10)
        self.assertEqual(summary.source_message_count, 6)
        self.assertEqual(summary.summary, "older context")

    def test_format_summary_context_uses_recent_summaries_without_database_in_test(self):
        sample = [
            self.summaries.SessionSummary(1, "s", "first", 1, 2, 2, "created"),
            self.summaries.SessionSummary(2, "s", "second", 3, 4, 2, "created"),
        ]

        with patch.object(self.summaries, "recent_summaries", return_value=sample) as recent:
            context = self.summaries.format_summary_context("s", 2)

        recent.assert_called_once_with("s", 2)
        self.assertIn("1. first", context)
        self.assertIn("2. second", context)

    def test_gap_scene_format_messages_labels_owner_user_and_assistant_content(self):
        rows = [
            {"role": "user", "user_id": "10001", "content": "owner message"},
            {"role": "user", "user_id": "20002", "content": "user message"},
            {"role": "assistant", "user_id": "", "content": "assistant message"},
        ]

        formatted = self.gap_scene_summaries._format_messages(rows, owner_qq="10001")

        self.assertIn("owner message", formatted)
        self.assertIn("user message", formatted)
        self.assertIn("AI: assistant message", formatted)

    def test_gap_scene_should_update_uses_creation_final_and_step_thresholds(self):
        summary = self.gap_scene_summaries.GapSceneSummary(
            id=1,
            session_key="s",
            slot=1,
            summary="old",
            message_start_id=1,
            message_end_id=10,
            source_message_count=10,
            created_at="created",
            updated_at="updated",
        )

        self.assertTrue(self.gap_scene_summaries._should_update(None, 10, 40))
        self.assertFalse(self.gap_scene_summaries._should_update(summary, 29, 40))
        self.assertTrue(self.gap_scene_summaries._should_update(summary, 30, 40))
        self.assertTrue(self.gap_scene_summaries._should_update(summary, 40, 40))


if __name__ == "__main__":
    unittest.main()
