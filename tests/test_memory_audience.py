from __future__ import annotations

import ast
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pure_ai_chat_loader import (
    AI_CHAT_ROOT, load_legacy_memory_modules, load_module,
    load_pure_graph_modules, load_rag_modules,
)


def plugin_functions(names, namespace):
    """Execute actual entry functions without starting NoneBot or live storage."""
    tree = ast.parse((AI_CHAT_ROOT / "__init__.py").read_text(encoding="utf-8"))
    nodes = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names
    ]
    if len(nodes) != len(names):
        raise AssertionError("Requested plugin functions are missing")
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *nodes,
    ], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), "<plugin-functions>", "exec"), namespace)
    return namespace


class GroupEvent:
    message_type = "group"
    user_id = "owner"
    group_id = "current"


class PrivateEvent:
    message_type = "private"
    user_id = "owner"


class FakeEmbedder:
    provider = "unit"
    model = "audience"

    def __init__(self):
        self.calls = []

    def embed(self, query):
        self.calls.append(query)
        return [1.0, 0.0]


class MemoryAudienceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rag = load_rag_modules()
        cls.legacy = load_legacy_memory_modules()
        cls.Audience = load_module(
            "src.plugins.ai_chat.memory_audience", AI_CHAT_ROOT / "memory_audience.py"
        ).MemoryAudience

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_scope = self.rag["database"].database_path_scope(Path(self.temp.name) / "test.db")
        self.db_scope.__enter__()
        self.addCleanup(self.db_scope.__exit__, None, None, None)
        self.embedder = FakeEmbedder()

    def add_document(self, source_id, vector=(1.0, 0.0), **fields):
        documents = self.rag["documents"]
        doc_id = documents.upsert_rag_document(
            namespace="semantic_memory", source_type=fields.pop("source_type", "session_summary"),
            source_id=source_id, title=source_id, content=source_id,
            visibility="owner_only", **fields,
        )
        document = documents.get_rag_document(doc_id)
        self.rag["embeddings"].upsert_rag_embedding(
            document_id=doc_id, provider="unit", model="audience",
            embedding=list(vector), content_hash=document.content_hash,
        )

    def retrieve(self, audience, **kwargs):
        return self.rag["memory_index"].retrieve_memory(
            query="remember", embedder=self.embedder, is_owner=True,
            min_score=0.0, audience=audience, **kwargs,
        )

    def test_group_filters_private_and_other_group_before_top_k(self):
        self.add_document("private-secret", session_key="private:owner", message_type="private")
        self.add_document("other-group", session_key="group:other", message_type="group", group_id="other")
        self.add_document("current-group", vector=(0.8, 0.6), session_key="group:current", message_type="group", group_id="current")
        results = self.retrieve(self.Audience("group", "owner", "current", "group:current"), top_k=1)
        self.assertEqual([item.document.content for item in results], ["current-group"])

    def test_private_preserves_own_summary_and_manual_memory(self):
        self.add_document("own-summary", session_key="persona:linyin:private:owner", message_type="private")
        self.add_document("other-summary", session_key="persona:linyin:private:other", message_type="private")
        self.add_document("own-fact", source_type="manual_fact", subject_type="user", subject_id="owner")
        self.add_document("legacy-own-fact", source_type="manual_fact", subject_type="private", subject_id="owner")
        self.add_document("other-fact", source_type="manual_fact", subject_type="user", subject_id="other")
        results = self.retrieve(self.Audience("private", "owner", session_key="persona:linyin:private:owner"), top_k=10)
        self.assertEqual({item.document.content for item in results}, {"own-summary", "own-fact", "legacy-own-fact"})

    def test_group_manual_memories_exclude_personal_preferences_and_other_groups(self):
        for name, subject_type, subject_id in [
            ("personal", "user", "owner"), ("local-group", "group", "current"),
            ("other-group", "group", "other"),
        ]:
            self.add_document(name, source_type="manual_preference", subject_type=subject_type, subject_id=subject_id)
        results = self.retrieve(self.Audience("group", "owner", "current", "group:current"))
        self.assertEqual([item.document.content for item in results], ["local-group"])

    def test_invalid_scope_and_inconsistent_group_metadata_fail_closed(self):
        self.add_document("wrong-metadata", session_key="group:current", message_type="private", group_id="current")
        self.add_document("missing-group", session_key="group:current", message_type="group")
        for audience in [self.Audience("group", "owner", "current", "group:current"), self.Audience("unknown", "owner")]:
            with self.subTest(audience=audience):
                self.assertEqual(self.retrieve(audience), [])

    def test_nonowner_is_denied_before_embedding(self):
        results = self.rag["memory_index"].retrieve_memory(
            query="secret", embedder=self.embedder, is_owner=False,
            audience=self.Audience("group", "other", "current", "group:current"),
        )
        self.assertEqual(results, [])
        self.assertEqual(self.embedder.calls, [])

    def test_manual_context_and_preference_writes_use_current_audience(self):
        manual = self.legacy["manual_memory"]
        with patch.dict("os.environ", {"ENABLE_MEMORY_RAG": "false"}):
            manual.add_manual_memory("user", "owner", "PRIVATE_FACT")
            manual.add_manual_memory("group", "current", "GROUP_FACT")
            manual.add_manual_memory("group", "other", "OTHER_GROUP_FACT")
        ns = plugin_functions({
            "memory_audience_for_event", "manual_memory_subjects", "manual_long_term_context",
            "fact_memory_subject", "preference_memory_subject",
        }, {
            "MemoryAudience": self.Audience, "GroupMessageEvent": GroupEvent,
            "user_id": lambda event: event.user_id, "group_id": lambda event: event.group_id,
            "config": SimpleNamespace(enable_long_term_memory_context=True, max_long_term_memories_in_context=10),
            "format_manual_memory_context": manual.format_manual_memory_context,
        })
        group = ns["manual_long_term_context"](GroupEvent())
        private = ns["manual_long_term_context"](PrivateEvent())
        self.assertIn("GROUP_FACT", group)
        self.assertNotIn("PRIVATE_FACT", group)
        self.assertNotIn("OTHER_GROUP_FACT", group)
        self.assertIn("PRIVATE_FACT", private)
        self.assertNotIn("GROUP_FACT", private)
        self.assertEqual(ns["preference_memory_subject"](GroupEvent()), ("group", "current"))
        self.assertEqual(ns["preference_memory_subject"](PrivateEvent()), ("user", "owner"))


