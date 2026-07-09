from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from pure_ai_chat_loader import (
    AI_CHAT_ROOT,
    ensure_ai_chat_packages,
    load_legacy_memory_modules,
    load_module,
)


class TempDatabaseMixin:
    def temp_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "chatbot.db"
        patcher = patch.object(self.database, "DATABASE_PATH", db_path)
        return temp_dir, patcher


class OwnerConsoleFastApiSmokeTests(TempDatabaseMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.memory_modules = load_legacy_memory_modules()
        cls.database = cls.memory_modules["database"]
        cls.agent_tasks = cls.memory_modules["agent_tasks"]
        cls.fastapi_app_module = load_module(
            "src.plugins.ai_chat.owner_console_fastapi_app",
            AI_CHAT_ROOT / "owner_console_fastapi_app.py",
        )

    def setUp(self) -> None:
        app = self.fastapi_app_module.create_owner_console_fastapi_app()
        self.client = TestClient(app)

    def test_healthz_reports_read_only_smoke_app(self):
        response = self.client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["service"], "owner-console")
        self.assertEqual(payload["schema_version"], "owner_console.http.v1")
        self.assertEqual(payload["api_prefix"], "/api/v1/owner-console")
        self.assertTrue(payload["read_only"])
        self.assertTrue(payload["http_api_enabled"])
        self.assertFalse(payload["web_write_enabled"])
        self.assertEqual(
            payload["enabled_routes"],
            [
                "/healthz",
                "/api/v1/owner-console/routes",
                "/api/v1/owner-console/overview",
                "/api/v1/owner-console/tasks",
                "/api/v1/owner-console/approvals",
            ],
        )

    def test_routes_endpoint_returns_restful_contract_envelope(self):
        response = self.client.get("/api/v1/owner-console/routes")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["schema_version"], "owner_console.http.v1")
        self.assertEqual(
            payload["read_model_schema_version"],
            "owner_console.read_model.v0",
        )
        self.assertEqual(payload["transport"], "http")
        self.assertEqual(payload["api_prefix"], "/api/v1/owner-console")
        self.assertEqual(payload["resource"], "routes")
        self.assertTrue(payload["read_only"])
        self.assertTrue(payload["http_api_enabled"])
        self.assertFalse(payload["web_write_enabled"])
        self.assertIsNone(payload["error"])

        data = payload["data"]
        self.assertEqual(data["api_prefix"], "/api/v1/owner-console")
        self.assertEqual(data["allowed_methods"], ["GET"])
        self.assertFalse(data["context_override_allowed"])
        self.assertFalse(data["write_routes_enabled"])
        self.assertEqual(data["route_count"], 10)
        rows = {row["name"]: row for row in data["rows"]}
        self.assertEqual(
            rows["routes"]["path"],
            "/api/v1/owner-console/routes",
        )
        self.assertEqual(rows["routes"]["method"], "GET")
        self.assertEqual(
            rows["routes"]["runtime_method"],
            "build_route_contract_snapshot",
        )
        self.assertEqual(
            rows["overview"]["path"],
            "/api/v1/owner-console/overview",
        )
        self.assertEqual(rows["overview"]["read_page"], "dashboard")
        self.assertTrue(rows["routes"]["http_api_enabled"])
        self.assertTrue(rows["overview"]["http_api_enabled"])
        self.assertTrue(rows["tasks"]["http_api_enabled"])
        self.assertTrue(rows["approvals"]["http_api_enabled"])
        self.assertFalse(rows["tasks.detail"]["http_api_enabled"])
        self.assertFalse(rows["approvals.detail"]["http_api_enabled"])
        self.assertEqual(rows["tasks.detail"]["path_params"], ["task_id"])
        self.assertEqual(
            rows["approvals.detail"]["path_params"],
            ["approval_id"],
        )
        self.assertFalse(
            data["boundary"]["ordinary_chat_can_trigger_main_agent"]
        )
        self.assertTrue(data["boundary"]["owner_write_requires_approval"])

    def test_app_only_exposes_enabled_get_routes_without_writes(self):
        self.assertEqual(self.client.get("/openapi.json").status_code, 404)
        self.assertEqual(self.client.get("/docs").status_code, 404)
        self.assertEqual(self.client.post("/api/v1/owner-console/routes").status_code, 405)
        self.assertEqual(self.client.post("/api/v1/owner-console/overview").status_code, 405)
        self.assertEqual(self.client.post("/api/v1/owner-console/tasks").status_code, 405)
        self.assertEqual(self.client.post("/api/v1/owner-console/approvals").status_code, 405)
        self.assertEqual(self.client.get("/api/v1/owner-console/tasks/1").status_code, 404)
        self.assertEqual(
            self.client.post("/api/v1/owner-console/approvals/1").status_code,
            404,
        )

    def test_overview_endpoint_uses_owner_private_context_from_config(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher, patch.dict(
            os.environ,
            {
                "BOT_OWNER_QQ": "10001",
                "ENABLE_PRIVATE_CHAT": "true",
                "ENABLE_GROUP_CHAT": "true",
            },
            clear=True,
        ):
            first_task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="owner pending task with approval",
            )
            second_task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="owner latest task",
            )
            other_task_id = self.agent_tasks.create_agent_task(
                session_key="private:20002",
                user_id="20002",
                goal="other owner task",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=first_task_id,
                tool_name="owner_write_command",
                tool_input_json='{"command":"clear_image_cache"}',
                risk_level="write_local",
                reason="clear image cache",
            )

            response = self.client.get(
                "/api/v1/owner-console/overview?task_limit=2&approval_limit=2"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["schema_version"], "owner_console.http.v1")
        self.assertEqual(payload["resource"], "overview")
        self.assertTrue(payload["read_only"])
        self.assertTrue(payload["http_api_enabled"])
        self.assertFalse(payload["web_write_enabled"])
        self.assertIsNone(payload["error"])
        data = payload["data"]
        self.assertEqual(data["task_limit"], 2)
        self.assertEqual(data["approval_limit"], 2)
        self.assertEqual(data["counters"]["pending_tasks"], 2)
        self.assertEqual(data["counters"]["pending_approvals"], 1)
        self.assertEqual(
            [row["task_id"] for row in data["recent_tasks"]],
            [second_task_id, first_task_id],
        )
        self.assertNotIn(
            other_task_id,
            [row["task_id"] for row in data["recent_tasks"]],
        )
        self.assertEqual(
            [row["approval_id"] for row in data["pending_approvals"]],
            [approval_id],
        )
        self.assertFalse(
            data["boundary"]["ordinary_chat_can_trigger_main_agent"]
        )

    def test_tasks_and_approvals_endpoints_use_owner_context_and_filters(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher, patch.dict(
            os.environ,
            {
                "BOT_OWNER_QQ": "10001",
                "ENABLE_PRIVATE_CHAT": "true",
                "ENABLE_GROUP_CHAT": "true",
            },
            clear=True,
        ):
            owner_task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="owner task waiting for approval",
            )
            failed_task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="owner failed task",
            )
            other_task_id = self.agent_tasks.create_agent_task(
                session_key="private:20002",
                user_id="20002",
                goal="other user task",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=owner_task_id,
                tool_name="owner_write_command",
                tool_input_json='{"command":"clear_error_log"}',
                risk_level="write_local",
                reason="clear errors",
            )
            self.agent_tasks.create_agent_approval(
                task_id=other_task_id,
                tool_name="owner_write_command",
                tool_input_json='{"command":"clear_image_cache"}',
                risk_level="write_local",
                reason="other approval",
            )
            with self.database.connect() as connection:
                connection.execute(
                    """
                    UPDATE agent_tasks
                    SET status = ?, result = ?
                    WHERE id = ?
                    """,
                    (
                        self.agent_tasks.AGENT_TASK_FAILED,
                        "failed during HTTP list test",
                        failed_task_id,
                    ),
                )

            tasks_response = self.client.get(
                "/api/v1/owner-console/tasks?status=pending&limit=20"
            )
            approvals_response = self.client.get(
                "/api/v1/owner-console/approvals?status=pending&limit=20"
            )

        self.assertEqual(tasks_response.status_code, 200)
        tasks_payload = tasks_response.json()
        self.assertEqual(tasks_payload["resource"], "tasks")
        self.assertTrue(tasks_payload["read_only"])
        self.assertTrue(tasks_payload["http_api_enabled"])
        self.assertFalse(tasks_payload["web_write_enabled"])
        self.assertIsNone(tasks_payload["error"])
        task_data = tasks_payload["data"]
        self.assertEqual(task_data["status_filter"], "pending")
        self.assertEqual(task_data["limit"], 20)
        self.assertEqual(task_data["total_visible"], 1)
        self.assertEqual([row["task_id"] for row in task_data["rows"]], [owner_task_id])
        self.assertEqual(task_data["rows"][0]["pending_approval_ids"], [approval_id])
        self.assertNotIn(other_task_id, [row["task_id"] for row in task_data["rows"]])
        self.assertFalse(
            task_data["boundary"]["ordinary_chat_can_trigger_main_agent"]
        )

        self.assertEqual(approvals_response.status_code, 200)
        approvals_payload = approvals_response.json()
        self.assertEqual(approvals_payload["resource"], "approvals")
        self.assertTrue(approvals_payload["read_only"])
        self.assertTrue(approvals_payload["http_api_enabled"])
        self.assertFalse(approvals_payload["web_write_enabled"])
        self.assertIsNone(approvals_payload["error"])
        approval_data = approvals_payload["data"]
        self.assertEqual(approval_data["status_filter"], "pending")
        self.assertEqual(approval_data["limit"], 20)
        self.assertEqual(approval_data["total_visible"], 1)
        self.assertEqual(
            [row["approval_id"] for row in approval_data["rows"]],
            [approval_id],
        )
        self.assertEqual(approval_data["rows"][0]["task_id"], owner_task_id)
        self.assertTrue(
            approval_data["rows"][0]["actionability"]["future_operation_only"]
        )

    def test_tasks_and_approvals_endpoints_validate_status_limit_and_owner(self):
        with patch.dict(os.environ, {}, clear=True):
            missing_owner = self.client.get("/api/v1/owner-console/tasks")

        self.assertEqual(missing_owner.status_code, 403)
        self.assertEqual(missing_owner.json()["error"]["code"], "forbidden")

        with patch.dict(os.environ, {"BOT_OWNER_QQ": "10001"}, clear=True):
            invalid_status = self.client.get(
                "/api/v1/owner-console/tasks?status=missing"
            )
            invalid_limit = self.client.get(
                "/api/v1/owner-console/approvals?limit=abc"
            )

        self.assertEqual(invalid_status.status_code, 400)
        status_payload = invalid_status.json()
        self.assertEqual(status_payload["resource"], "tasks")
        self.assertEqual(status_payload["error"]["code"], "bad_request")
        self.assertEqual(status_payload["error"]["details"]["field"], "status")
        self.assertIn("pending", status_payload["error"]["details"]["allowed"])
        self.assertFalse(status_payload["web_write_enabled"])

        self.assertEqual(invalid_limit.status_code, 400)
        limit_payload = invalid_limit.json()
        self.assertEqual(limit_payload["resource"], "approvals")
        self.assertEqual(limit_payload["error"]["code"], "bad_request")
        self.assertEqual(limit_payload["error"]["details"]["field"], "limit")
        self.assertFalse(limit_payload["web_write_enabled"])

    def test_overview_endpoint_requires_owner_config_and_valid_limits(self):
        with patch.dict(os.environ, {}, clear=True):
            missing_owner = self.client.get("/api/v1/owner-console/overview")

        self.assertEqual(missing_owner.status_code, 403)
        payload = missing_owner.json()
        self.assertEqual(payload["resource"], "overview")
        self.assertIsNone(payload["data"])
        self.assertEqual(payload["error"]["code"], "forbidden")
        self.assertEqual(payload["error"]["details"], {"config_key": "BOT_OWNER_QQ"})
        self.assertTrue(payload["http_api_enabled"])

        with patch.dict(os.environ, {"BOT_OWNER_QQ": "10001"}, clear=True):
            invalid_limit = self.client.get(
                "/api/v1/owner-console/overview?task_limit=0"
            )

        self.assertEqual(invalid_limit.status_code, 400)
        invalid_payload = invalid_limit.json()
        self.assertEqual(invalid_payload["error"]["code"], "bad_request")
        self.assertEqual(invalid_payload["error"]["details"]["field"], "task_limit")
        self.assertFalse(invalid_payload["web_write_enabled"])

    def test_fastapi_smoke_app_has_no_qq_adapter_or_write_runtime_dependency(self):
        sources = [
            AI_CHAT_ROOT / "owner_console_fastapi_app.py",
            AI_CHAT_ROOT / "owner_console_http_adapter.py",
        ]
        source = "\n".join(path.read_text(encoding="utf-8") for path in sources)
        lower_source = source.lower()

        self.assertNotIn("nonebot", lower_source)
        self.assertNotIn("messageevent", lower_source)
        self.assertNotIn("matcher.finish", lower_source)
        self.assertNotIn("bot.send", lower_source)
        self.assertNotIn("owner_write_runtime", source)
