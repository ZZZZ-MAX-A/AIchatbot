from __future__ import annotations

import asyncio
import base64
import binascii
from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from time import monotonic
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageOps

from .config import AiChatConfig
from .image_gen import (
    DEFAULT_IMAGE_OUTPUT_DIR,
    ImageArtifact,
    ImageGenError,
    _write_artifact,
    normalize_image_prompt,
    validate_image_bytes,
)
from .failure_diagnostics import sanitize_failure_text


QWEN_SPACE_DEFAULT_BASE_URL = (
    "https://prithivmlmods-qwen-image-edit-2511-loras-fast.hf.space"
)
# The Space currently exposes the public Gradio endpoint as /edit_image.
# Gradio keeps the v2 prefix on submission but not on the event-stream URL.
QWEN_SPACE_INFER_PATH = "/gradio_api/call/v2/edit_image"
QWEN_SPACE_EVENT_PATH = "/gradio_api/call/edit_image/{event_id}"
QWEN_SPACE_DEFAULT_GUIDANCE = 1.0
QWEN_SPACE_DEFAULT_STEPS = 4
_SAFE_EVENT_ID = re.compile(r"[A-Za-z0-9_-]{1,160}")


class QwenSpaceEditError(ImageGenError):
    """Stable failure code for the public Qwen image-edit Space."""


@dataclass(frozen=True)
class QwenEditPreset:
    key: str
    lora_adapter: str
    default_prompt: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class QwenEditRequest:
    preset_key: str
    lora_adapter: str
    prompt: str = field(repr=False)


@dataclass(frozen=True)
class QwenPreparedImage:
    data_url: str = field(repr=False)
    media_type: str
    width: int
    height: int
    byte_count: int


@dataclass(frozen=True)
class QwenRemoteResult:
    event_id: str
    result_url: str = field(repr=False)
    seed: int
    media_type: str
    # The current Space returns a base64 PNG data URL instead of a file URL.
    # Keep it out of repr/logs because it contains the complete generated image.
    result_data_url: str = field(default="", repr=False)


@dataclass(frozen=True)
class QwenResultTicket:
    remote: QwenRemoteResult
    expires_at: float
    artifact: ImageArtifact | None = None


QWEN_EDIT_PRESETS: tuple[QwenEditPreset, ...] = (
    QwenEditPreset(
        "anime",
        "Anime-V2",
        "Transform into anime while preserving identity, composition, clothing, and background details.",
        ("动漫", "动漫化", "anime", "anime-v2"),
    ),
    QwenEditPreset(
        "photo_to_anime",
        "Photo-to-Anime",
        "Transform into anime.",
        ("照片转动漫", "真人转动漫", "photo-to-anime"),
    ),
    QwenEditPreset(
        "unblur",
        "Unblur-Anything",
        "Unblur and upscale while preserving the original content.",
        ("变清晰", "去模糊", "修复", "unblur", "unblur-anything"),
    ),
    QwenEditPreset(
        "upscale",
        "Upscaler",
        "Upscale and enhance details while preserving the original image.",
        ("放大", "高清", "upscale", "upscaler"),
    ),
    QwenEditPreset(
        "realistic",
        "Anything2Real",
        "Change the picture to a realistic photograph while preserving identity and composition.",
        ("转写实", "写实化", "anything2real"),
    ),
    QwenEditPreset(
        "multiple_angles",
        "Multiple-Angles",
        "Rotate the camera 45 degrees to the right while preserving the subject.",
        ("多角度", "换角度", "multiple-angles"),
    ),
    QwenEditPreset(
        "fal_multiple_angles",
        "Fal-Multiple-Angles",
        "Front-right quarter view while preserving the subject.",
        ("多角度2", "fal多角度", "fal-multiple-angles"),
    ),
    QwenEditPreset(
        "manga_tone",
        "Manga-Tone",
        "Paint with manga tone.",
        ("漫画网点", "漫画色调", "manga-tone"),
    ),
    QwenEditPreset(
        "polaroid",
        "Polaroid-Photo",
        "Transform into a cinematic polaroid photo while preserving the subject.",
        ("拍立得", "polaroid", "polaroid-photo"),
    ),
    QwenEditPreset(
        "midnight_noir",
        "Midnight-Noir-Eyes-Spotlight",
        "Transform into Midnight Noir Eyes Spotlight.",
        ("午夜黑色", "黑色聚光", "midnight-noir-eyes-spotlight"),
    ),
    QwenEditPreset(
        "hyper_realistic_portrait",
        "Hyper-Realistic-Portrait",
        "Transform into a hyper-realistic face portrait.",
        ("超写实肖像", "hyper-realistic-portrait"),
    ),
    QwenEditPreset(
        "ultra_realistic_portrait",
        "Ultra-Realistic-Portrait",
        "Transform into an ultra-realistic portrait.",
        ("极写实肖像", "ultra-realistic-portrait"),
    ),
    QwenEditPreset(
        "pixar",
        "Pixar-Inspired-3D",
        "Transform into Pixar-inspired 3D while preserving identity and composition.",
        ("皮克斯3d", "皮克斯", "pixar", "pixar-inspired-3d"),
    ),
    QwenEditPreset(
        "noir_comic",
        "Noir-Comic-Book",
        "Transform into a noir comic book style.",
        ("黑色电影漫画", "黑白漫画", "noir-comic-book"),
    ),
    QwenEditPreset(
        "studio_delight",
        "Studio-DeLight",
        "Use neutral uniform studio lighting while preserving identity and composition.",
        ("影棚去光", "均匀灯光", "studio-delight"),
    ),
    QwenEditPreset(
        "cinematic_flatlog",
        "Cinematic-FlatLog",
        "Transform into a cinematic flat log while preserving the subject.",
        ("电影平坦", "电影log", "cinematic-flatlog"),
    ),
)


