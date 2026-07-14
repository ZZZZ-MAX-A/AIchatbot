import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from .local_time import DEFAULT_BOT_TIMEZONE, timezone_for_name


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


def _security_int_env(name: str, default: int) -> int:
    """Return an invalid fail-closed sentinel instead of breaking startup."""
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return 0


def _security_float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return 0.0


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return float(value)


def _csv_env(name: str) -> frozenset[str]:
    value = os.getenv(name, "")
    items = [item.strip() for item in value.split(",")]
    return frozenset(item for item in items if item)


def _timezone_env(name: str) -> str:
    value = os.getenv(name, DEFAULT_BOT_TIMEZONE).strip() or DEFAULT_BOT_TIMEZONE
    timezone_for_name(value)
    return value


@dataclass(frozen=True)
class AiChatConfig:
    bot_name: str
    bot_aliases: frozenset[str]
    bot_owner_qq: str
    bot_owner_public_name: str
    bot_timezone: str
    openai_api_key: str = field(repr=False)
    openai_base_url: str
    openai_model: str
    ai_temperature: float
    ai_timeout_seconds: int
    enable_main_agent: bool
    main_agent_use_llm: bool
    main_agent_owner_only: bool
    main_agent_allow_group: bool
    main_agent_max_steps: int
    main_agent_require_approval_for_writes: bool
    enable_agent_web: bool
    tavily_api_key: str = field(repr=False)
    tavily_timeout_seconds: int
    enable_agent_local_write: bool
    enable_agent_external_write: bool
    enable_agent_shell: bool
    main_llm_api_key: str = field(repr=False)
    main_llm_base_url: str
    main_llm_model: str
    main_llm_timeout_seconds: int
    chat_llm_api_key: str = field(repr=False)
    chat_llm_base_url: str
    chat_llm_model: str
    chat_llm_timeout_seconds: int
    enable_chat_graph_runtime: bool
    enable_vision: bool
    vision_ollama_base_url: str
    vision_model: str
    vision_timeout_seconds: int
    vision_num_ctx: int
    vision_max_images: int
    vision_max_image_bytes: int
    vision_image_cache_ttl_seconds: int
    vision_private_image_wait_seconds: int
    enable_local_stickers: bool
    local_sticker_root: Path = field(repr=False)
    local_sticker_max_file_bytes: int
    local_sticker_max_dynamic_file_bytes: int
    local_sticker_min_dimension: int
    local_sticker_max_dimension: int
    local_sticker_max_pixels: int
    local_sticker_max_animation_frames: int
    local_sticker_max_animation_duration_ms: int
    local_sticker_min_frame_duration_ms: int
    local_sticker_max_animation_decoded_pixels: int
    local_sticker_preview_cooldown_seconds: int
    enable_chat_sticker_intent_shadow: bool
    enable_chat_sticker_attachments: bool
    enable_remote_sticker_classifier: bool
    sticker_classifier_api_key: str = field(repr=False)
    sticker_classifier_base_url: str
    sticker_classifier_model: str
    sticker_classifier_timeout_seconds: int
    sticker_classifier_max_input_chars: int
    chat_sticker_owner_private_only: bool
    chat_sticker_cooldown_seconds: int
    chat_sticker_min_messages_between: int
    chat_sticker_max_per_hour: int
    chat_sticker_max_per_reply: int
    chat_sticker_min_intent_confidence: float
    enable_private_chat: bool
    enable_group_chat: bool
    max_context_messages: int
    enable_memory_compression: bool
    max_stored_messages_per_session: int
    summary_keep_recent_messages: int
    summary_batch_messages: int
    summary_min_source_messages: int
    max_session_summaries_in_context: int
    enable_gap_scene_summaries: bool
    gap_scene_summary_1_threshold: int
    gap_scene_summary_2_threshold: int
    max_gap_scene_summaries_in_context: int
    enable_long_term_memory_context: bool
    max_long_term_memories_in_context: int
    rule_reminder_interval_messages: int
    enable_memory_rag: bool
    enable_project_doc_rag: bool
    memory_rag_embedding_provider: str
    memory_rag_embedding_model: str
    memory_rag_embedding_base_url: str
    memory_rag_embedding_dimension: int
    memory_rag_embedding_timeout_seconds: int
    memory_rag_top_k: int
    memory_rag_min_score: float
    memory_rag_max_context_chars: int
    project_doc_rag_top_k: int
    project_doc_rag_min_score: float
    project_doc_rag_max_context_chars: int
    memory_rag_include_manual_facts: bool
    memory_rag_include_manual_preferences: bool
    memory_rag_include_session_summaries: bool
    memory_rag_include_short_messages: bool
    memory_rag_include_gap_scene_summaries: bool
    memory_rag_owner_only_debug: bool
    memory_rag_inject_in_chat: bool
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
    enable_owner_notifications: bool
    owner_notification_max_length: int
    owner_notification_global_cooldown_seconds: int
    owner_notification_group_cooldown_seconds: int
    owner_notification_user_cooldown_seconds: int
    enable_tts: bool
    tts_service_url: str
    tts_voice: str
    tts_emotion: str
    tts_timeout_seconds: int
    tts_max_chars: int
    tts_max_total_seconds: int
    tts_cooldown_seconds: int
    tts_auto_start: bool
    tts_startup_wait_seconds: int
    user_blacklist: frozenset[str]


