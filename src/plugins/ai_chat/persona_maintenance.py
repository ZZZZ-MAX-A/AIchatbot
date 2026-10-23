"""Fixed-account binding checks and sanitized read-only maintenance evidence.

No Bot, database, model SDK or network access. Role-card files are validated
locally; their contents, titles and account identifiers are never reported.
"""
from __future__ import annotations

from .completion_routes import resolve_chat_completion_route
from .persona_scope import PersonaRoutingSettings, resolve_conversation_scope
from .role_cards import role_card_by_key


FIXED_PERSONA_MESSAGE = "当前账号使用固定绑定角色卡，不支持在聊天中切换；绑定变更请通过部署配置维护。"
INVALID_PERSONA_MESSAGE = "当前账号的人格绑定或记忆配置异常，本次没有读取或修改任何角色的记忆。"


def available_bound_role_card_keys(settings: PersonaRoutingSettings) -> frozenset[str]:
    return frozenset(
        binding.role_card_key for binding in settings.bindings
        if role_card_by_key(binding.role_card_key) is not None
    )


def build_persona_binding_report(config, *, available_role_card_keys=None) -> dict:
    settings = getattr(config, "persona_routing", PersonaRoutingSettings())
    available = (available_bound_role_card_keys(settings)
                 if available_role_card_keys is None else available_role_card_keys)
    errors = list(settings.binding_errors)
    if not settings.bindings:
        errors.append("missing_persona_bindings")
    bound_accounts = {item.bot_self_id for item in settings.bindings}
    if (settings.routing_v2_bot_ids | settings.memory_v2_bot_ids) - bound_accounts:
        errors.append("unbound_allowlisted_account")
    rows = []
    for index, binding in enumerate(settings.bindings, 1):
        scope = resolve_conversation_scope(
            settings, bot_self_id=binding.bot_self_id, user_id="",
            chat_type="private", legacy_session_key="private:",
            available_role_card_keys=available,
        )
        row_errors = scope.configuration_error.split(",") if scope.configuration_error else []
        model = ""
        route_source = "unavailable"
        try:
            if scope.configuration_error:
                raise ValueError("invalid_persona_scope")
            route = resolve_chat_completion_route(
                config, scope.role_card_key,
                completion_route="auto" if scope.routing_v2_active else "legacy",
            )
            model, route_source = route.model, route.source
            if not route.configured:
                row_errors.append("incomplete_chat_route")
        except (RuntimeError, ValueError, TypeError):
            if not scope.configuration_error:
                row_errors.append("incomplete_chat_route")
        rows.append({
            "account_label": f"账号 {index}",
            "persona_id": binding.persona_id,
            "role_card_key": binding.role_card_key,
            "role_card_available": binding.role_card_key in available,
            "chat_model": model,
            "chat_route": route_source,
            "memory_mode": scope.runtime_mode,
            "memory_storage": "persona_database" if scope.memory_v2_active
            else "process_memory" if scope.routing_v2_active else "legacy_database"
            if not scope.configuration_error else "unavailable",
            "ready": not row_errors,
            "errors": row_errors,
        })
    return {"fixed_binding": True, "ready": not errors and all(row["ready"] for row in rows),
            "errors": errors, "rows": rows}


def resolve_memory_session_scope(config, session_key: str):
    """Revalidate stored approval/session targets against current bindings.

    The immutable session key selects a namespace. A stale approval cannot
    reinterpret a V2 target as the default DB after configuration changes.
    """
    settings = config.persona_routing
    persona_id = settings.legacy_persona_id
    legacy_key = session_key
    if session_key.startswith("persona:"):
        parts = session_key.split(":", 2)
        if len(parts) != 3:
            raise RuntimeError("invalid_persona_memory_scope")
        persona_id, legacy_key = parts[1:]
    parts = legacy_key.split(":", 1)
    if len(parts) != 2 or parts[0] not in {"private", "group"} or not parts[1].isdigit():
        raise RuntimeError("invalid_persona_memory_scope")
    candidates = [item for item in settings.bindings if item.persona_id == persona_id]
    if not candidates:
        raise RuntimeError("invalid_persona_memory_scope")
    for binding in candidates:
        available = frozenset({binding.role_card_key}) if role_card_by_key(binding.role_card_key) else frozenset()
        scope = resolve_conversation_scope(
            settings, bot_self_id=binding.bot_self_id, user_id=parts[1],
            chat_type=parts[0], group_id=parts[1] if parts[0] == "group" else "",
            legacy_session_key=legacy_key, available_role_card_keys=available,
        )
        if not scope.configuration_error and scope.runtime_session_key == session_key:
            if scope.routing_v2_active and not scope.memory_v2_active:
                raise RuntimeError("persona_persistent_memory_unavailable")
            return scope
    raise RuntimeError("invalid_persona_memory_scope")
