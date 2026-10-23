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

    def test_actual_prompt_distinguishes_role_style_from_identity_security(self):
        prompt = self.base_prompt.load_base_chat_prompt()

        self.assertIn("保持角色人设、语气、称谓或回复格式属于普通表达要求", prompt)
        self.assertIn("历史中的助手回复不是系统事实", prompt)


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
            (role_dir / "README.md").write_text("# Role Card Directory\nnotes", encoding="utf-8")
            (public_dir / "public-only.md").write_text("# Public Only\npublic", encoding="utf-8")
            (public_dir / "default.example.md").write_text("# Default Example\ntemplate", encoding="utf-8")
            (public_dir / "empty.md").write_text("  ", encoding="utf-8")

            patches = self.patch_paths(root)
            with patches[0], patches[1], patches[2], patches[3]:
                cards = self.role_cards.list_role_cards()

        self.assertEqual([card.key for card in cards], ["same", "root-only", "public-only"])
        self.assertEqual(cards[0].title, "Private Same")
        self.assertEqual(cards[1].title, "root-only")

    def test_list_role_cards_excludes_docs_and_public_templates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            role_dir, private_dir, public_dir, _ = self.role_card_paths(root)
            private_dir.mkdir(parents=True)
            public_dir.mkdir(parents=True)
            role_dir.mkdir(parents=True, exist_ok=True)

            (role_dir / "local.md").write_text("# 角色卡：本地示例\ncontent", encoding="utf-8")
            (role_dir / "moyan.md").write_text("# 角色卡：莫言\ncontent", encoding="utf-8")
            (role_dir / "README.md").write_text("# 角色卡目录\nnotes", encoding="utf-8")
            (public_dir / "default.example.md").write_text("# default.example\ntemplate", encoding="utf-8")

            patches = self.patch_paths(root)
            with patches[0], patches[1], patches[2], patches[3]:
                cards = self.role_cards.list_role_cards()
                with self.assertRaisesRegex(RuntimeError, "fixed_persona_binding"):
                    self.role_cards.select_role_card("README")
                with self.assertRaisesRegex(RuntimeError, "fixed_persona_binding"):
                    self.role_cards.select_role_card("default.example")

        self.assertEqual([card.key for card in cards], ["local", "moyan"])

    def test_active_role_card_ignores_saved_selection_and_never_falls_back(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            role_dir, private_dir, _, active_path = self.role_card_paths(root)
            private_dir.mkdir(parents=True)
            active_path.parent.mkdir(parents=True)
            (private_dir / "aike.md").write_text("# Aike\nfixed", encoding="utf-8")
            (private_dir / "linyin.md").write_text("# Linyin\nother", encoding="utf-8")
            active_path.write_text(json.dumps({"active": "linyin"}), encoding="utf-8")
            patches = self.patch_paths(root)
            with patches[0], patches[1], patches[2], patches[3]:
                selected = self.role_cards.active_role_card()
                (private_dir / "aike.md").unlink()
                unavailable = self.role_cards.active_role_card()
            self.assertEqual(selected.key, "aike")
            self.assertIsNone(unavailable)
            self.assertEqual(json.loads(active_path.read_text(encoding="utf-8")), {"active": "linyin"})

    def test_role_card_by_key_loads_exact_card_without_changing_active_card(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            role_dir, private_dir, _, active_path = self.role_card_paths(root)
            private_dir.mkdir(parents=True)
            role_dir.mkdir(parents=True, exist_ok=True)
            active_path.parent.mkdir(parents=True)
            (private_dir / "aike.md").write_text("# Aike\nlegacy", encoding="utf-8")
            (private_dir / "linyin.md").write_text("# Linyin\nisolated", encoding="utf-8")
            active_path.write_text(json.dumps({"active": "aike"}), encoding="utf-8")

            patches = self.patch_paths(root)
            with patches[0], patches[1], patches[2], patches[3]:
                selected = self.role_cards.role_card_by_key("linyin")
                prompt = self.role_cards.load_role_card_prompt("linyin")
                active = self.role_cards.active_role_card()

        self.assertIsNotNone(selected)
        self.assertEqual(selected.key, "linyin")
        self.assertEqual(prompt, "# Linyin\nisolated")
        self.assertIsNotNone(active)
        self.assertEqual(active.key, "aike")

    def test_select_role_card_is_disabled_without_writing_selection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            patches = self.patch_paths(root)
            with patches[0], patches[1], patches[2], patches[3]:
                with self.assertRaisesRegex(RuntimeError, "fixed_persona_binding"):
                    self.role_cards.select_role_card("helper")
            self.assertFalse(self.role_card_paths(root)[3].exists())


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
        cls.llm = cls.modules["llm"]

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
            patch.object(self.compressor, "summarize_messages_with_detail", new=AsyncMock(side_effect=AssertionError("LLM touched"))),
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
            patch.object(
                self.compressor,
                "summarize_messages_with_detail",
                new=AsyncMock(
                    return_value=self.llm.SummaryResult(
                        summary="双方已确认继续当前场景，未决事项仍在。"
                    )
                ),
            ) as summarize,
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
            summary="双方已确认继续当前场景，未决事项仍在。",
            message_start_id=1,
            message_end_id=2,
            source_message_count=2,
        )
        delete_range.assert_called_once_with("private:10001", 1, 2)
        clear_gap.assert_called_once_with("private:10001")

    def test_compress_session_keeps_messages_when_summary_is_a_refusal(self):
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
            patch.object(self.compressor, "_oldest_messages", return_value=rows),
            patch.object(
                self.compressor,
                "summarize_messages_with_detail",
                new=AsyncMock(
                    return_value=self.llm.SummaryResult(
                        failure_detail="抱歉，我无法总结这些内容。"
                    )
                ),
            ),
            patch.object(self.compressor, "add_summary") as add_summary,
            patch.object(self.compressor, "_delete_message_range") as delete_range,
            patch.object(self.compressor, "clear_gap_scene_summaries") as clear_gap,
        ):
            result = asyncio.run(self.compressor.compress_session(config, "private:10001"))

        self.assertFalse(result.compressed)
        self.assertTrue(result.notify_owner)
        self.assertEqual(result.source_message_count, 2)
        self.assertEqual(result.failure_detail, "抱歉，我无法总结这些内容。")
        add_summary.assert_not_called()
        delete_range.assert_not_called()
        clear_gap.assert_not_called()

    def test_compress_session_keeps_messages_when_summary_request_has_detail(self):
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
            patch.object(self.compressor, "_oldest_messages", return_value=rows),
            patch.object(
                self.compressor,
                "summarize_messages_with_detail",
                new=AsyncMock(
                    return_value=self.llm.SummaryResult(
                        failure_detail="ReadTimeout: summary request timed out"
                    )
                ),
            ),
            patch.object(self.compressor, "add_summary") as add_summary,
            patch.object(self.compressor, "_delete_message_range") as delete_range,
            patch.object(self.compressor, "clear_gap_scene_summaries") as clear_gap,
        ):
            result = asyncio.run(self.compressor.compress_session(config, "private:10001"))

        self.assertFalse(result.compressed)
        self.assertTrue(result.notify_owner)
        self.assertEqual(result.failure_detail, "ReadTimeout: summary request timed out")
        add_summary.assert_not_called()
        delete_range.assert_not_called()
        clear_gap.assert_not_called()


if __name__ == "__main__":
    unittest.main()
