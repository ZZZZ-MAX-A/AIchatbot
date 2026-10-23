"""Per-image diagnostics; never persist image bodies, source URLs or reasoning."""
from __future__ import annotations

import asyncio
import base64
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import re
from threading import Lock
import time
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from PIL import Image


VISION_LOG_PATH = Path(__file__).resolve().parents[3] / "logs" / "vision.log"
_ACTIVE: ContextVar[dict | None] = ContextVar("vision_observation", default=None)
_WRITE_LOCK = Lock()
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_BEIJING = timezone(timedelta(hours=8))
_KNOWN_ERROR_CODES = {
    "图片超过大小限制": "image_size_limit",
    "图片内容为空": "empty_image",
    "图片格式不受支持": "unsupported_image_format",
    "图片 data URL Base64 无效": "invalid_image_base64",
    "本地图片不在可信缓存目录内，已拒绝": "untrusted_local_path",
    "本地图片文件不存在": "local_image_missing",
    "本地图片路径无效": "invalid_local_path",
    "图片下载连接失败": "download_connection_failed",
    "图片地址 DNS 解析失败": "download_dns_failed",
    "图片地址指向非公网网络，已拒绝": "nonpublic_image_address",
    "图片重定向次数过多": "too_many_redirects",
}
_INTEGER_FIELDS = (
    "image_index", "image_bytes", "width", "height", "max_tokens", "timeout_seconds",
    "download_ms", "request_ms", "total_ms", "http_status", "raw_description_chars",
    "description_chars", "prompt_tokens", "completion_tokens", "total_tokens",
    "reasoning_tokens", "cached_tokens", "image_tokens", "reasoning_chars",
)
# Static rule names only; never store excerpts of the unfiltered response.
FILTER_MARKERS = frozenset({
    "忽略", "无视", "覆盖", "修改设定", "改变设定", "系统提示", "角色卡", "开发者",
    "越狱", "泄露", "透露", "ignore previous", "ignore all", "system prompt",
    "developer message", "jailbreak", "role card", "reveal", "password", "token", "api key",
})


def _identifier(value) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        return ""
    if value.lower().startswith(("sk-", "ak-")):
        return ""
    return value


def _count(value):
    return value if type(value) is int and 0 <= value <= 1_000_000_000 else None


def _field(value, name):
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def image_source_kind(source: str) -> str:
    if source.startswith("data:image/"):
        return "data"
    if source.startswith(("https://", "http://")):
        return "http"
    return "local_or_reference"


def record_image(row: dict, image_base64: str) -> None:
    """Inspect exactly the bytes passed to the provider, without loading pixels."""
    try:
        data = base64.b64decode(image_base64, validate=True)
        row.update(image_bytes=len(data), image_sha256=hashlib.sha256(data).hexdigest())
        with Image.open(io.BytesIO(data)) as image:
            row.update(width=image.width, height=image.height, image_format=image.format)
    except Exception:
        # Diagnostics must not replace the existing image-validation contract.
        pass


def record_response(row: dict, response) -> None:
    row["returned_model"] = _field(response, "model")
    usage = _field(response, "usage")
    for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
        row[name] = _count(_field(usage, name))
    prompt_details = _field(usage, "prompt_tokens_details")
    completion_details = _field(usage, "completion_tokens_details")
    for name in ("cached_tokens", "image_tokens"):
        row[name] = _count(_field(prompt_details, name))
    row["reasoning_tokens"] = _count(_field(completion_details, "reasoning_tokens"))
    choices = _field(response, "choices")
    if choices:
        row["finish_reason"] = _field(choices[0], "finish_reason")
        message = _field(choices[0], "message")
        reasoning = _field(message, "reasoning_content")
        row["reasoning_chars"] = len(reasoning) if isinstance(reasoning, str) else None


def safe_summary(text: str) -> str:
    """Extra log redaction on an already sanitized vision summary."""
    text = " ".join(text.split())
    text = re.sub(r"https?://\S+|data:image/\S+", "[已脱敏链接]", text, flags=re.I)
    text = re.sub(r"\b(?:sk-|ak-)[A-Za-z0-9_-]+\b", "[已脱敏密钥]", text, flags=re.I)
    text = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[已脱敏邮箱]", text, flags=re.I)
    text = re.sub(r"(?i)\b(?:api[_ -]?key|token|password|secret)\s*[:=：]\s*\S+", "[已脱敏密钥]", text)
    text = re.sub(r"(?:UID|账号|昵称|用户名|玩家名)\s*[:：=]?\s*[^，。；;\s]+", "[已脱敏标识]", text, flags=re.I)
    text = re.sub(r"\b\d{5,}\b", "[已脱敏号码]", text)
    return text[:180]


