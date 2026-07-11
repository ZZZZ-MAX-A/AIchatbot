from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


SYSTEM_DIAGNOSTICS_OVERVIEW_SCOPE = "overview"
SYSTEM_DIAGNOSTICS_OVERVIEW_RESPONSE_LIMIT = 1200
SYSTEM_DIAGNOSTICS_VISION_SCOPE = "vision"
SYSTEM_DIAGNOSTICS_VISION_RESPONSE_LIMIT = 1800
SYSTEM_DIAGNOSTICS_VOICE_SCOPE = "voice"
SYSTEM_DIAGNOSTICS_VOICE_RESPONSE_LIMIT = 1800
SYSTEM_DIAGNOSTICS_MEMORY_RAG_SCOPE = "memory_rag"
SYSTEM_DIAGNOSTICS_MEMORY_RAG_RESPONSE_LIMIT = 1800

VISION_INVOCATION_SCOPE = "vision_invocation"
VISION_INFERENCE_SCOPE = "vision_inference"

VISION_LAYER_CONFIGURATION = "configuration"
VISION_LAYER_SERVICE = "service"
VISION_LAYER_MODEL = "model"
VISION_LAYER_INVOCATION = "invocation"
VISION_LAYER_QUALITY = "quality"
VISION_LAYER_OBSERVATION = "observation"
VISION_LAYER_NONE = "none"

VOICE_LAYER_CONFIGURATION = "configuration"
VOICE_LAYER_ENDPOINT = "endpoint"
VOICE_LAYER_SERVICE = "service"
VOICE_LAYER_MODEL = "model"
VOICE_LAYER_OBSERVATION = "observation"
VOICE_LAYER_NONE = "none"

MEMORY_RAG_LAYER_CONFIGURATION = "configuration"
MEMORY_RAG_LAYER_STORAGE = "storage"
MEMORY_RAG_LAYER_INDEX = "index"
MEMORY_RAG_LAYER_RUNTIME = "runtime"
MEMORY_RAG_LAYER_OBSERVATION = "observation"
MEMORY_RAG_LAYER_NONE = "none"

ZONE_CORE = "core"
ZONE_CHAT = "chat"
ZONE_MAIN_AGENT = "main_agent"
ZONE_MEMORY_RAG = "memory_rag"
ZONE_VISION = "vision"
ZONE_VOICE = "voice"

STATUS_NORMAL = "normal"
STATUS_ATTENTION = "attention"
STATUS_DEGRADED = "degraded"
STATUS_ERROR = "error"
STATUS_OFF_BY_DESIGN = "off_by_design"
STATUS_UNKNOWN = "unknown"

ZONE_ORDER = (
    ZONE_CORE,
    ZONE_CHAT,
    ZONE_MAIN_AGENT,
    ZONE_MEMORY_RAG,
    ZONE_VISION,
    ZONE_VOICE,
)
STATUS_ORDER = (
    STATUS_NORMAL,
    STATUS_ATTENTION,
    STATUS_DEGRADED,
    STATUS_ERROR,
    STATUS_OFF_BY_DESIGN,
    STATUS_UNKNOWN,
)

ZONE_LABELS = {
    ZONE_CORE: "核心运行",
    ZONE_CHAT: "聊天",
    ZONE_MAIN_AGENT: "MainAgent",
    ZONE_MEMORY_RAG: "记忆与RAG",
    ZONE_VISION: "视觉",
    ZONE_VOICE: "语音",
}
STATUS_LABELS = {
    STATUS_NORMAL: "正常",
    STATUS_ATTENTION: "需要关注",
    STATUS_DEGRADED: "降级",
    STATUS_ERROR: "异常",
    STATUS_OFF_BY_DESIGN: "按设计关闭",
    STATUS_UNKNOWN: "未知",
}
VISION_LAYER_LABELS = {
    VISION_LAYER_CONFIGURATION: "配置层",
    VISION_LAYER_SERVICE: "服务层",
    VISION_LAYER_MODEL: "模型层",
    VISION_LAYER_INVOCATION: "调用层",
    VISION_LAYER_QUALITY: "结果质量层",
    VISION_LAYER_OBSERVATION: "观测层",
    VISION_LAYER_NONE: "未发现故障层",
}
VOICE_LAYER_LABELS = {
    VOICE_LAYER_CONFIGURATION: "配置层",
    VOICE_LAYER_ENDPOINT: "地址策略层",
    VOICE_LAYER_SERVICE: "服务层",
    VOICE_LAYER_MODEL: "模型层",
    VOICE_LAYER_OBSERVATION: "观测层",
    VOICE_LAYER_NONE: "未发现故障层",
}
MEMORY_RAG_LAYER_LABELS = {
    MEMORY_RAG_LAYER_CONFIGURATION: "配置层",
    MEMORY_RAG_LAYER_STORAGE: "存储层",
    MEMORY_RAG_LAYER_INDEX: "索引层",
    MEMORY_RAG_LAYER_RUNTIME: "运行观测层",
    MEMORY_RAG_LAYER_OBSERVATION: "证据层",
    MEMORY_RAG_LAYER_NONE: "未发现故障层",
}


def is_loopback_service_url(value: str) -> bool:
    try:
        hostname = (urlparse(str(value).strip()).hostname or "").strip().lower()
    except ValueError:
        return False
    return hostname in {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True)
