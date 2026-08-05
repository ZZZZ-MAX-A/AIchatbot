from __future__ import annotations

import ast
import asyncio
from array import array
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import wave

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module


class FakeCuda:
    def __init__(self) -> None:
        self.empty_cache_calls = 0

    @staticmethod
    def is_available() -> bool:
        return True

    @staticmethod
    def memory_allocated() -> int:
        return 10 * 1024 * 1024

    @staticmethod
    def memory_reserved() -> int:
        return 20 * 1024 * 1024

    @staticmethod
    def max_memory_allocated() -> int:
        return 30 * 1024 * 1024

    @staticmethod
    def max_memory_reserved() -> int:
        return 40 * 1024 * 1024

    def empty_cache(self) -> None:
        self.empty_cache_calls += 1


class FakeModel:
    constructed: list[dict[str, object]] = []

    def __init__(self, **kwargs: object) -> None:
        self.constructed.append(dict(kwargs))


class TtsServiceBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.service = load_module(
            "src.plugins.ai_chat.tts_service_bootstrap_test",
            AI_CHAT_ROOT / "tts_service.py",
        )

    def setUp(self) -> None:
        FakeModel.constructed.clear()

    def test_module_has_no_top_level_torch_or_indextts_import(self) -> None:
        source = (AI_CHAT_ROOT / "tts_service.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        top_level_imports: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                top_level_imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                top_level_imports.add(node.module)

        self.assertNotIn("torch", top_level_imports)
        self.assertFalse(
            any(name == "indextts" or name.startswith("indextts.") for name in top_level_imports)
        )

    def test_health_is_ready_before_runtime_import(self) -> None:
        state = self.service.ModelState(
            runtime_loader=lambda: self.fail("health must not import runtime")
        )
        with patch.object(self.service, "state", state):
            payload = asyncio.run(self.service.health())

        self.assertTrue(payload["ok"])
        self.assertFalse(payload["loaded"])
        self.assertFalse(payload["runtime_imported"])
        self.assertEqual(payload["language"], "zh")
        self.assertIsNone(payload["gpu_memory_mb"])

    def test_first_model_request_imports_runtime_once_and_reuses_it(self) -> None:
        cuda = FakeCuda()
        runtime = self.service.TtsRuntime(
            torch_module=SimpleNamespace(cuda=cuda),
            model_class=FakeModel,
        )
        loader_calls = 0

        def load_runtime():
            nonlocal loader_calls
            loader_calls += 1
            return runtime

        state = self.service.ModelState(runtime_loader=load_runtime)
        first = asyncio.run(state.ensure_loaded())
        second = asyncio.run(state.ensure_loaded())

        self.assertIs(first, second)
        self.assertEqual(loader_calls, 1)
        self.assertEqual(len(FakeModel.constructed), 1)
        self.assertTrue(state.loaded())
        self.assertIs(state.runtime, runtime)

        with patch.object(self.service, "state", state):
            payload = asyncio.run(self.service.health())
        self.assertTrue(payload["runtime_imported"])
        self.assertTrue(payload["loaded"])
        self.assertEqual(
            payload["gpu_memory_mb"],
            {
                "allocated": 10.0,
                "reserved": 20.0,
                "max_allocated": 30.0,
                "max_reserved": 40.0,
            },
        )

    def test_idle_unload_releases_model_without_reimporting_runtime(self) -> None:
        cuda = FakeCuda()
        runtime = self.service.TtsRuntime(
            torch_module=SimpleNamespace(cuda=cuda),
            model_class=FakeModel,
        )
        loader_calls = 0

        def load_runtime():
            nonlocal loader_calls
            loader_calls += 1
            return runtime

        state = self.service.ModelState(runtime_loader=load_runtime)
        asyncio.run(state.ensure_loaded())
        state.last_used_at = 0.0
        asyncio.run(state.unload_if_idle())

        self.assertFalse(state.loaded())
        self.assertIs(state.runtime, runtime)
        self.assertEqual(loader_calls, 1)
        self.assertEqual(cuda.empty_cache_calls, 1)

        asyncio.run(state.ensure_loaded())
        self.assertEqual(loader_calls, 1)
        self.assertEqual(len(FakeModel.constructed), 2)

    def test_runtime_import_failure_stays_unloaded_and_can_be_reported_by_tts(self) -> None:
        calls = 0

        def fail_runtime():
            nonlocal calls
            calls += 1
            raise RuntimeError("private runtime detail")

        state = self.service.ModelState(runtime_loader=fail_runtime)
        with self.assertRaises(RuntimeError):
            asyncio.run(state.ensure_loaded())

        self.assertEqual(calls, 1)
        self.assertFalse(state.loaded())
        self.assertIsNone(state.runtime)

    def test_trailing_low_energy_noise_is_trimmed_with_safe_silence(self) -> None:
        sample_rate = 22_050
        active_frames = int(sample_rate * 0.60)
        weak_tail_frames = int(sample_rate * 0.30)
        samples = array("h", [5_000] * active_frames)
        samples.extend([180] * weak_tail_frames)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "segment.wav"
            with wave.open(str(path), "wb") as writer:
                writer.setnchannels(1)
                writer.setsampwidth(2)
                writer.setframerate(sample_rate)
                writer.writeframes(samples.tobytes())

            changed = self.service.trim_trailing_low_energy_noise(path)

            with wave.open(str(path), "rb") as reader:
                duration = reader.getnframes() / reader.getframerate()
                output = array("h")
                output.frombytes(reader.readframes(reader.getnframes()))

        self.assertTrue(changed)
        self.assertAlmostEqual(duration, 0.74, delta=0.03)
        self.assertTrue(all(value == 0 for value in output[-int(sample_rate * 0.08) :]))

    def test_short_natural_tail_is_not_rewritten(self) -> None:
        sample_rate = 22_050
        active_frames = int(sample_rate * 0.60)
        short_tail_frames = int(sample_rate * 0.06)
        samples = array("h", [5_000] * active_frames)
        samples.extend([180] * short_tail_frames)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "segment.wav"
            with wave.open(str(path), "wb") as writer:
                writer.setnchannels(1)
                writer.setsampwidth(2)
                writer.setframerate(sample_rate)
                writer.writeframes(samples.tobytes())
            before = path.read_bytes()

            changed = self.service.trim_trailing_low_energy_noise(path)

            after = path.read_bytes()

        self.assertFalse(changed)
        self.assertEqual(after, before)

    def test_tail_cleanup_request_flag_defaults_off(self) -> None:
        default_request = self.service.TtsRequest(segments=["test"])
        enabled_request = self.service.TtsRequest(
            segments=["test"],
            trim_trailing_noise=True,
        )

        self.assertFalse(default_request.trim_trailing_noise)
        self.assertTrue(enabled_request.trim_trailing_noise)


if __name__ == "__main__":
    unittest.main()
