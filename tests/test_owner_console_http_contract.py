from __future__ import annotations

import json
import re
import unittest

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module


class OwnerConsoleHttpContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.http_models = load_module(
            "src.plugins.ai_chat.owner_console_http_models",
            AI_CHAT_ROOT / "owner_console_http_models.py",
        )
        cls.http_contract = load_module(
            "src.plugins.ai_chat.owner_console_http_contract",
            AI_CHAT_ROOT / "owner_console_http_contract.py",
        )
        cls.read_runtime = load_module(
            "src.plugins.ai_chat.owner_console_read_runtime",
            AI_CHAT_ROOT / "owner_console_read_runtime.py",
        )

    def test_http_route_contract_uses_restful_owner_console_namespace(self):
        snapshot = (
            self.http_contract.build_owner_console_http_route_contract_snapshot()
        )

        self.assertEqual(
            snapshot.schema_version,
            self.http_models.OWNER_CONSOLE_HTTP_SCHEMA_VERSION,
        )
        self.assertEqual(
            snapshot.read_model_schema_version,
            self.read_runtime.OWNER_CONSOLE_SCHEMA_VERSION,
        )
        self.assertEqual(snapshot.api_prefix, "/api/v1/owner-console")
        self.assertEqual(snapshot.allowed_methods, ["GET", "POST"])
        self.assertEqual(snapshot.context_strategy, "owner_private_session_from_config")
        self.assertFalse(snapshot.context_override_allowed)
        self.assertFalse(snapshot.write_routes_enabled)
        self.assertFalse(snapshot.manual_runtime_action_routes_enabled)
        self.assertFalse(snapshot.boundary.ordinary_chat_can_trigger_main_agent)
        self.assertTrue(snapshot.boundary.owner_write_requires_approval)

        expected = [
            ("routes", "routes", "/api/v1/owner-console/routes", "route_contract"),
            ("overview", "overview", "/api/v1/owner-console/overview", "dashboard"),
            ("tasks", "tasks", "/api/v1/owner-console/tasks", "tasks"),
            ("tasks.detail", "tasks", "/api/v1/owner-console/tasks/{task_id}", "task_detail"),
            ("approvals", "approvals", "/api/v1/owner-console/approvals", "approvals"),
            (
                "approvals.detail",
                "approvals",
                "/api/v1/owner-console/approvals/{approval_id}",
                "approval_detail",
            ),
            ("diagnostics", "diagnostics", "/api/v1/owner-console/diagnostics", "diagnostics"),
            (
                "reliability",
                "reliability",
                "/api/v1/owner-console/reliability",
                "reliability",
            ),
            (
                "external-read",
                "external-read",
                "/api/v1/owner-console/external-read",
                "external_read",
            ),
            ("memory", "memory", "/api/v1/owner-console/memory", "memory"),
            (
                "access-control",
                "access-control",
                "/api/v1/owner-console/access-control",
                "access_control",
            ),
            ("settings", "settings", "/api/v1/owner-console/settings", "settings"),
            (
                "manual-diagnostics",
                "manual-diagnostics",
                "/api/v1/owner-console/manual-diagnostics",
                "manual_diagnostics",
            ),
            (
                "manual-diagnostics.project-doc-rag",
                "manual-diagnostics/project-doc-rag",
                "/api/v1/owner-console/manual-diagnostics/project-doc-rag",
                "manual_diagnostics",
            ),
            (
                "manual-diagnostics.memory-rag-consistency",
                "manual-diagnostics/memory-rag-consistency",
                "/api/v1/owner-console/manual-diagnostics/memory-rag-consistency",
                "manual_diagnostics",
            ),
            (
                "manual-diagnostics.main-llm-contract",
                "manual-diagnostics/main-llm-contract",
                "/api/v1/owner-console/manual-diagnostics/main-llm-contract",
                "manual_diagnostics",
            ),
        ]
        self.assertEqual(
            [(row.name, row.resource, row.path, row.read_page) for row in snapshot.rows],
            expected,
        )
        self.assertEqual(snapshot.route_count, len(expected))

        runtime_class = self.read_runtime.OwnerConsoleReadRuntime
        for row in snapshot.rows:
            self.assertTrue(row.path.startswith("/api/v1/owner-console/"))
            self.assertEqual(row.path, row.path.lower())
            self.assertFalse(row.http_api_enabled)
            self.assertFalse(row.web_write_enabled)
            self.assertFalse(row.direct_qq_dependency_allowed)
            if row.name in {
                "manual-diagnostics.project-doc-rag",
                "manual-diagnostics.memory-rag-consistency",
                "manual-diagnostics.main-llm-contract",
            }:
                self.assertEqual(row.method, "POST")
                self.assertFalse(row.read_only)
                self.assertTrue(row.write_side_effect_allowed)
                self.assertTrue(row.manual_runtime_action_allowed)
            elif row.name == "manual-diagnostics":
                self.assertEqual(row.method, "GET")
                self.assertTrue(row.read_only)
                self.assertFalse(row.write_side_effect_allowed)
                self.assertFalse(row.manual_runtime_action_allowed)
            else:
                self.assertEqual(row.method, "GET")
                self.assertTrue(row.read_only)
                self.assertFalse(row.write_side_effect_allowed)
                self.assertFalse(row.manual_runtime_action_allowed)
                self.assertTrue(hasattr(runtime_class, row.runtime_method), row.name)
            for segment in row.path.split("/"):
                if not segment or segment.startswith("{"):
                    continue
                self.assertNotIn("_", segment)

        rows = {row.name: row for row in snapshot.rows}
        self.assertEqual(rows["routes"].runtime_method, "build_route_contract_snapshot")
        self.assertEqual(
            rows["routes"].read_model,
            "OwnerConsoleReadRouteContractSnapshot",
        )
        self.assertFalse(rows["routes"].requires_context)
        self.assertEqual(rows["overview"].runtime_method, "build_overview")
        self.assertEqual(rows["overview"].query_params, ["task_limit", "approval_limit"])
        self.assertTrue(rows["overview"].requires_context)
        self.assertEqual(rows["tasks.detail"].path_params, ["task_id"])
        self.assertEqual(
            rows["tasks.detail"].query_params,
            ["event_limit", "preview_limit"],
        )
        self.assertEqual(
            rows["tasks"].query_params,
            ["status", "work_type", "limit"],
        )
        self.assertEqual(rows["approvals.detail"].path_params, ["approval_id"])
        self.assertEqual(rows["settings"].query_params, [])
        self.assertFalse(rows["settings"].requires_context)
        self.assertTrue(rows["external-read"].requires_context)
        self.assertFalse(rows["reliability"].requires_context)
        self.assertEqual(
            rows["reliability"].read_model,
            "OwnerConsoleReliabilitySnapshot",
        )
        self.assertEqual(
            rows["external-read"].read_model,
            "OwnerConsoleExternalReadSnapshot",
        )
        self.assertEqual(
            rows["manual-diagnostics.project-doc-rag"].runtime_method,
            "run_project_doc_rag_probe",
        )
        self.assertEqual(
            rows["manual-diagnostics.memory-rag-consistency"].runtime_method,
            "run_memory_rag_consistency",
        )
        self.assertEqual(
            rows["manual-diagnostics.main-llm-contract"].runtime_method,
            "run_main_llm_contract",
        )

    def test_http_response_and_error_envelopes_are_stable_and_json_safe(self):
        snapshot = (
            self.http_contract.build_owner_console_http_route_contract_snapshot()
        )

        payload = self.http_models.owner_console_http_success_response(
            "routes",
            snapshot,
        )
        rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)

        self.assertEqual(payload["schema_version"], "owner_console.http.v1")
        self.assertEqual(
            payload["read_model_schema_version"],
            self.read_runtime.OWNER_CONSOLE_SCHEMA_VERSION,
        )
        self.assertEqual(payload["transport"], "http")
        self.assertEqual(payload["api_prefix"], "/api/v1/owner-console")
        self.assertEqual(payload["resource"], "routes")
        self.assertEqual(payload["generated_at"], snapshot.generated_at)
        self.assertTrue(payload["read_only"])
        self.assertFalse(payload["http_api_enabled"])
        self.assertFalse(payload["web_write_enabled"])
        self.assertIsNone(payload["error"])
        self.assertEqual(payload["data"]["route_count"], snapshot.route_count)
        self.assertIn('"path": "/api/v1/owner-console/routes"', rendered)

        error_payload = self.http_models.owner_console_http_error_response(
            "tasks",
            code="not_found",
            message="task not found",
            details={"task_id": 123},
        )
        json.dumps(error_payload, ensure_ascii=False, sort_keys=True)
        self.assertEqual(error_payload["schema_version"], "owner_console.http.v1")
        self.assertEqual(error_payload["resource"], "tasks")
        self.assertTrue(error_payload["read_only"])
        self.assertFalse(error_payload["web_write_enabled"])
        self.assertIsNone(error_payload["data"])
        self.assertEqual(error_payload["error"]["code"], "not_found")
        self.assertEqual(error_payload["error"]["message"], "task not found")
        self.assertEqual(error_payload["error"]["details"], {"task_id": 123})

        with self.assertRaises(ValueError):
            self.http_models.owner_console_http_success_response("", snapshot)
        with self.assertRaises(ValueError):
            self.http_models.owner_console_http_error_response(
                "tasks",
                code="missing_task",
                message="task not found",
            )

    def test_http_contract_has_no_qq_adapter_or_fastapi_dependency(self):
        sources = [
            AI_CHAT_ROOT / "owner_console_http_models.py",
            AI_CHAT_ROOT / "owner_console_http_contract.py",
        ]
        combined_source = "\n".join(path.read_text(encoding="utf-8") for path in sources)
        lower_source = combined_source.lower()

        self.assertNotIn("nonebot", lower_source)
        self.assertNotIn("messageevent", lower_source)
        self.assertNotIn("matcher.finish", lower_source)
        self.assertNotIn("bot.send", lower_source)
        self.assertNotIn("fastapi", lower_source)
        self.assertNotIn("owner_write_runtime", combined_source)
        self.assertIsNone(re.search(r"\bput\b|\bpatch\b|\bdelete\b", lower_source))
        self.assertIn('method="post"', lower_source)
        self.assertIn('owner_console_http_allowed_methods = ("get", "post")', lower_source)
