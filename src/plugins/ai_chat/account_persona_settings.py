"""Account-scoped owner-console views of current business configuration.

Account IDs are intentionally visible only in this local owner view. The
sanitized deployment preflight remains separate. No database is opened and
no model, TTS service or network request is started here.
"""
from __future__ import annotations

import io
from pathlib import Path
import re
import wave

from .aliyun_bailian_vision import (
    ALIYUN_BAILIAN_VISION_MODEL, ALIYUN_BAILIAN_REQUEST_TIMEOUT_SECONDS,
    _normalized_configuration,
)
from .completion_routes import resolve_chat_completion_route, resolve_chat_reasoning_effort, resolve_summary_completion_route
from .encyclopedia_capabilities import encyclopedia_policy_detail, resolve_encyclopedia_policy
from .main_agent_observability import redacted_base_url
from .persona_capabilities import resolve_persona_voice_route
from .persona_maintenance import available_bound_role_card_keys
from .memory_maintenance import MemoryMaintenanceError, resolve_memory_maintenance_scope
from .persona_scope import resolve_conversation_scope
from .scene_actor_profile import build_scene_actor_profile
from .sticker_library import ALLOWED_PERSONA_KEYS
from .vision_routes import persona_vision_provider, resolve_vision_provider_route, resolve_private_image_wait_seconds


PROJECT_ROOT = Path(__file__).resolve().parents[3]
VOICE_SAMPLE_ROOT = PROJECT_ROOT / "voice-samples" / "reference" / "zh"
MAX_VOICE_SAMPLE_BYTES = 20 * 1024 * 1024
VOICE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}")
VOICE_SAMPLE_ACTION_HEADER = "persona-voice-sample-v1"


def _scope(config, binding, available):
    return resolve_conversation_scope(
        config.persona_routing, bot_self_id=binding.bot_self_id, user_id="",
        chat_type="private", legacy_session_key="private:",
        available_role_card_keys=available,
    )


def _sample_path(voice: str) -> Path:
    if not VOICE_ID_PATTERN.fullmatch(voice):
        raise ValueError("voice_sample_unavailable")
    root = VOICE_SAMPLE_ROOT.resolve(strict=True)
    # Do not follow links/junctions in the configured reference tree.
    for part in (VOICE_SAMPLE_ROOT, *VOICE_SAMPLE_ROOT.parents):
        if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
            raise ValueError("voice_sample_unavailable")
        if part == PROJECT_ROOT:
            break
    path = VOICE_SAMPLE_ROOT / f"{voice}.wav"
    if path.is_symlink() or path.resolve(strict=True).parent != root:
        raise ValueError("voice_sample_unavailable")
    if not path.is_file() or not 44 < path.stat().st_size <= MAX_VOICE_SAMPLE_BYTES:
        raise ValueError("voice_sample_unavailable")
    return path


def _validate_wave(reader):
    if (reader.getcomptype() != "NONE" or reader.getnchannels() not in {1, 2}
            or reader.getsampwidth() not in {1, 2, 3, 4}
            or not 8000 <= reader.getframerate() <= 192000
            or not 0 < reader.getnframes() / reader.getframerate() <= 120):
        raise ValueError("voice_sample_unavailable")


def voice_sample_available(voice: str) -> bool:
    try:
        with wave.open(str(_sample_path(voice)), "rb") as reader:
            _validate_wave(reader)
            expected = reader.getnframes() * reader.getnchannels() * reader.getsampwidth()
            if len(reader.readframes(reader.getnframes())) != expected:
                return False
        return True
    except (OSError, ValueError, EOFError, wave.Error):
        return False


def read_account_voice_sample(config, bot_self_id: str) -> bytes:
    binding = next((b for b in config.persona_routing.bindings if b.bot_self_id == bot_self_id), None)
    if binding is None:
        raise ValueError("voice_sample_unavailable")
    scope = _scope(config, binding, available_bound_role_card_keys(config.persona_routing))
    route = resolve_persona_voice_route(config, scope)
    if not route.supported or not route.voice:
        raise ValueError("voice_sample_unavailable")
    with _sample_path(route.voice).open("rb") as file:
        content = file.read(MAX_VOICE_SAMPLE_BYTES + 1)
    if len(content) > MAX_VOICE_SAMPLE_BYTES:
        raise ValueError("voice_sample_unavailable")
    with wave.open(io.BytesIO(content), "rb") as reader:
        _validate_wave(reader)
        expected = reader.getnframes() * reader.getnchannels() * reader.getsampwidth()
        if len(reader.readframes(reader.getnframes())) != expected:
            raise ValueError("voice_sample_unavailable")
    return content