class CoreZoneEvidence:
    database_ok: bool | None


@dataclass(frozen=True)
class ChatZoneEvidence:
    enabled: bool
    model_configured: bool
    recent_observation_present: bool
    recent_error: bool


@dataclass(frozen=True)
class MainAgentZoneEvidence:
    enabled: bool
    owner_only: bool
    group_allowed: bool
    development_report_registered: bool
    system_report_registered: bool
    owner_write_registered: bool
    owner_write_requires_approval: bool
    owner_write_resume_enabled: bool
    enabled_high_risk_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemoryRagZoneEvidence:
    memory_rag_enabled: bool
    memory_rag_inject_in_chat: bool
    project_doc_rag_enabled: bool
    storage_ok: bool | None
    document_count: int = 0
    embedding_count: int = 0
    pending_count: int = 0
    recent_observation_present: bool = False
    recent_error: bool = False
    recent_attempted: bool = False
    recent_result_count: int = 0


@dataclass(frozen=True)
class VisionZoneEvidence:
    enabled: bool
    service_ok: bool | None
    model_exists: bool | None
    recent_usage_present: bool
    recent_error_count: int = 0
    recent_low_quality_count: int = 0


@dataclass(frozen=True)
class VoiceZoneEvidence:
    enabled: bool
    service_ok: bool | None
    model_loaded: bool | None
    service_is_loopback: bool | None = None
    service_reachable: bool | None = None
    language: str = ""
    recent_candidate_present: bool = False
    recent_generation_observation_present: bool = False
    recent_send_observation_present: bool = False


@dataclass(frozen=True)
class SystemDiagnosticsOverviewEvidence:
    core: CoreZoneEvidence
    chat: ChatZoneEvidence
    main_agent: MainAgentZoneEvidence
    memory_rag: MemoryRagZoneEvidence
    vision: VisionZoneEvidence
    voice: VoiceZoneEvidence
    local_probe_count: int = 0


@dataclass(frozen=True)
class DiagnosticZoneStatus:
    zone: str
    status: str
    headline: str
    recommended_scope: str = ""


@dataclass(frozen=True)
class SystemDiagnosticsReportPayload:
    scope: str
    overall_status: str
    zones: tuple[DiagnosticZoneStatus, ...]
    primary_recommended_scope: str
    local_probe_count: int
    external_request_count: int
    deep_probe_count: int
    repair_action_count: int
    high_risk_boundary_ok: bool
    report_text: str

    @property
    def status_counts(self) -> dict[str, int]:
        counts = {status: 0 for status in STATUS_ORDER}
        for zone in self.zones:
            counts[zone.status] += 1
        return counts


@dataclass(frozen=True)
class VisionDiagnosticsReportPayload:
    scope: str
    zone_status: DiagnosticZoneStatus
    fault_layer: str
    recommended_scope: str
    local_probe_count: int
    external_request_count: int
    deep_probe_count: int
    repair_action_count: int
    report_text: str


@dataclass(frozen=True)
class VoiceDiagnosticsReportPayload:
    scope: str
    zone_status: DiagnosticZoneStatus
    fault_layer: str
    recommended_scope: str
    local_probe_count: int
    external_request_count: int
    deep_probe_count: int
    repair_action_count: int
    report_text: str


@dataclass(frozen=True)
class MemoryRagDiagnosticsReportPayload:
    scope: str
    zone_status: DiagnosticZoneStatus
    fault_layer: str
    recommended_scope: str
    local_probe_count: int
    external_request_count: int
    deep_probe_count: int
    repair_action_count: int
    report_text: str


SystemDiagnosticsPayload = (
    SystemDiagnosticsReportPayload
    | VisionDiagnosticsReportPayload
    | VoiceDiagnosticsReportPayload
    | MemoryRagDiagnosticsReportPayload
)


def _zone(zone: str, status: str, headline: str) -> DiagnosticZoneStatus:
    recommended_scope = zone if status in {
        STATUS_ATTENTION,
        STATUS_DEGRADED,
        STATUS_ERROR,
        STATUS_UNKNOWN,
    } else ""
    return DiagnosticZoneStatus(
        zone=zone,
        status=status,
        headline=headline,
        recommended_scope=recommended_scope,
    )


def evaluate_core_zone(evidence: CoreZoneEvidence) -> DiagnosticZoneStatus:
    if evidence.database_ok is False:
        return _zone(ZONE_CORE, STATUS_ERROR, "数据库只读检查失败。")
    if evidence.database_ok is None:
        return _zone(ZONE_CORE, STATUS_UNKNOWN, "数据库只读状态无法确认。")
    return _zone(ZONE_CORE, STATUS_NORMAL, "当前任务入口和数据库只读检查通过。")


def evaluate_chat_zone(evidence: ChatZoneEvidence) -> DiagnosticZoneStatus:
    if not evidence.enabled:
        return _zone(ZONE_CHAT, STATUS_OFF_BY_DESIGN, "私聊和群聊均已关闭。")
    if not evidence.model_configured:
        return _zone(ZONE_CHAT, STATUS_DEGRADED, "聊天已开启，但模型配置不完整。")
    if evidence.recent_error:
        return _zone(ZONE_CHAT, STATUS_ATTENTION, "模型配置完整，但最近聊天观测记录了错误。")
    if evidence.recent_observation_present:
        return _zone(ZONE_CHAT, STATUS_NORMAL, "模型配置完整，最近聊天观测未记录错误。")
    return _zone(ZONE_CHAT, STATUS_NORMAL, "模型配置完整，暂无近期聊天观测。")


