import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, apiErrorMessage } from "./client";

afterEach(() => vi.unstubAllGlobals());

describe("typed API client", () => {
  it("keeps empty real collections empty", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));
    expect(await api.experiments()).toEqual([]);
  });

  it("distinguishes unavailable API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));
    await expect(api.runs()).rejects.toMatchObject({ code: "api_unavailable" });
    expect(apiErrorMessage(new ApiError(0, "api_unavailable", "API недоступен"))).toContain("API");
  });

  it("does not use a public tunnel URL for server-side API requests", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.invalid");
    vi.stubEnv("BEANFEATURE_INTERNAL_API_BASE_URL", undefined);
    vi.resetModules();
    const fetched = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
    vi.stubGlobal("fetch", fetched);
    const { api: freshApi } = await import("./client");
    await freshApi.runs();
    expect(fetched).toHaveBeenCalledWith("http://127.0.0.1:8000/api/v1/runs", expect.objectContaining({ cache: "no-store" }));
    vi.unstubAllEnvs();
  });
});
