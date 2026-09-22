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
from beanfeature_research.engine import (
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
        if run.display_id != "RUN-000003" or result is None:
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
            model=config.model, selector=config.selector, budget_kind="original_features",
            k_original_features=16, n_components=None, seed=config.seed,
            search_space=config.search_space,
        )
        pipeline = build_pipeline(condition).set_params(**chosen)
        pipeline.fit(dataset.features, dataset.target)
        metadata: dict[str, object] = {
            "model_id": "lr-uci-602-full16-v1",
            "model_family": "Logistic Regression",
            "source_run": run.display_id,
            "dataset_id": 602,
            "dataset_sha256": dataset.arff_sha256,
            "feature_names": list(dataset.feature_names),
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

    def classifier_example(self) -> dict[str, float]:
        if not self.dataset_store:
            raise RuntimeError("Dataset infrastructure is unavailable")
        dataset, _ = self.dataset_store.load()
        return {name: float(dataset.features.iloc[0][name]) for name in dataset.feature_names}

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
                    "macro_f1_fold_sd_descriptive": summary["macro_f1_fold_sd_descriptive"],
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
