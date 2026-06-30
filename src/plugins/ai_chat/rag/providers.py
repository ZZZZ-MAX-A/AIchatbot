from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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
