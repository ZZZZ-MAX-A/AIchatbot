import json
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import httpx
from nonebot import get_driver
from openai import AsyncOpenAI

from .config import AiChatConfig
from .completion_routes import resolve_chat_completion_route
from .database import DATABASE_PATH, connect, ensure_database
from .failure_diagnostics import format_failure_inspection, inspect_failure_lines
from .memory import memory_stats
from .role_cards import ROLE_CARD_DIR, active_role_card, list_role_cards
from .persona_maintenance import build_persona_binding_report
from .trials import trial_stats
from .vision import VisionInferenceCheck, check_vision_inference
from .vision_routes import persona_vision_api_key


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ERROR_LOG_PATH = PROJECT_ROOT / "logs" / "ai_chat_error.log"

CHAT_TEST_TIMEOUT_SECONDS = 5
OLLAMA_TEST_TIMEOUT_SECONDS = 3
CHAT_TEST_SYSTEM_PROMPT = (
    "你是聊天接口健康检查。请只返回一句普通中文，"
    "不要读取、猜测或输出任何隐私信息。"
)
CHAT_TEST_USER_PROMPT = "请回复：聊天接口正常"


SENSITIVE_PATTERNS = (
    (re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"), "[已脱敏邮箱]"),
    (re.compile(r"\b1[3-9]\d{9}\b"), "[已脱敏手机号]"),
    (re.compile(r"\b\d{17}[\dXx]\b|\b\d{15}\b"), "[已脱敏证件号]"),
    (re.compile(r"\b\d{13,19}\b"), "[已脱敏长号码]"),
    (re.compile(r"(?i)\b(?:sk-|ak-)[A-Za-z0-9_-]{10,}\b"), "[已脱敏密钥]"),
    (re.compile(r"(?i)\b(?:api[_ -]?key|token|password|passwd|secret)\s*[:=：]\s*\S+"), "[已脱敏密钥]"),
    (re.compile(r"https?://\S+", re.IGNORECASE), "[已脱敏链接]"),
)


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    detail: str


@dataclass(frozen=True)
class OllamaStatus:
    service: CheckResult
    model_exists: bool | None
    models: tuple[str, ...] = ()


def _yes_no(value: bool) -> str:
    return "是" if value else "否"


def _on_off(value: bool) -> str:
    return "开启" if value else "关闭"


def _configured(value: str) -> str:
    return "已配置" if value else "未配置"


def _redacted_url(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return "未配置"
    parsed = urlsplit(stripped)
    if not parsed.scheme or not parsed.netloc:
        return "[无效地址]"
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{host}{port}{path}"


def _service_address_scope(value: str) -> str:
    parsed = urlsplit(value.strip())
    host = (parsed.hostname or "").lower()
    if host in {"127.0.0.1", "localhost", "::1"}:
        return "本机 loopback"
    return "非本机地址" if host else "未知"


def _human_bytes(value: int) -> str:
    size = max(int(value), 0)
    if size and size % (1024 * 1024) == 0:
        return f"{size // (1024 * 1024)} MiB"
    if size and size % 1024 == 0:
        return f"{size // 1024} KiB"
    return f"{size} 字节"


def _short_error(exc: Exception) -> str:
    message = sanitize_text(str(exc))
    if len(message) > 80:
        message = message[:77].rstrip() + "..."
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__


def sanitize_text(text: str) -> str:
    sanitized = text.replace("\r", " ").replace("\n", " ")
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return " ".join(sanitized.split())


def _extract_chat_content(response: object) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""

    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts).strip()
    return ""


def _chat_finish_reason(response: object) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return "无 choices"
    reason = getattr(choices[0], "finish_reason", None)
    return str(reason) if reason else "未知"


def config_warnings(config: AiChatConfig) -> list[str]:
    warnings = [
        f"{item.key}: {item.message}"
        for item in getattr(config, "configuration_issues", ())
    ]
    chat_route = resolve_chat_completion_route(config)
    if not config.bot_owner_qq:
        warnings.append("BOT_OWNER_QQ 未配置，主人命令不可用。")
    if not chat_route.configured:
        warnings.append(
            "默认聊天路由配置不完整：" + ", ".join(chat_route.configuration_errors)
        )
    if (
        config.enable_main_agent
        and config.main_agent_use_llm
        and not config.main_llm_api_key
    ):
        warnings.append("MainAgent 已启用 Main LLM，但 MAIN_LLM_API_KEY 未配置。")
    if config.enable_vision:
        warning_vision_provider = str(
            getattr(config, "vision_provider", "ollama") or "ollama"
        ).strip().lower()
        if warning_vision_provider == "ollama" and not config.vision_model:
            warnings.append("ENABLE_VISION=true 且 VISION_PROVIDER=ollama，但 VISION_MODEL 为空。")
    if config.summary_keep_recent_messages >= config.max_stored_messages_per_session:
        warnings.append("SUMMARY_KEEP_RECENT_MESSAGES 不小于 MAX_STORED_MESSAGES_PER_SESSION，自动压缩可能难以触发。")
    if config.max_context_messages != config.summary_keep_recent_messages:
        warnings.append("MAX_CONTEXT_MESSAGES 与 SUMMARY_KEEP_RECENT_MESSAGES 不一致，可能产生保留但不可见的原文。")
    if config.group_auto_reply_threshold < 20:
        warnings.append("GROUP_AUTO_REPLY_THRESHOLD 低于 20，主动回复可能过于频繁。")
    vision_provider = str(
        getattr(config, "vision_provider", "ollama") or "ollama"
    ).strip().lower()
    if config.enable_vision and vision_provider == "aliyun_bailian":
        if not str(getattr(config, "aliyun_bailian_base_url", "") or "").strip():
            warnings.append("云端视觉已启用，但 ALIYUN_BAILIAN_BASE_URL 未配置。")
        if not str(getattr(config, "aliyun_bailian_api_key", "") or "").strip():
            warnings.append("云端视觉已启用，但 ALIYUN_BAILIAN_API_KEY 未配置。")
        if str(getattr(config, "vision_cloud_model", "") or "").strip() != "qwen3.7-flash":
            warnings.append("云端视觉模型不是当前固定合同 qwen3.7-flash。")
    if getattr(config, "enable_persona_llm_routing", False):
        if not getattr(config, "persona_llm_role_card_keys", frozenset()):
            warnings.append("人格聊天路由已开启，但 PERSONA_LLM_ROLE_CARD_KEYS 为空。")
        for role in getattr(config, "persona_llm_role_card_keys", ()):
            try:
                resolve_chat_completion_route(config, role)
            except (RuntimeError, ValueError, TypeError):
                warnings.append("人格聊天路由已开启，但路由配置不完整；不回退默认模型。")
                break
    if getattr(config, "enable_persona_vision_routing", False):
        if not getattr(config, "persona_vision_role_card_keys", frozenset()):
            warnings.append("人格视觉路由已开启，但 PERSONA_VISION_ROLE_CARD_KEYS 为空。")
        if not persona_vision_api_key(config):
            warnings.append("人格视觉路由已开启，但当前视觉线路的 Key 未配置。")
    if getattr(config, "enable_image_gen", False):
        if not getattr(config, "image_gen_api_key", "") or not getattr(config, "image_gen_base_url", ""):
            warnings.append("图片生成已开启，但图片接口或专属 Key 未完整配置。")
        if not getattr(config, "image_gen_model", "") or not getattr(config, "image_edit_model", ""):
            warnings.append("图片生成已开启，但文生图或改图模型为空。")
    if getattr(config, "enable_qwen_space_edit", False):
        if not getattr(config, "qwen_space_base_url", ""):
            warnings.append("Qwen Space 改图已开启，但 Space 地址为空。")
        if not getattr(config, "qwen_space_hf_token", ""):
            warnings.append("Qwen Space 当前使用匿名队列，建议配置 HF Token 以提高排队优先级。")
    if getattr(config, "enable_chat_weather", False):
        mode = str(getattr(config, "chat_weather_mode", "off") or "off").strip().lower()
        if mode == "off":
            warnings.append("天气能力总开关已开启，但 CHAT_WEATHER_MODE=off，实际不会提供天气上下文。")
    persona_routing = getattr(config, "persona_routing", None)
    if persona_routing is not None and getattr(persona_routing, "binding_errors", ()):
        warnings.append(
            f"人格绑定配置存在 {len(persona_routing.binding_errors)} 个错误项，相关路由会失败关闭。"
        )
    report = build_persona_binding_report(config)
    if not report["ready"]:
        warnings.append("账号固定绑定未就绪；请检查绑定、角色卡和人格路由，异常账号禁止借用默认记忆库。")
    return warnings


def _primary_text(config: AiChatConfig, name: str, default: str = "") -> str:
    return str(getattr(config, name, default) or "").strip()


def _primary_bool(config: AiChatConfig, name: str, default: bool = False) -> bool:
    return bool(getattr(config, name, default))


def _primary_int(config: AiChatConfig, name: str, default: int = 0) -> int:
    try:
        return int(getattr(config, name, default))
    except (TypeError, ValueError):
        return default


def _persona_binding_active(config: AiChatConfig, role_card_key: str) -> bool:
    settings = getattr(config, "persona_routing", None)
    if settings is None or not getattr(settings, "routing_v2_enabled", False):
        return False
    if getattr(settings, "binding_errors", ()):
        return False
    routing_bot_ids = {
        str(item).strip()
        for item in getattr(settings, "routing_v2_bot_ids", ())
        if str(item).strip()
    }
    for binding in getattr(settings, "bindings", ()):
        if (
            str(getattr(binding, "role_card_key", "")).strip() == role_card_key
            and str(getattr(binding, "bot_self_id", "")).strip() in routing_bot_ids
        ):
            return True
    return False


def _persona_memory_active(config: AiChatConfig, role_card_key: str) -> bool:
    settings = getattr(config, "persona_routing", None)
    if settings is None or not getattr(settings, "memory_v2_enabled", False):
        return False
    if not _persona_binding_active(config, role_card_key):
        return False
    memory_bot_ids = {
        str(item).strip()
        for item in getattr(settings, "memory_v2_bot_ids", ())
        if str(item).strip()
    }
    return any(
        str(getattr(binding, "role_card_key", "")).strip() == role_card_key
        and str(getattr(binding, "bot_self_id", "")).strip() in memory_bot_ids
        for binding in getattr(settings, "bindings", ())
    )


def _global_vision_ready(config: AiChatConfig) -> bool:
    if not _primary_bool(config, "enable_vision"):
        return False
    provider = _primary_text(config, "vision_provider", "aliyun_bailian").lower()
    if provider == "aliyun_bailian":
        return bool(
            _primary_text(config, "vision_cloud_model", "qwen3.7-flash")
            and _primary_text(config, "aliyun_bailian_base_url")
            and _primary_text(config, "aliyun_bailian_api_key")
        )
    return bool(
        _primary_text(config, "vision_model")
        and _primary_text(config, "vision_ollama_base_url")
    )


def _persona_vision_ready(config: AiChatConfig, role_card_key: str) -> bool:
    if not _global_vision_ready(config):
        return False
    if not _primary_bool(config, "enable_persona_vision_routing"):
        return False
    if role_card_key not in getattr(config, "persona_vision_role_card_keys", ()):
        return False
    return bool(
        _persona_binding_active(config, role_card_key)
        and _primary_text(config, "persona_vision_model")
        and _primary_text(config, "persona_vision_base_url")
        and persona_vision_api_key(config)
    )


def _chat_route_ready(config: AiChatConfig) -> bool:
    return resolve_chat_completion_route(config).configured


def _primary_model_status(config: AiChatConfig, *, persona: bool = False) -> str:
    try:
        route = resolve_chat_completion_route(config, "linyin" if persona else "aike")
    except (RuntimeError, ValueError, TypeError):
        return "配置不完整"
    if not route.configured:
        return "配置不完整"
    if persona and route.source == "persona" and not _persona_binding_active(config, "linyin"):
        return "模型已配置，角色绑定未启用"
    return "默认聊天线路已配置" if persona and route.source == "legacy" else "已启用"


def _primary_chat_model_name(config: AiChatConfig, role_card_key: str) -> str:
    try:
        return resolve_chat_completion_route(config, role_card_key).model or "未配置"
    except (RuntimeError, ValueError, TypeError):
        return "未就绪（角色路由配置不完整）"


def _primary_main_agent_status(config: AiChatConfig) -> str:
    if not _primary_bool(config, "enable_main_agent"):
        return "已关闭"
    if not _primary_bool(config, "main_agent_use_llm"):
        return "入口已启用，LLM 调用未启用"
    if not _primary_text(config, "main_llm_model") or not _primary_text(
        config, "main_llm_api_key"
    ):
        return "配置不完整"
    return "已启用"


def _primary_capability_lines(
    config: AiChatConfig,
    *,
    persona: bool,
) -> list[str]:
    capabilities: list[str] = ["文字聊天"]
    if persona:
        if _persona_vision_ready(config, "linyin"):
            capabilities.append("图片识别")
        if (
            _primary_bool(config, "enable_tts")
            and _primary_bool(config, "enable_linyin_tts")
            and _primary_text(config, "linyin_tts_voice")
            and _primary_text(config, "linyin_tts_emotion")
        ):
            capabilities.append("语音输出")
        if _primary_bool(config, "enable_chat_weather") and _primary_text(
            config, "chat_weather_mode", "off"
        ).lower() != "off":
            capabilities.append("天气查询（主人私聊）")
        if _persona_memory_active(config, "linyin"):
            capabilities.append("记忆")
        if _primary_bool(config, "enable_memory_rag") and _primary_bool(
            config, "memory_rag_inject_in_chat"
        ):
            capabilities.append("Memory RAG")
        if _primary_bool(config, "enable_shared_scene_hub"):
            capabilities.append("共享场景互动")
        return capabilities

    if _global_vision_ready(config):
        capabilities.append("图片识别")
    if _primary_bool(config, "enable_tts"):
        capabilities.append("语音输出")
    if (
        _primary_bool(config, "enable_local_stickers")
        and _primary_bool(config, "enable_remote_sticker_classifier")
        and _primary_bool(config, "enable_chat_sticker_attachments")
    ):
        capabilities.append("表情包识别与发送")
    if _primary_bool(config, "enable_chat_weather") and _primary_text(
        config, "chat_weather_mode", "off"
    ).lower() != "off":
        capabilities.append("天气查询（主人私聊）")
    capabilities.append("记忆")
    if _primary_bool(config, "enable_memory_rag") and _primary_bool(
        config, "memory_rag_inject_in_chat"
    ):
        capabilities.append("Memory RAG")
    if _primary_bool(config, "enable_group_auto_reply"):
        capabilities.append("群聊主动回复")
    if _primary_bool(config, "enable_shared_scene_hub"):
        capabilities.append("共享场景互动")
    return capabilities


def _primary_llm_detail_lines(config: AiChatConfig) -> list[str]:
    chat_model = _primary_chat_model_name(config, "aike")
    persona_model = _primary_chat_model_name(config, "linyin")
    main_model = _primary_text(config, "main_llm_model") or "未配置"
    lines = [
        "【主要 LLM】",
        "",
        "爱可 Chatbot",
        f"模型：{chat_model}",
        f"状态：{_primary_model_status(config)}",
        f"能力：{'、'.join(_primary_capability_lines(config, persona=False))}",
        "",
        "凛音 Chatbot",
        f"模型：{persona_model}",
        f"状态：{_primary_model_status(config, persona=True)}",
        f"能力：{'、'.join(_primary_capability_lines(config, persona=True))}",
        "说明：普通群聊主动回复、表情包识别与发送目前未接入；共享群聊场景使用 DeepSeek 路线",
        "",
        "MainAgent",
        f"模型：{main_model}",
        f"状态：{_primary_main_agent_status(config)}",
        "用途：项目上下文查询、系统状态与运行链路诊断、记忆与 RAG 查询、人格与访问状态查看、Web 公开资料检索、任务与审批工作流、生成并发送 TXT / Word / PPT",
    ]
    return lines


def _primary_tts_detail_lines(config: AiChatConfig) -> list[str]:
    enabled = _primary_bool(config, "enable_tts")
    default_voice = _primary_text(config, "tts_voice")
    default_emotion = _primary_text(config, "tts_emotion")
    default_route_ready = bool(enabled and default_voice and default_emotion)
    linyin_enabled = _primary_bool(config, "enable_linyin_tts")
    linyin_voice = _primary_text(config, "linyin_tts_voice")
    linyin_emotion = _primary_text(config, "linyin_tts_emotion")
    linyin_route_ready = bool(
        enabled and linyin_enabled and linyin_voice and linyin_emotion
    )

    if not enabled:
        default_route_status = "未启用"
        linyin_route_status = "未启用"
    else:
        default_route_status = (
            "已接入默认语音线路" if default_route_ready else "配置不完整"
        )
        if not linyin_enabled:
            linyin_route_status = "未启用"
        else:
            linyin_route_status = (
                "已接入独立语音线路" if linyin_route_ready else "配置不完整"
            )

    return [
        "【语音输出】",
        f"功能：{'已启用' if enabled else '已关闭'}",
        "引擎：IndexTTS2",
        "语言：中文",
        "使用范围：主人私聊",
        f"启动方式：{'按需自动冷启动' if _primary_bool(config, 'tts_auto_start') else '不会自动启动'}",
        f"文本上限：{getattr(config, 'tts_max_chars', 0)} 字",
        f"单次总时长上限：{getattr(config, 'tts_max_total_seconds', 0)} 秒",
        f"生成冷却：{getattr(config, 'tts_cooldown_seconds', 0)} 秒",
        "",
        "爱可 Chatbot",
        f"语音输出：{default_route_status}",
        f"音色：{'已配置' if default_voice else '未配置'}",
        f"情绪：{'已配置' if default_emotion else '未配置'}",
        "",
        "凛音 Chatbot",
        f"语音输出：{linyin_route_status}",
        f"音色：{'已配置' if linyin_voice else '未配置'}",
        f"情绪：{'已配置' if linyin_emotion else '未配置'}",
    ]


def _primary_vision_route_status(config: AiChatConfig, *, persona: bool) -> str:
    if not _primary_bool(config, "enable_vision"):
        return "未启用"
    default_ready = _global_vision_ready(config)
    if not persona:
        return "已接入默认视觉线路" if default_ready else "配置不完整"

    independent_requested = _primary_bool(
        config, "enable_persona_vision_routing"
    ) and "linyin" in getattr(config, "persona_vision_role_card_keys", ())
    if independent_requested:
        return (
            "已接入独立视觉线路"
            if _persona_vision_ready(config, "linyin")
            else "配置不完整"
        )
    return "已接入默认视觉线路" if default_ready else "配置不完整"


def _primary_vision_detail_lines(config: AiChatConfig) -> list[str]:
    provider = _primary_text(config, "vision_provider", "aliyun_bailian").lower()
    cloud_provider = provider == "aliyun_bailian"
    default_model = (
        _primary_text(config, "vision_cloud_model", "qwen3.7-flash")
        if cloud_provider
        else _primary_text(config, "vision_model")
    ) or "未配置"
    persona_model = _primary_text(config, "persona_vision_model") or "未配置"
    if cloud_provider:
        note = "说明：当前默认视觉使用云端线路；旧本地 Ollama 不作为当前主视觉线路。"
    elif provider == "ollama":
        note = "说明：当前默认视觉使用旧本地 Ollama 线路；云端视觉不作为当前主视觉线路。"
    else:
        note = "说明：当前默认视觉使用已配置线路；旧本地 Ollama 不作为当前主视觉线路。"

    return [
        "【图片识别】",
        f"功能：{'已启用' if _primary_bool(config, 'enable_vision') else '已关闭'}",
        "使用范围：聊天图片识别",
        f"每轮最多图片：{getattr(config, 'vision_max_images', 0)} 张",
        f"单图大小上限：{_human_bytes(getattr(config, 'vision_max_image_bytes', 0))}",
        "",
        "爱可 Chatbot",
        f"图片识别：{_primary_vision_route_status(config, persona=False)}",
        f"模型：{default_model}",
        "",
        "凛音 Chatbot",
        f"图片识别：{_primary_vision_route_status(config, persona=True)}",
        f"模型：{persona_model}",
        note,
    ]


def _primary_image_route_status(
    config: AiChatConfig,
    *,
    enabled_name: str,
    ready: bool,
    enabled_label: str,
) -> str:
    if not _primary_bool(config, enabled_name):
        return "未启用"
    return enabled_label if ready else "配置不完整"


def _primary_image_detail_lines(config: AiChatConfig) -> list[str]:
    image_enabled = _primary_bool(config, "enable_image_gen")
    image_ready = bool(
        image_enabled
        and _primary_text(config, "image_gen_api_key")
        and _primary_text(config, "image_gen_base_url")
        and _primary_text(config, "image_gen_model")
        and _primary_text(config, "image_edit_model")
    )
    qwen_enabled = _primary_bool(config, "enable_qwen_space_edit")
    qwen_ready = bool(
        qwen_enabled and _primary_text(config, "qwen_space_base_url")
    )
    qwen_download_retries = _primary_int(
        config, "qwen_space_download_retries"
    )
    lines = [
        "【图片生成与修改】",
        "使用范围：主人私聊",
        f"图片提示词上限：{_primary_int(config, 'image_gen_max_prompt_chars')} 字",
        f"普通图片输入上限：{_human_bytes(_primary_int(config, 'image_gen_max_input_bytes'))}",
        f"普通图片输出上限：{_human_bytes(_primary_int(config, 'image_gen_max_output_bytes'))}",
        f"单次操作冷却：{_primary_int(config, 'image_gen_cooldown_seconds')} 秒",
        f"每小时最多请求：{_primary_int(config, 'image_gen_max_requests_per_hour')} 次",
        "",
        "文生图",
        f"功能：{'已启用' if image_enabled else '已关闭'}",
        f"模型：{_primary_text(config, 'image_gen_model') or '未配置'}",
        f"状态：{_primary_image_route_status(config, enabled_name='enable_image_gen', ready=image_ready, enabled_label='已接入图片生成线路')}",
        f"接口等待上限：{_primary_int(config, 'image_gen_timeout_seconds')} 秒",
        "失败处理：不会自动重新生成",
        "",
        "普通改图",
        f"功能：{'已启用' if image_enabled else '已关闭'}",
        f"模型：{_primary_text(config, 'image_edit_model') or '未配置'}",
        f"状态：{_primary_image_route_status(config, enabled_name='enable_image_gen', ready=image_ready, enabled_label='已接入图片修改线路')}",
        f"等待发送待修改图片：{_primary_int(config, 'image_gen_pending_edit_seconds')} 秒",
        f"模型处理等待上限：{_primary_int(config, 'image_gen_timeout_seconds')} 秒",
        "失败处理：不会自动重新修改",
        "",
        "Qwen Space 改图",
        f"功能：{'已启用' if qwen_enabled else '已关闭'}",
        "模型：Qwen Image Edit",
        f"状态：{_primary_image_route_status(config, enabled_name='enable_qwen_space_edit', ready=qwen_ready, enabled_label='已接入 Qwen Space 改图线路')}",
        f"等待发送待修改图片：{_primary_int(config, 'image_gen_pending_edit_seconds')} 秒",
        f"提交阶段等待上限：{_primary_int(config, 'qwen_space_submit_timeout_seconds')} 秒",
        f"排队与推理等待上限：{_primary_int(config, 'qwen_space_infer_timeout_seconds')} 秒",
        f"结果下载单次等待上限：{_primary_int(config, 'qwen_space_download_timeout_seconds')} 秒",
        f"结果下载失败重试：{qwen_download_retries} 次",
        f"下载最多尝试：{qwen_download_retries + 1} 次（首次下载 + {qwen_download_retries} 次重试）",
        f"已生成结果可重新下载：{_primary_int(config, 'qwen_space_result_ttl_seconds') // 60} 分钟内有效",
        f"上传图片最长边：{_primary_int(config, 'qwen_space_max_side')} 像素",
        "失败处理：下载失败时可以重新下载，不会重复调用模型",
    ]
    return lines


def _primary_memory_detail_lines(config: AiChatConfig) -> list[str]:
    memory_rag_enabled = _primary_bool(config, "enable_memory_rag")
    project_doc_rag_enabled = _primary_bool(config, "enable_project_doc_rag")
    return [
        "【会话记忆与摘要】",
        f"自动压缩：{'已启用' if _primary_bool(config, 'enable_memory_compression') else '已关闭'}",
        f"每个会话最多保留原始消息：{_primary_int(config, 'max_stored_messages_per_session')} 条",
        f"保留最近原文：{_primary_int(config, 'summary_keep_recent_messages')} 条",
        f"触发摘要的最低消息数：{_primary_int(config, 'summary_min_source_messages')} 条",
        f"每次摘要处理消息数：{_primary_int(config, 'summary_batch_messages')} 条",
        f"带入上下文的正式摘要：{_primary_int(config, 'max_session_summaries_in_context')} 条",
        "",
        "【长期记忆】",
        f"长期记忆上下文：{'已启用' if _primary_bool(config, 'enable_long_term_memory_context') else '已关闭'}",
        f"带入上下文的长期记忆：最多 {_primary_int(config, 'max_long_term_memories_in_context')} 条",
        "记忆类型：长期事实、长期偏好",
        "",
        "【空窗场景摘要】",
        f"空窗摘要：{'已启用' if _primary_bool(config, 'enable_gap_scene_summaries') else '已关闭'}",
        "当前策略：无状态卡时累计 25 条新消息后首次写入；已有状态卡时每新增 20 条更新",
        "GAP_SCENE_SUMMARY_1_THRESHOLD / GAP_SCENE_SUMMARY_2_THRESHOLD：历史兼容配置，当前调度器不使用",
        f"带入上下文的空窗摘要：最多 {_primary_int(config, 'max_gap_scene_summaries_in_context')} 条",
        "",
        "【MemoryRAG 记忆索引】",
        f"功能：{'已启用' if memory_rag_enabled else '已关闭'}",
        f"聊天注入：{'已启用' if _primary_bool(config, 'memory_rag_inject_in_chat') else '未启用'}",
        f"向量模型：{_primary_text(config, 'memory_rag_embedding_model') or '未配置'}",
        f"每次最多召回：{_primary_int(config, 'memory_rag_top_k')} 条",
        f"最低匹配分数：{getattr(config, 'memory_rag_min_score', 0)}",
        f"注入上下文上限：{_primary_int(config, 'memory_rag_max_context_chars')} 字",
        "检索来源：",
        f"- 长期事实记忆：{'启用' if _primary_bool(config, 'memory_rag_include_manual_facts') else '关闭'}",
        f"- 长期偏好记忆：{'启用' if _primary_bool(config, 'memory_rag_include_manual_preferences') else '关闭'}",
        f"- 正式会话摘要：{'启用' if _primary_bool(config, 'memory_rag_include_session_summaries') else '关闭'}",
        f"- 短消息：{'启用' if _primary_bool(config, 'memory_rag_include_short_messages') else '关闭'}",
        f"- 空窗摘要：{'启用' if _primary_bool(config, 'memory_rag_include_gap_scene_summaries') else '关闭'}",
        "",
        "【ProjectDocRAG 项目文档索引】",
        f"功能：{'已启用' if project_doc_rag_enabled else '已关闭'}",
        "聊天注入：未启用",
        f"每次最多召回：{_primary_int(config, 'project_doc_rag_top_k')} 条",
        f"最低匹配分数：{getattr(config, 'project_doc_rag_min_score', 0)}",
        f"注入上下文上限：{_primary_int(config, 'project_doc_rag_max_context_chars')} 字",
    ]


def config_detail_sections(config: AiChatConfig) -> dict[str, list[str]]:
    return {
        "模型": _primary_llm_detail_lines(config),
        "TTS": _primary_tts_detail_lines(config),
        "视觉": _primary_vision_detail_lines(config),
        "图片": _primary_image_detail_lines(config),
        "记忆": _primary_memory_detail_lines(config),
    }


_CONFIG_DETAIL_ALIASES = {
    "模型": "模型",
    "model": "模型",
    "聊天": "模型",
    "chat": "模型",
    "TTS": "TTS",
    "tts": "TTS",
    "语音": "TTS",
    "视觉": "视觉",
    "vision": "视觉",
    "图片": "图片",
    "image": "图片",
    "记忆": "记忆",
    "memory": "记忆",
}


def format_config_detail_status(config: AiChatConfig, section: str = "") -> str:
    sections = config_detail_sections(config)
    normalized = re.sub(r"\s+", "", str(section or "")).casefold()
    if not normalized or normalized in {"帮助", "help", "?"}:
        return "配置详情用法：/配置详情 <模型|TTS|视觉|图片|记忆>\n当前可用区域：模型、TTS、视觉、图片、记忆"
    if normalized in {"全部", "all"}:
        selected = list(sections)
    else:
        target = _CONFIG_DETAIL_ALIASES.get(normalized)
        if target is None:
            return f"未知配置区域：{section}\n当前可用区域：模型、TTS、视觉、图片、记忆"
        selected = [target]
    if selected == ["模型"]:
        explanation = "说明：这里只展示三条主要 LLM 的业务用途，不展示 URL、Key、Token、上下文或角色卡内容。"
    elif selected == ["TTS"]:
        explanation = "说明：这里只展示语音功能的业务配置，不展示服务地址、Key、Token 或内部路径。"
    elif selected == ["视觉"]:
        explanation = "说明：这里只展示图片识别的业务配置，不展示接口地址、Key、Token、上下文或角色卡内容。"
    elif selected == ["图片"]:
        explanation = "说明：这里只展示图片生成与修改的业务配置，不展示接口地址、Key、Token 或内部请求参数。"
    elif selected == ["记忆"]:
        explanation = "说明：这里只展示记忆、摘要和索引的业务配置，不展示聊天原文、记忆正文、数据库路径、接口地址、Key 或 Token。"
    else:
        explanation = "说明：这里只展示业务配置，不展示 URL、Key、Token、上下文、角色卡或内部路径。"
    lines = [
        f"配置详情（{'、'.join(selected)}）：",
        explanation,
    ]
    for name in selected:
        lines.extend(["", f"{name}："])
        lines.extend(f"- {line}" for line in sections[name])
    return "\n".join(lines)


def format_config_status(config: AiChatConfig) -> str:
    use_chat_graph = config.enable_chat_graph_runtime
    chat_runtime = "ChatGraph/RootGraph" if use_chat_graph else "兼容聊天链路"
    chat_route = resolve_chat_completion_route(config)
    lines = [
        "配置状态：",
        "",
        "基础与入口：",
        f"机器人：{config.bot_name}",
        f"主人：{_configured(config.bot_owner_qq)}",
        f"主人公开称呼：{_configured(config.bot_owner_public_name)}",
        f"私聊：{_on_off(config.enable_private_chat)}",
        f"群聊：{_on_off(config.enable_group_chat)}",
        f"群主动回复：{_on_off(config.enable_group_auto_reply)}",
        f"主人转告：{_on_off(config.enable_owner_notifications)}",
        f"聊天运行链路：{chat_runtime}",
        "",
        "默认聊天模型：",
        f"Chat LLM：{_configured(chat_route.configured)}",
        f"配置来源：{'AIKE_LLM_*' if chat_route.source == 'legacy' else 'PERSONA_LLM_*'}",
        f"接口：{_redacted_url(chat_route.base_url)}",
        f"模型：{chat_route.model or '未配置'}",
        f"Key：{_configured(chat_route.api_key)}",
        f"超时：{chat_route.timeout_seconds} 秒",
        f"温度：{config.ai_temperature}",
        "",
        "MainAgent：",
        f"入口：{_on_off(config.enable_main_agent)}",
        f"仅主人：{_yes_no(config.main_agent_owner_only)}",
        f"允许群聊：{_yes_no(config.main_agent_allow_group)}",
        f"Main LLM：{_on_off(config.main_agent_use_llm)}",
        f"Main LLM 接口：{_redacted_url(config.main_llm_base_url)}",
        f"Main LLM 模型：{config.main_llm_model or '未配置'}",
        f"Main LLM Key：{_configured(config.main_llm_api_key)}",
        f"Main LLM 超时：{config.main_llm_timeout_seconds} 秒",
        f"最大步骤：{config.main_agent_max_steps}",
        f"主人写操作审批：{_on_off(config.main_agent_require_approval_for_writes)}",
        "",
        "记忆与 RAG：",
        f"记忆压缩：{_on_off(config.enable_memory_compression)}",
        f"上下文消息：{config.max_context_messages}",
        f"摘要上下文：{config.max_session_summaries_in_context}",
        f"空窗场景摘要：{_on_off(config.enable_gap_scene_summaries)}",
        f"空窗摘要上下文：{config.max_gap_scene_summaries_in_context}",
        f"手动长期记忆上下文：{_on_off(config.enable_long_term_memory_context)}",
        f"长期记忆上下文：{config.max_long_term_memories_in_context}",
        f"MemoryRAG：{_on_off(config.enable_memory_rag)}",
        f"普通聊天注入：{_on_off(config.memory_rag_inject_in_chat)}",
        f"ProjectDocRAG：{_on_off(config.enable_project_doc_rag)}",
        f"Embedding：{config.memory_rag_embedding_provider} / {config.memory_rag_embedding_model}",
        f"Embedding 地址：{_redacted_url(config.memory_rag_embedding_base_url)}",
        f"Embedding 维度：{config.memory_rag_embedding_dimension}",
        "MemoryRAG top_k / min_score / context："
        f"{config.memory_rag_top_k} / {config.memory_rag_min_score} / "
        f"{config.memory_rag_max_context_chars}",
        "ProjectDocRAG top_k / min_score / context："
        f"{config.project_doc_rag_top_k} / {config.project_doc_rag_min_score} / "
        f"{config.project_doc_rag_max_context_chars}",
        "",
        "视觉：",
        f"功能：{_on_off(config.enable_vision)}",
        f"当前提供方：{getattr(config, 'vision_provider', 'ollama') or 'ollama'}",
        f"云端模型：{getattr(config, 'vision_cloud_model', 'qwen3.7-flash') or 'qwen3.7-flash'}",
        f"云端接口：{_redacted_url(getattr(config, 'aliyun_bailian_base_url', ''))}",
        f"云端 Key：{_configured(getattr(config, 'aliyun_bailian_api_key', ''))}",
        f"旧本地服务地址：{_redacted_url(config.vision_ollama_base_url)}",
        f"地址范围：{_service_address_scope(config.vision_ollama_base_url)}",
        f"旧本地模型：{config.vision_model or '未配置'}",
        f"超时：{config.vision_timeout_seconds} 秒",
        f"上下文：{config.vision_num_ctx}",
        f"每轮图片：{config.vision_max_images}",
        f"单图上限：{_human_bytes(config.vision_max_image_bytes)}",
        f"缓存 TTL：{config.vision_image_cache_ttl_seconds} 秒",
        f"私聊图片等待：{config.vision_private_image_wait_seconds} 秒",
        "",
        "图片生成：",
        f"功能：{_on_off(config.enable_image_gen)}",
        f"接口：{_redacted_url(config.image_gen_base_url)}",
        f"Key：{_configured(config.image_gen_api_key)}",
        f"文生图模型：{config.image_gen_model or '未配置'}",
        f"改图模型：{config.image_edit_model or '未配置'}",
        f"超时：{config.image_gen_timeout_seconds} 秒",
        f"描述上限：{config.image_gen_max_prompt_chars} 字",
        f"输入图片上限：{_human_bytes(config.image_gen_max_input_bytes)}",
        f"输出图片上限：{_human_bytes(config.image_gen_max_output_bytes)}",
        f"待改图有效期：{config.image_gen_pending_edit_seconds} 秒",
        f"冷却：{config.image_gen_cooldown_seconds} 秒",
        f"每小时上限：{config.image_gen_max_requests_per_hour} 次",
        "",
        "Qwen Space 改图：",
        f"功能：{_on_off(config.enable_qwen_space_edit)}",
        f"接口：{_redacted_url(config.qwen_space_base_url)}",
        f"HF Token：{_configured(config.qwen_space_hf_token)}",
        f"提交超时：{config.qwen_space_submit_timeout_seconds} 秒",
        f"排队与推理超时：{config.qwen_space_infer_timeout_seconds} 秒",
        f"结果下载超时：{config.qwen_space_download_timeout_seconds} 秒",
        f"结果下载重试：{config.qwen_space_download_retries} 次",
        f"结果重取有效期：{config.qwen_space_result_ttl_seconds} 秒",
        f"上传最长边：{config.qwen_space_max_side} 像素",
        f"JPEG 质量：{getattr(config, 'qwen_space_jpeg_quality', 0)}",
        "",
        "语音：",
        f"功能：{_on_off(config.enable_tts)}",
        f"服务地址：{_redacted_url(config.tts_service_url)}",
        f"地址范围：{_service_address_scope(config.tts_service_url)}",
        f"自动启动：{_on_off(config.tts_auto_start)}",
        f"默认音色：{config.tts_voice}",
        f"默认情绪：{config.tts_emotion}",
        f"超时：{config.tts_timeout_seconds} 秒",
        f"文本上限：{config.tts_max_chars} 字",
        f"总时长上限：{config.tts_max_total_seconds} 秒",
        f"冷却：{config.tts_cooldown_seconds} 秒",
        "",
        "MainAgent 高风险边界：",
        f"Agent Web：{_on_off(config.enable_agent_web)}",
        f"Shell：{_on_off(config.enable_agent_shell)}",
        f"通用本地写：{_on_off(config.enable_agent_local_write)}",
        f"外部写：{_on_off(config.enable_agent_external_write)}",
        "主人管理写："
        + (
            "审批门控"
            if config.main_agent_require_approval_for_writes
            else "未要求审批"
        ),
        "",
        "说明：以上是当前进程加载的配置值，不代表服务在线、模型已加载或端到端功能已经验证。",
        "运行状态请使用 /agent 执行系统诊断任务，或对应的状态命令。",
        "业务配置详情请使用：/配置详情 <模型|TTS|视觉|图片|记忆>。",
    ]
    warnings = config_warnings(config)
    if warnings:
        lines.append("")
        lines.append("警告：")
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines)


