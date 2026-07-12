from __future__ import annotations

import ipaddress
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlsplit


EXTERNAL_READ_MAX_QUERY_CHARS = 300
EXTERNAL_READ_MAX_RESULTS = 3
EXTERNAL_READ_MAX_RESPONSE_BYTES = 262_144
EXTERNAL_READ_MAX_TIMEOUT_SECONDS = 15


class ExternalReadPolicyCategory(str, Enum):
    INVALID_QUERY = "invalid_query"
    SENSITIVE_QUERY = "sensitive_query"
    UNSAFE_PROVIDER_ENDPOINT = "unsafe_provider_endpoint"
    UNSAFE_RESOLVED_ADDRESS = "unsafe_resolved_address"
    INVALID_BUDGET = "invalid_budget"
    REQUEST_TIMEOUT = "request_timeout"
    AUTHENTICATION_FAILED = "authentication_failed"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    RESPONSE_TOO_LARGE = "response_too_large"
    INVALID_PROVIDER_RESPONSE = "invalid_provider_response"
    SANITIZATION_FAILED = "sanitization_failed"


class ExternalReadPolicyError(ValueError):
    def __init__(self, category: ExternalReadPolicyCategory, detail: str) -> None:
        super().__init__(detail)
        self.category = category
        self.detail = detail


@dataclass(frozen=True)
class ExternalReadEndpoint:
    base_url: str
    source_host: str


@dataclass(frozen=True)
class ExternalReadBudget:
    max_results: int = EXTERNAL_READ_MAX_RESULTS
    max_response_bytes: int = EXTERNAL_READ_MAX_RESPONSE_BYTES
    timeout_seconds: int = 10
    external_request_count: int = 1
    redirect_count: int = 0
    retry_count: int = 0

    def __post_init__(self) -> None:
        limits = (
            ("max_results", self.max_results, 1, EXTERNAL_READ_MAX_RESULTS),
            (
                "max_response_bytes",
                self.max_response_bytes,
                1,
                EXTERNAL_READ_MAX_RESPONSE_BYTES,
            ),
            (
                "timeout_seconds",
                self.timeout_seconds,
                1,
                EXTERNAL_READ_MAX_TIMEOUT_SECONDS,
            ),
        )
        for name, value, minimum, maximum in limits:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ExternalReadPolicyError(
                    ExternalReadPolicyCategory.INVALID_BUDGET,
                    f"{name} must be an integer",
                )
            if not minimum <= value <= maximum:
                raise ExternalReadPolicyError(
                    ExternalReadPolicyCategory.INVALID_BUDGET,
                    f"{name} must be between {minimum} and {maximum}",
                )

        fixed_counts = (
            ("external_request_count", self.external_request_count, 1),
            ("redirect_count", self.redirect_count, 0),
            ("retry_count", self.retry_count, 0),
        )
        for name, value, expected in fixed_counts:
            if isinstance(value, bool) or not isinstance(value, int) or value != expected:
                raise ExternalReadPolicyError(
                    ExternalReadPolicyCategory.INVALID_BUDGET,
                    f"{name} must equal {expected}",
                )


_SENSITIVE_QUERY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:api[\s_-]?key|access[\s_-]?token|refresh[\s_-]?token|token|password|passwd|secret)\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(r"\bauthorization\s*[:=]\s*(?:bearer|basic)\s+\S+", re.IGNORECASE),
    re.compile(r"\bcookie\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(
        r"(?:手机号|手机|联系电话|电话)\s*[:：=]?\s*(?:\+?86[-\s]?)?1[3-9]\d{9}"
    ),
    re.compile(r"(?:qq(?:号|号码)?|企鹅号)\s*[:：=]?\s*[1-9]\d{4,11}", re.IGNORECASE),
    re.compile(
        r"(?:身份证(?:号|号码)?|公民身份号码)\s*[:：=]?\s*\d{17}[\dXx]"
    ),
)

