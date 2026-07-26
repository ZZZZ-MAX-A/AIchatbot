from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx


ALIYUN_BAILIAN_VISION_PROVIDER = "aliyun_bailian"
ALIYUN_BAILIAN_VISION_REGION = "cn-beijing"
ALIYUN_BAILIAN_VISION_MODEL = "qwen3.7-flash"
ALIYUN_BAILIAN_RESPONSE_BYTES_LIMIT = 256 * 1024
ALIYUN_BAILIAN_ANSWER_CHARS_LIMIT = 2048
ALIYUN_BAILIAN_REQUEST_TIMEOUT_SECONDS = 60
ALIYUN_BAILIAN_BASE_URL_PATTERN = re.compile(
    r"https://ws-[a-z0-9]+\.cn-beijing\.maas\.aliyuncs\.com/compatible-mode/v1"
)
COMPLETE_LEADING_THINK_BLOCK_PATTERN = re.compile(
    r"^\s*<think>.*?</think>\s*",
    re.IGNORECASE | re.DOTALL,
)
STRAY_LEADING_THINK_CLOSE_PATTERN = re.compile(
    r"^\s*(?:</think>\s*)+",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AliyunBailianVisionResult:
    content: str
    raw_content: str
    response_cleanup_applied: bool
    configured_model: str
    returned_model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    elapsed_ms: int
    request_count: int = 1
    client_automatic_retry: bool = False
    tool_definitions_sent: bool = False
    thinking_enabled: bool = False


class AliyunBailianVisionError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        request_executed: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.request_executed = request_executed


def clean_bailian_response_content(content: str) -> tuple[str, bool]:
    cleaned = content
    cleanup_applied = False
    while True:
        updated = COMPLETE_LEADING_THINK_BLOCK_PATTERN.sub("", cleaned, count=1)
        if updated == cleaned:
            break
        cleaned = updated
        cleanup_applied = True
    updated = STRAY_LEADING_THINK_CLOSE_PATTERN.sub("", cleaned, count=1)
    if updated != cleaned:
        cleaned = updated
        cleanup_applied = True
    return cleaned.strip(), cleanup_applied


def _normalized_configuration(config: Any) -> tuple[str, str]:
    base_url = str(getattr(config, "aliyun_bailian_base_url", "") or "")
    base_url = base_url.strip().rstrip("/")
    api_key = str(getattr(config, "aliyun_bailian_api_key", "") or "").strip()
    provider = str(getattr(config, "vision_provider", "") or "").strip()
    configured_model = str(
        getattr(config, "vision_cloud_model", "") or ""
    ).strip()
    if provider != ALIYUN_BAILIAN_VISION_PROVIDER:
        raise AliyunBailianVisionError(
            "cloud_vision_provider_invalid",
            "云端视觉提供方配置无效",
        )
    if configured_model != ALIYUN_BAILIAN_VISION_MODEL:
        raise AliyunBailianVisionError(
            "cloud_vision_model_invalid",
            "云端视觉模型配置无效",
        )
    if not base_url or not api_key:
        raise AliyunBailianVisionError(
            "cloud_vision_credentials_missing",
            "阿里云百炼视觉 URL 或 API Key 未配置",
        )
    if ALIYUN_BAILIAN_BASE_URL_PATTERN.fullmatch(base_url) is None:
        raise AliyunBailianVisionError(
            "cloud_vision_endpoint_invalid",
            "阿里云百炼视觉 URL 不符合北京地域 Workspace 合同",
        )
    return base_url, api_key


def _image_data_url(image_base64: str, max_bytes: int) -> str:
    normalized = image_base64.strip()
    try:
        content = base64.b64decode(normalized, validate=True)
    except (ValueError, TypeError) as exc:
        raise AliyunBailianVisionError(
            "cloud_vision_image_invalid",
            "视觉图片 Base64 无效",
        ) from exc
    if not content:
        raise AliyunBailianVisionError(
            "cloud_vision_image_invalid",
            "视觉图片内容为空",
        )
    if len(content) > max(max_bytes, 1):
        raise AliyunBailianVisionError(
            "cloud_vision_image_too_large",
            "视觉图片超过大小限制",
        )
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        media_type = "image/png"
    elif content.startswith(b"\xff\xd8\xff"):
        media_type = "image/jpeg"
    elif content.startswith((b"GIF87a", b"GIF89a")):
        media_type = "image/gif"
    elif content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        media_type = "image/webp"
    else:
        raise AliyunBailianVisionError(
            "cloud_vision_image_type_unsupported",
            "视觉图片格式不受支持",
        )
    return f"data:{media_type};base64,{normalized}"


def _bounded_response_content(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > ALIYUN_BAILIAN_RESPONSE_BYTES_LIMIT:
            raise AliyunBailianVisionError(
                "cloud_vision_response_too_large",
                "阿里云百炼视觉响应超过安全上限",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _fixed_http_failure(status_code: int) -> AliyunBailianVisionError:
    if status_code in {401, 403}:
        return AliyunBailianVisionError(
            "cloud_vision_authentication_failed",
            "阿里云百炼视觉鉴权失败",
            request_executed=True,
        )
    if status_code == 429:
        return AliyunBailianVisionError(
            "cloud_vision_rate_limited",
            "阿里云百炼视觉请求受到限流",
            request_executed=True,
        )
    return AliyunBailianVisionError(
        "cloud_vision_request_rejected",
        f"阿里云百炼视觉请求被拒绝（HTTP {status_code}）",
        request_executed=True,
    )


def _non_negative_token(usage: dict[str, Any], name: str) -> int:
    value = usage.get(name)
    if type(value) is not int or value < 0:
        raise AliyunBailianVisionError(
            "cloud_vision_usage_metadata_unavailable",
            "阿里云百炼视觉 token usage 无效",
        )
    return value


def _parse_response(content: bytes, elapsed_ms: int) -> AliyunBailianVisionResult:
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AliyunBailianVisionError(
            "cloud_vision_response_contract_mismatch",
            "阿里云百炼视觉响应不是有效 UTF-8 JSON",
        ) from exc
    if not isinstance(payload, dict):
        raise AliyunBailianVisionError(
            "cloud_vision_response_contract_mismatch",
            "阿里云百炼视觉响应顶层合同无效",
        )
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise AliyunBailianVisionError(
            "cloud_vision_response_contract_mismatch",
            "阿里云百炼视觉 choices 合同无效",
        )
    choice = choices[0]
    message = choice.get("message") if isinstance(choice, dict) else None
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise AliyunBailianVisionError(
            "cloud_vision_response_contract_mismatch",
            "阿里云百炼视觉 assistant message 合同无效",
        )
    if message.get("tool_calls"):
        raise AliyunBailianVisionError(
            "cloud_vision_tool_call_rejected",
            "阿里云百炼视觉意外返回 tool call",
        )
    raw_content = message.get("content")
    if not isinstance(raw_content, str) or not raw_content.strip():
        raise AliyunBailianVisionError(
            "cloud_vision_empty_response",
            "阿里云百炼视觉返回空描述",
        )
    if len(raw_content) > ALIYUN_BAILIAN_ANSWER_CHARS_LIMIT:
        raise AliyunBailianVisionError(
            "cloud_vision_response_too_large",
            "阿里云百炼视觉描述超过字符上限",
        )
    cleaned, cleanup_applied = clean_bailian_response_content(raw_content)
    if not cleaned:
        raise AliyunBailianVisionError(
            "cloud_vision_empty_response",
            "阿里云百炼视觉描述清理后为空",
        )
    if len(re.findall(r"[\u4e00-\u9fff]", cleaned)) < 8:
        raise AliyunBailianVisionError(
            "cloud_vision_low_quality_response",
            "阿里云百炼视觉描述缺少足够中文信息",
        )
    returned_model = payload.get("model")
    if returned_model != ALIYUN_BAILIAN_VISION_MODEL:
        raise AliyunBailianVisionError(
            "cloud_vision_returned_model_mismatch",
            "阿里云百炼视觉返回模型与固定合同不一致",
        )
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        raise AliyunBailianVisionError(
            "cloud_vision_usage_metadata_unavailable",
            "阿里云百炼视觉响应缺少 token usage",
        )
    input_tokens = _non_negative_token(usage, "prompt_tokens")
    output_tokens = _non_negative_token(usage, "completion_tokens")
    total_tokens = _non_negative_token(usage, "total_tokens")
    if input_tokens + output_tokens != total_tokens:
        raise AliyunBailianVisionError(
            "cloud_vision_usage_metadata_unavailable",
            "阿里云百炼视觉 token usage 关系不自洽",
        )
    return AliyunBailianVisionResult(
        content=cleaned,
        raw_content=raw_content.strip(),
        response_cleanup_applied=cleanup_applied,
        configured_model=ALIYUN_BAILIAN_VISION_MODEL,
        returned_model=returned_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        elapsed_ms=elapsed_ms,
    )


def request_aliyun_bailian_vision(
    config: Any,
    image_base64: str,
    prompt: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> AliyunBailianVisionResult:
    normalized_prompt = prompt.strip()
    if not normalized_prompt or len(normalized_prompt) > 12_000:
        raise AliyunBailianVisionError(
            "cloud_vision_prompt_invalid",
            "云端视觉提示合同无效",
        )
    base_url, api_key = _normalized_configuration(config)
    image_url = _image_data_url(
        image_base64,
        int(getattr(config, "vision_max_image_bytes", 0) or 0),
    )
    payload = {
        "model": ALIYUN_BAILIAN_VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": normalized_prompt},
                ],
            }
        ],
        "stream": False,
        "temperature": 0,
        "max_tokens": 256,
        "enable_thinking": False,
    }
    configured_timeout = int(getattr(config, "vision_timeout_seconds", 0) or 0)
    total_timeout = min(
        max(configured_timeout, 1),
        ALIYUN_BAILIAN_REQUEST_TIMEOUT_SECONDS,
    )
    timeout = httpx.Timeout(
        connect=min(total_timeout, 10),
        read=total_timeout,
        write=min(total_timeout, 10),
        pool=min(total_timeout, 10),
    )
    started = time.monotonic()
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        ) as client:
            with client.stream(
                "POST",
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as response:
                response_content = _bounded_response_content(response)
                if response.status_code != 200:
                    raise _fixed_http_failure(response.status_code)
    except AliyunBailianVisionError:
        raise
    except httpx.TimeoutException as exc:
        raise AliyunBailianVisionError(
            "cloud_vision_request_timeout",
            "阿里云百炼视觉请求超时",
            request_executed=True,
        ) from exc
    except httpx.RequestError as exc:
        raise AliyunBailianVisionError(
            "cloud_vision_connection_failed",
            "阿里云百炼视觉连接失败",
            request_executed=True,
        ) from exc
    elapsed_ms = max(int((time.monotonic() - started) * 1000), 0)
    try:
        return _parse_response(response_content, elapsed_ms)
    except AliyunBailianVisionError as exc:
        exc.request_executed = True
        raise
