"""Time metadata for memory prompts. Never infer event dates from prose."""
from __future__ import annotations

from datetime import datetime, timezone
import math

from .local_time import CHINA_STANDARD_TIME


def parse_memory_time(value) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def event_message_time(event, *, now: datetime | None = None) -> str | None:
    value = getattr(event, "time", None)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        return None
    try:
        instant = datetime.fromtimestamp(value, timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None
    current = now or datetime.now(timezone.utc)
    if instant > current:
        return None
    return instant.isoformat(timespec="seconds")


def time_label(value, *, now: datetime | None = None) -> str:
    instant = parse_memory_time(value)
    if instant is None:
        return "未知"
    current = now or datetime.now(timezone.utc)
    elapsed = int((current - instant).total_seconds())
    absolute = instant.astimezone(CHINA_STANDARD_TIME).strftime("%Y-%m-%d %H:%M:%S")
    if elapsed < 0:
        relative = "晚于当前时间，需核对时钟"
    elif elapsed < 60:
        relative = f"{elapsed}秒前"
    elif elapsed < 3600:
        relative = f"{elapsed // 60}分{elapsed % 60}秒前"
    elif elapsed < 86400:
        relative = f"{elapsed // 3600}小时{elapsed % 3600 // 60}分前"
    else:
        relative = f"{elapsed // 86400}天{elapsed % 86400 // 3600}小时前"
    return f"{absolute} 北京时间（{relative}）"


def message_time_context(row, *, now: datetime | None = None) -> str:
    keys = row.keys()
    occurred = row["occurred_at"] if "occurred_at" in keys else None
    kind = row["time_kind"] if "time_kind" in keys else ""
    label = {"platform_sent": "消息发送时间", "reply_sent": "回复首段发送确认时间"}.get(kind, "记录时间（非发送确认）")
    value = occurred or (row["created_at"] if "created_at" in keys else None)
    return f"[{label}：{time_label(value, now=now)}]"


def source_time_range(rows) -> tuple[str | None, str | None]:
    """Only preserve known endpoints; never guess after source deletion."""
    def instant(row):
        keys = row.keys()
        value = row["occurred_at"] if "occurred_at" in keys and row["occurred_at"] else row["created_at"] if "created_at" in keys else None
        parsed = parse_memory_time(value)
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds") if parsed else None
    if not rows:
        return None, None
    return instant(rows[0]), instant(rows[-1])


def summary_time_context(summary, *, now: datetime | None = None, live: bool = False) -> str:
    generated = getattr(summary, "updated_at", None) if live else getattr(summary, "created_at", None)
    start = getattr(summary, "source_start_at", None)
    end = getattr(summary, "source_end_at", None)
    period = f"{time_label(start, now=now)} 至 {time_label(end, now=now)}" if start or end else "未知（旧原文时间未保留）"
    label = "状态卡更新时间" if live else "摘要生成时间"
    created = f"状态卡生成时间：{time_label(getattr(summary, 'created_at', None), now=now)}；" if live else ""
    return f"[{created}{label}：{time_label(generated, now=now)}；原消息时间范围：{period}；消息时间缺失时仅为记录时间，摘要生成时间不是事件发生时间]"