_LOCAL_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:^|\s)[A-Za-z]:[\\/]+\S*"),
    re.compile(r"(?:^|\s)\\\\[^\s\\/]+[\\/]+\S*"),
    re.compile(
        r"(?:^|\s)/(?:Users|home|etc|var|tmp|root|mnt|opt|srv|proc|sys|dev)(?:/|\s|$)\S*",
        re.IGNORECASE,
    ),
)

_URL_PATTERN = re.compile(r"\b(?:https?|ftp|file)://\S+", re.IGNORECASE)


def _normalize_untrusted_text(value: str) -> str:
    without_controls = "".join(
        " " if unicodedata.category(character).startswith("C") else character
        for character in value
    )
    return " ".join(without_controls.split())


def normalize_external_read_query(query: str) -> str:
    if not isinstance(query, str):
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.INVALID_QUERY,
            "query must be text",
        )
    normalized = _normalize_untrusted_text(query).strip()
    if not normalized:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.INVALID_QUERY,
            "query is empty",
        )
    if len(normalized) > EXTERNAL_READ_MAX_QUERY_CHARS:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.INVALID_QUERY,
            f"query exceeds {EXTERNAL_READ_MAX_QUERY_CHARS} characters",
        )
    if _URL_PATTERN.search(normalized):
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.INVALID_QUERY,
            "query must not contain a URL",
        )
    if any(pattern.search(normalized) for pattern in _LOCAL_PATH_PATTERNS):
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.SENSITIVE_QUERY,
            "query must not contain a local path",
        )
    if any(pattern.search(normalized) for pattern in _SENSITIVE_QUERY_PATTERNS):
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.SENSITIVE_QUERY,
            "query appears to contain a secret or explicitly identified personal data",
        )
    return normalized


def canonicalize_external_host(value: str) -> str:
    host = value.strip().rstrip(".").lower()
    if not host:
        return ""
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider hostname is invalid",
        ) from exc


def validate_external_read_endpoint(
    base_url: str,
    *,
    allowed_hosts: tuple[str, ...],
) -> ExternalReadEndpoint:
    if not isinstance(base_url, str) or not base_url.strip():
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider endpoint is empty",
        )
    if "\\" in base_url or any(
        unicodedata.category(character).startswith("C") for character in base_url
    ):
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider endpoint contains unsafe characters",
        )
    try:
        parsed = urlsplit(base_url.strip())
        port = parsed.port
        username = parsed.username
        password = parsed.password
    except ValueError as exc:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider endpoint is invalid",
        ) from exc

    if parsed.scheme.lower() != "https":
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider endpoint must use https",
        )
    if username is not None or password is not None:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider endpoint must not contain userinfo",
        )
    if parsed.fragment:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider endpoint must not contain a fragment",
        )
    if parsed.query:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider endpoint must not contain a query string",
        )
    if port not in {None, 443}:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider endpoint must use port 443",
        )

    host = canonicalize_external_host(parsed.hostname or "")
    allowed = {
        canonicalize_external_host(item) for item in allowed_hosts if item.strip()
    }
    if not allowed or host not in allowed:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider hostname is not allowlisted",
        )

    try:
        literal_address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal_address = None
    if literal_address is not None:
        validate_external_read_addresses((str(literal_address),))

    return ExternalReadEndpoint(base_url=base_url.strip(), source_host=host)


def validate_external_read_addresses(addresses: tuple[str, ...]) -> tuple[str, ...]:
    if not addresses:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_RESOLVED_ADDRESS,
            "provider hostname resolved to no addresses",
        )

    normalized: list[str] = []
    for value in addresses:
        try:
            address = ipaddress.ip_address(str(value).strip())
        except ValueError as exc:
            raise ExternalReadPolicyError(
                ExternalReadPolicyCategory.UNSAFE_RESOLVED_ADDRESS,
                "provider hostname resolved to an invalid address",
            ) from exc
        if (
            not address.is_global
            or address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            raise ExternalReadPolicyError(
                ExternalReadPolicyCategory.UNSAFE_RESOLVED_ADDRESS,
                "provider hostname resolved to a non-public address",
            )
        canonical = str(address)
        if canonical not in normalized:
            normalized.append(canonical)
    return tuple(normalized)
