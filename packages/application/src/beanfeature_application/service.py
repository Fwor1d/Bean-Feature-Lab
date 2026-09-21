from beanfeature_research.contracts import OriginalFeatureBudget, PCARepresentation, SelectorId

from .contracts import (
    Experiment,
    ExperimentConfig,
    ExperimentRepository,
    MetadataProvider,
    Run,
    RunRepository,
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
    ) -> None:
        self.experiments = experiments
        self.runs = runs
        self.metadata = metadata

    def create_experiment(self, name: str, configuration: ExperimentConfig) -> Experiment:
        clean_name = name.strip()
        if not clean_name or len(clean_name) > 120:
            raise ValueError("Experiment name must contain 1–120 characters")
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
