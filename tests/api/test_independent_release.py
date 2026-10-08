from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from beanfeature_application.contracts import Run
from beanfeature_research.contracts import RunStatus
from beanfeature_research.dataset import FEATURE_COLUMNS


def test_unrepresentable_integer_is_a_structured_input_error_with_cors(api_client):
    service = api_client.app.state.container.service
    service.deployment_models = SimpleNamespace(
        load=lambda: (object(), {"feature_names": list(FEATURE_COLUMNS)})
    )
    values = dict.fromkeys(FEATURE_COLUMNS, 1.0)
    values["Area"] = 10**309
    response = api_client.post(
        "/api/v1/classifier/predict",
        json={"features": values},
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_configuration"
    assert "finite numeric" in response.json()["error"]["message"]
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/runs/9223372036854775808",
        "/api/v1/experiments/9223372036854775808",
        "/api/v1/runs/1/paired-comparison/9223372036854775808",
        "/api/v1/runs/9223372036854775808/descriptive-comparison/1",
        "/api/v1/runs/0",
        "/api/v1/runs/-1",
    ],
)
def test_invalid_database_ids_never_reach_sqlite(api_client, path):
    response = api_client.get(path, headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_stored_failure_paths_remain_local(api_client, tmp_path, monkeypatch):
    missing = tmp_path / "private-model" / "missing.joblib"
    try:
        missing.read_bytes()
    except FileNotFoundError as exc:
        diagnostic = f"{type(exc).__name__}: {exc}"
    run = Run(1, 1, RunStatus.FAILED, datetime.now(UTC), error=diagnostic)
    service = api_client.app.state.container.service
    monkeypatch.setattr(service, "list_runs", lambda: [run])
    monkeypatch.setattr(service, "get_run", lambda identifier: run)
    for path in ["/api/v1/runs", "/api/v1/runs/1"]:
        response = api_client.get(path)
        assert response.status_code == 200
        assert str(missing) not in response.text
        data = response.json()
        record = data[0] if isinstance(data, list) else data
        assert record["status"] == "FAILED"
        assert "локальной диагностике" in record["error"]
    assert run.error == diagnostic  # Public DTOs never rewrite recorded diagnostics.
