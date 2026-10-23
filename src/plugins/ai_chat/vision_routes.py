"""Pure vision route selection shared by runtime and account settings."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from .config import AiChatConfig


class VisionError(RuntimeError):
    pass


@dataclass(frozen=True)
class VisionProviderRoute:
    provider: str
    api_key: str = field(default="", repr=False)
    base_url: str = ""
    model: str = ""
    timeout_seconds: int = 0
    max_tokens: int = 400
    reasoning_effort: str | None = None


def persona_vision_provider(model: str, base_url: str = "") -> str:
    if model.strip().lower().startswith("deepseek"):
        return "persona_deepseek"
    try:
        if urlsplit(base_url).hostname == "api.deepseek.com":
            return "persona_deepseek"
    except ValueError:
        pass
    return "persona_grok"


def persona_vision_api_key(config: AiChatConfig) -> str:
    key = getattr(config, "persona_vision_api_key", "").strip()
    provider = persona_vision_provider(
        getattr(config, "persona_vision_model", ""),
        getattr(config, "persona_vision_base_url", ""),
    )
    # DeepSeek inheritance is resolved by the config loader. Never substitute
    # the unrelated persona-chat credential after an explicit blank value.
    if provider == "persona_deepseek":
        return key
    return key or getattr(config, "persona_llm_api_key", "").strip()


def resolve_vision_provider_route(
    config: AiChatConfig,
    role_card_key: str = "",
) -> VisionProviderRoute:
    normalized_role_card_key = role_card_key.strip()
    legacy_card = getattr(getattr(config, "persona_routing", None), "legacy_role_card_key", "")
    if not (
        getattr(config, "enable_persona_vision_routing", False)
        and normalized_role_card_key
        and normalized_role_card_key != legacy_card
        and normalized_role_card_key
        in getattr(config, "persona_vision_role_card_keys", frozenset())
    ):
        return VisionProviderRoute(provider="aliyun_bailian")

    model = getattr(config, "persona_vision_model", "").strip()
    base_url = getattr(config, "persona_vision_base_url", "").strip()
    provider = persona_vision_provider(model, base_url)
    deepseek = provider == "persona_deepseek"
    values = {
        "PERSONA_VISION_API_KEY": persona_vision_api_key(config),
        "PERSONA_VISION_BASE_URL": (
            base_url
            or ("" if deepseek else getattr(config, "persona_llm_base_url", "").strip())
        ),
        "PERSONA_VISION_MODEL": model,
    }
    missing = [name for name, value in values.items() if not value]
    timeout_seconds = int(getattr(config, "persona_vision_timeout_seconds", 0))
    if timeout_seconds <= 0:
        missing.append("PERSONA_VISION_TIMEOUT_SECONDS")
    max_tokens = int(getattr(config, "persona_vision_max_tokens", 4096 if deepseek else 400))
    if max_tokens <= 0:
        missing.append("PERSONA_VISION_MAX_TOKENS")
    effort = getattr(config, "persona_vision_reasoning_effort", "high") if deepseek else None
    if deepseek and effort not in {"low", "high", "max"}:
        missing.append("PERSONA_VISION_REASONING_EFFORT")
    if missing:
        raise VisionError(
            "persona vision route is enabled but incomplete: "
            + ", ".join(missing)
        )
    return VisionProviderRoute(
        provider=provider,
        api_key=values["PERSONA_VISION_API_KEY"],
        base_url=values["PERSONA_VISION_BASE_URL"],
        model=values["PERSONA_VISION_MODEL"],
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        reasoning_effort=effort,
    )


def resolve_private_image_wait_seconds(
    config: AiChatConfig,
    role_card_key: str = "",
) -> int:
    legacy_wait_seconds = max(
        int(getattr(config, "vision_private_image_wait_seconds", 0)),
        0,
    )
    normalized_role_card_key = role_card_key.strip()
    if not (
        normalized_role_card_key
        and normalized_role_card_key
        in getattr(config, "persona_vision_role_card_keys", frozenset())
    ):
        return legacy_wait_seconds
    persona_wait_seconds = int(
        getattr(config, "persona_vision_private_image_wait_seconds", -1)
    )
    if persona_wait_seconds < 0:
        return legacy_wait_seconds
    return persona_wait_seconds
