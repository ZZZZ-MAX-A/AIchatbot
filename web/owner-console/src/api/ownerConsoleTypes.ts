export type OwnerConsoleHealth = {
  ok: boolean;
  service: string;
  schema_version: string;
  api_prefix: string;
  read_only: boolean;
  snapshot_read_only: boolean;
  http_api_enabled: boolean;
  web_write_enabled: boolean;
  approval_actions_enabled: boolean;
  task_actions_enabled: boolean;
  access_control_actions_enabled: boolean;
  manual_diagnostic_actions_enabled: boolean;
  automatic_diagnostics_enabled: boolean;
  configuration_write_enabled: boolean;
  business_data_write_enabled: boolean;
  enabled_routes: string[];
};

export type OwnerConsoleError = {
  code: string;
  message: string;
  details: Record<string, unknown> | null;
};

export type OwnerConsoleEnvelope<TData> = {
  schema_version: string;
  read_model_schema_version: string;
  transport: "http";
  api_prefix: string;
  resource: string;
  generated_at: string;
  read_only: boolean;
  http_api_enabled: boolean;
  web_write_enabled: boolean;
  data: TData | null;
  error: OwnerConsoleError | null;
};

export type OwnerConsoleRouteRow = {
  name: string;
  resource: string;
  path: string;
  method: "GET" | "POST";
  read_page: string;
  runtime_method: string;
  read_model: string;
  query_params: string[];
  path_params: string[];
  requires_context: boolean;
  read_only: boolean;
  http_api_enabled: boolean;
  web_write_enabled: boolean;
  direct_qq_dependency_allowed?: boolean;
  write_side_effect_allowed?: boolean;
  manual_runtime_action_allowed?: boolean;
  approval_action_allowed?: boolean;
  task_action_allowed?: boolean;
  access_action_allowed?: boolean;
};

export type OwnerConsoleRouteContract = {
  api_prefix: string;
  allowed_methods: string[];
  context_override_allowed: boolean;
  write_routes_enabled: boolean;
  manual_runtime_action_routes_enabled: boolean;
  approval_action_routes_enabled: boolean;
  task_action_routes_enabled: boolean;
  access_action_routes_enabled: boolean;
  route_count: number;
  rows: OwnerConsoleRouteRow[];
  boundary: Record<string, boolean>;
};

export type OwnerConsoleRoutesEnvelope =
  OwnerConsoleEnvelope<OwnerConsoleRouteContract>;

export type OwnerConsoleRuntimeBoundary = {
  main_agent_entry: string;
  ordinary_chat_can_trigger_main_agent: boolean;
  project_doc_rag_in_ordinary_chat: boolean;
  shell_tools_exposed: boolean;
  arbitrary_file_write_allowed: boolean;
  unregistered_db_write_allowed: boolean;
  owner_write_requires_approval: boolean;
  approval_resume_requires_registered_tool: boolean;
  approval_resume_requires_enabled_tool: boolean;
  multi_step_write_automation_allowed: boolean;
  extra_qq_send_side_effect_allowed: boolean;
};

export type OwnerConsoleTaskRow = {
  task_id: number;
  title: string;
  goal_preview: string;
  status: string;
  status_label: string;
  result_preview: string;
  created_at: string;
  updated_at: string;
  latest_event_kind: string;
  latest_event_summary: string;
  pending_approval_ids: number[];
  next_action: string;
  next_action_code: string;
  work_type: string;
  processing_category: string;
  processing_label: string;
  processing_detail: string;
  actionability: OwnerConsoleTaskActionability;
};

export type OwnerConsoleTaskActionability = {
  can_cancel: boolean;
  task_actions_enabled: boolean;
  blocked_reason: string;
};

export type OwnerConsoleTaskEventRow = {
  event_id: number;
  task_id: number;
  step_index: number;
  kind: string;
  tool_name: string;
  input_preview: string;
  output_summary: string;
  status: string;
  status_label: string;
  error: string;
  created_at: string;
};

export type OwnerConsoleApprovalActionability = {
  can_approve: boolean;
  can_reject: boolean;
  resume_enabled: boolean | null;
  blocked_reason: string;
  future_operation_only: boolean;
};

