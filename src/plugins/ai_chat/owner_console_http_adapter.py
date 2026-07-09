from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, TypeAlias

from .access_store import AccessStore, merged_access
from .config import AiChatConfig, load_config
from .owner_console_read_models import OwnerConsoleContext
from .owner_console_read_runtime import OwnerConsoleReadRuntime


ConfigProvider: TypeAlias = Callable[[], AiChatConfig]


@dataclass(frozen=True)
class OwnerConsoleHttpAdapterError(Exception):
    code: str
    message: str
    status_code: int
    details: dict[str, object] = field(default_factory=dict)


def build_owner_console_context_from_config(
    config: AiChatConfig,
) -> OwnerConsoleContext:
    owner_id = config.bot_owner_qq.strip()
    if not owner_id:
        raise OwnerConsoleHttpAdapterError(
            code="forbidden",
            message="owner is not configured",
            status_code=403,
            details={"config_key": "BOT_OWNER_QQ"},
        )
    return OwnerConsoleContext(
        session_key=f"private:{owner_id}",
        user_id=owner_id,
    )


def build_owner_console_access_from_config(config: AiChatConfig) -> AccessStore:
    return merged_access(
        config.private_whitelist,
        config.group_whitelist,
        config.user_blacklist,
    )


def create_owner_console_http_read_runtime(
    *,
    config_provider: ConfigProvider = load_config,
) -> OwnerConsoleReadRuntime:
    return OwnerConsoleReadRuntime(
        config_provider=config_provider,
        access_provider=lambda: build_owner_console_access_from_config(
            config_provider()
        ),
    )


def parse_owner_console_positive_int(
    value: str | None,
    *,
    default: int,
    field_name: str,
) -> int:
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise OwnerConsoleHttpAdapterError(
            code="bad_request",
            message=f"{field_name} must be an integer",
            status_code=400,
            details={"field": field_name, "value": value},
        ) from exc
    if parsed < 1:
        raise OwnerConsoleHttpAdapterError(
            code="bad_request",
            message=f"{field_name} must be greater than or equal to 1",
            status_code=400,
            details={"field": field_name, "value": value},
        )
    return parsed
