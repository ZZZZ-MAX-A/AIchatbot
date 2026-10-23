import type { OwnerConsoleModelConfigSnapshot } from "./ownerConsoleTypes";
import type { MemoryMaintenanceScope } from "./memoryScopeTypes";

export type AccountPersonaModel = OwnerConsoleModelConfigSnapshot & {
  provider: string; source: string; configured: boolean; errors: string[];
  reasoning_effort?: "low" | "high" | "max" | null;
  reasoning_effort_source?: string;
  max_tokens?: number;
};

export type AccountPersonaProfile = {
  account_label: string; bot_self_id: string; persona_id: string; persona_name: string;
  role_card_key: string; role_card_available: boolean; ready: boolean; errors: string[];
  chat_model: AccountPersonaModel; vision_model: AccountPersonaModel;
  voice: {
    voice_id: string; emotion: string; source: string; enabled: boolean;
    sample_available: boolean; sample_kind: string; trim_trailing_noise: boolean;
    service_url_redacted: string; timeout_seconds: number; max_chars: number;
    max_total_seconds: number; cooldown_seconds: number;
  };
  memory: {
    mode: string; storage: string; database: string; file_exists: boolean;
    health_checked: boolean; session_namespace: string;
    summary_model: AccountPersonaModel; embedding_model: string;
    maintenance_scope?: MemoryMaintenanceScope | null;
  };
  scene: {
    assigned: boolean; actor_model: AccountPersonaModel; director_model: string;
    style_examples_status: string; ordinary_world_card_injection: boolean;
  };
  capabilities: { key: string; label: string; state: string; detail: string }[];
  parameters: {
    temperature: number; vision_private_image_wait_seconds: number;
    memory_rag_top_k: number; memory_rag_max_context_chars: number;
    sticker_cooldown_seconds: number; sticker_max_per_hour: number;
    sticker_classifier_model: string; image_generation_model: string;
    image_edit_model: string; weather_mode: string;
  };
};