export type OwnerConsoleToolInputPreview = {
  preview_json: string;
  redacted: boolean;
  truncated: boolean;
};

export type OwnerConsoleApprovalRow = {
  approval_id: number;
  task_id: number;
  task_title: string;
  tool_name: string;
  risk_level: string;
  reason_preview: string;
  status: string;
  status_label: string;
  created_at: string;
  expires_at: string;
  decided_at: string;
  actionability: OwnerConsoleApprovalActionability;
};

export type OwnerConsoleOverviewCounters = {
  pending_tasks: number;
  failed_tasks: number;
  pending_approvals: number;
  recent_tasks_visible: number;
  pending_approvals_visible: number;
  awaiting_approval_tasks: number;
  ordinary_pending_tasks: number;
  stale_pending_tasks: number;
};

export type OwnerConsoleOverview = {
  generated_at: string;
  task_limit: number;
  approval_limit: number;
  counters: OwnerConsoleOverviewCounters;
  recent_tasks: OwnerConsoleTaskRow[];
  pending_approvals: OwnerConsoleApprovalRow[];
  boundary: OwnerConsoleRuntimeBoundary;
};

export type OwnerConsoleTextSnapshotSection = {
  title: string;
  ok: boolean;
  summary_text: string;
  display_lines: string[];
  error: string;
};

export type OwnerConsoleObservationSnapshot = {
  main_agent: string[];
  root_graph: string[];
};

export type OwnerConsoleHealthSnapshot = {
  generated_at: string;
  bot_status: OwnerConsoleTextSnapshotSection;
  diagnostics: OwnerConsoleTextSnapshotSection;
  config: OwnerConsoleTextSnapshotSection;
  vision: OwnerConsoleTextSnapshotSection;
  image_cache: OwnerConsoleTextSnapshotSection;
  memory: OwnerConsoleTextSnapshotSection;
  tts: OwnerConsoleTextSnapshotSection;
  recent_errors: OwnerConsoleTextSnapshotSection;
  observations: OwnerConsoleObservationSnapshot;
  boundary: OwnerConsoleRuntimeBoundary;
};

export type OwnerConsoleOverviewEnvelope =
  OwnerConsoleEnvelope<OwnerConsoleOverview>;

export type OwnerConsoleDiagnosticsEnvelope =
  OwnerConsoleEnvelope<OwnerConsoleHealthSnapshot>;

export type OwnerConsoleManualDiagnosticRun = {
  run_id: number;
  workflow: string;
  status: string;
  outcome: string;
  stage: string;
  code: string;
  code_label: string;
  started_at: string;
  finished_at: string;
  attempt_count: number;
  document_count: number;
  embedding_count: number;
  result_count: number;
  expected_document_matched: boolean;
  top_score: number;
  elapsed_ms: number;
  runtime_feature_enabled: boolean;
  owner_triggered: boolean;
  query_text_exposed: boolean;
  result_content_exposed: boolean;
  index_rebuild_executed: boolean;
  database_write_allowed: boolean;
  llm_called: boolean;
  dev_context_called: boolean;
  automatic_retry: boolean;
};

export type OwnerConsoleMemoryRagConsistencyRun = {
  run_id: number;
  workflow: string;
  status: string;
  outcome: string;
  stage: string;
  code: string;
  code_label: string;
  started_at: string;
  finished_at: string;
  attempt_count: number;
  manual_fact_documents: number;
  manual_preference_documents: number;
  session_summary_documents: number;
  active_document_count: number;
  valid_embedding_count: number;
  missing_embedding_count: number;
  missing_manual_fact_embeddings: number;
  missing_manual_preference_embeddings: number;
  missing_session_summary_embeddings: number;
  active_documents_missing_source: number;
  source_records_missing_document: number;
  inactive_document_embedding_count: number;
  runtime_feature_enabled: boolean;
  elapsed_ms: number;
  owner_triggered: boolean;
  memory_content_read: boolean;
  private_memory_query_executed: boolean;
  embedding_called: boolean;
  index_rebuild_executed: boolean;
  database_write_allowed: boolean;
  llm_called: boolean;
  dev_context_called: boolean;
  automatic_retry: boolean;
};

