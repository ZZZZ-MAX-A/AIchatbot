import {
  OWNER_CONSOLE_API_PREFIX,
  checkOwnerConsoleEnvelope,
} from "./ownerConsoleEnvelope";
import type {
  OwnerConsoleDiagnosticsEnvelope,
  OwnerConsoleHealth,
  OwnerConsoleOverviewEnvelope,
  OwnerConsoleRoutesEnvelope,
} from "./ownerConsoleTypes";

const API_BASE =
  import.meta.env.VITE_OWNER_CONSOLE_API_BASE ?? OWNER_CONSOLE_API_PREFIX;
const HEALTH_PATH = import.meta.env.VITE_OWNER_CONSOLE_HEALTH_PATH ?? "/healthz";

const allowedPaths = new Set([
  HEALTH_PATH,
  `${API_BASE}/routes`,
  `${API_BASE}/overview`,
  `${API_BASE}/diagnostics`,
]);

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
  if (!allowedPaths.has(routePath)) {
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
};
