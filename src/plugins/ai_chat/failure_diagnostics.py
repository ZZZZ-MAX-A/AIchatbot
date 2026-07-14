from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Iterable


class FailureCategory(str, Enum):
    CONFIGURATION = "configuration"
    MODEL = "model"
    PERMISSION = "permission"
    NETWORK = "network"
    DATA = "data"


CATEGORY_LABELS = {
    FailureCategory.CONFIGURATION: "配置问题",
    FailureCategory.MODEL: "模型问题",
    FailureCategory.PERMISSION: "权限问题",
    FailureCategory.NETWORK: "网络问题",
    FailureCategory.DATA: "数据问题",
}

CATEGORY_ACTIONS = {
    FailureCategory.CONFIGURATION: "检查对应功能开关、必填配置、服务地址和模型名；系统未自动修改配置。",
    FailureCategory.MODEL: "检查模型是否存在、服务额度、限流和响应格式；避免立即连续重试。",
    FailureCategory.PERMISSION: "检查 API 鉴权、主人权限或审批状态；系统不会绕过权限继续执行。",
    FailureCategory.NETWORK: "检查本地服务、网络、代理、DNS 和超时设置；先确认服务可达再重试。",
    FailureCategory.DATA: "检查数据库、索引、文件完整性和输入格式；在确认数据状态前不要覆盖原文件。",
}

_SECRET_PATTERNS = (
    (re.compile(r"(?i)\b(?:sk-|ak-)[A-Za-z0-9_-]{8,}\b"), "[redacted-key]"),
    (
        re.compile(
            r"(?i)\b(?:api[_ -]?key|token|password|passwd|secret)\s*[:=：]\s*\S+"
        ),
        "[redacted-key]",
    ),
    (re.compile(r"https?://\S+", re.IGNORECASE), "[redacted-url]"),
)

_PERMISSION_MARKERS = (
    "401",
    "403",
    "unauthorized",
    "forbidden",
    "auth_failed",
    "authentication",
    "permission denied",
    "access denied",
    "approval required",
    "owner only",
    "owner_only",
)
_CONFIGURATION_MARKERS = (
    "invalid_config",
    "configuration error",
    "config error",
    "not configured",
    "missing config",
    "missing api key",
    "invalid base url",
    "invalid url",
    "unsupported scope",
    "unsupported command",
)
_NETWORK_MARKERS = (
    "timeout",
    "timed out",
    "connection",
    "connecterror",
    "network",
    "dns",
    "proxy",
    "tls",
    "ssl",
    "remoteprotocolerror",
    "service unavailable",
    "502",
    "503",
    "504",
)
_MODEL_MARKERS = (
    "404",
    "429",
    "rate limit",
    "rate_limited",
    "quota",
    "model_not_found",
    "model not found",
    "model unavailable",
    "empty text",
    "empty response",
    "invalid model response",
    "content filter",
)
_DATA_MARKERS = (
    "sqlite",
    "database",
    "integrity",
    "sha256",
    "hash mismatch",
    "schema",
    "validation",
    "jsondecode",
    "invalid json",
    "decode failed",
    "file not found",
    "no such file",
    "path rejected",
    "keyerror",
    "valueerror",
)

_FAILURE_MARKERS = (
    "failed",
    "failure",
    "error",
    "exception",
    "timeout",
    "timed out",
    "traceback",
    "fatal",
    "critical",
    "unauthorized",
    "forbidden",
    "rate limit",
    "invalid_",
)
_SUCCESS_MARKERS = (
    "succeeded",
    "completed",
    "status=done",
    "status=completed",
    "approval_required",
)
_ABNORMAL_EXIT_MARKERS = (
    "systemexit",
    "exited unexpectedly",
    "process terminated unexpectedly",
    "fatal error",
    "critical error",
    "exit code 1",
    "exit code 2",
    "exit code -",
)


@dataclass(frozen=True)
class FailureDiagnosis:
    category: FailureCategory
    code: str
    summary: str
    action: str

    @property
    def category_label(self) -> str:
        return CATEGORY_LABELS[self.category]


@dataclass(frozen=True)
class FailureInspection:
    scanned_line_count: int
    failure_count: int
    category_counts: tuple[tuple[FailureCategory, int], ...]
    timeout_count: int
    failed_call_count: int
    abnormal_exit_count: int
    latest_timestamp: datetime | None
    window_hours: int | None

    @property
    def has_failures(self) -> bool:
        return self.failure_count > 0


