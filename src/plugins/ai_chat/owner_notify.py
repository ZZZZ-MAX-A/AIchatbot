import re

from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageEvent


EMPTY_NOTIFICATION_MESSAGE = "请填写 50 字以内的转告内容。"
TOO_LONG_NOTIFICATION_MESSAGE = "请主动联系主人，文本过长不予转告。"
SENSITIVE_NOTIFICATION_MESSAGE = "内容包含敏感信息，不予转告。"


SENSITIVE_PATTERNS = (
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?i)\b(api[_ -]?key|token|secret|password|passwd|pwd)\b"),
    re.compile(r"(密码|口令|验证码|令牌|密钥|二维码|数据库内容|chatbot\.db|身份证|手机号)"),
)


def contains_sensitive_notification_content(content: str) -> bool:
    return any(pattern.search(content) for pattern in SENSITIVE_PATTERNS)


def validate_owner_notification_content(content: str, max_length: int) -> str | None:
    if not content:
        return EMPTY_NOTIFICATION_MESSAGE
    if max_length > 0 and len(content) > max_length:
        return TOO_LONG_NOTIFICATION_MESSAGE
    if contains_sensitive_notification_content(content):
        return SENSITIVE_NOTIFICATION_MESSAGE
    return None


def format_owner_notification(event: MessageEvent, content: str) -> str:
    if isinstance(event, GroupMessageEvent):
        return "\n".join(
            [
                "收到一条转告：",
                f"来源：群 {event.group_id}",
                f"发送人：{event.user_id}",
                f"内容：{content}",
            ]
        )
    return "\n".join(
        [
            "收到一条转告：",
            f"来源：私聊用户 {event.user_id}",
            f"内容：{content}",
        ]
    )
