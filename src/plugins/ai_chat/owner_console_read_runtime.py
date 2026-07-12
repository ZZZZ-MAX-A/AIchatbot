from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib import metadata
import json
from typing import Any, TypeAlias

from .agent_tasks import (
    AGENT_APPROVAL_PENDING,
    AGENT_TASK_CANCELLED,
    AGENT_TASK_DONE,
    AGENT_TASK_FAILED,
    AGENT_TASK_PENDING,
    AGENT_TASK_RUNNING,
    AgentApproval,
    AgentTask,
    AgentTaskEvent,
    agent_task_work_type,
    agent_approval_status_label,
    agent_task_status_label,
    count_agent_approvals,
    count_agent_tasks,
    get_agent_approval,
    get_agent_task,
    latest_agent_task_event,
    list_agent_approvals,
    list_agent_task_events,
    list_agent_tasks,
)
from .access_store import AccessStore
from .config import AiChatConfig
from .database import utc_now
from . import database as database_module
from .external_read_status import latest_external_read_task_snapshot
from .main_agent_observability import redacted_base_url
from .owner_console_read_models import (
    OWNER_CONSOLE_SCHEMA_VERSION,
    OwnerConsoleAccessControlSnapshot,
    OwnerConsoleAccessList,
    OwnerConsoleApprovalActionability,
    OwnerConsoleApprovalDetail,
    OwnerConsoleApprovalList,
    OwnerConsoleApprovalRow,
    OwnerConsoleContext,
    OwnerConsoleHealthSnapshot,
    OwnerConsoleExternalReadBoundary,
    OwnerConsoleExternalReadDependencySnapshot,
    OwnerConsoleExternalReadSnapshot,
    OwnerConsoleExternalReadTaskSnapshot,
    OwnerConsoleMemoryContextPolicy,
    OwnerConsoleMemoryCounts,
    OwnerConsoleMemoryRagSnapshot,
    OwnerConsoleMemorySnapshot,
    OwnerConsoleModelConfigSnapshot,
    OwnerConsoleObservationSnapshot,
    OwnerConsoleOverview,
    OwnerConsoleOverviewCounters,
    OwnerConsoleProjectDocRagSnapshot,
    OwnerConsoleProviderWiringRow,
    OwnerConsoleProviderWiringSnapshot,
    OwnerConsoleReadRouteContractSnapshot,
    OwnerConsoleReadRouteRow,
    OwnerConsoleRoleCardRow,
    OwnerConsoleRuntimeBoundary,
    OwnerConsoleSettingsSnapshot,
    OwnerConsoleTaskDetail,
    OwnerConsoleTaskEventRow,
    OwnerConsoleTaskList,
    OwnerConsoleTaskRow,
    OwnerConsoleTextSnapshotSection,
    OwnerConsoleToolInputPreview,
    owner_console_page_response,
    owner_console_to_jsonable,
)


@dataclass(frozen=True)
class OwnerConsoleReadRouteSpec:
    page: str
    response_page: str
    runtime_method: str
    read_model: str
    requires_context: bool
    required_params: tuple[str, ...] = ()
    optional_params: tuple[str, ...] = ()


OWNER_CONSOLE_READ_ROUTE_SPECS = (
    OwnerConsoleReadRouteSpec(
        page="dashboard",
        response_page="dashboard",
        runtime_method="build_overview",
        read_model="OwnerConsoleOverview",
        requires_context=True,
        optional_params=("task_limit", "approval_limit"),
    ),
    OwnerConsoleReadRouteSpec(
        page="tasks",
        response_page="tasks",
        runtime_method="build_task_list",
        read_model="OwnerConsoleTaskList",
        requires_context=True,
        optional_params=("status", "work_type", "limit"),
    ),
    OwnerConsoleReadRouteSpec(
        page="task_detail",
        response_page="task_detail",
        runtime_method="build_task_detail",
        read_model="OwnerConsoleTaskDetail",
        requires_context=True,
        required_params=("task_id",),
        optional_params=("event_limit", "preview_limit"),
    ),
    OwnerConsoleReadRouteSpec(
        page="approvals",
        response_page="approvals",
        runtime_method="build_approval_list",
        read_model="OwnerConsoleApprovalList",
        requires_context=True,
        optional_params=("status", "limit"),
    ),
    OwnerConsoleReadRouteSpec(
        page="approval_detail",
        response_page="approval_detail",
        runtime_method="build_approval_detail",
        read_model="OwnerConsoleApprovalDetail",
        requires_context=True,
        required_params=("approval_id",),
        optional_params=("event_limit", "preview_limit"),
    ),
    OwnerConsoleReadRouteSpec(
        page="diagnostics",
        response_page="diagnostics",
        runtime_method="build_health_snapshot",
        read_model="OwnerConsoleHealthSnapshot",
        requires_context=False,
        optional_params=(
            "bot_status_lines",
            "diagnostics",
            "config",
            "vision",
            "image_cache",
            "memory",
            "tts",
            "recent_errors",
            "main_agent_observation_lines",
            "root_graph_observation_lines",
        ),
    ),
    OwnerConsoleReadRouteSpec(
        page="external_read",
        response_page="external_read",
        runtime_method="build_external_read_snapshot",
        read_model="OwnerConsoleExternalReadSnapshot",
        requires_context=True,
    ),
    OwnerConsoleReadRouteSpec(
        page="memory",
        response_page="memory",
        runtime_method="build_memory_snapshot",
        read_model="OwnerConsoleMemorySnapshot",
        requires_context=False,
    ),
    OwnerConsoleReadRouteSpec(
        page="access_control",
        response_page="access_control",
        runtime_method="build_access_control_snapshot",
        read_model="OwnerConsoleAccessControlSnapshot",
        requires_context=False,
        optional_params=("item_limit",),
    ),
    OwnerConsoleReadRouteSpec(
        page="settings",
        response_page="settings",
        runtime_method="build_settings_snapshot",
        read_model="OwnerConsoleSettingsSnapshot",
        requires_context=False,
    ),
)


