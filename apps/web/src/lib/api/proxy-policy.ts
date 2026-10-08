const exportKinds = new Set(["result.json", "config.json", "summary.md", "folds.csv", "selected-features.csv"]);

export function isAllowedBackendPath(path: string[]): boolean {
  if (path.length < 3 || path[0] !== "api" || path[1] !== "v1") return false;
  const runExport = path.length === 6 && path[2] === "runs" && /^[1-9]\d*$/.test(path[3]) &&
    path[4] === "export" && exportKinds.has(path[5]);
  return path.every((part, index) => /^[a-zA-Z0-9_-]+$/.test(part) || (runExport && index === 5));
}
