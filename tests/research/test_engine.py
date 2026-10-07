"""Small synthetic fixtures test mechanics, never reported as Dry Bean findings."""

import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import make_classification
from sklearn.feature_selection import RFE, SelectFromModel, SelectKBest
from sklearn.pipeline import Pipeline

from beanfeature_research.contracts import ModelId, SelectorId
from beanfeature_research.engine import (
    EngineCondition,
    NestedResult,
    build_pipeline,
    outer_splits,
    paired_comparison,
    preset_search_space,
    run_nested_cv,
)


@pytest.fixture
def synthetic_classification() -> tuple[pd.DataFrame, np.ndarray]:
    features, target = make_classification(
        n_samples=140,
        n_features=16,
        n_informative=10,
        n_redundant=0,
        n_classes=7,
        n_clusters_per_class=1,
        random_state=17,
    )
    return pd.DataFrame(features, columns=[f"feature_{index}" for index in range(16)]), target


def condition(*, seed: int = 42, mode: str = "smoke") -> EngineCondition:
    return EngineCondition(
        model=ModelId.LOGISTIC_REGRESSION,
        selector=SelectorId.MUTUAL_INFORMATION,
        budget_kind="original_features",
        k_original_features=4,
        n_components=None,
        seed=seed,
        search_space=preset_search_space(ModelId.LOGISTIC_REGRESSION, smoke=mode == "smoke"),
        evaluation_mode=mode,
    )


def test_outer_splits_reproducible_and_shared(synthetic_classification) -> None:
    _, target = synthetic_classification
    first = outer_splits(target, 42)
    second = outer_splits(target, 42)
    assert len(first) == 15
    for (train_a, test_a), (train_b, test_b) in zip(first, second, strict=True):
        np.testing.assert_array_equal(train_a, train_b)
        np.testing.assert_array_equal(test_a, test_b)
        assert set(train_a).isdisjoint(test_a)
    assert any(
        not np.array_equal(a[1], b[1]) for a, b in zip(first, outer_splits(target, 43), strict=True)
    )


def test_selector_and_scaler_are_fold_local_pipeline_steps() -> None:
    pipeline = build_pipeline(condition())
    assert isinstance(pipeline, Pipeline)
    assert isinstance(pipeline.named_steps["select"], SelectKBest)
    assert not hasattr(pipeline.named_steps["select"], "scores_")
    with pytest.raises(ValueError, match="PCA cannot"):
        EngineCondition(
            ModelId.LOGISTIC_REGRESSION,
            SelectorId.PCA,
            "pca_components",
            4,
            4,
            42,
            preset_search_space(ModelId.LOGISTIC_REGRESSION),
        )


def test_engine_rejects_target_column_among_predictors(synthetic_classification) -> None:
    features, target = synthetic_classification
    features = features.rename(columns={"feature_0": "Class"})
    with pytest.raises(ValueError, match="Target column"):
        run_nested_cv(features, target, condition())


def test_real_synthetic_end_to_end_smoke_and_no_outer_leakage(
    synthetic_classification, monkeypatch
) -> None:
    features, target = synthetic_classification
    fit_sizes: list[int] = []
    original_fit = SelectKBest.fit

    def recording_fit(self, X, y=None):
        fit_sizes.append(len(X))
        return original_fit(self, X, y)

    monkeypatch.setattr(SelectKBest, "fit", recording_fit)
    result = run_nested_cv(features, target, condition())
    assert len(result.folds) == 2
    assert len(result.splits) == 2
    assert all(size < len(features) for size in fit_sizes)
    assert any(size < min(fold["train_size"] for fold in result.folds) for size in fit_sizes)
    assert result.summary["outer_fold_count"] == 2
    assert result.summary["sufficient_k"] is None
    for fold in result.folds:
        assert len(fold["selected_original_features"]) == 4
        assert sum(map(sum, fold["confusion_matrix"])) == fold["test_size"]
        assert 0 <= fold["macro_f1"] <= 1
        assert len(fold["y_true"]) == fold["test_size"]


def test_paired_comparison_rejects_smoke_and_misaligned_folds(synthetic_classification) -> None:
    features, target = synthetic_classification
    smoke = run_nested_cv(features, target, condition())
    with pytest.raises(ValueError, match="Smoke results"):
        paired_comparison(smoke, smoke)


