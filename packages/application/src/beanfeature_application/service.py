import csv
import importlib.util
import io
import json
import math
import traceback
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

import pandas as pd

from beanfeature_research.contracts import (
    ModelId,
    OriginalFeatureBudget,
    PCARepresentation,
    SelectorId,
)
from beanfeature_research.dataset import dataset_quality_summary
from beanfeature_research.engine import (
    CV_PROTOCOL_VERSION,
    SMOKE_PROTOCOL_VERSION,
    EngineCondition,
    NestedResult,
    build_pipeline,
    paired_comparison,
    preset_search_space,
    run_nested_cv,
)

from .contracts import (
    DatasetRepository,
    DatasetStore,
    DeploymentModelStore,
    Experiment,
    ExperimentConfig,
    ExperimentRepository,
    MetadataProvider,
    Run,
    RunRepository,
    ScientificArtifactStore,
)


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


class ApplicationService:
    def __init__(
        self,
        experiments: ExperimentRepository,
        runs: RunRepository,
        metadata: MetadataProvider,
        *,
        datasets: DatasetRepository | None = None,
        dataset_store: DatasetStore | None = None,
        artifacts: ScientificArtifactStore | None = None,
        deployment_models: DeploymentModelStore | None = None,
    ) -> None:
        self.experiments = experiments
        self.runs = runs
        self.metadata = metadata
        self.datasets = datasets
        self.dataset_store = dataset_store
        self.artifacts = artifacts
        self.deployment_models = deployment_models

    def train_deployment_classifier(self) -> dict[str, object]:
        """Refit the completed 16-feature baseline for inference, never for evaluation."""
        if not self.dataset_store or not self.deployment_models:
            raise RuntimeError("Deployment infrastructure is unavailable")
        run = self.get_run(3)
        result = self.get_run_result(3)
        if run.display_id != "RUN-000003" or result is None or not self.verify_run(3)["verified"]:
            raise ConflictError("RUN-000003 must be completed with a verified result")
        config = self.get_experiment(run.experiment_id).configuration
        if (
            config.model is not ModelId.LOGISTIC_REGRESSION
            or config.selector is not SelectorId.NONE
            or config.budget_kind != "original_features"
            or config.k_original_features != 16
            or config.evaluation_mode != "protocol"
        ):
            raise ValueError("RUN-000003 is not the expected 16-feature LR baseline")
        dataset, manifest = self.dataset_store.load()
        if (
            run.dataset_hash != dataset.arff_sha256
            or config.dataset_version != manifest["dataset_version"]
        ):
            raise ValueError("Baseline run and validated dataset do not match")
        fold_params = [fold["best_params"] for fold in result["folds"]]
        if len(fold_params) != 15 or any(params != fold_params[0] for params in fold_params):
            raise ValueError("Baseline folds do not agree on deployment hyperparameters")
        chosen = fold_params[0]
        if chosen.get("model__C") not in config.search_space["model__C"]:
            raise ValueError("Deployment hyperparameter is outside the frozen search space")
        condition = EngineCondition(
            model=config.model,
            selector=config.selector,
            budget_kind="original_features",
            k_original_features=16,
            n_components=None,
            seed=config.seed,
            search_space=config.search_space,
        )
        pipeline = build_pipeline(condition).set_params(**chosen)
        pipeline.fit(dataset.features, dataset.target)
        observed_ranges = {
            name: {
                "minimum": float(dataset.features[name].min()),
                "maximum": float(dataset.features[name].max()),
            }
            for name in dataset.feature_names
        }
        metadata: dict[str, object] = {
            "model_id": "lr-uci-602-full16-v1",
            "model_version": "1.0.0",
            "model_family": "Logistic Regression",
            "estimator_identifier": config.model.value,
            "source_run": run.display_id,
            "source_result_sha256": run.result_sha256,
            "source_configuration": asdict(config),
            "dataset_id": 602,
            "dataset_sha256": dataset.arff_sha256,
            "dataset_version": manifest["dataset_version"],
            "training_rows": len(dataset.target),
            "feature_names": list(dataset.feature_names),
            "feature_schema": [
                {"name": name, "dtype": "numeric", **observed_ranges[name]}
                for name in dataset.feature_names
            ],
            "observed_ranges": observed_ranges,
            "classes": [str(value) for value in pipeline.classes_],
            "training_timestamp_utc": datetime.now(UTC).isoformat(),
            "selected_parameters": chosen,
            "deployment_model": True,
            "note": (
                "Inference/demo model refitted on all validated UCI 602 rows; "
                "not an independent performance evaluation."
            ),
        }
        return self.deployment_models.save(pipeline, metadata)

    def classifier_info(self) -> dict[str, object] | None:
        return self.deployment_models.metadata() if self.deployment_models else None

    def classifier_benchmark(self) -> dict[str, object] | None:
        return self.deployment_models.latest_benchmark() if self.deployment_models else None

    def classifier_example(self) -> dict[str, object]:
        if not self.dataset_store:
            raise RuntimeError("Dataset infrastructure is unavailable")
        dataset, _ = self.dataset_store.load()
        row_index = 0
        return {
            "source": "UCI Dry Bean Dataset 602",
            "row_index": row_index,
            "features": {
                name: float(dataset.features.iloc[row_index][name])
                for name in dataset.feature_names
            },
            "actual_class": str(dataset.target[row_index]),
            "note": "The actual class is display-only and is never passed to the model input.",
        }

    def predict_classifier(self, features: dict[str, object]) -> dict[str, object]:
        if not self.deployment_models:
            raise RuntimeError("Deployment infrastructure is unavailable")
        pipeline, metadata = self.deployment_models.load()
        names = metadata["feature_names"]
        if not isinstance(names, list) or set(features) != set(names):
            missing = sorted(set(names) - set(features)) if isinstance(names, list) else []
            extra = sorted(set(features) - set(names)) if isinstance(names, list) else []
            raise ValueError(
                f"Exactly 16 canonical features are required; missing={missing}, extra={extra}"
            )
        values: dict[str, float] = {}
        for name in names:
            raw = features[name]
            if isinstance(raw, bool) or not isinstance(raw, (float, int)) or not math.isfinite(raw):
                raise ValueError(f"{name} must be a finite numeric value")
            values[name] = float(raw)
        frame = pd.DataFrame([values], columns=names)
        predicted = str(pipeline.predict(frame)[0])
        probabilities = pipeline.predict_proba(frame)[0]
        labels = [str(label) for label in pipeline.classes_]
        scores = {label: float(score) for label, score in zip(labels, probabilities, strict=True)}
        if labels != metadata["classes"] or predicted not in scores:
            raise ValueError("Deployment model class metadata mismatch")
        return {
            "model_id": metadata["model_id"],
            "source_run": metadata["source_run"],
            "predicted_class": predicted,
            "predicted_probability": scores[predicted],
            "probabilities": scores,
            "features": values,
            "dataset_sha256": metadata["dataset_sha256"],
        }

    def create_experiment(self, name: str, configuration: ExperimentConfig) -> Experiment:
        clean_name = name.strip()
        if not clean_name or len(clean_name) > 120:
            raise ValueError("Experiment name must contain 1–120 characters")
        if configuration.budget_kind not in ("original_features", "pca_components"):
            raise ValueError("Unknown feature-budget representation")
        if configuration.budget_kind == "original_features":
            if (
                configuration.selector is SelectorId.PCA
                or configuration.n_components is not None
                or configuration.required_raw_feature_count is not None
            ):
                raise ValueError("PCA is not an original-feature selector")
            if configuration.k_original_features is None:
                raise ValueError("k_original_features is required")
            OriginalFeatureBudget(configuration.k_original_features)
            if (
                configuration.selector is SelectorId.NONE
                and configuration.k_original_features != 16
            ):
                raise ValueError("No-selector baseline requires 16 original features")
        else:
            if (
                configuration.selector is not SelectorId.PCA
                or configuration.k_original_features is not None
            ):
                raise ValueError("PCA requires pca selector and n_components")
            if configuration.n_components is None:
                raise ValueError("n_components is required")
            PCARepresentation(
                configuration.n_components,
                configuration.required_raw_feature_count
                if configuration.required_raw_feature_count is not None
                else 16,
            )
        if configuration.evaluation_mode not in ("protocol", "smoke"):
            raise ValueError("Unknown evaluation mode")
        if not 0 <= configuration.seed <= 4_294_967_295:
            raise ValueError("Seed must be a valid unsigned 32-bit integer")
        if configuration.selector in (
            SelectorId.CORRELATION_PRUNING,
            SelectorId.SEQUENTIAL_FEATURE_SELECTION,
        ):
            raise ValueError("Extended selector is not implemented in Core")
        frozen_space = preset_search_space(
            configuration.model, smoke=configuration.evaluation_mode == "smoke"
        )
        if configuration.search_space and configuration.search_space != frozen_space:
            raise ValueError("Search space differs from predeclared small-grid-v1 preset")
        configuration = replace(configuration, search_space=frozen_space)
        if self.datasets and configuration.dataset_version is None:
            registered = self.datasets.list()
            if len(registered) == 1:
                configuration = replace(
                    configuration, dataset_version=str(registered[0]["version"])
                )
        return self.experiments.create(clean_name, configuration)

    def list_experiments(self) -> list[Experiment]:
        return self.experiments.list()

    def get_experiment(self, experiment_id: int) -> Experiment:
        experiment = self.experiments.get(experiment_id)
        if experiment is None:
            raise NotFoundError("Experiment not found")
        return experiment

    def create_run(self, experiment_id: int) -> Run:
        self.get_experiment(experiment_id)
        return self.runs.create(experiment_id)

    def enqueue_core_matrix(self, *, create: bool) -> dict[str, object]:
        """Idempotently plan or enqueue missing Core MI and 16-feature baselines."""
        datasets = self.list_datasets()
        if len(datasets) != 1:
            raise ValueError("Exactly one validated dataset version is required")
        dataset_version = str(datasets[0]["version"])
        core_models = (
            ModelId.LOGISTIC_REGRESSION,
            ModelId.SVM_RBF,
            ModelId.RANDOM_FOREST,
            ModelId.XGBOOST,
            ModelId.LIGHTGBM,
        )
        conditions: list[tuple[str, ExperimentConfig]] = []
        for model in (*core_models, ModelId.MLP):
            conditions.append(
                (
                    f"C0 baseline {model.value}",
                    ExperimentConfig(
                        model=model,
                        selector=SelectorId.NONE,
                        budget_kind="original_features",
                        k_original_features=16,
                        dataset_version=dataset_version,
                        search_space=preset_search_space(model),
                    ),
                )
            )
        for model in core_models:
            for k in range(1, 17):
                conditions.append(
                    (
                        f"C1 MI {model.value} k={k}",
                        ExperimentConfig(
                            model=model,
                            selector=SelectorId.MUTUAL_INFORMATION,
                            budget_kind="original_features",
                            k_original_features=k,
                            dataset_version=dataset_version,
                            search_space=preset_search_space(model),
                        ),
                    )
                )
        experiments = self.list_experiments()
        runs = self.list_runs()
        run_by_experiment: dict[int, list[Run]] = {}
        for run in runs:
            run_by_experiment.setdefault(run.experiment_id, []).append(run)
        summary: dict[str, object] = {
            "total_conditions": len(conditions),
            "completed": 0,
            "active": 0,
            "missing": 0,
            "retried": 0,
            "created_run_ids": [],
        }
        for name, config in conditions:
            matching = [item for item in experiments if item.configuration == config]
            matching_runs = [run for item in matching for run in run_by_experiment.get(item.id, [])]
            if any(run.status.value == "COMPLETED" for run in matching_runs):
                summary["completed"] = int(summary["completed"]) + 1
                continue
            if any(run.status.value in {"QUEUED", "RUNNING"} for run in matching_runs):
                summary["active"] = int(summary["active"]) + 1
                continue
            summary["missing"] = int(summary["missing"]) + 1
            if not create:
                continue
            experiment = matching[0] if matching else self.create_experiment(name, config)
            created = self.create_run(experiment.id)
            created_ids = summary["created_run_ids"]
            assert isinstance(created_ids, list)
            created_ids.append(created.display_id)
            if matching_runs:
                summary["retried"] = int(summary["retried"]) + 1
        return summary

    def list_runs(self) -> list[Run]:
        return self.runs.list()

    def get_run(self, run_id: int) -> Run:
        run = self.runs.get(run_id)
        if run is None:
            raise NotFoundError("Run not found")
        return run

    def cancel_run(self, run_id: int) -> Run:
        run = self.get_run(run_id)
        if run.status.value not in ("DRAFT", "QUEUED", "RUNNING"):
            raise ConflictError("Run cannot be cancelled from its current state")
        cancelled = self.runs.cancel(run_id)
        if cancelled is None:
            raise ConflictError("Run status changed; refresh and retry")
        return cancelled

    def system_info(self) -> dict[str, object]:
        return self.metadata.system_info()

    def fetch_dataset(self, *, accept_official_schema: bool) -> dict[str, object]:
        if not self.dataset_store or not self.datasets:
            raise RuntimeError("Dataset infrastructure is unavailable")
        self.dataset_store.download()
        return self.validate_dataset(accept_official_schema=accept_official_schema)

    def validate_dataset(self, *, accept_official_schema: bool) -> dict[str, object]:
        if not self.dataset_store or not self.datasets:
            raise RuntimeError("Dataset infrastructure is unavailable")
        manifest = self.dataset_store.validate(accept_official_schema=accept_official_schema)
        self.datasets.register(manifest)
        return manifest

    def list_datasets(self) -> list[dict[str, object]]:
        return self.datasets.list() if self.datasets else []

    def get_dataset_manifest(self, dataset_id: int) -> dict[str, object]:
        if not any(item["id"] == dataset_id for item in self.list_datasets()):
            raise NotFoundError("Dataset not found")
        if not self.dataset_store:
            raise RuntimeError("Dataset infrastructure is unavailable")
        _, manifest = self.dataset_store.load()
        return manifest

    def dataset_quality(self, dataset_id: int) -> dict[str, object]:
        registered = next(
            (item for item in self.list_datasets() if int(item["id"]) == dataset_id), None
        )
        if registered is None:
            raise NotFoundError(f"Dataset {dataset_id} not found")
        if not self.dataset_store:
            raise RuntimeError("Dataset storage is unavailable")
        dataset, manifest = self.dataset_store.load()
        if dataset.arff_sha256 != registered["arff_sha256"]:
            raise ValueError("Registered dataset hash does not match validated source")
        return {
            **dataset_quality_summary(dataset),
            "source_id": manifest["source_id"],
            "schema_notice": manifest["schema_notice"],
        }

    def recover_interrupted_runs(self) -> int:
        return self.runs.recover_running()

    def process_next_run(self, *, should_stop: Callable[[], bool] | None = None) -> Run | None:
        run = self.runs.claim_next()
        if run is None:
            return None
        if not self.dataset_store or not self.artifacts:
            self.runs.fail(run.id, "ML infrastructure is unavailable")
            return self.get_run(run.id)
        try:
            experiment = self.get_experiment(run.experiment_id)
            dataset, manifest = self.dataset_store.load()
            config = experiment.configuration
            if config.dataset_version != manifest["dataset_version"]:
                raise ValueError(
                    "Experiment dataset version is absent or differs from validated UCI 602"
                )
            condition = EngineCondition(
                model=ModelId(config.model),
                selector=SelectorId(config.selector),
                budget_kind=config.budget_kind,
                k_original_features=config.k_original_features,
                n_components=config.n_components,
                seed=config.seed,
                search_space=config.search_space,
                evaluation_mode=config.evaluation_mode,
            )
            provenance = self.metadata.provenance()
            canonical = json.dumps(
                {
                    "configuration": asdict(config),
                    "dataset_hash": dataset.arff_sha256,
                    "provenance": provenance,
                },
                sort_keys=True,
                default=str,
            ).encode()
            fingerprint = sha256(canonical).hexdigest()
            result = run_nested_cv(
                dataset.features,
                dataset.target,
                condition,
                on_fold=lambda fold: self.artifacts.write_json(
                    f"{run.display_id}/fold-{fold['fold_id']}.json", fold
                ),
                should_cancel=lambda: (
                    bool(should_stop and should_stop())
                    or self.get_run(run.id).status.value == "CANCELLED"
                ),
            )
            payload = {
                "run_id": run.display_id,
                "experiment_id": experiment.id,
                "dataset_manifest": manifest,
                "configuration": asdict(config),
                "provenance": provenance,
                "fingerprint": fingerprint,
                "summary": result.summary,
                "folds": result.folds,
                "splits": result.splits,
            }
            path = f"{run.display_id}/result.json"
            digest = self.artifacts.write_json(path, payload)
            verified = self.artifacts.read_json(path, digest)
            expected = 15 if config.evaluation_mode == "protocol" else 2
            if not isinstance(verified, dict) or len(verified.get("folds", [])) != expected:
                raise ValueError("Result artifact does not contain all required outer folds")
            completed = self.runs.complete(
                run.id, path, digest, result.summary, dataset.arff_sha256, fingerprint
            )
            if completed is None:
                raise InterruptedError("Run state changed before completion")
            return completed
        except InterruptedError:
            if self.get_run(run.id).status.value == "RUNNING":
                self.runs.fail(run.id, "Worker interrupted; partial folds are not final results")
            return self.get_run(run.id)
        except Exception as exc:
            detail_path = f"{run.display_id}/error.json"
            self.artifacts.write_json(
                detail_path, {"error_type": type(exc).__name__, "traceback": traceback.format_exc()}
            )
            self.runs.fail(run.id, f"{type(exc).__name__}: {exc}", detail_path)
            return self.get_run(run.id)

    def get_run_result(self, run_id: int) -> dict[str, object] | None:
        run = self.get_run(run_id)
        if (
            run.status.value != "COMPLETED"
            or not run.result_artifact
            or not run.result_sha256
            or not self.artifacts
        ):
            return None
        payload = self.artifacts.read_json(run.result_artifact, run.result_sha256)
        if not isinstance(payload, dict):
            raise ValueError("Invalid scientific result artifact")
        return payload

    def get_run_detail(self, run_id: int) -> dict[str, object] | None:
        """Read verified provenance without transferring full predictions to the overview."""
        run = self.get_run(run_id)
        payload = self.get_run_result(run_id)
        if payload is None:
            return None
        return {
            "run_id": run.display_id,
            "configuration": payload["configuration"],
            "dataset_manifest": payload["dataset_manifest"],
            "provenance": payload["provenance"],
            "fingerprint": payload["fingerprint"],
            "result_artifact": run.result_artifact,
            "result_sha256": run.result_sha256,
            "artifact_verified": True,
        }

    def verify_run(self, run_id: int) -> dict[str, object]:
        """Verify immutable provenance, configuration, folds, and artifact integrity."""
        run = self.get_run(run_id)
        errors: list[str] = []
        checks: dict[str, bool] = {}
        try:
            payload = self.get_run_result(run_id)
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            payload = None
            errors.append(f"artifact_integrity: {exc}")
        checks["completed_with_verified_artifact"] = payload is not None
        if payload is None:
            return {
                "run_id": run.display_id,
                "verified": False,
                "checks": checks,
                "errors": errors or ["Scientific result is not available"],
            }

        experiment = self.get_experiment(run.experiment_id)
        stored_config = payload.get("configuration")
        current_config = {
            key: value
            for key, value in asdict(experiment.configuration).items()
            if value is not None
            or key in (stored_config if isinstance(stored_config, dict) else {})
        }
        checks["configuration_consistent"] = stored_config == current_config
        if not checks["configuration_consistent"]:
            errors.append("Artifact configuration differs from experiment metadata")

        manifest = payload.get("dataset_manifest")
        artifact_dataset_hash = manifest.get("arff_sha256") if isinstance(manifest, dict) else None
        artifact_dataset_version = (
            manifest.get("dataset_version") if isinstance(manifest, dict) else None
        )
        checks["dataset_provenance_consistent"] = (
            bool(artifact_dataset_hash)
            and artifact_dataset_hash == run.dataset_hash
            and artifact_dataset_version == experiment.configuration.dataset_version
        )
        if not checks["dataset_provenance_consistent"]:
            errors.append("Dataset hashes in artifact and run metadata differ")

        summary = payload.get("summary")
        folds = payload.get("folds")
        mode = experiment.configuration.evaluation_mode
        expected_folds = 15 if mode == "protocol" else 2
        checks["fold_completeness"] = (
            isinstance(folds, list)
            and len(folds) == expected_folds
            and len({fold.get("fold_id") for fold in folds if isinstance(fold, dict)})
            == expected_folds
        )
        if not checks["fold_completeness"]:
            errors.append(f"Expected {expected_folds} unique outer folds")
        fold_hashes = [
            str(fold.get("split_sha256")) for fold in folds or [] if isinstance(fold, dict)
        ]
        calculated_split_set = sha256("".join(fold_hashes).encode()).hexdigest()
        checks["outer_split_hash_consistent"] = (
            isinstance(summary, dict)
            and len(fold_hashes) == expected_folds
            and summary.get("outer_split_set_sha256") == calculated_split_set
        )
        if not checks["outer_split_hash_consistent"]:
            errors.append("Outer split-set hash does not match fold artifacts")

        expected_protocol = CV_PROTOCOL_VERSION if mode == "protocol" else SMOKE_PROTOCOL_VERSION
        checks["protocol_version_supported"] = (
            isinstance(summary, dict) and summary.get("cv_protocol_version") == expected_protocol
        )
        if not checks["protocol_version_supported"]:
            errors.append("Run protocol version differs from the current engine")

        provenance = payload.get("provenance")
        fingerprint_payload = {
            "configuration": stored_config,
            "dataset_hash": artifact_dataset_hash,
            "provenance": provenance,
        }
        calculated_fingerprint = sha256(
            json.dumps(fingerprint_payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        checks["fingerprint_consistent"] = (
            payload.get("fingerprint") == calculated_fingerprint == run.fingerprint
        )
        if not checks["fingerprint_consistent"]:
            errors.append("Configuration/provenance fingerprint differs")

        checks["fold_metrics_finite"] = isinstance(folds, list) and all(
            isinstance(fold, dict)
            and all(
                isinstance(fold.get(key), (int, float)) and math.isfinite(float(fold[key]))
                for key in ("macro_f1", "accuracy")
            )
            for fold in folds
        )
        if not checks["fold_metrics_finite"]:
            errors.append("Fold metrics are missing or non-finite")

        return {
            "run_id": run.display_id,
            "verified": all(checks.values()),
            "checks": checks,
            "errors": errors,
            "result_artifact": run.result_artifact,
            "result_sha256": run.result_sha256,
            "dataset_sha256": run.dataset_hash,
            "fingerprint": run.fingerprint,
        }

    def reproduce_run(self, run_id: int) -> Run:
        """Create a new queued run from an immutable verified configuration snapshot."""
        verification = self.verify_run(run_id)
        if not verification["verified"]:
            raise ConflictError("Source run failed verification and cannot be reproduced")
        source = self.get_run(run_id)
        source_experiment = self.get_experiment(source.experiment_id)
        if not self.dataset_store:
            raise RuntimeError("Dataset storage is unavailable")
        dataset, manifest = self.dataset_store.load()
        if dataset.arff_sha256 != source.dataset_hash:
            raise ConflictError("Current validated dataset differs from the source run")
        model = source_experiment.configuration.model
        dependency = {
            ModelId.XGBOOST: "xgboost",
            ModelId.LIGHTGBM: "lightgbm",
        }.get(model)
        if dependency and importlib.util.find_spec(dependency) is None:
            raise ConflictError(f"Required model dependency is unavailable: {dependency}")
        configuration = replace(
            source_experiment.configuration,
            dataset_version=str(manifest["dataset_version"]),
            reproduces_run_id=source.display_id,
        )
        experiment = self.create_experiment(f"Reproduction of {source.display_id}", configuration)
        return self.create_run(experiment.id)

    def export_run(self, run_id: int, kind: str) -> tuple[str, str, bytes]:
        """Create a deterministic export from a verified scientific result."""
        verification = self.verify_run(run_id)
        if not verification["verified"]:
            raise ConflictError("Only a verified completed run can be exported")
        payload = self.get_run_result(run_id)
        assert payload is not None
        run = self.get_run(run_id)
        if kind == "result.json":
            content = json.dumps(payload, ensure_ascii=False, indent=2).encode()
            return f"{run.display_id}-result.json", "application/json", content
        if kind == "config.json":
            snapshot = {
                "run_id": run.display_id,
                "configuration": payload["configuration"],
                "dataset_manifest": payload["dataset_manifest"],
                "provenance": payload["provenance"],
                "fingerprint": payload["fingerprint"],
                "result_sha256": run.result_sha256,
            }
            content = json.dumps(snapshot, ensure_ascii=False, indent=2).encode()
            return f"{run.display_id}-config.json", "application/json", content
        if kind not in {"folds.csv", "selected-features.csv"}:
            raise ValueError("Unsupported run export kind")
        output = io.StringIO(newline="")
        if kind == "folds.csv":
            fieldnames = [
                "fold_id",
                "split_sha256",
                "train_size",
                "test_size",
                "macro_f1",
                "accuracy",
                "roc_auc_ovr_macro",
                "search_seconds",
                "refit_seconds",
                "serialized_pipeline_bytes",
                "peak_memory_bytes",
                "selected_original_features",
                "best_params",
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for fold in payload["folds"]:
                writer.writerow(
                    {
                        **{key: fold.get(key) for key in fieldnames},
                        "selected_original_features": json.dumps(
                            fold.get("selected_original_features"), ensure_ascii=False
                        ),
                        "best_params": json.dumps(
                            fold.get("best_params"), ensure_ascii=False, sort_keys=True
                        ),
                    }
                )
            return (
                f"{run.display_id}-folds.csv",
                "text/csv; charset=utf-8",
                output.getvalue().encode(),
            )
        writer = csv.DictWriter(output, fieldnames=["fold_id", "feature", "selection_frequency"])
        writer.writeheader()
        frequencies = (payload.get("summary") or {}).get("feature_stability")
        frequency_by_name = frequencies.get("selection_frequency", {}) if frequencies else {}
        for fold in payload["folds"]:
            for feature in fold.get("selected_original_features") or []:
                writer.writerow(
                    {
                        "fold_id": fold["fold_id"],
                        "feature": feature,
                        "selection_frequency": frequency_by_name.get(feature),
                    }
                )
        return (
            f"{run.display_id}-selected-features.csv",
            "text/csv; charset=utf-8",
            output.getvalue().encode(),
        )

    def run_resources(self, run_id: int) -> dict[str, object]:
        """Aggregate recorded full-pipeline engineering measurements without inventing values."""
        payload = self.get_run_result(run_id)
        if payload is None:
            raise ConflictError("Scientific result is not available")
        folds = payload["folds"]

        def distribution(values: list[float]) -> dict[str, float | int] | None:
            if not values:
                return None
            series = pd.Series(values, dtype=float)
            return {
                "samples": len(values),
                "median": float(series.median()),
                "p95": float(series.quantile(0.95)),
                "minimum": float(series.min()),
                "maximum": float(series.max()),
            }

        latency: dict[str, object] = {}
        for key in ("single_row", "batch_1000"):
            samples = [
                float(value)
                for fold in folds
                for value in (fold.get("inference_latency", {}).get(key, {}).get("samples_ms", []))
            ]
            latency[key] = distribution(samples)
        peak_values = [
            int(fold["peak_memory_bytes"])
            for fold in folds
            if fold.get("peak_memory_bytes") is not None
        ]
        return {
            "run_id": payload["run_id"],
            "measurement_scope": "outer-fold full preprocessing-and-model pipelines",
            "total_nested_search_seconds": sum(float(fold["search_seconds"]) for fold in folds),
            "total_outer_refit_seconds": sum(float(fold["refit_seconds"]) for fold in folds),
            "inference_latency_ms": latency,
            "serialized_pipeline_bytes": distribution(
                [float(fold["serialized_pipeline_bytes"]) for fold in folds]
            ),
            "peak_memory_bytes": distribution([float(value) for value in peak_values]),
            "peak_memory_status": "CALCULATED" if peak_values else "NOT_CALCULATED",
            "peak_memory_reason": None
            if peak_values
            else "No reliable isolated process-tree RSS measurement was recorded for this run.",
            "software_hardware_profile": payload["provenance"],
            "timing_note": (
                "Latency includes the full fitted preprocessing pipeline, uses fold-local warm-up, "
                "and is an engineering benchmark rather than a scientific performance metric."
            ),
        }

    def feature_budget_series(self) -> list[dict[str, object]]:
        points = []
        for run in self.list_runs():
            summary = run.summary
            if run.status.value != "COMPLETED" or not summary:
                continue
            if (
                summary.get("evaluation_mode") != "protocol"
                or summary.get("selector") != "mutual_information"
            ):
                continue
            points.append(
                {
                    "run_id": run.display_id,
                    "model": summary["model"],
                    "budget_kind": summary["budget_kind"],
                    "k_original_features": summary["k_original_features"],
                    "macro_f1_mean": summary["macro_f1_mean"],
                    "accuracy_mean": summary["accuracy_mean"],
                    "macro_f1_fold_sd_descriptive": summary["macro_f1_fold_sd_descriptive"],
                    "dataset_hash": run.dataset_hash,
                    "outer_split_set_sha256": summary["outer_split_set_sha256"],
                }
            )
        return points

    def feature_selection_series(self) -> list[dict[str, object]]:
        """Expose real fold-derived stability summaries for original-feature selectors."""
        points: list[dict[str, object]] = []
        for run in self.list_runs():
            summary = run.summary
            if run.status.value != "COMPLETED" or not summary:
                continue
            stability = summary.get("feature_stability")
            if (
                summary.get("evaluation_mode") != "protocol"
                or summary.get("budget_kind") != "original_features"
                or not isinstance(stability, dict)
            ):
                continue
            points.append(
                {
                    "run_id": run.display_id,
                    "model": summary["model"],
                    "selector": summary["selector"],
                    "k_original_features": summary["k_original_features"],
                    "outer_fold_count": summary["outer_fold_count"],
                    "selection_frequency": stability["selection_frequency"],
                    "pairwise_jaccard_mean": stability["pairwise_jaccard_mean"],
                    "dataset_hash": run.dataset_hash,
                    "outer_split_set_sha256": summary["outer_split_set_sha256"],
                }
            )
        return points

    def compare_runs(
        self, compact_run_id: int, baseline_run_id: int, *, persist: bool = False
    ) -> dict[str, object]:
        """Compare matching outer folds without a sufficiency claim."""
        compact_run = self.get_run(compact_run_id)
        baseline_run = self.get_run(baseline_run_id)
        if compact_run.dataset_hash != baseline_run.dataset_hash or not compact_run.dataset_hash:
            raise ValueError("Paired runs require the same validated dataset hash")
        compact_payload = self.get_run_result(compact_run_id)
        baseline_payload = self.get_run_result(baseline_run_id)
        if not compact_payload or not baseline_payload:
            raise ConflictError("Both runs must be completed before paired comparison")
        compact_config = self.get_experiment(compact_run.experiment_id).configuration
        baseline_config = self.get_experiment(baseline_run.experiment_id).configuration
        if (
            compact_config.seed != baseline_config.seed
            or compact_config.search_space != baseline_config.search_space
            or compact_config.model != baseline_config.model
            or baseline_config.selector is not SelectorId.NONE
        ):
            raise ValueError(
                "Paired runs need matching seed/model/search space and a no-selector baseline"
            )
        compact = NestedResult(
            compact_payload["folds"], compact_payload["summary"], compact_payload["splits"]
        )
        baseline = NestedResult(
            baseline_payload["folds"], baseline_payload["summary"], baseline_payload["splits"]
        )
        comparison = paired_comparison(compact, baseline)
        payload = {
            "compact_run_id": compact_run.display_id,
            "baseline_run_id": baseline_run.display_id,
            "dataset_hash": compact_run.dataset_hash,
            "comparison": comparison,
        }
        if not persist:
            return payload
        if not self.artifacts:
            raise RuntimeError("Scientific artifact store is unavailable")
        path = f"{compact_run.display_id}/paired-vs-{baseline_run.display_id}.json"
        digest = self.artifacts.write_json(path, payload)
        return {**payload, "artifact_relative_path": path, "artifact_sha256": digest}

    def core_sufficiency(self, model: ModelId, *, persist: bool = False) -> dict[str, object]:
        """Evaluate all available Core MI k values against the matching no-selector baseline."""
        completed: list[tuple[Run, ExperimentConfig]] = []
        for run in self.list_runs():
            if run.status.value == "COMPLETED":
                completed.append((run, self.get_experiment(run.experiment_id).configuration))
        baselines = [
            (run, config)
            for run, config in completed
            if config.model is model
            and config.selector is SelectorId.NONE
            and config.budget_kind == "original_features"
            and config.k_original_features == 16
            and config.evaluation_mode == "protocol"
        ]
        if not baselines:
            return {
                "model": model.value,
                "minimal_sufficient_k": None,
                "status": "NOT_CALCULATED_MISSING_BASELINE",
                "comparisons": [],
            }
        baseline = baselines[0][0]
        comparisons: list[dict[str, object]] = []
        sufficient: list[int] = []
        for k in range(1, 16):
            candidates = [
                run
                for run, config in completed
                if config.model is model
                and config.selector is SelectorId.MUTUAL_INFORMATION
                and config.budget_kind == "original_features"
                and config.k_original_features == k
                and config.evaluation_mode == "protocol"
                and config.dataset_version == baselines[0][1].dataset_version
                and config.seed == baselines[0][1].seed
                and config.search_space == baselines[0][1].search_space
            ]
            if not candidates:
                comparisons.append({"k_original_features": k, "decision": "not_calculated"})
                continue
            result = self.compare_runs(candidates[0].id, baseline.id)["comparison"]
            assert isinstance(result, dict)
            comparisons.append({"k_original_features": k, **result})
            if result["decision"] == "sufficient":
                sufficient.append(k)
        calculated = sum(item["decision"] != "not_calculated" for item in comparisons)
        payload: dict[str, object] = {
            "model": model.value,
            "baseline_run_id": baseline.display_id,
            "dataset_hash": baseline.dataset_hash,
            "outer_split_set_sha256": baseline.summary["outer_split_set_sha256"]
            if baseline.summary
            else None,
            "minimal_sufficient_k": min(sufficient) if sufficient else None,
            "status": "CALCULATED" if calculated == 15 else "PARTIAL",
            "calculated_comparisons": calculated,
            "comparisons": comparisons,
        }
        if not persist:
            return payload
        if not self.artifacts:
            raise RuntimeError("Scientific artifact store is unavailable")
        path = (
            f"analysis/core-sufficiency-{model.value}-{payload['status'].lower()}-"
            f"{calculated:02d}.json"
        )
        digest = self.artifacts.write_json(path, payload)
        return {**payload, "artifact_relative_path": path, "artifact_sha256": digest}
