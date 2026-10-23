"""One policy resolver for runtime and the account settings view."""
from __future__ import annotations

from dataclasses import dataclass

from .completion_routes import resolve_chat_completion_route


@dataclass(frozen=True)
class EncyclopediaPolicy:
    enabled: bool
    supported: bool
    mode: str
    automatic: bool
    planner_ready: bool


def resolve_encyclopedia_policy(config, role_card_key: str, *, provider: str = "openai") -> EncyclopediaPolicy:
    legacy_card = getattr(getattr(config, "persona_routing", None), "legacy_role_card_key", "aike") or "aike"
    role = role_card_key.strip() or legacy_card
    global_enabled = bool(getattr(config, "enable_unknown_slang_tool", True))
    if role == "linyin":
        planner = resolve_chat_completion_route(config, completion_route="legacy")
        return EncyclopediaPolicy(
            global_enabled and bool(getattr(config, "enable_linyin_encyclopedia", False)),
            provider in {"openai", "ollama"}, "prefetch",
            bool(getattr(config, "linyin_encyclopedia_auto", True)),
            planner.configured and 0 < getattr(config, "encyclopedia_plan_timeout_seconds", 8) <= 30
            and 0 < getattr(config, "encyclopedia_lookup_timeout_seconds", 8) <= 30,
        )
    if role == legacy_card:
        return EncyclopediaPolicy(
            global_enabled and bool(getattr(config, "enable_aike_encyclopedia", True)),
            provider == "openai", "model_tool", True,
            0 < getattr(config, "encyclopedia_lookup_timeout_seconds", 8) <= 30,
        )
    return EncyclopediaPolicy(False, False, "unavailable", False, False)


def encyclopedia_policy_detail(policy: EncyclopediaPolicy) -> str:
    if policy.mode == "prefetch":
        trigger = "明确查询及自动查词" if policy.automatic else "明确查询"
        return f"萌娘百科：{trigger}；短查询指令及“知道／听过某词条吗”直接查询，其他消息由 DS 预判；当前角色模型仅生成一次回复。问候与短确认跳过预判；查询过程有总超时。"
    return "萌娘百科：短查询指令及“知道／听过某词条吗”直接查询，其他消息由当前角色模型按需请求工具；公共百科子图查询后回传资料，生成角色回复。"
