export type RunStatus = "DRAFT" | "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
export type ResultState = "NOT_CALCULATED" | "CALCULATED";
export type ModelId = "logistic_regression" | "svm_rbf" | "random_forest" | "xgboost" | "lightgbm" | "mlp";
export type SelectorId = "none" | "mutual_information" | "anova" | "rfe" | "l1_logistic" | "tree_importance" | "pca" | "correlation_pruning" | "sequential_feature_selection";

export interface ExperimentConfig {
  model: ModelId;
  selector: SelectorId;
  budget_kind: "original_features" | "pca_components";
  k_original_features: number | null;
  n_components: number | null;
  required_raw_feature_count: number | null;
  dataset_version: string | null;
  seed: number;
  evaluation_mode?: "protocol" | "smoke";
  search_space?: Record<string, unknown[]>;
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

export interface ClassifierModel {
  model_id: string;
  model_family: string;
  source_run: string;
  dataset_id: number;
  dataset_sha256: string;
  feature_names: string[];
  classes: string[];
  training_timestamp_utc: string;
  deployment_model: true;
  note: string;
}

export interface ClassifierPrediction {
  model_id: string;
  source_run: string;
  predicted_class: string;
  predicted_probability: number;
  probabilities: Record<string, number>;
  features: Record<string, number>;
  dataset_sha256: string;
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
  macro_f1_fold_sd_descriptive: number | null;
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
    margin_macro_f1: number;
    paired_losses: { fold_id: string; loss_macro_f1: number }[];
    mean_loss_descriptive: number;
    sufficient_k: number | null;
    status: string;
  };
}

export interface ApiErrorBody {
  error: { code: "validation_error" | "invalid_configuration" | "not_found" | "conflict" | "persistence_error" | "demo_read_only"; message: string };
}
