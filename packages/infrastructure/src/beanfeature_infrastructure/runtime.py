"""Versioned, read-only source snapshots of the existing local runtime layout."""

import gzip
import json
import os
import re
import shutil
import sqlite3
import tarfile
from collections import Counter
from contextlib import closing
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

from .bootstrap import create_container
from .database import Base, database_url
from .datasets import UCIDatasetStore
from .deployment import LocalDeploymentModelStore

DATABASE_PATH = "storage/sqlite/beanfeature.sqlite"
DATA_FILES = {
    "data/raw/uci-dry-bean-602.zip",
    "data/raw/uci-dry-bean-602.arff",
    "data/processed/uci-dry-bean-602-manifest.json",
}
FORMAT_VERSION = 1
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_PAYLOAD_BYTES = 16 * 1024**3
MAX_FILES = 100_000
OPTIONAL_GROUPS = ("partial_runs", "analysis", "models", "benchmarks")
EXCLUDED_CATEGORIES = [
    "Git and source checkout (obtain a compatible checkout separately)",
    "secrets, environment files and Cloudflare configuration",
    "dependencies, build output, caches, logs and temporary files",
    "SQLite journal/WAL/SHM companions (represented by the consistent DB snapshot)",
    "README scaffolding and unrecognized runtime files",
]


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or ":" in value
        or "\x00" in value
        or path.is_absolute()
        or ".." in path.parts
        or str(path) != value
    ):
        raise ValueError(f"Unsafe relative backup path: {value!r}")
    return value


def _file_group(path: str) -> str | None:
    if path == DATABASE_PATH:
        return "database"
    if path in DATA_FILES:
        return "dataset"
    if re.fullmatch(r"artifacts/runs/RUN-\d{6,}/(result|error|fold-r\d+-f\d+)\.json", path):
        return "runs"
    if re.fullmatch(r"artifacts/runs/RUN-\d{6,}/paired-vs-RUN-\d{6,}\.json", path):
        return "analysis"
    if re.fullmatch(r"artifacts/runs/analysis/core-sufficiency-[a-z0-9_-]+\.json", path):
        return "analysis"
    if path == "artifacts/models/registry.json":
        return "models"
    if re.fullmatch(r"artifacts/models/lr-uci-602-full16(?:-v\d+)?\.(json|joblib)", path):
        return "models"
    if re.fullmatch(
        r"artifacts/models/benchmarks/(latest|lr-uci-602-full16(?:-v\d+)?-\d{8}T\d{6}Z)\.json",
        path,
    ):
        return "benchmarks"
    return None


def _readonly_connection(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)


def _schema_revision() -> str:
    scripts = Path(__file__).resolve().parents[2] / "alembic"
    return ScriptDirectory(str(scripts)).get_current_head()


