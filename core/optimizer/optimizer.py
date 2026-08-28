"""Executor Optimizer and SLM Promotion Engine.

Manages executor promotion gates (Frontier LLM -> SLM / Code), verifies behavior compliance
invariants, and generates fine-tuning training candidate specifications for external backends (HF / TRL).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

import yaml

from core.validation.quality_record import (
    BehaviorVerdict,
    QualityRecord,
    evaluate_quality_fold,
)


@dataclass
class TrainingCandidate:
    """Specification of a training candidate for external fine-tuning (HF / TRL).

    Attributes:
        action_name: The workflow action/step being specialized into an SLM.
        candidate_id: Unique identifier for the training candidate.
        target_executor_type: Type of candidate executor (default: 'slm').
        base_model: Foundation model to be fine-tuned.
        framework: Training framework backend ('trl', 'huggingface', 'unsloth').
        trainer: Specific trainer class (e.g. 'SFTTrainer', 'DPOTrainer').
        dataset: Dataset configuration including formatted samples and split ratios.
        hyperparameters: Fine-tuning hyperparameters (LoRA rank, alpha, learning rate, etc.).
        behavior_invariants: List of non-negotiable behavior contracts required for this action.
        promotion_gate: Quality and behavior compliance criteria required before promotion.
        metadata: Additional provenance and export details.
    """

    action_name: str
    candidate_id: str
    target_executor_type: str = "slm"
    base_model: str = "Qwen/Qwen2.5-Coder-7B-Instruct"
    framework: str = "trl"
    trainer: str = "SFTTrainer"
    dataset: dict[str, Any] = field(default_factory=dict)
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    behavior_invariants: list[str] = field(default_factory=list)
    promotion_gate: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Converts the TrainingCandidate instance to a dictionary representation."""
        return asdict(self)

    def to_yaml(self) -> str:
        """Serializes the TrainingCandidate to a clean YAML string."""
        return yaml.dump({"training_candidate": self.to_dict()}, sort_keys=False)