def build_owner_console_route_contract_snapshot() -> OwnerConsoleReadRouteContractSnapshot:
    rows = [
        OwnerConsoleReadRouteRow(
            page=spec.page,
            response_page=spec.response_page,
            runtime_method=spec.runtime_method,
            read_model=spec.read_model,
            requires_context=spec.requires_context,
            required_params=list(spec.required_params),
            optional_params=list(spec.optional_params),
            read_only=True,
            http_api_enabled=False,
            web_write_enabled=False,
            direct_qq_dependency_allowed=False,
            write_side_effect_allowed=False,
        )
        for spec in OWNER_CONSOLE_READ_ROUTE_SPECS
    ]
    return OwnerConsoleReadRouteContractSnapshot(
        generated_at=utc_now(),
        route_count=len(rows),
        rows=rows,
        boundary=OwnerConsoleRuntimeBoundary(),
    )


SENSITIVE_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "authorization",
    "access_token",
    "refresh_token",
    "password",
    "secret",
    "cookie",
)
DEFAULT_PREVIEW_LIMIT = 240
OWNER_CONSOLE_WORK_TYPES = frozenset(
    {
        "development_context_report",
        "system_diagnostics_report",
        "external_read_report",
    }
)
ConfigProvider: TypeAlias = Callable[[], AiChatConfig]
AccessProvider: TypeAlias = Callable[[], AccessStore]
RoleCardsProvider: TypeAlias = Callable[[], list[Any]]
ActiveRoleCardKeyProvider: TypeAlias = Callable[[], str]
StatsProvider: TypeAlias = Callable[[], dict[str, Any]]


def _empty_role_cards_provider() -> list[Any]:
    return []


def _empty_active_role_card_key_provider() -> str:
    return ""


def _empty_stats_provider() -> dict[str, Any]:
    return {}


@dataclass(frozen=True)
class OwnerConsoleReadProviderSpec:
    provider_name: str
    required: bool
    read_model_area: str
    owner_console_methods: tuple[str, ...]
    fallback_behavior: str


OWNER_CONSOLE_READ_PROVIDER_SPECS = (
    OwnerConsoleReadProviderSpec(
        provider_name="config_provider",
        required=True,
        read_model_area="access/settings/memory",
        owner_console_methods=(
            "build_access_control_snapshot",
            "build_settings_snapshot",
            "build_memory_snapshot",
        ),
        fallback_behavior="none; required for config-backed snapshots",
    ),
    OwnerConsoleReadProviderSpec(
        provider_name="access_provider",
        required=True,
        read_model_area="access",
        owner_console_methods=("build_access_control_snapshot",),
        fallback_behavior="none; required for access control snapshot",
    ),
    OwnerConsoleReadProviderSpec(
        provider_name="role_cards_provider",
        required=False,
        read_model_area="settings",
        owner_console_methods=("build_settings_snapshot",),
        fallback_behavior="empty role card list",
    ),
    OwnerConsoleReadProviderSpec(
        provider_name="active_role_card_key_provider",
        required=False,
        read_model_area="settings",
        owner_console_methods=("build_settings_snapshot",),
        fallback_behavior="empty active role card key",
    ),
    OwnerConsoleReadProviderSpec(
        provider_name="memory_stats_provider",
        required=False,
        read_model_area="memory",
        owner_console_methods=("build_memory_snapshot",),
        fallback_behavior="zero memory counters",
    ),
    OwnerConsoleReadProviderSpec(
        provider_name="manual_memory_stats_provider",
        required=False,
        read_model_area="memory",
        owner_console_methods=("build_memory_snapshot",),
        fallback_behavior="zero manual memory counters",
    ),
    OwnerConsoleReadProviderSpec(
        provider_name="gap_scene_stats_provider",
        required=False,
        read_model_area="memory",
        owner_console_methods=("build_memory_snapshot",),
        fallback_behavior="zero gap scene counters",
    ),
    OwnerConsoleReadProviderSpec(
        provider_name="rag_document_stats_provider",
        required=False,
        read_model_area="memory",
        owner_console_methods=("build_memory_snapshot",),
        fallback_behavior="zero RAG document counters",
    ),
)


@dataclass(frozen=True)
class OwnerConsoleReadProviders:
    config_provider: ConfigProvider | None = None
    access_provider: AccessProvider | None = None
    role_cards_provider: RoleCardsProvider | None = None
    active_role_card_key_provider: ActiveRoleCardKeyProvider | None = None
    memory_stats_provider: StatsProvider | None = None
    manual_memory_stats_provider: StatsProvider | None = None
    gap_scene_stats_provider: StatsProvider | None = None
    rag_document_stats_provider: StatsProvider | None = None

    def missing_required(self) -> list[str]:
        return [
            spec.provider_name
            for spec in OWNER_CONSOLE_READ_PROVIDER_SPECS
            if spec.required and getattr(self, spec.provider_name) is None
        ]


