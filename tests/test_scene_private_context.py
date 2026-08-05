from __future__ import annotations

import contextlib
import unittest
from pathlib import Path
from unittest.mock import patch

from pure_ai_chat_loader import load_scene_private_context_module


class ScenePrivateContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_scene_private_context_module()

    def routing_settings(self, *, memory_bot_ids=frozenset({"20002"})):
        return self.module.PersonaRoutingSettings(
            routing_v2_enabled=True,
            memory_v2_enabled=True,
            routing_v2_bot_ids=frozenset({"20002"}),
            memory_v2_bot_ids=memory_bot_ids,
            legacy_persona_id="aike",
            legacy_role_card_key="aike",
            bindings=(
                self.module.PersonaBinding("20002", "linyin", "linyin"),
            ),
        )

    def test_aike_and_linyin_resolve_separate_owner_private_namespaces(self):
        settings = self.routing_settings()

        aike = self.module.resolve_scene_private_scope(
            settings,
            speaker="aike",
            owner_id="10001",
            aike_bot_id="20001",
            linyin_bot_id="20002",
        )
        linyin = self.module.resolve_scene_private_scope(
            settings,
            speaker="linyin",
            owner_id="10001",
            aike_bot_id="20001",
            linyin_bot_id="20002",
        )

        self.assertIsNotNone(aike)
        self.assertIsNotNone(linyin)
        self.assertEqual(aike.runtime_session_key, "private:10001")
        self.assertEqual(aike.persona_id, "aike")
        self.assertFalse(aike.memory_v2_active)
        self.assertEqual(linyin.runtime_session_key, "persona:linyin:private:10001")
        self.assertEqual(linyin.persona_id, "linyin")
        self.assertTrue(linyin.memory_v2_active)

    def test_v2_actor_without_its_memory_namespace_fails_closed(self):
        scope = self.module.resolve_scene_private_scope(
            self.routing_settings(memory_bot_ids=frozenset()),
            speaker="linyin",
            owner_id="10001",
            aike_bot_id="20001",
            linyin_bot_id="20002",
        )

        self.assertIsNone(scope)

    def test_formatter_marks_private_data_read_only_and_caps_total_size(self):
        history = [
            {"role": "user", "content": f"older-{index}-" + "x" * 180}
            for index in range(12)
        ]
        history.append({"role": "assistant", "content": "latest-private-topic"})

        prompt = self.module.format_scene_private_continuity_context(
            speaker="aike",
            history=history,
            manual_context="manual-memory-" + "y" * 400,
            max_chars=700,
        )

        self.assertLessEqual(len(prompt), 700)
        self.assertIn("只读连续性背景", prompt)
        self.assertIn("不是另一角色可见的记忆", prompt)
        self.assertIn("不得声称另一角色知道这些内容", prompt)
        self.assertIn("latest-private-topic", prompt)
        self.assertNotIn("older-0-", prompt)

    def test_linyin_reads_only_linyin_session_inside_persona_database_scope(self):
        entered_personas: list[str] = []
        history_calls: list[tuple[object, ...]] = []

        @contextlib.contextmanager
        def fake_persona_scope(persona_id):
            entered_personas.append(persona_id)
            yield

        def fake_history(*args):
            history_calls.append(args)
            return [{"role": "assistant", "content": "linyin-private-only"}]

        with (
            patch.object(self.module, "persona_memory_database_scope", fake_persona_scope),
            patch.object(self.module, "build_history", side_effect=fake_history),
            patch.object(
                self.module,
                "format_manual_memory_context",
                return_value="linyin-manual-only",
            ),
        ):
            prompt = self.module.build_scene_private_continuity_context(
                self.routing_settings(),
                speaker="linyin",
                owner_id="10001",
                aike_bot_id="20001",
                linyin_bot_id="20002",
                limits=self.module.ScenePrivateContextLimits(),
            )

        self.assertEqual(entered_personas, ["linyin"])
        self.assertEqual(
            history_calls,
            [("persona:linyin:private:10001", 12, 2, 1)],
        )
        self.assertIn("linyin-private-only", prompt)
        self.assertIn("linyin-manual-only", prompt)
        self.assertNotIn("aike", prompt)

    def test_legacy_aike_reads_only_legacy_owner_private_session(self):
        history_calls: list[tuple[object, ...]] = []

        @contextlib.contextmanager
        def forbidden_persona_scope(_persona_id):
            raise AssertionError("legacy Aike must not enter a Persona V2 database")
            yield

        def fake_history(*args):
            history_calls.append(args)
            return [{"role": "assistant", "content": "aike-private-only"}]

        with (
            patch.object(
                self.module,
                "persona_memory_database_scope",
                forbidden_persona_scope,
            ),
            patch.object(self.module, "build_history", side_effect=fake_history),
            patch.object(
                self.module,
                "format_manual_memory_context",
                return_value="aike-manual-only",
            ),
        ):
            prompt = self.module.build_scene_private_continuity_context(
                self.routing_settings(),
                speaker="aike",
                owner_id="10001",
                aike_bot_id="20001",
                linyin_bot_id="20002",
                limits=self.module.ScenePrivateContextLimits(),
            )

        self.assertEqual(history_calls, [("private:10001", 12, 2, 1)])
        self.assertIn("aike-private-only", prompt)
        self.assertIn("aike-manual-only", prompt)
        self.assertNotIn("linyin-private-only", prompt)

    def test_loader_uses_reads_only_and_never_runs_rag_or_memory_writes(self):
        source = Path(self.module.__file__).read_text(encoding="utf-8")

        self.assertIn("build_history(", source)
        self.assertIn("format_manual_memory_context(", source)
        self.assertNotIn("retrieve_memory", source)
        self.assertNotIn("append_message", source)
        self.assertNotIn("add_summary", source)
        self.assertNotIn("add_manual_memory", source)
        self.assertNotIn("upsert_gap_scene_summary", source)


if __name__ == "__main__":
    unittest.main()
