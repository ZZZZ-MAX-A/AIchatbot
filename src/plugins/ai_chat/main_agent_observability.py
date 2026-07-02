from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit


SENSITIVE_PATTERNS = (
    (re.compile(r"(?i)\b(?:sk-|ak-)[A-Za-z0-9_-]{10,}\b"), "[redacted-key]"),
    (re.compile(r"(?i)\b(?:api[_ -]?key|token|password|passwd|secret)\s*[:=：]\s*\S+"), "[redacted-key]"),
)


def sanitize_observation_text(text: object, *, limit: int = 160) -> str:
    sanitized = str(text).replace("\r", " ").replace("\n", " ")
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    sanitized = " ".join(sanitized.split())
    if len(sanitized) > limit:
        return sanitized[: limit - 3].rstrip() + "..."
    return sanitized


def redacted_base_url(base_url: str) -> str:
    stripped = base_url.strip()
    if not stripped:
        return "(empty)"

    parsed = urlsplit(stripped)
    if not parsed.scheme or not parsed.netloc:
        return sanitize_observation_text(stripped, limit=120)

    host = parsed.hostname or parsed.netloc
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{host}{port}{path}"


def _configured(value: object) -> str:
    return "yes" if bool(value) else "no"


def build_main_llm_failure_log_message(
    *,
    config: Any,
    phase: str,
    error_type: str,
    error_message: str,
) -> str:
    return " ".join(
        [
            "main_agent_llm_failed",
            f"phase={sanitize_observation_text(phase, limit=40)}",
            f"error_type={sanitize_observation_text(error_type, limit=80)}",
            f'error="{sanitize_observation_text(error_message)}"',
            f"model={sanitize_observation_text(getattr(config, 'main_llm_model', ''), limit=80)}",
            f"base_url={redacted_base_url(getattr(config, 'main_llm_base_url', ''))}",
            f"api_key_configured={_configured(getattr(config, 'main_llm_api_key', ''))}",
        ]
    )
