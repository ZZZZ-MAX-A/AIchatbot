import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  OwnerConsoleApprovalListEnvelope,
  OwnerConsoleTaskListEnvelope,
} from "../api/ownerConsoleTypes";
import { ApprovalsPage } from "./ApprovalsPage";
import { TasksPage } from "./TasksPage";

const { getApprovals, getTasks } = vi.hoisted(() => ({
  getApprovals: vi.fn(),
  getTasks: vi.fn(),
}));

vi.mock("../api/ownerConsoleApi", () => {
  class OwnerConsoleApiError extends Error {
    status = 500;
    code = "internal_error";
  }
  return {
    OwnerConsoleApiError,
    ownerConsoleApi: {
      getApprovals,
      getTasks,
    },
  };
});

const generatedAt = "2026-08-01T08:00:00Z";

function LocationProbe() {
  return <output aria-label="current search">{useLocation().search}</output>;
}

const taskEnvelope: OwnerConsoleTaskListEnvelope = {
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
    status_filter: "pending",
    work_type_filter: null,
    category_filter: null,
    limit: 20,
    page: 1,
    page_size: 20,
    total_matching: 0,
    total_pages: 1,
    has_previous: false,
    has_next: false,
    total_visible: 0,
    rows: [],
    boundary: {
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
    },
  },
};

const approvalEnvelope: OwnerConsoleApprovalListEnvelope = {
  ...taskEnvelope,
  resource: "approvals",
  data: {
    generated_at: generatedAt,
    status_filter: "pending",
    limit: 20,
    total_visible: 0,
    rows: [],
    boundary: taskEnvelope.data!.boundary,
  },
};

