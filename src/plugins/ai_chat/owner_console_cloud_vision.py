from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from .aliyun_bailian_vision import (
    ALIYUN_BAILIAN_BASE_URL_PATTERN,
    ALIYUN_BAILIAN_VISION_MODEL,
    ALIYUN_BAILIAN_VISION_PROVIDER,
    ALIYUN_BAILIAN_VISION_REGION,
    AliyunBailianVisionError,
    request_aliyun_bailian_vision,
)
from .owner_console_vision_inference import (
    VISION_FIXED_CONTRACT_VERSION,
    VISION_REFERENCE_STICKER_ID,
    VisionReferenceAsset,
    _load_registered_reference_asset,
)


CLOUD_VISION_WORKFLOW = "cloud_vision_fixed_description"
CLOUD_VISION_CONFIRMATION = "run_registered_cloud_vision_fixed_description"
CLOUD_VISION_ACTION_HEADER = "manual-cloud-vision-fixed-description-v1"
CLOUD_VISION_REFERENCE_PREVIEW_ACTION_HEADER = (
    "manual-cloud-vision-reference-preview-v1"
)
CLOUD_VISION_RESPONSE_QUALITY_ACCEPT_ACTION_HEADER = (
    "manual-cloud-vision-response-quality-accept-v1"
)
CLOUD_VISION_RESPONSE_QUALITY_REJECT_ACTION_HEADER = (
    "manual-cloud-vision-response-quality-reject-v1"
)
CLOUD_VISION_RESPONSE_QUALITY_ACCEPT_CONFIRMATION = (
    "accept_latest_cloud_vision_response_quality"
)
CLOUD_VISION_RESPONSE_QUALITY_REJECT_CONFIRMATION = (
    "reject_latest_cloud_vision_response_quality"
)
CLOUD_VISION_FIXED_PROMPT = (
    "请用80至150字的自然中文，描述这张图片中明确可见的内容，并概括它传达的"
    "情绪或感情色彩；可以结合人物表情、动作和画面元素判断，但不要猜测被遮挡"
    "或无法确认的细节。"
)
CLOUD_VISION_LATENCY_ATTENTION_MS = 30_000


@dataclass(frozen=True)
class CloudVisionEvidence:
    runtime_feature_enabled: bool
    provider: str
    region: str
    configured_model: str
    returned_model: str
    endpoint_contract_valid: bool
    workspace_configured: bool
    credentials_configured: bool
    fixed_image_contract: str
    fixed_image_bytes: int
    fixed_image_contract_valid: bool
    reference_sticker_id: str
    registered_reference_asset_read: bool
    external_image_upload_planned: bool
    external_image_upload_executed: bool
    provider_side_persistence_controlled_by_app: bool
    cloud_vision_called: bool
    request_count: int
    client_automatic_retry: bool
    tool_definitions_sent: bool
    thinking_enabled: bool
    response_mode: str
    structured_output_requested: bool
    semantic_contract_automatically_validated: bool
    owner_visual_judgment_required: bool
    response_contract_valid: bool
    response_preview: str
    response_description: str
    response_cleanup_applied: bool
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_elapsed_ms: int


class CloudVisionFailure(RuntimeError):
    def __init__(
        self,
        *,
        stage: str,
        code: str,
        code_label: str,
        **evidence: object,
    ) -> None:
        super().__init__(code)
        self.stage = stage
        self.code = code
        self.code_label = code_label
        defaults: dict[str, object] = {
            "runtime_feature_enabled": True,
            "provider": ALIYUN_BAILIAN_VISION_PROVIDER,
            "region": ALIYUN_BAILIAN_VISION_REGION,
            "configured_model": ALIYUN_BAILIAN_VISION_MODEL,
            "returned_model": "",
            "endpoint_contract_valid": False,
            "workspace_configured": False,
            "credentials_configured": False,
            "fixed_image_contract": VISION_FIXED_CONTRACT_VERSION,
            "fixed_image_bytes": 0,
            "fixed_image_contract_valid": False,
            "reference_sticker_id": VISION_REFERENCE_STICKER_ID,
            "registered_reference_asset_read": False,
            "external_image_upload_planned": True,
            "external_image_upload_executed": False,
            "provider_side_persistence_controlled_by_app": False,
            "cloud_vision_called": False,
            "request_count": 0,
            "client_automatic_retry": False,
            "tool_definitions_sent": False,
            "thinking_enabled": False,
            "response_mode": "natural_text",
            "structured_output_requested": False,
            "semantic_contract_automatically_validated": False,
            "owner_visual_judgment_required": True,
            "response_contract_valid": False,
            "response_preview": "",
            "response_description": "",
            "response_cleanup_applied": False,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "request_elapsed_ms": 0,
        }
        defaults.update(evidence)
        for name, value in defaults.items():
            setattr(self, name, value)