def sanitize_failure_text(value: object, *, limit: int = 240) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def classify_failure(value: object) -> FailureDiagnosis:
    text = sanitize_failure_text(value).lower()

    if "too_many_slides" in text:
        return FailureDiagnosis(
            FailureCategory.DATA,
            "presentation_slide_limit_exceeded",
            "PPT 预估或渲染页数超过安全上限。",
            "请减少章节或每页内容后重新发起任务；系统未生成或发送超限文件。",
        )
    if "delivery_integrity_failed" in text or "artifact_validation_failed" in text:
        return FailureDiagnosis(
            FailureCategory.DATA,
            "artifact_integrity_failed",
            "生成文件没有通过格式、大小或完整性复核。",
            "请保留原始要求并重新发起任务；系统不会发送未通过校验的文件。",
        )
    if "document_delivery_send_failed" in text or "qq_send_failed" in text:
        return FailureDiagnosis(
            FailureCategory.NETWORK,
            "document_delivery_failed",
            "文件已生成，但 QQ 文件发送没有成功。",
            "请先确认 QQ/OneBot 连接状态；系统未自动重试或更换接收者。",
        )
    if "approval_context" in text or "owner_context" in text:
        return FailureDiagnosis(
            FailureCategory.PERMISSION,
            "approval_context_invalid",
            "审批恢复上下文与当前主人私聊不一致。",
            "请在原主人私聊中重新发起任务并确认新审批；系统不会跨会话恢复。",
        )
    if "arguments_unavailable" in text:
        return FailureDiagnosis(
            FailureCategory.CONFIGURATION,
            "required_arguments_unavailable",
            "审批恢复所需的受控参数不完整。",
            "请在同一条请求中提供完整标题和内容要求后重新发起任务。",
        )
    if _contains_any(text, _PERMISSION_MARKERS):
        return FailureDiagnosis(
            FailureCategory.PERMISSION,
            "authorization_failed",
            "调用未通过鉴权、权限或审批检查。",
            CATEGORY_ACTIONS[FailureCategory.PERMISSION],
        )
    if _contains_any(text, _CONFIGURATION_MARKERS):
        return FailureDiagnosis(
            FailureCategory.CONFIGURATION,
            "invalid_configuration",
            "功能配置缺失、无效或与当前能力范围不一致。",
            CATEGORY_ACTIONS[FailureCategory.CONFIGURATION],
        )
    if _contains_any(text, _NETWORK_MARKERS):
        code = "request_timeout" if "timeout" in text or "timed out" in text else "connection_failed"
        summary = "调用在限定时间内没有完成。" if code == "request_timeout" else "服务连接或传输失败。"
        return FailureDiagnosis(
            FailureCategory.NETWORK,
            code,
            summary,
            CATEGORY_ACTIONS[FailureCategory.NETWORK],
        )
    if _contains_any(text, _MODEL_MARKERS):
        if "429" in text or "rate limit" in text or "rate_limited" in text or "quota" in text:
            code = "model_rate_limited"
            summary = "模型服务触发限流、额度或配额限制。"
        elif "not found" in text or "model_not_found" in text:
            code = "model_not_found"
            summary = "配置的模型或模型接口不存在。"
        else:
            code = "invalid_model_response"
            summary = "模型没有返回可用的结构化结果。"
        return FailureDiagnosis(
            FailureCategory.MODEL,
            code,
            summary,
            CATEGORY_ACTIONS[FailureCategory.MODEL],
        )
    if _contains_any(text, _DATA_MARKERS):
        return FailureDiagnosis(
            FailureCategory.DATA,
            "data_validation_failed",
            "本地数据、文件、数据库或结构校验失败。",
            CATEGORY_ACTIONS[FailureCategory.DATA],
        )

    return FailureDiagnosis(
        FailureCategory.DATA,
        "unexpected_runtime_state",
        "运行数据或内部状态不符合预期。",
        CATEGORY_ACTIONS[FailureCategory.DATA],
    )


