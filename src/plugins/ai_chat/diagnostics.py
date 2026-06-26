import json
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from nonebot import get_driver
from openai import AsyncOpenAI

from .config import AiChatConfig
from .database import DATABASE_PATH, connect, ensure_database
from .memory import memory_stats
from .role_cards import ROLE_CARD_DIR, active_role_card, list_role_cards
from .trials import trial_stats


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
    warnings: list[str] = []
    if not config.bot_owner_qq:
        warnings.append("BOT_OWNER_QQ 未配置，主人命令不可用。")
    if not config.openai_api_key:
        warnings.append("OPENAI_API_KEY 未配置，普通聊天不可用。")
    if not config.openai_model:
        warnings.append("OPENAI_MODEL 为空。")
    if config.enable_vision and not config.vision_model:
        warnings.append("ENABLE_VISION=true 但 VISION_MODEL 为空。")
    if config.summary_keep_recent_messages >= config.max_stored_messages_per_session:
        warnings.append("SUMMARY_KEEP_RECENT_MESSAGES 不小于 MAX_STORED_MESSAGES_PER_SESSION，自动压缩可能难以触发。")
    if config.max_context_messages != config.summary_keep_recent_messages:
        warnings.append("MAX_CONTEXT_MESSAGES 与 SUMMARY_KEEP_RECENT_MESSAGES 不一致，可能产生保留但不可见的原文。")
    if config.gap_scene_summary_1_threshold < config.max_context_messages:
        warnings.append("GAP_SCENE_SUMMARY_1_THRESHOLD 小于 MAX_CONTEXT_MESSAGES，空窗摘要可能过早触发。")
    if config.gap_scene_summary_2_threshold <= config.gap_scene_summary_1_threshold:
        warnings.append("GAP_SCENE_SUMMARY_2_THRESHOLD 不大于第 1 阈值，第 2 条空窗摘要可能无法正常分段。")
    if config.group_auto_reply_threshold < 20:
        warnings.append("GROUP_AUTO_REPLY_THRESHOLD 低于 20，主动回复可能过于频繁。")
    return warnings


def format_config_status(config: AiChatConfig) -> str:
    lines = [
        "配置状态：",
        f"机器人：{config.bot_name}",
        f"主人 QQ：{_configured(config.bot_owner_qq)}",
        f"主人公开称呼：{_configured(config.bot_owner_public_name)}",
        "",
        f"聊天接口：{config.openai_base_url}",
        f"聊天模型：{config.openai_model}",
        f"API Key：{_configured(config.openai_api_key)}",
        f"AI 超时：{config.ai_timeout_seconds} 秒",
        f"温度：{config.ai_temperature}",
        "",
        f"视觉：{_on_off(config.enable_vision)}",
        f"视觉接口：{config.vision_ollama_base_url}",
        f"视觉模型：{config.vision_model}",
        f"视觉超时：{config.vision_timeout_seconds} 秒",
        f"每轮图片：{config.vision_max_images}",
        f"单图大小：{config.vision_max_image_bytes} 字节",
        f"图片缓存 TTL：{config.vision_image_cache_ttl_seconds} 秒",
        f"私聊图片等待：{config.vision_private_image_wait_seconds} 秒",
        "",
        f"私聊：{_on_off(config.enable_private_chat)}",
        f"群聊：{_on_off(config.enable_group_chat)}",
        f"主动回复：{_on_off(config.enable_group_auto_reply)}",
        f"主人转告：{_on_off(config.enable_owner_notifications)}",
        f"记忆压缩：{_on_off(config.enable_memory_compression)}",
        f"上下文消息：{config.max_context_messages}",
        f"每会话原文上限：{config.max_stored_messages_per_session}",
        f"保留最近原文：{config.summary_keep_recent_messages}",
        f"每次压缩条数：{config.summary_batch_messages}",
        f"摘要上下文：{config.max_session_summaries_in_context}",
        f"空窗场景摘要：{_on_off(config.enable_gap_scene_summaries)}",
        f"空窗阈值：>{config.gap_scene_summary_1_threshold} / >{config.gap_scene_summary_2_threshold}",
        f"空窗摘要上下文：{config.max_gap_scene_summaries_in_context}",
        f"手动长期记忆上下文：{_on_off(config.enable_long_term_memory_context)}",
        f"长期记忆上下文：{config.max_long_term_memories_in_context}",
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


async def check_chat_api(config: AiChatConfig) -> CheckResult:
    if not config.openai_api_key:
        return CheckResult(False, "OPENAI_API_KEY 未配置")
    try:
        client = AsyncOpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            timeout=CHAT_TEST_TIMEOUT_SECONDS,
        )
        started = time.monotonic()
        response = await client.chat.completions.create(
            model=config.openai_model,
            messages=[
                {"role": "system", "content": CHAT_TEST_SYSTEM_PROMPT},
                {"role": "user", "content": CHAT_TEST_USER_PROMPT},
            ],
            temperature=0,
        )
        elapsed = time.monotonic() - started
        content = _extract_chat_content(response)
        if not content:
            reason = _chat_finish_reason(response)
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


