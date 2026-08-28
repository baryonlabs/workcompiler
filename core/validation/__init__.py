"""Validation, Quality Evaluation, and Behavior Contract classification engine."""

from core.validation.classifier import (
    BehaviorCategory,
    BehaviorClassification,
    classify_behavior,
)
from core.validation.quality_record import (
    BehaviorVerdict,
    QualityFoldResult,
    QualityRecord,
    evaluate_quality_fold,
)

# Alias for convenience
evaluate_quality_record = evaluate_quality_fold

__all__ = [
    "BehaviorCategory",
    "BehaviorClassification",
    "classify_behavior",
    "BehaviorVerdict",
    "QualityFoldResult",
    "QualityRecord",
    "evaluate_quality_fold",
    "evaluate_quality_record",
]
