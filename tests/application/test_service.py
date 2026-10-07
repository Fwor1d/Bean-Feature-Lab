import json
from dataclasses import replace
from datetime import UTC, datetime

import pandas as pd
import pytest
from sklearn.datasets import make_classification

from beanfeature_application.contracts import ExperimentConfig
from beanfeature_application.service import ApplicationService
from beanfeature_infrastructure.bootstrap import create_container
from beanfeature_infrastructure.database import Base
from beanfeature_infrastructure.files import ArtifactStore
from beanfeature_infrastructure.repositories import SQLiteRunRepository
from beanfeature_research.contracts import ModelId, SelectorId
from beanfeature_research.dataset import ValidatedDataset


def test_pca_cannot_be_original_budget(tmp_path) -> None:
    container = create_container(f"sqlite:///{tmp_path / 'test.sqlite'}")
    Base.metadata.create_all(container.metadata.engine)
    service: ApplicationService = container.service
    with pytest.raises(ValueError, match="PCA is not"):
        service.create_experiment(
            "wrong",
            ExperimentConfig(
                ModelId.SVM_RBF,
                SelectorId.PCA,
                "original_features",
                k_original_features=4,
            ),
        )
    with pytest.raises(ValueError, match="PCA requires"):
        service.create_experiment(
            "wrong",
            ExperimentConfig(
                ModelId.SVM_RBF,
                SelectorId.MUTUAL_INFORMATION,
                "pca_components",
                n_components=4,
            ),
        )
    with pytest.raises(ValueError, match="all 16"):
        service.create_experiment(
            "wrong",
            ExperimentConfig(
                ModelId.SVM_RBF,
                SelectorId.PCA,
                "pca_components",
                n_components=4,
                required_raw_feature_count=4,
            ),
        )


def test_completed_requires_verified_artifact_and_failure_has_no_metrics(tmp_path) -> None:
    container = create_container(f"sqlite:///{tmp_path / 'test.sqlite'}")
    Base.metadata.create_all(container.metadata.engine)
    service = container.service
    experiment = service.create_experiment(
        "invariant",
        ExperimentConfig(
            ModelId.LOGISTIC_REGRESSION,
            SelectorId.MUTUAL_INFORMATION,
            "original_features",
            k_original_features=4,
        ),
    )
    queued = service.create_run(experiment.id)
    assert queued.summary is None
    assert queued.result_artifact is None
    running = service.runs.claim_next()
    assert running and running.status.value == "RUNNING"
    with pytest.raises(FileNotFoundError):
        service.runs.complete(
            queued.id,
            "missing/result.json",
            "0" * 64,
            {"macro_f1_mean": 0.0},
            "hash",
            "fingerprint",
        )
    failed = service.runs.fail(queued.id, "intentional test failure")
    assert failed and failed.status.value == "FAILED"
    assert failed.summary is None
    assert failed.result_artifact is None
    assert service.get_run_result(queued.id) is None


def test_synthetic_end_to_end_persistence_roundtrip(tmp_path) -> None:
    features, target = make_classification(
        n_samples=140,
        n_features=16,
        n_informative=10,
        n_redundant=0,
        n_classes=7,
        n_clusters_per_class=1,
        random_state=21,
    )
    dataset = ValidatedDataset(
        pd.DataFrame(features, columns=[f"feature_{index}" for index in range(16)]),
        target,
        "synthetic-test-only",
    )

    class TestDatasetStore:
        def load(self):
            return dataset, {
                "dataset_version": "synthetic-test-only",
                "arff_sha256": "synthetic-test-only",
            }

    container = create_container(f"sqlite:///{tmp_path / 'test.sqlite'}")
    Base.metadata.create_all(container.metadata.engine)
    service = container.service
    artifacts = ArtifactStore(tmp_path / "artifacts")
    service.artifacts = artifacts
    service.runs.artifacts = artifacts
    service.dataset_store = TestDatasetStore()
    experiment = service.create_experiment(
        "synthetic integration test",
        ExperimentConfig(
            ModelId.LOGISTIC_REGRESSION,
            SelectorId.MUTUAL_INFORMATION,
            "original_features",
            k_original_features=4,
            dataset_version="synthetic-test-only",
            evaluation_mode="smoke",
        ),
    )
    queued = service.create_run(experiment.id)
    completed = service.process_next_run()
    assert completed and completed.status.value == "COMPLETED"
    reloaded = SQLiteRunRepository(service.runs.sessions, artifacts).get(queued.id)
    assert reloaded and reloaded.summary == completed.summary
    assert reloaded.result_sha256
    result = service.get_run_result(queued.id)
    assert result and len(result["folds"]) == 2
    assert result["summary"]["macro_f1_mean"] == completed.summary["macro_f1_mean"]
    verification = service.verify_run(queued.id)
    assert verification["verified"] is True
    assert all(verification["checks"].values())
    filename, media_type, content = service.export_run(queued.id, "folds.csv")
    assert filename == f"{queued.display_id}-folds.csv"
    assert media_type.startswith("text/csv")
    assert content.decode().splitlines()[0].startswith("fold_id,split_sha256")
    config_filename, config_type, config_content = service.export_run(queued.id, "config.json")
    assert config_filename == f"{queued.display_id}-config.json"
    assert config_type == "application/json"
    assert json.loads(config_content)["run_id"] == queued.display_id
    resources = service.run_resources(queued.id)
    assert resources["total_nested_search_seconds"] > 0
    assert resources["inference_latency_ms"]["single_row"]["samples"] == 6
    assert resources["serialized_pipeline_bytes"]["median"] > 0
    assert resources["peak_memory_status"] == "NOT_CALCULATED"
    assert resources["peak_memory_bytes"] is None
    reproduced = service.reproduce_run(queued.id)
    assert reproduced.status.value == "QUEUED"
    reproduced_config = service.get_experiment(reproduced.experiment_id).configuration
    assert reproduced_config == replace(
        experiment.configuration, reproduces_run_id=queued.display_id
    )


def test_core_enqueue_is_idempotent_and_missing_baseline_is_not_calculated(tmp_path) -> None:
    container = create_container(f"sqlite:///{tmp_path / 'test.sqlite'}")
    Base.metadata.create_all(container.metadata.engine)
    service = container.service
    assert service.datasets is not None
    service.datasets.register(
        {
            "dataset_version": "uci-602-test",
            "archive_sha256": "a" * 64,
            "arff_sha256": "b" * 64,
            "retrieved_at_utc": datetime.now(UTC).isoformat(),
            "rows": 13_611,
            "feature_count": 16,
            "classes": ["A", "B", "C", "D", "E", "F", "G"],
        }
    )
    dry = service.enqueue_core_matrix(create=False)
    assert dry["total_conditions"] == 86
    assert dry["missing"] == 86
    created = service.enqueue_core_matrix(create=True)
    assert len(created["created_run_ids"]) == 86
    repeated = service.enqueue_core_matrix(create=True)
    assert repeated["missing"] == 0
    assert repeated["active"] == 86
    assert repeated["created_run_ids"] == []
    missing = service.core_sufficiency(ModelId.LOGISTIC_REGRESSION)
    assert missing["status"] == "NOT_CALCULATED_MISSING_BASELINE"
    assert missing["minimal_sufficient_k"] is None
