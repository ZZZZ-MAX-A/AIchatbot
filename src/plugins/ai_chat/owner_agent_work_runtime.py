from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .agent_tasks import (
    AGENT_TASK_RESULT_LIMIT,
    AGENT_TASK_WORK_QUERY_SUMMARY_LIMIT,
    AgentTask,
    agent_task_status_label,
    claim_agent_task_for_work,
    complete_agent_task_work,
    create_agent_task,
    fail_agent_task_work,
)
from .development_context_report import (
    DEVELOPMENT_CONTEXT_REPORT_RESPONSE_LIMIT,
    DevelopmentContextReportPayload,
    redact_development_context_sensitive_text,
)
from .external_read_security import (
    ExternalReadPolicyCategory,
    ExternalReadPolicyError,
    normalize_external_read_query,
)
from .failure_diagnostics import format_failure_user_message
from .system_diagnostics_report import (
    STATUS_LABELS,
    STATUS_ORDER,
    SYSTEM_DIAGNOSTICS_MEMORY_RAG_RESPONSE_LIMIT,
    SYSTEM_DIAGNOSTICS_MEMORY_RAG_SCOPE,
    SYSTEM_DIAGNOSTICS_OVERVIEW_RESPONSE_LIMIT,
    SYSTEM_DIAGNOSTICS_OVERVIEW_SCOPE,
    SYSTEM_DIAGNOSTICS_VISION_RESPONSE_LIMIT,
    SYSTEM_DIAGNOSTICS_VISION_SCOPE,
    SYSTEM_DIAGNOSTICS_VOICE_RESPONSE_LIMIT,
    SYSTEM_DIAGNOSTICS_VOICE_SCOPE,
    VISION_INFERENCE_SCOPE,
    VISION_INVOCATION_SCOPE,
    VISION_LAYER_INVOCATION,
    VISION_LAYER_LABELS,
    VISION_LAYER_QUALITY,
    VOICE_LAYER_LABELS,
    MEMORY_RAG_LAYER_LABELS,
    ZONE_LABELS,
    ZONE_ORDER,
    ZONE_VISION,
    ZONE_VOICE,
    SystemDiagnosticsReportPayload,
    VisionDiagnosticsReportPayload,
    VoiceDiagnosticsReportPayload,
    MemoryRagDiagnosticsReportPayload,
)


DEVELOPMENT_CONTEXT_REPORT_WORK_TYPE = "development_context_report"
DEVELOPMENT_CONTEXT_REPORT_DISPLAY_NAME = "研发上下文报告"
DEVELOPMENT_CONTEXT_REPORT_RISK_LEVEL = "read_local"
DEVELOPMENT_CONTEXT_REPORT_COMMAND_PREFIX = "执行研发上下文任务"
SYSTEM_DIAGNOSTICS_REPORT_WORK_TYPE = "system_diagnostics_report"
SYSTEM_DIAGNOSTICS_REPORT_DISPLAY_NAME = "系统诊断报告"
SYSTEM_DIAGNOSTICS_REPORT_RISK_LEVEL = "read_local"
SYSTEM_DIAGNOSTICS_REPORT_COMMAND_PREFIX = "执行系统诊断任务"
SYSTEM_DIAGNOSTICS_UNSUPPORTED_SCOPE = "unsupported"
EXTERNAL_READ_REPORT_WORK_TYPE = "external_read_report"
EXTERNAL_READ_REPORT_DISPLAY_NAME = "外部只读查询报告"
EXTERNAL_READ_REPORT_RISK_LEVEL = "read_external"
EXTERNAL_READ_REPORT_RESPONSE_LIMIT = 3200
EXTERNAL_READ_REPORT_QUERY_SUMMARY = "主人显式提供的外部只读查询（原文未持久化）"
EXTERNAL_READ_REPORT_COMMAND_PREFIX = "执行外部只读查询"

SYSTEM_DIAGNOSTICS_SCOPE_ALIASES = {
    "overview": SYSTEM_DIAGNOSTICS_OVERVIEW_SCOPE,
    "概览": SYSTEM_DIAGNOSTICS_OVERVIEW_SCOPE,
    "core": "core",
    "核心": "core",
    "核心运行": "core",
    "chat": "chat",
    "聊天": "chat",
    "main_agent": "main_agent",
    "mainagent": "main_agent",
    "agent": "main_agent",
    "memory_rag": SYSTEM_DIAGNOSTICS_MEMORY_RAG_SCOPE,
    "memoryrag": SYSTEM_DIAGNOSTICS_MEMORY_RAG_SCOPE,
    "记忆与rag": SYSTEM_DIAGNOSTICS_MEMORY_RAG_SCOPE,
    "记忆与rag区": SYSTEM_DIAGNOSTICS_MEMORY_RAG_SCOPE,
    "vision": "vision",
    "视觉": "vision",
    "voice": SYSTEM_DIAGNOSTICS_VOICE_SCOPE,
    "语音": SYSTEM_DIAGNOSTICS_VOICE_SCOPE,
    "owner_console": "owner_console",
    "ownerconsole": "owner_console",
    "owner console": "owner_console",
}

