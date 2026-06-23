import asyncio
from datetime import datetime
from pathlib import Path

from nonebot import get_driver, on_command, on_message
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageEvent, PrivateMessageEvent
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata
from nonebot.rule import Rule, to_me

from .access import (
    can_group_chat,
    can_private_chat,
    group_id,
    is_owner,
    message_length_limit,
    rate_limit_seconds,
    user_id,
)
from .access_store import (
    add_item,
    ensure_access_store,
    load_access_store,
    merged_access,
    remove_item,
)
from .config import load_config
from .llm import ask_llm
from .memory import append_message, build_history, clear_session
from .rate_limit import can_use_private_trial, check_rate_limit, increment_private_trial


__plugin_meta__ = PluginMetadata(
    name="AI Chat",
    description="QQ AI chat plugin powered by DeepSeek/OpenAI-compatible API.",
    usage="私聊或在授权群中 @我。命令：/状态 /重置 /权限帮助",
)

config = load_config()
ensure_access_store()
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ERROR_LOG_PATH = PROJECT_ROOT / "logs" / "ai_chat_error.log"
_session_locks: dict[str, asyncio.Lock] = {}


def current_access():
    return merged_access(
        config.private_whitelist,
        config.group_whitelist,
        config.user_blacklist,
    )


def session_lock(key: str) -> asyncio.Lock:
    lock = _session_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _session_locks[key] = lock
    return lock


def log_ai_event_error(exc: Exception, event: MessageEvent) -> None:
    ERROR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    group = event.group_id if isinstance(event, GroupMessageEvent) else ""
    with ERROR_LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(
            f"{datetime.now().isoformat(timespec='seconds')} "
            f"user={event.user_id} group={group} "
            f"{type(exc).__name__}: {exc}\n"
        )


async def reject_or_silent(matcher: Matcher, reason: str | None) -> None:
    if reason:
        await matcher.finish(reason)
    await matcher.finish()


def should_count_private_trial(event: MessageEvent) -> bool:
    access = current_access()
    if not isinstance(event, PrivateMessageEvent):
        return False
    if is_owner(config, event):
        return False
    if user_id(event) in access.private_whitelist:
        return False
    return config.allow_unknown_private_chat


async def check_access(event: MessageEvent, matcher: Matcher) -> None:
    access = current_access()
    if isinstance(event, PrivateMessageEvent):
        allowed, reason = can_private_chat(config, access, event)
        if not allowed:
            await reject_or_silent(matcher, reason)
        if should_count_private_trial(event) and not can_use_private_trial(
            user_id(event), config.private_trial_messages
        ):
            await matcher.finish("私聊试用次数已用完，请联系主人加入白名单。")
        return

    if isinstance(event, GroupMessageEvent):
        allowed, reason = can_group_chat(config, access, event)
        if not allowed:
            await reject_or_silent(matcher, reason)


async def check_message_limits(event: MessageEvent, matcher: Matcher, text: str) -> None:
    limit = message_length_limit(config, event)
    if limit > 0 and len(text) > limit:
        await matcher.finish(f"消息太长了，请控制在 {limit} 字以内。")

    if is_owner(config, event):
        return

    rate_key = f"{event.message_type}:{event.user_id}"
    ok, wait_seconds = check_rate_limit(rate_key, rate_limit_seconds(config, event))
    if not ok:
        await matcher.finish(f"说太快了，请等 {wait_seconds} 秒再试。")


def _is_private_enabled(event: MessageEvent) -> bool:
    return config.enable_private_chat and isinstance(event, PrivateMessageEvent)


def _is_group_enabled(event: MessageEvent) -> bool:
    return config.enable_group_chat and isinstance(event, GroupMessageEvent)


async def private_rule(event: MessageEvent) -> bool:
    return _is_private_enabled(event)


async def group_rule(event: MessageEvent) -> bool:
    return _is_group_enabled(event)


def session_key(event: MessageEvent) -> str:
    if isinstance(event, GroupMessageEvent):
        return f"group:{event.group_id}"
    return f"private:{event.user_id}"


def clean_text(event: MessageEvent) -> str:
    text = event.get_plaintext().strip()
    if text.startswith(("/", "!", "！")):
        return ""
    return text


def parse_single_arg(arg_text: str) -> str:
    return arg_text.strip().split()[0] if arg_text.strip() else ""


