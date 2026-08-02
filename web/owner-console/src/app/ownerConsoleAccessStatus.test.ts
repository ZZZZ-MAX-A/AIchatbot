import { describe, expect, it } from "vitest";

import type {
  OwnerConsoleHealth,
  OwnerConsoleRoutesEnvelope,
} from "../api/ownerConsoleTypes";
import { buildOwnerConsoleAccessStatus } from "./ownerConsoleAccessStatus";

function createHealth(): OwnerConsoleHealth {
  return {
    ok: true,
    service: "owner-console",
    schema_version: "owner_console.http.v1",
    api_prefix: "/api/v1/owner-console",
    read_only: false,
    snapshot_read_only: true,
    http_api_enabled: true,
    web_write_enabled: true,
    approval_actions_enabled: true,
    task_actions_enabled: true,
    access_control_actions_enabled: true,
    manual_diagnostic_actions_enabled: true,
    automatic_diagnostics_enabled: false,
    configuration_write_enabled: false,
    business_data_write_enabled: true,
    enabled_routes: [],
  };
}

function createRoutes(): OwnerConsoleRoutesEnvelope {
  return {
    schema_version: "owner_console.http.v1",
    read_model_schema_version: "owner_console.read_model.v0",
    transport: "http",
    api_prefix: "/api/v1/owner-console",
    resource: "routes",
    generated_at: "2026-08-01T08:00:00Z",
    read_only: true,
    http_api_enabled: true,
    web_write_enabled: false,
    error: null,
    data: {
      api_prefix: "/api/v1/owner-console",
      allowed_methods: ["GET", "POST"],
      context_override_allowed: false,
      write_routes_enabled: true,
      manual_runtime_action_routes_enabled: true,
      approval_action_routes_enabled: true,
      task_action_routes_enabled: true,
      access_action_routes_enabled: true,
      route_count: 31,
      rows: [],
      boundary: {},
    },
  };
}

describe("buildOwnerConsoleAccessStatus", () => {
  it("treats read-only snapshots plus registered approval actions as the expected V1 contract", () => {
    const result = buildOwnerConsoleAccessStatus(createHealth(), createRoutes());

    expect(result.snapshot.state).toBe("read_only");
    expect(result.snapshot.value).toBe("只读");
    expect(result.webWrite.state).toBe("registered_actions");
    expect(result.webWrite.value).toBe("受限操作");
    expect(result.webWrite.route).toBe(
      "/owner-console/tasks?status=pending",
    );
  });

  it("keeps a fully closed web-write surface healthy", () => {
    const health = createHealth();
    const routes = createRoutes();
    health.read_only = true;
    health.web_write_enabled = false;
    health.approval_actions_enabled = false;
    health.task_actions_enabled = false;
    health.business_data_write_enabled = false;
    routes.data!.write_routes_enabled = false;
    routes.data!.approval_action_routes_enabled = false;
    routes.data!.task_action_routes_enabled = false;

    const result = buildOwnerConsoleAccessStatus(health, routes);

    expect(result.webWrite.state).toBe("closed");
    expect(result.webWrite.value).toBe("已关闭");
  });

  it("reports a contract mismatch as unsafe instead of calling every write mode abnormal", () => {
    const health = createHealth();
    const routes = createRoutes();
    health.configuration_write_enabled = true;

    const result = buildOwnerConsoleAccessStatus(health, routes);

    expect(result.webWrite.state).toBe("unsafe");
    expect(result.webWrite.value).toBe("异常");
    expect(result.webWrite.route).toBe("/owner-console/settings");
  });
});
