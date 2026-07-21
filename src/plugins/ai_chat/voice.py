import asyncio
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from .config import AiChatConfig
from .media_reliability import observe_tts_synthesis_safely


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INDEXTTS_ROOT = PROJECT_ROOT / "tts-validation" / "index-tts-main"
INDEXTTS_PYTHON = INDEXTTS_ROOT / ".venv" / "Scripts" / "python.exe"
TTS_SERVICE_SCRIPT = PROJECT_ROOT / "src" / "plugins" / "ai_chat" / "tts_service.py"
TTS_SERVICE_STDOUT = PROJECT_ROOT / "logs" / "tts-service.out.log"
TTS_SERVICE_STDERR = PROJECT_ROOT / "logs" / "tts-service.err.log"


class VoiceIntentType(str, Enum):
    DIRECT_TEXT = "direct_text"
    LAST_REPLY = "last_reply"
    SEMANTIC_REPLY = "semantic_reply"


@dataclass(frozen=True)
class VoiceIntent:
    type: VoiceIntentType
    text: str = ""
    semantic_goal: str = ""
    refresh_cache: bool = False
    preserve_original: bool = False
    language: str = "zh"


@dataclass(frozen=True)
class TtsCandidate:
    raw_text: str
    speakable_text: str
    created_at: datetime
    message_id: str = ""


@dataclass(frozen=True)
class AdaptedSpeech:
    text: str
    segments: tuple[str, ...]
    pauses_ms: tuple[int, ...]
    language: str = "zh"


@dataclass(frozen=True)
class TtsResult:
    audio_path: Path
    language: str
    duration_seconds: float = 0.0
    cache_hit: bool = False
    segments: tuple[dict[str, Any], ...] = ()


_last_tts_candidate: TtsCandidate | None = None

ACTION_BRACKET_PATTERNS = (
    re.compile(r"（[^（）]*）"),
    re.compile(r"\([^()]*\)"),
    re.compile(r"【[^【】]*】"),
    re.compile(r"\[[^\[\]]*\]"),
    re.compile(r"\*[^*]+\*"),
)

DIRECT_TEXT_PATTERNS = (
    re.compile(
        r"^(?:用中文语音说|中文语音说|用中文说|用语音说|语音说|念这句|读这句|读这段|这段话用语音|这句话用语音)[:：]?\s*(?P<text>.+)$",
        re.S,
    ),
    re.compile(
        r"^(?:帮我用中文语音说|帮我用语音说|帮我念|帮我读|让爱可用语音说|请爱可用语音说|爱可用语音说)[:：]?\s*(?P<text>.+)$",
        re.S,
    ),
)

LAST_REPLY_MARKERS = (
    "刚刚那句",
    "刚才那句",
    "刚刚那句话",
    "刚才那句话",
    "上一句",
    "上一条",
    "上条",
)

LAST_REPLY_ACTIONS = (
    "语音",
    "声音",
    "念给我听",
    "念一下",
    "读给我听",
    "读一下",
    "转语音",
)

VOICE_WORDS = ("语音", "声音", "念给我听", "说给我听", "读给我听")
SEMANTIC_ACTION_WORDS = (
    "说晚安",
    "晚安",
    "哄我睡",
    "哄睡",
    "安慰",
    "撒娇",
    "想我",
    "夸夸我",
    "夸我",
    "陪我",
)

VOICE_DISCUSSION_MARKERS = (
    "语音功能",
    "能不能发语音",
    "可以发语音",
    "支持语音",
    "声音是什么样",
    "音色",
    "tts",
)

TTS_REFRESH_MARKERS = (
    "重新生成",
    "重新抽",
    "重抽一版",
    "重抽",
)


def parse_voice_intent(text: str) -> VoiceIntent | None:
    normalized = text.strip()
    if not normalized:
        return None
    refresh_cache = any(marker in normalized for marker in TTS_REFRESH_MARKERS)

    for pattern in DIRECT_TEXT_PATTERNS:
        match = pattern.match(normalized)
        if match:
            direct_text = match.group("text").strip()
            if direct_text:
                return VoiceIntent(VoiceIntentType.DIRECT_TEXT, text=direct_text, refresh_cache=refresh_cache)

    if any(marker in normalized for marker in LAST_REPLY_MARKERS) and any(
        action in normalized for action in LAST_REPLY_ACTIONS
    ):
        return VoiceIntent(VoiceIntentType.LAST_REPLY, refresh_cache=refresh_cache)

    if any(marker in normalized.lower() for marker in VOICE_DISCUSSION_MARKERS):
        return None

    has_voice_request = any(word in normalized for word in VOICE_WORDS)
    has_semantic_action = any(word in normalized for word in SEMANTIC_ACTION_WORDS)
    imperative_voice = normalized.startswith(("请用语音", "用语音", "用声音", "我想听你用语音", "我想听你用声音"))
    if has_voice_request and (has_semantic_action or imperative_voice):
        return VoiceIntent(
            VoiceIntentType.SEMANTIC_REPLY,
            semantic_goal=extract_semantic_goal(normalized),
            refresh_cache=refresh_cache,
        )

    return None


