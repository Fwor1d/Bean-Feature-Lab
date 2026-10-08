"""PDF tests use explicitly synthetic test DTOs, never production substitutes."""

import io
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest
from pypdf import PdfReader
from tests.application.test_reporting import EvidenceService, build

from beanfeature_application.reporting import ReportError, digest
from beanfeature_infrastructure import reports


@pytest.fixture
def snapshot():
    body = build(EvidenceService([1, 16]))
    body["dataset"].update(
        source_id=602,
        rows=2,
        feature_count=16,
        classes=["DERMASON", "SEKER"],
        features=["AspectRation", "roundness"],
        dataset_version="test-only",
        archive_sha256="test-zip",
        retrieved_at_utc="2026-01-01T00:00:00Z",
        source_url="https://example.invalid/test-only",
    )
    body["quality"] = {
        "missing_values": 0,
        "class_balance": {
            "DERMASON": {"count": 1, "fraction": 0.5},
            "SEKER": {"count": 1, "fraction": 0.5},
        },
    }
    body["evidence_sha256"] = digest(
        {
            k: v
            for k, v in body.items()
            if k not in {"evidence_sha256", "verified_at_utc", "generation_context"}
        }
    )
    body.update(snapshot_id="test-only", expires_at_utc="2026-01-01T02:00:00Z")
    return body


def test_real_pdf_cyrillic_embedding_partial_and_source_identity(snapshot):
    renderer = reports.PDFReports()
    try:
        data = renderer.render(snapshot)
        assert data.startswith(b"%PDF-") and len(data) < reports.MAX_PDF_BYTES
        reader = PdfReader(io.BytesIO(data))
        texts = [page.extract_text() for page in reader.pages]
        text = "\n".join(texts)
        for expected in [
            "Число исходных признаков",
            "Не рассчитано",
            "PCA",
            "Nadeau",
            "Bonferroni",
            "external validation",
            "RUN-000001",
            snapshot["evidence_sha256"],
            "Renderer source SHA-256",
            "AspectRation",
            "DERMASON",
        ]:
            assert expected in text
        assert all(len(t) > 100 for t in texts)
        assert len(set(texts)) == len(texts) and len(texts) < 25
        embedded = set()
        for page in reader.pages:
            for font_ref in page["/Resources"]["/Font"].values():
                font = font_ref.get_object()
                if "DejaVu" in str(font.get("/BaseFont")):
                    assert font["/FontDescriptor"]["/FontFile2"].get_object().get_data()
                    assert font["/ToUnicode"].get_object().get_data()
                    embedded.add(str(font["/BaseFont"]))
        assert len(embedded) == 3
        assert renderer.render(snapshot) == data
    finally:
        renderer.close()


@pytest.mark.parametrize("problem", ["empty", "corrupt", "format", "protocol"])
def test_invalid_evidence_fails_safely(snapshot, problem):
    if problem == "empty":
        snapshot["runs"] = []
    elif problem == "corrupt":
        snapshot["runs"][0]["summary"]["macro_f1_mean"] = 0.999
    elif problem == "format":
        snapshot["format_version"] = "unknown"
    else:
        snapshot["protocol"]["margin"] = 0.02
    with pytest.raises(ReportError):
        reports.render_pdf(snapshot)


def test_render_coalesces_bounds_concurrency_and_recovers(monkeypatch, snapshot):
    entered, release = threading.Event(), threading.Event()
    calls = []

    def render(_snapshot):
        calls.append(True)
        entered.set()
        assert release.wait(3)
        return b"%PDF-test-only"

    monkeypatch.setattr(reports, "render_pdf", render)
    renderer = reports.PDFReports()
    try:
        with ThreadPoolExecutor(3) as pool:
            first = pool.submit(renderer.render, snapshot)
            assert entered.wait(2)
            second = pool.submit(renderer.render, snapshot)
            other = deepcopy(snapshot)
            other["snapshot_id"] = "other"
            with pytest.raises(ReportError, match="Другой PDF"):
                renderer.render(other)
            release.set()
            assert first.result() == second.result()
        assert len(calls) == 1
        for identifier in ["second", "third"]:
            renderer.render({**snapshot, "snapshot_id": identifier})
        assert len(renderer.outputs) == 2 and "test-only" not in renderer.outputs
        monkeypatch.setattr(reports, "render_pdf", lambda _: b"x" * (reports.MAX_PDF_BYTES + 1))
        with pytest.raises(ReportError):
            renderer.render({**snapshot, "snapshot_id": "too-big"})
        assert not renderer.pending
        monkeypatch.setattr(reports, "render_pdf", lambda _: b"%PDF-recovered")
        assert renderer.render({**snapshot, "snapshot_id": "recovered"}) == b"%PDF-recovered"
    finally:
        renderer.close()