def evaluate_main_agent_zone(
    evidence: MainAgentZoneEvidence,
) -> DiagnosticZoneStatus:
    if not evidence.enabled:
        return _zone(ZONE_MAIN_AGENT, STATUS_ERROR, "MainAgent 当前关闭。")
    missing_work_types: list[str] = []
    if not evidence.development_report_registered:
        missing_work_types.append("development_context_report")
    if not evidence.system_report_registered:
        missing_work_types.append("system_diagnostics_report")
    if missing_work_types:
        return _zone(
            ZONE_MAIN_AGENT,
            STATUS_DEGRADED,
            "正式只读工作未完整注册：" + "、".join(missing_work_types) + "。",
        )
    if not evidence.owner_only or evidence.group_allowed:
        return _zone(
            ZONE_MAIN_AGENT,
            STATUS_ATTENTION,
            "主人私聊专用策略与当前只读基线不一致。",
        )
    if not evidence.owner_write_registered:
        return _zone(
            ZONE_MAIN_AGENT,
            STATUS_ATTENTION,
            "主人本地写工具未注册，当前审批写能力不可用。",
        )
    if (
        not evidence.owner_write_requires_approval
        or not evidence.owner_write_resume_enabled
    ):
        return _zone(
            ZONE_MAIN_AGENT,
            STATUS_ERROR,
            "主人本地写工具未保持审批和受控恢复边界。",
        )
    if evidence.enabled_high_risk_capabilities:
        return _zone(
            ZONE_MAIN_AGENT,
            STATUS_ATTENTION,
            "高风险能力开关存在开启项："
            + "、".join(evidence.enabled_high_risk_capabilities)
            + "。",
        )
    return _zone(
        ZONE_MAIN_AGENT,
        STATUS_NORMAL,
        "主人私聊、两个正式只读工作和审批写边界正常。",
    )


def evaluate_memory_rag_zone(
    evidence: MemoryRagZoneEvidence,
) -> DiagnosticZoneStatus:
    if not evidence.memory_rag_enabled and not evidence.project_doc_rag_enabled:
        return _zone(
            ZONE_MEMORY_RAG,
            STATUS_OFF_BY_DESIGN,
            "MemoryRAG 和 ProjectDocRAG 均已关闭。",
        )

    if evidence.memory_rag_enabled:
        if evidence.storage_ok is False:
            return _zone(
                ZONE_MEMORY_RAG,
                STATUS_DEGRADED,
                "MemoryRAG 已开启，但索引统计读取失败。",
            )
        if evidence.storage_ok is None:
            return _zone(
                ZONE_MEMORY_RAG,
                STATUS_UNKNOWN,
                "MemoryRAG 已开启，但索引状态未确认。",
            )
        if evidence.pending_count > 0:
            return _zone(
                ZONE_MEMORY_RAG,
                STATUS_ATTENTION,
                f"MemoryRAG 有 {evidence.pending_count} 条待索引内容。",
            )
        if evidence.embedding_count < evidence.document_count:
            missing = evidence.document_count - evidence.embedding_count
            return _zone(
                ZONE_MEMORY_RAG,
                STATUS_ATTENTION,
                f"MemoryRAG 有 {missing} 条活动文档缺少向量。",
            )
        if evidence.recent_error:
            return _zone(
                ZONE_MEMORY_RAG,
                STATUS_ATTENTION,
                "索引统计正常，但最近 MemoryRAG 观测记录了错误。",
            )
        injection = "开启" if evidence.memory_rag_inject_in_chat else "关闭"
        return _zone(
            ZONE_MEMORY_RAG,
            STATUS_NORMAL,
            f"MemoryRAG 索引无待处理项，聊天注入{injection}。",
        )

    return _zone(
        ZONE_MEMORY_RAG,
        STATUS_NORMAL,
        "MemoryRAG 关闭；ProjectDocRAG 边界正常，本次未执行检索健康检查。",
    )


def evaluate_vision_zone(evidence: VisionZoneEvidence) -> DiagnosticZoneStatus:
    if not evidence.enabled:
        return _zone(ZONE_VISION, STATUS_OFF_BY_DESIGN, "视觉功能已关闭。")
    if evidence.service_ok is None:
        return _zone(
            ZONE_VISION,
            STATUS_UNKNOWN,
            "视觉已开启，但本次未确认本地 Ollama 状态。",
        )
    if not evidence.service_ok:
        return _zone(ZONE_VISION, STATUS_DEGRADED, "视觉已开启，但 Ollama 服务不可用。")
    if evidence.model_exists is False:
        return _zone(ZONE_VISION, STATUS_DEGRADED, "Ollama 在线，但视觉模型不可用。")
    if evidence.model_exists is None:
        return _zone(ZONE_VISION, STATUS_UNKNOWN, "Ollama 在线，但模型状态无法确认。")
    if evidence.recent_error_count > 0:
        return _zone(
            ZONE_VISION,
            STATUS_ATTENTION,
            "服务在线、模型可用，但最近视觉使用记录了错误。",
        )
    if evidence.recent_low_quality_count > 0:
        return _zone(
            ZONE_VISION,
            STATUS_ATTENTION,
            "服务在线、模型可用，但最近视觉结果被判为低质量。",
        )
    if evidence.recent_usage_present:
        return _zone(ZONE_VISION, STATUS_NORMAL, "服务在线、模型可用，最近使用未记录错误。")
    return _zone(ZONE_VISION, STATUS_NORMAL, "服务在线、模型可用，暂无近期使用证据。")


