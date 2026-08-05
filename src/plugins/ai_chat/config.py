import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from .local_time import DEFAULT_BOT_TIMEZONE, timezone_for_name
from .persona_scope import PersonaRoutingSettings, build_persona_routing_settings


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


def _trusted_path_roots_env(name: str) -> tuple[Path, ...]:
    """Load an explicit semicolon-separated local path allowlist.

    Empty or invalid entries are ignored so local-file access fails closed.
    Environment placeholders such as ``%USERPROFILE%`` are supported without
    committing machine-specific absolute paths.
    """
    raw_value = os.getenv(name, "")
    roots: list[Path] = []
    for raw_item in raw_value.split(";"):
        item = os.path.expandvars(raw_item.strip())
        if not item or "%" in item:
            continue
        candidate = Path(item).expanduser()
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        try:
            resolved = candidate.resolve(strict=False)
        except OSError:
            continue
        if resolved not in roots:
            roots.append(resolved)
    return tuple(roots)


def _timezone_env(name: str) -> str:
    value = os.getenv(name, DEFAULT_BOT_TIMEZONE).strip() or DEFAULT_BOT_TIMEZONE
    timezone_for_name(value)
    return value


def _chat_weather_mode_env(name: str, default: str = "off") -> str:
    value = os.getenv(name, default).strip().lower() or default
    if value not in {"off", "shadow", "owner_explicit", "owner_auto"}:
        return "off"
    return value


@dataclass(frozen=True)
class AiChatConfig:
    bot_name: str
    bot_aliases: frozenset[str]
    bot_owner_qq: str
    bot_owner_public_name: str
    bot_timezone: str
    persona_routing: PersonaRoutingSettings
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
    enable_persona_llm_routing: bool
    persona_llm_role_card_keys: frozenset[str]
    persona_llm_api_key: str = field(repr=False)
    persona_llm_base_url: str
    persona_llm_model: str
    persona_llm_timeout_seconds: int
    enable_persona_vision_routing: bool
    persona_vision_role_card_keys: frozenset[str]
    persona_vision_model: str
    persona_vision_timeout_seconds: int
    persona_vision_private_image_wait_seconds: int
    enable_chat_weather: bool
    chat_weather_mode: str
    chat_weather_provider: str
    chat_weather_default_location: str
    chat_weather_default_latitude: float
    chat_weather_default_longitude: float
    chat_weather_timeout_seconds: float
    enable_chat_graph_runtime: bool
    enable_vision: bool
    vision_ollama_base_url: str
    vision_model: str
    vision_timeout_seconds: int
    vision_num_ctx: int
    vision_max_images: int
    vision_max_image_bytes: int
    vision_trusted_local_roots: tuple[Path, ...] = field(repr=False)
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
    enable_shared_scene_hub: bool
    shared_scene_group_id: str = field(repr=False)
    shared_scene_aike_bot_id: str = field(repr=False)
    shared_scene_linyin_bot_id: str = field(repr=False)
    scene_director_provider: str
    scene_director_api_key: str = field(repr=False)
    scene_director_base_url: str
    scene_director_model: str
    scene_director_timeout_seconds: int
    scene_director_circuit_seconds: int
    scene_max_context_events: int
    scene_director_context_events: int
    scene_max_reply_sentences: int
    scene_max_reply_chars: int
    scene_actor_max_tokens: int
    scene_private_context_max_messages: int
    scene_private_context_max_summaries: int
    scene_private_context_max_gap_summaries: int
    scene_private_context_max_manual_memories: int
    scene_private_context_max_chars: int
    scene_member_cache_seconds: int
    scene_max_pending_turns: int
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
    memory_rag_embedding_num_gpu: int
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
    owner_max_private_message_length: int
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
    vision_provider: str = "aliyun_bailian"
    vision_cloud_model: str = "qwen3.7-flash"
    aliyun_bailian_base_url: str = field(default="", repr=False)
    aliyun_bailian_api_key: str = field(default="", repr=False)
    enable_linyin_tts: bool = False
    linyin_tts_voice: str = field(default="", repr=False)
    linyin_tts_emotion: str = field(default="", repr=False)
    enable_image_gen: bool = False
    image_gen_api_key: str = field(default="", repr=False)
    image_gen_base_url: str = field(default="", repr=False)
    image_gen_model: str = "grok-imagine-1.0"
    image_edit_model: str = "grok-imagine-1.0-edit"
    image_gen_timeout_seconds: int = 120
    image_gen_max_prompt_chars: int = 1000
    image_gen_max_input_bytes: int = 10_485_760
    image_gen_max_output_bytes: int = 10_485_760
    image_gen_pending_edit_seconds: int = 120
    image_gen_cooldown_seconds: int = 30
    image_gen_max_requests_per_hour: int = 10
    enable_qwen_space_edit: bool = False
    qwen_space_base_url: str = (
        "https://prithivmlmods-qwen-image-edit-2511-loras-fast.hf.space"
    )
    qwen_space_hf_token: str = field(default="", repr=False)
    qwen_space_submit_timeout_seconds: int = 60
    qwen_space_infer_timeout_seconds: int = 180
    qwen_space_download_timeout_seconds: int = 300
    qwen_space_download_retries: int = 2
    qwen_space_result_ttl_seconds: int = 1800
    qwen_space_max_side: int = 1024
    qwen_space_jpeg_quality: int = 90


