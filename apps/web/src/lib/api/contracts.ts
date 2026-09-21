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

export interface ApiErrorBody {
  error: { code: "validation_error" | "invalid_configuration" | "not_found" | "conflict" | "persistence_error"; message: string };
}
