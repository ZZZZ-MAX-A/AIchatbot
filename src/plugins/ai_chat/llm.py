from pathlib import Path

from openai import AsyncOpenAI

from .config import AiChatConfig


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SYSTEM_PROMPT_PATH = PROJECT_ROOT / "prompts" / "system.md"


def load_system_prompt() -> str:
    if not SYSTEM_PROMPT_PATH.exists():
        return "你是一个运行在 QQ 中的智能 AI 聊天机器人。"
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()


async def ask_llm(
    config: AiChatConfig,
    history: list[dict[str, str]],
    user_text: str,
) -> str:
    if not config.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = AsyncOpenAI(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        timeout=config.ai_timeout_seconds,
    )

    messages = [{"role": "system", "content": load_system_prompt()}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    response = await client.chat.completions.create(
        model=config.openai_model,
        messages=messages,
        temperature=config.ai_temperature,
    )
    content = response.choices[0].message.content
    return content.strip() if content else ""
