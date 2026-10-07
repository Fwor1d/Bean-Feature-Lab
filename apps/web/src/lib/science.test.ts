import { describe, expect, it } from "vitest";
import type { FeatureBudgetPoint } from "./api/contracts";
import { budgetCohorts, metric } from "./science";

const point = (dataset_hash: string, outer_split_set_sha256: string, k_original_features: number): FeatureBudgetPoint => ({
  run_id: `RUN-${k_original_features}`, model: "logistic_regression", selector: "mutual_information",
  budget_kind: "original_features", k_original_features, n_components: null, budget_value: k_original_features,
  macro_f1_mean: 0.5, accuracy_mean: 0.5, macro_f1_fold_sd_descriptive: null,
  dataset_hash, outer_split_set_sha256,
});

describe("scientific display invariants", () => {
  it("never merges different datasets or outer split sets into a budget curve", () => {
    const cohorts = budgetCohorts([point("official", "frozen", 4), point("official", "different", 5), point("other", "frozen", 6), point("official", "frozen", 7)]);
    expect(cohorts.map(([, values]) => values.map(value => value.k_original_features))).toEqual([[4, 7], [5], [6]]);
  });

  it("renders an absent scientific decision as not calculated rather than zero", () => {
    expect(metric(null, 0)).toBe("Не рассчитано");
  });
});
