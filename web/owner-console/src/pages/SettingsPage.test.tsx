import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SettingsPage } from "./SettingsPage";

const api = vi.hoisted(() => ({ getSettings: vi.fn() }));
vi.mock("../api/ownerConsoleApi", () => ({
  OwnerConsoleApiError: class extends Error {}, ownerConsoleApi: api,
}));
afterEach(cleanup);

describe("fixed account persona settings", () => {
  it("shows separate fixed cards, models, storage and an unavailable binding", async () => {
    const model = { model_name: "default-model", base_url_redacted: "", api_key_configured: true, timeout_seconds: 60 };
    api.getSettings.mockResolvedValue({ web_write_enabled: false, data: {
      generated_at: "test", chat_model: model, main_agent_model: model, embedding: model,
      active_role_card_key: "aike", role_cards: [], feature_flags: {}, boundary: {},
      persona_bindings: { fixed_binding: true, ready: false, errors: [], rows: [
        { account_label: "账号 1", persona_id: "aike", role_card_key: "aike", role_card_available: true,
          chat_model: "default-model", chat_route: "legacy", memory_mode: "legacy", ready: true, errors: [] },
        { account_label: "账号 2", persona_id: "linyin", role_card_key: "linyin", role_card_available: false,
          chat_model: "persona-model", chat_route: "persona", memory_mode: "invalid", ready: false, errors: ["missing_role_card"] },
      ] },
    } });
    render(<SettingsPage />);
    expect(await screen.findByText("账号 1 · aike")).toBeTruthy();
    expect(screen.getByText("账号 2 · linyin")).toBeTruthy();
    expect(screen.getByText("聊天模型：persona-model")).toBeTruthy();
    expect(screen.getByText("记忆：现有默认记忆库")).toBeTruthy();
    expect(screen.getByText("记忆：配置异常，操作已阻止")).toBeTruthy();
    expect(screen.getByText("角色卡：linyin · 不可用")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /切换|选择角色卡/ })).toBeNull();
  });
});
