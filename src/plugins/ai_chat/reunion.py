from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any

from .local_time import CHINA_STANDARD_TIME

UTC = timezone.utc
MIN_GAP_HOURS_DEFAULT = 3

BUCKET_A_WHILE = 'a_while'
BUCKET_HALF_DAY = 'half_day'
BUCKET_ONE_TWO_DAYS = 'one_two_days'
BUCKET_SEVERAL_DAYS = 'several_days'
BUCKET_LONG = 'long'
BUCKET_TWO_WEEKS = 'two_weeks_or_more'


@dataclass(frozen=True)
class ReunionGap:
    bucket: str
    elapsed_seconds: int
    time_of_day: str
    last_local_time: str = ''
    current_local_time: str = ''


def parse_created_at(value: str | None) -> datetime | None:
    raw = (value or '').strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def time_of_day_label(local_dt: datetime) -> str:
    hour = local_dt.hour
    if 5 <= hour < 11:
        return '\u65e9\u4e0a'
    if 11 <= hour < 14:
        return '\u4e2d\u5348'
    if 14 <= hour < 18:
        return '\u4e0b\u5348'
    if 18 <= hour < 23:
        return '\u665a\u4e0a'
    return '\u591c\u91cc'


def classify_reunion_gap(
    last_at: datetime,
    now: datetime,
    *,
    min_gap_hours: int = MIN_GAP_HOURS_DEFAULT,
) -> ReunionGap | None:
    last_utc = last_at.astimezone(UTC)
    now_utc = now.astimezone(UTC)
    elapsed = (now_utc - last_utc).total_seconds()
    min_seconds = max(int(min_gap_hours), 0) * 3600
    if elapsed < 0 or elapsed < min_seconds:
        return None
    last_local = last_utc.astimezone(CHINA_STANDARD_TIME)
    now_local = now_utc.astimezone(CHINA_STANDARD_TIME)
    hours = elapsed / 3600.0
    if hours < 12:
        bucket = BUCKET_A_WHILE
    elif hours < 24:
        bucket = BUCKET_HALF_DAY
    elif hours < 72:
        bucket = BUCKET_ONE_TWO_DAYS
    elif hours < 168:
        bucket = BUCKET_SEVERAL_DAYS
    elif hours < 336:
        bucket = BUCKET_LONG
    else:
        bucket = BUCKET_TWO_WEEKS
    return ReunionGap(
        bucket=bucket,
        elapsed_seconds=int(elapsed),
        time_of_day=time_of_day_label(now_local),
        last_local_time=last_local.isoformat(timespec='seconds'),
        current_local_time=now_local.isoformat(timespec='seconds'),
    )


