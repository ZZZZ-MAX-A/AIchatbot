import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OwnerConsoleExternalReadEnvelope } from "../api/ownerConsoleTypes";
import { ExternalReadPage } from "./ExternalReadPage";

const { getExternalRead } = vi.hoisted(() => ({
  getExternalRead: vi.fn(),
}));

vi.mock("../api/ownerConsoleApi", () => ({
  ownerConsoleApi: { getExternalRead },
}));

const envelope: OwnerConsoleExternalReadEnvelope = {
  schema_version: "owner_console.http.v1",
  read_model_schema_version: "owner_console.read_model.v0",
  transport: "http",
  api_prefix: "/api/v1/owner-console",
  resource: "external-read",
  generated_at: "2026-07-28T08:00:00+00:00",
  read_only: true,
  http_api_enabled: true,
  web_write_enabled: false,
  error: null,
  data: {
    generated_at: "2026-07-28T08:00:00+00:00",
    enabled: true,
    credential_configured: true,
    executor_configured: true,
    synthesis_configured: true,
    provider_name: "tavily",
    search_depth: "planned_basic_or_advanced",
    max_results: 10,
    timeout_seconds: 10,
    endpoint_host: "api.tavily.com",
    dependencies: {
      httpx_version: "0.28.1",
      httpcore_version: "1.0.9",
      compatible: true,
    },
    recent_task: {
      available: true,
      task_id: 58,
      task_status: "done",
      provider_name: "tavily",
      result_count: 0,
      source_host_count: 0,
      dropped_result_count: 5,
      provider_candidate_count: 5,
      official_content_strong_count: 0,
      failed_search_stage: "",
      search_stage_count: 2,
      official_stage_candidate_count: 2,
      official_stage_result_count: 0,
      media_stage_candidate_count: 3,
      media_stage_result_count: 0,
      planning_mode: "main_agent",
      scene: "current_status",
      primary_source_scope: "official",
      secondary_source_scope: "general",
      secondary_mode: "always",
      dropped_missing_date_count: 2,
      dropped_outside_window_count: 1,
      dropped_weak_only_count: 1,
      dropped_conflicting_date_count: 1,
      dropped_injection_count: 0,
      dropped_sanitization_count: 0,
      dropped_source_policy_count: 0,
      external_request_count: 2,
      provider_request_count: 2,
      synthesis_request_count: 0,
      synthesis_status: "not_run_no_evidence",
      synthesis_error_category: "none",
      owner_quality_status: "not_applicable",
      status_category: "no_results",
      error_category: "none",
      updated_at: "2026-07-28T08:00:00+00:00",
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
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ExternalReadPage", () => {
  it("renders only safe integer drop-reason diagnostics", async () => {
    getExternalRead.mockResolvedValue(envelope);
    render(<ExternalReadPage />);

    const panel = (await screen.findByText("最近正式任务")).closest("article");
    expect(panel).not.toBeNull();
    const scoped = within(panel!);
    const expected = [
      ["Provider 候选数", "5"],
      ["官方正文强日期数", "0"],
      ["失败检索阶段", "无"],
      ["检索阶段数", "2"],
      ["规划模式", "main_agent"],
      ["业务场景", "current_status"],
      ["第一阶段来源", "official"],
      ["第二阶段来源", "general"],
      ["第二阶段条件", "always"],
      ["第一阶段候选数", "2"],
      ["第一阶段合格数", "0"],
      ["第二阶段候选数", "3"],
      ["第二阶段合格数", "0"],
      ["日期缺失丢弃", "2"],
      ["窗口外丢弃", "1"],
      ["仅弱日期丢弃", "1"],
      ["日期冲突丢弃", "1"],
      ["注入嫌疑丢弃", "0"],
      ["来源策略丢弃", "0"],
      ["清洗/去重/预算丢弃", "0"],
    ];
    for (const [label, value] of expected) {
      const term = scoped.getByText(label);
      expect(term.nextElementSibling?.textContent).toBe(value);
    }
  });

  it("shows unknown for tasks created before reason counters existed", async () => {
    const data = envelope.data!;
    getExternalRead.mockResolvedValue({
      ...envelope,
      data: {
        ...data,
        recent_task: {
          ...data.recent_task,
          provider_candidate_count: null,
          official_content_strong_count: null,
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
        },
      },
    });
    render(<ExternalReadPage />);

    const panel = (await screen.findByText("最近正式任务")).closest("article");
    expect(panel).not.toBeNull();
    const scoped = within(panel!);
    expect(scoped.getByText("Provider 候选数").nextElementSibling?.textContent).toBe(
      "未知",
    );
    expect(scoped.getAllByText("未知").length).toBeGreaterThanOrEqual(14);
  });
});
