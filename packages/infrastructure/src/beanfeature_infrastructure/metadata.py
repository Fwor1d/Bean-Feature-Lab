import platform
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import version

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from .database import WorkerHeartbeatRow, utc_now


class EnvironmentMetadata:
    def __init__(self, engine: Engine, sessions: sessionmaker) -> None:
        self.engine = engine
        self.sessions = sessions

    def database_state(self) -> str:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                connection.execute(text("SELECT id FROM experiments LIMIT 1"))
            return "connected"
        except Exception:
            return "unavailable"

    def worker_status(self) -> str:
        try:
            with self.sessions() as session:
                heartbeat = session.scalar(
                    select(WorkerHeartbeatRow).where(WorkerHeartbeatRow.id == 1)
                )
            if heartbeat is None:
                return "not_started"
            seen_at = heartbeat.seen_at.replace(tzinfo=UTC)
            age = (datetime.now(UTC) - seen_at).total_seconds()
            return "online" if age < 20 else "offline"
        except Exception:
            return "unknown"

    def system_info(self) -> dict[str, object]:
        git_commit: str | None = None
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2,
                check=True,
            )
            git_commit = result.stdout.strip() or None
        except (OSError, subprocess.SubprocessError):
            pass
        return {
            "app_version": version("beanfeature-lab"),
            "api_version": "v1",
            "python_version": platform.python_version(),
            "platform": f"{sys.platform}-{platform.machine()}",
            "git_commit": git_commit,
            "database": self.database_state(),
            "worker": self.worker_status(),
            "scientific_results": "NOT_CALCULATED",
        }


class SQLiteWorkerHeartbeat:
    def __init__(self, sessions: sessionmaker) -> None:
        self.sessions = sessions

    def beat(self) -> None:
        with self.sessions.begin() as session:
            row = session.get(WorkerHeartbeatRow, 1)
            if row is None:
                session.add(WorkerHeartbeatRow(id=1, seen_at=utc_now()))
            else:
                row.seen_at = utc_now()

    def status(self) -> str:
        return "online"
