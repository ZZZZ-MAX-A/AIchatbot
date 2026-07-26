from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import wave
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urlsplit

import httpx


TTS_SYNTHESIS_WORKFLOW = "tts_managed_lifecycle"
TTS_SYNTHESIS_CONFIRMATION = "run_registered_tts_synthesis"
TTS_SYNTHESIS_ACTION_HEADER = "manual-tts-synthesis-v1"
TTS_AUDIO_PREVIEW_ACTION_HEADER = "manual-tts-audio-preview-v1"
TTS_AUDIO_QUALITY_ACCEPT_ACTION_HEADER = "manual-tts-audio-quality-accept-v1"
TTS_AUDIO_QUALITY_ACCEPT_CONFIRMATION = "accept_latest_tts_audio_quality"
TTS_AUDIO_QUALITY_REJECT_ACTION_HEADER = "manual-tts-audio-quality-reject-v1"
TTS_AUDIO_QUALITY_REJECT_CONFIRMATION = "reject_latest_tts_audio_quality"
TTS_SYNTHESIS_FIXED_TEXT = "这是一次固定语音合成检查。"
TTS_SYNTHESIS_HEALTH_TIMEOUT_SECONDS = 2
TTS_SYNTHESIS_STARTUP_TIMEOUT_SECONDS = 45
TTS_SYNTHESIS_STARTUP_POLL_SECONDS = 0.5
TTS_SYNTHESIS_STOP_TIMEOUT_SECONDS = 10
TTS_SYNTHESIS_KILL_TIMEOUT_SECONDS = 5
TTS_SYNTHESIS_TIMEOUT_SECONDS = 180
TTS_SYNTHESIS_MAX_TOTAL_SECONDS = 20
TTS_SYNTHESIS_STARTUP_ATTENTION_MS = 30_000
TTS_SYNTHESIS_LATENCY_ATTENTION_MS = 120_000
TTS_SYNTHESIS_RESPONSE_BYTES_LIMIT = 16 * 1024
TTS_SYNTHESIS_OUTPUT_BYTES_LIMIT = 50 * 1024 * 1024
TTS_SYNTHESIS_DURATION_TOLERANCE_MS = 250
PROJECT_ROOT = Path(__file__).resolve().parents[3]
TTS_SYNTHESIS_OUTPUT_ROOT = PROJECT_ROOT / "temp_audio"
INDEXTTS_ROOT = PROJECT_ROOT / "tts-validation" / "index-tts-main"
INDEXTTS_PYTHON = INDEXTTS_ROOT / ".venv" / "Scripts" / "python.exe"
TTS_SERVICE_SCRIPT = PROJECT_ROOT / "src" / "plugins" / "ai_chat" / "tts_service.py"


class ManagedTtsProcess(Protocol):
    pid: int

    def poll(self) -> int | None: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...
    def wait(self, timeout: float | None = None) -> int: ...


@dataclass(frozen=True)
class TtsHttpResponse:
    status_code: int
    payload: object


@dataclass(frozen=True)
class TtsHealthEvidence:
    model_loaded: bool
    runtime_imported: bool


