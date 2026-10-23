"""Per-turn encyclopedia diagnostics with a closed, text-free log schema."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import re
from pathlib import Path
from uuid import UUID, uuid4

from .failure_diagnostics import classify_failure
from .encyclopedia_diagnostics import sanitise_model_requests, sanitise_query_runs
from .reliability_events import CODE_CONTRACTS


ENCYCLOPEDIA_LOG_PATH = Path(__file__).resolve().parents[3] / "logs" / "encyclopedia.log"
BEIJING_TIME = timezone(timedelta(hours=8))
_STATUSES = frozenset({
    "not_started", "pending", "awaiting_model", "disabled", "skipped", "not_needed", "not_requested",
    "found", "partial", "not_found", "no_content", "source_unavailable", "planner_timeout", "lookup_timeout",
    "planner_empty_response", "planner_response_truncated", "planner_invalid_response", "planner_error",
    "lookup_error", "invalid_arguments", "unsupported_tool", "budget_exceeded",
})
_UNCERTAIN_REPLY = re.compile(r"没(?:有)?听(?:说)?过|不知道|不清楚|不认识|没(?:有)?印象|不了解")


def _enum(value, allowed, default="unknown"):
    return value if isinstance(value, str) and value in allowed else default


def _number(value, maximum=3_600_000):
    if type(value) is not int:
        return 0
    return min(max(value, 0), maximum)


def _diagnosis(row):
    if row["reply_status"] == "cancelled":
        return "interrupted", "本轮请求已取消，尚不能判断最终回答效果。"
    if row["reply_status"] == "failed":
        return "reply_request", "聊天请求失败；结合 reply_failure_code 与百科 status 区分两个阶段。"
    if row["reply_status"] == "empty":
        return "reply_empty", "聊天模型返回空文本。"
    if row["policy"] != "ready":
        return "policy_gate", "百科未获准启用；检查 policy 字段中的开关、场景或配置原因。"
    status = row["status"]
    if status == "skipped":
        return "local_gate", "程序按问候/短确认或仅明确查询的范围跳过。"
    if status == "not_needed":
        return "planner_decision", "DS 预判决定不查百科。"
    if status == "not_requested":
        if row["model_requests"] and row["model_requests"][0]["finish_reason"] == "length":
            return "model_tool_decision", "聊天模型响应被截断，未形成工具请求；不能据此认定模型主动决定不查询。"
        return "model_tool_decision", "聊天模型获得工具说明，但没有请求百科工具。"
    if status.startswith("planner_"):
        if status == "planner_response_truncated":
            return "planner", "预判被长度上限截断；查看 query_runs.planner 的输出/思考用量、长度和 json_valid，不能视为决定不查。"
        return "planner", "百科预判未成功完成；具体原因见 status。"
    if status in {"not_found", "no_content", "source_unavailable", "lookup_timeout", "lookup_error"}:
        if row["evidence_provided"]:
            return "lookup_partial", "部分查询没有取得正文，但已有资料交给模型；结合 tool_statuses 和实际回复核对。"
        if any((run.get("evidence_collected") or 0) > 0 for run in row["query_runs"]):
            return "public_lookup", "查询过程中已取得部分正文，但本轮未交给模型；检查 query_runs 中后续请求、取消位置和总预算。"
        return "public_lookup", "公共查询没有取得可靠正文；具体原因见 status。"
    if status == "invalid_arguments":
        return "query_arguments", "查询候选或工具参数无效。"
    if status in {"unsupported_tool", "budget_exceeded"}:
        return "tool_dispatch", "工具未受支持或超过本轮查询次数。"
    if row["evidence_provided"] and row["reply_uncertainty_cue"]:
        return "reply_review", "资料已交给模型，但回复含陌生/不确定措辞；需核对资料相关性和回复，不能据此断定答错。"
    if row["evidence_provided"]:
        return "evidence_delivered", "公共资料已交给聊天模型；回答内容的正确性仍需结合实际回复核对。"
    if status in {"found", "partial"}:
        return "evidence_delivery", "查询报告命中，但没有记录有效正文交给模型，需检查资料传递。"
    return "incomplete", "本轮没有完整的百科过程结果。"


def build_encyclopedia_turn_log(
    observation: dict[str, object], role_card_key: str, *, reply: str | None = None,
    error: BaseException | None = None, occurred_at: datetime | None = None,
) -> dict[str, object]:
    """Only fixed metadata survives; never serialize arbitrary observation fields."""
    trace = observation.get("encyclopedia_trace_id")
    try:
        trace = str(UUID(trace)) if isinstance(trace, str) else str(uuid4())
    except ValueError:
        trace = str(uuid4())
    reply_text = reply if isinstance(reply, str) else ""
    reply_status = (
        "cancelled" if isinstance(error, asyncio.CancelledError) else "failed" if error is not None else
        "not_returned" if reply is None else "succeeded" if reply_text.strip() else "empty"
    )
    row = {
        "time": (occurred_at or datetime.now(BEIJING_TIME)).astimezone(BEIJING_TIME).isoformat(timespec="seconds"),
        "component": "public_encyclopedia", "trace": trace,
        "persona": _enum(role_card_key, {"aike", "linyin"}, "other"),
        "mode": _enum(observation.get("encyclopedia_mode"), {"model_tool", "prefetch", "unavailable"}),
        "trigger": _enum(observation.get("encyclopedia_trigger"), {"direct_command", "direct_question", "automatic_plan", "model_tool", "local_skip"}, "none"),
        "policy": _enum(observation.get("encyclopedia_policy_reason"), {"ready", "not_allowed", "disabled_by_config", "unsupported_route", "incomplete_configuration"}, "not_evaluated"),
        "status": _enum(observation.get("encyclopedia_status"), _STATUSES),
        "query_failure_code": _enum(observation.get("encyclopedia_failure_code"), CODE_CONTRACTS, ""),
        "planner_used": observation.get("encyclopedia_planner_used") is True,
        "planner_needed": observation.get("encyclopedia_plan_needed") if type(observation.get("encyclopedia_plan_needed")) is bool else None,
        "lookup_attempted": observation.get("encyclopedia_lookup_attempted") is True,
        "evidence_count": _number(observation.get("encyclopedia_evidence_provided_count"), 12),
        "evidence_provided": observation.get("encyclopedia_evidence_provided") is True,
        "cache_hit": observation.get("encyclopedia_cache_hit") is True,
        "plan_ms": _number(observation.get("encyclopedia_plan_ms")),
        "lookup_ms": _number(observation.get("encyclopedia_lookup_ms")),
        "lookup_total_ms": _number(observation.get("encyclopedia_elapsed_ms")),
        "chat_requests": _number(observation.get("encyclopedia_chat_requests"), 2),
        "chat_ms": _number(observation.get("encyclopedia_chat_ms")),
        "chat_route": _enum(observation.get("encyclopedia_chat_route"), {"legacy", "persona"}),
        "chat_provider": _enum(observation.get("encyclopedia_chat_provider"), {"openai", "ollama"}),
        "reply_status": reply_status, "reply_chars": min(len(reply_text), 100_000),
        "reply_uncertainty_cue": bool(_UNCERTAIN_REPLY.search(reply_text)),
        "reply_failure_code": classify_failure(error).code if error is not None and reply_status == "failed" else "",
        "schema_version": 2,
        "query_runs": sanitise_query_runs(observation.get("encyclopedia_runs")),
        "model_requests": sanitise_model_requests(observation.get("encyclopedia_model_requests")),
    }
    statuses = observation.get("encyclopedia_tool_statuses")
    row["tool_statuses"] = [_enum(value, _STATUSES) for value in statuses[:16]] if isinstance(statuses, (list, tuple)) else []
    source_errors = observation.get("encyclopedia_source_error_types")
    row["source_error_types"] = [
        _enum(value, {"HTTPStatusError", "ConnectError", "ReadError", "ReadTimeout", "ConnectTimeout", "WriteTimeout", "PoolTimeout", "RemoteProtocolError", "ValueError", "RuntimeError"})
        for value in source_errors[:6]
    ] if isinstance(source_errors, (list, tuple)) else []
    row["location"], row["detail"] = _diagnosis(row)
    return row


def write_encyclopedia_turn_log_safely(
    observation: dict[str, object], role_card_key: str, *, reply: str | None = None,
    error: BaseException | None = None, path: Path | None = None,
) -> bool:
    try:
        row = build_encyclopedia_turn_log(observation, role_card_key, reply=reply, error=error)
        observation.update({
            "encyclopedia_reply_status": row["reply_status"],
            "encyclopedia_reply_uncertainty_cue": row["reply_uncertainty_cue"],
            "encyclopedia_diagnostic_location": row["location"],
        })
        target = ENCYCLOPEDIA_LOG_PATH if path is None else Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        observation["encyclopedia_log_written"] = True
        return True
    except Exception:
        observation["encyclopedia_log_written"] = False
        return False