export type OwnerConsoleMainLlmContractRun = {
  run_id: number;
  workflow: string;
  status: string;
  outcome: string;
  stage: string;
  code: string;
  code_label: string;
  started_at: string;
  finished_at: string;
  attempt_count: number;
  configured_model: string;
  runtime_feature_enabled: boolean;
  contract_version: string;
  probe_id: string;
  contract_valid: boolean;
  usage_metadata_available: boolean;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  tool_calls_present: boolean;
  elapsed_ms: number;
  owner_triggered: boolean;
  llm_called: boolean;
  tool_definitions_sent: boolean;
  tool_execution_allowed: boolean;
  client_automatic_retry: boolean;
  chat_history_read: boolean;
  chat_history_written: boolean;
  agent_task_written: boolean;
  approval_written: boolean;
  reliability_event_written: boolean;
  database_write_allowed: boolean;
  memory_rag_called: boolean;
  project_doc_rag_called: boolean;
  dev_context_called: boolean;
  combined_rag_called: boolean;
  tavily_called: boolean;
  tts_called: boolean;
  vision_called: boolean;
  qq_write_executed: boolean;
  prompt_exposed: boolean;
  response_content_exposed: boolean;
};

export type OwnerConsoleTtsSynthesisRun = {
  run_id: number;
  workflow: string;
  status: string;
  outcome: string;
  stage: string;
  code: string;
  code_label: string;
  started_at: string;
  finished_at: string;
  attempt_count: number;
  runtime_feature_enabled: boolean;
  service_health_checked: boolean;
  service_healthy: boolean;
  model_loaded_before: boolean;
  runtime_imported_before: boolean;
  model_load_may_have_occurred: boolean;
  configured_voice_present: boolean;
  tts_called: boolean;
  output_contract_valid: boolean;
  output_file_created: boolean;
  output_bytes: number;
  output_duration_ms: number;
  output_retained: boolean;
  partial_artifact_state: string;
  health_elapsed_ms: number;
  synthesis_elapsed_ms: number;
  elapsed_ms: number;
  fixed_text: string;
  technical_outcome: string;
  technical_code: string;
  audio_preview_available: boolean;
  audio_quality_review_required: boolean;
  audio_quality_reviewed: boolean;
  audio_quality_accepted: boolean | null;
  audio_reviewed_at: string;
  owner_triggered: boolean;
  service_preexisting: boolean;
  service_start_attempted: boolean;
  service_started: boolean;
  service_owned_by_diagnostic: boolean;
  service_stop_attempted: boolean;
  service_stopped: boolean;
  segment_directory_retained: boolean;
  artifact_cleanup_attempted: boolean;
  artifact_cleanup_succeeded: boolean;
  startup_elapsed_ms: number;
  cleanup_elapsed_ms: number;
  automatic_retry: boolean;
  qq_write_executed: boolean;
  reliability_event_written: boolean;
  database_write_allowed: boolean;
  local_file_write_expected: boolean;
  cleanup_executed: boolean;
  chat_history_read: boolean;
  memory_rag_called: boolean;
  project_doc_rag_called: boolean;
  dev_context_called: boolean;
  combined_rag_called: boolean;
  main_llm_called: boolean;
  vision_called: boolean;
  prompt_exposed: boolean;
  response_content_exposed: boolean;
  output_path_exposed: boolean;
  fixed_text_exposed: boolean;
  audio_preview_persisted: boolean;
  audio_preview_path_exposed: boolean;
  audio_review_action_executed: boolean;
};