class MemoryAudienceEntryTests(unittest.IsolatedAsyncioTestCase):
    async def test_normal_chat_and_debug_query_pass_actual_group_scope(self):
        graphs = load_pure_graph_modules()
        graph = graphs["memory"]
        retrieval_graph = graphs["retrieval"]
        audience = load_module("src.plugins.ai_chat.memory_audience", AI_CHAT_ROOT / "memory_audience.py").MemoryAudience
        captured = []

        def retrieval(**kwargs):
            captured.append(kwargs["audience"])
            return []

        async def noop(*args):
            return None

        ns = {
            "asyncio": asyncio, "MemoryAudience": audience, "GroupMessageEvent": GroupEvent,
            "user_id": lambda event: event.user_id, "group_id": lambda event: event.group_id,
            "is_owner": lambda config, event: True, "retrieve_memory": retrieval,
            "build_embedding_provider": lambda config: FakeEmbedder(),
            "MEMORY_RAG_SOURCE_TYPES": {"session_summary"},
            "conversation_scope": lambda event: SimpleNamespace(
                runtime_session_key="persona:linyin:group:current", routing_v2_active=False, memory_v2_active=False, configuration_error=""
            ),
            "config": SimpleNamespace(
                enable_memory_rag=True, memory_rag_inject_in_chat=True,
                memory_rag_owner_only_debug=True, memory_rag_top_k=5,
                memory_rag_min_score=0.5, memory_rag_max_context_chars=1600,
                max_context_messages=10, max_session_summaries_in_context=3,
                max_gap_scene_summaries_in_context=2,
            ),
            "language_reset_context": lambda: "", "speaker_identity_context": lambda event: "",
            "owner_public_context": lambda: "", "ensure_gap_scene_summaries": noop,
            "manual_long_term_context": lambda event: "", "semantic_memory_hit_snapshots": lambda hits: [],
            "format_semantic_memory_context": lambda hits: "", "consume_topic_switch_hint": lambda key: "",
            "reunion_hint_for_chat": lambda event, key: "", "build_history": lambda *args: [],
            "rule_reminder_context": lambda key: "", "format_memory_retrieval_reply": lambda *args: "no hits",
            "log_background_error": lambda *args: None,
        }
        ns.update({name: getattr(graph, name) for name in [
            "MemoryContext", "MemoryContextGraphRunner",
        ]})
        ns.update({name: getattr(retrieval_graph, name) for name in [
            "MemoryRetrievalState", "MemoryRetrievalAction", "MemoryRetrievalGraphRunner",
        ]})
        plugin_functions({"memory_audience_for_event", "run_memory_context_graph", "run_memory_retrieval_graph"}, ns)
        chat = await ns["run_memory_context_graph"](GroupEvent(), "persona:linyin:group:current", "query")
        debug = await ns["run_memory_retrieval_graph"](GroupEvent(), retrieval_graph.MemoryRetrievalAction.QUERY, "query")
        self.assertFalse(chat.result.semantic_memory_error)
        self.assertFalse(debug.state.error)
        self.assertEqual(captured, [audience("group", "owner", "current", "persona:linyin:group:current")] * 2)


if __name__ == "__main__":
    unittest.main()