class TtsAudioPreviewStore:
    """Keeps one validated fixed diagnostic WAV in process memory only."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._run_id: int | None = None
        self._content: bytearray | None = None

    @staticmethod
    def _validate(content: bytes) -> None:
        if (
            not isinstance(content, bytes)
            or not 44 < len(content) <= TTS_SYNTHESIS_OUTPUT_BYTES_LIMIT
            or content[:4] != b"RIFF"
            or content[8:12] != b"WAVE"
        ):
            raise ValueError("TTS preview content is not a bounded WAV")

    def _clear_locked(self) -> None:
        if self._content is not None:
            self._content[:] = b"\x00" * len(self._content)
        self._content = None
        self._run_id = None

    def publish(self, content: bytes) -> None:
        self._validate(content)
        with self._lock:
            self._clear_locked()
            self._content = bytearray(content)

    def bind(self, run_id: int) -> bool:
        if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0:
            return False
        with self._lock:
            if self._content is None or self._run_id is not None:
                return False
            self._run_id = run_id
            return True

    def read(self, run_id: int) -> bytes | None:
        with self._lock:
            if self._content is None or self._run_id != run_id:
                return None
            return bytes(self._content)

    def clear(self, run_id: int | None = None) -> bool:
        with self._lock:
            if run_id is not None and self._run_id != run_id:
                return False
            existed = self._content is not None
            self._clear_locked()
            return existed


@dataclass(frozen=True)
class TtsArtifactCleanupEvidence:
    attempted: bool
    succeeded: bool
    output_file_retained: bool
    segment_directory_retained: bool
    elapsed_ms: int


@dataclass(frozen=True)
class TtsSynthesisEvidence:
    runtime_feature_enabled: bool
    service_health_checked: bool
    service_healthy: bool
    service_preexisting: bool
    service_start_attempted: bool
    service_started: bool
    service_owned_by_diagnostic: bool
    service_stop_attempted: bool
    service_stopped: bool
    model_loaded_before: bool
    runtime_imported_before: bool
    model_load_may_have_occurred: bool
    configured_voice_present: bool
    tts_called: bool
    output_contract_valid: bool
    output_file_created: bool
    output_bytes: int
    output_duration_ms: int
    output_retained: bool
    segment_directory_retained: bool
    artifact_cleanup_attempted: bool
    artifact_cleanup_succeeded: bool
    partial_artifact_state: str
    startup_elapsed_ms: int
    health_elapsed_ms: int
    synthesis_elapsed_ms: int
    cleanup_elapsed_ms: int
    elapsed_ms: int


class TtsSynthesisFailure(RuntimeError):
    def __init__(self, *, stage: str, code: str, code_label: str, **evidence: object) -> None:
        super().__init__(code)
        self.stage, self.code, self.code_label = stage, code, code_label
        defaults: dict[str, object] = {
            "runtime_feature_enabled": False,
            "service_health_checked": False,
            "service_healthy": False,
            "service_preexisting": False,
            "service_start_attempted": False,
            "service_started": False,
            "service_owned_by_diagnostic": False,
            "service_stop_attempted": False,
            "service_stopped": False,
            "model_loaded_before": False,
            "runtime_imported_before": False,
            "configured_voice_present": False,
            "tts_called": False,
            "output_file_created": False,
            "output_retained": False,
            "segment_directory_retained": False,
            "artifact_cleanup_attempted": False,
            "artifact_cleanup_succeeded": False,
            "partial_artifact_state": "none_before_post",
            "startup_elapsed_ms": 0,
            "health_elapsed_ms": 0,
            "synthesis_elapsed_ms": 0,
            "cleanup_elapsed_ms": 0,
            "elapsed_ms": 0,
        }
        defaults.update(evidence)
        for name, value in defaults.items():
            setattr(self, name, value)


@dataclass
class _State:
    artifact_id: str
    runtime_feature_enabled: bool = False
    configured_voice_present: bool = False
    service_health_checked: bool = False
    service_healthy: bool = False
    service_preexisting: bool = False
    service_start_attempted: bool = False
    service_started: bool = False
    service_owned_by_diagnostic: bool = False
    service_stop_attempted: bool = False
    service_stopped: bool = False
    model_loaded_before: bool = False
    runtime_imported_before: bool = False
    tts_called: bool = False
    output_file_created: bool = False
    startup_elapsed_ms: int = 0
    health_elapsed_ms: int = 0
    synthesis_elapsed_ms: int = 0
    process: ManagedTtsProcess | None = None
    preview_wav: bytes | None = field(default=None, repr=False)


def _elapsed(clock: Callable[[], int], started: int) -> int:
    return int(max((clock() - started) // 1_000_000, 0))


def _decode_content(status: int, content: bytes) -> TtsHttpResponse:
    if len(content) > TTS_SYNTHESIS_RESPONSE_BYTES_LIMIT:
        raise ValueError("response exceeds fixed byte limit")
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("response is not valid UTF-8 JSON") from exc
    return TtsHttpResponse(status, payload)


def _decode_response(response: httpx.Response) -> TtsHttpResponse:
    return _decode_content(response.status_code, response.content)


def _bounded(response: httpx.Response) -> TtsHttpResponse:
    content = bytearray()
    for chunk in response.iter_bytes():
        content.extend(chunk)
        if len(content) > TTS_SYNTHESIS_RESPONSE_BYTES_LIMIT:
            raise ValueError("response exceeds fixed byte limit")
    return _decode_content(response.status_code, bytes(content))


def _http_get_health(base_url: str) -> TtsHttpResponse:
    with httpx.Client(
        timeout=TTS_SYNTHESIS_HEALTH_TIMEOUT_SECONDS,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        with client.stream("GET", f"{base_url}/health") as response:
            return _bounded(response)


def _http_post_synthesis(base_url: str, payload: Mapping[str, object]) -> TtsHttpResponse:
    with httpx.Client(
        timeout=TTS_SYNTHESIS_TIMEOUT_SECONDS,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        with client.stream("POST", f"{base_url}/tts", json=dict(payload)) as response:
            return _bounded(response)


def _start_managed_tts_process(token: str) -> ManagedTtsProcess:
    if not INDEXTTS_PYTHON.is_file() or not TTS_SERVICE_SCRIPT.is_file():
        raise FileNotFoundError("TTS runtime is unavailable")
    env = os.environ.copy()
    env["TTS_LIFECYCLE_OWNER_TOKEN"] = token
    kwargs: dict[str, object] = {
        "cwd": str(INDEXTTS_ROOT),
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": False,
    }
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    return subprocess.Popen(
        [str(INDEXTTS_PYTHON), str(TTS_SERVICE_SCRIPT)],
        **kwargs,
    )


def _normalized_config(config: Any) -> tuple[str, str, str, bool]:
    base = str(getattr(config, "tts_service_url", "") or "").strip()
    voice = str(getattr(config, "tts_voice", "") or "").strip()
    emotion = str(getattr(config, "tts_emotion", "") or "").strip()
    enabled = bool(getattr(config, "enable_tts", False))
    try:
        parsed = urlsplit(base)
        port = parsed.port
    except ValueError as exc:
        raise TtsSynthesisFailure(
            stage="preflight",
            code="tts_invalid_configuration",
            code_label="TTS 服务地址配置无效",
            runtime_feature_enabled=enabled,
            configured_voice_present=bool(voice),
        ) from exc
    if (
        parsed.scheme != "http" or (parsed.hostname or "").lower() not in {"127.0.0.1", "localhost", "::1"}
        or port != 7861
        or parsed.username is not None or parsed.password is not None
        or parsed.query or parsed.fragment or parsed.path not in {"", "/"}
    ):
        raise TtsSynthesisFailure(stage="preflight", code="tts_non_loopback_service_rejected", code_label="TTS 生命周期诊断只允许 loopback HTTP 服务", runtime_feature_enabled=enabled, configured_voice_present=bool(voice))
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}", voice) is None or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", emotion) is None:
        raise TtsSynthesisFailure(stage="preflight", code="tts_invalid_configuration", code_label="TTS 音色或情绪配置无效", runtime_feature_enabled=enabled, configured_voice_present=bool(voice))
    return base.rstrip("/"), voice, emotion, enabled


def _mapping(response: TtsHttpResponse) -> Mapping[str, object]:
    if not isinstance(response.status_code, int) or isinstance(response.status_code, bool) or not isinstance(response.payload, Mapping):
        raise ValueError("response contract is invalid")
    return response.payload


def _health(
    response: TtsHttpResponse,
    fingerprint: str = "",
) -> TtsHealthEvidence:
    payload = _mapping(response)
    if response.status_code != 200 or payload.get("ok") is not True or type(payload.get("loaded")) is not bool or payload.get("language") != "zh":
        raise ValueError("health contract is invalid")
    runtime_imported = payload.get("runtime_imported", payload["loaded"])
    if type(runtime_imported) is not bool or (
        payload["loaded"] and not runtime_imported
    ):
        raise ValueError("health runtime contract is invalid")
    if fingerprint and payload.get("lifecycle_owner_fingerprint") != fingerprint:
        raise TtsSynthesisFailure(stage="service_start", code="tts_service_ownership_mismatch", code_label="新启动的 TTS 服务所有权证据不匹配")
    return TtsHealthEvidence(
        model_loaded=bool(payload["loaded"]),
        runtime_imported=runtime_imported,
    )


def _offline(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            ConnectionRefusedError,
        ),
    )


def _request_error(exc: Exception) -> tuple[str, str]:
    text = f"{type(exc).__name__}: {exc}".lower()[:256]
    if isinstance(exc, httpx.TimeoutException) or "timeout" in text:
        return "tts_request_timeout", "TTS 固定合成在限定时间内未完成"
    if isinstance(exc, httpx.RequestError) or "connection" in text:
        return "tts_connection_failed", "TTS 固定合成连接失败"
    return "tts_request_rejected", "TTS 固定合成响应无法验证"


def _wav(path: Path) -> tuple[int, int]:
    try:
        with wave.open(str(path), "rb") as reader:
            channels, width = reader.getnchannels(), reader.getsampwidth()
            rate, frames = reader.getframerate(), reader.getnframes()
    except (EOFError, OSError, wave.Error) as exc:
        raise TtsSynthesisFailure(stage="result_validation", code="tts_output_invalid_wav", code_label="TTS 音频产物不是有效 WAV", tts_called=True, output_file_created=True) from exc
    if channels not in {1, 2} or width not in {1, 2, 3, 4} or not 8_000 <= rate <= 192_000 or frames <= 0:
        raise TtsSynthesisFailure(stage="result_validation", code="tts_output_invalid_wav", code_label="TTS WAV 参数不在固定边界内", tts_called=True, output_file_created=True)
    return rate, frames


def _validate_output(payload: Mapping[str, object], *, output_root: Path, artifact_id: str) -> tuple[int, int, bytes]:
    raw, declared = payload.get("audio_path"), payload.get("duration_seconds")
    if not isinstance(raw, str) or not raw or len(raw) > 1024:
        raise TtsSynthesisFailure(stage="result_validation", code="tts_response_contract_mismatch", code_label="TTS 响应缺少产物标识", tts_called=True)
    if isinstance(declared, bool) or not isinstance(declared, (int, float)) or not 0 < float(declared) <= 20:
        raise TtsSynthesisFailure(stage="result_validation", code="tts_output_duration_invalid", code_label="TTS 返回时长无效", tts_called=True)
    candidate, expected_name = Path(raw), f"tts_{artifact_id}.wav"
    if not candidate.is_absolute() or candidate.name != expected_name:
        raise TtsSynthesisFailure(stage="result_validation", code="tts_output_outside_boundary", code_label="TTS 产物不属于本次诊断", tts_called=True)
    try:
        if output_root.is_symlink():
            raise ValueError
        root = output_root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
        if resolved != root / expected_name or candidate.is_symlink() or not resolved.is_file():
            raise ValueError
    except FileNotFoundError as exc:
        raise TtsSynthesisFailure(stage="result_validation", code="tts_output_missing", code_label="TTS 音频产物不存在", tts_called=True) from exc
    except (OSError, ValueError) as exc:
        raise TtsSynthesisFailure(stage="result_validation", code="tts_output_outside_boundary", code_label="TTS 产物越过固定边界", tts_called=True) from exc
    size = resolved.stat().st_size
    if size <= 44 or size > TTS_SYNTHESIS_OUTPUT_BYTES_LIMIT:
        raise TtsSynthesisFailure(stage="result_validation", code="tts_output_empty", code_label="TTS 音频为空或过大", tts_called=True, output_file_created=True)
    rate, frames = _wav(resolved)
    duration = round(frames * 1000 / rate)
    if duration <= 0 or duration > 20_000 or abs(duration - round(float(declared) * 1000)) > 250:
        raise TtsSynthesisFailure(stage="result_validation", code="tts_output_duration_invalid", code_label="TTS WAV 时长合同不一致", tts_called=True, output_file_created=True)
    segment_dir, segment = root / f"tts_{artifact_id}_segments", root / f"tts_{artifact_id}_segments" / "segment_01.wav"
    try:
        entries = list(segment_dir.iterdir())
        if segment_dir.is_symlink() or len(entries) != 1 or entries[0] != segment or segment.is_symlink() or not segment.is_file():
            raise ValueError
        segment_size = segment.stat().st_size
        if segment_size <= 44 or segment_size > TTS_SYNTHESIS_OUTPUT_BYTES_LIMIT:
            raise ValueError
        _wav(segment)
        segments = payload.get("segments")
        if not isinstance(segments, list) or len(segments) != 1 or not isinstance(segments[0], Mapping) or segments[0].get("index") != 1 or segments[0].get("bytes") != segment_size:
            raise ValueError
    except (OSError, ValueError) as exc:
        raise TtsSynthesisFailure(stage="result_validation", code="tts_output_invalid_wav", code_label="TTS 分段产物合同无效", tts_called=True, output_file_created=True) from exc
    try:
        preview_wav = resolved.read_bytes()
    except OSError as exc:
        raise TtsSynthesisFailure(stage="result_validation", code="tts_audio_preview_unavailable", code_label="TTS 音频无法进入临时听检", tts_called=True, output_file_created=True) from exc
    if len(preview_wav) != size:
        raise TtsSynthesisFailure(stage="result_validation", code="tts_audio_preview_unavailable", code_label="TTS 音频临时听检字节不一致", tts_called=True, output_file_created=True)
    return size, duration, preview_wav


def _lexists(path: Path) -> bool:
    return os.path.lexists(str(path))


def _cleanup_artifacts(output_root: Path, artifact_id: str, *, monotonic_ns: Callable[[], int] = time.monotonic_ns) -> TtsArtifactCleanupEvidence:
    started, succeeded = monotonic_ns(), True
    output_retained = segment_retained = False
    try:
        if output_root.is_symlink():
            raise OSError
        if not output_root.exists():
            return TtsArtifactCleanupEvidence(True, True, False, False, 0)
        root = output_root.resolve(strict=True)
        output, segment_dir = root / f"tts_{artifact_id}.wav", root / f"tts_{artifact_id}_segments"
        if _lexists(output):
            if output.is_dir() and not output.is_symlink():
                succeeded = False
            else:
                output.unlink()
        if _lexists(segment_dir):
            if segment_dir.is_symlink():
                segment_dir.unlink()
            elif segment_dir.is_dir():
                for item in list(segment_dir.iterdir()):
                    if item.is_symlink() or (item.is_file() and re.fullmatch(r"segment_[0-9]{2}\.wav", item.name)):
                        item.unlink()
                    else:
                        succeeded = False
                if not any(segment_dir.iterdir()):
                    segment_dir.rmdir()
            else:
                segment_dir.unlink()
        output_retained, segment_retained = _lexists(output), _lexists(segment_dir)
        succeeded = succeeded and not output_retained and not segment_retained
    except OSError:
        succeeded, output_retained, segment_retained = False, True, True
    return TtsArtifactCleanupEvidence(True, succeeded, output_retained, segment_retained, _elapsed(monotonic_ns, started))


def _stop_process(process: ManagedTtsProcess) -> tuple[bool, bool]:
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


class TtsSynthesisExecutor:
    def __init__(
        self,
        *,
        config_provider: Callable[[], Any],
        health_request: Callable[[str], TtsHttpResponse] = _http_get_health,
        synthesis_request: Callable[
            [str, Mapping[str, object]], TtsHttpResponse
        ] = _http_post_synthesis,
        process_starter: Callable[
            [str], ManagedTtsProcess
        ] = _start_managed_tts_process,
        artifact_cleaner: Callable[
            [Path, str], TtsArtifactCleanupEvidence
        ]
        | None = None,
        preview_store: TtsAudioPreviewStore | None = None,
        output_root: Path = TTS_SYNTHESIS_OUTPUT_ROOT,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        sleep: Callable[[float], None] = time.sleep,
        token_factory: Callable[[], str] = lambda: secrets.token_hex(32),
        artifact_id_factory: Callable[[], str] = lambda: secrets.token_hex(16),
    ) -> None:
        self.config_provider, self.health_request = config_provider, health_request
        self.synthesis_request, self.process_starter = synthesis_request, process_starter
        self.artifact_cleaner, self.output_root = artifact_cleaner, output_root
        self.preview_store = preview_store
        self.clock, self.sleep = monotonic_ns, sleep
        self.token_factory, self.artifact_id_factory = token_factory, artifact_id_factory

    def _wait_started(self, base: str, fingerprint: str, state: _State) -> None:
        started = self.clock()
        deadline = started + TTS_SYNTHESIS_STARTUP_TIMEOUT_SECONDS * 1_000_000_000
        while True:
            if state.process is None or state.process.poll() is not None:
                state.startup_elapsed_ms = _elapsed(self.clock, started)
                raise TtsSynthesisFailure(stage="service_start", code="tts_managed_process_exited_early", code_label="TTS 进程在健康就绪前退出")
            health_started = self.clock()
            try:
                health = _health(self.health_request(base), fingerprint)
                state.model_loaded_before = health.model_loaded
                state.runtime_imported_before = health.runtime_imported
                state.health_elapsed_ms += _elapsed(self.clock, health_started)
                state.service_health_checked = state.service_healthy = True
                state.service_started = state.service_owned_by_diagnostic = True
                state.startup_elapsed_ms = _elapsed(self.clock, started)
                return
            except TtsSynthesisFailure:
                raise
            except Exception:
                state.health_elapsed_ms += _elapsed(self.clock, health_started)
                state.service_health_checked = True
            if self.clock() >= deadline:
                state.startup_elapsed_ms = _elapsed(self.clock, started)
                raise TtsSynthesisFailure(stage="service_start", code="tts_service_start_timeout", code_label="TTS 服务未在固定时间内健康就绪")
            self.sleep(TTS_SYNTHESIS_STARTUP_POLL_SECONDS)

    def _run(self, state: _State, total: int) -> TtsSynthesisEvidence:
        try:
            config = self.config_provider()
        except Exception as exc:
            raise TtsSynthesisFailure(stage="preflight", code="tts_invalid_configuration", code_label="无法读取 TTS 配置") from exc
        base, voice, emotion, enabled = _normalized_config(config)
        state.runtime_feature_enabled, state.configured_voice_present = enabled, True
        health_started = self.clock()
        try:
            health = _health(self.health_request(base))
            state.model_loaded_before = health.model_loaded
            state.runtime_imported_before = health.runtime_imported
        except Exception as exc:
            state.health_elapsed_ms += _elapsed(self.clock, health_started)
            state.service_health_checked = True
            if not _offline(exc):
                raise TtsSynthesisFailure(stage="health_check", code="tts_health_contract_invalid", code_label="已有 TTS 服务健康响应无法验证") from exc
            token = self.token_factory()
            if re.fullmatch(r"[0-9a-f]{64}", token) is None:
                raise TtsSynthesisFailure(stage="preflight", code="tts_invalid_configuration", code_label="TTS 所有权标识无效")
            state.service_start_attempted = True
            try:
                state.process = self.process_starter(token)
            except Exception as start_exc:
                raise TtsSynthesisFailure(stage="service_start", code="tts_service_start_failed", code_label="无法启动受管理 TTS 服务") from start_exc
            self._wait_started(base, hashlib.sha256(token.encode()).hexdigest(), state)
        else:
            state.health_elapsed_ms += _elapsed(self.clock, health_started)
            state.service_health_checked = state.service_healthy = state.service_preexisting = True
        payload: Mapping[str, object] = {
            "artifact_id": state.artifact_id,
            "segments": [TTS_SYNTHESIS_FIXED_TEXT],
            "pauses_ms": [],
            "voice_id": voice,
            "language": "zh",
            "emotion": emotion,
            "max_total_seconds": TTS_SYNTHESIS_MAX_TOTAL_SECONDS,
            "bypass_cache": True,
        }
        synthesis_started, state.tts_called = self.clock(), True
        try:
            response = self.synthesis_request(base, payload)
            result = _mapping(response)
        except Exception as exc:
            state.synthesis_elapsed_ms = _elapsed(self.clock, synthesis_started)
            code, label = _request_error(exc)
            raise TtsSynthesisFailure(stage="model_synthesis", code=code, code_label=label, tts_called=True) from exc
        state.synthesis_elapsed_ms = _elapsed(self.clock, synthesis_started)
        if response.status_code != 200:
            raise TtsSynthesisFailure(stage="model_synthesis", code="tts_request_rejected", code_label="TTS 服务拒绝固定合成", tts_called=True)
        if result.get("ok") is not True:
            raise TtsSynthesisFailure(stage="model_synthesis", code="tts_synthesis_failed", code_label="TTS 服务未能完成固定合成", tts_called=True)
        size, duration, state.preview_wav = _validate_output(
            result,
            output_root=self.output_root,
            artifact_id=state.artifact_id,
        )
        state.output_file_created = True
        return TtsSynthesisEvidence(
            runtime_feature_enabled=enabled,
            service_health_checked=True,
            service_healthy=True,
            service_preexisting=state.service_preexisting,
            service_start_attempted=state.service_start_attempted,
            service_started=state.service_started,
            service_owned_by_diagnostic=state.service_owned_by_diagnostic,
            service_stop_attempted=False,
            service_stopped=False,
            model_loaded_before=state.model_loaded_before,
            runtime_imported_before=state.runtime_imported_before,
            model_load_may_have_occurred=not state.model_loaded_before,
            configured_voice_present=True,
            tts_called=True,
            output_contract_valid=True,
            output_file_created=True,
            output_bytes=size,
            output_duration_ms=duration,
            output_retained=True,
            segment_directory_retained=True,
            artifact_cleanup_attempted=False,
            artifact_cleanup_succeeded=False,
            partial_artifact_state="final_output_validated",
            startup_elapsed_ms=state.startup_elapsed_ms,
            health_elapsed_ms=state.health_elapsed_ms,
            synthesis_elapsed_ms=state.synthesis_elapsed_ms,
            cleanup_elapsed_ms=0,
            elapsed_ms=_elapsed(self.clock, total),
        )

    def _cleanup(self, state: _State) -> TtsArtifactCleanupEvidence:
        if not state.tts_called:
            return TtsArtifactCleanupEvidence(False, True, False, False, 0)
        try:
            if self.artifact_cleaner is not None:
                return self.artifact_cleaner(self.output_root, state.artifact_id)
            return _cleanup_artifacts(
                self.output_root,
                state.artifact_id,
                monotonic_ns=self.clock,
            )
        except Exception:
            return TtsArtifactCleanupEvidence(True, False, True, True, 0)

    @staticmethod
    def _stop_owned_process(state: _State) -> None:
        if state.process is None:
            return
        try:
            state.service_stop_attempted, state.service_stopped = _stop_process(
                state.process
            )
        except Exception:
            state.service_stop_attempted = True
            state.service_stopped = False

    @staticmethod
    def _apply_state_to_failure(
        failure: TtsSynthesisFailure,
        state: _State,
    ) -> None:
        for name in (
            "runtime_feature_enabled",
            "service_health_checked",
            "service_healthy",
            "service_preexisting",
            "service_start_attempted",
            "service_started",
            "service_owned_by_diagnostic",
            "service_stop_attempted",
            "service_stopped",
            "model_loaded_before",
            "runtime_imported_before",
            "configured_voice_present",
            "tts_called",
            "startup_elapsed_ms",
            "health_elapsed_ms",
            "synthesis_elapsed_ms",
        ):
            setattr(failure, name, getattr(state, name))
        failure.output_file_created = bool(
            state.output_file_created or failure.output_file_created
        )

    def __call__(self) -> TtsSynthesisEvidence:
        total, artifact = self.clock(), self.artifact_id_factory()
        if re.fullmatch(r"[0-9a-f]{32}", artifact) is None:
            raise TtsSynthesisFailure(stage="preflight", code="tts_invalid_configuration", code_label="TTS 产物标识无效")
        state, evidence, failure = _State(artifact), None, None
        try:
            evidence = self._run(state, total)
        except TtsSynthesisFailure as exc:
            failure = exc
        except Exception as exc:
            failure = TtsSynthesisFailure(stage="unexpected", code="tts_unexpected_probe_failure", code_label="TTS 生命周期诊断遇到未归类失败")
            failure.__cause__ = exc
        cleanup = self._cleanup(state)
        self._stop_owned_process(state)
        if failure:
            self._apply_state_to_failure(failure, state)
            failure.output_retained, failure.segment_directory_retained = cleanup.output_file_retained, cleanup.segment_directory_retained
            failure.artifact_cleanup_attempted, failure.artifact_cleanup_succeeded = cleanup.attempted, cleanup.succeeded
            failure.cleanup_elapsed_ms, failure.elapsed_ms = cleanup.elapsed_ms, _elapsed(self.clock, total)
            failure.partial_artifact_state = "failed_artifacts_removed" if state.tts_called and cleanup.succeeded else ("cleanup_incomplete" if state.tts_called else "none_before_post")
            raise failure
        assert evidence is not None
        if self.preview_store is not None and state.preview_wav is not None:
            self.preview_store.publish(state.preview_wav)
        state.preview_wav = None
        return replace(
            evidence,
            service_stop_attempted=state.service_stop_attempted,
            service_stopped=state.service_stopped,
            output_retained=cleanup.output_file_retained,
            segment_directory_retained=cleanup.segment_directory_retained,
            artifact_cleanup_attempted=cleanup.attempted,
            artifact_cleanup_succeeded=cleanup.succeeded,
            partial_artifact_state=(
                "artifacts_removed" if cleanup.succeeded else "cleanup_incomplete"
            ),
            cleanup_elapsed_ms=cleanup.elapsed_ms,
            elapsed_ms=_elapsed(self.clock, total),
        )
