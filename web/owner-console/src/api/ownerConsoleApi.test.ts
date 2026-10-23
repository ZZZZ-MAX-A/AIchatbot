import { afterEach, describe, expect, it, vi } from "vitest";

import { ownerConsoleApi } from "./ownerConsoleApi";
import { alternateMemoryScope } from "../testFixtures/memoryScope";

const actionEnvelope = {
  schema_version: "owner_console.http.v1",
  read_model_schema_version: "owner_console.read_model.v0",
  transport: "http",
  api_prefix: "/api/v1/owner-console",
  resource: "manual-diagnostics/tts-synthesis",
  generated_at: "2026-07-24T05:01:02+00:00",
  read_only: false,
  http_api_enabled: true,
  web_write_enabled: false,
  manual_runtime_action: true,
  configuration_write_enabled: false,
  business_data_write_enabled: false,
  error: null,
  data: {},
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("memory maintenance scope API", () => {
  it("sends only the fixed account and revision while retaining action confirmation and header", async () => {
    const fetchMock = vi.fn().mockImplementation(async (_path, init) => new Response(JSON.stringify({
      ...actionEnvelope, resource: "memory", read_only: init.method === "GET",
    }), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await ownerConsoleApi.getMemory(undefined, alternateMemoryScope);
    await ownerConsoleApi.getDiagnostics(undefined, alternateMemoryScope);
    await ownerConsoleApi.getManualDiagnostics(undefined, alternateMemoryScope);
    await ownerConsoleApi.runMemoryRagConsistency(undefined, alternateMemoryScope);
    await ownerConsoleApi.getDiagnostics(undefined, null);
    const suffix = `?bot_self_id=3000000001&scope_revision=${alternateMemoryScope.revision}`;
    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      `/api/v1/owner-console/memory${suffix}`, `/api/v1/owner-console/diagnostics${suffix}`,
      `/api/v1/owner-console/manual-diagnostics${suffix}`, `/api/v1/owner-console/manual-diagnostics/memory-rag-consistency${suffix}`,
      "/api/v1/owner-console/diagnostics?skip_memory=true",
    ]);
    expect(fetchMock.mock.calls[3][1].method).toBe("POST");
    expect(fetchMock.mock.calls[3][1]).toMatchObject({
      body: JSON.stringify({ confirmation: "run_registered_memory_rag_consistency" }),
      headers: expect.objectContaining({ "X-Owner-Console-Action": "manual-memory-rag-consistency-v1" }),
    });
  });
});

describe("account voice reference API", () => {
  it("requests the selected account sample as a protected read", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(new Uint8Array(64), {
      status: 200, headers: { "Content-Type": "audio/wav" },
    }));
    vi.stubGlobal("fetch", fetchMock);
    expect((await ownerConsoleApi.getPersonaVoiceSample("3000000001")).size).toBe(64);
    expect(fetchMock.mock.calls[0]).toEqual([
      "/api/v1/owner-console/settings/accounts/3000000001/voice-sample",
      expect.objectContaining({ method: "GET", credentials: "same-origin", cache: "no-store",
        headers: { Accept: "audio/wav", "X-Owner-Console-Action": "persona-voice-sample-v1" } }),
    ]);
  });
  it("rejects caller-supplied paths before a request", async () => {
    const fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock);
    await expect(ownerConsoleApi.getPersonaVoiceSample("../sample")).rejects.toThrow("账号标识无效");
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("rejects non-audio responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("unexpected", {
      status: 200, headers: { "Content-Type": "text/html" },
    })));
    await expect(ownerConsoleApi.getPersonaVoiceSample("2000000001")).rejects.toThrow("音色样例格式无效");
  });
});

