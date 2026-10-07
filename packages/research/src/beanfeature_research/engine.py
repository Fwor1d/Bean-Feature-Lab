"""Leakage-safe nested CV for one predeclared scientific condition."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from hashlib import sha256
from io import BytesIO
from statistics import mean, median, stdev, variance
from time import perf_counter_ns
from typing import Literal

import joblib
import numpy as np
import pandas as pd
from scipy.stats import t as student_t
from sklearn.base import BaseEstimator, TransformerMixin, clone
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import (
    RFE,
    SelectFromModel,
    SelectKBest,
    f_classif,
    mutual_info_classif,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score, roc_auc_score
from sklearn.model_selection import GridSearchCV, RepeatedStratifiedKFold, StratifiedKFold
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from .contracts import ModelId, OriginalFeatureBudget, PCARepresentation, SelectorId
from .dataset import TARGET

CV_PROTOCOL_VERSION = "dry-bean-nested-5x3-4-v1"
SMOKE_PROTOCOL_VERSION = "integration-smoke-2x1-2-v1"
SEARCH_SPACE_VERSION = "small-grid-v1"
SUFFICIENCY_INTERVAL_VERSION = "nadeau-bengio-corrected-resampled-t-v1"
SUFFICIENCY_MARGIN = 0.01
SUFFICIENCY_FAMILY_ALPHA = 0.05
SUFFICIENCY_COMPARISONS = 15
OUTER_TEST_TRAIN_RATIO = 1 / 4


def preset_search_space(model: ModelId, *, smoke: bool = False) -> dict[str, list[object]]:
    """Freeze small, explicit grids before any outer-test results are inspected."""
    spaces: dict[ModelId, dict[str, list[object]]] = {
        ModelId.LOGISTIC_REGRESSION: {"model__C": [0.1, 1.0]},
        ModelId.SVM_RBF: {"model__C": [1.0, 10.0]},
        ModelId.RANDOM_FOREST: {"model__max_depth": [None, 20]},
        ModelId.XGBOOST: {"model__max_depth": [3, 5]},
        ModelId.LIGHTGBM: {"model__num_leaves": [15, 31]},
        ModelId.MLP: {"model__alpha": [0.001, 0.01]},
    }
    space = spaces[model]
    return {key: values[:1] if smoke else values[:] for key, values in space.items()}


class L1TopK(BaseEstimator, TransformerMixin):
    """Fold-local embedded ranking, retaining exactly k measured columns."""

    def __init__(self, k: int, seed: int = 42, C: float = 0.3) -> None:
        self.k = k
        self.seed = seed
        self.C = C

    def fit(self, X: np.ndarray, y: np.ndarray) -> "L1TopK":
        self.estimator_ = LogisticRegression(
            l1_ratio=1.0, solver="saga", C=self.C, max_iter=1200, random_state=self.seed
        ).fit(X, y)
        importance = np.max(np.abs(self.estimator_.coef_), axis=0)
        self.observed_nonzero_count_ = int(np.count_nonzero(importance))
        self.support_ = np.zeros(X.shape[1], dtype=bool)
        self.support_[np.argsort(-importance, kind="stable")[: self.k]] = True
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        return X[:, self.get_support()]

    def get_support(self) -> np.ndarray:
        if not hasattr(self, "support_"):
            raise ValueError("L1 selector has not been fitted")
        return self.support_


@dataclass(frozen=True)
class EngineCondition:
    model: ModelId
    selector: SelectorId
    budget_kind: Literal["original_features", "pca_components"]
    k_original_features: int | None
    n_components: int | None
    seed: int
    search_space: dict[str, list[object]]
    evaluation_mode: Literal["protocol", "smoke"] = "protocol"

    def __post_init__(self) -> None:
        if self.evaluation_mode not in ("protocol", "smoke"):
            raise ValueError("Unknown evaluation mode")
        if self.budget_kind not in ("original_features", "pca_components"):
            raise ValueError("Unknown feature-budget representation")
        if self.budget_kind == "pca_components":
            if self.selector is not SelectorId.PCA or self.k_original_features is not None:
                raise ValueError("PCA cannot be an original-feature budget")
            PCARepresentation(self.n_components or 0)
        else:
            if self.selector is SelectorId.PCA or self.n_components is not None:
                raise ValueError("Original-feature budget cannot use PCA")
            OriginalFeatureBudget(self.k_original_features or 0)
            if self.selector is SelectorId.NONE and self.k_original_features != 16:
                raise ValueError("No-selector baseline requires all 16 original features")
        if not self.search_space or any(not values for values in self.search_space.values()):
            raise ValueError("A frozen, nonempty hyperparameter search space is required")


@dataclass(frozen=True)
class NestedResult:
    folds: list[dict[str, object]]
    summary: dict[str, object]
    splits: list[dict[str, object]]


def outer_splits(
    y: np.ndarray, seed: int, mode: str = "protocol"
) -> list[tuple[np.ndarray, np.ndarray]]:
    n_splits, n_repeats = (5, 3) if mode == "protocol" else (2, 1)
    cv = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=seed)
    return list(cv.split(np.zeros(len(y)), y))


def _estimator(model: ModelId, seed: int) -> BaseEstimator:
    if model is ModelId.LOGISTIC_REGRESSION:
        return LogisticRegression(max_iter=800, random_state=seed)
    if model is ModelId.SVM_RBF:
        return SVC(kernel="rbf", random_state=seed)
    if model is ModelId.RANDOM_FOREST:
        return RandomForestClassifier(
            n_estimators=120, min_samples_leaf=2, n_jobs=1, random_state=seed
        )
    if model is ModelId.XGBOOST:
        from xgboost import XGBClassifier

        return XGBClassifier(
            n_estimators=120,
            learning_rate=0.1,
            subsample=0.9,
            colsample_bytree=0.9,
            tree_method="hist",
            n_jobs=1,
            eval_metric="mlogloss",
            random_state=seed,
        )
    if model is ModelId.LIGHTGBM:
        from lightgbm import LGBMClassifier

        return LGBMClassifier(
            n_estimators=120, learning_rate=0.1, verbosity=-1, n_jobs=1, random_state=seed
        )
    if model is ModelId.MLP:
        return MLPClassifier(
            hidden_layer_sizes=(32,),
            max_iter=160,
            early_stopping=True,
            n_iter_no_change=12,
            random_state=seed,
        )
    raise ValueError(f"Unsupported model: {model}")


def build_pipeline(condition: EngineCondition) -> Pipeline:
    """Every learned step is constructed inside the estimator passed to GridSearchCV."""
    k = condition.k_original_features
    seed = condition.seed
    use_scale = condition.model in (ModelId.LOGISTIC_REGRESSION, ModelId.SVM_RBF, ModelId.MLP)
    use_scale = use_scale or condition.selector in (
        SelectorId.RFE,
        SelectorId.L1_LOGISTIC,
        SelectorId.PCA,
    )
    if condition.selector is SelectorId.NONE:
        selector: object = "passthrough"
    elif condition.selector is SelectorId.MUTUAL_INFORMATION:
        selector = SelectKBest(partial(mutual_info_classif, random_state=seed, n_jobs=1), k=k)
    elif condition.selector is SelectorId.ANOVA:
        selector = SelectKBest(f_classif, k=k)
    elif condition.selector is SelectorId.RFE:
        selector = RFE(LogisticRegression(max_iter=800, random_state=seed), n_features_to_select=k)
    elif condition.selector is SelectorId.L1_LOGISTIC:
        selector = L1TopK(k=k or 0, seed=seed)
    elif condition.selector is SelectorId.TREE_IMPORTANCE:
        selector = SelectFromModel(
            RandomForestClassifier(n_estimators=80, n_jobs=1, random_state=seed),
            threshold=-np.inf,
            max_features=k,
        )
    elif condition.selector is SelectorId.PCA:
        selector = PCA(n_components=condition.n_components, random_state=seed)
    else:
        raise ValueError(f"Selector {condition.selector} is Extended, not implemented in Core")
    return Pipeline(
        [
            ("scale", StandardScaler() if use_scale else "passthrough"),
            ("select", selector),
            ("model", _estimator(condition.model, seed)),
        ]
    )


def _split_hash(train: np.ndarray, test: np.ndarray) -> str:
    payload = json.dumps([train.tolist(), test.tolist()], separators=(",", ":")).encode()
    return sha256(payload).hexdigest()


def _latency(pipeline: Pipeline, X: pd.DataFrame, repeats: int) -> dict[str, object]:
    result: dict[str, object] = {
        "method": "full_pipeline_predict_warmup_median_p95",
        "repeats": repeats,
    }
    for label, size in (("single_row", 1), ("batch_1000", min(1000, len(X)))):
        sample = X.iloc[:size]
        pipeline.predict(sample)  # warm-up excluded from measurements
        times = []
        for _ in range(repeats):
            started = perf_counter_ns()
            pipeline.predict(sample)
            times.append((perf_counter_ns() - started) / 1_000_000)
        result[label] = {
            "rows": size,
            "median_ms": median(times),
            "p95_ms": float(np.percentile(times, 95)),
            "samples_ms": times,
        }
    return result


def run_nested_cv(
    X: pd.DataFrame,
    y: np.ndarray,
    condition: EngineCondition,
    *,
    on_fold: Callable[[dict[str, object]], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> NestedResult:
    if len(X) != len(y) or len(X.columns) != 16 or len(set(X.columns)) != 16:
        raise ValueError("Expected 16 distinct numeric predictors aligned with target")
    if TARGET in X.columns:
        raise ValueError("Target column cannot appear among predictors")
    if any(not pd.api.types.is_numeric_dtype(X[column]) for column in X.columns):
        raise ValueError("Non-numeric predictor")
    labels = sorted({str(label) for label in y})
    if len(labels) < 2:
        raise ValueError("At least two target classes required")
    label_indices = {label: index for index, label in enumerate(labels)}
    encoded = np.array([label_indices[str(label)] for label in y], dtype=np.int64)
    inner_folds = 4 if condition.evaluation_mode == "protocol" else 2
    split_pairs = outer_splits(encoded, condition.seed, condition.evaluation_mode)
    folds: list[dict[str, object]] = []
    manifests: list[dict[str, object]] = []
    for index, (train, test) in enumerate(split_pairs):
        if should_cancel and should_cancel():
            raise InterruptedError("Run cancelled before next outer fold")
        outer_folds = 5 if condition.evaluation_mode == "protocol" else 2
        fold_id = f"r{index // outer_folds + 1:02d}-f{index % outer_folds + 1:02d}"
        split_hash = _split_hash(train, test)
        manifests.append(
            {
                "fold_id": fold_id,
                "split_sha256": split_hash,
                "train_indices": train.tolist(),
                "test_indices": test.tolist(),
            }
        )
        inner_seed = condition.seed + 1000 + index
        inner = StratifiedKFold(n_splits=inner_folds, shuffle=True, random_state=inner_seed)
        pipeline = build_pipeline(condition)
        search = GridSearchCV(
            pipeline,
            condition.search_space,
            scoring="f1_macro",
            cv=inner,
            refit=False,
            n_jobs=1,
            error_score="raise",
        )
        X_train, X_test = X.iloc[train], X.iloc[test]
        y_train, y_test = encoded[train], encoded[test]
        search_started = perf_counter_ns()
        search.fit(X_train, y_train)
        search_seconds = (perf_counter_ns() - search_started) / 1_000_000_000
        fitted = clone(pipeline).set_params(**search.best_params_)
        fit_started = perf_counter_ns()
        fitted.fit(X_train, y_train)
        refit_seconds = (perf_counter_ns() - fit_started) / 1_000_000_000
        predictions = fitted.predict(X_test)
        recalls = recall_score(
            y_test, predictions, labels=np.arange(len(labels)), average=None, zero_division=0
        )
        auc: float | None = None
        auc_reason: str | None = None
        if hasattr(fitted, "predict_proba"):
            probabilities = fitted.predict_proba(X_test)
            auc = float(
                roc_auc_score(
                    y_test,
                    probabilities,
                    labels=np.arange(len(labels)),
                    multi_class="ovr",
                    average="macro",
                )
            )
        else:
            auc_reason = "No calibrated multiclass probabilities; decision scores not substituted"
        selected: list[str] | None = None
        representation: dict[str, object] = {"budget_kind": condition.budget_kind}
        selector = fitted.named_steps["select"]
        if condition.budget_kind == "original_features":
            selected = (
                list(X.columns)
                if selector == "passthrough"
                else list(X.columns[selector.get_support()])
            )
            representation["k_original_features"] = len(selected)
            if isinstance(selector, L1TopK):
                representation["observed_nonzero_count"] = selector.observed_nonzero_count_
        else:
            representation.update(
                {
                    "n_components": condition.n_components,
                    "required_raw_feature_count": 16,
                    "explained_variance_ratio": selector.explained_variance_ratio_.tolist(),
                }
            )
        serialized = BytesIO()
        joblib.dump(fitted, serialized, compress=0)
        fold: dict[str, object] = {
            "fold_id": fold_id,
            "split_sha256": split_hash,
            "inner_seed": inner_seed,
            "train_size": len(train),
            "test_size": len(test),
            "best_params": search.best_params_,
            "inner_best_macro_f1": float(search.best_score_),
            "selected_original_features": selected,
            "representation": representation,
            "macro_f1": float(f1_score(y_test, predictions, average="macro")),
            "accuracy": float(accuracy_score(y_test, predictions)),
            "per_class_recall": dict(zip(labels, map(float, recalls), strict=True)),
            "confusion_matrix": confusion_matrix(
                y_test, predictions, labels=np.arange(len(labels))
            ).tolist(),
            "roc_auc_ovr_macro": auc,
            "roc_auc_reason": auc_reason,
            "search_seconds": search_seconds,
            "refit_seconds": refit_seconds,
            "search_plus_refit_seconds": search_seconds + refit_seconds,
            "inference_latency": _latency(
                fitted, X_test, 3 if condition.evaluation_mode == "smoke" else 5
            ),
            "serialized_pipeline_bytes": serialized.tell(),
            "peak_memory_bytes": None,
            "peak_memory_reason": "Not measured: no reliable isolated process-tree RSS sampler",
            "y_true": [labels[int(item)] for item in y_test],
            "y_pred": [labels[int(item)] for item in predictions],
            "model": condition.model.value,
            "selector": condition.selector.value,
        }
        folds.append(fold)
        if on_fold:
            on_fold(fold)
    scores = [float(fold["macro_f1"]) for fold in folds]
    accuracies = [float(fold["accuracy"]) for fold in folds]
    stability: dict[str, object] | None = None
    if condition.budget_kind == "original_features" and condition.selector is not SelectorId.NONE:
        sets = [set(fold["selected_original_features"]) for fold in folds]
        frequency = {name: sum(name in chosen for chosen in sets) / len(sets) for name in X.columns}
        jaccard = [len(a & b) / len(a | b) for i, a in enumerate(sets) for b in sets[i + 1 :]]
        stability = {
            "selection_frequency": frequency,
            "pairwise_jaccard_mean": mean(jaccard) if jaccard else None,
            "pairwise_jaccard_values": jaccard,
            "note": "Descriptive across dependent repeated-CV folds",
        }
    summary: dict[str, object] = {
        "evaluation_mode": condition.evaluation_mode,
        "cv_protocol_version": CV_PROTOCOL_VERSION
        if condition.evaluation_mode == "protocol"
        else SMOKE_PROTOCOL_VERSION,
        "search_space_version": SEARCH_SPACE_VERSION,
        "search_space": condition.search_space,
        "model": condition.model.value,
        "selector": condition.selector.value,
        "seed": condition.seed,
        "outer_split_set_sha256": sha256(
            "".join(str(fold["split_sha256"]) for fold in folds).encode()
        ).hexdigest(),
        "budget_kind": condition.budget_kind,
        "k_original_features": condition.k_original_features,
        "n_components": condition.n_components,
        "required_raw_feature_count": 16
        if condition.budget_kind == "pca_components"
        else condition.k_original_features,
        "outer_fold_count": len(folds),
        "inner_fold_count": inner_folds,
        "macro_f1_mean": mean(scores),
        "macro_f1_fold_sd_descriptive": stdev(scores) if len(scores) > 1 else None,
        "accuracy_mean": mean(accuracies),
        "repeat_macro_f1_means": [
            mean(scores[i : i + (5 if condition.evaluation_mode == "protocol" else 2)])
            for i in range(0, len(scores), 5 if condition.evaluation_mode == "protocol" else 2)
        ],
        "dispersion_note": (
            "Repeated-CV folds overlap; fold SD is descriptive, not an independent-sample CI"
        ),
        "feature_stability": stability,
        "sufficient_k": None,
        "sufficiency_status": "NOT_ASSESSED_INTERVAL_METHOD_UNAPPROVED",
        "sufficiency_margin_macro_f1": 0.01,
    }
    return NestedResult(folds, summary, manifests)


def paired_comparison(compact: NestedResult, baseline: NestedResult) -> dict[str, object]:
    if (
        compact.summary["evaluation_mode"] != "protocol"
        or baseline.summary["evaluation_mode"] != "protocol"
    ):
        raise ValueError("Smoke results cannot support sufficient-k analysis")
    if compact.summary["model"] != baseline.summary["model"]:
        raise ValueError("Paired comparison requires the same model")
    if (
        compact.summary["budget_kind"] != "original_features"
        or not 1 <= compact.summary["k_original_features"] < 16
    ):
        raise ValueError("Compact run must use fewer than 16 original features")
    if (
        baseline.summary["k_original_features"] != 16
        or baseline.summary["budget_kind"] != "original_features"
    ):
        raise ValueError("Baseline must have all 16 original features")
    losses = []
    for small, full in zip(compact.folds, baseline.folds, strict=True):
        if (small["fold_id"], small["split_sha256"]) != (full["fold_id"], full["split_sha256"]):
            raise ValueError("Outer folds differ; paired comparison is invalid")
        losses.append(
            {
                "fold_id": small["fold_id"],
                "loss_macro_f1": float(full["macro_f1"]) - float(small["macro_f1"]),
            }
        )
    values = [item["loss_macro_f1"] for item in losses]
    n = len(values)
    if n != 15:
        raise ValueError("Corrected sufficient-k analysis requires 15 paired outer folds")
    sample_variance = variance(values)
    corrected_variance = (1 / n + OUTER_TEST_TRAIN_RATIO) * sample_variance
    corrected_se = corrected_variance**0.5
    adjusted_alpha = SUFFICIENCY_FAMILY_ALPHA / SUFFICIENCY_COMPARISONS
    critical_value = float(student_t.ppf(1 - adjusted_alpha, df=n - 1))
    mean_loss = mean(values)
    upper_bound = mean_loss + critical_value * corrected_se
    sufficient = upper_bound <= SUFFICIENCY_MARGIN
    return {
        "interval_method": SUFFICIENCY_INTERVAL_VERSION,
        "margin_macro_f1": SUFFICIENCY_MARGIN,
        "family_alpha": SUFFICIENCY_FAMILY_ALPHA,
        "comparison_alpha": adjusted_alpha,
        "multiplicity_method": "bonferroni-within-model-15-one-sided",
        "n_paired_folds": n,
        "test_train_ratio": OUTER_TEST_TRAIN_RATIO,
        "paired_losses": losses,
        "mean_loss": mean_loss,
        "sample_variance": sample_variance,
        "corrected_variance": corrected_variance,
        "corrected_standard_error": corrected_se,
        "critical_value": critical_value,
        "one_sided_upper_confidence_bound": upper_bound,
        "decision": "sufficient" if sufficient else "not_sufficient",
        "sufficient_k": compact.summary["k_original_features"] if sufficient else None,
        "status": "CALCULATED",
    }