def _paired_fixture(
    losses: list[float], *, compact_k: int = 4
) -> tuple[NestedResult, NestedResult]:
    compact_folds = []
    baseline_folds = []
    for index, loss in enumerate(losses):
        fold = f"r{index // 5 + 1:02d}-f{index % 5 + 1:02d}"
        split = f"split-{index}"
        compact_folds.append({"fold_id": fold, "split_sha256": split, "macro_f1": 0.8})
        baseline_folds.append({"fold_id": fold, "split_sha256": split, "macro_f1": 0.8 + loss})
    compact = NestedResult(
        compact_folds,
        {
            "evaluation_mode": "protocol",
            "model": "logistic_regression",
            "budget_kind": "original_features",
            "k_original_features": compact_k,
        },
        [],
    )
    baseline = NestedResult(
        baseline_folds,
        {
            "evaluation_mode": "protocol",
            "model": "logistic_regression",
            "budget_kind": "original_features",
            "k_original_features": 16,
        },
        [],
    )
    return compact, baseline


def test_corrected_repeated_cv_interval_uses_predeclared_formula() -> None:
    losses = [0.001 * index for index in range(15)]
    compact, baseline = _paired_fixture(losses)
    first = paired_comparison(compact, baseline)
    second = paired_comparison(compact, baseline)
    sample_variance = np.var(losses, ddof=1)
    expected = ((1 / 15 + 1 / 4) * sample_variance) ** 0.5
    naive = sample_variance**0.5 / 15**0.5
    assert first == second
    assert first["corrected_standard_error"] == pytest.approx(expected)
    assert first["corrected_standard_error"] != pytest.approx(naive)
    assert first["comparison_alpha"] == pytest.approx(0.05 / 15)
    assert first["multiplicity_method"] == "bonferroni-within-model-15-one-sided"
    assert first["interval_method"] == "nadeau-bengio-corrected-resampled-t-v1"


def test_sufficiency_rejects_fold_mismatch_and_k16_candidate() -> None:
    compact, baseline = _paired_fixture([0.001] * 15)
    baseline.folds[2]["split_sha256"] = "different"
    with pytest.raises(ValueError, match="Outer folds differ"):
        paired_comparison(compact, baseline)
    full, reference = _paired_fixture([0.001] * 15, compact_k=16)
    with pytest.raises(ValueError, match="fewer than 16"):
        paired_comparison(full, reference)


@pytest.mark.parametrize(
    ("selector", "model"),
    [
        (SelectorId.MUTUAL_INFORMATION, ModelId.LOGISTIC_REGRESSION),
        (SelectorId.ANOVA, ModelId.SVM_RBF),
        (SelectorId.RFE, ModelId.LOGISTIC_REGRESSION),
        (SelectorId.TREE_IMPORTANCE, ModelId.RANDOM_FOREST),
        (SelectorId.PCA, ModelId.LOGISTIC_REGRESSION),
    ],
)
def test_core_selector_pipeline_contract(
    selector: SelectorId, model: ModelId, synthetic_classification
) -> None:
    pca = selector is SelectorId.PCA
    selected = EngineCondition(
        model,
        selector,
        "pca_components" if pca else "original_features",
        None if pca else 4,
        4 if pca else None,
        42,
        preset_search_space(model, smoke=True),
        "smoke",
    )
    pipeline = build_pipeline(selected)
    assert list(pipeline.named_steps) == ["scale", "select", "model"]
    features, target = synthetic_classification
    pipeline.fit(features.iloc[:112], target[:112])
    transformed = pipeline[:-1].transform(features.iloc[112:])
    assert transformed.shape == (28, 4)


def test_rfe_and_tree_ranking_estimators_follow_frozen_model_branch() -> None:
    svm_rfe = EngineCondition(
        ModelId.SVM_RBF,
        SelectorId.RFE,
        "original_features",
        4,
        None,
        42,
        preset_search_space(ModelId.SVM_RBF, smoke=True),
        "smoke",
        {"estimator": "linear_svm"},
    )
    rfe = build_pipeline(svm_rfe).named_steps["select"]
    assert isinstance(rfe, RFE)
    assert rfe.estimator.__class__.__name__ == "LinearSVC"

    xgb_tree = EngineCondition(
        ModelId.XGBOOST,
        SelectorId.TREE_IMPORTANCE,
        "original_features",
        4,
        None,
        42,
        preset_search_space(ModelId.XGBOOST, smoke=True),
        "smoke",
        {"estimator": "xgboost"},
    )
    tree = build_pipeline(xgb_tree).named_steps["select"]
    assert isinstance(tree, SelectFromModel)
    assert tree.estimator.__class__.__name__ == "XGBClassifier"

    wrong = EngineCondition(
        ModelId.SVM_RBF,
        SelectorId.RFE,
        "original_features",
        4,
        None,
        42,
        preset_search_space(ModelId.SVM_RBF, smoke=True),
        "smoke",
        {"estimator": "logistic_regression"},
    )
    with pytest.raises(ValueError, match="conflicts"):
        build_pipeline(wrong)


