import {
  OWNER_CONSOLE_API_PREFIX,
  checkOwnerConsoleActionEnvelope,
  checkOwnerConsoleEnvelope,
} from "./ownerConsoleEnvelope";
import type {
  OwnerConsoleAccessControlEnvelope,
  OwnerConsoleApprovalDetailEnvelope,
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
  OwnerConsoleTaskDetailEnvelope,
  OwnerConsoleTaskListEnvelope,
} from "./ownerConsoleTypes";

const API_BASE =
  import.meta.env.VITE_OWNER_CONSOLE_API_BASE ?? OWNER_CONSOLE_API_PREFIX;
const HEALTH_PATH = import.meta.env.VITE_OWNER_CONSOLE_HEALTH_PATH ?? "/healthz";

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
  `${API_BASE}/tasks`,
  `${API_BASE}/approvals`,
]);

const allowedPostPaths = new Set([
  `${API_BASE}/manual-diagnostics/project-doc-rag`,
  `${API_BASE}/manual-diagnostics/memory-rag-consistency`,
  `${API_BASE}/manual-diagnostics/main-llm-contract`,
]);

function isAllowedGetPath(routePath: string): boolean {
  if (allowedGetPaths.has(routePath)) {
    return true;
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
  body: Record<string, string>,
  headers: Record<string, string>,
  signal?: AbortSignal,
): Promise<TResponse> {
  const routePath = path.split("?")[0];
  if (!allowedPostPaths.has(routePath)) {
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

export const ownerConsoleApi = {
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
  ): Promise<OwnerConsoleDiagnosticsEnvelope> {
    const envelope = await getJson<OwnerConsoleDiagnosticsEnvelope>(
      `${API_BASE}/diagnostics`,
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
  ): Promise<OwnerConsoleManualDiagnosticsEnvelope> {
    const envelope = await getJson<OwnerConsoleManualDiagnosticsEnvelope>(
      `${API_BASE}/manual-diagnostics`,
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
  ): Promise<OwnerConsoleMemoryRagConsistencyEnvelope> {
    const envelope = await postJson<OwnerConsoleMemoryRagConsistencyEnvelope>(
      `${API_BASE}/manual-diagnostics/memory-rag-consistency`,
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

  async getMemory(signal?: AbortSignal): Promise<OwnerConsoleMemoryEnvelope> {
    const envelope = await getJson<OwnerConsoleMemoryEnvelope>(
      `${API_BASE}/memory`,
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
    params: { status?: string | null; work_type?: string | null; limit: number },
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
};
