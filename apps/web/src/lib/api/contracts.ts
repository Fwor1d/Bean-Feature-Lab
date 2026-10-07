export type RunStatus = "DRAFT" | "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
export type ResultState = "NOT_CALCULATED" | "CALCULATED";
export type ModelId = "logistic_regression" | "svm_rbf" | "random_forest" | "xgboost" | "lightgbm" | "mlp";
export type SelectorId = "none" | "mutual_information" | "anova" | "rfe" | "l1_logistic" | "tree_importance" | "pca" | "correlation_pruning" | "sequential_feature_selection";

export interface ExperimentConfig {
  model: ModelId;
  selector: SelectorId;
  budget_kind: "original_features" | "pca_components" | "sparse_original_features";
  k_original_features: number | null;
  n_components: number | null;
  required_raw_feature_count: number | null;
  dataset_version: string | null;
  seed: number;
  evaluation_mode?: "protocol" | "smoke";
  search_space?: Record<string, unknown[]>;
  reproduces_run_id?: string | null;
  selector_configuration?: Record<string, unknown>;
}

export interface Experiment {
  id: number;
  name: string;
  configuration: ExperimentConfig;
  created_at: string;
  updated_at: string;
}

export interface Run {
  id: number;
  display_id: string;
  experiment_id: number;
  status: RunStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  metrics: { macro_f1_mean: number; accuracy_mean: number } | null;
  result_state: ResultState;
}

export interface SystemInfo {
  app_version: string;
  api_version: string;
  python_version: string;
  platform: string;
  git_commit: string | null;
  database: "connected" | "unavailable";
  worker: "online" | "offline" | "not_started" | "unknown";
  scientific_results: ResultState;
}

export interface Project {
  id: number;
  name: string;
}

export interface Dataset {
  id: number;
  source_id: number;
  version: string;
  validated: boolean;
  rows?: number;
  feature_count?: number;
  arff_sha256?: string;
}

export interface DatasetManifest {
  source: string;
  source_id: number;
  source_url: string;
  retrieved_at_utc: string;
  archive_sha256: string;
  arff_sha256: string;
  dataset_version: string;
  rows: number;
  feature_count: number;
  features: string[];
  target: string;
  classes: string[];
  missing_values: number;
  schema_notice: string;
  official_schema_acknowledged: boolean;
}

export interface DatasetQuality {
  dataset_sha256: string;
  source_id: number;
  rows: number;
  columns: number;
  numeric_feature_count: number;
  missing_values: number;
  infinite_values: number;
  exact_duplicate_rows_involved: number;
  exact_duplicate_excess_rows: number;
  class_balance: Record<string, { count: number; fraction: number }>;
  constant_columns: string[];
  feature_statistics: Record<string, {
    minimum: number;
    maximum: number;
    median: number;
    q1: number;
    q3: number;
    iqr: number;
    constant: boolean;
    extreme_outlier_count: number;
    extreme_outlier_lower_fence: number;
    extreme_outlier_upper_fence: number;
  }>;
  pearson_correlation: Record<string, Record<string, number>>;
  high_absolute_correlation_pairs: { left: string; right: string; pearson_r: number }[];
  high_correlation_threshold: number;
  correlation_note: string;
  outlier_method: string;
  cleaning_applied: false;
  note: string;
  schema_notice: string;
}

export interface ClassifierModel {
  model_id: string;
  model_version?: string;
  model_family: string;
  source_run: string;
  dataset_id: number;
  dataset_sha256: string;
  feature_names: string[];
  classes: string[];
  training_timestamp_utc: string;
  deployment_model: true;
  deployment_status?: "ACTIVE" | "INACTIVE";
  active?: boolean;
  artifact_sha256?: string;
  observed_ranges?: Record<string, { minimum: number; maximum: number }>;
  note: string;
}

export interface ClassifierExample {
  source: string;
  row_index: number;
  features: Record<string, number>;
  actual_class: string;
  note: string;
}

export interface ClassifierBenchmark {
  status: "CALCULATED";
  benchmark_kind: string;
  model_id: string;
  source_run: string;
  dataset_sha256: string;
  peak_process_tree_rss_bytes: number;
  baseline_process_tree_rss_bytes: number;
  incremental_peak_rss_bytes: number;
  maximum_child_processes: number;
  sampling_interval_seconds: number;
  rss_samples: number;
  latency: Record<"single_row" | "batch_1000", {
    rows: number;
    repeats: number;
    median_ms: number;
    p95_ms: number;
    samples_ms: number[];
  }>;
  serialized_pipeline_bytes: number;
  warmup_repetitions: number;
  hardware: Record<string, string | number>;
  note: string;
  measured_at_utc: string;
}

export interface ClassifierPrediction {
  model_id: string;
  source_run: string;
  predicted_class: string;
  predicted_probability: number;
  probabilities: Record<string, number>;
  features: Record<string, number>;
  dataset_sha256: string;
  local_explanation: {
    method: string;
    target_class: string;
    intercept: number;
    contributions: {
      feature: string;
      standardized_value: number;
      coefficient: number;
      logit_contribution: number;
    }[];
    note: string;
  } | null;
}

export interface RunSummary {
  run_id: string;
  status: RunStatus;
  result_state: ResultState;
  summary: ScientificSummary | null;
}

