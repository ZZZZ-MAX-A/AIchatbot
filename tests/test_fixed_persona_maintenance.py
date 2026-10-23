from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from unittest.mock import AsyncMock

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module, load_pure_graph_modules
from test_memory_audience import plugin_functions


class FixedPersonaMaintenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_ai_chat_packages()
        cls.scope = load_module("src.plugins.ai_chat.persona_scope", AI_CHAT_ROOT / "persona_scope.py")
        cls.cards = load_module("src.plugins.ai_chat.role_cards", AI_CHAT_ROOT / "role_cards.py")
        cls.config = load_module("src.plugins.ai_chat.config", AI_CHAT_ROOT / "config.py")
        cls.maintenance = load_module("src.plugins.ai_chat.persona_maintenance", AI_CHAT_ROOT / "persona_maintenance.py")
        cls.routes = load_module("src.plugins.ai_chat.completion_routes", AI_CHAT_ROOT / "completion_routes.py")
        cls.graphs = load_pure_graph_modules()

    def configuration(self, **overrides):
        values = {
            "BOT_PERSONA_BINDINGS": "2000000001=aike:aike;3000000001=linyin:linyin",
            "ENABLE_PERSONA_ROUTING_V2": "true", "ENABLE_PERSONA_MEMORY_V2": "true",
            "PERSONA_ROUTING_V2_BOT_IDS": "3000000001", "PERSONA_MEMORY_V2_BOT_IDS": "3000000001",
            "AIKE_LLM_API_KEY": "TEST-DEFAULT", "AIKE_LLM_MODEL": "default-model",
            "ENABLE_PERSONA_LLM_ROUTING": "true", "PERSONA_LLM_ROLE_CARD_KEYS": "aike,linyin",
            "PERSONA_LLM_API_KEY": "TEST-PERSONA", "PERSONA_LLM_BASE_URL": "https://persona.example/v1",
            "PERSONA_LLM_MODEL": "persona-model",
        }
        values.update(overrides)
        return self.config.load_config(values)

    def resolve(self, config, bot="2000000001", cards=frozenset({"aike", "linyin"})):
        return self.scope.resolve_conversation_scope(
            config.persona_routing, bot_self_id=bot, user_id="1000000001",
            chat_type="private", legacy_session_key="private:1000000001",
            available_role_card_keys=cards,
        )

    def test_fixed_identity_preserves_both_storage_namespaces_and_routes(self):
        config = self.configuration()
        aike, linyin = self.resolve(config), self.resolve(config, "3000000001")
        self.assertEqual((aike.persona_id, aike.role_card_key, aike.runtime_session_key),
                         ("aike", "aike", "private:1000000001"))
        self.assertEqual(linyin.runtime_session_key, "persona:linyin:private:1000000001")
        self.assertTrue(linyin.memory_v2_active)
        self.assertEqual(self.routes.resolve_chat_completion_route(config, aike.role_card_key).model, "default-model")
        self.assertEqual(self.routes.resolve_chat_completion_route(config, linyin.role_card_key).model, "persona-model")

    def test_unbound_account_has_no_borrowed_identity(self):
        scope = self.resolve(self.configuration(), "4000000001")
        self.assertEqual((scope.persona_id, scope.role_card_key, scope.runtime_mode), ("", "", "invalid"))
        self.assertIn("missing_persona_binding", scope.configuration_error)

    def test_legacy_account_missing_card_is_invalid(self):
        scope = self.resolve(self.configuration(), cards=frozenset({"linyin"}))
        self.assertIn("missing_role_card", scope.configuration_error)

    def test_nonlegacy_bound_account_cannot_borrow_legacy_storage(self):
        config = self.configuration(ENABLE_PERSONA_ROUTING_V2="false", ENABLE_PERSONA_MEMORY_V2="false")
        self.assertIn("nonlegacy_persona_requires_routing_v2", self.resolve(config, "3000000001").configuration_error)

    def test_conflicting_cards_for_one_persona_fail_closed(self):
        config = self.configuration(BOT_PERSONA_BINDINGS="2000000001=aike:aike;3000000001=aike:linyin")
        self.assertIn("conflicting_persona_role_cards", config.persona_routing.binding_errors)
        self.assertTrue(self.resolve(config).configuration_error)

    def test_binding_report_is_sanitized_and_checks_card_availability(self):
        config = self.configuration()
        report = self.maintenance.build_persona_binding_report(config, available_role_card_keys=frozenset({"aike"}))
        self.assertFalse(report["ready"])
        self.assertTrue(report["rows"][0]["ready"])
        self.assertIn("missing_role_card", report["rows"][1]["errors"])
        encoded = json.dumps(report)
        for value in ("2000000001", "3000000001", "TEST-DEFAULT", "TEST-PERSONA", "persona.example"):
            self.assertNotIn(value, encoded)

    def test_unknown_allowlisted_account_invalidates_preflight(self):
        config = self.configuration(PERSONA_MEMORY_V2_BOT_IDS="3000000001,4000000001")
        report = self.maintenance.build_persona_binding_report(config, available_role_card_keys={"aike", "linyin"})
        self.assertIn("unbound_allowlisted_account", report["errors"])

    def test_stale_persona_approval_cannot_fall_back_after_v2_disabled(self):
        config = self.configuration(ENABLE_PERSONA_ROUTING_V2="false", ENABLE_PERSONA_MEMORY_V2="false")
        with patch.object(self.maintenance, "role_card_by_key", return_value=object()):
            with self.assertRaisesRegex(RuntimeError, "invalid_persona_memory_scope"):
                self.maintenance.resolve_memory_session_scope(config, "persona:linyin:private:1000000001")

    def test_approval_targets_preserve_legacy_and_persona_storage(self):
        with patch.object(self.maintenance, "role_card_by_key", return_value=object()):
            aike = self.maintenance.resolve_memory_session_scope(self.configuration(), "private:1000000001")
            linyin = self.maintenance.resolve_memory_session_scope(self.configuration(), "persona:linyin:private:1000000001")
        self.assertFalse(aike.memory_v2_active)
        self.assertTrue(linyin.memory_v2_active)

    def test_missing_card_and_ephemeral_memory_reject_approved_writes(self):
        with patch.object(self.maintenance, "role_card_by_key", return_value=None):
            with self.assertRaises(RuntimeError):
                self.maintenance.resolve_memory_session_scope(self.configuration(), "private:1000000001")
        with patch.object(self.maintenance, "role_card_by_key", return_value=object()):
            with self.assertRaisesRegex(RuntimeError, "persona_persistent_memory_unavailable"):
                self.maintenance.resolve_memory_session_scope(
                    self.configuration(ENABLE_PERSONA_MEMORY_V2="false"), "persona:linyin:private:1000000001")

    def test_invalid_admin_requests_never_invoke_any_writer(self):
        graph = self.graphs["memory"]
        config = self.configuration()
        scenarios = [self.resolve(config, cards={"aike"}, bot="3000000001"),
                     self.resolve(config, bot="4000000001"),
                     self.resolve(self.configuration(ENABLE_PERSONA_ROUTING_V2="false"), bot="3000000001")]
        for scope in scenarios:
            with self.subTest(error=scope.configuration_error):
                ns = {"conversation_scope": lambda event: scope,
                      "MemoryAdminAction": graph.MemoryAdminAction, "MemoryAdminState": graph.MemoryAdminState,
                      "MemoryAdminGraphRunner": graph.MemoryAdminGraphRunner,
                      "INVALID_PERSONA_MESSAGE": self.maintenance.INVALID_PERSONA_MESSAGE}
                plugin_functions({"run_memory_admin_graph"}, ns)
                # No persistence functions are injected; any access fails the test.
                for action in (graph.MemoryAdminAction.ADD_FACT_MEMORY, graph.MemoryAdminAction.CLEAR_ALL_CONTEXT,
                               graph.MemoryAdminAction.DELETE_LONG_TERM_MEMORY, graph.MemoryAdminAction.VIEW_LONG_TERM_MEMORY):
                    result = asyncio.run(ns["run_memory_admin_graph"](object(), action, content="test", target_id="1"))
                    self.assertEqual(result.result.error, "invalid_persona_scope")

    def test_invalid_retrieval_and_diagnostics_never_read_database(self):
        scope = self.resolve(self.configuration(), "4000000001")
        retrieval, diagnostics = self.graphs["retrieval"], self.graphs["diagnostics"]
        ns = {"conversation_scope": lambda event: scope, "user_id": lambda event: "1000000001",
              "config": SimpleNamespace(), "is_owner": lambda *args: True,
              "INVALID_PERSONA_MESSAGE": self.maintenance.INVALID_PERSONA_MESSAGE,
              "MemoryRetrievalState": retrieval.MemoryRetrievalState,
              "MemoryRetrievalAction": retrieval.MemoryRetrievalAction,
              "MemoryRetrievalGraphRunner": retrieval.MemoryRetrievalGraphRunner,
              "DiagnosticsState": diagnostics.DiagnosticsState, "DiagnosticsView": diagnostics.DiagnosticsView,
              "DiagnosticsGraphRunner": diagnostics.DiagnosticsGraphRunner}
        plugin_functions({"run_memory_retrieval_graph", "run_diagnostics_graph"}, ns)
        result = asyncio.run(ns["run_memory_retrieval_graph"](object(), retrieval.MemoryRetrievalAction.REBUILD))
        self.assertEqual(result.result.error, "invalid_persona_scope")
        result = asyncio.run(ns["run_diagnostics_graph"](object()))
        self.assertEqual(result.result.error, "invalid_persona_scope")

    def test_invalid_reset_does_not_touch_default_history(self):
        # Command decorators are excluded when extracting the actual handler.
        import ast
        tree = ast.parse((AI_CHAT_ROOT / "__init__.py").read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.decorator_list
                    and ast.unparse(n.decorator_list[0]) == "reset_cmd.handle()")
        node.decorator_list = []
        ns = {"conversation_scope": lambda e: self.resolve(self.configuration(), "4000000001"),
              "INVALID_PERSONA_MESSAGE": self.maintenance.INVALID_PERSONA_MESSAGE}
        module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), node], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), "<reset-handler>", "exec"), ns)
        replies = []
        async def finish(text): replies.append(text)
        asyncio.run(ns["_"](object(), SimpleNamespace(finish=finish)))
        self.assertEqual(replies, [self.maintenance.INVALID_PERSONA_MESSAGE])

    def test_corrupt_private_override_never_borrows_public_card(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); private, public = root / "private", root / "public"
            private.mkdir(); public.mkdir()
            (public / "aike.md").write_text("# Other copy", encoding="utf-8")
            (private / "aike.md").write_bytes(b"\xff")
            with patch.object(self.cards, "PRIVATE_ROLE_CARD_DIR", private), patch.object(self.cards, "PUBLIC_ROLE_CARD_DIR", public), patch.object(self.cards, "ROLE_CARD_DIR", root):
                self.assertIsNone(self.cards.role_card_by_key("aike"))

    def test_loading_one_card_does_not_scan_unrelated_broken_card(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "aike.md").write_text("# Fixed\ncontent", encoding="utf-8")
            (root / "other.md").write_bytes(b"\xff")
            with patch.object(self.cards, "PRIVATE_ROLE_CARD_DIR", root), patch.object(self.cards, "PUBLIC_ROLE_CARD_DIR", root), patch.object(self.cards, "ROLE_CARD_DIR", root):
                self.assertEqual(self.cards.role_card_by_key("aike").key, "aike")

    def test_world_background_policy_preserves_normal_legacy_and_scene_behavior(self):
        llm = load_module("src.plugins.ai_chat.llm", AI_CHAT_ROOT / "llm.py")
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="reply", tool_calls=[]))])
        create = AsyncMock(return_value=response)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.object(llm, "AsyncOpenAI", return_value=client), patch.object(llm, "load_system_prompt", return_value="system"), patch.object(llm, "load_base_chat_prompt", return_value=""), patch.object(llm, "load_persona_prompt", return_value="fixed persona"), patch.object(llm, "load_world_card_prompt", return_value="shared world") as world:
            asyncio.run(llm.ask_llm(self.configuration(), [], "test", role_card_key="aike", include_world_card=False))
            world.assert_not_called()
            self.assertFalse(any(item["content"] == "shared world" for item in create.call_args.kwargs["messages"]))
            asyncio.run(llm.ask_llm(self.configuration(), [], "test", role_card_key="aike"))
            world.assert_called_once_with("aike")
            self.assertTrue(any(item["content"] == "shared world" for item in create.call_args.kwargs["messages"]))

    def test_qq_request_always_carries_fixed_card_without_migrating_legacy_memory(self):
        contracts = load_module("src.plugins.ai_chat.chat_contracts", AI_CHAT_ROOT / "chat_contracts.py")
        ns = {"conversation_scope": lambda e: self.resolve(self.configuration()),
              "ChatRequest": contracts.ChatRequest, "tts_enabled_for_event": lambda e: True}
        plugin_functions({"chat_request_for_event"}, ns)
        request = ns["chat_request_for_event"](object(), "test", contracts.ChatImageContext([], False))
        self.assertEqual(request.role_card_key, "aike")
        self.assertEqual(request.key, "private:1000000001")
        self.assertTrue(request.persistent_memory_enabled)
        self.assertFalse(request.persona_memory_enabled)

    def test_legacy_chat_and_semantic_voice_reject_invalid_binding_before_preparation(self):
        replies = []
        async def finish(text): replies.append(text)
        ns = {"conversation_scope": lambda e: self.resolve(self.configuration(), "4000000001"),
              "check_access": AsyncMock(), "INVALID_PERSONA_MESSAGE": self.maintenance.INVALID_PERSONA_MESSAGE}
        plugin_functions({"prepare_chat_request", "run_legacy_chat_session"}, ns)
        matcher = SimpleNamespace(finish=finish)
        result = asyncio.run(ns["prepare_chat_request"](object(), object(), matcher, object()))
        self.assertIsNone(result)
        result = asyncio.run(ns["run_legacy_chat_session"](object(), object(), matcher, object(), object()))
        self.assertIsNone(result)
        self.assertEqual(replies, [self.maintenance.INVALID_PERSONA_MESSAGE] * 2)

    def test_old_selector_approval_is_not_resumable_from_web_or_execution_layer(self):
        actions = load_module("src.plugins.ai_chat.owner_console_approval_actions", AI_CHAT_ROOT / "owner_console_approval_actions.py")
        context = SimpleNamespace(metadata={"tool_arguments": {"target": "linyin"}}, query="", is_owner=True, is_group=False)
        with self.assertRaisesRegex(RuntimeError, "not_web_resumable"):
            actions._owner_console_write_executor({"command": "select_persona", "target": "linyin"}, context)
        approval = SimpleNamespace(status="pending", expires_at="2099-01-01T00:00:00+00:00", tool_input_json=json.dumps({"command": "select_persona", "target": "linyin"}), tool_name="owner_write_command", risk_level="write_local")
        actionable = actions.OwnerConsoleApprovalActionRuntime(enabled=True).actionability(approval)
        self.assertFalse(actionable.can_approve)
        self.assertTrue(actionable.can_reject)

    def test_web_memory_write_revalidates_scope_before_dispatch(self):
        actions = load_module("src.plugins.ai_chat.owner_console_approval_actions", AI_CHAT_ROOT / "owner_console_approval_actions.py")
        context = SimpleNamespace(metadata={"session_key": "persona:linyin:private:1000000001"})
        with patch.object(self.config, "load_config", return_value=self.configuration(ENABLE_PERSONA_ROUTING_V2="false")), patch.object(self.maintenance, "role_card_by_key", return_value=object()), patch.object(actions, "_execute_owner_console_local_write_scoped") as execute:
            with self.assertRaisesRegex(RuntimeError, "invalid_persona_memory_scope"):
                actions._execute_owner_console_local_write("add_fact_memory", context)
            execute.assert_not_called()

    def test_chat_persistence_rejects_mismatched_namespace_before_writes(self):
        ns = {"conversation_scope": lambda e: self.resolve(self.configuration(), "3000000001")}
        plugin_functions({"persist_scoped_chat_turn", "schedule_scoped_chat_compression"}, ns)
        with self.assertRaisesRegex(RuntimeError, "invalid_persona_memory_scope"):
            asyncio.run(ns["persist_scoped_chat_turn"]("private:1000000001", object(), object(), object()))
        with self.assertRaisesRegex(RuntimeError, "invalid_persona_memory_scope"):
            asyncio.run(ns["schedule_scoped_chat_compression"]("persona:linyin:private:1000000001", object(), persona_memory_id="aike"))

    def test_strict_preflight_rejects_missing_bindings_even_with_default_model(self):
        import importlib.util
        import io
        import sys
        from contextlib import redirect_stdout
        spec = importlib.util.spec_from_file_location("fixed_persona_cli_test", AI_CHAT_ROOT.parents[2] / "scripts/check_configuration.py")
        cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)
        reports = load_module("src.plugins.ai_chat.configuration_report", AI_CHAT_ROOT / "configuration_report.py")
        config = self.configuration(BOT_PERSONA_BINDINGS="", PERSONA_ROUTING_V2_BOT_IDS="", PERSONA_MEMORY_V2_BOT_IDS="")
        with patch.object(cli, "load_configuration_modules", return_value=(self.config, reports)), patch.object(self.config, "load_config", return_value=config), patch.object(sys, "argv", ["check_configuration.py", "--require-chat", "--json"]), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.main(), 1)
        report = json.loads(output.getvalue())
        self.assertTrue(report["default_chat"]["configured"])
        self.assertFalse(report["persona_bindings"]["ready"])


if __name__ == "__main__":
    unittest.main()
