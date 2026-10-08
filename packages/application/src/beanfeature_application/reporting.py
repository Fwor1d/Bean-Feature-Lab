"""Read-only, verified evidence for Conference Mode and scientific reports."""

import json
import math
import time
from concurrent.futures import Future, TimeoutError
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from threading import Lock, Semaphore
from uuid import uuid4

from beanfeature_research.contracts import ModelId, SelectorId
from beanfeature_research.engine import (
    CV_PROTOCOL_VERSION,
    SUFFICIENCY_COMPARISONS,
    SUFFICIENCY_FAMILY_ALPHA,
    SUFFICIENCY_INTERVAL_VERSION,
    SUFFICIENCY_MARGIN,
    NestedResult,
    paired_comparison,
)

from .service import ApplicationService

CORE_MODELS = tuple(model.value for model in ModelId if model is not ModelId.MLP)
CORE_SELECTORS = {s.value for s in SelectorId} - {
    "correlation_pruning",
    "sequential_feature_selection",
}
MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024


class ReportError(Exception):
    def __init__(self, code: str, message: str, status: int = 409):
        super().__init__(message)
        self.code, self.status = code, status


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: object) -> str:
    return sha256(canonical(value)).hexdigest()


def inventory(service: ApplicationService) -> str:
    # Include scientific metadata, but never operational worker heartbeat.
    return digest(
        {
            "runs": [
                asdict(run)
                | {
                    "created_at": str(run.created_at),
                    "started_at": str(run.started_at),
                    "finished_at": str(run.finished_at),
                }
                for run in service.list_runs()
            ],
            "experiments": [
                asdict(e) | {"created_at": str(e.created_at), "updated_at": str(e.updated_at)}
                for e in service.experiments.list()
            ],
            "datasets": service.list_datasets(),
        }
    )


def cohort_key(run, config) -> dict:
    summary = run.summary or {}
    return {
        "dataset_sha256": run.dataset_hash,
        "dataset_version": config.dataset_version,
        "outer_split_set_sha256": summary.get("outer_split_set_sha256"),
        "protocol_version": summary.get("cv_protocol_version"),
        "seed": config.seed,
    }


def cohorts(service: ApplicationService) -> list[dict]:
    groups = {}
    for run in service.list_runs():
        config = service.get_experiment(run.experiment_id).configuration
        if run.status.value != "COMPLETED" or config.evaluation_mode != "protocol":
            continue
        key = cohort_key(run, config)
        if key["protocol_version"] != CV_PROTOCOL_VERSION:
            continue
        identifier = digest(key)
        groups.setdefault(identifier, {"cohort_id": identifier, **key, "completed_conditions": 0})
        groups[identifier]["completed_conditions"] += 1
    return sorted(groups.values(), key=lambda row: row["cohort_id"])


def sufficiency_family(model: str, baseline: dict | None, candidates: dict[int, dict]) -> dict:
    comparisons = []
    for k in range(1, 16):
        candidate = candidates.get(k)
        result = {"decision": "not_calculated"}
        if baseline and candidate:
            result = paired_comparison(
                NestedResult(candidate["folds"], candidate["summary"], candidate["splits"]),
                NestedResult(baseline["folds"], baseline["summary"], baseline["splits"]),
            )
            result = {key: value for key, value in result.items() if key != "paired_losses"}
        comparisons.append({"k_original_features": k, **result})
    calculated = sum(row["decision"] != "not_calculated" for row in comparisons)
    passing = [row["k_original_features"] for row in comparisons if row["decision"] == "sufficient"]
    return {
        "model": model,
        "status": "CALCULATED" if calculated == 15 else "PARTIAL",
        "calculated_comparisons": calculated,
        "minimal_sufficient_k": min(passing) if passing and calculated == 15 else None,
        "comparisons": comparisons,
    }


