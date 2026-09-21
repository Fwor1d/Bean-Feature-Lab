"""Stable scientific identities and semantics; deliberately no estimators or metrics."""

from dataclasses import dataclass
from enum import StrEnum

DRY_BEAN_FEATURE_COUNT = 16
DRY_BEAN_DATASET_ID = 602


class ModelId(StrEnum):
    LOGISTIC_REGRESSION = "logistic_regression"
    SVM_RBF = "svm_rbf"
    RANDOM_FOREST = "random_forest"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    MLP = "mlp"


class SelectorId(StrEnum):
    MUTUAL_INFORMATION = "mutual_information"
    ANOVA = "anova"
    RFE = "rfe"
    L1_LOGISTIC = "l1_logistic"
    TREE_IMPORTANCE = "tree_importance"
    PCA = "pca"
    CORRELATION_PRUNING = "correlation_pruning"
    SEQUENTIAL_FEATURE_SELECTION = "sequential_feature_selection"


class RunStatus(StrEnum):
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ResultState(StrEnum):
    NOT_CALCULATED = "NOT_CALCULATED"
    CALCULATED = "CALCULATED"


_ALLOWED_TRANSITIONS = {
    RunStatus.DRAFT: {RunStatus.QUEUED, RunStatus.CANCELLED},
    RunStatus.QUEUED: {RunStatus.RUNNING, RunStatus.CANCELLED},
    RunStatus.RUNNING: {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED},
    RunStatus.COMPLETED: set(),
    RunStatus.FAILED: set(),
    RunStatus.CANCELLED: set(),
}


def assert_transition(current: RunStatus, target: RunStatus, *, has_result: bool = False) -> None:
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"Invalid run status transition: {current} → {target}")
    if target is RunStatus.COMPLETED and not has_result:
        raise ValueError("A run cannot complete without validated scientific results")


@dataclass(frozen=True)
class OriginalFeatureBudget:
    k_original_features: int

    def __post_init__(self) -> None:
        if not 1 <= self.k_original_features <= DRY_BEAN_FEATURE_COUNT:
            raise ValueError("Dry Bean original feature budget must be between 1 and 16")

    @property
    def budget_kind(self) -> str:
        return "original_features"


@dataclass(frozen=True)
class PCARepresentation:
    n_components: int
    required_raw_feature_count: int = DRY_BEAN_FEATURE_COUNT

    def __post_init__(self) -> None:
        if not 1 <= self.n_components <= DRY_BEAN_FEATURE_COUNT:
            raise ValueError("Dry Bean PCA components must be between 1 and 16")
        if self.required_raw_feature_count != DRY_BEAN_FEATURE_COUNT:
            raise ValueError("PCA representation requires all 16 raw Dry Bean features")

    @property
    def budget_kind(self) -> str:
        return "pca_components"


@dataclass(frozen=True)
class ScientificResultRef:
    """A future persisted result can only point to a real validated artifact."""

    state: ResultState = ResultState.NOT_CALCULATED
    artifact_relative_path: str | None = None

    def __post_init__(self) -> None:
        if self.state is ResultState.CALCULATED and not self.artifact_relative_path:
            raise ValueError("Calculated result requires an artifact reference")
        if self.state is ResultState.NOT_CALCULATED and self.artifact_relative_path:
            raise ValueError("Uncalculated result cannot reference an artifact")
