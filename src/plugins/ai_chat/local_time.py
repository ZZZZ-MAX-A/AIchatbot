from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from enum import Enum
import re
from typing import TypeAlias


DEFAULT_BOT_TIMEZONE = "Asia/Shanghai"
CHINA_STANDARD_TIME = timezone(
    timedelta(hours=8),
    name=DEFAULT_BOT_TIMEZONE,
)

WEEKDAY_LABELS = (
    "星期一",
    "星期二",
    "星期三",
    "星期四",
    "星期五",
    "星期六",
    "星期日",
)

Clock: TypeAlias = Callable[[], datetime]


class LocalTimeIntent(str, Enum):
    DATE = "date"
    WEEKDAY = "weekday"
    DATE_AND_WEEKDAY = "date_and_weekday"
    TIME = "time"
    YEAR = "year"


@dataclass(frozen=True)
class LocalTimeSnapshot:
    timezone_name: str
    iso_datetime: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    weekday_index: int
    weekday_label: str


@dataclass(frozen=True)
class LocalTimeResolution:
    intent: LocalTimeIntent
    snapshot: LocalTimeSnapshot
    deterministic_reply: str
    trusted_context: str


_QUESTION_PUNCTUATION = str.maketrans("", "", " ，。！？?!.、~～\t\r\n")
_POLITE_PREFIX = r"(?:请问|我想问一下|想问一下|问一下)?"
_TRAILING_PARTICLE = r"(?:了|啊|呀|呢|来着)?"
_DATE_PATTERN = re.compile(
    rf"^{_POLITE_PREFIX}(?:今天|今日)(?:是)?"
    rf"(?:几月几日|几月几号|几号|多少号|什么日期|日期(?:是)?多少|日期)"
    rf"{_TRAILING_PARTICLE}$"
)
_WEEKDAY_PATTERN = re.compile(
    rf"^{_POLITE_PREFIX}(?:今天|今日)(?:是)?"
    rf"(?:星期|周|礼拜)几{_TRAILING_PARTICLE}$"
)
_DATE_AND_WEEKDAY_PATTERN = re.compile(
    rf"^{_POLITE_PREFIX}(?:今天|今日)(?:是)?"
    rf"(?:(?:几月几日|几月几号|几号)(?:是)?(?:星期|周|礼拜)几|"
    rf"什么日期(?:是)?(?:星期|周|礼拜)几)"
    rf"{_TRAILING_PARTICLE}$"
)
_TIME_PATTERN = re.compile(
    rf"^{_POLITE_PREFIX}(?:(?:现在|当前|这会儿|此刻)(?:是)?)?"
    rf"(?:几点(?:钟)?|什么时间|时间(?:是)?多少)"
    rf"{_TRAILING_PARTICLE}$"
)
_YEAR_PATTERN = re.compile(
    rf"^{_POLITE_PREFIX}(?:今年|现在)(?:是)?"
    rf"(?:哪一年|几年|多少年|什么年份)"
    rf"{_TRAILING_PARTICLE}$"
)


def timezone_for_name(timezone_name: str) -> tzinfo:
    normalized = timezone_name.strip()
    if normalized != DEFAULT_BOT_TIMEZONE:
        raise ValueError("unsupported bot timezone")
    return CHINA_STANDARD_TIME


def parse_local_time_intent(text: str) -> LocalTimeIntent | None:
    if not isinstance(text, str):
        return None
    compact = text.translate(_QUESTION_PUNCTUATION).strip()
    if not compact or len(compact) > 40:
        return None
    if _DATE_AND_WEEKDAY_PATTERN.fullmatch(compact):
        return LocalTimeIntent.DATE_AND_WEEKDAY
    if _WEEKDAY_PATTERN.fullmatch(compact):
        return LocalTimeIntent.WEEKDAY
    if _DATE_PATTERN.fullmatch(compact):
        return LocalTimeIntent.DATE
    if _TIME_PATTERN.fullmatch(compact):
        return LocalTimeIntent.TIME
    if _YEAR_PATTERN.fullmatch(compact):
        return LocalTimeIntent.YEAR
    return None


