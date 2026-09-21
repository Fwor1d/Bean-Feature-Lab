import os
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class ExperimentRow(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RunRow(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("experiments.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class WorkerHeartbeatRow(Base):
    __tablename__ = "worker_heartbeat"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def database_url() -> str:
    return os.getenv("BEANFEATURE_DATABASE_URL", "sqlite:///storage/sqlite/beanfeature.sqlite")


def make_engine(url: str | None = None) -> Engine:
    engine = create_engine(url or database_url(), pool_pre_ping=True)

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def configure_sqlite(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
            del connection_record
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(engine, expire_on_commit=False)
