from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BAILIAN_MODEL = "qwen3.7-flash"
BAILIAN_PROMPT = (
    "请用80至150字的自然中文，描述这张图片中明确可见的内容，并概括它传达的"
    "情绪或感情色彩；可以结合人物表情、动作和画面元素判断，但不要猜测被遮挡"
    "或无法确认的细节。"
)
BAILIAN_RESPONSE_BYTES_LIMIT = 256 * 1024
BAILIAN_ANSWER_CHARS_LIMIT = 2048
BAILIAN_BASE_URL_PATTERN = re.compile(
    r"https://ws-[a-z0-9]+\.cn-beijing\.maas\.aliyuncs\.com/compatible-mode/v1"
)
COMPLETE_LEADING_THINK_BLOCK_PATTERN = re.compile(
    r"^\s*<think>.*?</think>\s*",
    re.IGNORECASE | re.DOTALL,
)
STRAY_LEADING_THINK_CLOSE_PATTERN = re.compile(
    r"^\s*(?:</think>\s*)+",
    re.IGNORECASE,
)
REFERENCE_ROOT = PROJECT_ROOT / "data" / "stickers"
REFERENCE_STICKER_ID = "aike_affection_005"
REFERENCE_RELATIVE_FILE = "aike_affection_005.png"
REFERENCE_WIDTH = 500
REFERENCE_HEIGHT = 500
REFERENCE_BYTES = 162_977
REFERENCE_SHA256 = (
    "1b0db22d21fc7ed998cec9da0568c0987ccf9738eea69bf5c8c436609bfed249"
)
REFERENCE_MANIFEST_BYTES_LIMIT = 1_048_576


def _load_private_configuration() -> tuple[str, str]:
    load_dotenv(PROJECT_ROOT / ".env")
    base_url = os.getenv("ALIYUN_BAILIAN_BASE_URL", "").strip().rstrip("/")
    api_key = os.getenv("ALIYUN_BAILIAN_API_KEY", "").strip()
    if not base_url or not api_key:
        raise RuntimeError(
            "请先在 .env 填写 ALIYUN_BAILIAN_BASE_URL 和 "
            "ALIYUN_BAILIAN_API_KEY"
        )
    if BAILIAN_BASE_URL_PATTERN.fullmatch(base_url) is None:
        raise RuntimeError("百炼 URL 必须是北京地域 Workspace 的 compatible-mode/v1 地址")
    return base_url, api_key


def _is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = os.lstat(path)
    except OSError:
        return True
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    return stat.S_ISLNK(metadata.st_mode) or bool(
        attributes & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    )


def _load_registered_reference_png() -> bytes:
    root = REFERENCE_ROOT.resolve(strict=True)
    if root != REFERENCE_ROOT.resolve() or _is_link_or_reparse(root):
        raise RuntimeError("固定视觉诊断资产根目录不安全")
    manifest_path = root / "library.json"
    approved_root = root / "approved"
    if (
        _is_link_or_reparse(manifest_path)
        or _is_link_or_reparse(approved_root)
        or not approved_root.is_dir()
    ):
        raise RuntimeError("固定视觉诊断 manifest 边界不安全")
    manifest_bytes = manifest_path.read_bytes()
    if (
        not manifest_bytes
        or len(manifest_bytes) > REFERENCE_MANIFEST_BYTES_LIMIT
    ):
        raise RuntimeError("固定视觉诊断 manifest 大小无效")
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("固定视觉诊断 manifest 无效") from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != 2
        or not isinstance(manifest.get("stickers"), list)
    ):
        raise RuntimeError("固定视觉诊断 manifest 合同无效")
    matches = [
        item
        for item in manifest["stickers"]
        if isinstance(item, dict)
        and item.get("sticker_id") == REFERENCE_STICKER_ID
    ]
    if len(matches) != 1:
        raise RuntimeError("固定视觉诊断表情登记无效")
    entry = matches[0]
    expected = {
        "relative_file": REFERENCE_RELATIVE_FILE,
        "sha256": REFERENCE_SHA256,
        "media_type": "image/png",
        "width": REFERENCE_WIDTH,
        "height": REFERENCE_HEIGHT,
        "bytes": REFERENCE_BYTES,
        "animated": False,
        "frame_count": 1,
        "duration_ms": 0,
        "scope": "owner_private",
        "enabled": True,
    }
    if any(entry.get(key) != value for key, value in expected.items()):
        raise RuntimeError("固定视觉诊断表情合同已经漂移")
    file_path = approved_root / REFERENCE_RELATIVE_FILE
    resolved_file = file_path.resolve(strict=True)
    if (
        resolved_file.parent != approved_root.resolve(strict=True)
        or _is_link_or_reparse(file_path)
        or not file_path.is_file()
    ):
        raise RuntimeError("固定视觉诊断图片边界不安全")
    content = file_path.read_bytes()
    if (
        not content.startswith(b"\x89PNG\r\n\x1a\n")
        or len(content) != REFERENCE_BYTES
        or hashlib.sha256(content).hexdigest() != REFERENCE_SHA256
        or int.from_bytes(content[16:20], "big") != REFERENCE_WIDTH
        or int.from_bytes(content[20:24], "big") != REFERENCE_HEIGHT
    ):
        raise RuntimeError("固定视觉诊断图片合同无效")
    return content


