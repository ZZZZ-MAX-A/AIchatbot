import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  OwnerConsoleDiagnosticsEnvelope,
  OwnerConsoleManualDiagnosticsEnvelope,
  OwnerConsoleMainLlmContractEnvelope,
  OwnerConsoleMemoryRagConsistencyEnvelope,
  OwnerConsoleProjectDocRagProbeEnvelope,
  OwnerConsoleTextSnapshotSection,
  OwnerConsoleTtsSynthesisEnvelope,
  OwnerConsoleVisionInferenceEnvelope,
  OwnerConsoleCloudVisionEnvelope,
} from "../api/ownerConsoleTypes";
import { DiagnosticsPage } from "./DiagnosticsPage";

const { getDiagnostics, getManualDiagnostics, runProjectDocRagProbe, runMemoryRagConsistency, runMainLlmContract, runTtsSynthesis, getTtsAudioPreview, acceptTtsAudioQuality, rejectTtsAudioQuality, runCloudVisionFixedDescription, getCloudVisionReferencePreview, acceptCloudVisionResponseQuality, rejectCloudVisionResponseQuality } = vi.hoisted(() => ({
  getDiagnostics: vi.fn(),
  getManualDiagnostics: vi.fn(),
  runProjectDocRagProbe: vi.fn(),
  runMemoryRagConsistency: vi.fn(),
  runMainLlmContract: vi.fn(),
  runTtsSynthesis: vi.fn(),
  getTtsAudioPreview: vi.fn(),
  acceptTtsAudioQuality: vi.fn(),
  rejectTtsAudioQuality: vi.fn(),
  runCloudVisionFixedDescription: vi.fn(),
  getCloudVisionReferencePreview: vi.fn(),
  acceptCloudVisionResponseQuality: vi.fn(),
  rejectCloudVisionResponseQuality: vi.fn(),
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
      runTtsSynthesis,
      getTtsAudioPreview,
      acceptTtsAudioQuality,
      rejectTtsAudioQuality,
      runCloudVisionFixedDescription,
      getCloudVisionReferencePreview,
      acceptCloudVisionResponseQuality,
      rejectCloudVisionResponseQuality,
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
      "vision_provider=aliyun_bailian",
      "vision_model=qwen3.7-flash",
      "vision_region=cn-beijing",
      "workspace_configured=true",
      "credentials_configured=true",
      "thinking_enabled=false",
      "client_automatic_retry=false",
      "automatic_local_fallback=false",
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
    tts_synthesis_enabled: false,
    vision_inference_enabled: false,
    cloud_vision_enabled: false,
    cloud_vision_workspace_configured: false,
    cloud_vision_credentials_configured: false,
    automatic_diagnostics_enabled: false,
    configuration_write_enabled: false,
    business_data_write_enabled: false,
    supported_workflows: [],
    latest_run: null,
    project_doc_rag_latest_run: null,
    memory_rag_consistency_latest_run: null,
    main_llm_contract_latest_run: null,
    tts_synthesis_latest_run: null,
    vision_inference_latest_run: null,
    cloud_vision_latest_run: null,
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

const ttsSuccessfulRun = {
  run_id: 1,
  workflow: "tts_managed_lifecycle",
  status: "completed",
  outcome: "attention",
  stage: "owner_audio_review",
  code: "tts_audio_quality_review_required",
  code_label: "TTS 技术合同通过，等待主人试听确认",
  started_at: "2026-07-24T05:01:00+00:00",
  finished_at: "2026-07-24T05:01:02+00:00",
  attempt_count: 1,
  runtime_feature_enabled: true,
  service_health_checked: true,
  service_healthy: true,
  model_loaded_before: false,
  runtime_imported_before: false,
  model_load_may_have_occurred: true,
  configured_voice_present: true,
  tts_called: true,
  output_contract_valid: true,
  output_file_created: true,
  output_bytes: 32044,
  output_duration_ms: 1000,
  output_retained: false,
  partial_artifact_state: "artifacts_removed",
  health_elapsed_ms: 12,
  synthesis_elapsed_ms: 1988,
  elapsed_ms: 2000,
  fixed_text: "这是一次固定语音合成检查。",
  technical_outcome: "succeeded",
  technical_code: "tts_managed_lifecycle_succeeded",
  audio_preview_available: true,
  audio_quality_review_required: true,
  audio_quality_reviewed: false,
  audio_quality_accepted: null,
  audio_reviewed_at: "",
  owner_triggered: true,
  service_preexisting: true,
  service_start_attempted: false,
  service_started: false,
  service_owned_by_diagnostic: false,
  service_stop_attempted: false,
  service_stopped: false,
  segment_directory_retained: false,
  artifact_cleanup_attempted: true,
  artifact_cleanup_succeeded: true,
  startup_elapsed_ms: 0,
  cleanup_elapsed_ms: 2,
  automatic_retry: false,
  qq_write_executed: false,
  reliability_event_written: false,
  database_write_allowed: false,
  local_file_write_expected: true,
  cleanup_executed: true,
  chat_history_read: false,
  memory_rag_called: false,
  project_doc_rag_called: false,
  dev_context_called: false,
  combined_rag_called: false,
  main_llm_called: false,
  vision_called: false,
  prompt_exposed: false,
  response_content_exposed: false,
  output_path_exposed: false,
  fixed_text_exposed: true,
  audio_preview_persisted: false,
  audio_preview_path_exposed: false,
  audio_review_action_executed: false,
};

const ttsActionEnvelope: OwnerConsoleTtsSynthesisEnvelope = {
  ...manualEnvelope,
  resource: "manual-diagnostics/tts-synthesis",
  generated_at: ttsSuccessfulRun.finished_at,
  read_only: false,
  manual_runtime_action: true,
  configuration_write_enabled: false,
  business_data_write_enabled: false,
  data: ttsSuccessfulRun,
};

const ttsAcceptedRun = {
  ...ttsSuccessfulRun,
  outcome: "succeeded",
  stage: "result_validation",
  code: "tts_managed_lifecycle_succeeded",
  code_label: "TTS 启动、固定合成和清理合同通过",
  audio_preview_available: false,
  audio_quality_review_required: false,
  audio_quality_reviewed: true,
  audio_quality_accepted: true,
  audio_reviewed_at: "2026-07-24T05:02:00+00:00",
  audio_review_action_executed: true,
};

const ttsAcceptedEnvelope: OwnerConsoleTtsSynthesisEnvelope = {
  ...ttsActionEnvelope,
  generated_at: ttsAcceptedRun.audio_reviewed_at,
  data: ttsAcceptedRun,
};

const ttsRejectedRun = {
  ...ttsSuccessfulRun,
  outcome: "failed",
  stage: "owner_audio_review",
  code: "tts_audio_quality_rejected",
  code_label: "TTS 技术合同通过，但主人听检不合格",
  audio_preview_available: false,
  audio_quality_review_required: false,
  audio_quality_reviewed: true,
  audio_quality_accepted: false,
  audio_reviewed_at: "2026-07-24T05:02:00+00:00",
  audio_review_action_executed: true,
};

const ttsRejectedEnvelope: OwnerConsoleTtsSynthesisEnvelope = {
  ...ttsActionEnvelope,
  generated_at: ttsRejectedRun.audio_reviewed_at,
  data: ttsRejectedRun,
};

const visionSuccessfulRun = {
  run_id: 1,
  workflow: "vision_managed_lifecycle",
  status: "completed",
  outcome: "attention",
  stage: "owner_visual_review",
  code: "vision_response_quality_review_required",
  code_label: "视觉技术合同通过，等待主人检查实际图片描述",
  started_at: "2026-07-24T06:01:00+00:00",
  finished_at: "2026-07-24T06:01:02+00:00",
  attempt_count: 1,
  configured_model: "qwen2.5vl:3b",
  runtime_feature_enabled: true,
  fixed_image_contract: "vision.sticker.v1",
  fixed_image_bytes: 162977,
  fixed_image_contract_valid: true,
  reference_sticker_id: "aike_affection_005",
  registered_reference_asset_read: true,
  expected_answer_disclosed_in_prompt: false,
  service_tags_checked: true,
  service_healthy: true,
  service_preexisting: true,
  service_start_attempted: false,
  service_started: false,
  service_owned_by_diagnostic: false,
  service_ownership_basis: "none",
  service_stop_attempted: false,
  service_stopped: false,
  model_available: true,
  model_residency_checked: true,
  model_loaded_before: false,
  keep_alive_zero_used: true,
  vision_called: true,
  response_contract_valid: true,
  response_mode: "natural_text",
  structured_output_requested: false,
  semantic_contract_automatically_validated: false,
  owner_visual_judgment_required: true,
  response_preview: "一名黑白双色头发的Q版人物抱着一个大爱心，周围漂浮着多个粉红色爱心。",
  response_description: "一名黑白双色头发的Q版人物抱着一个大爱心，周围漂浮着多个粉红色爱心。",
  response_content_exposed_to_owner: true,
  usage_metadata_available: true,
  input_tokens: 72,
  output_tokens: 28,
  total_tokens: 100,
  model_cleanup_required: true,
  model_cleanup_verified: true,
  model_cleanup_poll_count: 1,
  startup_elapsed_ms: 0,
  discovery_elapsed_ms: 5,
  residency_elapsed_ms: 3,
  inference_elapsed_ms: 1200,
  cleanup_elapsed_ms: 2,
  elapsed_ms: 1210,
  technical_outcome: "succeeded",
  technical_code: "vision_managed_lifecycle_succeeded",
  reference_preview_available: true,
  visual_quality_review_required: true,
  visual_quality_reviewed: false,
  visual_quality_accepted: null,
  visual_reviewed_at: "",
  visual_review_action_executed: false,
  response_preview_persisted: false,
  response_preview_path_exposed: false,
  reference_image_exposed_to_owner: false,
  owner_triggered: true,
  client_automatic_retry: false,
  tool_definitions_sent: false,
  qq_write_executed: false,
  reliability_event_written: false,
  database_write_allowed: false,
  project_file_write_allowed: false,
  project_artifact_write_expected: false,
  external_runtime_local_write_possible: true,
  model_pull_allowed: false,
  chat_history_read: false,
  memory_rag_called: false,
  project_doc_rag_called: false,
  dev_context_called: false,
  combined_rag_called: false,
  main_llm_called: false,
  tts_called: false,
  image_content_exposed: false,
  response_content_exposed: false,
};

const visionAcceptedRun = {
  ...visionSuccessfulRun,
  outcome: "succeeded",
  stage: "result_validation",
  code: "vision_managed_lifecycle_succeeded",
  code_label: "视觉服务、自然回复和资源收口技术合同通过",
  visual_quality_review_required: false,
  visual_quality_reviewed: true,
  visual_quality_accepted: true,
  visual_reviewed_at: "2026-07-24T06:03:00+00:00",
  visual_review_action_executed: true,
  reference_image_exposed_to_owner: true,
};

const visionActionEnvelope: OwnerConsoleVisionInferenceEnvelope = {
  ...manualEnvelope,
  resource: "manual-diagnostics/vision-inference",
  generated_at: visionSuccessfulRun.finished_at,
  read_only: false,
  manual_runtime_action: true,
  configuration_write_enabled: false,
  business_data_write_enabled: false,
  data: visionSuccessfulRun,
};

const visionAcceptedEnvelope: OwnerConsoleVisionInferenceEnvelope = {
  ...visionActionEnvelope,
  generated_at: visionAcceptedRun.visual_reviewed_at,
  data: visionAcceptedRun,
};

const cloudVisionSuccessfulRun = {
  run_id: 2,
  workflow: "cloud_vision_fixed_description",
  status: "completed",
  outcome: "attention",
  stage: "owner_visual_review",
  code: "cloud_vision_response_quality_review_required",
  code_label: "百炼视觉基础合同通过，等待主人检查图片描述",
  started_at: "2026-07-26T12:00:00+00:00",
  finished_at: "2026-07-26T12:00:02+00:00",
  attempt_count: 1,
  provider: "aliyun_bailian",
  region: "cn-beijing",
  configured_model: "qwen3.7-flash",
  returned_model: "qwen3.7-flash",
  runtime_feature_enabled: true,
  endpoint_contract_valid: true,
  workspace_configured: true,
  credentials_configured: true,
  fixed_image_contract: "vision.sticker.v1",
  fixed_image_bytes: 162977,
  fixed_image_contract_valid: true,
  reference_sticker_id: "aike_affection_005",
  registered_reference_asset_read: true,
  external_image_upload_planned: true,
  external_image_upload_executed: true,
  provider_side_persistence_controlled_by_app: false,
  cloud_vision_called: true,
  request_count: 1,
  client_automatic_retry: false,
  tool_definitions_sent: false,
  thinking_enabled: false,
  response_mode: "natural_text",
  structured_output_requested: false,
  semantic_contract_automatically_validated: false,
  owner_visual_judgment_required: true,
  response_contract_valid: true,
  response_preview: "角色双手捧着红色爱心，表达出浓烈的爱意、兴奋与撒娇感。",
  response_description: "角色双手捧着红色爱心，表达出浓烈的爱意、兴奋与撒娇感。",
  response_cleanup_applied: true,
  input_tokens: 316,
  output_tokens: 98,
  total_tokens: 414,
  request_elapsed_ms: 1578,
  technical_outcome: "succeeded",
  technical_code: "cloud_vision_fixed_description_succeeded",
  reference_preview_available: true,
  visual_quality_review_required: true,
  visual_quality_reviewed: false,
  visual_quality_accepted: null,
  visual_reviewed_at: "",
  visual_review_action_executed: false,
  owner_triggered: true,
  api_key_exposed: false,
  workspace_id_exposed: false,
  image_base64_exposed: false,
  response_preview_persisted: false,
  local_gpu_model_loaded: false,
  database_write_allowed: false,
  project_artifact_write_expected: false,
  reliability_event_written: false,
  qq_write_executed: false,
  chat_history_written: false,
  agent_task_written: false,
  approval_written: false,
  memory_rag_called: false,
  project_doc_rag_called: false,
  dev_context_called: false,
  combined_rag_called: false,
  main_llm_called: false,
  tts_called: false,
  local_vision_called: false,
};

const cloudVisionAcceptedRun = {
  ...cloudVisionSuccessfulRun,
  outcome: "succeeded",
  stage: "result_validation",
  code: "cloud_vision_fixed_description_succeeded",
  code_label: "百炼视觉请求与基础回复合同通过",
  visual_quality_review_required: false,
  visual_quality_reviewed: true,
  visual_quality_accepted: true,
  visual_reviewed_at: "2026-07-26T12:01:00+00:00",
  visual_review_action_executed: true,
};

const cloudVisionActionEnvelope: OwnerConsoleCloudVisionEnvelope = {
  ...manualEnvelope,
  resource: "manual-diagnostics/cloud-vision-fixed-description",
  generated_at: cloudVisionSuccessfulRun.finished_at,
  read_only: false,
  manual_runtime_action: true,
  configuration_write_enabled: false,
  business_data_write_enabled: false,
  data: cloudVisionSuccessfulRun,
};

const cloudVisionAcceptedEnvelope: OwnerConsoleCloudVisionEnvelope = {
  ...cloudVisionActionEnvelope,
  generated_at: cloudVisionAcceptedRun.visual_reviewed_at,
  data: cloudVisionAcceptedRun,
};

beforeEach(() => {
  getManualDiagnostics.mockResolvedValue(manualEnvelope);
  getTtsAudioPreview.mockResolvedValue(
    new Blob([new Uint8Array(64)], { type: "audio/wav" }),
  );
  acceptTtsAudioQuality.mockResolvedValue(ttsAcceptedEnvelope);
  getCloudVisionReferencePreview.mockResolvedValue(
    new Blob([new Uint8Array(162_977)], { type: "image/png" }),
  );
  acceptCloudVisionResponseQuality.mockResolvedValue(cloudVisionAcceptedEnvelope);
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: vi.fn(() => "blob:tts-audio-preview"),
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: vi.fn(),
  });
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
    expect(reading.textContent).toContain("1 个读取异常：云端视觉配置");
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
    expect(screen.getByLabelText("手动诊断配置状态").textContent).toContain(
      "手动诊断当前未开放",
    );
    expect(screen.getByLabelText("手动诊断配置状态").textContent).toContain(
      "功能代码和历史结果没有被删除",
    );
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
    expect(screen.getAllByText("client_automatic_retry=false").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("tool_definitions_sent=false")).toBeTruthy();
    expect(screen.getByText("database_write_allowed=false")).toBeTruthy();
    expect(document.body.textContent).not.toContain("amber-17");
    expect(document.body.textContent).not.toContain("run_registered_main_llm_contract");
  });

  it("runs one fixed TTS synthesis only after confirmation and exposes file boundaries", async () => {
    getDiagnostics.mockResolvedValue(envelope);
    getManualDiagnostics.mockResolvedValue({
      ...manualEnvelope,
      data: {
        ...manualEnvelope.data!,
        manual_diagnostic_actions_enabled: true,
        tts_synthesis_enabled: true,
        supported_workflows: ["tts_managed_lifecycle"],
      },
    });
    runTtsSynthesis.mockResolvedValue(ttsActionEnvelope);

    render(<DiagnosticsPage />);

    fireEvent.click(
      await screen.findByRole("button", { name: "检查启动、合成与清理" }),
    );
    expect(screen.getByText("确认执行一次 TTS 生命周期诊断？")).toBeTruthy();
    expect(runTtsSynthesis).not.toHaveBeenCalled();
    expect(document.body.textContent).toContain("若服务明确离线，诊断会启动一个受管理 TTS 子进程");
    expect(document.body.textContent).toContain("服务原本在线则直接复用且绝不停止");
    expect(document.body.textContent).toContain("只清理本次 artifact ID");
    expect(document.body.textContent).toContain("不会发送 QQ、写业务数据库或可靠性事件");
    expect(document.body.textContent).toContain("不会调用 LLM/RAG 或自动重试");

    fireEvent.click(screen.getByRole("button", { name: "确认并执行" }));
    await screen.findByText("TTS 技术合同通过，等待主人试听确认");
    expect(runTtsSynthesis).toHaveBeenCalledTimes(1);
    expect(screen.getByText("stage=owner_audio_review")).toBeTruthy();
    expect(screen.getByText("code=tts_audio_quality_review_required")).toBeTruthy();
    expect(screen.getByText("technical_outcome=succeeded")).toBeTruthy();
    expect(screen.getByText("technical_code=tts_managed_lifecycle_succeeded")).toBeTruthy();
    expect(screen.getByText("audio_preview_available=true")).toBeTruthy();
    expect(screen.getByText("audio_quality_review_required=true")).toBeTruthy();
    expect(document.body.textContent).toContain("应听到：这是一次固定语音合成检查。");
    expect(screen.getByText("总延迟 2000 ms")).toBeTruthy();
    expect(screen.getByText("启动 0 ms")).toBeTruthy();
    expect(screen.getByText("健康检查 12 ms")).toBeTruthy();
    expect(screen.getByText("合成 1988 ms")).toBeTruthy();
    expect(screen.getByText("清理 2 ms")).toBeTruthy();
    expect(screen.getByText("WAV 32044 bytes")).toBeTruthy();
    expect(screen.getByText("WAV 时长 1000 ms")).toBeTruthy();
    expect(screen.getByText("调用前模型 未加载")).toBeTruthy();
    expect(screen.getByText("调用前 runtime 未导入")).toBeTruthy();
    expect(screen.getByText("服务来源 原本在线")).toBeTruthy();
    expect(screen.getByText("服务收尾 不停止已有服务")).toBeTruthy();
    expect(screen.getByText("最终 WAV 已清理")).toBeTruthy();
    expect(screen.getByText("分段目录 已清理")).toBeTruthy();
    expect(screen.getByText("workflow=tts_managed_lifecycle")).toBeTruthy();
    expect(screen.getByText("tts_called=true")).toBeTruthy();
    expect(screen.getByText("runtime_imported_before=false")).toBeTruthy();
    expect(screen.getByText("service_preexisting=true")).toBeTruthy();
    expect(screen.getByText("service_start_attempted=false")).toBeTruthy();
    expect(screen.getByText("service_started=false")).toBeTruthy();
    expect(screen.getByText("service_owned_by_diagnostic=false")).toBeTruthy();
    expect(screen.getByText("service_stop_attempted=false")).toBeTruthy();
    expect(screen.getByText("service_stopped=false")).toBeTruthy();
    expect(screen.getByText("artifact_cleanup_attempted=true")).toBeTruthy();
    expect(screen.getByText("artifact_cleanup_succeeded=true")).toBeTruthy();
    expect(screen.getByText("output_retained=false")).toBeTruthy();
    expect(screen.getByText("segment_directory_retained=false")).toBeTruthy();
    expect(screen.getByText("automatic_retry=false")).toBeTruthy();
    expect(screen.getByText("qq_write_executed=false")).toBeTruthy();
    expect(screen.getByText("reliability_event_written=false")).toBeTruthy();
    expect(screen.getByText("database_write_allowed=false")).toBeTruthy();
    expect(screen.getByText("local_file_write_expected=true")).toBeTruthy();
    expect(screen.getByText("cleanup_executed=true")).toBeTruthy();
    expect(screen.getByText("partial_artifact_state=artifacts_removed")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "加载临时试听" }));
    const audio = await screen.findByLabelText("TTS 固定语音临时试听");
    expect(getTtsAudioPreview).toHaveBeenCalledWith(1);
    const acceptBeforePlayback = screen.getByRole("button", {
      name: "播放结束后确认合格",
    });
    expect(acceptBeforePlayback.hasAttribute("disabled")).toBe(true);
    fireEvent.ended(audio);
    const acceptButton = screen.getByRole("button", { name: "语音合格" });
    expect(acceptButton.hasAttribute("disabled")).toBe(false);
    fireEvent.click(acceptButton);
    await screen.findByText("TTS 启动、固定合成和清理合同通过");
    expect(acceptTtsAudioQuality).toHaveBeenCalledWith(1);
    expect(runTtsSynthesis).toHaveBeenCalledTimes(1);
    expect(screen.getByText("stage=result_validation")).toBeTruthy();
    expect(screen.getByText("code=tts_managed_lifecycle_succeeded")).toBeTruthy();
    expect(screen.getByText("audio_preview_available=false")).toBeTruthy();
    expect(screen.getByText("audio_quality_review_required=false")).toBeTruthy();
    expect(screen.getByText("audio_quality_reviewed=true")).toBeTruthy();
    expect(screen.getByText("audio_quality_accepted=true")).toBeTruthy();
    expect(screen.getByText("audio_review_action_executed=true")).toBeTruthy();
    expect(document.body.textContent).not.toContain("run_registered_tts_synthesis");
    expect(document.body.textContent).not.toContain("temp_audio/");
  });

  it("marks a technically valid WAV failed when the owner rejects audio quality", async () => {
    getDiagnostics.mockResolvedValue(envelope);
    getManualDiagnostics.mockResolvedValue({
      ...manualEnvelope,
      data: {
        ...manualEnvelope.data!,
        manual_diagnostic_actions_enabled: true,
        tts_synthesis_enabled: true,
        supported_workflows: ["tts_managed_lifecycle"],
        latest_run: ttsSuccessfulRun,
        tts_synthesis_latest_run: ttsSuccessfulRun,
      },
    });
    rejectTtsAudioQuality.mockResolvedValue(ttsRejectedEnvelope);

    render(<DiagnosticsPage />);

    fireEvent.click(
      await screen.findByRole("button", { name: "加载临时试听" }),
    );
    await screen.findByLabelText("TTS 固定语音临时试听");
    fireEvent.click(screen.getByRole("button", { name: "语音不合格" }));

    await screen.findByText("TTS 技术合同通过，但主人听检不合格");
    expect(rejectTtsAudioQuality).toHaveBeenCalledWith(1);
    expect(acceptTtsAudioQuality).not.toHaveBeenCalled();
    expect(runTtsSynthesis).not.toHaveBeenCalled();
    expect(screen.getByText("stage=owner_audio_review")).toBeTruthy();
    expect(screen.getByText("code=tts_audio_quality_rejected")).toBeTruthy();
    expect(screen.getByText("audio_quality_reviewed=true")).toBeTruthy();
    expect(screen.getByText("audio_quality_accepted=false")).toBeTruthy();
  });

  it("shows the fixed sticker and actual model description before owner acceptance", async () => {
    getDiagnostics.mockResolvedValue(envelope);
    getManualDiagnostics.mockResolvedValue({
      ...manualEnvelope,
      data: {
        ...manualEnvelope.data!,
        manual_diagnostic_actions_enabled: true,
        cloud_vision_enabled: true,
        cloud_vision_workspace_configured: true,
        cloud_vision_credentials_configured: true,
        supported_workflows: ["cloud_vision_fixed_description"],
      },
    });
    runCloudVisionFixedDescription.mockResolvedValue(cloudVisionActionEnvelope);

    render(<DiagnosticsPage />);

    fireEvent.click(
      await screen.findByRole("button", { name: "检查百炼表情描述与感情色彩" }),
    );
    expect(screen.getByText("确认把固定 owner_private 表情发送到阿里云百炼？")).toBeTruthy();
    expect(runCloudVisionFixedDescription).not.toHaveBeenCalled();
    expect(document.body.textContent).toContain("aike_affection_005.png");
    expect(document.body.textContent).toContain("阿里云百炼北京地域");
    expect(document.body.textContent).toContain("供应商侧的数据处理与留存");
    expect(document.body.textContent).toContain("不会读取聊天、QQ 临时图片或图片缓存");
    expect(document.body.textContent).toContain("不会写业务数据库");

    fireEvent.click(screen.getByRole("button", { name: "确认并执行" }));
    await screen.findByText("百炼视觉基础合同通过，等待主人检查图片描述");
    expect(runCloudVisionFixedDescription).toHaveBeenCalledTimes(1);
    expect(screen.getByText("配置模型 qwen3.7-flash")).toBeTruthy();
    expect(screen.getByText("返回模型 qwen3.7-flash")).toBeTruthy();
    expect(screen.getByText("请求耗时 1578 ms")).toBeTruthy();
    expect(screen.getByText("固定 PNG 162977 bytes")).toBeTruthy();
    expect(screen.getByText("固定样例 aike_affection_005")).toBeTruthy();
    expect(screen.getByText("基础回复合同 通过")).toBeTruthy();
    expect(screen.getByText("主人质检 待确认")).toBeTruthy();
    expect(
      screen.getAllByText(cloudVisionSuccessfulRun.response_description),
    ).toHaveLength(2);
    expect(screen.getByText("回复清理 已执行")).toBeTruthy();
    expect(screen.getByText("图片外发 已执行")).toBeTruthy();
    expect(screen.getByText("workflow=cloud_vision_fixed_description")).toBeTruthy();
    expect(screen.getByText("response_contract_valid=true")).toBeTruthy();
    expect(screen.getByText("response_mode=natural_text")).toBeTruthy();
    expect(screen.getByText("structured_output_requested=false")).toBeTruthy();
    expect(screen.getByText("semantic_contract_automatically_validated=false")).toBeTruthy();
    expect(screen.getByText("owner_visual_judgment_required=true")).toBeTruthy();
    expect(screen.getByText("reference_sticker_id=aike_affection_005")).toBeTruthy();
    expect(screen.getByText("registered_reference_asset_read=true")).toBeTruthy();
    expect(screen.getByText("response_cleanup_applied=true")).toBeTruthy();
    expect(screen.getByText("external_image_upload_executed=true")).toBeTruthy();
    expect(screen.getByText("visual_quality_review_required=true")).toBeTruthy();
    expect(screen.getByText("request_count=1")).toBeTruthy();
    expect(screen.getAllByText("client_automatic_retry=false").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("tool_definitions_sent=false")).toBeTruthy();
    expect(screen.getAllByText("thinking_enabled=false").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("qq_write_executed=false")).toBeTruthy();
    expect(screen.getByText("database_write_allowed=false")).toBeTruthy();
    expect(screen.getByText("project_artifact_write_expected=false")).toBeTruthy();
    expect(screen.getByText("local_vision_called=false")).toBeTruthy();
    expect(document.body.textContent).not.toContain("run_registered_cloud_vision_fixed_description");
    expect(document.body.textContent).not.toContain("data:image/");
    expect(document.body.textContent).not.toContain("Inspect the fixed");

    fireEvent.click(screen.getByRole("button", { name: "加载固定参考图" }));
    const image = await screen.findByAltText("固定视觉诊断参考表情");
    expect(getCloudVisionReferencePreview).toHaveBeenCalledTimes(1);
    fireEvent.load(image);
    fireEvent.click(screen.getByRole("button", { name: "描述合格" }));

    await screen.findByText("百炼视觉请求与基础回复合同通过");
    expect(acceptCloudVisionResponseQuality).toHaveBeenCalledWith(2);
    expect(rejectCloudVisionResponseQuality).not.toHaveBeenCalled();
    expect(runCloudVisionFixedDescription).toHaveBeenCalledTimes(1);
    expect(screen.getByText("visual_quality_reviewed=true")).toBeTruthy();
    expect(screen.getByText("visual_quality_accepted=true")).toBeTruthy();
  });

  it("disables the other manual workflows while TTS synthesis is running", async () => {
    getDiagnostics.mockResolvedValue(envelope);
    getManualDiagnostics.mockResolvedValue({
      ...manualEnvelope,
      data: {
        ...manualEnvelope.data!,
        manual_diagnostic_actions_enabled: true,
        project_doc_rag_probe_enabled: true,
        memory_rag_consistency_enabled: true,
        main_llm_contract_enabled: true,
        tts_synthesis_enabled: true,
        supported_workflows: [
          "project_doc_rag_fixed_retrieval",
          "memory_rag_index_consistency",
          "main_llm_fixed_contract",
          "tts_managed_lifecycle",
        ],
      },
    });
    let finishTts: ((value: OwnerConsoleTtsSynthesisEnvelope) => void) | undefined;
    runTtsSynthesis.mockReturnValue(
      new Promise<OwnerConsoleTtsSynthesisEnvelope>((resolve) => {
        finishTts = resolve;
      }),
    );

    render(<DiagnosticsPage />);
    fireEvent.click(
      await screen.findByRole("button", { name: "检查启动、合成与清理" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "确认并执行" }));

    const projectButton = within(
      screen.getByLabelText("项目文档 RAG 手动检查"),
    ).getByRole("button") as HTMLButtonElement;
    const memoryButton = within(
      screen.getByLabelText("MemoryRAG 索引一致性手动检查"),
    ).getByRole("button") as HTMLButtonElement;
    const mainLlmButton = within(
      screen.getByLabelText("Main LLM 固定问答手动检查"),
    ).getByRole("button") as HTMLButtonElement;
    const ttsConfirmButton = within(
      screen.getByLabelText("确认 TTS 一键生命周期检查"),
    ).getByRole("button", { name: "正在检查" }) as HTMLButtonElement;
    expect(projectButton.disabled).toBe(true);
    expect(memoryButton.disabled).toBe(true);
    expect(mainLlmButton.disabled).toBe(true);
    expect(ttsConfirmButton.disabled).toBe(true);
    expect(runProjectDocRagProbe).not.toHaveBeenCalled();
    expect(runMemoryRagConsistency).not.toHaveBeenCalled();
    expect(runMainLlmContract).not.toHaveBeenCalled();

    finishTts?.(ttsActionEnvelope);
    await screen.findByText("TTS 技术合同通过，等待主人试听确认");
  });
});