def build_owner_console_provider_wiring_snapshot(
    providers: OwnerConsoleReadProviders,
) -> OwnerConsoleProviderWiringSnapshot:
    missing_required = providers.missing_required()
    return OwnerConsoleProviderWiringSnapshot(
        generated_at=utc_now(),
        runtime_ready=not missing_required,
        missing_required=missing_required,
        rows=[
            OwnerConsoleProviderWiringRow(
                provider_name=spec.provider_name,
                required=spec.required,
                configured=getattr(providers, spec.provider_name) is not None,
                read_model_area=spec.read_model_area,
                owner_console_methods=list(spec.owner_console_methods),
                fallback_behavior=spec.fallback_behavior,
                direct_qq_dependency_allowed=False,
                write_side_effect_allowed=False,
            )
            for spec in OWNER_CONSOLE_READ_PROVIDER_SPECS
        ],
        boundary=OwnerConsoleRuntimeBoundary(),
    )


def create_owner_console_read_runtime(
    providers: OwnerConsoleReadProviders,
) -> OwnerConsoleReadRuntime:
    missing_required = providers.missing_required()
    if missing_required:
        missing_text = ", ".join(missing_required)
        raise ValueError(f"missing owner console read providers: {missing_text}")
    assert providers.config_provider is not None
    assert providers.access_provider is not None
    return OwnerConsoleReadRuntime(
        config_provider=providers.config_provider,
        access_provider=providers.access_provider,
        role_cards_provider=providers.role_cards_provider or _empty_role_cards_provider,
        active_role_card_key_provider=(
            providers.active_role_card_key_provider
            or _empty_active_role_card_key_provider
        ),
        memory_stats_provider=providers.memory_stats_provider or _empty_stats_provider,
        manual_memory_stats_provider=(
            providers.manual_memory_stats_provider or _empty_stats_provider
        ),
        gap_scene_stats_provider=providers.gap_scene_stats_provider
        or _empty_stats_provider,
        rag_document_stats_provider=providers.rag_document_stats_provider
        or _empty_stats_provider,
    )


@dataclass(frozen=True)
class OwnerConsoleReadRuntime:
    config_provider: ConfigProvider
    access_provider: AccessProvider
    role_cards_provider: RoleCardsProvider = _empty_role_cards_provider
    active_role_card_key_provider: ActiveRoleCardKeyProvider = (
        _empty_active_role_card_key_provider
    )
    memory_stats_provider: StatsProvider = _empty_stats_provider
    manual_memory_stats_provider: StatsProvider = _empty_stats_provider
    gap_scene_stats_provider: StatsProvider = _empty_stats_provider
    rag_document_stats_provider: StatsProvider = _empty_stats_provider

    def build_route_contract_snapshot(self) -> OwnerConsoleReadRouteContractSnapshot:
        return build_owner_console_route_contract_snapshot()

    def build_overview(
        self,
        context: OwnerConsoleContext,
        *,
        task_limit: int = 5,
        approval_limit: int = 5,
    ) -> OwnerConsoleOverview:
        return build_owner_console_overview(
            context,
            task_limit=task_limit,
            approval_limit=approval_limit,
        )

    def build_task_list(
        self,
        context: OwnerConsoleContext,
        *,
        status: str | None = None,
        work_type: str | None = None,
        limit: int = 20,
    ) -> OwnerConsoleTaskList:
        return build_owner_console_task_list(
            context,
            status=status,
            work_type=work_type,
            limit=limit,
        )

    def build_task_detail(
        self,
        context: OwnerConsoleContext,
        task_id: int,
        *,
        event_limit: int = 20,
        preview_limit: int = DEFAULT_PREVIEW_LIMIT,
    ) -> OwnerConsoleTaskDetail | None:
        return build_owner_console_task_detail(
            context,
            task_id,
            event_limit=event_limit,
            preview_limit=preview_limit,
        )

    def build_approval_list(
        self,
        context: OwnerConsoleContext,
        *,
        status: str | None = None,
        limit: int = 20,
    ) -> OwnerConsoleApprovalList:
        return build_owner_console_approval_list(
            context,
            status=status,
            limit=limit,
        )

    def build_approval_detail(
        self,
        context: OwnerConsoleContext,
        approval_id: int,
        *,
        event_limit: int = 5,
        preview_limit: int = DEFAULT_PREVIEW_LIMIT,
    ) -> OwnerConsoleApprovalDetail | None:
        return build_owner_console_approval_detail(
            context,
            approval_id,
            event_limit=event_limit,
            preview_limit=preview_limit,
        )

    def build_access_control_snapshot(
        self,
        *,
        item_limit: int = 50,
    ) -> OwnerConsoleAccessControlSnapshot:
        return build_owner_console_access_control_snapshot(
            self.config_provider(),
            self.access_provider(),
            item_limit=item_limit,
        )

    def build_settings_snapshot(self) -> OwnerConsoleSettingsSnapshot:
        return build_owner_console_settings_snapshot(
            self.config_provider(),
            role_cards=self.role_cards_provider(),
            active_role_card_key=self.active_role_card_key_provider(),
        )

    def build_memory_snapshot(self) -> OwnerConsoleMemorySnapshot:
        return build_owner_console_memory_snapshot(
            self.config_provider(),
            memory_stats=self.memory_stats_provider(),
            manual_memory_stats=self.manual_memory_stats_provider(),
            gap_scene_stats=self.gap_scene_stats_provider(),
            rag_document_stats=self.rag_document_stats_provider(),
        )

    def build_external_read_snapshot(
        self,
        context: OwnerConsoleContext,
    ) -> OwnerConsoleExternalReadSnapshot:
        return build_owner_console_external_read_snapshot(
            self.config_provider(),
            context,
        )

    def build_health_snapshot(
        self,
        *,
        bot_status_lines: Any = None,
        diagnostics: Any = None,
        config: Any = None,
        vision: Any = None,
        image_cache: Any = None,
        memory: Any = None,
        tts: Any = None,
        recent_errors: Any = None,
        main_agent_observation_lines: Any = None,
        root_graph_observation_lines: Any = None,
    ) -> OwnerConsoleHealthSnapshot:
        return build_owner_console_health_snapshot(
            bot_status_lines=bot_status_lines,
            diagnostics=diagnostics,
            config=config,
            vision=vision,
            image_cache=image_cache,
            memory=memory,
            tts=tts,
            recent_errors=recent_errors,
            main_agent_observation_lines=main_agent_observation_lines,
            root_graph_observation_lines=root_graph_observation_lines,
        )

    def serialize_model(self, model: Any) -> Any:
        return owner_console_to_jsonable(model)

    def serialize_page(self, page: str, model: Any) -> dict[str, Any]:
        return owner_console_page_response(page, model)


