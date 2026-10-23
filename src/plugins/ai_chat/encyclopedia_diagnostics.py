"""Task-local encyclopedia diagnostics. Never retain prompts or response text."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import hmac
import secrets
import time


_QUERY = ContextVar("encyclopedia_query_diagnostics", default=None)
_REQUEST = ContextVar("encyclopedia_source_request_diagnostics", default=None)
_REFERENCE_KEY = secrets.token_bytes(32)
_ERROR_TYPES = frozenset({
    "TimeoutError", "APITimeoutError", "APIConnectionError", "APIStatusError",
    "BadRequestError", "AuthenticationError", "PermissionDeniedError", "NotFoundError",
    "RateLimitError", "InternalServerError", "UnprocessableEntityError",
    "HTTPStatusError", "ConnectError", "ReadError", "ReadTimeout", "ConnectTimeout",
    "WriteTimeout", "PoolTimeout", "RemoteProtocolError", "ValueError", "RuntimeError",
    "JSONDecodeError", "CancelledError",
})


def public_reference(value: str) -> str:
    """Comparable within one process; prevents guessing logged names offline."""
    return hmac.new(_REFERENCE_KEY, value.strip().casefold().encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def current_query() -> dict | None:
    return _QUERY.get()


def current_request() -> dict | None:
    return _REQUEST.get()


def note_candidates(terms: list[str]) -> None:
    query = current_query()
    if query is not None:
        query["candidates"] = [{"ref": public_reference(term), "chars": len(term)} for term in terms[:3]]


def note_model_response(target: dict, response) -> None:
    usage = getattr(response, "usage", None)
    for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
        target[name] = getattr(usage, name, None)
    target["reasoning_tokens"] = getattr(getattr(usage, "completion_tokens_details", None), "reasoning_tokens", None)
    if not getattr(response, "choices", None):
        return
    choice = response.choices[0]
    message = choice.message
    content = getattr(message, "content", None)
    reasoning = getattr(message, "reasoning_content", None)
    target.update(finish_reason=getattr(choice, "finish_reason", None),
                  content_chars=len(content) if isinstance(content, str) else 0,
                  reasoning_chars=len(reasoning) if isinstance(reasoning, str) else None,
                  tool_calls=len(getattr(message, "tool_calls", None) or []))


async def wait_for_budget(operation, seconds: float, *, origin: str):
    task = asyncio.ensure_future(operation)
    try:
        return await asyncio.wait_for(task, seconds)
    except TimeoutError:
        query = current_query()
        if query is not None:
            query["timeout_origin"] = origin if task.cancelled() else "operation_timeout"
        raise


@contextmanager
def capture_query(plan_seconds: float, lookup_seconds: float, sink: list | None = None):
    query = {"plan_budget_ms": round(plan_seconds * 1000), "lookup_budget_ms": round(lookup_seconds * 1000),
             "planner": {}, "requests": [], "candidates": [], "cache": "not_checked",
             "evidence_collected": 0, "outcome": "running", "timeout_origin": "none"}
    if sink is not None:
        sink.append(query)
    token = _QUERY.set(query)
    started = time.monotonic()
    try:
        yield query
    except asyncio.CancelledError:
        query["outcome"] = "cancelled"
        raise
    finally:
        query["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        _QUERY.reset(token)


@contextmanager
def capture_source_request(phase: str, candidate_index: int):
    event = {"phase": phase, "candidate_index": candidate_index, "outcome": "running"}
    query = current_query()
    if query is not None:
        query["requests"].append(event)
    token = _REQUEST.set(event)
    started = time.monotonic()
    try:
        yield event
        event["outcome"] = "completed"
    except asyncio.CancelledError:
        event.update(outcome="cancelled", error_type="CancelledError")
        raise
    except Exception as exc:
        event.update(outcome="error", error_type=type(exc).__name__)
        raise
    finally:
        event["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        _REQUEST.reset(token)


def _integer(value, maximum=3_600_000):
    return min(max(value, 0), maximum) if type(value) is int else None


def _enum(value, allowed, default="unknown"):
    return value if isinstance(value, str) and value in allowed else default


def _reference(value):
    return value if isinstance(value, str) and len(value) == 16 and all(c in "0123456789abcdef" for c in value) else ""


def sanitise_query_runs(runs) -> list[dict]:
    """A second, closed boundary before writing nested observations to disk."""
    if not isinstance(runs, (list, tuple)):
        return []
    result = []
    for raw in runs[:2]:
        if not isinstance(raw, dict):
            continue
        row = {name: _integer(raw.get(name)) for name in (
            "plan_budget_ms", "lookup_budget_ms", "source_timeout_ms", "elapsed_ms", "evidence_collected")}
        row.update(
            outcome=_enum(raw.get("outcome"), {"running", "completed", "cancelled"}),
            status=_enum(raw.get("status"), {
                "not_needed", "found", "partial", "not_found", "no_content", "source_unavailable",
                "planner_timeout", "lookup_timeout", "planner_empty_response", "planner_response_truncated",
                "planner_invalid_response", "planner_error", "lookup_error", "invalid_arguments"}),
            cache=_enum(raw.get("cache"), {"not_checked", "hit", "miss"}),
            timeout_origin=_enum(raw.get("timeout_origin"), {"none", "plan_deadline", "lookup_deadline", "operation_timeout"}),
        )
        candidates = raw.get("candidates")
        row["candidates"] = [{"ref": _reference(term.get("ref")), "chars": _integer(term.get("chars"), 80)}
                             for term in candidates[:3] if isinstance(term, dict)] if isinstance(candidates, list) else []
        plan = raw.get("planner")
        plan = plan if isinstance(plan, dict) else {}
        row["planner"] = {name: _integer(plan.get(name)) for name in (
            "input_chars", "max_tokens", "request_timeout_ms", "sdk_max_retries", "prompt_tokens",
            "completion_tokens", "total_tokens", "reasoning_tokens", "content_chars", "reasoning_chars",
            "json_error_line", "json_error_column", "http_status")}
        row["planner"].update(
            route=_enum(plan.get("route"), {"legacy", "persona"}, "none"),
            model_ref=_reference(plan.get("model_ref")),
            thinking_mode=_enum(plan.get("thinking_mode"), {"disabled", "unspecified"}, "not_run"),
            input_truncated=plan.get("input_truncated") is True,
            json_valid=plan.get("json_valid") if type(plan.get("json_valid")) is bool else None,
            finish_reason=_enum(plan.get("finish_reason"), {"stop", "length", "tool_calls", "content_filter", "function_call"}, "unreported"),
            validation=_enum(plan.get("validation"), {"pending", "no_choices", "length_limit", "empty_content", "invalid_json", "wrong_shape", "invalid_candidates", "valid", "request_error", "cancelled"}, "not_run"),
            error_type=_enum(plan.get("error_type"), _ERROR_TYPES, ""),
        )
        events = raw.get("requests")
        row["requests"] = []
        for event in (events[:24] if isinstance(events, list) else []):
            if not isinstance(event, dict):
                continue
            entry = {name: _integer(event.get(name)) for name in (
                "candidate_index", "elapsed_ms", "http_status", "response_bytes", "page_count",
                "usable_pages", "search_results")}
            entry.update(
                phase=_enum(event.get("phase"), {"exact", "search", "search_page"}),
                outcome=_enum(event.get("outcome"), {"running", "completed", "error", "cancelled"}),
                error_type=_enum(event.get("error_type"), _ERROR_TYPES, ""),
                response_kind=_enum(event.get("response_kind"), {"object", "list", "invalid_json", "unsupported", "api_error"}, "unreported"),
                content_type=_enum(event.get("content_type"), {"json", "html", "text", "other"}, "unreported"),
                transport_phase=_enum(event.get("transport_phase"), {"connect", "tls", "send_headers", "send_body", "receive_headers", "receive_body", "close"}, "unreported"),
                transport_failure_phase=_enum(event.get("transport_failure_phase"), {"connect", "tls", "send_headers", "send_body", "receive_headers", "receive_body", "close"}, "unreported"),
                api_error=_enum(event.get("api_error"), {"maxlag", "ratelimited", "readonly", "permissiondenied", "badtitle", "missingtitle", "readapidenied", "internal_api_error"}, ""),
            )
            row["requests"].append(entry)
        result.append(row)
    return result


def sanitise_model_requests(requests) -> list[dict]:
    result = []
    for raw in (requests[:2] if isinstance(requests, list) else []):
        if not isinstance(raw, dict):
            continue
        row = {name: _integer(raw.get(name)) for name in (
            "elapsed_ms", "max_tokens", "content_chars", "reasoning_chars", "tool_calls",
            "prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens", "http_status")}
        row.update(
            finish_reason=_enum(raw.get("finish_reason"), {"stop", "length", "tool_calls", "content_filter", "function_call"}, "unreported"),
            tool_choice=_enum(raw.get("tool_choice"), {"auto", "none"}, "not_offered"),
            outcome=_enum(raw.get("outcome"), {"running", "completed", "error", "cancelled"}),
            error_type=_enum(raw.get("error_type"), _ERROR_TYPES, ""),
        )
        result.append(row)
    return result
