import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OwnerConsoleReliabilityEnvelope } from "../api/ownerConsoleTypes";
import { ReliabilityPage } from "./ReliabilityPage";

const { getReliability } = vi.hoisted(() => ({
  getReliability: vi.fn(),
}));

vi.mock("../api/ownerConsoleApi", () => {
  class OwnerConsoleApiError extends Error {
    status = 500;
    code = "internal_error";
  }
  return {
    OwnerConsoleApiError,
    ownerConsoleApi: { getReliability },
  };
});

const lifecycleItem = {
  component: "bot_runtime",
  component_label: "Bot 运行状态",
  operation: "lifecycle",
  operation_label: "进程启动与停止",
  category: "data",
  category_label: "数据问题",
  code: "suspected_abnormal_exit",
  code_label: "上次运行没有发现正常停止记录",
  occurrence_count: 2,
  first_seen_at: "2026-07-19T10:35:22+00:00",
  last_seen_at: "2026-07-19T12:31:39+00:00",
  last_success_at: "",
  recovery_state: "insufficient_evidence",
  recovery_state_label: "证据不足",
};

const envelope: OwnerConsoleReliabilityEnvelope = {
  schema_version: "owner_console.http.v1",
  read_model_schema_version: "owner_console.read_model.v0",
  transport: "http",
  api_prefix: "/api/v1/owner-console",
  resource: "reliability",
  generated_at: "2026-07-19T12:45:00+00:00",
  read_only: true,
  http_api_enabled: true,
  web_write_enabled: false,
  error: null,
  data: {
    generated_at: "2026-07-19T12:45:00+00:00",
    recent: {
      window_hours: 24,
      failure_occurrence_count: 2,
      failure_group_count: 1,
      state_counts: {
        unresolved: 0,
        recovered: 0,
        recurring: 0,
        insufficient_evidence: 1,
      },
      items: [lifecycleItem],
    },
    weekly: {
      window_hours: 168,
      failure_occurrence_count: 3,
      failure_group_count: 2,
      state_counts: {
        unresolved: 1,
        recovered: 0,
        recurring: 0,
        insufficient_evidence: 1,
      },
      items: [
        lifecycleItem,
        {
          component: "main_llm",
          component_label: "MainAgent 规划模型",
          operation: "plan_action",
          operation_label: "生成行动计划",
          category: "model",
          category_label: "模型问题",
          code: "invalid_model_response",
          code_label: "模型响应未通过格式或质量校验",
          occurrence_count: 1,
          first_seen_at: "2026-07-18T12:00:00+00:00",
          last_seen_at: "2026-07-18T12:00:00+00:00",
          last_success_at: "",
          recovery_state: "unresolved",
          recovery_state_label: "未恢复",
        },
      ],
    },
    coverage: [
      {
        component: "bot_runtime",
        component_label: "Bot 运行状态",
        operation: "lifecycle",
        operation_label: "进程启动与停止",
      },
      {
        component: "main_llm",
        component_label: "MainAgent 规划模型",
        operation: "plan_action",
        operation_label: "生成行动计划",
      },
    ],
    scope_note: "只统计固定结构化事件。",
    evidence_note: "没有结构化故障不等于已证明持续在线。",
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

const reliabilityData = envelope.data!;

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ReliabilityPage", () => {
  it("renders fixed structured trends and filters the seven-day table locally", async () => {
    getReliability.mockResolvedValue(envelope);
    render(<ReliabilityPage />);

    await screen.findByRole("table", { name: "结构化故障组" });
    expect(getReliability).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("可靠性摘要").textContent).toContain("2");
    expect(screen.getByLabelText("当前可靠性解读").textContent).toContain(
      "1 组证据不足",
    );
    expect(within(screen.getByRole("table")).getByText("证据不足")).toBeTruthy();
    expect(
      within(screen.getByRole("table")).getByText("bot_runtime / lifecycle"),
    ).toBeTruthy();
    expect(
      within(screen.getByRole("table")).getByText(
        "data / suspected_abnormal_exit",
      ),
    ).toBeTruthy();
    expect(within(screen.getByRole("table")).getByText("—")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "最近 7 天" }));
    await waitFor(() => {
      expect(screen.getByLabelText("可靠性摘要").textContent).toContain("3");
    });

    expect(
      within(screen.getByLabelText("功能")).getByRole("option", {
        name: "MainAgent 规划模型（main_llm）",
      }),
    ).toBeTruthy();

    fireEvent.change(screen.getByLabelText("功能"), {
      target: { value: "main_llm" },
    });
    const table = screen.getByRole("table", { name: "结构化故障组" });
    expect(within(table).getByText("MainAgent 规划模型 · 生成行动计划")).toBeTruthy();
    expect(within(table).getByText("main_llm / plan_action")).toBeTruthy();
    expect(within(table).getByText("model / invalid_model_response")).toBeTruthy();
    expect(within(table).queryByText("data / suspected_abnormal_exit")).toBeNull();
    expect(screen.getByLabelText("当前可靠性解读").textContent).toContain(
      "当前筛选有 1 组需要关注",
    );
  });

  it("explains recovered evidence without hiding the original English code", async () => {
    const recoveredItem = {
      ...reliabilityData.weekly.items[1],
      last_success_at: "2026-07-18T12:30:00+00:00",
      recovery_state: "recovered",
      recovery_state_label: "已恢复",
    };
    getReliability.mockResolvedValue({
      ...envelope,
      data: {
        ...reliabilityData,
        recent: {
          ...reliabilityData.recent,
          failure_occurrence_count: 1,
          failure_group_count: 1,
          state_counts: {
            unresolved: 0,
            recovered: 1,
            recurring: 0,
            insufficient_evidence: 0,
          },
          items: [recoveredItem],
        },
      },
    });

    render(<ReliabilityPage />);

    await screen.findByRole("table", { name: "结构化故障组" });
    expect(screen.getByLabelText("当前可靠性解读").textContent).toContain(
      "1 组在最后失败之后已有真实成功证据",
    );
    expect(
      within(screen.getByRole("table")).getByText(
        "model / invalid_model_response",
      ),
    ).toBeTruthy();
    expect(within(screen.getByRole("table")).getByText("recovered")).toBeTruthy();
  });

  it("keeps the empty-window conclusion evidence limited", async () => {
    getReliability.mockResolvedValue({
      ...envelope,
      data: {
        ...reliabilityData,
        recent: {
          ...reliabilityData.recent,
          failure_occurrence_count: 0,
          failure_group_count: 0,
          state_counts: {
            unresolved: 0,
            recovered: 0,
            recurring: 0,
            insufficient_evidence: 0,
          },
          items: [],
        },
      },
    });

    render(<ReliabilityPage />);

    await screen.findByText("当前窗口没有结构化故障");
    expect(screen.getByLabelText("当前可靠性解读").textContent).toContain(
      "这不等于系统持续在线",
    );
  });
});
