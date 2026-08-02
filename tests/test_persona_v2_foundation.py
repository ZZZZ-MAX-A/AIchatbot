from __future__ import annotations

import unittest
from pathlib import Path

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module


class PersonaScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.persona = load_module(
            "src.plugins.ai_chat.persona_scope",
            AI_CHAT_ROOT / "persona_scope.py",
        )

    def settings(self, **overrides):
        values = {
            "routing_v2_enabled": False,
            "memory_v2_enabled": False,
            "routing_v2_bot_ids": frozenset(),
            "memory_v2_bot_ids": frozenset(),
            "legacy_persona_id": "aike",
            "legacy_role_card_key": "aike",
            "raw_bindings": "2700318954=aike:aike;2993614760=linyin:linyin",
        }
        values.update(overrides)
        return self.persona.build_persona_routing_settings(**values)

    def test_binding_parser_accepts_stable_explicit_mappings(self):
        parsed = self.persona.parse_persona_bindings(
            "2700318954=aike:aike;1234567890=luna:luna-card"
        )

        self.assertEqual(parsed.errors, ())
        self.assertEqual(
            [
                (item.bot_self_id, item.persona_id, item.role_card_key)
                for item in parsed.bindings
            ],
            [
                ("1234567890", "luna", "luna-card"),
                ("2700318954", "aike", "aike"),
            ],
        )

    def test_invalid_and_duplicate_bindings_fail_closed(self):
        parsed = self.persona.parse_persona_bindings(
            "bad=aike:aike;1234567890=Luna:luna;"
            "2700318954=aike:aike;2700318954=luna:luna"
        )

        self.assertEqual(parsed.bindings, ())
        self.assertEqual(
            parsed.errors,
            (
                "entry_1:invalid_bot_self_id",
                "entry_2:invalid_persona_id",
                "entry_4:duplicate_bot_self_id",
            ),
        )

    def test_disabled_foundation_preserves_private_legacy_scope(self):
        scope = self.persona.resolve_conversation_scope(
            self.settings(),
            bot_self_id="2700318954",
            user_id="3313097998",
            chat_type="private",
            legacy_session_key="private:3313097998",
        )

        self.assertEqual(scope.persona_id, "aike")
        self.assertEqual(scope.role_card_key, "aike")
        self.assertEqual(scope.runtime_mode, "legacy")
        self.assertEqual(scope.legacy_session_key, "private:3313097998")
        self.assertFalse(scope.routing_v2_requested)
        self.assertFalse(scope.routing_v2_active)
        self.assertFalse(scope.memory_v2_requested)
        self.assertFalse(scope.memory_v2_active)
        self.assertEqual(scope.configuration_error, "")
        self.assertTrue(scope.as_artifact()["legacy_session_key_preserved"])

    def test_group_scope_keeps_the_existing_group_session_key(self):
        scope = self.persona.resolve_conversation_scope(
            self.settings(),
            bot_self_id="2700318954",
            user_id="3313097998",
            chat_type="group",
            group_id="778899",
            legacy_session_key="group:778899",
        )

        self.assertEqual(scope.chat_type, "group")
        self.assertEqual(scope.peer_id, "778899")
        self.assertEqual(scope.group_id, "778899")
        self.assertEqual(scope.legacy_session_key, "group:778899")
        self.assertEqual(scope.runtime_mode, "legacy")

    def test_second_bot_activates_ephemeral_persona_route(self):
        settings = self.settings(
            routing_v2_enabled=True,
            routing_v2_bot_ids=frozenset({"2993614760"}),
        )
        scope = self.persona.resolve_conversation_scope(
            settings,
            bot_self_id="2993614760",
            user_id="3313097998",
            chat_type="private",
            legacy_session_key="private:3313097998",
            available_role_card_keys=frozenset({"aike", "linyin"}),
        )

        self.assertTrue(scope.routing_v2_requested)
        self.assertTrue(scope.routing_v2_active)
        self.assertEqual(scope.persona_id, "linyin")
        self.assertEqual(scope.role_card_key, "linyin")
        self.assertEqual(
            scope.runtime_session_key,
            "persona:linyin:private:3313097998",
        )
        self.assertEqual(scope.runtime_mode, "persona_v2_ephemeral")
        self.assertFalse(scope.memory_v2_requested)
        self.assertFalse(scope.memory_v2_active)

    def test_aike_stays_on_exact_legacy_route_when_only_second_bot_is_allowlisted(self):
        settings = self.settings(
            routing_v2_enabled=True,
            routing_v2_bot_ids=frozenset({"2993614760"}),
        )
        scope = self.persona.resolve_conversation_scope(
            settings,
            bot_self_id="2700318954",
            user_id="3313097998",
            chat_type="private",
            legacy_session_key="private:3313097998",
            available_role_card_keys=frozenset({"aike", "linyin"}),
        )

        self.assertFalse(scope.routing_v2_requested)
        self.assertFalse(scope.routing_v2_active)
        self.assertEqual(scope.runtime_mode, "legacy")
        self.assertEqual(scope.runtime_session_key, "private:3313097998")

    def test_persona_memory_activates_only_for_the_explicit_routed_bot(self):
        settings = self.settings(
            routing_v2_enabled=True,
            memory_v2_enabled=True,
            routing_v2_bot_ids=frozenset({"2993614760"}),
            memory_v2_bot_ids=frozenset({"2993614760"}),
        )
        scope = self.persona.resolve_conversation_scope(
            settings,
            bot_self_id="2993614760",
            user_id="3313097998",
            chat_type="private",
            legacy_session_key="private:3313097998",
            available_role_card_keys=frozenset({"linyin"}),
        )

        self.assertTrue(scope.routing_v2_active)
        self.assertTrue(scope.memory_v2_requested)
        self.assertTrue(scope.memory_v2_active)
        self.assertEqual(scope.runtime_mode, "persona_v2_persistent")
        self.assertEqual(scope.configuration_error, "")

    def test_persona_memory_fails_closed_when_routing_is_not_allowlisted(self):
        settings = self.settings(
            routing_v2_enabled=True,
            memory_v2_enabled=True,
            routing_v2_bot_ids=frozenset(),
            memory_v2_bot_ids=frozenset({"2993614760"}),
        )
        scope = self.persona.resolve_conversation_scope(
            settings,
            bot_self_id="2993614760",
            user_id="3313097998",
            chat_type="private",
            legacy_session_key="private:3313097998",
            available_role_card_keys=frozenset({"linyin"}),
        )

        self.assertFalse(scope.routing_v2_active)
        self.assertFalse(scope.memory_v2_active)
        self.assertIn("memory_v2_requires_routing_v2", scope.configuration_error)

    def test_missing_role_card_fails_closed_without_legacy_persona_activation(self):
        settings = self.settings(
            routing_v2_enabled=True,
            routing_v2_bot_ids=frozenset({"2993614760"}),
        )
        scope = self.persona.resolve_conversation_scope(
            settings,
            bot_self_id="2993614760",
            user_id="3313097998",
            chat_type="private",
            legacy_session_key="private:3313097998",
            available_role_card_keys=frozenset({"aike"}),
        )

        self.assertFalse(scope.routing_v2_active)
        self.assertEqual(scope.runtime_mode, "legacy")
        self.assertEqual(scope.runtime_session_key, "private:3313097998")
        self.assertIn("missing_role_card", scope.configuration_error)

    def test_missing_binding_reports_configuration_error_without_routing(self):
        settings = self.settings(
            routing_v2_enabled=True,
            routing_v2_bot_ids=frozenset({"1234567890"}),
            raw_bindings="2700318954=aike:aike",
        )
        scope = self.persona.resolve_conversation_scope(
            settings,
            bot_self_id="1234567890",
            user_id="3313097998",
            chat_type="private",
            legacy_session_key="private:3313097998",
        )

        self.assertFalse(scope.routing_v2_active)
        self.assertEqual(scope.runtime_mode, "legacy")
        self.assertIn("missing_persona_binding", scope.configuration_error)


class EphemeralPersonaHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.module = load_module(
            "src.plugins.ai_chat.ephemeral_persona_history",
            AI_CHAT_ROOT / "ephemeral_persona_history.py",
        )

    def setUp(self) -> None:
        self.history = self.module.EphemeralPersonaHistory()

    def test_turns_are_scoped_and_bounded_in_memory(self):
        self.history.append_turn("persona:linyin:private:1", "u1", "a1", 2)
        self.history.append_turn("persona:linyin:private:1", "u2", "a2", 2)
        self.history.append_turn("private:1", "legacy", "legacy reply", 10)

        routed = self.history.build_history(
            "persona:linyin:private:1",
            2,
            ["system"],
        )

        self.assertEqual(
            routed,
            [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "u2"},
                {"role": "assistant", "content": "a2"},
            ],
        )
        self.assertEqual(self.history.message_count("private:1"), 2)

    def test_clear_only_removes_selected_persona_session(self):
        self.history.append_turn("persona:linyin:private:1", "u", "a", 10)
        self.history.append_turn("persona:linyin:private:2", "u", "a", 10)

        self.history.clear("persona:linyin:private:1")

        self.assertEqual(self.history.message_count("persona:linyin:private:1"), 0)
        self.assertEqual(self.history.message_count("persona:linyin:private:2"), 2)


class PersonaPhaseTwoIsolationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[1]
        cls.plugin_source = (
            cls.repo_root / "src" / "plugins" / "ai_chat" / "__init__.py"
        ).read_text(encoding="utf-8")
        cls.llm_source = (
            cls.repo_root / "src" / "plugins" / "ai_chat" / "llm.py"
        ).read_text(encoding="utf-8")
        cls.database_source = (
            cls.repo_root / "src" / "plugins" / "ai_chat" / "database.py"
        ).read_text(encoding="utf-8")
        cls.persona_source = (
            cls.repo_root / "src" / "plugins" / "ai_chat" / "persona_scope.py"
        ).read_text(encoding="utf-8")
        cls.ephemeral_source = (
            cls.repo_root / "src" / "plugins" / "ai_chat" / "ephemeral_persona_history.py"
        ).read_text(encoding="utf-8")

    def test_aike_role_card_loader_remains_the_default_legacy_loader(self):
        self.assertIn("else load_active_role_card_prompt()", self.llm_source)
        self.assertIn("role_card_key: str = \"\"", self.llm_source)
        self.assertNotIn("resolve_conversation_scope", self.llm_source)

    def test_chat_request_uses_scope_key_but_legacy_key_is_preserved(self):
        self.assertIn("key=scope.runtime_session_key", self.plugin_source)
        self.assertIn("async with session_lock(request.key):", self.plugin_source)
        self.assertIn("legacy_session_key=session_key(event)", self.plugin_source)

    def test_routed_persona_uses_ephemeral_memory_and_disables_tts_candidate(self):
        self.assertIn("ephemeral_persona_history.build_history", self.plugin_source)
        self.assertIn("ephemeral_persona_history.append_turn", self.plugin_source)
        self.assertIn("persistent_memory_enabled=not scope.routing_v2_active", self.plugin_source)
        self.assertIn("persona_memory_enabled=scope.memory_v2_active", self.plugin_source)
        self.assertIn("tts_enabled=bool(config.enable_tts and not scope.routing_v2_active)", self.plugin_source)
        self.assertNotIn(".database", self.ephemeral_source)
        self.assertNotIn("Path(", self.ephemeral_source)

    def test_database_schema_is_unchanged_in_phase_one(self):
        self.assertIn('SCHEMA_VERSION = "7"', self.database_source)
        self.assertNotIn("persona_id", self.database_source)
        self.assertNotIn("persona_messages", self.database_source)


if __name__ == "__main__":
    unittest.main()
