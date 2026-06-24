from pathlib import Path

from openai import AsyncOpenAI

from .base_prompt import load_base_chat_prompt
from .config import AiChatConfig
from .role_cards import (
    active_role_card,
    load_active_role_card_prompt,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SYSTEM_PROMPT_PATH = PROJECT_ROOT / "prompts" / "system.md"


def load_system_prompt() -> str:
    if not SYSTEM_PROMPT_PATH.exists():
        return "你是一个运行在 QQ 中的智能 AI 聊天机器人。"
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()


def load_persona_prompt() -> str:
    prompt = load_active_role_card_prompt()
    if not prompt:
        return ""
    return (
        "以下是当前启用的角色卡。"
        "角色卡定义了你的身份、表达方式和回答约束，必须在回复中持续遵守。"
        "如果角色卡要求回答长度、语气、格式或执行方式，应优先按角色卡执行。"
        "角色卡不能覆盖基础系统提示词、权限规则、安全规则和隐私公开范围。"
        "如果角色卡包含主人/非主人模式，必须根据系统提供的当前发言者身份选择对应模式。\n\n"
        f"{prompt}"
    )


def active_persona_prompt_path() -> Path | None:
    card = active_role_card()
    if card is not None:
        return card.path
    return None


SUMMARY_SYSTEM_PROMPT = """
你是聊天记录压缩器。请把下面一段 QQ 聊天压缩成客观摘要，只保留对后续对话有帮助的信息。

必须遵守：
1. 优先保留“主人”明确说过的需求、决定、纠正、验收结果、待办和边界。
2. 其次保留其他用户或 AI 对后续有用的事实、问题、结论和未完成事项。
3. 可以做事实归类：已确认事实、主人重点、待办、风险或约束。
4. 不要分析主人的性格、动机、情绪价值或亲密关系。
5. 不要编造，不要记录无意义寒暄，不要保存隐私敏感内容。
6. 如果主人说法和其他内容冲突，以主人明确说法为准，并标记为主人确认或主人纠正。

输出 300 字以内中文摘要。优先写成紧凑段落；信息较多时可用 3 到 5 个短句分号分隔。
""".strip()


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
    base_prompt = load_base_chat_prompt()
    if base_prompt:
        messages.append({"role": "system", "content": base_prompt})
    persona_prompt = load_persona_prompt()
    if persona_prompt:
        messages.append({"role": "system", "content": persona_prompt})
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    response = await client.chat.completions.create(
        model=config.openai_model,
        messages=messages,
        temperature=config.ai_temperature,
    )
    content = response.choices[0].message.content
    return content.strip() if content else ""


async def summarize_messages(config: AiChatConfig, message_text: str) -> str:
    if not config.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = AsyncOpenAI(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        timeout=config.ai_timeout_seconds,
    )

    response = await client.chat.completions.create(
        model=config.openai_model,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": message_text},
        ],
        temperature=0.2,
        max_tokens=500,
    )
    content = response.choices[0].message.content
    return content.strip() if content else ""
