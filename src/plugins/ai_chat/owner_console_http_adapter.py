from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Callable, TypeAlias

from .access_store import AccessStore, merged_access
from .config import AiChatConfig, load_config
from .gap_scene_summaries import gap_scene_summary_stats
from .manual_memory import manual_memory_stats
from .memory import memory_stats
from .owner_console_read_models import OwnerConsoleContext
from .owner_console_read_runtime import OwnerConsoleReadRuntime
from .rag.documents import rag_document_stats
from .role_cards import active_role_card, list_role_cards


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
        role_cards_provider=list_role_cards,
        active_role_card_key_provider=_active_owner_console_role_card_key,
        memory_stats_provider=memory_stats,
        manual_memory_stats_provider=manual_memory_stats,
        gap_scene_stats_provider=gap_scene_summary_stats,
        rag_document_stats_provider=rag_document_stats,
    )


def _active_owner_console_role_card_key() -> str:
    card = active_role_card()
    return card.key if card is not None else ""


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


def parse_owner_console_required_positive_int(
    value: str | None,
    *,
    field_name: str,
) -> int:
    if value is None or not value.strip():
        raise OwnerConsoleHttpAdapterError(
            code="bad_request",
            message=f"{field_name} is required",
            status_code=400,
            details={"field": field_name, "value": value or ""},
        )
    return parse_owner_console_positive_int(
        value,
        default=1,
        field_name=field_name,
    )


def parse_owner_console_optional_status(
    value: str | None,
    *,
    allowed_statuses: Collection[str],
    field_name: str = "status",
) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip().lower()
    if normalized not in allowed_statuses:
        raise OwnerConsoleHttpAdapterError(
            code="bad_request",
            message=f"{field_name} is not supported",
            status_code=400,
            details={
                "field": field_name,
                "value": value,
                "allowed": sorted(allowed_statuses),
            },
        )
    return normalized
