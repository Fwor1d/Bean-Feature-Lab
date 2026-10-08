import { afterEach, expect, it, vi } from "vitest";
import { acceptsNavigation, presentationStep, reportRequest, reportPoints, type CoreSnapshot } from "./reporting";
afterEach(() => vi.unstubAllGlobals());
it("validates deep-linked steps", () => {
  expect(presentationStep("#step=5")).toBe(4);
  expect(presentationStep("#step=9")).toBe(0);
  expect(presentationStep("bad")).toBe(0);
});
it("preserves keyboard controls while ignoring input/menu targets", () => {
  const e = { key: "ArrowRight", altKey: false, ctrlKey: false, metaKey: false };
  expect(acceptsNavigation(e, null)).toBe(true);
  expect(acceptsNavigation({ ...e, ctrlKey: true }, null)).toBe(false);
  expect(acceptsNavigation(e, { closest: () => ({}) } as unknown as HTMLElement)).toBe(false);
});
it("surfaces expired or invalid evidence rather than returning demo data", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, json: async () => ({ error: { code: "snapshot_expired", message: "Снимок истёк" } }) }));
  await expect(reportRequest("unknown/evidence")).rejects.toMatchObject({ code: "snapshot_expired" });
});
it("empty evidence remains empty", () => {
  expect(reportPoints({ runs: [] } as unknown as CoreSnapshot, "pca")).toEqual([]);
});

it("normalizes a network failure into a Russian recoverable error", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network")));
  await expect(reportRequest("cohorts")).rejects.toMatchObject({ code: "api_unavailable", message: expect.stringContaining("API недоступен") });
});
