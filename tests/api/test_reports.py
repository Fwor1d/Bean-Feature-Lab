def test_reports_public_read_only_and_empty(api_client):
    assert api_client.get("/api/v1/reports/core/cohorts").json() == []
    assert api_client.get("/api/v1/reports/core/snapshot?cohort_id=no").status_code == 422
    response = api_client.get("/api/v1/reports/core/snapshot", params={"cohort_id": "0" * 64})
    assert response.status_code == 409
    response = api_client.get("/api/v1/reports/core/unknown/evidence")
    assert response.status_code == 410
    assert response.headers["cache-control"] == "no-store"
    assert api_client.post("/api/v1/reports/core/snapshot").status_code == 405


def test_pdf_read_only_attachment_and_expiry(api_client, monkeypatch):
    from contextlib import contextmanager

    from beanfeature_application.reporting import ReportError

    cache = api_client.app.state.report_snapshots
    renderer = api_client.app.state.pdf_reports

    @contextmanager
    def lease(identifier):
        assert identifier == "test-only"
        yield {"snapshot_id": identifier, "evidence_sha256": "a" * 64}

    monkeypatch.setattr(cache, "lease", lease)
    monkeypatch.setattr(renderer, "render", lambda _: b"%PDF-test-only")
    response = api_client.get("/api/v1/reports/core/test-only/pdf")
    assert response.status_code == 200 and response.content == b"%PDF-test-only"
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["x-evidence-sha256"] == "a" * 64
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="BeanFeatureLab-aaaaaaaaaaaaaaaa.pdf"'
    )
    assert response.headers["cache-control"] == "no-store"

    def expired(_):
        raise ReportError("snapshot_expired", "Снимок истёк", 410)

    monkeypatch.setattr(cache, "lease", expired)
    assert api_client.get("/api/v1/reports/core/test-only/pdf").status_code == 410


def test_pdf_exception_is_safe_and_retryable(api_client, monkeypatch):
    from contextlib import contextmanager

    @contextmanager
    def lease(_):
        yield {"snapshot_id": "test-only", "evidence_sha256": "a" * 64}

    def failure(_):
        raise OSError("/secret/path/config")

    monkeypatch.setattr(api_client.app.state.report_snapshots, "lease", lease)
    monkeypatch.setattr(api_client.app.state.pdf_reports, "render", failure)
    response = api_client.get("/api/v1/reports/core/test-only/pdf")
    assert response.status_code == 503 and response.headers["retry-after"] == "5"
    assert "/secret" not in response.text
