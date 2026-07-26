from __future__ import annotations

import base64
import hashlib
import subprocess
import unittest
from types import SimpleNamespace

import httpx

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module


class FakeClock:
    def __init__(self) -> None:
        self.now_ns = 0

    def __call__(self) -> int:
        return self.now_ns

    def advance_ms(self, milliseconds: int) -> None:
        self.now_ns += milliseconds * 1_000_000

    def sleep(self, seconds: float) -> None:
        self.now_ns += round(seconds * 1_000_000_000)


class FakeProcess:
    pid = 456

    def __init__(self, *, returncode=None, stop_mode="success") -> None:
        self.returncode = returncode
        self.stop_mode = stop_mode
        self.terminate_calls = 0
        self.kill_calls = 0

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminate_calls += 1
        if self.stop_mode == "error":
            raise OSError("private stop error")
        if self.stop_mode == "success":
            self.returncode = 0

    def kill(self):
        self.kill_calls += 1
        if self.stop_mode == "kill":
            self.returncode = -9
        elif self.stop_mode == "error":
            raise OSError("private kill error")

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("fake-ollama", timeout)
        return self.returncode


class OwnerConsoleVisionInferenceTests(unittest.TestCase):
    MODEL = "qwen2.5vl:3b"

    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.vision = load_module(
            "src.plugins.ai_chat.owner_console_vision_inference",
            AI_CHAT_ROOT / "owner_console_vision_inference.py",
        )
        cls.reference = cls.vision._load_registered_reference_asset()

    @staticmethod
    def config(**overrides):
        values = {
            "vision_ollama_base_url": "http://127.0.0.1:11434",
            "vision_model": "qwen2.5vl:3b",
            "enable_vision": True,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def tags(self, models=None):
        names = [self.MODEL] if models is None else models
        return self.vision.VisionHttpResponse(
            200,
            {"models": [{"name": name, "digest": "private"} for name in names]},
        )

    def ps(self, models=None):
        return self.tags([] if models is None else models)

    def chat(self, content=None, **overrides):
        payload = {
            "done": True,
            "message": {
                "role": "assistant",
                "content": content or (
                    "画面中是一名黑白双色头发的卡通人物，"
                    "双手抱着红色爱心，周围还有多个粉红色爱心。"
                ),
            },
            "prompt_eval_count": 72,
            "eval_count": 28,
        }
        payload.update(overrides)
        return self.vision.VisionHttpResponse(200, payload)

    def executor(
        self,
        *,
        tags_request=None,
        ps_request=None,
        chat_request=None,
        process_starter=None,
        clock=None,
        reference_loader=None,
        config_provider=None,
    ):
        kwargs = {
            "config_provider": config_provider or self.config,
            "tags_request": tags_request or (lambda _base: self.tags()),
            "ps_request": ps_request or (lambda _base: self.ps()),
            "chat_request": chat_request or (
                lambda _base, _payload: self.chat()
            ),
            "process_starter": process_starter
            or (lambda: self.fail("preexisting service must not start")),
            "reference_loader": reference_loader or (lambda: self.reference),
        }
        if clock is not None:
            kwargs["monotonic_ns"] = clock
            kwargs["sleep"] = clock.sleep
        return self.vision.VisionInferenceExecutor(**kwargs)

    def test_registered_sticker_png_has_stable_manifest_hash_and_dimensions(self):
        asset = self.vision._load_registered_reference_asset()
        image = asset.content
        self.assertEqual(asset.sticker_id, "aike_affection_005")
        self.assertEqual(asset.media_type, "image/png")
        self.assertEqual(len(image), 162977)
        self.assertEqual(
            hashlib.sha256(image).hexdigest(),
            "1b0db22d21fc7ed998cec9da0568c0987ccf9738eea69bf5c8c436609bfed249",
        )
        self.assertTrue(self.vision._fixed_image_contract_valid(image))

        width = int.from_bytes(image[16:20], "big")
        height = int.from_bytes(image[20:24], "big")
        self.assertEqual((width, height), (500, 500))

    def test_preexisting_loaded_model_runs_once_without_unload(self):
        ps_calls = 0
        chat_payloads = []

        def ps(_base):
            nonlocal ps_calls
            ps_calls += 1
            return self.ps([self.MODEL])

        evidence = self.executor(
            ps_request=ps,
            chat_request=lambda _base, payload: (
                chat_payloads.append(payload) or self.chat()
            ),
        )()

        self.assertTrue(evidence.service_preexisting)
        self.assertFalse(evidence.service_start_attempted)
        self.assertTrue(evidence.model_loaded_before)
        self.assertFalse(evidence.keep_alive_zero_used)
        self.assertNotIn("keep_alive", chat_payloads[0])
        self.assertEqual(ps_calls, 1)
        self.assertTrue(evidence.model_cleanup_verified)
        self.assertEqual(evidence.model_cleanup_poll_count, 0)
        self.assertTrue(evidence.response_contract_valid)
        self.assertEqual(evidence.response_mode, "natural_text")
        self.assertFalse(evidence.structured_output_requested)
        self.assertFalse(evidence.semantic_contract_automatically_validated)
        self.assertTrue(evidence.owner_visual_judgment_required)
        self.assertEqual(evidence.reference_sticker_id, "aike_affection_005")
        self.assertTrue(evidence.registered_reference_asset_read)
        self.assertFalse(evidence.expected_answer_disclosed_in_prompt)
        self.assertIn("黑白双色头发", evidence.response_description)
        self.assertTrue(evidence.response_content_exposed_to_owner)
        self.assertEqual(evidence.total_tokens, 100)

    def test_preexisting_unloaded_model_uses_keep_alive_zero_and_verifies_cleanup(self):
        ps_calls = 0
        chat_payloads = []

        def ps(_base):
            nonlocal ps_calls
            ps_calls += 1
            return self.ps([])

        evidence = self.executor(
            ps_request=ps,
            chat_request=lambda _base, payload: (
                chat_payloads.append(payload) or self.chat()
            ),
        )()

        self.assertFalse(evidence.model_loaded_before)
        self.assertTrue(evidence.keep_alive_zero_used)
        self.assertEqual(chat_payloads[0]["keep_alive"], 0)
        self.assertEqual(ps_calls, 2)
        self.assertTrue(evidence.model_cleanup_required)
        self.assertTrue(evidence.model_cleanup_verified)
        self.assertEqual(evidence.model_cleanup_poll_count, 1)

    def test_cleanup_poll_waits_for_ollama_to_remove_model_without_retrying_chat(self):
        clock = FakeClock()
        ps_calls = 0
        chat_calls = 0

        def ps(_base):
            nonlocal ps_calls
            ps_calls += 1
            return self.ps([] if ps_calls == 1 or ps_calls >= 4 else [self.MODEL])

        def chat(_base, _payload):
            nonlocal chat_calls
            chat_calls += 1
            return self.chat()

        evidence = self.executor(
            ps_request=ps,
            chat_request=chat,
            clock=clock,
        )()

        self.assertEqual(chat_calls, 1)
        self.assertEqual(ps_calls, 4)
        self.assertTrue(evidence.model_cleanup_verified)
        self.assertEqual(evidence.model_cleanup_poll_count, 3)
        self.assertEqual(evidence.cleanup_elapsed_ms, 500)

    def test_payload_is_fixed_has_one_memory_image_and_no_tools(self):
        payloads = []
        self.executor(
            chat_request=lambda _base, payload: (
                payloads.append(payload) or self.chat()
            )
        )()
        payload = payloads[0]
        self.assertEqual(payload["model"], self.MODEL)
        self.assertFalse(payload["stream"])
        self.assertNotIn("format", payload)
        self.assertEqual(payload["options"], {"num_ctx": 4096, "temperature": 0})
        self.assertNotIn("tools", payload)
        self.assertEqual(len(payload["messages"]), 1)
        message = payload["messages"][0]
        self.assertEqual(message["role"], "user")
        self.assertEqual(
            message["content"],
            "请用自然中文客观描述这张图片中实际可见的内容。",
        )
        self.assertEqual(len(message["images"]), 1)
        self.assertEqual(
            base64.b64decode(message["images"][0], validate=True),
            self.reference.content,
        )
        prompt = message["content"].lower()
        for undisclosed in (
            "json",
            "contract_version",
            "subject_type",
            "hair_colors",
            "eye_color_family",
            "held_object",
            "floating_symbols",
            "visual_theme",
            "anime_character",
            "pink_red",
            "affection",
            '"black"',
            '"white"',
            '"heart"',
            '"hearts"',
        ):
            self.assertNotIn(undisclosed, prompt)

    def test_offline_service_is_started_owned_inferred_and_stopped(self):
        process = FakeProcess()
        tag_calls = 0
        starts = 0

        def tags(_base):
            nonlocal tag_calls
            tag_calls += 1
            if tag_calls == 1:
                raise httpx.ConnectError("offline")
            return self.tags()

        def start():
            nonlocal starts
            starts += 1
            return process

        evidence = self.executor(
            tags_request=tags,
            ps_request=lambda _base: self.ps([]),
            process_starter=start,
        )()

        self.assertEqual(starts, 1)
        self.assertFalse(evidence.service_preexisting)
        self.assertTrue(evidence.service_started)
        self.assertTrue(evidence.service_owned_by_diagnostic)
        self.assertEqual(
            evidence.service_ownership_basis,
            "offline_precheck_popen_handle",
        )
        self.assertTrue(evidence.service_stop_attempted)
        self.assertTrue(evidence.service_stopped)
        self.assertEqual(process.terminate_calls, 1)

    def test_exited_process_with_sudden_service_is_ownership_ambiguous_and_not_stopped(self):
        process = FakeProcess(returncode=7)
        tag_calls = 0

        def tags(_base):
            nonlocal tag_calls
            tag_calls += 1
            if tag_calls == 1:
                raise httpx.ConnectError("offline")
            return self.tags()

        with self.assertRaises(self.vision.VisionInferenceFailure) as raised:
            self.executor(
                tags_request=tags,
                process_starter=lambda: process,
            )()
        self.assertEqual(
            raised.exception.code,
            "vision_service_ownership_ambiguous",
        )
        self.assertFalse(raised.exception.service_owned_by_diagnostic)
        self.assertFalse(raised.exception.service_stop_attempted)
        self.assertEqual(process.terminate_calls, 0)

    def test_start_timeout_is_bounded_and_stops_only_held_process(self):
        clock = FakeClock()
        process = FakeProcess()

        def offline(_base):
            raise httpx.ConnectError("offline")

        with self.assertRaises(self.vision.VisionInferenceFailure) as raised:
            self.executor(
                tags_request=offline,
                process_starter=lambda: process,
                clock=clock,
            )()
        self.assertEqual(raised.exception.code, "vision_service_start_timeout")
        self.assertEqual(clock.now_ns, 30_000_000_000)
        self.assertTrue(raised.exception.service_stop_attempted)
        self.assertTrue(raised.exception.service_stopped)
        self.assertEqual(process.terminate_calls, 1)

    def test_malformed_or_timed_out_existing_service_does_not_blind_start(self):
        for error in (httpx.ReadTimeout("slow"), ValueError("bad json")):
            with self.subTest(error=type(error).__name__):
                starts = []

                def fail_tags(_base, exc=error):
                    raise exc

                with self.assertRaises(self.vision.VisionInferenceFailure) as raised:
                    self.executor(
                        tags_request=fail_tags,
                        process_starter=lambda: starts.append("started"),
                    )()
                self.assertEqual(
                    raised.exception.code,
                    "vision_service_contract_invalid",
                )
                self.assertEqual(starts, [])

    def test_missing_model_and_unavailable_residency_never_infer(self):
        cases = (
            (
                lambda _base: self.tags([]),
                lambda _base: self.ps([]),
                "vision_model_not_found",
            ),
            (
                lambda _base: self.tags(),
                lambda _base: (_ for _ in ()).throw(ValueError("bad ps")),
                "vision_model_residency_unavailable",
            ),
        )
        for tags, ps, code in cases:
            with self.subTest(code=code):
                calls = []
                with self.assertRaises(self.vision.VisionInferenceFailure) as raised:
                    self.executor(
                        tags_request=tags,
                        ps_request=ps,
                        chat_request=lambda _base, _payload: calls.append("chat"),
                    )()
                self.assertEqual(raised.exception.code, code)
                self.assertEqual(calls, [])

    def test_only_readable_natural_chinese_response_contract_is_automatic(self):
        cases = (
            (self.chat(content="   "), "vision_empty_response"),
            (self.chat(content="!!!!!!!!!!!!"), "vision_low_quality_response"),
            (
                self.chat(content="The image contains a character."),
                "vision_low_quality_response",
            ),
            (
                self.chat(content="一张图片"),
                "vision_low_quality_response",
            ),
            (self.chat(done=False), "vision_response_contract_mismatch"),
        )
        for response, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(self.vision.VisionInferenceFailure) as raised:
                    self.executor(
                        chat_request=lambda _base, _payload, value=response: value,
                )()
                self.assertEqual(raised.exception.code, code)
                self.assertFalse(raised.exception.response_contract_valid)
                content = response.payload.get("message", {}).get("content")
                if (
                    response.payload.get("done") is True
                    and isinstance(content, str)
                    and content.strip()
                ):
                    self.assertTrue(raised.exception.response_preview)

        semantically_inaccurate = self.executor(
            chat_request=lambda _base, _payload: self.chat(
                content="画面中似乎是一名戴着帽子的卡通人物，整体采用鲜艳配色。"
            )
        )()
        self.assertTrue(semantically_inaccurate.response_contract_valid)
        self.assertFalse(
            semantically_inaccurate.semantic_contract_automatically_validated
        )
        self.assertEqual(
            semantically_inaccurate.response_description,
            "画面中似乎是一名戴着帽子的卡通人物，整体采用鲜艳配色。",
        )

    def test_http_rejection_and_oversized_answer_are_failed(self):
        rejected = self.vision.VisionHttpResponse(503, {"error": "private"})
        cases = (
            (rejected, "vision_request_rejected"),
            (
                self.chat(content="x" * 2049),
                "vision_response_too_large",
            ),
        )
        for response, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(self.vision.VisionInferenceFailure) as raised:
                    self.executor(
                        chat_request=lambda _base, _payload, value=response: value,
                    )()
                self.assertEqual(raised.exception.code, code)

    def test_cleanup_failure_is_evidence_and_owned_process_still_stops(self):
        process = FakeProcess()
        clock = FakeClock()
        tag_calls = 0
        ps_calls = 0

        def tags(_base):
            nonlocal tag_calls
            tag_calls += 1
            if tag_calls == 1:
                raise httpx.ConnectError("offline")
            return self.tags()

        def ps(_base):
            nonlocal ps_calls
            ps_calls += 1
            return self.ps([] if ps_calls == 1 else [self.MODEL])

        evidence = self.executor(
            tags_request=tags,
            ps_request=ps,
            process_starter=lambda: process,
            clock=clock,
        )()
        self.assertTrue(evidence.response_contract_valid)
        self.assertFalse(evidence.model_cleanup_verified)
        self.assertEqual(evidence.model_cleanup_poll_count, 21)
        self.assertEqual(evidence.cleanup_elapsed_ms, 5000)
        self.assertTrue(evidence.service_stopped)

    def test_non_loopback_and_invalid_reference_fail_before_http_or_start(self):
        configs = (
            {"vision_ollama_base_url": "https://127.0.0.1:11434"},
            {"vision_ollama_base_url": "http://192.168.1.2:11434"},
            {"vision_ollama_base_url": "http://127.0.0.1:11435"},
            {"vision_ollama_base_url": "http://user:pass@127.0.0.1:11434"},
            {"vision_model": "../../model name"},
        )
        for overrides in configs:
            with self.subTest(overrides=overrides):
                calls = []
                with self.assertRaises(self.vision.VisionInferenceFailure) as raised:
                    self.executor(
                        config_provider=lambda values=overrides: self.config(**values),
                        tags_request=lambda _base: calls.append("tags"),
                        process_starter=lambda: calls.append("start"),
                    )()
                self.assertIn(
                    raised.exception.code,
                    {
                        "vision_invalid_configuration",
                        "vision_non_loopback_service_rejected",
                    },
                )
                self.assertEqual(calls, [])

        bad_reference = self.vision.VisionReferenceAsset(
            sticker_id="aike_affection_005",
            content=b"not-the-fixed-image",
            media_type="image/png",
            width=500,
            height=500,
        )
        with self.assertRaises(self.vision.VisionInferenceFailure) as raised:
            self.executor(reference_loader=lambda: bad_reference)()
        self.assertEqual(
            raised.exception.code,
            "vision_fixed_image_contract_invalid",
        )

        calls = []
        with self.assertRaises(self.vision.VisionInferenceFailure) as raised:
            self.executor(
                reference_loader=lambda: (_ for _ in ()).throw(
                    ValueError("disabled or drifted")
                ),
                tags_request=lambda _base: calls.append("tags"),
            )()
        self.assertEqual(
            raised.exception.code,
            "vision_reference_asset_unavailable",
        )
        self.assertEqual(calls, [])

    def test_decoder_is_bounded_and_module_has_no_production_dependencies(self):
        with self.assertRaises(ValueError):
            self.vision._decode_content(
                200,
                b"x" * (self.vision.VISION_RESPONSE_BYTES_LIMIT + 1),
            )
        with self.assertRaises(ValueError):
            self.vision._decode_content(200, b"not-json")

        source = (AI_CHAT_ROOT / "owner_console_vision_inference.py").read_text(
            encoding="utf-8"
        ).lower()
        for forbidden in (
            "describe_images",
            "diagnostic_vision_image_base64",
            "check_vision_inference",
            "from .database",
            "from .rag",
            "reliability",
            "nonebot",
            "onebot",
            "mainagent",
            "devcontext",
            "combinedrag",
            "start-ollama-vision",
            "ensure-ollama",
            "get-ciminstance",
            "get-process",
            "taskkill",
            "ollama pull",
            "ollama stop",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
