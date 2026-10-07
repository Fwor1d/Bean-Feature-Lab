def test_health_and_system_info(api_client) -> None:
    health = api_client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    info = api_client.get("/api/v1/system/info")
    assert info.status_code == 200
    assert info.json()["database"] == "connected"
    assert info.json()["scientific_results"] == "NOT_CALCULATED"
    assert "/Users/" not in str(info.json())


def test_empty_collections(api_client) -> None:
    for path in ("projects", "datasets", "experiments", "runs"):
        response = api_client.get(f"/api/v1/{path}")
        assert response.status_code == 200
        assert response.json() == []

    sufficiency = api_client.get("/api/v1/core/sufficiency")
    assert sufficiency.status_code == 200
    assert len(sufficiency.json()) == 5
    assert all(
        item["status"] == "NOT_CALCULATED_MISSING_BASELINE"
        and item["minimal_sufficient_k"] is None
        and item["comparisons"] == []
        for item in sufficiency.json()
    )
    assert api_client.get("/api/v1/features/selection-series").json() == []


def test_create_experiment_and_run_without_fake_metrics(api_client) -> None:
    experiment = api_client.post(
        "/api/v1/experiments",
        json={
            "name": "MI configuration",
            "configuration": {
                "model": "svm_rbf",
                "selector": "mutual_information",
                "budget_kind": "original_features",
                "k_original_features": 4,
            },
        },
    )
    assert experiment.status_code == 201
    experiment_id = experiment.json()["id"]
    assert api_client.get(f"/api/v1/experiments/{experiment_id}").status_code == 200
    run = api_client.post(f"/api/v1/experiments/{experiment_id}/runs")
    assert run.status_code == 201
    assert run.json()["display_id"] == "RUN-000001"
    assert run.json()["status"] == "QUEUED"
    assert run.json()["metrics"] is None
    assert run.json()["result_state"] == "NOT_CALCULATED"
    summary = api_client.get("/api/v1/runs/1/summary")
    assert summary.json()["result_state"] == "NOT_CALCULATED"
    assert summary.json()["summary"] is None
    folds = api_client.get("/api/v1/runs/1/folds")
    assert folds.status_code == 409
    assert folds.json()["error"]["code"] == "not_calculated"
    detail = api_client.get("/api/v1/runs/1/detail")
    assert detail.status_code == 409
    assert detail.json()["error"]["code"] == "not_calculated"
    verification = api_client.get("/api/v1/runs/1/verify")
    assert verification.status_code == 200
    assert verification.json()["verified"] is False
    export = api_client.get("/api/v1/runs/1/export/result.json")
    assert export.status_code == 409
    assert export.json()["error"]["code"] == "conflict"
    assert api_client.get("/api/v1/runs").json()[0]["display_id"] == "RUN-000001"
    assert api_client.post("/api/v1/runs/1/cancel").json()["status"] == "CANCELLED"
    conflict = api_client.post("/api/v1/runs/1/cancel")
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "conflict"


def test_validation_and_not_found_contracts(api_client) -> None:
    invalid = api_client.post(
        "/api/v1/experiments",
        json={
            "name": "Invalid PCA",
            "configuration": {
                "model": "svm_rbf",
                "selector": "pca",
                "budget_kind": "original_features",
                "k_original_features": 4,
            },
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_configuration"
    assert api_client.get("/api/v1/runs/999").json()["error"]["code"] == "not_found"
    assert api_client.get("/api/v1/datasets/999/manifest").json()["error"]["code"] == "not_found"
    assert api_client.get("/api/v1/datasets/999/quality").json()["error"]["code"] == "not_found"


def test_public_demo_is_read_only(monkeypatch, tmp_path) -> None:
    from fastapi.testclient import TestClient

    from beanfeature_api.main import create_app

    monkeypatch.setenv("BEANFEATURE_DEMO_READ_ONLY", "1")
    with TestClient(create_app(f"sqlite:///{tmp_path / 'demo.sqlite'}")) as client:
        assert client.get("/docs").status_code == 200
        response = client.post("/api/v1/experiments", json={"name": "Blocked"})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "demo_read_only"
        inference = client.post("/api/v1/classifier/predict", json={})
        assert inference.status_code == 422
        assert inference.json()["error"]["code"] == "validation_error"
        oversized = client.post(
            "/api/v1/classifier/predict",
            content=b"{}",
            headers={"content-length": "32769", "content-type": "application/json"},
        )
        assert oversized.status_code == 413
        assert oversized.json()["error"]["code"] == "payload_too_large"
