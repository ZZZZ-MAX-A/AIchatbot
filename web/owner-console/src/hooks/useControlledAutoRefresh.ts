import { useCallback, useEffect, useRef, useState } from "react";

export type AutoRefreshReason = "auto" | "visibility_resume";
export type AutoRefreshErrorDisposition = "abort" | "transient" | "terminal";
export type AutoRefreshStatus =
  | "disabled"
  | "waiting"
  | "refreshing"
  | "paused_hidden"
  | "paused_error";

type AutoRefreshSnapshot = {
  status: AutoRefreshStatus;
  consecutiveFailures: number;
  lastSuccessfulAt: Date | null;
  lastError: Error | null;
};

type UseControlledAutoRefreshOptions = {
  enabled: boolean;
  intervalMs: number;
  refresh: (signal: AbortSignal, reason: AutoRefreshReason) => Promise<void>;
  classifyError: (error: unknown) => AutoRefreshErrorDisposition;
  failureLimit?: number;
  visibilityResumeDelayMs?: number;
};

export type ControlledAutoRefresh = AutoRefreshSnapshot & {
  beginManualRefresh: () => boolean;
  finishManualRefresh: (succeeded: boolean) => void;
  resetAfterManualSuccess: () => void;
};

function isPageVisible(): boolean {
  return typeof document === "undefined" || document.visibilityState === "visible";
}

function toError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}

