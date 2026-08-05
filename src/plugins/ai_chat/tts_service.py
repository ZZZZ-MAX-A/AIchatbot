import asyncio
import gc
import hashlib
import json
import os
import re
import sys
import time
import uuid
import wave
from array import array
from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from typing import Any, Callable

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INDEXTTS_ROOT = PROJECT_ROOT / "tts-validation" / "index-tts-main"
TEMP_DIR = PROJECT_ROOT / "temp_audio"

if str(INDEXTTS_ROOT) not in sys.path:
    sys.path.insert(0, str(INDEXTTS_ROOT))

EMOTION_PRESETS = {
    "calm": {"emo_last": 0.25, "emo_alpha": 0.5},
    "affection": {"emo_last": 0.35, "emo_alpha": 0.55},
    "soft": {"emo_last": 0.45, "emo_alpha": 0.6},
    "warm": {"emo_last": 0.60, "emo_alpha": 0.65},
}

IDLE_UNLOAD_SECONDS = 600
DEFAULT_MAX_MEL_TOKENS = 700
DEFAULT_SILENCE_MS = 550
TAIL_NOISE_WINDOW_MS = 20
TAIL_NOISE_THRESHOLD = 0.01
TAIL_NOISE_SAFETY_MS = 60
TAIL_NOISE_FADE_MS = 20
TAIL_NOISE_OUTPUT_SILENCE_MS = 80
TAIL_NOISE_MIN_TRIM_MS = 80
LIFECYCLE_OWNER_TOKEN = os.getenv("TTS_LIFECYCLE_OWNER_TOKEN", "")
LIFECYCLE_OWNER_FINGERPRINT = (
    hashlib.sha256(LIFECYCLE_OWNER_TOKEN.encode("utf-8")).hexdigest()
    if LIFECYCLE_OWNER_TOKEN
    else ""
)


@dataclass(frozen=True)
class EngineConfig:
    language: str
    root: Path
    model_dir: Path
    config_path: Path
    voice_dir: Path
    default_voice_id: str
    default_silence_ms: int
    max_mel_tokens: int


@dataclass(frozen=True)
class TtsRuntime:
    torch_module: Any
    model_class: Any


def load_tts_runtime() -> TtsRuntime:
    import torch
    from indextts.infer_v2 import IndexTTS2

    return TtsRuntime(
        torch_module=torch,
        model_class=IndexTTS2,
    )


ENGINE_CONFIG = EngineConfig(
    language="zh",
    root=INDEXTTS_ROOT,
    model_dir=INDEXTTS_ROOT / "checkpoints",
    config_path=INDEXTTS_ROOT / "checkpoints" / "config.yaml",
    voice_dir=PROJECT_ROOT / "voice-samples" / "reference" / "zh",
    default_voice_id="zh_kelin_raw_20260625_222137",
    default_silence_ms=DEFAULT_SILENCE_MS,
    max_mel_tokens=DEFAULT_MAX_MEL_TOKENS,
)


class TtsRequest(BaseModel):
    artifact_id: str = ""
    segments: list[str]
    pauses_ms: list[int] | None = None
    voice_id: str = "zh_kelin_raw_20260625_222137"
    language: str = "zh"
    emotion: str = "affection"
    max_total_seconds: int = 60
    bypass_cache: bool = False
    trim_trailing_noise: bool = False


class ModelState:
    def __init__(
        self,
        runtime_loader: Callable[[], TtsRuntime] = load_tts_runtime,
    ) -> None:
        self.tts: Any | None = None
        self.runtime: TtsRuntime | None = None
        self.runtime_loader = runtime_loader
        self.last_used_at = 0.0
        self.lock = asyncio.Lock()

    def loaded(self) -> bool:
        return self.tts is not None

    async def ensure_loaded(self) -> Any:
        async with self.lock:
            if self.tts is None:
                started = time.perf_counter()
                if self.runtime is None:
                    self.runtime = self.runtime_loader()
                self.tts = self.runtime.model_class(
                    cfg_path=str(ENGINE_CONFIG.config_path),
                    model_dir=str(ENGINE_CONFIG.model_dir),
                    use_fp16=True,
                    use_cuda_kernel=False,
                    use_deepspeed=False,
                )
                print(f"model_loaded language=zh seconds={time.perf_counter() - started:.3f}", flush=True)
            self.last_used_at = time.monotonic()
            return self.tts

    async def unload_if_idle(self) -> None:
        async with self.lock:
            if self.tts is None:
                return
            if time.monotonic() - self.last_used_at < IDLE_UNLOAD_SECONDS:
                return
            self.tts = None
            gc.collect()
            if (
                self.runtime is not None
                and self.runtime.torch_module.cuda.is_available()
            ):
                self.runtime.torch_module.cuda.empty_cache()
            print("model_unloaded language=zh reason=idle", flush=True)


