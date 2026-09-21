import json
import os
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile


class ArtifactStore:
    """Atomic, hash-verified JSON artifacts constrained to a fixed root."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def resolve(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Artifact path must stay inside artifact root")
        return path

    def write_json(self, relative_path: str, payload: object) -> str:
        destination = self.resolve(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode()
        digest = sha256(content).hexdigest()
        with NamedTemporaryFile(
            dir=destination.parent, prefix=".beanfeature-", delete=False
        ) as handle:
            temporary = Path(handle.name)
            try:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        os.replace(temporary, destination)
        return digest

    def read_json(self, relative_path: str, expected_sha256: str) -> object:
        content = self.resolve(relative_path).read_bytes()
        if sha256(content).hexdigest() != expected_sha256:
            raise ValueError("Scientific artifact hash mismatch")
        return json.loads(content)
