"""Temporary fixture records exercise execution guards without ML training."""

import copy
import json
from dataclasses import asdict, replace
from hashlib import sha256
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from tests.research.test_frozen_splits import recorded_manifest

from beanfeature_application.contracts import ExperimentConfig
from beanfeature_infrastructure.bootstrap import create_container
from beanfeature_infrastructure.database import Base
from beanfeature_research.contracts import ModelId, SelectorId
from beanfeature_research.dataset import ValidatedDataset
from beanfeature_research.engine import SMOKE_PROTOCOL_VERSION, _split_hash


@pytest.fixture
def context(tmp_path):
    container = create_container(f"sqlite:///{tmp_path / 'state.sqlite'}", runtime_root=tmp_path)
    Base.metadata.create_all(container.metadata.engine)
    target, manifest = recorded_manifest()
    dataset = ValidatedDataset(
        pd.DataFrame(np.zeros((140, 16)), columns=[f"test_{i}" for i in range(16)]),
        target,
        manifest["dataset_hash"],
    )
    config = ExperimentConfig(
        ModelId.LOGISTIC_REGRESSION,
        SelectorId.NONE,
        "original_features",
        k_original_features=16,
        dataset_version=manifest["dataset_version"],
    )
    container.service.dataset_store = SimpleNamespace(
        load=lambda: (
            dataset,
            {"dataset_version": manifest["dataset_version"]},
        )
    )
    yield container.service, dataset, config, manifest
    container.metadata.engine.dispose()