WorkExecutor = Callable[[str], object | Awaitable[object]]


@dataclass(frozen=True)
class SanitizedAgentWorkResult:
    persisted_summary: str
    response_text: str


@dataclass(frozen=True)
class ExternalReadReportPayload:
    provider_name: str
    result_count: int
    source_host_count: int
    dropped_result_count: int
    external_request_count: int
    response_truncated: bool
    status_category: str
    error_category: str
    report_text: str


@dataclass(frozen=True)
class ExternalReadCommandDecision:
    allowed: bool
    normalized_query: str = ""
    reply_text: str = ""


WorkResultSanitizer = Callable[[object], SanitizedAgentWorkResult]


_EXTERNAL_READ_ERROR_REPLIES = {
    ExternalReadPolicyCategory.REQUEST_TIMEOUT: (
        "外部只读查询未完成：固定搜索 provider 请求超时。"
        "本次未自动重试，也未切换其他 provider。"
    ),
    ExternalReadPolicyCategory.PROVIDER_UNAVAILABLE: (
        "外部只读查询未完成：固定搜索 provider 当前不可用。"
        "本次未自动重试，也未回退其他服务。"
    ),
    ExternalReadPolicyCategory.AUTHENTICATION_FAILED: (
        "外部只读查询未完成：Tavily 凭据未通过鉴权。"
        "请检查本地 Key 或在官方控制台轮换凭据；本次未自动重试。"
    ),
    ExternalReadPolicyCategory.RATE_LIMITED: (
        "外部只读查询未完成：Tavily 当前返回限流。"
        "本次未自动重试，也未切换其他 provider。"
    ),
    ExternalReadPolicyCategory.RESPONSE_TOO_LARGE: (
        "外部只读查询未完成：provider 响应超过本地安全上限，已拒绝处理。"
        "原始响应未持久化。"
    ),
    ExternalReadPolicyCategory.INVALID_PROVIDER_RESPONSE: (
        "外部只读查询未完成：provider 返回结构不符合固定协议，已安全拒绝。"
        "原始响应和异常未写入任务记录。"
    ),
    ExternalReadPolicyCategory.SANITIZATION_FAILED: (
        "外部只读查询未完成：外部内容未通过安全清洗，已拒绝返回。"
        "原始内容未持久化。"
    ),
    ExternalReadPolicyCategory.UNSAFE_RESOLVED_ADDRESS: (
        "外部只读查询未完成：provider 地址未通过公网安全校验，本次未发送请求。"
    ),
    ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT: (
        "外部只读查询未完成：固定 provider endpoint 未通过安全校验，本次未发送请求。"
    ),
    ExternalReadPolicyCategory.INVALID_BUDGET: (
        "外部只读查询未完成：本地请求预算配置无效，本次未发送请求。"
    ),
}


def format_external_read_policy_error(error: ExternalReadPolicyError) -> str:
    return _EXTERNAL_READ_ERROR_REPLIES.get(
        error.category,
        "外部只读查询未完成：请求未通过本地安全策略。未自动重试或回退其他服务。",
    )


@dataclass(frozen=True)
class OwnerAgentWorkContext:
    session_key: str
    user_id: str


@dataclass(frozen=True)
class AgentWorkSpec:
    name: str
    display_name: str
    risk_level: str
    required_arguments: tuple[str, ...]
    executor: WorkExecutor
    result_sanitizer: WorkResultSanitizer
    requires_approval: bool
    result_limit: int
    persisted_query_summary: str | None


@dataclass(frozen=True)
class OwnerAgentWorkExecution:
    work_type: str
    task: AgentTask | None
    outcome: str
    result_summary: str
    response_text: str = ""


def parse_development_context_report_command(query: str) -> str | None:
    stripped = query.strip()
    if stripped == DEVELOPMENT_CONTEXT_REPORT_COMMAND_PREFIX:
        return ""
    for separator in ("：", ":"):
        prefix = f"{DEVELOPMENT_CONTEXT_REPORT_COMMAND_PREFIX}{separator}"
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip()
    return None


def parse_system_diagnostics_report_command(query: str) -> str | None:
    stripped = query.strip()
    if stripped == SYSTEM_DIAGNOSTICS_REPORT_COMMAND_PREFIX:
        return SYSTEM_DIAGNOSTICS_OVERVIEW_SCOPE
    for separator in ("：", ":"):
        prefix = f"{SYSTEM_DIAGNOSTICS_REPORT_COMMAND_PREFIX}{separator}"
        if stripped.startswith(prefix):
            requested_scope = stripped[len(prefix):].strip().lower()
            if not requested_scope:
                return SYSTEM_DIAGNOSTICS_UNSUPPORTED_SCOPE
            return SYSTEM_DIAGNOSTICS_SCOPE_ALIASES.get(
                requested_scope,
                SYSTEM_DIAGNOSTICS_UNSUPPORTED_SCOPE,
            )
    return None


