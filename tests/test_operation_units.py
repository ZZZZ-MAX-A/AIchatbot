from __future__ import annotations

import asyncio
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from pure_ai_chat_loader import load_legacy_operation_modules


class BasePromptPureUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_legacy_operation_modules()
        cls.base_prompt = cls.modules["base_prompt"]

    def test_load_json_returns_empty_for_missing_invalid_or_non_object_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            missing = temp_path / "missing.json"
            invalid = temp_path / "invalid.json"
            array_file = temp_path / "array.json"
            valid = temp_path / "valid.json"

            invalid.write_text("{not-json", encoding="utf-8")
            array_file.write_text("[1, 2, 3]", encoding="utf-8")
            valid.write_text('{"identity_rules": ["rule"]}', encoding="utf-8")

            self.assertEqual(self.base_prompt._load_json(missing), {})
            self.assertEqual(self.base_prompt._load_json(invalid), {})
            self.assertEqual(self.base_prompt._load_json(array_file), {})
            self.assertEqual(self.base_prompt._load_json(valid), {"identity_rules": ["rule"]})

    def test_string_list_accepts_lists_and_strips_empty_items(self):
        self.assertEqual(self.base_prompt._string_list("not-list"), [])
        self.assertEqual(self.base_prompt._string_list([" one ", "", 2, None]), ["one", "2", "None"])

    def test_load_base_chat_prompt_formats_enabled_sections_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "chat-core.json"
            path.write_text(
                json.dumps(
                    {
                        "identity_rules": ["keep owner identity"],
                        "permission_rules": ["ask before write", ""],
                        "privacy_rules": "ignored",
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(self.base_prompt, "BASE_PROMPT_PATH", path):
                prompt = self.base_prompt.load_base_chat_prompt()

        self.assertIn("keep owner identity", prompt)
        self.assertIn("ask before write", prompt)
        self.assertNotIn("ignored", prompt)


class RoleCardPureUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_legacy_operation_modules()
        cls.role_cards = cls.modules["role_cards"]

    def role_card_paths(self, root: Path):
        role_dir = root / "prompts" / "persona-cards"
        private_dir = role_dir / "private"
        public_dir = role_dir / "public"
        active_path = root / "data" / "active-role-card.json"
        return role_dir, private_dir, public_dir, active_path

    def patch_paths(self, root: Path):
        role_dir, private_dir, public_dir, active_path = self.role_card_paths(root)
        return (
            patch.object(self.role_cards, "ROLE_CARD_DIR", role_dir),
            patch.object(self.role_cards, "PRIVATE_ROLE_CARD_DIR", private_dir),
            patch.object(self.role_cards, "PUBLIC_ROLE_CARD_DIR", public_dir),
            patch.object(self.role_cards, "ACTIVE_ROLE_CARD_PATH", active_path),
        )

    def test_list_role_cards_uses_private_root_public_order_and_deduplicates_keys(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            role_dir, private_dir, public_dir, _ = self.role_card_paths(root)
            private_dir.mkdir(parents=True)
            public_dir.mkdir(parents=True)
            role_dir.mkdir(parents=True, exist_ok=True)

            (private_dir / "same.md").write_text("# Private Same\nprivate", encoding="utf-8")
            (role_dir / "same.md").write_text("# Root Same\nroot", encoding="utf-8")
            (role_dir / "root-only.md").write_text("body without title", encoding="utf-8")
            (public_dir / "public-only.md").write_text("# Public Only\npublic", encoding="utf-8")
            (public_dir / "empty.md").write_text("  ", encoding="utf-8")

            patches = self.patch_paths(root)
            with patches[0], patches[1], patches[2], patches[3]:
                cards = self.role_cards.list_role_cards()

        self.assertEqual([card.key for card in cards], ["same", "root-only", "public-only"])
        self.assertEqual(cards[0].title, "Private Same")
        self.assertEqual(cards[1].title, "root-only")

    def test_active_role_card_uses_saved_key_and_falls_back_to_first_card(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            role_dir, private_dir, _, active_path = self.role_card_paths(root)
            private_dir.mkdir(parents=True)
            role_dir.mkdir(parents=True, exist_ok=True)
            active_path.parent.mkdir(parents=True)

            (private_dir / "first.md").write_text("# First\ncontent", encoding="utf-8")
            (role_dir / "second.md").write_text("# Second\ncontent", encoding="utf-8")
            active_path.write_text(json.dumps({"active": "second"}), encoding="utf-8")

            patches = self.patch_paths(root)
            with patches[0], patches[1], patches[2], patches[3]:
                selected = self.role_cards.active_role_card()
                active_path.write_text("{bad-json", encoding="utf-8")
                fallback = self.role_cards.active_role_card()

        self.assertIsNotNone(selected)
        self.assertEqual(selected.key, "second")
        self.assertIsNotNone(fallback)
        self.assertEqual(fallback.key, "first")

    def test_select_role_card_matches_title_and_persists_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            role_dir, private_dir, _, active_path = self.role_card_paths(root)
            private_dir.mkdir(parents=True)
            role_dir.mkdir(parents=True, exist_ok=True)
            (role_dir / "helper.md").write_text("# Helpful Card\ncontent", encoding="utf-8")

            patches = self.patch_paths(root)
            with patches[0], patches[1], patches[2], patches[3]:
                selected = self.role_cards.select_role_card("helpful card")
                persisted = json.loads(active_path.read_text(encoding="utf-8"))

        self.assertIsNotNone(selected)
        self.assertEqual(selected.key, "helper")
        self.assertEqual(persisted, {"active": "helper"})


class TrialsPureUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_legacy_operation_modules()
        cls.trials = cls.modules["trials"]

    def test_can_use_private_trial_rejects_disabled_trials_without_database(self):
        with patch.object(self.trials, "private_trial_used", side_effect=AssertionError("database touched")):
            self.assertFalse(self.trials.can_use_private_trial("10001", 0))
            self.assertFalse(self.trials.can_use_private_trial("10001", -1))

    def test_can_use_private_trial_compares_used_count_to_limit(self):
        with patch.object(self.trials, "private_trial_used", return_value=2):
            self.assertTrue(self.trials.can_use_private_trial("10001", 3))
            self.assertFalse(self.trials.can_use_private_trial("10001", 2))


class CompressorPureUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_legacy_operation_modules()
        cls.compressor = cls.modules["compressor"]

    def make_config(self, **overrides):
        values = {
            "enable_memory_compression": True,
            "max_stored_messages_per_session": 10,
            "summary_keep_recent_messages": 3,
            "summary_min_source_messages": 0,
            "summary_batch_messages": 4,
            "bot_owner_qq": "10001",
        }
        values.update(overrides)
        return types.SimpleNamespace(**values)

    def test_format_messages_labels_owner_user_and_assistant(self):
        rows = [
            {"role": "user", "user_id": "10001", "content": "owner"},
            {"role": "user", "user_id": "20002", "content": "member"},
            {"role": "assistant", "user_id": "", "content": "reply"},
        ]

        formatted = self.compressor._format_messages(rows, owner_qq="10001")

        self.assertIn("owner", formatted)
        self.assertIn("member", formatted)
        self.assertIn("AI: reply", formatted)

    def test_compress_session_respects_disabled_automatic_compression_without_database(self):
        config = self.make_config(enable_memory_compression=False)

        with patch.object(self.compressor, "_message_count", side_effect=AssertionError("database touched")):
            result = asyncio.run(self.compressor.compress_session(config, "private:10001", force=False))

        self.assertFalse(result.compressed)
        self.assertIsNone(result.summary_id)

    def test_compress_session_skips_when_message_count_is_under_threshold(self):
        config = self.make_config(max_stored_messages_per_session=10)

        with patch.object(self.compressor, "_message_count", return_value=10):
            result = asyncio.run(self.compressor.compress_session(config, "private:10001"))

        self.assertFalse(result.compressed)
        self.assertEqual(result.source_message_count, 0)

    def test_compress_session_reports_too_few_source_messages_before_llm_call(self):
        config = self.make_config(
            max_stored_messages_per_session=10,
            summary_keep_recent_messages=5,
            summary_min_source_messages=20,
        )

        with (
            patch.object(self.compressor, "_message_count", return_value=12),
            patch.object(self.compressor, "summarize_messages", new=AsyncMock(side_effect=AssertionError("LLM touched"))),
        ):
            result = asyncio.run(self.compressor.compress_session(config, "private:10001"))

        self.assertFalse(result.compressed)
        self.assertEqual(result.source_message_count, 7)

    def test_compress_session_summarizes_deletes_and_clears_gap_summaries(self):
        config = self.make_config(
            max_stored_messages_per_session=3,
            summary_batch_messages=2,
            summary_keep_recent_messages=1,
        )
        rows = [
            {
                "id": 1,
                "message_type": "private",
                "user_id": "10001",
                "group_id": None,
                "role": "user",
                "content": "hello",
            },
            {
                "id": 2,
                "message_type": "private",
                "user_id": "10001",
                "group_id": None,
                "role": "assistant",
                "content": "hi",
            },
        ]

        with (
            patch.object(self.compressor, "_message_count", return_value=5),
            patch.object(self.compressor, "_oldest_messages", return_value=rows) as oldest_messages,
            patch.object(self.compressor, "summarize_messages", new=AsyncMock(return_value="summary")) as summarize,
            patch.object(self.compressor, "add_summary", return_value=42) as add_summary,
            patch.object(self.compressor, "_delete_message_range", return_value=2) as delete_range,
            patch.object(self.compressor, "clear_gap_scene_summaries") as clear_gap,
        ):
            result = asyncio.run(self.compressor.compress_session(config, "private:10001"))

        self.assertTrue(result.compressed)
        self.assertEqual(result.summary_id, 42)
        self.assertEqual(result.source_message_count, 2)
        oldest_messages.assert_called_once_with("private:10001", 2)
        summarize.assert_awaited_once()
        add_summary.assert_called_once_with(
            session_key="private:10001",
            message_type="private",
            user_id="10001",
            group_id=None,
            summary="summary",
            message_start_id=1,
            message_end_id=2,
            source_message_count=2,
        )
        delete_range.assert_called_once_with("private:10001", 1, 2)
        clear_gap.assert_called_once_with("private:10001")


if __name__ == "__main__":
    unittest.main()
