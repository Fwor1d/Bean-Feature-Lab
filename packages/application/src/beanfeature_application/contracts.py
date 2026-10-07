from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol

from beanfeature_research.contracts import ModelId, RunStatus, SelectorId
from beanfeature_research.dataset import ValidatedDataset


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
    evaluation_mode: Literal["protocol", "smoke"] = "protocol"
    search_space: dict[str, list[object]] = field(default_factory=dict)
    reproduces_run_id: str | None = None


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
    result_artifact: str | None = None
    result_sha256: str | None = None
    summary: dict[str, object] | None = None
    dataset_hash: str | None = None
    fingerprint: str | None = None
    error_detail_artifact: str | None = None

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
    def claim_next(self) -> Run | None: ...
    def complete(
        self,
        run_id: int,
        artifact: str,
        artifact_hash: str,
        summary: dict[str, object],
        dataset_hash: str,
        fingerprint: str,
    ) -> Run | None: ...
    def fail(self, run_id: int, error: str, detail_artifact: str | None = None) -> Run | None: ...
    def recover_running(self) -> int: ...


class DatasetRepository(Protocol):
    def register(self, manifest: dict[str, object]) -> dict[str, object]: ...
    def list(self) -> list[dict[str, object]]: ...


class DatasetStore(Protocol):
    def download(self) -> None: ...
    def validate(self, *, accept_official_schema: bool = False) -> dict[str, object]: ...
    def load(self) -> tuple[ValidatedDataset, dict[str, object]]: ...


class ScientificArtifactStore(Protocol):
    def write_json(self, relative_path: str, payload: object) -> str: ...
    def read_json(self, relative_path: str, expected_sha256: str) -> object: ...


class DeploymentModelStore(Protocol):
    def save(self, pipeline: object, metadata: dict[str, object]) -> dict[str, object]: ...
    def load(self) -> tuple[object, dict[str, object]]: ...
    def metadata(self) -> dict[str, object] | None: ...
    def latest_benchmark(self) -> dict[str, object] | None: ...


class MetadataProvider(Protocol):
    def system_info(self) -> dict[str, object]: ...
    def provenance(self) -> dict[str, object]: ...


class WorkerHeartbeat(Protocol):
    def beat(self) -> None: ...
    def status(self) -> str: ...
