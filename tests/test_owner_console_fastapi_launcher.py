from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from pure_ai_chat_loader import REPO_ROOT


class OwnerConsoleFastApiLauncherTests(unittest.TestCase):
    def test_start_script_registers_independent_manual_diagnostic_switches(self):
        script = (REPO_ROOT / "scripts" / "start-owner-console.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("[switch]$EnableProjectDocRagProbe", script)
        self.assertIn("[switch]$EnableMemoryRagConsistencyProbe", script)
        self.assertIn("[switch]$EnableMainLlmContractProbe", script)
        self.assertIn("[switch]$EnableTtsSynthesisProbe", script)
        self.assertIn("[switch]$EnableCloudVisionProbe", script)
        self.assertIn("[switch]$EnableApprovalActions", script)
        self.assertIn("[switch]$EnableTaskActions", script)
        self.assertIn("[switch]$EnableAccessActions", script)
        self.assertIn("$EnableProjectDocRagProbe -or", script)
        self.assertIn("$EnableMemoryRagConsistencyProbe -or", script)
        self.assertIn("$EnableMainLlmContractProbe", script)
        self.assertIn("$EnableTtsSynthesisProbe", script)
        self.assertIn("$EnableCloudVisionProbe", script)
        self.assertIn("OWNER_CONSOLE_MEMORY_RAG_CONSISTENCY_ENABLED", script)
        self.assertIn("OWNER_CONSOLE_MAIN_LLM_CONTRACT_ENABLED", script)
        self.assertIn("OWNER_CONSOLE_TTS_SYNTHESIS_ENABLED", script)
        self.assertIn("OWNER_CONSOLE_VISION_INFERENCE_ENABLED", script)
        self.assertIn("OWNER_CONSOLE_CLOUD_VISION_ENABLED", script)
        self.assertIn("OWNER_CONSOLE_APPROVAL_ACTIONS_ENABLED", script)
        self.assertIn("OWNER_CONSOLE_TASK_ACTIONS_ENABLED", script)
        self.assertIn("OWNER_CONSOLE_ACCESS_ACTIONS_ENABLED", script)
        self.assertIn("Test-OwnerConsoleHealth", script)
        self.assertIn("/healthz", script)
        self.assertIn("Start-Sleep -Milliseconds 200", script)
        self.assertIn("ElapsedMilliseconds", script)
        self.assertNotIn("Start-Sleep -Seconds 1", script)

    def test_launcher_import_does_not_execute_ai_chat_plugin_entrypoint(self):
        script = """
import json
import os
import sys
os.environ["OWNER_CONSOLE_STATIC_ENABLED"] = "false"
import src.owner_console_fastapi_launcher as launcher

plugin_package = sys.modules.get("src.plugins.ai_chat")
payload = {
    "has_app": hasattr(launcher.app, "router"),
    "plugin_file": getattr(plugin_package, "__file__", None),
    "plugin_path": list(getattr(plugin_package, "__path__", [])),
    "nonebot_loaded": "nonebot" in sys.modules,
    "openai_loaded": "openai" in sys.modules,
    "chat_llm_loaded": "src.plugins.ai_chat.llm" in sys.modules,
    "qq_entry_loaded": "src.plugins.ai_chat.__init__" in sys.modules,
    "routes": [getattr(route, "path", "") for route in launcher.app.routes],
}
print(json.dumps(payload, sort_keys=True))
"""
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["has_app"])
        self.assertIsNone(payload["plugin_file"])
        self.assertTrue(payload["plugin_path"])
        self.assertFalse(payload["nonebot_loaded"])
        self.assertFalse(payload["openai_loaded"])
        self.assertFalse(payload["chat_llm_loaded"])
        self.assertFalse(payload["qq_entry_loaded"])
        self.assertEqual(
            payload["routes"],
            [
                "/healthz",
                "/api/v1/owner-console/routes",
                "/api/v1/owner-console/overview",
                "/api/v1/owner-console/tasks",
                "/api/v1/owner-console/tasks/{task_id}",
                "/api/v1/owner-console/tasks/{task_id}/cancel",
                "/api/v1/owner-console/approvals",
                "/api/v1/owner-console/approvals/{approval_id}",
                "/api/v1/owner-console/approvals/{approval_id}/approve",
                "/api/v1/owner-console/approvals/{approval_id}/reject",
                "/api/v1/owner-console/access-control",
                "/api/v1/owner-console/access-control/private-whitelist/add",
                "/api/v1/owner-console/access-control/private-whitelist/remove",
                "/api/v1/owner-console/access-control/group-whitelist/add",
                "/api/v1/owner-console/access-control/group-whitelist/remove",
                "/api/v1/owner-console/access-control/user-blacklist/add",
                "/api/v1/owner-console/access-control/user-blacklist/remove",
                "/api/v1/owner-console/settings",
                "/api/v1/owner-console/memory",
                "/api/v1/owner-console/external-read",
                "/api/v1/owner-console/diagnostics",
                "/api/v1/owner-console/reliability",
                "/api/v1/owner-console/manual-diagnostics",
                "/api/v1/owner-console/manual-diagnostics/project-doc-rag",
                "/api/v1/owner-console/manual-diagnostics/tts-synthesis/audio-preview/{run_id}",
                "/api/v1/owner-console/manual-diagnostics/tts-synthesis/audio-quality/accept",
                "/api/v1/owner-console/manual-diagnostics/tts-synthesis/audio-quality/reject",
                "/api/v1/owner-console/manual-diagnostics/memory-rag-consistency",
                "/api/v1/owner-console/manual-diagnostics/main-llm-contract",
                "/api/v1/owner-console/manual-diagnostics/tts-synthesis",
                "/api/v1/owner-console/manual-diagnostics/vision-inference",
                "/api/v1/owner-console/manual-diagnostics/vision-inference/reference-preview",
                "/api/v1/owner-console/manual-diagnostics/vision-inference/response-quality/accept",
                "/api/v1/owner-console/manual-diagnostics/vision-inference/response-quality/reject",
                "/api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description",
                "/api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description/reference-preview",
                "/api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description/response-quality/accept",
                "/api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description/response-quality/reject",
            ],
        )

    def test_launcher_app_serves_smoke_routes(self):
        with patch.dict(
            os.environ,
            {"OWNER_CONSOLE_STATIC_ENABLED": "false"},
            clear=False,
        ):
            import src.owner_console_fastapi_launcher as launcher

            client = TestClient(launcher.create_app())

        health_response = client.get("/healthz")
        routes_response = client.get("/api/v1/owner-console/routes")

        self.assertEqual(health_response.status_code, 200)
        self.assertTrue(health_response.json()["ok"])
        self.assertEqual(routes_response.status_code, 200)
        payload = routes_response.json()
        self.assertEqual(payload["schema_version"], "owner_console.http.v1")
        self.assertTrue(payload["http_api_enabled"])
        self.assertFalse(payload["web_write_enabled"])
        self.assertEqual(payload["data"]["api_prefix"], "/api/v1/owner-console")

    def test_launcher_refuses_after_ai_chat_plugin_package_is_initialized(self):
        script = """
import json
import os
import sys
import types
os.environ["OWNER_CONSOLE_STATIC_ENABLED"] = "false"

module = types.ModuleType("src.plugins.ai_chat")
module.__file__ = "D:/AIchatbot/src/plugins/ai_chat/__init__.py"
module.__path__ = ["D:/AIchatbot/src/plugins/ai_chat"]
sys.modules["src.plugins.ai_chat"] = module

import src.owner_console_fastapi_launcher as launcher

try:
    launcher.ensure_owner_console_import_boundary()
except RuntimeError as exc:
    print(json.dumps({"raised": True, "message": str(exc)}))
else:
    print(json.dumps({"raised": False, "message": ""}))
"""
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("src.plugins.ai_chat is already initialized", completed.stderr)
