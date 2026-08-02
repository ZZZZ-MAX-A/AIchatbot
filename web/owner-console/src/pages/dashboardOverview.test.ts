import { describe, expect, it } from "vitest";

import { buildDashboardOverview } from "./dashboardOverview";

type DashboardInput = Parameters<typeof buildDashboardOverview>[0];

const nowMs = Date.parse("2026-08-01T08:00:00.000Z");
const freshAt = "2026-08-01T07:59:30.000Z";

function snapshotSection(ok = true) {
  return {
    title: "快照",
    ok,
    summary_text: "",
    display_lines: [],
    error: ok ? "" : "unavailable",
  };
}

function createInput(): DashboardInput {
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
  return {
    overview: {
      generated_at: freshAt,
      task_limit: 5,
      approval_limit: 5,
      counters: {
        pending_tasks: 0,
        failed_tasks: 0,
        pending_approvals: 0,
        recent_tasks_visible: 0,
        pending_approvals_visible: 0,
        awaiting_approval_tasks: 0,
        ordinary_pending_tasks: 0,
        stale_pending_tasks: 0,
      },
      recent_tasks: [],
      pending_approvals: [],
      boundary,
    },
    webWriteState: "closed",
    diagnostics: {
      generated_at: freshAt,
      bot_status: snapshotSection(),
      diagnostics: snapshotSection(),
      config: snapshotSection(),
      vision: snapshotSection(),
      image_cache: snapshotSection(),
      memory: snapshotSection(),
      tts: snapshotSection(),
      recent_errors: snapshotSection(),
      observations: { main_agent: [], root_graph: [] },
      boundary,
    },
    externalRead: {
      generated_at: freshAt,
      enabled: true,
      executor_configured: true,
    } as DashboardInput["externalRead"],
    reliability: {
      generated_at: freshAt,
      recent: emptyWindow,
      weekly: { ...emptyWindow, window_hours: 168 },
      coverage: [],
      scope_note: "",
      evidence_note: "",
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
    unavailableSources: [],
    nowMs,
  };
}

describe("buildDashboardOverview", () => {
  it("reports a stable current scope only when every source is fresh and no action is pending", () => {
    const result = buildDashboardOverview(createInput());

    expect(result.overall.tone).toBe("success");
    expect(result.availableSourceCount).toBe(4);
    expect(result.staleSourceCount).toBe(0);
    expect(result.actionableCount).toBe(0);
  });

  it("prioritizes a security-boundary violation over lower-level evidence", () => {
    const input = createInput();
    input.overview!.boundary.shell_tools_exposed = true;
    input.overview!.counters.pending_tasks = 1;

    const result = buildDashboardOverview(input);

    expect(result.overall.tone).toBe("danger");
    expect(result.security.violationLabels).toHaveLength(1);
    expect(result.attentionItems[0].id).toBe("security:boundary");
  });

  it("treats insufficient recovery evidence as neutral instead of healthy", () => {
    const input = createInput();
    input.reliability!.recent.state_counts.insufficient_evidence = 1;
    input.reliability!.recent.failure_group_count = 1;

    const result = buildDashboardOverview(input);

    expect(result.overall.tone).toBe("neutral");
    expect(result.actionableCount).toBe(0);
    expect(result.attentionItems.some((item) => item.id === "reliability:insufficient")).toBe(true);
  });

  it("marks snapshots older than the threshold as stale evidence", () => {
    const input = createInput();
    input.overview!.generated_at = "2026-08-01T07:55:00.000Z";

    const result = buildDashboardOverview(input);

    expect(result.overall.tone).toBe("neutral");
    expect(result.staleSourceCount).toBe(1);
    expect(result.sources.find((source) => source.key === "overview")?.stale).toBe(true);
  });

  it("counts pending tasks and approvals as actionable without calling them failures", () => {
    const input = createInput();
    input.overview!.counters.pending_tasks = 2;
    input.overview!.counters.ordinary_pending_tasks = 2;
    input.overview!.counters.pending_approvals = 3;

    const result = buildDashboardOverview(input);

    expect(result.overall.tone).toBe("warning");
    expect(result.actionableCount).toBe(2);
    expect(result.attentionItems.map((item) => item.id)).toEqual(
      expect.arrayContaining(["work:tasks-ordinary-pending", "work:approvals"]),
    );
    expect(
      result.attentionItems.find((item) => item.id === "work:tasks-ordinary-pending")?.route,
    ).toBe("/owner-console/tasks?status=pending&category=ordinary_pending");
    expect(
      result.attentionItems.find((item) => item.id === "work:approvals")?.route,
    ).toBe("/owner-console/approvals?status=pending");
  });

  it("separates external-read configuration readiness from a live outage", () => {
    const input = createInput();
    input.externalRead!.executor_configured = false;

    const result = buildDashboardOverview(input);

    expect(result.overall.tone).toBe("warning");
    expect(result.attentionItems.find((item) => item.id === "external-read:not-ready")?.detail).toContain(
      "不会执行 Tavily 实时探测",
    );
  });

  it("describes an unreadable diagnostic section without asserting an upstream outage", () => {
    const input = createInput();
    input.diagnostics!.vision.ok = false;

    const result = buildDashboardOverview(input);
    const item = result.attentionItems.find((candidate) => candidate.id === "diagnostics:unreadable");

    expect(result.overall.tone).toBe("warning");
    expect(item?.detail).toContain("不直接等价于外部服务故障");
    expect(item?.detail).toContain("图片识别");
  });

  it("accepts approval-only web writes but flags an unsafe write contract", () => {
    const approvedInput = createInput();
    approvedInput.webWriteState = "approval_only";
    expect(buildDashboardOverview(approvedInput).security.violationLabels).toEqual(
      [],
    );

    const unsafeInput = createInput();
    unsafeInput.webWriteState = "unsafe";
    expect(buildDashboardOverview(unsafeInput).security.violationLabels).toEqual([
      "网页写入超出审批安全合同",
    ]);
  });
});
