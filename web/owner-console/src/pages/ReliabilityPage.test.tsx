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
  operation: "lifecycle",
  category: "data",
  category_label: "数据问题",
  code: "suspected_abnormal_exit",
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
          operation: "plan_action",
          category: "model",
          category_label: "模型问题",
          code: "invalid_model_response",
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
      { component: "bot_runtime", operation: "lifecycle" },
      { component: "main_llm", operation: "plan_action" },
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
    expect(within(screen.getByRole("table")).getByText("证据不足")).toBeTruthy();
    expect(within(screen.getByRole("table")).getByText("—")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "最近 7 天" }));
    await waitFor(() => {
      expect(screen.getByLabelText("可靠性摘要").textContent).toContain("3");
    });

    fireEvent.change(screen.getByLabelText("组件"), {
      target: { value: "main_llm" },
    });
    const table = screen.getByRole("table", { name: "结构化故障组" });
    expect(within(table).getByText("main_llm")).toBeTruthy();
    expect(within(table).getByText("invalid_model_response")).toBeTruthy();
    expect(within(table).queryByText("suspected_abnormal_exit")).toBeNull();
  });
});
