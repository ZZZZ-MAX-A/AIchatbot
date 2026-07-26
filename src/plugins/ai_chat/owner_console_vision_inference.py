from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urlsplit

import httpx


VISION_INFERENCE_WORKFLOW = "vision_managed_lifecycle"
VISION_INFERENCE_CONFIRMATION = "run_registered_vision_inference"
VISION_INFERENCE_ACTION_HEADER = "manual-vision-inference-v1"
VISION_REFERENCE_PREVIEW_ACTION_HEADER = "manual-vision-reference-preview-v1"
VISION_RESPONSE_QUALITY_ACCEPT_ACTION_HEADER = (
    "manual-vision-response-quality-accept-v1"
)
VISION_RESPONSE_QUALITY_REJECT_ACTION_HEADER = (
    "manual-vision-response-quality-reject-v1"
)
VISION_RESPONSE_QUALITY_ACCEPT_CONFIRMATION = (
    "accept_latest_vision_response_quality"
)
VISION_RESPONSE_QUALITY_REJECT_CONFIRMATION = (
    "reject_latest_vision_response_quality"
)
VISION_FIXED_CONTRACT_VERSION = "vision.sticker.v1"
VISION_REFERENCE_STICKER_ID = "aike_affection_005"
VISION_REFERENCE_RELATIVE_FILE = "aike_affection_005.png"
VISION_FIXED_WIDTH = 500
VISION_FIXED_HEIGHT = 500
VISION_FIXED_PNG_BYTES = 162_977
VISION_FIXED_PNG_SHA256 = (
    "1b0db22d21fc7ed998cec9da0568c0987ccf9738eea69bf5c8c436609bfed249"
)
VISION_FIXED_NUM_CTX = 4096
VISION_DISCOVERY_TIMEOUT_SECONDS = 3
VISION_STARTUP_TIMEOUT_SECONDS = 30
VISION_STARTUP_POLL_SECONDS = 0.5
VISION_INFERENCE_TIMEOUT_SECONDS = 180
VISION_MODEL_CLEANUP_TIMEOUT_SECONDS = 5
VISION_MODEL_CLEANUP_POLL_SECONDS = 0.25
VISION_RESPONSE_BYTES_LIMIT = 64 * 1024
VISION_ANSWER_CHARS_LIMIT = 2048
VISION_STARTUP_ATTENTION_MS = 20_000
VISION_INFERENCE_LATENCY_ATTENTION_MS = 120_000
VISION_SERVICE_OWNERSHIP_BASIS = "offline_precheck_popen_handle"
VISION_FIXED_PROMPT = "请用自然中文客观描述这张图片中实际可见的内容。"
VISION_RESPONSE_MODE = "natural_text"
DEFAULT_OLLAMA_MODELS_ROOT = Path("D:/OllamaModels")
DEFAULT_VISION_REFERENCE_ROOT = (
    Path(__file__).resolve().parents[3] / "data" / "stickers"
)
VISION_REFERENCE_MANIFEST_BYTES_LIMIT = 1_048_576


class ManagedVisionProcess(Protocol):
    pid: int

    def poll(self) -> int | None: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...
    def wait(self, timeout: float | None = None) -> int: ...


@dataclass(frozen=True)
class VisionHttpResponse:
    status_code: int
    payload: object


@dataclass(frozen=True)
class VisionReferenceAsset:
    sticker_id: str
    content: bytes
    media_type: str
    width: int
    height: int


@dataclass(frozen=True)
class VisionInferenceEvidence:
    runtime_feature_enabled: bool
    configured_model: str
    fixed_image_contract: str
    fixed_image_bytes: int
    fixed_image_contract_valid: bool
    reference_sticker_id: str
    registered_reference_asset_read: bool
    expected_answer_disclosed_in_prompt: bool
    service_tags_checked: bool
    service_healthy: bool
    service_preexisting: bool
    service_start_attempted: bool
    service_started: bool
    service_owned_by_diagnostic: bool
    service_ownership_basis: str
    service_stop_attempted: bool
    service_stopped: bool
    model_available: bool
    model_residency_checked: bool
    model_loaded_before: bool
    keep_alive_zero_used: bool
    vision_called: bool
    response_contract_valid: bool
    response_mode: str
    structured_output_requested: bool
    semantic_contract_automatically_validated: bool
    owner_visual_judgment_required: bool
    response_preview: str
    response_description: str
    response_content_exposed_to_owner: bool
    usage_metadata_available: bool
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    model_cleanup_required: bool
    model_cleanup_verified: bool
    model_cleanup_poll_count: int
    startup_elapsed_ms: int
    discovery_elapsed_ms: int
    residency_elapsed_ms: int
    inference_elapsed_ms: int
    cleanup_elapsed_ms: int
    elapsed_ms: int


