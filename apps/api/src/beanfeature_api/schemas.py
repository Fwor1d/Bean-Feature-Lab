from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from beanfeature_application.contracts import Experiment, ExperimentConfig, Run
from beanfeature_research.contracts import ModelId, RunStatus, SelectorId


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]


class SystemInfoResponse(BaseModel):
    app_version: str
    api_version: str
    python_version: str
    platform: str
    git_commit: str | None
    database: str
    worker: str
    scientific_results: Literal["NOT_CALCULATED"]


class ProjectResponse(BaseModel):
    id: int
    name: str


class DatasetResponse(BaseModel):
    id: int
    source_id: int
    version: str
    validated: bool


class ExperimentConfigDTO(BaseModel):
    model: ModelId
    selector: SelectorId
    budget_kind: Literal["original_features", "pca_components"]
    k_original_features: int | None = Field(default=None, ge=1, le=16)
    n_components: int | None = Field(default=None, ge=1, le=16)
    required_raw_feature_count: int | None = None
    dataset_version: str | None = Field(default=None, max_length=128)
    seed: int = 42

    def to_domain(self) -> ExperimentConfig:
        return ExperimentConfig(**self.model_dump())


class CreateExperimentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    configuration: ExperimentConfigDTO


class ExperimentResponse(BaseModel):
    id: int
    name: str
    configuration: ExperimentConfigDTO
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, experiment: Experiment) -> "ExperimentResponse":
        return cls(
            id=experiment.id,
            name=experiment.name,
            configuration=ExperimentConfigDTO.model_validate(experiment.configuration.__dict__),
            created_at=experiment.created_at,
            updated_at=experiment.updated_at,
        )


class RunResponse(BaseModel):
    id: int
    display_id: str
    experiment_id: int
    status: RunStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    metrics: None = None  # No scientific result path exists in Stage 4A.
    result_state: Literal["NOT_CALCULATED"] = "NOT_CALCULATED"

    @classmethod
    def from_domain(cls, run: Run) -> "RunResponse":
        return cls(
            id=run.id,
            display_id=run.display_id,
            experiment_id=run.experiment_id,
            status=run.status,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            error=run.error,
        )