def status_lines() -> list[str]:
    driver = get_driver()
    access = current_access()
    return [
        f"机器人：{config.bot_name}",
        f"模型：{config.openai_model}",
        f"接口：{config.openai_base_url}",
        f"私聊：{'开启' if config.enable_private_chat else '关闭'}",
        f"群聊：{'开启' if config.enable_group_chat else '关闭'}",
        f"主人：{'已配置' if config.bot_owner_qq else '未配置'}",
        f"私聊白名单：{len(access.private_whitelist)}",
        f"群白名单：{len(access.group_whitelist)}",
        f"黑名单：{len(access.user_blacklist)}",
        f"私聊长度限制：{config.max_private_message_length}",
        f"群聊长度限制：{config.max_group_message_length}",
        f"私聊冷却：{config.private_rate_limit_seconds} 秒",
        f"群聊冷却：{config.group_rate_limit_seconds} 秒",
        f"环境：{driver.env}",
    ]


def list_lines(title: str, items: frozenset[str]) -> str:
    if not items:
        return f"{title}：空"
    return f"{title}：\n" + "\n".join(sorted(items))


async def require_owner(event: MessageEvent, matcher: Matcher) -> None:
    if not is_owner(config, event):
        await matcher.finish("只有主人可以执行这个命令。")


private_chat = on_message(rule=Rule(private_rule), priority=20, block=True)
group_chat = on_message(rule=to_me() & Rule(group_rule), priority=20, block=True)
reset_cmd = on_command("reset", aliases={"重置", "清空上下文"}, priority=5, block=True)
status_cmd = on_command("status", aliases={"状态"}, priority=5, block=True)
help_cmd = on_command("权限帮助", aliases={"白名单帮助", "管理帮助"}, priority=5, block=True)

allow_group_cmd = on_command("加入群白名单", aliases={"允许群", "allow_group"}, priority=5, block=True)
deny_group_cmd = on_command("移出群白名单", aliases={"删除群白名单", "deny_group"}, priority=5, block=True)
enable_group_cmd = on_command("启用本群", aliases={"加入本群", "enable_group"}, priority=5, block=True)
disable_group_cmd = on_command("禁用本群", aliases={"移出本群", "disable_group"}, priority=5, block=True)

allow_private_cmd = on_command("加入私聊白名单", aliases={"允许私聊", "allow_private"}, priority=5, block=True)
deny_private_cmd = on_command("移出私聊白名单", aliases={"删除私聊白名单", "deny_private"}, priority=5, block=True)

block_user_cmd = on_command("加入黑名单", aliases={"拉黑用户", "block_user"}, priority=5, block=True)
unblock_user_cmd = on_command("移出黑名单", aliases={"解除拉黑", "unblock_user"}, priority=5, block=True)

groups_cmd = on_command("群白名单", aliases={"groups"}, priority=5, block=True)
private_users_cmd = on_command("私聊白名单", aliases={"private_users"}, priority=5, block=True)
blacklist_cmd = on_command("黑名单", aliases={"blacklist"}, priority=5, block=True)


async def handle_chat(event: MessageEvent, matcher: Matcher) -> None:
    await check_access(event, matcher)

    text = clean_text(event)
    if not text:
        return

    await check_message_limits(event, matcher, text)

    key = session_key(event)
    async with session_lock(key):
        history = build_history(key, config.max_context_messages)

        await matcher.send("正在思考...")
        try:
            reply = await ask_llm(config, history, text)
        except Exception as exc:
            log_ai_event_error(exc, event)
            await matcher.finish(f"AI 调用失败：{type(exc).__name__}")
            return

        append_message(key, "user", text, config.max_context_messages)
        append_message(key, "assistant", reply, config.max_context_messages)
        if should_count_private_trial(event):
            increment_private_trial(user_id(event))
        await matcher.finish(reply)


@private_chat.handle()
async def _(event: MessageEvent, matcher: Matcher) -> None:
    await handle_chat(event, matcher)


@group_chat.handle()
async def _(event: MessageEvent, matcher: Matcher) -> None:
    await handle_chat(event, matcher)


@reset_cmd.handle()
async def _(event: MessageEvent, matcher: Matcher) -> None:
    clear_session(session_key(event))
    await matcher.finish("已清空当前会话上下文。")


@status_cmd.handle()
async def _(event: MessageEvent, matcher: Matcher) -> None:
    await require_owner(event, matcher)
    await matcher.finish("\n".join(status_lines()))