def _bounded_json(response: httpx.Response) -> dict[str, Any]:
    content = response.content
    if len(content) > BAILIAN_RESPONSE_BYTES_LIMIT:
        raise RuntimeError("百炼响应超过 256 KiB 安全上限")
    if response.status_code != 200:
        if response.status_code in {401, 403}:
            code = "authentication_failed"
        elif response.status_code == 429:
            code = "rate_limited"
        else:
            code = "request_rejected"
        raise RuntimeError(f"百炼请求失败：{code}，HTTP {response.status_code}")
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("百炼返回了无法解析的 UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("百炼响应顶层必须是 JSON object")
    return payload


def _clean_response_content(content: str) -> tuple[str, bool]:
    cleaned = content
    cleanup_applied = False
    while True:
        updated = COMPLETE_LEADING_THINK_BLOCK_PATTERN.sub("", cleaned, count=1)
        if updated == cleaned:
            break
        cleaned = updated
        cleanup_applied = True
    updated = STRAY_LEADING_THINK_CLOSE_PATTERN.sub("", cleaned, count=1)
    if updated != cleaned:
        cleaned = updated
        cleanup_applied = True
    return cleaned.strip(), cleanup_applied


def _extract_result(
    payload: dict[str, Any],
) -> tuple[str, str, dict[str, int], bool]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise RuntimeError("百炼响应 choices 合同无效")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise RuntimeError("百炼响应 choice 合同无效")
    message = choice.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise RuntimeError("百炼响应 assistant message 合同无效")
    if message.get("tool_calls"):
        raise RuntimeError("百炼最小视觉测试意外返回了 tool_calls")
    raw_answer = message.get("content")
    if not isinstance(raw_answer, str) or not raw_answer.strip():
        raise RuntimeError("百炼返回了空的视觉描述")
    if len(raw_answer) > BAILIAN_ANSWER_CHARS_LIMIT:
        raise RuntimeError("百炼视觉描述超过 2048 字符安全上限")
    answer, cleanup_applied = _clean_response_content(raw_answer)
    if not answer:
        raise RuntimeError("百炼视觉描述清理后为空")

    usage = payload.get("usage")
    if not isinstance(usage, dict):
        raise RuntimeError("百炼响应缺少 usage")
    token_usage: dict[str, int] = {}
    for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(name)
        if type(value) is not int or value < 0:
            raise RuntimeError(f"百炼 usage.{name} 合同无效")
        token_usage[name] = value
    if (
        token_usage["prompt_tokens"] + token_usage["completion_tokens"]
        != token_usage["total_tokens"]
    ):
        raise RuntimeError("百炼 token usage 关系不自洽")

    returned_model = payload.get("model")
    model = returned_model if isinstance(returned_model, str) else "unavailable"
    return answer, model, token_usage, cleanup_applied


def main() -> int:
    try:
        base_url, api_key = _load_private_configuration()
        image_bytes = _load_registered_reference_png()
        image_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode(
            "ascii"
        )
        payload = {
            "model": BAILIAN_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": BAILIAN_PROMPT},
                    ],
                }
            ],
            "stream": False,
            "temperature": 0,
            "max_tokens": 256,
            "enable_thinking": False,
        }
        started = time.monotonic()
        timeout = httpx.Timeout(connect=10, read=60, write=10, pool=10)
        with httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        elapsed_ms = max(int((time.monotonic() - started) * 1000), 0)
        result = _bounded_json(response)
        answer, returned_model, usage, cleanup_applied = _extract_result(result)
    except Exception as exc:
        print(f"测试失败：{exc}", file=sys.stderr)
        return 1

    print("测试成功")
    print(f"configured_model={BAILIAN_MODEL}")
    print(f"returned_model={returned_model}")
    print("request_count=1")
    print("client_automatic_retry=false")
    print("tool_definitions_sent=false")
    print("thinking_enabled=false")
    print(f"response_cleanup_applied={str(cleanup_applied).lower()}")
    print(f"reference_sticker_id={REFERENCE_STICKER_ID}")
    print("reference_scope=owner_private")
    print("external_image_upload_planned=true")
    print("external_image_upload_executed=true")
    print("provider_side_persistence_controlled_by_app=false")
    print(f"elapsed_ms={elapsed_ms}")
    print(f"input_tokens={usage['prompt_tokens']}")
    print(f"output_tokens={usage['completion_tokens']}")
    print(f"total_tokens={usage['total_tokens']}")
    print(f"response={answer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
