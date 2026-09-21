"""Strict parsing of the unmodified UCI 602 ARFF payload."""

import re
from dataclasses import dataclass
from hashlib import sha256
from io import StringIO

import numpy as np
import pandas as pd
from scipy.io import arff

SOURCE_ID = 602
EXPECTED_ROWS = 13_611
TARGET = "Class"
# These are the literal attribute names in the official ARFF, including its spelling/case.
FEATURE_COLUMNS = (
    "Area",
    "Perimeter",
    "MajorAxisLength",
    "MinorAxisLength",
    "AspectRation",
    "Eccentricity",
    "ConvexArea",
    "EquivDiameter",
    "Extent",
    "Solidity",
    "roundness",
    "Compactness",
    "ShapeFactor1",
    "ShapeFactor2",
    "ShapeFactor3",
    "ShapeFactor4",
)
CLASSES = ("BARBUNYA", "BOMBAY", "CALI", "DERMASON", "HOROZ", "SEKER", "SIRA")
SOURCE_SCHEMA_NOTICE = (
    "Official UCI ARFF spells the class DERMASON (PRODUCT.md: Dermosan) and attributes "
    "AspectRation/roundness (descriptive text: AspectRatio/Roundness). Values are never renamed."
)


class DatasetValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedDataset:
    features: pd.DataFrame
    target: np.ndarray
    arff_sha256: str

    @property
    def feature_names(self) -> tuple[str, ...]:
        return tuple(self.features.columns)


def validate_arff(data: bytes, *, accept_official_schema: bool = False) -> ValidatedDataset:
    """Check the source bytes before *any* learned data transformation."""
    if not accept_official_schema:
        raise DatasetValidationError(
            "Explicit acknowledgement of source/document schema difference required: "
            f"{SOURCE_SCHEMA_NOTICE}"
        )
    names = re.findall(rb"(?im)^@attribute\s+([^\s]+)", data)
    decoded = [name.decode("ascii", errors="strict") for name in names]
    if len(decoded) != len(set(name.casefold() for name in decoded)):
        raise DatasetValidationError("Duplicate ARFF attribute names")
    if decoded != [*FEATURE_COLUMNS, TARGET]:
        raise DatasetValidationError(
            f"Unexpected UCI 602 columns/order: {decoded}; expected {[*FEATURE_COLUMNS, TARGET]}"
        )
    try:
        records, _metadata = arff.loadarff(StringIO(data.decode("utf-8")))
    except (ValueError, TypeError) as exc:
        raise DatasetValidationError(f"Invalid ARFF: {exc}") from exc
    frame = pd.DataFrame(records)
    if frame.shape != (EXPECTED_ROWS, 17):
        raise DatasetValidationError(f"Expected 13611 rows and 17 columns, got {frame.shape}")
    if TARGET not in frame or TARGET in FEATURE_COLUMNS:
        raise DatasetValidationError("Target column missing or included among predictors")
    features = frame.loc[:, FEATURE_COLUMNS].copy()
    if not all(pd.api.types.is_numeric_dtype(features[name]) for name in FEATURE_COLUMNS):
        raise DatasetValidationError("All 16 predictors must be numeric")
    if features.isna().any().any() or not np.isfinite(features.to_numpy(dtype=float)).all():
        raise DatasetValidationError("Predictors contain missing or non-finite values")
    raw_target = frame[TARGET]
    if raw_target.isna().any():
        raise DatasetValidationError("Target contains missing values")
    target = np.array(
        [value.decode("ascii") if isinstance(value, bytes) else str(value) for value in raw_target]
    )
    if tuple(sorted(set(target))) != CLASSES:
        raise DatasetValidationError(
            f"Expected seven official classes {CLASSES}; got {sorted(set(target))}"
        )
    return ValidatedDataset(features, target, sha256(data).hexdigest())