def parse_external_read_report_command(query: str) -> str | None:
    stripped = query.strip()
    if stripped == EXTERNAL_READ_REPORT_COMMAND_PREFIX:
        return ""
    for separator in ("：", ":"):
        prefix = f"{EXTERNAL_READ_REPORT_COMMAND_PREFIX}{separator}"
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip()
    return None


def prepare_external_read_command(
    query: str,
    *,
    is_private_session: bool,
    owner_authorized: bool,
    feature_enabled: bool,
    executor_configured: bool,
) -> ExternalReadCommandDecision:
    if not is_private_session:
        return ExternalReadCommandDecision(
            allowed=False,
            reply_text="外部只读查询只允许主人私聊通过 /agent 严格命令执行。",
        )
    if not owner_authorized:
        return ExternalReadCommandDecision(
            allowed=False,
            reply_text="外部只读查询被拒绝：需要主人权限。",
        )
    if not feature_enabled:
        return ExternalReadCommandDecision(
            allowed=False,
            reply_text=(
                "外部只读查询未启用：ENABLE_AGENT_WEB=false；"
                "未创建任务，也未调用 provider。"
            ),
        )
    if not executor_configured:
        return ExternalReadCommandDecision(
            allowed=False,
            reply_text=(
                "外部只读查询暂不可用：固定 provider 尚未配置；"
                "未创建任务，也未发起外部请求。"
            ),
        )
    try:
        normalized_query = normalize_external_read_query(query)
    except ExternalReadPolicyError as exc:
        reason = {
            ExternalReadPolicyCategory.INVALID_QUERY: (
                "查询格式无效；请只提交明确的公开信息问题，不要包含 URL"
            ),
            ExternalReadPolicyCategory.SENSITIVE_QUERY: (
                "查询疑似包含凭据、本地路径或其他敏感内容；请移除后重试"
            ),
        }.get(exc.category, "查询未通过本地安全策略")
        return ExternalReadCommandDecision(
            allowed=False,
            reply_text=(
                f"外部只读查询被拒绝：{exc.category.value}（{reason}）；"
                "未创建任务，也未调用 provider。"
            ),
        )
    return ExternalReadCommandDecision(
        allowed=True,
        normalized_query=normalized_query,
    )


def format_owner_agent_work_execution(execution: OwnerAgentWorkExecution) -> str:
    task = execution.task
    is_system_diagnostics = execution.work_type == SYSTEM_DIAGNOSTICS_REPORT_WORK_TYPE
    is_external_read = execution.work_type == EXTERNAL_READ_REPORT_WORK_TYPE
    if is_system_diagnostics:
        task_label = "系统诊断任务"
    elif is_external_read:
        task_label = "外部只读查询任务"
    else:
        task_label = "研发上下文任务"
    if task is None:
        return f"{task_label}未创建；未执行任何执行器。"

    if execution.outcome == "completed":
        headline = f"{task_label} #{task.id} 已完成。"
    elif execution.outcome == "failed":
        headline = f"{task_label} #{task.id} 执行失败。"
    else:
        headline = f"{task_label} #{task.id} 未进入执行。"

    boundary = (
        "边界：只执行已注册的确定性系统概览，或主人显式选择的视觉、语音、"
        "记忆与RAG区详情；"
        "未开放深度探针、外部请求、自动重试或修复。"
        if is_system_diagnostics
        else (
            "边界：只执行已注册的单次固定 provider 外部读取；未自动重试、打开来源页面、"
            "写入 RAG/记忆或发送额外 QQ。"
            if is_external_read
            else "边界：只执行已注册的只读研发上下文报告；未开放 shell、文件写入、Web 写操作或自动重试。"
        )
    )

    return "\n".join(
        [
            headline,
            f"状态：{agent_task_status_label(task.status)}",
            "结果：",
            execution.response_text or execution.result_summary,
            f"查看：/agent 任务详情 {task.id}",
            boundary,
        ]
    )


def _normalize_query(query: str) -> str:
    if not isinstance(query, str):
        raise ValueError("work query must be text")
    without_controls = "".join(
        " " if ord(character) < 32 else character for character in query
    )
    compact = " ".join(without_controls.split())
    if not compact:
        raise ValueError("work query must be non-empty")
    return compact[:AGENT_TASK_WORK_QUERY_SUMMARY_LIMIT].rstrip()


def _first_count(text: str, labels: tuple[str, ...]) -> int | None:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*(\d+)", text)
        if match:
            return int(match.group(1))
    return None


