import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  OwnerConsoleDiagnosticsEnvelope,
  OwnerConsoleManualDiagnosticsEnvelope,
  OwnerConsoleMainLlmContractEnvelope,
  OwnerConsoleMemoryRagConsistencyEnvelope,
  OwnerConsoleProjectDocRagProbeEnvelope,
  OwnerConsoleTextSnapshotSection,
} from "../api/ownerConsoleTypes";
import { DiagnosticsPage } from "./DiagnosticsPage";

const { getDiagnostics, getManualDiagnostics, runProjectDocRagProbe, runMemoryRagConsistency, runMainLlmContract } = vi.hoisted(() => ({
  getDiagnostics: vi.fn(),
  getManualDiagnostics: vi.fn(),
  runProjectDocRagProbe: vi.fn(),
  runMemoryRagConsistency: vi.fn(),
  runMainLlmContract: vi.fn(),
}));

vi.mock("../api/ownerConsoleApi", () => {
  class OwnerConsoleApiError extends Error {
    status = 500;
    code = "internal_error";
  }
  return {
    OwnerConsoleApiError,
    ownerConsoleApi: {
      getDiagnostics,
      getManualDiagnostics,
      runProjectDocRagProbe,
      runMemoryRagConsistency,
      runMainLlmContract,
    },
  };
});

function section(
  title: string,
  displayLines: string[],
  overrides: Partial<OwnerConsoleTextSnapshotSection> = {},
): OwnerConsoleTextSnapshotSection {
  return {
    title,
    ok: true,
    summary_text: displayLines.join("\n"),
    display_lines: displayLines,
    error: "",
    ...overrides,
  };
}

const envelope: OwnerConsoleDiagnosticsEnvelope = {
  schema_version: "owner_console.http.v1",
  read_model_schema_version: "owner_console.read_model.v0",
  transport: "http",
  api_prefix: "/api/v1/owner-console",
  resource: "diagnostics",
  generated_at: "2026-07-21T06:28:07+00:00",
  read_only: true,
  http_api_enabled: true,
  web_write_enabled: false,
  error: null,
  data: {
    generated_at: "2026-07-21T06:28:07+00:00",
    bot_status: section("bot_status", [
      "Owner Console HTTP API: ok",
      "transport=http",
      "mode=read_only",
      "web_write_enabled=false",
    ]),
    diagnostics: section("diagnostics", [
      "diagnostics_snapshot=read_only",
      "external_probes_executed=false",
      "qq_adapter_imported=false",
      "diagnostics_module_imported=false",
    ]),
    config: section("config", [
      "bot_owner_configured=true",
      "enable_main_agent=true",
      "main_agent_use_llm=true",
    ]),
    vision: section("vision", [
      "enable_vision=true",
      "vision_model=qwen2.5vl:3b",
      "ollama_probe_executed=false",
      "vision_inference_executed=false",
    ]),
    image_cache: section("image_cache", [
      "image_cache_stats_collected=false",
      "image_cache_ttl_seconds=120",
    ]),
    memory: section("memory", [
      "memory_snapshot=collected",
      "message_count=350",
      "memory_content_exposed=false",
      "retrieval_executed=false",
    ]),
    tts: section("tts", [
      "enable_tts=true",
      "tts_voice_configured=true",
      "tts_probe_executed=false",
    ]),
    recent_errors: section("recent_errors", [
      "recent_error_log_read=false",
      "recent_errors_collected=false",
    ]),
    observations: {
      main_agent: [],
      root_graph: [],
    },
    boundary: {
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
    },
  },
};

const manualEnvelope: OwnerConsoleManualDiagnosticsEnvelope = {
  schema_version: "owner_console.http.v1",
  read_model_schema_version: "owner_console.read_model.v0",
  transport: "http",
  api_prefix: "/api/v1/owner-console",
  resource: "manual-diagnostics",
  generated_at: "2026-07-21T07:00:00+00:00",
  read_only: true,
  http_api_enabled: true,
  web_write_enabled: false,
  error: null,
  data: {
    generated_at: "2026-07-21T07:00:00+00:00",
    manual_diagnostic_actions_enabled: false,
    project_doc_rag_probe_enabled: false,
    memory_rag_consistency_enabled: false,
    main_llm_contract_enabled: false,
    automatic_diagnostics_enabled: false,
    configuration_write_enabled: false,
    business_data_write_enabled: false,
    supported_workflows: [],
    latest_run: null,
    project_doc_rag_latest_run: null,
    memory_rag_consistency_latest_run: null,
    main_llm_contract_latest_run: null,
  },
};

