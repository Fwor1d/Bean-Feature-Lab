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
