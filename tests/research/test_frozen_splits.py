"""Recorded split mechanics only: no estimator is trained by these regressions."""

import copy
from dataclasses import replace
from hashlib import sha256

import numpy as np
import pandas as pd
import pytest

from beanfeature_research import engine
from beanfeature_research.contracts import ModelId, SelectorId
from beanfeature_research.engine import (
    CV_PROTOCOL_VERSION,
    EngineCondition,
    _split_hash,
    outer_splits,
    preset_search_space,
    validated_frozen_outer_splits,
)


def recorded_manifest():
    target = np.repeat(np.arange(7), 20)
    records = []
    for index, (train, test) in enumerate(outer_splits(target, 42)):
        # Preserve recorded row order too; regeneration/sorting would silently change it.
        train = train[::-1]
        records.append(
            {
                "fold_id": f"r{index // 5 + 1:02d}-f{index % 5 + 1:02d}",
                "train_indices": train.tolist(),
                "test_indices": test.tolist(),
                "split_sha256": _split_hash(train, test),
            }
        )
    manifest = {
        "dataset_hash": "a" * 64,
        "dataset_version": "test-only-v1",
        "seed": 42,
        "rows": len(target),
        "cv_protocol_version": CV_PROTOCOL_VERSION,
        "splits": records,
    }
    reseal(manifest)
    return target, manifest


def reseal(manifest):
    for record in manifest["splits"]:
        record["split_sha256"] = _split_hash(
            np.array(record["train_indices"]), np.array(record["test_indices"])
        )
    manifest["outer_split_set_sha256"] = sha256(
        "".join(r["split_sha256"] for r in manifest["splits"]).encode()
    ).hexdigest()


def validate(manifest, target):
    return validated_frozen_outer_splits(
        manifest, target, seed=42, dataset_hash="a" * 64, dataset_version="test-only-v1"
    )


def test_consumes_all_recorded_indices_and_order_without_regeneration(monkeypatch):
    target, manifest = recorded_manifest()
    original = copy.deepcopy(manifest)
    monkeypatch.setattr(engine, "outer_splits", lambda *a, **k: pytest.fail("Regenerated splits"))
    pairs = validate(manifest, target)
    for (train, test), record in zip(pairs, manifest["splits"], strict=True):
        assert train.tolist() == record["train_indices"]
        assert test.tolist() == record["test_indices"]
    assert manifest == original


@pytest.mark.parametrize(
    "field,value",
    [
        ("dataset_hash", "b" * 64),
        ("dataset_version", "other"),
        ("seed", 43),
        ("seed", True),
        ("rows", 141),
        ("cv_protocol_version", "unsupported"),
    ],
)
def test_rejects_incompatible_identity(field, value):
    target, manifest = recorded_manifest()
    manifest[field] = value
    with pytest.raises(ValueError, match="incompatible"):
        validate(manifest, target)


@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "missing_folds",
        "partial",
        "order",
        "row_hash",
        "set_hash",
        "negative",
        "out_of_range",
        "bool",
        "float",
        "overlap",
        "empty",
        "repeat",
        "strata",
    ],
)
def test_rejects_missing_corrupt_or_structurally_invalid_manifest(failure):
    target, manifest = recorded_manifest()
    record = manifest["splits"][0]
    if failure == "missing":
        manifest = None
    elif failure == "missing_folds":
        manifest.pop("splits")
    elif failure == "partial":
        manifest["splits"].pop()
    elif failure == "order":
        record["fold_id"] = "r99-f99"
    elif failure == "row_hash":
        record["split_sha256"] = "0" * 64
    elif failure == "set_hash":
        manifest["outer_split_set_sha256"] = "0" * 64
    elif failure in {"negative", "out_of_range", "bool", "float", "overlap"}:
        record["train_indices"][0] = {
            "negative": -1,
            "out_of_range": len(target),
            "bool": True,
            "float": 0.5,
            "overlap": record["test_indices"][0],
        }[failure]
        reseal(manifest)
    elif failure == "empty":
        record["test_indices"] = []
        reseal(manifest)
    elif failure == "repeat":
        manifest["splits"][1] = {**copy.deepcopy(record), "fold_id": "r01-f02"}
        reseal(manifest)
    else:
        record["test_indices"] = list(range(28))
        record["train_indices"] = list(range(28, 140))
        reseal(manifest)
    with pytest.raises(ValueError, match="Frozen|frozen"):
        validate(manifest, target)


@pytest.mark.parametrize(
    "model,selector,kind,k,n_components",
    [
        (ModelId.LOGISTIC_REGRESSION, SelectorId.MUTUAL_INFORMATION, "original_features", 1, None),
        (ModelId.SVM_RBF, SelectorId.NONE, "original_features", 16, None),
        (ModelId.LIGHTGBM, SelectorId.PCA, "pca_components", None, 4),
    ],
)
def test_execution_uses_exact_saved_training_rows_before_any_fit(
    model, selector, kind, k, n_components, monkeypatch
):
    target, manifest = recorded_manifest()
    features = pd.DataFrame(np.zeros((140, 16)), columns=[f"test_{i}" for i in range(16)])
    condition = EngineCondition(
        model, selector, kind, k, n_components, 42, preset_search_space(model)
    )
    seen = []

    def stop_before_training(self, X, y):
        seen.append(X.index.tolist())
        raise InterruptedError("Regression stops before any estimator training")

    monkeypatch.setattr(engine, "outer_splits", lambda *a, **k: pytest.fail("Regenerated splits"))
    monkeypatch.setattr(engine, "build_pipeline", lambda condition: object())
    monkeypatch.setattr(engine.GridSearchCV, "fit", stop_before_training)
    with pytest.raises(InterruptedError, match="before any estimator"):
        engine.run_nested_cv(
            features,
            target,
            condition,
            frozen_outer_manifest=manifest,
            dataset_hash="a" * 64,
            dataset_version="test-only-v1",
        )
    assert seen == [manifest["splits"][0]["train_indices"]]
    with pytest.raises(ValueError, match="missing"):
        engine.run_nested_cv(features, target, condition)
    with pytest.raises(ValueError, match="integration smoke"):
        engine.run_nested_cv(
            features,
            target,
            replace(condition, evaluation_mode="smoke"),
            frozen_outer_manifest=manifest,
        )
