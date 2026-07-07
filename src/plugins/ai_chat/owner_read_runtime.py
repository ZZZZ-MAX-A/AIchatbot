from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeAlias

from .graph.diagnostics import DiagnosticsView
from .graph.memory import MemoryAdminAction
from .graph.retrieval import MemoryRetrievalAction


TextProvider: TypeAlias = Callable[[], str | Awaitable[str]]
LinesProvider: TypeAlias = Callable[[], list[str] | Awaitable[list[str]]]
DiagnosticsRunner: TypeAlias = Callable[
    [DiagnosticsView | None],
    Any | Awaitable[Any],
]
MemoryRetrievalRunner: TypeAlias = Callable[
    [MemoryRetrievalAction, str],
    Any | Awaitable[Any],
]
MemoryAdminRunner: TypeAlias = Callable[
    [MemoryAdminAction],
    Any | Awaitable[Any],
]


def _missing_text_provider(name: str) -> TextProvider:
    def provider() -> str:
        raise RuntimeError(f"owner read dependency not configured: {name}")

    return provider


def _missing_lines_provider(name: str) -> LinesProvider:
    def provider() -> list[str]:
        raise RuntimeError(f"owner read dependency not configured: {name}")

    return provider


def _missing_diagnostics_runner(name: str) -> DiagnosticsRunner:
    def runner(_view: DiagnosticsView | None):
        raise RuntimeError(f"owner read dependency not configured: {name}")

    return runner


def _missing_memory_retrieval_runner(name: str) -> MemoryRetrievalRunner:
    def runner(_action: MemoryRetrievalAction, _query: str = ""):
        raise RuntimeError(f"owner read dependency not configured: {name}")

    return runner


def _missing_memory_admin_runner(name: str) -> MemoryAdminRunner:
    def runner(_action: MemoryAdminAction):
        raise RuntimeError(f"owner read dependency not configured: {name}")

    return runner


@dataclass(frozen=True)
class OwnerReadRuntime:
    bot_status_lines: LinesProvider = field(
        default_factory=lambda: _missing_lines_provider("bot_status_lines")
    )
    ops_health_reply: TextProvider = field(
        default_factory=lambda: _missing_text_provider("ops_health_reply")
    )
    vision_troubleshoot_reply: TextProvider = field(
        default_factory=lambda: _missing_text_provider("vision_troubleshoot_reply")
    )
    memory_rag_troubleshoot_reply: TextProvider = field(
        default_factory=lambda: _missing_text_provider("memory_rag_troubleshoot_reply")
    )
    run_diagnostics: DiagnosticsRunner = field(
        default_factory=lambda: _missing_diagnostics_runner("run_diagnostics")
    )
    run_memory_retrieval: MemoryRetrievalRunner = field(
        default_factory=lambda: _missing_memory_retrieval_runner("run_memory_retrieval")
    )
    run_memory_admin: MemoryAdminRunner = field(
        default_factory=lambda: _missing_memory_admin_runner("run_memory_admin")
    )
    load_persona_prompt: TextProvider = field(
        default_factory=lambda: _missing_text_provider("load_persona_prompt")
    )
    persona_status_lines: LinesProvider = field(
        default_factory=lambda: _missing_lines_provider("persona_status_lines")
    )
    role_card_list_lines: LinesProvider = field(
        default_factory=lambda: _missing_lines_provider("role_card_list_lines")
    )
    model_config_status_lines: LinesProvider = field(
        default_factory=lambda: _missing_lines_provider("model_config_status_lines")
    )
    access_overview_lines: LinesProvider = field(
        default_factory=lambda: _missing_lines_provider("access_overview_lines")
    )
    rag_index_detail_lines: LinesProvider = field(
        default_factory=lambda: _missing_lines_provider("rag_index_detail_lines")
    )
    main_agent_observation_lines: LinesProvider = field(
        default_factory=lambda: _missing_lines_provider("main_agent_observation_lines")
    )
    root_graph_observation_lines: LinesProvider = field(
        default_factory=lambda: _missing_lines_provider("root_graph_observation_lines")
    )
    group_whitelist_reply: TextProvider = field(
        default_factory=lambda: _missing_text_provider("group_whitelist_reply")
    )
    private_whitelist_reply: TextProvider = field(
        default_factory=lambda: _missing_text_provider("private_whitelist_reply")
    )
    blacklist_reply: TextProvider = field(
        default_factory=lambda: _missing_text_provider("blacklist_reply")
    )


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def _join_lines(provider: LinesProvider) -> str:
    return "\n".join(await _maybe_await(provider()))


