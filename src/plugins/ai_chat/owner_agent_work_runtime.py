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


WorkResultSanitizer = Callable[[object], SanitizedAgentWorkResult]


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


def format_owner_agent_work_execution(execution: OwnerAgentWorkExecution) -> str:
    task = execution.task
    is_system_diagnostics = execution.work_type == SYSTEM_DIAGNOSTICS_REPORT_WORK_TYPE
    task_label = "系统诊断任务" if is_system_diagnostics else "研发上下文任务"
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
        else "边界：只执行已注册的只读研发上下文报告；未开放 shell、文件写入、Web 写操作或自动重试。"
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
    )


class OwnerAgentWorkRuntime:
    """Runs registered read-only work types without any QQ dependency."""

    def __init__(
        self,
        *,
        context: OwnerAgentWorkContext,
        development_context_report_executor: WorkExecutor,
        system_diagnostics_report_executor: WorkExecutor,
    ) -> None:
        self.context = context
        specs = (
            _development_context_report_spec(development_context_report_executor),
            _system_diagnostics_report_spec(system_diagnostics_report_executor),
        )
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
        task_id = create_agent_task(
            session_key=self.context.session_key,
            user_id=self.context.user_id,
            title=spec.display_name,
            goal=f"{spec.display_name}：{normalized_query}",
        )
        task, claimed = claim_agent_task_for_work(
            task_id=task_id,
            session_key=self.context.session_key,
            user_id=self.context.user_id,
            work_type=spec.name,
            query_summary=normalized_query,
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
            safe_error = f"{type(exc).__name__}: {spec.name} execution failed."
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
                response_text=safe_error,
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