def _sanitize_development_context_response(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("development context report response must be non-empty")
    normalized_lines: list[str] = []
    for line in text.splitlines():
        without_controls = "".join(
            " " if ord(character) < 32 else character for character in line
        )
        normalized_lines.append(without_controls.rstrip())
    normalized = redact_development_context_sensitive_text(
        "\n".join(normalized_lines).strip()
    )
    if not normalized:
        raise ValueError("development context report response became empty")
    return normalized[:DEVELOPMENT_CONTEXT_REPORT_RESPONSE_LIMIT].rstrip()


def _persisted_development_context_summary(
    *,
    project_count: int | None,
    memory_count: int | None,
    summary_mode: str = "legacy_count_only",
    current_status_anchor_included: bool | None = None,
    retrieval_warning_count: int = 0,
) -> str:
    lines = ["研发上下文报告已完成。"]
    if project_count is not None:
        lines.append(f"项目文档命中：{project_count}。")
    if memory_count is not None:
        lines.append(f"开发侧记忆命中：{memory_count}。")
    if project_count is None and memory_count is None:
        lines.append("执行器未返回可持久化的命中计数。")
    if current_status_anchor_included is not None:
        anchor_status = "已加载" if current_status_anchor_included else "缺失"
        lines.append(f"当前状态锚点：{anchor_status}。")
        lines.append(f"检索警告：{retrieval_warning_count}。")
    if summary_mode == "bounded_llm":
        lines.append("详细回复：受限主模型结构化总结，仅在本次主人私聊返回。")
    elif summary_mode == "deterministic_fallback":
        lines.append("详细回复：确定性回退摘要，仅在本次主人私聊返回。")
    lines.append("任务记录未保存原始 RAG 片段、路径、详细回复或异常文本。")
    return "\n".join(lines)[:AGENT_TASK_RESULT_LIMIT].rstrip()


def _sanitize_development_context_report(raw_result: object) -> SanitizedAgentWorkResult:
    if isinstance(raw_result, DevelopmentContextReportPayload):
        if raw_result.project_result_count < 0 or raw_result.memory_result_count < 0:
            raise ValueError("development context report counts must be non-negative")
        if raw_result.current_status_anchor_included is not None and not isinstance(
            raw_result.current_status_anchor_included,
            bool,
        ):
            raise ValueError("development context report anchor flag is invalid")
        if (
            not isinstance(raw_result.retrieval_warning_count, int)
            or isinstance(raw_result.retrieval_warning_count, bool)
            or raw_result.retrieval_warning_count < 0
        ):
            raise ValueError("development context report warning count is invalid")
        if raw_result.summary_mode not in {"bounded_llm", "deterministic_fallback"}:
            raise ValueError("development context report summary mode is invalid")
        persisted_summary = _persisted_development_context_summary(
            project_count=raw_result.project_result_count,
            memory_count=raw_result.memory_result_count,
            summary_mode=raw_result.summary_mode,
            current_status_anchor_included=raw_result.current_status_anchor_included,
            retrieval_warning_count=raw_result.retrieval_warning_count,
        )
        response_text = _sanitize_development_context_response(raw_result.report_text)
        return SanitizedAgentWorkResult(
            persisted_summary=persisted_summary,
            response_text=response_text,
        )

    if not isinstance(raw_result, str) or not raw_result.strip():
        raise ValueError("development context report executor returned no text")

    project_count = _first_count(raw_result, ("project docs:", "项目文档命中："))
    memory_count = _first_count(raw_result, ("memories:", "记忆命中："))
    persisted_summary = _persisted_development_context_summary(
        project_count=project_count,
        memory_count=memory_count,
    )
    return SanitizedAgentWorkResult(
        persisted_summary=persisted_summary,
        response_text=persisted_summary,
    )


def _sanitize_system_diagnostics_response(text: str, *, limit: int) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("system diagnostics report response must be non-empty")
    normalized_lines: list[str] = []
    for line in text.splitlines():
        without_controls = "".join(
            " " if ord(character) < 32 else character for character in line
        )
        normalized_lines.append(without_controls.rstrip())
    normalized = redact_development_context_sensitive_text(
        "\n".join(normalized_lines).strip()
    )
    if not normalized:
        raise ValueError("system diagnostics report response became empty")
    return normalized[:limit].rstrip()


def _persisted_system_diagnostics_summary(
    payload: SystemDiagnosticsReportPayload,
) -> str:
    counts = payload.status_counts
    count_text = "，".join(
        f"{STATUS_LABELS[status]} {counts[status]}"
        for status in STATUS_ORDER
    )
    primary_label = (
        ZONE_LABELS[payload.primary_recommended_scope]
        if payload.primary_recommended_scope
        else "无"
    )
    lines = [
        "系统诊断概览已完成。",
        f"总体状态：{STATUS_LABELS[payload.overall_status]}。",
        f"大区：{count_text}。",
        f"优先排查区域：{primary_label}。",
        f"本地检查：{payload.local_probe_count}。",
        f"深度探针：{payload.deep_probe_count}。",
        f"外部请求：{payload.external_request_count}。",
        f"修复操作：{payload.repair_action_count}。",
        "详细回复：确定性大区概览，仅在本次主人私聊返回。",
        "任务记录未保存完整诊断证据、配置值、错误原文、路径或观测明细。",
    ]
    return "\n".join(lines)[:AGENT_TASK_RESULT_LIMIT].rstrip()


def _persisted_vision_diagnostics_summary(
    payload: VisionDiagnosticsReportPayload,
) -> str:
    recommended_scope = payload.recommended_scope or "无"
    lines = [
        "视觉区详情诊断已完成。",
        f"区域状态：{STATUS_LABELS[payload.zone_status.status]}。",
        f"定位层级：{VISION_LAYER_LABELS[payload.fault_layer]}。",
        f"推荐下一范围：{recommended_scope}。",
        f"本地检查：{payload.local_probe_count}。",
        f"深度探针：{payload.deep_probe_count}。",
        f"外部请求：{payload.external_request_count}。",
        f"修复操作：{payload.repair_action_count}。",
        "详细回复：确定性视觉状态链，仅在本次主人私聊返回。",
        "任务记录未保存日志、图片、路径、配置值、完整观测或详细报告。",
    ]
    return "\n".join(lines)[:AGENT_TASK_RESULT_LIMIT].rstrip()


def _persisted_voice_diagnostics_summary(
    payload: VoiceDiagnosticsReportPayload,
) -> str:
    lines = [
        "语音区详情诊断已完成。",
        f"区域状态：{STATUS_LABELS[payload.zone_status.status]}。",
        f"定位层级：{VOICE_LAYER_LABELS[payload.fault_layer]}。",
        "推荐下一范围：无。",
        f"本地检查：{payload.local_probe_count}。",
        f"深度探针：{payload.deep_probe_count}。",
        f"外部请求：{payload.external_request_count}。",
        f"修复操作：{payload.repair_action_count}。",
        "详细回复：确定性语音状态链，仅在本次主人私聊返回。",
        "任务记录未保存服务地址、健康原文、候选文本、音频、路径或完整观测。",
    ]
    return "\n".join(lines)[:AGENT_TASK_RESULT_LIMIT].rstrip()


def _persisted_memory_rag_diagnostics_summary(
    payload: MemoryRagDiagnosticsReportPayload,
) -> str:
    lines = [
        "记忆与RAG区详情诊断已完成。",
        f"区域状态：{STATUS_LABELS[payload.zone_status.status]}。",
        f"定位层级：{MEMORY_RAG_LAYER_LABELS[payload.fault_layer]}。",
        "推荐下一范围：无。",
        f"本地检查：{payload.local_probe_count}。",
        f"深度探针：{payload.deep_probe_count}。",
        f"外部请求：{payload.external_request_count}。",
        f"修复操作：{payload.repair_action_count}。",
        "详细回复：确定性记忆与RAG状态链，仅在本次主人私聊返回。",
        "任务记录未保存检索正文、来源路径、错误原文、配置值或完整观测。",
    ]
    return "\n".join(lines)[:AGENT_TASK_RESULT_LIMIT].rstrip()


def _validate_system_diagnostics_counts(
    *,
    local_probe_count: int,
    external_request_count: int,
    deep_probe_count: int,
    repair_action_count: int,
) -> None:
    for count in (
        local_probe_count,
        external_request_count,
        deep_probe_count,
        repair_action_count,
    ):
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("system diagnostics count is invalid")
    if external_request_count or deep_probe_count or repair_action_count:
        raise ValueError("system diagnostics exceeded read-only scope")


def _sanitize_system_diagnostics_report(
    raw_result: object,
) -> SanitizedAgentWorkResult:
    if isinstance(raw_result, SystemDiagnosticsReportPayload):
        if raw_result.scope != SYSTEM_DIAGNOSTICS_OVERVIEW_SCOPE:
            raise ValueError("system diagnostics scope is invalid")
        if raw_result.overall_status not in STATUS_ORDER:
            raise ValueError("system diagnostics overall status is invalid")
        if tuple(zone.zone for zone in raw_result.zones) != ZONE_ORDER:
            raise ValueError("system diagnostics zones are invalid")
        for zone in raw_result.zones:
            if zone.status not in STATUS_ORDER:
                raise ValueError("system diagnostics zone status is invalid")
            if not isinstance(zone.headline, str) or not zone.headline.strip():
                raise ValueError("system diagnostics zone headline is invalid")
            if zone.recommended_scope not in {"", zone.zone}:
                raise ValueError("system diagnostics recommended scope is invalid")
        if raw_result.primary_recommended_scope not in {"", *ZONE_ORDER}:
            raise ValueError("system diagnostics primary scope is invalid")
        _validate_system_diagnostics_counts(
            local_probe_count=raw_result.local_probe_count,
            external_request_count=raw_result.external_request_count,
            deep_probe_count=raw_result.deep_probe_count,
            repair_action_count=raw_result.repair_action_count,
        )
        response_text = _sanitize_system_diagnostics_response(
            raw_result.report_text,
            limit=SYSTEM_DIAGNOSTICS_OVERVIEW_RESPONSE_LIMIT,
        )
        return SanitizedAgentWorkResult(
            persisted_summary=_persisted_system_diagnostics_summary(raw_result),
            response_text=response_text,
        )

    if isinstance(raw_result, VisionDiagnosticsReportPayload):
        if raw_result.scope != SYSTEM_DIAGNOSTICS_VISION_SCOPE:
            raise ValueError("vision diagnostics scope is invalid")
        zone = raw_result.zone_status
        if zone.zone != ZONE_VISION or zone.status not in STATUS_ORDER:
            raise ValueError("vision diagnostics zone status is invalid")
        if not isinstance(zone.headline, str) or not zone.headline.strip():
            raise ValueError("vision diagnostics zone headline is invalid")
        if zone.recommended_scope not in {"", ZONE_VISION}:
            raise ValueError("vision diagnostics zone recommendation is invalid")
        if raw_result.fault_layer not in VISION_LAYER_LABELS:
            raise ValueError("vision diagnostics fault layer is invalid")
        expected_statuses = {
            "configuration": {"off_by_design"},
            "service": {"unknown", "degraded"},
            "model": {"unknown", "degraded"},
            "invocation": {"attention"},
            "quality": {"attention"},
            "observation": {"normal"},
            "none": {"normal"},
        }
        if zone.status not in expected_statuses[raw_result.fault_layer]:
            raise ValueError("vision diagnostics layer status is invalid")
        expected_scope = {
            VISION_LAYER_INVOCATION: VISION_INVOCATION_SCOPE,
            VISION_LAYER_QUALITY: VISION_INFERENCE_SCOPE,
        }.get(raw_result.fault_layer, "")
        if raw_result.recommended_scope != expected_scope:
            raise ValueError("vision diagnostics recommended scope is invalid")
        _validate_system_diagnostics_counts(
            local_probe_count=raw_result.local_probe_count,
            external_request_count=raw_result.external_request_count,
            deep_probe_count=raw_result.deep_probe_count,
            repair_action_count=raw_result.repair_action_count,
        )
        response_text = _sanitize_system_diagnostics_response(
            raw_result.report_text,
            limit=SYSTEM_DIAGNOSTICS_VISION_RESPONSE_LIMIT,
        )
        return SanitizedAgentWorkResult(
            persisted_summary=_persisted_vision_diagnostics_summary(raw_result),
            response_text=response_text,
        )

    if isinstance(raw_result, VoiceDiagnosticsReportPayload):
        if raw_result.scope != SYSTEM_DIAGNOSTICS_VOICE_SCOPE:
            raise ValueError("voice diagnostics scope is invalid")
        zone = raw_result.zone_status
        if zone.zone != ZONE_VOICE or zone.status not in STATUS_ORDER:
            raise ValueError("voice diagnostics zone status is invalid")
        if not isinstance(zone.headline, str) or not zone.headline.strip():
            raise ValueError("voice diagnostics zone headline is invalid")
        if zone.recommended_scope not in {"", ZONE_VOICE}:
            raise ValueError("voice diagnostics zone recommendation is invalid")
        if raw_result.fault_layer not in VOICE_LAYER_LABELS:
            raise ValueError("voice diagnostics fault layer is invalid")
        expected_statuses = {
            "configuration": {"off_by_design"},
            "startup": {"normal"},
            "endpoint": {"unknown"},
            "service": {"unknown", "degraded"},
            "model": {"unknown", "attention"},
            "observation": {"normal"},
            "none": {"normal"},
        }
        if zone.status not in expected_statuses[raw_result.fault_layer]:
            raise ValueError("voice diagnostics layer status is invalid")
        if raw_result.recommended_scope:
            raise ValueError("voice diagnostics recommended scope is invalid")
        _validate_system_diagnostics_counts(
            local_probe_count=raw_result.local_probe_count,
            external_request_count=raw_result.external_request_count,
            deep_probe_count=raw_result.deep_probe_count,
            repair_action_count=raw_result.repair_action_count,
        )
        response_text = _sanitize_system_diagnostics_response(
            raw_result.report_text,
            limit=SYSTEM_DIAGNOSTICS_VOICE_RESPONSE_LIMIT,
        )
        return SanitizedAgentWorkResult(
            persisted_summary=_persisted_voice_diagnostics_summary(raw_result),
            response_text=response_text,
        )

    if isinstance(raw_result, MemoryRagDiagnosticsReportPayload):
        if raw_result.scope != SYSTEM_DIAGNOSTICS_MEMORY_RAG_SCOPE:
            raise ValueError("memory RAG diagnostics scope is invalid")
        zone = raw_result.zone_status
        if zone.zone != "memory_rag" or zone.status not in STATUS_ORDER:
            raise ValueError("memory RAG diagnostics zone status is invalid")
        if not isinstance(zone.headline, str) or not zone.headline.strip():
            raise ValueError("memory RAG diagnostics zone headline is invalid")
        if zone.recommended_scope not in {"", "memory_rag"}:
            raise ValueError("memory RAG diagnostics zone recommendation is invalid")
        if raw_result.fault_layer not in MEMORY_RAG_LAYER_LABELS:
            raise ValueError("memory RAG diagnostics fault layer is invalid")
        expected_statuses = {
            "configuration": {"off_by_design"},
            "storage": {"unknown", "degraded"},
            "index": {"attention"},
            "runtime": {"attention"},
            "observation": {"normal"},
            "none": {"normal"},
        }
        if zone.status not in expected_statuses[raw_result.fault_layer]:
            raise ValueError("memory RAG diagnostics layer status is invalid")
        if raw_result.recommended_scope:
            raise ValueError("memory RAG diagnostics recommended scope is invalid")
        _validate_system_diagnostics_counts(
            local_probe_count=raw_result.local_probe_count,
            external_request_count=raw_result.external_request_count,
            deep_probe_count=raw_result.deep_probe_count,
            repair_action_count=raw_result.repair_action_count,
        )
        response_text = _sanitize_system_diagnostics_response(
            raw_result.report_text,
            limit=SYSTEM_DIAGNOSTICS_MEMORY_RAG_RESPONSE_LIMIT,
        )
        return SanitizedAgentWorkResult(
            persisted_summary=_persisted_memory_rag_diagnostics_summary(raw_result),
            response_text=response_text,
        )

    raise ValueError("system diagnostics executor returned invalid payload")


def _validate_external_read_count(
    value: object,
    *,
    field_name: str,
    maximum: int | None = None,
) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"external read {field_name} is invalid")
    if maximum is not None and value > maximum:
        raise ValueError(f"external read {field_name} exceeded its limit")
    return value