def _safe_limit(value: int) -> int:
    return max(1, value)


def _stat_int(stats: dict[str, Any] | None, key: str) -> int:
    if not stats:
        return 0
    try:
        return int(stats.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _installed_version(distribution: str) -> str:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return "not_installed"


def _version_in_range(
    value: str,
    *,
    minimum: tuple[int, ...],
    maximum: tuple[int, ...],
) -> bool:
    try:
        numeric = tuple(int(part) for part in value.split(".")[:3])
    except ValueError:
        return False
    return minimum <= numeric < maximum


def build_owner_console_external_read_snapshot(
    config: AiChatConfig,
    context: OwnerConsoleContext,
    *,
    httpx_version: str | None = None,
    httpcore_version: str | None = None,
) -> OwnerConsoleExternalReadSnapshot:
    selected_httpx_version = httpx_version or _installed_version("httpx")
    selected_httpcore_version = httpcore_version or _installed_version("httpcore")
    dependencies_compatible = (
        _version_in_range(
            selected_httpx_version,
            minimum=(0, 28, 1),
            maximum=(0, 29, 0),
        )
        and _version_in_range(
            selected_httpcore_version,
            minimum=(1, 0, 9),
            maximum=(1, 1, 0),
        )
    )
    task = latest_external_read_task_snapshot(
        session_key=context.session_key,
        user_id=context.user_id,
        database_path=database_module.DATABASE_PATH,
    )
    recent_task = (
        OwnerConsoleExternalReadTaskSnapshot(available=False)
        if task is None
        else OwnerConsoleExternalReadTaskSnapshot(
            available=True,
            task_id=task.task_id,
            task_status=task.task_status,
            provider_name=task.provider_name,
            result_count=task.result_count,
            source_host_count=task.source_host_count,
            dropped_result_count=task.dropped_result_count,
            external_request_count=task.external_request_count,
            status_category=task.status_category,
            error_category=task.error_category,
            updated_at=task.updated_at,
        )
    )
    credential_configured = bool(config.tavily_api_key)
    return OwnerConsoleExternalReadSnapshot(
        generated_at=utc_now(),
        enabled=config.enable_agent_web,
        credential_configured=credential_configured,
        executor_configured=(
            config.enable_agent_web
            and credential_configured
            and dependencies_compatible
        ),
        provider_name="tavily",
        search_depth="basic",
        max_results=3,
        timeout_seconds=config.tavily_timeout_seconds,
        endpoint_host="api.tavily.com",
        dependencies=OwnerConsoleExternalReadDependencySnapshot(
            httpx_version=selected_httpx_version,
            httpcore_version=selected_httpcore_version,
            compatible=dependencies_compatible,
        ),
        recent_task=recent_task,
        boundary=OwnerConsoleExternalReadBoundary(),
    )


def _visible_items(items: frozenset[str], *, limit: int) -> tuple[list[str], bool]:
    sorted_items = sorted(items)
    safe_limit = _safe_limit(limit)
    return sorted_items[:safe_limit], len(sorted_items) > safe_limit


def _access_list(
    label: str,
    items: frozenset[str],
    *,
    limit: int,
) -> OwnerConsoleAccessList:
    visible, truncated = _visible_items(items, limit=limit)
    return OwnerConsoleAccessList(
        label=label,
        count=len(items),
        items=visible,
        truncated=truncated,
    )


def _lines_from_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return value.splitlines() if value else []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]


def _text_from_lines(lines: list[str]) -> str:
    return "\n".join(lines).strip()


def _snapshot_section(title: str, value: Any = None) -> OwnerConsoleTextSnapshotSection:
    result = getattr(value, "result", None)
    if result is not None:
        error = str(getattr(result, "error", "") or "")
        reply_text = str(getattr(result, "reply_text", "") or "")
        lines = _lines_from_value(reply_text or error)
        return OwnerConsoleTextSnapshotSection(
            title=title,
            ok=not bool(error),
            summary_text=_text_from_lines(lines),
            display_lines=lines,
            error=error,
        )
    lines = _lines_from_value(value)
    return OwnerConsoleTextSnapshotSection(
        title=title,
        ok=True,
        summary_text=_text_from_lines(lines),
        display_lines=lines,
        error="",
    )


