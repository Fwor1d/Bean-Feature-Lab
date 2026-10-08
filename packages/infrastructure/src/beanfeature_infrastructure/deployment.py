"""Single local, hash-checked inference artifact; separate from scientific run results."""

import json
import re
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import joblib

from .files import ArtifactStore


class LocalDeploymentModelStore:
    """Versioned local registry with exactly one explicitly active deployment model."""

    MODEL = "lr-uci-602-full16.joblib"
    METADATA = "lr-uci-602-full16.json"
    REGISTRY = "registry.json"
    BENCHMARK_INDEX = "benchmarks/latest.json"

    def __init__(self, root: Path = Path("artifacts/models")) -> None:
        self.artifacts = ArtifactStore(root)

    def save(self, pipeline: object, metadata: dict[str, object]) -> dict[str, object]:
        model_id = metadata.get("model_id")
        if not isinstance(model_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,79}", model_id):
            raise ValueError("Deployment model_id must be a safe stable identifier")
        model_path = f"{model_id}.joblib"
        metadata_path = f"{model_id}.json"
        binary = BytesIO()
        joblib.dump(pipeline, binary)
        digest = self.artifacts.write_binary(model_path, binary.getvalue())
        result = {
            **metadata,
            "artifact_sha256": digest,
            "model_sha256": digest,
            "deployment_status": "ACTIVE",
            "active": True,
        }
        metadata_digest = self.artifacts.write_json(metadata_path, result)
        registry = {
            "registry_version": 1,
            "active_model_id": model_id,
            "models": {
                model_id: {
                    "model_id": model_id,
                    "model_path": model_path,
                    "metadata_path": metadata_path,
                    "metadata_sha256": metadata_digest,
                    "deployment_status": "ACTIVE",
                }
            },
        }
        self.artifacts.write_json(self.REGISTRY, registry)
        return result

    def metadata(self) -> dict[str, object] | None:
        registry_path = self.artifacts.resolve(self.REGISTRY)
        if registry_path.exists():
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            active = registry.get("active_model_id") if isinstance(registry, dict) else None
            models = registry.get("models") if isinstance(registry, dict) else None
            record = (
                models.get(active) if isinstance(models, dict) and isinstance(active, str) else None
            )
            if not isinstance(record, dict):
                raise ValueError("Deployment registry has no valid active model")
            metadata_path = record.get("metadata_path")
            metadata_hash = record.get("metadata_sha256")
            if not isinstance(metadata_path, str) or not isinstance(metadata_hash, str):
                raise ValueError("Deployment registry record is incomplete")
            payload = self.artifacts.read_json(metadata_path, metadata_hash)
        else:
            path = self.artifacts.resolve(self.METADATA)
            if not path.exists():
                return None
            payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("deployment_model") is not True:
            raise ValueError("Invalid deployment model metadata")
        return payload

    def verified_binary(self) -> tuple[bytes, dict[str, object]]:
        """Check existing model integrity without executing a serialized pipeline."""
        metadata = self.metadata()
        if metadata is None:
            raise FileNotFoundError("Deployment model has not been trained")
        digest = metadata.get("artifact_sha256", metadata.get("model_sha256"))
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("Deployment model checksum is missing")
        registry_path = self.artifacts.resolve(self.REGISTRY)
        model_path = self.MODEL
        if registry_path.exists():
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            record = registry["models"][registry["active_model_id"]]
            model_path = record["model_path"]
        binary = self.artifacts.resolve(model_path).read_bytes()
        if sha256(binary).hexdigest() != digest:
            raise ValueError("Deployment model checksum mismatch")
        return binary, metadata

    def load(self) -> tuple[object, dict[str, object]]:
        binary, metadata = self.verified_binary()
        return joblib.load(BytesIO(binary)), metadata

    def latest_benchmark(self) -> dict[str, object] | None:
        index_path = self.artifacts.resolve(self.BENCHMARK_INDEX)
        if not index_path.exists():
            return None
        index = json.loads(index_path.read_text(encoding="utf-8"))
        if not isinstance(index, dict):
            raise ValueError("Invalid deployment benchmark index")
        relative = index.get("artifact_relative_path")
        digest = index.get("artifact_sha256")
        if not isinstance(relative, str) or not isinstance(digest, str):
            raise ValueError("Incomplete deployment benchmark index")
        payload = self.artifacts.read_json(relative, digest)
        metadata = self.metadata()
        if (
            not isinstance(payload, dict)
            or not metadata
            or payload.get("model_id") != metadata.get("model_id")
        ):
            raise ValueError("Benchmark does not belong to the active deployment model")
        return payload
