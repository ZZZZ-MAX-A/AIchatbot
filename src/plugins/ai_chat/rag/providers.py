from __future__ import annotations

import json
from dataclasses import dataclass
import time
from types import SimpleNamespace
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


EMBEDDING_HEALTH_CHECK_TEXT = "AIchatbot embedding health check"
EMBEDDING_HEALTH_CHECK_TIMEOUT_SECONDS = 20


class EmbeddingProviderError(RuntimeError):
    """Raised when an embedding provider cannot return a usable vector."""


class EmbeddingProvider(Protocol):
    provider: str
    model: str

    def embed(self, text: str) -> list[float]:
        ...


@dataclass(frozen=True)
class EmbeddingProviderConfig:
    provider: str
    model: str
    base_url: str
    timeout_seconds: int = 60
    expected_dimension: int = 0


@dataclass(frozen=True)
class EmbeddingProviderCheck:
    ok: bool
    detail: str
    dimension: int = 0
    elapsed_seconds: float = 0.0


def _as_float_vector(value: Any) -> list[float]:
    if not isinstance(value, list) or not value:
        raise EmbeddingProviderError("Embedding response did not contain a non-empty vector.")
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise EmbeddingProviderError("Embedding response contained non-numeric values.") from exc


def parse_ollama_embedding_response(payload: dict[str, Any]) -> list[float]:
    if isinstance(payload.get("embedding"), list):
        return _as_float_vector(payload["embedding"])

    embeddings = payload.get("embeddings")
    if isinstance(embeddings, list) and embeddings:
        first = embeddings[0]
        if isinstance(first, list):
            return _as_float_vector(first)

    raise EmbeddingProviderError("Ollama embedding response did not contain embedding data.")


class OllamaEmbeddingProvider:
    provider = "ollama"

    def __init__(
        self,
        *,
        model: str,
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: int = 60,
        expected_dimension: int = 0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.expected_dimension = expected_dimension

    def embed(self, text: str) -> list[float]:
        if not text.strip():
            raise EmbeddingProviderError("Cannot embed empty text.")

        try:
            vector = self._embed_new_api(text)
        except EmbeddingProviderError:
            vector = self._embed_legacy_api(text)

        if self.expected_dimension > 0 and len(vector) != self.expected_dimension:
            raise EmbeddingProviderError(
                f"Embedding dimension {len(vector)} does not match expected "
                f"{self.expected_dimension}."
            )
        return vector

    def embed_once(self, text: str) -> list[float]:
        """Use the current Ollama embedding API exactly once without fallback."""

        if not text.strip():
            raise EmbeddingProviderError("Cannot embed empty text.")
        vector = self._embed_new_api(text)
        if self.expected_dimension > 0 and len(vector) != self.expected_dimension:
            raise EmbeddingProviderError(
                f"Embedding dimension {len(vector)} does not match expected "
                f"{self.expected_dimension}."
            )
        return vector

    def _post_json(self, path: str, payload: dict[str, object]) -> dict[str, Any]:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raise EmbeddingProviderError(f"Ollama returned HTTP {exc.code}.") from exc
        except URLError as exc:
            raise EmbeddingProviderError(f"Cannot connect to Ollama: {exc.reason}") from exc
        except TimeoutError as exc:
            raise EmbeddingProviderError("Ollama embedding request timed out.") from exc

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise EmbeddingProviderError("Ollama returned invalid JSON.") from exc
        if not isinstance(decoded, dict):
            raise EmbeddingProviderError("Ollama returned a non-object JSON payload.")
        return decoded

    def _embed_new_api(self, text: str) -> list[float]:
        payload = self._post_json("/api/embed", {"model": self.model, "input": text})
        return parse_ollama_embedding_response(payload)

    def _embed_legacy_api(self, text: str) -> list[float]:
        payload = self._post_json("/api/embeddings", {"model": self.model, "prompt": text})
        return parse_ollama_embedding_response(payload)


def build_embedding_provider(config: Any) -> EmbeddingProvider:
    provider = str(config.memory_rag_embedding_provider).strip().lower()
    if provider == "ollama":
        return OllamaEmbeddingProvider(
            model=str(config.memory_rag_embedding_model),
            base_url=str(config.memory_rag_embedding_base_url),
            timeout_seconds=int(config.memory_rag_embedding_timeout_seconds),
            expected_dimension=int(config.memory_rag_embedding_dimension),
        )
    raise ValueError(f"Unsupported embedding provider: {provider}")


def check_embedding_provider(
    config: Any,
    *,
    enabled: bool = True,
) -> EmbeddingProviderCheck:
    if not enabled:
        return EmbeddingProviderCheck(False, "RAG 未开启，未执行")

    timeout_seconds = min(
        max(int(getattr(config, "memory_rag_embedding_timeout_seconds", 1) or 1), 1),
        EMBEDDING_HEALTH_CHECK_TIMEOUT_SECONDS,
    )
    check_config = SimpleNamespace(
        memory_rag_embedding_provider=getattr(config, "memory_rag_embedding_provider", ""),
        memory_rag_embedding_model=getattr(config, "memory_rag_embedding_model", ""),
        memory_rag_embedding_base_url=getattr(config, "memory_rag_embedding_base_url", ""),
        memory_rag_embedding_timeout_seconds=timeout_seconds,
        memory_rag_embedding_dimension=getattr(config, "memory_rag_embedding_dimension", 0),
    )

    started = time.monotonic()
    try:
        embedder = build_embedding_provider(check_config)
        vector = embedder.embed(EMBEDDING_HEALTH_CHECK_TEXT)
    except Exception as exc:
        elapsed = time.monotonic() - started
        message = str(exc).strip() or type(exc).__name__
        return EmbeddingProviderCheck(False, f"失败：{message}，用时 {elapsed:.1f} 秒", elapsed_seconds=elapsed)

    elapsed = time.monotonic() - started
    return EmbeddingProviderCheck(
        True,
        f"正常，用时 {elapsed:.1f} 秒，维度 {len(vector)}",
        dimension=len(vector),
        elapsed_seconds=elapsed,
    )