@help_cmd.handle()
async def _(matcher: Matcher) -> None:
    await matcher.finish(
        "\n".join(
            [
                "权限管理命令：",
                "/启用本群",
                "/禁用本群",
                "/加入群白名单 群号",
                "/移出群白名单 群号",
                "/加入私聊白名单 QQ号",
                "/移出私聊白名单 QQ号",
                "/加入黑名单 QQ号",
                "/移出黑名单 QQ号",
                "/群白名单",
                "/私聊白名单",
                "/黑名单",
                "以上管理命令只有主人可用。",
            ]
        )
    )


@enable_group_cmd.handle()
async def _(event: MessageEvent, matcher: Matcher) -> None:
    await require_owner(event, matcher)
    if not isinstance(event, GroupMessageEvent):
        await matcher.finish("这个命令只能在群聊中使用。")
    changed = add_item("group_whitelist", group_id(event))
    await matcher.finish("已加入本群白名单。" if changed else "本群已经在白名单中。")


@disable_group_cmd.handle()
async def _(event: MessageEvent, matcher: Matcher) -> None:
    await require_owner(event, matcher)
    if not isinstance(event, GroupMessageEvent):
        await matcher.finish("这个命令只能在群聊中使用。")
    changed = remove_item("group_whitelist", group_id(event))
    await matcher.finish("已移出本群白名单。" if changed else "本群不在动态白名单中。")


@allow_group_cmd.handle()
async def _(event: MessageEvent, matcher: Matcher, arg=CommandArg()) -> None:
    await require_owner(event, matcher)
    target = parse_single_arg(arg.extract_plain_text())
    if not target:
        await matcher.finish("用法：/加入群白名单 群号")
    changed = add_item("group_whitelist", target)
    await matcher.finish(f"已加入群白名单：{target}" if changed else f"群已在白名单中：{target}")


@deny_group_cmd.handle()
async def _(event: MessageEvent, matcher: Matcher, arg=CommandArg()) -> None:
    await require_owner(event, matcher)
    target = parse_single_arg(arg.extract_plain_text())
    if not target:
        await matcher.finish("用法：/移出群白名单 群号")
    changed = remove_item("group_whitelist", target)
    await matcher.finish(f"已移出群白名单：{target}" if changed else f"动态群白名单中没有：{target}")


@allow_private_cmd.handle()
async def _(event: MessageEvent, matcher: Matcher, arg=CommandArg()) -> None:
    await require_owner(event, matcher)
    target = parse_single_arg(arg.extract_plain_text())
    if not target:
        await matcher.finish("用法：/加入私聊白名单 QQ号")
    changed = add_item("private_whitelist", target)
    await matcher.finish(f"已加入私聊白名单：{target}" if changed else f"用户已在私聊白名单中：{target}")


@deny_private_cmd.handle()
async def _(event: MessageEvent, matcher: Matcher, arg=CommandArg()) -> None:
    await require_owner(event, matcher)
    target = parse_single_arg(arg.extract_plain_text())
    if not target:
        await matcher.finish("用法：/移出私聊白名单 QQ号")
    changed = remove_item("private_whitelist", target)
    await matcher.finish(f"已移出私聊白名单：{target}" if changed else f"动态私聊白名单中没有：{target}")


@block_user_cmd.handle()
async def _(event: MessageEvent, matcher: Matcher, arg=CommandArg()) -> None:
    await require_owner(event, matcher)
    target = parse_single_arg(arg.extract_plain_text())
    if not target:
        await matcher.finish("用法：/加入黑名单 QQ号")
    changed = add_item("user_blacklist", target)
    await matcher.finish(f"已加入黑名单：{target}" if changed else f"用户已在黑名单中：{target}")


@unblock_user_cmd.handle()
async def _(event: MessageEvent, matcher: Matcher, arg=CommandArg()) -> None:
    await require_owner(event, matcher)
    target = parse_single_arg(arg.extract_plain_text())
    if not target:
        await matcher.finish("用法：/移出黑名单 QQ号")
    changed = remove_item("user_blacklist", target)
    await matcher.finish(f"已移出黑名单：{target}" if changed else f"动态黑名单中没有：{target}")


@groups_cmd.handle()
async def _(event: MessageEvent, matcher: Matcher) -> None:
    await require_owner(event, matcher)
    await matcher.finish(list_lines("群白名单", current_access().group_whitelist))


@private_users_cmd.handle()
async def _(event: MessageEvent, matcher: Matcher) -> None:
    await require_owner(event, matcher)
    await matcher.finish(list_lines("私聊白名单", current_access().private_whitelist))


@blacklist_cmd.handle()
async def _(event: MessageEvent, matcher: Matcher) -> None:
    await require_owner(event, matcher)
    await matcher.finish(list_lines("黑名单", current_access().user_blacklist))