def build_snapshot(service: ApplicationService, cohort_id: str) -> dict:
    before = inventory(service)
    available = {row["cohort_id"]: row for row in cohorts(service)}
    if cohort_id not in available:
        raise ReportError("cohort_unavailable", "Выбранная группа результатов недоступна.")
    cohort = available[cohort_id]
    selected, excluded = {}, []
    for run in sorted(service.list_runs(), key=lambda r: (r.finished_at or r.created_at, r.id)):
        config = service.get_experiment(run.experiment_id).configuration
        reason = None
        if run.status.value != "COMPLETED":
            reason = run.status.value.lower()
        elif config.evaluation_mode != "protocol":
            reason = "integration_smoke"
        elif digest(cohort_key(run, config)) != cohort_id:
            reason = "different_cohort"
        elif config.selector.value not in CORE_SELECTORS:
            reason = "extended_scope"
        key = digest(
            {
                k: v
                for k, v in asdict(config).items()
                if k not in {"reproduces_run_id", "search_space"}
            }
        )
        if reason is None and key in selected:
            reason = "duplicate_condition_earliest_completed_selected"
        if reason:
            excluded.append({"run_id": run.display_id, "reason": reason})
        else:
            selected[key] = (run, config)
    if not selected or len(selected) > 512:
        raise ReportError("evidence_size", "Недостаточный или слишком большой набор результатов.")
    loaded, records = [], []
    for run, config in selected.values():
        if not service.verify_run(run.id)["verified"]:
            raise ReportError(
                "verification_failed", f"{run.display_id}: проверка artifact не пройдена."
            )
        payload = service.get_run_result(run.id)
        if payload is None:
            raise ReportError("verification_failed", f"{run.display_id}: результат недоступен.")
        summary = payload["summary"]
        if summary != run.summary or digest(cohort_key(run, config)) != cohort_id:
            raise ReportError(
                "inconsistent_evidence", f"{run.display_id}: metadata не согласованы."
            )
        if any(
            not math.isfinite(summary[m]) or not 0 <= summary[m] <= 1
            for m in ("macro_f1_mean", "accuracy_mean")
        ):
            raise ReportError("invalid_metrics", f"{run.display_id}: некорректные метрики.")
        config_values = asdict(config)
        identity_fields = (
            "model",
            "selector",
            "budget_kind",
            "k_original_features",
            "n_components",
            "seed",
            "search_space",
        )
        if (
            summary.get("outer_fold_count") != 15
            or summary.get("inner_fold_count") != 4
            or any(summary.get(key) != config_values[key] for key in identity_fields)
        ):
            raise ReportError(
                "inconsistent_protocol",
                f"{run.display_id}: summary и frozen configuration различаются.",
            )
        loaded.append((run, config, payload))
        records.append(
            {
                "run_id": run.display_id,
                "id": run.id,
                "result_sha256": run.result_sha256,
                "fingerprint": run.fingerprint,
                "finished_at": str(run.finished_at),
                "configuration": asdict(config),
                "summary": summary,
                "provenance": payload["provenance"],
            }
        )
    # Baseline compatibility is validated for every condition, not only MI pairs.
    baselines = {
        c.model.value: p
        for _, c, p in loaded
        if c.selector is SelectorId.NONE and c.k_original_features == 16
    }
    for run, config, payload in loaded:
        baseline = baselines.get(config.model.value)
        if not baseline:
            continue  # Missing baselines remain explicit; no formal conclusion.
        base_config = baseline["configuration"]
        if any(
            base_config[key] != asdict(config)[key]
            for key in ("model", "dataset_version", "seed", "search_space", "evaluation_mode")
        ):
            raise ReportError("incompatible_baseline", f"{run.display_id}: несовместимый baseline.")
        if (
            payload["summary"]["search_space_version"]
            != baseline["summary"]["search_space_version"]
        ):
            raise ReportError(
                "incompatible_baseline", f"{run.display_id}: другая версия search space."
            )
        if [(f["fold_id"], f["split_sha256"]) for f in payload["folds"]] != [
            (f["fold_id"], f["split_sha256"]) for f in baseline["folds"]
        ]:
            raise ReportError("incompatible_splits", f"{run.display_id}: outer folds различаются.")
    sufficiency = [
        sufficiency_family(
            model,
            baselines.get(model),
            {
                c.k_original_features: p
                for _, c, p in loaded
                if c.model.value == model and c.selector is SelectorId.MUTUAL_INFORMATION
            },
        )
        for model in CORE_MODELS
    ]
    registered = next((d for d in service.list_datasets() if d["source_id"] == 602), None)
    if not registered:
        raise ReportError("dataset_missing", "Официальный dataset не зарегистрирован.")
    manifest = service.get_dataset_manifest(registered["id"])
    quality = service.dataset_quality(registered["id"])
    if manifest["arff_sha256"] != cohort["dataset_sha256"]:
        raise ReportError("dataset_mismatch", "Доступный dataset не соответствует результатам.")
    if before != inventory(service):
        raise ReportError("evidence_changed", "Научные данные изменились. Создайте новый снимок.")
    protocol = {
        "version": CV_PROTOCOL_VERSION,
        "outer_splits": 5,
        "outer_repeats": 3,
        "inner_splits": 4,
        "primary_metric": "Macro-F1",
        "margin": SUFFICIENCY_MARGIN,
        "family_alpha": SUFFICIENCY_FAMILY_ALPHA,
        "comparisons_per_model": SUFFICIENCY_COMPARISONS,
        "method": SUFFICIENCY_INTERVAL_VERSION,
        "reference": "docs/research/EXPERIMENT_PROTOCOL.md",
    }
    evidence = {
        "format_version": "core-report-v1",
        "cohort": cohort,
        "dataset": manifest,
        "quality": quality,
        "protocol": protocol,
        "runs": records,
        "sufficiency": sufficiency,
        "excluded": excluded,
        "selection": "earliest completed per condition; full protocol; no metric selection",
    }
    body = {
        **evidence,
        "evidence_sha256": digest(evidence),
        "verified_at_utc": datetime.now(UTC).isoformat(),
        "generation_context": service.system_info(),
    }
    if len(canonical(body)) > MAX_SNAPSHOT_BYTES:
        raise ReportError("evidence_size", "Снимок превышает допустимый размер.")
    return body


