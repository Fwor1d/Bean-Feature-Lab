import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace

import pytest

from beanfeature_application import reporting as reports
from beanfeature_application.contracts import Experiment, ExperimentConfig, Run
from beanfeature_research.contracts import ModelId, RunStatus, SelectorId
from beanfeature_research.engine import CV_PROTOCOL_VERSION


class EvidenceService:
    """Explicit test evidence; never used by application runtime."""

    def __init__(self, budgets=range(1, 17)):
        self.configs, self.payloads, self.records = {}, {}, []
        self.bad = False
        self.changed = False
        for i, k in enumerate([16, *budgets], 1):
            config = ExperimentConfig(
                ModelId.LOGISTIC_REGRESSION,
                SelectorId.NONE if i == 1 else SelectorId.MUTUAL_INFORMATION,
                "original_features",
                k_original_features=k,
                dataset_version="test",
            )
            folds = [
                {"fold_id": str(f), "split_sha256": str(f), "macro_f1": 0.8} for f in range(15)
            ]
            summary = {
                "evaluation_mode": "protocol",
                "model": config.model.value,
                "budget_kind": "original_features",
                "k_original_features": k,
                "cv_protocol_version": CV_PROTOCOL_VERSION,
                "search_space_version": "test",
                "outer_split_set_sha256": sha256(
                    "".join(str(f) for f in range(15)).encode()
                ).hexdigest(),
                "selector": config.selector.value,
                "n_components": None,
                "seed": 42,
                "search_space": {},
                "outer_fold_count": 15,
                "inner_fold_count": 4,
                "macro_f1_mean": 0.8,
                "accuracy_mean": 0.8,
            }
            now = datetime(2026, 1, 1, tzinfo=UTC)
            self.configs[i] = Experiment(i, "test", config, now, now)
            self.records.append(
                Run(
                    i,
                    i,
                    RunStatus.COMPLETED,
                    now,
                    finished_at=now,
                    result_sha256=str(i),
                    summary=deepcopy(summary),
                    dataset_hash="dataset",
                )
            )
            self.payloads[i] = {
                "configuration": reports.asdict(config),
                "folds": folds,
                "summary": summary,
                "splits": [],
                "provenance": {},
            }
        self.experiments = SimpleNamespace(list=lambda: list(self.configs.values()))

    def list_runs(self):
        return self.records

    def get_experiment(self, identifier):
        return self.configs[identifier]

    def list_datasets(self):
        return [{"id": 1, "source_id": 602}]

    def verify_run(self, identifier):
        return {"verified": not self.bad}

    def get_run_result(self, identifier):
        if self.changed:
            self.records[0] = replace(self.records[0], fingerprint="changed")
        return deepcopy(self.payloads[identifier])

    def get_dataset_manifest(self, identifier):
        return {"arff_sha256": "dataset"}

    def dataset_quality(self, identifier):
        return {}

    def system_info(self):
        return {"git_commit": "different-software-is-allowed"}


def build(service):
    return reports.build_snapshot(service, reports.cohorts(service)[0]["cohort_id"])


def test_complete_formal_family_and_verified_identity():
    result = build(EvidenceService())
    family = result["sufficiency"][0]
    assert family["status"] == "CALCULATED"
    assert family["minimal_sufficient_k"] == 1
    assert family["comparisons"][0]["comparison_alpha"] == 0.05 / 15
    assert family["comparisons"][0]["interval_method"] == "nadeau-bengio-corrected-resampled-t-v1"
    assert len(result["evidence_sha256"]) == 64


def test_partial_family_never_declares_minimum():
    family = build(EvidenceService([1, 16]))["sufficiency"][0]
    assert family["calculated_comparisons"] == 1
    assert family["comparisons"][0]["decision"] == "sufficient"
    assert family["status"] == "PARTIAL" and family["minimal_sufficient_k"] is None


@pytest.mark.parametrize("failure", ["bad", "changed", "search", "folds", "summary"])
def test_explicit_verification_and_compatibility_failures(failure):
    service = EvidenceService()
    if failure in {"bad", "changed"}:
        setattr(service, failure, True)
    elif failure == "search":
        service.configs[2] = replace(
            service.configs[2],
            configuration=replace(service.configs[2].configuration, search_space={"C": [2]}),
        )
    elif failure == "folds":
        service.payloads[2]["folds"][0]["split_sha256"] = "different"
    else:
        service.payloads[2]["summary"]["macro_f1_mean"] = 0.9
    with pytest.raises(reports.ReportError):
        build(service)


def test_earliest_selection_no_metric_fallback():
    service = EvidenceService([1, 1, 16])
    service.payloads[3]["summary"]["macro_f1_mean"] = 0.99
    result = build(service)
    assert {r["id"] for r in result["runs"]} == {1, 2, 4}
    assert result["excluded"][0]["run_id"] == "RUN-000003"
    service.bad = True
    with pytest.raises(reports.ReportError, match="RUN-000001"):
        build(service)


def test_smoke_failed_and_missing_baseline_are_not_formal():
    service = EvidenceService([1, 16])
    service.records[0] = replace(service.records[0], status=RunStatus.FAILED)
    service.configs[3] = replace(
        service.configs[3],
        configuration=replace(service.configs[3].configuration, evaluation_mode="smoke"),
    )
    result = build(service)
    assert len(result["runs"]) == 1
    assert result["sufficiency"][0]["minimal_sufficient_k"] is None
    assert {r["reason"] for r in result["excluded"]} == {"failed", "integration_smoke"}


def test_cache_coalesces_identical_and_bounds_different_requests(monkeypatch):
    service = EvidenceService()
    cohort = reports.cohorts(service)[0]["cohort_id"]
    started, release = threading.Event(), threading.Event()
    calls = []

    def builder(*_args):
        calls.append(True)
        started.set()
        assert release.wait(3)
        return {"evidence_sha256": "test"}

    monkeypatch.setattr(reports, "build_snapshot", builder)
    cache = reports.SnapshotCache()
    with ThreadPoolExecutor(4) as pool:
        first = pool.submit(cache.snapshot, service, cohort)
        assert started.wait(2)
        second = pool.submit(cache.snapshot, service, cohort)
        with pytest.raises(reports.ReportError, match="другой"):
            cache.snapshot(service, "different")
        release.set()
        a, b = first.result(), second.result()
    assert a == b and len(calls) == 1
    a["evidence_sha256"] = "modified"
    assert cache.snapshot(service, cohort)["evidence_sha256"] == "test"


def test_expiration_and_active_snapshot_protection(monkeypatch):
    service = EvidenceService()
    monkeypatch.setattr(reports, "build_snapshot", lambda *_: {})
    now = [0.0]
    monkeypatch.setattr(reports.time, "monotonic", lambda: now[0])
    cache = reports.SnapshotCache(ttl_seconds=60, capacity=1)
    a = cache.snapshot(service, "one")
    with cache.lease(a["snapshot_id"]):
        with pytest.raises(reports.ReportError, match="активно"):
            cache.snapshot(service, "two")
        now[0] = 61
        with pytest.raises(reports.ReportError) as exc:
            cache.lease(a["snapshot_id"]).__enter__()
        assert exc.value.status == 410
        with pytest.raises(reports.ReportError):
            cache.snapshot(service, "two")
    b = cache.snapshot(service, "two")
    assert b["snapshot_id"] != a["snapshot_id"]


@pytest.mark.parametrize("ttl", [0, 59, 86401])
def test_invalid_configuration(ttl):
    with pytest.raises(ValueError):
        reports.SnapshotCache(ttl_seconds=ttl)