def evaluate_voice_zone(evidence: VoiceZoneEvidence) -> DiagnosticZoneStatus:
    if not evidence.enabled:
        return _zone(ZONE_VOICE, STATUS_OFF_BY_DESIGN, "语音输出已关闭。")
    if evidence.service_ok is None:
        return _zone(ZONE_VOICE, STATUS_UNKNOWN, "语音已开启，但本地服务状态未确认。")
    if not evidence.service_ok:
        return _zone(ZONE_VOICE, STATUS_DEGRADED, "语音已开启，但 TTS 服务不可用。")
    if evidence.model_loaded is False:
        return _zone(ZONE_VOICE, STATUS_ATTENTION, "TTS 服务在线，但模型尚未加载。")
    if evidence.model_loaded is None:
        return _zone(ZONE_VOICE, STATUS_UNKNOWN, "TTS 服务在线，但模型加载状态无法确认。")
    return _zone(ZONE_VOICE, STATUS_NORMAL, "TTS 服务在线。")


def _overall_status(zones: tuple[DiagnosticZoneStatus, ...]) -> str:
    zone_statuses = {zone.status for zone in zones}
    if STATUS_ERROR in zone_statuses:
        return STATUS_ERROR
    if STATUS_DEGRADED in zone_statuses:
        return STATUS_DEGRADED
    if STATUS_ATTENTION in zone_statuses or STATUS_UNKNOWN in zone_statuses:
        return STATUS_ATTENTION
    return STATUS_NORMAL


def _primary_scope(zones: tuple[DiagnosticZoneStatus, ...]) -> str:
    severity_order = (
        STATUS_ERROR,
        STATUS_DEGRADED,
        STATUS_ATTENTION,
        STATUS_UNKNOWN,
    )
    by_zone = {zone.zone: zone for zone in zones}
    for severity in severity_order:
        for zone_name in ZONE_ORDER:
            zone = by_zone[zone_name]
            if zone.status == severity:
                return zone.recommended_scope
    return ""


def _status_count_text(payload: SystemDiagnosticsReportPayload) -> str:
    counts = payload.status_counts
    parts = [
        f"{STATUS_LABELS[status]} {counts[status]}"
        for status in STATUS_ORDER
        if counts[status]
    ]
    return "｜".join(parts)


def format_system_diagnostics_overview(
    payload: SystemDiagnosticsReportPayload,
) -> str:
    lines = [
        f"系统诊断：{STATUS_LABELS[payload.overall_status]}",
        f"大区状态：{_status_count_text(payload)}",
    ]

    problem_zones = [
        zone
        for zone in payload.zones
        if zone.status in {
            STATUS_ATTENTION,
            STATUS_DEGRADED,
            STATUS_ERROR,
            STATUS_UNKNOWN,
        }
    ]
    if problem_zones:
        lines.extend(["", "需关注区域："])
        for zone in problem_zones:
            lines.append(
                f"- {ZONE_LABELS[zone.zone]}（{STATUS_LABELS[zone.status]}）："
                f"{zone.headline}"
            )

    normal_labels = [
        ZONE_LABELS[zone.zone]
        for zone in payload.zones
        if zone.status == STATUS_NORMAL
    ]
    off_labels = [
        ZONE_LABELS[zone.zone]
        for zone in payload.zones
        if zone.status == STATUS_OFF_BY_DESIGN
    ]
    if normal_labels:
        lines.append("")
        lines.append("正常：" + "、".join(normal_labels) + "。")
    if off_labels:
        lines.append("按设计关闭：" + "、".join(off_labels) + "。")

    if payload.high_risk_boundary_ok:
        lines.append(
            "高风险能力：Agent Web、Shell、任意文件写入和外部写入未注册；"
            "主人本地写保持审批门控。"
        )
    else:
        lines.append("高风险能力：存在开启项，已纳入 MainAgent 区判断。")

    if payload.primary_recommended_scope:
        lines.extend(
            [
                "",
                "建议优先排查："
                + ZONE_LABELS[payload.primary_recommended_scope]
                + "区。",
            ]
        )
        if payload.primary_recommended_scope == ZONE_VISION:
            lines.append(
                "如需详情，请由主人显式执行 /agent 执行系统诊断任务：视觉；"
                "本次未自动创建区域详情任务。"
            )
        elif payload.primary_recommended_scope == ZONE_MEMORY_RAG:
            lines.append(
                "如需详情，请由主人显式执行 /agent 执行系统诊断任务：记忆与RAG；"
                "本次未自动创建区域详情任务。"
            )
        elif payload.primary_recommended_scope == ZONE_VOICE:
            lines.append(
                "如需详情，请由主人显式执行 /agent 执行系统诊断任务：语音；"
                "本次未自动创建区域详情任务。"
            )
        else:
            lines.append("该区域详情尚未注册，本次未自动创建区域详情任务。")
    else:
        lines.extend(["", "未发现需要深入排查的大区。"])

    lines.extend(
        [
            f"本次使用被动证据和 {payload.local_probe_count} 项廉价本地检查。",
            "未执行模型推理、embedding/RAG 召回、外部请求、自动重试或修复。",
        ]
    )
    return "\n".join(lines)[:SYSTEM_DIAGNOSTICS_OVERVIEW_RESPONSE_LIMIT].rstrip()


