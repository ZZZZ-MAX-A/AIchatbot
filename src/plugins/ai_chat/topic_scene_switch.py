from __future__ import annotations

from .memory_time import message_time_context

from dataclasses import dataclass
import re
from threading import RLock
from typing import Any

from .config import AiChatConfig
from .database import connect, current_persona_memory_id, ensure_database
from .gap_scene_summaries import clear_gap_scene_summaries
from .llm import summarize_topic_scene_messages
from .memory import clear_session
from .summaries import add_summary


TOPIC_SCENE_SUMMARY_PREFIX = "【话题场景摘要｜主动换场】"
TOPIC_SCENE_HINT_TURNS_DEFAULT = 3

_HARD_TRIGGER_EXACT = frozenset(
    {
        "换个话题",
        "换话题",
        "聊点别的",
        "先到这里",
        "先这样吧，换一段",
        "先这样吧换一段",
        "新开一段",
        "重新开始这段",
        "这段先结束",
        "清空短时上下文",
    }
)

_HARD_TRIGGER_COMMAND_ALIASES = frozenset(
    {
        "换话题",
        "新开一段",
        "场景重置",
        "topic_switch",
        "switch_topic",
    }
)

_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class TopicSwitchIntent:
    trigger: str
    source: str
    raw_text: str


@dataclass(frozen=True)
class TopicSwitchResult:
    ok: bool
    reason_code: str
    ack_text: str
    summary_id: int | None = None
    source_message_count: int = 0
    cleared_messages: bool = False
    summarized: bool = False


@dataclass(frozen=True)
class TopicSwitchRuntimeState:
    remaining_hint_turns: int = 0
    last_summary_id: int | None = None


_runtime_lock = RLock()
_runtime_state: dict[str, TopicSwitchRuntimeState] = {}


def normalize_topic_switch_text(text: str) -> str:
    cleaned = _WHITESPACE_RE.sub("", (text or "").strip())
    return cleaned.strip("。.!！?？~～")


def detect_topic_switch_intent(text: str) -> TopicSwitchIntent | None:
    raw = (text or "").strip()
    if not raw:
        return None
    normalized = normalize_topic_switch_text(raw)
    if not normalized:
        return None
    if normalized in _HARD_TRIGGER_EXACT:
        return TopicSwitchIntent(trigger=normalized, source="natural", raw_text=raw)
    return None


def detect_topic_switch_command(command_name: str) -> TopicSwitchIntent | None:
    name = normalize_topic_switch_text(command_name or "")
    if name in _HARD_TRIGGER_COMMAND_ALIASES or name in _HARD_TRIGGER_EXACT:
        return TopicSwitchIntent(trigger=name or "换话题", source="command", raw_text=command_name)
    return None


def format_topic_scene_summary(body: str) -> str:
    content = (body or "").strip()
    if not content:
        return ""
    if content.startswith(TOPIC_SCENE_SUMMARY_PREFIX):
        return content
    return f"{TOPIC_SCENE_SUMMARY_PREFIX}\n{content}"


def mark_topic_switch_hint(
    session_key: str,
    *,
    summary_id: int | None = None,
    turns: int = TOPIC_SCENE_HINT_TURNS_DEFAULT,
) -> None:
    key = (session_key or "").strip()
    if not key:
        return
    remaining = max(0, int(turns))
    with _runtime_lock:
        _runtime_state[key] = TopicSwitchRuntimeState(
            remaining_hint_turns=remaining,
            last_summary_id=summary_id,
        )


def consume_topic_switch_hint(session_key: str) -> str:
    key = (session_key or "").strip()
    if not key:
        return ""
    with _runtime_lock:
        state = _runtime_state.get(key)
        if state is None or state.remaining_hint_turns <= 0:
            return ""
        remaining = state.remaining_hint_turns - 1
        if remaining <= 0:
            _runtime_state.pop(key, None)
        else:
            _runtime_state[key] = TopicSwitchRuntimeState(
                remaining_hint_turns=remaining,
                last_summary_id=state.last_summary_id,
            )
    return (
        "主人已主动结束上一短时场景并开启新话题。"
        "不要默认续写上一场景的动作、姿势或未完成角色扮演。"
        "若新消息未提及旧场景，按新场景自然开聊；"
        "仅当主人明确要求“接着刚才”时再回到上一场景摘要。"
    )


def clear_topic_switch_runtime_for_tests() -> None:
    with _runtime_lock:
        _runtime_state.clear()


def _success_ack(*, summarized: bool, source_message_count: int) -> str:
    if summarized:
        return (
            "好，上一场景我先收束归档了。短时上下文已重置，长期记忆还在。\n"
            "你直接说下一句，我们开新的一段。"
        )
    if source_message_count <= 0:
        return (
            "当前几乎没有需要归档的短时内容。已按新话题处理，长期记忆还在。\n"
            "你直接说下一句吧。"
        )
    return (
        "好，短时上下文已重置，长期记忆还在。\n"
        "你直接说下一句，我们开新的一段。"
    )


