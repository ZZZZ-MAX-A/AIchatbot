import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATABASE_PATH = PROJECT_ROOT / "data" / "chatbot.db"
SCHEMA_VERSION = "6"


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def ensure_database() -> None:
    with connect() as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_key TEXT NOT NULL,
                message_type TEXT NOT NULL,
                user_id TEXT NOT NULL,
                group_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_session_id
            ON messages (session_key, id)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS long_term_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                content TEXT NOT NULL,
                source_session_key TEXT,
                confidence REAL NOT NULL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_long_term_memories_subject
            ON long_term_memories (subject_type, subject_id, memory_type)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_embeddings (
                memory_id INTEGER PRIMARY KEY,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(memory_id) REFERENCES long_term_memories(id)
                    ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS session_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_key TEXT NOT NULL,
                message_type TEXT NOT NULL,
                user_id TEXT,
                group_id TEXT,
                summary TEXT NOT NULL,
                message_start_id INTEGER NOT NULL,
                message_end_id INTEGER NOT NULL,
                source_message_count INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_session_summaries_session_id
            ON session_summaries (session_key, id)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS gap_scene_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_key TEXT NOT NULL,
                slot INTEGER NOT NULL,
                summary TEXT NOT NULL,
                message_start_id INTEGER NOT NULL,
                message_end_id INTEGER NOT NULL,
                source_message_count INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(session_key, slot)
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_gap_scene_summaries_session_slot
            ON gap_scene_summaries (session_key, slot)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                namespace TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_version TEXT,
                subject_type TEXT,
                subject_id TEXT,
                session_key TEXT,
                message_type TEXT,
                user_id TEXT,
                group_id TEXT,
                visibility TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                chunk_index INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_rag_documents_unique_source_chunk
            ON rag_documents (namespace, source_type, source_id, chunk_index)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_rag_documents_namespace
            ON rag_documents (namespace, deleted_at)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_rag_documents_source
            ON rag_documents (source_type, source_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_rag_documents_scope
            ON rag_documents (subject_type, subject_id, session_key, visibility)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                embedding_provider TEXT NOT NULL,
                embedding_model TEXT NOT NULL,
                embedding_dimension INTEGER NOT NULL,
                embedding TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(document_id) REFERENCES rag_documents(id)
                    ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_rag_embeddings_document_model
            ON rag_embeddings (document_id, embedding_provider, embedding_model)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS private_trials (
                user_id TEXT PRIMARY KEY,
                used_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_key TEXT NOT NULL,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                goal TEXT NOT NULL,
                status TEXT NOT NULL,
                result TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_agent_tasks_session_status
            ON agent_tasks (session_key, status, id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_agent_tasks_user_status
            ON agent_tasks (user_id, status, id)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_task_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                step_index INTEGER NOT NULL,
                kind TEXT NOT NULL,
                tool_name TEXT,
                input_json TEXT,
                output_summary TEXT,
                status TEXT NOT NULL,
                error TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES agent_tasks(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_agent_task_events_task_step
            ON agent_task_events (task_id, step_index, id)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                tool_name TEXT NOT NULL,
                tool_input_json TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                decided_at TEXT,
                FOREIGN KEY(task_id) REFERENCES agent_tasks(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_agent_approvals_task_status
            ON agent_approvals (task_id, status, id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_agent_approvals_status_id
            ON agent_approvals (status, id)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO schema_meta (key, value)
            VALUES ('schema_version', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (SCHEMA_VERSION,),
        )
