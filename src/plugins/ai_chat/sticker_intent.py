from __future__ import annotations

from dataclasses import dataclass
import json
import re

from .sticker_library import ALLOWED_INTENSITIES, ALLOWED_MOODS, ALLOWED_USAGE_TAGS


STICKER_INTENT_START = "[[STICKER_INTENT]]"
STICKER_INTENT_END = "[[/STICKER_INTENT]]"
MAX_STICKER_INTENT_JSON_CHARS = 600

STICKER_INTENT_SYSTEM_CONTEXT = f"""
你仍然必须先按当前角色卡正常回答用户。只有在正常可见回复全部结束后，追加一行机器控制标记；不要在正文中解释、引用或提及该标记。

固定格式：
{STICKER_INTENT_START}{{"attach":true或false,"mood":"白名单值","intensity":"soft|medium|strong","scene":"白名单值","confidence":0到1}}{STICKER_INTENT_END}

情绪白名单：{', '.join(sorted(ALLOWED_MOODS))}
场景白名单：{', '.join(sorted(ALLOWED_USAGE_TAGS))}

判定原则：
1. attach 只是“建议本轮文本之后可以附带一张表情”，不是发送命令；你不能选择 sticker ID、文件名、路径或 URL。
2. 只有本轮回复具有明确、自然、值得强调的情绪或互动动作时才 attach=true。普通事实回答、技术说明、安全边界、管理命令、严肃内容、道歉纠错和不确定语境默认 false。
3. 不要因为用户消息出现某个关键词就机械触发；按本轮完整语义和你实际写出的回复判断。
4. mood、intensity、scene 只能各选一个白名单值。无法确定时 attach=false，confidence 降低。
5. 即使 attach=true，本地策略仍可能因为低置信度、无匹配、冷却或频率上限拒绝；不得在正文承诺会发送图片。
6. 标记必须是最后一行，只能出现一次；不得输出 Markdown 代码围栏或额外 JSON。
""".strip()


_FINAL_MARKER_PATTERN = re.compile(
    rf"(?:\r?\n)?{re.escape(STICKER_INTENT_START)}(.{{1,{MAX_STICKER_INTENT_JSON_CHARS}}}){re.escape(STICKER_INTENT_END)}\s*\Z",
    re.DOTALL,
)


@dataclass(frozen=True)
class StickerIntent:
    mood: str
    intensity: str
    scene: str
    confidence: float


@dataclass(frozen=True)
class StickerIntentExtraction:
    visible_reply: str
    intent: StickerIntent | None
    status: str


def _visible_prefix(content: str) -> str:
    positions = [
        position
        for token in (STICKER_INTENT_START, STICKER_INTENT_END)
        if (position := content.find(token)) >= 0
    ]
    if not positions:
        return content.strip()
    return content[: min(positions)].rstrip()


def extract_sticker_intent(content: str) -> StickerIntentExtraction:
    if not isinstance(content, str):
        return StickerIntentExtraction("", None, "invalid_reply_type")
    if STICKER_INTENT_START not in content and STICKER_INTENT_END not in content:
        return StickerIntentExtraction(content.strip(), None, "marker_absent")
    visible_reply = _visible_prefix(content)
    match = _FINAL_MARKER_PATTERN.search(content)
    if match is None or match.start() < len(visible_reply):
        return StickerIntentExtraction(visible_reply, None, "marker_invalid")
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return StickerIntentExtraction(visible_reply, None, "json_invalid")
    if not isinstance(payload, dict) or set(payload) != {
        "attach",
        "mood",
        "intensity",
        "scene",
        "confidence",
    }:
        return StickerIntentExtraction(visible_reply, None, "contract_invalid")
    attach = payload.get("attach")
    if type(attach) is not bool:
        return StickerIntentExtraction(visible_reply, None, "contract_invalid")
    mood = payload.get("mood")
    intensity = payload.get("intensity")
    scene = payload.get("scene")
    confidence = payload.get("confidence")
    if (
        not isinstance(mood, str)
        or mood not in ALLOWED_MOODS
        or not isinstance(intensity, str)
        or intensity not in ALLOWED_INTENSITIES
        or not isinstance(scene, str)
        or scene not in ALLOWED_USAGE_TAGS
        or not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0.0 <= float(confidence) <= 1.0
    ):
        return StickerIntentExtraction(visible_reply, None, "contract_invalid")
    if not attach:
        return StickerIntentExtraction(visible_reply, None, "not_requested")
    return StickerIntentExtraction(
        visible_reply,
        StickerIntent(mood, intensity, scene, float(confidence)),
        "requested",
    )
