from dataclasses import dataclass
from pathlib import Path

from beanfeature_application.service import ApplicationService

from .database import make_engine, make_session_factory
from .datasets import UCIDatasetStore
from .deployment import LocalDeploymentModelStore
from .files import ArtifactStore
from .metadata import EnvironmentMetadata, SQLiteWorkerHeartbeat
from .repositories import SQLiteDatasetRepository, SQLiteExperimentRepository, SQLiteRunRepository
from .resources import ProcessTreeResourceMonitor


@dataclass
class Container:
    service: ApplicationService
    metadata: EnvironmentMetadata
    heartbeat: SQLiteWorkerHeartbeat


def create_container(
    database_url: str | None = None, *, measure_process_resources: bool = False
) -> Container:
    engine = make_engine(database_url)
    sessions = make_session_factory(engine)
    metadata = EnvironmentMetadata(engine, sessions)
    dataset_store = UCIDatasetStore()
    datasets = SQLiteDatasetRepository(sessions)
    artifacts = ArtifactStore(Path("artifacts/runs"))
    return Container(
        service=ApplicationService(
            SQLiteExperimentRepository(sessions),
            SQLiteRunRepository(sessions, artifacts),
            metadata,
            datasets=datasets,
            dataset_store=dataset_store,
            artifacts=artifacts,
            deployment_models=LocalDeploymentModelStore(),
            resource_monitor=ProcessTreeResourceMonitor() if measure_process_resources else None,
        ),
        metadata=metadata,
        heartbeat=SQLiteWorkerHeartbeat(sessions),
    )
