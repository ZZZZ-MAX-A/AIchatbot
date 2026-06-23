import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return float(value)


def _csv_env(name: str) -> frozenset[str]:
    value = os.getenv(name, "")
    items = [item.strip() for item in value.split(",")]
    return frozenset(item for item in items if item)


@dataclass(frozen=True)
class AiChatConfig:
    bot_name: str
    bot_aliases: frozenset[str]
    bot_owner_qq: str
    bot_owner_public_name: str
    openai_api_key: str
    openai_base_url: str
    openai_model: str
    ai_temperature: float
    ai_timeout_seconds: int
    enable_private_chat: bool
    enable_group_chat: bool
    max_context_messages: int
    enable_memory_compression: bool
    max_stored_messages_per_session: int
    summary_keep_recent_messages: int
    summary_batch_messages: int
    max_session_summaries_in_context: int
    max_long_term_memories_in_context: int
    private_whitelist: frozenset[str]
    allow_unknown_private_chat: bool
    private_trial_messages: int
    private_rate_limit_seconds: int
    max_private_message_length: int
    group_whitelist: frozenset[str]
    group_rate_limit_seconds: int
    max_group_message_length: int
    enable_group_auto_reply: bool
    group_auto_reply_threshold: int
    group_auto_reply_cooldown_seconds: int
    group_auto_reply_owner_cooldown_seconds: int
    group_auto_reply_user_cooldown_seconds: int
    user_blacklist: frozenset[str]


def load_config() -> AiChatConfig:
    return AiChatConfig(
        bot_name=os.getenv("BOT_NAME", "AI Assistant"),
        bot_aliases=_csv_env("BOT_ALIASES"),
        bot_owner_qq=os.getenv("BOT_OWNER_QQ", "").strip(),
        bot_owner_public_name=os.getenv("BOT_OWNER_PUBLIC_NAME", "").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com"),
        openai_model=os.getenv("OPENAI_MODEL", "deepseek-v4-flash"),
        ai_temperature=_float_env("AI_TEMPERATURE", 0.7),
        ai_timeout_seconds=_int_env("AI_TIMEOUT_SECONDS", 60),
        enable_private_chat=_bool_env("ENABLE_PRIVATE_CHAT", True),
        enable_group_chat=_bool_env("ENABLE_GROUP_CHAT", True),
        max_context_messages=_int_env("MAX_CONTEXT_MESSAGES", 20),
        enable_memory_compression=_bool_env("ENABLE_MEMORY_COMPRESSION", True),
        max_stored_messages_per_session=_int_env("MAX_STORED_MESSAGES_PER_SESSION", 200),
        summary_keep_recent_messages=_int_env("SUMMARY_KEEP_RECENT_MESSAGES", 80),
        summary_batch_messages=_int_env("SUMMARY_BATCH_MESSAGES", 120),
        max_session_summaries_in_context=_int_env("MAX_SESSION_SUMMARIES_IN_CONTEXT", 3),
        max_long_term_memories_in_context=_int_env("MAX_LONG_TERM_MEMORIES_IN_CONTEXT", 8),
        private_whitelist=_csv_env("PRIVATE_WHITELIST"),
        allow_unknown_private_chat=_bool_env("ALLOW_UNKNOWN_PRIVATE_CHAT", False),
        private_trial_messages=_int_env("PRIVATE_TRIAL_MESSAGES", 3),
        private_rate_limit_seconds=_int_env("PRIVATE_RATE_LIMIT_SECONDS", 10),
        max_private_message_length=_int_env("MAX_PRIVATE_MESSAGE_LENGTH", 150),
        group_whitelist=_csv_env("GROUP_WHITELIST"),
        group_rate_limit_seconds=_int_env("GROUP_RATE_LIMIT_SECONDS", 5),
        max_group_message_length=_int_env("MAX_GROUP_MESSAGE_LENGTH", 300),
        enable_group_auto_reply=_bool_env("ENABLE_GROUP_AUTO_REPLY", False),
        group_auto_reply_threshold=_int_env("GROUP_AUTO_REPLY_THRESHOLD", 50),
        group_auto_reply_cooldown_seconds=_int_env("GROUP_AUTO_REPLY_COOLDOWN_SECONDS", 60),
        group_auto_reply_owner_cooldown_seconds=_int_env("GROUP_AUTO_REPLY_OWNER_COOLDOWN_SECONDS", 30),
        group_auto_reply_user_cooldown_seconds=_int_env("GROUP_AUTO_REPLY_USER_COOLDOWN_SECONDS", 120),
        user_blacklist=_csv_env("USER_BLACKLIST"),
    )