def database_status_lines() -> list[str]:
    try:
        ensure_database()
        stats = memory_stats()
        trials = trial_stats()
        with connect() as connection:
            connection.execute("SELECT 1").fetchone()
        return [
            "数据库：正常",
            f"路径：{DATABASE_PATH}",
            f"消息：{stats['message_count']}",
            f"会话：{stats['session_count']}",
            f"摘要：{stats['summary_count']}",
            f"已压缩消息：{stats['summarized_message_count']}",
            f"试用用户：{trials['trial_user_count']}",
        ]
    except sqlite3.Error as exc:
        return [
            f"数据库：失败 {_short_error(exc)}",
            f"路径：{DATABASE_PATH}",
        ]
    except Exception as exc:
        return [
            f"数据库：失败 {_short_error(exc)}",
            f"路径：{DATABASE_PATH}",
        ]


def role_card_status_lines() -> list[str]:
    try:
        card = active_role_card()
        cards = list_role_cards()
        return [
            f"角色卡：{'已启用' if card is not None else '未启用'}",
            f"当前角色卡：{card.path.name if card is not None else '无'}",
            f"角色卡目录：{ROLE_CARD_DIR}",
            f"可用角色卡：{len(cards)}",
        ]
    except Exception as exc:
        return [f"角色卡：失败 {_short_error(exc)}"]


