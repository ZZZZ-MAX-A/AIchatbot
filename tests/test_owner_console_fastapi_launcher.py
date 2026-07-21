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
        self.assertFalse(payload["qq_entry_loaded"])
        self.assertEqual(
            payload["routes"],
            [
                "/healthz",
                "/api/v1/owner-console/routes",
                "/api/v1/owner-console/overview",
                "/api/v1/owner-console/tasks",
                "/api/v1/owner-console/tasks/{task_id}",
                "/api/v1/owner-console/approvals",
                "/api/v1/owner-console/approvals/{approval_id}",
                "/api/v1/owner-console/access-control",
                "/api/v1/owner-console/settings",
                "/api/v1/owner-console/memory",
                "/api/v1/owner-console/external-read",
                "/api/v1/owner-console/diagnostics",
                "/api/v1/owner-console/reliability",
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
