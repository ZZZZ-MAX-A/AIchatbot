from __future__ import annotations

import asyncio
import random
import re
from threading import RLock
from typing import Any

FULLWIDTH_LEFT = chr(0xFF08)
FULLWIDTH_RIGHT = chr(0xFF09)

DEFAULT_MAX_BUBBLES = 3
HARD_MAX_DELAY_MS = 1800
HARD_MAX_TOTAL_DELAY_MS = 3500
SHORT_BUBBLE_CHARS = 40
LONG_PREV_CHARS = 120
SHORT_DIALOGUE_CHARS = 24
SHORT_DELAY_MIN_MS = 500
SHORT_DELAY_MAX_MS = 800
LONG_DELAY_MIN_MS = 1000
LONG_DELAY_MAX_MS = 1500
POLL_SECONDS = 0.05

_BLANK_PARA_RE = re.compile(r'\n\s*\n+')
_generation_lock = RLock()
_generations: dict[str, int] = {}


def _session_key(session_key: str) -> str:
    return (session_key or '').strip() or 'legacy'


def bump_chat_bubble_generation(session_key: str) -> int:
    key = _session_key(session_key)
    with _generation_lock:
        current = _generations.get(key, 0) + 1
        _generations[key] = current
        return current


def current_chat_bubble_generation(session_key: str) -> int:
    key = _session_key(session_key)
    with _generation_lock:
        return _generations.get(key, 0)


def clear_chat_bubble_generations_for_tests() -> None:
    with _generation_lock:
        _generations.clear()


def action_brackets_balanced(text: str) -> bool:
    pairs = ((FULLWIDTH_LEFT, FULLWIDTH_RIGHT), ('(', ')'))
    for left, right in pairs:
        depth = 0
        for char in text:
            if char == left:
                depth += 1
            elif char == right:
                depth -= 1
                if depth < 0:
                    return False
        if not depth == 0:
            return False
    return True


def split_blank_line_paragraphs(text: str) -> list[str]:
    normalized = (text or '').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not normalized:
        return []
    return [part.strip() for part in _BLANK_PARA_RE.split(normalized) if part.strip()]


def is_pure_action_paragraph(text: str) -> bool:
    value = (text or '').strip()
    if not value:
        return False
    starts_action = value[0] in {'(', FULLWIDTH_LEFT}
    ends_action = value[-1] in {')', FULLWIDTH_RIGHT}
    return starts_action and ends_action and action_brackets_balanced(value)


def is_short_dialogue_paragraph(text: str, *, limit: int = SHORT_DIALOGUE_CHARS) -> bool:
    value = (text or '').strip()
    if not value or len(value) > limit:
        return False
    return not is_pure_action_paragraph(value)


def merge_short_adjacent_dialogues(
    paragraphs: list[str],
    *,
    limit: int = SHORT_DIALOGUE_CHARS,
    max_keep: int = DEFAULT_MAX_BUBBLES,
) -> list[str]:
    items = [item.strip() for item in paragraphs if item.strip()]
    keep = max(1, int(max_keep))
    changed = True
    while changed and len(items) > keep:
        changed = False
        for index, current in enumerate(items):
            if not is_short_dialogue_paragraph(current, limit=limit):
                continue
            if index > 0 and not is_pure_action_paragraph(items[index - 1]):
                items[index - 1] = items[index - 1] + '\n\n' + current
                del items[index]
                changed = True
                break
            if index + 1 < len(items) and not is_pure_action_paragraph(items[index + 1]):
                items[index] = current + '\n\n' + items[index + 1]
                del items[index + 1]
                changed = True
                break
            if index > 0:
                items[index - 1] = items[index - 1] + '\n\n' + current
                del items[index]
                changed = True
                break
            if index + 1 < len(items):
                items[index] = current + '\n\n' + items[index + 1]
                del items[index + 1]
                changed = True
                break
    return items


def pack_paragraphs(paragraphs: list[str], max_bubbles: int) -> list[str]:
    items = [item.strip() for item in paragraphs if item.strip()]
    max_n = max(1, min(int(max_bubbles), DEFAULT_MAX_BUBBLES))
    if not items:
        return []
    if len(items) <= max_n:
        return items
    if max_n == 1:
        return ['\n\n'.join(items)]
    if max_n == 2:
        return [items[0], '\n\n'.join(items[1:])]
    return [items[0], '\n\n'.join(items[1:-1]), items[-1]]


