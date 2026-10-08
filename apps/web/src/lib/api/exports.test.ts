import { afterEach, expect, it, vi } from "vitest";
import { downloadRunExport } from "./exports";
afterEach(() => vi.unstubAllGlobals());
it("preserves verified export bytes and uses its own safe meaningful filename", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("fold_id,macro_f1\nr01-f01,0.8\n", { headers: { "Content-Type": "text/csv; charset=utf-8", "Content-Disposition": 'attachment; filename="../../bad.csv"' } })));
  const output = await downloadRunExport(3, "folds.csv");
  expect(output.filename).toBe("RUN-000003-folds.csv");
  expect(await output.blob.text()).toContain("r01-f01");
});
it("surfaces failed verification and network failure instead of downloading an error as evidence", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"error":{"code":"conflict","message":"Artifact verification failed"}}', { status: 409 })));
  await expect(downloadRunExport(3, "result.json")).rejects.toThrow("verification failed");
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  await expect(downloadRunExport(3, "result.json")).rejects.toThrow("Экспорт недоступен");
});
it("rejects wrong content type", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("html", { headers: { "Content-Type": "text/html" } })));
  await expect(downloadRunExport(3, "result.json")).rejects.toThrow("некорректный формат");
});
