"""Pure model-route selection shared by chat calls and read-only diagnostics.

ChatGraph selects execution flow; it never selects a model or credentials.
This module imports no clients, prompts, QQ adapters, or database helpers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from .config import AiChatConfig


@dataclass(frozen=True)
class ChatCompletionRoute:
    api_key: str = field(repr=False)
    base_url: str
    model: str
    timeout_seconds: int
    source: str
    provider: str = "openai"
    num_ctx: int = 0
    max_tokens: int = 0
    keep_alive_seconds: int = 0

    @property
    def configuration_errors(self) -> tuple[str, ...]:
        """Return configuration names only, never credentials or their values."""
        prefix = {"legacy": "AIKE", "persona": "PERSONA", "summary": "SUMMARY"}[self.source]
        errors = []
        if self.provider not in {"openai", "ollama"}:
            errors.append(f"{prefix}_LLM_PROVIDER")
        if self.provider == "openai" and not self.api_key.strip():
            errors.append(f"{prefix}_LLM_API_KEY")
        if not self.base_url.strip():
            errors.append(f"{prefix}_LLM_BASE_URL")
        if not self.model.strip():
            errors.append(f"{prefix}_LLM_MODEL")
        if self.timeout_seconds <= 0:
            errors.append(f"{prefix}_LLM_TIMEOUT_SECONDS")
        if self.provider == "ollama":
            if self.num_ctx <= 0:
                errors.append(f"{prefix}_LLM_NUM_CTX")
            if self.max_tokens <= 0:
                errors.append(f"{prefix}_LLM_MAX_TOKENS")
            if self.keep_alive_seconds < 0:
                errors.append(f"{prefix}_LLM_KEEP_ALIVE_SECONDS")
        return tuple(errors)

    @property
    def configured(self) -> bool:
        return not self.configuration_errors

    def require_configured(self) -> None:
        if self.configuration_errors:
            raise RuntimeError(
                "LLM route is incomplete: " + ", ".join(self.configuration_errors)
            )


def resolve_chat_completion_route(
    config: AiChatConfig,
    role_card_key: str = "",
    *,
    completion_route: str = "auto",
) -> ChatCompletionRoute:
    """Select an explicitly allowlisted persona endpoint or the legacy route.

    The alternate route is deliberately limited to normal persona replies.
    Summary and memory-compression calls resolve through
    ``resolve_summary_completion_route`` instead, so Aike/legacy summaries
    can use their own credentials without changing ordinary chat routing.
    """

    if completion_route not in {"auto", "legacy"}:
        raise ValueError("completion_route must be 'auto' or 'legacy'")
    legacy_route = ChatCompletionRoute(
        api_key=getattr(config, "aike_llm_api_key", ""),
        base_url=getattr(config, "aike_llm_base_url", ""),
        model=getattr(config, "aike_llm_model", ""),
        timeout_seconds=getattr(config, "aike_llm_timeout_seconds", 0),
        source="legacy",
    )
    normalized_role_card_key = role_card_key.strip()
    legacy_card = getattr(getattr(config, "persona_routing", None), "legacy_role_card_key", "")
    if not (
        completion_route == "auto"
        and getattr(config, "enable_persona_llm_routing", False)
        and normalized_role_card_key
        and normalized_role_card_key != legacy_card
        and normalized_role_card_key
        in getattr(config, "persona_llm_role_card_keys", frozenset())
    ):
        return legacy_route

    route = ChatCompletionRoute(
        api_key=getattr(config, "persona_llm_api_key", "").strip(),
        base_url=getattr(config, "persona_llm_base_url", "").strip(),
        model=getattr(config, "persona_llm_model", "").strip(),
        timeout_seconds=int(getattr(config, "persona_llm_timeout_seconds", 0)),
        source="persona",
        provider=getattr(config, "persona_llm_provider", "openai").strip().lower(),
        num_ctx=int(getattr(config, "persona_llm_num_ctx", 4096)),
        max_tokens=int(getattr(config, "persona_llm_max_tokens", 640)),
        keep_alive_seconds=int(getattr(config, "persona_llm_keep_alive_seconds", 0)),
    )
    if not route.configured:
        raise RuntimeError(
            "persona LLM route is enabled but incomplete: "
            + ", ".join(route.configuration_errors)
        )
    return route



def uses_deepseek_chat_api(route: ChatCompletionRoute) -> bool:
    """Scope vendor request fields to DeepSeek, including compatible proxies."""
    if route.provider != "openai":
        return False
    if route.model.strip().lower().startswith("deepseek"):
        return True
    try:
        return urlparse(route.base_url).hostname == "api.deepseek.com"
    except ValueError:
        return False


def resolve_chat_reasoning_effort(
    config: AiChatConfig,
    route: ChatCompletionRoute,
    *,
    override: str | None = None,
) -> str | None:
    """Keep Aike chat effort separate from planners, summaries and scene overrides."""
    if override is not None:
        effort = override
    elif route.source == "legacy" and uses_deepseek_chat_api(route):
        effort = getattr(config, "aike_llm_reasoning_effort", None)
    else:
        effort = None
    if effort not in {None, "low", "high", "max"}:
        raise ValueError("reasoning_effort must be low, high, max, or None")
    return effort


def resolve_summary_completion_route(
    config: AiChatConfig,
    role_card_key: str = "",
) -> ChatCompletionRoute:
    """Return the one shared summary route for every persona and chat mode.

    ``role_card_key`` is intentionally accepted for call-site compatibility,
    but it never participates in endpoint selection. Persona-specific chat
    routing and summary routing are separate concerns.
    """
    return ChatCompletionRoute(
        api_key=getattr(config, "summary_llm_api_key", "").strip(),
        base_url=getattr(
            config,
            "summary_llm_base_url",
            "https://api.deepseek.com",
        ).strip(),
        model=getattr(config, "summary_llm_model", "deepseek-v4-flash").strip(),
        timeout_seconds=int(
            getattr(
                config,
                "summary_llm_timeout_seconds",
                60,
            )
        ),
        source="summary",
    )
