from __future__ import annotations

import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from pure_ai_chat_loader import load_legacy_business_modules


class AccessRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_legacy_business_modules()
        cls.access = cls.modules["access"]
        cls.access_store = cls.modules["access_store"]
        cls.events = cls.modules["events"]

    def make_config(self, **overrides):
        values = {
            "bot_owner_qq": "10001",
            "enable_private_chat": True,
            "enable_group_chat": True,
            "allow_unknown_private_chat": False,
            "max_group_message_length": 300,
            "max_private_message_length": 150,
            "group_rate_limit_seconds": 5,
            "private_rate_limit_seconds": 10,
        }
        values.update(overrides)
        return types.SimpleNamespace(**values)

    def make_store(self, *, private=(), groups=(), blacklist=()):
        return self.access_store.AccessStore(
            private_whitelist=frozenset(private),
            group_whitelist=frozenset(groups),
            user_blacklist=frozenset(blacklist),
        )

    def test_owner_and_private_whitelist_can_private_chat(self):
        config = self.make_config()
        store = self.make_store(private={"20002"})
        owner_event = self.events.PrivateMessageEvent(user_id=10001)
        whitelisted_event = self.events.PrivateMessageEvent(user_id=20002)

        owner_allowed, _ = self.access.can_private_chat(config, store, owner_event)
        whitelist_allowed, _ = self.access.can_private_chat(config, store, whitelisted_event)

        self.assertTrue(owner_allowed)
        self.assertTrue(whitelist_allowed)

    def test_unknown_private_chat_is_denied_unless_enabled(self):
        event = self.events.PrivateMessageEvent(user_id=30003)
        store = self.make_store()

        denied, reason = self.access.can_private_chat(self.make_config(), store, event)
        allowed, enabled_reason = self.access.can_private_chat(
            self.make_config(allow_unknown_private_chat=True),
            store,
            event,
        )

        self.assertFalse(denied)
        self.assertIsNotNone(reason)
        self.assertTrue(allowed)
        self.assertIsNone(enabled_reason)

    def test_blacklist_blocks_private_and_group_chat(self):
        config = self.make_config()
        store = self.make_store(groups={"42"}, blacklist={"30003"})
        private_event = self.events.PrivateMessageEvent(user_id=30003)
        group_event = self.events.GroupMessageEvent(user_id=30003, group_id=42)

        private_allowed, _ = self.access.can_private_chat(config, store, private_event)
        group_allowed, _ = self.access.can_group_chat(config, store, group_event)

        self.assertFalse(private_allowed)
        self.assertFalse(group_allowed)

    def test_group_chat_requires_group_whitelist(self):
        config = self.make_config()
        event = self.events.GroupMessageEvent(user_id=30003, group_id=42)

        no_whitelist_allowed, _ = self.access.can_group_chat(config, self.make_store(), event)
        wrong_group_allowed, _ = self.access.can_group_chat(
            config,
            self.make_store(groups={"99"}),
            event,
        )
        allowed, reason = self.access.can_group_chat(
            config,
            self.make_store(groups={"42"}),
            event,
        )

        self.assertFalse(no_whitelist_allowed)
        self.assertFalse(wrong_group_allowed)
        self.assertTrue(allowed)
        self.assertIsNone(reason)

    def test_limits_choose_private_or_group_values_by_event_type(self):
        config = self.make_config()
        private_event = self.events.PrivateMessageEvent(user_id=10001)
        group_event = self.events.GroupMessageEvent(user_id=10001, group_id=42)

        self.assertEqual(self.access.message_length_limit(config, private_event), 150)
        self.assertEqual(self.access.message_length_limit(config, group_event), 300)
        self.assertEqual(self.access.rate_limit_seconds(config, private_event), 10)
        self.assertEqual(self.access.rate_limit_seconds(config, group_event), 5)


class AccessStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_legacy_business_modules()
        cls.access_store = cls.modules["access_store"]

    def test_access_store_round_trips_normalized_items(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "access.json"
            with patch.object(self.access_store, "ACCESS_STORE_PATH", path):
                self.assertEqual(self.access_store.load_access_store(), self.access_store.EMPTY_STORE)

                added = self.access_store.add_item("private_whitelist", " 10001 ")
                duplicate = self.access_store.add_item("private_whitelist", "10001")
                group_added = self.access_store.add_item("group_whitelist", "42")
                removed = self.access_store.remove_item("private_whitelist", "10001")
                missing_removed = self.access_store.remove_item("private_whitelist", "10001")
                store = self.access_store.load_access_store()

        self.assertTrue(added)
        self.assertFalse(duplicate)
        self.assertTrue(group_added)
        self.assertTrue(removed)
        self.assertFalse(missing_removed)
        self.assertEqual(store.private_whitelist, frozenset())
        self.assertEqual(store.group_whitelist, frozenset({"42"}))

    def test_merged_access_combines_env_and_file_store(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "access.json"
            with patch.object(self.access_store, "ACCESS_STORE_PATH", path):
                self.access_store.save_access_store(
                    self.access_store.AccessStore(
                        private_whitelist=frozenset({"file-private"}),
                        group_whitelist=frozenset({"file-group"}),
                        user_blacklist=frozenset({"file-blocked"}),
                    )
                )
                merged = self.access_store.merged_access(
                    frozenset({"env-private"}),
                    frozenset({"env-group"}),
                    frozenset({"env-blocked"}),
                )

        self.assertEqual(merged.private_whitelist, frozenset({"env-private", "file-private"}))
        self.assertEqual(merged.group_whitelist, frozenset({"env-group", "file-group"}))
        self.assertEqual(merged.user_blacklist, frozenset({"env-blocked", "file-blocked"}))


class ReplyDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_legacy_business_modules()
        cls.reply_decider = cls.modules["reply_decider"]

    def make_config(self, threshold=50):
        return types.SimpleNamespace(
            bot_name="Helper",
            bot_aliases=frozenset({"Bot"}),
            group_auto_reply_threshold=threshold,
        )

    def make_profile(self):
        return self.reply_decider.AutoReplyProfile(
            role_key="test",
            bot_aliases=("Assistant",),
            call_markers=("come",),
            question_markers=("?",),
            help_markers=("help",),
            owner_target_markers=("owner",),
            insult_markers=("bad",),
            self_negative_markers=("i am bad",),
        )

    def test_empty_and_short_plain_messages_do_not_trigger_reply(self):
        config = self.make_config()

        empty = self.reply_decider.decide_group_auto_reply(config, "   ", False)
        short = self.reply_decider.decide_group_auto_reply(config, "ok", False)

        self.assertFalse(empty.should_reply)
        self.assertEqual(empty.reason, "empty")
        self.assertFalse(short.should_reply)
        self.assertEqual(short.reason, "short_plain")

    def test_bot_alias_and_help_markers_can_trigger_reply(self):
        config = self.make_config(threshold=50)

        with patch.object(self.reply_decider, "load_auto_reply_profile", return_value=self.make_profile()):
            decision = self.reply_decider.decide_group_auto_reply(
                config,
                "Assistant please help?",
                False,
                role_key="test",
            )

        self.assertTrue(decision.should_reply)
        self.assertGreaterEqual(decision.score, 50)
        self.assertIn("bot_alias", decision.reason)
        self.assertIn("help", decision.reason)

    def test_owner_sender_gets_owner_specific_score(self):
        config = self.make_config(threshold=60)

        with patch.object(self.reply_decider, "load_auto_reply_profile", return_value=self.make_profile()):
            decision = self.reply_decider.decide_group_auto_reply(
                config,
                "i am bad?",
                True,
                role_key="test",
            )

        self.assertTrue(decision.should_reply)
        self.assertIn("owner_sender", decision.reason)
        self.assertIn("owner_question", decision.reason)
        self.assertIn("owner_self_negative", decision.reason)


class NotificationAndRateLimitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_legacy_business_modules()
        cls.owner_notify = cls.modules["owner_notify"]
        cls.rate_limit = cls.modules["rate_limit"]
        cls.events = cls.modules["events"]

    def setUp(self) -> None:
        self.rate_limit._last_seen.clear()

    def test_owner_notification_validation_rejects_empty_long_and_sensitive_content(self):
        self.assertEqual(
            self.owner_notify.validate_owner_notification_content("", 50),
            self.owner_notify.EMPTY_NOTIFICATION_MESSAGE,
        )
        self.assertEqual(
            self.owner_notify.validate_owner_notification_content("x" * 51, 50),
            self.owner_notify.TOO_LONG_NOTIFICATION_MESSAGE,
        )
        self.assertEqual(
            self.owner_notify.validate_owner_notification_content("token sk-abcdefghijkl", 50),
            self.owner_notify.SENSITIVE_NOTIFICATION_MESSAGE,
        )
        self.assertIsNone(
            self.owner_notify.validate_owner_notification_content("please tell owner", 50)
        )

    def test_format_owner_notification_includes_private_or_group_source(self):
        private_event = self.events.PrivateMessageEvent(user_id=10001)
        group_event = self.events.GroupMessageEvent(user_id=20002, group_id=42)

        private_message = self.owner_notify.format_owner_notification(private_event, "hello")
        group_message = self.owner_notify.format_owner_notification(group_event, "hello")

        self.assertIn("10001", private_message)
        self.assertIn("hello", private_message)
        self.assertIn("42", group_message)
        self.assertIn("20002", group_message)

    def test_rate_limit_allows_first_call_and_blocks_immediate_repeat(self):
        allowed, wait = self.rate_limit.check_rate_limit("user:1", 10)
        repeated, repeated_wait = self.rate_limit.check_rate_limit("user:1", 10)

        self.assertTrue(allowed)
        self.assertEqual(wait, 0)
        self.assertFalse(repeated)
        self.assertGreaterEqual(repeated_wait, 1)

    def test_check_rate_limits_updates_all_keys_atomically(self):
        allowed, wait = self.rate_limit.check_rate_limits([("global", 10), ("user", 10)])
        blocked, blocked_wait = self.rate_limit.check_rate_limits([("global", 10), ("other", 10)])
        other_allowed, other_wait = self.rate_limit.check_rate_limit("other", 10)

        self.assertTrue(allowed)
        self.assertEqual(wait, 0)
        self.assertFalse(blocked)
        self.assertGreaterEqual(blocked_wait, 1)
        self.assertTrue(other_allowed)
        self.assertEqual(other_wait, 0)


if __name__ == "__main__":
    unittest.main()
