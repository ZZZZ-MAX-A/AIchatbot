from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
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
    pid = 123

    def __init__(
        self,
        *,
        returncode: int | None = None,
        stop_mode: str = "success",
    ) -> None:
        self.returncode = returncode
        self.stop_mode = stop_mode
        self.terminate_calls = 0
        self.kill_calls = 0

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminate_calls += 1
        if self.stop_mode == "error":
            raise OSError("private stop detail")
        if self.stop_mode == "success":
            self.returncode = 0

    def kill(self) -> None:
        self.kill_calls += 1
        if self.stop_mode == "error":
            raise OSError("private kill detail")
        if self.stop_mode == "kill":
            self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        if self.returncode is None:
            raise subprocess.TimeoutExpired("fake-tts", timeout)
        return self.returncode


class OwnerConsoleTtsSynthesisTests(unittest.TestCase):
    ARTIFACT_ID = "a" * 32
    OWNER_TOKEN = "b" * 64

    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.tts = load_module(
            "src.plugins.ai_chat.owner_console_tts_synthesis",
            AI_CHAT_ROOT / "owner_console_tts_synthesis.py",
        )

    @staticmethod
    def config(**overrides):
        values = {
            "tts_service_url": "http://127.0.0.1:7861",
            "tts_voice": "reference_voice",
            "tts_emotion": "neutral",
            "enable_tts": True,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    @staticmethod
    def write_wav(
        path: Path,
        *,
        channels: int = 1,
        sample_width: int = 2,
        frame_rate: int = 16_000,
        frame_count: int = 16_000,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as writer:
            writer.setnchannels(channels)
            writer.setsampwidth(sample_width)
            writer.setframerate(frame_rate)
            writer.writeframes(
                b"\x00" * channels * sample_width * frame_count
            )

    def write_artifacts(
        self,
        output_root: Path,
        artifact_id: str | None = None,
    ) -> tuple[Path, Path]:
        artifact = artifact_id or self.ARTIFACT_ID
        output = output_root / f"tts_{artifact}.wav"
        segment = (
            output_root
            / f"tts_{artifact}_segments"
            / "segment_01.wav"
        )
        self.write_wav(output)
        self.write_wav(segment)
        return output, segment

    def successful_response(
        self,
        output_root: Path,
        artifact_id: str | None = None,
    ):
        output, segment = self.write_artifacts(output_root, artifact_id)
        return self.tts.TtsHttpResponse(
            200,
            {
                "ok": True,
                "audio_path": str(output.resolve()),
                "duration_seconds": 1.0,
                "segments": [
                    {
                        "index": 1,
                        "bytes": segment.stat().st_size,
                        "text": "must-not-escape",
                    }
                ],
                "error": "must-not-escape",
            },
        )

    def executor(
        self,
        *,
        output_root: Path,
        health_request,
        synthesis_request,
        process_starter=None,
        clock: FakeClock | None = None,
        artifact_cleaner=None,
        preview_store=None,
    ):
        fake_clock = clock or FakeClock()
        kwargs = {
            "config_provider": self.config,
            "health_request": health_request,
            "synthesis_request": synthesis_request,
            "output_root": output_root,
            "monotonic_ns": fake_clock,
            "sleep": fake_clock.sleep,
            "token_factory": lambda: self.OWNER_TOKEN,
            "artifact_id_factory": lambda: self.ARTIFACT_ID,
            "preview_store": preview_store,
        }
        if process_starter is not None:
            kwargs["process_starter"] = process_starter
        else:
            kwargs["process_starter"] = lambda _token: self.fail(
                "an online-service test must not start TTS"
            )
        if artifact_cleaner is not None:
            kwargs["artifact_cleaner"] = artifact_cleaner
        return self.tts.TtsSynthesisExecutor(**kwargs)

    def test_preexisting_service_uses_exact_payload_cleans_artifacts_and_is_not_stopped(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            calls: list[tuple[str, str, object]] = []

            def health(base_url):
                calls.append(("health", base_url, None))
                return self.tts.TtsHttpResponse(
                    200,
                    {
                        "ok": True,
                        "loaded": False,
                        "runtime_imported": False,
                        "language": "zh",
                    },
                )

            def synthesis(base_url, payload):
                calls.append(("synthesis", base_url, dict(payload)))
                return self.successful_response(root)

            evidence = self.executor(
                output_root=root,
                health_request=health,
                synthesis_request=synthesis,
            )()

            self.assertEqual(
                calls,
                [
                    ("health", "http://127.0.0.1:7861", None),
                    (
                        "synthesis",
                        "http://127.0.0.1:7861",
                        {
                            "artifact_id": self.ARTIFACT_ID,
                            "segments": ["这是一次固定语音合成检查。"],
                            "pauses_ms": [],
                            "voice_id": "reference_voice",
                            "language": "zh",
                            "emotion": "neutral",
                            "max_total_seconds": 20,
                            "bypass_cache": True,
                        },
                    ),
                ],
            )
            self.assertTrue(evidence.service_preexisting)
            self.assertFalse(evidence.service_start_attempted)
            self.assertFalse(evidence.service_owned_by_diagnostic)
            self.assertFalse(evidence.model_loaded_before)
            self.assertFalse(evidence.runtime_imported_before)
            self.assertFalse(evidence.service_stop_attempted)
            self.assertFalse(evidence.service_stopped)
            self.assertTrue(evidence.output_contract_valid)
            self.assertTrue(evidence.artifact_cleanup_attempted)
            self.assertTrue(evidence.artifact_cleanup_succeeded)
            self.assertFalse(evidence.output_retained)
            self.assertFalse(evidence.segment_directory_retained)
            self.assertEqual(evidence.partial_artifact_state, "artifacts_removed")
            self.assertFalse((root / f"tts_{self.ARTIFACT_ID}.wav").exists())
            self.assertFalse(
                (root / f"tts_{self.ARTIFACT_ID}_segments").exists()
            )
            self.assertNotIn("must-not-escape", repr(evidence))
            self.assertNotIn(str(root), repr(evidence))

    def test_health_runtime_contract_is_backward_compatible_but_rejects_impossible_state(
        self,
    ) -> None:
        legacy_unloaded = self.tts._health(
            self.tts.TtsHttpResponse(
                200,
                {"ok": True, "loaded": False, "language": "zh"},
            )
        )
        legacy_loaded = self.tts._health(
            self.tts.TtsHttpResponse(
                200,
                {"ok": True, "loaded": True, "language": "zh"},
            )
        )

        self.assertFalse(legacy_unloaded.runtime_imported)
        self.assertTrue(legacy_loaded.runtime_imported)
        with self.assertRaises(ValueError):
            self.tts._health(
                self.tts.TtsHttpResponse(
                    200,
                    {
                        "ok": True,
                        "loaded": True,
                        "runtime_imported": False,
                        "language": "zh",
                    },
                )
            )

    def test_validated_wav_moves_to_bounded_memory_preview_before_disk_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = self.tts.TtsAudioPreviewStore()
            captured: list[bytes] = []

            def synthesis(_base, _payload):
                response = self.successful_response(root)
                captured.append(
                    (root / f"tts_{self.ARTIFACT_ID}.wav").read_bytes()
                )
                return response

            evidence = self.executor(
                output_root=root,
                health_request=lambda _base: self.tts.TtsHttpResponse(
                    200,
                    {
                        "ok": True,
                        "loaded": False,
                        "runtime_imported": False,
                        "language": "zh",
                    },
                ),
                synthesis_request=synthesis,
                preview_store=store,
            )()

            self.assertTrue(evidence.artifact_cleanup_succeeded)
            self.assertFalse((root / f"tts_{self.ARTIFACT_ID}.wav").exists())
            self.assertTrue(store.bind(7))
            self.assertEqual(store.read(7), captured[0])
            self.assertIsNone(store.read(8))
            self.assertTrue(store.clear(7))
            self.assertIsNone(store.read(7))
            self.assertFalse(store.clear(7))
            with self.assertRaises(ValueError):
                store.publish(b"not-a-wav")

    def test_offline_service_is_started_once_owned_synthesized_cleaned_and_stopped(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            process = FakeProcess()
            health_calls = 0
            started_tokens: list[str] = []
            synthesis_calls = 0

            def health(_base):
                nonlocal health_calls
                health_calls += 1
                if health_calls == 1:
                    raise httpx.ConnectError("offline")
                return self.tts.TtsHttpResponse(
                    200,
                    {
                        "ok": True,
                        "loaded": False,
                        "language": "zh",
                        "lifecycle_owner_fingerprint": hashlib.sha256(
                            self.OWNER_TOKEN.encode()
                        ).hexdigest(),
                    },
                )

            def synthesis(_base, _payload):
                nonlocal synthesis_calls
                synthesis_calls += 1
                return self.successful_response(root)

            evidence = self.executor(
                output_root=root,
                health_request=health,
                synthesis_request=synthesis,
                process_starter=lambda token: (
                    started_tokens.append(token) or process
                ),
            )()

            self.assertEqual(health_calls, 2)
            self.assertEqual(started_tokens, [self.OWNER_TOKEN])
            self.assertEqual(synthesis_calls, 1)
            self.assertFalse(evidence.service_preexisting)
            self.assertTrue(evidence.service_start_attempted)
            self.assertTrue(evidence.service_started)
            self.assertTrue(evidence.service_owned_by_diagnostic)
            self.assertTrue(evidence.service_stop_attempted)
            self.assertTrue(evidence.service_stopped)
            self.assertEqual(process.terminate_calls, 1)
            self.assertEqual(process.kill_calls, 0)
            self.assertTrue(evidence.artifact_cleanup_succeeded)

    def test_connect_timeout_enters_the_same_owned_start_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            process = FakeProcess()
            health_calls = 0
            started_tokens: list[str] = []

            def health(_base):
                nonlocal health_calls
                health_calls += 1
                if health_calls == 1:
                    raise httpx.ConnectTimeout("loopback connect timed out")
                return self.tts.TtsHttpResponse(
                    200,
                    {
                        "ok": True,
                        "loaded": False,
                        "language": "zh",
                        "lifecycle_owner_fingerprint": hashlib.sha256(
                            self.OWNER_TOKEN.encode()
                        ).hexdigest(),
                    },
                )

            evidence = self.executor(
                output_root=root,
                health_request=health,
                synthesis_request=lambda _base, _payload: (
                    self.successful_response(root)
                ),
                process_starter=lambda token: (
                    started_tokens.append(token) or process
                ),
            )()

            self.assertEqual(health_calls, 2)
            self.assertEqual(started_tokens, [self.OWNER_TOKEN])
            self.assertTrue(evidence.service_start_attempted)
            self.assertTrue(evidence.service_owned_by_diagnostic)
            self.assertTrue(evidence.tts_called)
            self.assertTrue(evidence.output_contract_valid)
            self.assertTrue(evidence.artifact_cleanup_succeeded)
            self.assertTrue(evidence.service_stop_attempted)
            self.assertTrue(evidence.service_stopped)

    def test_ownership_mismatch_never_synthesizes_and_stops_held_process(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            process = FakeProcess()
            health_calls = 0
            synthesis_calls: list[str] = []

            def health(_base):
                nonlocal health_calls
                health_calls += 1
                if health_calls == 1:
                    raise httpx.ConnectError("offline")
                return self.tts.TtsHttpResponse(
                    200,
                    {
                        "ok": True,
                        "loaded": False,
                        "language": "zh",
                        "lifecycle_owner_fingerprint": "wrong",
                    },
                )

            executor = self.executor(
                output_root=Path(temp_dir),
                health_request=health,
                synthesis_request=lambda _base, _payload: synthesis_calls.append(
                    "called"
                ),
                process_starter=lambda _token: process,
            )
            with self.assertRaises(self.tts.TtsSynthesisFailure) as raised:
                executor()

            failure = raised.exception
            self.assertEqual(failure.code, "tts_service_ownership_mismatch")
            self.assertTrue(failure.service_start_attempted)
            self.assertFalse(failure.service_owned_by_diagnostic)
            self.assertTrue(failure.service_stop_attempted)
            self.assertTrue(failure.service_stopped)
            self.assertFalse(failure.tts_called)
            self.assertFalse(failure.artifact_cleanup_attempted)
            self.assertEqual(synthesis_calls, [])
            self.assertEqual(process.terminate_calls, 1)

    def test_startup_early_exit_and_timeout_are_bounded_and_stop_only_held_process(
        self,
    ) -> None:
        cases = (
            (
                FakeProcess(returncode=7),
                "tts_managed_process_exited_early",
            ),
            (
                FakeProcess(),
                "tts_service_start_timeout",
            ),
        )
        for process, expected_code in cases:
            with self.subTest(expected_code=expected_code), tempfile.TemporaryDirectory() as temp_dir:
                clock = FakeClock()

                def offline(_base):
                    raise httpx.ConnectError("offline")

                executor = self.executor(
                    output_root=Path(temp_dir),
                    health_request=offline,
                    synthesis_request=lambda _base, _payload: self.fail(
                        "startup failure must not synthesize"
                    ),
                    process_starter=lambda _token, value=process: value,
                    clock=clock,
                )
                with self.assertRaises(self.tts.TtsSynthesisFailure) as raised:
                    executor()
                failure = raised.exception
                self.assertEqual(failure.code, expected_code)
                self.assertTrue(failure.service_start_attempted)
                self.assertFalse(failure.tts_called)
                self.assertTrue(failure.service_stopped)
                if expected_code == "tts_service_start_timeout":
                    self.assertEqual(clock.now_ns, 45_000_000_000)
                    self.assertTrue(failure.service_stop_attempted)
                    self.assertEqual(process.terminate_calls, 1)
                else:
                    self.assertFalse(failure.service_stop_attempted)
                    self.assertEqual(process.terminate_calls, 0)

    def test_existing_malformed_or_timed_out_health_does_not_blind_start(
        self,
    ) -> None:
        cases = (
            httpx.ReadTimeout("slow"),
            ValueError("invalid JSON"),
        )
        for error in cases:
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as temp_dir:
                starts: list[str] = []

                def fail_health(_base, exc=error):
                    raise exc

                executor = self.executor(
                    output_root=Path(temp_dir),
                    health_request=fail_health,
                    synthesis_request=lambda _base, _payload: self.fail(
                        "invalid health must not synthesize"
                    ),
                    process_starter=lambda token: (
                        starts.append(token) or FakeProcess()
                    ),
                )
                with self.assertRaises(self.tts.TtsSynthesisFailure) as raised:
                    executor()
                self.assertEqual(
                    raised.exception.code,
                    "tts_health_contract_invalid",
                )
                self.assertEqual(starts, [])

    def test_post_failure_still_cleans_exact_artifacts_and_stops_owned_process(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            process = FakeProcess()
            health_calls = 0

            def health(_base):
                nonlocal health_calls
                health_calls += 1
                if health_calls == 1:
                    raise httpx.ConnectError("offline")
                return self.tts.TtsHttpResponse(
                    200,
                    {
                        "ok": True,
                        "loaded": False,
                        "language": "zh",
                        "lifecycle_owner_fingerprint": hashlib.sha256(
                            self.OWNER_TOKEN.encode()
                        ).hexdigest(),
                    },
                )

            def synthesis(_base, _payload):
                self.write_artifacts(root)
                return self.tts.TtsHttpResponse(
                    200,
                    {"ok": False, "error": "private server traceback"},
                )

            executor = self.executor(
                output_root=root,
                health_request=health,
                synthesis_request=synthesis,
                process_starter=lambda _token: process,
            )
            with self.assertRaises(self.tts.TtsSynthesisFailure) as raised:
                executor()

            failure = raised.exception
            self.assertEqual(failure.code, "tts_synthesis_failed")
            self.assertTrue(failure.tts_called)
            self.assertTrue(failure.artifact_cleanup_attempted)
            self.assertTrue(failure.artifact_cleanup_succeeded)
            self.assertEqual(
                failure.partial_artifact_state,
                "failed_artifacts_removed",
            )
            self.assertTrue(failure.service_stop_attempted)
            self.assertTrue(failure.service_stopped)
            self.assertFalse((root / f"tts_{self.ARTIFACT_ID}.wav").exists())
            self.assertNotIn("private", repr(failure.__dict__))

    def test_cleanup_exception_does_not_skip_owned_process_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            process = FakeProcess()
            health_calls = 0

            def health(_base):
                nonlocal health_calls
                health_calls += 1
                if health_calls == 1:
                    raise httpx.ConnectError("offline")
                return self.tts.TtsHttpResponse(
                    200,
                    {
                        "ok": True,
                        "loaded": True,
                        "language": "zh",
                        "lifecycle_owner_fingerprint": hashlib.sha256(
                            self.OWNER_TOKEN.encode()
                        ).hexdigest(),
                    },
                )

            evidence = self.executor(
                output_root=root,
                health_request=health,
                synthesis_request=lambda _base, _payload: (
                    self.successful_response(root)
                ),
                process_starter=lambda _token: process,
                artifact_cleaner=lambda _root, _artifact: (_ for _ in ()).throw(
                    RuntimeError("private cleanup failure")
                ),
            )()

            self.assertFalse(evidence.artifact_cleanup_succeeded)
            self.assertTrue(evidence.output_retained)
            self.assertTrue(evidence.segment_directory_retained)
            self.assertTrue(evidence.service_stop_attempted)
            self.assertTrue(evidence.service_stopped)

    def test_stop_timeout_is_reported_without_scanning_other_processes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            process = FakeProcess(stop_mode="timeout")
            health_calls = 0

            def health(_base):
                nonlocal health_calls
                health_calls += 1
                if health_calls == 1:
                    raise httpx.ConnectError("offline")
                return self.tts.TtsHttpResponse(
                    200,
                    {
                        "ok": True,
                        "loaded": True,
                        "language": "zh",
                        "lifecycle_owner_fingerprint": hashlib.sha256(
                            self.OWNER_TOKEN.encode()
                        ).hexdigest(),
                    },
                )

            evidence = self.executor(
                output_root=root,
                health_request=health,
                synthesis_request=lambda _base, _payload: (
                    self.successful_response(root)
                ),
                process_starter=lambda _token: process,
            )()

            self.assertTrue(evidence.service_owned_by_diagnostic)
            self.assertTrue(evidence.service_stop_attempted)
            self.assertFalse(evidence.service_stopped)
            self.assertEqual(process.terminate_calls, 1)
            self.assertEqual(process.kill_calls, 1)

    def test_cleanup_removes_only_exact_artifact_and_preserves_other_runs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            other_id = "c" * 32
            other_output, other_segment = self.write_artifacts(root, other_id)

            evidence = self.executor(
                output_root=root,
                health_request=lambda _base: self.tts.TtsHttpResponse(
                    200,
                    {"ok": True, "loaded": True, "language": "zh"},
                ),
                synthesis_request=lambda _base, _payload: (
                    self.successful_response(root)
                ),
            )()

            self.assertTrue(evidence.artifact_cleanup_succeeded)
            self.assertTrue(other_output.exists())
            self.assertTrue(other_segment.exists())

    def test_unknown_segment_entry_makes_cleanup_incomplete_without_recursive_delete(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output, segment = self.write_artifacts(root)
            unknown = segment.parent / "keep.txt"
            unknown.write_text("owner data", encoding="utf-8")

            cleanup = self.tts._cleanup_artifacts(
                root,
                self.ARTIFACT_ID,
                monotonic_ns=FakeClock(),
            )

            self.assertTrue(cleanup.attempted)
            self.assertFalse(cleanup.succeeded)
            self.assertFalse(cleanup.output_file_retained)
            self.assertTrue(cleanup.segment_directory_retained)
            self.assertFalse(output.exists())
            self.assertFalse(segment.exists())
            self.assertTrue(unknown.exists())

    @unittest.skipIf(os.name == "nt", "Windows symlink creation may require elevation")
    def test_cleanup_unlinks_exact_symlink_without_following_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as outside_dir:
            root = Path(temp_dir)
            target = Path(outside_dir) / "owner.wav"
            self.write_wav(target)
            link = root / f"tts_{self.ARTIFACT_ID}.wav"
            link.symlink_to(target)

            cleanup = self.tts._cleanup_artifacts(root, self.ARTIFACT_ID)

            self.assertTrue(cleanup.succeeded)
            self.assertFalse(os.path.lexists(link))
            self.assertTrue(target.exists())

    def test_non_loopback_and_invalid_config_fail_before_http_or_start(
        self,
    ) -> None:
        cases = (
            {"tts_service_url": "https://127.0.0.1:7861"},
            {"tts_service_url": "http://192.168.1.2:7861"},
            {"tts_service_url": "http://127.0.0.1:7862"},
            {"tts_service_url": "http://127.0.0.1:bad"},
            {"tts_service_url": "http://user:pass@127.0.0.1:7861"},
            {"tts_service_url": "http://127.0.0.1:7861/custom"},
            {"tts_voice": "../../voice"},
            {"tts_emotion": "contains space"},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides), tempfile.TemporaryDirectory() as temp_dir:
                calls: list[str] = []
                executor = self.tts.TtsSynthesisExecutor(
                    config_provider=lambda values=overrides: self.config(
                        **values
                    ),
                    health_request=lambda _base: calls.append("health"),
                    synthesis_request=lambda _base, _payload: calls.append(
                        "synthesis"
                    ),
                    process_starter=lambda _token: calls.append("start"),
                    output_root=Path(temp_dir),
                    artifact_id_factory=lambda: self.ARTIFACT_ID,
                )
                with self.assertRaises(self.tts.TtsSynthesisFailure) as raised:
                    executor()
                self.assertIn(
                    raised.exception.code,
                    {
                        "tts_non_loopback_service_rejected",
                        "tts_invalid_configuration",
                    },
                )
                self.assertEqual(calls, [])

    def test_output_contract_rejects_wrong_artifact_and_invalid_wav(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            wrong = root / f"tts_{'d' * 32}.wav"
            self.write_wav(wrong)
            invalid = root / f"tts_{self.ARTIFACT_ID}.wav"
            invalid.write_bytes(b"x" * 100)
            cases = (
                (
                    {
                        "audio_path": str(wrong.resolve()),
                        "duration_seconds": 1.0,
                    },
                    "tts_output_outside_boundary",
                ),
                (
                    {
                        "audio_path": str(invalid.resolve()),
                        "duration_seconds": 1.0,
                    },
                    "tts_output_invalid_wav",
                ),
            )
            for payload, expected_code in cases:
                with self.subTest(expected_code=expected_code):
                    with self.assertRaises(
                        self.tts.TtsSynthesisFailure
                    ) as raised:
                        self.tts._validate_output(
                            payload,
                            output_root=root,
                            artifact_id=self.ARTIFACT_ID,
                        )
                    self.assertEqual(raised.exception.code, expected_code)

    def test_response_decoder_is_bounded_and_requires_mapping(self) -> None:
        oversized = httpx.Response(
            200,
            content=b"x"
            * (self.tts.TTS_SYNTHESIS_RESPONSE_BYTES_LIMIT + 1),
        )
        with self.assertRaises(ValueError):
            self.tts._decode_response(oversized)
        with self.assertRaises(ValueError):
            self.tts._decode_response(
                httpx.Response(200, content=b"not-json")
            )
        decoded = self.tts._decode_response(
            httpx.Response(
                200,
                content=json.dumps([1, 2]).encode("utf-8"),
            )
        )
        with self.assertRaises(ValueError):
            self.tts._mapping(decoded)

    def test_module_has_no_production_qq_rag_database_or_reliability_dependency(
        self,
    ) -> None:
        source = (AI_CHAT_ROOT / "owner_console_tts_synthesis.py").read_text(
            encoding="utf-8"
        ).lower()
        for forbidden in (
            "request_tts",
            "ensure_tts_service",
            "send_tts_record",
            "reliability",
            "from .database",
            "from .rag",
            "nonebot",
            "onebot",
            "mainagent",
            "devcontext",
            "combinedrag",
            "get-ciminstance",
            "get-process",
            "taskkill",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
