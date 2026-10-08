"""Portability fixtures are test-only records, never generated scientific measurements."""

import json
import sqlite3
import tarfile
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError
from typer.testing import CliRunner

from beanfeature_application.contracts import ExperimentConfig
from beanfeature_application.runtime import RuntimeStateService
from beanfeature_cli.main import app
from beanfeature_infrastructure import runtime
from beanfeature_infrastructure.bootstrap import create_container
from beanfeature_infrastructure.database import Base, RunRow
from beanfeature_infrastructure.datasets import UCIDatasetStore
from beanfeature_infrastructure.deployment import LocalDeploymentModelStore
from beanfeature_infrastructure.files import ArtifactStore
from beanfeature_research.contracts import ModelId, SelectorId
from beanfeature_research.engine import SMOKE_PROTOCOL_VERSION


@pytest.fixture
def source(tmp_path, monkeypatch):
    root = tmp_path / "source"
    (root / runtime.DATABASE_PATH).parent.mkdir(parents=True)
    for relative, content in (
        ("data/raw/uci-dry-bean-602.zip", b"test-only archive"),
        ("data/raw/uci-dry-bean-602.arff", b"test-only ARFF"),
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    arff_hash = runtime._hash(root / "data/raw/uci-dry-bean-602.arff")
    manifest = {
        "source_id": 602,
        "dataset_version": "test-only-version",
        "archive_sha256": runtime._hash(root / "data/raw/uci-dry-bean-602.zip"),
        "arff_sha256": arff_hash,
        "rows": 3,
        "feature_count": 16,
        "features": [f"fixture_{i}" for i in range(16)],
        "classes": ["TEST_ONLY"],
        "retrieved_at_utc": "2020-01-01T00:00:00+00:00",
    }
    path = root / "data/processed/uci-dry-bean-602-manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(manifest))

    # Only acquisition is substituted. The real run verifier, DB, hashes and archives are exercised.
    def load(store):
        stored = json.loads(store.manifest_path.read_bytes())
        assert runtime._hash(store.archive) == stored["archive_sha256"]
        assert runtime._hash(store.arff) == stored["arff_sha256"]
        return SimpleNamespace(
            arff_sha256=stored["arff_sha256"], target=range(3), feature_names=stored["features"]
        ), stored

    monkeypatch.setattr(UCIDatasetStore, "load", load)
    container = create_container(f"sqlite:///{root / runtime.DATABASE_PATH}", runtime_root=root)
    Base.metadata.create_all(container.metadata.engine)
    with container.metadata.engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY)")
        connection.exec_driver_sql(
            "INSERT INTO alembic_version VALUES (?)", (runtime._schema_revision(),)
        )
    service = container.service
    service.datasets.register(manifest)
    config = ExperimentConfig(
        ModelId.LOGISTIC_REGRESSION,
        SelectorId.NONE,
        "original_features",
        k_original_features=16,
        dataset_version=manifest["dataset_version"],
        evaluation_mode="smoke",
    )
    experiment = service.experiments.create("Test-only portability fixture", config)
    run = service.runs.create(experiment.id)
    provenance = {"git_commit": "test-only-source", "package_versions": {"test-library": "0"}}
    fingerprint = sha256(
        json.dumps(
            {
                "configuration": asdict(config),
                "dataset_hash": arff_hash,
                "provenance": provenance,
            },
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()
    folds = [
        {"fold_id": f"r01-f{i:02d}", "split_sha256": str(i) * 64, "macro_f1": 0.5, "accuracy": 0.5}
        for i in (1, 2)
    ]
    summary = {
        "cv_protocol_version": SMOKE_PROTOCOL_VERSION,
        "outer_split_set_sha256": sha256(
            "".join(f["split_sha256"] for f in folds).encode()
        ).hexdigest(),
    }
    payload = {
        "run_id": run.display_id,
        "experiment_id": experiment.id,
        "configuration": asdict(config),
        "dataset_manifest": manifest,
        "provenance": provenance,
        "fingerprint": fingerprint,
        "folds": folds,
        "summary": summary,
        "splits": [{"fold_id": f["fold_id"]} for f in folds],
    }
    store = ArtifactStore(root / "artifacts/runs")
    digest = store.write_json(f"{run.display_id}/result.json", payload)
    for fold in folds:
        store.write_json(f"{run.display_id}/fold-{fold['fold_id']}.json", fold)
    with container.service.runs.sessions.begin() as session:
        row = session.get(RunRow, run.id)
        row.status = "COMPLETED"
        row.result_artifact = f"{run.display_id}/result.json"
        row.result_sha256, row.dataset_hash, row.fingerprint = digest, arff_hash, fingerprint
        row.summary = summary
    failed = service.runs.create(experiment.id)
    with service.runs.sessions.begin() as session:
        session.get(RunRow, failed.id).status = "RUNNING"
    service.runs.fail(failed.id, "Test-only interruption")
    store.write_json(f"{failed.display_id}/fold-r01-f01.json", folds[0])
    store.write_json("analysis/core-sufficiency-test-only.json", {"status": "NOT_CALCULATED"})
    (root / "data/raw/secret.env").write_text("excluded-test-only-value")
    container.metadata.engine.dispose()
    return root


def _backup(source, tmp_path):
    archive = tmp_path / "state.tar.gz"
    RuntimeStateService(runtime.LocalRuntimeStateStore()).backup(archive, source)
    return archive


def _rewrite(archive, transform):
    with tarfile.open(archive, "r:gz") as packed:
        entries = [(member, packed.extractfile(member).read()) for member in packed]
    entries = transform(entries)
    with tarfile.open(archive, "w:gz", format=tarfile.USTAR_FORMAT) as packed:
        for member, content in entries:
            member.size = len(content)
            packed.addfile(member, BytesIO(content))


def _change_manifest(archive, change):
    def transform(entries):
        manifest = json.loads(
            next(content for member, content in entries if member.name == "manifest.json")
        )
        change(manifest)
        raw = runtime._json_bytes(manifest)
        return [
            (
                member,
                raw
                if member.name == "manifest.json"
                else (sha256(raw).hexdigest() + "\n").encode()
                if member.name == "manifest.sha256"
                else content,
            )
            for member, content in entries
        ]

    _rewrite(archive, transform)


def test_real_verifier_round_trip_and_unchanged_source(source, tmp_path):
    before = {
        str(p.relative_to(source)): runtime._hash(p) for p in source.rglob("*") if p.is_file()
    }
    archive = _backup(source, tmp_path)
    port = runtime.LocalRuntimeStateStore()
    inspected = port.inspect(archive)
    assert inspected["manifest_verified"] and not inspected["payload_verified"]
    manifest = inspected["manifest"]
    assert "sha256" not in manifest
    assert manifest["optional_groups"]["models"]["status"] == "absent"
    assert manifest["optional_groups"]["partial_runs"]["file_count"] == 1
    assert "data/raw/secret.env" in manifest["excluded"]["runtime_paths"]
    verified = port.verify(archive)
    assert verified["state"]["completed_runs_verified"] == 1
    assert verified["state"]["database"]["run_counts"] == {"COMPLETED": 1, "FAILED": 1}
    target = tmp_path / "restored"
    restored = port.restore(archive, target)
    assert restored["state"] == verified["state"]
    for entry in manifest["files"]:
        assert runtime._hash(target / entry["path"]) == entry["sha256"]
    assert not (target / "data/raw/secret.env").exists()
    assert before == {
        str(p.relative_to(source)): runtime._hash(p) for p in source.rglob("*") if p.is_file()
    }
    assert not (target / ".restore-in-progress").exists()


def test_models_verified_without_deserialization(source, tmp_path, monkeypatch):
    store = LocalDeploymentModelStore(source / "artifacts/models")
    metadata = store.save(
        {"test-only": True},
        {
            "model_id": "lr-uci-602-full16-v1",
            "deployment_model": True,
            "dataset_sha256": runtime._hash(source / "data/raw/uci-dry-bean-602.arff"),
            "source_run": "RUN-000001",
        },
    )
    digest = store.artifacts.write_json(
        "benchmarks/lr-uci-602-full16-v1-20200101T000000Z.json",
        {
            "model_id": metadata["model_id"],
            "status": "CALCULATED",
        },
    )
    store.artifacts.write_json(
        "benchmarks/latest.json",
        {
            "artifact_relative_path": "benchmarks/lr-uci-602-full16-v1-20200101T000000Z.json",
            "artifact_sha256": digest,
        },
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Portability must never deserialize a model")

    monkeypatch.setattr("beanfeature_infrastructure.deployment.joblib.load", forbidden)
    archive = _backup(source, tmp_path)
    assert (
        runtime.LocalRuntimeStateStore().verify(archive)["state"]["active_deployment_model"]
        == metadata["model_id"]
    )


@pytest.mark.parametrize(
    "case", ["payload", "manifest", "missing", "extra", "duplicate", "symlink", "traversal"]
)
def test_invalid_archive_refused_before_target_creation(source, tmp_path, case):
    archive = _backup(source, tmp_path)

    def transform(entries):
        if case == "payload":
            return [(m, b"x" * len(c) if m.name.endswith(".arff") else c) for m, c in entries]
        if case == "manifest":
            return [(m, c + b" " if m.name == "manifest.json" else c) for m, c in entries]
        if case == "missing":
            return [(m, c) for m, c in entries if not m.name.endswith(".arff")]
        if case == "duplicate":
            return entries + [entries[0]]
        member = tarfile.TarInfo("../escape" if case == "traversal" else "unlisted.txt")
        if case == "symlink":
            member.type, member.linkname = tarfile.SYMTYPE, "/outside"
        return entries + [(member, b"")]

    _rewrite(archive, transform)
    with pytest.raises(ValueError):
        runtime.LocalRuntimeStateStore().restore(archive, tmp_path / "target")
    assert not (tmp_path / "target").exists()
    assert not list(tmp_path.glob(".beanfeature-restore-*"))


@pytest.mark.parametrize(
    "change",
    [
        lambda m: m.update(format_version=2),
        lambda m: m["state"].update(completed_runs_verified=999),
        lambda m: m["files"][0].update(role="optional"),
    ],
)
def test_invalid_format_or_manifest_state(source, tmp_path, change):
    archive = _backup(source, tmp_path)
    _change_manifest(archive, change)
    with pytest.raises(ValueError):
        runtime.LocalRuntimeStateStore().verify(archive)


def test_different_exporter_provenance_is_compatible(source, tmp_path):
    archive = _backup(source, tmp_path)
    _change_manifest(
        archive,
        lambda m: m.update(
            exporter_provenance={
                "git_commit": "different-checkout",
                "python_version": "different",
                "package_versions": {},
            }
        ),
    )
    assert runtime.LocalRuntimeStateStore().verify(archive)["verified"]


@pytest.mark.parametrize("status", ["QUEUED", "RUNNING"])
def test_active_runs_refuse_backup(source, tmp_path, status):
    with sqlite3.connect(source / runtime.DATABASE_PATH) as connection:
        connection.execute("UPDATE runs SET status=? WHERE id=2", (status,))
    with pytest.raises(ValueError, match="drain the queue"):
        _backup(source, tmp_path)
    assert not (tmp_path / "state.tar.gz").exists()


def test_fresh_worker_refuses_backup(source, tmp_path):
    with sqlite3.connect(source / runtime.DATABASE_PATH) as connection:
        connection.execute(
            "INSERT INTO worker_heartbeat VALUES (1,?)", (datetime.now(UTC).isoformat(),)
        )
    with pytest.raises(ValueError, match="heartbeat is fresh"):
        _backup(source, tmp_path)


def test_incompatible_db_schema_refuses_backup(source, tmp_path):
    with sqlite3.connect(source / runtime.DATABASE_PATH) as connection:
        connection.execute("UPDATE alembic_version SET version_num='future-schema'")
    with pytest.raises(ValueError, match="Unsupported runtime SQLite schema"):
        _backup(source, tmp_path)


def test_wal_snapshot_includes_committed_metadata(source, tmp_path):
    connection = sqlite3.connect(source / runtime.DATABASE_PATH)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("UPDATE experiments SET name='Committed in WAL'")
        connection.commit()
        archive = _backup(source, tmp_path)
        target = tmp_path / "restored"
        runtime.LocalRuntimeStateStore().restore(archive, target)
        with sqlite3.connect(target / runtime.DATABASE_PATH) as restored:
            assert restored.execute("SELECT name FROM experiments").fetchone() == (
                "Committed in WAL",
            )
    finally:
        connection.close()


def test_source_change_discards_backup(source, tmp_path, monkeypatch):
    write = runtime._write_archive

    def mutate(*args):
        write(*args)
        (source / "artifacts/runs/RUN-000002/fold-r01-f01.json").write_text("changed")

    monkeypatch.setattr(runtime, "_write_archive", mutate)
    with pytest.raises(ValueError, match="changed during backup"):
        _backup(source, tmp_path)
    assert not (tmp_path / "state.tar.gz").exists()
    assert not list(tmp_path.glob(".beanfeature-backup-*"))


def test_overwrite_and_concurrent_publication_protection(source, tmp_path, monkeypatch):
    archive = _backup(source, tmp_path)
    before = archive.read_bytes()
    service = RuntimeStateService(runtime.LocalRuntimeStateStore())
    with pytest.raises(FileExistsError):
        service.backup(archive, source)
    assert archive.read_bytes() == before
    target = tmp_path / "target"
    target.mkdir()
    sentinel = target / "existing"
    sentinel.write_text("keep")
    with pytest.raises(FileExistsError):
        service.restore(archive, target)
    assert sentinel.read_text() == "keep"
    target2 = tmp_path / "racing-target"
    check = runtime._check_manifest_state

    def racing(*args):
        result = check(*args)
        target2.mkdir()
        (target2 / "existing").write_text("keep")
        return result

    monkeypatch.setattr(runtime, "_check_manifest_state", racing)
    with pytest.raises(FileExistsError):
        service.restore(archive, target2)
    assert (target2 / "existing").read_text() == "keep"


def test_restore_publication_failure_cleans_only_new_target(source, tmp_path, monkeypatch):
    archive = _backup(source, tmp_path)
    target = tmp_path / "target"
    move = runtime.shutil.move

    def fail(src, dst):
        if Path(src).name == "artifacts":
            raise OSError("test-only publication failure")
        return move(src, dst)

    monkeypatch.setattr(runtime.shutil, "move", fail)
    with pytest.raises(OSError, match="publication failure"):
        runtime.LocalRuntimeStateStore().restore(archive, target)
    assert not target.exists()


def test_existing_default_paths_and_isolated_di(tmp_path):
    normal = create_container(f"sqlite:///{tmp_path / 'normal.db'}")
    isolated = create_container(f"sqlite:///{tmp_path / 'isolated.db'}", runtime_root=tmp_path)
    try:
        assert normal.service.dataset_store.raw == Path("data/raw")
        assert normal.service.artifacts.root == Path("artifacts/runs").resolve()
        assert normal.service.deployment_models.artifacts.root == Path("artifacts/models").resolve()
        assert isolated.service.dataset_store.raw == tmp_path / "data/raw"
        assert isolated.service.artifacts.root == tmp_path / "artifacts/runs"
    finally:
        normal.metadata.engine.dispose()
        isolated.metadata.engine.dispose()


def test_cli_round_trip_and_error_exit(source, tmp_path):
    runner = CliRunner()
    archive = tmp_path / "cli.tar.gz"
    assert (
        runner.invoke(
            app, ["runtime", "backup", "--source-root", str(source), "--output", str(archive)]
        ).exit_code
        == 0
    )
    assert json.loads(runner.invoke(app, ["runtime", "inspect", str(archive)]).stdout)[
        "manifest_verified"
    ]
    assert json.loads(runner.invoke(app, ["runtime", "verify", str(archive)]).stdout)["verified"]
    target = tmp_path / "cli-restored"
    assert (
        runner.invoke(
            app, ["runtime", "restore", str(archive), "--target-root", str(target)]
        ).exit_code
        == 0
    )
    failure = runner.invoke(app, ["runtime", "restore", str(archive), "--target-root", str(target)])
    assert failure.exit_code == 1
    assert "already exists" in failure.stderr


@pytest.mark.parametrize(
    "relative",
    [
        "data/raw/uci-dry-bean-602.arff",
        "artifacts/runs/RUN-000001/fold-r01-f01.json",
    ],
)
def test_missing_required_source_content(source, tmp_path, relative):
    (source / relative).unlink()
    with pytest.raises(ValueError, match="[Mm]issing"):
        _backup(source, tmp_path)
    assert not (tmp_path / "state.tar.gz").exists()


def test_changed_scientific_artifact_refuses_backup(source, tmp_path):
    (source / "artifacts/runs/RUN-000001/result.json").write_text("{}")
    with pytest.raises(ValueError, match="failed verification"):
        _backup(source, tmp_path)


def test_unsupported_scientific_protocol_refuses_backup(source, tmp_path):
    path = source / "artifacts/runs/RUN-000001/result.json"
    payload = json.loads(path.read_bytes())
    payload["summary"]["cv_protocol_version"] = "future-protocol"
    digest = ArtifactStore(source / "artifacts/runs").write_json("RUN-000001/result.json", payload)
    with sqlite3.connect(source / runtime.DATABASE_PATH) as connection:
        connection.execute(
            "UPDATE runs SET result_sha256=?,summary=? WHERE id=1",
            (
                digest,
                json.dumps(payload["summary"]),
            ),
        )
    with pytest.raises(ValueError, match="protocol version"):
        _backup(source, tmp_path)


def test_runtime_directory_symlink_refused(source, tmp_path):
    (source / "data").rename(tmp_path / "real-data")
    (source / "data").symlink_to(tmp_path / "real-data", target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        _backup(source, tmp_path)


def test_missing_source_db_never_created(tmp_path):
    with pytest.raises(ValueError, match="existing regular file"):
        runtime.LocalRuntimeStateStore().backup(tmp_path / "state.tar.gz", tmp_path / "absent")
    assert not (tmp_path / "absent").exists()


def test_environment_db_override_is_snapshotted_to_conventional_path(source, tmp_path, monkeypatch):
    database = source / runtime.DATABASE_PATH
    external = tmp_path / "custom.sqlite"
    database.rename(external)
    (source / "pyproject.toml").write_text("[project]\nname = 'test-only-checkout'\n")
    monkeypatch.chdir(source)
    monkeypatch.setenv("BEANFEATURE_DATABASE_URL", f"sqlite:///{external}")
    archive = tmp_path / "external.tar.gz"
    RuntimeStateService(runtime.LocalRuntimeStateStore()).backup(archive)
    assert runtime.LocalRuntimeStateStore().verify(archive)["verified"]
    assert not database.exists()
    with pytest.raises(ValueError, match="journal companions"):
        RuntimeStateService(runtime.LocalRuntimeStateStore()).backup(Path(str(external) + "-wal"))


def test_concurrent_backup_output_creator_preserved(source, tmp_path, monkeypatch):
    write = runtime._write_archive
    output = tmp_path / "state.tar.gz"

    def race(*args):
        write(*args)
        output.write_bytes(b"concurrently-created-file")

    monkeypatch.setattr(runtime, "_write_archive", race)
    with pytest.raises(FileExistsError):
        _backup(source, tmp_path)
    assert output.read_bytes() == b"concurrently-created-file"


def test_read_only_verification_connection_rejects_writes(source):
    url = "sqlite:///" + (source / runtime.DATABASE_PATH).as_uri() + "?mode=ro&uri=true"
    container = create_container(url, runtime_root=source)
    try:
        with pytest.raises(OperationalError, match="readonly"):
            with container.metadata.engine.begin() as connection:
                connection.exec_driver_sql("DELETE FROM runs")
    finally:
        container.metadata.engine.dispose()
