from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .database import utc_now
from .owner_console_read_models import (
    OWNER_CONSOLE_SCHEMA_VERSION,
    OwnerConsoleRuntimeBoundary,
    owner_console_to_jsonable,
)


OWNER_CONSOLE_HTTP_SCHEMA_VERSION = "owner_console.http.v1"
OWNER_CONSOLE_HTTP_API_PREFIX = "/api/v1/owner-console"
OWNER_CONSOLE_HTTP_ALLOWED_METHODS = ("GET",)
OWNER_CONSOLE_HTTP_ERROR_CODES = (
    "bad_request",
    "forbidden",
    "not_found",
    "provider_unavailable",
    "internal_error",
)


@dataclass(frozen=True)
class OwnerConsoleHttpError:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OwnerConsoleHttpRouteRow:
    name: str
    resource: str
    method: str
    path: str
    read_page: str
    runtime_method: str
    read_model: str
    requires_context: bool
    path_params: list[str]
    query_params: list[str]
    read_only: bool = True
    http_api_enabled: bool = False
    web_write_enabled: bool = False
    direct_qq_dependency_allowed: bool = False
    write_side_effect_allowed: bool = False


@dataclass(frozen=True)
class OwnerConsoleHttpRouteContractSnapshot:
    generated_at: str
    schema_version: str
    read_model_schema_version: str
    api_prefix: str
    allowed_methods: list[str]
    route_count: int
    rows: list[OwnerConsoleHttpRouteRow]
    context_strategy: str
    context_override_allowed: bool
    write_routes_enabled: bool
    boundary: OwnerConsoleRuntimeBoundary


def _normalized_resource(resource: str) -> str:
    normalized = resource.strip()
    if not normalized:
        raise ValueError("owner console HTTP resource must be non-empty")
    return normalized


def _generated_at_from_data(serialized_data: Any) -> str:
    if isinstance(serialized_data, dict):
        return str(serialized_data.get("generated_at") or "")
    return ""


def owner_console_http_success_response(
    resource: str,
    data: Any,
    *,
    http_api_enabled: bool = False,
) -> dict[str, Any]:
    serialized_data = owner_console_to_jsonable(data)
    return {
        "schema_version": OWNER_CONSOLE_HTTP_SCHEMA_VERSION,
        "read_model_schema_version": OWNER_CONSOLE_SCHEMA_VERSION,
        "transport": "http",
        "api_prefix": OWNER_CONSOLE_HTTP_API_PREFIX,
        "resource": _normalized_resource(resource),
        "generated_at": _generated_at_from_data(serialized_data),
        "read_only": True,
        "http_api_enabled": http_api_enabled,
        "web_write_enabled": False,
        "data": serialized_data,
        "error": None,
    }


def owner_console_http_error_response(
    resource: str,
    *,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    http_api_enabled: bool = False,
) -> dict[str, Any]:
    normalized_code = code.strip()
    if normalized_code not in OWNER_CONSOLE_HTTP_ERROR_CODES:
        raise ValueError(f"unsupported owner console HTTP error code: {code}")
    error = OwnerConsoleHttpError(
        code=normalized_code,
        message=message.strip(),
        details=details or {},
    )
    return {
        "schema_version": OWNER_CONSOLE_HTTP_SCHEMA_VERSION,
        "read_model_schema_version": OWNER_CONSOLE_SCHEMA_VERSION,
        "transport": "http",
        "api_prefix": OWNER_CONSOLE_HTTP_API_PREFIX,
        "resource": _normalized_resource(resource),
        "generated_at": utc_now(),
        "read_only": True,
        "http_api_enabled": http_api_enabled,
        "web_write_enabled": False,
        "data": None,
        "error": owner_console_to_jsonable(error),
    }
