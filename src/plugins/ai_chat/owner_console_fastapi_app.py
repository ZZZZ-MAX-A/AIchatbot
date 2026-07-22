from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from .agent_tasks import AGENT_APPROVAL_STATUSES, AGENT_TASK_STATUSES
from .config import PROJECT_ROOT, load_config
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
    owner_console_http_action_error_response,
    owner_console_http_action_success_response,
    owner_console_http_error_response,
    owner_console_http_success_response,
)
from .owner_console_manual_diagnostics import (
    MAIN_LLM_CONTRACT_ACTION_HEADER,
    MAIN_LLM_CONTRACT_CONFIRMATION,
    MEMORY_RAG_CONSISTENCY_ACTION_HEADER,
    MEMORY_RAG_CONSISTENCY_CONFIRMATION,
    PROJECT_DOC_RAG_PROBE_ACTION_HEADER,
    PROJECT_DOC_RAG_PROBE_CONFIRMATION,
    OwnerConsoleManualDiagnosticBusy,
    OwnerConsoleManualDiagnosticDisabled,
    create_owner_console_manual_diagnostics_runtime,
)
from .owner_console_read_runtime import DEFAULT_PREVIEW_LIMIT, OWNER_CONSOLE_WORK_TYPES


OWNER_CONSOLE_FASTAPI_APP_TITLE = "AIchatbot Owner Console API"
OWNER_CONSOLE_STATIC_PREFIX = "/owner-console"
OWNER_CONSOLE_STATIC_ENABLED_ENV = "OWNER_CONSOLE_STATIC_ENABLED"
OWNER_CONSOLE_STATIC_DIR_ENV = "OWNER_CONSOLE_STATIC_DIR"
OWNER_CONSOLE_MANUAL_DIAGNOSTICS_ENABLED_ENV = (
    "OWNER_CONSOLE_MANUAL_DIAGNOSTICS_ENABLED"
)
OWNER_CONSOLE_PROJECT_DOC_RAG_PROBE_ENABLED_ENV = (
    "OWNER_CONSOLE_PROJECT_DOC_RAG_PROBE_ENABLED"
)
OWNER_CONSOLE_MEMORY_RAG_CONSISTENCY_ENABLED_ENV = (
    "OWNER_CONSOLE_MEMORY_RAG_CONSISTENCY_ENABLED"
)
OWNER_CONSOLE_MAIN_LLM_CONTRACT_ENABLED_ENV = (
    "OWNER_CONSOLE_MAIN_LLM_CONTRACT_ENABLED"
)
OWNER_CONSOLE_ACTION_COOKIE = "owner_console_action_session"
OWNER_CONSOLE_ACTION_HEADER = "x-owner-console-action"
OWNER_CONSOLE_DEFAULT_STATIC_DIR = PROJECT_ROOT / "web" / "owner-console" / "dist"
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
        "reliability",
        "external-read",
        "manual-diagnostics",
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
    f"{OWNER_CONSOLE_HTTP_API_PREFIX}/reliability",
    f"{OWNER_CONSOLE_HTTP_API_PREFIX}/external-read",
    f"{OWNER_CONSOLE_HTTP_API_PREFIX}/manual-diagnostics",
)


def _owner_console_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _owner_console_bool(value: bool) -> str:
    return "true" if value else "false"


def _owner_console_static_enabled() -> bool:
    return _owner_console_bool_env(OWNER_CONSOLE_STATIC_ENABLED_ENV, False)


def _owner_console_manual_diagnostics_enabled() -> bool:
    return _owner_console_bool_env(
        OWNER_CONSOLE_MANUAL_DIAGNOSTICS_ENABLED_ENV,
        False,
    )


def _owner_console_project_doc_rag_probe_enabled() -> bool:
    return _owner_console_bool_env(
        OWNER_CONSOLE_PROJECT_DOC_RAG_PROBE_ENABLED_ENV,
        False,
    )


def _owner_console_memory_rag_consistency_enabled() -> bool:
    return _owner_console_bool_env(
        OWNER_CONSOLE_MEMORY_RAG_CONSISTENCY_ENABLED_ENV,
        False,
    )