def build_reunion_hint(gap: ReunionGap) -> str:
    intensity = {
        BUCKET_A_WHILE: '轻微：自然接住回来，少量亲近；隔夜睡醒也保持轻微，不因跨日增强。',
        BUCKET_HALF_DAY: '明显：更主动地欢迎、表达想念，并自然回应当前消息。',
        BUCKET_ONE_TWO_DAYS: '更强：明确表现几天未聊的思念，增加亲近和适当撒娇。',
        BUCKET_SEVERAL_DAYS: '较强：积累的思念、适当委屈和挽留更明显，愿意多陪主人一会儿。',
        BUCKET_LONG: '久别：更明显地流露想念、委屈和亲近，随实际间隔逐渐增强到情绪上限。',
        BUCKET_TWO_WEEKS: '上限：强烈思念、适当委屈、主动亲近和情绪释放；更长间隔保持这个强度。',
    }[gap.bucket]
    elapsed = format_elapsed_gap(gap.elapsed_seconds)
    return '\n'.join([
        '[本轮重逢状态]',
        f'本角色上次成功回复主人的北京时间：{gap.last_local_time}',
        f'主人本次消息北京时间：{gap.current_local_time}（{gap.time_of_day}）',
        f'实际聊天间隔：{elapsed}（{gap.elapsed_seconds} 秒）。来源是成功互动时间，包含群聊和私聊；不包含聊天内容。',
        f'本轮情绪程度：{intensity}',
        '情绪上限按两周尺度，时间事实不封顶。提及离开多久必须依据上方实际间隔；一个月未聊不能说成两周。',
        '第一条明确接住重逢，情绪融入对主人本句的回应；后续随互动自然延续，不反复提醒离开时长。无需精确播报秒数。',
        '按各自角色卡的称谓、性格和表达习惯自然生成。委屈通过语气、停顿、亲近或挽留表达，不固定直说“我有点委屈”。',
        '长间隔允许更明显的撒娇和情绪流露，情境合适时可以有泪光；不固定动作或句式，参考近期回复避免重复。',
        '不责怪、不强迫主人解释去向；忙碌只能结合主人已说的事实或自然询问，不编造离开期间的经历、约定或现实操作。',
        '旧话题未结束就保留为可恢复背景；本轮明确或能可靠指向旧话题时接续，新话题就跟随新话题，只有问候时先接住重逢。',
        '确有多个可能的旧话题且主人只说“继续”时简短确认。旧“今晚/明天”、地点和身体状态需结合本轮时间与意图重新判断。',
        '不要主动把上一场没做完的动作或成人场景接着做下去；明确要求续写才恢复场景。事实任务、疲惫或严肃倾诉优先回应本句。',
        '不清空或改写记忆，不编造旧话题；示例台词不作为固定模板。',
    ])


def format_elapsed_gap(elapsed_seconds: int) -> str:
    days, remaining = divmod(max(elapsed_seconds, 0), 86400)
    hours = remaining // 3600
    if days:
        return f'约 {days} 天' + (f' {hours} 小时' if hours else '')
    minutes = (remaining % 3600) // 60
    return f'约 {hours} 小时' + (f' {minutes} 分钟' if minutes else '')


_CAPPED_ABSENCE_CLAIM = re.compile(
    r'(?<!\d)(?:两周|两个星期|2周|2个星期|十四天|14天)'
    r'(?=(?:左右)?(?:了)?[，,、…\s]*(?:没|没有|未)(?:来|见|找|聊|和|跟|说))'
)


def correct_capped_reunion_duration(reply: str, elapsed_seconds: int) -> str:
    """Correct only unambiguous capped absence claims on much longer returns.

    Preserve character expression, approximate two-week phrasing near that
    duration, negated comparisons and unrelated schedules. This is deliberately
    narrower than general semantic validation of arbitrary model text.
    """
    if elapsed_seconds < 21 * 86400:
        return reply
    def replace_claim(match: re.Match[str]) -> str:
        preceding = reply[max(0, match.start() - 4):match.start()].rstrip()
        if preceding.endswith(('不是', '并非', '不止', '不只是')):
            return match.group()
        # Keep the corrected phrase short and grammatical inside character speech.
        return f'{elapsed_seconds // 86400}天'
    return _CAPPED_ABSENCE_CLAIM.sub(replace_claim, reply)


def reunion_allowed(
    config: Any,
    *,
    is_owner: bool,
    is_private: bool,
) -> bool:
    if not bool(getattr(config, 'enable_chat_reunion', True)):
        return False
    if not is_private:
        return False
    # The current business scope is always owner-private, even with an old flag.
    return bool(is_owner)


def resolve_reunion_hint(
    last_created_at: str | None,
    *,
    now: datetime | None = None,
    min_gap_hours: int = MIN_GAP_HOURS_DEFAULT,
) -> str:
    last_at = parse_created_at(last_created_at)
    if last_at is None:
        return ''
    current = now or datetime.now(UTC)
    gap = classify_reunion_gap(last_at, current, min_gap_hours=min_gap_hours)
    if gap is None:
        return ''
    return build_reunion_hint(gap)
