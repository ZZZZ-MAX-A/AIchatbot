import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AccountPersonaProfile } from "../api/accountPersonaTypes";
import { AccountPersonaPanel } from "./AccountPersonaPanel";

const api = vi.hoisted(() => ({ getPersonaVoiceSample: vi.fn() }));
vi.mock("../api/ownerConsoleApi", () => ({ ownerConsoleApi: api }));

function profile(persona: "aike" | "linyin"): AccountPersonaProfile {
  const linyin = persona === "linyin";
  const model = { model_name: linyin ? "persona-chat" : "default-chat", provider: "openai",
    source: linyin ? "PERSONA_LLM_*" : "AIKE_LLM_*", base_url_redacted: "https://example/v1",
    api_key_configured: true, timeout_seconds: 60, configured: true, errors: [] };
  return {
    account_label: linyin ? "账号 2" : "账号 1", bot_self_id: linyin ? "3000000001" : "2000000001",
    persona_id: persona, persona_name: linyin ? "凛音" : "爱可", role_card_key: persona,
    role_card_available: true, ready: true, errors: [], chat_model: model,
    vision_model: { ...model, model_name: linyin ? "persona-vision" : "default-vision" },
    voice: { voice_id: `${persona}-voice`, emotion: "soft", source: "TTS_*", enabled: true,
      sample_available: true, sample_kind: "reference", trim_trailing_noise: linyin,
      service_url_redacted: "http://127.0.0.1:7861", timeout_seconds: 180, max_chars: 260,
      max_total_seconds: 60, cooldown_seconds: 20 },
    memory: { mode: linyin ? "persona_v2_persistent" : "legacy", storage: linyin ? "persona_database" : "legacy_database",
      database: linyin ? "data/persona-memory/linyin.db" : "data/chatbot.db", file_exists: true,
      health_checked: false, session_namespace: linyin ? "persona:linyin:" : "private:/group:",
      summary_model: { ...model, model_name: "summary", source: "SUMMARY_LLM_*" }, embedding_model: "embedding" },
    scene: { assigned: true, actor_model: { ...model, model_name: "default-chat", source: "AIKE_LLM_*" },
      director_model: "director", style_examples_status: "loaded", ordinary_world_card_injection: linyin },
    capabilities: [{ key: "encyclopedia", label: "百科查询", state: "enabled", detail: "百科能力说明" },
      { key: "stickers", label: "表情包", state: linyin ? "unsupported" : "enabled", detail: "表情能力说明" }],
    parameters: { temperature: 0.8, vision_private_image_wait_seconds: 5, memory_rag_top_k: 4,
      memory_rag_max_context_chars: 1600, sticker_cooldown_seconds: 120, sticker_max_per_hour: 6,
      sticker_classifier_model: linyin ? "" : "classifier", image_generation_model: "image-gen", image_edit_model: "image-edit", weather_mode: "auto" },
  };
}

