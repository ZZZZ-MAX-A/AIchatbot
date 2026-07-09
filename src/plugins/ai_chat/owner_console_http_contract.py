from __future__ import annotations

from dataclasses import dataclass

from .database import utc_now
from .owner_console_http_models import (
    OWNER_CONSOLE_HTTP_ALLOWED_METHODS,
    OWNER_CONSOLE_HTTP_API_PREFIX,
    OWNER_CONSOLE_HTTP_SCHEMA_VERSION,
    OwnerConsoleHttpRouteContractSnapshot,
    OwnerConsoleHttpRouteRow,
)
from .owner_console_read_models import (
    OWNER_CONSOLE_SCHEMA_VERSION,
    OwnerConsoleRuntimeBoundary,
)
from .owner_console_read_runtime import (
    OWNER_CONSOLE_READ_ROUTE_SPECS,
    OwnerConsoleReadRouteSpec,
)


@dataclass(frozen=True)
class OwnerConsoleHttpRouteSpec:
    name: str
    resource: str
    method: str
    path: str
    read_page: str
    runtime_method: str
    read_model: str
    requires_context: bool
    path_params: tuple[str, ...] = ()
    query_params: tuple[str, ...] = ()


@dataclass(frozen=True)
class _OwnerConsoleHttpRouteMapping:
    name: str
    resource: str
    path: str
    read_page: str


_READ_ROUTE_SPECS_BY_PAGE: dict[str, OwnerConsoleReadRouteSpec] = {
    spec.page: spec
    for spec in OWNER_CONSOLE_READ_ROUTE_SPECS
}


_HTTP_ROUTE_MAPPINGS = (
    _OwnerConsoleHttpRouteMapping(
        name="routes",
        resource="routes",
        path=f"{OWNER_CONSOLE_HTTP_API_PREFIX}/routes",
        read_page="route_contract",
    ),
    _OwnerConsoleHttpRouteMapping(
        name="overview",
        resource="overview",
        path=f"{OWNER_CONSOLE_HTTP_API_PREFIX}/overview",
        read_page="dashboard",
    ),
    _OwnerConsoleHttpRouteMapping(
        name="tasks",
        resource="tasks",
        path=f"{OWNER_CONSOLE_HTTP_API_PREFIX}/tasks",
        read_page="tasks",
    ),
    _OwnerConsoleHttpRouteMapping(
        name="tasks.detail",
        resource="tasks",
        path=f"{OWNER_CONSOLE_HTTP_API_PREFIX}/tasks/{{task_id}}",
        read_page="task_detail",
    ),
    _OwnerConsoleHttpRouteMapping(
        name="approvals",
        resource="approvals",
        path=f"{OWNER_CONSOLE_HTTP_API_PREFIX}/approvals",
        read_page="approvals",
    ),
    _OwnerConsoleHttpRouteMapping(
        name="approvals.detail",
        resource="approvals",
        path=f"{OWNER_CONSOLE_HTTP_API_PREFIX}/approvals/{{approval_id}}",
        read_page="approval_detail",
    ),
    _OwnerConsoleHttpRouteMapping(
        name="diagnostics",
        resource="diagnostics",
        path=f"{OWNER_CONSOLE_HTTP_API_PREFIX}/diagnostics",
        read_page="diagnostics",
    ),
    _OwnerConsoleHttpRouteMapping(
        name="memory",
        resource="memory",
        path=f"{OWNER_CONSOLE_HTTP_API_PREFIX}/memory",
        read_page="memory",
    ),
    _OwnerConsoleHttpRouteMapping(
        name="access-control",
        resource="access-control",
        path=f"{OWNER_CONSOLE_HTTP_API_PREFIX}/access-control",
        read_page="access_control",
    ),
    _OwnerConsoleHttpRouteMapping(
        name="settings",
        resource="settings",
        path=f"{OWNER_CONSOLE_HTTP_API_PREFIX}/settings",
        read_page="settings",
    ),
)


