from __future__ import annotations

import asyncio
import base64
import binascii
from collections import deque
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
import re
from time import monotonic
from typing import Any
from uuid import uuid4

from openai import AsyncOpenAI
from PIL import Image, UnidentifiedImageError

from .config import AiChatConfig


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_IMAGE_OUTPUT_DIR = PROJECT_ROOT / "data" / "generated-images"
ALLOWED_IMAGE_FORMATS = frozenset({"PNG", "JPEG", "WEBP"})
MAX_IMAGE_PIXELS = 16_777_216
IMAGE_REQUEST_SIZE = "1024x1024"
IMAGE_REQUEST_QUALITY = "high"


class ImageGenError(RuntimeError):
    """Stable, non-secret image-task failure exposed to the QQ layer."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ProviderFailureDiagnostic:
    exception_type: str
    http_status: int | None
    provider_code: str
    provider_param: str


@dataclass(frozen=True)
class ImageArtifact:
    path: Path
    media_type: str
    image_format: str
    width: int
    height: int
    byte_count: int
    operation: str


@dataclass(frozen=True)
class ValidatedImage:
    content: bytes = field(repr=False)
    media_type: str
    image_format: str
    width: int
    height: int
    extension: str


@dataclass(frozen=True)
class PendingImageEdit:
    prompt: str = field(repr=False)
    expires_at: float
    provider: str = "openai"
    lora_adapter: str = ""


@dataclass(frozen=True)
class ImageRequestDecision:
    allowed: bool
    status: str
    wait_seconds: int = 0


_SAFE_PROVIDER_TOKEN = re.compile(r"[A-Za-z0-9_.\[\]-]{1,80}")


def _safe_provider_token(value: object) -> str:
    text = str(value or "").strip()
    return text if _SAFE_PROVIDER_TOKEN.fullmatch(text) else "-"


def provider_failure_diagnostic(error: BaseException) -> ProviderFailureDiagnostic:
    """Extract non-secret provider metadata without retaining response text."""
    status_value = getattr(error, "status_code", None)
    http_status = (
        status_value
        if isinstance(status_value, int)
        and not isinstance(status_value, bool)
        and 100 <= status_value <= 599
        else None
    )
    payload: dict[str, Any] = {}
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        nested = body.get("error")
        payload = nested if isinstance(nested, dict) else body
    provider_code = (
        getattr(error, "code", None)
        or payload.get("code")
        or payload.get("type")
    )
    provider_param = getattr(error, "param", None) or payload.get("param")
    return ProviderFailureDiagnostic(
        exception_type=_safe_provider_token(type(error).__name__),
        http_status=http_status,
        provider_code=_safe_provider_token(provider_code),
        provider_param=_safe_provider_token(provider_param),
    )


def format_provider_failure_diagnostic(error: BaseException) -> str:
    diagnostic = provider_failure_diagnostic(error)
    status = str(diagnostic.http_status) if diagnostic.http_status is not None else "-"
    return (
        f"provider_type={diagnostic.exception_type} "
        f"http_status={status} "
        f"provider_code={diagnostic.provider_code} "
        f"provider_param={diagnostic.provider_param}"
    )


def image_gen_settings_status(config: AiChatConfig) -> str:
    if not config.enable_image_gen:
        return "disabled"
    if not config.image_gen_api_key.strip():
        return "api_key_missing"
    if not config.image_gen_base_url.strip():
        return "base_url_missing"
    if not config.image_gen_model.strip() or not config.image_edit_model.strip():
        return "model_missing"
    numeric_ranges = (
        (config.image_gen_timeout_seconds, 1, 600),
        (config.image_gen_max_prompt_chars, 1, 10_000),
        (config.image_gen_max_input_bytes, 1024, 50_000_000),
        (config.image_gen_max_output_bytes, 1024, 50_000_000),
        (config.image_gen_pending_edit_seconds, 10, 600),
        (config.image_gen_cooldown_seconds, 0, 3600),
        (config.image_gen_max_requests_per_hour, 1, 1000),
    )
    if any(not lower <= value <= upper for value, lower, upper in numeric_ranges):
        return "invalid_limits"
    return "ready"


def normalize_image_prompt(prompt: str, *, max_chars: int) -> str:
    if not isinstance(prompt, str):
        raise ImageGenError("prompt_invalid")
    normalized = re.sub(r"\s+", " ", prompt).strip()
    if not normalized:
        raise ImageGenError("prompt_empty")
    if len(normalized) > max(max_chars, 1):
        raise ImageGenError("prompt_too_long")
    return normalized


def _media_type_and_extension(image_format: str) -> tuple[str, str]:
    if image_format == "PNG":
        return "image/png", ".png"
    if image_format == "JPEG":
        return "image/jpeg", ".jpg"
    if image_format == "WEBP":
        return "image/webp", ".webp"
    raise ImageGenError("image_format_unsupported")


def validate_image_bytes(content: bytes, *, max_bytes: int) -> ValidatedImage:
    if not isinstance(content, bytes) or not content:
        raise ImageGenError("image_empty")
    if len(content) > max(max_bytes, 1):
        raise ImageGenError("image_too_large")
    try:
        with Image.open(BytesIO(content)) as image:
            image_format = str(image.format or "").upper()
            width, height = image.size
            if image_format not in ALLOWED_IMAGE_FORMATS:
                raise ImageGenError("image_format_unsupported")
            if getattr(image, "is_animated", False):
                raise ImageGenError("animated_image_unsupported")
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise ImageGenError("image_dimensions_invalid")
            image.verify()
    except ImageGenError:
        raise
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ImageGenError("image_invalid") from exc
    media_type, extension = _media_type_and_extension(image_format)
    return ValidatedImage(
        content=content,
        media_type=media_type,
        image_format=image_format,
        width=width,
        height=height,
        extension=extension,
    )


def _response_value(data: object, name: str) -> str:
    if isinstance(data, dict):
        return str(data.get(name) or "").strip()
    return str(getattr(data, name, "") or "").strip()


def _decode_image_base64(value: str, *, max_bytes: int) -> bytes:
    payload = value.split(",", 1)[1] if value.startswith("data:") and "," in value else value
    if len(payload) > max(max_bytes, 1) * 2:
        raise ImageGenError("image_too_large")
    try:
        content = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ImageGenError("image_base64_invalid") from exc
    return content


async def _response_image_bytes(response: object, *, max_bytes: int) -> bytes:
    data_items = getattr(response, "data", None)
    if not isinstance(data_items, list) or not data_items:
        raise ImageGenError("provider_response_empty")
    data = data_items[0]
    encoded = _response_value(data, "b64_json")
    if encoded:
        return _decode_image_base64(encoded, max_bytes=max_bytes)
    url = _response_value(data, "url")
    if not url:
        raise ImageGenError("provider_image_missing")
    try:
        from .vision import _download_image_base64

        downloaded = await asyncio.to_thread(
            _download_image_base64,
            url,
            30,
            max_bytes,
            (),
        )
    except Exception as exc:
        raise ImageGenError("provider_image_download_failed") from exc
    return _decode_image_base64(downloaded, max_bytes=max_bytes)


def _client(config: AiChatConfig) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=config.image_gen_api_key,
        base_url=config.image_gen_base_url.rstrip("/"),
        timeout=config.image_gen_timeout_seconds,
        max_retries=0,
    )


def _transparent_mask_file(source: ValidatedImage) -> tuple[str, bytes, str]:
    output = BytesIO()
    with Image.new(
        "RGBA",
        (source.width, source.height),
        (0, 0, 0, 0),
    ) as mask:
        mask.save(output, format="PNG")
    return ("mask.png", output.getvalue(), "image/png")


def _write_artifact(
    image: ValidatedImage,
    *,
    operation: str,
    output_dir: Path,
) -> ImageArtifact:
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_dir = output_dir.resolve()
    final_path = resolved_dir / f"{operation}_{uuid4().hex}{image.extension}"
    temporary_path = resolved_dir / f".{final_path.name}.tmp"
    try:
        temporary_path.write_bytes(image.content)
        temporary_path.replace(final_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return ImageArtifact(
        path=final_path,
        media_type=image.media_type,
        image_format=image.image_format,
        width=image.width,
        height=image.height,
        byte_count=len(image.content),
        operation=operation,
    )


async def _save_response(
    response: object,
    *,
    config: AiChatConfig,
    operation: str,
    output_dir: Path | None,
) -> ImageArtifact:
    content = await _response_image_bytes(
        response,
        max_bytes=config.image_gen_max_output_bytes,
    )
    validated = validate_image_bytes(
        content,
        max_bytes=config.image_gen_max_output_bytes,
    )
    return await asyncio.to_thread(
        _write_artifact,
        validated,
        operation=operation,
        output_dir=output_dir or DEFAULT_IMAGE_OUTPUT_DIR,
    )


async def generate_image(
    config: AiChatConfig,
    prompt: str,
    *,
    output_dir: Path | None = None,
) -> ImageArtifact:
    if image_gen_settings_status(config) != "ready":
        raise ImageGenError("image_gen_not_ready")
    normalized_prompt = normalize_image_prompt(
        prompt,
        max_chars=config.image_gen_max_prompt_chars,
    )
    try:
        response = await _client(config).images.generate(
            model=config.image_gen_model,
            prompt=normalized_prompt,
            n=1,
            size=IMAGE_REQUEST_SIZE,
            quality=IMAGE_REQUEST_QUALITY,
            timeout=config.image_gen_timeout_seconds,
        )
    except Exception as exc:
        raise ImageGenError("provider_generate_failed") from exc
    return await _save_response(
        response,
        config=config,
        operation="gen",
        output_dir=output_dir,
    )


async def edit_image(
    config: AiChatConfig,
    prompt: str,
    source_image: bytes,
    *,
    output_dir: Path | None = None,
) -> ImageArtifact:
    if image_gen_settings_status(config) != "ready":
        raise ImageGenError("image_gen_not_ready")
    normalized_prompt = normalize_image_prompt(
        prompt,
        max_chars=config.image_gen_max_prompt_chars,
    )
    validated_source = validate_image_bytes(
        source_image,
        max_bytes=config.image_gen_max_input_bytes,
    )
    source_file: tuple[str, bytes, str] = (
        f"source{validated_source.extension}",
        validated_source.content,
        validated_source.media_type,
    )
    mask_file = _transparent_mask_file(validated_source)
    try:
        response = await _client(config).images.edit(
            model=config.image_edit_model,
            image=source_file,
            mask=mask_file,
            prompt=normalized_prompt,
            n=1,
            size=IMAGE_REQUEST_SIZE,
            quality=IMAGE_REQUEST_QUALITY,
            timeout=config.image_gen_timeout_seconds,
        )
    except Exception as exc:
        raise ImageGenError("provider_edit_failed") from exc
    return await _save_response(
        response,
        config=config,
        operation="edit",
        output_dir=output_dir,
    )


async def load_image_ref(
    image_ref: str,
    *,
    timeout_seconds: int,
    max_bytes: int,
    trusted_local_roots: tuple[Path, ...] = (),
) -> bytes:
    try:
        from .vision import _download_image_base64

        encoded = await asyncio.to_thread(
            _download_image_base64,
            image_ref,
            timeout_seconds,
            max_bytes,
            trusted_local_roots,
        )
    except Exception as exc:
        raise ImageGenError("input_image_load_failed") from exc
    content = _decode_image_base64(encoded, max_bytes=max_bytes)
    return validate_image_bytes(content, max_bytes=max_bytes).content


class ImageGenRuntime:
    """Process-local pending-edit, lock, cooldown, and hourly-cost boundary."""

    def __init__(self) -> None:
        self._pending_edits: dict[str, PendingImageEdit] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._request_times: dict[str, deque[float]] = {}

    def lock(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    def begin_edit(
        self,
        key: str,
        prompt: str,
        *,
        ttl_seconds: int,
        provider: str = "openai",
        lora_adapter: str = "",
    ) -> None:
        self._pending_edits[key] = PendingImageEdit(
            prompt=prompt,
            expires_at=monotonic() + max(ttl_seconds, 1),
            provider=provider,
            lora_adapter=lora_adapter,
        )

    def pending_edit(self, key: str, *, now: float | None = None) -> PendingImageEdit | None:
        current = self._pending_edits.get(key)
        if current is None:
            return None
        observed_at = monotonic() if now is None else now
        if current.expires_at <= observed_at:
            self._pending_edits.pop(key, None)
            return None
        return current

    def consume_edit(self, key: str, *, now: float | None = None) -> PendingImageEdit | None:
        current = self.pending_edit(key, now=now)
        if current is not None:
            self._pending_edits.pop(key, None)
        return current

    def cancel_edit(self, key: str) -> bool:
        return self._pending_edits.pop(key, None) is not None

    def claim_request(
        self,
        key: str,
        *,
        cooldown_seconds: int,
        max_requests_per_hour: int,
        now: float | None = None,
    ) -> ImageRequestDecision:
        observed_at = monotonic() if now is None else now
        history = self._request_times.setdefault(key, deque())
        while history and observed_at - history[0] >= 3600:
            history.popleft()
        if len(history) >= max(max_requests_per_hour, 1):
            wait_seconds = max(1, int(round(3600 - (observed_at - history[0]))))
            return ImageRequestDecision(False, "hourly_limit", wait_seconds)
        if history and observed_at - history[-1] < max(cooldown_seconds, 0):
            wait_seconds = max(
                1,
                int(round(max(cooldown_seconds, 0) - (observed_at - history[-1]))),
            )
            return ImageRequestDecision(False, "cooldown", wait_seconds)
        history.append(observed_at)
        return ImageRequestDecision(True, "allowed")
