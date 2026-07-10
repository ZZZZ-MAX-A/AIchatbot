import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OwnerConsoleApiError } from "../api/ownerConsoleApi";
import {
  classifyOwnerConsoleAutoRefreshError,
  isAbortError,
} from "../app/ownerConsoleRefreshPolicy";
import { useControlledAutoRefresh } from "./useControlledAutoRefresh";
import type {
  AutoRefreshErrorDisposition,
  AutoRefreshReason,
} from "./useControlledAutoRefresh";

const INTERVAL_MS = 1_000;
const RESUME_DELAY_MS = 100;

let visibilityState: DocumentVisibilityState;

function setVisibility(state: DocumentVisibilityState) {
  visibilityState = state;
  document.dispatchEvent(new Event("visibilitychange"));
}

async function advanceTimersByTime(milliseconds: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(milliseconds);
  });
}

function renderAutoRefresh({
  enabled = true,
  refresh = vi.fn<
    (signal: AbortSignal, reason: AutoRefreshReason) => Promise<void>
  >().mockResolvedValue(undefined),
  classifyError = () => "transient" as AutoRefreshErrorDisposition,
}: {
  enabled?: boolean;
  refresh?: (
    signal: AbortSignal,
    reason: AutoRefreshReason,
  ) => Promise<void>;
  classifyError?: (error: unknown) => AutoRefreshErrorDisposition;
} = {}) {
  return renderHook(
    ({ active }) =>
      useControlledAutoRefresh({
        enabled: active,
        intervalMs: INTERVAL_MS,
        refresh,
        classifyError,
        failureLimit: 3,
        visibilityResumeDelayMs: RESUME_DELAY_MS,
      }),
    { initialProps: { active: enabled } },
  );
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-07-11T00:00:00Z"));
  visibilityState = "visible";
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    get: () => visibilityState,
  });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  Reflect.deleteProperty(document, "visibilityState");
});