state = ModelState()
app = FastAPI(title="AI Chatbot Local TTS Service")


def voice_path(voice_id: str) -> Path:
    if not voice_id.strip():
        voice_id = ENGINE_CONFIG.default_voice_id
    safe_id = "".join(char for char in voice_id if char.isalnum() or char in {"_", "-"})
    path = ENGINE_CONFIG.voice_dir / f"{safe_id}.wav"
    if not path.exists():
        raise FileNotFoundError(f"voice not found: {safe_id}")
    return path


def emotion_preset(emotion: str) -> dict[str, float]:
    selected = EMOTION_PRESETS.get(emotion, EMOTION_PRESETS["affection"])
    return {
        "emo_last": float(selected["emo_last"]),
        "emo_alpha": float(selected["emo_alpha"]),
    }


def trim_trailing_low_energy_noise(path: Path) -> bool:
    with wave.open(str(path), "rb") as reader:
        params = reader.getparams()
        channels = reader.getnchannels()
        sample_width = reader.getsampwidth()
        frame_rate = reader.getframerate()
        frame_count = reader.getnframes()
        raw_frames = reader.readframes(frame_count)

    if sample_width != 2 or channels <= 0 or frame_rate <= 0 or frame_count <= 0:
        return False

    samples = array("h")
    samples.frombytes(raw_frames)
    if sys.byteorder != "little":
        samples.byteswap()

    window_frames = max(int(frame_rate * TAIL_NOISE_WINDOW_MS / 1000), 1)
    window_samples = window_frames * channels
    last_active_frame = 0
    for start in range(0, len(samples) - window_samples + 1, window_samples):
        block = samples[start : start + window_samples]
        rms = sqrt(sum(value * value for value in block) / len(block)) / 32768.0
        if rms >= TAIL_NOISE_THRESHOLD:
            last_active_frame = min(start // channels + window_frames, frame_count)

    if last_active_frame <= 0:
        return False

    safety_frames = int(frame_rate * TAIL_NOISE_SAFETY_MS / 1000)
    retained_frames = min(last_active_frame + safety_frames, frame_count)
    trim_frames = frame_count - retained_frames
    minimum_trim_frames = int(frame_rate * TAIL_NOISE_MIN_TRIM_MS / 1000)
    if trim_frames < minimum_trim_frames:
        return False

    retained = array("h", samples[: retained_frames * channels])
    fade_frames = min(
        int(frame_rate * TAIL_NOISE_FADE_MS / 1000),
        retained_frames,
    )
    fade_start = retained_frames - fade_frames
    for frame_index in range(fade_frames):
        gain = (fade_frames - frame_index - 1) / max(fade_frames, 1)
        sample_start = (fade_start + frame_index) * channels
        for channel_index in range(channels):
            index = sample_start + channel_index
            retained[index] = int(retained[index] * gain)

    output_silence_frames = int(
        frame_rate * TAIL_NOISE_OUTPUT_SILENCE_MS / 1000
    )
    retained.extend([0] * output_silence_frames * channels)

    if sys.byteorder != "little":
        retained.byteswap()
    temporary = path.with_suffix(".tail-clean.tmp.wav")
    try:
        with wave.open(str(temporary), "wb") as writer:
            writer.setparams(params)
            writer.writeframes(retained.tobytes())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def concat_wavs(paths: list[Path], output_path: Path, pauses_ms: list[int]) -> float:
    params = None
    chunks: list[bytes] = []
    frame_count = 0
    for path in paths:
        with wave.open(str(path), "rb") as reader:
            current = reader.getparams()
            if params is None:
                params = current
            elif (
                current.nchannels != params.nchannels
                or current.sampwidth != params.sampwidth
                or current.framerate != params.framerate
                or current.comptype != params.comptype
            ):
                raise ValueError(f"WAV format mismatch: {path}")
            frames = reader.getnframes()
            chunks.append(reader.readframes(frames))
            frame_count += frames

    if params is None:
        raise ValueError("No WAV files to concatenate")

    with wave.open(str(output_path), "wb") as writer:
        writer.setparams(params)
        for index, chunk in enumerate(chunks):
            if index:
                silence_ms = pauses_ms[index - 1] if index - 1 < len(pauses_ms) else DEFAULT_SILENCE_MS
                silence_frames = int(params.framerate * silence_ms / 1000)
                silence = b"\x00" * silence_frames * params.nchannels * params.sampwidth
                writer.writeframes(silence)
                frame_count += silence_frames
            writer.writeframes(chunk)

    return frame_count / params.framerate


def gpu_memory_mb(runtime: TtsRuntime | None) -> dict[str, float] | None:
    if runtime is None or not runtime.torch_module.cuda.is_available():
        return None
    torch = runtime.torch_module
    return {
        "allocated": round(torch.cuda.memory_allocated() / 1024 / 1024, 1),
        "reserved": round(torch.cuda.memory_reserved() / 1024 / 1024, 1),
        "max_allocated": round(torch.cuda.max_memory_allocated() / 1024 / 1024, 1),
        "max_reserved": round(torch.cuda.max_memory_reserved() / 1024 / 1024, 1),
    }


@app.on_event("startup")
async def startup() -> None:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    asyncio.create_task(idle_unload_loop())


async def idle_unload_loop() -> None:
    while True:
        await asyncio.sleep(30)
        await state.unload_if_idle()


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "loaded": state.loaded(),
        "runtime_imported": state.runtime is not None,
        "language": "zh",
        "lifecycle_owner_fingerprint": LIFECYCLE_OWNER_FINGERPRINT,
        "idle_unload_seconds": IDLE_UNLOAD_SECONDS,
        "gpu_memory_mb": gpu_memory_mb(state.runtime),
    }


