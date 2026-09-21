from pathlib import Path


class ArtifactStore:
    """Safe path boundary for future files; no artifacts are written in Stage 4A."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def resolve(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Artifact path must stay inside artifact root")
        return path
