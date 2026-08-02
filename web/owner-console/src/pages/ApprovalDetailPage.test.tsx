import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  OwnerConsoleApprovalActionEnvelope,
  OwnerConsoleApprovalActionability,
  OwnerConsoleApprovalDetailEnvelope,
} from "../api/ownerConsoleTypes";
import { ApprovalDetailPage } from "./ApprovalDetailPage";

const { approveApproval, getApprovalDetail, rejectApproval } = vi.hoisted(() => ({
  approveApproval: vi.fn(),
  getApprovalDetail: vi.fn(),
  rejectApproval: vi.fn(),
}));

vi.mock("../api/ownerConsoleApi", () => {
  class OwnerConsoleApiError extends Error {
    status = 500;
    code = "internal_error";
  }
  return {
    OwnerConsoleApiError,
    ownerConsoleApi: {
      approveApproval,
      getApprovalDetail,
      rejectApproval,
    },
  };
});

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

function detailEnvelope(
  overrides: Partial<OwnerConsoleApprovalActionability> = {},
): OwnerConsoleApprovalDetailEnvelope {
  return {
    schema_version: "owner_console.http.v1",
    read_model_schema_version: "owner_console.read_model.v0",
    transport: "http",
    api_prefix: "/api/v1/owner-console",
    resource: "approvals",
    generated_at: generatedAt,
    read_only: true,
    http_api_enabled: true,
    web_write_enabled: false,
    error: null,
    data: {
      generated_at: generatedAt,
      approval: {
        approval_id: 42,
        task_id: 9,
        task_title: "清理错误日志",
        tool_name: "owner_write_command",
        risk_level: "write_local",
        reason_preview: "主人要求清理错误日志",
        status: "pending",
        status_label: "待审批",
        created_at: generatedAt,
        expires_at: "",
        decided_at: "",
        actionability: {
          can_approve: true,
          can_reject: true,
          resume_enabled: true,
          blocked_reason: "",
          future_operation_only: false,
          ...overrides,
        },
      },
      reason: "主人要求清理错误日志",
      tool_input: {
        preview_json: '{"command":"clear_error_log"}',
        redacted: false,
        truncated: false,
      },
      task: {
        task_id: 9,
        title: "清理错误日志",
        goal_preview: "清理错误日志",
        status: "pending",
        status_label: "待处理",
        result_preview: "",
        created_at: generatedAt,
        updated_at: generatedAt,
        latest_event_kind: "approval_requested",
        latest_event_summary: "等待审批",
        pending_approval_ids: [42],
        next_action: "请先处理关联审批 #42；审批未决定前不取消任务。",
        next_action_code: "review_pending_approval",
        work_type: "",
        processing_category: "awaiting_approval",
        processing_label: "等待审批",
        processing_detail: "请先处理关联审批 #42；审批未决定前不取消任务。",
        actionability: {
          can_cancel: false,
          task_actions_enabled: true,
          blocked_reason: "decide the pending approval before cancelling the task",
        },
      },
      recent_events: [],
      boundary,
    },
  };
}

function approvedActionEnvelope(): OwnerConsoleApprovalActionEnvelope {
  const approvedDetail = detailEnvelope();
  if (!approvedDetail.data) {
    throw new Error("test detail missing");
  }
  approvedDetail.data.approval = {
    ...approvedDetail.data.approval,
    status: "approved",
    status_label: "已批准",
    decided_at: generatedAt,
    actionability: {
      can_approve: false,
      can_reject: false,
      resume_enabled: false,
      blocked_reason: "approval is not pending",
      future_operation_only: false,
    },
  };
  approvedDetail.data.task = approvedDetail.data.task
    ? {
        ...approvedDetail.data.task,
        status: "done",
        status_label: "已完成",
        pending_approval_ids: [],
        next_action: "completed",
      }
    : null;
  return {
    schema_version: "owner_console.http.v1",
    read_model_schema_version: "owner_console.read_model.v0",
    transport: "http",
    api_prefix: "/api/v1/owner-console",
    resource: "approvals/42/approve",
    generated_at: generatedAt,
    read_only: false,
    http_api_enabled: true,
    web_write_enabled: true,
    manual_runtime_action: false,
    approval_action: true,
    configuration_write_enabled: false,
    business_data_write_enabled: true,
    error: null,
    data: {
      action: {
        generated_at: generatedAt,
        approval_id: 42,
        task_id: 9,
        decision: "approved",
        decision_changed: true,
        resume_attempted: true,
        resume_executed: true,
        task_status: "done",
        outcome: "succeeded",
        code: "approval_resume_succeeded",
        safe_message: "本地工具已受控执行完成。",
      },
      approval_detail: approvedDetail.data,
    },
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/owner-console/approvals/42"]}>
      <Routes>
        <Route
          path="/owner-console/approvals/:approval_id"
          element={<ApprovalDetailPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ApprovalDetailPage", () => {
  beforeEach(() => {
    getApprovalDetail.mockReset();
    approveApproval.mockReset();
    rejectApproval.mockReset();
    getApprovalDetail.mockResolvedValue(detailEnvelope());
    approveApproval.mockResolvedValue(approvedActionEnvelope());
  });

  afterEach(() => cleanup());

  it("requires a second confirmation before approving and refreshes task state", async () => {
    renderPage();

    const approveButton = await screen.findByRole("button", { name: "批准并执行" });
    fireEvent.click(approveButton);
    expect(approveApproval).not.toHaveBeenCalled();
    expect(screen.getByText("确认批准并立即执行？")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "确认批准并执行" }));
    await waitFor(() => expect(approveApproval).toHaveBeenCalledWith(42));
    expect(await screen.findByText("本地工具已受控执行完成。")).toBeTruthy();
    expect(screen.getByText("已批准")).toBeTruthy();
    expect(screen.getByText("已完成")).toBeTruthy();
  });

  it("keeps reject available when approval is blocked by redacted input", async () => {
    getApprovalDetail.mockResolvedValue(
      detailEnvelope({
        can_approve: false,
        can_reject: true,
        resume_enabled: false,
        blocked_reason: "sensitive tool input is redacted; web approval is blocked",
      }),
    );
    renderPage();

    const approveButton = await screen.findByRole("button", { name: "批准并执行" });
    expect(approveButton.hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "拒绝审批" }).hasAttribute("disabled")).toBe(false);
    expect(screen.getByText(/参数中存在被隐藏的敏感值/)).toBeTruthy();
  });
});