def format_failure_user_message(value: object, *, component: str) -> str:
    diagnosis = classify_failure(value)
    target = component.strip() or "当前操作"
    return (
        f"{target}失败（{diagnosis.category_label} / {diagnosis.code}）："
        f"{diagnosis.summary}{diagnosis.action}"
    )


def _parse_timestamp(line: str) -> datetime | None:
    candidate = line.strip()[:25]
    match = re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:?\d{2})?", candidate)
    if not match:
        return None
    try:
        return datetime.fromisoformat(match.group(0))
    except ValueError:
        return None


def _is_failure_line(line: str) -> bool:
    lowered = line.lower()
    if _contains_any(lowered, _SUCCESS_MARKERS) and not _contains_any(
        lowered, ("failed", "failure", "error", "timeout")
    ):
        return False
    return _contains_any(lowered, _FAILURE_MARKERS)


def inspect_failure_lines(
    lines: Iterable[object],
    *,
    now: datetime | None = None,
    window_hours: int | None = 24,
) -> FailureInspection:
    normalized = [sanitize_failure_text(line, limit=600) for line in lines]
    normalized = [line for line in normalized if line]
    reference_now = now or datetime.now()
    cutoff = (
        reference_now - timedelta(hours=window_hours)
        if window_hours is not None
        else None
    )
    selected: list[tuple[str, datetime | None]] = []
    for line in normalized:
        timestamp = _parse_timestamp(line)
        comparable_timestamp = timestamp
        comparable_cutoff = cutoff
        if timestamp is not None and cutoff is not None:
            if timestamp.tzinfo is not None and cutoff.tzinfo is None:
                comparable_cutoff = cutoff.replace(tzinfo=timestamp.tzinfo)
            elif timestamp.tzinfo is None and cutoff.tzinfo is not None:
                comparable_timestamp = timestamp.replace(tzinfo=cutoff.tzinfo)
            if comparable_timestamp < comparable_cutoff:
                continue
        selected.append((line, timestamp))

    failures = [line for line, _timestamp in selected if _is_failure_line(line)]
    counter = Counter(classify_failure(line).category for line in failures)
    ordered_counts = tuple(
        (category, counter[category])
        for category in FailureCategory
        if counter[category]
    )
    timestamps = [timestamp for _line, timestamp in selected if timestamp is not None]
    lowered_failures = [line.lower() for line in failures]
    return FailureInspection(
        scanned_line_count=len(selected),
        failure_count=len(failures),
        category_counts=ordered_counts,
        timeout_count=sum(
            1 for line in lowered_failures if "timeout" in line or "timed out" in line
        ),
        failed_call_count=sum(
            1
            for line in lowered_failures
            if any(marker in line for marker in ("call", "request", "tool", "llm", "api", "send"))
        ),
        abnormal_exit_count=sum(
            1 for line in lowered_failures if _contains_any(line, _ABNORMAL_EXIT_MARKERS)
        ),
        latest_timestamp=max(timestamps) if timestamps else None,
        window_hours=window_hours,
    )


def format_failure_inspection(inspection: FailureInspection) -> str:
    status = "需要关注" if inspection.has_failures else "正常"
    window = (
        f"最近 {inspection.window_hours} 小时"
        if inspection.window_hours is not None
        else "当前读取范围"
    )
    lines = [
        f"可靠性巡检：{status}",
        f"范围：{window}，读取 {inspection.scanned_line_count} 条安全日志信号。",
        (
            "关键场景："
            f"失败 {inspection.failure_count}｜超时 {inspection.timeout_count}｜"
            f"失败调用 {inspection.failed_call_count}｜疑似异常退出 {inspection.abnormal_exit_count}。"
        ),
    ]
    if inspection.category_counts:
        lines.extend(["", "错误分类："])
        ranked = sorted(inspection.category_counts, key=lambda item: (-item[1], item[0].value))
        for category, count in ranked:
            lines.append(f"- {CATEGORY_LABELS[category]}：{count}。{CATEGORY_ACTIONS[category]}")
    else:
        lines.append("错误分类：当前时间窗内未发现失败信号。")
    lines.extend(
        [
            "",
            "说明：巡检只读取和分类现有安全日志；未发起外部模型请求，未重试、重启、修改配置或修复数据。",
            "异常退出仅依据日志信号判断；没有信号不等于已独立证明进程持续在线。",
        ]
    )
    return "\n".join(lines)