async def check_chat_api(
    config: AiChatConfig,
    role_card_key: str = "",
    *,
    completion_route: str = "auto",
) -> CheckResult:
    """Probe one effective route with public fixed prompts and no tool calls."""
    try:
        route = resolve_chat_completion_route(
            config, role_card_key, completion_route=completion_route
        )
        if not route.configured:
            return CheckResult(
                False, "聊天路由配置不完整：" + ", ".join(route.configuration_errors)
            )
        messages = [
            {"role": "system", "content": CHAT_TEST_SYSTEM_PROMPT},
            {"role": "user", "content": CHAT_TEST_USER_PROMPT},
        ]
        timeout = min(route.timeout_seconds, CHAT_TEST_TIMEOUT_SECONDS)
        started = time.monotonic()
        if route.provider == "ollama":
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{route.base_url.rstrip('/')}/api/chat",
                    json={
                        "model": route.model,
                        "messages": messages,
                        "stream": False,
                        "keep_alive": 0,
                        "options": {
                            "temperature": 0,
                            "num_ctx": route.num_ctx,
                            "num_predict": min(32, route.max_tokens),
                        },
                    },
                )
                response.raise_for_status()
            message = response.json().get("message", {})
            content = message.get("content", "") if isinstance(message, dict) else ""
            content = content.strip() if isinstance(content, str) else ""
            reason = "未返回文本"
        else:
            async with AsyncOpenAI(
                api_key=route.api_key,
                base_url=route.base_url,
                timeout=timeout,
                max_retries=0,
            ) as client:
                response = await client.chat.completions.create(
                    model=route.model,
                    messages=messages,
                    temperature=0,
                )
            content = _extract_chat_content(response)
            reason = _chat_finish_reason(response)
        elapsed = time.monotonic() - started
        if not content:
            return CheckResult(False, f"返回空内容，用时 {elapsed:.1f} 秒，结束原因：{reason}")
        return CheckResult(True, f"正常，用时 {elapsed:.1f} 秒")
    except Exception as exc:
        return CheckResult(False, _short_error(exc))


