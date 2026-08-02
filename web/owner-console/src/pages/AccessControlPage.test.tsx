import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  OwnerConsoleAccessActionEnvelope,
  OwnerConsoleAccessControlEnvelope,
} from "../api/ownerConsoleTypes";
import { AccessControlPage } from "./AccessControlPage";

const api = vi.hoisted(() => ({
  getAccessControl: vi.fn(),
  addPrivateWhitelistItem: vi.fn(),
  removePrivateWhitelistItem: vi.fn(),
  addGroupWhitelistItem: vi.fn(),
  removeGroupWhitelistItem: vi.fn(),
  addUserBlacklistItem: vi.fn(),
  removeUserBlacklistItem: vi.fn(),
}));

vi.mock("../api/ownerConsoleApi", () => ({
  OwnerConsoleApiError: class OwnerConsoleApiError extends Error {
    status = 500;
    code = "internal_error";
  },
  ownerConsoleApi: api,
}));

const generatedAt = "2026-08-01T08:00:00+00:00";
const boundary = {
  main_agent_entry: "/agent explicit owner entry only",
  ordinary_chat_can_trigger_main_agent: false,
  project_doc_rag_in_ordinary_chat: false,
  shell_tools_exposed: false,
  arbitrary_file_write_allowed: false,
  unregistered_db_write_allowed: false,
  owner_write_requires_approval: true,
  approval_resume_requires_registered_tool: true,
  approval_resume_requires_enabled_tool: true,
  multi_step_write_automation_allowed: false,
  extra_qq_send_side_effect_allowed: false,
};

function snapshotEnvelope(): OwnerConsoleAccessControlEnvelope {
  return {
    schema_version: "owner_console.http.v1",
    read_model_schema_version: "owner_console.read_model.v0",
    transport: "http",
    api_prefix: "/api/v1/owner-console",
    resource: "access-control",
    generated_at: generatedAt,
    read_only: true,
    http_api_enabled: true,
    web_write_enabled: false,
    error: null,
    data: {
      generated_at: generatedAt,
      revision: 4,
      access_actions_enabled: true,
      owner_configured: true,
      private_chat_enabled: true,
      group_chat_enabled: true,
      unknown_private_policy: "deny",
      private_whitelist: {
        label: "private_whitelist",
        count: 2,
        environment_count: 1,
        dynamic_count: 1,
        truncated: false,
        items: [
          { value: "11111", source: "environment", editable: false },
          { value: "22222", source: "dynamic", editable: true },
        ],
      },
      group_whitelist: {
        label: "group_whitelist",
        count: 0,
        environment_count: 0,
        dynamic_count: 0,
        truncated: false,
        items: [],
      },
      user_blacklist: {
        label: "user_blacklist",
        count: 0,
        environment_count: 0,
        dynamic_count: 0,
        truncated: false,
        items: [],
      },
      boundary,
    },
  };
}

function actionEnvelope(): OwnerConsoleAccessActionEnvelope {
  const snapshot = snapshotEnvelope();
  if (!snapshot.data) throw new Error("missing test snapshot");
  return {
    ...snapshot,
    resource: "access-control/private-whitelist/add",
    read_only: false,
    web_write_enabled: true,
    manual_runtime_action: false,
    approval_action: false,
    task_action: false,
    access_action: true,
    configuration_write_enabled: false,
    business_data_write_enabled: true,
    data: {
      action: {
        generated_at: generatedAt,
        list_name: "private_whitelist",
        operation: "add",
        item: "33333",
        changed: true,
        effective: true,
        revision: 5,
        source_after: "dynamic",
        code: "access_item_added",
        safe_message: "动态访问名单已加入并立即生效。",
      },
      access_control: snapshot.data,
    },
  };
}

describe("AccessControlPage", () => {
  beforeEach(() => {
    for (const mock of Object.values(api)) mock.mockReset();
    api.getAccessControl.mockResolvedValue(snapshotEnvelope());
    api.addPrivateWhitelistItem.mockResolvedValue(actionEnvelope());
  });

  afterEach(() => cleanup());

  it("marks environment items as fixed and exposes removal only for dynamic items", async () => {
    render(<AccessControlPage />);

    expect(await screen.findByText("环境固定")).toBeTruthy();
    expect(screen.getByText("动态可编辑")).toBeTruthy();
    expect(screen.getByText("网页不可删除")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "移除 11111" })).toBeNull();
    expect(screen.getByRole("button", { name: "移除 22222" })).toBeTruthy();
  });

  it("requires confirmation, sends the snapshot revision and reloads after success", async () => {
    render(<AccessControlPage />);
    const inputs = await screen.findAllByPlaceholderText("输入 5–20 位纯数字");
    const input = inputs[0];
    fireEvent.change(input, { target: { value: "33333" } });
    fireEvent.click(screen.getAllByRole("button", { name: "准备加入" })[0]);

    expect(api.addPrivateWhitelistItem).not.toHaveBeenCalled();
    expect(screen.getByText(/确认加入“.*33333.*”吗/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "确认执行" }));

    await waitFor(() =>
      expect(api.addPrivateWhitelistItem).toHaveBeenCalledWith("33333", 4),
    );
    await waitFor(() => expect(api.getAccessControl).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("动态访问名单已加入并立即生效。")).toBeTruthy();
  });
});
