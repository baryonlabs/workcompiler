"""SLM (Small Language Model) task analyzer for OpenWorkflow WorkCompiler.

Analyzes recorded trace steps to detect narrow generative language tasks
(e.g., email intent extraction, customer support summary, short proposal drafting)
and synthesizes SFT (Supervised Fine-Tuning) dataset pairs for specialized 1B–3B student models.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from core.optimizer.optimizer import TrainingCandidate
from protocols.traces.trace_ir import TraceStep


@dataclass
class SLMAnalysisResult:
    """Outcome of SLM candidate analysis for a workflow action step."""

    is_slm_candidate: bool
    tier: str  # 'slm' or 'none'
    confidence: float = 1.0
    preferred_model: str = ""
    fallback_chain: List[str] = field(default_factory=lambda: ["frontier_llm", "human"])
    training_candidate: Optional[TrainingCandidate] = None
    prompt_template: Optional[str] = None
    reasoning: str = ""


class SLMAnalyzer:
    """Analyzer for identifying workflow steps suitable for SLM specialization.

    Detects narrow generative language tasks including:
    - Email intent extraction and classification
    - Customer support ticket and conversation summarization
    - Short renewal and commercial proposal drafting
    - General narrow structured text composition

    Generates structured SFT dataset pairs configured for fine-tuning
    1.5B/3B parameter student models (e.g., Qwen2.5-1.5B-Instruct, Llama-3.2-1B/3B).
    """

    # Generative task pattern specifications
    GENERATIVE_TASK_PATTERNS: Dict[str, Dict[str, Any]] = {
        "intent_extraction": {
            "keywords": [
                "intent",
                "extract_intent",
                "intent_extraction",
                "email_intent",
                "parse_intent",
                "classify_intent",
                "extract_intent_from_email",
                "email_intent_extraction",
                "intent_classifier",
            ],
            "instruction": "Extract the customer's intent, category, and key parameters from the email/text.",
            "default_system_prompt": (
                "You are a specialized SLM for intent extraction. "
                "Analyze the provided text and extract user intent and parameters accurately in structured format."
            ),
        },
        "support_summary": {
            "keywords": [
                "summar",
                "support_summary",
                "ticket_summary",
                "summarize_ticket",
                "summarize_support",
                "summarize_conversation",
                "support_notes_summary",
                "issue_summary",
                "case_summary",
                "recap",
                "digest",
            ],
            "instruction": "Summarize the customer support interaction, identifying the core issue and resolution.",
            "default_system_prompt": (
                "You are a specialized SLM for customer support summarization. "
                "Produce a concise, factual summary of the customer issue and resolution."
            ),
        },
        "proposal_drafting": {
            "keywords": [
                "draft_proposal",
                "short_proposal_drafting",
                "proposal_drafting",
                "draft_renewal_proposal",
                "draft_short_proposal",
                "draft_quote",
                "draft_offer",
                "compose_proposal",
                "generate_proposal",
                "proposal_generator",
            ],
            "instruction": "Draft a concise commercial proposal based on the customer contract and usage data.",
            "default_system_prompt": (
                "You are a specialized SLM for drafting commercial proposals. "
                "Generate clear, professional, and accurate proposal text following business constraints."
            ),
        },
        "email_drafting": {
            "keywords": [
                "draft_email",
                "draft_response",
                "draft_reply",
                "compose_email",
                "compose_response",
                "write_email",
                "generate_reply",
            ],
            "instruction": "Draft a professional email response addressing the customer's inquiry.",
            "default_system_prompt": (
                "You are a specialized SLM for customer communication. "
                "Draft helpful, clear, and context-aware responses."
            ),
        },
    }

    # Deterministic patterns that must be rejected from SLM distillation
    NON_SLM_KEYWORDS: Set[str] = {
        "calculate",
        "compute",
        "lookup",
        "search",
        "query",
        "fetch",
        "verify",
        "check",
        "validate",
        "price",
        "pricing",
        "tax",
        "discount",
        "ratio",
        "count",
        "sum",
    }

    def __init__(
        self,
        candidate_model_size: str = "1.5B",
        base_model: Optional[str] = None,
        default_base_model: Optional[str] = None,
        default_framework: str = "trl",
        default_trainer: str = "SFTTrainer",
        max_sample_display: int = 5,
    ) -> None:
        """Initialize the SLMAnalyzer.

        Args:
            candidate_model_size: Target student model parameter size (e.g., '1.5B', '3B', '7B').
            base_model: Base foundation model identifier (e.g., 'Qwen/Qwen2.5-1.5B-Instruct').
            default_base_model: Alias for base_model.
            default_framework: Fine-tuning framework ('trl', 'unsloth', 'axolotl').
            default_trainer: Fine-tuning trainer ('SFTTrainer', 'DPOTrainer').
            max_sample_display: Maximum number of SFT sample pairs to display in preview summary.
        """
        self.candidate_model_size = candidate_model_size
        self.base_model = base_model or default_base_model or "Qwen/Qwen2.5-1.5B-Instruct"
        self.default_base_model = self.base_model
        self.default_framework = default_framework
        self.default_trainer = default_trainer
        self.max_sample_display = max_sample_display

    def is_generative_task(self, action_name: str) -> bool:
        """Determine if an action represents a narrow generative language task."""
        if not action_name:
            return False
        act_lower = action_name.lower()

        # Match against known generative patterns first
        for pattern_info in self.GENERATIVE_TASK_PATTERNS.values():
            if any(kw in act_lower for kw in pattern_info["keywords"]):
                return True

        tokens = set(re.split(r"[._\s]+", act_lower))
        # Reject explicitly deterministic operations
        if any(non in tokens or non == act_lower for non in self.NON_SLM_KEYWORDS):
            return False

        # Fallback keywords
        general_gen_keywords = ["draft", "summar", "generate", "compose", "synthesize", "rewrite", "translate"]
        return any(g in act_lower for g in general_gen_keywords)

    def detect_task_type(self, action_name: str) -> Optional[str]:
        """Detect the specialized generative task type for an action."""
        if not action_name:
            return None
        act_lower = action_name.lower()

        for task_type, pattern_info in self.GENERATIVE_TASK_PATTERNS.items():
            if any(kw in act_lower for kw in pattern_info["keywords"]):
                return task_type

        tokens = set(re.split(r"[._\s]+", act_lower))
        if any(non in tokens or non == act_lower for non in self.NON_SLM_KEYWORDS):
            return None

        # Heuristic detection
        if "intent" in act_lower:
            return "intent_extraction"
        if "summar" in act_lower:
            return "support_summary"
        if "proposal" in act_lower or "quote" in act_lower:
            return "proposal_drafting"
        if "email" in act_lower or "reply" in act_lower or "draft" in act_lower:
            return "email_drafting"

        return None

    def analyze_steps(
        self, action_name: str, steps: List[Union[TraceStep, Dict[str, Any]]]
    ) -> Optional[Dict[str, Any]]:
        """Analyze trace steps for an action to generate an SLM distillation lowering spec.

        Args:
            action_name: The name of the action step.
            steps: List of TraceStep instances or step dictionaries.

        Returns:
            Dictionary containing SLM lowering target specifications and SFT pairs,
            or None if the steps do not qualify for SLM specialization.
        """
        if not action_name or not steps:
            return None

        if not self.is_generative_task(action_name):
            return None

        task_type = self.detect_task_type(action_name) or "general_generative"
        pattern_info = self.GENERATIVE_TASK_PATTERNS.get(task_type, {})
        instruction = pattern_info.get(
            "instruction",
            f"Execute generative task '{action_name}' accurately following provided input context.",
        )
        system_prompt = pattern_info.get(
            "default_system_prompt",
            f"You are a specialized SLM for {action_name.replace('_', ' ')}. Provide accurate, structured responses.",
        )

        sft_dataset: List[Dict[str, Any]] = []

        for step in steps:
            inp, out = self._extract_step_io(step)
            if not inp or not out:
                continue

            input_str = self._format_data_string(inp)
            output_str = self._format_data_string(out)

            if not input_str or not output_str:
                continue

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{instruction}\n\nContext:\n{input_str}"},
                {"role": "assistant", "content": output_str},
            ]

            sft_dataset.append(
                {
                    "instruction": instruction,
                    "input": input_str,
                    "output": output_str,
                    "messages": messages,
                }
            )

        if not sft_dataset:
            return None

        return {
            "target_executor": "slm",
            "candidate_model_size": self.candidate_model_size,
            "base_model": self.base_model,
            "task_type": task_type,
            "action_name": action_name,
            "sft_pairs_count": len(sft_dataset),
            "sft_dataset": sft_dataset,
            "sft_dataset_sample": sft_dataset[: self.max_sample_display],
            "framework": self.default_framework,
            "trainer": self.default_trainer,
        }

    def analyze_action(
        self,
        action_name: str,
        steps: Optional[List[TraceStep]] = None,
        target_name: str = "workflow",
        behaviors: Optional[List[Dict[str, Any]]] = None,
    ) -> SLMAnalysisResult:
        """Analyze an action step to determine if it is suitable for SLM distillation."""
        act_lower = action_name.lower()
        steps = steps or []
        behaviors = behaviors or []

        is_gen = self.is_generative_task(action_name)
        if is_gen:
            clean_action = action_name.replace("_", "-")
            preferred_model = f"models/{target_name}-{clean_action}-slm-v1"

            training_candidate = self.generate_training_candidate(
                action_name=action_name,
                steps=steps,
                target_name=target_name,
                base_model=self.base_model,
                behaviors=behaviors,
            )

            return SLMAnalysisResult(
                is_slm_candidate=True,
                tier="slm",
                confidence=0.95,
                preferred_model=preferred_model,
                fallback_chain=["frontier_llm", "human"],
                training_candidate=training_candidate,
                reasoning=f"Action '{action_name}' is a narrow generative language task distillable into a dedicated SLM",
            )

        return SLMAnalysisResult(
            is_slm_candidate=False,
            tier="none",
            confidence=0.0,
            preferred_model="",
            fallback_chain=["frontier_llm", "human"],
            training_candidate=None,
            reasoning=f"Action '{action_name}' did not match SLM generative patterns",
        )

    def generate_training_candidate(
        self,
        action_name: str,
        steps: List[TraceStep],
        target_name: str = "workflow",
        base_model: Optional[str] = None,
        behaviors: Optional[List[Dict[str, Any]]] = None,
    ) -> TrainingCandidate:
        """Generate a TrainingCandidate specification for fine-tuning via TRL/HuggingFace."""
        clean_action = action_name.replace("_", "-")
        target_slm_id = f"models/{target_name}-{clean_action}-slm-v1"
        base_m = base_model or self.base_model

        sft_pairs: List[Dict[str, str]] = []
        for step in steps:
            inp, out = self._extract_step_io(step)
            if inp and out:
                prompt_text = f"Action: {action_name}\nInput: {json.dumps(inp, ensure_ascii=False)}"
                completion_text = json.dumps(out, ensure_ascii=False) if isinstance(out, (dict, list)) else str(out)
                sft_pairs.append({"prompt": prompt_text, "completion": completion_text})

        task_type = self.detect_task_type(action_name) or "general_generative"
        template = f"Context: {{input}}\nExecute {task_type} adhering to business contracts."

        invariants: List[str] = []
        if behaviors:
            for b in behaviors:
                b_name = b.get("name", "")
                if b_name:
                    invariants.append(b_name)

        return TrainingCandidate(
            action_name=action_name,
            candidate_id=target_slm_id,
            target_executor_type="slm",
            base_model=base_m,
            framework=self.default_framework,
            trainer=self.default_trainer,
            dataset={"samples": sft_pairs, "num_samples": len(sft_pairs), "task_type": task_type},
            hyperparameters={"learning_rate": 2e-4, "epochs": 3, "lora_r": 16, "lora_alpha": 32},
            behavior_invariants=invariants,
            promotion_gate={"min_quality": 0.95, "min_behavior_compliance": 1.0, "max_latency_ms": 1500.0},
            metadata={"workflow": target_name, "prompt_template": template},
        )

    def _extract_step_io(
        self, step: Union[TraceStep, Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], Any]:
        """Extract input and output data from a TraceStep or dict."""
        if isinstance(step, dict):
            inp = step.get("input") or {}
            out = step.get("output") or {}
            return inp, out

        inp = getattr(step, "input", {}) or {}
        out = getattr(step, "output", {}) or {}

        if hasattr(inp, "model_dump"):
            inp = inp.model_dump()
        elif hasattr(inp, "to_dict"):
            inp = inp.to_dict()

        if hasattr(out, "model_dump"):
            out = out.model_dump()
        elif hasattr(out, "to_dict"):
            out = out.to_dict()

        return dict(inp) if isinstance(inp, dict) else {}, out

    def _format_data_string(self, data: Any) -> str:
        """Format input or output data into string representation."""
        if isinstance(data, str):
            return data.strip()
        if isinstance(data, dict):
            if not data:
                return ""
            # If dict has a single prominent text key
            for k in ("email", "transcript", "text", "message", "body", "proposal", "summary", "content"):
                if k in data and isinstance(data[k], str):
                    extra = {k2: v2 for k2, v2 in data.items() if k2 != k}
                    if extra:
                        return f"{data[k]}\n\nMetadata: {json.dumps(extra, ensure_ascii=False)}"
                    return data[k]
            return json.dumps(data, indent=2, ensure_ascii=False)
        if isinstance(data, (list, int, float, bool)):
            return json.dumps(data, ensure_ascii=False)
        return str(data)
