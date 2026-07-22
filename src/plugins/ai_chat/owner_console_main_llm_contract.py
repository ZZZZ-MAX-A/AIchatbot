from __future__ import annotations

import json
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlsplit


MAIN_LLM_CONTRACT_WORKFLOW = "main_llm_fixed_contract"
MAIN_LLM_CONTRACT_CONFIRMATION = "run_registered_main_llm_contract"
MAIN_LLM_CONTRACT_ACTION_HEADER = "manual-main-llm-contract-v1"
MAIN_LLM_CONTRACT_VERSION = "main_llm.fixed.v1"
MAIN_LLM_CONTRACT_PROBE_ID = "p2_49c"
MAIN_LLM_CONTRACT_MAX_COMPLETION_TOKENS = 256
MAIN_LLM_CONTRACT_RESPONSE_CHARACTER_LIMIT = 1024
MAIN_LLM_CONTRACT_TIMEOUT_SECONDS = 30
MAIN_LLM_CONTRACT_LATENCY_ATTENTION_MS = 15_000

MAIN_LLM_CONTRACT_MESSAGES: tuple[dict[str, str], ...] = (
    {
        "role": "system",
        "content": (
            "You are a fixed Main LLM contract probe.\n"
            "You have no tools.\n"
            "Return exactly one JSON object.\n"
            "Do not use markdown fences or surrounding prose.\n"
            "Use exactly the registered keys, types, and values."
        ),
    },
    {
        "role": "user",
        "content": (
            'For probe marker "amber-17", compute 17 + 25 and return the '
            "registered contract object."
        ),
    },
)

MAIN_LLM_CONTRACT_EXPECTED_RESPONSE: dict[str, object] = {
    "contract_version": MAIN_LLM_CONTRACT_VERSION,
    "probe_id": MAIN_LLM_CONTRACT_PROBE_ID,
    "marker": "amber-17",
    "sum": 42,
    "status": "ok",
}


@dataclass(frozen=True)
class MainLlmContractEvidence:
    configured_model: str
    runtime_feature_enabled: bool
    contract_valid: bool
    usage_metadata_available: bool
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    tool_calls_present: bool
    elapsed_ms: int


class MainLlmContractFailure(RuntimeError):
    def __init__(
        self,
        *,
        stage: str,
        code: str,
        code_label: str,
        configured_model: str = "",
        runtime_feature_enabled: bool = False,
        elapsed_ms: int = 0,
        llm_called: bool = False,
    ) -> None:
        super().__init__(code)
        self.stage = stage
        self.code = code
        self.code_label = code_label
        self.configured_model = configured_model
        self.runtime_feature_enabled = runtime_feature_enabled
        self.elapsed_ms = elapsed_ms
        self.llm_called = llm_called


def _build_main_llm_contract_model(config: Any) -> Any:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise MainLlmContractFailure(
            stage="preflight",
            code="invalid_configuration",
            code_label="Main LLM 客户端依赖不可用",
        ) from exc

    return ChatOpenAI(
        api_key=config.main_llm_api_key,
        base_url=config.main_llm_base_url,
        model=config.main_llm_model,
        timeout=MAIN_LLM_CONTRACT_TIMEOUT_SECONDS,
        max_retries=0,
        streaming=False,
        max_tokens=MAIN_LLM_CONTRACT_MAX_COMPLETION_TOKENS,
    )


def _normalized_config(config: Any) -> tuple[str, bool]:
    api_key = str(getattr(config, "main_llm_api_key", "") or "").strip()
    base_url = str(getattr(config, "main_llm_base_url", "") or "").strip()
    model = str(getattr(config, "main_llm_model", "") or "").strip()
    parsed = urlsplit(base_url)
    if (
        not api_key
        or not model
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,119}", model) is None
        or parsed.scheme not in {"http", "https"}
        or not parsed.hostname
    ):
        raise MainLlmContractFailure(
            stage="preflight",
            code="invalid_configuration",
            code_label="Main LLM 固定合同所需配置不完整或无效",
            configured_model=model[:120],
            runtime_feature_enabled=bool(
                getattr(config, "enable_main_agent", False)
                and getattr(config, "main_agent_use_llm", False)
            ),
        )
    return model, bool(
        getattr(config, "enable_main_agent", False)
        and getattr(config, "main_agent_use_llm", False)
    )


def _content_part_text(part: object) -> str:
    if isinstance(part, str):
        return part
    if isinstance(part, Mapping):
        value = part.get("text")
        return value if isinstance(value, str) else ""
    value = getattr(part, "text", None)
    return value if isinstance(value, str) else ""


def _response_text(response: object) -> str:
    if isinstance(response, str):
        return response
    content = (
        response.get("content")
        if isinstance(response, Mapping)
        else getattr(response, "content", None)
    )
    if isinstance(content, str):
        return content
    if isinstance(content, Sequence) and not isinstance(
        content,
        (str, bytes, bytearray),
    ):
        return "".join(_content_part_text(part) for part in content)
    return ""


def _has_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return bool(value)
    return True


def _tool_calls_present(response: object) -> bool:
    def value(name: str) -> object:
        if isinstance(response, Mapping):
            return response.get(name)
        return getattr(response, name, None)

    if _has_value(value("tool_calls")) or _has_value(value("invalid_tool_calls")):
        return True
    additional = value("additional_kwargs")
    return isinstance(additional, Mapping) and (
        _has_value(additional.get("tool_calls"))
        or _has_value(additional.get("invalid_tool_calls"))
    )