def _sanitize_external_read_response(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("external read report response must be non-empty")
    normalized_lines: list[str] = []
    for line in text.splitlines():
        without_controls = "".join(
            " " if ord(character) < 32 else character for character in line
        )
        normalized_lines.append(without_controls.rstrip())
    normalized = redact_development_context_sensitive_text(
        "\n".join(normalized_lines).strip()
    )
    if not normalized:
        raise ValueError("external read report response became empty")
    return normalized[:EXTERNAL_READ_REPORT_RESPONSE_LIMIT].rstrip()


def _sanitize_external_read_report(
    raw_result: object,
) -> SanitizedAgentWorkResult:
    if not isinstance(raw_result, ExternalReadReportPayload):
        raise ValueError("external read executor returned invalid payload")

    if not isinstance(raw_result.provider_name, str):
        raise ValueError("external read provider name is invalid")
    provider_name = raw_result.provider_name.strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", provider_name):
        raise ValueError("external read provider name is invalid")

    result_count = _validate_external_read_count(
        raw_result.result_count,
        field_name="result count",
        maximum=3,
    )
    source_host_count = _validate_external_read_count(
        raw_result.source_host_count,
        field_name="source host count",
        maximum=3,
    )
    dropped_result_count = _validate_external_read_count(
        raw_result.dropped_result_count,
        field_name="dropped result count",
    )
    external_request_count = _validate_external_read_count(
        raw_result.external_request_count,
        field_name="external request count",
    )
    if external_request_count != 1:
        raise ValueError("external read must use exactly one external request")
    if source_host_count > result_count:
        raise ValueError("external read source host count exceeds result count")
    if not isinstance(raw_result.response_truncated, bool):
        raise ValueError("external read response truncated flag is invalid")

    if not isinstance(raw_result.status_category, str):
        raise ValueError("external read status category is invalid")
    status_category = raw_result.status_category.strip().lower()
    if status_category not in {"completed", "no_results"}:
        raise ValueError("external read status category is invalid")
    if (result_count == 0) != (status_category == "no_results"):
        raise ValueError("external read status category does not match result count")
    if not isinstance(raw_result.error_category, str):
        raise ValueError("external read error category is invalid")
    error_category = raw_result.error_category.strip().lower()
    if error_category != "none":
        raise ValueError("external read successful payload has an invalid error category")

    response_text = _sanitize_external_read_response(raw_result.report_text)
    persisted_summary = "\n".join(
        [
            "外部只读查询已完成。",
            f"Provider：{provider_name}。",
            f"结果数：{result_count}。",
            f"来源主机数：{source_host_count}。",
            f"丢弃结果数：{dropped_result_count}。",
            f"外部请求：{external_request_count}。",
            f"响应截断：{'是' if raw_result.response_truncated else '否'}。",
            f"状态类别：{status_category}。",
            f"错误类别：{error_category}。",
            "详细回复仅在本次主人私聊返回。",
            "任务记录未保存 query、标题、摘要、URL、来源主机明细、provider endpoint 或原始异常。",
        ]
    )[:AGENT_TASK_RESULT_LIMIT].rstrip()
    return SanitizedAgentWorkResult(
        persisted_summary=persisted_summary,
        response_text=response_text,
    )


def _development_context_report_spec(executor: WorkExecutor) -> AgentWorkSpec:
    return AgentWorkSpec(
        name=DEVELOPMENT_CONTEXT_REPORT_WORK_TYPE,
        display_name=DEVELOPMENT_CONTEXT_REPORT_DISPLAY_NAME,
        risk_level=DEVELOPMENT_CONTEXT_REPORT_RISK_LEVEL,
        required_arguments=("query",),
        executor=executor,
        result_sanitizer=_sanitize_development_context_report,
        requires_approval=False,
        result_limit=AGENT_TASK_RESULT_LIMIT,
        persisted_query_summary=None,
    )


def _system_diagnostics_report_spec(executor: WorkExecutor) -> AgentWorkSpec:
    return AgentWorkSpec(
        name=SYSTEM_DIAGNOSTICS_REPORT_WORK_TYPE,
        display_name=SYSTEM_DIAGNOSTICS_REPORT_DISPLAY_NAME,
        risk_level=SYSTEM_DIAGNOSTICS_REPORT_RISK_LEVEL,
        required_arguments=("scope",),
        executor=executor,
        result_sanitizer=_sanitize_system_diagnostics_report,
        requires_approval=False,
        result_limit=AGENT_TASK_RESULT_LIMIT,
        persisted_query_summary=None,
    )


def _external_read_report_spec(executor: WorkExecutor) -> AgentWorkSpec:
    return AgentWorkSpec(
        name=EXTERNAL_READ_REPORT_WORK_TYPE,
        display_name=EXTERNAL_READ_REPORT_DISPLAY_NAME,
        risk_level=EXTERNAL_READ_REPORT_RISK_LEVEL,
        required_arguments=("query",),
        executor=executor,
        result_sanitizer=_sanitize_external_read_report,
        requires_approval=False,
        result_limit=AGENT_TASK_RESULT_LIMIT,
        persisted_query_summary=EXTERNAL_READ_REPORT_QUERY_SUMMARY,
    )


class OwnerAgentWorkRuntime:
    """Runs registered read-only work types without any QQ dependency."""

    def __init__(
        self,
        *,
        context: OwnerAgentWorkContext,
        development_context_report_executor: WorkExecutor,
        system_diagnostics_report_executor: WorkExecutor,
        external_read_report_executor: WorkExecutor | None = None,
    ) -> None:
        self.context = context
        specs = [
            _development_context_report_spec(development_context_report_executor),
            _system_diagnostics_report_spec(system_diagnostics_report_executor),
        ]
        if external_read_report_executor is not None:
            specs.append(_external_read_report_spec(external_read_report_executor))
        self._work_specs = {spec.name: spec for spec in specs}

    @property
    def registered_work_types(self) -> tuple[str, ...]:
        return tuple(self._work_specs)

    def work_spec(self, work_type: str) -> AgentWorkSpec:
        normalized_work_type = str(work_type).strip()
        spec = self._work_specs.get(normalized_work_type)
        if spec is None:
            raise ValueError(f"unsupported owner agent work type: {normalized_work_type}")
        return spec

    async def execute(self, *, work_type: str, query: str) -> OwnerAgentWorkExecution:
        spec = self.work_spec(work_type)
        normalized_query = _normalize_query(query)
        persisted_query_summary = (
            spec.persisted_query_summary or normalized_query
        )
        task_id = create_agent_task(
            session_key=self.context.session_key,
            user_id=self.context.user_id,
            title=spec.display_name,
            goal=f"{spec.display_name}：{persisted_query_summary}",
        )
        task, claimed = claim_agent_task_for_work(
            task_id=task_id,
            session_key=self.context.session_key,
            user_id=self.context.user_id,
            work_type=spec.name,
            query_summary=persisted_query_summary,
        )
        if not claimed:
            return OwnerAgentWorkExecution(
                work_type=spec.name,
                task=task,
                outcome="not_claimed",
                result_summary="注册的只读工作任务未能领取，未执行执行器。",
                response_text="注册的只读工作任务未能领取，未执行执行器。",
            )

        try:
            value = spec.executor(normalized_query)
            raw_result = await value if inspect.isawaitable(value) else value
            sanitized_result = spec.result_sanitizer(raw_result)
        except Exception as exc:
            external_policy_error = (
                exc
                if spec.name == EXTERNAL_READ_REPORT_WORK_TYPE
                and isinstance(exc, ExternalReadPolicyError)
                else None
            )
            safe_error = (
                f"ExternalReadPolicyError: {spec.name} execution failed "
                f"({external_policy_error.category.value})."
                if external_policy_error is not None
                else f"{type(exc).__name__}: {spec.name} execution failed."
            )
            failed_task, _ = fail_agent_task_work(
                task_id=task_id,
                session_key=self.context.session_key,
                user_id=self.context.user_id,
                work_type=spec.name,
                error_summary=safe_error,
            )
            return OwnerAgentWorkExecution(
                work_type=spec.name,
                task=failed_task,
                outcome="failed",
                result_summary=safe_error,
                response_text=(
                    format_external_read_policy_error(external_policy_error)
                    if external_policy_error is not None
                    else format_failure_user_message(
                        safe_error,
                        component=spec.display_name,
                    )
                ),
            )

        result_summary = sanitized_result.persisted_summary
        completed_task, completed = complete_agent_task_work(
            task_id=task_id,
            session_key=self.context.session_key,
            user_id=self.context.user_id,
            work_type=spec.name,
            result=result_summary,
        )
        return OwnerAgentWorkExecution(
            work_type=spec.name,
            task=completed_task,
            outcome="completed" if completed else "not_completed",
            result_summary=result_summary,
            response_text=sanitized_result.response_text,
        )