export type OwnerConsoleVisionInferenceRun = {
  run_id: number;
  workflow: string;
  status: string;
  outcome: string;
  stage: string;
  code: string;
  code_label: string;
  started_at: string;
  finished_at: string;
  attempt_count: number;
  configured_model: string;
  runtime_feature_enabled: boolean;
  fixed_image_contract: string;
  fixed_image_bytes: number;
  fixed_image_contract_valid: boolean;
  reference_sticker_id: string;
  registered_reference_asset_read: boolean;
  expected_answer_disclosed_in_prompt: boolean;
  service_tags_checked: boolean;
  service_healthy: boolean;
  service_preexisting: boolean;
  service_start_attempted: boolean;
  service_started: boolean;
  service_owned_by_diagnostic: boolean;
  service_ownership_basis: string;
  service_stop_attempted: boolean;
  service_stopped: boolean;
  model_available: boolean;
  model_residency_checked: boolean;
  model_loaded_before: boolean;
  keep_alive_zero_used: boolean;
  vision_called: boolean;
  response_contract_valid: boolean;
  response_mode: string;
  structured_output_requested: boolean;
  semantic_contract_automatically_validated: boolean;
  owner_visual_judgment_required: boolean;
  response_preview: string;
  response_description: string;
  response_content_exposed_to_owner: boolean;
  usage_metadata_available: boolean;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  model_cleanup_required: boolean;
  model_cleanup_verified: boolean;
  model_cleanup_poll_count: number;
  startup_elapsed_ms: number;
  discovery_elapsed_ms: number;
  residency_elapsed_ms: number;
  inference_elapsed_ms: number;
  cleanup_elapsed_ms: number;
  elapsed_ms: number;
  technical_outcome: string;
  technical_code: string;
  reference_preview_available: boolean;
  visual_quality_review_required: boolean;
  visual_quality_reviewed: boolean;
  visual_quality_accepted: boolean | null;
  visual_reviewed_at: string;
  visual_review_action_executed: boolean;
  response_preview_persisted: boolean;
  response_preview_path_exposed: boolean;
  reference_image_exposed_to_owner: boolean;
  owner_triggered: boolean;
  client_automatic_retry: boolean;
  tool_definitions_sent: boolean;
  qq_write_executed: boolean;
  reliability_event_written: boolean;
  database_write_allowed: boolean;
  project_file_write_allowed: boolean;
  project_artifact_write_expected: boolean;
  external_runtime_local_write_possible: boolean;
  model_pull_allowed: boolean;
  chat_history_read: boolean;
  memory_rag_called: boolean;
  project_doc_rag_called: boolean;
  dev_context_called: boolean;
  combined_rag_called: boolean;
  main_llm_called: boolean;
  tts_called: boolean;
  image_content_exposed: boolean;
  response_content_exposed: boolean;
};

export type OwnerConsoleCloudVisionRun = {
  run_id: number;
  workflow: string;
  status: string;
  outcome: string;
  stage: string;
  code: string;
  code_label: string;
  started_at: string;
  finished_at: string;
  attempt_count: number;
  provider: string;
  region: string;
  configured_model: string;
  returned_model: string;
  runtime_feature_enabled: boolean;
  endpoint_contract_valid: boolean;
  workspace_configured: boolean;
  credentials_configured: boolean;
  fixed_image_contract: string;
  fixed_image_bytes: number;
  fixed_image_contract_valid: boolean;
  reference_sticker_id: string;
  registered_reference_asset_read: boolean;
  external_image_upload_planned: boolean;
  external_image_upload_executed: boolean;
  provider_side_persistence_controlled_by_app: boolean;
  cloud_vision_called: boolean;
  request_count: number;
  client_automatic_retry: boolean;
  tool_definitions_sent: boolean;
  thinking_enabled: boolean;
  response_mode: string;
  structured_output_requested: boolean;
  semantic_contract_automatically_validated: boolean;
  owner_visual_judgment_required: boolean;
  response_contract_valid: boolean;
  response_preview: string;
  response_description: string;
  response_cleanup_applied: boolean;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  request_elapsed_ms: number;
  technical_outcome: string;
  technical_code: string;
  reference_preview_available: boolean;
  visual_quality_review_required: boolean;
  visual_quality_reviewed: boolean;
  visual_quality_accepted: boolean | null;
  visual_reviewed_at: string;
  visual_review_action_executed: boolean;
  owner_triggered: boolean;
  api_key_exposed: boolean;
  workspace_id_exposed: boolean;
  image_base64_exposed: boolean;
  response_preview_persisted: boolean;
  local_gpu_model_loaded: boolean;
  database_write_allowed: boolean;
  project_artifact_write_expected: boolean;
  reliability_event_written: boolean;
  qq_write_executed: boolean;
  chat_history_written: boolean;
  agent_task_written: boolean;
  approval_written: boolean;
  memory_rag_called: boolean;
  project_doc_rag_called: boolean;
  dev_context_called: boolean;
  combined_rag_called: boolean;
  main_llm_called: boolean;
  tts_called: boolean;
  local_vision_called: boolean;
};