class VisionInferenceFailure(RuntimeError):
    def __init__(self, *, stage: str, code: str, code_label: str, **evidence: object) -> None:
        super().__init__(code)
        self.stage, self.code, self.code_label = stage, code, code_label
        defaults: dict[str, object] = {
            "runtime_feature_enabled": False,
            "configured_model": "",
            "fixed_image_contract": VISION_FIXED_CONTRACT_VERSION,
            "fixed_image_bytes": 0,
            "fixed_image_contract_valid": False,
            "reference_sticker_id": VISION_REFERENCE_STICKER_ID,
            "registered_reference_asset_read": False,
            "expected_answer_disclosed_in_prompt": False,
            "service_tags_checked": False,
            "service_healthy": False,
            "service_preexisting": False,
            "service_start_attempted": False,
            "service_started": False,
            "service_owned_by_diagnostic": False,
            "service_ownership_basis": "none",
            "service_stop_attempted": False,
            "service_stopped": False,
            "model_available": False,
            "model_residency_checked": False,
            "model_loaded_before": False,
            "keep_alive_zero_used": False,
            "vision_called": False,
            "response_contract_valid": False,
            "response_mode": VISION_RESPONSE_MODE,
            "structured_output_requested": False,
            "semantic_contract_automatically_validated": False,
            "owner_visual_judgment_required": True,
            "response_preview": "",
            "response_description": "",
            "response_content_exposed_to_owner": False,
            "usage_metadata_available": False,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "model_cleanup_required": False,
            "model_cleanup_verified": False,
            "model_cleanup_poll_count": 0,
            "startup_elapsed_ms": 0,
            "discovery_elapsed_ms": 0,
            "residency_elapsed_ms": 0,
            "inference_elapsed_ms": 0,
            "cleanup_elapsed_ms": 0,
            "elapsed_ms": 0,
        }
        defaults.update(evidence)
        for name, value in defaults.items():
            setattr(self, name, value)


@dataclass
class _State:
    configured_model: str = ""
    runtime_feature_enabled: bool = False
    fixed_image_bytes: int = 0
    fixed_image_contract_valid: bool = False
    reference_sticker_id: str = VISION_REFERENCE_STICKER_ID
    registered_reference_asset_read: bool = False
    expected_answer_disclosed_in_prompt: bool = False
    service_tags_checked: bool = False
    service_healthy: bool = False
    service_preexisting: bool = False
    service_start_attempted: bool = False
    service_started: bool = False
    service_owned_by_diagnostic: bool = False
    service_ownership_basis: str = "none"
    service_stop_attempted: bool = False
    service_stopped: bool = False
    model_available: bool = False
    model_residency_checked: bool = False
    model_loaded_before: bool = False
    keep_alive_zero_used: bool = False
    vision_called: bool = False
    response_mode: str = VISION_RESPONSE_MODE
    structured_output_requested: bool = False
    semantic_contract_automatically_validated: bool = False
    owner_visual_judgment_required: bool = True
    response_preview: str = ""
    response_description: str = ""
    response_content_exposed_to_owner: bool = False
    model_cleanup_required: bool = False
    model_cleanup_verified: bool = False
    model_cleanup_poll_count: int = 0
    startup_elapsed_ms: int = 0
    discovery_elapsed_ms: int = 0
    residency_elapsed_ms: int = 0
    inference_elapsed_ms: int = 0
    cleanup_elapsed_ms: int = 0
    process: ManagedVisionProcess | None = None


