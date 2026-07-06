from __future__ import annotations

import types
import unittest
from unittest.mock import patch

from pure_ai_chat_loader import load_legacy_diagnostics_modules


class DiagnosticsPureUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_legacy_diagnostics_modules()
        cls.diagnostics = cls.modules["diagnostics"]
        cls.vision = cls.modules["vision"]

    def make_vision_config(self, *, enable_vision: bool = True):
        return types.SimpleNamespace(
            enable_vision=enable_vision,
            vision_ollama_base_url="http://127.0.0.1:11434",
            vision_model="qwen2.5vl:3b",
            vision_num_ctx=16384,
            vision_image_cache_ttl_seconds=120,
            vision_private_image_wait_seconds=5,
            vision_max_images=1,
            vision_max_image_bytes=5242880,
        )

    def test_format_vision_status_includes_inference_check_result(self):
        status = self.diagnostics.OllamaStatus(
            self.diagnostics.CheckResult(True, "service-ok"),
            True,
            ("qwen2.5vl:3b",),
        )
        probe = self.vision.VisionInferenceCheck(True, "probe-ok")

        with patch.object(self.diagnostics, "check_ollama", return_value=status):
            with patch.object(self.diagnostics, "check_vision_inference", return_value=probe):
                reply = self.diagnostics.format_vision_status(
                    self.make_vision_config(),
                    {"total": 0, "private": 0, "group": 0},
                )

        self.assertIn("service-ok", reply)
        self.assertIn("probe-ok", reply)

    def test_format_vision_status_skips_inference_when_ollama_is_down(self):
        status = self.diagnostics.OllamaStatus(
            self.diagnostics.CheckResult(False, "service-down"),
            None,
            (),
        )

        with patch.object(self.diagnostics, "check_ollama", return_value=status):
            with patch.object(self.diagnostics, "check_vision_inference") as probe:
                reply = self.diagnostics.format_vision_status(
                    self.make_vision_config(),
                    {"total": 0, "private": 0, "group": 0},
                )

        probe.assert_not_called()
        self.assertIn("service-down", reply)


if __name__ == "__main__":
    unittest.main()
