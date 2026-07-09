from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
import math
from typing import Any


OWNER_CONSOLE_SCHEMA_VERSION = "owner_console.read_model.v0"


@dataclass(frozen=True)
class OwnerConsoleContext:
    session_key: str
    user_id: str


@dataclass(frozen=True)
class OwnerConsoleRuntimeBoundary:
    main_agent_entry: str = "/agent explicit owner entry only"
    ordinary_chat_can_trigger_main_agent: bool = False
    project_doc_rag_in_ordinary_chat: bool = False
    shell_tools_exposed: bool = False
    arbitrary_file_write_allowed: bool = False
    unregistered_db_write_allowed: bool = False
    owner_write_requires_approval: bool = True
    approval_resume_requires_registered_tool: bool = True
    approval_resume_requires_enabled_tool: bool = True
    multi_step_write_automation_allowed: bool = False
    extra_qq_send_side_effect_allowed: bool = False


@dataclass(frozen=True)
class OwnerConsoleToolInputPreview:
    preview_json: str
    redacted: bool
    truncated: bool


@dataclass(frozen=True)
class OwnerConsoleApprovalActionability:
    can_approve: bool
    can_reject: bool
    resume_enabled: bool | None
    blocked_reason: str
    future_operation_only: bool = True


@dataclass(frozen=True)
class OwnerConsoleTaskEventRow:
    event_id: int
    task_id: int
    step_index: int
    kind: str
    tool_name: str
    input_preview: str
    output_summary: str
    status: str
    status_label: str
    error: str
    created_at: str


@dataclass(frozen=True)
class OwnerConsoleApprovalRow:
    approval_id: int
    task_id: int
    task_title: str
    tool_name: str
    risk_level: str
    reason_preview: str
    status: str
    status_label: str
    created_at: str
    expires_at: str
    decided_at: str
    actionability: OwnerConsoleApprovalActionability


@dataclass(frozen=True)
class OwnerConsoleTaskRow:
    task_id: int
    title: str
    goal_preview: str
    status: str
    status_label: str
    result_preview: str
    created_at: str
    updated_at: str
    latest_event_kind: str
    latest_event_summary: str
    pending_approval_ids: list[int] = field(default_factory=list)
    next_action: str = ""


@dataclass(frozen=True)
class OwnerConsoleTaskList:
    generated_at: str
    status_filter: str | None
    limit: int
    total_visible: int
    rows: list[OwnerConsoleTaskRow]
    boundary: OwnerConsoleRuntimeBoundary


@dataclass(frozen=True)
class OwnerConsoleTaskDetail:
    generated_at: str
    task: OwnerConsoleTaskRow
    goal: str
    result: str
    events: list[OwnerConsoleTaskEventRow]
    approvals: list[OwnerConsoleApprovalRow]
    next_action: str
    boundary: OwnerConsoleRuntimeBoundary


@dataclass(frozen=True)
class OwnerConsoleApprovalList:
    generated_at: str
    status_filter: str | None
    limit: int
    total_visible: int
    rows: list[OwnerConsoleApprovalRow]
    boundary: OwnerConsoleRuntimeBoundary


@dataclass(frozen=True)
class OwnerConsoleOverviewCounters:
    pending_tasks: int
    failed_tasks: int
    pending_approvals: int
    recent_tasks_visible: int
    pending_approvals_visible: int


@dataclass(frozen=True)
class OwnerConsoleOverview:
    generated_at: str
    task_limit: int
    approval_limit: int
    counters: OwnerConsoleOverviewCounters
    recent_tasks: list[OwnerConsoleTaskRow]
    pending_approvals: list[OwnerConsoleApprovalRow]
    boundary: OwnerConsoleRuntimeBoundary


@dataclass(frozen=True)
class OwnerConsoleAccessList:
    label: str
    count: int
    items: list[str]
    truncated: bool


@dataclass(frozen=True)
class OwnerConsoleAccessControlSnapshot:
    generated_at: str
    owner_configured: bool
    private_chat_enabled: bool
    group_chat_enabled: bool
    unknown_private_policy: str
    private_whitelist: OwnerConsoleAccessList
    group_whitelist: OwnerConsoleAccessList
    user_blacklist: OwnerConsoleAccessList
    boundary: OwnerConsoleRuntimeBoundary


@dataclass(frozen=True)
class OwnerConsoleModelConfigSnapshot:
    model_name: str
    base_url_redacted: str
    api_key_configured: bool
    timeout_seconds: int


@dataclass(frozen=True)
class OwnerConsoleRoleCardRow:
    key: str
    title: str
    active: bool


@dataclass(frozen=True)
class OwnerConsoleSettingsSnapshot:
    generated_at: str
    chat_model: OwnerConsoleModelConfigSnapshot
    main_agent_model: OwnerConsoleModelConfigSnapshot
    embedding: OwnerConsoleModelConfigSnapshot
    role_cards: list[OwnerConsoleRoleCardRow]
    active_role_card_key: str
    feature_flags: dict[str, bool]
    boundary: OwnerConsoleRuntimeBoundary


@dataclass(frozen=True)
class OwnerConsoleTextSnapshotSection:
    title: str
    ok: bool
    summary_text: str
    display_lines: list[str]
    error: str = ""


@dataclass(frozen=True)
class OwnerConsoleObservationSnapshot:
    main_agent: list[str]
    root_graph: list[str]


