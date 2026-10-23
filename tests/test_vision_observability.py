from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from pure_ai_chat_loader import load_legacy_media_modules


class VisionObservabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = load_legacy_media_modules()
        cls.vision = cls.modules["vision"]
        cls.observability = sys.modules["src.plugins.ai_chat.vision_observability"]

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "vision.log"
        log_patch = patch.object(self.observability, "VISION_LOG_PATH", self.path)
        log_patch.start()
        self.addCleanup(log_patch.stop)
        self.image = self.vision.diagnostic_vision_image_base64()
        self.route = self.vision.VisionProviderRoute(
            provider="persona_grok", api_key="sk-PRIVATE-KEY",
            base_url="https://proxy.example/v1?key=PRIVATE-QUERY",
            model="grok-4.6", timeout_seconds=90,
        )

    def rows(self):
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines()]

    def response(self, *, content="图片为红、蓝、绿、白四块纯色色块。", finish="stop", usage=None):
        return SimpleNamespace(
            model="grok-4.6-build", usage=usage,
            choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(
                content=content, reasoning_content="PRIVATE-REASONING",
            ))],
        )

    def run_provider(self, response=None, error=None):
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(
                return_value=response, side_effect=error,
            ))), close=AsyncMock(),
        )
        with patch.object(self.vision, "AsyncOpenAI", return_value=client):
            result = asyncio.run(self._call_provider())
        return result, client

    async def _call_provider(self):
        with self.observability.vision_log_scope(persona="linyin"):
            return await self.vision._openai_chat_vision(self.route, self.image)

    def test_success_records_exact_image_returned_model_usage_and_closes_sdk(self):
        usage = SimpleNamespace(
            prompt_tokens=120, completion_tokens=400, total_tokens=520,
            prompt_tokens_details=SimpleNamespace(cached_tokens=0, image_tokens=0),
            completion_tokens_details=SimpleNamespace(reasoning_tokens=370),
        )
        result, client = self.run_provider(self.response(usage=usage))
        self.assertIn("色块", result)
        client.close.assert_awaited_once()
        row, = self.rows()
        self.assertEqual(row["persona"], "linyin")
        self.assertEqual(row["status"], "succeeded")
        self.assertEqual(row["requested_model"], "grok-4.6")
        self.assertEqual(row["returned_model"], "grok-4.6-build")
        self.assertFalse(row["model_name_matches"])
        self.assertEqual(row["image_sha256"], hashlib.sha256(base64.b64decode(self.image)).hexdigest())
        self.assertEqual((row["width"], row["height"]), (32, 32))
        self.assertEqual(row["reasoning_tokens"], 370)
        self.assertEqual(row["image_tokens"], 0)
        self.assertEqual(row["reasoning_chars"], len("PRIVATE-REASONING"))
        self.assertEqual(row["endpoint_host"], "proxy.example")
        self.assertTrue(row["time"].endswith("+08:00"))
        text = self.path.read_text(encoding="utf-8")
        self.assertNotIn("PRIVATE", text)
        self.assertNotIn(self.image, text)

    def test_missing_usage_is_null_and_does_not_invent_http_status(self):
        self.run_provider(self.response())
        row, = self.rows()
        for name in ("image_tokens", "prompt_tokens", "completion_tokens", "reasoning_tokens", "http_status"):
            self.assertIsNone(row[name])
        self.assertTrue(row["response_received"])

    def test_truncated_empty_response_records_usage_and_failure_stage(self):
        response = self.response(content="", finish="length", usage={
            "completion_tokens": 400, "completion_tokens_details": {"reasoning_tokens": 400},
        })
        with self.assertRaises(self.vision.VisionError):
            self.run_provider(response)
        row, = self.rows()
        self.assertEqual(row["finish_reason"], "length")
        self.assertEqual(row["reasoning_tokens"], 400)
        self.assertEqual(row["raw_description_chars"], 0)
        self.assertEqual(row["error_code"], "empty_description")
        self.assertEqual(row["stage"], "filter")
        self.assertEqual(row["status"], "failed")

    def test_nonempty_truncation_preserves_existing_return_behavior(self):
        result, _ = self.run_provider(self.response(finish="length"))
        self.assertIn("色块", result)
        self.assertEqual(self.rows()[0]["status"], "response_truncated")

    def test_filter_replacement_is_visible_without_original_prompt_text(self):
        self.run_provider(self.response(content="代码包含系统提示 PRIVATE-ORIGINAL-PROMPT"))
        row, = self.rows()
        self.assertTrue(row["filter_changed"])
        self.assertEqual(row["filter_reason"], "prompt_marker")
        self.assertEqual(row["filter_markers"], ["系统提示"])
        self.assertIn("疑似提示注入", row["summary"])
        self.assertNotIn("PRIVATE", self.path.read_text(encoding="utf-8"))

    def test_timeout_closes_client_and_records_cause_without_error_text(self):
        with self.assertRaises(self.vision.VisionError):
            self.run_provider(error=TimeoutError("PRIVATE-REQUEST-URL"))
        row, = self.rows()
        self.assertEqual(row["stage"], "request")
        self.assertEqual(row["cause_type"], "TimeoutError")
        self.assertEqual(row["error_code"], "request_timeout")
        self.assertTrue(row["request_started"])
        self.assertFalse(row["response_received"])
        self.assertNotIn("PRIVATE", self.path.read_text(encoding="utf-8"))

    def test_benign_omission_phrase_exposes_existing_filter_rule(self):
        # This documents the existing false positive, without changing policy.
        self.run_provider(self.response(content="原神十连结果，右下角账号已忽略。"))
        row, = self.rows()
        self.assertEqual(row["filter_markers"], ["忽略"])
        self.assertEqual(row["filter_reason"], "prompt_marker")
        self.assertIn("疑似提示注入", row["summary"])
        self.assertNotIn("原神十连结果", row["summary"])
        self.assertEqual(set(self.vision.PROMPT_INJECTION_MARKERS), self.observability.FILTER_MARKERS)

    def test_cancellation_is_logged_and_propagated(self):
        with self.assertRaises(asyncio.CancelledError):
            self.run_provider(error=asyncio.CancelledError())
        row, = self.rows()
        self.assertEqual(row["status"], "cancelled")
        self.assertEqual(row["stage"], "request")
        self.assertIsNotNone(row["request_ms"])

    def test_log_io_failure_does_not_change_successful_response(self):
        with patch.object(self.observability, "VISION_LOG_PATH", self.path / "child"):
            self.path.write_text("blocked", encoding="utf-8")
            result, _ = self.run_provider(self.response())
        self.assertIn("色块", result)

    def test_download_failure_has_no_model_request_or_source_url(self):
        config = SimpleNamespace(enable_vision=True, vision_max_images=1,
            vision_timeout_seconds=10, vision_max_image_bytes=1024, vision_trusted_local_roots=())
        with (
            patch.object(self.vision, "_image_url_to_base64", AsyncMock(side_effect=self.vision.VisionError("PRIVATE-URL"))),
            patch.object(self.vision, "observe_vision_infer_safely"),
        ):
            descriptions = asyncio.run(self.vision.describe_images(
                config, ["https://PRIVATE-HOST/image?PRIVATE-TOKEN"], role_card_key="linyin",
            ))
        self.assertEqual(descriptions, [self.vision.VISION_FAILURE_DESCRIPTION])
        row, = self.rows()
        self.assertEqual(row["stage"], "download")
        self.assertFalse(row["request_started"])
        self.assertIsNotNone(row["download_ms"])
        self.assertNotIn("PRIVATE", self.path.read_text(encoding="utf-8"))

    def test_size_rejection_has_specific_code_without_model_request(self):
        with self.assertRaises(self.vision.VisionError):
            with self.observability.vision_log_scope() as row:
                row["stage"] = "download"
                self.vision._validated_image_base64(base64.b64decode(self.image), 1)
        row, = self.rows()
        self.assertEqual(row["error_code"], "image_size_limit")
        self.assertFalse(row["request_started"])

    def test_empty_choices_has_response_metadata_and_specific_code(self):
        response = self.response(usage={"completion_tokens": 0})
        response.choices = []
        with self.assertRaises(self.vision.VisionError):
            self.run_provider(response)
        row, = self.rows()
        self.assertTrue(row["response_received"])
        self.assertEqual(row["returned_model"], "grok-4.6-build")
        self.assertEqual(row["completion_tokens"], 0)
        self.assertEqual(row["error_code"], "empty_choices")

    def test_concurrent_personas_and_nested_thread_scope_are_isolated(self):
        def thread_work():
            with self.observability.vision_log_scope() as row:
                row["summary"] = "线程里的图片摘要"
        async def work(persona):
            with self.observability.vision_log_scope(persona=persona) as row:
                row["requested_model"] = persona
                await asyncio.sleep(0)
                await asyncio.to_thread(thread_work)
        async def run():
            await asyncio.gather(work("aike"), work("linyin"))
        asyncio.run(run())
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["persona"] for row in rows}, {"aike", "linyin"})
        self.assertTrue(all(row["requested_model"] == row["persona"] for row in rows))
        self.assertTrue(all(row["summary"] == "线程里的图片摘要" for row in rows))
        self.assertEqual(len({row["trace"] for row in rows}), 2)

    def test_summary_and_closed_schema_remove_identifiers_and_arbitrary_fields(self):
        row = self.observability.build_vision_log({
            "trace": "PRIVATE-TRACE", "api_key": "PRIVATE-KEY", "raw_response": "PRIVATE-RAW",
            "requested_model": "https://bad.invalid/?PRIVATE-KEY", "prompt_tokens": True,
            "summary": "战绩22击败，UID:123456789，邮箱 test@example.com，sk-abcdefghijklmnop",
        })
        text = json.dumps(row, ensure_ascii=False)
        for secret in ("PRIVATE", "123456789", "test@example.com", "sk-abcdefghijklmnop"):
            self.assertNotIn(secret, text)
        self.assertIn("22击败", text)
        self.assertIsNone(row["prompt_tokens"])
        self.assertEqual(row["requested_model"], "")

    def test_bailian_records_metadata_in_same_persona_scope(self):
        result = SimpleNamespace(content="图片是清楚的四色块测试图。", configured_model="qwen3.7-flash",
            returned_model="qwen3.7-flash", input_tokens=100, output_tokens=30, total_tokens=130)
        async def run():
            with self.observability.vision_log_scope(persona="aike"):
                return await asyncio.to_thread(self.vision._bailian_chat_vision, SimpleNamespace(), self.image)
        with patch.object(self.vision, "request_aliyun_bailian_vision", return_value=result):
            asyncio.run(run())
        row, = self.rows()
        self.assertEqual(row["persona"], "aike")
        self.assertEqual(row["provider"], "aliyun_bailian")
        self.assertEqual(row["total_tokens"], 130)
        self.assertTrue(row["model_name_matches"])


if __name__ == "__main__":
    unittest.main()
