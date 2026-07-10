import { OwnerConsoleApiError } from "../api/ownerConsoleApi";
import type { AutoRefreshErrorDisposition } from "../hooks/useControlledAutoRefresh";

export const OWNER_CONSOLE_HEALTH_REFRESH_INTERVAL_MS = 60_000;
export const OWNER_CONSOLE_PAGE_REFRESH_INTERVAL_MS = 30_000;
export const OWNER_CONSOLE_AUTO_REFRESH_FAILURE_LIMIT = 3;
export const OWNER_CONSOLE_VISIBILITY_RESUME_DELAY_MS = 1_000;

export function isAbortError(error: unknown): boolean {
  return (
    error instanceof DOMException && error.name === "AbortError"
  ) || (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    error.name === "AbortError"
  );
}

export function classifyOwnerConsoleAutoRefreshError(
  error: unknown,
): AutoRefreshErrorDisposition {
  if (isAbortError(error)) {
    return "abort";
  }

  if (error instanceof OwnerConsoleApiError) {
    return [400, 403, 404].includes(error.status) ? "terminal" : "transient";
  }

  return error instanceof TypeError ? "transient" : "terminal";
}