export type OwnerConsoleManualDiagnosticsSnapshot = {
  generated_at: string;
  manual_diagnostic_actions_enabled: boolean;
  project_doc_rag_probe_enabled: boolean;
  memory_rag_consistency_enabled: boolean;
  main_llm_contract_enabled: boolean;
  tts_synthesis_enabled: boolean;
  vision_inference_enabled: boolean;
  cloud_vision_enabled: boolean;
  cloud_vision_workspace_configured: boolean;
  cloud_vision_credentials_configured: boolean;
  automatic_diagnostics_enabled: boolean;
  configuration_write_enabled: boolean;
  business_data_write_enabled: boolean;
  supported_workflows: string[];
  latest_run:
    | OwnerConsoleManualDiagnosticRun
    | OwnerConsoleMemoryRagConsistencyRun
    | OwnerConsoleMainLlmContractRun
    | OwnerConsoleTtsSynthesisRun
    | OwnerConsoleVisionInferenceRun
    | OwnerConsoleCloudVisionRun
    | null;
  project_doc_rag_latest_run: OwnerConsoleManualDiagnosticRun | null;
  memory_rag_consistency_latest_run: OwnerConsoleMemoryRagConsistencyRun | null;
  main_llm_contract_latest_run: OwnerConsoleMainLlmContractRun | null;
  tts_synthesis_latest_run: OwnerConsoleTtsSynthesisRun | null;
  vision_inference_latest_run: OwnerConsoleVisionInferenceRun | null;
  cloud_vision_latest_run: OwnerConsoleCloudVisionRun | null;
};

export type OwnerConsoleManualDiagnosticsEnvelope =
  OwnerConsoleEnvelope<OwnerConsoleManualDiagnosticsSnapshot>;

export type OwnerConsoleActionEnvelope<TData> =
  OwnerConsoleEnvelope<TData> & {
    read_only: false;
    manual_runtime_action: true;
    configuration_write_enabled: false;
    business_data_write_enabled: false;
  };

export type OwnerConsoleApprovalActionResult = {
  generated_at: string;
  approval_id: number;
  task_id: number;
  decision: "approved" | "rejected";
  decision_changed: boolean;
  resume_attempted: boolean;
  resume_executed: boolean;
  task_status: string;
  outcome: string;
  code: string;
  safe_message: string;
};

export type OwnerConsoleApprovalActionPayload = {
  action: OwnerConsoleApprovalActionResult;
  approval_detail: OwnerConsoleApprovalDetail;
};

export type OwnerConsoleApprovalActionEnvelope =
  OwnerConsoleEnvelope<OwnerConsoleApprovalActionPayload> & {
    read_only: false;
    web_write_enabled: true;
    manual_runtime_action: false;
    approval_action: true;
    configuration_write_enabled: false;
    business_data_write_enabled: true;
  };

export type OwnerConsoleTaskActionResult = {
  generated_at: string;
  task_id: number;
  previous_status: string;
  task_status: string;
  status_changed: boolean;
  tool_executed: false;
  approval_resumed: false;
  outcome: string;
  code: string;
  safe_message: string;
};

export type OwnerConsoleTaskActionPayload = {
  action: OwnerConsoleTaskActionResult;
  task_detail: OwnerConsoleTaskDetail;
};

export type OwnerConsoleTaskActionEnvelope =
  OwnerConsoleEnvelope<OwnerConsoleTaskActionPayload> & {
    read_only: false;
    web_write_enabled: true;
    manual_runtime_action: false;
    approval_action: false;
    task_action: true;
    configuration_write_enabled: false;
    business_data_write_enabled: true;
  };

export type OwnerConsoleAccessActionResult = {
  generated_at: string;
  list_name: OwnerConsoleAccessListName;
  operation: "add" | "remove";
  item: string;
  changed: true;
  effective: boolean;
  revision: number;
  source_after: string;
  code: string;
  safe_message: string;
};

export type OwnerConsoleAccessActionPayload = {
  action: OwnerConsoleAccessActionResult;
  access_control: OwnerConsoleAccessControlSnapshot;
};

