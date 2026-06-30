from __future__ import annotations

import hashlib
from typing import Any

from ..database import connect, ensure_database, utc_now
from .schema import RagDocument


def stable_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _text_or_empty(value: object) -> str:
    return "" if value is None else str(value)


def document_from_row(row: Any) -> RagDocument:
    return RagDocument(
        id=int(row["id"]),
        namespace=str(row["namespace"]),
        source_type=str(row["source_type"]),
        source_id=str(row["source_id"]),
        source_version=_text_or_empty(row["source_version"]),
        subject_type=_text_or_empty(row["subject_type"]),
        subject_id=_text_or_empty(row["subject_id"]),
        session_key=_text_or_empty(row["session_key"]),
        message_type=_text_or_empty(row["message_type"]),
        user_id=_text_or_empty(row["user_id"]),
        group_id=_text_or_empty(row["group_id"]),
        visibility=str(row["visibility"]),
        title=str(row["title"]),
        content=str(row["content"]),
        content_hash=str(row["content_hash"]),
        chunk_index=int(row["chunk_index"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        deleted_at=_text_or_empty(row["deleted_at"]),
    )


def upsert_rag_document(
    *,
    namespace: str,
    source_type: str,
    source_id: str,
    title: str,
    content: str,
    visibility: str,
    chunk_index: int = 0,
    source_version: str = "",
    subject_type: str = "",
    subject_id: str = "",
    session_key: str = "",
    message_type: str = "",
    user_id: str = "",
    group_id: str = "",
) -> int:
    ensure_database()
    now = utc_now()
    content_hash = stable_content_hash(content)
    with connect() as connection:
        existing = connection.execute(
            """
            SELECT id
            FROM rag_documents
            WHERE namespace = ?
              AND source_type = ?
              AND source_id = ?
              AND chunk_index = ?
            """,
            (namespace, source_type, source_id, chunk_index),
        ).fetchone()
        if existing is None:
            cursor = connection.execute(
                """
                INSERT INTO rag_documents (
                    namespace,
                    source_type,
                    source_id,
                    source_version,
                    subject_type,
                    subject_id,
                    session_key,
                    message_type,
                    user_id,
                    group_id,
                    visibility,
                    title,
                    content,
                    content_hash,
                    chunk_index,
                    created_at,
                    updated_at,
                    deleted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    namespace,
                    source_type,
                    source_id,
                    source_version,
                    subject_type,
                    subject_id,
                    session_key,
                    message_type,
                    user_id,
                    group_id,
                    visibility,
                    title,
                    content,
                    content_hash,
                    chunk_index,
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

        document_id = int(existing["id"])
        connection.execute(
            """
            UPDATE rag_documents
            SET
                source_version = ?,
                subject_type = ?,
                subject_id = ?,
                session_key = ?,
                message_type = ?,
                user_id = ?,
                group_id = ?,
                visibility = ?,
                title = ?,
                content = ?,
                content_hash = ?,
                updated_at = ?,
                deleted_at = NULL
            WHERE id = ?
            """,
            (
                source_version,
                subject_type,
                subject_id,
                session_key,
                message_type,
                user_id,
                group_id,
                visibility,
                title,
                content,
                content_hash,
                now,
                document_id,
            ),
        )
        return document_id


def get_rag_document(document_id: int, *, include_deleted: bool = False) -> RagDocument | None:
    ensure_database()
    where_deleted = "" if include_deleted else "AND deleted_at IS NULL"
    with connect() as connection:
        row = connection.execute(
            f"""
            SELECT *
            FROM rag_documents
            WHERE id = ?
            {where_deleted}
            """,
            (document_id,),
        ).fetchone()
    return None if row is None else document_from_row(row)


def list_rag_documents(
    *,
    namespace: str | None = None,
    source_type: str | None = None,
    include_deleted: bool = False,
    limit: int = 100,
) -> list[RagDocument]:
    ensure_database()
    clauses: list[str] = []
    params: list[object] = []
    if namespace:
        clauses.append("namespace = ?")
        params.append(namespace)
    if source_type:
        clauses.append("source_type = ?")
        params.append(source_type)
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    with connect() as connection:
        rows = connection.execute(
            f"""
            SELECT *
            FROM rag_documents
            {where_clause}
            ORDER BY id DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
    return [document_from_row(row) for row in rows]


def soft_delete_rag_documents(
    *,
    namespace: str | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
    session_key: str | None = None,
) -> int:
    ensure_database()
    clauses = ["deleted_at IS NULL"]
    params: list[object] = []
    if namespace:
        clauses.append("namespace = ?")
        params.append(namespace)
    if source_type:
        clauses.append("source_type = ?")
        params.append(source_type)
    if source_id:
        clauses.append("source_id = ?")
        params.append(source_id)
    if session_key:
        clauses.append("session_key = ?")
        params.append(session_key)
    if len(clauses) == 1:
        raise ValueError("Refusing to soft delete all RAG documents without a filter.")

    now = utc_now()
    with connect() as connection:
        cursor = connection.execute(
            f"""
            UPDATE rag_documents
            SET deleted_at = ?, updated_at = ?
            WHERE {' AND '.join(clauses)}
            """,
            (now, now, *params),
        )
        return int(cursor.rowcount)


def rag_document_stats() -> dict[str, int]:
    ensure_database()
    with connect() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS document_count,
                SUM(CASE WHEN deleted_at IS NULL THEN 1 ELSE 0 END) AS active_document_count
            FROM rag_documents
            """
        ).fetchone()
        embedding_row = connection.execute(
            "SELECT COUNT(*) AS embedding_count FROM rag_embeddings"
        ).fetchone()
    return {
        "document_count": int(row["document_count"] or 0),
        "active_document_count": int(row["active_document_count"] or 0),
        "embedding_count": int(embedding_row["embedding_count"] or 0),
    }
