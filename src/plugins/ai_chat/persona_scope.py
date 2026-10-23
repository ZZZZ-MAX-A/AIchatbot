from __future__ import annotations

import re
from dataclasses import dataclass, field


PERSONA_V2_FOUNDATION_VERSION = 3
PERSONA_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
BOT_SELF_ID_PATTERN = re.compile(r"^[0-9]{5,20}$")


@dataclass(frozen=True)
class PersonaBinding:
    bot_self_id: str
    persona_id: str
    role_card_key: str


@dataclass(frozen=True)
class ParsedPersonaBindings:
    bindings: tuple[PersonaBinding, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class PersonaRoutingSettings:
    routing_v2_enabled: bool = False
    memory_v2_enabled: bool = False
    routing_v2_bot_ids: frozenset[str] = field(default_factory=frozenset)
    memory_v2_bot_ids: frozenset[str] = field(default_factory=frozenset)
    legacy_persona_id: str = "aike"
    legacy_role_card_key: str = "aike"
    bindings: tuple[PersonaBinding, ...] = ()
    binding_errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConversationScope:
    bot_self_id: str
    persona_id: str
    role_card_key: str
    chat_type: str
    peer_id: str
    group_id: str
    legacy_session_key: str
    runtime_session_key: str
    binding_source: str
    runtime_mode: str
    routing_v2_requested: bool
    routing_v2_active: bool
    memory_v2_requested: bool
    memory_v2_active: bool
    configuration_error: str = ""

    def as_artifact(self) -> dict[str, object]:
        return {
            "foundation_version": PERSONA_V2_FOUNDATION_VERSION,
            "bot_self_id": self.bot_self_id,
            "persona_id": self.persona_id,
            "role_card_key": self.role_card_key,
            "chat_type": self.chat_type,
            "binding_source": self.binding_source,
            "runtime_mode": self.runtime_mode,
            "legacy_session_key": self.legacy_session_key,
            "legacy_session_key_preserved": True,
            "runtime_session_key": self.runtime_session_key,
            "routing_v2_requested": self.routing_v2_requested,
            "routing_v2_active": self.routing_v2_active,
            "memory_v2_requested": self.memory_v2_requested,
            "memory_v2_active": self.memory_v2_active,
            "configuration_error": self.configuration_error,
        }


def valid_persona_id(value: str) -> bool:
    return PERSONA_ID_PATTERN.fullmatch(value.strip()) is not None


def valid_role_card_key(value: str) -> bool:
    normalized = value.strip()
    return bool(
        normalized
        and len(normalized) <= 128
        and "/" not in normalized
        and "\\" not in normalized
        and normalized not in {".", ".."}
    )


def parse_persona_bindings(raw_value: str) -> ParsedPersonaBindings:
    """Parse ``bot_self_id=persona_id:role_card_key`` entries.

    Entries are separated with semicolons. Invalid or duplicate entries fail
    closed: they are reported and omitted instead of selecting a persona.
    """

    by_bot: dict[str, PersonaBinding] = {}
    duplicate_bot_ids: set[str] = set()
    errors: list[str] = []
    entries = [item.strip() for item in raw_value.split(";") if item.strip()]
    for index, entry in enumerate(entries, start=1):
        if "=" not in entry:
            errors.append(f"entry_{index}:missing_equals")
            continue
        raw_bot_id, raw_target = entry.split("=", 1)
        bot_self_id = raw_bot_id.strip()
        target_parts = [part.strip() for part in raw_target.split(":", 1)]
        persona_id = target_parts[0] if target_parts else ""
        role_card_key = target_parts[1] if len(target_parts) > 1 else persona_id
        if BOT_SELF_ID_PATTERN.fullmatch(bot_self_id) is None:
            errors.append(f"entry_{index}:invalid_bot_self_id")
            continue
        if not valid_persona_id(persona_id):
            errors.append(f"entry_{index}:invalid_persona_id")
            continue
        if not valid_role_card_key(role_card_key):
            errors.append(f"entry_{index}:invalid_role_card_key")
            continue
        if bot_self_id in by_bot or bot_self_id in duplicate_bot_ids:
            by_bot.pop(bot_self_id, None)
            duplicate_bot_ids.add(bot_self_id)
            errors.append(f"entry_{index}:duplicate_bot_self_id")
            continue
        by_bot[bot_self_id] = PersonaBinding(
            bot_self_id=bot_self_id,
            persona_id=persona_id,
            role_card_key=role_card_key,
        )
    persona_cards: dict[str, str] = {}
    for binding in by_bot.values():
        previous = persona_cards.setdefault(binding.persona_id, binding.role_card_key)
        if previous != binding.role_card_key:
            errors.append("conflicting_persona_role_cards")
            break
    return ParsedPersonaBindings(
        bindings=tuple(by_bot[key] for key in sorted(by_bot)),
        errors=tuple(errors),
    )


def build_persona_routing_settings(
    *,
    routing_v2_enabled: bool,
    memory_v2_enabled: bool,
    routing_v2_bot_ids: frozenset[str],
    memory_v2_bot_ids: frozenset[str],
    legacy_persona_id: str,
    legacy_role_card_key: str,
    raw_bindings: str,
) -> PersonaRoutingSettings:
    parsed = parse_persona_bindings(raw_bindings)
    normalized_legacy_persona_id = legacy_persona_id.strip()
    settings_errors = list(parsed.errors)
    if not valid_persona_id(normalized_legacy_persona_id):
        settings_errors.append("invalid_legacy_persona_id")
        normalized_legacy_persona_id = "aike"
    normalized_legacy_role_card_key = legacy_role_card_key.strip()
    if not valid_role_card_key(normalized_legacy_role_card_key):
        settings_errors.append("invalid_legacy_role_card_key")
        normalized_legacy_role_card_key = normalized_legacy_persona_id
    return PersonaRoutingSettings(
        routing_v2_enabled=bool(routing_v2_enabled),
        memory_v2_enabled=bool(memory_v2_enabled),
        routing_v2_bot_ids=frozenset(
            item.strip() for item in routing_v2_bot_ids if item.strip()
        ),
        memory_v2_bot_ids=frozenset(
            item.strip() for item in memory_v2_bot_ids if item.strip()
        ),
        legacy_persona_id=normalized_legacy_persona_id,
        legacy_role_card_key=normalized_legacy_role_card_key,
        bindings=parsed.bindings,
        binding_errors=tuple(settings_errors),
    )


def resolve_conversation_scope(
    settings: PersonaRoutingSettings,
    *,
    bot_self_id: str,
    user_id: str,
    chat_type: str,
    group_id: str = "",
    legacy_session_key: str,
    available_role_card_keys: frozenset[str] | None = None,
) -> ConversationScope:
    """Resolve a fixed account identity independently of its storage mode.

    Only the explicitly bound legacy identity may use the existing default DB
    and session keys. Other identities require V2; invalid scopes never borrow
    another account's role card or persistence.
    """

    normalized_bot_id = bot_self_id.strip()
    normalized_chat_type = "group" if chat_type == "group" else "private"
    normalized_group_id = group_id.strip() if normalized_chat_type == "group" else ""
    peer_id = normalized_group_id if normalized_chat_type == "group" else user_id.strip()
    binding = next(
        (
            item
            for item in settings.bindings
            if item.bot_self_id == normalized_bot_id
        ),
        None,
    )
    routing_requested = bool(
        settings.routing_v2_enabled
        and normalized_bot_id
        and normalized_bot_id in settings.routing_v2_bot_ids
    )
    memory_requested = bool(
        settings.memory_v2_enabled
        and normalized_bot_id
        and normalized_bot_id in settings.memory_v2_bot_ids
    )

    errors: list[str] = []
    if binding is None:
        errors.append("missing_persona_binding")
    if memory_requested and not routing_requested:
        errors.append("memory_v2_requires_routing_v2")
    if settings.binding_errors:
        errors.append("persona_binding_parse_errors")
    if binding is not None and not routing_requested and (
        binding.persona_id != settings.legacy_persona_id
        or binding.role_card_key != settings.legacy_role_card_key
    ):
        errors.append("nonlegacy_persona_requires_routing_v2")
    if (
        binding is not None
        and available_role_card_keys is not None
        and binding.role_card_key not in available_role_card_keys
    ):
        errors.append("missing_role_card")

    routing_active = bool(routing_requested and binding is not None and not errors)
    memory_active = bool(memory_requested and routing_active)
    persona_id = binding.persona_id if binding is not None else ""
    role_card_key = (
        binding.role_card_key
        if binding is not None
        else ""
    )
    runtime_session_key = (
        f"persona:{persona_id}:{legacy_session_key}"
        if routing_active
        else legacy_session_key
    )
    return ConversationScope(
        bot_self_id=normalized_bot_id,
        persona_id=persona_id,
        role_card_key=role_card_key,
        chat_type=normalized_chat_type,
        peer_id=peer_id,
        group_id=normalized_group_id,
        legacy_session_key=legacy_session_key,
        runtime_session_key=runtime_session_key,
        binding_source="explicit" if binding is not None else "unbound",
        runtime_mode=(
            "invalid"
            if errors
            else "persona_v2_persistent"
            if memory_active
            else "persona_v2_ephemeral"
            if routing_active
            else "legacy"
        ),
        routing_v2_requested=routing_requested,
        routing_v2_active=routing_active,
        memory_v2_requested=memory_requested,
        memory_v2_active=memory_active,
        configuration_error=",".join(errors),
    )
