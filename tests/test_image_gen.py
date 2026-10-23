from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from pure_ai_chat_loader import AI_CHAT_ROOT, load_image_gen_module


def png_bytes(color: tuple[int, int, int] = (20, 40, 80)) -> bytes:
    output = BytesIO()
    Image.new("RGB", (32, 24), color).save(output, format="PNG")
    return output.getvalue()


class FakeImages:
    def __init__(self, response, *, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.generate_calls = []
        self.edit_calls = []

    async def generate(self, **kwargs):
        self.generate_calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response

    async def edit(self, **kwargs):
        self.edit_calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, images: FakeImages) -> None:
        self.images = images


class ImageGenTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_image_gen_module()

    def settings(self, **overrides):
        values = {
            "enable_image_gen": True,
            "image_gen_api_key": "unit-secret",
            "image_gen_base_url": "https://unit.invalid/v1",
            "image_gen_model": "grok-imagine-image-quality",
            "image_edit_model": "grok-imagine-image-quality",
            "image_gen_timeout_seconds": 120,
            "image_gen_max_prompt_chars": 1000,
            "image_gen_max_input_bytes": 10_485_760,
            "image_gen_max_output_bytes": 10_485_760,
            "image_gen_pending_edit_seconds": 120,
            "image_gen_cooldown_seconds": 30,
            "image_gen_max_requests_per_hour": 10,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def response(self, content: bytes | None = None):
        encoded = base64.b64encode(content or png_bytes()).decode("ascii")
        return SimpleNamespace(data=[SimpleNamespace(b64_json=encoded, url=None)])

    def test_settings_fail_closed_and_prompt_limits_are_explicit(self):
        status = self.module.image_gen_settings_status
        self.assertEqual(status(self.settings(enable_image_gen=False)), "disabled")
        self.assertEqual(status(self.settings(image_gen_api_key="")), "api_key_missing")
        self.assertEqual(status(self.settings(image_gen_base_url="")), "base_url_missing")
        self.assertEqual(status(self.settings(image_gen_model="")), "model_missing")
        self.assertEqual(status(self.settings(image_gen_timeout_seconds=0)), "invalid_limits")
        self.assertEqual(status(self.settings()), "ready")
        self.assertEqual(
            self.module.normalize_image_prompt("  雨夜\n白猫  ", max_chars=20),
            "雨夜 白猫",
        )
        with self.assertRaisesRegex(self.module.ImageGenError, "prompt_too_long"):
            self.module.normalize_image_prompt("123", max_chars=2)

    async def test_generate_uses_fixed_model_once_without_max_tokens_and_saves_image(self):
        images = FakeImages(self.response())
        client_options = {}

        def client_factory(**kwargs):
            client_options.update(kwargs)
            return FakeClient(images)

        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            self.module, "AsyncOpenAI", side_effect=client_factory
        ):
            artifact = await self.module.generate_image(
                self.settings(),
                "一只雨夜白猫",
                output_dir=Path(temp_dir),
            )
            content = artifact.path.read_bytes()

        self.assertEqual(len(images.generate_calls), 1)
        call = images.generate_calls[0]
        self.assertEqual(call["model"], "grok-imagine-image-quality")
        self.assertEqual(call["n"], 1)
        self.assertEqual(call["size"], "1024x1024")
        self.assertEqual(call["quality"], "high")
        self.assertEqual(call["response_format"], "b64_json")
        self.assertNotIn("max_tokens", call)
        self.assertEqual(client_options["max_retries"], 0)
        self.assertEqual(client_options["base_url"], "https://unit.invalid/v1")
        self.assertNotIn("unit-secret", repr(artifact))
        self.assertEqual(content[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(artifact.operation, "gen")
        self.assertEqual((artifact.width, artifact.height), (32, 24))

    async def test_edit_uses_edit_model_and_validated_source_once(self):
        images = FakeImages(self.response(png_bytes((80, 30, 20))))
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            self.module,
            "AsyncOpenAI",
            return_value=FakeClient(images),
        ):
            artifact = await self.module.edit_image(
                self.settings(),
                "把背景改成夜晚",
                png_bytes(),
                output_dir=Path(temp_dir),
            )

        self.assertEqual(len(images.edit_calls), 1)
        call = images.edit_calls[0]
        self.assertEqual(call["model"], "grok-imagine-image-quality")
        self.assertEqual(call["n"], 1)
        self.assertEqual(call["size"], "1024x1024")
        self.assertEqual(call["quality"], "high")
        self.assertEqual(call["response_format"], "b64_json")
        self.assertNotIn("max_tokens", call)
        filename, source, media_type = call["image"]
        self.assertEqual(filename, "source.png")
        self.assertEqual(source[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(media_type, "image/png")
        mask_filename, mask_content, mask_media_type = call["mask"]
        self.assertEqual(mask_filename, "mask.png")
        self.assertEqual(mask_media_type, "image/png")
        with Image.open(BytesIO(mask_content)) as mask:
            self.assertEqual(mask.format, "PNG")
            self.assertEqual(mask.mode, "RGBA")
            self.assertEqual(mask.size, (32, 24))
            self.assertEqual(mask.getextrema()[3], (0, 0))
        self.assertEqual(artifact.operation, "edit")

    async def test_url_response_remains_supported(self):
        encoded = base64.b64encode(png_bytes()).decode("ascii")
        vision = SimpleNamespace(_download_image_base64=lambda *args: encoded)
        response = SimpleNamespace(
            data=[SimpleNamespace(b64_json=None, url="https://unit.invalid/image")]
        )
        with patch.dict(sys.modules, {"src.plugins.ai_chat.vision": vision}):
            content = await self.module._response_image_bytes(
                response,
                max_bytes=10_485_760,
            )
        self.assertEqual(content[:8], b"\x89PNG\r\n\x1a\n")

    def test_provider_diagnostic_keeps_only_safe_structured_fields(self):
        class ProviderError(RuntimeError):
            status_code = 400
            body = {
                "error": {
                    "message": "prompt=private-text key=unit-secret",
                    "type": "invalid_request_error",
                    "param": "response_format",
                }
            }

        error = ProviderError(
            "https://unit.invalid/v1 prompt=private-text key=unit-secret"
        )
        text = self.module.format_provider_failure_diagnostic(error)
        self.assertEqual(
            text,
            "provider_type=ProviderError http_status=400 "
            "provider_code=invalid_request_error provider_param=response_format "
            'provider_message="[redacted-field] [redacted-field]"',
        )
        self.assertNotIn("unit-secret", text)
        self.assertNotIn("private-text", text)
        self.assertNotIn("unit.invalid", text)

    async def test_url_download_failure_keeps_only_safe_result_metadata(self):
        def failed_download(*_args):
            raise RuntimeError("download rejected: https://cdn.example/result?token=unit-secret")

        vision = SimpleNamespace(_download_image_base64=failed_download)
        response = SimpleNamespace(
            data=[
                SimpleNamespace(
                    b64_json=None,
                    url="https://cdn.example/result?token=unit-secret",
                )
            ]
        )

        with patch.dict(sys.modules, {"src.plugins.ai_chat.vision": vision}):
            with self.assertRaisesRegex(
                self.module.ImageGenError,
                "provider_image_download_failed",
            ) as raised:
                await self.module._response_image_bytes(
                    response,
                    max_bytes=10_485_760,
                )

        context = raised.exception.context
        self.assertEqual(context["stage"], "result_download")
        self.assertEqual(context["response_mode"], "url")
        self.assertEqual(context["result_scheme"], "https")
        self.assertEqual(context["result_host"], "cdn.example")
        self.assertEqual(context["result_has_query"], "yes")
        formatted = self.module.format_image_gen_context(context)
        self.assertIn("result_host=cdn.example", formatted)
        self.assertNotIn("unit-secret", formatted)
        self.assertNotIn("https://", formatted)

    async def test_provider_request_failure_records_safe_request_context(self):
        images = FakeImages(self.response(), error=RuntimeError("provider unavailable"))
        with patch.object(
            self.module,
            "AsyncOpenAI",
            return_value=FakeClient(images),
        ):
            with self.assertRaisesRegex(
                self.module.ImageGenError,
                "provider_generate_failed",
            ) as raised:
                await self.module.generate_image(self.settings(), "测试")

        context = raised.exception.context
        self.assertEqual(context["stage"], "provider_request")
        self.assertEqual(context["model"], "grok-imagine-image-quality")
        self.assertEqual(context["size"], "1024x1024")
        self.assertEqual(context["quality"], "high")
        self.assertEqual(context["response_format"], "b64_json")

    async def test_provider_failure_is_not_retried_and_invalid_output_is_rejected(self):
        failed_images = FakeImages(
            self.response(), error=RuntimeError("provider unavailable")
        )
        with patch.object(
            self.module,
            "AsyncOpenAI",
            return_value=FakeClient(failed_images),
        ):
            with self.assertRaisesRegex(
                self.module.ImageGenError, "provider_generate_failed"
            ):
                await self.module.generate_image(self.settings(), "测试")
        self.assertEqual(len(failed_images.generate_calls), 1)

        invalid_images = FakeImages(
            SimpleNamespace(
                data=[SimpleNamespace(
                    b64_json=base64.b64encode(b"not-an-image").decode("ascii"),
                    url=None,
                )]
            )
        )
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            self.module,
            "AsyncOpenAI",
            return_value=FakeClient(invalid_images),
        ):
            with self.assertRaisesRegex(self.module.ImageGenError, "image_invalid"):
                await self.module.generate_image(
                    self.settings(), "测试", output_dir=Path(temp_dir)
                )
            self.assertEqual(list(Path(temp_dir).iterdir()), [])

    def test_runtime_pending_edit_expiry_cancel_cooldown_and_hourly_limit(self):
        runtime = self.module.ImageGenRuntime()
        runtime.begin_edit("bot:owner", "改成夜景", ttl_seconds=10)
        pending = runtime.pending_edit("bot:owner", now=0)
        self.assertIsNotNone(pending)
        self.assertEqual(pending.prompt, "改成夜景")
        self.assertIsNone(
            runtime.pending_edit("bot:owner", now=pending.expires_at)
        )

        runtime.begin_edit("bot:owner", "换背景", ttl_seconds=10)
        self.assertTrue(runtime.cancel_edit("bot:owner"))
        self.assertFalse(runtime.cancel_edit("bot:owner"))

        first = runtime.claim_request(
            "bot:owner", cooldown_seconds=30, max_requests_per_hour=2, now=100
        )
        cooldown = runtime.claim_request(
            "bot:owner", cooldown_seconds=30, max_requests_per_hour=2, now=110
        )
        second = runtime.claim_request(
            "bot:owner", cooldown_seconds=30, max_requests_per_hour=2, now=131
        )
        hourly = runtime.claim_request(
            "bot:owner", cooldown_seconds=30, max_requests_per_hour=2, now=200
        )
        self.assertTrue(first.allowed)
        self.assertEqual(cooldown.status, "cooldown")
        self.assertTrue(second.allowed)
        self.assertEqual(hourly.status, "hourly_limit")

    def test_nonebot_contract_is_owner_private_two_step_and_memory_free(self):
        source = (AI_CHAT_ROOT / "__init__.py").read_text(encoding="utf-8")
        command_block = source.split("@generate_image_cmd.handle()", 1)[1].split(
            "@reset_cmd.handle()", 1
        )[0]
        declaration_block = source.split("private_chat = on_message", 1)[1].split(
            "async def run_auto_compression", 1
        )[0]

        self.assertIn('on_command(\n    "生成图片"', declaration_block)
        self.assertIn('on_command(\n    "修改图片"', declaration_block)
        self.assertIn('on_command(\n    "取消改图"', declaration_block)
        self.assertIn("priority=10, block=True", declaration_block)
        self.assertIn("await require_owner(event, matcher)", command_block)
        self.assertIn("PrivateMessageEvent", command_block)
        self.assertIn("_image_gen_runtime.begin_edit(", command_block)
        self.assertIn("_image_gen_runtime.consume_edit(key)", command_block)
        self.assertIn("image_refs_from_event(event)", command_block)
        self.assertIn("_send_generated_image(bot, event, artifact)", command_block)
        self.assertIn('"send_private_msg"', source)
        self.assertNotIn("handle_chat(", command_block)
        self.assertNotIn("save_message(", command_block)
        self.assertNotIn("append_message(", command_block)
        self.assertNotIn("compress_session(", command_block)


if __name__ == "__main__":
    unittest.main()
