from __future__ import annotations

from .failure_diagnostics import sanitize_failure_text
from .reliability_events import ReliabilityOutcome, record_result_safely


def _safe_error_text(error: object) -> str:
    return sanitize_failure_text(error, limit=320).lower()


def vision_failure_code(error: object) -> str:
    text = _safe_error_text(error)
    if any(marker in text for marker in ("401", "403", "unauthorized", "forbidden")):
        return "authorization_failed"
    if any(marker in text for marker in ("超时", "timeout", "timed out")):
        return "request_timeout"
    if any(marker in text for marker in ("ollama http 429", "rate limit", "quota")):
        return "model_rate_limited"
    if any(
        marker in text
        for marker in (
            "ollama 不可用",
            "下载失败",
            "connection",
            "connecterror",
            "winerror 10061",
            "service unavailable",
            "ollama http 500",
            "ollama http 502",
            "ollama http 503",
            "ollama http 504",
        )
    ):
        return "connection_failed"
    if any(
        marker in text
        for marker in (
            "vision_model 未配置",
            "视觉未开启",
            "视觉提示合同无效",
            "invalid base url",
            "invalid url",
        )
    ):
        return "invalid_configuration"
    if any(
        marker in text
        for marker in (
            "ollama http 404",
            "视觉模型不存在",
            "model not found",
            "model_not_found",
        )
    ):
        return "model_not_found"
    if any(
        marker in text
        for marker in (
            "返回空描述",
            "低质量重复内容",
            "返回内容不是 json",
            "返回内容过长",
            "empty response",
            "invalid model response",
        )
    ):
        return "invalid_model_response"
    if any(
        marker in text
        for marker in (
            "data url 格式无效",
            "图片地址不是",
            "本地图片路径无效",
            "本地图片文件不存在",
            "图片超过大小限制",
            "图片内容为空",
            "decode",
            "validation",
        )
    ):
        return "data_validation_failed"
    return "unexpected_runtime_state"


def tts_failure_code(error: object) -> str:
    text = _safe_error_text(error)
    if any(marker in text for marker in ("401", "403", "unauthorized", "forbidden")):
        return "authorization_failed"
    if any(
        marker in text
        for marker in (
            "timeout",
            "timed out",
            "did not start within",
            "启动等待超时",
            "请求超时",
        )
    ):
        return "request_timeout"
    if any(marker in text for marker in ("429", "rate limit", "quota")):
        return "model_rate_limited"
    if any(
        marker in text
        for marker in (
            "connection",
            "connecterror",
            "winerror 10061",
            "service unavailable",
            "network",
            "502",
            "503",
            "504",
        )
    ):
        return "connection_failed"
    if any(
        marker in text
        for marker in (
            "indextts2 python was not found",
            "checkpoint",
            "model not found",
            "model_not_found",
            "模型不存在",
        )
    ):
        return "model_not_found"
    if any(
        marker in text
        for marker in (
            "tts service script was not found",
            "invalid base url",
            "invalid url",
            "voice_id is empty",
            "音色未配置",
            "voice not found",
        )
    ):
        return "invalid_configuration"
    if any(
        marker in text
        for marker in (
            "tts service failed",
            "合成失败",
            "invalid response",
            "invalid json",
            "jsondecode",
            "empty response",
        )
    ):
        return "invalid_model_response"
    if any(
        marker in text
        for marker in (
            "tts output not found",
            "tts output is empty",
            "tts output duration invalid",
            "tts output exceeds duration limit",
            "audio path",
            "empty tts segments",
        )
    ):
        return "data_validation_failed"
    return "unexpected_runtime_state"


def observe_vision_infer_safely(
    *,
    attempted_count: int,
    successful_count: int,
    error: object | None = None,
) -> bool:
    try:
        if attempted_count <= 0:
            return False
        if successful_count >= attempted_count:
            return record_result_safely(
                component="vision",
                operation="infer",
                code="operation_succeeded",
                outcome=ReliabilityOutcome.SUCCEEDED,
            )
        return record_result_safely(
            component="vision",
            operation="infer",
            code=vision_failure_code(error),
            outcome=(
                ReliabilityOutcome.DEGRADED
                if successful_count > 0
                else ReliabilityOutcome.FAILED
            ),
        )
    except Exception:
        return False


def observe_tts_synthesis_safely(
    *,
    succeeded: bool,
    error: object | None = None,
) -> bool:
    try:
        return record_result_safely(
            component="tts",
            operation="synthesize",
            code="operation_succeeded" if succeeded else tts_failure_code(error),
            outcome=(
                ReliabilityOutcome.SUCCEEDED
                if succeeded
                else ReliabilityOutcome.FAILED
            ),
        )
    except Exception:
        return False
