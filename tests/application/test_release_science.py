"""Regression evidence is test-only; no persisted scientific results are changed."""

from dataclasses import replace
from types import SimpleNamespace

import pytest
from tests.application.test_reporting import EvidenceService

from beanfeature_application.service import ApplicationService
from beanfeature_research.contracts import ModelId


def service_for(evidence):
    service = ApplicationService(evidence.experiments, SimpleNamespace(), SimpleNamespace())
    service.list_runs = evidence.list_runs
    service.get_experiment = evidence.get_experiment
    service.get_run = lambda identifier: next(r for r in evidence.records if r.id == identifier)
    service.get_run_result = evidence.get_run_result
    service.verify_run = evidence.verify_run
    return service


def test_workstation_partial_family_never_declares_a_formal_minimum():
    service = service_for(EvidenceService([1, 16]))
    result = service.core_sufficiency(ModelId.LOGISTIC_REGRESSION)
    assert result["status"] == "PARTIAL"
    assert result["comparisons"][0]["decision"] == "sufficient"
    assert result["minimal_sufficient_k"] is None


def test_workstation_uses_earliest_completed_not_repository_order_or_best_metric():
    evidence = EvidenceService([1, 1, 16])
    evidence.records.reverse()  # Production repository is newest-first.
    service = service_for(evidence)
    selected = []
    original = service.compare_runs

    def record(compact, baseline):
        selected.append((compact, baseline))
        return original(compact, baseline)

    service.compare_runs = record
    service.core_sufficiency(ModelId.LOGISTIC_REGRESSION)
    assert selected == [(2, 1)]
    evidence.bad = True
    with pytest.raises(ValueError, match="verification failed"):
        service.core_sufficiency(ModelId.LOGISTIC_REGRESSION)


@pytest.mark.parametrize("failure", ["seed", "version", "summary", "folds"])
def test_comparison_rejects_incompatible_or_inconsistent_evidence(failure):
    evidence = EvidenceService([1])
    if failure in {"seed", "version"}:
        evidence.configs[2] = replace(
            evidence.configs[2],
            configuration=replace(
                evidence.configs[2].configuration,
                **({"seed": 99} if failure == "seed" else {"dataset_version": "other"}),
            ),
        )
    elif failure == "summary":
        evidence.payloads[2]["summary"]["macro_f1_mean"] = 0.99
    else:
        evidence.payloads[2]["folds"][0]["split_sha256"] = "other"
    with pytest.raises(ValueError):
        service_for(evidence).compare_runs(2, 1)
