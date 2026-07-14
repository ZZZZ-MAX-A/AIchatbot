from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "plugins" / "ai_chat" / "failure_diagnostics.py"


def load_failure_diagnostics_module():
    spec = importlib.util.spec_from_file_location("failure_diagnostics_test", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FailureDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.failure = load_failure_diagnostics_module()

    def test_classifies_the_five_public_categories(self):
        cases = {
            "invalid_config: missing api key": ("configuration", "invalid_configuration"),
            "429 rate limit quota exceeded": ("model", "model_rate_limited"),
            "HTTP 401 unauthorized": ("permission", "authorization_failed"),
            "Request timed out": ("network", "request_timeout"),
            "sqlite database schema validation failed": ("data", "data_validation_failed"),
        }

        for message, expected in cases.items():
            with self.subTest(message=message):
                diagnosis = self.failure.classify_failure(message)
                self.assertEqual((diagnosis.category.value, diagnosis.code), expected)

    def test_sanitizes_secrets_and_urls(self):
        text = self.failure.sanitize_failure_text(
            "api_key=sk-real-secret123456 https://api.example.com/v1"
        )

        self.assertNotIn("sk-real-secret123456", text)
        self.assertNotIn("api.example.com", text)
        self.assertIn("[redacted-key]", text)
        self.assertIn("[redacted-url]", text)

    def test_inspection_counts_failures_timeouts_calls_and_abnormal_exits(self):
        lines = [
            "2026-07-14T09:00:00 main_agent_llm_succeeded status=completed",
            "2026-07-14T09:10:00 main_agent_llm_failed Request timeout",
            "2026-07-14T09:20:00 document send failed HTTP 403 forbidden",
            "2026-07-14T09:30:00 fatal error process exited unexpectedly exit code 1",
            "2026-07-12T09:00:00 old request failed timeout",
        ]

        inspection = self.failure.inspect_failure_lines(
            lines,
            now=datetime(2026, 7, 14, 10, 0, 0),
            window_hours=24,
        )

        self.assertEqual(inspection.scanned_line_count, 4)
        self.assertEqual(inspection.failure_count, 3)
        self.assertEqual(inspection.timeout_count, 1)
        self.assertEqual(inspection.failed_call_count, 2)
        self.assertEqual(inspection.abnormal_exit_count, 1)
        self.assertEqual(
            dict((category.value, count) for category, count in inspection.category_counts),
            {"permission": 1, "network": 1, "data": 1},
        )

    def test_readable_report_has_boundaries_without_raw_failures(self):
        inspection = self.failure.inspect_failure_lines(
            ["2026-07-14T09:10:00 Request failed timeout api_key=sk-secret123456"],
            now=datetime(2026, 7, 14, 10, 0, 0),
        )

        report = self.failure.format_failure_inspection(inspection)

        self.assertIn("可靠性巡检：需要关注", report)
        self.assertIn("网络问题", report)
        self.assertIn("未重试、重启、修改配置或修复数据", report)
        self.assertNotIn("sk-secret123456", report)
        self.assertNotIn("Request failed", report)

    def test_user_message_is_categorized_and_actionable(self):
        message = self.failure.format_failure_user_message(
            RuntimeError("model_not_found"),
            component="文档生成",
        )

        self.assertIn("文档生成失败", message)
        self.assertIn("模型问题 / model_not_found", message)
        self.assertIn("检查模型是否存在", message)

    def test_document_delivery_failures_have_specific_safe_codes(self):
        cases = {
            "document_delivery_too_many_slides": "presentation_slide_limit_exceeded",
            "document_delivery_delivery_integrity_failed": "artifact_integrity_failed",
            "document_delivery_send_failed": "document_delivery_failed",
            "document_delivery_approval_context_invalid": "approval_context_invalid",
            "document_delivery_arguments_unavailable": "required_arguments_unavailable",
        }

        for raw_error, expected_code in cases.items():
            with self.subTest(raw_error=raw_error):
                diagnosis = self.failure.classify_failure(raw_error)
                self.assertEqual(diagnosis.code, expected_code)
                message = self.failure.format_failure_user_message(
                    RuntimeError(raw_error),
                    component="审批恢复",
                )
                self.assertIn(expected_code, message)

    def test_document_delivery_failures_have_specific_safe_codes(self):
        cases = {
            "document_delivery_too_many_slides": "presentation_slide_limit_exceeded",
            "document_delivery_delivery_integrity_failed": "artifact_integrity_failed",
            "document_delivery_send_failed": "document_delivery_failed",
            "document_delivery_approval_context_invalid": "approval_context_invalid",
            "document_delivery_arguments_unavailable": "required_arguments_unavailable",
        }

        for raw_error, expected_code in cases.items():
            with self.subTest(raw_error=raw_error):
                diagnosis = self.failure.classify_failure(raw_error)
                self.assertEqual(diagnosis.code, expected_code)
                message = self.failure.format_failure_user_message(
                    RuntimeError(raw_error),
                    component="审批恢复",
                )
                self.assertIn(expected_code, message)


if __name__ == "__main__":
    unittest.main()
