import pytest

from beanfeature_research.contracts import (
    ModelId,
    OriginalFeatureBudget,
    PCARepresentation,
    ResultState,
    RunStatus,
    ScientificResultRef,
    SelectorId,
    assert_transition,
)


def test_model_and_selector_ids_are_stable() -> None:
    assert {item.value for item in ModelId} == {
        "logistic_regression",
        "svm_rbf",
        "random_forest",
        "xgboost",
        "lightgbm",
        "mlp",
    }
    assert {item.value for item in SelectorId} >= {
        "mutual_information",
        "anova",
        "rfe",
        "l1_logistic",
        "tree_importance",
        "pca",
    }


def test_original_budget_is_not_pca_representation() -> None:
    assert OriginalFeatureBudget(4).k_original_features == 4
    assert PCARepresentation(4).n_components == 4
    assert PCARepresentation(4).required_raw_feature_count == 16
    assert OriginalFeatureBudget(4).budget_kind != PCARepresentation(4).budget_kind
    with pytest.raises(ValueError):
        OriginalFeatureBudget(0)
    with pytest.raises(ValueError):
        OriginalFeatureBudget(17)
    with pytest.raises(ValueError):
        PCARepresentation(4, required_raw_feature_count=4)


def test_execution_state_and_result_state_are_distinct() -> None:
    assert RunStatus.QUEUED != ResultState.NOT_CALCULATED
    with pytest.raises(ValueError, match="validated scientific results"):
        assert_transition(RunStatus.RUNNING, RunStatus.COMPLETED)
    with pytest.raises(ValueError):
        assert_transition(RunStatus.QUEUED, RunStatus.COMPLETED, has_result=True)
    with pytest.raises(ValueError):
        ScientificResultRef(ResultState.CALCULATED)
    assert ScientificResultRef().artifact_relative_path is None
