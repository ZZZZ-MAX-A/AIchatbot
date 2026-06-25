import asyncio
import gc
import json
import sys
import time
import uuid
import wave
from pathlib import Path
from typing import Any

import torch
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INDEXTTS_ROOT = PROJECT_ROOT / "tts-validation" / "index-tts-main"
MODEL_DIR = INDEXTTS_ROOT / "checkpoints"
CONFIG_PATH = MODEL_DIR / "config.yaml"
TEMP_DIR = PROJECT_ROOT / "temp_audio"
VOICE_DIR = PROJECT_ROOT / "voice-samples" / "reference" / "zh"

if str(INDEXTTS_ROOT) not in sys.path:
    sys.path.insert(0, str(INDEXTTS_ROOT))

from indextts.infer_v2 import IndexTTS2  # noqa: E402


EMOTION_PRESETS = {
    "calm": {"emo_last": 0.25, "emo_alpha": 0.5},
    "affection": {"emo_last": 0.35, "emo_alpha": 0.55},
    "soft": {"emo_last": 0.45, "emo_alpha": 0.6},
    "warm": {"emo_last": 0.60, "emo_alpha": 0.65},
}

IDLE_UNLOAD_SECONDS = 600
DEFAULT_MAX_MEL_TOKENS = 700
DEFAULT_SILENCE_MS = 550


class TtsRequest(BaseModel):
    segments: list[str]
    pauses_ms: list[int] | None = None
    voice_id: str = "zh_kelin_raw_20260625_222137"
    emotion: str = "affection"
    max_total_seconds: int = 60


class ModelState:
    def __init__(self) -> None:
        self.tts: IndexTTS2 | None = None
        self.last_used_at = 0.0
        self.lock = asyncio.Lock()

    def loaded(self) -> bool:
        return self.tts is not None

    async def ensure_loaded(self) -> IndexTTS2:
        async with self.lock:
            if self.tts is None:
                started = time.perf_counter()
                self.tts = IndexTTS2(
                    cfg_path=str(CONFIG_PATH),
                    model_dir=str(MODEL_DIR),
                    use_fp16=True,
                    use_cuda_kernel=False,
                    use_deepspeed=False,
                )
                print(f"model_loaded seconds={time.perf_counter() - started:.3f}", flush=True)
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
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("model_unloaded idle=true", flush=True)


state = ModelState()
app = FastAPI(title="AI Chatbot Local TTS Service")


def voice_path(voice_id: str) -> Path:
    safe_id = "".join(char for char in voice_id if char.isalnum() or char in {"_", "-"})
    path = VOICE_DIR / f"{safe_id}.wav"
    if not path.exists():
        raise FileNotFoundError(f"voice not found: {safe_id}")
    return path


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


def gpu_memory_mb() -> dict[str, float] | None:
    if not torch.cuda.is_available():
        return None
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
        "idle_unload_seconds": IDLE_UNLOAD_SECONDS,
        "gpu_memory_mb": gpu_memory_mb(),
    }


@app.post("/tts")
async def tts(request: TtsRequest) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        segments = [segment.strip() for segment in request.segments if segment.strip()]
        if not segments:
            raise ValueError("segments is empty")
        prompt = voice_path(request.voice_id)
        preset = EMOTION_PRESETS.get(request.emotion, EMOTION_PRESETS["affection"])
        pauses_ms = request.pauses_ms or [DEFAULT_SILENCE_MS for _ in range(max(len(segments) - 1, 0))]

        tts_model = await state.ensure_loaded()
        run_id = uuid.uuid4().hex
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
                max_mel_tokens=DEFAULT_MAX_MEL_TOKENS,
                num_beams=1,
                verbose=False,
            )
            generated.append(segment_path)
            results.append(
                {
                    "index": index,
                    "seconds": round(time.perf_counter() - infer_started, 3),
                    "bytes": segment_path.stat().st_size,
                }
            )

        duration = concat_wavs(generated, output_path, pauses_ms)
        if request.max_total_seconds > 0 and duration > request.max_total_seconds:
            raise ValueError(f"generated audio too long: {duration:.2f}s")

        state.last_used_at = time.monotonic()
        return {
            "ok": True,
            "audio_path": str(output_path),
            "duration_seconds": round(duration, 3),
            "total_seconds": round(time.perf_counter() - started, 3),
            "segments": results,
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
                "idle_unload_seconds": IDLE_UNLOAD_SECONDS,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    uvicorn.run(app, host="127.0.0.1", port=7861)
