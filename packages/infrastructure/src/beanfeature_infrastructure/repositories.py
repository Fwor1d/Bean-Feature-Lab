from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from beanfeature_application.contracts import Experiment, ExperimentConfig, Run
from beanfeature_research.contracts import ModelId, RunStatus, SelectorId

from .database import DatasetVersionRow, ExperimentRow, RunEventRow, RunRow, utc_now


def _aware(value):  # type: ignore[no-untyped-def]
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _experiment(row: ExperimentRow) -> Experiment:
    configuration = dict(row.configuration)
    configuration["model"] = ModelId(configuration["model"])
    configuration["selector"] = SelectorId(configuration["selector"])
    return Experiment(
        row.id,
        row.name,
        ExperimentConfig(**configuration),
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
        row.result_artifact,
        row.result_sha256,
        row.summary,
        row.dataset_hash,
        row.fingerprint,
        row.error_detail_artifact,
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
            session.add(RunEventRow(run_id=row.id, status="QUEUED", created_at=utc_now()))
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
            session.add(RunEventRow(run_id=run_id, status="CANCELLED", created_at=utc_now()))
            return _run(row)

    def claim_next(self) -> Run | None:
        with self.sessions.begin() as session:
            ids = session.scalars(
                select(RunRow.id).where(RunRow.status == "QUEUED").order_by(RunRow.id).limit(1)
            ).all()
            if not ids:
                return None
            run_id = ids[0]
            changed = session.execute(
                update(RunRow)
                .where(RunRow.id == run_id, RunRow.status == "QUEUED")
                .values(status="RUNNING", started_at=utc_now(), error=None)
            )
            if changed.rowcount != 1:
                return None
            session.add(RunEventRow(run_id=run_id, status="RUNNING", created_at=utc_now()))
            return _run(session.get(RunRow, run_id))

    def complete(
        self,
        run_id: int,
        artifact: str,
        artifact_hash: str,
        summary: dict[str, object],
        dataset_hash: str,
        fingerprint: str,
    ) -> Run | None:
        with self.sessions.begin() as session:
            changed = session.execute(
                update(RunRow)
                .where(RunRow.id == run_id, RunRow.status == "RUNNING")
                .values(
                    status="COMPLETED",
                    finished_at=utc_now(),
                    result_artifact=artifact,
                    result_sha256=artifact_hash,
                    summary=summary,
                    dataset_hash=dataset_hash,
                    fingerprint=fingerprint,
                )
            )
            if changed.rowcount != 1:
                return None
            session.add(RunEventRow(run_id=run_id, status="COMPLETED", created_at=utc_now()))
            return _run(session.get(RunRow, run_id))

    def fail(self, run_id: int, error: str, detail_artifact: str | None = None) -> Run | None:
        with self.sessions.begin() as session:
            changed = session.execute(
                update(RunRow)
                .where(RunRow.id == run_id, RunRow.status == "RUNNING")
                .values(
                    status="FAILED",
                    finished_at=utc_now(),
                    error=error[:1000],
                    error_detail_artifact=detail_artifact,
                )
            )
            if changed.rowcount != 1:
                return None
            session.add(
                RunEventRow(run_id=run_id, status="FAILED", created_at=utc_now(), note=error[:255])
            )
            return _run(session.get(RunRow, run_id))

    def recover_running(self) -> int:
        with self.sessions.begin() as session:
            ids = session.scalars(select(RunRow.id).where(RunRow.status == "RUNNING")).all()
            for run_id in ids:
                session.execute(
                    update(RunRow)
                    .where(RunRow.id == run_id)
                    .values(
                        status="FAILED",
                        finished_at=utc_now(),
                        error="Worker interrupted; create a new run to restart",
                    )
                )
                session.add(
                    RunEventRow(
                        run_id=run_id,
                        status="FAILED",
                        created_at=utc_now(),
                        note="Recovered after worker restart",
                    )
                )
            return len(ids)


class SQLiteDatasetRepository:
    def __init__(self, sessions: sessionmaker) -> None:
        self.sessions = sessions

    def register(self, manifest: dict[str, object]) -> dict[str, object]:
        version = str(manifest["dataset_version"])
        with self.sessions.begin() as session:
            row = session.scalar(
                select(DatasetVersionRow).where(DatasetVersionRow.version == version)
            )
            if row is None:
                row = DatasetVersionRow(
                    source_id=602,
                    version=version,
                    archive_sha256=str(manifest["archive_sha256"]),
                    arff_sha256=str(manifest["arff_sha256"]),
                    manifest_path="data/processed/uci-dry-bean-602-manifest.json",
                    retrieved_at=datetime.fromisoformat(str(manifest["retrieved_at_utc"])),
                    rows=int(manifest["rows"]),
                    feature_count=int(manifest["feature_count"]),
                    classes=list(manifest["classes"]),
                )
                session.add(row)
                session.flush()
            elif row.arff_sha256 != manifest["arff_sha256"]:
                raise ValueError("Registered dataset version hash collision")
            return {
                "id": row.id,
                "source_id": row.source_id,
                "version": row.version,
                "validated": True,
                "rows": row.rows,
                "feature_count": row.feature_count,
                "arff_sha256": row.arff_sha256,
            }

    def list(self) -> list[dict[str, object]]:
        with self.sessions() as session:
            rows = session.scalars(select(DatasetVersionRow).order_by(DatasetVersionRow.id)).all()
            return [
                {
                    "id": row.id,
                    "source_id": row.source_id,
                    "version": row.version,
                    "validated": True,
                    "rows": row.rows,
                    "feature_count": row.feature_count,
                    "arff_sha256": row.arff_sha256,
                }
                for row in rows
            ]