def _preset_lookup() -> dict[str, QwenEditPreset]:
    lookup: dict[str, QwenEditPreset] = {}
    for preset in QWEN_EDIT_PRESETS:
        for alias in (*preset.aliases, preset.key, preset.lora_adapter):
            lookup[alias.casefold()] = preset
    return lookup


_PRESET_LOOKUP = _preset_lookup()


def qwen_space_settings_status(config: AiChatConfig) -> str:
    if not config.enable_qwen_space_edit:
        return "disabled"
    if not config.qwen_space_base_url.strip():
        return "base_url_missing"
    parsed = urlparse(config.qwen_space_base_url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        return "base_url_invalid"
    numeric_ranges = (
        (config.qwen_space_submit_timeout_seconds, 1, 600),
        (config.qwen_space_infer_timeout_seconds, 1, 900),
        (config.qwen_space_download_timeout_seconds, 1, 900),
        (config.qwen_space_download_retries, 0, 5),
        (config.qwen_space_result_ttl_seconds, 60, 86_400),
        (config.qwen_space_max_side, 64, 4096),
        (config.qwen_space_jpeg_quality, 50, 100),
    )
    if any(not lower <= value <= upper for value, lower, upper in numeric_ranges):
        return "invalid_limits"
    return "ready"


def qwen_mode_summary() -> str:
    return "动漫、照片转动漫、变清晰、放大、转写实、多角度、漫画网点、拍立得、超写实肖像、皮克斯3D、黑色电影漫画"


def resolve_qwen_edit_request(text: str, *, max_chars: int) -> QwenEditRequest:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if not normalized:
        raise QwenSpaceEditError("qwen_mode_missing")
    mode, _, custom_prompt = normalized.partition(" ")
    preset = _PRESET_LOOKUP.get(mode.casefold())
    if preset is None:
        raise QwenSpaceEditError("qwen_mode_unknown")
    prompt = preset.default_prompt
    if custom_prompt.strip():
        prompt = f"{prompt} Additional instruction: {custom_prompt.strip()}"
    prompt = normalize_image_prompt(prompt, max_chars=max_chars)
    return QwenEditRequest(
        preset_key=preset.key,
        lora_adapter=preset.lora_adapter,
        prompt=prompt,
    )


def prepare_qwen_image(
    source_image: bytes,
    *,
    max_input_bytes: int,
    max_side: int,
    jpeg_quality: int,
) -> QwenPreparedImage:
    validated = validate_image_bytes(source_image, max_bytes=max_input_bytes)
    with Image.open(BytesIO(validated.content)) as opened:
        image = ImageOps.exif_transpose(opened)
        image.load()
        width, height = image.size
        scale = min(1.0, max_side / max(width, height))
        target_width = max(8, int(width * scale) // 8 * 8)
        target_height = max(8, int(height * scale) // 8 * 8)
        if (target_width, target_height) != image.size:
            image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        has_alpha = "A" in image.getbands() or "transparency" in image.info
        output = BytesIO()
        if has_alpha:
            image.convert("RGBA").save(output, format="PNG", optimize=True)
            media_type = "image/png"
        else:
            image.convert("RGB").save(
                output,
                format="JPEG",
                quality=jpeg_quality,
                optimize=True,
            )
            media_type = "image/jpeg"
        content = output.getvalue()
    if not content or len(content) > max_input_bytes:
        raise QwenSpaceEditError("qwen_preprocessed_image_too_large")
    encoded = base64.b64encode(content).decode("ascii")
    return QwenPreparedImage(
        data_url=f"data:{media_type};base64,{encoded}",
        media_type=media_type,
        width=target_width,
        height=target_height,
        byte_count=len(content),
    )


def _auth_headers(config: AiChatConfig) -> dict[str, str]:
    token = config.qwen_space_hf_token.strip()
    return {"Authorization": f"Bearer {token}"} if token else {}


def _base_url(config: AiChatConfig) -> str:
    return config.qwen_space_base_url.rstrip("/")


def _classify_space_error(payload: str) -> str:
    lowered = payload.casefold()
    if "no gpu was available" in lowered or "no gpu available" in lowered:
        return "qwen_gpu_unavailable"
    if any(token in lowered for token in ("quota", "gpu time", "exceeded")):
        return "qwen_quota_exceeded"
    if any(token in lowered for token in ("duration", "timeout", "timed out")):
        return "qwen_infer_timeout"
    return "qwen_infer_failed"


def _safe_space_response_excerpt(value: object) -> str:
    """Return a short, secret-safe provider response fragment for diagnostics."""
    text = str(value or "")
    text = re.sub(
        r"data:image/[^,\s]+;base64,[A-Za-z0-9+/=]+",
        "[redacted-image]",
        text,
        flags=re.IGNORECASE,
    )
    return sanitize_failure_text(text, limit=240)


def _space_response_context(
    response: httpx.Response,
    *,
    phase: str,
    endpoint: str,
) -> dict[str, object]:
    """Build safe HTTP details without retaining tokens, images, or URLs."""
    return {
        "qwen_phase": phase,
        "qwen_http_status": response.status_code,
        "qwen_api_path": urlparse(endpoint).path or endpoint,
        "qwen_response_type": response.headers.get("content-type", "")[:80],
        "qwen_response_excerpt": _safe_space_response_excerpt(response.text),
    }


def _space_http_error(
    response: httpx.Response,
    *,
    phase: str,
    endpoint: str,
) -> QwenSpaceEditError:
    """Map a Space HTTP failure to a useful stable code for logs and QQ."""
    excerpt = _safe_space_response_excerpt(response.text)
    lowered = excerpt.casefold()
    if "no gpu was available" in lowered or "no gpu available" in lowered:
        code = "qwen_gpu_unavailable"
    elif response.status_code in {401, 403}:
        code = "qwen_auth_failed"
    elif response.status_code == 404:
        code = "qwen_endpoint_not_found"
    elif response.status_code == 429:
        code = "qwen_rate_limited"
    elif response.status_code >= 500:
        code = "qwen_space_server_error"
    elif any(token in lowered for token in ("quota", "gpu time", "exceeded")):
        code = "qwen_quota_exceeded"
    else:
        code = f"qwen_http_{response.status_code}"
    return QwenSpaceEditError(
        code,
        context=_space_response_context(
            response,
            phase=phase,
            endpoint=endpoint,
        ),
    )


def _qwen_result_from_payload(
    event_id: str,
    values: object,
    *,
    max_output_bytes: int,
    base_hostname: str,
) -> QwenRemoteResult:
    """Parse both the current data-URL result and the older URL result shape."""
    if not isinstance(values, list) or not values or not isinstance(values[0], dict):
        raise QwenSpaceEditError("qwen_result_invalid")
    result_data = values[0]
    legacy_seed = values[1] if len(values) > 1 else result_data.get("seed")
    try:
        seed = int(result_data.get("seed", legacy_seed))
    except (TypeError, ValueError) as exc:
        raise QwenSpaceEditError("qwen_seed_invalid") from exc

    image_value = result_data.get("image")
    if isinstance(image_value, dict):
        image_value = image_value.get("url") or image_value.get("path")
    result_value = str(image_value or "").strip()
    if result_value.startswith("data:image/"):
        if len(result_value) > max(max_output_bytes, 1) * 2:
            raise QwenSpaceEditError("image_too_large")
        header, separator, _payload = result_value.partition(",")
        if separator != "," or ";base64" not in header.casefold():
            raise QwenSpaceEditError("qwen_result_invalid")
        media_type = header[5:].split(";", 1)[0].strip().lower()
        return QwenRemoteResult(
            event_id=event_id,
            result_url="",
            seed=seed,
            media_type=media_type,
            result_data_url=result_value,
        )

    result_url = str(result_data.get("url") or result_value).strip()
    result_parsed = urlparse(result_url)
    if (
        result_parsed.scheme != "https"
        or not result_parsed.hostname
        or result_parsed.hostname != base_hostname
    ):
        raise QwenSpaceEditError("qwen_result_url_invalid")
    return QwenRemoteResult(
        event_id=event_id,
        result_url=result_url,
        seed=seed,
        media_type=str(result_data.get("mime_type") or "").strip(),
    )


async def submit_qwen_edit(
    config: AiChatConfig,
    request: QwenEditRequest,
    prepared: QwenPreparedImage,
) -> QwenRemoteResult:
    if qwen_space_settings_status(config) != "ready":
        raise QwenSpaceEditError("qwen_not_ready")
    body = {
        "images_b64_json": json.dumps([prepared.data_url], separators=(",", ":")),
        "prompt": request.prompt,
        "lora_adapter": request.lora_adapter,
        "seed": 0,
        "randomize_seed": True,
        "guidance_scale": QWEN_SPACE_DEFAULT_GUIDANCE,
        "steps": QWEN_SPACE_DEFAULT_STEPS,
    }
    headers = _auth_headers(config)
    timeout = httpx.Timeout(
        connect=min(config.qwen_space_submit_timeout_seconds, 60),
        write=config.qwen_space_submit_timeout_seconds,
        read=config.qwen_space_infer_timeout_seconds,
        pool=config.qwen_space_submit_timeout_seconds,
    )
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=headers,
        ) as client:
            submitted = await client.post(
                f"{_base_url(config)}{QWEN_SPACE_INFER_PATH}",
                json=body,
            )
            if submitted.is_error:
                raise _space_http_error(
                    submitted,
                    phase="submit",
                    endpoint=str(submitted.request.url),
                )
            event_id = str(submitted.json().get("event_id") or "").strip()
            if not _SAFE_EVENT_ID.fullmatch(event_id):
                raise QwenSpaceEditError("qwen_event_id_invalid")
            event_url = f"{_base_url(config)}{QWEN_SPACE_EVENT_PATH.format(event_id=event_id)}"
            current_event = ""
            async with client.stream("GET", event_url) as response:
                if response.is_error:
                    await response.aread()
                    raise _space_http_error(
                        response,
                        phase="event_stream",
                        endpoint=event_url,
                    )
                async for line in response.aiter_lines():
                    if line.startswith("event:"):
                        current_event = line.split(":", 1)[1].strip()
                        continue
                    if not line.startswith("data:"):
                        continue
                    payload = line.split(":", 1)[1].strip()
                    if current_event == "error":
                        raise QwenSpaceEditError(
                            _classify_space_error(payload),
                            context={
                                "qwen_phase": "inference",
                                "qwen_api_path": urlparse(event_url).path,
                                "qwen_response_excerpt": _safe_space_response_excerpt(payload),
                            },
                        )
                    if current_event != "complete":
                        continue
                    return _qwen_result_from_payload(
                        event_id,
                        json.loads(payload),
                        max_output_bytes=config.image_gen_max_output_bytes,
                        base_hostname=urlparse(_base_url(config)).hostname or "",
                    )
    except QwenSpaceEditError:
        raise
    except json.JSONDecodeError as exc:
        raise QwenSpaceEditError(
            "qwen_response_json_invalid",
            context={"qwen_phase": "submit"},
        ) from exc
    except (httpx.TimeoutException,) as exc:
        raise QwenSpaceEditError(
            "qwen_submit_timeout",
            context={"qwen_phase": "submit"},
        ) from exc
    except httpx.HTTPError as exc:
        raise QwenSpaceEditError("qwen_submit_network_error") from exc
    except (TypeError, ValueError) as exc:
        raise QwenSpaceEditError("qwen_submit_failed") from exc
    raise QwenSpaceEditError("qwen_event_incomplete")


def _partial_path(remote: QwenRemoteResult, output_dir: Path) -> Path:
    token = sha256(remote.event_id.encode("utf-8")).hexdigest()[:24]
    return output_dir.resolve() / f".qwen_{token}.part"


async def download_qwen_result(
    config: AiChatConfig,
    remote: QwenRemoteResult,
    *,
    output_dir: Path | None = None,
) -> ImageArtifact:
    destination = (output_dir or DEFAULT_IMAGE_OUTPUT_DIR).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    if remote.result_data_url:
        try:
            _header, separator, encoded = remote.result_data_url.partition(",")
            if separator != ",":
                raise QwenSpaceEditError("qwen_result_invalid")
            content = base64.b64decode(encoded, validate=True)
            validated = validate_image_bytes(
                content,
                max_bytes=config.image_gen_max_output_bytes,
            )
            return _write_artifact(
                validated,
                operation="qwen_edit",
                output_dir=destination,
            )
        except QwenSpaceEditError:
            raise
        except (binascii.Error, ValueError) as exc:
            raise QwenSpaceEditError("qwen_result_base64_invalid") from exc
        except ImageGenError as exc:
            raise QwenSpaceEditError("qwen_result_invalid") from exc
    if not remote.result_url:
        raise QwenSpaceEditError("qwen_result_invalid")
    partial = _partial_path(remote, destination)
    headers = _auth_headers(config)
    timeout = httpx.Timeout(
        connect=min(config.qwen_space_download_timeout_seconds, 60),
        write=30,
        read=config.qwen_space_download_timeout_seconds,
        pool=60,
    )
    last_error: BaseException | None = None
    for _attempt in range(config.qwen_space_download_retries + 1):
        offset = partial.stat().st_size if partial.exists() else 0
        request_headers = dict(headers)
        if offset:
            request_headers["Range"] = f"bytes={offset}-"
        expected_size: int | None = None
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers=request_headers,
            ) as client:
                async with client.stream("GET", remote.result_url) as response:
                    response.raise_for_status()
                    append = offset > 0 and response.status_code == 206
                    if not append:
                        offset = 0
                    content_length = response.headers.get("content-length", "")
                    if content_length.isdigit():
                        expected_size = offset + int(content_length)
                    mode = "ab" if append else "wb"
                    with partial.open(mode) as output:
                        async for chunk in response.aiter_bytes():
                            if not chunk:
                                continue
                            output.write(chunk)
                            if output.tell() > config.image_gen_max_output_bytes:
                                raise QwenSpaceEditError("image_too_large")
            if expected_size is not None and partial.stat().st_size < expected_size:
                raise QwenSpaceEditError("qwen_download_incomplete")
            content = partial.read_bytes()
            validated = validate_image_bytes(
                content,
                max_bytes=config.image_gen_max_output_bytes,
            )
            artifact = _write_artifact(
                validated,
                operation="qwen_edit",
                output_dir=destination,
            )
            partial.unlink(missing_ok=True)
            return artifact
        except QwenSpaceEditError as exc:
            last_error = exc
        except (httpx.HTTPError, OSError) as exc:
            last_error = exc
        if _attempt < config.qwen_space_download_retries:
            await asyncio.sleep(0)
    raise QwenSpaceEditError("qwen_download_failed") from last_error


class QwenSpaceRuntime:
    """Process-local global lock and short-lived completed-result tickets."""

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self._tickets: dict[str, QwenResultTicket] = {}

    def remember_remote(
        self,
        key: str,
        remote: QwenRemoteResult,
        *,
        ttl_seconds: int,
        now: float | None = None,
    ) -> None:
        observed_at = monotonic() if now is None else now
        self._tickets[key] = QwenResultTicket(
            remote=remote,
            expires_at=observed_at + max(ttl_seconds, 1),
        )

    def remember_artifact(self, key: str, artifact: ImageArtifact) -> None:
        ticket = self._tickets.get(key)
        if ticket is None:
            return
        self._tickets[key] = QwenResultTicket(
            remote=ticket.remote,
            expires_at=ticket.expires_at,
            artifact=artifact,
        )

    def ticket(
        self,
        key: str,
        *,
        now: float | None = None,
    ) -> QwenResultTicket | None:
        ticket = self._tickets.get(key)
        if ticket is None:
            return None
        observed_at = monotonic() if now is None else now
        if ticket.expires_at <= observed_at:
            self._tickets.pop(key, None)
            return None
        return ticket
