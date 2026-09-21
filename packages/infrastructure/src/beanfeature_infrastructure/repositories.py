from dataclasses import asdict
from datetime import UTC

from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from beanfeature_application.contracts import Experiment, ExperimentConfig, Run
from beanfeature_research.contracts import RunStatus

from .database import ExperimentRow, RunRow, utc_now


def _aware(value):  # type: ignore[no-untyped-def]
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _experiment(row: ExperimentRow) -> Experiment:
    return Experiment(
        row.id,
        row.name,
        ExperimentConfig(**row.configuration),
        _aware(row.created_at),
        _aware(row.updated_at),
    )


def _run(row: RunRow) -> Run:
    return Run(
        row.id,
        row.experiment_id,
        RunStatus(row.status),
        _aware(row.created_at),
        _aware(row.started_at),
        _aware(row.finished_at),
        row.error,
    )


class SQLiteExperimentRepository:
    def __init__(self, sessions: sessionmaker) -> None:
        self.sessions = sessions

    def create(self, name: str, configuration: ExperimentConfig) -> Experiment:
        now = utc_now()
        with self.sessions.begin() as session:
            row = ExperimentRow(
                name=name,
                configuration=asdict(configuration),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            return _experiment(row)

    def list(self) -> list[Experiment]:
        with self.sessions() as session:
            rows = session.scalars(select(ExperimentRow).order_by(ExperimentRow.id.desc())).all()
            return [_experiment(row) for row in rows]

    def get(self, experiment_id: int) -> Experiment | None:
        with self.sessions() as session:
            row = session.get(ExperimentRow, experiment_id)
            return _experiment(row) if row else None


class SQLiteRunRepository:
    def __init__(self, sessions: sessionmaker) -> None:
        self.sessions = sessions

    def create(self, experiment_id: int) -> Run:
        with self.sessions.begin() as session:
            row = RunRow(
                experiment_id=experiment_id,
                status=RunStatus.QUEUED.value,
                created_at=utc_now(),
            )
            session.add(row)
            session.flush()  # SQLite ROWID allocation is atomic; no MAX(id)+1 race.
            return _run(row)

    def list(self) -> list[Run]:
        with self.sessions() as session:
            rows = session.scalars(select(RunRow).order_by(RunRow.id.desc())).all()
            return [_run(row) for row in rows]

    def get(self, run_id: int) -> Run | None:
        with self.sessions() as session:
            row = session.get(RunRow, run_id)
            return _run(row) if row else None

    def cancel(self, run_id: int) -> Run | None:
        with self.sessions.begin() as session:
            changed = session.execute(
                update(RunRow)
                .where(RunRow.id == run_id, RunRow.status.in_(["DRAFT", "QUEUED", "RUNNING"]))
                .values(status=RunStatus.CANCELLED.value, finished_at=utc_now())
            )
            if changed.rowcount != 1:
                return None
            row = session.get(RunRow, run_id)
            return _run(row)