const successfulRun = {
  run_id: 1,
  workflow: "project_doc_rag_fixed_retrieval",
  status: "completed",
  outcome: "succeeded",
  stage: "result_validation",
  code: "project_doc_rag_probe_succeeded",
  code_label: "固定项目文档真实检索通过",
  started_at: "2026-07-21T07:01:00+00:00",
  finished_at: "2026-07-21T07:01:01+00:00",
  attempt_count: 1,
  document_count: 1601,
  embedding_count: 1601,
  result_count: 5,
  expected_document_matched: true,
  top_score: 0.91,
  elapsed_ms: 900,
  runtime_feature_enabled: false,
  owner_triggered: true,
  query_text_exposed: false,
  result_content_exposed: false,
  index_rebuild_executed: false,
  database_write_allowed: false,
  llm_called: false,
  dev_context_called: false,
  automatic_retry: false,
};

const actionEnvelope: OwnerConsoleProjectDocRagProbeEnvelope = {
  ...manualEnvelope,
  resource: "manual-diagnostics/project-doc-rag",
  generated_at: successfulRun.finished_at,
  read_only: false,
  manual_runtime_action: true,
  configuration_write_enabled: false,
  business_data_write_enabled: false,
  data: successfulRun,
};

const memoryAttentionRun = {
  run_id: 1,
  workflow: "memory_rag_index_consistency",
  status: "completed",
  outcome: "attention",
  stage: "result_validation",
  code: "memory_rag_active_embedding_gap",
  code_label: "2 个活动记忆文档缺少当前有效向量",
  started_at: "2026-07-21T08:01:00+00:00",
  finished_at: "2026-07-21T08:01:00+00:00",
  attempt_count: 1,
  manual_fact_documents: 10,
  manual_preference_documents: 3,
  session_summary_documents: 24,
  active_document_count: 37,
  valid_embedding_count: 35,
  missing_embedding_count: 2,
  missing_manual_fact_embeddings: 2,
  missing_manual_preference_embeddings: 0,
  missing_session_summary_embeddings: 0,
  active_documents_missing_source: 0,
  source_records_missing_document: 0,
  inactive_document_embedding_count: 5,
  runtime_feature_enabled: false,
  elapsed_ms: 4,
  owner_triggered: true,
  memory_content_read: false,
  private_memory_query_executed: false,
  embedding_called: false,
  index_rebuild_executed: false,
  database_write_allowed: false,
  llm_called: false,
  dev_context_called: false,
  automatic_retry: false,
};

const memoryActionEnvelope: OwnerConsoleMemoryRagConsistencyEnvelope = {
  ...manualEnvelope,
  resource: "manual-diagnostics/memory-rag-consistency",
  generated_at: memoryAttentionRun.finished_at,
  read_only: false,
  manual_runtime_action: true,
  configuration_write_enabled: false,
  business_data_write_enabled: false,
  data: memoryAttentionRun,
};

const mainLlmSuccessfulRun = {
  run_id: 1,
  workflow: "main_llm_fixed_contract",
  status: "completed",
  outcome: "succeeded",
  stage: "result_validation",
  code: "main_llm_contract_succeeded",
  code_label: "Main LLM 固定问题回答与运行合同通过",
  started_at: "2026-07-22T05:01:00+00:00",
  finished_at: "2026-07-22T05:01:01+00:00",
  attempt_count: 1,
  configured_model: "gpt-5.5",
  runtime_feature_enabled: true,
  contract_version: "main_llm.fixed.v1",
  probe_id: "p2_49c",
  contract_valid: true,
  usage_metadata_available: true,
  input_tokens: 51,
  output_tokens: 42,
  total_tokens: 93,
  tool_calls_present: false,
  elapsed_ms: 650,
  owner_triggered: true,
  llm_called: true,
  tool_definitions_sent: false,
  tool_execution_allowed: false,
  client_automatic_retry: false,
  chat_history_read: false,
  chat_history_written: false,
  agent_task_written: false,
  approval_written: false,
  reliability_event_written: false,
  database_write_allowed: false,
  memory_rag_called: false,
  project_doc_rag_called: false,
  dev_context_called: false,
  combined_rag_called: false,
  tavily_called: false,
  tts_called: false,
  vision_called: false,
  qq_write_executed: false,
  prompt_exposed: false,
  response_content_exposed: false,
};

