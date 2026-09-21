from dataclasses import dataclass

from beanfeature_application.service import ApplicationService

from .database import make_engine, make_session_factory
from .metadata import EnvironmentMetadata, SQLiteWorkerHeartbeat
from .repositories import SQLiteExperimentRepository, SQLiteRunRepository


@dataclass
class Container:
    service: ApplicationService
    metadata: EnvironmentMetadata
    heartbeat: SQLiteWorkerHeartbeat


def create_container(database_url: str | None = None) -> Container:
    engine = make_engine(database_url)
    sessions = make_session_factory(engine)
    metadata = EnvironmentMetadata(engine, sessions)
    return Container(
        service=ApplicationService(
            SQLiteExperimentRepository(sessions),
            SQLiteRunRepository(sessions),
            metadata,
        ),
        metadata=metadata,
        heartbeat=SQLiteWorkerHeartbeat(sessions),
    )