def _elapsed(clock: Callable[[], int], started: int) -> int:
    return int(max((clock() - started) // 1_000_000, 0))


def _fixed_image_contract_valid(image: bytes) -> bool:
    return (
        image.startswith(b"\x89PNG\r\n\x1a\n")
        and len(image) == VISION_FIXED_PNG_BYTES
        and hashlib.sha256(image).hexdigest() == VISION_FIXED_PNG_SHA256
        and int.from_bytes(image[16:20], "big") == VISION_FIXED_WIDTH
        and int.from_bytes(image[20:24], "big") == VISION_FIXED_HEIGHT
    )


def _is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = os.lstat(path)
    except OSError:
        return True
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    return stat.S_ISLNK(metadata.st_mode) or bool(
        attributes & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    )


def _load_registered_reference_asset(
    root: Path = DEFAULT_VISION_REFERENCE_ROOT,
) -> VisionReferenceAsset:
    expected_root = DEFAULT_VISION_REFERENCE_ROOT.resolve(strict=True)
    selected_root = root.resolve(strict=True)
    if selected_root != expected_root or _is_link_or_reparse(selected_root):
        raise ValueError("vision reference root is unsafe")
    manifest_path = selected_root / "library.json"
    approved_root = selected_root / "approved"
    if (
        _is_link_or_reparse(manifest_path)
        or _is_link_or_reparse(approved_root)
        or not approved_root.is_dir()
    ):
        raise ValueError("vision reference manifest boundary is unsafe")
    manifest_bytes = manifest_path.read_bytes()
    if not manifest_bytes or len(manifest_bytes) > VISION_REFERENCE_MANIFEST_BYTES_LIMIT:
        raise ValueError("vision reference manifest size is invalid")
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("vision reference manifest is invalid") from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != 2
        or not isinstance(manifest.get("stickers"), list)
    ):
        raise ValueError("vision reference manifest contract is invalid")
    matches = [
        item
        for item in manifest["stickers"]
        if isinstance(item, dict)
        and item.get("sticker_id") == VISION_REFERENCE_STICKER_ID
    ]
    if len(matches) != 1:
        raise ValueError("vision reference sticker registration is invalid")
    entry = matches[0]
    expected = {
        "relative_file": VISION_REFERENCE_RELATIVE_FILE,
        "sha256": VISION_FIXED_PNG_SHA256,
        "media_type": "image/png",
        "width": VISION_FIXED_WIDTH,
        "height": VISION_FIXED_HEIGHT,
        "bytes": VISION_FIXED_PNG_BYTES,
        "animated": False,
        "frame_count": 1,
        "duration_ms": 0,
        "scope": "owner_private",
        "enabled": True,
    }
    if any(entry.get(key) != value for key, value in expected.items()):
        raise ValueError("vision reference sticker contract drifted")
    file_path = approved_root / VISION_REFERENCE_RELATIVE_FILE
    resolved_file = file_path.resolve(strict=True)
    if (
        resolved_file.parent != approved_root.resolve(strict=True)
        or _is_link_or_reparse(file_path)
        or not file_path.is_file()
    ):
        raise ValueError("vision reference file boundary is unsafe")
    content = file_path.read_bytes()
    if not _fixed_image_contract_valid(content):
        raise ValueError("vision reference image contract is invalid")
    return VisionReferenceAsset(
        sticker_id=VISION_REFERENCE_STICKER_ID,
        content=content,
        media_type="image/png",
        width=VISION_FIXED_WIDTH,
        height=VISION_FIXED_HEIGHT,
    )


def _decode_content(status: int, content: bytes) -> VisionHttpResponse:
    if len(content) > VISION_RESPONSE_BYTES_LIMIT:
        raise ValueError("response exceeds fixed byte limit")
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("response is not valid UTF-8 JSON") from exc
    return VisionHttpResponse(status, payload)


def _bounded(response: httpx.Response) -> VisionHttpResponse:
    content = bytearray()
    for chunk in response.iter_bytes():
        content.extend(chunk)
        if len(content) > VISION_RESPONSE_BYTES_LIMIT:
            raise ValueError("response exceeds fixed byte limit")
    return _decode_content(response.status_code, bytes(content))


def _http_get(base_url: str, endpoint: str) -> VisionHttpResponse:
    with httpx.Client(
        timeout=VISION_DISCOVERY_TIMEOUT_SECONDS,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        with client.stream("GET", f"{base_url}{endpoint}") as response:
            return _bounded(response)


def _http_get_tags(base_url: str) -> VisionHttpResponse:
    return _http_get(base_url, "/api/tags")


def _http_get_ps(base_url: str) -> VisionHttpResponse:
    return _http_get(base_url, "/api/ps")


def _http_post_chat(base_url: str, payload: Mapping[str, object]) -> VisionHttpResponse:
    with httpx.Client(
        timeout=VISION_INFERENCE_TIMEOUT_SECONDS,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        with client.stream("POST", f"{base_url}/api/chat", json=dict(payload)) as response:
            return _bounded(response)


def _ollama_models_root() -> Path:
    raw = os.getenv("OLLAMA_MODELS", "").strip()
    root = Path(raw) if raw else DEFAULT_OLLAMA_MODELS_ROOT
    if not root.is_absolute() or not (root / "blobs").is_dir() or not (root / "manifests").is_dir():
        raise FileNotFoundError("Ollama models root is unavailable")
    return root.resolve(strict=True)


def _start_managed_ollama_process() -> ManagedVisionProcess:
    executable = shutil.which("ollama")
    if not executable:
        raise FileNotFoundError("Ollama runtime is unavailable")
    models_root = _ollama_models_root()
    env = os.environ.copy()
    env["OLLAMA_HOST"] = "127.0.0.1:11434"
    env["OLLAMA_MODELS"] = str(models_root)
    kwargs: dict[str, object] = {
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": False,
    }
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    return subprocess.Popen([executable, "serve"], **kwargs)


def _normalized_config(config: Any) -> tuple[str, str, bool]:
    base = str(getattr(config, "vision_ollama_base_url", "") or "").strip()
    model = str(getattr(config, "vision_model", "") or "").strip()
    enabled = bool(getattr(config, "enable_vision", False))
    try:
        parsed = urlsplit(base)
        port = parsed.port
    except ValueError as exc:
        raise VisionInferenceFailure(
            stage="preflight",
            code="vision_invalid_configuration",
            code_label="视觉服务地址配置无效",
            runtime_feature_enabled=enabled,
        ) from exc
    if (
        parsed.scheme != "http"
        or (parsed.hostname or "").lower() not in {"127.0.0.1", "localhost", "::1"}
        or port != 11434
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise VisionInferenceFailure(
            stage="preflight",
            code="vision_non_loopback_service_rejected",
            code_label="视觉诊断只允许固定 loopback Ollama 服务",
            runtime_feature_enabled=enabled,
        )
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}", model) is None:
        raise VisionInferenceFailure(
            stage="preflight",
            code="vision_invalid_configuration",
            code_label="视觉模型配置无效",
            runtime_feature_enabled=enabled,
        )
    return base.rstrip("/"), model, enabled


def _mapping(response: VisionHttpResponse) -> Mapping[str, object]:
    if (
        not isinstance(response.status_code, int)
        or isinstance(response.status_code, bool)
        or not isinstance(response.payload, Mapping)
    ):
        raise ValueError("response contract is invalid")
    return response.payload


def _model_names(response: VisionHttpResponse) -> tuple[str, ...]:
    payload = _mapping(response)
    if response.status_code != 200 or not isinstance(payload.get("models"), list):
        raise ValueError("Ollama model list contract is invalid")
    names: list[str] = []
    for item in payload["models"]:
        if not isinstance(item, Mapping):
            raise ValueError("Ollama model entry contract is invalid")
        raw = item.get("name", item.get("model"))
        if not isinstance(raw, str) or not raw or len(raw) > 200:
            raise ValueError("Ollama model name contract is invalid")
        names.append(raw)
    return tuple(names)


def _offline(exc: Exception) -> bool:
    return isinstance(exc, (httpx.ConnectError, ConnectionRefusedError))


def _request_error(exc: Exception) -> tuple[str, str]:
    text = f"{type(exc).__name__}: {exc}".lower()[:256]
    if isinstance(exc, httpx.TimeoutException) or "timeout" in text:
        return "vision_request_timeout", "视觉固定推理在限定时间内未完成"
    if isinstance(exc, httpx.RequestError) or "connection" in text:
        return "vision_connection_failed", "视觉固定推理连接失败"
    if isinstance(exc, ValueError) and "byte limit" in text:
        return "vision_response_too_large", "视觉响应超过固定大小上限"
    return "vision_request_rejected", "视觉固定推理响应无法验证"


def _integer_token(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _low_quality_answer(answer: str) -> bool:
    compact = "".join(answer.split())
    if not compact:
        return True
    if len(compact) >= 4 and len(set(compact)) <= 2:
        return True
    return re.search(r"(.{1,16})\1{3,}", compact) is not None


def _safe_response_preview(answer: str) -> str:
    bidi_controls = {
        "\u061c",
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }
    cleaned = "".join(
        character
        for character in answer
        if character not in bidi_controls
        and (character in {"\n", "\t"} or ord(character) >= 32)
    )
    return cleaned.strip()[:VISION_ANSWER_CHARS_LIMIT]


def _validate_chat(
    response: VisionHttpResponse,
) -> tuple[bool, int | None, int | None, int | None, str, str]:
    payload = _mapping(response)
    if response.status_code != 200:
        raise VisionInferenceFailure(
            stage="model_inference",
            code="vision_request_rejected",
            code_label="Ollama 拒绝视觉固定推理",
            vision_called=True,
        )
    if payload.get("done") is not True or not isinstance(payload.get("message"), Mapping):
        raise VisionInferenceFailure(
            stage="result_validation",
            code="vision_response_contract_mismatch",
            code_label="视觉响应结构无法证明推理完成",
            vision_called=True,
        )
    message = payload["message"]
    if message.get("role") != "assistant" or message.get("tool_calls") not in (None, []):
        raise VisionInferenceFailure(
            stage="result_validation",
            code="vision_response_contract_mismatch",
            code_label="视觉回答角色或工具边界不符合固定合同",
            vision_called=True,
        )
    answer = message.get("content")
    if not isinstance(answer, str) or not answer.strip():
        raise VisionInferenceFailure(
            stage="result_validation",
            code="vision_empty_response",
            code_label="视觉模型没有返回图片内容",
            vision_called=True,
        )
    preview = _safe_response_preview(answer)
    if len(answer) > VISION_ANSWER_CHARS_LIMIT:
        raise VisionInferenceFailure(
            stage="result_validation",
            code="vision_response_too_large",
            code_label="视觉回答超过固定长度上限",
            vision_called=True,
            response_preview=preview,
            response_content_exposed_to_owner=bool(preview),
        )
    if (
        not preview
        or _low_quality_answer(preview)
        or len(re.findall(r"[\u4e00-\u9fff]", preview)) < 8
    ):
        raise VisionInferenceFailure(
            stage="result_validation",
            code="vision_low_quality_response",
            code_label="视觉模型没有返回可供主人判断的自然中文描述",
            vision_called=True,
            response_preview=preview,
            response_content_exposed_to_owner=bool(preview),
        )
    input_tokens = _integer_token(payload.get("prompt_eval_count"))
    output_tokens = _integer_token(payload.get("eval_count"))
    available = input_tokens is not None and output_tokens is not None
    total_tokens = input_tokens + output_tokens if available else None
    return (
        available,
        input_tokens,
        output_tokens,
        total_tokens,
        preview,
        preview,
    )


def _stop_process(process: ManagedVisionProcess) -> tuple[bool, bool]:
    if process.poll() is not None:
        return False, True
    try:
        process.terminate()
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            return True, False
    except OSError:
        return True, False
    return True, process.poll() is not None


class VisionInferenceExecutor:
    def __init__(
        self,
        *,
        config_provider: Callable[[], Any],
        tags_request: Callable[[str], VisionHttpResponse] = _http_get_tags,
        ps_request: Callable[[str], VisionHttpResponse] = _http_get_ps,
        chat_request: Callable[[str, Mapping[str, object]], VisionHttpResponse] = _http_post_chat,
        process_starter: Callable[[], ManagedVisionProcess] = _start_managed_ollama_process,
        reference_loader: Callable[[], VisionReferenceAsset] = (
            _load_registered_reference_asset
        ),
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config_provider = config_provider
        self.tags_request, self.ps_request = tags_request, ps_request
        self.chat_request, self.process_starter = chat_request, process_starter
        self.reference_loader = reference_loader
        self.clock, self.sleep = monotonic_ns, sleep

    def _wait_started(self, base: str, state: _State) -> tuple[str, ...]:
        started = self.clock()
        deadline = started + VISION_STARTUP_TIMEOUT_SECONDS * 1_000_000_000
        while True:
            if state.process is None:
                raise VisionInferenceFailure(
                    stage="service_start",
                    code="vision_service_ownership_ambiguous",
                    code_label="视觉诊断无法证明新服务进程所有权",
                )
            if state.process.poll() is not None:
                try:
                    names = _model_names(self.tags_request(base))
                except Exception:
                    state.startup_elapsed_ms = _elapsed(self.clock, started)
                    raise VisionInferenceFailure(
                        stage="service_start",
                        code="vision_managed_process_exited_early",
                        code_label="Ollama 进程在服务就绪前退出",
                    )
                state.service_tags_checked = state.service_healthy = True
                state.startup_elapsed_ms = _elapsed(self.clock, started)
                state.model_available = state.configured_model in names
                raise VisionInferenceFailure(
                    stage="service_start",
                    code="vision_service_ownership_ambiguous",
                    code_label="端口已出现服务，但本次进程所有权无法确认",
                )
            request_started = self.clock()
            try:
                names = _model_names(self.tags_request(base))
            except Exception:
                state.discovery_elapsed_ms += _elapsed(self.clock, request_started)
                state.service_tags_checked = True
            else:
                state.discovery_elapsed_ms += _elapsed(self.clock, request_started)
                state.service_tags_checked = state.service_healthy = True
                state.service_started = state.service_owned_by_diagnostic = True
                state.service_ownership_basis = VISION_SERVICE_OWNERSHIP_BASIS
                state.startup_elapsed_ms = _elapsed(self.clock, started)
                return names
            if self.clock() >= deadline:
                state.startup_elapsed_ms = _elapsed(self.clock, started)
                raise VisionInferenceFailure(
                    stage="service_start",
                    code="vision_service_start_timeout",
                    code_label="Ollama 未在固定时间内就绪",
                )
            self.sleep(VISION_STARTUP_POLL_SECONDS)

    def _discover(self, base: str, state: _State) -> tuple[str, ...]:
        started = self.clock()
        try:
            names = _model_names(self.tags_request(base))
        except Exception as exc:
            state.discovery_elapsed_ms += _elapsed(self.clock, started)
            state.service_tags_checked = True
            if not _offline(exc):
                raise VisionInferenceFailure(
                    stage="service_discovery",
                    code="vision_service_contract_invalid",
                    code_label="已有 Ollama 服务响应无法验证",
                ) from exc
            state.service_start_attempted = True
            try:
                state.process = self.process_starter()
            except Exception as start_exc:
                raise VisionInferenceFailure(
                    stage="service_start",
                    code="vision_service_start_failed",
                    code_label="无法启动受管理 Ollama 服务",
                ) from start_exc
            return self._wait_started(base, state)
        state.discovery_elapsed_ms += _elapsed(self.clock, started)
        state.service_tags_checked = state.service_healthy = state.service_preexisting = True
        return names

    def _residency(self, base: str, state: _State) -> bool:
        started = self.clock()
        try:
            names = _model_names(self.ps_request(base))
        except Exception as exc:
            state.residency_elapsed_ms += _elapsed(self.clock, started)
            raise VisionInferenceFailure(
                stage="model_residency",
                code="vision_model_residency_unavailable",
                code_label="无法验证视觉模型推理前驻留状态",
            ) from exc
        state.residency_elapsed_ms += _elapsed(self.clock, started)
        state.model_residency_checked = True
        return state.configured_model in names

    def _cleanup_model(self, base: str, state: _State) -> None:
        if not state.model_cleanup_required:
            state.model_cleanup_verified = True
            return
        started = self.clock()
        deadline = started + VISION_MODEL_CLEANUP_TIMEOUT_SECONDS * 1_000_000_000
        while True:
            state.model_cleanup_poll_count += 1
            try:
                names = _model_names(self.ps_request(base))
                if state.configured_model not in names:
                    state.model_cleanup_verified = True
                    break
            except Exception:
                state.model_cleanup_verified = False
            if self.clock() >= deadline:
                break
            remaining_seconds = max((deadline - self.clock()) / 1_000_000_000, 0)
            self.sleep(min(VISION_MODEL_CLEANUP_POLL_SECONDS, remaining_seconds))
        state.cleanup_elapsed_ms = _elapsed(self.clock, started)

    @staticmethod
    def _stop_owned_process(state: _State) -> None:
        if state.process is None:
            return
        try:
            state.service_stop_attempted, state.service_stopped = _stop_process(state.process)
        except Exception:
            state.service_stop_attempted, state.service_stopped = True, False

    @staticmethod
    def _apply_state_to_failure(failure: VisionInferenceFailure, state: _State) -> None:
        for name in (
            "runtime_feature_enabled",
            "configured_model",
            "fixed_image_bytes",
            "fixed_image_contract_valid",
            "reference_sticker_id",
            "registered_reference_asset_read",
            "expected_answer_disclosed_in_prompt",
            "service_tags_checked",
            "service_healthy",
            "service_preexisting",
            "service_start_attempted",
            "service_started",
            "service_owned_by_diagnostic",
            "service_ownership_basis",
            "service_stop_attempted",
            "service_stopped",
            "model_available",
            "model_residency_checked",
            "model_loaded_before",
            "keep_alive_zero_used",
            "vision_called",
            "response_mode",
            "structured_output_requested",
            "semantic_contract_automatically_validated",
            "owner_visual_judgment_required",
            "response_preview",
            "response_description",
            "response_content_exposed_to_owner",
            "model_cleanup_required",
            "model_cleanup_verified",
            "model_cleanup_poll_count",
            "startup_elapsed_ms",
            "discovery_elapsed_ms",
            "residency_elapsed_ms",
            "inference_elapsed_ms",
            "cleanup_elapsed_ms",
        ):
            setattr(failure, name, getattr(state, name))

    def _run(
        self,
        state: _State,
        total_started: int,
        config: Any,
    ) -> VisionInferenceEvidence:
        base, model, enabled = _normalized_config(config)
        state.configured_model, state.runtime_feature_enabled = model, enabled
        try:
            reference = self.reference_loader()
        except Exception as exc:
            raise VisionInferenceFailure(
                stage="preflight",
                code="vision_reference_asset_unavailable",
                code_label="视觉固定表情参考资产不可用或合同已漂移",
                runtime_feature_enabled=enabled,
            ) from exc
        state.reference_sticker_id = reference.sticker_id
        state.registered_reference_asset_read = True
        state.fixed_image_bytes = len(reference.content)
        state.fixed_image_contract_valid = _fixed_image_contract_valid(
            reference.content
        )
        if not state.fixed_image_contract_valid:
            raise VisionInferenceFailure(
                stage="preflight",
                code="vision_fixed_image_contract_invalid",
                code_label="视觉固定表情图片合同无效",
            )
        names = self._discover(base, state)
        state.model_available = model in names
        if not state.model_available:
            raise VisionInferenceFailure(
                stage="model_discovery",
                code="vision_model_not_found",
                code_label="当前 Ollama 服务没有配置的视觉模型",
            )
        state.model_loaded_before = self._residency(base, state)
        state.model_cleanup_required = not state.model_loaded_before
        state.keep_alive_zero_used = state.model_cleanup_required
        payload: dict[str, object] = {
            "model": model,
            "stream": False,
            "options": {"num_ctx": VISION_FIXED_NUM_CTX, "temperature": 0},
            "messages": [
                {
                    "role": "user",
                    "content": VISION_FIXED_PROMPT,
                    "images": [
                        base64.b64encode(reference.content).decode("ascii")
                    ],
                }
            ],
        }
        if state.keep_alive_zero_used:
            payload["keep_alive"] = 0
        inference_started, state.vision_called = self.clock(), True
        try:
            response = self.chat_request(base, payload)
            (
                usage,
                input_tokens,
                output_tokens,
                total_tokens,
                state.response_preview,
                state.response_description,
            ) = _validate_chat(response)
            state.response_content_exposed_to_owner = bool(
                state.response_preview
            )
        except VisionInferenceFailure as exc:
            state.inference_elapsed_ms = _elapsed(self.clock, inference_started)
            state.response_preview = str(
                getattr(exc, "response_preview", "")
            )
            state.response_description = str(
                getattr(exc, "response_description", "")
            )
            state.response_content_exposed_to_owner = bool(
                getattr(exc, "response_content_exposed_to_owner", False)
            )
            raise
        except Exception as exc:
            state.inference_elapsed_ms = _elapsed(self.clock, inference_started)
            code, label = _request_error(exc)
            raise VisionInferenceFailure(
                stage="model_inference",
                code=code,
                code_label=label,
                vision_called=True,
            ) from exc
        state.inference_elapsed_ms = _elapsed(self.clock, inference_started)
        return VisionInferenceEvidence(
            runtime_feature_enabled=enabled,
            configured_model=model,
            fixed_image_contract=VISION_FIXED_CONTRACT_VERSION,
            fixed_image_bytes=len(reference.content),
            fixed_image_contract_valid=True,
            reference_sticker_id=state.reference_sticker_id,
            registered_reference_asset_read=True,
            expected_answer_disclosed_in_prompt=False,
            service_tags_checked=state.service_tags_checked,
            service_healthy=state.service_healthy,
            service_preexisting=state.service_preexisting,
            service_start_attempted=state.service_start_attempted,
            service_started=state.service_started,
            service_owned_by_diagnostic=state.service_owned_by_diagnostic,
            service_ownership_basis=state.service_ownership_basis,
            service_stop_attempted=False,
            service_stopped=False,
            model_available=True,
            model_residency_checked=True,
            model_loaded_before=state.model_loaded_before,
            keep_alive_zero_used=state.keep_alive_zero_used,
            vision_called=True,
            response_contract_valid=True,
            response_mode=VISION_RESPONSE_MODE,
            structured_output_requested=False,
            semantic_contract_automatically_validated=False,
            owner_visual_judgment_required=True,
            response_preview=state.response_preview,
            response_description=state.response_description,
            response_content_exposed_to_owner=(
                state.response_content_exposed_to_owner
            ),
            usage_metadata_available=usage,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            model_cleanup_required=state.model_cleanup_required,
            model_cleanup_verified=False,
            model_cleanup_poll_count=0,
            startup_elapsed_ms=state.startup_elapsed_ms,
            discovery_elapsed_ms=state.discovery_elapsed_ms,
            residency_elapsed_ms=state.residency_elapsed_ms,
            inference_elapsed_ms=state.inference_elapsed_ms,
            cleanup_elapsed_ms=0,
            elapsed_ms=_elapsed(self.clock, total_started),
        )

    def __call__(self) -> VisionInferenceEvidence:
        total_started = self.clock()
        state, evidence, failure = _State(), None, None
        base = ""
        try:
            try:
                config = self.config_provider()
                base, _, _ = _normalized_config(config)
            except VisionInferenceFailure:
                raise
            except Exception as exc:
                raise VisionInferenceFailure(
                    stage="preflight",
                    code="vision_invalid_configuration",
                    code_label="无法读取视觉配置",
                ) from exc
            evidence = self._run(state, total_started, config)
        except VisionInferenceFailure as exc:
            failure = exc
        except Exception as exc:
            failure = VisionInferenceFailure(
                stage="unexpected",
                code="vision_unexpected_probe_failure",
                code_label="视觉固定诊断遇到未归类失败",
            )
            failure.__cause__ = exc
        if base and state.vision_called:
            self._cleanup_model(base, state)
        self._stop_owned_process(state)
        if failure is not None:
            self._apply_state_to_failure(failure, state)
            failure.elapsed_ms = _elapsed(self.clock, total_started)
            raise failure
        assert evidence is not None
        return replace(
            evidence,
            model_cleanup_verified=state.model_cleanup_verified,
            model_cleanup_poll_count=state.model_cleanup_poll_count,
            service_stop_attempted=state.service_stop_attempted,
            service_stopped=state.service_stopped,
            cleanup_elapsed_ms=state.cleanup_elapsed_ms,
            elapsed_ms=_elapsed(self.clock, total_started),
        )
