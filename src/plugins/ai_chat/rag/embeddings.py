from __future__ import annotations

import json
from collections.abc import Iterable

from ..database import connect, ensure_database, utc_now


def serialize_embedding(values: Iterable[float]) -> str:
    return json.dumps([float(value) for value in values], separators=(",", ":"))


def deserialize_embedding(value: str) -> list[float]:
    payload = json.loads(value)
    if not isinstance(payload, list):
        raise ValueError("Embedding payload must be a list.")
    return [float(item) for item in payload]


def upsert_rag_embedding(
    *,
    document_id: int,
    provider: str,
    model: str,
    embedding: Iterable[float],
    content_hash: str,
) -> int:
    ensure_database()
    vector = [float(value) for value in embedding]
    if not vector:
        raise ValueError("Embedding vector must not be empty.")
    now = utc_now()
    serialized = serialize_embedding(vector)
    with connect() as connection:
        existing = connection.execute(
            """
            SELECT id
            FROM rag_embeddings
            WHERE document_id = ?
              AND embedding_provider = ?
              AND embedding_model = ?
            """,
            (document_id, provider, model),
        ).fetchone()
        if existing is None:
            cursor = connection.execute(
                """
                INSERT INTO rag_embeddings (
                    document_id,
                    embedding_provider,
                    embedding_model,
                    embedding_dimension,
                    embedding,
                    content_hash,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (document_id, provider, model, len(vector), serialized, content_hash, now),
            )
            return int(cursor.lastrowid)

        embedding_id = int(existing["id"])
        connection.execute(
            """
            UPDATE rag_embeddings
            SET
                embedding_dimension = ?,
                embedding = ?,
                content_hash = ?,
                created_at = ?
            WHERE id = ?
            """,
            (len(vector), serialized, content_hash, now, embedding_id),
        )
        return embedding_id