def load_config() -> AiChatConfig:
    return AiChatConfig(
        bot_name=os.getenv("BOT_NAME", "AI Assistant"),
        bot_aliases=_csv_env("BOT_ALIASES"),
        bot_owner_qq=os.getenv("BOT_OWNER_QQ", "").strip(),
        bot_owner_public_name=os.getenv("BOT_OWNER_PUBLIC_NAME", "").strip(),
        bot_timezone=_timezone_env("BOT_TIMEZONE"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com"),
        openai_model=os.getenv("OPENAI_MODEL", "deepseek-v4-flash"),
        ai_temperature=_float_env("AI_TEMPERATURE", 0.7),
        ai_timeout_seconds=_int_env("AI_TIMEOUT_SECONDS", 60),
        enable_main_agent=_bool_env("ENABLE_MAIN_AGENT", False),
        main_agent_use_llm=_bool_env("MAIN_AGENT_USE_LLM", False),
        main_agent_owner_only=_bool_env("MAIN_AGENT_OWNER_ONLY", True),
        main_agent_allow_group=_bool_env("MAIN_AGENT_ALLOW_GROUP", False),
        main_agent_max_steps=_int_env("MAIN_AGENT_MAX_STEPS", 5),
        main_agent_require_approval_for_writes=_bool_env("MAIN_AGENT_REQUIRE_APPROVAL_FOR_WRITES", True),
        enable_agent_web=_bool_env("ENABLE_AGENT_WEB", False),
        tavily_api_key=os.getenv("TAVILY_API_KEY", "").strip(),
        tavily_timeout_seconds=_security_int_env("TAVILY_TIMEOUT_SECONDS", 10),
        enable_agent_local_write=_bool_env("ENABLE_AGENT_LOCAL_WRITE", False),
        enable_agent_external_write=_bool_env("ENABLE_AGENT_EXTERNAL_WRITE", False),
        enable_agent_shell=_bool_env("ENABLE_AGENT_SHELL", False),
        main_llm_api_key=os.getenv("MAIN_LLM_API_KEY", ""),
        main_llm_base_url=os.getenv("MAIN_LLM_BASE_URL", "https://api.openai.com/v1"),
        main_llm_model=os.getenv("MAIN_LLM_MODEL", "gpt-4.1-mini"),
        main_llm_timeout_seconds=_int_env("MAIN_LLM_TIMEOUT_SECONDS", 60),
        chat_llm_api_key=os.getenv("CHAT_LLM_API_KEY", os.getenv("OPENAI_API_KEY", "")),
        chat_llm_base_url=os.getenv("CHAT_LLM_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")),
        chat_llm_model=os.getenv("CHAT_LLM_MODEL", os.getenv("OPENAI_MODEL", "deepseek-v4-flash")),
        chat_llm_timeout_seconds=_int_env("CHAT_LLM_TIMEOUT_SECONDS", _int_env("AI_TIMEOUT_SECONDS", 60)),
        enable_chat_graph_runtime=_bool_env("ENABLE_CHAT_GRAPH_RUNTIME", False),
        enable_vision=_bool_env("ENABLE_VISION", True),
        vision_ollama_base_url=os.getenv("VISION_OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        vision_model=os.getenv("VISION_MODEL", "qwen2.5vl:3b"),
        vision_timeout_seconds=_int_env("VISION_TIMEOUT_SECONDS", 180),
        vision_num_ctx=_int_env("VISION_NUM_CTX", 16384),
        vision_max_images=_int_env("VISION_MAX_IMAGES", 1),
        vision_max_image_bytes=_int_env("VISION_MAX_IMAGE_BYTES", 5242880),
        vision_image_cache_ttl_seconds=_int_env("VISION_IMAGE_CACHE_TTL_SECONDS", 120),
        vision_private_image_wait_seconds=_int_env("VISION_PRIVATE_IMAGE_WAIT_SECONDS", 5),
        enable_local_stickers=_bool_env("ENABLE_LOCAL_STICKERS", False),
        local_sticker_root=PROJECT_ROOT / "data" / "stickers",
        local_sticker_max_file_bytes=_security_int_env(
            "LOCAL_STICKER_MAX_FILE_BYTES",
            2_097_152,
        ),
        local_sticker_max_dynamic_file_bytes=_security_int_env(
            "LOCAL_STICKER_MAX_DYNAMIC_FILE_BYTES",
            5_242_880,
        ),
        local_sticker_min_dimension=_security_int_env(
            "LOCAL_STICKER_MIN_DIMENSION",
            32,
        ),
        local_sticker_max_dimension=_security_int_env(
            "LOCAL_STICKER_MAX_DIMENSION",
            2048,
        ),
        local_sticker_max_pixels=_security_int_env(
            "LOCAL_STICKER_MAX_PIXELS",
            4_194_304,
        ),
        local_sticker_max_animation_frames=_security_int_env(
            "LOCAL_STICKER_MAX_ANIMATION_FRAMES",
            120,
        ),
        local_sticker_max_animation_duration_ms=_security_int_env(
            "LOCAL_STICKER_MAX_ANIMATION_DURATION_MS",
            10_000,
        ),
        local_sticker_min_frame_duration_ms=_security_int_env(
            "LOCAL_STICKER_MIN_FRAME_DURATION_MS",
            20,
        ),
        local_sticker_max_animation_decoded_pixels=_security_int_env(
            "LOCAL_STICKER_MAX_ANIMATION_DECODED_PIXELS",
            60_000_000,
        ),
        local_sticker_preview_cooldown_seconds=_security_int_env(
            "LOCAL_STICKER_PREVIEW_COOLDOWN_SECONDS",
            3,
        ),
        enable_chat_sticker_intent_shadow=_bool_env(
            "ENABLE_CHAT_STICKER_INTENT_SHADOW",
            False,
        ),
        enable_chat_sticker_attachments=_bool_env(
            "ENABLE_CHAT_STICKER_ATTACHMENTS",
            False,
        ),
        enable_remote_sticker_classifier=_bool_env(
            "ENABLE_REMOTE_STICKER_CLASSIFIER",
            False,
        ),
        sticker_classifier_api_key=os.getenv(
            "STICKER_CLASSIFIER_API_KEY",
            "",
        ).strip(),
        sticker_classifier_base_url=os.getenv(
            "STICKER_CLASSIFIER_BASE_URL",
            "",
        ).strip(),
        sticker_classifier_model=os.getenv(
            "STICKER_CLASSIFIER_MODEL",
            "",
        ).strip(),
        sticker_classifier_timeout_seconds=_security_int_env(
            "STICKER_CLASSIFIER_TIMEOUT_SECONDS",
            8,
        ),
        sticker_classifier_max_input_chars=_security_int_env(
            "STICKER_CLASSIFIER_MAX_INPUT_CHARS",
            2400,
        ),
        chat_sticker_owner_private_only=_bool_env(
            "CHAT_STICKER_OWNER_PRIVATE_ONLY",
            True,
        ),
        chat_sticker_cooldown_seconds=_security_int_env(
            "CHAT_STICKER_COOLDOWN_SECONDS",
            120,
        ),
        chat_sticker_min_messages_between=_security_int_env(
            "CHAT_STICKER_MIN_MESSAGES_BETWEEN",
            4,
        ),
        chat_sticker_max_per_hour=_security_int_env(
            "CHAT_STICKER_MAX_PER_HOUR",
            6,
        ),
        chat_sticker_max_per_reply=_security_int_env(
            "CHAT_STICKER_MAX_PER_REPLY",
            1,
        ),
        chat_sticker_min_intent_confidence=_security_float_env(
            "CHAT_STICKER_MIN_INTENT_CONFIDENCE",
            0.82,
        ),
        enable_private_chat=_bool_env("ENABLE_PRIVATE_CHAT", True),
        enable_group_chat=_bool_env("ENABLE_GROUP_CHAT", True),
        max_context_messages=_int_env("MAX_CONTEXT_MESSAGES", 40),
        enable_memory_compression=_bool_env("ENABLE_MEMORY_COMPRESSION", True),
        max_stored_messages_per_session=_int_env("MAX_STORED_MESSAGES_PER_SESSION", 120),
        summary_keep_recent_messages=_int_env("SUMMARY_KEEP_RECENT_MESSAGES", 40),
        summary_batch_messages=_int_env("SUMMARY_BATCH_MESSAGES", 80),
        summary_min_source_messages=_int_env("SUMMARY_MIN_SOURCE_MESSAGES", 40),
        max_session_summaries_in_context=_int_env("MAX_SESSION_SUMMARIES_IN_CONTEXT", 3),
        enable_gap_scene_summaries=_bool_env("ENABLE_GAP_SCENE_SUMMARIES", True),
        gap_scene_summary_1_threshold=_int_env("GAP_SCENE_SUMMARY_1_THRESHOLD", 40),
        gap_scene_summary_2_threshold=_int_env("GAP_SCENE_SUMMARY_2_THRESHOLD", 80),
        max_gap_scene_summaries_in_context=_int_env("MAX_GAP_SCENE_SUMMARIES_IN_CONTEXT", 2),
        enable_long_term_memory_context=_bool_env("ENABLE_LONG_TERM_MEMORY_CONTEXT", True),
        max_long_term_memories_in_context=_int_env("MAX_LONG_TERM_MEMORIES_IN_CONTEXT", 8),
        rule_reminder_interval_messages=_int_env("RULE_REMINDER_INTERVAL_MESSAGES", 40),
        enable_memory_rag=_bool_env("ENABLE_MEMORY_RAG", False),
        enable_project_doc_rag=_bool_env("ENABLE_PROJECT_DOC_RAG", False),
        memory_rag_embedding_provider=os.getenv("MEMORY_RAG_EMBEDDING_PROVIDER", "ollama"),
        memory_rag_embedding_model=os.getenv("MEMORY_RAG_EMBEDDING_MODEL", "bge-m3"),
        memory_rag_embedding_base_url=os.getenv("MEMORY_RAG_EMBEDDING_BASE_URL", "http://127.0.0.1:11434"),
        memory_rag_embedding_dimension=_int_env("MEMORY_RAG_EMBEDDING_DIMENSION", 1024),
        memory_rag_embedding_timeout_seconds=_int_env("MEMORY_RAG_EMBEDDING_TIMEOUT_SECONDS", 60),
        memory_rag_top_k=_int_env("MEMORY_RAG_TOP_K", 5),
        memory_rag_min_score=_float_env("MEMORY_RAG_MIN_SCORE", 0.55),
        memory_rag_max_context_chars=_int_env("MEMORY_RAG_MAX_CONTEXT_CHARS", 1600),
        project_doc_rag_top_k=_int_env("PROJECT_DOC_RAG_TOP_K", 4),
        project_doc_rag_min_score=_float_env("PROJECT_DOC_RAG_MIN_SCORE", 0.50),
        project_doc_rag_max_context_chars=_int_env("PROJECT_DOC_RAG_MAX_CONTEXT_CHARS", 2000),
        memory_rag_include_manual_facts=_bool_env("MEMORY_RAG_INCLUDE_MANUAL_FACTS", True),
        memory_rag_include_manual_preferences=_bool_env("MEMORY_RAG_INCLUDE_MANUAL_PREFERENCES", True),
        memory_rag_include_session_summaries=_bool_env("MEMORY_RAG_INCLUDE_SESSION_SUMMARIES", True),
        memory_rag_include_short_messages=_bool_env("MEMORY_RAG_INCLUDE_SHORT_MESSAGES", False),
        memory_rag_include_gap_scene_summaries=_bool_env("MEMORY_RAG_INCLUDE_GAP_SCENE_SUMMARIES", False),
        memory_rag_owner_only_debug=_bool_env("MEMORY_RAG_OWNER_ONLY_DEBUG", True),
        memory_rag_inject_in_chat=_bool_env("MEMORY_RAG_INJECT_IN_CHAT", False),
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
        enable_owner_notifications=_bool_env("ENABLE_OWNER_NOTIFICATIONS", True),
        owner_notification_max_length=_int_env("OWNER_NOTIFICATION_MAX_LENGTH", 50),
        owner_notification_global_cooldown_seconds=_int_env("OWNER_NOTIFICATION_GLOBAL_COOLDOWN_SECONDS", 60),
        owner_notification_group_cooldown_seconds=_int_env("OWNER_NOTIFICATION_GROUP_COOLDOWN_SECONDS", 120),
        owner_notification_user_cooldown_seconds=_int_env("OWNER_NOTIFICATION_USER_COOLDOWN_SECONDS", 300),
        enable_tts=_bool_env("ENABLE_TTS", False),
        tts_service_url=os.getenv("TTS_SERVICE_URL", "http://127.0.0.1:7861"),
        tts_voice=os.getenv("TTS_VOICE", "zh_kelin_raw_20260625_222137"),
        tts_emotion=os.getenv("TTS_EMOTION", "affection"),
        tts_timeout_seconds=_int_env("TTS_TIMEOUT_SECONDS", 180),
        tts_max_chars=_int_env("TTS_MAX_CHARS", 180),
        tts_max_total_seconds=_int_env("TTS_MAX_TOTAL_SECONDS", 60),
        tts_cooldown_seconds=_int_env("TTS_COOLDOWN_SECONDS", 20),
        tts_auto_start=_bool_env("TTS_AUTO_START", True),
        tts_startup_wait_seconds=_int_env("TTS_STARTUP_WAIT_SECONDS", 45),
        user_blacklist=_csv_env("USER_BLACKLIST"),
    )
