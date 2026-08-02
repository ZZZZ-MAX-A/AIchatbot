from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Callable

from .access_store import (
    AccessStoreCorruptError,
    AccessStoreRevisionConflict,
    ListName,
    update_item,
)
from .config import AiChatConfig, load_config
from .database import utc_now


OWNER_CONSOLE_ACCESS_ACTIONS_ENABLED_ENV = "OWNER_CONSOLE_ACCESS_ACTIONS_ENABLED"
OWNER_CONSOLE_ACCESS_ACTION_HEADERS = {
    ("private_whitelist", "add"): "access-private-whitelist-add-v1",
    ("private_whitelist", "remove"): "access-private-whitelist-remove-v1",
    ("group_whitelist", "add"): "access-group-whitelist-add-v1",
    ("group_whitelist", "remove"): "access-group-whitelist-remove-v1",
    ("user_blacklist", "add"): "access-user-blacklist-add-v1",
    ("user_blacklist", "remove"): "access-user-blacklist-remove-v1",
}
OWNER_CONSOLE_ACCESS_CONFIRMATIONS = {
    ("private_whitelist", "add"): "add_private_whitelist_item",
    ("private_whitelist", "remove"): "remove_private_whitelist_item",
    ("group_whitelist", "add"): "add_group_whitelist_item",
    ("group_whitelist", "remove"): "remove_group_whitelist_item",
    ("user_blacklist", "add"): "add_user_blacklist_item",
    ("user_blacklist", "remove"): "remove_user_blacklist_item",
}


class OwnerConsoleAccessActionError(RuntimeError):
    code = "internal_error"
    status_code = 500


class OwnerConsoleAccessActionDisabled(OwnerConsoleAccessActionError):
    code = "forbidden"
    status_code = 403


class OwnerConsoleAccessActionForbidden(OwnerConsoleAccessActionError):
    code = "forbidden"
    status_code = 403


class OwnerConsoleAccessActionInvalid(OwnerConsoleAccessActionError):
    code = "bad_request"
    status_code = 400


class OwnerConsoleAccessActionConflict(OwnerConsoleAccessActionError):
    code = "conflict"
    status_code = 409


@dataclass(frozen=True)
class OwnerConsoleAccessActionResult:
    generated_at: str
    list_name: str
    operation: str
    item: str
    changed: bool
    effective: bool
    revision: int
    source_after: str
    code: str
    safe_message: str


def _environment_items(config: AiChatConfig, list_name: ListName) -> frozenset[str]:
    return {
        "private_whitelist": config.private_whitelist,
        "group_whitelist": config.group_whitelist,
        "user_blacklist": config.user_blacklist,
    }[list_name]


def _validated_item(item: str) -> str:
    normalized = item.strip()
    if not normalized.isascii() or not normalized.isdigit():
        raise OwnerConsoleAccessActionInvalid("access item must contain ASCII digits only")
    if not 5 <= len(normalized) <= 20:
        raise OwnerConsoleAccessActionInvalid(
            "access item length must be between 5 and 20 digits"
        )
    return normalized


@dataclass
class OwnerConsoleAccessActionRuntime:
    enabled: bool = False
    config_provider: Callable[[], AiChatConfig] = load_config
    store_path: Path | None = None

    def __post_init__(self) -> None:
        self.enabled = bool(self.enabled)
        self._lock = RLock()

    def mutate(
        self,
        *,
        list_name: ListName,
        operation: str,
        item: str,
        expected_revision: int,
    ) -> OwnerConsoleAccessActionResult:
        if not self.enabled:
            raise OwnerConsoleAccessActionDisabled("web access actions are disabled")
        if operation not in {"add", "remove"}:
            raise OwnerConsoleAccessActionInvalid("unsupported access operation")
        normalized = _validated_item(item)
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
            raise OwnerConsoleAccessActionInvalid("access revision must be an integer")
        if expected_revision < 0:
            raise OwnerConsoleAccessActionInvalid("access revision must not be negative")

        with self._lock:
            config = self.config_provider()
            environment_items = _environment_items(config, list_name)
            if (
                list_name == "user_blacklist"
                and operation == "add"
                and normalized == config.bot_owner_qq.strip()
            ):
                raise OwnerConsoleAccessActionForbidden(
                    "the configured owner cannot be added to the user blacklist"
                )
            if operation == "add" and normalized in environment_items:
                raise OwnerConsoleAccessActionConflict(
                    "access item is already managed by the environment"
                )
            try:
                updated, changed = update_item(
                    list_name,
                    normalized,
                    add=operation == "add",
                    expected_revision=expected_revision,
                    path=self.store_path,
                )
            except AccessStoreRevisionConflict as exc:
                raise OwnerConsoleAccessActionConflict(
                    "access list changed; refresh before retrying"
                ) from exc
            except AccessStoreCorruptError as exc:
                raise OwnerConsoleAccessActionConflict(
                    "access store is invalid and was not overwritten"
                ) from exc
            if not changed:
                if operation == "remove" and normalized in environment_items:
                    raise OwnerConsoleAccessActionForbidden(
                        "environment-managed access items cannot be removed from the web"
                    )
                verb = "already exists" if operation == "add" else "does not exist"
                raise OwnerConsoleAccessActionConflict(f"dynamic access item {verb}")

            dynamic_items = getattr(updated, list_name)
            in_environment = normalized in environment_items
            in_dynamic = normalized in dynamic_items
            source_after = (
                "environment_and_dynamic"
                if in_environment and in_dynamic
                else "environment"
                if in_environment
                else "dynamic"
                if in_dynamic
                else "none"
            )
            effective = in_environment or in_dynamic
            if operation == "add":
                safe_message = "动态访问名单已加入并立即生效。"
            elif effective:
                safe_message = "动态副本已移除；环境固定项仍然生效。"
            else:
                safe_message = "动态访问名单条目已移除。"
            return OwnerConsoleAccessActionResult(
                generated_at=utc_now(),
                list_name=list_name,
                operation=operation,
                item=normalized,
                changed=True,
                effective=effective,
                revision=updated.revision,
                source_after=source_after,
                code=f"access_item_{'added' if operation == 'add' else 'removed'}",
                safe_message=safe_message,
            )