def _failure_stage(code: str) -> str:
    if code in {
        "cloud_vision_provider_invalid",
        "cloud_vision_model_invalid",
        "cloud_vision_credentials_missing",
        "cloud_vision_endpoint_invalid",
        "cloud_vision_image_invalid",
        "cloud_vision_image_too_large",
        "cloud_vision_image_type_unsupported",
        "cloud_vision_prompt_invalid",
    }:
        return "preflight"
    if code in {
        "cloud_vision_response_contract_mismatch",
        "cloud_vision_tool_call_rejected",
        "cloud_vision_empty_response",
        "cloud_vision_low_quality_response",
        "cloud_vision_response_too_large",
        "cloud_vision_usage_metadata_unavailable",
        "cloud_vision_returned_model_mismatch",
    }:
        return "result_validation"
    return "model_inference"


class CloudVisionExecutor:
    def __init__(
        self,
        *,
        config_provider: Callable[[], Any],
        reference_loader: Callable[[], VisionReferenceAsset] = (
            _load_registered_reference_asset
        ),
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config_provider = config_provider
        self._reference_loader = reference_loader
        self._transport = transport
        self._clock = clock

    def __call__(self) -> CloudVisionEvidence:
        started = self._clock()
        config = self._config_provider()
        base_url = str(getattr(config, "aliyun_bailian_base_url", "") or "")
        base_url = base_url.strip().rstrip("/")
        api_key = str(getattr(config, "aliyun_bailian_api_key", "") or "").strip()
        endpoint_contract_valid = bool(
            ALIYUN_BAILIAN_BASE_URL_PATTERN.fullmatch(base_url)
        )
        common = {
            "endpoint_contract_valid": endpoint_contract_valid,
            "workspace_configured": bool(base_url),
            "credentials_configured": bool(api_key),
        }
        try:
            asset = self._reference_loader()
        except Exception as exc:
            raise CloudVisionFailure(
                stage="preflight",
                code="cloud_vision_reference_asset_unavailable",
                code_label="百炼固定视觉诊断参考图不可用",
                **common,
            ) from exc
        image_base64 = base64.b64encode(asset.content).decode("ascii")
        try:
            result = request_aliyun_bailian_vision(
                config,
                image_base64,
                CLOUD_VISION_FIXED_PROMPT,
                transport=self._transport,
            )
        except AliyunBailianVisionError as exc:
            raise CloudVisionFailure(
                stage=_failure_stage(exc.code),
                code=exc.code,
                code_label=str(exc),
                fixed_image_bytes=len(asset.content),
                fixed_image_contract_valid=True,
                registered_reference_asset_read=True,
                external_image_upload_executed=exc.request_executed,
                cloud_vision_called=exc.request_executed,
                request_count=1 if exc.request_executed else 0,
                request_elapsed_ms=max(int((self._clock() - started) * 1000), 0),
                **common,
            ) from exc
        return CloudVisionEvidence(
            runtime_feature_enabled=True,
            provider=ALIYUN_BAILIAN_VISION_PROVIDER,
            region=ALIYUN_BAILIAN_VISION_REGION,
            configured_model=ALIYUN_BAILIAN_VISION_MODEL,
            returned_model=result.returned_model,
            endpoint_contract_valid=True,
            workspace_configured=True,
            credentials_configured=True,
            fixed_image_contract=VISION_FIXED_CONTRACT_VERSION,
            fixed_image_bytes=len(asset.content),
            fixed_image_contract_valid=True,
            reference_sticker_id=asset.sticker_id,
            registered_reference_asset_read=True,
            external_image_upload_planned=True,
            external_image_upload_executed=True,
            provider_side_persistence_controlled_by_app=False,
            cloud_vision_called=True,
            request_count=result.request_count,
            client_automatic_retry=result.client_automatic_retry,
            tool_definitions_sent=result.tool_definitions_sent,
            thinking_enabled=result.thinking_enabled,
            response_mode="natural_text",
            structured_output_requested=False,
            semantic_contract_automatically_validated=False,
            owner_visual_judgment_required=True,
            response_contract_valid=True,
            response_preview=result.content,
            response_description=result.content,
            response_cleanup_applied=result.response_cleanup_applied,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
            request_elapsed_ms=result.elapsed_ms,
        )