beforeEach(() => {
  api.getPersonaVoiceSample.mockReset();
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: vi.fn(() => "blob:voice-test"), revokeObjectURL: vi.fn() }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("account persona configuration", () => {
  it("shows DeepSeek vision parameters separately from the persona chat model", () => {
    const p = profile("linyin");
    p.vision_model = { ...p.vision_model, model_name: "deepseek-flash", provider: "persona_deepseek",
      max_tokens: 4096, reasoning_effort: "max", reasoning_effort_source: "PERSONA_VISION_REASONING_EFFORT" };
    render(<AccountPersonaPanel profiles={[p]} />);
    const vision = screen.getByRole("heading", { name: "视觉模型" }).closest("section")!;
    expect(within(vision).getByText("DeepSeek 图片识别接口")).toBeTruthy();
    expect(within(vision).getByText("deepseek-flash")).toBeTruthy();
    expect(within(vision).getByText(/4096 token/)).toBeTruthy();
    expect(within(vision).getByText("max（最高）")).toBeTruthy();
    expect(screen.getByText("persona-chat")).toBeTruthy();
  });
  it("shows global binding errors even when no account survived parsing", () => {
    render(<AccountPersonaPanel profiles={[]} bindingErrors={["invalid_bindings"]} />);
    expect(screen.getByRole("alert").textContent).toContain("invalid_bindings");
    expect(screen.getByText("未配置账号绑定")).toBeTruthy();
  });
  it("keeps account, memory, both models, voice and capability differences together", () => {
    render(<AccountPersonaPanel profiles={[profile("aike"), profile("linyin")]} />);
    const a = within(screen.getByRole("article", { name: "爱可账号配置" }));
    const b = within(screen.getByRole("article", { name: "凛音账号配置" }));
    expect(a.getByText("账号：2000000001")).toBeTruthy();
    expect(b.getByText("账号：3000000001")).toBeTruthy();
    expect(a.getByText("data/chatbot.db")).toBeTruthy();
    expect(b.getByText("data/persona-memory/linyin.db")).toBeTruthy();
    expect(a.getByText("default-vision")).toBeTruthy();
    expect(b.getByText("persona-chat")).toBeTruthy();
    expect(b.getByText("persona-vision")).toBeTruthy();
    expect(b.getByText("linyin-voice")).toBeTruthy();
    expect(b.getAllByText("尚未接入")).toHaveLength(1);
    expect(b.getAllByText("已启用").length).toBeGreaterThan(1);
    expect(a.getAllByText("已启用").length).toBeGreaterThan(1);
    expect(screen.queryByText(/MainAgent/)).toBeNull();
  });

  it("shows chat effort and scene overrides without assigning effort to vision", () => {
    const aike = profile("aike"), linyin = profile("linyin");
    Object.assign(aike.chat_model, { reasoning_effort: "max", reasoning_effort_source: "AIKE_LLM_REASONING_EFFORT" });
    Object.assign(aike.scene.actor_model, { reasoning_effort: "max", reasoning_effort_source: "AIKE_LLM_REASONING_EFFORT" });
    Object.assign(linyin.chat_model, { reasoning_effort: null, reasoning_effort_source: "服务端默认" });
    Object.assign(linyin.scene.actor_model, { reasoning_effort: "low", reasoning_effort_source: "SceneHub 演员配置" });
    render(<AccountPersonaPanel profiles={[aike, linyin]} />);
    const a = within(screen.getByRole("article", { name: "爱可账号配置" }));
    const b = within(screen.getByRole("article", { name: "凛音账号配置" }));
    expect(a.getAllByText("max（最高）")).toHaveLength(2);
    expect(a.getAllByText("AIKE_LLM_REASONING_EFFORT")).toHaveLength(2);
    expect(b.getByText("未指定（服务端默认）")).toBeTruthy();
    expect(b.getByText("low（低）")).toBeTruthy();
    const vision = a.getByRole("heading", { name: "视觉模型" }).closest("section")!;
    expect(within(vision).queryByText("思考强度")).toBeNull();
  });

  it("loads only the selected account reference sample and releases its blob on unmount", async () => {
    api.getPersonaVoiceSample.mockResolvedValue(new Blob(["sample"], { type: "audio/wav" }));
    const view = render(<AccountPersonaPanel profiles={[profile("linyin")]} />);
    fireEvent.click(screen.getByRole("button", { name: "试听音色" }));
    const audio = await screen.findByLabelText("凛音音色样例");
    expect(audio.getAttribute("src")).toBe("blob:voice-test");
    expect(api.getPersonaVoiceSample.mock.calls[0][0]).toBe("3000000001");
    expect(screen.getByText(/本地参考样例/)).toBeTruthy();
    view.unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:voice-test");
  });

  it("shows unavailable samples without borrowing another voice", () => {
    const unavailable = profile("linyin"); unavailable.voice.sample_available = false;
    render(<AccountPersonaPanel profiles={[unavailable]} />);
    expect((screen.getByRole("button", { name: "试听音色" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/缺失或不可读/)).toBeTruthy();
    expect(api.getPersonaVoiceSample).not.toHaveBeenCalled();
  });

  it("keeps playback failures visible and does not generate speech", async () => {
    api.getPersonaVoiceSample.mockRejectedValue(new Error("样例暂不可用"));
    render(<AccountPersonaPanel profiles={[profile("aike")]} />);
    fireEvent.click(screen.getByRole("button", { name: "试听音色" }));
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "样例暂不可用");
    expect(screen.queryByLabelText("爱可音色样例")).toBeNull();
  });
});