def completed_fixture(context, *, config=None, mutate=None):
    service, dataset, default, manifest = context
    experiment = service.create_experiment("test-only saved manifest", config or default)
    run = service.create_run(experiment.id)
    service.runs.claim_next()
    config_snapshot = asdict(experiment.configuration)
    fingerprint = sha256(
        json.dumps(
            {
                "configuration": config_snapshot,
                "dataset_hash": dataset.arff_sha256,
                "provenance": {"test_only": True},
            },
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()
    payload = {
        "run_id": run.display_id,
        "experiment_id": experiment.id,
        "configuration": config_snapshot,
        "dataset_manifest": {
            "arff_sha256": dataset.arff_sha256,
            "dataset_version": default.dataset_version,
            "rows": len(dataset.target),
        },
        "provenance": {"test_only": True},
        "fingerprint": fingerprint,
        "summary": {
            "evaluation_mode": "protocol",
            "macro_f1_mean": 0.8,
            "accuracy_mean": 0.8,
            "seed": experiment.configuration.seed,
            "cv_protocol_version": manifest["cv_protocol_version"],
            "outer_split_set_sha256": manifest["outer_split_set_sha256"],
        },
        "splits": copy.deepcopy(manifest["splits"]),
        "folds": [
            {
                "fold_id": r["fold_id"],
                "split_sha256": r["split_sha256"],
                "macro_f1": 0.8,
                "accuracy": 0.8,
            }
            for r in manifest["splits"]
        ],
    }
    if mutate:
        mutate(payload)
    path = f"{run.display_id}/result.json"
    digest = service.artifacts.write_json(path, payload)
    service.runs.complete(
        run.id, path, digest, payload["summary"], dataset.arff_sha256, fingerprint
    )
    return service.get_run(run.id)


def test_earliest_verified_saved_source_is_reused_without_any_runtime_write(context):
    service, dataset, config, manifest = context
    first = completed_fixture(context)
    completed_fixture(context)  # Repository returns newer runs first.
    before = [(r.id, r.status, r.result_sha256, r.fingerprint) for r in service.list_runs()]
    chosen = service.resolve_frozen_outer_manifest(config, dataset)
    assert chosen["source_run_id"] == first.display_id
    assert chosen["source_result_sha256"] == first.result_sha256
    assert chosen["splits"] == manifest["splits"]
    assert before == [(r.id, r.status, r.result_sha256, r.fingerprint) for r in service.list_runs()]


@pytest.mark.parametrize(
    "failure",
    ["missing_file", "corrupt_file", "missing_splits", "indices", "protocol", "summary_seed"],
)
def test_bad_selected_source_never_switches_to_a_later_valid_run(context, failure):
    service, dataset, config, _ = context

    def mutate(payload):
        if failure == "missing_splits":
            payload.pop("splits")
        elif failure == "indices":
            payload["splits"][0]["train_indices"][0] = -1
        elif failure == "protocol":
            payload["summary"]["cv_protocol_version"] = "unsupported"
        elif failure == "summary_seed":
            payload["summary"]["seed"] = 43

    first = completed_fixture(context, mutate=mutate)
    completed_fixture(context)
    path = service.artifacts.resolve(first.result_artifact)
    if failure == "missing_file":
        path.unlink()
    elif failure == "corrupt_file":
        path.write_bytes(b"broken test-only artifact")
    with pytest.raises(ValueError, match="verification failed|Frozen|frozen"):
        service.resolve_frozen_outer_manifest(config, dataset)


@pytest.mark.parametrize("failure", ["absent", "seed", "version", "hash", "smoke", "failed"])
def test_required_source_cohort_must_be_compatible_and_completed(context, failure):
    service, dataset, config, _ = context
    if failure not in {"absent", "failed"}:
        completed_fixture(context)
    if failure == "seed":
        config = replace(config, seed=43)
    elif failure == "version":
        config = replace(config, dataset_version="other")
    elif failure == "hash":
        dataset = replace(dataset, arff_sha256="b" * 64)
    elif failure == "smoke":
        config = replace(config, evaluation_mode="smoke")
    elif failure == "failed":
        experiment = service.create_experiment("failed test-only source", config)
        run = service.create_run(experiment.id)
        service.runs.claim_next()
        service.runs.fail(run.id, "test-only failure")
    with pytest.raises(ValueError, match="missing|full protocol"):
        service.resolve_frozen_outer_manifest(config, dataset)


def test_missing_manifest_fails_execution_before_entering_engine(context, monkeypatch):
    service, _, config, _ = context
    experiment = service.create_experiment("test-only rejected execution", config)
    run = service.create_run(experiment.id)
    monkeypatch.setattr(
        "beanfeature_application.service.run_nested_cv",
        lambda *a, **k: pytest.fail("Entered ML engine"),
    )
    failed = service.process_next_run()
    assert failed.id == run.id and failed.status.value == "FAILED"
    assert "frozen outer split manifest is missing" in failed.error
    assert failed.result_artifact is None and failed.summary is None


def test_execution_passes_verified_manifest_and_preserves_source(context, monkeypatch):
    service, _, config, manifest = context
    source = completed_fixture(context)
    experiment = service.create_experiment("test-only pre-fit execution", config)
    service.create_run(experiment.id)
    seen = []

    def stop_before_training(X, y, condition, **kwargs):
        seen.append(kwargs["frozen_outer_manifest"])
        assert kwargs["dataset_hash"] == manifest["dataset_hash"]
        assert kwargs["dataset_version"] == config.dataset_version
        raise InterruptedError("Test stops before training")

    monkeypatch.setattr("beanfeature_application.service.run_nested_cv", stop_before_training)
    assert service.process_next_run().status.value == "FAILED"
    assert seen[0]["source_run_id"] == source.display_id
    assert seen[0]["splits"] == manifest["splits"]
    assert service.get_run(source.id) == source


def test_smoke_record_cannot_supply_a_required_full_protocol_manifest(context):
    service, dataset, config, _ = context

    def smoke_payload(payload):
        payload["folds"] = payload["folds"][:2]
        payload["splits"] = payload["splits"][:2]
        payload["summary"]["evaluation_mode"] = "smoke"
        payload["summary"]["cv_protocol_version"] = SMOKE_PROTOCOL_VERSION
        payload["summary"]["outer_split_set_sha256"] = sha256(
            "".join(f["split_sha256"] for f in payload["folds"]).encode()
        ).hexdigest()

    completed_fixture(
        context, config=replace(config, evaluation_mode="smoke"), mutate=smoke_payload
    )
    with pytest.raises(ValueError, match="manifest is missing"):
        service.resolve_frozen_outer_manifest(config, dataset)


def test_reproduction_must_match_the_canonical_frozen_source(context):
    service, dataset, config, _ = context
    original = completed_fixture(context)
    assert (
        service.resolve_frozen_outer_manifest(
            replace(config, reproduces_run_id=original.display_id), dataset
        )["source_run_id"]
        == original.display_id
    )

    def different_recorded_order(payload):
        record = payload["splits"][0]
        record["train_indices"].reverse()
        record["split_sha256"] = _split_hash(
            np.array(record["train_indices"]), np.array(record["test_indices"])
        )
        payload["folds"][0]["split_sha256"] = record["split_sha256"]
        payload["summary"]["outer_split_set_sha256"] = sha256(
            "".join(f["split_sha256"] for f in payload["folds"]).encode()
        ).hexdigest()

    incompatible = completed_fixture(context, mutate=different_recorded_order)
    assert service.verify_run(incompatible.id)["verified"]
    with pytest.raises(ValueError, match="Reproduction source differs"):
        service.resolve_frozen_outer_manifest(
            replace(config, reproduces_run_id=incompatible.display_id), dataset
        )
