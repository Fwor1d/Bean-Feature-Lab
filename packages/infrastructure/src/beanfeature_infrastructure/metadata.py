import platform
import subprocess
import sys
from datetime import UTC, datetime
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from .database import Base, RunRow, WorkerHeartbeatRow, utc_now


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

    def presentation_readiness(self) -> bool:
        """Cheap read-only schema check; no migrations, training or artifact rehashing."""
        try:
            head = ScriptDirectory(str(Path(__file__).resolve().parents[2] / "alembic"))
            with self.engine.connect() as connection:
                revisions = connection.execute(text("SELECT version_num FROM alembic_version"))
                if revisions.scalars().all() != [head.get_current_head()]:
                    return False
                for table in Base.metadata.sorted_tables:
                    connection.execute(select(table).limit(0))
            return True
        except Exception:
            return False

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
        with self.sessions() as session:
            has_results = (
                session.scalar(select(RunRow.id).where(RunRow.status == "COMPLETED").limit(1))
                is not None
            )
        return {
            "app_version": version("beanfeature-lab"),
            "api_version": "v1",
            "python_version": platform.python_version(),
            "platform": f"{sys.platform}-{platform.machine()}",
            "git_commit": git_commit,
            "database": self.database_state(),
            "worker": self.worker_status(),
            "scientific_results": "CALCULATED" if has_results else "NOT_CALCULATED",
        }

    def provenance(self) -> dict[str, object]:
        """Capture a content fingerprint even when research code is not committed."""
        root = Path.cwd()
        digest = sha256()
        for base in (
            "packages/research",
            "packages/application",
            "packages/infrastructure",
            "apps/worker",
            "configs/experiments",
        ):
            for path in sorted((root / base).rglob("*.py")):
                if "__pycache__" in path.parts:
                    continue
                digest.update(str(path.relative_to(root)).encode())
                digest.update(path.read_bytes())
        digest.update((root / "pyproject.toml").read_bytes())
        try:
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=2, check=True
            ).stdout.strip()
            dirty = bool(
                subprocess.run(
                    ["git", "status", "--porcelain"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=True,
                ).stdout.strip()
            )
        except (OSError, subprocess.SubprocessError):
            commit, dirty = None, True
        libraries = ("numpy", "pandas", "scipy", "scikit-learn", "xgboost", "lightgbm")
        return {
            "git_commit": commit,
            "git_dirty": dirty,
            "source_tree_sha256": digest.hexdigest(),
            "python_version": platform.python_version(),
            "platform": f"{sys.platform}-{platform.machine()}",
            "package_versions": {name: version(name) for name in libraries},
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
