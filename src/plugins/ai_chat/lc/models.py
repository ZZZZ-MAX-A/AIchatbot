from __future__ import annotations

from typing import Any

from ..config import AiChatConfig
from ..completion_routes import resolve_chat_completion_route


def _chat_openai(**kwargs: Any) -> Any:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError(
            "langchain-openai is not installed. Run the project setup after updating dependencies."
        ) from exc
    return ChatOpenAI(**kwargs)


def build_main_llm(config: AiChatConfig) -> Any:
    return _chat_openai(
        api_key=config.main_llm_api_key,
        base_url=config.main_llm_base_url,
        model=config.main_llm_model,
        timeout=config.main_llm_timeout_seconds,
    )


def build_external_research_llm(config: AiChatConfig) -> Any:
    return _chat_openai(
        api_key=config.main_llm_api_key,
        base_url=config.main_llm_base_url,
        model=config.main_llm_model,
        timeout=config.main_llm_timeout_seconds,
        max_retries=0,
    )


def build_chat_llm(
    config: AiChatConfig,
    role_card_key: str = "",
    *,
    completion_route: str = "auto",
) -> Any:
    route = resolve_chat_completion_route(
        config, role_card_key, completion_route=completion_route
    )
    route.require_configured()
    if route.provider != "openai":
        raise RuntimeError(
            "build_chat_llm supports OpenAI-compatible routes only; "
            "use ask_llm for the native Ollama route"
        )
    return _chat_openai(
        api_key=route.api_key,
        base_url=route.base_url,
        model=route.model,
        timeout=route.timeout_seconds,
    )
