import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { alternateMemoryScope, defaultMemoryScope, memoryEnvelope, memoryScopeSettings } from "../testFixtures/memoryScope";
import type { OwnerConsoleMemoryEnvelope } from "../api/ownerConsoleTypes";
import { MemoryPage } from "./MemoryPage";

const api = vi.hoisted(() => ({ getSettings: vi.fn(), getMemory: vi.fn() }));
vi.mock("../api/ownerConsoleApi", () => ({ OwnerConsoleApiError: class extends Error {}, ownerConsoleApi: api }));
beforeEach(() => {
  api.getSettings.mockResolvedValue(memoryScopeSettings);
  api.getMemory.mockImplementation((_signal, scope) => Promise.resolve(memoryEnvelope(scope, scope.persona_id === "aike" ? 111 : 222)));
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

describe("MemoryPage fixed-account scope", () => {
  it("uses the selected account library for labels and statistics", async () => {
    render(<MemoryRouter><MemoryPage /></MemoryRouter>);
    expect(within(await screen.findByLabelText("记忆计数")).getByText("111")).toBeTruthy();
    expect(api.getMemory).toHaveBeenLastCalledWith(expect.any(AbortSignal), defaultMemoryScope);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: alternateMemoryScope.bot_self_id } });
    const counts = await screen.findByLabelText("记忆计数");
    await waitFor(() => expect(within(counts).getByText("222")).toBeTruthy());
    expect(api.getMemory).toHaveBeenLastCalledWith(expect.any(AbortSignal), alternateMemoryScope);
    expect(screen.queryByText("111")).toBeNull();
    expect(screen.getByText(alternateMemoryScope.database)).toBeTruthy();
  });

  it("aborts an old account read and ignores its late response", async () => {
    let finish: (value: OwnerConsoleMemoryEnvelope) => void = () => {};
    api.getMemory.mockImplementationOnce(() => new Promise<OwnerConsoleMemoryEnvelope>((resolve) => { finish = resolve; }));
    render(<MemoryRouter><MemoryPage /></MemoryRouter>);
    await waitFor(() => expect(api.getMemory).toHaveBeenCalledTimes(1));
    const signal = api.getMemory.mock.calls[0][0] as AbortSignal;
    fireEvent.change(screen.getByRole("combobox"), { target: { value: alternateMemoryScope.bot_self_id } });
    await waitFor(() => expect(within(screen.getByLabelText("记忆计数")).getByText("222")).toBeTruthy());
    expect(signal.aborted).toBe(true);
    await act(async () => finish(memoryEnvelope(defaultMemoryScope, 111)));
    expect(screen.queryByText("111")).toBeNull();
    expect(within(screen.getByLabelText("记忆计数")).getByText("222")).toBeTruthy();
  });

  it.each(["unbound", "2000000001"])("does not fall back from an unknown or unavailable URL account %s", async (account) => {
    if (account === "2000000001") api.getSettings.mockResolvedValue({ data: { account_personas: [
      { ...memoryScopeSettings.data.account_personas[0], memory: { storage: "legacy_database", maintenance_scope: null } },
      memoryScopeSettings.data.account_personas[1],
    ] } });
    render(<MemoryRouter initialEntries={[`/memory?memory_account=${account}`]}><MemoryPage /></MemoryRouter>);
    await screen.findByRole("alert");
    expect(api.getMemory).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("记忆计数")).toBeNull();
  });

  it("rejects a response for a different persona", async () => {
    api.getMemory.mockResolvedValue(memoryEnvelope(alternateMemoryScope, 222));
    render(<MemoryRouter><MemoryPage /></MemoryRouter>);
    await screen.findByText("记忆快照范围与当前账号不一致，请刷新绑定。");
    expect(screen.queryByLabelText("记忆计数")).toBeNull();
  });
});
