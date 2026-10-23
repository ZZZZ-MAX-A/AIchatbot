"""Read-only evidence; validate local cards without disclosing contents.

No network probes, database access or Bot/client initialization.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from .completion_routes import resolve_chat_completion_route, resolve_summary_completion_route
from .persona_maintenance import build_persona_binding_report

if TYPE_CHECKING:
    from .config import AiChatConfig


def _route_status(config: AiChatConfig, role: str = "", override: str = "auto") -> dict:
    try:
        route = resolve_chat_completion_route(config, role, completion_route=override)
        return {
            "source": route.source,
            "provider": route.provider,
            "configured": route.configured,
            "missing_fields": list(route.configuration_errors),
        }
    except (RuntimeError, ValueError, TypeError):
        return {"source": "persona", "configured": False, "reason": "角色路由配置不完整"}


def local_ollama_dependencies(config: AiChatConfig) -> tuple[tuple[str, str], ...]:
    """Return purpose/URL internally; callers must not render raw URLs."""
    dependencies = []
    if (config.enable_memory_rag or config.enable_project_doc_rag) and config.memory_rag_embedding_provider == "ollama":
        dependencies.append(("embedding", config.memory_rag_embedding_base_url))
    if config.enable_vision and config.vision_provider == "ollama":
        dependencies.append(("vision", config.vision_ollama_base_url))
    if config.enable_persona_llm_routing and config.persona_llm_role_card_keys and config.persona_llm_provider == "ollama":
        dependencies.append(("persona_chat", config.persona_llm_base_url))
    return tuple(dependencies)


def loopback_endpoint(url: str) -> tuple[str, int] | None:
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            return None
        return parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return None


def build_configuration_report(config: AiChatConfig) -> dict:
    summary = resolve_summary_completion_route(config)
    local_plans = {}
    for purpose, url in local_ollama_dependencies(config):
        endpoint = loopback_endpoint(url)
        if endpoint is None:
            continue
        parsed = urlsplit(url)
        host = f"[{endpoint[0]}]" if endpoint[0] == "::1" else endpoint[0]
        safe_url = f"{parsed.scheme}://{host}:{endpoint[1]}{parsed.path.rstrip('/')}"
        model = config.memory_rag_embedding_model if purpose == "embedding" else config.persona_llm_model if purpose == "persona_chat" else config.vision_model
        plan = local_plans.setdefault(safe_url, {"base_url": safe_url, "models": [], "standard_local": endpoint in {("127.0.0.1", 11434), ("localhost", 11434)}})
        if model not in plan["models"]:
            plan["models"].append(model)
    report = {
        "parse_ok": True,
        "snapshot_kind": config.configuration_snapshot_kind,
        "reload_policy": "import_time_dotenv_then_process_snapshot; restart_required_for_file_changes",
        "issues": [
            {"key": issue.key, "code": issue.code, "severity": issue.severity, "message": issue.message}
            for issue in config.configuration_issues
        ],
        "sources": dict(config.configuration_sources),
        "chat_runtime": "chat_graph" if config.enable_chat_graph_runtime else "legacy",
        "nonebot_port": config.nonebot_port,
        "default_chat": _route_status(config),
        "persona_bindings": build_persona_binding_report(config),
        "persona_chat": [
            _route_status(config, role) for role in sorted(config.persona_llm_role_card_keys)
        ] if config.enable_persona_llm_routing else [],
        "summary": {
            "enabled": config.enable_memory_compression or config.enable_gap_scene_summaries,
            "source": summary.source,
            "configured": summary.configured,
            "missing_fields": list(summary.configuration_errors),
        },
        "main_agent": {
            "enabled": config.enable_main_agent,
            "llm_enabled": config.enable_main_agent and config.main_agent_use_llm,
            "configured": bool(config.main_llm_api_key.strip() and config.main_llm_base_url.strip() and config.main_llm_model.strip() and config.main_llm_timeout_seconds > 0),
        },
        "vision": {
            "enabled": config.enable_vision,
            "provider": config.vision_provider,
            "configured": bool(config.aliyun_bailian_api_key and config.aliyun_bailian_base_url)
            if config.vision_provider == "aliyun_bailian"
            else bool(config.vision_ollama_base_url and config.vision_model),
        },
        "ollama_dependencies": [
            {"purpose": purpose, "loopback": loopback_endpoint(url) is not None}
            for purpose, url in local_ollama_dependencies(config)
        ],
        "ollama_required": bool(local_ollama_dependencies(config)),
        "ollama_local_plans": list(local_plans.values()),
        "ollama_auto_ensure": any(
            loopback_endpoint(url) in {("127.0.0.1", 11434), ("localhost", 11434)}
            for _, url in local_ollama_dependencies(config)
        ),
        "persona_local_ollama": any(
            purpose == "persona_chat" and loopback_endpoint(url) in {("127.0.0.1", 11434), ("localhost", 11434)}
            for purpose, url in local_ollama_dependencies(config)
        ),
        "persona_ollama_model": config.persona_llm_model
        if config.enable_persona_llm_routing and config.persona_llm_provider == "ollama" else "",
        "external_probes_executed": False,
        "database_opened": False,
    }
    return report
