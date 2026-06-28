from __future__ import annotations

from typing import Any

from ..config import AiChatConfig


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


def build_chat_llm(config: AiChatConfig) -> Any:
    return _chat_openai(
        api_key=config.chat_llm_api_key,
        base_url=config.chat_llm_base_url,
        model=config.chat_llm_model,
        timeout=config.chat_llm_timeout_seconds,
    )

