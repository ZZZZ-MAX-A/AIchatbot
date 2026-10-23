from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
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
from .completion_routes import resolve_chat_completion_route
from .persona_maintenance import build_persona_binding_report
from .account_persona_settings import build_account_persona_profiles
from .memory_maintenance import (
    resolve_memory_maintenance_scope, memory_maintenance_database_scope, read_memory_maintenance_counts,
)
from .database import utc_now
from . import database as database_module
from .external_read_status import latest_external_read_task_snapshot
from .main_agent_observability import redacted_base_url
from .owner_console_read_models import (
    OWNER_CONSOLE_SCHEMA_VERSION,
    OwnerConsoleAccessControlSnapshot,
    OwnerConsoleAccessList,
    OwnerConsoleAccessListItem,
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
    OwnerConsoleReliabilityBoundary,
    OwnerConsoleReliabilityCoverageRow,
    OwnerConsoleReliabilitySnapshot,
    OwnerConsoleReliabilityStateCounts,
    OwnerConsoleReliabilityTrendItem,
    OwnerConsoleReliabilityWindow,
    OwnerConsoleReadRouteContractSnapshot,
    OwnerConsoleReadRouteRow,
    OwnerConsoleRoleCardRow,
    OwnerConsoleRuntimeBoundary,
    OwnerConsoleSettingsSnapshot,
    OwnerConsoleTaskDetail,
    OwnerConsoleTaskActionability,
    OwnerConsoleTaskEventRow,
    OwnerConsoleTaskList,
    OwnerConsoleTaskRow,
    OwnerConsoleTextSnapshotSection,
    OwnerConsoleToolInputPreview,
    owner_console_page_response,
    owner_console_to_jsonable,
)
from .failure_diagnostics import CATEGORY_LABELS
from .reliability_events import (
    RECOVERY_STATE_LABELS,
    ReliabilityRecoveryState,
    ReliabilityTrendSummary,
    read_reliability_trend,
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
        optional_params=(
            "status",
            "work_type",
            "category",
            "page",
            "page_size",
            "limit",
        ),
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
        page="reliability",
        response_page="reliability",
        runtime_method="build_reliability_snapshot",
        read_model="OwnerConsoleReliabilitySnapshot",
        requires_context=False,
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
        optional_params=("bot_self_id", "scope_revision"),
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
OWNER_CONSOLE_STALE_PENDING_SECONDS = 24 * 60 * 60
OWNER_CONSOLE_TASK_PAGE_SIZE_DEFAULT = 20
OWNER_CONSOLE_TASK_PAGE_SIZE_MAX = 100
OWNER_CONSOLE_TASK_SCAN_BATCH_SIZE = 200
OWNER_CONSOLE_TASK_CATEGORIES = frozenset(
    {
        "awaiting_approval",
        "ordinary_pending",
        "stale_residual",
        "running",
        "failed",
        "closed",
    }
)
_SETTLED_PENDING_EVENT_KINDS = frozenset(
    {
        "approval_rejected",
        "approval_approved",
        "tool_resume_finished",
        "tool_resume_failed",
    }
)
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
ReliabilityTrendProvider: TypeAlias = Callable[..., ReliabilityTrendSummary]


OWNER_CONSOLE_RELIABILITY_COVERAGE = (
    ("bot_runtime", "lifecycle"),
    ("main_llm", "plan_action"),
    ("sticker_classifier", "classify_intent"),
    ("document_delivery", "send_document"),
    ("project_doc_rag", "rebuild_index"),
    ("vision", "infer"),
    ("tts", "synthesize"),
)

RELIABILITY_COMPONENT_LABELS = {
    "bot_runtime": "Bot 运行状态",
    "main_llm": "MainAgent 规划模型",
    "sticker_classifier": "表情意图分类",
    "document_delivery": "文档交付",
    "project_doc_rag": "项目文档索引",
    "vision": "图片理解",
    "tts": "语音合成",
}

RELIABILITY_OPERATION_LABELS = {
    "lifecycle": "进程启动与停止",
    "plan_action": "生成行动计划",
    "classify_intent": "判断表情意图",
    "send_document": "发送新文档",
    "rebuild_index": "重建项目文档索引",
    "infer": "识别图片内容",
    "synthesize": "生成语音",
}

RELIABILITY_CODE_LABELS = {
    "request_timeout": "请求在限定时间内没有完成",
    "connection_failed": "服务连接或传输失败",
    "model_rate_limited": "模型服务拒绝或限制了当前请求",
    "model_not_found": "配置的模型当前不可用",
    "invalid_model_response": "模型响应未通过格式或质量校验",
    "authorization_failed": "鉴权或权限检查未通过",
    "invalid_configuration": "功能配置不完整或不合法",
    "data_validation_failed": "输入或产物未通过数据校验",
    "presentation_slide_limit_exceeded": "演示文稿页数超过安全上限",
    "artifact_integrity_failed": "文档产物完整性复核失败",
    "document_delivery_failed": "文档交付没有完成",
    "approval_context_invalid": "审批上下文与当前任务不一致",
    "required_arguments_unavailable": "执行所需参数不完整",
    "unexpected_runtime_state": "运行状态不在已知安全范围内",
    "suspected_abnormal_exit": "上次运行没有发现正常停止记录",
}


def _reliability_label(labels: dict[str, str], value: str) -> str:
    return labels.get(value, "未收录中文解读")


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
    OwnerConsoleReadProviderSpec(
        provider_name="reliability_trend_provider",
        required=False,
        read_model_area="reliability",
        owner_console_methods=("build_reliability_snapshot",),
        fallback_behavior="P2.47 SQLite mode=ro trend reader",
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
    reliability_trend_provider: ReliabilityTrendProvider | None = None

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
        reliability_trend_provider=(
            providers.reliability_trend_provider or read_reliability_trend
        ),
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
    reliability_trend_provider: ReliabilityTrendProvider = read_reliability_trend
    approval_actionability_provider: Callable[
        [AgentApproval], OwnerConsoleApprovalActionability
    ] | None = None
    task_actions_enabled: bool = False
    access_actions_enabled: bool = False
    dynamic_access_provider: AccessProvider | None = None
    memory_counts_provider: Callable[[], dict[str, dict[str, int]]] | None = None

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
            actionability_provider=self.approval_actionability_provider,
            task_actions_enabled=self.task_actions_enabled,
        )

    def build_task_list(
        self,
        context: OwnerConsoleContext,
        *,
        status: str | None = None,
        work_type: str | None = None,
        category: str | None = None,
        limit: int = 20,
        page: int = 1,
        page_size: int | None = None,
    ) -> OwnerConsoleTaskList:
        return build_owner_console_task_list(
            context,
            status=status,
            work_type=work_type,
            category=category,
            limit=limit,
            page=page,
            page_size=page_size,
            task_actions_enabled=self.task_actions_enabled,
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
            actionability_provider=self.approval_actionability_provider,
            task_actions_enabled=self.task_actions_enabled,
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
            actionability_provider=self.approval_actionability_provider,
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
            actionability_provider=self.approval_actionability_provider,
        )

    def build_access_control_snapshot(
        self,
        *,
        item_limit: int = 50,
    ) -> OwnerConsoleAccessControlSnapshot:
        config = self.config_provider()
        access = self.access_provider()
        dynamic_access = (
            self.dynamic_access_provider()
            if self.dynamic_access_provider is not None
            else AccessStore(
                private_whitelist=access.private_whitelist - config.private_whitelist,
                group_whitelist=access.group_whitelist - config.group_whitelist,
                user_blacklist=access.user_blacklist - config.user_blacklist,
                revision=access.revision,
            )
        )
        return build_owner_console_access_control_snapshot(
            config,
            access,
            dynamic_access=dynamic_access,
            item_limit=item_limit,
            access_actions_enabled=self.access_actions_enabled,
        )

    def build_settings_snapshot(self) -> OwnerConsoleSettingsSnapshot:
        return build_owner_console_settings_snapshot(
            self.config_provider(),
            role_cards=self.role_cards_provider(),
            active_role_card_key=self.active_role_card_key_provider(),
        )

    def read_account_voice_sample(self, bot_self_id: str) -> bytes:
        from .account_persona_settings import read_account_voice_sample
        return read_account_voice_sample(self.config_provider(), bot_self_id)

    def build_account_memory_snapshot(self, bot_self_id: str | None = None,
                                      revision: str | None = None) -> OwnerConsoleMemorySnapshot:
        from dataclasses import replace
        config = self.config_provider()
        target = resolve_memory_maintenance_scope(config, bot_self_id, revision)
        with memory_maintenance_database_scope(config, target):
            snapshot = build_owner_console_memory_snapshot(config, **read_memory_maintenance_counts())
        return replace(snapshot, memory_scope=target.as_dict())

    def build_memory_snapshot(self, *, bot_self_id: str | None = None,
                              scope_revision: str | None = None) -> OwnerConsoleMemorySnapshot:
        if bot_self_id is not None or scope_revision is not None:
            return self.build_account_memory_snapshot(bot_self_id, scope_revision)
        if self.memory_counts_provider is not None:
            return build_owner_console_memory_snapshot(self.config_provider(), **self.memory_counts_provider())
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

    def build_reliability_snapshot(self) -> OwnerConsoleReliabilitySnapshot:
        return build_owner_console_reliability_snapshot(
            trend_provider=self.reliability_trend_provider,
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


def _owner_console_reliability_state_counts(
    summary: ReliabilityTrendSummary,
) -> OwnerConsoleReliabilityStateCounts:
    counts = {
        state: sum(1 for item in summary.items if item.recovery_state == state)
        for state in ReliabilityRecoveryState
    }
    return OwnerConsoleReliabilityStateCounts(
        unresolved=counts[ReliabilityRecoveryState.UNRESOLVED],
        recovered=counts[ReliabilityRecoveryState.RECOVERED],
        recurring=counts[ReliabilityRecoveryState.RECURRING],
        insufficient_evidence=counts[
            ReliabilityRecoveryState.INSUFFICIENT_EVIDENCE
        ],
    )


def _owner_console_reliability_window(
    summary: ReliabilityTrendSummary,
) -> OwnerConsoleReliabilityWindow:
    rows = []
    for item in summary.items:
        last_success_at = ""
        if (
            item.last_success_at is not None
            and item.recovery_state
            != ReliabilityRecoveryState.INSUFFICIENT_EVIDENCE
        ):
            last_success_at = item.last_success_at.isoformat()
        rows.append(
            OwnerConsoleReliabilityTrendItem(
                component=item.component,
                component_label=_reliability_label(
                    RELIABILITY_COMPONENT_LABELS,
                    item.component,
                ),
                operation=item.operation,
                operation_label=_reliability_label(
                    RELIABILITY_OPERATION_LABELS,
                    item.operation,
                ),
                category=item.category.value,
                category_label=CATEGORY_LABELS[item.category],
                code=item.code,
                code_label=_reliability_label(RELIABILITY_CODE_LABELS, item.code),
                occurrence_count=item.occurrence_count,
                first_seen_at=item.first_seen_at.isoformat(),
                last_seen_at=item.last_seen_at.isoformat(),
                last_success_at=last_success_at,
                recovery_state=item.recovery_state.value,
                recovery_state_label=RECOVERY_STATE_LABELS[item.recovery_state],
            )
        )
    return OwnerConsoleReliabilityWindow(
        window_hours=summary.window_hours,
        failure_occurrence_count=summary.failure_occurrence_count,
        failure_group_count=len(summary.items),
        state_counts=_owner_console_reliability_state_counts(summary),
        items=rows,
    )


def build_owner_console_reliability_snapshot(
    *,
    trend_provider: ReliabilityTrendProvider = read_reliability_trend,
    now: datetime | None = None,
) -> OwnerConsoleReliabilitySnapshot:
    generated_at = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    recent = trend_provider(window_hours=24, now=generated_at)
    weekly = trend_provider(window_hours=24 * 7, now=generated_at)
    return OwnerConsoleReliabilitySnapshot(
        generated_at=generated_at.isoformat(),
        recent=_owner_console_reliability_window(recent),
        weekly=_owner_console_reliability_window(weekly),
        coverage=[
            OwnerConsoleReliabilityCoverageRow(
                component=component,
                component_label=_reliability_label(
                    RELIABILITY_COMPONENT_LABELS,
                    component,
                ),
                operation=operation,
                operation_label=_reliability_label(
                    RELIABILITY_OPERATION_LABELS,
                    operation,
                ),
            )
            for component, operation in OWNER_CONSOLE_RELIABILITY_COVERAGE
        ],
        scope_note=(
            "只统计已接入 P2.47 的固定结构化失败/降级事件；"
            "不读取聊天正文或原始异常。"
        ),
        evidence_note=(
            "没有结构化故障不等于已证明系统持续在线；"
            "未接入组件仍需结合可靠性巡检和最近错误查看。"
        ),
        boundary=OwnerConsoleReliabilityBoundary(),
    )


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
            provider_candidate_count=task.provider_candidate_count,
            official_content_strong_count=task.official_content_strong_count,
            failed_search_stage=task.failed_search_stage,
            search_stage_count=task.search_stage_count,
            official_stage_candidate_count=task.official_stage_candidate_count,
            official_stage_result_count=task.official_stage_result_count,
            media_stage_candidate_count=task.media_stage_candidate_count,
            media_stage_result_count=task.media_stage_result_count,
            planning_mode=task.planning_mode,
            scene=task.scene,
            primary_source_scope=task.primary_source_scope,
            secondary_source_scope=task.secondary_source_scope,
            secondary_mode=task.secondary_mode,
            dropped_missing_date_count=task.dropped_missing_date_count,
            dropped_outside_window_count=task.dropped_outside_window_count,
            dropped_weak_only_count=task.dropped_weak_only_count,
            dropped_conflicting_date_count=task.dropped_conflicting_date_count,
            dropped_injection_count=task.dropped_injection_count,
            dropped_sanitization_count=task.dropped_sanitization_count,
            dropped_source_policy_count=task.dropped_source_policy_count,
            external_request_count=task.external_request_count,
            provider_request_count=task.provider_request_count,
            synthesis_request_count=task.synthesis_request_count,
            synthesis_status=task.synthesis_status,
            synthesis_error_category=task.synthesis_error_category,
            owner_quality_status=task.owner_quality_status,
            status_category=task.status_category,
            error_category=task.error_category,
            updated_at=task.updated_at,
        )
    )
    credential_configured = bool(config.tavily_api_key)
    executor_configured = (
        config.enable_agent_web
        and credential_configured
        and dependencies_compatible
    )
    synthesis_configured = (
        config.main_agent_use_llm and bool(config.main_llm_api_key)
    )
    explicit_agent_trigger_enabled = (
        executor_configured
        and synthesis_configured
        and config.enable_main_agent
    )
    return OwnerConsoleExternalReadSnapshot(
        generated_at=utc_now(),
        enabled=config.enable_agent_web,
        credential_configured=credential_configured,
        executor_configured=executor_configured,
        synthesis_configured=synthesis_configured,
        provider_name="tavily",
        search_depth="planned_basic_or_advanced",
        max_results=10,
        timeout_seconds=config.tavily_timeout_seconds,
        endpoint_host="api.tavily.com",
        dependencies=OwnerConsoleExternalReadDependencySnapshot(
            httpx_version=selected_httpx_version,
            httpcore_version=selected_httpcore_version,
            compatible=dependencies_compatible,
        ),
        recent_task=recent_task,
        boundary=OwnerConsoleExternalReadBoundary(
            owner_private_strict_command_only=True,
            main_llm_can_trigger=explicit_agent_trigger_enabled,
            ordinary_chat_can_trigger=False,
        ),
    )