@dataclass
class Entry:
    payload: dict
    deadline: float
    touched: float
    leases: int = 0


class SnapshotCache:
    """Bounded process-local cache and single-flight builder; no persistent writes."""

    def __init__(self, ttl_seconds: int = 7200, capacity: int = 4):
        if not 60 <= ttl_seconds <= 86400 or not 1 <= capacity <= 4:
            raise ValueError("Report TTL must be 60..86400 seconds; capacity must be 1..4")
        self.ttl, self.capacity = ttl_seconds, capacity
        self.entries: dict[str, Entry] = {}
        self.keys: dict[str, str] = {}
        self.pending: dict[str, Future] = {}
        self.lock, self.builder = Lock(), Semaphore(1)

    def snapshot(self, service: ApplicationService, cohort_id: str) -> dict:
        key = digest([cohort_id, inventory(service)])
        with self.lock:
            identifier = self.keys.get(key)
            if identifier and identifier in self.entries:
                entry = self.entries[identifier]
                if time.monotonic() < entry.deadline:
                    entry.touched = time.monotonic()
                    return deepcopy(entry.payload)
            future = self.pending.get(key)
            owner = future is None
            if owner:
                if not self.builder.acquire(blocking=False):
                    raise ReportError(
                        "report_busy", "Проверяется другой снимок. Повторите запрос.", 503
                    )
                future = Future()
                self.pending[key] = future
        if not owner:
            try:
                return deepcopy(future.result(timeout=60))
            except TimeoutError as exc:
                raise ReportError(
                    "report_busy", "Проверка ещё выполняется. Повторите запрос.", 503
                ) from exc
        try:
            payload = build_snapshot(service, cohort_id)
            now = time.monotonic()
            payload |= {
                "snapshot_id": uuid4().hex,
                "expires_at_utc": (datetime.now(UTC) + timedelta(seconds=self.ttl)).isoformat(),
            }
            with self.lock:
                if len(self.entries) >= self.capacity:
                    evictable = [
                        (e.touched, i)
                        for i, e in self.entries.items()
                        if not e.leases and (now >= e.deadline or now - e.touched >= 300)
                    ]
                    if not evictable:
                        raise ReportError(
                            "report_busy", "Все снимки активно используются. Повторите позже.", 503
                        )
                    del self.entries[min(evictable)[1]]
                identifier = payload["snapshot_id"]
                self.entries[identifier] = Entry(payload, now + self.ttl, now)
                self.keys = {k: i for k, i in self.keys.items() if i in self.entries}
                self.keys[key] = identifier
            future.set_result(payload)
            return deepcopy(payload)
        except BaseException as exc:
            future.set_exception(exc)
            raise
        finally:
            with self.lock:
                del self.pending[key]
            self.builder.release()

    @contextmanager
    def lease(self, identifier: str):
        with self.lock:
            entry = self.entries.get(identifier)
            if not entry or time.monotonic() >= entry.deadline:
                raise ReportError(
                    "snapshot_expired", "Снимок истёк. Создайте новый проверенный снимок.", 410
                )
            entry.leases += 1
            entry.touched = time.monotonic()
        try:
            yield deepcopy(entry.payload)
        finally:
            with self.lock:
                entry.leases -= 1