def _list_session_messages(session_key: str) -> list[Any]:
    ensure_database()
    with connect() as connection:
        return connection.execute(
            """
            SELECT
                id,
                message_type,
                user_id,
                group_id,
                role,
                content, created_at, occurred_at, time_kind
            FROM messages
            WHERE session_key = ?
            ORDER BY id ASC
            """,
            (session_key,),
        ).fetchall()


def _format_messages_for_summary(rows: list[Any], owner_qq: str) -> str:
    lines: list[str] = []
    for row in rows:
        if row["role"] != "user":
            role = "AI"
        elif owner_qq and str(row["user_id"]) == owner_qq:
            role = "主人"
        else:
            role = "用户"
        content = str(row["content"] or "").strip()
        if content:
            lines.append(f"{message_time_context(row)} {role}: {content}")
    return "\n".join(lines)


async def switch_topic_scene(
    config: AiChatConfig,
    session_key: str,
    *,
    intent: TopicSwitchIntent | None = None,
    message_type: str = "private",
    user_id: str | None = None,
    group_id: str | None = None,
    allow_when_disabled: bool = False,
) -> TopicSwitchResult:
    if not allow_when_disabled and not getattr(config, "enable_topic_scene_switch", True):
        return TopicSwitchResult(
            ok=False,
            reason_code="disabled",
            ack_text="换话题功能当前未开启。",
        )

    key = (session_key or "").strip()
    if not key:
        return TopicSwitchResult(
            ok=False,
            reason_code="invalid_session",
            ack_text="当前会话无效，无法换话题。",
        )

    if getattr(config, "topic_scene_switch_private_only", True) and message_type != "private":
        return TopicSwitchResult(
            ok=False,
            reason_code="not_private",
            ack_text="换话题目前只支持私聊。",
        )

    rows = _list_session_messages(key)
    source_count = len(rows)
    min_source = max(int(getattr(config, "topic_scene_min_source_messages", 4) or 0), 0)

    summary_id: int | None = None
    summarized = False

    if source_count >= min_source and source_count > 0:
        message_text = _format_messages_for_summary(rows, getattr(config, "bot_owner_qq", ""))
        if message_text.strip():
            try:
                body = await summarize_topic_scene_messages(
                    config,
                    message_text,
                    role_card_key=current_persona_memory_id(),
                )
            except Exception:
                return TopicSwitchResult(
                    ok=False,
                    reason_code="summarize_failed",
                    ack_text="换场失败：场景摘要生成出错，短时上下文仍保留。请稍后再试。",
                    source_message_count=source_count,
                    cleared_messages=False,
                    summarized=False,
                )
            formatted = format_topic_scene_summary(body)
            if not formatted:
                return TopicSwitchResult(
                    ok=False,
                    reason_code="summarize_failed",
                    ack_text="换场失败：场景摘要为空，短时上下文仍保留。请稍后再试。",
                    source_message_count=source_count,
                    cleared_messages=False,
                    summarized=False,
                )
            first = rows[0]
            last = rows[-1]
            resolved_message_type = str(first["message_type"] or message_type or "private")
            resolved_group_id = (
                str(first["group_id"]) if first["group_id"] is not None else group_id
            )
            resolved_user_id = (
                str(first["user_id"])
                if resolved_message_type == "private" and first["user_id"] is not None
                else user_id
            )
            try:
                summary_id = add_summary(
                    session_key=key,
                    message_type=resolved_message_type,
                    user_id=resolved_user_id,
                    group_id=resolved_group_id,
                    summary=formatted,
                    message_start_id=int(first["id"]),
                    message_end_id=int(last["id"]),
                    source_message_count=source_count,
                )
            except Exception:
                return TopicSwitchResult(
                    ok=False,
                    reason_code="summarize_failed",
                    ack_text="换场失败：场景摘要写入出错，短时上下文仍保留。请稍后再试。",
                    source_message_count=source_count,
                    cleared_messages=False,
                    summarized=False,
                )
            summarized = True

    try:
        clear_session(key)
    except Exception:
        return TopicSwitchResult(
            ok=False,
            reason_code="clear_failed",
            ack_text=(
                "已尝试归档，但短时上下文重置未完成。请再说一次“换个话题”。"
                if summarized
                else "换场失败：短时上下文重置出错，请稍后再试。"
            ),
            summary_id=summary_id,
            source_message_count=source_count,
            cleared_messages=False,
            summarized=summarized,
        )

    try:
        clear_gap_scene_summaries(key)
    except Exception:
        pass

    remaining = int(
        getattr(config, "topic_scene_hint_turns", TOPIC_SCENE_HINT_TURNS_DEFAULT) or 0
    )
    mark_topic_switch_hint(key, summary_id=summary_id, turns=max(remaining, 0))

    return TopicSwitchResult(
        ok=True,
        reason_code="ok",
        ack_text=_success_ack(summarized=summarized, source_message_count=source_count),
        summary_id=summary_id,
        source_message_count=source_count,
        cleared_messages=True,
        summarized=summarized,
    )


def topic_switch_enabled(config: AiChatConfig) -> bool:
    return bool(getattr(config, "enable_topic_scene_switch", True))