def _visible_items(items: frozenset[str], *, limit: int) -> tuple[list[str], bool]:
    sorted_items = sorted(items)
    safe_limit = _safe_limit(limit)
    return sorted_items[:safe_limit], len(sorted_items) > safe_limit


def _access_list(
    label: str,
    effective_items: frozenset[str],
    environment_items: frozenset[str],
    dynamic_items: frozenset[str],
    *,
    limit: int,
) -> OwnerConsoleAccessList:
    visible, truncated = _visible_items(effective_items, limit=limit)
    return OwnerConsoleAccessList(
        label=label,
        count=len(effective_items),
        items=[
            OwnerConsoleAccessListItem(
                value=item,
                source=(
                    "environment_and_dynamic"
                    if item in environment_items and item in dynamic_items
                    else "environment"
                    if item in environment_items
                    else "dynamic"
                ),
                editable=item in dynamic_items,
            )
            for item in visible
        ],
        truncated=truncated,
        environment_count=len(environment_items),
        dynamic_count=len(dynamic_items),
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
    dynamic_access: AccessStore | None = None,
    item_limit: int = 50,
    access_actions_enabled: bool = False,
) -> OwnerConsoleAccessControlSnapshot:
    dynamic = dynamic_access or AccessStore(
        private_whitelist=access.private_whitelist - config.private_whitelist,
        group_whitelist=access.group_whitelist - config.group_whitelist,
        user_blacklist=access.user_blacklist - config.user_blacklist,
        revision=access.revision,
    )
    return OwnerConsoleAccessControlSnapshot(
        generated_at=utc_now(),
        revision=dynamic.revision,
        access_actions_enabled=access_actions_enabled,
        owner_configured=bool(config.bot_owner_qq),
        private_chat_enabled=config.enable_private_chat,
        group_chat_enabled=config.enable_group_chat,
        unknown_private_policy=(
            "allow_trial" if config.allow_unknown_private_chat else "deny"
        ),
        private_whitelist=_access_list(
            "private_whitelist",
            access.private_whitelist,
            config.private_whitelist,
            dynamic.private_whitelist,
            limit=item_limit,
        ),
        group_whitelist=_access_list(
            "group_whitelist",
            access.group_whitelist,
            config.group_whitelist,
            dynamic.group_whitelist,
            limit=item_limit,
        ),
        user_blacklist=_access_list(
            "user_blacklist",
            access.user_blacklist,
            config.user_blacklist,
            dynamic.user_blacklist,
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
    settings = getattr(config, "persona_routing", None)
    active_key = getattr(settings, "legacy_role_card_key", "")
    # This global snapshot has no QQ event/persona scope. It describes the
    # default route; active_role_card_key is a card-selection indicator only.
    chat_route = resolve_chat_completion_route(config)
    return OwnerConsoleSettingsSnapshot(
        generated_at=utc_now(),
        chat_model=_model_snapshot(
            model_name=chat_route.model,
            base_url=chat_route.base_url,
            api_key=chat_route.api_key,
            timeout_seconds=chat_route.timeout_seconds,
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
        persona_bindings=build_persona_binding_report(config),
        account_personas=build_account_persona_profiles(config),
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


def _task_is_stale(task: AgentTask, *, now: datetime | None = None) -> bool:
    try:
        updated_at = datetime.fromisoformat(task.updated_at)
    except (TypeError, ValueError):
        return True
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    current = now or datetime.now(UTC)
    return (current - updated_at.astimezone(UTC)).total_seconds() >= (
        OWNER_CONSOLE_STALE_PENDING_SECONDS
    )


def _task_processing(
    task: AgentTask,
    approvals: list[AgentApproval],
    *,
    latest_event_kind: str,
) -> tuple[str, str, str]:
    pending_ids = [
        approval.id
        for approval in approvals
        if approval.status == AGENT_APPROVAL_PENDING
    ]
    if pending_ids:
        rendered = "、".join(f"#{approval_id}" for approval_id in pending_ids)
        return (
            "awaiting_approval",
            "等待审批",
            f"请先处理关联审批 {rendered}；审批未决定前不取消任务。",
        )
    if task.status == AGENT_TASK_PENDING:
        if latest_event_kind in _SETTLED_PENDING_EVENT_KINDS:
            if latest_event_kind == "approval_rejected":
                detail = "审批已经拒绝，但旧任务状态没有同步收口；建议取消任务。"
            elif latest_event_kind == "approval_approved":
                detail = "旧版审批已经批准，但没有工具恢复结果；不能重试，建议取消后按需重新创建。"
            else:
                detail = "工具恢复已有结束事件，但旧任务仍为待处理；建议取消并收口。"
            return "stale_residual", "旧任务残留", detail
        if _task_is_stale(task):
            return (
                "stale_residual",
                "旧任务残留",
                "任务长期没有进入审批或执行；建议取消，仍需要时重新创建明确任务。",
            )
        return (
            "ordinary_pending",
            "普通待处理",
            "任务尚未进入审批或执行；请核对目标，确定是否继续或取消。",
        )
    if task.status == AGENT_TASK_RUNNING:
        return "running", "执行中", "任务正在执行，不支持网页取消或自动重试。"
    if task.status == AGENT_TASK_FAILED:
        return "failed", "执行失败", "请查看失败事件；网页不会自动重试。"
    return "closed", "已收口", "任务已经完成或取消，仅供复盘。"


def _task_actionability(
    task: AgentTask,
    approvals: list[AgentApproval],
    *,
    task_actions_enabled: bool,
) -> OwnerConsoleTaskActionability:
    if task.status != AGENT_TASK_PENDING:
        return OwnerConsoleTaskActionability(
            can_cancel=False,
            task_actions_enabled=task_actions_enabled,
            blocked_reason="only a pending task can be cancelled",
        )
    if any(approval.status == AGENT_APPROVAL_PENDING for approval in approvals):
        return OwnerConsoleTaskActionability(
            can_cancel=False,
            task_actions_enabled=task_actions_enabled,
            blocked_reason="decide the pending approval before cancelling the task",
        )
    if not task_actions_enabled:
        return OwnerConsoleTaskActionability(
            can_cancel=False,
            task_actions_enabled=False,
            blocked_reason="web task actions are disabled",
        )
    return OwnerConsoleTaskActionability(
        can_cancel=True,
        task_actions_enabled=True,
        blocked_reason="",
    )


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
    actionability_provider: Callable[
        [AgentApproval], OwnerConsoleApprovalActionability
    ] | None = None,
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
        actionability=(actionability_provider or _actionability_for_approval)(approval),
    )


def _task_row(
    task: AgentTask,
    *,
    approvals: list[AgentApproval] | None = None,
    preview_limit: int = DEFAULT_PREVIEW_LIMIT,
    task_actions_enabled: bool = False,
) -> OwnerConsoleTaskRow:
    related_approvals = approvals or []
    pending_approval_ids = [
        approval.id
        for approval in related_approvals
        if approval.status == AGENT_APPROVAL_PENDING
    ]
    event_kind, event_summary = _event_summary(latest_agent_task_event(task.id))
    processing_category, processing_label, processing_detail = _task_processing(
        task,
        related_approvals,
        latest_event_kind=event_kind,
    )
    next_action_code = _next_action_for_task(task, related_approvals)
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
        next_action=next_action_code,
        next_action_code=next_action_code,
        work_type=safe_work_type,
        processing_category=processing_category,
        processing_label=processing_label,
        processing_detail=processing_detail,
        actionability=_task_actionability(
            task,
            related_approvals,
            task_actions_enabled=task_actions_enabled,
        ),
    )


def build_owner_console_task_list(
    context: OwnerConsoleContext,
    *,
    status: str | None = None,
    work_type: str | None = None,
    category: str | None = None,
    limit: int = 20,
    page: int = 1,
    page_size: int | None = None,
    task_actions_enabled: bool = False,
) -> OwnerConsoleTaskList:
    if work_type is not None and work_type not in OWNER_CONSOLE_WORK_TYPES:
        raise ValueError("unsupported owner console work type")
    if category is not None and category not in OWNER_CONSOLE_TASK_CATEGORIES:
        raise ValueError("unsupported owner console task category")
    safe_page_size = min(
        OWNER_CONSOLE_TASK_PAGE_SIZE_MAX,
        _safe_limit(page_size if page_size is not None else limit),
    )
    requested_page = _safe_limit(page)

    def build_rows(tasks: list[AgentTask]) -> list[OwnerConsoleTaskRow]:
        built_rows: list[OwnerConsoleTaskRow] = []
        for task in tasks:
            approvals = list_agent_approvals(
                session_key=context.session_key,
                user_id=context.user_id,
                task_id=task.id,
                status=AGENT_APPROVAL_PENDING,
                limit=20,
            )
            built_rows.append(
                _task_row(
                    task,
                    approvals=approvals,
                    task_actions_enabled=task_actions_enabled,
                )
            )
        return built_rows

    if category is None:
        total_matching = count_agent_tasks(
            session_key=context.session_key,
            user_id=context.user_id,
            status=status,
            work_type=work_type,
        )
        total_pages = max(1, (total_matching + safe_page_size - 1) // safe_page_size)
        safe_page = min(requested_page, total_pages)
        tasks = list_agent_tasks(
            session_key=context.session_key,
            user_id=context.user_id,
            status=status,
            work_type=work_type,
            limit=safe_page_size,
            offset=(safe_page - 1) * safe_page_size,
        )
        rows = build_rows(tasks)
    else:
        matching_rows: list[OwnerConsoleTaskRow] = []
        scan_offset = 0
        while True:
            task_batch = list_agent_tasks(
                session_key=context.session_key,
                user_id=context.user_id,
                status=status,
                work_type=work_type,
                limit=OWNER_CONSOLE_TASK_SCAN_BATCH_SIZE,
                offset=scan_offset,
            )
            if not task_batch:
                break
            matching_rows.extend(
                row
                for row in build_rows(task_batch)
                if row.processing_category == category
            )
            scan_offset += len(task_batch)
            if len(task_batch) < OWNER_CONSOLE_TASK_SCAN_BATCH_SIZE:
                break
        total_matching = len(matching_rows)
        total_pages = max(1, (total_matching + safe_page_size - 1) // safe_page_size)
        safe_page = min(requested_page, total_pages)
        start = (safe_page - 1) * safe_page_size
        rows = matching_rows[start : start + safe_page_size]

    return OwnerConsoleTaskList(
        generated_at=utc_now(),
        status_filter=status,
        work_type_filter=work_type,
        category_filter=category,
        limit=safe_page_size,
        page=safe_page,
        page_size=safe_page_size,
        total_matching=total_matching,
        total_pages=total_pages,
        has_previous=safe_page > 1,
        has_next=safe_page < total_pages,
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
    actionability_provider: Callable[
        [AgentApproval], OwnerConsoleApprovalActionability
    ] | None = None,
    task_actions_enabled: bool = False,
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
    task_row = _task_row(
        task,
        approvals=approvals,
        preview_limit=preview_limit,
        task_actions_enabled=task_actions_enabled,
    )
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
            _approval_row(
                approval,
                reason_limit=preview_limit,
                actionability_provider=actionability_provider,
            )
            for approval in approvals
        ],
        next_action=task_row.processing_detail,
        boundary=OwnerConsoleRuntimeBoundary(),
    )


def build_owner_console_approval_list(
    context: OwnerConsoleContext,
    *,
    status: str | None = None,
    limit: int = 20,
    actionability_provider: Callable[
        [AgentApproval], OwnerConsoleApprovalActionability
    ] | None = None,
) -> OwnerConsoleApprovalList:
    approvals = list_agent_approvals(
        session_key=context.session_key,
        user_id=context.user_id,
        status=status,
        limit=limit,
    )
    rows = [
        _approval_row(
            approval,
            actionability_provider=actionability_provider,
        )
        for approval in approvals
    ]
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
    actionability_provider: Callable[
        [AgentApproval], OwnerConsoleApprovalActionability
    ] | None = None,
    task_actions_enabled: bool = False,
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
        recent_task_rows.append(
            _task_row(
                task,
                approvals=task_pending_approvals,
                task_actions_enabled=task_actions_enabled,
            )
        )
    pending_task_rows: list[OwnerConsoleTaskRow] = []
    for task in list_agent_tasks(
        session_key=context.session_key,
        user_id=context.user_id,
        status=AGENT_TASK_PENDING,
        limit=10_000,
    ):
        related = list_agent_approvals(
            session_key=context.session_key,
            user_id=context.user_id,
            task_id=task.id,
            limit=20,
        )
        pending_task_rows.append(
            _task_row(
                task,
                approvals=related,
                task_actions_enabled=task_actions_enabled,
            )
        )
    approval_rows = [
        _approval_row(
            approval,
            actionability_provider=actionability_provider,
        )
        for approval in pending_approvals
    ]
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
            awaiting_approval_tasks=sum(
                row.processing_category == "awaiting_approval"
                for row in pending_task_rows
            ),
            ordinary_pending_tasks=sum(
                row.processing_category == "ordinary_pending"
                for row in pending_task_rows
            ),
            stale_pending_tasks=sum(
                row.processing_category == "stale_residual"
                for row in pending_task_rows
            ),
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
    actionability_provider: Callable[
        [AgentApproval], OwnerConsoleApprovalActionability
    ] | None = None,
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
        approval=_approval_row(
            approval,
            reason_limit=preview_limit,
            actionability_provider=actionability_provider,
        ),
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
