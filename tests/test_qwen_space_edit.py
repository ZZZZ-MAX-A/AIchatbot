from __future__ import annotations

import base64
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import httpx
from PIL import Image

from pure_ai_chat_loader import AI_CHAT_ROOT, load_qwen_space_edit_module


def image_bytes(
    size: tuple[int, int] = (96, 64),
    color: tuple[int, int, int] = (30, 80, 140),
) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format="PNG")
    return output.getvalue()


class QwenSpaceEditTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_qwen_space_edit_module()

    def settings(self, **overrides):
        values = {
            "enable_qwen_space_edit": True,
            "qwen_space_base_url": "https://unit.invalid",
            "qwen_space_hf_token": "unit-token",
            "qwen_space_submit_timeout_seconds": 60,
            "qwen_space_infer_timeout_seconds": 180,
            "qwen_space_download_timeout_seconds": 300,
            "qwen_space_download_retries": 2,
            "qwen_space_result_ttl_seconds": 1800,
            "qwen_space_max_side": 1024,
            "qwen_space_jpeg_quality": 90,
            "image_gen_max_prompt_chars": 1000,
            "image_gen_max_input_bytes": 10_485_760,
            "image_gen_max_output_bytes": 10_485_760,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_settings_presets_and_prompt_are_explicit(self):
        status = self.module.qwen_space_settings_status
        self.assertEqual(
            status(self.settings(enable_qwen_space_edit=False)),
            "disabled",
        )
        self.assertEqual(
            status(self.settings(qwen_space_base_url="http://unit.invalid")),
            "base_url_invalid",
        )
        self.assertEqual(
            status(self.settings(qwen_space_download_retries=6)),
            "invalid_limits",
        )
        self.assertEqual(status(self.settings()), "ready")

        request = self.module.resolve_qwen_edit_request(
            "动漫 保留发型",
            max_chars=1000,
        )
        self.assertEqual(request.lora_adapter, "Anime-V2")
        self.assertIn("保留发型", request.prompt)
        with self.assertRaisesRegex(
            self.module.QwenSpaceEditError,
            "qwen_mode_unknown",
        ):
            self.module.resolve_qwen_edit_request("不存在的模式", max_chars=1000)
        self.assertEqual(
            self.module._classify_space_error(
                '{"error":"No GPU was available after 60s"}'
            ),
            "qwen_gpu_unavailable",
        )
        self.assertEqual(
            self.module._classify_space_error(
                '{"error":"No GPU was available after 60s"}'
            ),
            "qwen_gpu_unavailable",
        )

    def test_preprocessing_limits_long_side_and_creates_data_url(self):
        prepared = self.module.prepare_qwen_image(
            image_bytes((2000, 1000)),
            max_input_bytes=10_485_760,
            max_side=1024,
            jpeg_quality=90,
        )
        self.assertEqual((prepared.width, prepared.height), (1024, 512))
        self.assertEqual(prepared.media_type, "image/jpeg")
        self.assertTrue(prepared.data_url.startswith("data:image/jpeg;base64,"))
        decoded = base64.b64decode(prepared.data_url.split(",", 1)[1])
        with Image.open(BytesIO(decoded)) as image:
            self.assertEqual(image.size, (1024, 512))

    async def test_submit_uses_current_public_edit_endpoint_and_parses_data_url(self):
        calls: list[httpx.Request] = []
        result_data_url = "data:image/png;base64," + base64.b64encode(
            image_bytes((48, 32))
        ).decode("ascii")

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if request.url.path.endswith("/call/v2/edit_image"):
                payload = json.loads(request.content)
                images = json.loads(payload["images_b64_json"])
                self.assertIsInstance(images, list)
                self.assertEqual(len(images), 1)
                self.assertTrue(images[0].startswith("data:image/"))
                self.assertEqual(payload["steps"], 4)
                self.assertEqual(payload["guidance_scale"], 1.0)
                return httpx.Response(200, json={"event_id": "event-unit-1"})
            if request.url.path.endswith("/call/edit_image/event-unit-1"):
                event_data = json.dumps(
                    [{"image": result_data_url, "seed": 123456}]
                )
                return httpx.Response(
                    200,
                    text=f"event: complete\ndata: {event_data}\n\n",
                    headers={"content-type": "text/event-stream"},
                )
            raise AssertionError(f"Unexpected request: {request.url}")

        transport = httpx.MockTransport(handler)
        real_client = httpx.AsyncClient

        def client_factory(**kwargs):
            return real_client(transport=transport, **kwargs)

        prepared = self.module.prepare_qwen_image(
            image_bytes(),
            max_input_bytes=10_485_760,
            max_side=1024,
            jpeg_quality=90,
        )
        request = self.module.resolve_qwen_edit_request("动漫", max_chars=1000)
        with patch.object(
            self.module.httpx,
            "AsyncClient",
            side_effect=client_factory,
        ):
            remote = await self.module.submit_qwen_edit(
                self.settings(),
                request,
                prepared,
            )

        self.assertEqual(remote.event_id, "event-unit-1")
        self.assertEqual(remote.seed, 123456)
        self.assertEqual(remote.result_url, "")
        self.assertEqual(remote.result_data_url, result_data_url)
        self.assertEqual(len([c for c in calls if c.method == "POST"]), 1)
        self.assertTrue(
            all(c.headers.get("authorization") == "Bearer unit-token" for c in calls)
        )
        self.assertNotIn("unit-token", repr(remote))
        self.assertNotIn(result_data_url, repr(remote))

    async def test_submit_maps_http_status_to_actionable_code(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                404,
                text="Not Found: edit_image endpoint",
                headers={"content-type": "text/plain"},
            )

        transport = httpx.MockTransport(handler)
        real_client = httpx.AsyncClient

        def client_factory(**kwargs):
            return real_client(transport=transport, **kwargs)

        prepared = self.module.prepare_qwen_image(
            image_bytes(),
            max_input_bytes=10_485_760,
            max_side=1024,
            jpeg_quality=90,
        )
        request = self.module.resolve_qwen_edit_request("动漫", max_chars=1000)
        with patch.object(
            self.module.httpx,
            "AsyncClient",
            side_effect=client_factory,
        ):
            with self.assertRaisesRegex(
                self.module.QwenSpaceEditError,
                "qwen_endpoint_not_found",
            ) as raised:
                await self.module.submit_qwen_edit(
                    self.settings(),
                    request,
                    prepared,
                )
        self.assertEqual(raised.exception.context["qwen_http_status"], 404)
        self.assertIn("edit_image endpoint", raised.exception.context["qwen_response_excerpt"])

    async def test_download_resumes_partial_result_without_inference(self):
        content = image_bytes((48, 32), (90, 20, 70))
        remote = self.module.QwenRemoteResult(
            event_id="event-resume-1",
            result_url="https://unit.invalid/gradio_api/file=result.png",
            seed=77,
            media_type="image/png",
        )
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            self.assertEqual(
                request.headers.get("range"),
                f"bytes={len(content) // 2}-",
            )
            return httpx.Response(
                206,
                content=content[len(content) // 2 :],
                headers={"content-type": "image/png"},
            )

        transport = httpx.MockTransport(handler)
        real_client = httpx.AsyncClient

        def client_factory(**kwargs):
            return real_client(transport=transport, **kwargs)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            partial = self.module._partial_path(remote, output_dir)
            partial.write_bytes(content[: len(content) // 2])
            with patch.object(
                self.module.httpx,
                "AsyncClient",
                side_effect=client_factory,
            ):
                artifact = await self.module.download_qwen_result(
                    self.settings(),
                    remote,
                    output_dir=output_dir,
                )
            saved = artifact.path.read_bytes()
            self.assertFalse(partial.exists())

        self.assertEqual(saved, content)
        self.assertEqual(artifact.operation, "qwen_edit")
        self.assertEqual(len(requests), 1)

    def test_runtime_ticket_expires_and_keeps_local_artifact(self):
        runtime = self.module.QwenSpaceRuntime()
        remote = self.module.QwenRemoteResult(
            event_id="event-ticket",
            result_url="https://unit.invalid/gradio_api/file=result.png",
            seed=9,
            media_type="image/png",
        )
        runtime.remember_remote("bot:owner", remote, ttl_seconds=30, now=100)
        self.assertIsNotNone(runtime.ticket("bot:owner", now=129))
        self.assertIsNone(runtime.ticket("bot:owner", now=130))

    def test_nonebot_contract_is_private_memory_free_and_retrievable(self):
        source = (AI_CHAT_ROOT / "__init__.py").read_text(encoding="utf-8")
        command_block = source.split("@qwen_space_edit_cmd.handle()", 1)[1].split(
            "@reset_cmd.handle()",
            1,
        )[0]
        declaration_block = source.split("private_chat = on_message", 1)[1].split(
            "async def run_auto_compression",
            1,
        )[0]

        self.assertIn('"Qwen改图", aliases={"qwen改图"}', declaration_block)
        self.assertIn('"重取改图", aliases={"重新获取改图"}', declaration_block)
        self.assertIn("await require_owner(event, matcher)", command_block)
        self.assertIn("PrivateMessageEvent", command_block)
        self.assertIn('provider="qwen_space"', command_block)
        self.assertIn("submit_qwen_edit(config, request, prepared)", command_block)
        self.assertIn("download_qwen_result(config, remote)", command_block)
        self.assertIn("_qwen_space_runtime.remember_remote(", command_block)
        self.assertNotIn("handle_chat(", command_block)
        self.assertNotIn("save_message(", command_block)
        self.assertNotIn("append_message(", command_block)
        self.assertNotIn("compress_session(", command_block)


if __name__ == "__main__":
    unittest.main()
