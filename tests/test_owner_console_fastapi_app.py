from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
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
        cls.memory = cls.memory_modules["memory"]
        cls.reliability = load_module(
            "src.plugins.ai_chat.reliability_events",
            AI_CHAT_ROOT / "reliability_events.py",
        )
        cls.fastapi_app_module = load_module(
            "src.plugins.ai_chat.owner_console_fastapi_app",
            AI_CHAT_ROOT / "owner_console_fastapi_app.py",
        )

    def setUp(self) -> None:
        with patch.dict(
            os.environ,
            {"OWNER_CONSOLE_STATIC_ENABLED": "false"},
            clear=False,
        ):
            app = self.fastapi_app_module.create_owner_console_fastapi_app()
        self.client = TestClient(app)

    def build_static_dist(self, root: Path) -> Path:
        dist = root / "dist"
        assets = dist / "assets"
        assets.mkdir(parents=True)
        (dist / "index.html").write_text(
            '<!doctype html><html lang="zh-CN"><body><div id="root"></div></body></html>',
            encoding="utf-8",
        )
        (assets / "index-test.js").write_text(
            "console.log('owner-console-static-ok');",
            encoding="utf-8",
        )
        return dist

    def test_healthz_reports_read_only_smoke_app(self):
        response = self.client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["service"], "owner-console")
        self.assertEqual(payload["schema_version"], "owner_console.http.v1")
        self.assertEqual(payload["api_prefix"], "/api/v1/owner-console")
        self.assertTrue(payload["read_only"])
        self.assertTrue(payload["snapshot_read_only"])
        self.assertTrue(payload["http_api_enabled"])
        self.assertFalse(payload["web_write_enabled"])
        self.assertFalse(payload["manual_diagnostic_actions_enabled"])
        self.assertFalse(payload["automatic_diagnostics_enabled"])
        self.assertFalse(payload["configuration_write_enabled"])
        self.assertFalse(payload["business_data_write_enabled"])
        self.assertEqual(
            payload["enabled_routes"],
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
                "/api/v1/owner-console/diagnostics",
                "/api/v1/owner-console/reliability",
                "/api/v1/owner-console/external-read",
                "/api/v1/owner-console/manual-diagnostics",
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
        self.assertEqual(data["allowed_methods"], ["GET", "POST"])
        self.assertFalse(data["context_override_allowed"])
        self.assertFalse(data["write_routes_enabled"])
        self.assertEqual(data["route_count"], 16)
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
        self.assertTrue(rows["tasks.detail"]["http_api_enabled"])
        self.assertTrue(rows["approvals.detail"]["http_api_enabled"])
        self.assertTrue(rows["access-control"]["http_api_enabled"])
        self.assertTrue(rows["settings"]["http_api_enabled"])
        self.assertTrue(rows["memory"]["http_api_enabled"])
        self.assertTrue(rows["diagnostics"]["http_api_enabled"])
        self.assertTrue(rows["reliability"]["http_api_enabled"])
        self.assertTrue(rows["external-read"]["http_api_enabled"])
        self.assertTrue(rows["manual-diagnostics"]["http_api_enabled"])
        self.assertFalse(
            rows["manual-diagnostics.project-doc-rag"]["http_api_enabled"]
        )
        self.assertFalse(
            rows["manual-diagnostics.memory-rag-consistency"]["http_api_enabled"]
        )
        self.assertFalse(
            rows["manual-diagnostics.main-llm-contract"]["http_api_enabled"]
        )
        self.assertFalse(data["manual_runtime_action_routes_enabled"])
        self.assertEqual(
            rows["manual-diagnostics.project-doc-rag"]["method"],
            "POST",
        )
        self.assertFalse(rows["manual-diagnostics.project-doc-rag"]["read_only"])
        self.assertTrue(
            rows["manual-diagnostics.project-doc-rag"][
                "manual_runtime_action_allowed"
            ]
        )
        self.assertEqual(
            rows["manual-diagnostics.memory-rag-consistency"]["method"],
            "POST",
        )
        self.assertTrue(
            rows["manual-diagnostics.memory-rag-consistency"][
                "manual_runtime_action_allowed"
            ]
        )
        self.assertEqual(
            rows["manual-diagnostics.main-llm-contract"]["method"],
            "POST",
        )
        self.assertTrue(
            rows["manual-diagnostics.main-llm-contract"][
                "manual_runtime_action_allowed"
            ]
        )
        self.assertEqual(rows["tasks.detail"]["path_params"], ["task_id"])
        self.assertEqual(
            rows["approvals.detail"]["path_params"],
            ["approval_id"],
        )
        self.assertFalse(rows["access-control"]["requires_context"])
        self.assertEqual(rows["access-control"]["query_params"], ["item_limit"])
        self.assertFalse(rows["settings"]["requires_context"])
        self.assertFalse(
            data["boundary"]["ordinary_chat_can_trigger_main_agent"]
        )
        self.assertTrue(data["boundary"]["owner_write_requires_approval"])

    def test_memory_manual_action_route_requires_its_explicit_switch(self):
        with patch.dict(
            os.environ,
            {
                "OWNER_CONSOLE_STATIC_ENABLED": "false",
                "OWNER_CONSOLE_MANUAL_DIAGNOSTICS_ENABLED": "true",
                "OWNER_CONSOLE_PROJECT_DOC_RAG_PROBE_ENABLED": "false",
                "OWNER_CONSOLE_MEMORY_RAG_CONSISTENCY_ENABLED": "true",
                "OWNER_CONSOLE_MAIN_LLM_CONTRACT_ENABLED": "false",
            },
            clear=False,
        ):
            app = self.fastapi_app_module.create_owner_console_fastapi_app()
        client = TestClient(app)

        health = client.get("/healthz").json()
        self.assertTrue(health["manual_diagnostic_actions_enabled"])
        self.assertIn(
            "/api/v1/owner-console/manual-diagnostics/memory-rag-consistency",
            health["enabled_routes"],
        )
        self.assertNotIn(
            "/api/v1/owner-console/manual-diagnostics/project-doc-rag",
            health["enabled_routes"],
        )
        rows = {
            row["name"]: row
            for row in client.get(
                "/api/v1/owner-console/routes"
            ).json()["data"]["rows"]
        }
        self.assertTrue(
            rows["manual-diagnostics.memory-rag-consistency"][
                "http_api_enabled"
            ]
        )
        self.assertFalse(
            rows["manual-diagnostics.project-doc-rag"]["http_api_enabled"]
        )
        self.assertFalse(
            rows["manual-diagnostics.main-llm-contract"]["http_api_enabled"]
        )

    def test_main_llm_manual_action_route_requires_its_explicit_switch(self):
        with patch.dict(
            os.environ,
            {
                "OWNER_CONSOLE_STATIC_ENABLED": "false",
                "OWNER_CONSOLE_MANUAL_DIAGNOSTICS_ENABLED": "true",
                "OWNER_CONSOLE_PROJECT_DOC_RAG_PROBE_ENABLED": "false",
                "OWNER_CONSOLE_MEMORY_RAG_CONSISTENCY_ENABLED": "false",
                "OWNER_CONSOLE_MAIN_LLM_CONTRACT_ENABLED": "true",
            },
            clear=False,
        ):
            app = self.fastapi_app_module.create_owner_console_fastapi_app()
        client = TestClient(app)

        health = client.get("/healthz").json()
        self.assertTrue(health["manual_diagnostic_actions_enabled"])
        self.assertIn(
            "/api/v1/owner-console/manual-diagnostics/main-llm-contract",
            health["enabled_routes"],
        )
        rows = {
            row["name"]: row
            for row in client.get(
                "/api/v1/owner-console/routes"
            ).json()["data"]["rows"]
        }
        self.assertTrue(
            rows["manual-diagnostics.main-llm-contract"]["http_api_enabled"]
        )
        self.assertFalse(
            rows["manual-diagnostics.memory-rag-consistency"]["http_api_enabled"]
        )

    def test_app_only_exposes_enabled_get_routes_without_writes(self):
        self.assertEqual(self.client.get("/openapi.json").status_code, 404)
        self.assertEqual(self.client.get("/docs").status_code, 404)
        self.assertEqual(self.client.get("/owner-console").status_code, 404)
        self.assertEqual(self.client.get("/owner-console/tasks/1").status_code, 404)
        self.assertEqual(self.client.post("/api/v1/owner-console/routes").status_code, 405)
        self.assertEqual(self.client.post("/api/v1/owner-console/overview").status_code, 405)
        self.assertEqual(self.client.post("/api/v1/owner-console/tasks").status_code, 405)
        self.assertEqual(self.client.post("/api/v1/owner-console/approvals").status_code, 405)
        self.assertEqual(self.client.post("/api/v1/owner-console/tasks/1").status_code, 405)
        self.assertEqual(
            self.client.post("/api/v1/owner-console/approvals/1").status_code,
            405,
        )
        self.assertEqual(
            self.client.post("/api/v1/owner-console/access-control").status_code,
            405,
        )
        self.assertEqual(
            self.client.post("/api/v1/owner-console/settings").status_code,
            405,
        )
        self.assertEqual(
            self.client.post("/api/v1/owner-console/memory").status_code,
            405,
        )
        self.assertEqual(
            self.client.post("/api/v1/owner-console/diagnostics").status_code,
            405,
        )
        self.assertEqual(
            self.client.post("/api/v1/owner-console/reliability").status_code,
            405,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/owner-console/manual-diagnostics/project-doc-rag",
                json={"confirmation": "run_registered_project_doc_rag_probe"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/owner-console/manual-diagnostics/memory-rag-consistency",
                json={"confirmation": "run_registered_memory_rag_consistency"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/owner-console/manual-diagnostics/main-llm-contract",
                json={"confirmation": "run_registered_main_llm_contract"},
            ).status_code,
            403,
        )

    def test_reliability_endpoint_reads_structured_events_without_writing(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            occurred_at = datetime.now(UTC) - timedelta(hours=1)
            recorded = self.reliability.record_result_safely(
                component="bot_runtime",
                operation="lifecycle",
                code="suspected_abnormal_exit",
                outcome=self.reliability.ReliabilityOutcome.DEGRADED,
                occurred_at=occurred_at,
                runtime_id=self.reliability.new_runtime_id(),
            )
            self.assertTrue(recorded)
            db_path = self.database.DATABASE_PATH
            before = db_path.stat()

            response = self.client.get("/api/v1/owner-console/reliability")

            after = db_path.stat()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["resource"], "reliability")
        self.assertTrue(payload["read_only"])
        self.assertTrue(payload["http_api_enabled"])
        self.assertFalse(payload["web_write_enabled"])
        self.assertIsNone(payload["error"])
        data = payload["data"]
        self.assertEqual(data["recent"]["window_hours"], 24)
        self.assertEqual(data["weekly"]["window_hours"], 168)
        self.assertEqual(data["recent"]["failure_occurrence_count"], 1)
        self.assertEqual(data["recent"]["failure_group_count"], 1)
        self.assertEqual(
            data["recent"]["state_counts"]["insufficient_evidence"],
            1,
        )
        item = data["recent"]["items"][0]
        self.assertEqual(item["component"], "bot_runtime")
        self.assertEqual(item["component_label"], "Bot 运行状态")
        self.assertEqual(item["operation"], "lifecycle")
        self.assertEqual(item["operation_label"], "进程启动与停止")
        self.assertEqual(item["code"], "suspected_abnormal_exit")
        self.assertEqual(
            item["code_label"],
            "上次运行没有发现正常停止记录",
        )
        self.assertEqual(item["last_success_at"], "")
        self.assertEqual(
            set(item),
            {
                "component",
                "component_label",
                "operation",
                "operation_label",
                "category",
                "category_label",
                "code",
                "code_label",
                "occurrence_count",
                "first_seen_at",
                "last_seen_at",
                "last_success_at",
                "recovery_state",
                "recovery_state_label",
            },
        )
        self.assertEqual(len(data["coverage"]), 7)
        self.assertIn(
            {
                "component": "vision",
                "component_label": "图片理解",
                "operation": "infer",
                "operation_label": "识别图片内容",
            },
            data["coverage"],
        )
        self.assertIn(
            {
                "component": "tts",
                "component_label": "语音合成",
                "operation": "synthesize",
                "operation_label": "生成语音",
            },
            data["coverage"],
        )
        self.assertTrue(data["boundary"]["sqlite_mode_ro"])
        self.assertFalse(data["boundary"]["ensure_database_called"])
        self.assertFalse(data["boundary"]["chat_content_read"])
        self.assertFalse(data["boundary"]["raw_exception_read"])
        self.assertFalse(data["boundary"]["llm_called"])
        self.assertFalse(data["boundary"]["rag_called"])
        self.assertFalse(data["boundary"]["write_side_effect_allowed"])
        self.assertEqual(before.st_size, after.st_size)
        self.assertEqual(before.st_mtime_ns, after.st_mtime_ns)

    def test_optional_static_mode_serves_spa_without_touching_api_routes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dist = self.build_static_dist(Path(temp_dir))
            with patch.dict(
                os.environ,
                {
                    "OWNER_CONSOLE_STATIC_ENABLED": "true",
                    "OWNER_CONSOLE_STATIC_DIR": str(dist),
                },
                clear=True,
            ):
                app = self.fastapi_app_module.create_owner_console_fastapi_app()

            client = TestClient(app)

            for path in (
                "/owner-console",
                "/owner-console/",
                "/owner-console/tasks",
                "/owner-console/tasks/1",
                "/owner-console/approvals/1",
            ):
                response = client.get(path)
                self.assertEqual(response.status_code, 200, path)
                self.assertIn("text/html", response.headers["content-type"])
                self.assertIn('<div id="root"></div>', response.text)

            asset_response = client.get("/owner-console/assets/index-test.js")
            self.assertEqual(asset_response.status_code, 200)
            self.assertIn("owner-console-static-ok", asset_response.text)

            self.assertEqual(
                client.get("/owner-console/assets/missing.js").status_code,
                404,
            )
            self.assertEqual(client.post("/owner-console/tasks").status_code, 405)

            api_response = client.get("/api/v1/owner-console/routes")
            self.assertEqual(api_response.status_code, 200)
            self.assertEqual(
                api_response.headers["content-type"].split(";")[0],
                "application/json",
            )
            self.assertEqual(api_response.json()["resource"], "routes")
            self.assertEqual(
                client.post("/api/v1/owner-console/tasks").status_code,
                405,
            )
            self.assertEqual(client.get("/docs").status_code, 404)
            self.assertEqual(client.get("/redoc").status_code, 404)
            self.assertEqual(client.get("/openapi.json").status_code, 404)

    def test_static_mode_requires_existing_dist_index(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_dist = Path(temp_dir) / "missing-dist"
            with patch.dict(
                os.environ,
                {
                    "OWNER_CONSOLE_STATIC_ENABLED": "true",
                    "OWNER_CONSOLE_STATIC_DIR": str(missing_dist),
                },
                clear=True,
            ):
                with self.assertRaisesRegex(RuntimeError, "static mode is enabled"):
                    self.fastapi_app_module.create_owner_console_fastapi_app()

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
            running_task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="owner running work task",
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
            self.agent_tasks.claim_agent_task_for_work(
                task_id=running_task_id,
                session_key="private:10001",
                user_id="10001",
                work_type="development_context_report",
                query_summary="verify read-only running task contract",
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
            running_response = self.client.get(
                "/api/v1/owner-console/tasks?status=running&work_type=development_context_report&limit=20"
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

        self.assertEqual(running_response.status_code, 200)
        running_payload = running_response.json()
        self.assertEqual(running_payload["resource"], "tasks")
        self.assertTrue(running_payload["read_only"])
        self.assertFalse(running_payload["web_write_enabled"])
        self.assertIsNone(running_payload["error"])
        running_data = running_payload["data"]
        self.assertEqual(running_data["status_filter"], "running")
        self.assertEqual(
            running_data["work_type_filter"],
            "development_context_report",
        )
        self.assertEqual([row["task_id"] for row in running_data["rows"]], [running_task_id])
        self.assertEqual(
            running_data["rows"][0]["work_type"],
            "development_context_report",
        )
        self.assertEqual(running_data["rows"][0]["status_label"], "运行中")
        self.assertEqual(running_data["rows"][0]["next_action"], "monitor_running_task")

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
            invalid_work_type = self.client.get(
                "/api/v1/owner-console/tasks?work_type=unknown_work"
            )

        self.assertEqual(invalid_status.status_code, 400)
        status_payload = invalid_status.json()
        self.assertEqual(status_payload["resource"], "tasks")
        self.assertEqual(status_payload["error"]["code"], "bad_request")
        self.assertEqual(invalid_work_type.status_code, 400)
        self.assertEqual(
            invalid_work_type.json()["error"]["details"]["field"],
            "work_type",
        )
        self.assertEqual(status_payload["error"]["details"]["field"], "status")
        self.assertIn("pending", status_payload["error"]["details"]["allowed"])
        self.assertFalse(status_payload["web_write_enabled"])

        self.assertEqual(invalid_limit.status_code, 400)
        limit_payload = invalid_limit.json()
        self.assertEqual(limit_payload["resource"], "approvals")
        self.assertEqual(limit_payload["error"]["code"], "bad_request")
        self.assertEqual(limit_payload["error"]["details"]["field"], "limit")
        self.assertFalse(limit_payload["web_write_enabled"])

    def test_detail_endpoints_use_owner_context_limits_and_not_found(self):
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
                goal="owner task detail goal",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=owner_task_id,
                tool_name="owner_write_command",
                tool_input_json='{"command":"clear_error_log"}',
                risk_level="write_local",
                reason="clear detail errors",
            )
            other_task_id = self.agent_tasks.create_agent_task(
                session_key="private:20002",
                user_id="20002",
                goal="other task detail goal",
            )
            other_approval_id = self.agent_tasks.create_agent_approval(
                task_id=other_task_id,
                tool_name="owner_write_command",
                tool_input_json='{"command":"clear_image_cache"}',
                risk_level="write_local",
                reason="other detail approval",
            )

            task_response = self.client.get(
                f"/api/v1/owner-console/tasks/{owner_task_id}"
                "?event_limit=1&preview_limit=240"
            )
            approval_response = self.client.get(
                f"/api/v1/owner-console/approvals/{approval_id}"
                "?event_limit=1&preview_limit=240"
            )
            other_task_response = self.client.get(
                f"/api/v1/owner-console/tasks/{other_task_id}"
            )
            other_approval_response = self.client.get(
                f"/api/v1/owner-console/approvals/{other_approval_id}"
            )

        self.assertEqual(task_response.status_code, 200)
        task_payload = task_response.json()
        self.assertEqual(task_payload["resource"], "tasks")
        self.assertTrue(task_payload["read_only"])
        self.assertTrue(task_payload["http_api_enabled"])
        self.assertFalse(task_payload["web_write_enabled"])
        self.assertIsNone(task_payload["error"])
        task_data = task_payload["data"]
        self.assertEqual(task_data["task"]["task_id"], owner_task_id)
        self.assertEqual(task_data["goal"], "owner task detail goal")
        self.assertEqual([row["kind"] for row in task_data["events"]], ["created"])
        self.assertEqual(
            [row["approval_id"] for row in task_data["approvals"]],
            [approval_id],
        )
        self.assertFalse(
            task_data["boundary"]["ordinary_chat_can_trigger_main_agent"]
        )

        self.assertEqual(approval_response.status_code, 200)
        approval_payload = approval_response.json()
        self.assertEqual(approval_payload["resource"], "approvals")
        self.assertTrue(approval_payload["read_only"])
        self.assertTrue(approval_payload["http_api_enabled"])
        self.assertFalse(approval_payload["web_write_enabled"])
        self.assertIsNone(approval_payload["error"])
        approval_data = approval_payload["data"]
        self.assertEqual(approval_data["approval"]["approval_id"], approval_id)
        self.assertEqual(approval_data["approval"]["task_id"], owner_task_id)
        self.assertEqual(approval_data["reason"], "clear detail errors")
        self.assertIn(
            "clear_error_log",
            approval_data["tool_input"]["preview_json"],
        )
        self.assertEqual(approval_data["task"]["task_id"], owner_task_id)
        self.assertEqual(
            [row["kind"] for row in approval_data["recent_events"]],
            ["created"],
        )

        self.assertEqual(other_task_response.status_code, 404)
        self.assertEqual(
            other_task_response.json()["error"]["details"],
            {"task_id": other_task_id},
        )
        self.assertEqual(other_approval_response.status_code, 404)
        self.assertEqual(
            other_approval_response.json()["error"]["details"],
            {"approval_id": other_approval_id},
        )

    def test_detail_endpoints_validate_ids_limits_and_owner(self):
        with patch.dict(os.environ, {}, clear=True):
            missing_owner = self.client.get("/api/v1/owner-console/tasks/1")

        self.assertEqual(missing_owner.status_code, 403)
        self.assertEqual(missing_owner.json()["error"]["code"], "forbidden")

        with patch.dict(os.environ, {"BOT_OWNER_QQ": "10001"}, clear=True):
            invalid_task_id = self.client.get(
                "/api/v1/owner-console/tasks/not-a-number"
            )
            invalid_approval_id = self.client.get(
                "/api/v1/owner-console/approvals/0"
            )
            invalid_event_limit = self.client.get(
                "/api/v1/owner-console/approvals/1?event_limit=0"
            )
            invalid_preview_limit = self.client.get(
                "/api/v1/owner-console/tasks/1?preview_limit=abc"
            )

        self.assertEqual(invalid_task_id.status_code, 400)
        task_id_payload = invalid_task_id.json()
        self.assertEqual(task_id_payload["resource"], "tasks")
        self.assertEqual(task_id_payload["error"]["code"], "bad_request")
        self.assertEqual(task_id_payload["error"]["details"]["field"], "task_id")

        self.assertEqual(invalid_approval_id.status_code, 400)
        approval_id_payload = invalid_approval_id.json()
        self.assertEqual(approval_id_payload["resource"], "approvals")
        self.assertEqual(approval_id_payload["error"]["code"], "bad_request")
        self.assertEqual(
            approval_id_payload["error"]["details"]["field"],
            "approval_id",
        )

        self.assertEqual(invalid_event_limit.status_code, 400)
        event_limit_payload = invalid_event_limit.json()
        self.assertEqual(event_limit_payload["resource"], "approvals")
        self.assertEqual(
            event_limit_payload["error"]["details"]["field"],
            "event_limit",
        )

        self.assertEqual(invalid_preview_limit.status_code, 400)
        preview_limit_payload = invalid_preview_limit.json()
        self.assertEqual(preview_limit_payload["resource"], "tasks")
        self.assertEqual(
            preview_limit_payload["error"]["details"]["field"],
            "preview_limit",
        )

    def test_access_control_and_settings_endpoints_are_read_only_snapshots(self):
        with patch.dict(
            os.environ,
            {
                "BOT_OWNER_QQ": "10001",
                "ENABLE_PRIVATE_CHAT": "false",
                "ENABLE_GROUP_CHAT": "true",
                "ALLOW_UNKNOWN_PRIVATE_CHAT": "true",
                "PRIVATE_WHITELIST": "10001,20002",
                "GROUP_WHITELIST": "90001",
                "USER_BLACKLIST": "30003",
                "OPENAI_API_KEY": "sk-http-secret",
                "OPENAI_BASE_URL": "https://user:pass@example.com/v1?api_key=hidden",
                "OPENAI_MODEL": "fallback-chat",
                "CHAT_LLM_MODEL": "chat-http-model",
                "CHAT_LLM_TIMEOUT_SECONDS": "23",
                "MAIN_LLM_API_KEY": "main-http-secret",
                "MAIN_LLM_BASE_URL": "https://main.example.com/v1?token=hidden",
                "MAIN_LLM_MODEL": "main-http-model",
                "MAIN_LLM_TIMEOUT_SECONDS": "37",
                "MEMORY_RAG_EMBEDDING_BASE_URL": "http://127.0.0.1:11434/private?token=hidden",
                "MEMORY_RAG_EMBEDDING_MODEL": "bge-http",
                "MEMORY_RAG_EMBEDDING_TIMEOUT_SECONDS": "13",
                "ENABLE_MAIN_AGENT": "true",
                "MAIN_AGENT_USE_LLM": "true",
                "ENABLE_MEMORY_RAG": "true",
                "ENABLE_PROJECT_DOC_RAG": "true",
                "MEMORY_RAG_INJECT_IN_CHAT": "false",
                "ENABLE_AGENT_WEB": "false",
                "ENABLE_AGENT_SHELL": "false",
            },
            clear=True,
        ):
            access_response = self.client.get(
                "/api/v1/owner-console/access-control?item_limit=50"
            )
            settings_response = self.client.get("/api/v1/owner-console/settings")

        self.assertEqual(access_response.status_code, 200)
        access_payload = access_response.json()
        self.assertEqual(access_payload["resource"], "access-control")
        self.assertTrue(access_payload["read_only"])
        self.assertTrue(access_payload["http_api_enabled"])
        self.assertFalse(access_payload["web_write_enabled"])
        self.assertIsNone(access_payload["error"])
        access_data = access_payload["data"]
        self.assertTrue(access_data["owner_configured"])
        self.assertFalse(access_data["private_chat_enabled"])
        self.assertTrue(access_data["group_chat_enabled"])
        self.assertEqual(access_data["unknown_private_policy"], "allow_trial")
        self.assertTrue(
            {"10001", "20002"}.issubset(
                set(access_data["private_whitelist"]["items"])
            )
        )
        self.assertIn("90001", access_data["group_whitelist"]["items"])
        self.assertIn("30003", access_data["user_blacklist"]["items"])
        self.assertFalse(
            access_data["boundary"]["ordinary_chat_can_trigger_main_agent"]
        )

        self.assertEqual(settings_response.status_code, 200)
        settings_payload = settings_response.json()
        self.assertEqual(settings_payload["resource"], "settings")
        self.assertTrue(settings_payload["read_only"])
        self.assertTrue(settings_payload["http_api_enabled"])
        self.assertFalse(settings_payload["web_write_enabled"])
        self.assertIsNone(settings_payload["error"])
        settings_data = settings_payload["data"]
        self.assertEqual(settings_data["chat_model"]["model_name"], "chat-http-model")
        self.assertEqual(
            settings_data["chat_model"]["base_url_redacted"],
            "https://example.com/v1",
        )
        self.assertTrue(settings_data["chat_model"]["api_key_configured"])
        self.assertEqual(settings_data["chat_model"]["timeout_seconds"], 23)
        self.assertEqual(
            settings_data["main_agent_model"]["base_url_redacted"],
            "https://main.example.com/v1",
        )
        self.assertTrue(settings_data["main_agent_model"]["api_key_configured"])
        self.assertEqual(
            settings_data["embedding"]["base_url_redacted"],
            "http://127.0.0.1:11434/private",
        )
        self.assertFalse(settings_data["embedding"]["api_key_configured"])
        self.assertTrue(settings_data["feature_flags"]["enable_main_agent"])
        self.assertTrue(settings_data["feature_flags"]["main_agent_use_llm"])
        self.assertTrue(settings_data["feature_flags"]["enable_memory_rag"])
        self.assertFalse(settings_data["feature_flags"]["memory_rag_inject_in_chat"])
        self.assertFalse(settings_data["feature_flags"]["enable_agent_web"])
        self.assertFalse(settings_data["feature_flags"]["enable_agent_shell"])
        self.assertIsInstance(settings_data["role_cards"], list)

        rendered = json.dumps(settings_payload, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("sk-http-secret", rendered)
        self.assertNotIn("main-http-secret", rendered)
        self.assertNotIn("hidden", rendered)

    def test_access_control_endpoint_validates_item_limit_without_owner_context(self):
        with patch.dict(os.environ, {}, clear=True):
            access_response = self.client.get("/api/v1/owner-console/access-control")
            settings_response = self.client.get("/api/v1/owner-console/settings")
            invalid_limit = self.client.get(
                "/api/v1/owner-console/access-control?item_limit=0"
            )

        self.assertEqual(access_response.status_code, 200)
        self.assertFalse(access_response.json()["data"]["owner_configured"])
        self.assertEqual(settings_response.status_code, 200)
        self.assertEqual(invalid_limit.status_code, 400)
        invalid_payload = invalid_limit.json()
        self.assertEqual(invalid_payload["resource"], "access-control")
        self.assertEqual(invalid_payload["error"]["code"], "bad_request")
        self.assertEqual(
            invalid_payload["error"]["details"]["field"],
            "item_limit",
        )

    def test_memory_endpoint_reports_counts_flags_and_never_exposes_content(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher, patch.dict(
            os.environ,
            {
                "ENABLE_MEMORY_COMPRESSION": "false",
                "ENABLE_GAP_SCENE_SUMMARIES": "true",
                "ENABLE_LONG_TERM_MEMORY_CONTEXT": "true",
                "MAX_CONTEXT_MESSAGES": "42",
                "MAX_STORED_MESSAGES_PER_SESSION": "121",
                "SUMMARY_KEEP_RECENT_MESSAGES": "43",
                "SUMMARY_BATCH_MESSAGES": "83",
                "SUMMARY_MIN_SOURCE_MESSAGES": "44",
                "MAX_SESSION_SUMMARIES_IN_CONTEXT": "4",
                "MAX_GAP_SCENE_SUMMARIES_IN_CONTEXT": "3",
                "MAX_LONG_TERM_MEMORIES_IN_CONTEXT": "9",
                "ENABLE_MEMORY_RAG": "true",
                "MEMORY_RAG_INJECT_IN_CHAT": "false",
                "MEMORY_RAG_OWNER_ONLY_DEBUG": "false",
                "MEMORY_RAG_TOP_K": "6",
                "MEMORY_RAG_MIN_SCORE": "0.61",
                "MEMORY_RAG_MAX_CONTEXT_CHARS": "1666",
                "MEMORY_RAG_INCLUDE_MANUAL_FACTS": "true",
                "MEMORY_RAG_INCLUDE_MANUAL_PREFERENCES": "false",
                "MEMORY_RAG_INCLUDE_SESSION_SUMMARIES": "true",
                "MEMORY_RAG_INCLUDE_SHORT_MESSAGES": "true",
                "MEMORY_RAG_INCLUDE_GAP_SCENE_SUMMARIES": "true",
                "ENABLE_PROJECT_DOC_RAG": "true",
                "PROJECT_DOC_RAG_TOP_K": "3",
                "PROJECT_DOC_RAG_MIN_SCORE": "0.49",
                "PROJECT_DOC_RAG_MAX_CONTEXT_CHARS": "1234",
            },
            clear=True,
        ):
            self.memory.append_message(
                "private:10001",
                "user",
                "secret owner message",
                "private",
                "10001",
            )
            self.memory.append_message(
                "private:20002",
                "assistant",
                "secret assistant message",
                "private",
                "20002",
            )

            response = self.client.get("/api/v1/owner-console/memory")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["resource"], "memory")
        self.assertTrue(payload["read_only"])
        self.assertTrue(payload["http_api_enabled"])
        self.assertFalse(payload["web_write_enabled"])
        self.assertIsNone(payload["error"])

        data = payload["data"]
        self.assertEqual(data["counts"]["message_count"], 2)
        self.assertEqual(data["counts"]["session_count"], 2)
        self.assertFalse(data["context_policy"]["memory_compression_enabled"])
        self.assertTrue(data["context_policy"]["gap_scene_summaries_enabled"])
        self.assertTrue(data["context_policy"]["long_term_memory_context_enabled"])
        self.assertEqual(data["context_policy"]["max_context_messages"], 42)
        self.assertEqual(
            data["context_policy"]["max_stored_messages_per_session"],
            121,
        )
        self.assertEqual(data["context_policy"]["summary_keep_recent_messages"], 43)
        self.assertEqual(data["context_policy"]["summary_batch_messages"], 83)
        self.assertEqual(data["context_policy"]["summary_min_source_messages"], 44)
        self.assertEqual(data["context_policy"]["max_session_summaries_in_context"], 4)
        self.assertEqual(data["context_policy"]["max_gap_scene_summaries_in_context"], 3)
        self.assertEqual(data["context_policy"]["max_long_term_memories_in_context"], 9)
        self.assertTrue(data["memory_rag"]["enabled"])
        self.assertFalse(data["memory_rag"]["inject_in_chat"])
        self.assertFalse(data["memory_rag"]["owner_only_debug"])
        self.assertEqual(data["memory_rag"]["top_k"], 6)
        self.assertAlmostEqual(data["memory_rag"]["min_score"], 0.61)
        self.assertEqual(data["memory_rag"]["max_context_chars"], 1666)
        self.assertTrue(data["memory_rag"]["include_manual_facts"])
        self.assertFalse(data["memory_rag"]["include_manual_preferences"])
        self.assertTrue(data["memory_rag"]["include_session_summaries"])
        self.assertTrue(data["memory_rag"]["include_short_messages"])
        self.assertTrue(data["memory_rag"]["include_gap_scene_summaries"])
        self.assertTrue(data["project_doc_rag"]["enabled"])
        self.assertTrue(data["project_doc_rag"]["explicit_agent_dev_context_only"])
        self.assertFalse(data["project_doc_rag"]["ordinary_chat_injection_allowed"])
        self.assertEqual(data["project_doc_rag"]["top_k"], 3)
        self.assertAlmostEqual(data["project_doc_rag"]["min_score"], 0.49)
        self.assertEqual(data["project_doc_rag"]["max_context_chars"], 1234)
        self.assertFalse(data["memory_content_exposed"])
        self.assertFalse(data["project_doc_content_exposed"])
        self.assertFalse(data["retrieval_executed"])
        self.assertFalse(data["index_rebuild_executed"])
        self.assertFalse(data["boundary"]["project_doc_rag_in_ordinary_chat"])

        rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("secret owner message", rendered)
        self.assertNotIn("secret assistant message", rendered)

    def test_external_read_endpoint_is_local_safe_and_exposes_only_metadata(self):
        temp_dir, patcher = self.temp_database()
        safe_result = "\n".join(
            [
                "外部只读查询已完成。",
                "Provider：tavily。",
                "结果数：3。",
                "来源主机数：2。",
                "丢弃结果数：1。",
                "外部请求：1。",
                "状态类别：completed。",
                "错误类别：none。",
            ]
        )
        with temp_dir, patcher, patch.dict(
            os.environ,
            {
                "BOT_OWNER_QQ": "10001",
                "ENABLE_AGENT_WEB": "true",
                "TAVILY_API_KEY": "tvly-secret-must-not-leak",
                "TAVILY_TIMEOUT_SECONDS": "10",
            },
            clear=True,
        ):
            task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                title="外部只读查询报告",
                goal="主人显式提供的外部只读查询（原文未持久化）",
            )
            _, claimed = self.agent_tasks.claim_agent_task_for_work(
                task_id=task_id,
                session_key="private:10001",
                user_id="10001",
                work_type="external_read_report",
                query_summary="主人显式提供的外部只读查询（原文未持久化）",
            )
            _, completed = self.agent_tasks.complete_agent_task_work(
                task_id=task_id,
                session_key="private:10001",
                user_id="10001",
                work_type="external_read_report",
                result=safe_result,
            )

            response = self.client.get("/api/v1/owner-console/external-read")

        self.assertTrue(claimed)
        self.assertTrue(completed)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["resource"], "external-read")
        self.assertTrue(payload["read_only"])
        self.assertFalse(payload["web_write_enabled"])
        data = payload["data"]
        self.assertTrue(data["enabled"])
        self.assertTrue(data["credential_configured"])
        self.assertTrue(data["executor_configured"])
        self.assertEqual(data["provider_name"], "tavily")
        self.assertEqual(data["search_depth"], "basic")
        self.assertEqual(data["max_results"], 3)
        self.assertEqual(data["endpoint_host"], "api.tavily.com")
        self.assertTrue(data["dependencies"]["compatible"])
        self.assertTrue(data["recent_task"]["available"])
        self.assertEqual(data["recent_task"]["task_id"], task_id)
        self.assertEqual(data["recent_task"]["result_count"], 3)
        self.assertEqual(data["recent_task"]["external_request_count"], 1)
        self.assertFalse(data["boundary"]["live_probe_executed"])
        self.assertFalse(data["boundary"]["external_request_executed"])
        self.assertFalse(data["boundary"]["query_exposed"])
        self.assertFalse(data["boundary"]["result_content_exposed"])
        self.assertFalse(data["boundary"]["source_url_exposed"])
        self.assertFalse(data["boundary"]["credential_value_exposed"])

        rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("tvly-secret-must-not-leak", rendered)
        self.assertNotIn("主人显式提供", rendered)
        self.assertNotIn("https://", rendered.lower())

    def test_diagnostics_endpoint_is_read_only_and_skips_external_probes(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher, patch.dict(
            os.environ,
            {
                "BOT_OWNER_QQ": "10001",
                "ENABLE_PRIVATE_CHAT": "true",
                "ENABLE_GROUP_CHAT": "true",
                "ENABLE_MAIN_AGENT": "true",
                "MAIN_AGENT_USE_LLM": "false",
                "ENABLE_CHAT_GRAPH_RUNTIME": "true",
                "ENABLE_VISION": "true",
                "VISION_MODEL": "qwen2.5vl:3b",
                "VISION_NUM_CTX": "16384",
                "VISION_MAX_IMAGES": "1",
                "VISION_IMAGE_CACHE_TTL_SECONDS": "120",
                "VISION_PRIVATE_IMAGE_WAIT_SECONDS": "5",
                "ENABLE_TTS": "false",
                "TTS_AUTO_START": "false",
            },
            clear=True,
        ):
            self.memory.append_message(
                "private:10001",
                "user",
                "diagnostics secret message",
                "private",
                "10001",
            )

            response = self.client.get("/api/v1/owner-console/diagnostics")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["resource"], "diagnostics")
        self.assertTrue(payload["read_only"])
        self.assertTrue(payload["http_api_enabled"])
        self.assertFalse(payload["web_write_enabled"])
        self.assertIsNone(payload["error"])

        data = payload["data"]
        self.assertEqual(
            data["bot_status"]["display_lines"],
            [
                "Owner Console HTTP API: ok",
                "transport=http",
                "mode=read_only",
                "web_write_enabled=false",
            ],
        )
        self.assertIn(
            "external_probes_executed=false",
            data["diagnostics"]["display_lines"],
        )
        self.assertIn(
            "qq_adapter_imported=false",
            data["diagnostics"]["display_lines"],
        )
        self.assertIn(
            "diagnostics_module_imported=false",
            data["diagnostics"]["display_lines"],
        )
        self.assertIn("enable_main_agent=true", data["config"]["display_lines"])
        self.assertIn("main_agent_use_llm=false", data["config"]["display_lines"])
        self.assertIn("vision_model=qwen2.5vl:3b", data["vision"]["display_lines"])
        self.assertIn("ollama_probe_executed=false", data["vision"]["display_lines"])
        self.assertIn(
            "vision_inference_executed=false",
            data["vision"]["display_lines"],
        )
        self.assertIn(
            "image_cache_stats_collected=false",
            data["image_cache"]["display_lines"],
        )
        self.assertIn("message_count=1", data["memory"]["display_lines"])
        self.assertIn(
            "memory_content_exposed=false",
            data["memory"]["display_lines"],
        )
        self.assertIn(
            "retrieval_executed=false",
            data["memory"]["display_lines"],
        )
        self.assertIn(
            "index_rebuild_executed=false",
            data["memory"]["display_lines"],
        )
        self.assertIn("tts_probe_executed=false", data["tts"]["display_lines"])
        self.assertIn(
            "recent_error_log_read=false",
            data["recent_errors"]["display_lines"],
        )
        self.assertEqual(data["observations"]["main_agent"], [])
        self.assertEqual(data["observations"]["root_graph"], [])
        self.assertFalse(
            data["boundary"]["ordinary_chat_can_trigger_main_agent"]
        )

        rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("diagnostics secret message", rendered)

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