def test_l1_sparse_path_records_observed_nonzero_features(synthetic_classification) -> None:
    features, target = synthetic_classification
    condition = EngineCondition(
        ModelId.LOGISTIC_REGRESSION,
        SelectorId.L1_LOGISTIC,
        "sparse_original_features",
        None,
        None,
        42,
        preset_search_space(ModelId.LOGISTIC_REGRESSION, smoke=True),
        "smoke",
        {"estimator": "l1_logistic", "C": 0.1},
    )
    pipeline = build_pipeline(condition)
    pipeline.fit(features.iloc[:112], target[:112])
    selector = pipeline.named_steps["select"]
    transformed = pipeline[:-1].transform(features.iloc[112:])
    assert 1 <= selector.observed_nonzero_count_ <= 16
    assert transformed.shape == (28, selector.observed_nonzero_count_)

    with pytest.raises(ValueError, match="fixed-k"):
        EngineCondition(
            ModelId.LOGISTIC_REGRESSION,
            SelectorId.L1_LOGISTIC,
            "original_features",
            4,
            None,
            42,
            preset_search_space(ModelId.LOGISTIC_REGRESSION, smoke=True),
            "smoke",
        )


@pytest.mark.parametrize(
    "condition",
    [
        EngineCondition(
            ModelId.SVM_RBF,
            SelectorId.ANOVA,
            "original_features",
            4,
            None,
            42,
            preset_search_space(ModelId.SVM_RBF, smoke=True),
            "smoke",
        ),
        EngineCondition(
            ModelId.LOGISTIC_REGRESSION,
            SelectorId.RFE,
            "original_features",
            4,
            None,
            42,
            preset_search_space(ModelId.LOGISTIC_REGRESSION, smoke=True),
            "smoke",
            {"estimator": "logistic_regression"},
        ),
        EngineCondition(
            ModelId.RANDOM_FOREST,
            SelectorId.TREE_IMPORTANCE,
            "original_features",
            4,
            None,
            42,
            preset_search_space(ModelId.RANDOM_FOREST, smoke=True),
            "smoke",
            {"estimator": "random_forest"},
        ),
        EngineCondition(
            ModelId.LOGISTIC_REGRESSION,
            SelectorId.L1_LOGISTIC,
            "sparse_original_features",
            None,
            None,
            42,
            preset_search_space(ModelId.LOGISTIC_REGRESSION, smoke=True),
            "smoke",
            {"estimator": "l1_logistic", "C": 10.0},
        ),
        EngineCondition(
            ModelId.LOGISTIC_REGRESSION,
            SelectorId.PCA,
            "pca_components",
            None,
            4,
            42,
            preset_search_space(ModelId.LOGISTIC_REGRESSION, smoke=True),
            "smoke",
        ),
    ],
    ids=["anova", "rfe", "tree", "l1-sparse", "pca"],
)
def test_comparator_branch_nested_cv_smoke(
    condition: EngineCondition, synthetic_classification
) -> None:
    features, target = synthetic_classification
    result = run_nested_cv(features, target, condition)
    assert len(result.folds) == 2
    assert result.summary["outer_fold_count"] == 2
    assert result.summary["selector"] == condition.selector.value
    assert all(0 <= fold["macro_f1"] <= 1 for fold in result.folds)
    if condition.selector is SelectorId.PCA:
        assert all(fold["selected_original_features"] is None for fold in result.folds)
        assert all(fold["representation"]["n_components"] == 4 for fold in result.folds)
    else:
        assert all(fold["selected_original_features"] for fold in result.folds)


@pytest.mark.parametrize("model", list(ModelId))
def test_core_model_can_fit_inside_pipeline(model: ModelId, synthetic_classification) -> None:
    features, target = synthetic_classification
    chosen = EngineCondition(
        model,
        SelectorId.NONE,
        "original_features",
        16,
        None,
        42,
        preset_search_space(model, smoke=True),
        "smoke",
    )
    pipeline = build_pipeline(chosen)
    pipeline.fit(features.iloc[:112], target[:112])
    assert len(pipeline.predict(features.iloc[112:])) == 28