def _model(model="", *, provider="", source="", base_url="", api_key="", timeout=0,
           configured=False, errors=()):
    return {"model_name": model, "provider": provider, "source": source,
            "base_url_redacted": redacted_base_url(base_url),
            "api_key_configured": bool(api_key), "timeout_seconds": timeout,
            "configured": configured, "errors": list(errors)}


def _completion(config, card, completion_route="auto", reasoning_effort=None):
    try:
        route = resolve_chat_completion_route(config, card, completion_route=completion_route)
        model = _model(route.model, provider=route.provider,
                      source="PERSONA_LLM_*" if route.source == "persona" else "AIKE_LLM_*",
                      base_url=route.base_url, api_key=route.api_key, timeout=route.timeout_seconds,
                      configured=route.configured, errors=route.configuration_errors)
        effort = resolve_chat_reasoning_effort(config, route, override=reasoning_effort)
        model.update(reasoning_effort=effort, reasoning_effort_source=(
            "SceneHub 演员配置" if reasoning_effort is not None
            else "AIKE_LLM_REASONING_EFFORT" if effort is not None else "服务端默认"
        ))
        return model
    except (RuntimeError, ValueError):
        return _model(source="PERSONA_LLM_*", errors=["incomplete_chat_route"])


def _vision(config, scope):
    try:
        route = resolve_vision_provider_route(config, scope.role_card_key)
        if route.provider == "aliyun_bailian":
            errors = []
            try:
                _normalized_configuration(config)
            except ValueError:
                errors.append("incomplete_bailian_vision")
            except RuntimeError:
                errors.append("incomplete_bailian_vision")
            return _model(
                getattr(config, "vision_cloud_model", ALIYUN_BAILIAN_VISION_MODEL),
                provider="aliyun_bailian", source="VISION_CLOUD_MODEL / ALIYUN_BAILIAN_*",
                base_url=config.aliyun_bailian_base_url, api_key=config.aliyun_bailian_api_key,
                timeout=ALIYUN_BAILIAN_REQUEST_TIMEOUT_SECONDS,
                configured=not errors, errors=errors,
            )
        model = _model(route.model, provider=route.provider, source="PERSONA_VISION_*",
                      base_url=route.base_url, api_key=route.api_key, timeout=route.timeout_seconds,
                      configured=True)
        model["max_tokens"] = route.max_tokens
        if route.reasoning_effort is not None:
            model.update(reasoning_effort=route.reasoning_effort,
                         reasoning_effort_source="PERSONA_VISION_REASONING_EFFORT")
        return model
    except (RuntimeError, ValueError):
        return _model(config.persona_vision_model, provider=persona_vision_provider(
                          config.persona_vision_model, config.persona_vision_base_url),
                      source="PERSONA_VISION_*", errors=["incomplete_persona_vision"])


def _capability(key, label, enabled, detail, *, supported=True, valid=True, configured=True):
    state = ("blocked" if not valid else "unsupported" if not supported
             else "disabled" if not enabled else "incomplete" if not configured else "enabled")
    return {"key": key, "label": label, "state": state, "detail": detail}


