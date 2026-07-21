export type OwnerConsoleHealth = {
  ok: boolean;
  service: string;
  schema_version: string;
  api_prefix: string;
  read_only: boolean;
  http_api_enabled: boolean;
  web_write_enabled: boolean;
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
  method: "GET";
  read_page: string;
  runtime_method: string;
  read_model: string;
  query_params: string[];
  path_params: string[];
  requires_context: boolean;
  read_only: boolean;
  http_api_enabled: boolean;
  web_write_enabled: boolean;
};

export type OwnerConsoleRouteContract = {
  api_prefix: string;
  allowed_methods: string[];
  context_override_allowed: boolean;
  write_routes_enabled: boolean;
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
  work_type: string;
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
  external_request_count: number | null;
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
  operation: string;
  category: string;
  category_label: string;
  code: string;
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
  operation: string;
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

export type OwnerConsoleAccessList = {
  label: string;
  count: number;
  items: string[];
  truncated: boolean;
};

export type OwnerConsoleAccessControlSnapshot = {
  generated_at: string;
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
  limit: number;
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
