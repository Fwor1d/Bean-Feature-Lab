import { describe, expect, it } from "vitest";
import type { FeatureSelectionPoint } from "./api/contracts";
import { featureFilterParams, sameRequestedRun, selectFeatureCondition, selectFold } from "./view-selection";

const points: FeatureSelectionPoint[] = [
  { run_id: "RUN-000173", model: "random_forest", selector: "anova", k_original_features: 1,
    outer_fold_count: 15, selection_frequency: {}, pairwise_jaccard_mean: null, dataset_hash: "fixture", outer_split_set_sha256: "fixture" },
  { run_id: "RUN-000016", model: "logistic_regression", selector: "mutual_information", k_original_features: 14,
    outer_fold_count: 15, selection_frequency: {}, pairwise_jaccard_mean: null, dataset_hash: "fixture", outer_split_set_sha256: "fixture" },
];

describe("explicit scientific view selections", () => {
  it("never substitutes RF/ANOVA for an unavailable MLP condition", () => {
    expect(selectFeatureCondition(points, { model: "mlp", selector: "mutual_information", k: "4" })).toBeNull();
    expect(selectFeatureCondition(points, { model: "logistic_regression", selector: "anova", k: "1" })).toBeNull();
  });

  it("honors an explicit budget instead of falling back within the model", () => {
    expect(selectFeatureCondition(points, { model: "random_forest", selector: "anova", k: "4" })).toBeNull();
    expect(selectFeatureCondition(points, { model: "random_forest", selector: "anova", k: "1" })?.run_id).toBe("RUN-000173");
  });

  it("retains the existing unfiltered initial view without a scientific optimality claim", () => {
    expect(selectFeatureCondition(points, {})?.run_id).toBe("RUN-000016");
  });

  it("resets dependent filters when a model or selection method changes", () => {
    const search = "model=random_forest&selector=anova&k=1";
    const model = featureFilterParams(search, "model", "logistic_regression");
    expect(model.toString()).toBe("model=logistic_regression");
    const method = featureFilterParams(search, "selector", "mutual_information");
    expect(method.get("k")).toBeNull();
    expect(method.get("model")).toBe("random_forest");
    expect(method.get("selector")).toBe("mutual_information");
  });

  it("does not replace an explicitly unavailable fold with the first fold", () => {
    const folds = [{ fold_id: "r01-f01" }, { fold_id: "r02-f01" }];
    expect(selectFold(folds, "r99-f99")).toBeUndefined();
    expect(selectFold(folds)?.fold_id).toBe("r01-f01");
    expect(selectFold(folds, "r02-f01")?.fold_id).toBe("r02-f01");
  });

  it("recognizes numeric aliases as the same run rather than changing a comparison", () => {
    expect(sameRequestedRun("03", "3")).toBe(true);
    expect(sameRequestedRun("3", "4")).toBe(false);
    expect(sameRequestedRun(undefined, "3")).toBe(false);
  });
});
