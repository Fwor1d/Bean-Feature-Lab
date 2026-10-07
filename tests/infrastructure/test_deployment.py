import json

import pytest

from beanfeature_infrastructure.deployment import LocalDeploymentModelStore


def test_versioned_deployment_registry_roundtrip(tmp_path) -> None:
    store = LocalDeploymentModelStore(tmp_path)
    metadata = store.save(
        {"pipeline": "test-only"},
        {
            "model_id": "test-model-v1",
            "model_version": "1.0.0",
            "deployment_model": True,
            "source_run": "RUN-000001",
        },
    )
    assert metadata["active"] is True
    assert metadata["deployment_status"] == "ACTIVE"
    assert metadata["artifact_sha256"] == metadata["model_sha256"]
    pipeline, loaded = store.load()
    assert pipeline == {"pipeline": "test-only"}
    assert loaded == metadata
    registry = json.loads((tmp_path / "registry.json").read_text())
    assert registry["active_model_id"] == "test-model-v1"
    assert list(registry["models"]) == ["test-model-v1"]


def test_deployment_registry_rejects_unsafe_id_and_tampering(tmp_path) -> None:
    store = LocalDeploymentModelStore(tmp_path)
    with pytest.raises(ValueError, match="safe stable identifier"):
        store.save({}, {"model_id": "../escape", "deployment_model": True})
    store.save({}, {"model_id": "safe-model-v1", "deployment_model": True})
    (tmp_path / "safe-model-v1.joblib").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum mismatch"):
        store.load()
