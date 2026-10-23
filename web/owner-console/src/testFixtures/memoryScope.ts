import type { MemoryMaintenanceScope } from "../api/memoryScopeTypes";
import type { OwnerConsoleMemoryEnvelope } from "../api/ownerConsoleTypes";

export const defaultMemoryScope: MemoryMaintenanceScope = {
  bot_self_id: "2000000001", persona_id: "aike", persona_name: "爱可", role_card_key: "aike",
  storage: "legacy_database", database: "data/chatbot.db", session_namespace: "private:/group:", revision: "a".repeat(64),
};
export const alternateMemoryScope: MemoryMaintenanceScope = {
  bot_self_id: "3000000001", persona_id: "linyin", persona_name: "凛音", role_card_key: "linyin",
  storage: "persona_database", database: "data/persona-memory/linyin.db", session_namespace: "persona:linyin:", revision: "b".repeat(64),
};
export const memoryScopeSettings = { data: { account_personas: [defaultMemoryScope, alternateMemoryScope].map((scope) => ({
  bot_self_id: scope.bot_self_id, persona_name: scope.persona_name,
  memory: { storage: scope.storage, maintenance_scope: scope },
})) } };

export function memoryEnvelope(scope: MemoryMaintenanceScope, count: number): OwnerConsoleMemoryEnvelope {
  return {
    schema_version: "owner_console.http.v1", read_model_schema_version: "owner_console.read_model.v0",
    transport: "http", api_prefix: "/api/v1/owner-console", resource: "memory", generated_at: "test",
    read_only: true, http_api_enabled: true, web_write_enabled: false, error: null,
    data: {
      memory_scope: scope, generated_at: "test", counts: {
        message_count: count, session_count: 1, session_summary_count: 0, summarized_message_count: 0,
        manual_memory_count: 0, manual_memory_subject_count: 0, gap_scene_summary_count: 0, gap_scene_source_message_count: 0,
        rag_document_count: count, rag_active_document_count: count, rag_embedding_count: 0,
      },
      context_policy: { memory_compression_enabled: false, gap_scene_summaries_enabled: false,
        long_term_memory_context_enabled: true, max_context_messages: 40, max_stored_messages_per_session: 120,
        summary_keep_recent_messages: 40, summary_batch_messages: 80, summary_min_source_messages: 40,
        max_session_summaries_in_context: 2, max_gap_scene_summaries_in_context: 2, max_long_term_memories_in_context: 4 },
      memory_rag: { enabled: true, inject_in_chat: false, owner_only_debug: true, top_k: 5, min_score: 0.3,
        max_context_chars: 1000, include_manual_facts: true, include_manual_preferences: true,
        include_session_summaries: true, include_short_messages: false, include_gap_scene_summaries: false },
      project_doc_rag: { enabled: false, explicit_agent_dev_context_only: true, ordinary_chat_injection_allowed: false,
        top_k: 5, min_score: 0.3, max_context_chars: 1000 },
      memory_content_exposed: false, project_doc_content_exposed: false, retrieval_executed: false, index_rebuild_executed: false,
      boundary: { main_agent_entry: "explicit", ordinary_chat_can_trigger_main_agent: false,
        project_doc_rag_in_ordinary_chat: false, shell_tools_exposed: false, arbitrary_file_write_allowed: false,
        unregistered_db_write_allowed: false, owner_write_requires_approval: true, approval_resume_requires_registered_tool: true,
        approval_resume_requires_enabled_tool: true, multi_step_write_automation_allowed: false, extra_qq_send_side_effect_allowed: false },
    },
  };
}
