from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeAlias


AccessOperation: TypeAlias = Callable[[str, str], bool]
ClearImageCache: TypeAlias = Callable[[], int]
ClearErrorLog: TypeAlias = Callable[[], str]
SelectRoleCard: TypeAlias = Callable[[str], Any]
AddManualMemory: TypeAlias = Callable[..., int]
SubjectLabel: TypeAlias = Callable[[str, str], str]
ClearSessionSummaries: TypeAlias = Callable[[str], int]
DeleteSessionSummary: TypeAlias = Callable[[str, int], bool]


def _missing(name: str):
    def provider(*_args, **_kwargs):
        raise RuntimeError(f"owner write dependency not configured: {name}")

    return provider


@dataclass(frozen=True)
class OwnerWriteRuntime:
    clear_image_cache: ClearImageCache = field(
        default_factory=lambda: _missing("clear_image_cache")
    )
    clear_error_log: ClearErrorLog = field(
        default_factory=lambda: _missing("clear_error_log")
    )
    add_access_item: AccessOperation = field(
        default_factory=lambda: _missing("add_access_item")
    )
    remove_access_item: AccessOperation = field(
        default_factory=lambda: _missing("remove_access_item")
    )
    select_role_card: SelectRoleCard = field(
        default_factory=lambda: _missing("select_role_card")
    )
    add_manual_memory: AddManualMemory = field(
        default_factory=lambda: _missing("add_manual_memory")
    )
    subject_label: SubjectLabel = field(
        default_factory=lambda: _missing("subject_label")
    )
    clear_session_summaries: ClearSessionSummaries = field(
        default_factory=lambda: _missing("clear_session_summaries")
    )
    delete_session_summary: DeleteSessionSummary = field(
        default_factory=lambda: _missing("delete_session_summary")
    )
    owner_user_id_default: str = ""
    fact_memory_type: str = "fact_summary"
    preference_memory_type: str = "preference_summary"


def _context_metadata(context: Any) -> dict[str, Any]:
    metadata = getattr(context, "metadata", {}) or {}
    return metadata if isinstance(metadata, dict) else {}


def _tool_arguments(context: Any) -> dict[str, Any]:
    arguments = _context_metadata(context).get("tool_arguments", {}) or {}
    return arguments if isinstance(arguments, dict) else {}


def _argument_text(context: Any, name: str) -> str:
    return str(_tool_arguments(context).get(name) or "").strip()


def _metadata_text(context: Any, name: str) -> str:
    return str(_context_metadata(context).get(name) or "").strip()


def run_owner_write_command(
    runtime: OwnerWriteRuntime,
    command: str,
    context: Any,
) -> str:
    if command == "clear_image_cache":
        count = runtime.clear_image_cache()
        return f"已清空图片缓存：{count} 条。"
    if command == "clear_error_log":
        return runtime.clear_error_log()

    access_operations: dict[str, tuple[AccessOperation, str, str, str]] = {
        "allow_group": (
            runtime.add_access_item,
            "group_whitelist",
            "已加入群白名单",
            "群已在白名单中",
        ),
        "deny_group": (
            runtime.remove_access_item,
            "group_whitelist",
            "已移出群白名单",
            "动态群白名单中没有",
        ),
        "allow_private": (
            runtime.add_access_item,
            "private_whitelist",
            "已加入私聊白名单",
            "用户已在私聊白名单中",
        ),
        "deny_private": (
            runtime.remove_access_item,
            "private_whitelist",
            "已移出私聊白名单",
            "动态私聊白名单中没有",
        ),
        "block_user": (
            runtime.add_access_item,
            "user_blacklist",
            "已加入黑名单",
            "用户已在黑名单中",
        ),
        "unblock_user": (
            runtime.remove_access_item,
            "user_blacklist",
            "已移出黑名单",
            "动态黑名单中没有",
        ),
    }
    if command in access_operations:
        target = _argument_text(context, "target")
        if not target.isdigit():
            raise RuntimeError(f"{command} requires numeric target")
        operation, list_name, changed_text, unchanged_text = access_operations[command]
        changed = operation(list_name, target)
        return f"{changed_text}：{target}" if changed else f"{unchanged_text}：{target}"

    if command == "select_persona":
        target = _argument_text(context, "target")
        if not target:
            raise RuntimeError("select_persona requires target")
        card = runtime.select_role_card(target)
        if card is None:
            return f"没有找到角色卡：{target}"
        return f"已选择角色卡：{card.key}，{card.title}"

    if command in {"add_fact_memory", "add_preference_memory"}:
        content = _argument_text(context, "content")
        if not content:
            raise RuntimeError(f"{command} requires content")
        owner_user_id = _metadata_text(context, "user_id") or runtime.owner_user_id_default
        if not owner_user_id:
            raise RuntimeError(f"{command} requires owner user_id")
        memory_type = (
            runtime.fact_memory_type
            if command == "add_fact_memory"
            else runtime.preference_memory_type
        )
        memory_id = runtime.add_manual_memory(
            subject_type="user",
            subject_id=owner_user_id,
            content=content,
            memory_type=memory_type,
            source_session_key=_metadata_text(context, "session_key") or None,
        )
        label = "事实摘要记忆" if command == "add_fact_memory" else "偏好摘要记忆"
        return (
            f"已添加{label}：ID {memory_id}，对象："
            f"{runtime.subject_label('user', owner_user_id)}。"
        )

    if command == "clear_session_summaries":
        key = _metadata_text(context, "session_key")
        if not key:
            raise RuntimeError("clear_session_summaries requires session_key")
        count = runtime.clear_session_summaries(key)
        return f"已清空当前会话摘要：{count} 条。"

    if command == "delete_session_summary":
        key = _metadata_text(context, "session_key")
        if not key:
            raise RuntimeError("delete_session_summary requires session_key")
        summary_id = _argument_text(context, "summary_id")
        if not summary_id.isdigit():
            raise RuntimeError("delete_session_summary requires numeric summary_id")
        deleted = runtime.delete_session_summary(key, int(summary_id))
        if deleted:
            return f"已删除当前会话摘要：ID {summary_id}。"
        return f"没有找到当前会话摘要：{summary_id}"

    raise RuntimeError(f"unsupported owner write command: {command}")
