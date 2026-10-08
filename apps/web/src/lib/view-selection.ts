import type { FeatureSelectionPoint } from "./api/contracts";

type FeatureQuery = { model?: string; selector?: string; k?: string };

/** Explicit filters never substitute a different scientific condition. */
export function selectFeatureCondition(points: FeatureSelectionPoint[], query: FeatureQuery) {
  const requested = [query.model, query.selector, query.k].some(value => value !== undefined);
  const matching = points.filter(point =>
    (query.model === undefined || point.model === query.model) &&
    (query.selector === undefined || point.selector === query.selector) &&
    (query.k === undefined || point.k_original_features === Number(query.k)));
  if (!requested) {
    const preferred = points.find(point => point.model === "logistic_regression" &&
      point.selector === "mutual_information" && point.k_original_features === 14);
    if (preferred) return preferred;
  }
  return [...matching].sort((a, b) => b.k_original_features - a.k_original_features)[0] ?? null;
}

export function featureFilterParams(search: string, key: string, value: string) {
  const params = new URLSearchParams(search);
  params.set(key, value);
  if (key === "model") params.delete("selector");
  if (key === "model" || key === "selector") params.delete("k");
  return params;
}

export function selectFold<T extends { fold_id: string }>(folds: T[], requested?: string) {
  return requested === undefined ? folds[0] : folds.find(fold => fold.fold_id === requested);
}

export function sameRequestedRun(left?: string, right?: string) {
  return left !== undefined && right !== undefined && Number(left) === Number(right);
}