def _execution_reply_or_raise(execution: Any) -> str:
    result = getattr(execution, "result", None)
    if result is None:
        raise RuntimeError("owner read graph returned no result")
    error = str(getattr(result, "error", "") or "")
    reply_text = str(getattr(result, "reply_text", "") or "")
    if error:
        raise RuntimeError(reply_text or error)
    return reply_text


def _tool_query(context: Any) -> str:
    metadata = getattr(context, "metadata", {}) or {}
    if not isinstance(metadata, dict):
        return ""
    arguments = metadata.get("tool_arguments", {})
    if not isinstance(arguments, dict):
        return ""
    return str(arguments.get("query") or "").strip()


async def run_owner_read_command(
    runtime: OwnerReadRuntime,
    command: str,
    context: Any,
) -> str:
    if command == "ops_health":
        return str(await _maybe_await(runtime.ops_health_reply()))
    if command == "vision_troubleshoot":
        return str(await _maybe_await(runtime.vision_troubleshoot_reply()))
    if command == "memory_rag_troubleshoot":
        return str(await _maybe_await(runtime.memory_rag_troubleshoot_reply()))

    views: dict[str, DiagnosticsView | None] = {
        "diagnostics": None,
        "config_status": DiagnosticsView.CONFIG,
        "vision_status": DiagnosticsView.VISION,
        "recent_errors": DiagnosticsView.RECENT_ERRORS,
        "image_cache_status": DiagnosticsView.IMAGE_CACHE,
        "memory_status": DiagnosticsView.MEMORY,
        "tts_status": DiagnosticsView.TTS,
    }
    if command == "bot_status":
        return await _join_lines(runtime.bot_status_lines)
    if command in views:
        execution = await _maybe_await(runtime.run_diagnostics(views[command]))
        return _execution_reply_or_raise(execution)

    if command == "rag_status":
        execution = await _maybe_await(
            runtime.run_memory_retrieval(MemoryRetrievalAction.STATUS, "")
        )
        return _execution_reply_or_raise(execution)
    if command == "memory_retrieval":
        execution = await _maybe_await(
            runtime.run_memory_retrieval(
                MemoryRetrievalAction.QUERY,
                _tool_query(context),
            )
        )
        result = getattr(execution, "result", None)
        return "" if result is None else str(getattr(result, "reply_text", "") or "")

    memory_admin_actions = {
        "summary_status": MemoryAdminAction.SUMMARY_STATUS,
        "view_summaries": MemoryAdminAction.VIEW_SUMMARIES,
        "view_gap_scene_summaries": MemoryAdminAction.VIEW_GAP_SCENE_SUMMARIES,
        "view_long_term_memory": MemoryAdminAction.VIEW_LONG_TERM_MEMORY,
    }
    if command in memory_admin_actions:
        execution = await _maybe_await(runtime.run_memory_admin(memory_admin_actions[command]))
        return _execution_reply_or_raise(execution)

    if command == "view_persona":
        prompt = str(await _maybe_await(runtime.load_persona_prompt()) or "")
        if prompt:
            return "当前角色卡内容：\n" + prompt
        return await _join_lines(runtime.persona_status_lines)
    if command == "role_card_list":
        return await _join_lines(runtime.role_card_list_lines)
    if command == "model_config_status":
        return await _join_lines(runtime.model_config_status_lines)
    if command == "access_overview":
        return await _join_lines(runtime.access_overview_lines)
    if command == "rag_index_detail":
        return await _join_lines(runtime.rag_index_detail_lines)
    if command == "main_agent_observations":
        return await _join_lines(runtime.main_agent_observation_lines)
    if command == "root_graph_observations":
        return await _join_lines(runtime.root_graph_observation_lines)
    if command == "group_whitelist":
        return str(await _maybe_await(runtime.group_whitelist_reply()))
    if command == "private_whitelist":
        return str(await _maybe_await(runtime.private_whitelist_reply()))
    if command == "blacklist":
        return str(await _maybe_await(runtime.blacklist_reply()))

    raise RuntimeError(f"unsupported owner read command: {command}")