@dataclass(frozen=True)
class OwnerConsoleHealthSnapshot:
    generated_at: str
    bot_status: OwnerConsoleTextSnapshotSection
    diagnostics: OwnerConsoleTextSnapshotSection
    config: OwnerConsoleTextSnapshotSection
    vision: OwnerConsoleTextSnapshotSection
    image_cache: OwnerConsoleTextSnapshotSection
    memory: OwnerConsoleTextSnapshotSection
    tts: OwnerConsoleTextSnapshotSection
    recent_errors: OwnerConsoleTextSnapshotSection
    observations: OwnerConsoleObservationSnapshot
    boundary: OwnerConsoleRuntimeBoundary


@dataclass(frozen=True)
class OwnerConsoleMemoryCounts:
    message_count: int
    session_count: int
    session_summary_count: int
    summarized_message_count: int
    manual_memory_count: int
    manual_memory_subject_count: int
    gap_scene_summary_count: int
    gap_scene_source_message_count: int
    rag_document_count: int
    rag_active_document_count: int
    rag_embedding_count: int


@dataclass(frozen=True)
class OwnerConsoleMemoryContextPolicy:
    memory_compression_enabled: bool
    gap_scene_summaries_enabled: bool
    long_term_memory_context_enabled: bool
    max_context_messages: int
    max_stored_messages_per_session: int
    summary_keep_recent_messages: int
    summary_batch_messages: int
    summary_min_source_messages: int
    max_session_summaries_in_context: int
    max_gap_scene_summaries_in_context: int
    max_long_term_memories_in_context: int


@dataclass(frozen=True)
class OwnerConsoleMemoryRagSnapshot:
    enabled: bool
    inject_in_chat: bool
    owner_only_debug: bool
    top_k: int
    min_score: float
    max_context_chars: int
    include_manual_facts: bool
    include_manual_preferences: bool
    include_session_summaries: bool
    include_short_messages: bool
    include_gap_scene_summaries: bool


@dataclass(frozen=True)
class OwnerConsoleProjectDocRagSnapshot:
    enabled: bool
    explicit_agent_dev_context_only: bool
    ordinary_chat_injection_allowed: bool
    top_k: int
    min_score: float
    max_context_chars: int


@dataclass(frozen=True)
class OwnerConsoleMemorySnapshot:
    generated_at: str
    counts: OwnerConsoleMemoryCounts
    context_policy: OwnerConsoleMemoryContextPolicy
    memory_rag: OwnerConsoleMemoryRagSnapshot
    project_doc_rag: OwnerConsoleProjectDocRagSnapshot
    memory_content_exposed: bool
    project_doc_content_exposed: bool
    retrieval_executed: bool
    index_rebuild_executed: bool
    boundary: OwnerConsoleRuntimeBoundary


@dataclass(frozen=True)
class OwnerConsoleProviderWiringRow:
    provider_name: str
    required: bool
    configured: bool
    read_model_area: str
    owner_console_methods: list[str]
    fallback_behavior: str
    direct_qq_dependency_allowed: bool = False
    write_side_effect_allowed: bool = False


@dataclass(frozen=True)
class OwnerConsoleProviderWiringSnapshot:
    generated_at: str
    runtime_ready: bool
    missing_required: list[str]
    rows: list[OwnerConsoleProviderWiringRow]
    boundary: OwnerConsoleRuntimeBoundary


@dataclass(frozen=True)
class OwnerConsoleReadRouteRow:
    page: str
    response_page: str
    runtime_method: str
    read_model: str
    requires_context: bool
    required_params: list[str]
    optional_params: list[str]
    read_only: bool = True
    http_api_enabled: bool = False
    web_write_enabled: bool = False
    direct_qq_dependency_allowed: bool = False
    write_side_effect_allowed: bool = False


@dataclass(frozen=True)
class OwnerConsoleReadRouteContractSnapshot:
    generated_at: str
    route_count: int
    rows: list[OwnerConsoleReadRouteRow]
    boundary: OwnerConsoleRuntimeBoundary


@dataclass(frozen=True)
class OwnerConsoleApprovalDetail:
    generated_at: str
    approval: OwnerConsoleApprovalRow
    reason: str
    tool_input: OwnerConsoleToolInputPreview
    task: OwnerConsoleTaskRow | None
    recent_events: list[OwnerConsoleTaskEventRow]
    boundary: OwnerConsoleRuntimeBoundary


def owner_console_to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError("owner console read model contains a non-finite float")
        return value
    if isinstance(value, Enum):
        return owner_console_to_jsonable(value.value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: owner_console_to_jsonable(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, dict):
        return {
            str(key): owner_console_to_jsonable(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [owner_console_to_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [
            owner_console_to_jsonable(item)
            for item in sorted(value, key=lambda item: str(item))
        ]
    raise TypeError(
        "owner console read model contains unsupported value "
        f"{type(value).__name__}"
    )


def owner_console_page_response(page: str, data: Any) -> dict[str, Any]:
    page_name = page.strip()
    if not page_name:
        raise ValueError("owner console page must be non-empty")
    serialized_data = owner_console_to_jsonable(data)
    generated_at = ""
    if isinstance(serialized_data, dict):
        generated_at = str(serialized_data.get("generated_at") or "")
    return {
        "schema_version": OWNER_CONSOLE_SCHEMA_VERSION,
        "page": page_name,
        "generated_at": generated_at,
        "read_only": True,
        "http_api_enabled": False,
        "web_write_enabled": False,
        "data": serialized_data,
    }