def extract_semantic_goal(text: str) -> str:
    goal = text.strip()
    prefixes = (
        "请",
        "重新生成",
        "重新抽",
        "重抽一版",
        "重抽",
        "可以",
        "能不能",
        "我想听你",
        "我想让你",
        "帮我",
        "用语音",
        "用声音",
        "给我",
        "和我",
        "跟我",
    )
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if goal.startswith(prefix):
                goal = goal[len(prefix):].strip()
                changed = True
    goal = goal.replace("用语音", "").replace("用声音", "").replace("语音", "").strip()
    return goal or text.strip()


def set_last_tts_candidate(raw_text: str, message_id: str = "", *, force_language: str = "") -> TtsCandidate | None:
    adapted = adapt_speech_text(raw_text)
    if not adapted.text:
        return None
    candidate = TtsCandidate(
        raw_text=raw_text,
        speakable_text=adapted.text,
        created_at=datetime.now(),
        message_id=message_id,
    )
    global _last_tts_candidate
    _last_tts_candidate = candidate
    return candidate


def get_last_tts_candidate() -> TtsCandidate | None:
    return _last_tts_candidate


def adapt_speech_text(raw_text: str, *, light_stutter: bool = True, force_language: str = "") -> AdaptedSpeech:
    text = raw_text.strip()
    for pattern in ACTION_BRACKET_PATTERNS:
        text = pattern.sub("", text)
    text = apply_reading_replacements(text)
    text = normalize_punctuation(text)
    if light_stutter:
        text = normalize_stutter_light(text)
    text = normalize_whitespace(text)
    segments, pauses = split_speech_segments(text)
    return AdaptedSpeech(text="\n".join(segments), segments=tuple(segments), pauses_ms=tuple(pauses))


