import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  OwnerConsoleTaskActionEnvelope,
  OwnerConsoleTaskDetailEnvelope,
} from "../api/ownerConsoleTypes";
import { TaskDetailPage } from "./TaskDetailPage";

const { cancelTask, getTaskDetail } = vi.hoisted(() => ({
  cancelTask: vi.fn(),
  getTaskDetail: vi.fn(),
}));

vi.mock("../api/ownerConsoleApi", () => {
  class OwnerConsoleApiError extends Error {
    status = 500;
    code = "internal_error";
  }
  return {
    OwnerConsoleApiError,
    ownerConsoleApi: { cancelTask, getTaskDetail },
  };
});

const generatedAt = "2026-08-01T08:00:00Z";
const boundary = {
  main_agent_entry: "owner_only",
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
  overrides: Partial<OwnerConsoleTaskDetailEnvelope["data"] extends infer T ? NonNullable<T> : never> = {},
): OwnerConsoleTaskDetailEnvelope {
  const task = {
    task_id: 9,
    title: "历史演练任务",
    goal_preview: "历史演练任务",
    status: "pending",
    status_label: "待处理",
    result_preview: "",
    created_at: generatedAt,
    updated_at: generatedAt,
    latest_event_kind: "created",
    latest_event_summary: "任务已创建",
    pending_approval_ids: [] as number[],
    next_action: "任务长期没有进入审批或执行；建议取消。",
    next_action_code: "review_task_goal",
    work_type: "",
    processing_category: "stale_residual",
    processing_label: "旧任务残留",
    processing_detail: "任务长期没有进入审批或执行；建议取消。",
    actionability: {
      can_cancel: true,
      task_actions_enabled: true,
      blocked_reason: "",
    },
  };
  return {
    schema_version: "owner_console.http.v1",
    read_model_schema_version: "owner_console.read_model.v0",
    transport: "http",
    api_prefix: "/api/v1/owner-console",
    resource: "tasks",
    generated_at: generatedAt,
    read_only: true,
    http_api_enabled: true,
    web_write_enabled: false,
    error: null,
    data: {
      generated_at: generatedAt,
      task,
      goal: "历史演练任务",
      result: "",
      events: [],
      approvals: [],
      next_action: task.processing_detail,
      boundary,
      ...overrides,
    },
  };
}

function cancelledEnvelope(): OwnerConsoleTaskActionEnvelope {
  const original = detailEnvelope();
  const taskDetail = {
    ...original.data!,
    task: {
      ...original.data!.task,
      status: "cancelled",
      status_label: "已取消",
      processing_category: "closed",
      processing_label: "已收口",
      processing_detail: "任务已经完成或取消，仅供复盘。",
      actionability: {
        can_cancel: false,
        task_actions_enabled: true,
        blocked_reason: "only a pending task can be cancelled",
      },
    },
  };
  return {
    ...original,
    resource: "tasks/9/cancel",
    read_only: false,
    web_write_enabled: true,
    manual_runtime_action: false,
    approval_action: false,
    task_action: true,
    configuration_write_enabled: false,
    business_data_write_enabled: true,
    data: {
      action: {
        generated_at: generatedAt,
        task_id: 9,
        previous_status: "pending",
        task_status: "cancelled",
        status_changed: true,
        tool_executed: false,
        approval_resumed: false,
        outcome: "cancelled",
        code: "task_cancelled",
        safe_message: "任务已取消并收口；未执行原工具，也未恢复任何审批。",
      },
      task_detail: taskDetail,
    },
  };
}

function renderPage() {
  render(
    <MemoryRouter initialEntries={["/owner-console/tasks/9"]}>
      <Routes>
        <Route path="/owner-console/tasks/:task_id" element={<TaskDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  getTaskDetail.mockResolvedValue(detailEnvelope());
  cancelTask.mockResolvedValue(cancelledEnvelope());
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("TaskDetailPage task cancellation", () => {
  it("requires two explicit clicks and updates the task after cancellation", async () => {
    renderPage();
    const begin = await screen.findByRole("button", { name: "取消并收口" });
    expect(screen.queryByText("review_task_goal")).toBeNull();

    fireEvent.click(begin);
    expect(cancelTask).not.toHaveBeenCalled();
    expect(screen.getByText("不可撤销操作")).toBeTruthy();
    expect(screen.getByText("任务状态将永久变为“已取消”")).toBeTruthy();
    expect(screen.getByRole("group", { name: "取消任务确认" }).className).toContain(
      "action-confirmation--danger",
    );

    fireEvent.click(
      screen.getByRole("button", { name: "确认取消并收口（不可撤销）" }),
    );
    await waitFor(() => expect(cancelTask).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("任务已取消并收口；未执行原工具，也未恢复任何审批。")).toBeTruthy();
    expect(screen.getByText("已取消")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "取消并收口" })).toBeNull();
  });

  it("shows the approval entry and never offers cancellation while approval is pending", async () => {
    const envelope = detailEnvelope();
    envelope.data!.task = {
      ...envelope.data!.task,
      pending_approval_ids: [42],
      processing_category: "awaiting_approval",
      processing_label: "等待审批",
      processing_detail: "请先处理关联审批 #42；审批未决定前不取消任务。",
      actionability: {
        can_cancel: false,
        task_actions_enabled: true,
        blocked_reason: "decide the pending approval before cancelling the task",
      },
    };
    getTaskDetail.mockResolvedValue(envelope);
    renderPage();

    expect(await screen.findByRole("link", { name: "处理审批 #42" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /取消/ })).toBeNull();
  });

  it("keeps task actions hidden when the independent switch is disabled", async () => {
    const envelope = detailEnvelope();
    envelope.data!.task.actionability = {
      can_cancel: false,
      task_actions_enabled: false,
      blocked_reason: "web task actions are disabled",
    };
    getTaskDetail.mockResolvedValue(envelope);
    renderPage();

    expect(await screen.findByText("网页任务处理开关未开启，当前只能查看任务证据。")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "取消并收口" })).toBeNull();
  });
});
