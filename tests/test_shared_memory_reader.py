from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from pure_ai_chat_loader import AI_CHAT_ROOT, load_legacy_memory_modules, load_module, load_rag_modules
from src.bilibili_memory import MemoryScope, read_snapshot


STAMP = "2026-10-20T12:00:00+00:00"


class Embedder:
    provider, model = "unit", "shared-memory"

    def __init__(self, vector=(1.0, 0.0), fail=False):
        self.vector, self.fail, self.calls = list(vector), fail, []

    def embed(self, text):
        self.calls.append(text)
        if self.fail:
            raise RuntimeError("PRIVATE_PROVIDER_ERROR_MUST_NOT_LEAK")
        return self.vector


class SharedMemoryReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qq = load_legacy_memory_modules()
        cls.rag = load_rag_modules()
        cls.reader = load_module("src.plugins.ai_chat.memory_reader", AI_CHAT_ROOT / "memory_reader.py")
        cls.providers = importlib.import_module("src.plugins.ai_chat.rag.providers")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "private.db"
        self.database = self.qq["database"]
        scope = self.database.database_path_scope(self.path)
        scope.__enter__()
        self.addCleanup(scope.__exit__, None, None, None)
        self.database.ensure_database()
        self.scope = MemoryScope("11111", "22222", "private:11111", self.path, "legacy")
        self.config = NS(max_context_messages=40, max_session_summaries_in_context=1,
                         enable_gap_scene_summaries=True, max_gap_scene_summaries_in_context=2,
                         enable_long_term_memory_context=True, max_long_term_memories_in_context=4,
                         enable_memory_rag=True, memory_rag_inject_in_chat=True,
                         memory_rag_top_k=5, memory_rag_min_score=0.55, memory_rag_max_context_chars=1600,
                         memory_rag_embedding_provider="unit", memory_rag_embedding_model="shared-memory")
        self.embedder = Embedder()

    def add_summary(self, ident, body, *, session=None, owner=None, kind="private", group=None):
        with self.database.connect() as c:
            c.execute("INSERT INTO session_summaries(id,session_key,message_type,user_id,group_id,summary,"
                      "message_start_id,message_end_id,source_message_count,created_at) VALUES(?,?,?,?,?,?,1,40,40,?)",
                      (ident, session or self.scope.session, kind, owner or self.scope.qq_owner, group, body, STAMP))

    def add_manual(self, ident, body, *, owner=None, kind="fact_summary", source=None):
        with self.database.connect() as c:
            c.execute("INSERT INTO long_term_memories(id,subject_type,subject_id,memory_type,content,source_session_key,"
                      "confidence,created_at,updated_at) VALUES(?,'user',?,?,?,?,1,?,?)",
                      (ident, owner or self.scope.qq_owner, kind, body, source, STAMP, STAMP))

    def index_summary(self, ident, body, *, session=None, owner=None, vector=(1.0, 0.0)):
        return self.index(str(ident), body, source_type="session_summary", session_key=session or self.scope.session,
                          message_type="private", user_id=owner or self.scope.qq_owner, vector=vector)

    def index(self, source_id, body, *, vector=(1.0, 0.0), **kwargs):
        ident = self.rag["documents"].upsert_rag_document(
            namespace="semantic_memory", source_id=source_id, title="Synthetic memory",
            content=body, visibility="owner_only", source_version=STAMP, **kwargs)
        doc = self.rag["documents"].get_rag_document(ident)
        self.rag["embeddings"].upsert_rag_embedding(document_id=ident, provider=self.embedder.provider,
                                                   model=self.embedder.model, embedding=list(vector),
                                                   content_hash=doc.content_hash)
        return ident

    def load(self):
        return read_snapshot(self.scope, self.config)

    def context(self, snapshot):
        with patch.object(self.providers, "build_embedding_provider", return_value=self.embedder):
            return snapshot.context({"video": {"title": "PUBLIC_VIDEO_QUERY"}})

    def test_qq_and_bilibili_use_same_order_counts_text_and_scene_card(self):
        with self.database.connect() as c:
            c.executemany("INSERT INTO messages(session_key,message_type,user_id,role,content,created_at)"
                          " VALUES(?,'private',?,'user',?,?)",
                          [(self.scope.session, self.scope.qq_owner, f"message-{n}", STAMP) for n in range(50)])
            c.execute("INSERT INTO gap_scene_summaries(session_key,slot,summary,message_start_id,message_end_id,"
                      "source_message_count,created_at,updated_at) VALUES(?,1,'LIVE_SCENE',1,10,10,?,?)",
                      (self.scope.session, STAMP, STAMP))
        self.add_summary(1, "OLDER_SUMMARY")
        self.add_summary(2, "LATEST_SUMMARY")
        for n in range(6):
            self.add_manual(n + 1, f"manual-{n}")
        snapshot = self.load()
        now = self.reader.datetime.now(self.reader.timezone.utc)
        with patch.object(self.qq["memory"], "datetime") as clock:
            clock.now.return_value = now
            qq_history = self.qq["memory"].build_history(self.scope.session, 40, 1, 2)
        self.assertEqual(qq_history, snapshot.records.history(now=now))
        self.assertEqual(len(snapshot.recent), 40)
        self.assertEqual(snapshot.recent[0]["content"], "message-10")
        self.assertEqual([r["summary"] for r in snapshot.summaries], ["LATEST_SUMMARY"])
        self.assertEqual([r["summary"] for r in snapshot.scene_cards], ["LIVE_SCENE"])
        qq_manual = self.qq["manual_memory"].list_manual_memories("user", self.scope.qq_owner, 4)
        self.assertEqual([m.content for m in qq_manual], [r["content"] for r in snapshot.long_term])

    def test_read_and_snapshot_retrieval_never_initialize_or_modify_database(self):
        self.add_summary(1, "OLD_MATCH")
        self.index_summary(1, "OLD_MATCH")
        before = self.path.read_bytes()
        with (patch.object(self.database, "ensure_database", side_effect=AssertionError("migration")),
              patch.object(self.rag["search"], "ensure_database", side_effect=AssertionError("index initialization"))):
            snapshot = self.load()
            payload, measured = self.context(snapshot)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(measured["semantic_retrieval_status"], "matched")
        self.assertEqual(payload["semantic_memory"][0]["text"], "OLD_MATCH")

    def test_semantic_recall_uses_qq_search_and_can_recall_older_than_fixed_summary(self):
        self.add_summary(1, "OLD_MATCH")
        self.add_summary(2, "LATEST_UNRELATED")
        self.index_summary(1, "OLD_MATCH")
        self.index_summary(2, "LATEST_UNRELATED", vector=(0.0, 1.0))
        snapshot = self.load()
        qq_hits = self.rag["memory_index"].retrieve_memory(
            query="PUBLIC_VIDEO_QUERY", embedder=self.embedder, is_owner=True, audience=snapshot.audience,
            top_k=self.config.memory_rag_top_k, min_score=self.config.memory_rag_min_score,
            max_context_chars=self.config.memory_rag_max_context_chars)
        payload, _ = self.context(snapshot)
        self.assertEqual(payload["summaries"][0]["text"], "LATEST_UNRELATED")
        self.assertEqual([h["text"] for h in payload["semantic_memory"]], [h.document.content for h in qq_hits])
        self.assertEqual([h["text"] for h in payload["semantic_memory"]], ["OLD_MATCH"])

    def test_private_audience_and_source_provenance_are_filtered_before_top_k(self):
        self.config.memory_rag_top_k = 1
        self.add_summary(1, "VALID_MATCH")
        self.index_summary(1, "VALID_MATCH", vector=(0.8, 0.6))
        self.add_summary(2, "OTHER_OWNER_SECRET", session="private:99999", owner="99999")
        self.index_summary(2, "OTHER_OWNER_SECRET", session="private:99999", owner="99999")
        self.add_manual(1, "GROUP_SOURCED_SECRET", source="group:88888")
        self.index("1", "GROUP_SOURCED_SECRET", source_type="manual_fact",
                   subject_type="user", subject_id=self.scope.qq_owner)
        payload, _ = self.context(self.load())
        self.assertEqual([h["text"] for h in payload["semantic_memory"]], ["VALID_MATCH"])
        self.assertNotIn("SECRET", json.dumps(payload))

    def test_deleted_or_changed_source_is_not_resurrected_from_old_index(self):
        self.add_summary(1, "DELETED_SOURCE")
        self.add_summary(2, "STALE_SOURCE")
        self.index_summary(1, "DELETED_SOURCE")
        self.index_summary(2, "STALE_SOURCE")
        with self.database.connect() as c:
            c.execute("DELETE FROM session_summaries WHERE id=1")
            c.execute("UPDATE session_summaries SET summary='CURRENT_SOURCE' WHERE id=2")
        snapshot = self.load()
        payload, _ = self.context(snapshot)
        self.assertEqual(snapshot.semantic_status, "empty")
        self.assertEqual(payload["semantic_memory"], [])
        self.assertNotIn("STALE_SOURCE", json.dumps(payload))
        self.assertEqual(self.embedder.calls, [])

    def test_no_semantic_match_does_not_fall_back_to_keyword_or_old_memory(self):
        self.add_summary(1, "OLD_WORD_MATCH")
        self.add_summary(2, "NEWEST_CONTEXT")
        self.index_summary(1, "OLD_WORD_MATCH", vector=(0.0, 1.0))
        payload, measured = self.context(self.load())
        self.assertEqual(payload["semantic_memory"], [])
        self.assertEqual(measured["semantic_retrieval_status"], "no_match")
        self.assertEqual(payload["summaries"][0]["text"], "NEWEST_CONTEXT")

    def test_provider_failure_is_visible_sanitized_and_not_retried(self):
        self.add_summary(1, "BASE_CONTEXT")
        self.index_summary(1, "BASE_CONTEXT")
        self.embedder.fail = True
        payload, measured = self.context(self.load())
        self.assertEqual(measured["semantic_retrieval_status"], "retrieval_unavailable")
        self.assertNotIn("PRIVATE_PROVIDER_ERROR", json.dumps((payload, measured)))
        self.assertEqual([q.strip() for q in self.embedder.calls], ["PUBLIC_VIDEO_QUERY"])
        self.assertEqual(payload["summaries"][0]["text"], "BASE_CONTEXT")

    def test_disabled_rag_never_embeds_or_reads_index(self):
        self.config.memory_rag_inject_in_chat = False
        snapshot = self.load()
        with patch.object(self.providers, "build_embedding_provider", side_effect=AssertionError("embedding")):
            payload, measured = snapshot.context({"video": {"title": "PUBLIC_QUERY"}})
        self.assertEqual(measured["semantic_retrieval_status"], "disabled")
        self.assertEqual(payload["semantic_memory"], [])

    def test_missing_index_is_reported_without_creating_tables(self):
        with self.database.connect() as c:
            c.execute("DROP TABLE rag_embeddings")
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        snapshot = self.load()
        self.assertEqual(snapshot.semantic_status, "index_missing")
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), before)

    def test_existing_index_is_read_once_and_snapshot_survives_database_removal(self):
        self.add_summary(1, "FROZEN_CONTEXT")
        self.index_summary(1, "FROZEN_CONTEXT")
        snapshot = self.load()
        self.path.unlink()
        payload, _ = self.context(snapshot)
        self.assertEqual(payload["semantic_memory"][0]["text"], "FROZEN_CONTEXT")
        self.assertFalse(self.path.exists())

    def test_context_and_status_omit_private_identifiers_and_database_paths(self):
        self.add_summary(1, "PLAIN_MEMORY")
        self.index_summary(1, "PLAIN_MEMORY")
        snapshot = self.load()
        payload, measured = self.context(snapshot)
        encoded = json.dumps((payload, measured, snapshot.public_status()))
        for secret in (self.scope.qq_owner, self.scope.qq_bot, self.scope.session, str(self.path)):
            self.assertNotIn(secret, encoded)
        self.assertEqual(measured["included_counts"]["semantic_memory"], 1)
        self.assertEqual([q.strip() for q in self.embedder.calls], ["PUBLIC_VIDEO_QUERY"])

    def test_read_callback_is_enforced_read_only_by_sqlite(self):
        before = self.path.read_bytes()

        def attempt_write(connection):
            connection.execute("DELETE FROM messages")

        with self.assertRaises(sqlite3.OperationalError):
            self.reader.read_conversation_memory(self.path, self.scope.session, self.reader.MemoryReadPolicy(recent=40),
                                                 read_extra=attempt_write)
        self.assertEqual(self.path.read_bytes(), before)

    def test_session_mismatch_is_rejected_before_returning_records(self):
        audience = self.load().audience
        with self.assertRaises(ValueError):
            self.reader.read_conversation_memory(self.path, "private:99999", self.reader.MemoryReadPolicy(recent=40),
                                                 audience=audience)


if __name__ == "__main__":
    unittest.main()
