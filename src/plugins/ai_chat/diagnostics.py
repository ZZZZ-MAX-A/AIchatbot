import json
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from nonebot import get_driver
from openai import AsyncOpenAI

from .config import AiChatConfig
from .database import DATABASE_PATH, connect, ensure_database
from .failure_diagnostics import format_failure_inspection, inspect_failure_lines
from .memory import memory_stats
from .role_cards import ROLE_CARD_DIR, active_role_card, list_role_cards
from .trials import trial_stats
from .vision import VisionInferenceCheck, check_vision_inference


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
    warnings: list[str] = []
    chat_api_key = (
        config.chat_llm_api_key
        if config.enable_chat_graph_runtime
        else config.openai_api_key
    )
    chat_model = (
        config.chat_llm_model
        if config.enable_chat_graph_runtime
        else config.openai_model
    )
    if not config.bot_owner_qq:
        warnings.append("BOT_OWNER_QQ 未配置，主人命令不可用。")
    if not chat_api_key:
        warnings.append("当前聊天运行链路的 API Key 未配置，普通聊天不可用。")
    if not chat_model:
        warnings.append("当前聊天运行链路的模型为空。")
    if (
        config.enable_main_agent
        and config.main_agent_use_llm
        and not config.main_llm_api_key
    ):
        warnings.append("MainAgent 已启用 Main LLM，但 MAIN_LLM_API_KEY 未配置。")
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
    use_chat_graph = config.enable_chat_graph_runtime
    chat_runtime = "ChatGraph/RootGraph" if use_chat_graph else "兼容聊天链路"
    chat_api_key = config.chat_llm_api_key if use_chat_graph else config.openai_api_key
    chat_base_url = config.chat_llm_base_url if use_chat_graph else config.openai_base_url
    chat_model = config.chat_llm_model if use_chat_graph else config.openai_model
    chat_timeout = (
        config.chat_llm_timeout_seconds if use_chat_graph else config.ai_timeout_seconds
    )
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
        "聊天模型：",
        f"Chat LLM：{_configured(chat_api_key and chat_model)}",
        f"接口：{_redacted_url(chat_base_url)}",
        f"模型：{chat_model or '未配置'}",
        f"Key：{_configured(chat_api_key)}",
        f"超时：{chat_timeout} 秒",
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
        f"服务地址：{_redacted_url(config.vision_ollama_base_url)}",
        f"地址范围：{_service_address_scope(config.vision_ollama_base_url)}",
        f"模型：{config.vision_model or '未配置'}",
        f"超时：{config.vision_timeout_seconds} 秒",
        f"上下文：{config.vision_num_ctx}",
        f"每轮图片：{config.vision_max_images}",
        f"单图上限：{_human_bytes(config.vision_max_image_bytes)}",
        f"缓存 TTL：{config.vision_image_cache_ttl_seconds} 秒",
        f"私聊图片等待：{config.vision_private_image_wait_seconds} 秒",
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
    status = check_ollama(config) if config.enable_vision else OllamaStatus(CheckResult(False, "视觉未开启"), None)
    lines = [
        "视觉状态：",
        f"视觉识图：{_on_off(config.enable_vision)}",
        f"Ollama 地址：{config.vision_ollama_base_url}",
        f"Ollama 服务：{status.service.detail}",
        f"视觉模型：{config.vision_model}",
        f"模型存在：{_yes_no(status.model_exists) if status.model_exists is not None else '无法检查'}",
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
    inference = _vision_inference_check_for_status(config, status)
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
    elif config.enable_vision and not status.service.ok:
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
    if vision_disabled:
        findings.append("视觉功能当前关闭，图片不会进入识图推理。")

    if not vision_disabled:
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
            if "低质量重复内容" in inference_line and "模型存在：是" in joined_vision:
                model_line = _first_line_with_prefix(vision_lines, "视觉模型：")
                model = model_line.partition("：")[2].strip()
                findings.extend(vision_runner_recovery_suggestion(model))

    if _vision_detail_metric_positive(root_lines, "errors"):
        findings.append("最近 RootGraph 视觉观测里出现过识图错误计数，请查看 RootGraph 证据。")
    if _vision_detail_metric_positive(root_lines, "low_quality"):
        findings.append("最近 RootGraph 视觉观测里出现过低质量识图输出，请查看 RootGraph 证据。")
    if recent_errors:
        findings.append("最近错误日志非空，优先核对其中的 Ollama/vision/image 相关错误。")
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