def format_vision_status(config: AiChatConfig, image_cache_stats: dict[str, int]) -> str:
    status = check_ollama(config) if config.enable_vision else OllamaStatus(CheckResult(False, "视觉未开启"), None)
    lines = [
        "视觉状态：",
        f"视觉识图：{_on_off(config.enable_vision)}",
        f"Ollama 地址：{config.vision_ollama_base_url}",
        f"Ollama 服务：{status.service.detail}",
        f"视觉模型：{config.vision_model}",
        f"模型存在：{_yes_no(status.model_exists) if status.model_exists is not None else '无法检查'}",
        "",
        f"图片缓存：{image_cache_stats.get('total', 0)} 条",
        f"私聊缓存：{image_cache_stats.get('private', 0)} 条",
        f"群聊缓存：{image_cache_stats.get('group', 0)} 条",
        f"缓存 TTL：{config.vision_image_cache_ttl_seconds} 秒",
        f"私聊图片等待：{config.vision_private_image_wait_seconds} 秒",
        f"每轮最多图片：{config.vision_max_images}",
        f"单图大小上限：{config.vision_max_image_bytes} 字节",
    ]
    if config.enable_vision and not status.service.ok:
        lines.extend(
            [
                "",
                "建议：",
                "1. 确认 ollama.exe 正在运行。",
                "2. 确认 OLLAMA_MODELS 指向 D:\\OllamaModels。",
                "3. 避免 ollama app.exe 托盘程序用默认中文路径接管。",
            ]
        )
    elif config.enable_vision and status.service.ok and status.model_exists is False:
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


def recent_error_lines(limit: int = 5) -> list[str]:
    if not ERROR_LOG_PATH.exists():
        return []
    lines = ERROR_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    return [sanitize_text(line) for line in lines[-limit:] if line.strip()]


def format_recent_errors(limit: int = 5) -> str:
    errors = recent_error_lines(limit)
    if not errors:
        return "最近错误：\n暂无。"
    lines = ["最近错误："]
    lines.extend(f"{index}. {line}" for index, line in enumerate(errors, 1))
    return "\n".join(lines)


def clear_error_log() -> str:
    if not ERROR_LOG_PATH.exists():
        return "错误日志不存在。"
    ERROR_LOG_PATH.write_text("", encoding="utf-8")
    return "已清空错误日志。"


async def format_diagnostics(config: AiChatConfig, image_cache_stats: dict[str, int]) -> str:
    chat = await check_chat_api(config)
    ollama = check_ollama(config) if config.enable_vision else OllamaStatus(CheckResult(False, "视觉未开启"), None)
    db_lines = database_status_lines()
    role_lines = role_card_status_lines()
    errors = recent_error_lines(5)
    driver = get_driver()

    lines = [
        "诊断结果：",
        f"机器人：{config.bot_name}",
        f"环境：{driver.env}",
        "",
        f"聊天接口：{_configured(config.openai_api_key)}",
        f"聊天模型：{config.openai_model}",
        f"聊天连通性：{chat.detail}",
        "",
        f"视觉识图：{_on_off(config.enable_vision)}",
        f"Ollama：{ollama.service.detail}",
        f"视觉模型：{config.vision_model}",
        f"模型存在：{_yes_no(ollama.model_exists) if ollama.model_exists is not None else '无法检查'}",
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
