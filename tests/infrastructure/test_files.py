import pytest

from beanfeature_infrastructure.files import ArtifactStore


def test_artifact_path_cannot_escape_root(tmp_path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    assert store.resolve("runs/run-1.json").is_relative_to(tmp_path)
    with pytest.raises(ValueError):
        store.resolve("../../outside.txt")