def build_system_diagnostics_overview(
    evidence: SystemDiagnosticsOverviewEvidence,
) -> SystemDiagnosticsReportPayload:
    if evidence.local_probe_count < 0:
        raise ValueError("local probe count must be non-negative")
    zones = (
        evaluate_core_zone(evidence.core),
        evaluate_chat_zone(evidence.chat),
        evaluate_main_agent_zone(evidence.main_agent),
        evaluate_memory_rag_zone(evidence.memory_rag),
        evaluate_vision_zone(evidence.vision),
        evaluate_voice_zone(evidence.voice),
    )
    enabled_high_risk = evidence.main_agent.enabled_high_risk_capabilities
    payload = SystemDiagnosticsReportPayload(
        scope=SYSTEM_DIAGNOSTICS_OVERVIEW_SCOPE,
        overall_status=_overall_status(zones),
        zones=zones,
        primary_recommended_scope=_primary_scope(zones),
        local_probe_count=evidence.local_probe_count,
        external_request_count=0,
        deep_probe_count=0,
        repair_action_count=0,
        high_risk_boundary_ok=not enabled_high_risk,
        report_text="",
    )
    return SystemDiagnosticsReportPayload(
        scope=payload.scope,
        overall_status=payload.overall_status,
        zones=payload.zones,
        primary_recommended_scope=payload.primary_recommended_scope,
        local_probe_count=payload.local_probe_count,
        external_request_count=payload.external_request_count,
        deep_probe_count=payload.deep_probe_count,
        repair_action_count=payload.repair_action_count,
        high_risk_boundary_ok=payload.high_risk_boundary_ok,
        report_text=format_system_diagnostics_overview(payload),
    )


def _vision_detail_judgment(fault_layer: str) -> str:
    judgments = {
        VISION_LAYER_CONFIGURATION: (
            "视觉功能按设计关闭，未继续检查服务、模型或最近使用。"
        ),
        VISION_LAYER_SERVICE: (
            "当前证据停在服务层；先在系统外确认本地 Ollama 地址、进程和端口，"
            "再重新执行视觉区详情。本次不启动或重启服务。"
        ),
        VISION_LAYER_MODEL: (
            "Ollama 服务已可访问，但模型层尚未通过；先在系统外确认已配置视觉模型"
            "是否已安装。本次不拉取模型。"
        ),
        VISION_LAYER_INVOCATION: (
            "服务和模型可用，问题更可能位于图片上下文或视觉调用过程。"
        ),
        VISION_LAYER_QUALITY: (
            "服务和模型可用，最近问题更可能位于推理结果质量，而不是服务连通性。"
        ),
        VISION_LAYER_OBSERVATION: (
            "配置、服务和模型可用，但暂无近期使用证据；这不等于已完成端到端验证。"
        ),
        VISION_LAYER_NONE: (
            "配置、服务、模型和最近使用观测均未显示需要深入排查的问题。"
        ),
    }
    return judgments[fault_layer]


def format_vision_diagnostics_report(
    payload: VisionDiagnosticsReportPayload,
    evidence: VisionZoneEvidence,
) -> str:
    lines = [
        f"视觉区诊断：{STATUS_LABELS[payload.zone_status.status]}",
        f"定位层级：{VISION_LAYER_LABELS[payload.fault_layer]}",
        "",
        "状态链：",
        f"- 功能配置：{'开启' if evidence.enabled else '关闭'}。",
    ]

    if evidence.enabled:
        if evidence.service_ok is None:
            lines.append("- Ollama 服务：未验证（只允许检查本机 loopback 地址）。")
        elif evidence.service_ok:
            lines.append("- Ollama 服务：在线。")
        else:
            lines.append("- Ollama 服务：不可用。")

    if evidence.enabled and evidence.service_ok:
        if evidence.model_exists is None:
            lines.append("- 视觉模型：状态无法确认。")
        elif evidence.model_exists:
            lines.append("- 视觉模型：可用。")
        else:
            lines.append("- 视觉模型：不可用。")

    if evidence.enabled and evidence.service_ok and evidence.model_exists:
        if evidence.recent_error_count > 0:
            lines.append("- 最近使用：记录到错误。")
        elif evidence.recent_low_quality_count > 0:
            lines.append("- 最近使用：记录到低质量结果。")
        elif evidence.recent_usage_present:
            lines.append("- 最近使用：有近期记录，未记录错误或低质量结果。")
        else:
            lines.append("- 最近使用：暂无近期使用证据。")

    lines.extend(
        [
            "",
            "初步判断：",
            _vision_detail_judgment(payload.fault_layer),
            "",
        ]
    )
    if payload.recommended_scope:
        lines.extend(
            [
                f"建议下一范围：{payload.recommended_scope}。",
                "该深度范围尚未注册，本次未创建下一级任务或执行深度探针。",
            ]
        )
    else:
        lines.append("建议下一范围：无；本次不自动扩大诊断范围。")

    lines.extend(
        [
            f"本次使用被动证据和 {payload.local_probe_count} 项廉价本地检查。",
            "未执行真实视觉推理、测试图片、外部请求、自动重试或修复。",
        ]
    )
    return "\n".join(lines)[:SYSTEM_DIAGNOSTICS_VISION_RESPONSE_LIMIT].rstrip()