beforeEach(() => {
  getTasks.mockResolvedValue(taskEnvelope);
  getApprovals.mockResolvedValue(approvalEnvelope);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("pending list URL filters", () => {
  it("keeps a task-detail entry in the first visible columns", async () => {
    getTasks.mockResolvedValue({
      ...taskEnvelope,
      data: {
        ...taskEnvelope.data!,
        category_filter: "stale_residual",
        total_visible: 1,
        rows: [
          {
            task_id: 23,
            title: "审批演练",
            goal_preview: "审批演练：任务详情卡测试",
            status: "pending",
            status_label: "待处理",
            result_preview: "",
            created_at: generatedAt,
            updated_at: generatedAt,
            latest_event_kind: "approval_rejected",
            latest_event_summary: "主人拒绝审批 #18",
            pending_approval_ids: [],
            next_action: "review_task_goal",
            next_action_code: "review_task_goal",
            work_type: "",
            processing_category: "stale_residual",
            processing_label: "旧任务残留",
            processing_detail: "审批已经拒绝，但旧任务状态没有同步收口；建议取消任务。",
            actionability: {
              can_cancel: true,
              task_actions_enabled: true,
              blocked_reason: "",
            },
          },
        ],
      },
    });

    render(
      <MemoryRouter
        initialEntries={[
          "/owner-console/tasks?status=pending&category=stale_residual",
        ]}
      >
        <TasksPage />
      </MemoryRouter>,
    );

    const processLink = await screen.findByRole("link", {
      name: "处理收口 #23",
    });
    expect(processLink.getAttribute("href")).toBe("/owner-console/tasks/23");
    expect(processLink.className).toContain("task-process-link--danger");
    const taskTable = screen.getByRole("table", { name: "任务列表" });
    expect(
      within(taskTable).getByText("旧任务残留").closest(".status-badge")?.className,
    ).toContain("status-badge--danger");
    expect(
      screen.getByRole("link", { name: "进入任务 #23 详情" }).getAttribute("href"),
    ).toBe("/owner-console/tasks/23");
    expect(screen.getByText(/点击每行左侧的任务编号/)).toBeTruthy();
  });

  it("opens the task list directly in the pending filter and keeps the URL as filter state", async () => {
    render(
      <MemoryRouter initialEntries={["/owner-console/tasks?status=pending"]}>
        <TasksPage />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(getTasks).toHaveBeenCalledWith(
        expect.objectContaining({ status: "pending" }),
        expect.anything(),
      ),
    );
    expect(screen.getByRole("button", { name: "待处理" }).className).toContain(
      "is-active",
    );

    fireEvent.click(screen.getByRole("button", { name: "全部" }));
    await waitFor(() =>
      expect(getTasks).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: null }),
        expect.anything(),
      ),
    );
  });

  it("loads a URL-selected page and navigates through server pagination", async () => {
    getTasks.mockImplementation(async (params: { page: number; page_size: number }) => ({
      ...taskEnvelope,
      data: {
        ...taskEnvelope.data!,
        page: params.page,
        page_size: params.page_size,
        total_matching: 25,
        total_pages: 3,
        has_previous: params.page > 1,
        has_next: params.page < 3,
        total_visible: params.page === 3 ? 5 : 10,
      },
    }));

    render(
      <MemoryRouter
        initialEntries={["/owner-console/tasks?status=pending&page=2&page_size=10"]}
      >
        <TasksPage />
        <LocationProbe />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(getTasks).toHaveBeenCalledWith(
        expect.objectContaining({
          status: "pending",
          page: 2,
          page_size: 10,
        }),
        expect.anything(),
      ),
    );
    expect(screen.getByText("第 2 / 3 页，共 25 个任务")).toBeTruthy();
    expect(screen.getByRole("button", { name: "第 2 页" }).getAttribute("aria-current")).toBe(
      "page",
    );

    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    await waitFor(() =>
      expect(getTasks).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 3, page_size: 10 }),
        expect.anything(),
      ),
    );
    expect(screen.getByLabelText("current search").textContent).toContain("page=3");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "第 3 页" }).getAttribute("aria-current")).toBe(
        "page",
      ),
    );

    fireEvent.click(screen.getByRole("button", { name: "上一页" }));
    await waitFor(() =>
      expect(getTasks).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 2, page_size: 10 }),
        expect.anything(),
      ),
    );
    expect(screen.getByLabelText("current search").textContent).toContain("page=2");
  });

  it("returns to the first page when a filter or page size changes", async () => {
    getTasks.mockImplementation(async (params: { page: number; page_size: number }) => ({
      ...taskEnvelope,
      data: {
        ...taskEnvelope.data!,
        page: params.page,
        page_size: params.page_size,
        total_matching: 45,
        total_pages: Math.max(1, Math.ceil(45 / params.page_size)),
        has_previous: params.page > 1,
        has_next: params.page < Math.ceil(45 / params.page_size),
      },
    }));

    render(
      <MemoryRouter initialEntries={["/owner-console/tasks?page=3"]}>
        <TasksPage />
        <LocationProbe />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(getTasks).toHaveBeenCalledWith(
        expect.objectContaining({ page: 3, page_size: 20 }),
        expect.anything(),
      ),
    );
    expect(screen.getByLabelText("current search").textContent).toContain("page=3");

    fireEvent.click(screen.getByRole("button", { name: "待处理" }));
    await waitFor(() =>
      expect(getTasks).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: "pending", page: 1 }),
        expect.anything(),
      ),
    );
    expect(screen.getByLabelText("current search").textContent).not.toContain("page=3");

    fireEvent.change(screen.getByRole("combobox", { name: "每页任务数" }), {
      target: { value: "50" },
    });
    await waitFor(() =>
      expect(getTasks).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: "pending", page: 1, page_size: 50 }),
        expect.anything(),
      ),
    );
    expect(screen.getByLabelText("current search").textContent).toContain("page_size=50");
    expect(screen.getByLabelText("current search").textContent).not.toMatch(/[?&]page=/);
  });

  it("opens the approval list directly in the pending filter", async () => {
    render(
      <MemoryRouter initialEntries={["/owner-console/approvals?status=pending"]}>
        <ApprovalsPage />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(getApprovals).toHaveBeenCalledWith(
        expect.objectContaining({ status: "pending" }),
        expect.anything(),
      ),
    );
    expect(screen.getByRole("button", { name: "待审批" }).className).toContain(
      "is-active",
    );

    fireEvent.click(screen.getByRole("button", { name: "全部" }));
    await waitFor(() =>
      expect(getApprovals).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: null }),
        expect.anything(),
      ),
    );
  });
});