class ExecutorOptimizer:
    """Manages executor routing, evaluation gates, and SLM/Code promotion.

    Enforces the 4-condition promotion gate:
      1. Outcome Quality >= threshold (result quality)
      2. Behavior Compliance >= threshold (process compliance, rejecting lucky-corrects)
      3. Cost Improvement (lower or comparable execution cost)
      4. Latency Acceptable (latency meets operational envelope)
    """

    def __init__(self) -> None:
        self._active_executors: dict[str, str] = {}
        self._promotion_history: dict[str, list[dict[str, Any]]] = {}

    def get_active_executor(self, action_name: str, default: str = "frontier_llm") -> str:
        """Returns the currently active executor for a given action."""
        return self._active_executors.get(action_name, default)

    def evaluate_promotion(
        self,
        action_name: str,
        candidate_executor: str,
        quality_records: list[QualityRecord],
        min_quality: float = 0.95,
        min_behavior_compliance: float = 1.0,
        max_latency_ms: float | None = None,
        max_cost: float | None = None,
    ) -> bool:
        """Evaluates whether a candidate executor (SLM or Code) can be promoted for an action.

        Promotion requires that:
          - A non-empty set of quality records is evaluated for the action.
          - The overall quality fold pass rate (PASS) is >= min_quality.
          - The behavior compliance rate is >= min_behavior_compliance (zero tolerance for lucky-corrects).
          - No record passes solely through a lucky-correct anomaly.
          - Average latency and cost satisfy optional constraints.

        Args:
            action_name: The workflow action/step being evaluated.
            candidate_executor: Identifier or type of candidate executor (e.g. 'slm', 'code').
            quality_records: Held-out evaluation trace quality records.
            min_quality: Minimum fraction of records that must achieve 'PASS' (default: 0.95).
            min_behavior_compliance: Minimum behavior compliance rate (default: 1.0 = 100%).
            max_latency_ms: Optional upper bound on average execution latency in ms.
            max_cost: Optional upper bound on average execution cost.

        Returns:
            True if all promotion criteria are satisfied, False otherwise.
        """
        # Filter records for action_name if action_name is specified on records
        relevant_records = [
            r for r in quality_records
            if not r.action_name or r.action_name == action_name
        ]

        if not relevant_records:
            return False

        pass_count = 0
        lucky_correct_count = 0
        total_latency = 0.0
        total_cost = 0.0
        compliant_records = 0

        for record in relevant_records:
            fold_verdict = evaluate_quality_fold(record)
            if fold_verdict == "PASS":
                pass_count += 1

            if record.is_lucky_correct():
                lucky_correct_count += 1

            if not record.has_behavior_failures():
                compliant_records += 1

            total_latency += record.execution_latency_ms
            total_cost += record.execution_cost

        total = len(relevant_records)
        pass_rate = pass_count / total
        behavior_compliance_rate = compliant_records / total
        avg_latency = total_latency / total
        avg_cost = total_cost / total

        # Check quality pass rate
        if pass_rate < min_quality:
            return False

        # Check behavior compliance rate
        if behavior_compliance_rate < min_behavior_compliance:
            return False

        # Lucky-correct anomalies must not be promoted
        if lucky_correct_count > 0 and min_behavior_compliance >= 1.0:
            return False

        # Latency check
        if max_latency_ms is not None and avg_latency > max_latency_ms:
            return False

        # Cost check
        if max_cost is not None and avg_cost > max_cost:
            return False

        return True

    def promote(
        self,
        action_name: str,
        candidate_executor: str,
        quality_records: list[QualityRecord],
        min_quality: float = 0.95,
        min_behavior_compliance: float = 1.0,
        max_latency_ms: float | None = None,
        max_cost: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Evaluates promotion and, if successful, registers the candidate as the active executor."""
        is_promoted = self.evaluate_promotion(
            action_name=action_name,
            candidate_executor=candidate_executor,
            quality_records=quality_records,
            min_quality=min_quality,
            min_behavior_compliance=min_behavior_compliance,
            max_latency_ms=max_latency_ms,
            max_cost=max_cost,
        )

        history_entry = {
            "action_name": action_name,
            "candidate_executor": candidate_executor,
            "promoted": is_promoted,
            "num_records_evaluated": len(quality_records),
            "min_quality_threshold": min_quality,
            "metadata": metadata or {},
        }
        self._promotion_history.setdefault(action_name, []).append(history_entry)

        if is_promoted:
            self._active_executors[action_name] = candidate_executor

        return is_promoted

    def evaluate_batch(self, quality_records: list[QualityRecord]) -> dict[str, Any]:
        """Calculates aggregated metrics over a collection of quality records."""
        if not quality_records:
            return {
                "total_records": 0,
                "pass_count": 0,
                "fail_count": 0,
                "na_count": 0,
                "pass_rate": 0.0,
                "lucky_correct_count": 0,
                "behavior_compliance_rate": 1.0,
                "avg_latency_ms": 0.0,
                "avg_cost": 0.0,
            }

        total = len(quality_records)
        pass_count = 0
        fail_count = 0
        na_count = 0
        lucky_correct_count = 0
        compliant_count = 0
        total_latency = 0.0
        total_cost = 0.0

        for r in quality_records:
            verdict = evaluate_quality_fold(r)
            if verdict == "PASS":
                pass_count += 1
            elif verdict == "FAIL":
                fail_count += 1
            else:
                na_count += 1

            if r.is_lucky_correct():
                lucky_correct_count += 1

            if not r.has_behavior_failures():
                compliant_count += 1

            total_latency += r.execution_latency_ms
            total_cost += r.execution_cost

        return {
            "total_records": total,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "na_count": na_count,
            "pass_rate": pass_count / total,
            "lucky_correct_count": lucky_correct_count,
            "behavior_compliance_rate": compliant_count / total,
            "avg_latency_ms": total_latency / total,
            "avg_cost": total_cost / total,
        }


def generate_training_candidate(
    action_name: str,
    approved_traces: list[Any],
    base_model: str = "Qwen/Qwen2.5-Coder-7B-Instruct",
    hyperparameters: dict[str, Any] | None = None,
    behavior_invariants: list[str] | None = None,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """Generates a TrainingCandidate definition dictionary/YAML for external fine-tuning backends (HF/TRL).

    Extracts instruction-input-output pairs and process invariants from approved execution traces,
    structuring them into standard Hugging Face / TRL SFTTrainer format.

    Args:
        action_name: Workflow action name to synthesize training candidate for (e.g. 'draft_proposal').
        approved_traces: List of approved traces or trace step dictionaries.
        base_model: Target foundation model identifier (default: 'Qwen/Qwen2.5-Coder-7B-Instruct').
        hyperparameters: Optional dictionary of fine-tuning hyperparameters.
        behavior_invariants: Optional list of required behavior contract invariant names.
        system_prompt: Optional default system prompt instructing the specialized SLM.

    Returns:
        Dictionary representation of the TrainingCandidate ready for YAML export or TRL execution.
    """
    default_system_prompt = system_prompt or (
        f"You are a specialized OpenWorkflow SLM executor for action '{action_name}'. "
        "Strictly adhere to specified behavior contracts and schema invariants."
    )

    extracted_examples: list[dict[str, Any]] = []
    inferred_invariants: set[str] = set(behavior_invariants or [])

    for trace in approved_traces:
        # Handle trace as dictionary or object
        trace_dict: dict[str, Any] = trace if isinstance(trace, dict) else (
            asdict(trace) if hasattr(trace, "__dataclass_fields__") else vars(trace)
        )

        # Collect behaviors if attached to trace
        if "behaviors" in trace_dict:
            for b in trace_dict["behaviors"]:
                if isinstance(b, str):
                    inferred_invariants.add(b)
                elif isinstance(b, dict) and "name" in b:
                    inferred_invariants.add(b["name"])
        elif "behavior_verdicts" in trace_dict:
            for b in trace_dict["behavior_verdicts"].keys():
                inferred_invariants.add(b)

        # Check if trace contains multi-step sequence
        steps = trace_dict.get("steps", [])
        if steps:
            for step in steps:
                if hasattr(step, "to_dict"):
                    step_dict = step.to_dict()
                elif isinstance(step, dict):
                    step_dict = step
                else:
                    step_dict = {}

                step_action = step_dict.get("action") or step_dict.get("action_name")
                if step_action == action_name:
                    step_input = step_dict.get("input", {})
                    step_output = step_dict.get("output", {})
                    step_sys = step_dict.get("system_prompt", default_system_prompt)
                    example = _format_chat_example(step_sys, step_input, step_output)
                    extracted_examples.append(example)
        else:
            # Flat trace or single action trace
            trace_action = trace_dict.get("action") or trace_dict.get("action_name")
            if not trace_action or trace_action == action_name:
                inp = trace_dict.get("input", trace_dict.get("inputs", {}))
                out = trace_dict.get("output", trace_dict.get("outputs", trace_dict.get("result", {})))
                sys_prompt = trace_dict.get("system_prompt", default_system_prompt)
                if inp or out:
                    example = _format_chat_example(sys_prompt, inp, out)
                    extracted_examples.append(example)

    total_samples = len(extracted_examples)
    train_count = int(total_samples * 0.8)
    eval_count = total_samples - train_count

    default_hyperparams: dict[str, Any] = {
        "learning_rate": 2e-4,
        "num_train_epochs": 3,
        "per_device_train_batch_size": 4,
        "gradient_accumulation_steps": 4,
        "warmup_ratio": 0.05,
        "weight_decay": 0.01,
        "max_seq_length": 2048,
        "peft": {
            "method": "lora",
            "lora_r": 16,
            "lora_alpha": 32,
            "lora_dropout": 0.05,
            "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        },
    }

    if hyperparameters:
        default_hyperparams.update(hyperparameters)

    candidate_id = f"{action_name.replace('_', '-')}-slm-candidate"

    candidate = TrainingCandidate(
        action_name=action_name,
        candidate_id=candidate_id,
        target_executor_type="slm",
        base_model=base_model,
        framework="trl",
        trainer="SFTTrainer",
        dataset={
            "format": "chat_messages",
            "num_samples": total_samples,
            "train_samples": train_count,
            "eval_samples": eval_count,
            "train_eval_split": 0.8,
            "examples": extracted_examples,
        },
        hyperparameters=default_hyperparams,
        behavior_invariants=sorted(list(inferred_invariants)),
        promotion_gate={
            "min_quality": 0.95,
            "min_behavior_compliance": 1.0,
            "reject_on_lucky_correct": True,
            "max_latency_ms": 1500.0,
        },
        metadata={
            "source": "OpenWorkflow ExecutorOptimizer",
            "target_backends": ["huggingface", "trl", "unsloth"],
        },
    )

    return candidate.to_dict()


def _format_chat_example(system_prompt: str, step_input: Any, step_output: Any) -> dict[str, Any]:
    """Formats inputs and outputs into standardized chat message format."""
    input_str = json.dumps(step_input, indent=2) if isinstance(step_input, (dict, list)) else str(step_input)
    output_str = json.dumps(step_output, indent=2) if isinstance(step_output, (dict, list)) else str(step_output)

    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input_str},
            {"role": "assistant", "content": output_str},
        ]
    }
