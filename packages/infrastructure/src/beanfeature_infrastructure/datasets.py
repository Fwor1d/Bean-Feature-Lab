"""Official UCI 602 acquisition; no third-party mirrors or learned preprocessing."""

import json
import os
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.request import urlopen
from zipfile import BadZipFile, ZipFile

from beanfeature_research.dataset import (
    CLASSES,
    FEATURE_COLUMNS,
    SOURCE_SCHEMA_NOTICE,
    ValidatedDataset,
    validate_arff,
)

UCI_URL = "https://archive.ics.uci.edu/static/public/602/dry%2Bbean%2Bdataset.zip"
ARFF_MEMBER = "DryBeanDataset/Dry_Bean_Dataset.arff"
MAX_ARCHIVE_BYTES = 20_000_000
MAX_ARFF_BYTES = 10_000_000
EXPECTED_ARCHIVE_SHA256 = "0a64eff5be87f48c3dbbfc0a12a56c5d5b5167ef8e61cd45d69b3e7c7130c06f"
EXPECTED_ARFF_SHA256 = "b2a4a76a2aedfb8ed415adfc1bfc70b5f202cb00cb72e500766e364c14834014"


def _hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, prefix=".beanfeature-", delete=False) as handle:
        temp = Path(handle.name)
        try:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    os.replace(temp, path)


class UCIDatasetStore:
    def __init__(self, root: Path = Path("data")) -> None:
        self.raw = root / "raw"
        self.processed = root / "processed"
        self.archive = self.raw / "uci-dry-bean-602.zip"
        self.arff = self.raw / "uci-dry-bean-602.arff"
        self.manifest_path = self.processed / "uci-dry-bean-602-manifest.json"

    def download(self) -> None:
        if self.archive.exists():
            return
        self.raw.mkdir(parents=True, exist_ok=True)
        with urlopen(UCI_URL, timeout=60) as response:
            if response.geturl().split("/")[2] != "archive.ics.uci.edu":
                raise ValueError("Official UCI download redirected to another host")
            payload = response.read(MAX_ARCHIVE_BYTES + 1)
        if len(payload) > MAX_ARCHIVE_BYTES:
            raise ValueError("UCI archive exceeds size limit")
        _atomic_bytes(self.archive, payload)

    def validate(self, *, accept_official_schema: bool = False) -> dict[str, object]:
        if not self.archive.exists():
            raise FileNotFoundError("Official UCI archive absent; run 'beanfeature dataset fetch'")
        if self.archive.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ValueError("UCI archive exceeds size limit")
        archive_hash = _hash(self.archive)
        if archive_hash != EXPECTED_ARCHIVE_SHA256:
            raise ValueError(f"Official UCI archive checksum changed: {archive_hash}")
        try:
            with ZipFile(self.archive) as archive:
                members = [name for name in archive.namelist() if name == ARFF_MEMBER]
                if len(members) != 1 or archive.getinfo(ARFF_MEMBER).file_size > MAX_ARFF_BYTES:
                    raise ValueError("Official archive has no single bounded Dry Bean ARFF")
                payload = archive.read(ARFF_MEMBER)
        except BadZipFile as exc:
            raise ValueError("Invalid UCI ZIP archive") from exc
        validated = validate_arff(payload, accept_official_schema=accept_official_schema)
        if validated.arff_sha256 != EXPECTED_ARFF_SHA256:
            raise ValueError(f"Official UCI ARFF checksum changed: {validated.arff_sha256}")
        if self.arff.exists() and _hash(self.arff) != validated.arff_sha256:
            raise ValueError("Existing raw ARFF hash differs from official archive")
        if not self.arff.exists():
            _atomic_bytes(self.arff, payload)
        previous = json.loads(self.manifest_path.read_text()) if self.manifest_path.exists() else {}
        acquired_at = (
            previous.get("retrieved_at_utc")
            if previous.get("archive_sha256") == archive_hash
            else None
        )
        manifest: dict[str, object] = {
            "source": "UCI Machine Learning Repository — Dry Bean Dataset",
            "source_id": 602,
            "source_url": UCI_URL,
            "retrieved_at_utc": acquired_at or datetime.now(UTC).isoformat(),
            "archive_sha256": archive_hash,
            "arff_sha256": validated.arff_sha256,
            "dataset_version": f"uci-602-{validated.arff_sha256[:12]}",
            "rows": len(validated.target),
            "feature_count": len(FEATURE_COLUMNS),
            "features": list(FEATURE_COLUMNS),
            "target": "Class",
            "classes": list(CLASSES),
            "missing_values": 0,
            "schema_notice": SOURCE_SCHEMA_NOTICE,
            "official_schema_acknowledged": True,
        }
        _atomic_bytes(
            self.manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2).encode()
        )
        return manifest

    def load(self) -> tuple[ValidatedDataset, dict[str, object]]:
        if not self.manifest_path.exists() or not self.arff.exists() or not self.archive.exists():
            raise FileNotFoundError(
                "Validated UCI 602 manifest/ARFF absent; fetch and validate first"
            )
        manifest = json.loads(self.manifest_path.read_text())
        if manifest.get("source_id") != 602 or not manifest.get("official_schema_acknowledged"):
            raise ValueError("Unapproved dataset manifest")
        if _hash(self.archive) != manifest.get("archive_sha256"):
            raise ValueError("UCI archive hash changed after validation")
        payload = self.arff.read_bytes()
        if sha256(payload).hexdigest() != manifest.get("arff_sha256"):
            raise ValueError("Raw ARFF hash changed after validation")
        dataset = validate_arff(payload, accept_official_schema=True)
        if manifest.get("dataset_version") != f"uci-602-{dataset.arff_sha256[:12]}":
            raise ValueError("Dataset version does not match ARFF")
        return dataset, manifest
