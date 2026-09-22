"""Schema guards use a tiny ARFF fixture, not simulated scientific findings."""

import pytest

import beanfeature_research.dataset as dataset_module
from beanfeature_research.dataset import (
    CLASSES,
    FEATURE_COLUMNS,
    DatasetValidationError,
    validate_arff,
)


def arff_payload() -> bytes:
    lines = ["@RELATION drybean_test"]
    lines.extend(f"@ATTRIBUTE {name} NUMERIC" for name in FEATURE_COLUMNS)
    lines.append("@ATTRIBUTE Class {" + ",".join(CLASSES) + "}")
    lines.append("@DATA")
    lines.extend(",".join([str(index + 1)] * 16 + [name]) for index, name in enumerate(CLASSES))
    return "\n".join(lines).encode()


def test_exact_official_schema_and_acknowledgement(monkeypatch) -> None:
    monkeypatch.setattr(dataset_module, "EXPECTED_ROWS", 7)
    payload = arff_payload()
    with pytest.raises(DatasetValidationError, match="acknowledgement"):
        validate_arff(payload)
    validated = validate_arff(payload, accept_official_schema=True)
    assert validated.features.shape == (7, 16)
    assert tuple(sorted(set(validated.target))) == CLASSES


def test_rejects_schema_drift_missing_and_duplicate_attributes(monkeypatch) -> None:
    monkeypatch.setattr(dataset_module, "EXPECTED_ROWS", 7)
    payload = arff_payload()
    with pytest.raises(DatasetValidationError, match="Unexpected UCI 602 columns"):
        validate_arff(payload.replace(b"AspectRation", b"AspectRatio"), accept_official_schema=True)
    with pytest.raises(DatasetValidationError, match="Duplicate ARFF"):
        validate_arff(
            payload.replace(b"@ATTRIBUTE Perimeter", b"@ATTRIBUTE Area"),
            accept_official_schema=True,
        )
    with pytest.raises(DatasetValidationError, match="missing or non-finite"):
        validate_arff(payload.replace(b"1,1,1", b"?,1,1", 1), accept_official_schema=True)
    with pytest.raises(DatasetValidationError, match="seven official classes"):
        validate_arff(payload.replace(b"SEKER", b"SIRA"), accept_official_schema=True)