def _token_count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _usage_mapping(response: object) -> Mapping[str, object] | None:
    usage = (
        response.get("usage_metadata")
        if isinstance(response, Mapping)
        else getattr(response, "usage_metadata", None)
    )
    if isinstance(usage, Mapping):
        return usage
    metadata = (
        response.get("response_metadata")
        if isinstance(response, Mapping)
        else getattr(response, "response_metadata", None)
    )
    if not isinstance(metadata, Mapping):
        return None
    token_usage = metadata.get("token_usage")
    return token_usage if isinstance(token_usage, Mapping) else None


def _token_usage(
    response: object,
) -> tuple[bool, int | None, int | None, int | None]:
    usage = _usage_mapping(response)
    if usage is None:
        return False, None, None, None
    input_tokens = _token_count(
        usage.get("input_tokens", usage.get("prompt_tokens"))
    )
    output_tokens = _token_count(
        usage.get("output_tokens", usage.get("completion_tokens"))
    )
    total_tokens = _token_count(usage.get("total_tokens"))
    available = all(
        value is not None
        for value in (input_tokens, output_tokens, total_tokens)
    )
    if not available:
        return False, None, None, None
    return True, input_tokens, output_tokens, total_tokens


def _contract_valid(text: str, *, tool_calls_present: bool) -> bool:
    if tool_calls_present or not text or len(text) > MAIN_LLM_CONTRACT_RESPONSE_CHARACTER_LIMIT:
        return False
    try:
        payload = json.loads(text, object_pairs_hook=_unique_json_object)
    except (TypeError, ValueError):
        return False
    return (
        isinstance(payload, dict)
        and set(payload) == set(MAIN_LLM_CONTRACT_EXPECTED_RESPONSE)
        and payload == MAIN_LLM_CONTRACT_EXPECTED_RESPONSE
        and type(payload["sum"]) is int
    )


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError("duplicate JSON object key")
        payload[key] = value
    return payload


def _status_code(exc: Exception) -> int | None:
    value = getattr(exc, "status_code", None)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _request_failure_contract(exc: Exception) -> tuple[str, str]:
    status = _status_code(exc)
    error_type = type(exc).__name__.lower()
    message = str(exc).lower()[:512]
    if status in {401, 403} or any(
        marker in error_type or marker in message
        for marker in ("authentication", "permissiondenied", "unauthorized")
    ):
        return "authorization_failed", "Main LLM 鉴权或权限检查失败"
    if status == 404 or "notfound" in error_type or "model_not_found" in message:
        return "model_not_found", "配置的 Main LLM 模型或接口不存在"
    if status == 429 or "ratelimit" in error_type or "rate limit" in message:
        return "model_rate_limited", "Main LLM 触发限流、额度或配额限制"
    if "timeout" in error_type or "timeout" in message or "timed out" in message:
        return "request_timeout", "Main LLM 固定请求在限定时间内未完成"
    if any(
        marker in error_type or marker in message
        for marker in ("connection", "connecterror", "network", "dns", "tls")
    ):
        return "connection_failed", "Main LLM 服务连接或传输失败"
    if status == 400:
        return "main_llm_request_rejected", "Main LLM provider 拒绝固定请求合同"
    return "unexpected_probe_failure", "Main LLM 固定请求遇到未归类的运行失败"


class MainLlmContractExecutor:
    def __init__(
        self,
        *,
        config_provider: Callable[[], Any],
        model_factory: Callable[[Any], Any] = _build_main_llm_contract_model,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self._config_provider = config_provider
        self._model_factory = model_factory
        self._monotonic_ns = monotonic_ns

    def __call__(self) -> MainLlmContractEvidence:
        try:
            config = self._config_provider()
        except Exception as exc:
            raise MainLlmContractFailure(
                stage="preflight",
                code="invalid_configuration",
                code_label="无法读取 Main LLM 固定合同配置",
            ) from exc
        model, runtime_feature_enabled = _normalized_config(config)
        try:
            client = self._model_factory(config)
        except MainLlmContractFailure:
            raise
        except Exception as exc:
            raise MainLlmContractFailure(
                stage="preflight",
                code="invalid_configuration",
                code_label="无法构造 Main LLM 固定合同客户端",
                configured_model=model,
                runtime_feature_enabled=runtime_feature_enabled,
            ) from exc

        invoke = getattr(client, "invoke", None)
        if not callable(invoke):
            raise MainLlmContractFailure(
                stage="preflight",
                code="invalid_configuration",
                code_label="Main LLM 固定合同客户端不可调用",
                configured_model=model,
                runtime_feature_enabled=runtime_feature_enabled,
            )

        started_ns = self._monotonic_ns()
        try:
            response = invoke(tuple(dict(message) for message in MAIN_LLM_CONTRACT_MESSAGES))
        except Exception as exc:
            elapsed_ms = max((self._monotonic_ns() - started_ns) // 1_000_000, 0)
            code, code_label = _request_failure_contract(exc)
            raise MainLlmContractFailure(
                stage="request" if code != "unexpected_probe_failure" else "unexpected",
                code=code,
                code_label=code_label,
                configured_model=model,
                runtime_feature_enabled=runtime_feature_enabled,
                elapsed_ms=int(elapsed_ms),
                llm_called=True,
            ) from exc
        elapsed_ms = max((self._monotonic_ns() - started_ns) // 1_000_000, 0)
        tool_calls_present = _tool_calls_present(response)
        text = _response_text(response)
        usage_available, input_tokens, output_tokens, total_tokens = _token_usage(
            response
        )
        return MainLlmContractEvidence(
            configured_model=model,
            runtime_feature_enabled=runtime_feature_enabled,
            contract_valid=_contract_valid(
                text,
                tool_calls_present=tool_calls_present,
            ),
            usage_metadata_available=usage_available,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            tool_calls_present=tool_calls_present,
            elapsed_ms=int(elapsed_ms),
        )
