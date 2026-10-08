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

it("downloads only the selected snapshot with valid binary PDF and safe filename", async () => {
  const { reportPDF } = await import("./reporting");
  const snapshot = { snapshot_id: "fixed-id", evidence_sha256: "a".repeat(64) };
  const fetch = vi.fn().mockResolvedValue(new Response(new Uint8Array([37, 80, 68, 70, 45, 255, 0]), { headers: { "Content-Type": "application/pdf", "X-Evidence-SHA256": snapshot.evidence_sha256, "Content-Disposition": 'attachment; filename="../../unsafe.pdf"' } }));
  vi.stubGlobal("fetch", fetch);
  const output = await reportPDF(snapshot);
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining("fixed-id/pdf"), { cache: "no-store" });
  expect(new Uint8Array(await output.blob.arrayBuffer())).toEqual(new Uint8Array([37, 80, 68, 70, 45, 255, 0]));
  expect(output.filename).toBe("BeanFeatureLab-aaaaaaaaaaaaaaaa.pdf");
});
it("rejects expired snapshots and mismatched PDF evidence without substitution", async () => {
  const { reportPDF } = await import("./reporting");
  const snapshot = { snapshot_id: "fixed-id", evidence_sha256: "a".repeat(64) };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: "snapshot_expired", message: "Снимок истёк" } }), { status: 410 })));
  await expect(reportPDF(snapshot)).rejects.toMatchObject({ code: "snapshot_expired" });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("%PDF-test", { headers: { "Content-Type": "application/pdf", "X-Evidence-SHA256": "other" } })));
  await expect(reportPDF(snapshot)).rejects.toMatchObject({ code: "invalid_pdf" });
});
