"""Behavior Contract classification engine.

Classifies AgentBehavior specifications into executable targets:
- Rule/Policy (Deterministic invariants & permission gates)
- Workflow Transition Constraint (Step ordering & dependency DAG)
- Runtime Evaluator Judge (Semantic & qualitative conduct)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class BehaviorCategory(str, Enum):
    """Categorization of a behavior contract."""

    RULE_POLICY = "Rule/Policy"
    WORKFLOW_TRANSITION = "Workflow Transition Constraint"
    RUNTIME_EVALUATOR = "Runtime Evaluator Judge"

    def __str__(self) -> str:
        return self.value


@dataclass
class BehaviorClassification:
    """Detailed result of behavior classification."""

    category: BehaviorCategory
    reasoning: str
    enforcement_mechanism: str
    target_layer: str
    confidence: float = 1.0
    extracted_dependencies: list[tuple[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.category.value

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "reasoning": self.reasoning,
            "enforcement_mechanism": self.enforcement_mechanism,
            "target_layer": self.target_layer,
            "confidence": self.confidence,
            "extracted_dependencies": self.extracted_dependencies,
            "metadata": self.metadata,
        }


# Heuristic patterns for workflow transitions (ordering / DAG constraints)
_TRANSITION_PATTERNS = [
    r"workflow\s+transition",
    r"transition\s+dependency",
    r"ordering\s+between\s+steps",
    r"step\s+occurring\s+before",
    r"occurring\s+before",
    r"prior\s+to",
    r"precedes",
    r"must\s+precede",
    r"before\s+computing",
    r"before\s+drafting",
    r"before\s+pricing",
    r"structural\s+procedure",
    r"prerequisite\s+step",
    r"execution\s+order",
    r"dependency\s+DAG",
]

# Heuristic patterns for deterministic rules / policies
_RULE_POLICY_PATTERNS = [
    r"deterministic\s+rule",
    r"rule\s+engine",
    r"policy\s+engine",
    r"rule\s*/\s*policy",
    r"approval\s+before\s+send",
    r"approval\s+gate",
    r"permission",
    r"authorization",
    r"write\s+lock",
    r"pricing\s+policy",
    r"pricing\s+table",
    r"deterministic\s+invariant",
    r"rule\s+executor",
    r"policy\s+check",
]

# Heuristic patterns for runtime evaluator judges
_JUDGE_PATTERNS = [
    r"semantic",
    r"qualitative",
    r"hallucinat",
    r"factual\s+accuracy",
    r"tone",
    r"over\-infer",
    r"evaluator",
    r"judge",
    r"slm\s+judge",
    r"llm\s+judge",
    r"post\-hoc\s+judge",
]


def classify_behavior(behavior_data: Dict[str, Any]) -> BehaviorClassification:
    """Categorize an AgentBehavior spec into one of three execution targets:

    1. Rule/Policy: Deterministic checks, policy rules, or permission gates.
    2. Workflow Transition Constraint: Step ordering / prerequisite dependencies.
    3. Runtime Evaluator Judge: Qualitative / semantic evaluation at runtime.

    Follows the 4-step decision procedure:
    - Step 1: Is the trigger observable in the trace? If no -> Runtime Evaluator Judge.
    - Step 2: Does the conduct impose an ordering/dependency between steps? -> Workflow Transition Constraint.
    - Step 3: Can the conduct be expressed as a deterministic rule? -> Rule/Policy.
    - Step 4: Otherwise (semantic/qualitative conduct) -> Runtime Evaluator Judge.

    Args:
        behavior_data: Parsed dictionary from parse_behavior_md.

    Returns:
        BehaviorClassification containing the assigned category, reasoning, and enforcement target.
    """
    if not isinstance(behavior_data, dict):
        raise TypeError(f"Expected dict for behavior_data, got {type(behavior_data)}")

    name = str(behavior_data.get("name", "")).lower()
    intent = str(behavior_data.get("intent", "")).lower()
    evidence = str(behavior_data.get("evidence", "")).lower()
    execution = str(behavior_data.get("execution", "")).lower()
    failure_modes = str(behavior_data.get("failure_modes", "")).lower()

    combined_text = f"{name} {intent} {evidence} {execution} {failure_modes}"

    # Check explicit execution hints
    if "workflow transition" in execution:
        return BehaviorClassification(
            category=BehaviorCategory.WORKFLOW_TRANSITION,
            reasoning="Execution specification explicitly designates this behavior as a workflow transition dependency.",
            enforcement_mechanism="Workflow graph dependency",
            target_layer="workflow",
            confidence=0.98,
        )

    if "rule engine" in execution or "deterministic rule" in execution:
        return BehaviorClassification(
            category=BehaviorCategory.RULE_POLICY,
            reasoning="Execution specification explicitly designates this behavior as an enforced Rule engine step.",
            enforcement_mechanism="Runtime policy engine",
            target_layer="policy",
            confidence=0.98,
        )

    if "runtime judge" in execution or "evaluator-only" in execution or "slm judge" in execution:
        return BehaviorClassification(
            category=BehaviorCategory.RUNTIME_EVALUATOR,
            reasoning="Execution specification designates this behavior as a semantic runtime judge.",
            enforcement_mechanism="SLM/LLM behavior judge",
            target_layer="evaluator",
            confidence=0.95,
        )

    # Step 2: Evaluate Workflow Transition / Ordering Dependency
    transition_score = sum(
        1 for pat in _TRANSITION_PATTERNS if re.search(pat, combined_text)
    )
    # Check if evidence contains step ordering phrases like `A` occurring before `B` or `A` prior to `B`
    ordering_match = re.search(
        r"(`?[\w\.\-]+`?)\s+(?:occurring\s+before|prior\s+to|preceding|before)\s+(`?[\w\.\-]+`?)",
        evidence,
    )
    extracted_deps = []
    if ordering_match:
        step_a = ordering_match.group(1).replace("`", "").strip()
        step_b = ordering_match.group(2).replace("`", "").strip()
        extracted_deps.append((step_a, step_b))
        transition_score += 3

    # Step 3: Evaluate Rule / Policy
    rule_score = sum(
        1 for pat in _RULE_POLICY_PATTERNS if re.search(pat, combined_text)
    )

    # Step 4: Evaluate Runtime Evaluator
    judge_score = sum(
        1 for pat in _JUDGE_PATTERNS if re.search(pat, combined_text)
    )

    # Decision logic
    if transition_score > rule_score and transition_score > 0:
        return BehaviorClassification(
            category=BehaviorCategory.WORKFLOW_TRANSITION,
            reasoning=(
                f"Imposes structural ordering and dependency constraints between steps "
                f"(transition score: {transition_score})."
            ),
            enforcement_mechanism="Workflow graph dependency",
            target_layer="workflow",
            confidence=min(0.95, 0.7 + 0.05 * transition_score),
            extracted_dependencies=extracted_deps,
        )
    elif rule_score >= transition_score and rule_score > 0:
        return BehaviorClassification(
            category=BehaviorCategory.RULE_POLICY,
            reasoning=(
                f"Conduct can be expressed as a deterministic rule, validation check, or policy gate "
                f"(rule score: {rule_score})."
            ),
            enforcement_mechanism="Runtime policy engine",
            target_layer="policy",
            confidence=min(0.95, 0.7 + 0.05 * rule_score),
        )
    elif judge_score > 0:
        return BehaviorClassification(
            category=BehaviorCategory.RUNTIME_EVALUATOR,
            reasoning=(
                f"Requires semantic/qualitative judgment over trajectory output or conduct "
                f"(judge score: {judge_score})."
            ),
            enforcement_mechanism="SLM/LLM behavior judge",
            target_layer="evaluator",
            confidence=0.85,
        )
    else:
        # Default fallback per Decision Procedure step 4
        return BehaviorClassification(
            category=BehaviorCategory.RUNTIME_EVALUATOR,
            reasoning="Fallback to runtime evaluator judge for qualitative behavior verification.",
            enforcement_mechanism="SLM/LLM behavior judge",
            target_layer="evaluator",
            confidence=0.6,
        )