def _database_state(path: Path, *, quiescent: bool = False) -> dict[str, object]:
    with closing(_readonly_connection(path)) as connection:
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("SQLite integrity check failed")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("SQLite foreign key check failed")
        tables = [
            name
            for (name,) in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        if not set(Base.metadata.tables).union({"alembic_version"}).issubset(tables):
            raise ValueError("Runtime SQLite schema is incomplete")
        revisions = connection.execute("SELECT version_num FROM alembic_version").fetchall()
        if revisions != [(_schema_revision(),)]:
            raise ValueError(f"Unsupported runtime SQLite schema revision: {revisions}")
        for name, table in Base.metadata.tables.items():
            columns = {row[1] for row in connection.execute(f'PRAGMA table_info("{name}")')}
            if not set(table.columns.keys()).issubset(columns):
                raise ValueError(f"Runtime SQLite table has incompatible columns: {name}")
        rows = {}
        for name in tables:
            quoted = name.replace('"', '""')
            rows[name] = connection.execute(f'SELECT * FROM "{quoted}" ORDER BY 1').fetchall()
        connection.row_factory = sqlite3.Row
        runs = [dict(row) for row in connection.execute("SELECT * FROM runs ORDER BY id")]
        datasets = [
            dict(row) for row in connection.execute("SELECT * FROM dataset_versions ORDER BY id")
        ]
        if quiescent:
            if any(run["status"] in {"QUEUED", "RUNNING", "CANCELLING"} for run in runs):
                raise ValueError("Stop scientific writers and drain the queue before backup")
            for row in connection.execute("SELECT seen_at FROM worker_heartbeat"):
                timestamp = datetime.fromisoformat(row[0]).replace(tzinfo=UTC)
                if (datetime.now(UTC) - timestamp).total_seconds() < 20:
                    raise ValueError("Worker heartbeat is fresh; stop the worker before backup")
        return {
            "schema_revision": revisions[0][0],
            "table_counts": {name: len(values) for name, values in rows.items()},
            "logical_sha256": sha256(_json_bytes(rows)).hexdigest(),
            "run_counts": dict(sorted(Counter(run["status"] for run in runs).items())),
            "run_identities": [
                {
                    key: run[key]
                    for key in (
                        "id",
                        "experiment_id",
                        "status",
                        "result_artifact",
                        "result_sha256",
                        "dataset_hash",
                        "fingerprint",
                        "error_detail_artifact",
                    )
                }
                for run in runs
            ],
            "datasets": datasets,
        }


def _inventory(root: Path) -> tuple[list[dict[str, object]], list[str]]:
    included, excluded = [], []
    for base in ("data/raw", "data/processed", "artifacts/runs", "artifacts/models"):
        directory = root / base
        if any(path.is_symlink() for path in (directory, directory.parent)):
            raise ValueError(f"Runtime directory must not be a symlink: {base}")
        for path in sorted(directory.rglob("*")):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                raise ValueError(f"Runtime symlink cannot be backed up: {relative}")
            if path.is_dir():
                continue
            if not path.is_file():
                raise ValueError(f"Runtime special file cannot be backed up: {relative}")
            group = _file_group(relative)
            if group is None:
                excluded.append(relative)
            else:
                included.append(
                    {
                        "path": relative,
                        "size_bytes": path.stat().st_size,
                        "sha256": _hash(path),
                        "group": group,
                    }
                )
    return included, excluded


def _source_database(root: Path, explicit_root: bool) -> Path:
    if explicit_root:
        path = root / DATABASE_PATH
    else:
        url = make_url(database_url())
        if url.get_backend_name() != "sqlite" or not url.database or url.query:
            raise ValueError("Backup supports a local file SQLite URL without URI options")
        if url.database == ":memory:":
            raise ValueError("In-memory SQLite cannot be backed up as local runtime")
        path = Path(url.database)
        if not path.is_absolute():
            path = root / path
    if path.is_symlink() or not path.is_file():
        raise ValueError("Source SQLite must be an existing regular file")
    return path.resolve()


def _database_file_hashes(path: Path) -> dict[str, str]:
    return {
        suffix: _hash(candidate)
        for suffix in ("", "-wal", "-shm", "-journal")
        if (candidate := Path(str(path) + suffix)).is_file()
    }


def _verify_state(root: Path) -> dict[str, object]:
    """Reuse scientific reads; never train, recover runs, validate/write or deserialize."""
    state = _database_state(root / DATABASE_PATH)
    dataset, manifest = UCIDatasetStore(root / "data").load()
    for record in state["datasets"]:
        if record["manifest_path"] != "data/processed/uci-dry-bean-602-manifest.json":
            raise ValueError("Unsupported dataset manifest reference")
        expected = {
            "source_id": manifest["source_id"],
            "version": manifest["dataset_version"],
            "archive_sha256": manifest["archive_sha256"],
            "arff_sha256": dataset.arff_sha256,
            "rows": len(dataset.target),
            "feature_count": len(dataset.feature_names),
        }
        if any(record[key] != value for key, value in expected.items()):
            raise ValueError("Dataset DB metadata differs from validated files")
        if json.loads(record["classes"]) != manifest["classes"]:
            raise ValueError("Dataset DB class schema differs from manifest")
    if len(state["datasets"]) != 1:
        raise ValueError("Runtime portability v1 requires one validated UCI dataset version")
    url = "sqlite:///" + (root / DATABASE_PATH).as_uri() + "?mode=ro&uri=true"
    container = create_container(url, runtime_root=root)
    service = container.service
    required = set(DATA_FILES) | {DATABASE_PATH}
    protocols = set()
    verified = 0
    try:
        for run in service.list_runs():
            if run.error_detail_artifact:
                reference = _safe_path("artifacts/runs/" + run.error_detail_artifact)
                if not (root / reference).is_file():
                    raise ValueError(f"Missing error artifact: {reference}")
                required.add(reference)
            if run.status.value != "COMPLETED":
                continue
            verification = service.verify_run(run.id)
            if not verification["verified"]:
                raise ValueError(f"{run.display_id} failed verification: {verification['errors']}")
            payload = service.get_run_result(run.id)
            if (
                payload["run_id"] != run.display_id
                or payload["experiment_id"] != run.experiment_id
                or payload["summary"] != run.summary
            ):
                raise ValueError(f"{run.display_id} DB/result identity or summary differs")
            required.add(_safe_path("artifacts/runs/" + run.result_artifact))
            for fold in payload["folds"]:
                reference = _safe_path(
                    f"artifacts/runs/{run.display_id}/fold-{fold['fold_id']}.json"
                )
                if not (root / reference).is_file():
                    raise ValueError(f"Missing completed fold artifact: {reference}")
                if json.loads((root / reference).read_bytes()) != fold:
                    raise ValueError(f"Fold companion differs from result: {reference}")
                required.add(reference)
            protocols.add(payload["summary"]["cv_protocol_version"])
            verified += 1
        models = LocalDeploymentModelStore(root / "artifacts/models")
        metadata = models.metadata()
        if metadata is not None:
            models.verified_binary()
            if metadata.get("dataset_sha256") != dataset.arff_sha256:
                raise ValueError("Deployment model and validated dataset identities differ")
            source_run = metadata.get("source_run")
            if source_run:
                if not isinstance(source_run, str) or not re.fullmatch(r"RUN-\d{6,}", source_run):
                    raise ValueError("Invalid deployment source run reference")
                source = service.get_run(int(source_run[4:]))
                if source.status.value != "COMPLETED" or (
                    metadata.get("source_result_sha256")
                    and metadata["source_result_sha256"] != source.result_sha256
                ):
                    raise ValueError("Deployment source result does not match DB")
        benchmark = models.latest_benchmark()
        # Preserve and check legacy/unregistered LR artifacts as well as the active registry.
        for model_path in sorted((root / "artifacts/models").glob("*.joblib")):
            companion = model_path.with_suffix(".json")
            if not companion.is_file():
                raise ValueError(f"Missing model metadata: {model_path.name}")
            stored = json.loads(companion.read_bytes())
            expected_hash = stored.get("artifact_sha256", stored.get("model_sha256"))
            if _hash(model_path) != expected_hash:
                raise ValueError(f"Deployment model checksum mismatch: {model_path.name}")
    finally:
        container.metadata.engine.dispose()
    return {
        "database": state,
        "dataset_identity": {
            key: manifest[key]
            for key in (
                "source_id",
                "dataset_version",
                "archive_sha256",
                "arff_sha256",
                "rows",
                "feature_count",
                "features",
                "classes",
            )
        },
        "completed_runs_verified": verified,
        "protocol_versions": sorted(protocols),
        "active_deployment_model": metadata.get("model_id") if metadata else None,
        "deployment_benchmark_present": benchmark is not None,
        "required_paths": sorted(required),
    }


def _read_manifest(
    archive: tarfile.TarFile,
) -> tuple[dict[str, object], dict[str, tarfile.TarInfo]]:
    members, declared_bytes = {}, 0
    for member in archive:
        name = _safe_path(member.name)
        if (
            name in members
            or member.type not in {tarfile.REGTYPE, tarfile.AREGTYPE}
            or member.pax_headers
            or member.offset_data != member.offset + 512
        ):
            raise ValueError(f"Duplicate, nonregular or extended archive entry: {name}")
        declared_bytes += member.size
        if member.size < 0 or declared_bytes > MAX_PAYLOAD_BYTES + MAX_MANIFEST_BYTES + 65:
            raise ValueError("Backup exceeds the declared archive size limit")
        if name == "manifest.json" and member.size > MAX_MANIFEST_BYTES:
            raise ValueError("Backup manifest exceeds its size limit")
        if name == "manifest.sha256" and member.size != 65:
            raise ValueError("Backup manifest checksum is malformed")
        members[name] = member
        if len(members) > MAX_FILES + 2:
            raise ValueError("Backup archive contains too many entries")
    if not {"manifest.json", "manifest.sha256"}.issubset(members):
        raise ValueError("Backup manifest.json/manifest.sha256 is missing")
    if members["manifest.json"].size > MAX_MANIFEST_BYTES or members["manifest.sha256"].size != 65:
        raise ValueError("Backup manifest exceeds limits or its checksum is malformed")
    raw = archive.extractfile(members["manifest.json"]).read()
    checksum = archive.extractfile(members["manifest.sha256"]).read()
    if checksum != (sha256(raw).hexdigest() + "\n").encode():
        raise ValueError("Backup manifest SHA-256 mismatch")
    manifest = json.loads(raw)
    if (
        not isinstance(manifest, dict)
        or type(manifest.get("format_version")) is not int
        or manifest["format_version"] != FORMAT_VERSION
    ):
        raise ValueError("Unsupported backup format version")
    entries = manifest.get("files")
    if not isinstance(entries, list) or len(entries) > MAX_FILES:
        raise ValueError("Invalid backup inventory")
    paths, total = set(), 0
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ValueError("Invalid backup file entry")
        name = _safe_path(entry["path"])
        group = _file_group(name)
        size = entry.get("size_bytes")
        if (
            name in paths
            or group is None
            or entry.get("group") not in {group, "partial_runs"}
            or (entry.get("group") == "partial_runs" and group != "runs")
            or entry.get("role") not in {"required", "optional"}
            or type(size) is not int
            or size < 0
            or not isinstance(entry.get("sha256"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"])
        ):
            raise ValueError(f"Invalid backup inventory entry: {name}")
        paths.add(name)
        total += size
        if name not in members or members[name].size != size:
            raise ValueError(f"Missing payload or size mismatch: {name}")
    if total > MAX_PAYLOAD_BYTES:
        raise ValueError("Backup exceeds the v1 uncompressed payload limit (16 GiB)")
    if set(members) != paths | {"manifest.json", "manifest.sha256"}:
        raise ValueError("Backup contains files outside its inventory")
    if not DATA_FILES.union({DATABASE_PATH}).issubset(paths):
        raise ValueError("Backup is missing required SQLite/dataset content")
    return manifest, members


def _extract(archive_path: Path, root: Path) -> dict[str, object]:
    with tarfile.open(archive_path, "r:gz") as archive:
        manifest, members = _read_manifest(archive)
        for entry in manifest["files"]:
            destination = root / entry["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            digest, written = sha256(), 0
            with (
                archive.extractfile(members[entry["path"]]) as source,
                destination.open("xb") as out,
            ):
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    written += len(chunk)
                    if written > entry["size_bytes"]:
                        raise ValueError(f"Payload exceeds declared size: {entry['path']}")
                    digest.update(chunk)
                    out.write(chunk)
            destination.chmod(0o600)
            if written != entry["size_bytes"] or digest.hexdigest() != entry["sha256"]:
                raise ValueError(f"Payload SHA-256 mismatch: {entry['path']}")
    return manifest


def _check_manifest_state(manifest: dict[str, object], root: Path) -> dict[str, object]:
    state = _verify_state(root)
    if state != manifest.get("state"):
        raise ValueError("Backup state metadata differs from verified payload")
    required = set(state["required_paths"])
    entries = {entry["path"]: entry for entry in manifest["files"]}
    if not required.issubset(entries) or any(
        entries[path]["role"] != "required" for path in required
    ):
        raise ValueError("Backup required references are missing or marked optional")
    optional = {
        group: {
            "status": "present"
            if (count := sum(e["group"] == group for e in entries.values()))
            else "absent",
            "file_count": count,
        }
        for group in OPTIONAL_GROUPS
    }
    if manifest.get("optional_groups") != optional:
        raise ValueError("Backup optional-group metadata differs from inventory")
    return state


def _write_archive(path: Path, root: Path, manifest: dict[str, object]) -> None:
    raw = _json_bytes(manifest)
    (root / "manifest.json").write_bytes(raw)
    (root / "manifest.sha256").write_bytes((sha256(raw).hexdigest() + "\n").encode())
    names = sorted(["manifest.json", "manifest.sha256", *[e["path"] for e in manifest["files"]]])
    with (
        path.open("xb") as output,
        gzip.GzipFile(filename="", fileobj=output, mode="wb", mtime=0) as gz,
    ):
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name in names:
                info = tarfile.TarInfo(name)
                info.size = (root / name).stat().st_size
                info.mode = 0o600
                with (root / name).open("rb") as content:
                    archive.addfile(info, content)
    path.chmod(0o600)


class LocalRuntimeStateStore:
    def backup(self, output: Path, source_root: Path | None) -> dict[str, object]:
        root = (source_root or Path.cwd()).resolve()
        database = _source_database(root, source_root is not None)
        output = output.absolute()
        for base in ("data", "artifacts", "storage/sqlite"):
            if output.resolve().is_relative_to(root / base):
                raise ValueError("Backup output must be outside scientific runtime directories")
        if output.resolve() in {
            Path(str(database) + suffix) for suffix in ("", "-wal", "-shm", "-journal")
        }:
            raise ValueError("Backup output must not replace SQLite or its journal companions")
        before = _database_state(database, quiescent=True)
        db_hashes = _database_file_hashes(database)
        inventory, excluded = _inventory(root)
        if not DATA_FILES.issubset({entry["path"] for entry in inventory}):
            raise ValueError("Required source dataset files are missing")
        output.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".beanfeature-backup-", dir=output.parent) as temp:
            stage = Path(temp) / "state"
            (stage / DATABASE_PATH).parent.mkdir(parents=True)
            with (
                closing(_readonly_connection(database)) as source,
                closing(sqlite3.connect(stage / DATABASE_PATH)) as destination,
            ):
                source.backup(destination)
            for entry in inventory:
                target = stage / entry["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / entry["path"], target)
                if _hash(target) != entry["sha256"]:
                    raise ValueError("Source runtime changed while copying")
            state = _verify_state(stage)
            if state["database"] != before:
                raise ValueError("Source DB changed while snapshotting")
            entries = [dict(entry) for entry in inventory] + [
                {
                    "path": DATABASE_PATH,
                    "group": "database",
                    "size_bytes": (stage / DATABASE_PATH).stat().st_size,
                    "sha256": _hash(stage / DATABASE_PATH),
                }
            ]
            required = set(state["required_paths"])
            for entry in entries:
                entry["role"] = "required" if entry["path"] in required else "optional"
                if entry["group"] == "runs" and entry["role"] == "optional":
                    entry["group"] = "partial_runs"
            manifest = {
                "format_version": FORMAT_VERSION,
                "created_at_utc": datetime.now(UTC).isoformat(),
                "state": state,
                "files": sorted(entries, key=lambda entry: entry["path"]),
                "optional_groups": {
                    group: {
                        "status": "present"
                        if (count := sum(e["group"] == group for e in entries))
                        else "absent",
                        "file_count": count,
                    }
                    for group in OPTIONAL_GROUPS
                },
                "excluded": {"categories": EXCLUDED_CATEGORIES, "runtime_paths": excluded},
            }
            # Exporter provenance describes this checkout, never replaces historical run provenance.
            container = create_container(
                "sqlite:///" + (stage / DATABASE_PATH).as_uri() + "?mode=ro&uri=true",
                runtime_root=stage,
            )
            try:
                manifest["exporter_provenance"] = container.metadata.provenance()
            finally:
                container.metadata.engine.dispose()
            packed = Path(temp) / "backup.tar.gz"
            _write_archive(packed, stage, manifest)
            self.inspect(packed)
            if (
                _database_state(database, quiescent=True) != before
                or _database_file_hashes(database) != db_hashes
                or _inventory(root) != (inventory, excluded)
            ):
                raise ValueError("Source runtime changed during backup; no archive published")
            os.link(
                packed, output
            )  # Atomic no-clobber publication, including a concurrent creator.
        return {"archive": str(output), "archive_sha256": _hash(output), "manifest": manifest}

    def inspect(self, archive: Path) -> dict[str, object]:
        with tarfile.open(archive, "r:gz") as packed:
            manifest, _ = _read_manifest(packed)
        return {"manifest_verified": True, "payload_verified": False, "manifest": manifest}

    def verify(self, archive: Path) -> dict[str, object]:
        with TemporaryDirectory(prefix="beanfeature-verify-") as temp:
            root = Path(temp)
            manifest = _extract(archive, root)
            state = _check_manifest_state(manifest, root)
        return {
            "verified": True,
            "archive_sha256": _hash(archive),
            "payload_files_verified": len(manifest["files"]),
            "state": state,
        }

    def restore(self, archive: Path, target_root: Path) -> dict[str, object]:
        target = target_root.absolute()
        if target.exists() or target.is_symlink():
            raise FileExistsError("Restore target already exists; choose a new directory")
        if not target.parent.is_dir():
            raise ValueError("Restore target parent must already exist")
        with TemporaryDirectory(prefix=".beanfeature-restore-", dir=target.parent) as temp:
            stage = Path(temp) / "state"
            stage.mkdir()
            manifest = _extract(archive, stage)
            state = _check_manifest_state(manifest, stage)
            target.mkdir(mode=0o700)  # Exclusive reservation; never rename over an existing target.
            try:
                marker = target / ".restore-in-progress"
                marker.write_text("Incomplete restore; do not start application processes.\n")
                for directory in ("data", "artifacts", "storage"):
                    if (stage / directory).exists():
                        shutil.move(str(stage / directory), target / directory)
                marker.unlink()
            except BaseException:
                shutil.rmtree(target)
                raise
        return {
            "restored": True,
            "target_root": str(target),
            "payload_files_restored": len(manifest["files"]),
            "state": state,
        }
