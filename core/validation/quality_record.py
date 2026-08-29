"""Quality Record and Evaluation Engine.

Defines the QualityRecord dataclass and deterministic fold evaluation logic,
enforcing behavior compliance invariants and rejecting lucky-correct anomalies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BehaviorVerdict(str, Enum):
    """Behavior compliance verdict for an individual behavior contract.

    Adopts the AgentBehavior / OpenWorkCompiler standard convention:
      - TRUE: Trigger fired and required conduct was observed.
      - FALSE: Trigger fired, conduct was missing, skipped, or failed.
      - NA: No trigger in this trajectory, or behavior is unjudgeable.
    """

    TRUE = "true"
    FALSE = "false"
    NA = "na"


class QualityFoldResult(str, Enum):
    """Deterministic fold evaluation outcome."""

    PASS = "PASS"
    FAIL = "FAIL"
    NA = "NA"


@dataclass
class QualityRecord:
    """Represents a unified quality evaluation record for an execution trace.

    Combines human outcome ratings, automated schema/rule checks,
    per-behavior compliance verdicts (true/false/na), and telemetry (cost & latency).

    Attributes:
        trace_id: Unique identifier of the execution trace or run.
        action_name: The workflow step or action name evaluated (e.g. 'draft_proposal').
        executor_type: Type of executor that produced the trace (e.g. 'frontier_llm', 'slm', 'code', 'rule').
        human_ratings: Mapping of human evaluation criteria (e.g. {'approved': True, 'reviewer_acceptance': 1.0, 'score': 5.0}).
        automated_checks: Mapping of automated assertions (e.g. {'schema_valid': True, 'rule_check_pass': True}).
        behavior_verdicts: Mapping of behavior name to verdict string or BehaviorVerdict ('true', 'false', 'na').
        execution_cost: Cost of execution in USD or standard units.
        execution_latency_ms: Duration of execution in milliseconds.
        metadata: Arbitrary additional contextual metadata (e.g. prompt_tokens, model_name, timestamp).
    """

    trace_id: str
    action_name: str = ""
    executor_type: str = "frontier_llm"
    human_ratings: dict[str, Any] = field(default_factory=dict)
    automated_checks: dict[str, bool] = field(default_factory=dict)
    behavior_verdicts: dict[str, str | BehaviorVerdict] = field(default_factory=dict)
    execution_cost: float = 0.0
    execution_latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_lucky_correct(self) -> bool:
        """Determines if the trace exhibits a lucky-correct anomaly.

        A lucky-correct outcome occurs when human ratings or automated checks appear
        successful, but one or more required behavior contracts failed (conduct was skipped).
        """
        outcome_passed = self._check_outcome_passed()
        behavior_failed = self.has_behavior_failures()
        return outcome_passed and behavior_failed

    def has_behavior_failures(self) -> bool:
        """Returns True if any behavior verdict is 'false'."""
        for verdict in self.behavior_verdicts.values():
            val = verdict.value if isinstance(verdict, BehaviorVerdict) else str(verdict).lower()
            if val == BehaviorVerdict.FALSE.value:
                return True
        return False

    def has_automated_failures(self) -> bool:
        """Returns True if any automated check is False."""
        for passed in self.automated_checks.values():
            if not passed:
                return True
        return False

    def behavior_compliance_rate(self) -> float:
        """Calculates the ratio of passed behaviors over all evaluated behaviors (excluding 'na').

        Returns:
            Float between 0.0 and 1.0. Returns 1.0 if all behaviors are 'na' or empty.
        """
        true_count = 0
        false_count = 0
        for verdict in self.behavior_verdicts.values():
            val = verdict.value if isinstance(verdict, BehaviorVerdict) else str(verdict).lower()
            if val == BehaviorVerdict.TRUE.value:
                true_count += 1
            elif val == BehaviorVerdict.FALSE.value:
                false_count += 1

        total_evaluated = true_count + false_count
        if total_evaluated == 0:
            return 1.0
        return true_count / total_evaluated

    def _check_outcome_passed(self) -> bool:
        """Helper to determine if human ratings and automated checks indicate outcome success."""
        # Check automated checks
        if self.has_automated_failures():
            return False

        # Check human ratings
        if "approved" in self.human_ratings:
            if not self.human_ratings["approved"]:
                return False

        for key, value in self.human_ratings.items():
            if key == "approved":
                continue
            if isinstance(value, bool) and not value:
                return False
            if isinstance(value, (int, float)):
                # If rating is 0.0 or below minimum passing score
                if value <= 0.0:
                    return False

        # Outcome is considered passed if there are positive ratings/checks or no failures
        return True

    def to_dict(self) -> dict[str, Any]:
        """Converts the QualityRecord instance to a dictionary representation."""
        verdicts_serialized = {}
        for k, v in self.behavior_verdicts.items():
            verdicts_serialized[k] = v.value if isinstance(v, BehaviorVerdict) else str(v)

        return {
            "trace_id": self.trace_id,
            "action_name": self.action_name,
            "executor_type": self.executor_type,
            "human_ratings": dict(self.human_ratings),
            "automated_checks": dict(self.automated_checks),
            "behavior_verdicts": verdicts_serialized,
            "execution_cost": self.execution_cost,
            "execution_latency_ms": self.execution_latency_ms,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityRecord:
        """Instantiates a QualityRecord from a dictionary."""
        raw_verdicts = data.get("behavior_verdicts", {})
        verdicts: dict[str, str | BehaviorVerdict] = {}
        for k, v in raw_verdicts.items():
            val_str = str(v).lower()
            if val_str in (BehaviorVerdict.TRUE.value, BehaviorVerdict.FALSE.value, BehaviorVerdict.NA.value):
                verdicts[k] = BehaviorVerdict(val_str)
            else:
                verdicts[k] = val_str

        return cls(
            trace_id=data.get("trace_id", ""),
            action_name=data.get("action_name", ""),
            executor_type=data.get("executor_type", "frontier_llm"),
            human_ratings=data.get("human_ratings", {}),
            automated_checks=data.get("automated_checks", {}),
            behavior_verdicts=verdicts,
            execution_cost=float(data.get("execution_cost", 0.0)),
            execution_latency_ms=float(data.get("execution_latency_ms", 0.0)),
            metadata=data.get("metadata", {}),
        )


def evaluate_quality_fold(quality_record: QualityRecord) -> str:
    """Evaluates the unified quality fold for a QualityRecord according to OpenWorkCompiler principles.

    Evaluation logic enforcing the Lucky-Correct check:
      1. Any behavior verdict == 'false' -> FAIL (regardless of outcome or other passing checks).
         A lucky-correct result that skipped a required process is a failure, not a pass.
      2. Any automated check == False -> FAIL.
      3. Any human rating indicating rejection (approved == False or negative score) -> FAIL.
      4. Otherwise, if there is positive evidence (behavior == 'true', passing automated checks,
         or approved human ratings) -> PASS.
      5. If all behavior verdicts are 'na' and no checks/ratings exist -> NA.

    Args:
        quality_record: The QualityRecord instance to evaluate.

    Returns:
        String verdict: 'PASS', 'FAIL', or 'NA'.
    """
    # 1. Behavior Verification & Lucky-Correct Defense:
    # Any behavior evaluated as false causes an immediate FAIL.
    if quality_record.has_behavior_failures():
        return QualityFoldResult.FAIL.value

    # 2. Automated Invariants & Schema Checks:
    # Any automated check failing causes a FAIL.
    if quality_record.has_automated_failures():
        return QualityFoldResult.FAIL.value

    # 3. Human Outcome Evaluation:
    # Check explicit approval or rejection
    if "approved" in quality_record.human_ratings:
        if not quality_record.human_ratings["approved"]:
            return QualityFoldResult.FAIL.value

    # Check numerical ratings/scores if present
    for key, value in quality_record.human_ratings.items():
        if key == "approved":
            continue
        if isinstance(value, bool) and not value:
            return QualityFoldResult.FAIL.value
        if isinstance(value, (int, float)):
            # Normalize common ratings: e.g. 1-5 stars or 0.0-1.0 probability
            if value <= 0.0:
                return QualityFoldResult.FAIL.value

    # 4. Check for positive confirmation
    has_positive_behavior = any(
        (v.value if isinstance(v, BehaviorVerdict) else str(v).lower()) == BehaviorVerdict.TRUE.value
        for v in quality_record.behavior_verdicts.values()
    )
    has_passing_checks = len(quality_record.automated_checks) > 0 and all(quality_record.automated_checks.values())
    has_passing_ratings = len(quality_record.human_ratings) > 0 and (
        quality_record.human_ratings.get("approved") is True or any(
            isinstance(v, (int, float)) and v > 0 for k, v in quality_record.human_ratings.items() if k != "approved"
        )
    )

    if has_positive_behavior or has_passing_checks or has_passing_ratings:
        return QualityFoldResult.PASS.value

    # If behavior_verdicts exists and contains only 'na', and no ratings/checks:
    if quality_record.behavior_verdicts:
        all_na = all(
            (v.value if isinstance(v, BehaviorVerdict) else str(v).lower()) == BehaviorVerdict.NA.value
            for v in quality_record.behavior_verdicts.values()
        )
        if all_na and not quality_record.automated_checks and not quality_record.human_ratings:
            return QualityFoldResult.NA.value

    # Default to PASS if no constraints were violated
    return QualityFoldResult.PASS.value