def build_vision_diagnostics_report(
    evidence: VisionZoneEvidence,
    *,
    local_probe_count: int = 0,
) -> VisionDiagnosticsReportPayload:
    for count in (
        local_probe_count,
        evidence.recent_error_count,
        evidence.recent_low_quality_count,
    ):
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("vision diagnostics count must be non-negative")

    zone_status = evaluate_vision_zone(evidence)
    recommended_scope = ""
    if not evidence.enabled:
        fault_layer = VISION_LAYER_CONFIGURATION
    elif evidence.service_ok is None or not evidence.service_ok:
        fault_layer = VISION_LAYER_SERVICE
    elif evidence.model_exists is None or not evidence.model_exists:
        fault_layer = VISION_LAYER_MODEL
    elif evidence.recent_error_count > 0:
        fault_layer = VISION_LAYER_INVOCATION
        recommended_scope = VISION_INVOCATION_SCOPE
    elif evidence.recent_low_quality_count > 0:
        fault_layer = VISION_LAYER_QUALITY
        recommended_scope = VISION_INFERENCE_SCOPE
    elif evidence.recent_usage_present:
        fault_layer = VISION_LAYER_NONE
    else:
        fault_layer = VISION_LAYER_OBSERVATION

    payload = VisionDiagnosticsReportPayload(
        scope=SYSTEM_DIAGNOSTICS_VISION_SCOPE,
        zone_status=zone_status,
        fault_layer=fault_layer,
        recommended_scope=recommended_scope,
        local_probe_count=local_probe_count,
        external_request_count=0,
        deep_probe_count=0,
        repair_action_count=0,
        report_text="",
    )
    return VisionDiagnosticsReportPayload(
        scope=payload.scope,
        zone_status=payload.zone_status,
        fault_layer=payload.fault_layer,
        recommended_scope=payload.recommended_scope,
        local_probe_count=payload.local_probe_count,
        external_request_count=payload.external_request_count,
        deep_probe_count=payload.deep_probe_count,
        repair_action_count=payload.repair_action_count,
        report_text=format_vision_diagnostics_report(payload, evidence),
    )


def _voice_detail_judgment(fault_layer: str) -> str:
    judgments = {
        VOICE_LAYER_CONFIGURATION: (
            "语音功能按设计关闭，未继续检查服务、模型、生成或发送观测。"
        ),
        VOICE_LAYER_ENDPOINT: (
            "TTS 地址不是本机 loopback，本次按安全边界未主动访问服务。"
        ),
        VOICE_LAYER_SERVICE: (
            "当前证据停在服务层；本次不启动、重启或修复 TTS 服务。"
        ),
        VOICE_LAYER_MODEL: (
            "TTS 服务已可访问，但 IndexTTS2 加载状态尚未通过；本次不加载或下载模型。"
        ),
        VOICE_LAYER_OBSERVATION: (
            "配置、服务和模型状态未显示硬错误，但缺少最近生成或发送证据；"
            "这不等于已完成端到端验证。"
        ),
        VOICE_LAYER_NONE: (
            "配置、服务、模型和最近安全发送观测均未显示需要深入排查的问题。"
        ),
    }
    return judgments[fault_layer]


