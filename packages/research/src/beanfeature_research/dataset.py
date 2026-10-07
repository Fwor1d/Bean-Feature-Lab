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


def dataset_quality_summary(dataset: ValidatedDataset) -> dict[str, object]:
    """Describe the validated source without changing or filtering any observation."""
    features = dataset.features
    target = pd.Series(dataset.target, name=TARGET)
    combined = features.assign(**{TARGET: target.to_numpy()})
    class_counts = target.value_counts().sort_index()
    feature_statistics: dict[str, dict[str, float | int | bool]] = {}
    for name in features.columns:
        values = features[name].astype(float)
        q1 = float(values.quantile(0.25))
        q3 = float(values.quantile(0.75))
        iqr = q3 - q1
        lower = q1 - 3 * iqr
        upper = q3 + 3 * iqr
        feature_statistics[str(name)] = {
            "minimum": float(values.min()),
            "maximum": float(values.max()),
            "median": float(values.median()),
            "q1": q1,
            "q3": q3,
            "iqr": iqr,
            "constant": bool(values.nunique(dropna=False) == 1),
            "extreme_outlier_count": int(((values < lower) | (values > upper)).sum()),
            "extreme_outlier_lower_fence": lower,
            "extreme_outlier_upper_fence": upper,
        }
    return {
        "dataset_sha256": dataset.arff_sha256,
        "rows": len(features),
        "columns": len(features.columns) + 1,
        "numeric_feature_count": len(features.columns),
        "missing_values": int(combined.isna().sum().sum()),
        "infinite_values": int(np.isinf(features.to_numpy(dtype=float)).sum()),
        "exact_duplicate_rows_involved": int(combined.duplicated(keep=False).sum()),
        "exact_duplicate_excess_rows": int(combined.duplicated(keep="first").sum()),
        "class_balance": {
            str(label): {
                "count": int(count),
                "fraction": float(count / len(target)),
            }
            for label, count in class_counts.items()
        },
        "constant_columns": [
            name for name, values in feature_statistics.items() if values["constant"]
        ],
        "feature_statistics": feature_statistics,
        "outlier_method": "Tukey extreme fences: below Q1 - 3*IQR or above Q3 + 3*IQR",
        "cleaning_applied": False,
        "note": (
            "Diagnostics only: duplicates and extreme values are reported, never removed "
            "or clipped automatically."
        ),
    }


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
