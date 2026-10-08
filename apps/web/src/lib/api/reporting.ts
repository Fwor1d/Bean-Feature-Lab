import type { DatasetManifest, DatasetQuality, ExperimentConfig, FeatureBudgetPoint, ModelId } from "./contracts";

export interface ReportCohort { cohort_id: string; dataset_sha256: string; dataset_version: string; outer_split_set_sha256: string; protocol_version: string; seed: number; completed_conditions: number }
export interface ReportRun { run_id: string; id: number; result_sha256: string; fingerprint: string; finished_at: string; configuration: ExperimentConfig; summary: { model: ModelId; selector: FeatureBudgetPoint["selector"]; budget_kind: FeatureBudgetPoint["budget_kind"] | "sparse_original_features"; k_original_features: number | null; n_components: number | null; macro_f1_mean: number; accuracy_mean: number; macro_f1_fold_sd_descriptive: number | null; observed_nonzero_feature_counts: number[] | null }; provenance: Record<string, unknown> }
export interface ReportComparison { k_original_features: number; decision: "not_calculated" | "sufficient" | "not_sufficient"; one_sided_upper_confidence_bound?: number; mean_loss?: number }
export interface ReportFamily { model: ModelId; status: "CALCULATED" | "PARTIAL"; calculated_comparisons: number; minimal_sufficient_k: number | null; comparisons: ReportComparison[] }
export interface CoreSnapshot { snapshot_id: string; expires_at_utc: string; verified_at_utc: string; evidence_sha256: string; cohort: ReportCohort; dataset: DatasetManifest; quality: DatasetQuality; protocol: { version: string; outer_splits: number; outer_repeats: number; inner_splits: number; margin: number; family_alpha: number; comparisons_per_model: number; method: string }; runs: ReportRun[]; sufficiency: ReportFamily[]; excluded: { run_id: string; reason: string }[]; generation_context: Record<string, unknown> }
export const reportsBase = "/api/backend/api/v1/reports/core";
export class ReportRequestError extends Error { constructor(public code: string, message: string) { super(message); } }
export async function reportRequest<T>(path: string): Promise<T> {
  try {
    const response = await fetch(`${reportsBase}/${path}`, { cache: "no-store" });
    const body = await response.json();
    if (!response.ok) throw new ReportRequestError(body.error?.code ?? "api_unavailable", body.error?.message ?? "API недоступен. Повторите запрос.");
    return body as T;
  } catch (error) {
    if (error instanceof ReportRequestError) throw error;
    throw new ReportRequestError("api_unavailable", "API недоступен. Проверьте подключение и повторите запрос.");
  }
}
export function reportPoints(snapshot: CoreSnapshot, selector: FeatureBudgetPoint["selector"]): FeatureBudgetPoint[] {
  return snapshot.runs.filter(r => r.summary.selector === selector && r.summary.budget_kind !== "sparse_original_features").map(r => ({
    ...r.summary, budget_kind: r.summary.budget_kind as FeatureBudgetPoint["budget_kind"],
    budget_value: r.summary.k_original_features ?? r.summary.n_components!, run_id: r.run_id,
    dataset_hash: snapshot.cohort.dataset_sha256, outer_split_set_sha256: snapshot.cohort.outer_split_set_sha256,
  }));
}
export function presentationStep(hash: string): number {
  const match = hash.match(/^#step=([1-8])$/);
  return match ? Number(match[1]) - 1 : 0;
}
export function acceptsNavigation(event: { key: string; altKey: boolean; ctrlKey: boolean; metaKey: boolean }, target: HTMLElement | null): boolean {
  return ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key) && !event.altKey && !event.ctrlKey && !event.metaKey && !target?.closest("input,textarea,select,button,[role=combobox],[role=listbox],[role=menu],[contenteditable=true]");
}
