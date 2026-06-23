import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AiChatConfig


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROLE_CARD_DIR = PROJECT_ROOT / "prompts" / "persona-cards"


@dataclass(frozen=True)
class ReplyDecision:
    should_reply: bool
    score: int
    reason: str


@dataclass(frozen=True)
class AutoReplyProfile:
    role_key: str
    bot_aliases: tuple[str, ...]
    call_markers: tuple[str, ...]
    question_markers: tuple[str, ...]
    help_markers: tuple[str, ...]
    owner_target_markers: tuple[str, ...]
    insult_markers: tuple[str, ...]
    self_negative_markers: tuple[str, ...]


SELF_NEGATIVE_PATTERN = re.compile(
    r"(我|自己|本人|本主人)"
    r".{0,6}"
    r"(废物|真废|好废|太废|没用|不行|太菜|好菜|真菜|很菜|太差|好差|真差|很差|做不好|傻|笨|蠢)"
)


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in markers)


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


def _load_profile_data(role_key: str) -> dict[str, Any]:
    if not role_key:
        return {}
    path = ROLE_CARD_DIR / f"{role_key}.auto-reply.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_auto_reply_profile(role_key: str) -> AutoReplyProfile:
    data = _load_profile_data(role_key)
    return AutoReplyProfile(
        role_key=role_key,
        bot_aliases=_string_tuple(data.get("bot_aliases")),
        call_markers=_string_tuple(data.get("call_markers")),
        question_markers=_string_tuple(data.get("question_markers")),
        help_markers=_string_tuple(data.get("help_markers")),
        owner_target_markers=_string_tuple(data.get("owner_target_markers")),
        insult_markers=_string_tuple(data.get("insult_markers")),
        self_negative_markers=_string_tuple(data.get("self_negative_markers")),
    )


def _is_self_negative(text: str, profile: AutoReplyProfile) -> bool:
    return _contains_any(text, profile.self_negative_markers) or bool(
        SELF_NEGATIVE_PATTERN.search(text)
    )


def _bot_names(config: AiChatConfig, profile: AutoReplyProfile) -> tuple[str, ...]:
    names = list(profile.bot_aliases)
    names.extend(config.bot_aliases)
    if config.bot_name:
        names.append(config.bot_name)
    return tuple(dict.fromkeys(name for name in names if name))


def decide_group_auto_reply(
    config: AiChatConfig,
    text: str,
    is_owner_sender: bool,
    role_key: str = "",
) -> ReplyDecision:
    normalized = text.strip()
    if not normalized:
        return ReplyDecision(False, 0, "empty")

    if len(normalized) <= 1:
        return ReplyDecision(False, 0, "too_short")

    profile = load_auto_reply_profile(role_key)
    score = 0
    reasons: list[str] = []

    mentions_bot = _contains_any(normalized, _bot_names(config, profile))
    if mentions_bot:
        score += 80
        reasons.append("bot_alias")

    if mentions_bot and _contains_any(normalized, profile.call_markers):
        score += 25
        reasons.append("bot_call")

    has_question = _contains_any(normalized, profile.question_markers)
    if has_question:
        score += 25
        reasons.append("question")

    if _contains_any(normalized, profile.help_markers):
        score += 25
        reasons.append("help")

    owner_targeted = _contains_any(normalized, profile.owner_target_markers)
    has_insult = _contains_any(normalized, profile.insult_markers)
    if owner_targeted and has_insult:
        score += 90
        reasons.append("owner_insult")

    if is_owner_sender:
        score += 45
        reasons.append("owner_sender")
        if has_question:
            score += 25
            reasons.append("owner_question")
        if _is_self_negative(normalized, profile):
            score += 70
            reasons.append("owner_self_negative")

    if len(normalized) <= 3 and not reasons:
        score -= 20
        reasons.append("short_plain")

    should_reply = score >= config.group_auto_reply_threshold
    return ReplyDecision(should_reply, score, "+".join(reasons) if reasons else "none")
