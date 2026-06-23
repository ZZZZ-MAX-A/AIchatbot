from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageEvent, PrivateMessageEvent

from .config import AiChatConfig
from .access_store import AccessStore


def user_id(event: MessageEvent) -> str:
    return str(event.user_id)


def group_id(event: GroupMessageEvent) -> str:
    return str(event.group_id)


def is_owner(config: AiChatConfig, event: MessageEvent) -> bool:
    return bool(config.bot_owner_qq) and user_id(event) == config.bot_owner_qq


def is_blacklisted(access: AccessStore, event: MessageEvent) -> bool:
    return user_id(event) in access.user_blacklist


def can_private_chat(
    config: AiChatConfig,
    access: AccessStore,
    event: PrivateMessageEvent,
) -> tuple[bool, str | None]:
    if not config.enable_private_chat:
        return False, None
    if is_blacklisted(access, event):
        return False, None
    if is_owner(config, event):
        return True, None
    if user_id(event) in access.private_whitelist:
        return True, None
    if config.allow_unknown_private_chat:
        return True, None
    return False, "当前不开放私聊，请在授权群聊中 @我使用。"


def can_group_chat(
    config: AiChatConfig,
    access: AccessStore,
    event: GroupMessageEvent,
) -> tuple[bool, str | None]:
    if not config.enable_group_chat:
        return False, None
    if is_blacklisted(access, event):
        return False, None
    if not access.group_whitelist:
        return False, None
    if group_id(event) not in access.group_whitelist:
        return False, None
    return True, None


def message_length_limit(config: AiChatConfig, event: MessageEvent) -> int:
    if isinstance(event, GroupMessageEvent):
        return config.max_group_message_length
    return config.max_private_message_length


def rate_limit_seconds(config: AiChatConfig, event: MessageEvent) -> int:
    if isinstance(event, GroupMessageEvent):
        return config.group_rate_limit_seconds
    return config.private_rate_limit_seconds
