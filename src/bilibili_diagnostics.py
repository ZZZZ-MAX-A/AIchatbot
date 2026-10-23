"""Allowlisted Bilibili diagnostics; never persist credentials or response text."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
from pathlib import Path
import re
from threading import Lock
import uuid

from .bilibili_connector import connector_home

_LOCK = Lock()
_LOG_NAME = re.compile(r"browse-\d{8}-[0-9a-f]{32}\.jsonl\Z")
_EVENTS = {"run_start", "http_response", "http_error", "check", "validation_failed", "run_end"}
_STAGES = {"runtime", "nav", "detail", "player", "subtitle_cdn", "home", "following", "other", "evidence", "diagnose", "preview", "selection", "summary"}
_CHECKS = {"account_binding", "login_state", "player_identity", "subtitle_timeline", "subtitle_structure",
           "signing_encoding", "signature_vector", "player_signing", "response_structure", "business_code", "evidence",
           "selection_structure", "summary_structure", "content_alignment"}
_BOOLEANS = {"ok", "signed", "truncated", "binding_matches", "worth_sharing", "proxy_configured", "trust_env",
             "http_proxy_configured", "https_proxy_configured", "all_proxy_configured", "no_proxy_configured"}
_NUMBERS = {"http_status", "business_code", "body_bytes", "elapsed_ms", "server_clock_delta_seconds",
            "cache_age_seconds", "segments", "characters", "pages", "write_failures"}
_ENUMS = {
    "content_type": {"json", "html", "text", "other", "missing"},
    "body_kind": {"json", "html", "text", "empty", "invalid"},
    "outcome": {"ok", "partial", "http_rejected", "too_large", "invalid_json", "network_error", "business_error", "source_error", "unavailable"},
    "error_kind": {"timeout", "proxy", "connect", "transport", "http", "structure", "identity", "timeline", "signing"},
    "content_alignment": {"consistent", "uncertain", "mismatch"},
}
BODY_SIGNALS = ("请求被拦截", "请求被拒绝", "访问被拒绝", "风控", "安全验证", "验证码", "风险", "precondition failed")
PARAMETER_NAMES = {"aid", "bvid", "cid", "wts", "w_rid", "ps", "fresh_type", "fresh_idx", "type"}


class DiagnosticLog:
    """One bounded JSONL per run, keeping at most 20 completed/recent files."""

    def __init__(self, directory: Path | None = None, *, max_bytes: int = 512 * 1024):
        self.trace_id = uuid.uuid4().hex
        self.path = (directory if directory is not None else connector_home() / "logs") / (
            f"browse-{datetime.now(timezone.utc):%Y%m%d}-{self.trace_id}.jsonl")
        self.max_bytes = max_bytes
        self.write_failures = 0
        self.events: list[dict] = []

    def record(self, event: str, stage: str, **fields) -> None:
        if event not in _EVENTS or stage not in _STAGES:
            return
        row = {"schema_version": 1, "trace_id": self.trace_id,
               "time_utc": datetime.now(timezone.utc).isoformat(), "event": event, "stage": stage}
        for key, value in fields.items():
            if key in _BOOLEANS and type(value) is bool:
                row[key] = value
            elif key in _NUMBERS and type(value) in (int, float) and abs(value) < 1e15:
                row[key] = value
            elif key in _ENUMS and isinstance(value, str) and value in _ENUMS[key]:
                row[key] = value
            elif key == "check" and isinstance(value, str) and value in _CHECKS:
                row[key] = value
            elif key == "body_sha256" and isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
                row[key] = value
            elif key == "parameter_names" and isinstance(value, list):
                row[key] = sorted({v for v in value if isinstance(v, str) and v in PARAMETER_NAMES})
            elif key == "body_signals" and isinstance(value, list):
                row[key] = [v for v in BODY_SIGNALS if v in value]
        self.events.append(row)
        self.events[:] = self.events[-200:]
        encoded = (json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        try:
            with _LOCK:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if not self.path.exists():
                    previous = sorted((p for p in self.path.parent.iterdir() if _LOG_NAME.fullmatch(p.name) and p.is_file()),
                                      key=lambda p: p.stat().st_mtime, reverse=True)
                    for stale in previous[19:]:
                        stale.unlink()
                if self.path.exists() and self.path.stat().st_size + len(encoded) > self.max_bytes:
                    self.write_failures += 1
                    return
                if len(encoded) > self.max_bytes:
                    self.write_failures += 1
                    return
                with self.path.open("ab") as stream:
                    stream.write(encoded)
        except OSError:
            # Observability must not hide the original request/validation error.
            self.write_failures += 1

    def public_status(self) -> dict:
        return {"trace_id": self.trace_id, "path": str(self.path), "write_failures": self.write_failures}


def response_facts(response, raw: bytes | bytearray, *, truncated: bool, elapsed_ms: int) -> dict:
    """Extract only typed numbers, hashes and fixed classifications from untrusted data."""
    mime = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    kind = "missing" if not mime else "json" if mime == "application/json" or mime.endswith("+json") else (
        "html" if mime == "text/html" else "text" if mime.startswith("text/") else "other")
    facts = {"http_status": response.status_code, "content_type": kind, "body_bytes": len(raw),
             "body_sha256": hashlib.sha256(raw).hexdigest(), "truncated": truncated, "elapsed_ms": elapsed_ms}
    try:
        payload = json.loads(raw)
        facts["body_kind"] = "json"
        if isinstance(payload, dict) and type(payload.get("code")) is int:
            facts["business_code"] = payload["code"]
    except (ValueError, UnicodeError, RecursionError):
        prefix = bytes(raw[:4096]).lstrip().lower()
        facts["body_kind"] = "empty" if not raw else "html" if (
            b"<html" in prefix or b"<!doctype html" in prefix) else "text"
    # Only look for predeclared signals; never serialize server messages or body snippets.
    decoded = bytes(raw[:65536]).decode("utf-8", errors="replace").lower()
    facts["body_signals"] = [word for word in BODY_SIGNALS if word in decoded]
    try:
        server_time = parsedate_to_datetime(response.headers.get("date", ""))
        if server_time.tzinfo is not None:
            facts["server_clock_delta_seconds"] = round((datetime.now(timezone.utc) - server_time).total_seconds(), 1)
    except (TypeError, ValueError, OverflowError):
        pass
    age = response.headers.get("age", "")
    if age.isascii() and age.isdigit() and len(age) <= 10:
        facts["cache_age_seconds"] = int(age)
    return facts
