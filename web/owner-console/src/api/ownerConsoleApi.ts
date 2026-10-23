import {
  OWNER_CONSOLE_API_PREFIX,
  checkOwnerConsoleActionEnvelope,
  checkOwnerConsoleAccessActionEnvelope,
  checkOwnerConsoleApprovalActionEnvelope,
  checkOwnerConsoleTaskActionEnvelope,
  checkOwnerConsoleEnvelope,
} from "./ownerConsoleEnvelope";
import type {
  OwnerConsoleAccessControlEnvelope,
  OwnerConsoleAccessActionEnvelope,
  OwnerConsoleApprovalDetailEnvelope,
  OwnerConsoleApprovalActionEnvelope,
  OwnerConsoleApprovalListEnvelope,
  OwnerConsoleDiagnosticsEnvelope,
  OwnerConsoleExternalReadEnvelope,
  OwnerConsoleHealth,
  OwnerConsoleMemoryEnvelope,
  OwnerConsoleMemoryRagConsistencyEnvelope,
  OwnerConsoleMainLlmContractEnvelope,
  OwnerConsoleManualDiagnosticsEnvelope,
  OwnerConsoleOverviewEnvelope,
  OwnerConsoleReliabilityEnvelope,
  OwnerConsoleProjectDocRagProbeEnvelope,
  OwnerConsoleRoutesEnvelope,
  OwnerConsoleSettingsEnvelope,
  OwnerConsoleTtsSynthesisEnvelope,
  OwnerConsoleCloudVisionEnvelope,
  OwnerConsoleTaskDetailEnvelope,
  OwnerConsoleTaskListEnvelope,
  OwnerConsoleTaskActionEnvelope,
} from "./ownerConsoleTypes";

const API_BASE =
  import.meta.env.VITE_OWNER_CONSOLE_API_BASE ?? OWNER_CONSOLE_API_PREFIX;
const HEALTH_PATH = import.meta.env.VITE_OWNER_CONSOLE_HEALTH_PATH ?? "/healthz";

function memoryScopeQuery(scope?: import("./memoryScopeTypes").MemoryMaintenanceScope): string {
  return scope ? buildQuery({ bot_self_id: scope.bot_self_id, scope_revision: scope.revision }) : "";
}

const allowedGetPaths = new Set([
  HEALTH_PATH,
  `${API_BASE}/routes`,
  `${API_BASE}/overview`,
  `${API_BASE}/diagnostics`,
  `${API_BASE}/manual-diagnostics`,
  `${API_BASE}/reliability`,
  `${API_BASE}/external-read`,
  `${API_BASE}/memory`,
  `${API_BASE}/access-control`,
  `${API_BASE}/settings`,
  `${API_BASE}/manual-diagnostics/cloud-vision-fixed-description/reference-preview`,
  `${API_BASE}/tasks`,
  `${API_BASE}/approvals`,
]);

const allowedPostPaths = new Set([
  `${API_BASE}/access-control/private-whitelist/add`,
  `${API_BASE}/access-control/private-whitelist/remove`,
  `${API_BASE}/access-control/group-whitelist/add`,
  `${API_BASE}/access-control/group-whitelist/remove`,
  `${API_BASE}/access-control/user-blacklist/add`,
  `${API_BASE}/access-control/user-blacklist/remove`,
  `${API_BASE}/manual-diagnostics/project-doc-rag`,
  `${API_BASE}/manual-diagnostics/memory-rag-consistency`,
  `${API_BASE}/manual-diagnostics/main-llm-contract`,
  `${API_BASE}/manual-diagnostics/tts-synthesis`,
  `${API_BASE}/manual-diagnostics/tts-synthesis/audio-quality/accept`,
  `${API_BASE}/manual-diagnostics/tts-synthesis/audio-quality/reject`,
  `${API_BASE}/manual-diagnostics/cloud-vision-fixed-description`,
  `${API_BASE}/manual-diagnostics/cloud-vision-fixed-description/response-quality/accept`,
  `${API_BASE}/manual-diagnostics/cloud-vision-fixed-description/response-quality/reject`,
]);

