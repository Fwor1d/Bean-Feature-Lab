"""Single local, hash-checked inference artifact; separate from scientific run results."""

import json
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import joblib

from .files import ArtifactStore


class LocalDeploymentModelStore:
    MODEL = "lr-uci-602-full16.joblib"
    METADATA = "lr-uci-602-full16.json"

    def __init__(self, root: Path = Path("artifacts/models")) -> None:
        self.artifacts = ArtifactStore(root)

    def save(self, pipeline: object, metadata: dict[str, object]) -> dict[str, object]:
        binary = BytesIO()
        joblib.dump(pipeline, binary)
        digest = self.artifacts.write_binary(self.MODEL, binary.getvalue())
        result = {**metadata, "model_sha256": digest}
        self.artifacts.write_json(self.METADATA, result)
        return result

    def metadata(self) -> dict[str, object] | None:
        path = self.artifacts.resolve(self.METADATA)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("deployment_model") is not True:
            raise ValueError("Invalid deployment model metadata")
        return payload

    def load(self) -> tuple[object, dict[str, object]]:
        metadata = self.metadata()
        if metadata is None:
            raise FileNotFoundError("Deployment model has not been trained")
        digest = metadata.get("model_sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("Deployment model checksum is missing")
        binary = self.artifacts.resolve(self.MODEL).read_bytes()
        if sha256(binary).hexdigest() != digest:
            raise ValueError("Deployment model checksum mismatch")
        return joblib.load(BytesIO(binary)), metadata