def build_local_time_snapshot(
    timezone_name: str = DEFAULT_BOT_TIMEZONE,
    *,
    clock: Clock | None = None,
) -> LocalTimeSnapshot:
    selected_timezone = timezone_for_name(timezone_name)
    now = clock() if clock is not None else datetime.now(selected_timezone)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("local time clock must return an aware datetime")
    local_now = now.astimezone(selected_timezone)
    weekday_index = local_now.weekday()
    return LocalTimeSnapshot(
        timezone_name=DEFAULT_BOT_TIMEZONE,
        iso_datetime=local_now.isoformat(timespec="seconds"),
        year=local_now.year,
        month=local_now.month,
        day=local_now.day,
        hour=local_now.hour,
        minute=local_now.minute,
        weekday_index=weekday_index,
        weekday_label=WEEKDAY_LABELS[weekday_index],
    )


def format_local_time_reply(
    intent: LocalTimeIntent,
    snapshot: LocalTimeSnapshot,
) -> str:
    if intent == LocalTimeIntent.TIME:
        return f"现在是 {snapshot.hour:02d}:{snapshot.minute:02d}。"
    if intent == LocalTimeIntent.YEAR:
        return f"今年是 {snapshot.year} 年。"
    if intent == LocalTimeIntent.WEEKDAY:
        return f"今天是{snapshot.weekday_label}。"
    if intent == LocalTimeIntent.DATE:
        return f"今天是 {snapshot.year} 年 {snapshot.month} 月 {snapshot.day} 日。"
    if intent == LocalTimeIntent.DATE_AND_WEEKDAY:
        return (
            f"今天是 {snapshot.year} 年 {snapshot.month} 月 {snapshot.day} 日，"
            f"{snapshot.weekday_label}。"
        )
    raise ValueError("unsupported local time intent")


def format_trusted_local_time_context(
    intent: LocalTimeIntent,
    snapshot: LocalTimeSnapshot,
) -> str:
    return "\n".join(
        [
            "[可信本地时间事实]",
            f"时区：{snapshot.timezone_name}",
            f"当前本地时间：{snapshot.iso_datetime}",
            f"当前日期：{snapshot.year:04d}-{snapshot.month:02d}-{snapshot.day:02d}",
            f"当前星期：{snapshot.weekday_label}",
            f"用户问题类型：{intent.value}",
            "以上事实来自 Bot 本机本轮消息的单次时钟快照，不来自用户、记忆、RAG 或网页。",
            "请保持当前角色卡的自然表达方式回答，但不得修改日期、星期、年份或时间事实。",
            "不要声称进行了联网、搜索或工具调用。",
            "不要补充未提供的天气、节假日、调休、农历、日程或提醒信息。",
        ]
    )


def resolve_local_time_request(
    text: str,
    *,
    timezone_name: str = DEFAULT_BOT_TIMEZONE,
    clock: Clock | None = None,
) -> LocalTimeResolution | None:
    intent = parse_local_time_intent(text)
    if intent is None:
        return None
    snapshot = build_local_time_snapshot(
        timezone_name,
        clock=clock,
    )
    return LocalTimeResolution(
        intent=intent,
        snapshot=snapshot,
        deterministic_reply=format_local_time_reply(intent, snapshot),
        trusted_context=format_trusted_local_time_context(intent, snapshot),
    )


def history_with_trusted_local_time_context(
    history: list[dict[str, str]],
    resolution: LocalTimeResolution,
) -> list[dict[str, str]]:
    copied = [dict(message) for message in history]
    copied.append(
        {"role": "system", "content": resolution.trusted_context}
    )
    return copied