def _spec_for_mapping(
    mapping: _OwnerConsoleHttpRouteMapping,
) -> OwnerConsoleHttpRouteSpec:
    if mapping.read_page == "route_contract":
        return OwnerConsoleHttpRouteSpec(
            name=mapping.name,
            resource=mapping.resource,
            method="GET",
            path=mapping.path,
            read_page=mapping.read_page,
            runtime_method="build_route_contract_snapshot",
            read_model="OwnerConsoleReadRouteContractSnapshot",
            requires_context=False,
        )
    read_spec = _READ_ROUTE_SPECS_BY_PAGE[mapping.read_page]
    return OwnerConsoleHttpRouteSpec(
        name=mapping.name,
        resource=mapping.resource,
        method="GET",
        path=mapping.path,
        read_page=read_spec.page,
        runtime_method=read_spec.runtime_method,
        read_model=read_spec.read_model,
        requires_context=read_spec.requires_context,
        path_params=read_spec.required_params,
        query_params=read_spec.optional_params,
    )


OWNER_CONSOLE_HTTP_ROUTE_SPECS = tuple(
    _spec_for_mapping(mapping)
    for mapping in _HTTP_ROUTE_MAPPINGS
)


def _validate_http_route_specs(
    specs: tuple[OwnerConsoleHttpRouteSpec, ...],
) -> None:
    names: set[str] = set()
    paths: set[tuple[str, str]] = set()
    for spec in specs:
        if spec.name in names:
            raise ValueError(f"duplicate owner console HTTP route name: {spec.name}")
        names.add(spec.name)
        method_path = (spec.method, spec.path)
        if method_path in paths:
            raise ValueError(f"duplicate owner console HTTP route path: {spec.path}")
        paths.add(method_path)
        if spec.method not in OWNER_CONSOLE_HTTP_ALLOWED_METHODS:
            raise ValueError(
                f"unsupported owner console HTTP method: {spec.method}"
            )
        if not spec.path.startswith(f"{OWNER_CONSOLE_HTTP_API_PREFIX}/"):
            raise ValueError(
                f"owner console HTTP path must use API prefix: {spec.path}"
            )
        if spec.path != spec.path.lower():
            raise ValueError(
                f"owner console HTTP path must be lowercase: {spec.path}"
            )
        static_segments = [
            segment
            for segment in spec.path.split("/")
            if segment and not segment.startswith("{")
        ]
        if any("_" in segment for segment in static_segments):
            raise ValueError(
                f"owner console HTTP path must use kebab-case: {spec.path}"
            )


def build_owner_console_http_route_contract_snapshot(
    *,
    enabled_route_names: frozenset[str] | None = None,
) -> OwnerConsoleHttpRouteContractSnapshot:
    _validate_http_route_specs(OWNER_CONSOLE_HTTP_ROUTE_SPECS)
    enabled_routes = enabled_route_names or frozenset()
    rows = [
        OwnerConsoleHttpRouteRow(
            name=spec.name,
            resource=spec.resource,
            method=spec.method,
            path=spec.path,
            read_page=spec.read_page,
            runtime_method=spec.runtime_method,
            read_model=spec.read_model,
            requires_context=spec.requires_context,
            path_params=list(spec.path_params),
            query_params=list(spec.query_params),
            read_only=True,
            http_api_enabled=spec.name in enabled_routes,
            web_write_enabled=False,
            direct_qq_dependency_allowed=False,
            write_side_effect_allowed=False,
        )
        for spec in OWNER_CONSOLE_HTTP_ROUTE_SPECS
    ]
    return OwnerConsoleHttpRouteContractSnapshot(
        generated_at=utc_now(),
        schema_version=OWNER_CONSOLE_HTTP_SCHEMA_VERSION,
        read_model_schema_version=OWNER_CONSOLE_SCHEMA_VERSION,
        api_prefix=OWNER_CONSOLE_HTTP_API_PREFIX,
        allowed_methods=list(OWNER_CONSOLE_HTTP_ALLOWED_METHODS),
        route_count=len(rows),
        rows=rows,
        context_strategy="owner_private_session_from_config",
        context_override_allowed=False,
        write_routes_enabled=False,
        boundary=OwnerConsoleRuntimeBoundary(),
    )