export interface ScientificSummary {
  evaluation_mode: "protocol" | "smoke";
  cv_protocol_version: string;
  model: ModelId;
  selector: SelectorId;
  seed: number;
  outer_split_set_sha256: string;
  budget_kind: "original_features" | "pca_components";
  k_original_features: number | null;
  n_components: number | null;
  outer_fold_count: number;
  inner_fold_count: number;
  macro_f1_mean: number;
  macro_f1_fold_sd_descriptive: number | null;
  accuracy_mean: number;
  repeat_macro_f1_means: number[];
  feature_stability: FeatureStability | null;
  sufficient_k: number | null;
  sufficiency_status: string;
  sufficiency_margin_macro_f1: number;
  dispersion_note: string;
}

export interface FeatureStability {
  selection_frequency: Record<string, number>;
  pairwise_jaccard_mean: number | null;
  pairwise_jaccard_values: number[];
  note: string;
}

export interface FeatureBudgetPoint {
  run_id: string;
  model: ModelId;
  budget_kind: "original_features";
  k_original_features: number;
  macro_f1_mean: number;
  accuracy_mean: number;
  macro_f1_fold_sd_descriptive: number | null;
  dataset_hash: string;
  outer_split_set_sha256: string;
}

export interface FeatureSelectionPoint {
  run_id: string;
  model: ModelId;
  selector: SelectorId;
  k_original_features: number;
  outer_fold_count: number;
  selection_frequency: Record<string, number>;
  pairwise_jaccard_mean: number | null;
  dataset_hash: string;
  outer_split_set_sha256: string;
}

export interface RunDetail {
  run_id: string;
  configuration: ExperimentConfig;
  dataset_manifest: DatasetManifest;
  provenance: {
    git_commit: string | null;
    git_dirty: boolean;
    source_tree_sha256: string;
    python_version: string;
    platform: string;
    package_versions: Record<string, string>;
  };
  fingerprint: string;
  result_artifact: string;
  result_sha256: string;
  artifact_verified: boolean;
}

export interface RunVerification {
  run_id: string;
  verified: boolean;
  checks: Record<string, boolean>;
  errors: string[];
  result_artifact?: string;
  result_sha256?: string;
  dataset_sha256?: string;
  fingerprint?: string;
}

export interface ResourceDistribution {
  samples: number;
  median: number;
  p95: number;
  minimum: number;
  maximum: number;
}

export interface RunResources {
  run_id: string;
  measurement_scope: string;
  total_nested_search_seconds: number;
  total_outer_refit_seconds: number;
  inference_latency_ms: {
    single_row: ResourceDistribution | null;
    batch_1000: ResourceDistribution | null;
  };
  serialized_pipeline_bytes: ResourceDistribution | null;
  peak_memory_bytes: ResourceDistribution | null;
  peak_memory_status: "CALCULATED" | "NOT_CALCULATED";
  peak_memory_reason: string | null;
  software_hardware_profile: RunDetail["provenance"];
  timing_note: string;
}

export interface FoldResult {
  fold_id: string;
  split_sha256: string;
  train_size: number;
  test_size: number;
  best_params: Record<string, unknown>;
  selected_original_features: string[] | null;
  representation: Record<string, unknown>;
  macro_f1: number;
  accuracy: number;
  per_class_recall: Record<string, number>;
  confusion_matrix: number[][];
  roc_auc_ovr_macro: number | null;
  search_seconds: number;
  refit_seconds: number;
  inference_latency: Record<string, unknown>;
  serialized_pipeline_bytes: number;
  peak_memory_bytes: number | null;
}

export interface PairedComparison {
  compact_run_id: string;
  baseline_run_id: string;
  dataset_hash: string;
  comparison: {
    interval_method: string;
    margin_macro_f1: number;
    family_alpha: number;
    comparison_alpha: number;
    multiplicity_method: string;
    n_paired_folds: number;
    test_train_ratio: number;
    paired_losses: { fold_id: string; loss_macro_f1: number }[];
    mean_loss: number;
    sample_variance: number;
    corrected_variance: number;
    corrected_standard_error: number;
    critical_value: number;
    one_sided_upper_confidence_bound: number;
    decision: "sufficient" | "not_sufficient";
    sufficient_k: number | null;
    status: string;
  };
}

export interface SufficiencyComparison {
  k_original_features: number;
  decision: "sufficient" | "not_sufficient" | "not_calculated";
  interval_method: string | null;
  margin_macro_f1: number | null;
  family_alpha: number | null;
  comparison_alpha: number | null;
  multiplicity_method: string | null;
  n_paired_folds: number | null;
  test_train_ratio: number | null;
  paired_losses: { fold_id: string; loss_macro_f1: number }[];
  mean_loss: number | null;
  sample_variance: number | null;
  corrected_variance: number | null;
  corrected_standard_error: number | null;
  critical_value: number | null;
  one_sided_upper_confidence_bound: number | null;
  sufficient_k: number | null;
  status: string | null;
}

export interface CoreSufficiency {
  model: ModelId;
  baseline_run_id: string | null;
  dataset_hash: string | null;
  outer_split_set_sha256: string | null;
  minimal_sufficient_k: number | null;
  status: "CALCULATED" | "PARTIAL" | "NOT_CALCULATED_MISSING_BASELINE";
  calculated_comparisons: number;
  comparisons: SufficiencyComparison[];
}

export interface ApiErrorBody {
  error: { code: "validation_error" | "invalid_configuration" | "invalid_request" | "not_found" | "conflict" | "persistence_error" | "demo_read_only" | "payload_too_large"; message: string };
}