def load_config() -> AiChatConfig:
    persona_routing = build_persona_routing_settings(
        routing_v2_enabled=_bool_env("ENABLE_PERSONA_ROUTING_V2", False),
        memory_v2_enabled=_bool_env("ENABLE_PERSONA_MEMORY_V2", False),
        routing_v2_bot_ids=_csv_env("PERSONA_ROUTING_V2_BOT_IDS"),
        memory_v2_bot_ids=_csv_env("PERSONA_MEMORY_V2_BOT_IDS"),
        legacy_persona_id=os.getenv("LEGACY_PERSONA_ID", "aike"),
        legacy_role_card_key=os.getenv("LEGACY_ROLE_CARD_KEY", "aike"),
        raw_bindings=os.getenv("BOT_PERSONA_BINDINGS", ""),
    )
    return AiChatConfig(
        bot_name=os.getenv("BOT_NAME", "AI Assistant"),
        bot_aliases=_csv_env("BOT_ALIASES"),
        bot_owner_qq=os.getenv("BOT_OWNER_QQ", "").strip(),
        bot_owner_public_name=os.getenv("BOT_OWNER_PUBLIC_NAME", "").strip(),
        bot_timezone=_timezone_env("BOT_TIMEZONE"),
        persona_routing=persona_routing,
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
        enable_persona_llm_routing=_bool_env("ENABLE_PERSONA_LLM_ROUTING", False),
        persona_llm_role_card_keys=_csv_env("PERSONA_LLM_ROLE_CARD_KEYS"),
        persona_llm_api_key=os.getenv("PERSONA_LLM_API_KEY", "").strip(),
        persona_llm_base_url=os.getenv("PERSONA_LLM_BASE_URL", "").strip(),
        persona_llm_model=os.getenv("PERSONA_LLM_MODEL", "").strip(),
        persona_llm_timeout_seconds=_security_int_env(
            "PERSONA_LLM_TIMEOUT_SECONDS",
            _int_env("AI_TIMEOUT_SECONDS", 60),
        ),
        enable_persona_vision_routing=_bool_env(
            "ENABLE_PERSONA_VISION_ROUTING",
            False,
        ),
        persona_vision_role_card_keys=_csv_env(
            "PERSONA_VISION_ROLE_CARD_KEYS"
        ),
        persona_vision_model=os.getenv(
            "PERSONA_VISION_MODEL",
            os.getenv("PERSONA_LLM_MODEL", ""),
        ).strip(),
        persona_vision_timeout_seconds=_security_int_env(
            "PERSONA_VISION_TIMEOUT_SECONDS",
            _security_int_env(
                "PERSONA_LLM_TIMEOUT_SECONDS",
                _int_env("AI_TIMEOUT_SECONDS", 60),
            ),
        ),
        persona_vision_private_image_wait_seconds=_int_env(
            "PERSONA_VISION_PRIVATE_IMAGE_WAIT_SECONDS",
            -1,
        ),
        enable_chat_weather=_bool_env("ENABLE_CHAT_WEATHER", False),
        chat_weather_mode=_chat_weather_mode_env("CHAT_WEATHER_MODE"),
        chat_weather_provider=os.getenv(
            "CHAT_WEATHER_PROVIDER",
            "open_meteo",
        ).strip().lower(),
        chat_weather_default_location=os.getenv(
            "CHAT_WEATHER_DEFAULT_LOCATION",
            "",
        ).strip(),
        chat_weather_default_latitude=_security_float_env(
            "CHAT_WEATHER_DEFAULT_LATITUDE",
            0.0,
        ),
        chat_weather_default_longitude=_security_float_env(
            "CHAT_WEATHER_DEFAULT_LONGITUDE",
            0.0,
        ),
        chat_weather_timeout_seconds=_security_float_env(
            "CHAT_WEATHER_TIMEOUT_SECONDS",
            5.0,
        ),
        enable_chat_graph_runtime=_bool_env("ENABLE_CHAT_GRAPH_RUNTIME", False),
        enable_vision=_bool_env("ENABLE_VISION", True),
        vision_ollama_base_url=os.getenv("VISION_OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        vision_model=os.getenv("VISION_MODEL", "qwen2.5vl:3b"),
        vision_timeout_seconds=_int_env("VISION_TIMEOUT_SECONDS", 180),
        vision_num_ctx=_int_env("VISION_NUM_CTX", 16384),
        vision_max_images=_int_env("VISION_MAX_IMAGES", 1),
        vision_max_image_bytes=_int_env("VISION_MAX_IMAGE_BYTES", 5242880),
        vision_trusted_local_roots=_trusted_path_roots_env(
            "VISION_TRUSTED_LOCAL_ROOTS"
        ),
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
        enable_shared_scene_hub=_bool_env("ENABLE_SHARED_SCENE_HUB", False),
        shared_scene_group_id=os.getenv("SHARED_SCENE_GROUP_ID", "").strip(),
        shared_scene_aike_bot_id=os.getenv(
            "SHARED_SCENE_AIKE_BOT_ID", ""
        ).strip(),
        shared_scene_linyin_bot_id=os.getenv(
            "SHARED_SCENE_LINYIN_BOT_ID", ""
        ).strip(),
        scene_director_provider=os.getenv(
            "SCENE_DIRECTOR_PROVIDER", "qwen"
        ).strip().lower(),
        scene_director_api_key=os.getenv(
            "SCENE_DIRECTOR_API_KEY", ""
        ).strip(),
        scene_director_base_url=os.getenv(
            "SCENE_DIRECTOR_BASE_URL", ""
        ).strip(),
        scene_director_model=os.getenv("SCENE_DIRECTOR_MODEL", "").strip(),
        scene_director_timeout_seconds=_security_int_env(
            "SCENE_DIRECTOR_TIMEOUT_SECONDS", 15
        ),
        scene_director_circuit_seconds=_security_int_env(
            "SCENE_DIRECTOR_CIRCUIT_SECONDS", 120
        ),
        scene_max_context_events=_security_int_env(
            "SCENE_MAX_CONTEXT_EVENTS", 20
        ),
        scene_director_context_events=_security_int_env(
            "SCENE_DIRECTOR_CONTEXT_EVENTS", 6
        ),
        scene_max_reply_sentences=_security_int_env(
            "SCENE_MAX_REPLY_SENTENCES", 3
        ),
        scene_max_reply_chars=_security_int_env("SCENE_MAX_REPLY_CHARS", 160),
        scene_actor_max_tokens=_security_int_env(
            "SCENE_ACTOR_MAX_TOKENS", 256
        ),
        scene_private_context_max_messages=_security_int_env(
            "SCENE_PRIVATE_CONTEXT_MAX_MESSAGES", 12
        ),
        scene_private_context_max_summaries=_security_int_env(
            "SCENE_PRIVATE_CONTEXT_MAX_SUMMARIES", 2
        ),
        scene_private_context_max_gap_summaries=_security_int_env(
            "SCENE_PRIVATE_CONTEXT_MAX_GAP_SUMMARIES", 1
        ),
        scene_private_context_max_manual_memories=_security_int_env(
            "SCENE_PRIVATE_CONTEXT_MAX_MANUAL_MEMORIES", 8
        ),
        scene_private_context_max_chars=_security_int_env(
            "SCENE_PRIVATE_CONTEXT_MAX_CHARS", 2400
        ),
        scene_member_cache_seconds=_security_int_env(
            "SCENE_MEMBER_CACHE_SECONDS", 30
        ),
        scene_max_pending_turns=_security_int_env(
            "SCENE_MAX_PENDING_TURNS", 1
        ),
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
        memory_rag_embedding_num_gpu=_int_env("MEMORY_RAG_EMBEDDING_NUM_GPU", -1),
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
        owner_max_private_message_length=_int_env(
            "OWNER_MAX_PRIVATE_MESSAGE_LENGTH",
            0,
        ),
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
        tts_max_chars=_int_env("TTS_MAX_CHARS", 260),
        tts_max_total_seconds=_int_env("TTS_MAX_TOTAL_SECONDS", 60),
        tts_cooldown_seconds=_int_env("TTS_COOLDOWN_SECONDS", 20),
        tts_auto_start=_bool_env("TTS_AUTO_START", True),
        tts_startup_wait_seconds=_int_env("TTS_STARTUP_WAIT_SECONDS", 45),
        user_blacklist=_csv_env("USER_BLACKLIST"),
        vision_provider="aliyun_bailian",
        vision_cloud_model="qwen3.7-flash",
        aliyun_bailian_base_url=os.getenv(
            "ALIYUN_BAILIAN_BASE_URL",
            "",
        ).strip(),
        aliyun_bailian_api_key=os.getenv(
            "ALIYUN_BAILIAN_API_KEY",
            "",
        ).strip(),
        enable_linyin_tts=_bool_env("ENABLE_LINYIN_TTS", False),
        linyin_tts_voice=os.getenv("LINYIN_TTS_VOICE", "").strip(),
        linyin_tts_emotion=os.getenv("LINYIN_TTS_EMOTION", "").strip(),
        enable_image_gen=_bool_env("ENABLE_IMAGE_GEN", False),
        image_gen_api_key=os.getenv(
            "IMAGE_GEN_API_KEY",
            os.getenv("PERSONA_LLM_API_KEY", ""),
        ).strip(),
        image_gen_base_url=os.getenv(
            "IMAGE_GEN_BASE_URL",
            os.getenv("PERSONA_LLM_BASE_URL", ""),
        ).strip(),
        image_gen_model=os.getenv(
            "IMAGE_GEN_MODEL", "grok-imagine-1.0"
        ).strip(),
        image_edit_model=os.getenv(
            "IMAGE_EDIT_MODEL", "grok-imagine-1.0-edit"
        ).strip(),
        image_gen_timeout_seconds=_security_int_env(
            "IMAGE_GEN_TIMEOUT_SECONDS", 120
        ),
        image_gen_max_prompt_chars=_security_int_env(
            "IMAGE_GEN_MAX_PROMPT_CHARS", 1000
        ),
        image_gen_max_input_bytes=_security_int_env(
            "IMAGE_GEN_MAX_INPUT_BYTES", 10_485_760
        ),
        image_gen_max_output_bytes=_security_int_env(
            "IMAGE_GEN_MAX_OUTPUT_BYTES", 10_485_760
        ),
        image_gen_pending_edit_seconds=_security_int_env(
            "IMAGE_GEN_PENDING_EDIT_SECONDS", 120
        ),
        image_gen_cooldown_seconds=_security_int_env(
            "IMAGE_GEN_COOLDOWN_SECONDS", 30
        ),
        image_gen_max_requests_per_hour=_security_int_env(
            "IMAGE_GEN_MAX_REQUESTS_PER_HOUR", 10
        ),
        enable_qwen_space_edit=_bool_env("ENABLE_QWEN_SPACE_EDIT", False),
        qwen_space_base_url=os.getenv(
            "QWEN_SPACE_BASE_URL",
            "https://prithivmlmods-qwen-image-edit-2511-loras-fast.hf.space",
        ).strip(),
        qwen_space_hf_token=os.getenv("QWEN_SPACE_HF_TOKEN", "").strip(),
        qwen_space_submit_timeout_seconds=_security_int_env(
            "QWEN_SPACE_SUBMIT_TIMEOUT_SECONDS", 60
        ),
        qwen_space_infer_timeout_seconds=_security_int_env(
            "QWEN_SPACE_INFER_TIMEOUT_SECONDS", 180
        ),
        qwen_space_download_timeout_seconds=_security_int_env(
            "QWEN_SPACE_DOWNLOAD_TIMEOUT_SECONDS", 300
        ),
        qwen_space_download_retries=_security_int_env(
            "QWEN_SPACE_DOWNLOAD_RETRIES", 2
        ),
        qwen_space_result_ttl_seconds=_security_int_env(
            "QWEN_SPACE_RESULT_TTL_SECONDS", 1800
        ),
        qwen_space_max_side=_security_int_env("QWEN_SPACE_MAX_SIDE", 1024),
        qwen_space_jpeg_quality=_security_int_env(
            "QWEN_SPACE_JPEG_QUALITY", 90
        ),
    )