def format_voice_diagnostics_report(
    payload: VoiceDiagnosticsReportPayload,
    evidence: VoiceZoneEvidence,
) -> str:
    lines = [
        f"语音区诊断：{STATUS_LABELS[payload.zone_status.status]}",
        f"定位层级：{VOICE_LAYER_LABELS[payload.fault_layer]}",
        "",
        "状态链：",
        f"- 功能配置：{'开启' if evidence.enabled else '关闭'}。",
    ]
    if evidence.enabled:
        if evidence.service_is_loopback is False:
            lines.append("- TTS 地址：非本机地址，本次未主动访问。")
            lines.append(
                "- 后续状态：按安全边界未验证健康接口、IndexTTS2、语言和运行观测。"
            )
        elif evidence.service_is_loopback:
            lines.append("- TTS 地址：本机 loopback。")
        else:
            lines.append("- TTS 地址：无法确认。")

    if evidence.enabled and evidence.service_is_loopback:
        if evidence.service_reachable is False:
            lines.append("- 本地服务：不可用。")
            lines.append("- 健康接口：未继续检查（本地服务不可达）。")
        elif evidence.service_reachable is True:
            lines.append("- 本地服务：在线。")
            lines.append(
                f"- 健康接口：{'正常' if evidence.service_ok else '异常'}。"
            )
        else:
            lines.append("- 本地服务：未验证。")
            lines.append("- 健康接口：未继续检查（服务可达性未确认）。")

    if evidence.enabled and evidence.service_ok:
        if evidence.model_loaded is True:
            lines.append("- IndexTTS2：已加载。")
        elif evidence.model_loaded is False:
            lines.append("- IndexTTS2：未加载。")
        else:
            lines.append("- IndexTTS2：状态无法确认。")
        lines.append(f"- 语言：{evidence.language or '未知'}。")
    elif evidence.enabled and evidence.service_is_loopback:
        reason = (
            "本地服务不可达"
            if evidence.service_reachable is False
            else "健康接口未通过"
            if evidence.service_reachable is True
            else "服务可达性未确认"
        )
        lines.append(f"- IndexTTS2：未继续判断（{reason}）。")
        lines.append(f"- 语言：未继续判断（{reason}）。")

    if evidence.enabled and evidence.service_ok and evidence.model_loaded:
        lines.append(
            "- 最近语音候选："
            + ("存在。" if evidence.recent_candidate_present else "无。")
        )
        lines.append(
            "- 最近生成观测："
            + (
                "存在安全成功证据。"
                if evidence.recent_generation_observation_present
                else "暂无结构化成功证据。"
            )
        )
        lines.append(
            "- 最近发送观测："
            + (
                "存在安全成功证据。"
                if evidence.recent_send_observation_present
                else "暂无结构化成功证据。"
            )
        )
    elif evidence.enabled and evidence.service_ok:
        lines.append("- 最近生成观测：未继续判断（模型加载状态未通过）。")
        lines.append("- 最近发送观测：未继续判断（模型加载状态未通过）。")
    elif evidence.enabled and evidence.service_is_loopback:
        reason = (
            "本地服务不可达"
            if evidence.service_reachable is False
            else "健康接口未通过"
            if evidence.service_reachable is True
            else "服务可达性未确认"
        )
        lines.append(f"- 最近生成观测：未继续判断（{reason}）。")
        lines.append(f"- 最近发送观测：未继续判断（{reason}）。")

    lines.extend(
        [
            "",
            "初步判断：",
            _voice_detail_judgment(payload.fault_layer),
            "",
            "建议下一范围：无；本次不自动扩大诊断范围。",
            f"本次使用被动证据和 {payload.local_probe_count} 项廉价本地检查。",
            "未生成测试语音、创建音频文件、发送 QQ、重启服务、加载模型、"
            "下载模型、修改配置、自动重试或修复。",
        ]
    )
    return "\n".join(lines)[:SYSTEM_DIAGNOSTICS_VOICE_RESPONSE_LIMIT].rstrip()


def build_voice_diagnostics_report(
    evidence: VoiceZoneEvidence,
    *,
    local_probe_count: int = 0,
) -> VoiceDiagnosticsReportPayload:
    if (
        not isinstance(local_probe_count, int)
        or isinstance(local_probe_count, bool)
        or local_probe_count < 0
    ):
        raise ValueError("voice diagnostics count must be non-negative")

    zone_status = evaluate_voice_zone(evidence)
    if not evidence.enabled:
        fault_layer = VOICE_LAYER_CONFIGURATION
    elif evidence.service_is_loopback is False:
        fault_layer = VOICE_LAYER_ENDPOINT
    elif evidence.service_ok is None or not evidence.service_ok:
        fault_layer = VOICE_LAYER_SERVICE
    elif evidence.model_loaded is None or not evidence.model_loaded:
        fault_layer = VOICE_LAYER_MODEL
    elif not evidence.recent_send_observation_present:
        fault_layer = VOICE_LAYER_OBSERVATION
    else:
        fault_layer = VOICE_LAYER_NONE

    payload = VoiceDiagnosticsReportPayload(
        scope=SYSTEM_DIAGNOSTICS_VOICE_SCOPE,
        zone_status=zone_status,
        fault_layer=fault_layer,
        recommended_scope="",
        local_probe_count=local_probe_count,
        external_request_count=0,
        deep_probe_count=0,
        repair_action_count=0,
        report_text="",
    )
    return VoiceDiagnosticsReportPayload(
        scope=payload.scope,
        zone_status=payload.zone_status,
        fault_layer=payload.fault_layer,
        recommended_scope=payload.recommended_scope,
        local_probe_count=payload.local_probe_count,
        external_request_count=payload.external_request_count,
        deep_probe_count=payload.deep_probe_count,
        repair_action_count=payload.repair_action_count,
        report_text=format_voice_diagnostics_report(payload, evidence),
    )


def _memory_rag_detail_judgment(fault_layer: str) -> str:
    judgments = {
        MEMORY_RAG_LAYER_CONFIGURATION: (
            "MemoryRAG 与 ProjectDocRAG 均按设计关闭，未继续读取索引统计。"
        ),
        MEMORY_RAG_LAYER_STORAGE: (
            "MemoryRAG 已开启，但本地索引统计无法读取；本次不修改数据库或重建索引。"
        ),
        MEMORY_RAG_LAYER_INDEX: (
            "本地索引存在待处理内容或缺失向量；本次只报告现象，不执行 embedding 或重建。"
        ),
        MEMORY_RAG_LAYER_RUNTIME: (
            "索引统计可读，但最近 MemoryRAG 安全观测记录了运行错误。"
        ),
        MEMORY_RAG_LAYER_OBSERVATION: (
            "配置与索引统计未显示硬错误，但暂无近期 MemoryRAG 运行证据；"
            "这不等于已完成语义召回验证。"
        ),
        MEMORY_RAG_LAYER_NONE: (
            "配置、索引统计和最近安全观测未显示需要深入排查的问题。"
        ),
    }
    return judgments[fault_layer]