const mainLlmActionEnvelope: OwnerConsoleMainLlmContractEnvelope = {
  ...manualEnvelope,
  resource: "manual-diagnostics/main-llm-contract",
  generated_at: mainLlmSuccessfulRun.finished_at,
  read_only: false,
  manual_runtime_action: true,
  configuration_write_enabled: false,
  business_data_write_enabled: false,
  data: mainLlmSuccessfulRun,
};

beforeEach(() => {
  getManualDiagnostics.mockResolvedValue(manualEnvelope);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("DiagnosticsPage", () => {
  it("separates snapshot readability from service health and keeps raw evidence visible", async () => {
    getDiagnostics.mockResolvedValue(envelope);
    render(<DiagnosticsPage />);

    const reading = await screen.findByLabelText("当前诊断解读");
    expect(reading.textContent).toContain("8 个诊断区块均已读取");
    expect(reading.textContent).toContain("不等同于功能异常");
    expect(screen.getByLabelText("诊断快照状态").textContent).toContain("8/8");

    const diagnosticsCard = document.querySelector('[data-section="diagnostics"]');
    expect(diagnosticsCard).not.toBeNull();
    expect(within(diagnosticsCard as HTMLElement).getByText("只读诊断边界")).toBeTruthy();
    expect(within(diagnosticsCard as HTMLElement).getByText("diagnostics")).toBeTruthy();
    expect(within(diagnosticsCard as HTMLElement).getByText("外部探测")).toBeTruthy();
    expect(
      within(diagnosticsCard as HTMLElement).getByText("未执行（符合只读边界）"),
    ).toBeTruthy();
    expect(
      within(diagnosticsCard as HTMLElement).getByText(
        "external_probes_executed=false",
      ),
    ).toBeTruthy();
  });

  it("prioritizes a failed snapshot section without hiding its English error", async () => {
    const visionError = "vision_snapshot_failed: connection refused";
    getDiagnostics.mockResolvedValue({
      ...envelope,
      data: {
        ...envelope.data!,
        vision: section("vision", [], {
          ok: false,
          summary_text: "",
          error: visionError,
        }),
      },
    });

    render(<DiagnosticsPage />);

    const reading = await screen.findByLabelText("当前诊断解读");
    expect(reading.textContent).toContain("1 个读取异常：视觉配置");
    const visionCard = document.querySelector('[data-section="vision"]');
    expect(visionCard).not.toBeNull();
    expect(visionCard?.className).toContain("diagnostic-card--attention");
    expect(within(visionCard as HTMLElement).getByText("原始错误")).toBeTruthy();
    expect(within(visionCard as HTMLElement).getByText(visionError)).toBeTruthy();
  });

  it("keeps empty observations concise and exposes no write controls", async () => {
    getDiagnostics.mockResolvedValue(envelope);
    render(<DiagnosticsPage />);

    await screen.findByLabelText("当前诊断解读");
    expect(
      screen.getAllByText("本次快照无结构化观测记录"),
    ).toHaveLength(2);
    expect(screen.getAllByRole("button").map((button) => button.textContent)).toEqual([
      "刷新诊断",
    ]);
  });

  it("requires explicit confirmation for the one registered ProjectDocRAG action", async () => {
    getDiagnostics.mockResolvedValue(envelope);
    getManualDiagnostics.mockResolvedValue({
      ...manualEnvelope,
      data: {
        ...manualEnvelope.data!,
        manual_diagnostic_actions_enabled: true,
        project_doc_rag_probe_enabled: true,
        supported_workflows: ["project_doc_rag_fixed_retrieval"],
        project_doc_rag_latest_run: null,
      },
    });
    runProjectDocRagProbe.mockResolvedValue(actionEnvelope);

    render(<DiagnosticsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "手动检查检索" }));
    expect(screen.getByText("确认执行一次固定真实检索？")).toBeTruthy();
    expect(runProjectDocRagProbe).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "确认并执行" }));
    await screen.findByText("固定项目文档真实检索通过");
    expect(runProjectDocRagProbe).toHaveBeenCalledTimes(1);
    expect(screen.getByText("code=project_doc_rag_probe_succeeded")).toBeTruthy();
    expect(screen.getByText("项目文档 1601")).toBeTruthy();
    expect(screen.getByText("生产功能 未启用")).toBeTruthy();
    expect(screen.getByText("runtime_feature_enabled=false")).toBeTruthy();
    expect(screen.queryByText("run_registered_project_doc_rag_probe")).toBeNull();
  });

  it("runs the fixed MemoryRAG consistency check once and keeps private data absent", async () => {
    getDiagnostics.mockResolvedValue(envelope);
    getManualDiagnostics.mockResolvedValue({
      ...manualEnvelope,
      data: {
        ...manualEnvelope.data!,
        manual_diagnostic_actions_enabled: true,
        memory_rag_consistency_enabled: true,
        supported_workflows: ["memory_rag_index_consistency"],
      },
    });
    runMemoryRagConsistency.mockResolvedValue(memoryActionEnvelope);

    render(<DiagnosticsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "手动检查一致性" }));
    expect(screen.getByText("确认执行一次只读一致性核对？")).toBeTruthy();
    expect(runMemoryRagConsistency).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "确认并执行" }));
    await screen.findByText("2 个活动记忆文档缺少当前有效向量");
    expect(runMemoryRagConsistency).toHaveBeenCalledTimes(1);
    expect(screen.getByText("需要关注")).toBeTruthy();
    expect(screen.getByText("活动文档 37")).toBeTruthy();
    expect(screen.getByText("有效向量 35")).toBeTruthy();
    expect(screen.getByText("缺失向量 2")).toBeTruthy();
    expect(screen.getByText("软删除历史向量 5")).toBeTruthy();
    expect(screen.getByText("code=memory_rag_active_embedding_gap")).toBeTruthy();
    expect(screen.getByText("memory_content_read=false")).toBeTruthy();
    expect(screen.getByText("private_memory_query_executed=false")).toBeTruthy();
    expect(screen.getByText("embedding_called=false")).toBeTruthy();
    expect(document.body.textContent).not.toContain("private-fact");
    expect(document.body.textContent).not.toContain("run_registered_memory_rag_consistency");
  });

  it("runs one fixed Main LLM question without exposing prompt or tool selection", async () => {
    getDiagnostics.mockResolvedValue(envelope);
    getManualDiagnostics.mockResolvedValue({
      ...manualEnvelope,
      data: {
        ...manualEnvelope.data!,
        manual_diagnostic_actions_enabled: true,
        main_llm_contract_enabled: true,
        supported_workflows: ["main_llm_fixed_contract"],
      },
    });
    runMainLlmContract.mockResolvedValue(mainLlmActionEnvelope);

    render(<DiagnosticsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "手动检查问答" }));
    expect(screen.getByText("确认执行一次远程固定问答？")).toBeTruthy();
    expect(runMainLlmContract).not.toHaveBeenCalled();
    expect(document.body.textContent).toContain("不评价任意问题应选择什么工具");

    fireEvent.click(screen.getByRole("button", { name: "确认并执行" }));
    await screen.findByText("Main LLM 固定问题回答与运行合同通过");
    expect(runMainLlmContract).toHaveBeenCalledTimes(1);
    expect(screen.getByText("模型 gpt-5.5")).toBeTruthy();
    expect(screen.getByText("响应 650 ms")).toBeTruthy();
    expect(screen.getByText("输入 token 51")).toBeTruthy();
    expect(screen.getByText("输出 token 42")).toBeTruthy();
    expect(screen.getByText("code=main_llm_contract_succeeded")).toBeTruthy();
    expect(screen.getByText("client_automatic_retry=false")).toBeTruthy();
    expect(screen.getByText("tool_definitions_sent=false")).toBeTruthy();
    expect(screen.getByText("database_write_allowed=false")).toBeTruthy();
    expect(document.body.textContent).not.toContain("amber-17");
    expect(document.body.textContent).not.toContain("run_registered_main_llm_contract");
  });
});