describe("useControlledAutoRefresh", () => {
  it("does not schedule while disabled", async () => {
    const refresh = vi.fn().mockResolvedValue(undefined);
    const { result } = renderAutoRefresh({ enabled: false, refresh });

    expect(result.current.status).toBe("disabled");
    expect(vi.getTimerCount()).toBe(0);
    await advanceTimersByTime(INTERVAL_MS * 2);
    expect(refresh).not.toHaveBeenCalled();
  });

  it("runs once per completion-based interval", async () => {
    const refresh = vi.fn().mockResolvedValue(undefined);
    const { result } = renderAutoRefresh({ refresh });

    await advanceTimersByTime(INTERVAL_MS - 1);
    expect(refresh).not.toHaveBeenCalled();

    await advanceTimersByTime(1);
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(refresh.mock.calls[0]?.[1]).toBe("auto");
    expect(result.current.status).toBe("waiting");
    expect(result.current.lastSuccessfulAt).toEqual(
      new Date("2026-07-11T00:00:01Z"),
    );

    await advanceTimersByTime(INTERVAL_MS);
    expect(refresh).toHaveBeenCalledTimes(2);
  });

  it("never overlaps a slow refresh", async () => {
    let resolveRefresh: (() => void) | null = null;
    const refresh = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveRefresh = resolve;
        }),
    );
    const { result } = renderAutoRefresh({ refresh });

    await advanceTimersByTime(INTERVAL_MS);
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(result.current.status).toBe("refreshing");

    await advanceTimersByTime(INTERVAL_MS * 5);
    expect(refresh).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveRefresh?.();
      await Promise.resolve();
    });
    expect(result.current.status).toBe("waiting");

    await advanceTimersByTime(INTERVAL_MS);
    expect(refresh).toHaveBeenCalledTimes(2);
  });

  it("pauses while hidden and catches up at most once", async () => {
    const refresh = vi.fn().mockResolvedValue(undefined);
    const { result } = renderAutoRefresh({ refresh });

    act(() => setVisibility("hidden"));
    expect(result.current.status).toBe("paused_hidden");
    await advanceTimersByTime(INTERVAL_MS * 5);
    expect(refresh).not.toHaveBeenCalled();

    act(() => setVisibility("visible"));
    await advanceTimersByTime(RESUME_DELAY_MS - 1);
    expect(refresh).not.toHaveBeenCalled();

    await advanceTimersByTime(1);
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(refresh.mock.calls[0]?.[1]).toBe("visibility_resume");
  });

  it("pauses after three transient failures without immediate retries", async () => {
    const refresh = vi.fn().mockRejectedValue(new TypeError("offline"));
    const { result } = renderAutoRefresh({
      refresh,
      classifyError: classifyOwnerConsoleAutoRefreshError,
    });

    await advanceTimersByTime(INTERVAL_MS);
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(result.current.consecutiveFailures).toBe(1);
    expect(result.current.status).toBe("waiting");

    await advanceTimersByTime(INTERVAL_MS);
    expect(refresh).toHaveBeenCalledTimes(2);
    expect(result.current.consecutiveFailures).toBe(2);

    await advanceTimersByTime(INTERVAL_MS);
    expect(refresh).toHaveBeenCalledTimes(3);
    expect(result.current.consecutiveFailures).toBe(3);
    expect(result.current.status).toBe("paused_error");

    await advanceTimersByTime(INTERVAL_MS * 5);
    expect(refresh).toHaveBeenCalledTimes(3);
  });

  it("pauses immediately for a terminal failure and resets after manual success", async () => {
    const refresh = vi
      .fn()
      .mockRejectedValueOnce(new Error("contract mismatch"))
      .mockResolvedValue(undefined);
    const { result } = renderAutoRefresh({
      refresh,
      classifyError: () => "terminal",
    });

    await advanceTimersByTime(INTERVAL_MS);
    expect(result.current.status).toBe("paused_error");
    expect(result.current.consecutiveFailures).toBe(1);

    act(() => result.current.resetAfterManualSuccess());
    expect(result.current.status).toBe("waiting");
    expect(result.current.consecutiveFailures).toBe(0);
    expect(result.current.lastError).toBeNull();

    await advanceTimersByTime(INTERVAL_MS);
    expect(refresh).toHaveBeenCalledTimes(2);
    expect(result.current.status).toBe("waiting");
  });

  it("suspends automatic scheduling during a manual refresh", async () => {
    const refresh = vi.fn().mockResolvedValue(undefined);
    const { result } = renderAutoRefresh({ refresh });

    expect(result.current.beginManualRefresh()).toBe(true);
    await advanceTimersByTime(INTERVAL_MS * 2);
    expect(refresh).not.toHaveBeenCalled();

    act(() => result.current.finishManualRefresh(true));
    await advanceTimersByTime(INTERVAL_MS);
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("refuses a manual refresh while an automatic request is active", async () => {
    const refresh = vi.fn(() => new Promise<void>(() => undefined));
    const { result, unmount } = renderAutoRefresh({ refresh });

    await advanceTimersByTime(INTERVAL_MS);
    expect(result.current.status).toBe("refreshing");
    expect(result.current.beginManualRefresh()).toBe(false);
    unmount();
  });

  it("aborts an active refresh when the page becomes hidden", async () => {
    const activeSignals: AbortSignal[] = [];
    const refresh = vi.fn(
      (signal: AbortSignal) =>
        new Promise<void>((_resolve, reject) => {
          activeSignals.push(signal);
          signal.addEventListener("abort", () => {
            reject(new DOMException("aborted", "AbortError"));
          });
        }),
    );
    const { result } = renderAutoRefresh({
      refresh,
      classifyError: classifyOwnerConsoleAutoRefreshError,
    });

    await advanceTimersByTime(INTERVAL_MS);
    expect(result.current.status).toBe("refreshing");

    await act(async () => {
      setVisibility("hidden");
      await Promise.resolve();
    });
    expect(activeSignals[0]?.aborted).toBe(true);
    expect(result.current.status).toBe("paused_hidden");
    expect(result.current.consecutiveFailures).toBe(0);
  });

  it("aborts and clears state when disabled", async () => {
    const activeSignals: AbortSignal[] = [];
    const refresh = vi.fn(
      (signal: AbortSignal) =>
        new Promise<void>((_resolve, reject) => {
          activeSignals.push(signal);
          signal.addEventListener("abort", () => {
            reject(new DOMException("aborted", "AbortError"));
          });
        }),
    );
    const { result, rerender } = renderAutoRefresh({ refresh });

    await advanceTimersByTime(INTERVAL_MS);
    rerender({ active: false });
    await act(async () => Promise.resolve());

    expect(activeSignals[0]?.aborted).toBe(true);
    expect(result.current.status).toBe("disabled");
    expect(result.current.consecutiveFailures).toBe(0);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("aborts an active refresh when unmounted", async () => {
    const activeSignals: AbortSignal[] = [];
    const refresh = vi.fn(
      (signal: AbortSignal) =>
        new Promise<void>((_resolve, reject) => {
          activeSignals.push(signal);
          signal.addEventListener("abort", () => {
            reject(new DOMException("aborted", "AbortError"));
          });
        }),
    );
    const { unmount } = renderAutoRefresh({ refresh });

    await advanceTimersByTime(INTERVAL_MS);
    unmount();
    await act(async () => Promise.resolve());

    expect(activeSignals[0]?.aborted).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("owner console auto-refresh error classification", () => {
  it("distinguishes abort, terminal HTTP, transient HTTP and network errors", () => {
    expect(isAbortError(new DOMException("aborted", "AbortError"))).toBe(true);
    for (const status of [400, 403, 404]) {
      expect(
        classifyOwnerConsoleAutoRefreshError(
          new OwnerConsoleApiError("terminal", {
            status,
            code: "terminal",
            details: null,
          }),
        ),
      ).toBe("terminal");
    }
    expect(
      classifyOwnerConsoleAutoRefreshError(
        new OwnerConsoleApiError("server", {
          status: 500,
          code: "internal_error",
          details: null,
        }),
      ),
    ).toBe("transient");
    expect(classifyOwnerConsoleAutoRefreshError(new TypeError("offline"))).toBe(
      "transient",
    );
    expect(classifyOwnerConsoleAutoRefreshError(new Error("contract"))).toBe(
      "terminal",
    );
  });
});
