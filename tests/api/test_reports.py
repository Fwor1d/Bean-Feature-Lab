def test_reports_public_read_only_and_empty(api_client):
    assert api_client.get("/api/v1/reports/core/cohorts").json() == []
    assert api_client.get("/api/v1/reports/core/snapshot?cohort_id=no").status_code == 422
    response = api_client.get("/api/v1/reports/core/snapshot", params={"cohort_id": "0" * 64})
    assert response.status_code == 409
    response = api_client.get("/api/v1/reports/core/unknown/evidence")
    assert response.status_code == 410
    assert response.headers["cache-control"] == "no-store"
    assert api_client.post("/api/v1/reports/core/snapshot").status_code == 405