function isAllowedPostPath(routePath: string): boolean {
  if (allowedPostPaths.has(routePath)) {
    return true;
  }
  const taskPrefix = `${API_BASE}/tasks/`;
  if (routePath.startsWith(taskPrefix)) {
    const suffix = routePath.slice(taskPrefix.length);
    return /^[1-9]\d*\/cancel$/.test(suffix);
  }
  const approvalPrefix = `${API_BASE}/approvals/`;
  if (!routePath.startsWith(approvalPrefix)) {
    return false;
  }
  const suffix = routePath.slice(approvalPrefix.length);
  return /^[1-9]\d*\/(approve|reject)$/.test(suffix);
}

function isAllowedGetPath(routePath: string): boolean {
  if (allowedGetPaths.has(routePath)) {
    return true;
  }
  const personaSamplePrefix = `${API_BASE}/settings/accounts/`;
  if (routePath.startsWith(personaSamplePrefix)) {
    return /^[0-9]{5,20}\/voice-sample$/.test(routePath.slice(personaSamplePrefix.length));
  }

  const taskDetailPrefix = `${API_BASE}/tasks/`;
  if (routePath.startsWith(taskDetailPrefix)) {
    const taskId = routePath.slice(taskDetailPrefix.length);
    return /^[1-9]\d*$/.test(taskId);
  }

  const approvalDetailPrefix = `${API_BASE}/approvals/`;
  if (routePath.startsWith(approvalDetailPrefix)) {
    const approvalId = routePath.slice(approvalDetailPrefix.length);
    return /^[1-9]\d*$/.test(approvalId);
  }

  const ttsPreviewPrefix = `${API_BASE}/manual-diagnostics/tts-synthesis/audio-preview/`;
  if (routePath.startsWith(ttsPreviewPrefix)) {
    const runId = routePath.slice(ttsPreviewPrefix.length);
    return /^[1-9]\d*$/.test(runId);
  }

  return false;
}

export class OwnerConsoleApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown> | null;

  constructor(
    message: string,
    {
      status,
      code,
      details,
    }: { status: number; code: string; details: Record<string, unknown> | null },
  ) {
    super(message);
    this.name = "OwnerConsoleApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function getJson<TResponse>(
  path: string,
  signal?: AbortSignal,
): Promise<TResponse> {
  const routePath = path.split("?")[0];
  if (!isAllowedGetPath(routePath)) {
    throw new Error("前端请求路径不在只读 allowlist 内");
  }

  const response = await fetch(path, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    signal,
  });

  const payload = (await response.json()) as TResponse;
  if (!response.ok) {
    const maybeError = payload as {
      error?: {
        code?: string;
        message?: string;
        details?: Record<string, unknown> | null;
      } | null;
    };
    throw new OwnerConsoleApiError(
      maybeError.error?.message ?? `请求失败：HTTP ${response.status}`,
      {
        status: response.status,
        code: maybeError.error?.code ?? "http_error",
        details: maybeError.error?.details ?? null,
      },
    );
  }
  return payload;
}

async function postJson<TResponse>(
  path: string,
  body: Record<string, string | number | boolean>,
  headers: Record<string, string>,
  signal?: AbortSignal,
): Promise<TResponse> {
  const routePath = path.split("?")[0];
  if (!isAllowedPostPath(routePath)) {
    throw new Error("前端手动动作路径不在固定 allowlist 内");
  }

  const response = await fetch(path, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...headers,
    },
    body: JSON.stringify(body),
    signal,
  });
  const payload = (await response.json()) as TResponse;
  if (!response.ok) {
    const maybeError = payload as {
      error?: {
        code?: string;
        message?: string;
        details?: Record<string, unknown> | null;
      } | null;
    };
    throw new OwnerConsoleApiError(
      maybeError.error?.message ?? `请求失败：HTTP ${response.status}`,
      {
        status: response.status,
        code: maybeError.error?.code ?? "http_error",
        details: maybeError.error?.details ?? null,
      },
    );
  }
  return payload;
}

