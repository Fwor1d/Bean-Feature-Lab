from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from beanfeature_research.contracts import ModelId, RunStatus, SelectorId


@dataclass(frozen=True)
class ExperimentConfig:
    model: ModelId
    selector: SelectorId
    budget_kind: Literal["original_features", "pca_components"]
    k_original_features: int | None = None
    n_components: int | None = None
    required_raw_feature_count: int | None = None
    dataset_version: str | None = None
    seed: int = 42


@dataclass(frozen=True)
class Experiment:
    id: int
    name: str
    configuration: ExperimentConfig
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Run:
    id: int
    experiment_id: int
    status: RunStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None

    @property
    def display_id(self) -> str:
        return f"RUN-{self.id:06d}"


class ExperimentRepository(Protocol):
    def create(self, name: str, configuration: ExperimentConfig) -> Experiment: ...
    def list(self) -> list[Experiment]: ...
    def get(self, experiment_id: int) -> Experiment | None: ...


class RunRepository(Protocol):
    def create(self, experiment_id: int) -> Run: ...
    def list(self) -> list[Run]: ...
    def get(self, run_id: int) -> Run | None: ...
    def cancel(self, run_id: int) -> Run | None: ...


class MetadataProvider(Protocol):
    def system_info(self) -> dict[str, object]: ...


class WorkerHeartbeat(Protocol):
    def beat(self) -> None: ...
    def status(self) -> str: ...
