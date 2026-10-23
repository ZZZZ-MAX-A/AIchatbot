from __future__ import annotations

import ast
import asyncio
from copy import deepcopy
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module


class BilibiliContextRuntimeTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        ensure_ai_chat_packages()
        cls.graph = load_module("src.plugins.ai_chat.graph.memory", AI_CHAT_ROOT / "graph/memory.py")
        cls.contracts = load_module("src.plugins.ai_chat.chat_contracts", AI_CHAT_ROOT / "chat_contracts.py")
        cls.config_module = load_module("src.plugins.ai_chat.config", AI_CHAT_ROOT / "config.py")

    def fixture(self, *, private=True, owner=True):
        config = NS(enable_memory_rag=True, memory_rag_inject_in_chat=True,
                    memory_rag_top_k=5, memory_rag_min_score=0.50, memory_rag_max_context_chars=1600,
                    max_context_messages=40, max_session_summaries_in_context=1,
                    max_gap_scene_summaries_in_context=1)
        event = NS(message_type="private" if private else "group", user_id="owner", group_id="group")
        original = [{"role": "system", "content": "QQ_SUMMARY"},
                    {"role": "user", "content": "QQ_HOT_USER"}, {"role": "assistant", "content": "QQ_HOT_AI"}]
        background = Mock(side_effect=lambda cfg, **kw: (
            [kw["history"][0], {"role": "system", "content": "BILIBILI_BACKGROUND"}, *kw["history"][1:]],
            {"status": "included", "recent_rounds": 3, "recalled_messages": 5},
        ))
        ns = {
            "asyncio": asyncio, "MemoryContext": self.graph.MemoryContext,
            "MemoryContextGraphRunner": self.graph.MemoryContextGraphRunner,
            "ChatPromptContext": self.contracts.ChatPromptContext, "config": config,
            "GroupMessageEvent": type("GroupEvent", (), {}),
            "language_reset_context": lambda: "", "speaker_identity_context": lambda event: "",
            "owner_public_context": lambda: "", "user_id": lambda event: event.user_id,
            "group_id": lambda event: event.group_id, "is_owner": lambda cfg, event: owner,
            "ensure_gap_scene_summaries": AsyncMock(), "manual_long_term_context": lambda event: "MANUAL_QQ",
            "build_embedding_provider": Mock(return_value="QQ_EMBEDDER"),
            "retrieve_memory": Mock(return_value=["QQ_HIT"]), "MEMORY_RAG_SOURCE_TYPES": {"session_summary"},
            "memory_audience_for_event": lambda event, key: "QQ_AUDIENCE",
            "semantic_memory_hit_snapshots": lambda hits: list(hits),
            "format_semantic_memory_context": lambda hits: "QQ_RAG_RESULT",
            "consume_topic_switch_hint": lambda key: "", "build_history": Mock(return_value=deepcopy(original)),
            "qq_bilibili_background": background, "conversation_scope": lambda event: "VERIFIED_SCOPE",
            "rule_reminder_context": lambda key: "", "log_background_error": Mock(),
            "current_message_identity_context": lambda event: "CURRENT_QQ_IDENTITY",
        }
        tree = ast.parse((AI_CHAT_ROOT / "__init__.py").read_text(encoding="utf-8"))
        names = {"run_memory_context_graph", "build_chat_prompt_context"}
        nodes = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name in names]
        self.assertEqual(len(nodes), 2)
        module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *nodes], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), "<bilibili-qq-runtime>", "exec"), ns)
        return ns, event, original

    async def test_real_qq_entry_preserves_original_rag_and_places_bilibili_before_hot_messages(self):
        ns, event, original = self.fixture()
        result = await ns["build_chat_prompt_context"](event, "private:owner", "current query",
                                                       semantic_voice=False, has_image_context=False)
        ns["build_history"].assert_called_once()
        args = ns["build_history"].call_args.args
        self.assertEqual(args[1:4], (40, 1, 1))
        self.assertIn("QQ_RAG_RESULT", args[4])
        kwargs = ns["retrieve_memory"].call_args.kwargs
        self.assertEqual((kwargs["top_k"], kwargs["max_context_chars"]), (5, 1600))
        self.assertEqual(result.history[0], original[0])
        self.assertEqual(result.history[1]["content"], "BILIBILI_BACKGROUND")
        self.assertEqual(result.history[2:4], original[1:])
        self.assertEqual(result.semantic_memory_result_count, 1)
        self.assertEqual(result.bilibili_memory_status["recalled_messages"], 5)
        self.assertEqual(result.history[-1]["content"], "CURRENT_QQ_IDENTITY")

    async def test_group_and_non_owner_do_not_read_bilibili(self):
        for private, owner in ((False, True), (True, False)):
            ns, event, original = self.fixture(private=private, owner=owner)
            output = await ns["run_memory_context_graph"](event, "session", "query")
            ns["qq_bilibili_background"].assert_not_called()
            self.assertEqual(list(output.result.history), original)

    async def test_bilibili_failure_cannot_remove_qq_history_or_rag(self):
        ns, event, original = self.fixture()
        ns["qq_bilibili_background"].side_effect = RuntimeError("PRIVATE_PATH_OR_MEMORY")
        output = await ns["run_memory_context_graph"](event, "session", "query")
        self.assertEqual(list(output.result.history), original)
        self.assertEqual(output.result.semantic_memory_result_count, 1)
        self.assertEqual(output.result.bilibili_memory_status, {"status": "unavailable"})
        self.assertEqual(output.result.error, "")

    def test_separate_budget_defaults_and_overrides_do_not_change_qq_limits(self):
        defaults = self.config_module.load_config({})
        self.assertEqual(defaults.bilibili_background_max_tokens, 1200)
        self.assertEqual(defaults.bilibili_background_qq_ratio, 0.20)
        configured = self.config_module.load_config({"BILIBILI_BACKGROUND_MAX_TOKENS": "800",
                                                    "BILIBILI_BACKGROUND_QQ_RATIO": "0.15",
                                                    "MAX_CONTEXT_MESSAGES": "40",
                                                    "MAX_SESSION_SUMMARIES_IN_CONTEXT": "1"})
        self.assertEqual(configured.bilibili_background_max_tokens, 800)
        self.assertEqual(configured.bilibili_background_qq_ratio, 0.15)
        self.assertEqual(configured.max_context_messages, 40)
        self.assertEqual(configured.max_session_summaries_in_context, 1)


if __name__ == "__main__":
    unittest.main()
