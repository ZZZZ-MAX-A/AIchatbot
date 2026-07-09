import {
  OWNER_CONSOLE_API_PREFIX,
  checkOwnerConsoleEnvelope,
} from "./ownerConsoleEnvelope";
import type {
  OwnerConsoleHealth,
  OwnerConsoleRoutesEnvelope,
} from "./ownerConsoleTypes";

const API_BASE =
  import.meta.env.VITE_OWNER_CONSOLE_API_BASE ?? OWNER_CONSOLE_API_PREFIX;
const HEALTH_PATH = import.meta.env.VITE_OWNER_CONSOLE_HEALTH_PATH ?? "/healthz";

const allowedPaths = new Set([
  HEALTH_PATH,
  `${API_BASE}/routes`,
]);

async function getJson<TResponse>(
  path: string,
  signal?: AbortSignal,
): Promise<TResponse> {
  if (!allowedPaths.has(path)) {
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
    throw new Error(`请求失败：HTTP ${response.status}`);
  }
  return payload;
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
};
