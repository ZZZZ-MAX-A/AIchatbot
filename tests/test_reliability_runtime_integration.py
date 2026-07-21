from __future__ import annotations

import ast
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PATH = REPO_ROOT / "src" / "plugins" / "ai_chat" / "__init__.py"
LC_PATH = REPO_ROOT / "src" / "plugins" / "ai_chat" / "lc" / "main_agent.py"
PROJECT_INDEX_PATH = (
    REPO_ROOT / "src" / "plugins" / "ai_chat" / "rag" / "project_index.py"
)
MEDIA_RELIABILITY_PATH = (
    REPO_ROOT / "src" / "plugins" / "ai_chat" / "media_reliability.py"
)
VISION_PATH = REPO_ROOT / "src" / "plugins" / "ai_chat" / "vision.py"
VOICE_PATH = REPO_ROOT / "src" / "plugins" / "ai_chat" / "voice.py"


class ReliabilityRuntimeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plugin_source = PLUGIN_PATH.read_text(encoding="utf-8")
        cls.lc_source = LC_PATH.read_text(encoding="utf-8")
        cls.project_index_source = PROJECT_INDEX_PATH.read_text(encoding="utf-8")
        cls.media_reliability_source = MEDIA_RELIABILITY_PATH.read_text(
            encoding="utf-8"
        )
        cls.vision_source = VISION_PATH.read_text(encoding="utf-8")
        cls.voice_source = VOICE_PATH.read_text(encoding="utf-8")

    def function_source(self, source: str, name: str) -> str:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                segment = ast.get_source_segment(source, node)
                if segment is None:
                    break
                return segment
        raise AssertionError(f"function not found: {name}")

    def test_bot_lifecycle_registers_one_start_and_one_stop_hook(self):
        self.assertEqual(
            self.plugin_source.count("_driver.on_startup(_record_runtime_started)"),
            1,
        )
        self.assertEqual(
            self.plugin_source.count("_driver.on_shutdown(_record_runtime_stopped)"),
            1,
        )
        start = self.function_source(self.plugin_source, "_record_runtime_started")
        stop = self.function_source(self.plugin_source, "_record_runtime_stopped")
        self.assertIn("begin_runtime_lifecycle_safely", start)
        self.assertIn("finish_runtime_lifecycle_safely", stop)

    def test_classifier_records_only_fixed_status_mapping_after_classification(self):
        mapping = self.function_source(
            self.plugin_source,
            "_record_remote_sticker_classifier_reliability",
        )
        scheduler = self.function_source(
            self.plugin_source,
            "schedule_remote_sticker_classifier_shadow",
        )

        for status in (
            "requested",
            "not_requested",
            "not_configured",
            "invalid_config",
            "input_invalid",
            "auth_failed",
            "rate_limited",
            "timeout",
            "unavailable",
            "empty_response",
            "response_too_large",
            "json_invalid",
            "contract_invalid",
        ):
            self.assertIn(f'"{status}"', mapping)
        self.assertNotIn("user_text", mapping)
        self.assertNotIn("reply_text", mapping)
        self.assertLess(
            scheduler.index("classification = await classify_sticker_intent("),
            scheduler.index("_record_remote_sticker_classifier_reliability("),
        )

    def test_main_llm_observer_covers_full_action_generation_and_is_fail_open(self):
        plugin_call = self.function_source(self.plugin_source, "run_main_agent_qq_command")
        lc_factory = self.function_source(self.lc_source, "create_main_agent_lc_call_handler")

        self.assertIn("result_observer=_record_main_llm_plan_result", plugin_call)
        self.assertIn("result_observer=result_observer", lc_factory)
        raw_call = self.function_source(self.lc_source, "create_main_llm_call")
        self.assertNotIn("result_observer=result_observer", raw_call)

    def test_document_delivery_records_fixed_failure_and_real_success(self):
        delivery = self.function_source(self.plugin_source, "_send_new_document_deliveries")

        self.assertIn('code="document_delivery_failed"', delivery)
        self.assertIn('record_success_safely("document_delivery", "send_document")', delivery)
        self.assertNotIn("pending.user_id,", delivery)
        self.assertNotIn("delivery.file_path,", delivery)

    def test_project_doc_rebuild_wraps_success_and_failure_without_changing_stats(self):
        rebuild = self.function_source(
            self.project_index_source,
            "rebuild_project_doc_index",
        )

        self.assertIn("_rebuild_project_doc_index", rebuild)
        self.assertIn('record_failure_safely("project_doc_rag", "rebuild_index", exc)', rebuild)
        self.assertIn('record_success_safely("project_doc_rag", "rebuild_index")', rebuild)
        self.assertIn("return stats", rebuild)

    def test_vision_records_only_real_user_inference_not_diagnostic_probe(self):
        describe = self.function_source(self.vision_source, "describe_images")
        diagnostic = self.function_source(
            self.vision_source,
            "check_vision_inference",
        )

        self.assertIn("observe_vision_infer_safely", describe)
        self.assertIn("attempted_count", describe)
        self.assertIn("successful_count", describe)
        self.assertNotIn("observe_vision_infer_safely", diagnostic)

    def test_tts_records_synthesis_after_validation_not_health_or_qq_send(self):
        request = self.function_source(self.voice_source, "request_tts")
        health = self.function_source(self.voice_source, "tts_service_is_healthy")
        observer = self.function_source(
            self.media_reliability_source,
            "observe_tts_synthesis_safely",
        )

        self.assertIn("audio_path.stat().st_size", request)
        self.assertIn("duration_seconds <= 0", request)
        self.assertIn("observe_tts_synthesis_safely(succeeded=True)", request)
        self.assertIn("observe_tts_synthesis_safely(succeeded=False", request)
        self.assertNotIn("observe_tts_synthesis_safely", health)
        self.assertNotIn("qq_adapter", observer)
        self.assertNotIn("send_message", observer)


if __name__ == "__main__":
    unittest.main()