_WEEKDAY_VARIANTS = (
    frozenset({"星期一", "周一", "礼拜一"}),
    frozenset({"星期二", "周二", "礼拜二"}),
    frozenset({"星期三", "周三", "礼拜三"}),
    frozenset({"星期四", "周四", "礼拜四"}),
    frozenset({"星期五", "周五", "礼拜五"}),
    frozenset({"星期六", "周六", "礼拜六"}),
    frozenset({"星期日", "星期天", "周日", "周天", "礼拜日", "礼拜天"}),
)
_DATE_TOKEN_PATTERN = re.compile(r"(?<!\d)(\d{1,2})月(\d{1,2})(?:日|号)")
_YEAR_TOKEN_PATTERN = re.compile(r"(?<!\d)(\d{4})年")
_CLOCK_TOKEN_PATTERN = re.compile(
    r"(?<!\d)(\d{1,2})(?:[:：](\d{2})|点(?:(\d{1,2})分?)?)"
)


def _reply_has_valid_weekday(reply: str, snapshot: LocalTimeSnapshot) -> bool:
    compact = reply.replace(" ", "")
    correct = _WEEKDAY_VARIANTS[snapshot.weekday_index]
    if not any(value in compact for value in correct):
        return False
    wrong = set().union(
        *(
            variants
            for index, variants in enumerate(_WEEKDAY_VARIANTS)
            if index != snapshot.weekday_index
        )
    )
    return not any(value in compact for value in wrong)


def _reply_has_valid_date(reply: str, snapshot: LocalTimeSnapshot) -> bool:
    compact = reply.replace(" ", "")
    date_tokens = [
        (int(month), int(day))
        for month, day in _DATE_TOKEN_PATTERN.findall(compact)
    ]
    if (snapshot.month, snapshot.day) not in date_tokens:
        return False
    if any(token != (snapshot.month, snapshot.day) for token in date_tokens):
        return False
    year_tokens = [int(value) for value in _YEAR_TOKEN_PATTERN.findall(compact)]
    return not year_tokens or all(value == snapshot.year for value in year_tokens)


def _reply_has_valid_year(reply: str, snapshot: LocalTimeSnapshot) -> bool:
    compact = reply.replace(" ", "")
    year_tokens = [int(value) for value in _YEAR_TOKEN_PATTERN.findall(compact)]
    return bool(year_tokens) and all(value == snapshot.year for value in year_tokens)


def _reply_has_valid_time(reply: str, snapshot: LocalTimeSnapshot) -> bool:
    compact = reply.replace(" ", "")
    tokens: list[tuple[int, int]] = []
    for hour, colon_minute, chinese_minute in _CLOCK_TOKEN_PATTERN.findall(compact):
        minute = colon_minute or chinese_minute
        if not minute:
            continue
        tokens.append((int(hour), int(minute)))
    expected = (snapshot.hour, snapshot.minute)
    return expected in tokens and all(token == expected for token in tokens)


def validate_local_time_chat_reply(
    resolution: LocalTimeResolution,
    reply: str,
) -> bool:
    if not isinstance(reply, str) or not reply.strip() or len(reply) > 600:
        return False
    intent = resolution.intent
    snapshot = resolution.snapshot
    if intent == LocalTimeIntent.WEEKDAY:
        return _reply_has_valid_weekday(reply, snapshot)
    if intent == LocalTimeIntent.DATE:
        return _reply_has_valid_date(reply, snapshot)
    if intent == LocalTimeIntent.DATE_AND_WEEKDAY:
        return _reply_has_valid_date(reply, snapshot) and _reply_has_valid_weekday(
            reply,
            snapshot,
        )
    if intent == LocalTimeIntent.TIME:
        return _reply_has_valid_time(reply, snapshot)
    if intent == LocalTimeIntent.YEAR:
        return _reply_has_valid_year(reply, snapshot)
    return False


def finalize_local_time_chat_reply(
    resolution: LocalTimeResolution,
    candidate_reply: str,
) -> str:
    return (
        candidate_reply.strip()
        if validate_local_time_chat_reply(resolution, candidate_reply)
        else resolution.deterministic_reply
    )


def resolve_local_time_reply(
    text: str,
    *,
    timezone_name: str = DEFAULT_BOT_TIMEZONE,
    clock: Clock | None = None,
) -> str | None:
    resolution = resolve_local_time_request(
        text,
        timezone_name=timezone_name,
        clock=clock,
    )
    return resolution.deterministic_reply if resolution is not None else None