def format_memory_rag_diagnostics_report(
    payload: MemoryRagDiagnosticsReportPayload,
    evidence: MemoryRagZoneEvidence,
) -> str:
    lines = [
        f"记忆与RAG区诊断：{STATUS_LABELS[payload.zone_status.status]}",
        f"定位层级：{MEMORY_RAG_LAYER_LABELS[payload.fault_layer]}",
        "",
        "状态链：",
        f"- MemoryRAG：{'开启' if evidence.memory_rag_enabled else '关闭'}。",
        f"- 普通聊天注入：{'开启' if evidence.memory_rag_inject_in_chat else '关闭'}。",
        f"- ProjectDocRAG：{'开启' if evidence.project_doc_rag_enabled else '关闭'}。",
    ]

    if evidence.memory_rag_enabled:
        if evidence.storage_ok is True:
            lines.extend(
                [
                    "- 本地索引统计：可读。",
                    f"- 活动文档：{evidence.document_count}。",
                    f"- 向量记录：{evidence.embedding_count}。",
                    f"- 待索引内容：{evidence.pending_count}。",
                ]
            )
        elif evidence.storage_ok is False:
            lines.append("- 本地索引统计：读取失败。")
        else:
            lines.append("- 本地索引统计：未确认。")

    if evidence.memory_rag_enabled and evidence.storage_ok:
        missing = max(evidence.document_count - evidence.embedding_count, 0)
        lines.append(f"- 缺少向量的活动文档：{missing}。")
        if evidence.recent_error:
            lines.append("- 最近运行观测：记录到错误。")
        elif evidence.recent_observation_present:
            attempted = "是" if evidence.recent_attempted else "否"
            lines.append(
                f"- 最近运行观测：存在；尝试召回={attempted}，"
                f"结果数={evidence.recent_result_count}。"
            )
        else:
            lines.append("- 最近运行观测：暂无。")

    lines.extend(
        [
            "",
            "初步判断：",
            _memory_rag_detail_judgment(payload.fault_layer),
            "",
            "建议下一范围：无；本次不自动扩大诊断范围。",
            f"本次使用被动证据和 {payload.local_probe_count} 项廉价本地检查。",
            "未执行 embedding 自检、语义召回、ProjectDocRAG 正文读取、索引重建、"
            "数据库写入、自动重试或修复。",
        ]
    )
    return "\n".join(lines)[:SYSTEM_DIAGNOSTICS_MEMORY_RAG_RESPONSE_LIMIT].rstrip()


def build_memory_rag_diagnostics_report(
    evidence: MemoryRagZoneEvidence,
    *,
    local_probe_count: int = 0,
) -> MemoryRagDiagnosticsReportPayload:
    counts = (
        local_probe_count,
        evidence.document_count,
        evidence.embedding_count,
        evidence.pending_count,
        evidence.recent_result_count,
    )
    if any(
        not isinstance(count, int) or isinstance(count, bool) or count < 0
        for count in counts
    ):
        raise ValueError("memory RAG diagnostics count must be non-negative")

    zone_status = evaluate_memory_rag_zone(evidence)
    missing = max(evidence.document_count - evidence.embedding_count, 0)
    if not evidence.memory_rag_enabled and not evidence.project_doc_rag_enabled:
        fault_layer = MEMORY_RAG_LAYER_CONFIGURATION
    elif evidence.memory_rag_enabled and evidence.storage_ok is not True:
        fault_layer = MEMORY_RAG_LAYER_STORAGE
    elif evidence.memory_rag_enabled and (evidence.pending_count > 0 or missing > 0):
        fault_layer = MEMORY_RAG_LAYER_INDEX
    elif evidence.memory_rag_enabled and evidence.recent_error:
        fault_layer = MEMORY_RAG_LAYER_RUNTIME
    elif evidence.memory_rag_enabled and not evidence.recent_observation_present:
        fault_layer = MEMORY_RAG_LAYER_OBSERVATION
    else:
        fault_layer = MEMORY_RAG_LAYER_NONE

    payload = MemoryRagDiagnosticsReportPayload(
        scope=SYSTEM_DIAGNOSTICS_MEMORY_RAG_SCOPE,
        zone_status=zone_status,
        fault_layer=fault_layer,
        recommended_scope="",
        local_probe_count=local_probe_count,
        external_request_count=0,
        deep_probe_count=0,
        repair_action_count=0,
        report_text="",
    )
    return MemoryRagDiagnosticsReportPayload(
        scope=payload.scope,
        zone_status=payload.zone_status,
        fault_layer=payload.fault_layer,
        recommended_scope=payload.recommended_scope,
        local_probe_count=payload.local_probe_count,
        external_request_count=payload.external_request_count,
        deep_probe_count=payload.deep_probe_count,
        repair_action_count=payload.repair_action_count,
        report_text=format_memory_rag_diagnostics_report(payload, evidence),
    )