describe("ownerConsoleApi manual TTS action", () => {
  it("sends the one fixed allowlisted path, header and confirmation body", async () => {
    const fetchMock = vi.fn().mockImplementation(async () =>
      new Response(JSON.stringify(actionEnvelope), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await ownerConsoleApi.runTtsSynthesis();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe(
      "/api/v1/owner-console/manual-diagnostics/tts-synthesis",
    );
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-Owner-Console-Action": "manual-tts-synthesis-v1",
    });
    expect(init.body).toBe(
      JSON.stringify({ confirmation: "run_registered_tts_synthesis" }),
    );
  });

  it("loads only the bounded fixed-run WAV preview with the protected header", async () => {
    const wav = new Uint8Array(64);
    wav.set(new TextEncoder().encode("RIFF"), 0);
    wav.set(new TextEncoder().encode("WAVE"), 8);
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(wav, {
        status: 200,
        headers: { "Content-Type": "audio/wav" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const preview = await ownerConsoleApi.getTtsAudioPreview(7);

    expect(preview.size).toBe(64);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe(
      "/api/v1/owner-console/manual-diagnostics/tts-synthesis/audio-preview/7",
    );
    expect(init).toMatchObject({
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        Accept: "audio/wav",
        "X-Owner-Console-Action": "manual-tts-audio-preview-v1",
      },
    });
  });

  it("uses distinct fixed accept and reject review actions bound to run_id", async () => {
    const fetchMock = vi.fn().mockImplementation(async () =>
      new Response(JSON.stringify(actionEnvelope), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await ownerConsoleApi.acceptTtsAudioQuality(7);
    await ownerConsoleApi.rejectTtsAudioQuality(8);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [acceptPath, acceptInit] = fetchMock.mock.calls[0] as [
      string,
      RequestInit,
    ];
    expect(acceptPath).toBe(
      "/api/v1/owner-console/manual-diagnostics/tts-synthesis/audio-quality/accept",
    );
    expect(acceptInit.headers).toEqual({
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-Owner-Console-Action": "manual-tts-audio-quality-accept-v1",
    });
    expect(acceptInit.body).toBe(
      JSON.stringify({
        confirmation: "accept_latest_tts_audio_quality",
        run_id: 7,
      }),
    );

    const [rejectPath, rejectInit] = fetchMock.mock.calls[1] as [
      string,
      RequestInit,
    ];
    expect(rejectPath).toBe(
      "/api/v1/owner-console/manual-diagnostics/tts-synthesis/audio-quality/reject",
    );
    expect(rejectInit.headers).toEqual({
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-Owner-Console-Action": "manual-tts-audio-quality-reject-v1",
    });
    expect(rejectInit.body).toBe(
      JSON.stringify({
        confirmation: "reject_latest_tts_audio_quality",
        run_id: 8,
      }),
    );

    await expect(ownerConsoleApi.getTtsAudioPreview(0)).rejects.toThrow(
      "run_id 无效",
    );
    await expect(ownerConsoleApi.acceptTtsAudioQuality(Number.NaN)).rejects.toThrow(
      "run_id 无效",
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe("ownerConsoleApi manual cloud vision action", () => {
  it("sends only the fixed vision path, header and confirmation body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          ...actionEnvelope,
          resource: "manual-diagnostics/cloud-vision-fixed-description",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await ownerConsoleApi.runCloudVisionFixedDescription();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe(
      "/api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description",
    );
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-Owner-Console-Action": "manual-cloud-vision-fixed-description-v1",
    });
    expect(init.body).toBe(
      JSON.stringify({ confirmation: "run_registered_cloud_vision_fixed_description" }),
    );
  });

  it("loads only the fixed protected PNG reference preview", async () => {
    const png = new Uint8Array(162_977);
    png.set(new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]), 0);
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(png, {
        status: 200,
        headers: { "Content-Type": "image/png" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const preview = await ownerConsoleApi.getCloudVisionReferencePreview();

    expect(preview.size).toBe(162_977);
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe(
      "/api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description/reference-preview",
    );
    expect(init).toMatchObject({
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        Accept: "image/png",
        "X-Owner-Console-Action": "manual-cloud-vision-reference-preview-v1",
      },
    });
  });

  it("uses distinct fixed visual quality decisions without rerunning vision", async () => {
    const fetchMock = vi.fn().mockImplementation(async () =>
      new Response(JSON.stringify(actionEnvelope), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await ownerConsoleApi.acceptCloudVisionResponseQuality(7);
    await ownerConsoleApi.rejectCloudVisionResponseQuality(8);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [acceptPath, acceptInit] = fetchMock.mock.calls[0] as [
      string,
      RequestInit,
    ];
    expect(acceptPath).toBe(
      "/api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description/response-quality/accept",
    );
    expect(acceptInit.headers).toEqual({
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-Owner-Console-Action": "manual-cloud-vision-response-quality-accept-v1",
    });
    expect(acceptInit.body).toBe(
      JSON.stringify({
        confirmation: "accept_latest_cloud_vision_response_quality",
        run_id: 7,
      }),
    );

    const [rejectPath, rejectInit] = fetchMock.mock.calls[1] as [
      string,
      RequestInit,
    ];
    expect(rejectPath).toBe(
      "/api/v1/owner-console/manual-diagnostics/cloud-vision-fixed-description/response-quality/reject",
    );
    expect(rejectInit.headers).toEqual({
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-Owner-Console-Action": "manual-cloud-vision-response-quality-reject-v1",
    });
    expect(rejectInit.body).toBe(
      JSON.stringify({
        confirmation: "reject_latest_cloud_vision_response_quality",
        run_id: 8,
      }),
    );

    await expect(
      ownerConsoleApi.acceptCloudVisionResponseQuality(0),
    ).rejects.toThrow("run_id 无效");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
