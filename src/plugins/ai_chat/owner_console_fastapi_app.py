from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .agent_tasks import AGENT_APPROVAL_STATUSES, AGENT_TASK_STATUSES
from .config import load_config
from .owner_console_http_adapter import (
    OwnerConsoleHttpAdapterError,
    build_owner_console_context_from_config,
    create_owner_console_http_read_runtime,
    parse_owner_console_optional_status,
    parse_owner_console_positive_int,
    parse_owner_console_required_positive_int,
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
from .owner_console_read_runtime import DEFAULT_PREVIEW_LIMIT


OWNER_CONSOLE_FASTAPI_APP_TITLE = "AIchatbot Owner Console API"
OWNER_CONSOLE_FASTAPI_ENABLED_ROUTE_NAMES = frozenset(
    {
        "routes",
        "overview",
        "tasks",
        "tasks.detail",
        "approvals",
        "approvals.detail",
        "access-control",
        "settings",
        "memory",
        "diagnostics",
    }
)
OWNER_CONSOLE_FASTAPI_ENABLED_ROUTES = (
    "/healthz",
    f"{OWNER_CONSOLE_HTTP_API_PREFIX}/routes",
    f"{OWNER_CONSOLE_HTTP_API_PREFIX}/overview",
    f"{OWNER_CONSOLE_HTTP_API_PREFIX}/tasks",
    f"{OWNER_CONSOLE_HTTP_API_PREFIX}/tasks/{{task_id}}",
    f"{OWNER_CONSOLE_HTTP_API_PREFIX}/approvals",
    f"{OWNER_CONSOLE_HTTP_API_PREFIX}/approvals/{{approval_id}}",
    f"{OWNER_CONSOLE_HTTP_API_PREFIX}/access-control",
    f"{OWNER_CONSOLE_HTTP_API_PREFIX}/settings",
    f"{OWNER_CONSOLE_HTTP_API_PREFIX}/memory",
    f"{OWNER_CONSOLE_HTTP_API_PREFIX}/diagnostics",
)


def _owner_console_bool(value: bool) -> str:
    return "true" if value else "false"


def _owner_console_runtime_from_config(config: Any) -> Any:
    return create_owner_console_http_read_runtime(
        config_provider=lambda: config,
    )


def _owner_console_success(resource: str, data: Any) -> Any:
    return owner_console_http_success_response(
        resource,
        data,
        http_api_enabled=True,
    )


def _owner_console_error_response(
    resource: str,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    payload = owner_console_http_error_response(
        resource,
        code=code,
        message=message,
        details=details,
        http_api_enabled=True,
    )
    return JSONResponse(status_code=status_code, content=payload)


def _owner_console_adapter_error(
    resource: str,
    exc: OwnerConsoleHttpAdapterError,
) -> JSONResponse:
    return _owner_console_error_response(
        resource,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


def _owner_console_internal_error(
    resource: str,
    message: str,
    exc: Exception,
) -> JSONResponse:
    return _owner_console_error_response(
        resource,
        status_code=500,
        code="internal_error",
        message=message,
        details={"error_type": type(exc).__name__},
    )


def _build_owner_console_http_diagnostics(runtime: Any, config: Any) -> Any:
    memory = runtime.build_memory_snapshot()
    counts = memory.counts
    return runtime.build_health_snapshot(
        bot_status_lines=[
            "Owner Console HTTP API: ok",
            "transport=http",
            "mode=read_only",
            "web_write_enabled=false",
        ],
        diagnostics=[
            "diagnostics_snapshot=read_only",
            "external_probes_executed=false",
            "qq_adapter_imported=false",
            "diagnostics_module_imported=false",
        ],
        config=[
            f"bot_owner_configured={_owner_console_bool(bool(config.bot_owner_qq))}",
            f"enable_private_chat={_owner_console_bool(config.enable_private_chat)}",
            f"enable_group_chat={_owner_console_bool(config.enable_group_chat)}",
            f"enable_main_agent={_owner_console_bool(config.enable_main_agent)}",
            f"main_agent_use_llm={_owner_console_bool(config.main_agent_use_llm)}",
            f"enable_chat_graph_runtime={_owner_console_bool(config.enable_chat_graph_runtime)}",
        ],
        vision=[
            f"enable_vision={_owner_console_bool(config.enable_vision)}",
            f"vision_model={config.vision_model}",
            f"vision_num_ctx={config.vision_num_ctx}",
            f"vision_max_images={config.vision_max_images}",
            "ollama_probe_executed=false",
            "vision_inference_executed=false",
        ],
        image_cache=[
            "image_cache_stats_collected=false",
            f"image_cache_ttl_seconds={config.vision_image_cache_ttl_seconds}",
            f"private_image_wait_seconds={config.vision_private_image_wait_seconds}",
        ],
        memory=[
            "memory_snapshot=collected",
            f"message_count={counts.message_count}",
            f"session_count={counts.session_count}",
            f"session_summary_count={counts.session_summary_count}",
            f"manual_memory_count={counts.manual_memory_count}",
            f"rag_document_count={counts.rag_document_count}",
            f"rag_embedding_count={counts.rag_embedding_count}",
            f"memory_content_exposed={_owner_console_bool(memory.memory_content_exposed)}",
            f"project_doc_content_exposed={_owner_console_bool(memory.project_doc_content_exposed)}",
            f"retrieval_executed={_owner_console_bool(memory.retrieval_executed)}",
            f"index_rebuild_executed={_owner_console_bool(memory.index_rebuild_executed)}",
        ],
        tts=[
            f"enable_tts={_owner_console_bool(config.enable_tts)}",
            f"tts_voice_configured={_owner_console_bool(bool(config.tts_voice))}",
            f"tts_auto_start={_owner_console_bool(config.tts_auto_start)}",
            "tts_probe_executed=false",
        ],
        recent_errors=[
            "recent_error_log_read=false",
            "recent_errors_collected=false",
        ],
        main_agent_observation_lines=[],
        root_graph_observation_lines=[],
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
            return _owner_console_internal_error(
                "routes",
                message="failed to build owner console route contract",
                exc=exc,
            )
        return _owner_console_success(
            "routes",
            snapshot,
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
            runtime = _owner_console_runtime_from_config(config)
            overview = runtime.build_overview(
                context,
                task_limit=parsed_task_limit,
                approval_limit=parsed_approval_limit,
            )
        except OwnerConsoleHttpAdapterError as exc:
            return _owner_console_adapter_error(
                "overview",
                exc,
            )
        except Exception as exc:
            return _owner_console_internal_error(
                "overview",
                message="failed to build owner console overview",
                exc=exc,
            )
        return _owner_console_success(
            "overview",
            overview,
        )

    @app.get(f"{OWNER_CONSOLE_HTTP_API_PREFIX}/tasks", response_model=None)
    async def owner_console_tasks(
        status: str | None = None,
        limit: str | None = None,
    ) -> Any:
        try:
            parsed_status = parse_owner_console_optional_status(
                status,
                allowed_statuses=AGENT_TASK_STATUSES,
            )
            parsed_limit = parse_owner_console_positive_int(
                limit,
                default=20,
                field_name="limit",
            )
            config = load_config()
            context = build_owner_console_context_from_config(config)
            runtime = _owner_console_runtime_from_config(config)
            task_list = runtime.build_task_list(
                context,
                status=parsed_status,
                limit=parsed_limit,
            )
        except OwnerConsoleHttpAdapterError as exc:
            return _owner_console_adapter_error(
                "tasks",
                exc,
            )
        except Exception as exc:
            return _owner_console_internal_error(
                "tasks",
                message="failed to build owner console task list",
                exc=exc,
            )
        return _owner_console_success(
            "tasks",
            task_list,
        )

    @app.get(f"{OWNER_CONSOLE_HTTP_API_PREFIX}/tasks/{{task_id}}", response_model=None)
    async def owner_console_task_detail(
        task_id: str,
        event_limit: str | None = None,
        preview_limit: str | None = None,
    ) -> Any:
        try:
            parsed_task_id = parse_owner_console_required_positive_int(
                task_id,
                field_name="task_id",
            )
            parsed_event_limit = parse_owner_console_positive_int(
                event_limit,
                default=20,
                field_name="event_limit",
            )
            parsed_preview_limit = parse_owner_console_positive_int(
                preview_limit,
                default=DEFAULT_PREVIEW_LIMIT,
                field_name="preview_limit",
            )
            config = load_config()
            context = build_owner_console_context_from_config(config)
            runtime = _owner_console_runtime_from_config(config)
            task_detail = runtime.build_task_detail(
                context,
                parsed_task_id,
                event_limit=parsed_event_limit,
                preview_limit=parsed_preview_limit,
            )
            if task_detail is None:
                return _owner_console_error_response(
                    "tasks",
                    status_code=404,
                    code="not_found",
                    message="owner console task not found",
                    details={"task_id": parsed_task_id},
                )
        except OwnerConsoleHttpAdapterError as exc:
            return _owner_console_adapter_error(
                "tasks",
                exc,
            )
        except Exception as exc:
            return _owner_console_internal_error(
                "tasks",
                message="failed to build owner console task detail",
                exc=exc,
            )
        return _owner_console_success(
            "tasks",
            task_detail,
        )

    @app.get(f"{OWNER_CONSOLE_HTTP_API_PREFIX}/approvals", response_model=None)
    async def owner_console_approvals(
        status: str | None = None,
        limit: str | None = None,
    ) -> Any:
        try:
            parsed_status = parse_owner_console_optional_status(
                status,
                allowed_statuses=AGENT_APPROVAL_STATUSES,
            )
            parsed_limit = parse_owner_console_positive_int(
                limit,
                default=20,
                field_name="limit",
            )
            config = load_config()
            context = build_owner_console_context_from_config(config)
            runtime = _owner_console_runtime_from_config(config)
            approval_list = runtime.build_approval_list(
                context,
                status=parsed_status,
                limit=parsed_limit,
            )
        except OwnerConsoleHttpAdapterError as exc:
            return _owner_console_adapter_error(
                "approvals",
                exc,
            )
        except Exception as exc:
            return _owner_console_internal_error(
                "approvals",
                message="failed to build owner console approval list",
                exc=exc,
            )
        return _owner_console_success(
            "approvals",
            approval_list,
        )

    @app.get(
        f"{OWNER_CONSOLE_HTTP_API_PREFIX}/approvals/{{approval_id}}",
        response_model=None,
    )
    async def owner_console_approval_detail(
        approval_id: str,
        event_limit: str | None = None,
        preview_limit: str | None = None,
    ) -> Any:
        try:
            parsed_approval_id = parse_owner_console_required_positive_int(
                approval_id,
                field_name="approval_id",
            )
            parsed_event_limit = parse_owner_console_positive_int(
                event_limit,
                default=5,
                field_name="event_limit",
            )
            parsed_preview_limit = parse_owner_console_positive_int(
                preview_limit,
                default=DEFAULT_PREVIEW_LIMIT,
                field_name="preview_limit",
            )
            config = load_config()
            context = build_owner_console_context_from_config(config)
            runtime = _owner_console_runtime_from_config(config)
            approval_detail = runtime.build_approval_detail(
                context,
                parsed_approval_id,
                event_limit=parsed_event_limit,
                preview_limit=parsed_preview_limit,
            )
            if approval_detail is None:
                return _owner_console_error_response(
                    "approvals",
                    status_code=404,
                    code="not_found",
                    message="owner console approval not found",
                    details={"approval_id": parsed_approval_id},
                )
        except OwnerConsoleHttpAdapterError as exc:
            return _owner_console_adapter_error(
                "approvals",
                exc,
            )
        except Exception as exc:
            return _owner_console_internal_error(
                "approvals",
                message="failed to build owner console approval detail",
                exc=exc,
            )
        return _owner_console_success(
            "approvals",
            approval_detail,
        )

    @app.get(f"{OWNER_CONSOLE_HTTP_API_PREFIX}/access-control", response_model=None)
    async def owner_console_access_control(
        item_limit: str | None = None,
    ) -> Any:
        try:
            parsed_item_limit = parse_owner_console_positive_int(
                item_limit,
                default=50,
                field_name="item_limit",
            )
            config = load_config()
            runtime = _owner_console_runtime_from_config(config)
            access_control = runtime.build_access_control_snapshot(
                item_limit=parsed_item_limit,
            )
        except OwnerConsoleHttpAdapterError as exc:
            return _owner_console_adapter_error(
                "access-control",
                exc,
            )
        except Exception as exc:
            return _owner_console_internal_error(
                "access-control",
                message="failed to build owner console access control snapshot",
                exc=exc,
            )
        return _owner_console_success(
            "access-control",
            access_control,
        )

    @app.get(f"{OWNER_CONSOLE_HTTP_API_PREFIX}/settings", response_model=None)
    async def owner_console_settings() -> Any:
        try:
            config = load_config()
            runtime = _owner_console_runtime_from_config(config)
            settings = runtime.build_settings_snapshot()
        except OwnerConsoleHttpAdapterError as exc:
            return _owner_console_adapter_error(
                "settings",
                exc,
            )
        except Exception as exc:
            return _owner_console_internal_error(
                "settings",
                message="failed to build owner console settings snapshot",
                exc=exc,
            )
        return _owner_console_success(
            "settings",
            settings,
        )

    @app.get(f"{OWNER_CONSOLE_HTTP_API_PREFIX}/memory", response_model=None)
    async def owner_console_memory() -> Any:
        try:
            config = load_config()
            runtime = _owner_console_runtime_from_config(config)
            memory = runtime.build_memory_snapshot()
        except OwnerConsoleHttpAdapterError as exc:
            return _owner_console_adapter_error(
                "memory",
                exc,
            )
        except Exception as exc:
            return _owner_console_internal_error(
                "memory",
                message="failed to build owner console memory snapshot",
                exc=exc,
            )
        return _owner_console_success(
            "memory",
            memory,
        )

    @app.get(f"{OWNER_CONSOLE_HTTP_API_PREFIX}/diagnostics", response_model=None)
    async def owner_console_diagnostics() -> Any:
        try:
            config = load_config()
            runtime = _owner_console_runtime_from_config(config)
            diagnostics = _build_owner_console_http_diagnostics(runtime, config)
        except OwnerConsoleHttpAdapterError as exc:
            return _owner_console_adapter_error(
                "diagnostics",
                exc,
            )
        except Exception as exc:
            return _owner_console_internal_error(
                "diagnostics",
                message="failed to build owner console diagnostics snapshot",
                exc=exc,
            )
        return _owner_console_success(
            "diagnostics",
            diagnostics,
        )

    return app


app = create_owner_console_fastapi_app()
