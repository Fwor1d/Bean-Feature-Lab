"""Independent research contracts. No training is implemented in Stage 4A."""

from .contracts import (
    ModelId,
    OriginalFeatureBudget,
    PCARepresentation,
    ResultState,
    RunStatus,
    SelectorId,
    assert_transition,
)

__all__ = [
    "ModelId",
    "OriginalFeatureBudget",
    "PCARepresentation",
    "ResultState",
    "RunStatus",
    "SelectorId",
    "assert_transition",
]
