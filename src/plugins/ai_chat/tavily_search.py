from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Mapping, Protocol

from .external_read_security import (
    EXTERNAL_READ_MAX_RESPONSE_BYTES,
    ExternalReadPolicyCategory,
    ExternalReadPolicyError,
    validate_external_read_endpoint,
)
from .external_search import (
    ExternalSearchProviderResponse,
    ExternalSearchResult,
)


TAVILY_PROVIDER_NAME = "tavily"
TAVILY_SEARCH_ENDPOINT = "https://api.tavily.com/search"
TAVILY_ALLOWED_HOSTS = ("api.tavily.com",)
TAVILY_USER_AGENT = "AIchatbot-Tavily-Search/1.0"
TAVILY_MAX_CONTENT_CHARS = 360

_TAVILY_MARKDOWN_HEADING_PATTERN = re.compile(
    r"(^|\s)#{1,6}\s+",
    re.MULTILINE,
)
_TAVILY_MARKDOWN_LIST_PATTERN = re.compile(
    r"(^|\s)[*+-]\s+",
    re.MULTILINE,
)
_TAVILY_MARKDOWN_DECORATION_PATTERN = re.compile(r"(?:\*\*|__|~~)")


@dataclass(frozen=True)
class TavilyHttpResponse:
    status_code: int
    content_type: str
    body: bytes


class TavilySearchTransport(Protocol):
    async def post_json(
        self,
        endpoint: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, object],
        timeout_seconds: int,
        max_response_bytes: int,
    ) -> TavilyHttpResponse: ...


def _validated_api_key(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Tavily API key must be text")
    key = value.strip()
    if not key or len(key) > 512:
        raise ValueError("Tavily API key is missing or invalid")
    if any(unicodedata.category(character).startswith("C") for character in key):
        raise ValueError("Tavily API key contains unsafe characters")
    if re.search(r"\s", key):
        raise ValueError("Tavily API key contains whitespace")
    return key


def _invalid_response(detail: str) -> ExternalReadPolicyError:
    return ExternalReadPolicyError(
        ExternalReadPolicyCategory.INVALID_PROVIDER_RESPONSE,
        detail,
    )


def _provider_unavailable() -> ExternalReadPolicyError:
    return ExternalReadPolicyError(
        ExternalReadPolicyCategory.PROVIDER_UNAVAILABLE,
        "Tavily search request failed",
    )


def _authentication_failed() -> ExternalReadPolicyError:
    return ExternalReadPolicyError(
        ExternalReadPolicyCategory.AUTHENTICATION_FAILED,
        "Tavily authentication failed",
    )


def _rate_limited() -> ExternalReadPolicyError:
    return ExternalReadPolicyError(
        ExternalReadPolicyCategory.RATE_LIMITED,
        "Tavily request was rate limited",
    )


def normalize_tavily_content(value: object) -> object:
    if not isinstance(value, str):
        return value
    normalized = _TAVILY_MARKDOWN_HEADING_PATTERN.sub(r"\1", value)
    normalized = _TAVILY_MARKDOWN_LIST_PATTERN.sub(r"\1", normalized)
    normalized = _TAVILY_MARKDOWN_DECORATION_PATTERN.sub("", normalized)
    normalized = normalized.replace("`", "").replace("¶", " ")
    normalized = normalized.replace("|", " · ")
    normalized = " ".join(normalized.split())
    if len(normalized) > TAVILY_MAX_CONTENT_CHARS:
        normalized = (
            normalized[: TAVILY_MAX_CONTENT_CHARS - 3].rstrip()
            + "..."
        )
    return normalized


class TavilyBasicSearchProvider:
    name = TAVILY_PROVIDER_NAME

    def __init__(
        self,
        *,
        api_key: str,
        transport: TavilySearchTransport,
        endpoint: str = TAVILY_SEARCH_ENDPOINT,
        timeout_seconds: int = 10,
        max_response_bytes: int = EXTERNAL_READ_MAX_RESPONSE_BYTES,
    ) -> None:
        validated_endpoint = validate_external_read_endpoint(
            endpoint,
            allowed_hosts=TAVILY_ALLOWED_HOSTS,
        )
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int):
            raise ValueError("Tavily timeout must be an integer")
        if not 1 <= timeout_seconds <= 15:
            raise ValueError("Tavily timeout must be between 1 and 15 seconds")
        if isinstance(max_response_bytes, bool) or not isinstance(
            max_response_bytes,
            int,
        ):
            raise ValueError("Tavily response budget must be an integer")
        if not 1 <= max_response_bytes <= EXTERNAL_READ_MAX_RESPONSE_BYTES:
            raise ValueError("Tavily response budget exceeds the external-read limit")
        self._api_key = _validated_api_key(api_key)
        self._transport = transport
        self._endpoint = validated_endpoint.base_url
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes

    async def search(
        self,
        query: str,
        *,
        max_results: int,
    ) -> ExternalSearchProviderResponse:
        if isinstance(max_results, bool) or not isinstance(max_results, int):
            raise ExternalReadPolicyError(
                ExternalReadPolicyCategory.INVALID_BUDGET,
                "Tavily max_results must be an integer",
            )
        if not 1 <= max_results <= 3:
            raise ExternalReadPolicyError(
                ExternalReadPolicyCategory.INVALID_BUDGET,
                "Tavily max_results must be between 1 and 3",
            )

        response = await self._transport.post_json(
            self._endpoint,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": TAVILY_USER_AGENT,
                "Authorization": f"Bearer {self._api_key}",
            },
            json_body={
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
                "auto_parameters": False,
            },
            timeout_seconds=self._timeout_seconds,
            max_response_bytes=self._max_response_bytes,
        )
        if not isinstance(response, TavilyHttpResponse):
            raise _invalid_response("Tavily transport returned an invalid response")
        if (
            isinstance(response.status_code, bool)
            or not isinstance(response.status_code, int)
            or not 100 <= response.status_code <= 599
        ):
            raise _invalid_response("Tavily response status is invalid")
        if response.status_code in {401, 403}:
            raise _authentication_failed()
        if response.status_code == 429:
            raise _rate_limited()
        if response.status_code != 200:
            raise _provider_unavailable()
        if not isinstance(response.content_type, str) or (
            response.content_type.split(";", 1)[0].strip().lower()
            != "application/json"
        ):
            raise _invalid_response("Tavily response content type is unsupported")
        if not isinstance(response.body, bytes):
            raise _invalid_response("Tavily response body must be bytes")
        if len(response.body) > self._max_response_bytes:
            raise ExternalReadPolicyError(
                ExternalReadPolicyCategory.RESPONSE_TOO_LARGE,
                "Tavily response exceeded the byte budget",
            )

        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _invalid_response("Tavily response is not valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise _invalid_response("Tavily response root must be an object")
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise _invalid_response("Tavily response results must be a list")

        results: list[ExternalSearchResult] = []
        for item in raw_results:
            if not isinstance(item, dict):
                results.append(ExternalSearchResult("", "", ""))
                continue
            published_at = item.get("published_date", "")
            if not published_at:
                published_at = item.get("publishedDate", "")
            results.append(
                ExternalSearchResult(
                    title=item.get("title", ""),
                    snippet=normalize_tavily_content(item.get("content", "")),
                    source_url=item.get("url", ""),
                    published_at=published_at,
                )
            )

        return ExternalSearchProviderResponse(
            results=tuple(results),
            response_bytes=len(response.body),
        )