@app.post("/tts")
async def tts(request: TtsRequest) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        segments = [segment.strip() for segment in request.segments if segment.strip()]
        if not segments:
            raise ValueError("segments is empty")
        prompt = voice_path(request.voice_id)
        preset = emotion_preset(request.emotion)
        pauses_ms = request.pauses_ms or [DEFAULT_SILENCE_MS for _ in range(max(len(segments) - 1, 0))]

        artifact_id = request.artifact_id.strip()
        if artifact_id and re.fullmatch(r"[0-9a-f]{32}", artifact_id) is None:
            raise ValueError("artifact_id is invalid")
        run_id = artifact_id or uuid.uuid4().hex
        tts_model = await state.ensure_loaded()
        segment_dir = TEMP_DIR / f"tts_{run_id}_segments"
        segment_dir.mkdir(parents=True, exist_ok=True)
        output_path = TEMP_DIR / f"tts_{run_id}.wav"

        generated: list[Path] = []
        results: list[dict[str, Any]] = []
        for index, text in enumerate(segments, start=1):
            segment_path = segment_dir / f"segment_{index:02d}.wav"
            infer_started = time.perf_counter()
            tts_model.infer(
                spk_audio_prompt=str(prompt),
                text=text,
                output_path=str(segment_path),
                emo_vector=[0, 0, 0, 0, 0, 0, 0, float(preset["emo_last"])],
                emo_alpha=float(preset["emo_alpha"]),
                use_random=False,
                max_mel_tokens=ENGINE_CONFIG.max_mel_tokens,
                num_beams=1,
                verbose=False,
            )
            tail_trimmed = False
            if request.trim_trailing_noise:
                tail_trimmed = trim_trailing_low_energy_noise(segment_path)
            generated.append(segment_path)
            results.append(
                {
                    "index": index,
                    "text": text,
                    "max_mel_tokens": ENGINE_CONFIG.max_mel_tokens,
                    "seconds": round(time.perf_counter() - infer_started, 3),
                    "bytes": segment_path.stat().st_size,
                    "tail_trimmed": tail_trimmed,
                }
            )

        duration = concat_wavs(generated, output_path, pauses_ms)
        if request.max_total_seconds > 0 and duration > request.max_total_seconds:
            raise ValueError(f"generated audio too long: {duration:.2f}s")

        state.last_used_at = time.monotonic()
        return {
            "ok": True,
            "audio_path": str(output_path),
            "language": "zh",
            "duration_seconds": round(duration, 3),
            "total_seconds": round(time.perf_counter() - started, 3),
            "segments": results,
            "pauses_ms": pauses_ms,
            "cache_hit": False,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "total_seconds": round(time.perf_counter() - started, 3),
        }


if __name__ == "__main__":
    print(
        json.dumps(
            {
                "service": "tts",
                "host": "127.0.0.1",
                "port": 7861,
                "languages": ["zh"],
                "idle_unload_seconds": IDLE_UNLOAD_SECONDS,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    uvicorn.run(app, host="127.0.0.1", port=7861)
