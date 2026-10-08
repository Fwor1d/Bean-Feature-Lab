import math
from pathlib import Path

import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from beanfeature_application.service import ApplicationService
from beanfeature_infrastructure.bootstrap import create_container
from beanfeature_infrastructure.database import Base
from beanfeature_infrastructure.deployment import LocalDeploymentModelStore
from beanfeature_research.dataset import CLASSES, FEATURE_COLUMNS


def classifier_service(tmp_path: Path) -> ApplicationService:
    container = create_container(f"sqlite:///{tmp_path / 'test.sqlite'}")
    Base.metadata.create_all(container.metadata.engine)
    store = LocalDeploymentModelStore(tmp_path / "models")
    features = pd.DataFrame(
        [[float(index + 1)] * len(FEATURE_COLUMNS) for index in range(len(CLASSES))],
        columns=FEATURE_COLUMNS,
    )
    estimator = DummyClassifier(strategy="prior").fit(features, list(CLASSES))
    store.save(
        estimator,
        {
            "model_id": "test-classifier-v1",
            "model_family": "Dummy test estimator",
            "source_run": "RUN-000001",
            "dataset_id": 602,
            "dataset_sha256": "a" * 64,
            "feature_names": list(FEATURE_COLUMNS),
            "classes": list(CLASSES),
            "training_timestamp_utc": "2026-01-01T00:00:00+00:00",
            "selected_parameters": {},
            "deployment_model": True,
            "note": "test-only",
        },
    )
    container.service.deployment_models = store
    return container.service


def test_classifier_returns_real_estimator_probabilities(tmp_path) -> None:
    service = classifier_service(tmp_path)
    values = {name: 1.0 for name in FEATURE_COLUMNS}
    result = service.predict_classifier(values)
    assert result["predicted_class"] in CLASSES
    assert math.isclose(sum(result["probabilities"].values()), 1.0)
    assert result["predicted_probability"] == result["probabilities"][result["predicted_class"]]


def test_classifier_rejects_schema_drift_and_non_finite_values(tmp_path) -> None:
    service = classifier_service(tmp_path)
    values = {name: 1.0 for name in FEATURE_COLUMNS}
    with pytest.raises(ValueError, match="Exactly 16 canonical features"):
        service.predict_classifier({key: value for key, value in values.items() if key != "Area"})
    values["Area"] = float("nan")
    with pytest.raises(ValueError, match="finite numeric"):
        service.predict_classifier(values)


def test_logistic_classifier_returns_exact_local_logit_contributions(tmp_path) -> None:
    container = create_container(f"sqlite:///{tmp_path / 'test.sqlite'}")
    Base.metadata.create_all(container.metadata.engine)
    store = LocalDeploymentModelStore(tmp_path / "models")
    rows = [
        [float(class_index * 4 + repeat + feature_index / 10) for feature_index in range(16)]
        for class_index in range(len(CLASSES))
        for repeat in range(3)
    ]
    target = [label for label in CLASSES for _ in range(3)]
    features = pd.DataFrame(rows, columns=FEATURE_COLUMNS)
    pipeline = Pipeline(
        [
            ("scale", StandardScaler()),
            ("select", "passthrough"),
            ("model", LogisticRegression(max_iter=1000, random_state=42)),
        ]
    ).fit(features, target)
    store.save(
        pipeline,
        {
            "model_id": "test-logistic-v1",
            "model_family": "Logistic Regression",
            "source_run": "RUN-000003",
            "dataset_id": 602,
            "dataset_sha256": "b" * 64,
            "feature_names": list(FEATURE_COLUMNS),
            "classes": [str(value) for value in pipeline.classes_],
            "training_timestamp_utc": "2026-01-01T00:00:00+00:00",
            "selected_parameters": {},
            "deployment_model": True,
            "note": "test-only",
        },
    )
    container.service.deployment_models = store
    values = {name: float(features.iloc[8][name]) for name in FEATURE_COLUMNS}
    result = container.service.predict_classifier(values)
    explanation = result["local_explanation"]
    assert explanation and explanation["method"] == "linear_logit_contribution-v1"
    assert len(explanation["contributions"]) == 16
    explained_logit = explanation["intercept"] + sum(
        item["logit_contribution"] for item in explanation["contributions"]
    )
    predicted_index = list(pipeline.classes_).index(result["predicted_class"])
    expected_logit = pipeline.decision_function(pd.DataFrame([values]))[0][predicted_index]
    assert explained_logit == pytest.approx(expected_logit)


@pytest.mark.parametrize(
    "probabilities", [[float("nan")] * 7, [0.5] * 7, [-1.0, 2.0, 0, 0, 0, 0, 0]]
)
def test_unusable_model_probabilities_fail_safely(probabilities):
    from types import SimpleNamespace

    pipeline = SimpleNamespace(
        classes_=list(CLASSES),
        predict=lambda frame: [CLASSES[0]],
        predict_proba=lambda frame: [probabilities],
    )
    store = SimpleNamespace(
        load=lambda: (pipeline, {"feature_names": list(FEATURE_COLUMNS), "classes": list(CLASSES)})
    )
    service = ApplicationService(None, None, None, deployment_models=store)
    with pytest.raises(ValueError, match="probabilities are unavailable"):
        service.predict_classifier({name: 1.0 for name in FEATURE_COLUMNS})