def build_account_persona_profiles(config) -> list[dict]:
    # The launcher imports these view helpers before serving requests. Keep
    # the classifier's model SDK out of that import-only path.
    from .sticker_classifier import RemoteStickerClassifierSettings, classifier_settings_status

    settings = config.persona_routing
    available = available_bound_role_card_keys(settings)
    scene_accounts = {"aike": config.shared_scene_aike_bot_id, "linyin": config.shared_scene_linyin_bot_id}
    scene_bindings_ready = len(set(scene_accounts.values()) - {""}) == 2
    for speaker, account in scene_accounts.items():
        actor_binding = next((item for item in settings.bindings if item.bot_self_id == account), None)
        if (actor_binding is None or actor_binding.persona_id != speaker
                or _scope(config, actor_binding, available).configuration_error):
            scene_bindings_ready = False
    rows = []
    for index, binding in enumerate(settings.bindings, 1):
        scope = _scope(config, binding, available)
        valid = not scope.configuration_error
        ordinary_route = "auto" if scope.routing_v2_active else "legacy"
        chat = _completion(config, scope.role_card_key, ordinary_route) if valid else _model(errors=["invalid_persona_scope"])
        vision = _vision(config, scope) if valid else _model(errors=["invalid_persona_scope"])
        voice = resolve_persona_voice_route(config, scope)
        sample = voice_sample_available(voice.voice) if voice.voice else False
        if not valid:
            memory_path, storage = "", "unavailable"
        elif scope.memory_v2_active:
            memory_path, storage = f"data/persona-memory/{scope.persona_id}.db", "persona_database"
        elif scope.routing_v2_active:
            memory_path, storage = "", "process_memory"
        else:
            memory_path, storage = "data/chatbot.db", "legacy_database"
        persistent = storage in {"persona_database", "legacy_database"}
        try:
            maintenance_scope = resolve_memory_maintenance_scope(config, binding.bot_self_id).as_dict()
        except MemoryMaintenanceError:
            maintenance_scope = None
        scene_speakers = [speaker for speaker, account in scene_accounts.items() if account and account == binding.bot_self_id]
        scene_assigned = bool(scene_speakers)
        scene_ready = bool(scene_assigned and config.shared_scene_group_id and config.bot_owner_qq
                           and scene_bindings_ready)
        scene_profile = build_scene_actor_profile(binding.persona_id) if scene_speakers == [binding.persona_id] and valid else None
        scene_model = _completion(config, scope.role_card_key, scene_profile.completion_route,
                                  reasoning_effort=scene_profile.reasoning_effort) if scene_profile else _model()
        encyclopedia = resolve_encyclopedia_policy(config, scope.role_card_key, provider=chat["provider"])
        encyclopedia_detail = encyclopedia_policy_detail(encyclopedia)
        if encyclopedia.mode == "prefetch":
            encyclopedia_detail += (
                f" 资料预判模型：{config.aike_llm_model}（AIKE_LLM_*）；"
                f"预判 / 查询总超时：{config.encyclopedia_plan_timeout_seconds} / {config.encyclopedia_lookup_timeout_seconds} 秒。"
            )
        sticker_supported = binding.role_card_key in ALLOWED_PERSONA_KEYS
        classifier_supported = sticker_supported
        classifier_configured = classifier_settings_status(RemoteStickerClassifierSettings(
            enabled=True, api_key=config.sticker_classifier_api_key,
            base_url=config.sticker_classifier_base_url, model=config.sticker_classifier_model,
            timeout_seconds=config.sticker_classifier_timeout_seconds,
            max_input_chars=config.sticker_classifier_max_input_chars,
        )) == "ready"
        capabilities = [
            _capability("encyclopedia", "百科查询", encyclopedia.enabled,
                        encyclopedia_detail, supported=encyclopedia.supported,
                        configured=encyclopedia.planner_ready, valid=valid),
            _capability("stickers", "表情包", config.enable_local_stickers,
                        "使用当前角色专属及明确批准的共用表情；爱可、凛音共用素材，发送频率按账号和会话独立计算。" if sticker_supported
                        else "当前角色未接入表情库。", supported=sticker_supported, valid=valid),
            _capability("sticker_attachments", "聊天自动附带表情", config.enable_chat_sticker_attachments and config.enable_local_stickers,
                        "主人私聊成功文本回复后附图；仅使用正式库可用组合，受冷却、回复间隔、频率和意图匹配限制。",
                        supported=classifier_supported, valid=valid,
                        configured=config.enable_remote_sticker_classifier and classifier_configured),
            _capability("sticker_classifier", "表情意图模型", config.enable_remote_sticker_classifier,
                        "成功文本回复后异步判断；普通聊天和 ChatGraph 使用同一入口，按账号及人格隔离。",
                        supported=classifier_supported, valid=valid, configured=classifier_configured),
            _capability("sticker_shadow", "表情意图观察", config.enable_chat_sticker_intent_shadow,
                        "观察聊天表情意图，不等同于实际发送表情。", supported=sticker_supported, valid=valid),
            _capability("vision", "图片理解", config.enable_vision,
                        "独立视觉线路提取图片事实，再由当前聊天模型回复。", valid=valid, configured=vision["configured"]),
            _capability("tts", "语音回复", config.enable_tts and (not scope.routing_v2_active or config.enable_linyin_tts),
                        "当前角色音色；参考音频可独立试听。", supported=voice.supported, valid=valid,
                        configured=bool(voice.voice and voice.emotion and sample)),
            _capability("memory_rag", "记忆检索", config.enable_memory_rag,
                        "在当前人格的记忆库中检索，继续区分群聊和私聊受众。", supported=persistent, valid=valid),
            _capability("memory_injection", "聊天记忆检索注入", config.enable_memory_rag and config.memory_rag_inject_in_chat,
                        "检索结果注入普通聊天；群私聊边界保持现有规则。", supported=persistent, valid=valid),
            _capability("compression", "记忆压缩", config.enable_memory_compression,
                        "读取当前人格库并使用共享摘要模型。", supported=persistent, valid=valid),
            _capability("private_chat", "私聊", config.enable_private_chat, "沿用主人识别、白名单和访问限制。", valid=valid),
            _capability("group_chat", "群聊响应", config.enable_group_chat, "沿用群白名单及触发规则。", valid=valid),
            _capability("group_auto_reply", "普通群自动回复", config.enable_group_auto_reply and config.enable_group_chat,
                        "V2 普通群自动回复当前未接入；与 SceneHub 分开。" if scope.routing_v2_active
                        else "沿用默认线路的群触发阈值和冷却。", supported=not scope.routing_v2_active, valid=valid),
            _capability("scene", "共享场景", config.enable_shared_scene_hub,
                        "仅现有特定群及成员规则；主人触发连续性和主动互动维持各自边界。" if scene_bindings_ready
                        else "场景演员账号与固定人格绑定不完整或不一致。",
                        supported=scene_assigned, valid=valid, configured=scene_ready and scene_model["configured"]),
            _capability("weather", "聊天天气", config.enable_chat_weather, "沿用当前天气策略。", valid=valid),
            _capability("image_generation", "生成图片", config.enable_image_gen,
                        "主人私聊与现有确认、频率限制；独立于视觉理解。", valid=valid,
                        configured=bool(config.image_gen_api_key and config.image_gen_base_url)),
        ]
        summary = resolve_summary_completion_route(config)
        rows.append({
            "account_label": f"账号 {index}", "bot_self_id": binding.bot_self_id,
            "persona_id": binding.persona_id,
            "persona_name": {"aike": "爱可", "linyin": "凛音"}.get(binding.persona_id, binding.persona_id),
            "role_card_key": binding.role_card_key, "role_card_available": binding.role_card_key in available,
            "ready": valid and chat["configured"], "errors": scope.configuration_error.split(",") if not valid else chat["errors"],
            "chat_model": chat, "vision_model": vision,
            "voice": {"voice_id": voice.voice, "emotion": voice.emotion, "source": voice.source,
                      "enabled": voice.enabled, "sample_available": sample, "sample_kind": "reference",
                      "trim_trailing_noise": voice.trim_trailing_noise,
                      "service_url_redacted": redacted_base_url(config.tts_service_url),
                      "timeout_seconds": config.tts_timeout_seconds, "max_chars": config.tts_max_chars,
                      "max_total_seconds": config.tts_max_total_seconds, "cooldown_seconds": config.tts_cooldown_seconds},
            "memory": {"mode": scope.runtime_mode, "storage": storage, "database": memory_path,
                       "maintenance_scope": maintenance_scope,
                       "file_exists": (PROJECT_ROOT / memory_path).is_file() if memory_path else False,
                       "health_checked": False,
                       "session_namespace": f"persona:{scope.persona_id}:" if scope.routing_v2_active else "private:/group:" if valid else "",
                       "summary_model": _model(summary.model, provider=summary.provider, source="SUMMARY_LLM_*",
                                               base_url=summary.base_url, api_key=summary.api_key,
                                               timeout=summary.timeout_seconds, configured=summary.configured,
                                               errors=summary.configuration_errors),
                       "embedding_model": config.memory_rag_embedding_model},
            "scene": {"assigned": scene_assigned, "actor_model": scene_model,
                      "director_model": config.scene_director_model,
                      "style_examples_status": scene_profile.style_examples.status if scene_profile else "not_applicable",
                      "ordinary_world_card_injection": bool(valid and scope.routing_v2_active)},
            "capabilities": capabilities,
            "parameters": {"temperature": config.ai_temperature,
                           "vision_private_image_wait_seconds": resolve_private_image_wait_seconds(config, scope.role_card_key) if valid else 0,
                           "memory_rag_top_k": config.memory_rag_top_k,
                           "memory_rag_max_context_chars": config.memory_rag_max_context_chars,
                           "sticker_cooldown_seconds": config.chat_sticker_cooldown_seconds,
                           "sticker_max_per_hour": config.chat_sticker_max_per_hour,
                           "sticker_classifier_model": config.sticker_classifier_model if classifier_supported else "",
                           "image_generation_model": config.image_gen_model,
                           "image_edit_model": config.image_edit_model,
                           "weather_mode": config.chat_weather_mode},
        })
    return rows