function buildQuery(params: Record<string, string | number | null | undefined>) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      query.set(key, String(value));
    }
  });
  const rendered = query.toString();
  return rendered ? `?${rendered}` : "";
}

type AccessRouteName =
  | "private-whitelist"
  | "group-whitelist"
  | "user-blacklist";
type AccessOperation = "add" | "remove";

const accessActionContracts = {
  "private-whitelist:add": {
    confirmation: "add_private_whitelist_item",
    header: "access-private-whitelist-add-v1",
  },
  "private-whitelist:remove": {
    confirmation: "remove_private_whitelist_item",
    header: "access-private-whitelist-remove-v1",
  },
  "group-whitelist:add": {
    confirmation: "add_group_whitelist_item",
    header: "access-group-whitelist-add-v1",
  },
  "group-whitelist:remove": {
    confirmation: "remove_group_whitelist_item",
    header: "access-group-whitelist-remove-v1",
  },
  "user-blacklist:add": {
    confirmation: "add_user_blacklist_item",
    header: "access-user-blacklist-add-v1",
  },
  "user-blacklist:remove": {
    confirmation: "remove_user_blacklist_item",
    header: "access-user-blacklist-remove-v1",
  },
} as const;

async function postAccessAction(
  routeName: AccessRouteName,
  operation: AccessOperation,
  item: string,
  revision: number,
  signal?: AbortSignal,
): Promise<OwnerConsoleAccessActionEnvelope> {
  const contract = accessActionContracts[`${routeName}:${operation}`];
  const envelope = await postJson<OwnerConsoleAccessActionEnvelope>(
    `${API_BASE}/access-control/${routeName}/${operation}`,
    { item, revision, confirmation: contract.confirmation },
    { "X-Owner-Console-Action": contract.header },
    signal,
  );
  const checked = checkOwnerConsoleAccessActionEnvelope(envelope);
  if (!checked.ok) {
    throw new Error(checked.message);
  }
  return envelope;
}