def build_vision_log(row: dict) -> dict:
    """Closed schema: arbitrary request/response fields cannot enter the log."""
    try:
        trace = str(UUID(row.get("trace", "")))
    except (ValueError, TypeError, AttributeError):
        trace = str(uuid4())
    result = {
        "schema_version": 1,
        "time": datetime.now(_BEIJING).isoformat(timespec="milliseconds"),
        "component": "vision", "trace": trace,
        "batch": _identifier(row.get("batch")),
        "persona": row.get("persona") if row.get("persona") in {"aike", "linyin"} else "other",
    }
    for name in _INTEGER_FIELDS:
        result[name] = _count(row.get(name))
    for name in ("provider", "requested_model", "returned_model", "finish_reason", "error_type", "cause_type", "error_code", "image_format", "filter_reason"):
        result[name] = _identifier(row.get(name))
    effort = row.get("reasoning_effort")
    result["reasoning_effort"] = effort if isinstance(effort, str) and effort in {"low", "high", "max"} else None
    for name, allowed, default in (
        ("status", {"succeeded", "failed", "cancelled", "response_truncated"}, "failed"),
        ("stage", {"download", "route", "request", "response", "filter", "validation"}, "route"),
        ("source_kind", {"data", "http", "local_or_reference", "base64"}, "base64"),
    ):
        result[name] = row.get(name) if row.get(name) in allowed else default
    digest = row.get("image_sha256")
    result["image_sha256"] = digest if isinstance(digest, str) and re.fullmatch(r"[a-f0-9]{64}", digest) else ""
    try:
        result["endpoint_host"] = urlsplit(row.get("base_url") or "").hostname or ""
    except ValueError:
        result["endpoint_host"] = ""
    result["request_started"] = row.get("request_started") is True
    result["response_received"] = row.get("response_received") is True
    result["filter_changed"] = row.get("filter_changed") is True
    markers = row.get("filter_markers")
    result["filter_markers"] = sorted({
        marker for marker in markers if isinstance(marker, str) and marker in FILTER_MARKERS
    }) if isinstance(markers, (list, tuple)) else []
    requested, returned = result["requested_model"], result["returned_model"]
    result["model_name_matches"] = requested == returned if requested and returned else None
    result["summary"] = safe_summary(row.get("summary") or "")
    return result


def write_vision_log_safely(row: dict, *, path: Path | None = None) -> bool:
    try:
        line = json.dumps(build_vision_log(row), ensure_ascii=False, separators=(",", ":")) + "\n"
        target = VISION_LOG_PATH if path is None else Path(path)
        with _WRITE_LOCK:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as stream:
                stream.write(line)
        return True
    except Exception:
        return False


@contextmanager
def vision_log_scope(**metadata):
    """Nested route/provider calls share one record; tasks keep separate records."""
    active = _ACTIVE.get()
    if active is not None:
        yield active
        return
    row = {"trace": str(uuid4()), "stage": "route", **metadata}
    token = _ACTIVE.set(row)
    started = time.monotonic()
    try:
        yield row
    except BaseException as exc:
        row["status"] = "cancelled" if isinstance(exc, asyncio.CancelledError) else "failed"
        row["error_type"] = type(exc).__name__
        cause = exc.__cause__ or exc
        row["cause_type"] = type(cause).__name__
        row.setdefault("http_status", getattr(cause, "status_code", None))
        # Match fixed application messages only; never persist exception text,
        # which can contain signed URLs or upstream credentials.
        if not row.get("error_code"):
            row["error_code"] = _KNOWN_ERROR_CODES.get(str(exc), "")
        if not row.get("error_code") and row.get("stage") == "download":
            row["error_code"] = "download_failed"
        raise
    else:
        row.setdefault("status", "succeeded")
    finally:
        row["total_ms"] = round((time.monotonic() - started) * 1000)
        _ACTIVE.reset(token)
        write_vision_log_safely(row)