def _compact_text(value: str) -> str:
    return " ".join(value.strip().split())


def _preview_text(value: str, *, limit: int = DEFAULT_PREVIEW_LIMIT) -> tuple[str, bool]:
    compact = _compact_text(value)
    if len(compact) <= limit:
        return compact, False
    return compact[: max(0, limit - 3)].rstrip() + "...", True


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)


def _redact_json_value(value: Any) -> tuple[Any, bool]:
    if isinstance(value, dict):
        redacted = False
        result: dict[str, Any] = {}
        for key, item in value.items():
            text_key = str(key)
            if _is_sensitive_key(text_key):
                result[text_key] = "***"
                redacted = True
                continue
            nested, nested_redacted = _redact_json_value(item)
            result[text_key] = nested
            redacted = redacted or nested_redacted
        return result, redacted
    if isinstance(value, list):
        redacted = False
        result: list[Any] = []
        for item in value:
            nested, nested_redacted = _redact_json_value(item)
            result.append(nested)
            redacted = redacted or nested_redacted
        return result, redacted
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return value, False
            nested, nested_redacted = _redact_json_value(parsed)
            return (
                json.dumps(nested, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                nested_redacted,
            )
    return value, False


def build_tool_input_preview(
    value: str,
    *,
    limit: int = DEFAULT_PREVIEW_LIMIT,
) -> OwnerConsoleToolInputPreview:
    stripped = value.strip()
    if not stripped:
        return OwnerConsoleToolInputPreview(
            preview_json="",
            redacted=False,
            truncated=False,
        )
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        preview, truncated = _preview_text(stripped, limit=limit)
        return OwnerConsoleToolInputPreview(
            preview_json=preview,
            redacted=False,
            truncated=truncated,
        )
    redacted_value, redacted = _redact_json_value(parsed)
    rendered = json.dumps(
        redacted_value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    preview, truncated = _preview_text(rendered, limit=limit)
    return OwnerConsoleToolInputPreview(
        preview_json=preview,
        redacted=redacted,
        truncated=truncated,
    )


def build_owner_console_access_control_snapshot(
    config: AiChatConfig,
    access: AccessStore,
    *,
    item_limit: int = 50,
) -> OwnerConsoleAccessControlSnapshot:
    return OwnerConsoleAccessControlSnapshot(
        generated_at=utc_now(),
        owner_configured=bool(config.bot_owner_qq),
        private_chat_enabled=config.enable_private_chat,
        group_chat_enabled=config.enable_group_chat,
        unknown_private_policy=(
            "allow_trial" if config.allow_unknown_private_chat else "deny"
        ),
        private_whitelist=_access_list(
            "private_whitelist",
            access.private_whitelist,
            limit=item_limit,
        ),
        group_whitelist=_access_list(
            "group_whitelist",
            access.group_whitelist,
            limit=item_limit,
        ),
        user_blacklist=_access_list(
            "user_blacklist",
            access.user_blacklist,
            limit=item_limit,
        ),
        boundary=OwnerConsoleRuntimeBoundary(),
    )


def _model_snapshot(
    *,
    model_name: str,
    base_url: str,
    api_key: str,
    timeout_seconds: int,
) -> OwnerConsoleModelConfigSnapshot:
    return OwnerConsoleModelConfigSnapshot(
        model_name=model_name or "未配置",
        base_url_redacted=redacted_base_url(base_url),
        api_key_configured=bool(api_key),
        timeout_seconds=timeout_seconds,
    )


def build_owner_console_settings_snapshot(
    config: AiChatConfig,
    *,
    role_cards: list[Any] | None = None,
    active_role_card_key: str = "",
) -> OwnerConsoleSettingsSnapshot:
    cards = role_cards or []
    active_key = active_role_card_key.strip()
    return OwnerConsoleSettingsSnapshot(
        generated_at=utc_now(),
        chat_model=_model_snapshot(
            model_name=config.chat_llm_model or config.openai_model,
            base_url=config.chat_llm_base_url or config.openai_base_url,
            api_key=config.chat_llm_api_key or config.openai_api_key,
            timeout_seconds=config.chat_llm_timeout_seconds,
        ),
        main_agent_model=_model_snapshot(
            model_name=config.main_llm_model,
            base_url=config.main_llm_base_url,
            api_key=config.main_llm_api_key,
            timeout_seconds=config.main_llm_timeout_seconds,
        ),
        embedding=_model_snapshot(
            model_name=config.memory_rag_embedding_model,
            base_url=config.memory_rag_embedding_base_url,
            api_key="",
            timeout_seconds=config.memory_rag_embedding_timeout_seconds,
        ),
        role_cards=[
            OwnerConsoleRoleCardRow(
                key=str(getattr(card, "key", "") or ""),
                title=str(getattr(card, "title", "") or ""),
                active=bool(active_key and str(getattr(card, "key", "") or "") == active_key),
            )
            for card in cards
        ],
        active_role_card_key=active_key,
        feature_flags={
            "enable_main_agent": config.enable_main_agent,
            "main_agent_use_llm": config.main_agent_use_llm,
            "main_agent_owner_only": config.main_agent_owner_only,
            "main_agent_allow_group": config.main_agent_allow_group,
            "enable_chat_graph_runtime": config.enable_chat_graph_runtime,
            "enable_vision": config.enable_vision,
            "enable_memory_rag": config.enable_memory_rag,
            "enable_project_doc_rag": config.enable_project_doc_rag,
            "memory_rag_inject_in_chat": config.memory_rag_inject_in_chat,
            "enable_tts": config.enable_tts,
            "enable_agent_web": config.enable_agent_web,
            "enable_agent_shell": config.enable_agent_shell,
            "enable_agent_local_write": config.enable_agent_local_write,
            "enable_agent_external_write": config.enable_agent_external_write,
        },
        boundary=OwnerConsoleRuntimeBoundary(),
    )


def build_owner_console_memory_snapshot(
    config: AiChatConfig,
    *,
    memory_stats: dict[str, Any] | None = None,
    manual_memory_stats: dict[str, Any] | None = None,
    gap_scene_stats: dict[str, Any] | None = None,
    rag_document_stats: dict[str, Any] | None = None,
) -> OwnerConsoleMemorySnapshot:
    return OwnerConsoleMemorySnapshot(
        generated_at=utc_now(),
        counts=OwnerConsoleMemoryCounts(
            message_count=_stat_int(memory_stats, "message_count"),
            session_count=_stat_int(memory_stats, "session_count"),
            session_summary_count=_stat_int(memory_stats, "summary_count"),
            summarized_message_count=_stat_int(memory_stats, "summarized_message_count"),
            manual_memory_count=_stat_int(manual_memory_stats, "memory_count"),
            manual_memory_subject_count=_stat_int(manual_memory_stats, "subject_count"),
            gap_scene_summary_count=_stat_int(gap_scene_stats, "summary_count"),
            gap_scene_source_message_count=_stat_int(
                gap_scene_stats,
                "source_message_count",
            ),
            rag_document_count=_stat_int(rag_document_stats, "document_count"),
            rag_active_document_count=_stat_int(
                rag_document_stats,
                "active_document_count",
            ),
            rag_embedding_count=_stat_int(rag_document_stats, "embedding_count"),
        ),
        context_policy=OwnerConsoleMemoryContextPolicy(
            memory_compression_enabled=config.enable_memory_compression,
            gap_scene_summaries_enabled=config.enable_gap_scene_summaries,
            long_term_memory_context_enabled=config.enable_long_term_memory_context,
            max_context_messages=config.max_context_messages,
            max_stored_messages_per_session=config.max_stored_messages_per_session,
            summary_keep_recent_messages=config.summary_keep_recent_messages,
            summary_batch_messages=config.summary_batch_messages,
            summary_min_source_messages=config.summary_min_source_messages,
            max_session_summaries_in_context=config.max_session_summaries_in_context,
            max_gap_scene_summaries_in_context=config.max_gap_scene_summaries_in_context,
            max_long_term_memories_in_context=config.max_long_term_memories_in_context,
        ),
        memory_rag=OwnerConsoleMemoryRagSnapshot(
            enabled=config.enable_memory_rag,
            inject_in_chat=config.memory_rag_inject_in_chat,
            owner_only_debug=config.memory_rag_owner_only_debug,
            top_k=config.memory_rag_top_k,
            min_score=config.memory_rag_min_score,
            max_context_chars=config.memory_rag_max_context_chars,
            include_manual_facts=config.memory_rag_include_manual_facts,
            include_manual_preferences=config.memory_rag_include_manual_preferences,
            include_session_summaries=config.memory_rag_include_session_summaries,
            include_short_messages=config.memory_rag_include_short_messages,
            include_gap_scene_summaries=config.memory_rag_include_gap_scene_summaries,
        ),
        project_doc_rag=OwnerConsoleProjectDocRagSnapshot(
            enabled=config.enable_project_doc_rag,
            explicit_agent_dev_context_only=True,
            ordinary_chat_injection_allowed=False,
            top_k=config.project_doc_rag_top_k,
            min_score=config.project_doc_rag_min_score,
            max_context_chars=config.project_doc_rag_max_context_chars,
        ),
        memory_content_exposed=False,
        project_doc_content_exposed=False,
        retrieval_executed=False,
        index_rebuild_executed=False,
        boundary=OwnerConsoleRuntimeBoundary(),
    )


def build_owner_console_health_snapshot(
    *,
    bot_status_lines: Any = None,
    diagnostics: Any = None,
    config: Any = None,
    vision: Any = None,
    image_cache: Any = None,
    memory: Any = None,
    tts: Any = None,
    recent_errors: Any = None,
    main_agent_observation_lines: Any = None,
    root_graph_observation_lines: Any = None,
) -> OwnerConsoleHealthSnapshot:
    return OwnerConsoleHealthSnapshot(
        generated_at=utc_now(),
        bot_status=_snapshot_section("bot_status", bot_status_lines),
        diagnostics=_snapshot_section("diagnostics", diagnostics),
        config=_snapshot_section("config", config),
        vision=_snapshot_section("vision", vision),
        image_cache=_snapshot_section("image_cache", image_cache),
        memory=_snapshot_section("memory", memory),
        tts=_snapshot_section("tts", tts),
        recent_errors=_snapshot_section("recent_errors", recent_errors),
        observations=OwnerConsoleObservationSnapshot(
            main_agent=_lines_from_value(main_agent_observation_lines),
            root_graph=_lines_from_value(root_graph_observation_lines),
        ),
        boundary=OwnerConsoleRuntimeBoundary(),
    )


def _actionability_for_approval(
    approval: AgentApproval,
) -> OwnerConsoleApprovalActionability:
    if approval.status == AGENT_APPROVAL_PENDING:
        return OwnerConsoleApprovalActionability(
            can_approve=True,
            can_reject=True,
            resume_enabled=None,
            blocked_reason="",
            future_operation_only=True,
        )
    return OwnerConsoleApprovalActionability(
        can_approve=False,
        can_reject=False,
        resume_enabled=None,
        blocked_reason="approval is not pending",
        future_operation_only=True,
    )


def _event_summary(event: AgentTaskEvent | None) -> tuple[str, str]:
    if event is None:
        return "", ""
    summary = event.error or event.output_summary or event.kind
    preview, _ = _preview_text(summary, limit=120)
    return event.kind, preview


def _next_action_for_task(task: AgentTask, approvals: list[AgentApproval]) -> str:
    if any(approval.status == AGENT_APPROVAL_PENDING for approval in approvals):
        return "review_pending_approval"
    if task.status == AGENT_TASK_FAILED:
        return "inspect_failure"
    if task.status == AGENT_TASK_PENDING:
        return "review_task_goal"
    if task.status == AGENT_TASK_RUNNING:
        return "monitor_running_task"
    if task.status == AGENT_TASK_DONE:
        return "completed"
    if task.status == AGENT_TASK_CANCELLED:
        return "cancelled"
    return "review_status"


def _task_event_row(
    event: AgentTaskEvent,
    *,
    preview_limit: int = DEFAULT_PREVIEW_LIMIT,
) -> OwnerConsoleTaskEventRow:
    input_preview = build_tool_input_preview(
        event.input_json,
        limit=preview_limit,
    ).preview_json
    output_summary, _ = _preview_text(event.output_summary, limit=preview_limit)
    error, _ = _preview_text(event.error, limit=preview_limit)
    return OwnerConsoleTaskEventRow(
        event_id=event.id,
        task_id=event.task_id,
        step_index=event.step_index,
        kind=event.kind,
        tool_name=event.tool_name,
        input_preview=input_preview,
        output_summary=output_summary,
        status=event.status,
        status_label=agent_task_status_label(event.status),
        error=error,
        created_at=event.created_at,
    )


def _approval_row(
    approval: AgentApproval,
    *,
    reason_limit: int = DEFAULT_PREVIEW_LIMIT,
) -> OwnerConsoleApprovalRow:
    reason_preview, _ = _preview_text(approval.reason, limit=reason_limit)
    return OwnerConsoleApprovalRow(
        approval_id=approval.id,
        task_id=approval.task_id,
        task_title=approval.task_title,
        tool_name=approval.tool_name,
        risk_level=approval.risk_level,
        reason_preview=reason_preview,
        status=approval.status,
        status_label=agent_approval_status_label(approval.status),
        created_at=approval.created_at,
        expires_at=approval.expires_at,
        decided_at=approval.decided_at,
        actionability=_actionability_for_approval(approval),
    )


def _task_row(
    task: AgentTask,
    *,
    approvals: list[AgentApproval] | None = None,
    preview_limit: int = DEFAULT_PREVIEW_LIMIT,
) -> OwnerConsoleTaskRow:
    related_approvals = approvals or []
    pending_approval_ids = [
        approval.id
        for approval in related_approvals
        if approval.status == AGENT_APPROVAL_PENDING
    ]
    event_kind, event_summary = _event_summary(latest_agent_task_event(task.id))
    goal_preview, _ = _preview_text(task.goal, limit=preview_limit)
    result_preview, _ = _preview_text(task.result, limit=preview_limit)
    candidate_work_type = agent_task_work_type(task.id)
    safe_work_type = (
        candidate_work_type
        if candidate_work_type in OWNER_CONSOLE_WORK_TYPES
        else ""
    )
    return OwnerConsoleTaskRow(
        task_id=task.id,
        title=task.title,
        goal_preview=goal_preview,
        status=task.status,
        status_label=agent_task_status_label(task.status),
        result_preview=result_preview,
        created_at=task.created_at,
        updated_at=task.updated_at,
        latest_event_kind=event_kind,
        latest_event_summary=event_summary,
        pending_approval_ids=pending_approval_ids,
        next_action=_next_action_for_task(task, related_approvals),
        work_type=safe_work_type,
    )


def build_owner_console_task_list(
    context: OwnerConsoleContext,
    *,
    status: str | None = None,
    work_type: str | None = None,
    limit: int = 20,
) -> OwnerConsoleTaskList:
    if work_type is not None and work_type not in OWNER_CONSOLE_WORK_TYPES:
        raise ValueError("unsupported owner console work type")
    tasks = list_agent_tasks(
        session_key=context.session_key,
        user_id=context.user_id,
        status=status,
        work_type=work_type,
        limit=limit,
    )
    rows: list[OwnerConsoleTaskRow] = []
    for task in tasks:
        approvals = list_agent_approvals(
            session_key=context.session_key,
            user_id=context.user_id,
            task_id=task.id,
            status=AGENT_APPROVAL_PENDING,
            limit=20,
        )
        rows.append(_task_row(task, approvals=approvals))
    return OwnerConsoleTaskList(
        generated_at=utc_now(),
        status_filter=status,
        work_type_filter=work_type,
        limit=_safe_limit(limit),
        total_visible=len(rows),
        rows=rows,
        boundary=OwnerConsoleRuntimeBoundary(),
    )


def build_owner_console_task_detail(
    context: OwnerConsoleContext,
    task_id: int,
    *,
    event_limit: int = 20,
    preview_limit: int = DEFAULT_PREVIEW_LIMIT,
) -> OwnerConsoleTaskDetail | None:
    task = get_agent_task(
        task_id,
        session_key=context.session_key,
        user_id=context.user_id,
    )
    if task is None:
        return None
    events = list_agent_task_events(task.id, limit=event_limit)
    approvals = list_agent_approvals(
        session_key=context.session_key,
        user_id=context.user_id,
        task_id=task.id,
        limit=20,
    )
    task_row = _task_row(task, approvals=approvals, preview_limit=preview_limit)
    return OwnerConsoleTaskDetail(
        generated_at=utc_now(),
        task=task_row,
        goal=task.goal,
        result=task.result,
        events=[
            _task_event_row(event, preview_limit=preview_limit)
            for event in events
        ],
        approvals=[
            _approval_row(approval, reason_limit=preview_limit)
            for approval in approvals
        ],
        next_action=task_row.next_action,
        boundary=OwnerConsoleRuntimeBoundary(),
    )


def build_owner_console_approval_list(
    context: OwnerConsoleContext,
    *,
    status: str | None = None,
    limit: int = 20,
) -> OwnerConsoleApprovalList:
    approvals = list_agent_approvals(
        session_key=context.session_key,
        user_id=context.user_id,
        status=status,
        limit=limit,
    )
    rows = [_approval_row(approval) for approval in approvals]
    return OwnerConsoleApprovalList(
        generated_at=utc_now(),
        status_filter=status,
        limit=_safe_limit(limit),
        total_visible=len(rows),
        rows=rows,
        boundary=OwnerConsoleRuntimeBoundary(),
    )


def build_owner_console_overview(
    context: OwnerConsoleContext,
    *,
    task_limit: int = 5,
    approval_limit: int = 5,
) -> OwnerConsoleOverview:
    safe_task_limit = _safe_limit(task_limit)
    safe_approval_limit = _safe_limit(approval_limit)
    recent_tasks = list_agent_tasks(
        session_key=context.session_key,
        user_id=context.user_id,
        limit=safe_task_limit,
    )
    pending_approvals = list_agent_approvals(
        session_key=context.session_key,
        user_id=context.user_id,
        status=AGENT_APPROVAL_PENDING,
        limit=safe_approval_limit,
    )
    recent_task_rows: list[OwnerConsoleTaskRow] = []
    for task in recent_tasks:
        task_pending_approvals = list_agent_approvals(
            session_key=context.session_key,
            user_id=context.user_id,
            task_id=task.id,
            status=AGENT_APPROVAL_PENDING,
            limit=20,
        )
        recent_task_rows.append(_task_row(task, approvals=task_pending_approvals))
    approval_rows = [_approval_row(approval) for approval in pending_approvals]
    return OwnerConsoleOverview(
        generated_at=utc_now(),
        task_limit=safe_task_limit,
        approval_limit=safe_approval_limit,
        counters=OwnerConsoleOverviewCounters(
            pending_tasks=count_agent_tasks(
                session_key=context.session_key,
                user_id=context.user_id,
                status=AGENT_TASK_PENDING,
            ),
            failed_tasks=count_agent_tasks(
                session_key=context.session_key,
                user_id=context.user_id,
                status=AGENT_TASK_FAILED,
            ),
            pending_approvals=count_agent_approvals(
                session_key=context.session_key,
                user_id=context.user_id,
                status=AGENT_APPROVAL_PENDING,
            ),
            recent_tasks_visible=len(recent_task_rows),
            pending_approvals_visible=len(approval_rows),
        ),
        recent_tasks=recent_task_rows,
        pending_approvals=approval_rows,
        boundary=OwnerConsoleRuntimeBoundary(),
    )


def build_owner_console_approval_detail(
    context: OwnerConsoleContext,
    approval_id: int,
    *,
    event_limit: int = 5,
    preview_limit: int = DEFAULT_PREVIEW_LIMIT,
) -> OwnerConsoleApprovalDetail | None:
    approval = get_agent_approval(
        approval_id,
        session_key=context.session_key,
        user_id=context.user_id,
    )
    if approval is None:
        return None
    task = get_agent_task(
        approval.task_id,
        session_key=context.session_key,
        user_id=context.user_id,
    )
    approvals = [approval]
    task_row = (
        _task_row(task, approvals=approvals, preview_limit=preview_limit)
        if task is not None
        else None
    )
    events = list_agent_task_events(approval.task_id, limit=event_limit)
    return OwnerConsoleApprovalDetail(
        generated_at=utc_now(),
        approval=_approval_row(approval, reason_limit=preview_limit),
        reason=approval.reason,
        tool_input=build_tool_input_preview(
            approval.tool_input_json,
            limit=preview_limit,
        ),
        task=task_row,
        recent_events=[
            _task_event_row(event, preview_limit=preview_limit)
            for event in events
        ],
        boundary=OwnerConsoleRuntimeBoundary(),
    )