export const ownerConsoleApi = {
  async getPersonaVoiceSample(botSelfId: string, signal?: AbortSignal): Promise<Blob> {
    if (!/^[0-9]{5,20}$/.test(botSelfId)) {
      throw new Error("账号标识无效");
    }
    const path = `${API_BASE}/settings/accounts/${botSelfId}/voice-sample`;
    if (!isAllowedGetPath(path)) throw new Error("音色样例路径未注册");
    const response = await fetch(path, {
      method: "GET", credentials: "same-origin", cache: "no-store", signal,
      headers: { Accept: "audio/wav", "X-Owner-Console-Action": "persona-voice-sample-v1" },
    });
    if (!response.ok) throw new Error("当前账号的音色样例不可用，请刷新配置后重试。");
    const blob = await response.blob();
    if (response.headers.get("content-type")?.split(";", 1)[0] !== "audio/wav"
      || blob.size <= 44 || blob.size > 20 * 1024 * 1024) {
      throw new Error("音色样例格式无效");
    }
    return blob;
  },
  getHealth(signal?: AbortSignal): Promise<OwnerConsoleHealth> {
    return getJson<OwnerConsoleHealth>(HEALTH_PATH, signal);
  },

  async getRoutes(signal?: AbortSignal): Promise<OwnerConsoleRoutesEnvelope> {
    const envelope = await getJson<OwnerConsoleRoutesEnvelope>(
      `${API_BASE}/routes`,
      signal,
    );
    const contract = checkOwnerConsoleEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async getOverview(
    params: { task_limit: number; approval_limit: number },
    signal?: AbortSignal,
  ): Promise<OwnerConsoleOverviewEnvelope> {
    const envelope = await getJson<OwnerConsoleOverviewEnvelope>(
      `${API_BASE}/overview${buildQuery(params)}`,
      signal,
    );
    const contract = checkOwnerConsoleEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async getDiagnostics(
    signal?: AbortSignal,
    scope?: import("./memoryScopeTypes").MemoryMaintenanceScope | null,
  ): Promise<OwnerConsoleDiagnosticsEnvelope> {
    const envelope = await getJson<OwnerConsoleDiagnosticsEnvelope>(
      `${API_BASE}/diagnostics${scope === null ? "?skip_memory=true" : memoryScopeQuery(scope)}`,
      signal,
    );
    const contract = checkOwnerConsoleEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async getManualDiagnostics(
    signal?: AbortSignal,
    scope?: import("./memoryScopeTypes").MemoryMaintenanceScope,
  ): Promise<OwnerConsoleManualDiagnosticsEnvelope> {
    const envelope = await getJson<OwnerConsoleManualDiagnosticsEnvelope>(
      `${API_BASE}/manual-diagnostics${memoryScopeQuery(scope)}`,
      signal,
    );
    const contract = checkOwnerConsoleEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async runProjectDocRagProbe(
    signal?: AbortSignal,
  ): Promise<OwnerConsoleProjectDocRagProbeEnvelope> {
    const envelope = await postJson<OwnerConsoleProjectDocRagProbeEnvelope>(
      `${API_BASE}/manual-diagnostics/project-doc-rag`,
      { confirmation: "run_registered_project_doc_rag_probe" },
      { "X-Owner-Console-Action": "manual-project-doc-rag-probe-v1" },
      signal,
    );
    const contract = checkOwnerConsoleActionEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async runMemoryRagConsistency(
    signal?: AbortSignal,
    scope?: import("./memoryScopeTypes").MemoryMaintenanceScope,
  ): Promise<OwnerConsoleMemoryRagConsistencyEnvelope> {
    const envelope = await postJson<OwnerConsoleMemoryRagConsistencyEnvelope>(
      `${API_BASE}/manual-diagnostics/memory-rag-consistency${memoryScopeQuery(scope)}`,
      { confirmation: "run_registered_memory_rag_consistency" },
      { "X-Owner-Console-Action": "manual-memory-rag-consistency-v1" },
      signal,
    );
    const contract = checkOwnerConsoleActionEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async runMainLlmContract(
    signal?: AbortSignal,
  ): Promise<OwnerConsoleMainLlmContractEnvelope> {
    const envelope = await postJson<OwnerConsoleMainLlmContractEnvelope>(
      `${API_BASE}/manual-diagnostics/main-llm-contract`,
      { confirmation: "run_registered_main_llm_contract" },
      { "X-Owner-Console-Action": "manual-main-llm-contract-v1" },
      signal,
    );
    const contract = checkOwnerConsoleActionEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async runTtsSynthesis(
    signal?: AbortSignal,
  ): Promise<OwnerConsoleTtsSynthesisEnvelope> {
    const envelope = await postJson<OwnerConsoleTtsSynthesisEnvelope>(
      `${API_BASE}/manual-diagnostics/tts-synthesis`,
      { confirmation: "run_registered_tts_synthesis" },
      { "X-Owner-Console-Action": "manual-tts-synthesis-v1" },
      signal,
    );
    const contract = checkOwnerConsoleActionEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async getTtsAudioPreview(
    runId: number,
    signal?: AbortSignal,
  ): Promise<Blob> {
    if (!Number.isSafeInteger(runId) || runId <= 0) {
      throw new Error("TTS 临时试听 run_id 无效");
    }
    const path = `${API_BASE}/manual-diagnostics/tts-synthesis/audio-preview/${runId}`;
    if (!isAllowedGetPath(path)) {
      throw new Error("TTS 临时试听路径不在 allowlist 内");
    }
    const response = await fetch(path, {
      method: "GET",
      credentials: "same-origin",
      headers: {
        Accept: "audio/wav",
        "X-Owner-Console-Action": "manual-tts-audio-preview-v1",
      },
      cache: "no-store",
      signal,
    });
    if (!response.ok) {
      let message = "TTS 临时试听不可用";
      try {
        const payload = (await response.json()) as {
          error?: { message?: string } | null;
        };
        message = payload.error?.message || message;
      } catch {
        // The bounded public message remains intentionally generic.
      }
      throw new Error(message);
    }
    const contentType = response.headers.get("content-type")?.split(";", 1)[0];
    const blob = await response.blob();
    if (
      contentType !== "audio/wav" ||
      blob.size <= 44 ||
      blob.size > 50 * 1024 * 1024
    ) {
      throw new Error("TTS 临时试听响应合同无效");
    }
    return blob;
  },

  async acceptTtsAudioQuality(
    runId: number,
    signal?: AbortSignal,
  ): Promise<OwnerConsoleTtsSynthesisEnvelope> {
    if (!Number.isSafeInteger(runId) || runId <= 0) {
      throw new Error("TTS 主人听检 run_id 无效");
    }
    const envelope = await postJson<OwnerConsoleTtsSynthesisEnvelope>(
      `${API_BASE}/manual-diagnostics/tts-synthesis/audio-quality/accept`,
      { confirmation: "accept_latest_tts_audio_quality", run_id: runId },
      { "X-Owner-Console-Action": "manual-tts-audio-quality-accept-v1" },
      signal,
    );
    const contract = checkOwnerConsoleActionEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async rejectTtsAudioQuality(
    runId: number,
    signal?: AbortSignal,
  ): Promise<OwnerConsoleTtsSynthesisEnvelope> {
    if (!Number.isSafeInteger(runId) || runId <= 0) {
      throw new Error("TTS 主人听检 run_id 无效");
    }
    const envelope = await postJson<OwnerConsoleTtsSynthesisEnvelope>(
      `${API_BASE}/manual-diagnostics/tts-synthesis/audio-quality/reject`,
      { confirmation: "reject_latest_tts_audio_quality", run_id: runId },
      { "X-Owner-Console-Action": "manual-tts-audio-quality-reject-v1" },
      signal,
    );
    const contract = checkOwnerConsoleActionEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async runCloudVisionFixedDescription(
    signal?: AbortSignal,
  ): Promise<OwnerConsoleCloudVisionEnvelope> {
    const envelope = await postJson<OwnerConsoleCloudVisionEnvelope>(
      `${API_BASE}/manual-diagnostics/cloud-vision-fixed-description`,
      { confirmation: "run_registered_cloud_vision_fixed_description" },
      { "X-Owner-Console-Action": "manual-cloud-vision-fixed-description-v1" },
      signal,
    );
    const contract = checkOwnerConsoleActionEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async getCloudVisionReferencePreview(
    signal?: AbortSignal,
  ): Promise<Blob> {
    const path = (
      `${API_BASE}/manual-diagnostics/cloud-vision-fixed-description/reference-preview`
    );
    if (!isAllowedGetPath(path)) {
      throw new Error("视觉固定参考图路径不在 allowlist 内");
    }
    const response = await fetch(path, {
      method: "GET",
      credentials: "same-origin",
      headers: {
        Accept: "image/png",
        "X-Owner-Console-Action": "manual-cloud-vision-reference-preview-v1",
      },
      cache: "no-store",
      signal,
    });
    if (!response.ok) {
      let message = "视觉固定参考图不可用";
      try {
        const payload = (await response.json()) as {
          error?: { message?: string } | null;
        };
        message = payload.error?.message || message;
      } catch {
        // The bounded public message remains intentionally generic.
      }
      throw new Error(message);
    }
    const contentType = response.headers.get("content-type")?.split(";", 1)[0];
    const blob = await response.blob();
    if (contentType !== "image/png" || blob.size !== 162_977) {
      throw new Error("视觉固定参考图响应合同无效");
    }
    return blob;
  },

  async acceptCloudVisionResponseQuality(
    runId: number,
    signal?: AbortSignal,
  ): Promise<OwnerConsoleCloudVisionEnvelope> {
    if (!Number.isSafeInteger(runId) || runId <= 0) {
      throw new Error("视觉主人质检 run_id 无效");
    }
    const envelope = await postJson<OwnerConsoleCloudVisionEnvelope>(
      `${API_BASE}/manual-diagnostics/cloud-vision-fixed-description/response-quality/accept`,
      {
        confirmation: "accept_latest_cloud_vision_response_quality",
        run_id: runId,
      },
      {
        "X-Owner-Console-Action": "manual-cloud-vision-response-quality-accept-v1",
      },
      signal,
    );
    const contract = checkOwnerConsoleActionEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async rejectCloudVisionResponseQuality(
    runId: number,
    signal?: AbortSignal,
  ): Promise<OwnerConsoleCloudVisionEnvelope> {
    if (!Number.isSafeInteger(runId) || runId <= 0) {
      throw new Error("视觉主人质检 run_id 无效");
    }
    const envelope = await postJson<OwnerConsoleCloudVisionEnvelope>(
      `${API_BASE}/manual-diagnostics/cloud-vision-fixed-description/response-quality/reject`,
      {
        confirmation: "reject_latest_cloud_vision_response_quality",
        run_id: runId,
      },
      {
        "X-Owner-Console-Action": "manual-cloud-vision-response-quality-reject-v1",
      },
      signal,
    );
    const contract = checkOwnerConsoleActionEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async getReliability(
    signal?: AbortSignal,
  ): Promise<OwnerConsoleReliabilityEnvelope> {
    const envelope = await getJson<OwnerConsoleReliabilityEnvelope>(
      `${API_BASE}/reliability`,
      signal,
    );
    const contract = checkOwnerConsoleEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async getMemory(signal?: AbortSignal, scope?: import("./memoryScopeTypes").MemoryMaintenanceScope): Promise<OwnerConsoleMemoryEnvelope> {
    const envelope = await getJson<OwnerConsoleMemoryEnvelope>(
      `${API_BASE}/memory${memoryScopeQuery(scope)}`,
      signal,
    );
    const contract = checkOwnerConsoleEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async getExternalRead(
    signal?: AbortSignal,
  ): Promise<OwnerConsoleExternalReadEnvelope> {
    const envelope = await getJson<OwnerConsoleExternalReadEnvelope>(
      `${API_BASE}/external-read`,
      signal,
    );
    const contract = checkOwnerConsoleEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async getAccessControl(
    params: { item_limit: number },
    signal?: AbortSignal,
  ): Promise<OwnerConsoleAccessControlEnvelope> {
    const envelope = await getJson<OwnerConsoleAccessControlEnvelope>(
      `${API_BASE}/access-control${buildQuery(params)}`,
      signal,
    );
    const contract = checkOwnerConsoleEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async addPrivateWhitelistItem(
    item: string,
    revision: number,
    signal?: AbortSignal,
  ): Promise<OwnerConsoleAccessActionEnvelope> {
    return postAccessAction("private-whitelist", "add", item, revision, signal);
  },

  async removePrivateWhitelistItem(
    item: string,
    revision: number,
    signal?: AbortSignal,
  ): Promise<OwnerConsoleAccessActionEnvelope> {
    return postAccessAction("private-whitelist", "remove", item, revision, signal);
  },

  async addGroupWhitelistItem(
    item: string,
    revision: number,
    signal?: AbortSignal,
  ): Promise<OwnerConsoleAccessActionEnvelope> {
    return postAccessAction("group-whitelist", "add", item, revision, signal);
  },

  async removeGroupWhitelistItem(
    item: string,
    revision: number,
    signal?: AbortSignal,
  ): Promise<OwnerConsoleAccessActionEnvelope> {
    return postAccessAction("group-whitelist", "remove", item, revision, signal);
  },

  async addUserBlacklistItem(
    item: string,
    revision: number,
    signal?: AbortSignal,
  ): Promise<OwnerConsoleAccessActionEnvelope> {
    return postAccessAction("user-blacklist", "add", item, revision, signal);
  },

  async removeUserBlacklistItem(
    item: string,
    revision: number,
    signal?: AbortSignal,
  ): Promise<OwnerConsoleAccessActionEnvelope> {
    return postAccessAction("user-blacklist", "remove", item, revision, signal);
  },

  async getSettings(signal?: AbortSignal): Promise<OwnerConsoleSettingsEnvelope> {
    const envelope = await getJson<OwnerConsoleSettingsEnvelope>(
      `${API_BASE}/settings`,
      signal,
    );
    const contract = checkOwnerConsoleEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async getTasks(
    params: {
      status?: string | null;
      work_type?: string | null;
      category?: string | null;
      page?: number;
      page_size?: number;
      limit?: number;
    },
    signal?: AbortSignal,
  ): Promise<OwnerConsoleTaskListEnvelope> {
    const envelope = await getJson<OwnerConsoleTaskListEnvelope>(
      `${API_BASE}/tasks${buildQuery(params)}`,
      signal,
    );
    const contract = checkOwnerConsoleEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async getTaskDetail(
    taskId: number,
    params: { event_limit: number; preview_limit: number },
    signal?: AbortSignal,
  ): Promise<OwnerConsoleTaskDetailEnvelope> {
    const envelope = await getJson<OwnerConsoleTaskDetailEnvelope>(
      `${API_BASE}/tasks/${taskId}${buildQuery(params)}`,
      signal,
    );
    const contract = checkOwnerConsoleEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async cancelTask(
    taskId: number,
    signal?: AbortSignal,
  ): Promise<OwnerConsoleTaskActionEnvelope> {
    if (!Number.isSafeInteger(taskId) || taskId < 1) {
      throw new Error("任务 ID 无效");
    }
    const envelope = await postJson<OwnerConsoleTaskActionEnvelope>(
      `${API_BASE}/tasks/${taskId}/cancel`,
      { confirmation: "cancel_single_pending_task" },
      { "X-Owner-Console-Action": "task-cancel-v1" },
      signal,
    );
    const contract = checkOwnerConsoleTaskActionEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async getApprovals(
    params: { status?: string | null; limit: number },
    signal?: AbortSignal,
  ): Promise<OwnerConsoleApprovalListEnvelope> {
    const envelope = await getJson<OwnerConsoleApprovalListEnvelope>(
      `${API_BASE}/approvals${buildQuery(params)}`,
      signal,
    );
    const contract = checkOwnerConsoleEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async getApprovalDetail(
    approvalId: number,
    params: { event_limit: number; preview_limit: number },
    signal?: AbortSignal,
  ): Promise<OwnerConsoleApprovalDetailEnvelope> {
    const envelope = await getJson<OwnerConsoleApprovalDetailEnvelope>(
      `${API_BASE}/approvals/${approvalId}${buildQuery(params)}`,
      signal,
    );
    const contract = checkOwnerConsoleEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async approveApproval(
    approvalId: number,
    signal?: AbortSignal,
  ): Promise<OwnerConsoleApprovalActionEnvelope> {
    const envelope = await postJson<OwnerConsoleApprovalActionEnvelope>(
      `${API_BASE}/approvals/${approvalId}/approve`,
      { confirmation: "approve_registered_pending_approval" },
      { "X-Owner-Console-Action": "approval-approve-v1" },
      signal,
    );
    const contract = checkOwnerConsoleApprovalActionEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },

  async rejectApproval(
    approvalId: number,
    signal?: AbortSignal,
  ): Promise<OwnerConsoleApprovalActionEnvelope> {
    const envelope = await postJson<OwnerConsoleApprovalActionEnvelope>(
      `${API_BASE}/approvals/${approvalId}/reject`,
      { confirmation: "reject_registered_pending_approval" },
      { "X-Owner-Console-Action": "approval-reject-v1" },
      signal,
    );
    const contract = checkOwnerConsoleApprovalActionEnvelope(envelope);
    if (!contract.ok) {
      throw new Error(contract.message);
    }
    return envelope;
  },
};
