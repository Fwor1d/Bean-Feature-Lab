from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from beanfeature_application.contracts import Experiment, ExperimentConfig, Run
from beanfeature_research.contracts import ModelId, ResultState, RunStatus, SelectorId


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]


class SystemInfoResponse(BaseModel):
    app_version: str
    api_version: str
    python_version: str
    platform: str
    git_commit: str | None
    database: str
    worker: str
    scientific_results: ResultState


class ProjectResponse(BaseModel):
    id: int
    name: str


class DatasetResponse(BaseModel):
    id: int
    source_id: int
    version: str
    validated: bool
    rows: int | None = None
    feature_count: int | None = None
    arff_sha256: str | None = None


class ClassBalanceResponse(BaseModel):
    count: int
    fraction: float


class FeatureQualityResponse(BaseModel):
    minimum: float
    maximum: float
    median: float
    q1: float
    q3: float
    iqr: float
    constant: bool
    extreme_outlier_count: int
    extreme_outlier_lower_fence: float
    extreme_outlier_upper_fence: float


class DatasetQualityResponse(BaseModel):
    dataset_sha256: str
    source_id: int
    rows: int
    columns: int
    numeric_feature_count: int
    missing_values: int
    infinite_values: int
    exact_duplicate_rows_involved: int
    exact_duplicate_excess_rows: int
    class_balance: dict[str, ClassBalanceResponse]
    constant_columns: list[str]
    feature_statistics: dict[str, FeatureQualityResponse]
    outlier_method: str
    cleaning_applied: Literal[False]
    note: str
    schema_notice: str


class ExperimentConfigDTO(BaseModel):
    model: ModelId
    selector: SelectorId
    budget_kind: Literal["original_features", "pca_components"]
    k_original_features: int | None = Field(default=None, ge=1, le=16)
    n_components: int | None = Field(default=None, ge=1, le=16)
    required_raw_feature_count: int | None = None
    dataset_version: str | None = Field(default=None, max_length=128)
    seed: int = Field(default=42, ge=0, le=4_294_967_295)
    evaluation_mode: Literal["protocol", "smoke"] = "protocol"
    search_space: dict[str, list[object]] = Field(default_factory=dict)

    def to_domain(self) -> ExperimentConfig:
        return ExperimentConfig(**self.model_dump())


class CreateExperimentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    configuration: ExperimentConfigDTO


class ExperimentResponse(BaseModel):
    id: int
    name: str
    configuration: ExperimentConfigDTO
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, experiment: Experiment) -> "ExperimentResponse":
        return cls(
            id=experiment.id,
            name=experiment.name,
            configuration=ExperimentConfigDTO.model_validate(experiment.configuration.__dict__),
            created_at=experiment.created_at,
            updated_at=experiment.updated_at,
        )


class RunResponse(BaseModel):
    id: int
    display_id: str
    experiment_id: int
    status: RunStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    metrics: dict[str, float] | None = None
    result_state: ResultState = ResultState.NOT_CALCULATED

    @classmethod
    def from_domain(cls, run: Run) -> "RunResponse":
        return cls(
            id=run.id,
            display_id=run.display_id,
            experiment_id=run.experiment_id,
            status=run.status,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            error=run.error,
            metrics={
                "macro_f1_mean": float(run.summary["macro_f1_mean"]),
                "accuracy_mean": float(run.summary["accuracy_mean"]),
            }
            if run.status is RunStatus.COMPLETED and run.summary
            else None,
            result_state=ResultState.CALCULATED
            if run.status is RunStatus.COMPLETED and run.summary
            else ResultState.NOT_CALCULATED,
        )


class RunSummaryResponse(BaseModel):
    run_id: str
    status: RunStatus
    result_state: ResultState
    summary: dict[str, object] | None


class FeatureBudgetPointResponse(BaseModel):
    run_id: str
    model: ModelId
    budget_kind: Literal["original_features"]
    k_original_features: int
    macro_f1_mean: float
    accuracy_mean: float
    macro_f1_fold_sd_descriptive: float | None
    dataset_hash: str
    outer_split_set_sha256: str


class PairedLossResponse(BaseModel):
    fold_id: str
    loss_macro_f1: float


class SufficiencyComparisonResponse(BaseModel):
    k_original_features: int
    decision: Literal["sufficient", "not_sufficient", "not_calculated"]
    interval_method: str | None = None
    margin_macro_f1: float | None = None
    family_alpha: float | None = None
    comparison_alpha: float | None = None
    multiplicity_method: str | None = None
    n_paired_folds: int | None = None
    test_train_ratio: float | None = None
    paired_losses: list[PairedLossResponse] = Field(default_factory=list)
    mean_loss: float | None = None
    sample_variance: float | None = None
    corrected_variance: float | None = None
    corrected_standard_error: float | None = None
    critical_value: float | None = None
    one_sided_upper_confidence_bound: float | None = None
    sufficient_k: int | None = None
    status: str | None = None


class CoreSufficiencyResponse(BaseModel):
    model: ModelId
    baseline_run_id: str | None = None
    dataset_hash: str | None = None
    outer_split_set_sha256: str | None = None
    minimal_sufficient_k: int | None
    status: Literal["CALCULATED", "PARTIAL", "NOT_CALCULATED_MISSING_BASELINE"]
    calculated_comparisons: int = 0
    comparisons: list[SufficiencyComparisonResponse]


class PredictRequest(BaseModel):
    features: dict[str, object]


class PredictResponse(BaseModel):
    model_id: str
    source_run: str
    predicted_class: str
    predicted_probability: float
    probabilities: dict[str, float]
    features: dict[str, float]
    dataset_sha256: str


class FoldResultResponse(BaseModel):
    fold_id: str
    split_sha256: str
    inner_seed: int
    train_size: int
    test_size: int
    best_params: dict[str, object]
    inner_best_macro_f1: float
    selected_original_features: list[str] | None
    representation: dict[str, object]
    macro_f1: float
    accuracy: float
    per_class_recall: dict[str, float]
    confusion_matrix: list[list[int]]
    roc_auc_ovr_macro: float | None
    roc_auc_reason: str | None
    search_seconds: float
    refit_seconds: float
    search_plus_refit_seconds: float
    inference_latency: dict[str, object]
    serialized_pipeline_bytes: int
    peak_memory_bytes: int | None
    peak_memory_reason: str | None
    y_true: list[str]
    y_pred: list[str]
    model: ModelId
    selector: SelectorId