def apply_reading_replacements(text: str) -> str:
    replacements = {
        "狗修金": "主人",
        "爱可": "我",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def normalize_punctuation(text: str) -> str:
    text = text.replace("......", "……")
    text = re.sub(r"…{3,}", "……", text)
    text = re.sub(r"。{2,}", "。", text)
    text = re.sub(r"！{2,}", "！", text)
    text = re.sub(r"？{2,}", "？", text)
    text = re.sub(r"，{2,}", "，", text)
    return text


def normalize_stutter_light(text: str) -> str:
    protected: list[str] = []

    def protect(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f"__STUTTER_{len(protected) - 1}__"

    text = re.sub(r"主、主人", protect, text, count=1)
    text = re.sub(r"好、好不好", protect, text, count=1)
    text = re.sub(r"([\u4e00-\u9fff])、\1(?:、\1)+", r"\1、\1", text)
    text = re.sub(r"([\u4e00-\u9fff])、\1", r"\1", text)

    for index, value in enumerate(protected):
        text = text.replace(f"__STUTTER_{index}__", value)
    return text


def normalize_whitespace(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def split_speech_segments(text: str) -> tuple[list[str], list[int]]:
    candidates: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        candidates.extend(_split_line_by_sentence(line))

    segments: list[str] = []
    for candidate in candidates:
        segments.extend(_split_long_segment(candidate, max_chars=70))

    clean_segments = [segment.strip() for segment in segments if segment.strip()]
    pauses = [550 for _ in range(max(len(clean_segments) - 1, 0))]
    return clean_segments, pauses


def _split_line_by_sentence(line: str) -> list[str]:
    result: list[str] = []
    current: list[str] = []
    for char in line:
        current.append(char)
        if char in "。！？!?":
            segment = "".join(current).strip()
            if segment:
                result.append(segment)
            current = []
    rest = "".join(current).strip()
    if rest:
        result.append(rest)
    return result


def _split_long_segment(segment: str, max_chars: int) -> list[str]:
    if len(segment) <= max_chars:
        return [segment]
    parts = re.split(r"([，；;、])", segment)
    result: list[str] = []
    current = ""
    for index in range(0, len(parts), 2):
        part = parts[index]
        punct = parts[index + 1] if index + 1 < len(parts) else ""
        unit = part + punct
        if current and len(current) + len(unit) > max_chars:
            result.append(current.strip())
            current = unit
        else:
            current += unit
    if current.strip():
        result.append(current.strip())
    return result or [segment]


def semantic_voice_instruction() -> str:
    return (
        "本次主人明确请求语音回复，输出将直接转为语音发送。"
        "请按当前角色卡直接回复主人要听的内容。"
        "不要解释“我会用语音说”、不要描述生成语音的过程。"
        "回复可以保持角色原有的亲昵、害羞和自然表达。"
        "如果主人要求较长语音、复述或翻译，不要擅自压缩成短回复。"
    )


def semantic_voice_user_text(original_text: str, semantic_goal: str, *, preserve_original: bool = False) -> str:
    goal = semantic_goal.strip() or original_text.strip()
    return (
        "主人明确请求你用语音回复。\n"
        f"语义目标：{goal}\n"
        "请直接生成要对主人说出口的中文内容，不要说明你将使用语音。"
    )


async def request_tts(config: AiChatConfig, adapted: AdaptedSpeech, *, refresh_cache: bool = False) -> TtsResult:
    if not adapted.segments:
        raise RuntimeError("empty TTS segments")

    try:
        await ensure_tts_service(config)

        payload: dict[str, Any] = {
            "segments": list(adapted.segments),
            "pauses_ms": list(adapted.pauses_ms),
            "voice_id": config.tts_voice,
            "language": "zh",
            "emotion": config.tts_emotion,
            "max_total_seconds": config.tts_max_total_seconds,
            "bypass_cache": refresh_cache,
        }
        async with httpx.AsyncClient(timeout=config.tts_timeout_seconds) as client:
            response = await client.post(f"{config.tts_service_url.rstrip('/')}/tts", json=payload)
            response.raise_for_status()
            data = response.json()
        if not data.get("ok"):
            raise RuntimeError(str(data.get("error") or "TTS service failed"))
        audio_path = Path(str(data.get("audio_path") or ""))
        if not audio_path.is_file():
            raise RuntimeError(f"TTS output not found: {audio_path}")
        if audio_path.stat().st_size <= 0:
            raise RuntimeError("TTS output is empty")
        duration_seconds = float(data.get("duration_seconds") or 0.0)
        if duration_seconds <= 0:
            raise RuntimeError("TTS output duration invalid")
        if (
            config.tts_max_total_seconds > 0
            and duration_seconds > config.tts_max_total_seconds
        ):
            raise RuntimeError("TTS output exceeds duration limit")
        result = TtsResult(
            audio_path=audio_path,
            language=str(data.get("language") or "zh"),
            duration_seconds=duration_seconds,
            cache_hit=bool(data.get("cache_hit")),
            segments=tuple(data.get("segments") or ()),
        )
    except Exception as exc:
        observe_tts_synthesis_safely(succeeded=False, error=exc)
        raise
    observe_tts_synthesis_safely(succeeded=True)
    return result


async def ensure_tts_service(config: AiChatConfig) -> None:
    if await tts_service_is_healthy(config):
        return
    if not config.tts_auto_start:
        return
    if not is_local_tts_service(config.tts_service_url):
        return

    async with tts_start_lock():
        if await tts_service_is_healthy(config):
            return
        start_local_tts_service()
        wait_seconds = max(config.tts_startup_wait_seconds, 1)
        deadline = asyncio.get_running_loop().time() + wait_seconds
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(1)
            if await tts_service_is_healthy(config):
                return
        raise RuntimeError(f"TTS service did not start within {wait_seconds} seconds")


async def tts_service_is_healthy(config: AiChatConfig) -> bool:
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(f"{config.tts_service_url.rstrip('/')}/health")
        if response.status_code != 200:
            return False
        data = response.json()
    except Exception:
        return False
    return bool(data.get("ok"))


def is_local_tts_service(url: str) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    return hostname in {"127.0.0.1", "localhost", "::1"}


def tts_start_lock() -> asyncio.Lock:
    lock = getattr(tts_start_lock, "_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        setattr(tts_start_lock, "_lock", lock)
    return lock


def start_local_tts_service() -> None:
    if not INDEXTTS_PYTHON.exists():
        raise FileNotFoundError(f"IndexTTS2 python was not found: {INDEXTTS_PYTHON}")
    if not TTS_SERVICE_SCRIPT.exists():
        raise FileNotFoundError(f"TTS service script was not found: {TTS_SERVICE_SCRIPT}")

    if sys.platform.startswith("win"):
        subprocess.Popen(
            [str(INDEXTTS_PYTHON), str(TTS_SERVICE_SCRIPT)],
            cwd=str(INDEXTTS_ROOT),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
            close_fds=False,
        )
        return

    TTS_SERVICE_STDOUT.parent.mkdir(parents=True, exist_ok=True)
    stdout = TTS_SERVICE_STDOUT.open("a", encoding="utf-8")
    stderr = TTS_SERVICE_STDERR.open("a", encoding="utf-8")
    try:
        subprocess.Popen(
            [str(INDEXTTS_PYTHON), str(TTS_SERVICE_SCRIPT)],
            cwd=str(INDEXTTS_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            close_fds=False,
        )
    finally:
        stdout.close()
        stderr.close()
