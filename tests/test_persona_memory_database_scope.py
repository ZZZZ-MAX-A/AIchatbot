from __future__ import annotations

import asyncio
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from pure_ai_chat_loader import (
    AI_CHAT_ROOT,
    ensure_ai_chat_packages,
    load_legacy_memory_modules,
    load_module,
    load_rag_modules,
)


class PersonaMemoryDatabaseScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.memory_modules = load_legacy_memory_modules()
        cls.rag_modules = load_rag_modules()
        cls.database = cls.memory_modules["database"]
        cls.memory = cls.memory_modules["memory"]
        cls.summaries = cls.memory_modules["summaries"]
        cls.gap_summaries = cls.memory_modules["gap_scene_summaries"]
        cls.manual_memory = cls.memory_modules["manual_memory"]
        cls.documents = cls.rag_modules["documents"]
        cls.embeddings = cls.rag_modules["embeddings"]
        cls.schema = cls.rag_modules["schema"]
        ensure_ai_chat_packages()
        cls.persona_scope = load_module(
            "src.plugins.ai_chat.persona_memory_scope",
            AI_CHAT_ROOT / "persona_memory_scope.py",
        )

    def scoped_paths(self):
        temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(temp_dir.name)
        legacy_path = root / "chatbot.db"
        persona_dir = root / "persona-memory"
        return temp_dir, root, legacy_path, persona_dir

    @staticmethod
    def row_count(path: Path, table: str) -> int:
        with closing(sqlite3.connect(path)) as connection:
            row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        assert row is not None
        return int(row[0])

    def test_default_and_persona_writes_use_different_database_files(self):
        temp_dir, _, legacy_path, persona_dir = self.scoped_paths()
        with (
            temp_dir,
            patch.object(self.database, "DATABASE_PATH", legacy_path),
            patch.object(self.persona_scope, "PERSONA_MEMORY_DIR", persona_dir),
        ):
            self.memory.append_message("private:1", "user", "aike", "private", "1")
            with self.persona_scope.persona_memory_database_scope("linyin"):
                self.memory.append_message(
                    "persona:linyin:private:1",
                    "user",
                    "linyin",
                    "private",
                    "1",
                )

            linyin_path = persona_dir / "linyin.db"
            self.assertEqual(self.row_count(legacy_path, "messages"), 1)
            self.assertEqual(self.row_count(linyin_path, "messages"), 1)
            with closing(sqlite3.connect(legacy_path)) as connection:
                legacy_keys = {
                    row[0] for row in connection.execute("SELECT session_key FROM messages")
                }
            with closing(sqlite3.connect(linyin_path)) as connection:
                persona_keys = {
                    row[0] for row in connection.execute("SELECT session_key FROM messages")
                }
                schema_version = connection.execute(
                    "SELECT value FROM schema_meta WHERE key = 'schema_version'"
                ).fetchone()[0]
                message_columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(messages)")
                }

        self.assertEqual(legacy_keys, {"private:1"})
        self.assertEqual(persona_keys, {"persona:linyin:private:1"})
        self.assertEqual(schema_version, self.database.SCHEMA_VERSION)
        self.assertNotIn("persona_id", message_columns)

    def test_async_child_task_and_to_thread_inherit_persona_scope(self):
        temp_dir, _, legacy_path, persona_dir = self.scoped_paths()

        async def exercise() -> Path:
            async def child_write() -> None:
                await asyncio.sleep(0)
                self.memory.append_message(
                    "persona:linyin:private:1",
                    "assistant",
                    "child",
                    "private",
                    "1",
                )

            with self.persona_scope.persona_memory_database_scope("linyin"):
                task = asyncio.create_task(child_write())
                threaded_path = await asyncio.to_thread(
                    self.database.current_database_path
                )
            await task
            return threaded_path

        with (
            temp_dir,
            patch.object(self.database, "DATABASE_PATH", legacy_path),
            patch.object(self.persona_scope, "PERSONA_MEMORY_DIR", persona_dir),
        ):
            threaded_path = asyncio.run(exercise())
            linyin_path = persona_dir / "linyin.db"
            self.assertEqual(threaded_path, linyin_path)
            self.assertEqual(self.row_count(linyin_path, "messages"), 1)
            self.assertFalse(legacy_path.exists())

    def test_two_concurrent_persona_tasks_do_not_switch_each_others_database(self):
        temp_dir, _, legacy_path, persona_dir = self.scoped_paths()

        async def write(persona_id: str) -> None:
            with self.persona_scope.persona_memory_database_scope(persona_id):
                await asyncio.sleep(0)
                self.memory.append_message(
                    f"persona:{persona_id}:private:1",
                    "user",
                    persona_id,
                    "private",
                    "1",
                )
                await asyncio.sleep(0)
                self.memory.append_message(
                    f"persona:{persona_id}:private:1",
                    "assistant",
                    f"{persona_id}-reply",
                    "private",
                    "1",
                )

        async def exercise() -> None:
            await asyncio.gather(write("linyin"), write("luna"))

        with (
            temp_dir,
            patch.object(self.database, "DATABASE_PATH", legacy_path),
            patch.object(self.persona_scope, "PERSONA_MEMORY_DIR", persona_dir),
        ):
            asyncio.run(exercise())
            self.assertEqual(self.row_count(persona_dir / "linyin.db", "messages"), 2)
            self.assertEqual(self.row_count(persona_dir / "luna.db", "messages"), 2)
            self.assertFalse(legacy_path.exists())

    def test_summaries_gap_manual_memory_and_vectors_are_isolated(self):
        temp_dir, _, legacy_path, persona_dir = self.scoped_paths()
        with (
            temp_dir,
            patch.object(self.database, "DATABASE_PATH", legacy_path),
            patch.object(self.persona_scope, "PERSONA_MEMORY_DIR", persona_dir),
        ):
            with self.persona_scope.persona_memory_database_scope("linyin"):
                summary_id = self.summaries.add_summary(
                    "persona:linyin:private:1",
                    "private",
                    "1",
                    None,
                    "linyin summary",
                    1,
                    2,
                    2,
                )
                self.gap_summaries.upsert_gap_scene_summary(
                    "persona:linyin:private:1",
                    1,
                    "linyin gap",
                    1,
                    2,
                    2,
                )
                memory_id = self.manual_memory.add_manual_memory(
                    subject_type="user",
                    subject_id="1",
                    content="linyin fact",
                    memory_type="fact_summary",
                    source_session_key="persona:linyin:private:1",
                )
                document_id = self.documents.upsert_rag_document(
                    namespace=self.schema.NAMESPACE_SEMANTIC_MEMORY,
                    source_type=self.schema.SOURCE_MANUAL_FACT,
                    source_id=f"manual:{memory_id}",
                    title="linyin fact",
                    content="linyin fact",
                    visibility=self.schema.VISIBILITY_OWNER_ONLY,
                )
                document = self.documents.get_rag_document(document_id)
                assert document is not None
                self.embeddings.upsert_rag_embedding(
                    document_id=document_id,
                    provider="unit",
                    model="toy",
                    embedding=[0.0, 1.0],
                    content_hash=document.content_hash,
                )

            linyin_path = persona_dir / "linyin.db"
            self.assertGreater(summary_id, 0)
            self.assertEqual(self.row_count(linyin_path, "session_summaries"), 1)
            self.assertEqual(self.row_count(linyin_path, "gap_scene_summaries"), 1)
            self.assertEqual(self.row_count(linyin_path, "long_term_memories"), 1)
            self.assertEqual(self.row_count(linyin_path, "rag_documents"), 1)
            self.assertEqual(self.row_count(linyin_path, "rag_embeddings"), 1)
            self.assertFalse(legacy_path.exists())

    def test_reset_clears_only_persona_recent_messages_and_gap_summary(self):
        temp_dir, _, legacy_path, persona_dir = self.scoped_paths()
        key = "persona:linyin:private:1"
        with (
            temp_dir,
            patch.object(self.database, "DATABASE_PATH", legacy_path),
            patch.object(self.persona_scope, "PERSONA_MEMORY_DIR", persona_dir),
        ):
            with self.persona_scope.persona_memory_database_scope("linyin"):
                self.memory.append_message(key, "user", "hello", "private", "1")
                self.summaries.add_summary(
                    key,
                    "private",
                    "1",
                    None,
                    "keep me",
                    1,
                    1,
                    1,
                )
                self.gap_summaries.upsert_gap_scene_summary(
                    key,
                    1,
                    "clear me",
                    1,
                    1,
                    1,
                )
                self.memory.clear_session(key)

            linyin_path = persona_dir / "linyin.db"
            self.assertEqual(self.row_count(linyin_path, "messages"), 0)
            self.assertEqual(self.row_count(linyin_path, "gap_scene_summaries"), 0)
            self.assertEqual(self.row_count(linyin_path, "session_summaries"), 1)
            self.assertFalse(legacy_path.exists())


if __name__ == "__main__":
    unittest.main()
