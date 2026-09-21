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
});