export function useControlledAutoRefresh({
  enabled,
  intervalMs,
  refresh,
  classifyError,
  failureLimit = 3,
  visibilityResumeDelayMs = 1_000,
}: UseControlledAutoRefreshOptions): ControlledAutoRefresh {
  const [snapshot, setSnapshot] = useState<AutoRefreshSnapshot>(() => ({
    status: enabled
      ? isPageVisible()
        ? "waiting"
        : "paused_hidden"
      : "disabled",
    consecutiveFailures: 0,
    lastSuccessfulAt: null,
    lastError: null,
  }));

  const mountedRef = useRef(true);
  const enabledRef = useRef(enabled);
  const refreshRef = useRef(refresh);
  const classifyErrorRef = useRef(classifyError);
  const timerRef = useRef<number | null>(null);
  const nextDueAtRef = useRef<number | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const requestInFlightRef = useRef(false);
  const manualRefreshInFlightRef = useRef(false);
  const failureCountRef = useRef(0);
  const failurePausedRef = useRef(false);
  const runRefreshRef = useRef<
    (reason: AutoRefreshReason) => Promise<void>
  >(async () => undefined);

  enabledRef.current = enabled;
  refreshRef.current = refresh;
  classifyErrorRef.current = classifyError;

  const updateSnapshot = useCallback(
    (update: (current: AutoRefreshSnapshot) => AutoRefreshSnapshot) => {
      if (mountedRef.current) {
        setSnapshot(update);
      }
    },
    [],
  );

  const clearTimer = useCallback((preserveDueAt = false) => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (!preserveDueAt) {
      nextDueAtRef.current = null;
    }
  }, []);

  const abortCurrentRefresh = useCallback(() => {
    controllerRef.current?.abort();
  }, []);

  const schedule = useCallback(
    (delayMs: number, reason: AutoRefreshReason) => {
      clearTimer();
      if (
        !enabledRef.current ||
        failurePausedRef.current ||
        manualRefreshInFlightRef.current ||
        !isPageVisible()
      ) {
        return;
      }

      const safeDelayMs = Math.max(0, delayMs);
      nextDueAtRef.current = Date.now() + safeDelayMs;
      timerRef.current = window.setTimeout(() => {
        timerRef.current = null;
        nextDueAtRef.current = null;
        void runRefreshRef.current(reason);
      }, safeDelayMs);
      updateSnapshot((current) => ({ ...current, status: "waiting" }));
    },
    [clearTimer, updateSnapshot],
  );

  const runRefresh = useCallback(
    async (reason: AutoRefreshReason) => {
      if (
        !enabledRef.current ||
        failurePausedRef.current ||
        manualRefreshInFlightRef.current ||
        requestInFlightRef.current
      ) {
        return;
      }
      if (!isPageVisible()) {
        updateSnapshot((current) => ({
          ...current,
          status: "paused_hidden",
        }));
        return;
      }

      clearTimer();
      const controller = new AbortController();
      controllerRef.current = controller;
      requestInFlightRef.current = true;
      updateSnapshot((current) => ({ ...current, status: "refreshing" }));

      try {
        await refreshRef.current(controller.signal, reason);
        if (controller.signal.aborted) {
          return;
        }
        failureCountRef.current = 0;
        failurePausedRef.current = false;
        updateSnapshot((current) => ({
          ...current,
          status: "waiting",
          consecutiveFailures: 0,
          lastSuccessfulAt: new Date(),
          lastError: null,
        }));
      } catch (error) {
        const disposition = controller.signal.aborted
          ? "abort"
          : classifyErrorRef.current(error);
        if (disposition === "abort") {
          return;
        }

        const nextFailureCount = failureCountRef.current + 1;
        failureCountRef.current = nextFailureCount;
        failurePausedRef.current =
          disposition === "terminal" || nextFailureCount >= failureLimit;
        updateSnapshot((current) => ({
          ...current,
          status: failurePausedRef.current ? "paused_error" : "waiting",
          consecutiveFailures: nextFailureCount,
          lastError: toError(error),
        }));
      } finally {
        requestInFlightRef.current = false;
        if (controllerRef.current === controller) {
          controllerRef.current = null;
        }
        if (!mountedRef.current) {
          return;
        }
        if (!enabledRef.current) {
          updateSnapshot((current) => ({ ...current, status: "disabled" }));
        } else if (failurePausedRef.current) {
          updateSnapshot((current) => ({
            ...current,
            status: "paused_error",
          }));
        } else if (!isPageVisible()) {
          updateSnapshot((current) => ({
            ...current,
            status: "paused_hidden",
          }));
        } else {
          schedule(intervalMs, "auto");
        }
      }
    },
    [clearTimer, failureLimit, intervalMs, schedule, updateSnapshot],
  );

  runRefreshRef.current = runRefresh;

  const resetAfterManualSuccess = useCallback(() => {
    failureCountRef.current = 0;
    failurePausedRef.current = false;
    updateSnapshot((current) => ({
      ...current,
      status: enabledRef.current
        ? isPageVisible()
          ? "waiting"
          : "paused_hidden"
        : "disabled",
      consecutiveFailures: 0,
      lastSuccessfulAt: new Date(),
      lastError: null,
    }));

    if (enabledRef.current && isPageVisible()) {
      schedule(intervalMs, "auto");
    } else {
      clearTimer();
    }
  }, [clearTimer, intervalMs, schedule, updateSnapshot]);

  const beginManualRefresh = useCallback(() => {
    if (requestInFlightRef.current || manualRefreshInFlightRef.current) {
      return false;
    }
    manualRefreshInFlightRef.current = true;
    clearTimer();
    return true;
  }, [clearTimer]);

  const finishManualRefresh = useCallback(
    (succeeded: boolean) => {
      if (!manualRefreshInFlightRef.current) {
        return;
      }
      manualRefreshInFlightRef.current = false;
      if (succeeded) {
        resetAfterManualSuccess();
      } else if (
        enabledRef.current &&
        !failurePausedRef.current &&
        isPageVisible()
      ) {
        schedule(intervalMs, "auto");
      }
    },
    [intervalMs, resetAfterManualSuccess, schedule],
  );

  useEffect(() => {
    clearTimer();
    if (!enabled) {
      abortCurrentRefresh();
      manualRefreshInFlightRef.current = false;
      failureCountRef.current = 0;
      failurePausedRef.current = false;
      updateSnapshot((current) => ({
        ...current,
        status: "disabled",
        consecutiveFailures: 0,
        lastError: null,
      }));
      return;
    }

    failureCountRef.current = 0;
    failurePausedRef.current = false;
    updateSnapshot((current) => ({
      ...current,
      status: isPageVisible() ? "waiting" : "paused_hidden",
      consecutiveFailures: 0,
      lastError: null,
    }));
    if (isPageVisible()) {
      schedule(intervalMs, "auto");
    }
  }, [
    abortCurrentRefresh,
    clearTimer,
    enabled,
    intervalMs,
    schedule,
    updateSnapshot,
  ]);

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }

    const handleVisibilityChange = () => {
      if (!enabledRef.current) {
        return;
      }

      if (!isPageVisible()) {
        if (nextDueAtRef.current === null) {
          nextDueAtRef.current = Date.now();
        }
        clearTimer(true);
        abortCurrentRefresh();
        updateSnapshot((current) => ({
          ...current,
          status: "paused_hidden",
        }));
        return;
      }

      if (failurePausedRef.current) {
        updateSnapshot((current) => ({
          ...current,
          status: "paused_error",
        }));
        return;
      }

      const nextDueAt = nextDueAtRef.current;
      const remainingMs = nextDueAt === null ? intervalMs : nextDueAt - Date.now();
      schedule(
        remainingMs <= 0 ? visibilityResumeDelayMs : remainingMs,
        remainingMs <= 0 ? "visibility_resume" : "auto",
      );
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [
    abortCurrentRefresh,
    clearTimer,
    intervalMs,
    schedule,
    updateSnapshot,
    visibilityResumeDelayMs,
  ]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      manualRefreshInFlightRef.current = false;
      clearTimer();
      abortCurrentRefresh();
    };
  }, [abortCurrentRefresh, clearTimer]);

  return {
    ...snapshot,
    beginManualRefresh,
    finishManualRefresh,
    resetAfterManualSuccess,
  };
}
