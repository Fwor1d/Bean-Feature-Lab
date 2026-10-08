import { describe, expect, it } from "vitest";
import { isAllowedBackendPath } from "./proxy-policy";

describe("backend proxy path boundary", () => {
  it("allows ordinary versioned API paths", () => {
    expect(isAllowedBackendPath(["api", "v1", "classifier", "predict"])).toBe(true);
    expect(isAllowedBackendPath(["api", "v1", "runs", "3", "detail"])).toBe(true);
  });
  it("allows only known dotted run export names", () => {
    for (const name of ["result.json", "config.json", "summary.md", "folds.csv", "selected-features.csv"]) {
      expect(isAllowedBackendPath(["api", "v1", "runs", "3", "export", name])).toBe(true);
    }
    expect(isAllowedBackendPath(["api", "v1", "runs", "3", "export", "model.joblib"])).toBe(false);
    expect(isAllowedBackendPath(["api", "v1", "datasets", "3", "export", "result.json"])).toBe(false);
  });
  it("rejects traversal, slashes and unknown dotted segments", () => {
    for (const segment of ["..", ".env", "../result.json", "result.json/extra", "%2e%2e", "%2f", "result.json?path=secret"]) {
      expect(isAllowedBackendPath(["api", "v1", "runs", "3", "export", segment])).toBe(false);
    }
    expect(isAllowedBackendPath(["api", "v1", "runs", "..", "export", "result.json"])).toBe(false);
    expect(isAllowedBackendPath(["api", "v1", "runs", "3", "export", "result.json", "extra"])).toBe(false);
  });
  it("rejects paths outside the versioned API", () => {
    expect(isAllowedBackendPath(["health"])).toBe(false);
    expect(isAllowedBackendPath(["api", "v2", "runs"])).toBe(false);
    expect(isAllowedBackendPath(["https:", "example.com", "data"])).toBe(false);
  });
});