def _owner_console_main_llm_contract_enabled() -> bool:
    return _owner_console_bool_env(
        OWNER_CONSOLE_MAIN_LLM_CONTRACT_ENABLED_ENV,
        False,
    )


def _owner_console_static_dir() -> Path:
    configured = os.getenv(OWNER_CONSOLE_STATIC_DIR_ENV, "").strip()
    if not configured:
        return OWNER_CONSOLE_DEFAULT_STATIC_DIR.resolve()

    path = Path(configured)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _owner_console_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _owner_console_prepare_static_dir() -> Path:
    static_dir = _owner_console_static_dir()
    index_file = static_dir / "index.html"
    if not index_file.is_file():
        raise RuntimeError(
            "Owner Console static mode is enabled but "
            f"{index_file} does not exist. Run npm run build in "
            "web/owner-console or disable OWNER_CONSOLE_STATIC_ENABLED."
        )
    return static_dir


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


def _owner_console_action_success(resource: str, data: Any) -> dict[str, Any]:
    return owner_console_http_action_success_response(
        resource,
        data,
        http_api_enabled=True,
    )


def _owner_console_action_error_response(
    resource: str,
    *,
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    payload = owner_console_http_action_error_response(
        resource,
        code=code,
        message=message,
        details={},
        http_api_enabled=True,
    )
    return JSONResponse(status_code=status_code, content=payload)


def _owner_console_loopback_host(host_header: str) -> bool:
    hostname = urlsplit(f"//{host_header}").hostname
    return hostname in {"127.0.0.1", "localhost", "::1"}


def _owner_console_same_origin_request(request: Request) -> bool:
    host = request.headers.get("host", "").strip().lower()
    origin = request.headers.get("origin", "").strip().lower()
    if not host or not origin or not _owner_console_loopback_host(host):
        return False
    parsed = urlsplit(origin)
    return (
        parsed.scheme == "http"
        and parsed.netloc == host
        and not parsed.path
        and not parsed.query
        and not parsed.fragment
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


def _register_owner_console_static_routes(app: FastAPI, static_dir: Path) -> None:
    index_file = static_dir / "index.html"
    assets_dir = static_dir / "assets"

    @app.get(OWNER_CONSOLE_STATIC_PREFIX, include_in_schema=False)
    @app.get(f"{OWNER_CONSOLE_STATIC_PREFIX}/", include_in_schema=False)
    async def owner_console_static_index() -> FileResponse:
        return FileResponse(index_file, media_type="text/html")

    @app.get(
        f"{OWNER_CONSOLE_STATIC_PREFIX}/assets/{{asset_path:path}}",
        include_in_schema=False,
    )
    async def owner_console_static_asset(asset_path: str) -> FileResponse:
        asset_file = (assets_dir / asset_path).resolve()
        if (
            not _owner_console_is_relative_to(asset_file, assets_dir)
            or not asset_file.is_file()
        ):
            raise HTTPException(status_code=404, detail="Owner Console asset not found")
        return FileResponse(asset_file)

    @app.get(
        f"{OWNER_CONSOLE_STATIC_PREFIX}/{{client_path:path}}",
        include_in_schema=False,
    )
    async def owner_console_static_fallback(client_path: str) -> FileResponse:
        if client_path.startswith("assets/"):
            raise HTTPException(status_code=404, detail="Owner Console asset not found")
        return FileResponse(index_file, media_type="text/html")


def create_owner_console_fastapi_app(
    *,
    manual_diagnostics_runtime: Any | None = None,
    action_session_token: str | None = None,
) -> FastAPI:
    manual_runtime = manual_diagnostics_runtime
    if manual_runtime is None:
        manual_runtime = create_owner_console_manual_diagnostics_runtime(
            config_provider=load_config,
            manual_diagnostic_actions_enabled=(
                _owner_console_manual_diagnostics_enabled()
            ),
            project_doc_rag_probe_enabled=(
                _owner_console_project_doc_rag_probe_enabled()
            ),
            memory_rag_consistency_enabled=(
                _owner_console_memory_rag_consistency_enabled()
            ),
            main_llm_contract_enabled=(
                _owner_console_main_llm_contract_enabled()
            ),
        )
    manual_snapshot = manual_runtime.build_snapshot()
    project_doc_rag_action_enabled = bool(
        manual_snapshot.project_doc_rag_probe_enabled
    )
    memory_rag_action_enabled = bool(
        manual_snapshot.memory_rag_consistency_enabled
    )
    main_llm_action_enabled = bool(
        manual_snapshot.main_llm_contract_enabled
    )
    manual_action_enabled = bool(
        project_doc_rag_action_enabled
        or memory_rag_action_enabled
        or main_llm_action_enabled
    )
    enabled_route_names = set(OWNER_CONSOLE_FASTAPI_ENABLED_ROUTE_NAMES)
    enabled_routes = list(OWNER_CONSOLE_FASTAPI_ENABLED_ROUTES)
    if project_doc_rag_action_enabled:
        enabled_route_names.add("manual-diagnostics.project-doc-rag")
        enabled_routes.append(
            f"{OWNER_CONSOLE_HTTP_API_PREFIX}"
            "/manual-diagnostics/project-doc-rag"
        )
    if memory_rag_action_enabled:
        enabled_route_names.add("manual-diagnostics.memory-rag-consistency")
        enabled_routes.append(
            f"{OWNER_CONSOLE_HTTP_API_PREFIX}"
            "/manual-diagnostics/memory-rag-consistency"
        )
    if main_llm_action_enabled:
        enabled_route_names.add("manual-diagnostics.main-llm-contract")
        enabled_routes.append(
            f"{OWNER_CONSOLE_HTTP_API_PREFIX}"
            "/manual-diagnostics/main-llm-contract"
        )
    action_token = action_session_token or secrets.token_urlsafe(32)

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
            "snapshot_read_only": True,
            "http_api_enabled": True,
            "web_write_enabled": False,
            "manual_diagnostic_actions_enabled": manual_action_enabled,
            "automatic_diagnostics_enabled": False,
            "configuration_write_enabled": False,
            "business_data_write_enabled": False,
            "enabled_routes": enabled_routes,
        }

    @app.get(f"{OWNER_CONSOLE_HTTP_API_PREFIX}/routes", response_model=None)
    async def owner_console_routes() -> Any:
        try:
            snapshot = build_owner_console_http_route_contract_snapshot(
                enabled_route_names=frozenset(enabled_route_names),
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
        work_type: str | None = None,
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
            parsed_work_type = parse_owner_console_optional_status(
                work_type,
                allowed_statuses=OWNER_CONSOLE_WORK_TYPES,
                field_name="work_type",
            )
            config = load_config()
            context = build_owner_console_context_from_config(config)
            runtime = _owner_console_runtime_from_config(config)
            task_list = runtime.build_task_list(
                context,
                status=parsed_status,
                work_type=parsed_work_type,
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

    @app.get(f"{OWNER_CONSOLE_HTTP_API_PREFIX}/external-read", response_model=None)
    async def owner_console_external_read() -> Any:
        try:
            config = load_config()
            context = build_owner_console_context_from_config(config)
            runtime = _owner_console_runtime_from_config(config)
            snapshot = runtime.build_external_read_snapshot(context)
        except OwnerConsoleHttpAdapterError as exc:
            return _owner_console_adapter_error(
                "external-read",
                exc,
            )
        except Exception as exc:
            return _owner_console_internal_error(
                "external-read",
                message="failed to build owner console external read snapshot",
                exc=exc,
            )
        return _owner_console_success(
            "external-read",
            snapshot,
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

    @app.get(f"{OWNER_CONSOLE_HTTP_API_PREFIX}/reliability", response_model=None)
    async def owner_console_reliability() -> Any:
        try:
            config = load_config()
            runtime = _owner_console_runtime_from_config(config)
            snapshot = runtime.build_reliability_snapshot()
        except Exception as exc:
            return _owner_console_internal_error(
                "reliability",
                message="failed to build owner console reliability snapshot",
                exc=exc,
            )
        return _owner_console_success(
            "reliability",
            snapshot,
        )

    @app.get(
        f"{OWNER_CONSOLE_HTTP_API_PREFIX}/manual-diagnostics",
        response_model=None,
    )
    async def owner_console_manual_diagnostics() -> Any:
        payload = _owner_console_success(
            "manual-diagnostics",
            manual_runtime.build_snapshot(),
        )
        response = JSONResponse(content=payload)
        response.set_cookie(
            OWNER_CONSOLE_ACTION_COOKIE,
            action_token,
            httponly=True,
            samesite="strict",
            secure=False,
            path=OWNER_CONSOLE_HTTP_API_PREFIX,
        )
        return response

    @app.post(
        f"{OWNER_CONSOLE_HTTP_API_PREFIX}"
        "/manual-diagnostics/project-doc-rag",
        response_model=None,
    )
    async def owner_console_project_doc_rag_probe(request: Request) -> Any:
        resource = "manual-diagnostics/project-doc-rag"
        if not project_doc_rag_action_enabled:
            return _owner_console_action_error_response(
                resource,
                status_code=403,
                code="forbidden",
                message="project document RAG manual probe is disabled",
            )
        if not _owner_console_same_origin_request(request):
            return _owner_console_action_error_response(
                resource,
                status_code=403,
                code="forbidden",
                message="manual diagnostic action requires a same-origin loopback request",
            )
        if request.headers.get(OWNER_CONSOLE_ACTION_HEADER, "") != (
            PROJECT_DOC_RAG_PROBE_ACTION_HEADER
        ):
            return _owner_console_action_error_response(
                resource,
                status_code=403,
                code="forbidden",
                message="manual diagnostic action header is invalid",
            )
        cookie_token = request.cookies.get(OWNER_CONSOLE_ACTION_COOKIE, "")
        if not cookie_token or not secrets.compare_digest(
            cookie_token,
            action_token,
        ):
            return _owner_console_action_error_response(
                resource,
                status_code=403,
                code="forbidden",
                message="manual diagnostic action session is invalid",
            )
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type.strip().lower() != "application/json":
            return _owner_console_action_error_response(
                resource,
                status_code=400,
                code="bad_request",
                message="manual diagnostic action requires application/json",
            )
        try:
            body = await request.json()
        except Exception:
            body = None
        if body != {"confirmation": PROJECT_DOC_RAG_PROBE_CONFIRMATION}:
            return _owner_console_action_error_response(
                resource,
                status_code=400,
                code="bad_request",
                message="manual diagnostic confirmation is invalid",
            )
        try:
            result = await run_in_threadpool(
                manual_runtime.run_project_doc_rag_probe
            )
        except OwnerConsoleManualDiagnosticDisabled:
            return _owner_console_action_error_response(
                resource,
                status_code=403,
                code="forbidden",
                message="project document RAG manual probe is disabled",
            )
        except OwnerConsoleManualDiagnosticBusy:
            return _owner_console_action_error_response(
                resource,
                status_code=409,
                code="conflict",
                message="another manual diagnostic is already running",
            )
        return _owner_console_action_success(resource, result)

    @app.post(
        f"{OWNER_CONSOLE_HTTP_API_PREFIX}"
        "/manual-diagnostics/memory-rag-consistency",
        response_model=None,
    )
    async def owner_console_memory_rag_consistency(request: Request) -> Any:
        resource = "manual-diagnostics/memory-rag-consistency"
        if not memory_rag_action_enabled:
            return _owner_console_action_error_response(
                resource,
                status_code=403,
                code="forbidden",
                message="MemoryRAG consistency diagnostic is disabled",
            )
        if not _owner_console_same_origin_request(request):
            return _owner_console_action_error_response(
                resource,
                status_code=403,
                code="forbidden",
                message="manual diagnostic action requires a same-origin loopback request",
            )
        if request.headers.get(OWNER_CONSOLE_ACTION_HEADER, "") != (
            MEMORY_RAG_CONSISTENCY_ACTION_HEADER
        ):
            return _owner_console_action_error_response(
                resource,
                status_code=403,
                code="forbidden",
                message="manual diagnostic action header is invalid",
            )
        cookie_token = request.cookies.get(OWNER_CONSOLE_ACTION_COOKIE, "")
        if not cookie_token or not secrets.compare_digest(
            cookie_token,
            action_token,
        ):
            return _owner_console_action_error_response(
                resource,
                status_code=403,
                code="forbidden",
                message="manual diagnostic action session is invalid",
            )
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type.strip().lower() != "application/json":
            return _owner_console_action_error_response(
                resource,
                status_code=400,
                code="bad_request",
                message="manual diagnostic action requires application/json",
            )
        try:
            body = await request.json()
        except Exception:
            body = None
        if body != {"confirmation": MEMORY_RAG_CONSISTENCY_CONFIRMATION}:
            return _owner_console_action_error_response(
                resource,
                status_code=400,
                code="bad_request",
                message="manual diagnostic confirmation is invalid",
            )
        try:
            result = await run_in_threadpool(
                manual_runtime.run_memory_rag_consistency
            )
        except OwnerConsoleManualDiagnosticDisabled:
            return _owner_console_action_error_response(
                resource,
                status_code=403,
                code="forbidden",
                message="MemoryRAG consistency diagnostic is disabled",
            )
        except OwnerConsoleManualDiagnosticBusy:
            return _owner_console_action_error_response(
                resource,
                status_code=409,
                code="conflict",
                message="another manual diagnostic is already running",
            )
        return _owner_console_action_success(resource, result)

    @app.post(
        f"{OWNER_CONSOLE_HTTP_API_PREFIX}"
        "/manual-diagnostics/main-llm-contract",
        response_model=None,
    )
    async def owner_console_main_llm_contract(request: Request) -> Any:
        resource = "manual-diagnostics/main-llm-contract"
        if not main_llm_action_enabled:
            return _owner_console_action_error_response(
                resource,
                status_code=403,
                code="forbidden",
                message="Main LLM contract diagnostic is disabled",
            )
        if not _owner_console_same_origin_request(request):
            return _owner_console_action_error_response(
                resource,
                status_code=403,
                code="forbidden",
                message="manual diagnostic action requires a same-origin loopback request",
            )
        if request.headers.get(OWNER_CONSOLE_ACTION_HEADER, "") != (
            MAIN_LLM_CONTRACT_ACTION_HEADER
        ):
            return _owner_console_action_error_response(
                resource,
                status_code=403,
                code="forbidden",
                message="manual diagnostic action header is invalid",
            )
        cookie_token = request.cookies.get(OWNER_CONSOLE_ACTION_COOKIE, "")
        if not cookie_token or not secrets.compare_digest(
            cookie_token,
            action_token,
        ):
            return _owner_console_action_error_response(
                resource,
                status_code=403,
                code="forbidden",
                message="manual diagnostic action session is invalid",
            )
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type.strip().lower() != "application/json":
            return _owner_console_action_error_response(
                resource,
                status_code=400,
                code="bad_request",
                message="manual diagnostic action requires application/json",
            )
        try:
            body = await request.json()
        except Exception:
            body = None
        if body != {"confirmation": MAIN_LLM_CONTRACT_CONFIRMATION}:
            return _owner_console_action_error_response(
                resource,
                status_code=400,
                code="bad_request",
                message="manual diagnostic confirmation is invalid",
            )
        try:
            result = await run_in_threadpool(
                manual_runtime.run_main_llm_contract
            )
        except OwnerConsoleManualDiagnosticDisabled:
            return _owner_console_action_error_response(
                resource,
                status_code=403,
                code="forbidden",
                message="Main LLM contract diagnostic is disabled",
            )
        except OwnerConsoleManualDiagnosticBusy:
            return _owner_console_action_error_response(
                resource,
                status_code=409,
                code="conflict",
                message="another manual diagnostic is already running",
            )
        return _owner_console_action_success(resource, result)

    if _owner_console_static_enabled():
        _register_owner_console_static_routes(
            app,
            _owner_console_prepare_static_dir(),
        )

    return app


app = create_owner_console_fastapi_app()