export type OwnerConsoleAccessActionEnvelope =
  OwnerConsoleEnvelope<OwnerConsoleAccessActionPayload> & {
    read_only: false;
    web_write_enabled: true;
    manual_runtime_action: false;
    approval_action: false;
    task_action: false;
    access_action: true;
    configuration_write_enabled: false;
    business_data_write_enabled: true;
  };

export type OwnerConsoleProjectDocRagProbeEnvelope =
  OwnerConsoleActionEnvelope<OwnerConsoleManualDiagnosticRun>;

export type OwnerConsoleMemoryRagConsistencyEnvelope =
  OwnerConsoleActionEnvelope<OwnerConsoleMemoryRagConsistencyRun>;

export type OwnerConsoleMainLlmContractEnvelope =
  OwnerConsoleActionEnvelope<OwnerConsoleMainLlmContractRun>;

export type OwnerConsoleTtsSynthesisEnvelope =
  OwnerConsoleActionEnvelope<OwnerConsoleTtsSynthesisRun>;

export type OwnerConsoleVisionInferenceEnvelope =
  OwnerConsoleActionEnvelope<OwnerConsoleVisionInferenceRun>;

export type OwnerConsoleCloudVisionEnvelope =
  OwnerConsoleActionEnvelope<OwnerConsoleCloudVisionRun>;

export type OwnerConsoleMemoryCounts = {
  message_count: number;
  session_count: number;
  session_summary_count: number;
  summarized_message_count: number;
  manual_memory_count: number;
  manual_memory_subject_count: number;
  gap_scene_summary_count: number;
  gap_scene_source_message_count: number;
  rag_document_count: number;
  rag_active_document_count: number;
  rag_embedding_count: number;
};

export type OwnerConsoleMemoryContextPolicy = {
  memory_compression_enabled: boolean;
  gap_scene_summaries_enabled: boolean;
  long_term_memory_context_enabled: boolean;
  max_context_messages: number;
  max_stored_messages_per_session: number;
  summary_keep_recent_messages: number;
  summary_batch_messages: number;
  summary_min_source_messages: number;
  max_session_summaries_in_context: number;
  max_gap_scene_summaries_in_context: number;
  max_long_term_memories_in_context: number;
};

export type OwnerConsoleMemoryRagSnapshot = {
  enabled: boolean;
  inject_in_chat: boolean;
  owner_only_debug: boolean;
  top_k: number;
  min_score: number;
  max_context_chars: number;
  include_manual_facts: boolean;
  include_manual_preferences: boolean;
  include_session_summaries: boolean;
  include_short_messages: boolean;
  include_gap_scene_summaries: boolean;
};

export type OwnerConsoleProjectDocRagSnapshot = {
  enabled: boolean;
  explicit_agent_dev_context_only: boolean;
  ordinary_chat_injection_allowed: boolean;
  top_k: number;
  min_score: number;
  max_context_chars: number;
};

export type OwnerConsoleMemorySnapshot = {
  generated_at: string;
  counts: OwnerConsoleMemoryCounts;
  context_policy: OwnerConsoleMemoryContextPolicy;
  memory_rag: OwnerConsoleMemoryRagSnapshot;
  project_doc_rag: OwnerConsoleProjectDocRagSnapshot;
  memory_content_exposed: boolean;
  project_doc_content_exposed: boolean;
  retrieval_executed: boolean;
  index_rebuild_executed: boolean;
  boundary: OwnerConsoleRuntimeBoundary;
};

export type OwnerConsoleMemoryEnvelope =
  OwnerConsoleEnvelope<OwnerConsoleMemorySnapshot>;

export type OwnerConsoleExternalReadDependencySnapshot = {
  httpx_version: string;
  httpcore_version: string;
  compatible: boolean;
};

