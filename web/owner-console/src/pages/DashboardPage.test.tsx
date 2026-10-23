import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  OwnerConsoleDiagnosticsEnvelope,
  OwnerConsoleExternalReadEnvelope,
  OwnerConsoleOverviewEnvelope,
  OwnerConsoleReliabilityEnvelope,
  OwnerConsoleTextSnapshotSection,
} from "../api/ownerConsoleTypes";
import { AutoRefreshProvider } from "../app/AutoRefreshContext";
import { DashboardPage } from "./DashboardPage";

const { getDiagnostics, getExternalRead, getOverview, getReliability } = vi.hoisted(
  () => ({
    getDiagnostics: vi.fn(),
    getExternalRead: vi.fn(),
    getOverview: vi.fn(),
    getReliability: vi.fn(),
  }),
);

vi.mock("../api/ownerConsoleApi", () => {
  class OwnerConsoleApiError extends Error {
    status = 500;
    code = "internal_error";
  }
  return {
    OwnerConsoleApiError,
    ownerConsoleApi: {
      getDiagnostics,
      getExternalRead,
      getOverview,
      getReliability,
    },
  };
});

const generatedAt = new Date().toISOString();
const safeBoundary = {
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

function section(title: string, ok = true): OwnerConsoleTextSnapshotSection {
  return {
    title,
    ok,
    summary_text: ok ? "快照读取完成" : "快照读取失败",
    display_lines: [],
    error: ok ? "" : "snapshot_unavailable",
  };
}

const overviewEnvelope: OwnerConsoleOverviewEnvelope = {
  schema_version: "owner_console.http.v1",
  read_model_schema_version: "owner_console.read_model.v0",
  transport: "http",
  api_prefix: "/api/v1/owner-console",
  resource: "overview",
  generated_at: generatedAt,
  read_only: true,
  http_api_enabled: true,
  web_write_enabled: false,
  error: null,
  data: {
    generated_at: generatedAt,
    task_limit: 5,
    approval_limit: 5,
    counters: {
      pending_tasks: 0,
      failed_tasks: 19,
      pending_approvals: 0,
      recent_tasks_visible: 1,
      pending_approvals_visible: 0,
      awaiting_approval_tasks: 0,
      ordinary_pending_tasks: 0,
      stale_pending_tasks: 0,
    },
    recent_tasks: [
      {
        task_id: 41,
        title: "检查索引",
        goal_preview: "检查索引状态",
        status: "done",
        status_label: "已完成",
        result_preview: "检查完成",
        created_at: generatedAt,
        updated_at: generatedAt,
        latest_event_kind: "completed",
        latest_event_summary: "任务已完成",
        pending_approval_ids: [],
        next_action: "无需操作",
        next_action_code: "completed",
        work_type: "diagnostic",
        processing_category: "closed",
        processing_label: "已收口",
        processing_detail: "任务已经完成，仅供复盘。",
        actionability: {
          can_cancel: false,
          task_actions_enabled: true,
          blocked_reason: "only a pending task can be cancelled",
        },
      },
    ],
    pending_approvals: [],
    boundary: safeBoundary,
  },
};

const diagnosticsEnvelope: OwnerConsoleDiagnosticsEnvelope = {
  ...overviewEnvelope,
  resource: "diagnostics",
  data: {
    generated_at: generatedAt,
    bot_status: section("Bot 状态"),
    diagnostics: section("运行诊断"),
    config: section("配置"),
    vision: section("图片识别"),
    image_cache: section("图片缓存"),
    memory: section("记忆"),
    tts: section("语音"),
    recent_errors: section("最近错误"),
    observations: { main_agent: [], root_graph: [] },
    boundary: safeBoundary,
  },
};

const externalReadEnvelope = {
  ...overviewEnvelope,
  resource: "external-read",
  data: {
    generated_at: generatedAt,
    enabled: true,
    credential_configured: true,
    executor_configured: true,
    synthesis_configured: true,
    provider_name: "tavily",
    search_depth: "basic",
    max_results: 5,
    timeout_seconds: 10,
    endpoint_host: "api.tavily.com",
    dependencies: {
      httpx_version: "0.28.1",
      httpcore_version: "1.0.9",
      compatible: true,
    },
    recent_task: {
      available: false,
      task_id: null,
      task_status: "",
      provider_name: "",
      result_count: null,
      source_host_count: null,
      dropped_result_count: null,
      provider_candidate_count: null,
      official_content_strong_count: null,
      failed_search_stage: "",
      search_stage_count: null,
      official_stage_candidate_count: null,
      official_stage_result_count: null,
      media_stage_candidate_count: null,
      media_stage_result_count: null,
      planning_mode: "",
      scene: "",
      primary_source_scope: "",
      secondary_source_scope: "",
      secondary_mode: "",
      dropped_missing_date_count: null,
      dropped_outside_window_count: null,
      dropped_weak_only_count: null,
      dropped_conflicting_date_count: null,
      dropped_injection_count: null,
      dropped_sanitization_count: null,
      dropped_source_policy_count: null,
      external_request_count: null,
      provider_request_count: null,
      synthesis_request_count: null,
      synthesis_status: "",
      synthesis_error_category: "",
      owner_quality_status: "",
      status_category: "",
      error_category: "",
      updated_at: "",
    },
    boundary: {
      owner_private_strict_command_only: true,
      main_llm_can_trigger: true,
      ordinary_chat_can_trigger: false,
      arbitrary_url_fetch_allowed: false,
      ai_answer_enabled: false,
      raw_content_enabled: false,
      isolated_synthesis_enabled: true,
      images_enabled: false,
      retry_enabled: false,
      fallback_enabled: false,
      live_probe_executed: false,
      external_request_executed: false,
      query_exposed: false,
      result_content_exposed: false,
      source_url_exposed: false,
      credential_value_exposed: false,
    },
  },
} satisfies OwnerConsoleExternalReadEnvelope;

const emptyWindow = {
  window_hours: 24,
  failure_occurrence_count: 0,
  failure_group_count: 0,
  state_counts: {
    unresolved: 0,
    recovered: 0,
    recurring: 0,
    insufficient_evidence: 0,
  },
  items: [],
};

const reliabilityEnvelope: OwnerConsoleReliabilityEnvelope = {
  ...overviewEnvelope,
  resource: "reliability",
  data: {
    generated_at: generatedAt,
    recent: emptyWindow,
    weekly: { ...emptyWindow, window_hours: 168 },
    coverage: [],
    scope_note: "只读取固定结构化事件",
    evidence_note: "没有事件不证明持续在线",
    boundary: {
      sqlite_mode_ro: true,
      ensure_database_called: false,
      chat_content_read: false,
      raw_exception_read: false,
      user_identifier_read: false,
      runtime_identifier_exposed: false,
      database_identifier_exposed: false,
      llm_called: false,
      rag_called: false,
      alert_executed: false,
      repair_executed: false,
      retry_executed: false,
      restart_executed: false,
      cleanup_executed: false,
      write_side_effect_allowed: false,
    },
  },
};

function arrangeSuccessfulLoad() {
  getOverview.mockResolvedValue(overviewEnvelope);
  getDiagnostics.mockResolvedValue(diagnosticsEnvelope);
  getExternalRead.mockResolvedValue(externalReadEnvelope);
  getReliability.mockResolvedValue(reliabilityEnvelope);
}

function renderDashboard() {
  return render(
    <MemoryRouter>
      <AutoRefreshProvider>
        <DashboardPage />
      </AutoRefreshProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  arrangeSuccessfulLoad();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("DashboardPage", () => {
  it("keeps diagnostic evidence on its dedicated page and retains configuration and maintenance links", async () => {
    getDiagnostics.mockResolvedValue({
      ...diagnosticsEnvelope,
      data: {
        ...diagnosticsEnvelope.data!,
        memory: { ...section("记忆"), display_lines: ["message_count=12345"], summary_text: "message_count=12345" },
      },
    });
    renderDashboard();
    const links = await screen.findByLabelText("维护入口");
    expect(within(links).getByRole("link", { name: "账号、人物、模型与音色配置" }).getAttribute("href")).toBe("/owner-console/settings");
    expect(within(links).getByRole("link", { name: "按账号查看人格记忆统计与策略" }).getAttribute("href")).toBe("/owner-console/memory");
    expect(screen.getByRole("link", { name: "执行手动检查" }).getAttribute("href")).toBe("/owner-console/diagnostics");
    expect(screen.queryByText("message_count=12345")).toBeNull();
  });

  it("loads all four read-only sources and keeps a historical failure count out of current status", async () => {
    renderDashboard();

    const overall = await screen.findByLabelText("当前总体判断");
    expect(getOverview).toHaveBeenCalledTimes(1);
    expect(getDiagnostics).toHaveBeenCalledTimes(1);
    expect(getExternalRead).toHaveBeenCalledTimes(1);
    expect(getReliability).toHaveBeenCalledTimes(1);
    expect(within(overall).getByText("当前稳定")).toBeTruthy();
    expect(screen.getByText(/历史失败任务 19 个/)).toBeTruthy();
    expect(screen.queryByText("正常")).toBeNull();
    expect(screen.getByText("检查与维护")).toBeTruthy();
    expect(screen.getByText("配置就绪不等于实时可用。")).toBeTruthy();
  });

  it("provides deterministic links for recent tasks and pending approvals", async () => {
    const approval = {
      approval_id: 73,
      task_id: 42,
      task_title: "生成文档",
      tool_name: "create_document",
      risk_level: "medium",
      reason_preview: "需要写入文件",
      status: "pending",
      status_label: "待审批",
      created_at: generatedAt,
      expires_at: generatedAt,
      decided_at: "",
      actionability: {
        can_approve: true,
        can_reject: true,
        resume_enabled: true,
        blocked_reason: "",
        future_operation_only: false,
      },
    };
    getOverview.mockResolvedValue({
      ...overviewEnvelope,
      data: {
        ...overviewEnvelope.data!,
        counters: {
          ...overviewEnvelope.data!.counters,
          pending_approvals: 1,
          pending_approvals_visible: 1,
        },
        pending_approvals: [approval],
      },
    });

    renderDashboard();

    const taskLink = await screen.findByRole("link", { name: "#41" });
    const approvalLink = screen.getByRole("link", { name: "#73" });
    expect(taskLink.getAttribute("href")).toBe("/owner-console/tasks/41");
    expect(approvalLink.getAttribute("href")).toBe("/owner-console/approvals/73");

    const metrics = screen.getByLabelText("首页关键计数");
    expect(within(metrics).getByText("需要关注").closest("a")?.getAttribute("href")).toBe(
      "#attention-details",
    );
    expect(within(metrics).getByText("待审批").closest("a")?.getAttribute("href")).toBe(
      "/owner-console/approvals?status=pending",
    );
    expect(within(metrics).getByText("普通待处理").closest("a")?.getAttribute("href")).toBe(
      "/owner-console/tasks?status=pending&category=ordinary_pending",
    );
    expect(screen.getByLabelText("异常与待处理明细")).toBeTruthy();
  });

  it("marks unresolved structured reliability evidence as degraded", async () => {
    getReliability.mockResolvedValue({
      ...reliabilityEnvelope,
      data: {
        ...reliabilityEnvelope.data!,
        recent: {
          window_hours: 24,
          failure_occurrence_count: 3,
          failure_group_count: 1,
          state_counts: {
            unresolved: 1,
            recovered: 0,
            recurring: 0,
            insufficient_evidence: 0,
          },
          items: [
            {
              component: "vision",
              component_label: "图片识别",
              operation: "recognize",
              operation_label: "识别图片",
              category: "network",
              category_label: "网络",
              code: "upstream_unavailable",
              code_label: "上游暂不可用",
              occurrence_count: 3,
              first_seen_at: generatedAt,
              last_seen_at: generatedAt,
              last_success_at: "",
              recovery_state: "unresolved",
              recovery_state_label: "尚未恢复",
            },
          ],
        },
      },
    });

    renderDashboard();

    const overall = await screen.findByLabelText("当前总体判断");
    expect(within(overall).getByText("已降级")).toBeTruthy();
    expect(screen.getByText(/可靠性故障组尚未恢复/)).toBeTruthy();
    const reliabilityLinks = screen.getAllByRole("link", { name: /查看故障证据|查看全部/ });
    expect(reliabilityLinks.some((link) => link.getAttribute("href") === "/owner-console/reliability")).toBe(true);
  });

  it("keeps successful snapshots visible when one source becomes unavailable", async () => {
    getDiagnostics.mockRejectedValue(new Error("diagnostics offline"));

    renderDashboard();

    await screen.findByText("部分数据源暂不可用");
    expect(screen.getByText("联网查询证据")).toBeTruthy();
    const freshness = screen.getByLabelText("概况数据新鲜度");
    expect(within(freshness).getByText("诊断快照").closest(".status-badge")?.textContent).toContain(
      "不可用",
    );
    expect(screen.getByLabelText("当前总体判断").textContent).toContain("证据不足");
    expect(screen.queryByText("当前稳定")).toBeNull();
    expect(screen.queryByText("diagnostics offline")).toBeNull();
  });

  it("shows unknown values instead of safe zeros when the overview source is missing", async () => {
    getOverview.mockRejectedValue(new Error("C:\\private\\owner-console.log"));

    renderDashboard();

    await screen.findByText("部分数据源暂不可用");
    expect(screen.getByText("待审批").closest(".metric-tile")?.textContent).toContain("—");
    expect(screen.getByText("普通待处理").closest(".metric-tile")?.textContent).toContain("—");
    expect(screen.getByText("旧任务残留").closest(".metric-tile")?.textContent).toContain("—");
    expect(screen.getByText("安全边界快照").closest(".status-badge")?.textContent).toContain(
      "证据不可用",
    );
    expect(screen.queryByText(/owner-console\.log/)).toBeNull();
  });

  it("does not present a missing reliability snapshot as zero failures", async () => {
    getReliability.mockRejectedValue(new Error("reliability unavailable"));

    renderDashboard();

    await screen.findByText("可靠性证据暂不可用");
    expect(screen.getByText("活跃可靠性故障组").closest(".metric-tile")?.textContent).toContain("—");
    expect(screen.queryByText("可靠性证据不可用")?.textContent).toBe("可靠性证据不可用");
  });

  it("refreshes all four sources again from the manual refresh button", async () => {
    renderDashboard();
    await screen.findByLabelText("当前总体判断");

    fireEvent.click(screen.getByRole("button", { name: "刷新概况" }));

    await waitFor(() => {
      expect(getOverview).toHaveBeenCalledTimes(2);
      expect(getDiagnostics).toHaveBeenCalledTimes(2);
      expect(getExternalRead).toHaveBeenCalledTimes(2);
      expect(getReliability).toHaveBeenCalledTimes(2);
    });
  });
});
