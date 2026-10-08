import { afterEach, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "./route";
afterEach(() => vi.unstubAllGlobals());
it("preserves PDF bytes, evidence and download headers through the proxy", async () => {
  const bytes = new Uint8Array([37, 80, 68, 70, 45, 255, 0, 128]);
  const fetch = vi.fn().mockResolvedValue(new Response(bytes, { headers: {
    "Content-Type": "application/pdf", "Content-Disposition": 'attachment; filename="BeanFeatureLab-test.pdf"',
    "X-Evidence-SHA256": "test-sha", "Cache-Control": "no-store",
  } }));
  vi.stubGlobal("fetch", fetch);
  const output = await GET(new NextRequest("http://localhost/api/backend/api/v1/reports/core/id/pdf?test=1"), { params: Promise.resolve({ path: ["api", "v1", "reports", "core", "id", "pdf"] }) });
  expect(new Uint8Array(await output.arrayBuffer())).toEqual(bytes);
  expect(output.headers.get("Content-Type")).toBe("application/pdf");
  expect(output.headers.get("Content-Disposition")).toContain("attachment");
  expect(output.headers.get("X-Evidence-SHA256")).toBe("test-sha");
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/id/pdf?test=1"), expect.anything());
});
it("preserves expiry/errors and renderer backoff; network failure is explicit", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"error":{"code":"pdf_busy"}}', { status: 503, headers: { "Retry-After": "5", "Content-Type": "application/json" } })));
  const args = [new NextRequest("http://localhost/api/backend/api/v1/reports/core/id/pdf"), { params: Promise.resolve({ path: ["api", "v1", "reports", "core", "id", "pdf"] }) }] as const;
  const output = await GET(...args);
  expect(output.status).toBe(503);
  expect(output.headers.get("Retry-After")).toBe("5");
  expect(await output.json()).toEqual({ error: { code: "pdf_busy" } });
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
  expect((await GET(...args)).status).toBe(503);
});