export type OwnerConsoleExternalReadTaskSnapshot = {
  available: boolean;
  task_id: number | null;
  task_status: string;
  provider_name: string;
  result_count: number | null;
  source_host_count: number | null;
  dropped_result_count: number | null;
  provider_candidate_count: number | null;
  official_content_strong_count: number | null;
  failed_search_stage: string;
  search_stage_count: number | null;
  official_stage_candidate_count: number | null;
  official_stage_result_count: number | null;
  media_stage_candidate_count: number | null;
  media_stage_result_count: number | null;
  planning_mode: string;
  scene: string;
  primary_source_scope: string;
  secondary_source_scope: string;
  secondary_mode: string;
  dropped_missing_date_count: number | null;
  dropped_outside_window_count: number | null;
  dropped_weak_only_count: number | null;
  dropped_conflicting_date_count: number | null;
  dropped_injection_count: number | null;
  dropped_sanitization_count: number | null;
  dropped_source_policy_count: number | null;
  external_request_count: number | null;
  provider_request_count: number | null;
  synthesis_request_count: number | null;
  synthesis_status: string;
  synthesis_error_category: string;
  owner_quality_status: string;
  status_category: string;
  error_category: string;
  updated_at: string;
};

export type OwnerConsoleExternalReadBoundary = {
  owner_private_strict_command_only: boolean;
  main_llm_can_trigger: boolean;
  ordinary_chat_can_trigger: boolean;
  arbitrary_url_fetch_allowed: boolean;
  ai_answer_enabled: boolean;
  raw_content_enabled: boolean;
  isolated_synthesis_enabled: boolean;
  images_enabled: boolean;
  retry_enabled: boolean;
  fallback_enabled: boolean;
  live_probe_executed: boolean;
  external_request_executed: boolean;
  query_exposed: boolean;
  result_content_exposed: boolean;
  source_url_exposed: boolean;
  credential_value_exposed: boolean;
};

export type OwnerConsoleExternalReadSnapshot = {
  generated_at: string;
  enabled: boolean;
  credential_configured: boolean;
  executor_configured: boolean;
  synthesis_configured: boolean;
  provider_name: string;
  search_depth: string;
  max_results: number;
  timeout_seconds: number;
  endpoint_host: string;
  dependencies: OwnerConsoleExternalReadDependencySnapshot;
  recent_task: OwnerConsoleExternalReadTaskSnapshot;
  boundary: OwnerConsoleExternalReadBoundary;
};

export type OwnerConsoleExternalReadEnvelope =
  OwnerConsoleEnvelope<OwnerConsoleExternalReadSnapshot>;

export type OwnerConsoleReliabilityStateCounts = {
  unresolved: number;
  recovered: number;
  recurring: number;
  insufficient_evidence: number;
};

export type OwnerConsoleReliabilityTrendItem = {
  component: string;
  component_label: string;
  operation: string;
  operation_label: string;
  category: string;
  category_label: string;
  code: string;
  code_label: string;
  occurrence_count: number;
  first_seen_at: string;
  last_seen_at: string;
  last_success_at: string;
  recovery_state: string;
  recovery_state_label: string;
};

export type OwnerConsoleReliabilityWindow = {
  window_hours: number;
  failure_occurrence_count: number;
  failure_group_count: number;
  state_counts: OwnerConsoleReliabilityStateCounts;
  items: OwnerConsoleReliabilityTrendItem[];
};

export type OwnerConsoleReliabilityCoverageRow = {
  component: string;
  component_label: string;
  operation: string;
  operation_label: string;
};

export type OwnerConsoleReliabilityBoundary = {
  sqlite_mode_ro: boolean;
  ensure_database_called: boolean;
  chat_content_read: boolean;
  raw_exception_read: boolean;
  user_identifier_read: boolean;
  runtime_identifier_exposed: boolean;
  database_identifier_exposed: boolean;
  llm_called: boolean;
  rag_called: boolean;
  alert_executed: boolean;
  repair_executed: boolean;
  retry_executed: boolean;
  restart_executed: boolean;
  cleanup_executed: boolean;
  write_side_effect_allowed: boolean;
};

export type OwnerConsoleReliabilitySnapshot = {
  generated_at: string;
  recent: OwnerConsoleReliabilityWindow;
  weekly: OwnerConsoleReliabilityWindow;
  coverage: OwnerConsoleReliabilityCoverageRow[];
  scope_note: string;
  evidence_note: string;
  boundary: OwnerConsoleReliabilityBoundary;
};

export type OwnerConsoleReliabilityEnvelope =
  OwnerConsoleEnvelope<OwnerConsoleReliabilitySnapshot>;

