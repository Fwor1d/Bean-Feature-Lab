"""Small synthetic fixtures test mechanics, never reported as Dry Bean findings."""

import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import make_classification
from sklearn.feature_selection import SelectKBest
from sklearn.pipeline import Pipeline

from beanfeature_research.contracts import ModelId, SelectorId
from beanfeature_research.engine import (
    EngineCondition,
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


@pytest.mark.parametrize(
    "selector",
    [
        SelectorId.MUTUAL_INFORMATION,
        SelectorId.ANOVA,
        SelectorId.RFE,
        SelectorId.L1_LOGISTIC,
        SelectorId.TREE_IMPORTANCE,
        SelectorId.PCA,
    ],
)
def test_core_selector_pipeline_contract(selector: SelectorId, synthetic_classification) -> None:
    pca = selector is SelectorId.PCA
    selected = EngineCondition(
        ModelId.LOGISTIC_REGRESSION,
        selector,
        "pca_components" if pca else "original_features",
        None if pca else 4,
        4 if pca else None,
        42,
        preset_search_space(ModelId.LOGISTIC_REGRESSION, smoke=True),
        "smoke",
    )
    pipeline = build_pipeline(selected)
    assert list(pipeline.named_steps) == ["scale", "select", "model"]
    features, target = synthetic_classification
    pipeline.fit(features.iloc[:112], target[:112])
    transformed = pipeline[:-1].transform(features.iloc[112:])
    assert transformed.shape == (28, 4)


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
