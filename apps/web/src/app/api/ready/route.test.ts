import { afterEach, describe, expect, it, vi } from "vitest";
import { GET } from "./route";

afterEach(() => vi.unstubAllGlobals());

describe("Web readiness", () => {
  it("requires a ready BeanFeature API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ application: "beanfeature-api", status: "ready" })));
    const response = await GET();
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ application: "beanfeature-web", status: "ready" });
    expect(response.headers.get("cache-control")).toBe("no-store");
  });

  it.each([
    Response.json({ status: "ready", application: "unrelated" }),
    Response.json({ status: "not_ready", application: "beanfeature-api" }, { status: 503 }),
  ])("rejects unavailable or unrelated upstream", async (upstream) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(upstream));
    expect((await GET()).status).toBe(503);
  });

  it("hides backend details on network failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("secret internal URL")));
    const response = await GET();
    expect(response.status).toBe(503);
    expect(await response.text()).not.toContain("secret");
  });
});
