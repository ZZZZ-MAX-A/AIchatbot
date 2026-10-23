from __future__ import annotations

import math
from collections.abc import Callable

from ..database import connect, ensure_database
from .documents import document_from_row
from .embeddings import deserialize_embedding
from .schema import RagDocument, RagSearchResult


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return dot / (left_norm * right_norm)


def search_rag_documents(
    *,
    query_embedding: list[float],
    namespace: str,
    provider: str,
    model: str,
    source_types: set[str] | None = None,
    min_score: float = 0.0,
    top_k: int = 5,
    document_filter: Callable[[RagDocument], bool] | None = None,
    candidates: list[tuple[RagDocument, list[float]]] | None = None,
) -> list[RagSearchResult]:
    if top_k <= 0:
        return []
    if candidates is None:
        ensure_database()
        with connect() as connection:
            candidates = read_rag_candidates(connection, namespace=namespace, provider=provider, model=model,
                                             source_types=source_types, document_filter=document_filter)
    results: list[RagSearchResult] = []
    for document, embedding in candidates:
        if document.namespace != namespace or document.deleted_at or (source_types and document.source_type not in source_types):
            continue
        # Audience checks precede top_k for both live reads and fixed snapshots.
        if document_filter is not None and not document_filter(document):
            continue
        score = cosine_similarity(query_embedding, embedding)
        if not math.isfinite(score) or score < min_score:
            continue
        results.append(RagSearchResult(document, score))
    results.sort(key=lambda item: item.score, reverse=True)
    return results[:top_k]


def read_rag_candidates(connection, *, namespace, provider, model, source_types=None, document_filter=None):
    params: list[object] = [provider, model, namespace]
    source_clause = ""
    if source_types:
        placeholders = ", ".join("?" for _ in source_types)
        source_clause = f"AND d.source_type IN ({placeholders})"
        params.extend(sorted(source_types))

    rows = connection.execute(
        f"""
        SELECT
            d.*,
            e.embedding AS embedding
        FROM rag_documents d
        JOIN rag_embeddings e ON e.document_id = d.id
        WHERE e.embedding_provider = ?
          AND e.embedding_model = ?
          AND e.content_hash = d.content_hash
          AND d.namespace = ?
          AND d.deleted_at IS NULL
          {source_clause}
        """,
        tuple(params),
    ).fetchall()

    candidates = []
    for row in rows:
        document = document_from_row(row)
        if document_filter is not None and not document_filter(document):
            continue
        candidates.append((document, deserialize_embedding(str(row["embedding"]))))
    return candidates
