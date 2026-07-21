from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pure_ai_chat_loader import load_legacy_media_modules


class MediaReliabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_legacy_media_modules()
        cls.media = cls.modules["media_reliability"]
        cls.database = cls.modules["database"]

    def test_vision_failure_mapping_is_deterministic(self):
        cases = {
            "Ollama 识别超时": "request_timeout",
            "Ollama HTTP 429: rate limit": "model_rate_limited",
            "下载失败 <urlopen error connection refused>": "connection_failed",
            "Ollama HTTP 404: model not found": "model_not_found",
            "Ollama 返回低质量重复内容": "invalid_model_response",
            "本地图片文件不存在 D:/private/image.png": "data_validation_failed",
            "VISION_MODEL 未配置": "invalid_configuration",
            "unknown private detail": "unexpected_runtime_state",
        }
        for error, expected in cases.items():
            with self.subTest(error=error):
                self.assertEqual(self.media.vision_failure_code(error), expected)

    def test_tts_failure_mapping_is_deterministic(self):
        cases = {
            "TTS service did not start within 45 seconds": "request_timeout",
            "HTTP 429 rate limit": "model_rate_limited",
            "ConnectError connection refused": "connection_failed",
            "IndexTTS2 python was not found": "model_not_found",
            "TTS service failed": "invalid_model_response",
            "TTS output not found: D:/private/audio.wav": "data_validation_failed",
            "TTS service script was not found": "invalid_configuration",
            "FileNotFoundError: voice not found: missing_voice": "invalid_configuration",
            "unknown private detail": "unexpected_runtime_state",
        }
        for error, expected in cases.items():
            with self.subTest(error=error):
                self.assertEqual(self.media.tts_failure_code(error), expected)

    def test_vision_observer_records_one_fixed_result_per_logical_batch(self):
        secret_error = RuntimeError(
            "Ollama 返回低质量重复内容 api_key=sk-private https://private.invalid"
        )
        with patch.object(
            self.media,
            "record_result_safely",
            return_value=True,
        ) as recorder:
            recorded = self.media.observe_vision_infer_safely(
                attempted_count=2,
                successful_count=1,
                error=secret_error,
            )

        self.assertTrue(recorded)
        recorder.assert_called_once_with(
            component="vision",
            operation="infer",
            code="invalid_model_response",
            outcome=self.media.ReliabilityOutcome.DEGRADED,
        )
        rendered = repr(recorder.call_args)
        self.assertNotIn("sk-private", rendered)
        self.assertNotIn("private.invalid", rendered)

    def test_vision_observer_does_not_record_non_attempts(self):
        with patch.object(self.media, "record_result_safely") as recorder:
            recorded = self.media.observe_vision_infer_safely(
                attempted_count=0,
                successful_count=0,
                error=RuntimeError("private content"),
            )

        self.assertFalse(recorded)
        recorder.assert_not_called()

    def test_tts_observer_keeps_synthesis_separate_from_qq_delivery(self):
        with patch.object(
            self.media,
            "record_result_safely",
            return_value=True,
        ) as recorder:
            self.media.observe_tts_synthesis_safely(succeeded=True)

        recorder.assert_called_once_with(
            component="tts",
            operation="synthesize",
            code="operation_succeeded",
            outcome=self.media.ReliabilityOutcome.SUCCEEDED,
        )
        self.assertNotIn("qq_adapter", repr(recorder.call_args))
        self.assertNotIn("send_message", repr(recorder.call_args))

    def test_observers_are_fail_open(self):
        with patch.object(
            self.media,
            "record_result_safely",
            side_effect=RuntimeError("database unavailable"),
        ):
            vision_recorded = self.media.observe_vision_infer_safely(
                attempted_count=1,
                successful_count=0,
                error=RuntimeError("connection refused"),
            )
            tts_recorded = self.media.observe_tts_synthesis_safely(
                succeeded=False,
                error=RuntimeError("connection refused"),
            )

        self.assertFalse(vision_recorded)
        self.assertFalse(tts_recorded)

    def test_media_error_secrets_are_not_persisted(self):
        secret = "api_key=sk-private-secret https://private.invalid D:/private/image.png"
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "chatbot.db"
            with patch.object(self.database, "DATABASE_PATH", db_path):
                recorded = self.media.observe_vision_infer_safely(
                    attempted_count=1,
                    successful_count=0,
                    error=RuntimeError(f"Ollama 识别超时 {secret}"),
                )
                raw_database = db_path.read_bytes()
                with self.database.connect() as connection:
                    row = connection.execute(
                        "SELECT component, operation, category, code, outcome "
                        "FROM reliability_event_buckets"
                    ).fetchone()

        self.assertTrue(recorded)
        self.assertNotIn(b"sk-private-secret", raw_database)
        self.assertNotIn(b"private.invalid", raw_database)
        self.assertNotIn(b"D:/private/image.png", raw_database)
        self.assertEqual(
            tuple(row),
            ("vision", "infer", "network", "request_timeout", "failed"),
        )


if __name__ == "__main__":
    unittest.main()
