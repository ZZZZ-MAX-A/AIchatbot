from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .config import load_config
from .owner_console_http_adapter import (
    OwnerConsoleHttpAdapterError,
    build_owner_console_context_from_config,
    create_owner_console_http_read_runtime,
    parse_owner_console_positive_int,
)
from .owner_console_http_contract import (
    build_owner_console_http_route_contract_snapshot,
)
from .owner_console_http_models import (
    OWNER_CONSOLE_HTTP_API_PREFIX,
    OWNER_CONSOLE_HTTP_SCHEMA_VERSION,
    owner_console_http_error_response,
    owner_console_http_success_response,
)


OWNER_CONSOLE_FASTAPI_APP_TITLE = "AIchatbot Owner Console API"
OWNER_CONSOLE_FASTAPI_ENABLED_ROUTE_NAMES = frozenset({"routes", "overview"})
OWNER_CONSOLE_FASTAPI_ENABLED_ROUTES = (
    "/healthz",
    f"{OWNER_CONSOLE_HTTP_API_PREFIX}/routes",
    f"{OWNER_CONSOLE_HTTP_API_PREFIX}/overview",
)


def create_owner_console_fastapi_app() -> FastAPI:
    app = FastAPI(
        title=OWNER_CONSOLE_FASTAPI_APP_TITLE,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {
            "ok": True,
            "service": "owner-console",
            "schema_version": OWNER_CONSOLE_HTTP_SCHEMA_VERSION,
            "api_prefix": OWNER_CONSOLE_HTTP_API_PREFIX,
            "read_only": True,
            "http_api_enabled": True,
            "web_write_enabled": False,
            "enabled_routes": list(OWNER_CONSOLE_FASTAPI_ENABLED_ROUTES),
        }

    @app.get(f"{OWNER_CONSOLE_HTTP_API_PREFIX}/routes", response_model=None)
    async def owner_console_routes() -> Any:
        try:
            snapshot = build_owner_console_http_route_contract_snapshot(
                enabled_route_names=OWNER_CONSOLE_FASTAPI_ENABLED_ROUTE_NAMES,
            )
        except Exception as exc:
            payload = owner_console_http_error_response(
                "routes",
                code="internal_error",
                message="failed to build owner console route contract",
                details={"error_type": type(exc).__name__},
                http_api_enabled=True,
            )
            return JSONResponse(status_code=500, content=payload)
        return owner_console_http_success_response(
            "routes",
            snapshot,
            http_api_enabled=True,
        )

    @app.get(f"{OWNER_CONSOLE_HTTP_API_PREFIX}/overview", response_model=None)
    async def owner_console_overview(
        task_limit: str | None = None,
        approval_limit: str | None = None,
    ) -> Any:
        try:
            parsed_task_limit = parse_owner_console_positive_int(
                task_limit,
                default=5,
                field_name="task_limit",
            )
            parsed_approval_limit = parse_owner_console_positive_int(
                approval_limit,
                default=5,
                field_name="approval_limit",
            )
            config = load_config()
            context = build_owner_console_context_from_config(config)
            runtime = create_owner_console_http_read_runtime(
                config_provider=lambda: config,
            )
            overview = runtime.build_overview(
                context,
                task_limit=parsed_task_limit,
                approval_limit=parsed_approval_limit,
            )
        except OwnerConsoleHttpAdapterError as exc:
            payload = owner_console_http_error_response(
                "overview",
                code=exc.code,
                message=exc.message,
                details=exc.details,
                http_api_enabled=True,
            )
            return JSONResponse(status_code=exc.status_code, content=payload)
        except Exception as exc:
            payload = owner_console_http_error_response(
                "overview",
                code="internal_error",
                message="failed to build owner console overview",
                details={"error_type": type(exc).__name__},
                http_api_enabled=True,
            )
            return JSONResponse(status_code=500, content=payload)
        return owner_console_http_success_response(
            "overview",
            overview,
            http_api_enabled=True,
        )

    return app


app = create_owner_console_fastapi_app()