def check_ollama(config: AiChatConfig) -> OllamaStatus:
    base_url = config.vision_ollama_base_url.rstrip("/")
    request = Request(f"{base_url}/api/tags", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=OLLAMA_TEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return OllamaStatus(CheckResult(False, f"HTTP {exc.code}"), None)
    except URLError as exc:
        return OllamaStatus(CheckResult(False, _short_error(exc)), None)
    except TimeoutError as exc:
        return OllamaStatus(CheckResult(False, _short_error(exc)), None)
    except json.JSONDecodeError as exc:
        return OllamaStatus(CheckResult(False, _short_error(exc)), None)
    except Exception as exc:
        return OllamaStatus(CheckResult(False, _short_error(exc)), None)

    models = tuple(
        str(item.get("name", ""))
        for item in payload.get("models", [])
        if isinstance(item, dict) and item.get("name")
    )
    model_exists = config.vision_model in models
    return OllamaStatus(CheckResult(True, "正常"), model_exists, models)


def _skipped_vision_inference(detail: str) -> VisionInferenceCheck:
    return VisionInferenceCheck(False, detail)


def _vision_inference_check_for_status(
    config: AiChatConfig,
    status: OllamaStatus,
) -> VisionInferenceCheck:
    if not config.enable_vision:
        return _skipped_vision_inference("视觉未开启，未执行")
    if not status.service.ok:
        return _skipped_vision_inference("Ollama 服务异常，未执行")
    if status.model_exists is False:
        return _skipped_vision_inference("视觉模型不存在，未执行")
    return check_vision_inference(config)


def vision_runner_recovery_suggestion(model: str) -> list[str]:
    selected_model = model.strip() or "<视觉模型>"
    return [
        "服务和模型均可用，但推理返回低质量重复内容；当前视觉 runner 可能处于异常状态。",
        f"可在 Bot 所在机器手动执行：ollama stop {selected_model}",
        "该命令只卸载当前模型，下一次视觉请求会重新加载；本次诊断未执行该命令，也未自动重试。",
    ]


def _vision_inference_is_low_quality_repeat(inference: VisionInferenceCheck) -> bool:
    return "低质量重复内容" in inference.detail


def format_vision_status(config: AiChatConfig, image_cache_stats: dict[str, int]) -> str:
    vision_provider = str(
        getattr(config, "vision_provider", "ollama") or "ollama"
    ).strip().lower()
    cloud_provider = vision_provider == "aliyun_bailian"
    if not config.enable_vision:
        status = OllamaStatus(CheckResult(False, "视觉未开启"), None)
    elif cloud_provider:
        status = OllamaStatus(
            CheckResult(True, "当前使用云端视觉，未主动发起远程探针"),
            None,
        )
    else:
        status = check_ollama(config)

    cloud_model = getattr(config, "vision_cloud_model", "qwen3.7-flash") or "qwen3.7-flash"
    cloud_base_url = getattr(config, "aliyun_bailian_base_url", "") or ""
    cloud_api_key = getattr(config, "aliyun_bailian_api_key", "") or ""
    lines = [
        "视觉状态：",
        f"视觉识图：{_on_off(config.enable_vision)}",
        f"当前提供方：{vision_provider}",
        f"云端模型：{cloud_model}",
        f"云端接口：{_redacted_url(cloud_base_url)}",
        f"云端 Key：{_configured(cloud_api_key)}",
        f"旧本地 Ollama 地址：{_redacted_url(config.vision_ollama_base_url)}",
        f"旧本地 Ollama 服务：{status.service.detail if not cloud_provider else '未执行（当前不是本地提供方）'}",
        f"旧本地视觉模型：{config.vision_model}",
        f"本地模型存在：{_yes_no(status.model_exists) if status.model_exists is not None else '未检查'}",
        f"视觉上下文：{config.vision_num_ctx}",
        "",
        f"图片缓存：{image_cache_stats.get('total', 0)} 条",
        f"私聊缓存：{image_cache_stats.get('private', 0)} 条",
        f"群聊缓存：{image_cache_stats.get('group', 0)} 条",
        f"缓存 TTL：{config.vision_image_cache_ttl_seconds} 秒",
        f"私聊图片等待：{config.vision_private_image_wait_seconds} 秒",
        f"每轮最多图片：{config.vision_max_images}",
        f"单图大小上限：{config.vision_max_image_bytes} 字节",
    ]
    inference = (
        _skipped_vision_inference("云端视觉未主动发起远程推理探针")
        if cloud_provider
        else _vision_inference_check_for_status(config, status)
    )
    lines.insert(7, f"推理自检：{inference.detail}")
    if (
        config.enable_vision
        and status.service.ok
        and status.model_exists is True
        and _vision_inference_is_low_quality_repeat(inference)
    ):
        lines.extend(
            [
                "",
                "Runner 恢复建议：",
                *vision_runner_recovery_suggestion(config.vision_model),
            ]
        )
    elif config.enable_vision and not cloud_provider and not status.service.ok:
        lines.extend(
            [
                "",
                "建议：",
                "1. 确认 ollama.exe 正在运行。",
                "2. 确认 OLLAMA_MODELS 指向 D:\\OllamaModels。",
                "3. 避免 ollama app.exe 托盘程序用默认中文路径接管。",
            ]
        )
    elif (
        config.enable_vision
        and not cloud_provider
        and status.service.ok
        and status.model_exists is False
    ):
        lines.extend(["", "建议：", f"运行 ollama pull {config.vision_model}"])
    return "\n".join(lines)


def format_image_cache_status(config: AiChatConfig, image_cache_stats: dict[str, int]) -> str:
    return "\n".join(
        [
            "图片缓存状态：",
            f"缓存数量：{image_cache_stats.get('total', 0)}",
            f"私聊缓存：{image_cache_stats.get('private', 0)}",
            f"群聊缓存：{image_cache_stats.get('group', 0)}",
            f"缓存 TTL：{config.vision_image_cache_ttl_seconds} 秒",
            f"私聊图片等待：{config.vision_private_image_wait_seconds} 秒",
            f"每轮最多图片：{config.vision_max_images}",
        ]
    )


def _first_line_with_prefix(lines: list[str], prefix: str) -> str:
    for line in lines:
        if line.startswith(prefix):
            return line
    return ""


def _vision_detail_metric_positive(root_lines: list[str], metric: str) -> bool:
    pattern = re.compile(rf"\b{re.escape(metric)}=(\d+)\b")
    for line in root_lines:
        if not line.startswith("Vision detail："):
            continue
        match = pattern.search(line)
        if match and int(match.group(1)) > 0:
            return True
    return False


def vision_troubleshoot_findings(
    *,
    vision_lines: list[str],
    recent_errors: list[str],
    root_lines: list[str],
) -> list[str]:
    joined_vision = "\n".join(vision_lines)
    findings: list[str] = []
    vision_disabled = "视觉识图：关闭" in joined_vision
    cloud_provider = "当前提供方：aliyun_bailian" in joined_vision
    if vision_disabled:
        findings.append("视觉功能当前关闭，图片不会进入识图推理。")

    if not vision_disabled:
        if cloud_provider:
            if "云端接口：未配置" in joined_vision or "云端接口：(empty)" in joined_vision:
                findings.append("云端视觉接口未配置，无法发起识图请求。")
            if "云端 Key：未配置" in joined_vision:
                findings.append("云端视觉 API Key 未配置，无法发起识图请求。")
        else:
            service_line = _first_line_with_prefix(vision_lines, "Ollama 服务：")
            if service_line and not any(
                marker in service_line.lower() for marker in ("ok", "正常")
            ):
                findings.append(f"Ollama 服务需要关注：{service_line}")
            if "模型存在：否" in joined_vision:
                model_line = _first_line_with_prefix(vision_lines, "视觉模型：")
                findings.append(f"视觉模型不存在或未拉取：{model_line or '请检查视觉模型配置'}")
        inference_line = _first_line_with_prefix(vision_lines, "推理自检：")
        if inference_line and not any(
            marker in inference_line.lower()
            for marker in ("ok", "正常", "成功", "跳过")
        ):
            findings.append(f"视觉推理自检需要关注：{inference_line}")
            if (
                not cloud_provider
                and "低质量重复内容" in inference_line
                and ("模型存在：是" in joined_vision or "本地模型存在：是" in joined_vision)
            ):
                model_line = _first_line_with_prefix(vision_lines, "视觉模型：") or _first_line_with_prefix(vision_lines, "旧本地视觉模型：")
                model = model_line.partition("：")[2].strip()
                findings.extend(vision_runner_recovery_suggestion(model))

    if _vision_detail_metric_positive(root_lines, "errors"):
        findings.append("最近 RootGraph 视觉观测里出现过识图错误计数，请查看 RootGraph 证据。")
    if _vision_detail_metric_positive(root_lines, "low_quality"):
        findings.append("最近 RootGraph 视觉观测里出现过低质量识图输出，请查看 RootGraph 证据。")
    if recent_errors:
        findings.append(
            "最近错误日志非空，优先核对其中的云端视觉、Ollama、vision 或 image 阶段错误。"
        )
    if not findings:
        findings.append("未发现明确的视觉链路硬错误；如果 QQ 侧仍异常，下一步优先看最近一条 RootGraph Vision detail 是否有图片 URL、缓存和低质量输出计数。")
    return findings


def _line_int_after_prefix(lines: list[str], prefix: str) -> int | None:
    line = _first_line_with_prefix(lines, prefix)
    if not line:
        return None
    match = re.search(r"-?\d+", line)
    return int(match.group(0)) if match else None


def _root_memory_rag_values(root_lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in root_lines:
        if not line.startswith("MemoryRAG："):
            continue
        for key, value in re.findall(r"\b([a-z_]+)=([^\s]+)", line):
            values[key] = value
    return values


def _truthy_runtime_value(value: str) -> bool:
    return value.strip().lower() in {"是", "true", "1", "yes", "y"}


def _runtime_int_value(values: dict[str, str], key: str) -> int:
    try:
        return int(values.get(key, "0") or 0)
    except (TypeError, ValueError):
        return 0


def memory_rag_troubleshoot_findings(
    *,
    status_lines: list[str],
    index_lines: list[str],
    recent_errors: list[str],
    root_lines: list[str],
) -> list[str]:
    joined_status = "\n".join(status_lines)
    joined_index = "\n".join(index_lines)
    findings: list[str] = []
    rag_disabled = "RAG 开关：关闭" in joined_status
    inject_disabled = "聊天注入：关闭" in joined_status

    if rag_disabled:
        findings.append("MemoryRAG 当前关闭，普通聊天不会进行语义记忆召回。")
    if inject_disabled:
        findings.append("MemoryRAG 聊天注入当前关闭，即使索引正常也不会注入普通聊天上下文。")

    embedding_line = _first_line_with_prefix(status_lines, "Embedding 自检：")
    if embedding_line and not rag_disabled and not any(
        marker in embedding_line.lower() for marker in ("ok", "正常", "成功")
    ):
        findings.append(f"Embedding 自检需要关注：{embedding_line}")

    document_count = _line_int_after_prefix(status_lines, "索引文档数量：")
    embedding_count = _line_int_after_prefix(status_lines, "向量记录数量：")
    pending_count = _line_int_after_prefix(status_lines, "待索引数量：")
    if not rag_disabled and document_count == 0:
        findings.append("MemoryRAG 索引文档数量为 0，检索不到长期记忆或摘要是预期结果。")
    if not rag_disabled and embedding_count == 0:
        findings.append("MemoryRAG 向量记录数量为 0，语义检索没有可搜索向量。")
    if pending_count is not None and pending_count > 0:
        findings.append(f"MemoryRAG 还有 {pending_count} 条待索引内容，可能需要重建记忆索引后才能被召回。")

    if "暂无 RAG 索引记录" in joined_index:
        findings.append("RAG 索引详情为空，当前没有任何 RAG 文档记录。")

    runtime_values = _root_memory_rag_values(root_lines)
    if runtime_values:
        if _truthy_runtime_value(runtime_values.get("error", "")):
            findings.append("最近普通聊天 MemoryRAG 观测记录了错误，请查看 RootGraph 证据里的 MemoryRAG error。")
        attempted = _truthy_runtime_value(runtime_values.get("attempted", ""))
        results = _runtime_int_value(runtime_values, "results")
        context_chars = _runtime_int_value(runtime_values, "context_chars")
        if attempted and results == 0:
            findings.append("最近普通聊天尝试过 MemoryRAG 召回，但结果数为 0；可换更具体查询或检查索引覆盖范围。")
        if attempted and results > 0 and context_chars == 0:
            findings.append("最近普通聊天有 MemoryRAG 命中，但注入上下文字数为 0，请检查上下文上限或召回格式。")
    elif not rag_disabled:
        findings.append("RootGraph 最近观测中没有 MemoryRAG commit 细节，可能最近一轮普通聊天未进入记忆召回阶段。")

    if recent_errors:
        findings.append("最近错误日志非空，优先核对其中的 embedding、MemoryRAG、rag_documents 或 Ollama 相关错误。")
    if not findings:
        findings.append("未发现明确的 MemoryRAG 硬错误；如果仍检索不到，下一步优先检查查询词是否过宽、相似度阈值和索引覆盖范围。")
    return findings


def recent_error_lines(limit: int = 5) -> list[str]:
    if not ERROR_LOG_PATH.exists():
        return []
    lines = ERROR_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    return [sanitize_text(line) for line in lines[-limit:] if line.strip()]


def format_recent_errors(limit: int = 5) -> str:
    errors = recent_error_lines(max(limit, 200))
    return format_failure_inspection(inspect_failure_lines(errors, window_hours=24))


def clear_error_log() -> str:
    if not ERROR_LOG_PATH.exists():
        return "错误日志不存在。"
    ERROR_LOG_PATH.write_text("", encoding="utf-8")
    return "已清空错误日志。"


async def format_diagnostics(config: AiChatConfig, image_cache_stats: dict[str, int]) -> str:
    chat = await check_chat_api(config)
    vision_provider = str(
        getattr(config, "vision_provider", "ollama") or "ollama"
    ).strip()
    ollama = (
        check_ollama(config)
        if config.enable_vision and vision_provider == "ollama"
        else OllamaStatus(
            CheckResult(
                True,
                "云端提供方已配置，未主动发起远程探针"
                if config.enable_vision
                else "视觉未开启",
            ),
            None,
        )
    )
    chat_route = resolve_chat_completion_route(config)
    vision_model = (
        getattr(config, "vision_cloud_model", "qwen3.7-flash")
        if vision_provider == "aliyun_bailian"
        else config.vision_model
    )
    db_lines = database_status_lines()
    role_lines = role_card_status_lines()
    errors = recent_error_lines(5)
    driver = get_driver()

    lines = [
        "诊断结果：",
        f"机器人：{config.bot_name}",
        f"环境：{driver.env}",
        "",
        f"默认聊天接口：{_configured(chat_route.configured)}",
        f"默认聊天模型：{chat_route.model}",
        f"聊天连通性：{chat.detail}",
        "",
        f"视觉识图：{_on_off(config.enable_vision)}",
        f"视觉提供方：{vision_provider}",
        f"视觉模型：{vision_model}",
        f"视觉服务检查：{ollama.service.detail}",
        f"本地模型存在：{_yes_no(ollama.model_exists) if ollama.model_exists is not None else '未执行（非本地提供方）'}",
        "",
        *db_lines,
        "",
        *role_lines,
        "",
        f"私聊：{_on_off(config.enable_private_chat)}",
        f"群聊：{_on_off(config.enable_group_chat)}",
        f"主动回复：{_on_off(config.enable_group_auto_reply)}",
        f"主人转告：{_on_off(config.enable_owner_notifications)}",
        f"记忆压缩：{_on_off(config.enable_memory_compression)}",
        "",
        f"图片缓存：{image_cache_stats.get('total', 0)} 条",
        f"最近错误：{len(errors)} 条",
    ]
    warnings = config_warnings(config)
    if warnings:
        lines.append("")
        lines.append("警告：")
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines)
