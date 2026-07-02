from __future__ import annotations

import importlib.util
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "plugins" / "ai_chat" / "main_agent_observability.py"


def load_observability_module():
    spec = importlib.util.spec_from_file_location("main_agent_observability_test", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MainAgentObservabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.obs = load_observability_module()

    def test_redacted_base_url_keeps_endpoint_but_removes_query_and_userinfo(self):
        self.assertEqual(
            self.obs.redacted_base_url("https://user:secret@api.example.com:8443/v1?key=sk-test"),
            "https://api.example.com:8443/v1",
        )

    def test_failure_log_message_summarizes_config_without_api_key(self):
        config = types.SimpleNamespace(
            main_llm_model="gpt-5.5",
            main_llm_base_url="https://api.example.com/v1?token=sk-secret12345",
            main_llm_api_key="sk-real-secret12345",
        )

        message = self.obs.build_main_llm_failure_log_message(
            config=config,
            phase="action_request",
            error_type="APIConnectionError",
            error_message="Connection error. api_key=sk-real-secret12345",
        )

        self.assertIn("main_agent_llm_failed", message)
        self.assertIn("phase=action_request", message)
        self.assertIn("error_type=APIConnectionError", message)
        self.assertIn("model=gpt-5.5", message)
        self.assertIn("base_url=https://api.example.com/v1", message)
        self.assertIn("api_key_configured=yes", message)
        self.assertNotIn("sk-real-secret12345", message)
        self.assertNotIn("sk-secret12345", message)


if __name__ == "__main__":
    unittest.main()