export type OwnerConsoleAccessListName =
  | "private_whitelist"
  | "group_whitelist"
  | "user_blacklist";

export type OwnerConsoleAccessListItem = {
  value: string;
  source: "environment" | "dynamic" | "environment_and_dynamic";
  editable: boolean;
};

export type OwnerConsoleAccessList = {
  label: string;
  count: number;
  items: OwnerConsoleAccessListItem[];
  truncated: boolean;
  environment_count: number;
  dynamic_count: number;
};

export type OwnerConsoleAccessControlSnapshot = {
  generated_at: string;
  revision: number;
  access_actions_enabled: boolean;
  owner_configured: boolean;
  private_chat_enabled: boolean;
  group_chat_enabled: boolean;
  unknown_private_policy: string;
  private_whitelist: OwnerConsoleAccessList;
  group_whitelist: OwnerConsoleAccessList;
  user_blacklist: OwnerConsoleAccessList;
  boundary: OwnerConsoleRuntimeBoundary;
};

export type OwnerConsoleAccessControlEnvelope =
  OwnerConsoleEnvelope<OwnerConsoleAccessControlSnapshot>;

export type OwnerConsoleModelConfigSnapshot = {
  model_name: string;
  base_url_redacted: string;
  api_key_configured: boolean;
  timeout_seconds: number;
};

export type OwnerConsoleRoleCardRow = {
  key: string;
  title: string;
  active: boolean;
};

export type OwnerConsoleSettingsSnapshot = {
  generated_at: string;
  chat_model: OwnerConsoleModelConfigSnapshot;
  main_agent_model: OwnerConsoleModelConfigSnapshot;
  embedding: OwnerConsoleModelConfigSnapshot;
  role_cards: OwnerConsoleRoleCardRow[];
  active_role_card_key: string;
  feature_flags: Record<string, boolean>;
  boundary: OwnerConsoleRuntimeBoundary;
};

export type OwnerConsoleSettingsEnvelope =
  OwnerConsoleEnvelope<OwnerConsoleSettingsSnapshot>;

export type OwnerConsoleTaskList = {
  generated_at: string;
  status_filter: string | null;
  work_type_filter: string | null;
  category_filter: string | null;
  limit: number;
  page: number;
  page_size: number;
  total_matching: number;
  total_pages: number;
  has_previous: boolean;
  has_next: boolean;
  total_visible: number;
  rows: OwnerConsoleTaskRow[];
  boundary: OwnerConsoleRuntimeBoundary;
};

export type OwnerConsoleTaskListEnvelope =
  OwnerConsoleEnvelope<OwnerConsoleTaskList>;

export type OwnerConsoleTaskDetail = {
  generated_at: string;
  task: OwnerConsoleTaskRow;
  goal: string;
  result: string;
  events: OwnerConsoleTaskEventRow[];
  approvals: OwnerConsoleApprovalRow[];
  next_action: string;
  boundary: OwnerConsoleRuntimeBoundary;
};

export type OwnerConsoleTaskDetailEnvelope =
  OwnerConsoleEnvelope<OwnerConsoleTaskDetail>;

export type OwnerConsoleApprovalList = {
  generated_at: string;
  status_filter: string | null;
  limit: number;
  total_visible: number;
  rows: OwnerConsoleApprovalRow[];
  boundary: OwnerConsoleRuntimeBoundary;
};

export type OwnerConsoleApprovalListEnvelope =
  OwnerConsoleEnvelope<OwnerConsoleApprovalList>;

export type OwnerConsoleApprovalDetail = {
  generated_at: string;
  approval: OwnerConsoleApprovalRow;
  reason: string;
  tool_input: OwnerConsoleToolInputPreview;
  task: OwnerConsoleTaskRow | null;
  recent_events: OwnerConsoleTaskEventRow[];
  boundary: OwnerConsoleRuntimeBoundary;
};

export type OwnerConsoleApprovalDetailEnvelope =
  OwnerConsoleEnvelope<OwnerConsoleApprovalDetail>;

export type OwnerConsoleSnapshot = {
  health: OwnerConsoleHealth | null;
  routes: OwnerConsoleRoutesEnvelope | null;
};