def split_reply_bubbles(text: str, *, max_bubbles: int = DEFAULT_MAX_BUBBLES) -> list[str]:
    raw = (text or '').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not raw:
        return []
    try:
        if not action_brackets_balanced(raw):
            return [raw]
        paragraphs = split_blank_line_paragraphs(raw)
        if len(paragraphs) <= 1:
            return [raw]
        max_n = max(1, min(int(max_bubbles), DEFAULT_MAX_BUBBLES))
        if len(paragraphs) <= max_n:
            return paragraphs
        merged = merge_short_adjacent_dialogues(paragraphs, max_keep=max_n)
        packed = pack_paragraphs(merged, max_n)
        cleaned = [item.strip() for item in packed if item.strip()]
        if cleaned:
            return cleaned
        return [raw]
    except Exception:
        return [raw]


def chat_bubble_split_allowed(
    config: Any,
    *,
    is_owner: bool,
    is_private: bool,
) -> bool:
    if not bool(getattr(config, 'enable_chat_bubble_split', False)):
        return False
    if not is_private:
        return False
    if bool(getattr(config, 'chat_bubble_split_owner_private_only', True)):
        return bool(is_owner)
    return True


def normalize_bubble_limits(config: Any) -> tuple[int, int, int]:
    min_delay = int(getattr(config, 'chat_bubble_min_delay_ms', 700) or 0)
    max_delay = int(getattr(config, 'chat_bubble_max_delay_ms', 1200) or 0)
    max_bubbles = int(getattr(config, 'chat_bubble_max_bubbles', DEFAULT_MAX_BUBBLES) or 0)
    if min_delay < 0:
        min_delay = 0
    if max_delay < 0:
        max_delay = 0
    if min_delay > max_delay:
        min_delay, max_delay = max_delay, min_delay
    max_delay = min(max_delay, HARD_MAX_DELAY_MS)
    min_delay = min(min_delay, max_delay)
    if max_bubbles <= 0:
        max_bubbles = 1
    max_bubbles = max(1, min(max_bubbles, DEFAULT_MAX_BUBBLES))
    return min_delay, max_delay, max_bubbles


def resolve_chat_bubbles(
    text: str,
    *,
    enabled: bool,
    max_bubbles: int = DEFAULT_MAX_BUBBLES,
) -> tuple[str, ...]:
    raw = text or ''
    if not enabled:
        return (raw,)
    bubbles = split_reply_bubbles(raw, max_bubbles=max_bubbles)
    if not bubbles:
        return (raw,)
    return tuple(bubbles)


def bubble_delay_ms(
    previous: str,
    current: str,
    *,
    min_delay_ms: int,
    max_delay_ms: int,
    remaining_budget_ms: int,
    rng: random.Random | None = None,
) -> int:
    if remaining_budget_ms <= 0:
        return 0
    low = min_delay_ms
    high = max_delay_ms
    prev_len = len((previous or '').strip())
    curr_len = len((current or '').strip())
    if prev_len <= SHORT_BUBBLE_CHARS and curr_len <= SHORT_BUBBLE_CHARS:
        low, high = SHORT_DELAY_MIN_MS, SHORT_DELAY_MAX_MS
    elif prev_len > LONG_PREV_CHARS:
        low, high = LONG_DELAY_MIN_MS, LONG_DELAY_MAX_MS
    if low > high:
        low, high = high, low
    high = min(high, HARD_MAX_DELAY_MS, remaining_budget_ms)
    low = min(low, high)
    if high <= 0:
        return 0
    roller = rng or random.Random()
    return int(roller.randint(low, high))


def next_bubble_delays(
    bubbles: list[str],
    *,
    min_delay_ms: int,
    max_delay_ms: int,
    rng: random.Random | None = None,
) -> list[int]:
    delays: list[int] = []
    remaining = HARD_MAX_TOTAL_DELAY_MS
    for index in range(1, len(bubbles)):
        delay = bubble_delay_ms(
            bubbles[index - 1],
            bubbles[index],
            min_delay_ms=min_delay_ms,
            max_delay_ms=max_delay_ms,
            remaining_budget_ms=remaining,
            rng=rng,
        )
        delays.append(delay)
        remaining = max(0, remaining - delay)
    return delays


async def wait_for_bubble_delay(session_key: str, generation: int, delay_ms: int) -> bool:
    if delay_ms <= 0:
        return not current_chat_bubble_generation(session_key) == generation
    loop = asyncio.get_running_loop()
    deadline = loop.time() + (delay_ms / 1000.0)
    while True:
        if not current_chat_bubble_generation(session_key) == generation:
            return True
        remaining = deadline - loop.time()
        if remaining <= 0:
            return not current_chat_bubble_generation(session_key) == generation
        await asyncio.sleep(min(POLL_SECONDS, remaining))
