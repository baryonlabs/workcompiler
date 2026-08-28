"""Work Compiler engine for OpenWorkflow.

Decomposes recorded agent execution traces, discovers state machine states,
detects causal and behavioral action dependencies, extracts process invariants,
integrates middle-end analyzers (Determinism, Prediction, SLM), and synthesizes
deterministic Work IR specifications lowering steps across the 8-tier executor hierarchy.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from core.compiler.analyzers.determinism import (
    DeterminismAnalysisResult,
    DeterminismAnalyzer,
)
from core.compiler.analyzers.prediction import (
    PredictionAnalysisResult,
    PredictionAnalyzer,
)
from core.compiler.analyzers.slm import (
    SLMAnalysisResult,
    SLMAnalyzer,
)
from core.optimizer.optimizer import TrainingCandidate
from core.validation.classifier import (
    BehaviorCategory,
    classify_behavior,
)
from core.work_ir.work_ir import (
    BehaviorRef,
    ExecutorConfig,
    ExecutorType,
    WorkIR,
)
from protocols.traces.trace_ir import TraceIR, TraceStep


class WorkCompiler:
    """Compiles agent execution traces and behavior contracts into executable Work IR.

    Integrates DeterminismAnalyzer, PredictionAnalyzer, and SLMAnalyzer to automatically
    lower workflow steps across the 8-tier executor hierarchy:
      - Priority 1 (Model Elimination): Constant / Lookup -> SQL -> Rule -> Deterministic Code
      - Priority 2 (Model Lowering): Traditional ML -> Vector RAG -> Distilled SLM
      - Priority 3 (Residual Execution): Frontier LLM -> Human-in-the-Loop
    """

    def __init__(
        self,
        default_quality: Optional[Dict[str, str]] = None,
        default_escalation: Optional[Dict[str, str]] = None,
        determinism_analyzer: Optional[DeterminismAnalyzer] = None,
        prediction_analyzer: Optional[PredictionAnalyzer] = None,
        slm_analyzer: Optional[SLMAnalyzer] = None,
    ) -> None:
        self.default_quality = default_quality or {
            "reviewer_acceptance": ">=0.95",
            "factual_accuracy": ">=0.99",
        }
        self.default_escalation = default_escalation or {
            "on_error": "fallback_to_frontier_llm",
            "on_quality_drop": "require_human_review",
            "on_timeout": "escalate_to_human",
        }
        self.determinism_analyzer = determinism_analyzer or DeterminismAnalyzer()
        self.prediction_analyzer = prediction_analyzer or PredictionAnalyzer()
        self.slm_analyzer = slm_analyzer or SLMAnalyzer()
        self.training_candidates: Dict[str, TrainingCandidate] = {}

    def compile_traces_to_work_ir(
        self,
        traces: List[TraceIR | Dict[str, Any]],
        behaviors: List[Dict[str, Any]],
        target_name: str,
        description: str = "",
    ) -> WorkIR:
        """Compile agent execution traces and behavior contracts into a WorkIR instance.

        Args:
            traces: List of TraceIR objects or dictionaries representing agent trajectories.
            behaviors: List of parsed AgentBehavior dictionaries.
            target_name: Unique identifier for the compiled work (e.g. 'customer-renewal').
            description: Optional human-readable description.

        Returns:
            WorkIR instance ready for durable runtime execution or YAML export.
        """
        # Normalize traces to TraceIR instances
        normalized_traces: List[TraceIR] = []
        for t in traces:
            if isinstance(t, dict):
                normalized_traces.append(TraceIR.from_dict(t))
            elif isinstance(t, TraceIR):
                normalized_traces.append(t)

        # Index steps by normalized action name across all traces
        steps_by_action: Dict[str, List[TraceStep]] = defaultdict(list)
        for trace in normalized_traces:
            for step in trace.steps:
                if step.action:
                    norm_act = self._normalize_action_name(step.action)
                    steps_by_action[norm_act].append(step)

        # 1. Decompose steps across all traces
        actions, action_handlers = self._decompose_actions(normalized_traces)
        inputs = self._extract_inputs(normalized_traces)
        outputs = self._extract_outputs(normalized_traces)

        # 2. Discover durable state machine states
        states = self.discover_states(actions)

        # 3. Detect action dependencies (temporal DAG + behavior constraints)
        dependencies = self.detect_dependencies(normalized_traces, behaviors, actions)

        # 4. Extract process invariants and behavior references
        invariants, behavior_refs = self.extract_invariants(behaviors)

        # 5. Synthesize executor routing across the 8-tier hierarchy
        executors = self.synthesize_executors(
            actions=actions,
            action_handlers=action_handlers,
            behaviors=behaviors,
            target_name=target_name,
            steps_by_action=steps_by_action,
        )

        if not description:
            description = f"Compiled workflow for automating {target_name.replace('-', ' ')}"

        return WorkIR(
            work=target_name,
            version="3.0",
            description=description,
            inputs=inputs,
            outputs=outputs,
            states=states,
            actions=actions,
            dependencies=dependencies,
            invariants=invariants,
            quality=dict(self.default_quality),
            behaviors=behavior_refs,
            escalation=dict(self.default_escalation),
            executors=executors,
        )

    def _normalize_action_name(self, raw_action: str) -> str:
        """Normalize raw action string to a clean identifier.

        Examples:
            'crm.lookup_contract' -> 'lookup_contract'
            'services.usage.calculate' -> 'calculate_usage'
            'connectors.email.send' -> 'send_email'
            'draft_proposal' -> 'draft_proposal'
        """
        if not raw_action:
            return ""

        parts = [p.strip().lower() for p in raw_action.split(".") if p.strip()]
        if not parts:
            return ""

        last = parts[-1]
        # If the last segment has an underscore (e.g. lookup_contract, send_email)
        if "_" in last:
            return re.sub(r"[^\w]+", "_", last)

        # If last segment is a common verb and second-to-last exists
        verbs = {
            "calculate", "compute", "send", "search", "query", "get", "lookup",
            "fetch", "check", "verify", "price", "classify", "predict", "score", "draft"
        }
        if len(parts) >= 2 and last in verbs:
            prev = parts[-2]
            return f"{last}_{prev}"
        elif len(parts) >= 2 and parts[-2] in verbs:
            return f"{parts[-2]}_{last}"

        return re.sub(r"[^\w]+", "_", last)

    def _decompose_actions(
        self, traces: List[TraceIR]
    ) -> Tuple[List[str], Dict[str, str]]:
        """Decompose atomic action steps and record handler paths."""
        action_order: List[str] = []
        seen_actions: Set[str] = set()
        action_handlers: Dict[str, str] = {}

        for trace in traces:
            for step in trace.steps:
                if not step.action:
                    continue
                norm_action = self._normalize_action_name(step.action)
                if norm_action not in seen_actions:
                    seen_actions.add(norm_action)
                    action_order.append(norm_action)

                # Track handler path cleanly without duplicate prefixes
                if norm_action not in action_handlers:
                    raw = step.action.strip()
                    if (
                        raw.startswith("connectors.")
                        or raw.startswith("services.")
                        or raw.startswith("rules.")
                        or raw.startswith("models.")
                        or raw.startswith("surfaces.")
                    ):
                        action_handlers[norm_action] = raw
                    elif "." in raw:
                        if raw.startswith("crm.") or raw.startswith("email.") or raw.startswith("db."):
                            action_handlers[norm_action] = f"connectors.{raw}"
                        elif raw.startswith("usage.") or raw.startswith("billing."):
                            action_handlers[norm_action] = f"services.{raw}"
                        elif raw.startswith("pricing_"):
                            action_handlers[norm_action] = f"rules.{raw}"
                        elif raw.startswith("ml."):
                            action_handlers[norm_action] = f"models.{raw}"
                        else:
                            action_handlers[norm_action] = f"connectors.{raw}"
                    else:
                        action_handlers[norm_action] = f"services.{norm_action}"

        return action_order, action_handlers

    def _extract_inputs(self, traces: List[TraceIR]) -> List[str]:
        """Extract workflow input parameters from initial steps across traces."""
        input_keys: List[str] = []
        seen_keys: Set[str] = set()

        for trace in traces:
            if not trace.steps:
                continue
            first_step = trace.steps[0]
            if first_step.input and isinstance(first_step.input, dict):
                for k in first_step.input.keys():
                    clean_k = str(k).strip()
                    if clean_k and clean_k not in seen_keys:
                        seen_keys.add(clean_k)
                        input_keys.append(clean_k)

        # Fallback if no trace steps had explicit input keys
        if not input_keys:
            input_keys = ["customer_id"]

        return input_keys

    def _extract_outputs(self, traces: List[TraceIR]) -> List[str]:
        """Extract workflow output parameters or artifacts from traces."""
        output_keys: List[str] = []
        seen_keys: Set[str] = set()

        for trace in traces:
            for art in trace.artifacts:
                art_name = art.split("/")[-1].replace(".", "_")
                if art_name not in seen_keys:
                    seen_keys.add(art_name)
                    output_keys.append(art_name)

            if trace.steps:
                last_step = trace.steps[-1]
                if last_step.output and isinstance(last_step.output, dict):
                    for k in last_step.output.keys():
                        clean_k = str(k).strip()
                        if clean_k and clean_k not in seen_keys:
                            seen_keys.add(clean_k)
                            output_keys.append(clean_k)

        # Default fallback if no explicit outputs found
        if not output_keys:
            output_keys = ["renewal_proposal_pdf"]

        return output_keys

    def discover_states(self, actions: List[str]) -> List[str]:
        """Discover durable state machine states corresponding to action progression.

        Converts actions (e.g. 'lookup_contract', 'calculate_usage', 'draft_proposal', 'send_email')
        into past-tense state machine states ('contract_verified', 'usage_calculated', etc.).
        """
        states: List[str] = ["initialized"]

        state_mapping = {
            "lookup_contract": "contract_verified",
            "verify_contract": "contract_verified",
            "search_crm": "crm_queried",
            "calculate_usage": "usage_calculated",
            "price_offer": "offer_priced",
            "classify_ticket": "ticket_classified",
            "score_risk": "risk_scored",
            "draft_proposal": "proposal_drafted",
            "review_proposal": "proposal_reviewed",
            "approve": "approved",
            "require_approval": "approved",
            "send_email": "sent",
            "send_notification": "sent",
        }

        for action in actions:
            if action in state_mapping:
                state_name = state_mapping[action]
            elif "price" in action or "pricing" in action:
                state_name = "offer_priced"
            elif "usage" in action and ("calc" in action or "compute" in action):
                state_name = "usage_calculated"
            elif "contract" in action and ("lookup" in action or "verify" in action):
                state_name = "contract_verified"
            elif "email" in action and "send" in action:
                state_name = "sent"
            else:
                # Heuristic: convert 'verb_noun' to 'noun_verbed' or 'action_completed'
                clean_act = re.sub(r"_v\d+$", "", action)
                parts = clean_act.split("_")
                if len(parts) == 2:
                    verb, noun = parts[0], parts[1]
                    if verb.endswith("e"):
                        verbed = verb + "d"
                    elif not verb.endswith("ed"):
                        verbed = verb + "ed"
                    else:
                        verbed = verb
                    state_name = f"{noun}_{verbed}"
                else:
                    state_name = f"{action}_completed"

            if state_name not in states:
                states.append(state_name)

        return states

    def detect_dependencies(
        self,
        traces: List[TraceIR],
        behaviors: List[Dict[str, Any]],
        actions: List[str],
    ) -> Dict[str, List[str]]:
        """Detect action dependencies combining sequential trace ordering and behavior contracts.

        Args:
            traces: List of TraceIR objects.
            behaviors: List of behavior contract dictionaries.
            actions: List of canonical action names.

        Returns:
            Dictionary mapping each action to its list of prerequisite action names.
        """
        dependencies: Dict[str, List[str]] = defaultdict(list)
        action_indices = {act: idx for idx, act in enumerate(actions)}

        # 1. Detect sequential pipeline dependencies from traces
        for trace in traces:
            trace_actions = [
                self._normalize_action_name(step.action)
                for step in trace.steps
                if step.action
            ]
            for i in range(1, len(trace_actions)):
                prev_act = trace_actions[i - 1]
                curr_act = trace_actions[i]
                if prev_act != curr_act and prev_act in action_indices and curr_act in action_indices:
                    if prev_act not in dependencies[curr_act]:
                        dependencies[curr_act].append(prev_act)

        # If no traces provided sequential pairs, construct default linear chain
        if not dependencies and len(actions) > 1:
            for i in range(1, len(actions)):
                dependencies[actions[i]].append(actions[i - 1])

        # 2. Inject explicit constraints from Workflow Transition behaviors
        for behavior in behaviors:
            classification = classify_behavior(behavior)
            if classification.category == BehaviorCategory.WORKFLOW_TRANSITION:
                evidence_text = f"{behavior.get('evidence', '')} {behavior.get('intent', '')}"
                for act_a in actions:
                    for act_b in actions:
                        if act_a == act_b:
                            continue
                        pat = rf"{act_a}.*?(?:before|prior to|preceding).*?{act_b}"
                        if re.search(pat, evidence_text, re.IGNORECASE):
                            if act_a not in dependencies[act_b]:
                                dependencies[act_b].append(act_a)

        # 3. Transitive reduction: keep DAG sparse and eliminate redundant transitive edges
        clean_deps: Dict[str, List[str]] = {}
        for act in actions:
            if act in dependencies and dependencies[act]:
                clean_deps[act] = sorted(
                    dependencies[act], key=lambda x: action_indices.get(x, 0)
                )

        return clean_deps

    def extract_invariants(
        self, behaviors: List[Dict[str, Any]]
    ) -> Tuple[List[str], List[BehaviorRef]]:
        """Extract non-removable invariants and behavior references from behavior contracts.

        Args:
            behaviors: List of parsed AgentBehavior dictionaries.

        Returns:
            Tuple of (invariants list, behavior references list).
        """
        invariants: List[str] = []
        behavior_refs: List[BehaviorRef] = []
        seen_invariants: Set[str] = set()

        for b in behaviors:
            raw_name = b.get("name", "")
            if not raw_name:
                continue

            inv_key = re.sub(r"[^\w]+", "_", raw_name.strip().lower())
            if inv_key not in seen_invariants:
                seen_invariants.add(inv_key)
                invariants.append(inv_key)

            behavior_path = b.get("path") or f"behaviors/{raw_name}/BEHAVIOR.md"
            behavior_refs.append(BehaviorRef(name=raw_name, path=behavior_path))

        return invariants, behavior_refs

    def synthesize_executors(
        self,
        actions: List[str],
        action_handlers: Dict[str, str],
        behaviors: List[Dict[str, Any]],
        target_name: str,
        steps_by_action: Optional[Dict[str, List[TraceStep]]] = None,
    ) -> Dict[str, ExecutorConfig]:
        """Synthesize executor configurations lowering each action step across the 8-tier hierarchy.

        8-Tier Lowering Pipeline:
          1. Human Approval / Review Gate (Tier 9)
          2. Model Elimination (Tiers 1-4: Constant, SQL, Rule, Code/HTTP) via DeterminismAnalyzer
          3. Model Lowering (Tiers 5-7: Traditional ML, Vector RAG, Distilled SLM) via Prediction & SLM Analyzers
          4. Residual Frontier LLM (Tier 8)

        Args:
            actions: List of canonical action names.
            action_handlers: Inferred or declared handler module paths.
            behaviors: Attached behavior contracts.
            target_name: Workflow identifier.
            steps_by_action: Optional mapping of action names to recorded trace steps.

        Returns:
            Dictionary mapping action names to ExecutorConfig instances.
        """
        executors: Dict[str, ExecutorConfig] = {}
        steps_map = steps_by_action or {}

        for action in actions:
            action_steps = steps_map.get(action, [])
            default_handler = action_handlers.get(action, "")
            executor_cfg = self.lower_action(
                action_name=action,
                default_handler=default_handler,
                behaviors=behaviors,
                target_name=target_name,
                steps=action_steps,
            )
            executors[action] = executor_cfg

        return executors

    def lower_action(
        self,
        action_name: str,
        default_handler: str,
        behaviors: List[Dict[str, Any]],
        target_name: str,
        steps: Optional[List[TraceStep]] = None,
    ) -> ExecutorConfig:
        """Lower an individual workflow action to the optimal tier in the 8-tier executor hierarchy.

        Args:
            action_name: Canonical name of the action step.
            default_handler: Inferred or declared handler path.
            behaviors: Attached behavior contracts.
            target_name: Workflow identifier.
            steps: Optional list of recorded trace steps.

        Returns:
            Lowered ExecutorConfig instance.
        """
        act_lower = action_name.lower()
        steps = steps or []

        # Tier 9: Human-in-the-Loop Gate (Approval, Review, Manual Intervention)
        if any(k in act_lower for k in ("approve", "review", "manual", "human_gate")):
            handler_path = default_handler or f"surfaces.approvals.{action_name}"
            return ExecutorConfig(
                type=ExecutorType.HUMAN,
                handler=handler_path,
            )

        # Priority 1: Model Elimination (Tiers 1-4 via DeterminismAnalyzer)
        det_result = self.determinism_analyzer.analyze_action(
            action_name=action_name,
            steps=steps,
            behaviors=behaviors,
        )

        if det_result.is_deterministic:
            if det_result.tier == "rule":
                handler = default_handler if default_handler.startswith("rules.") else (det_result.handler or f"rules.{action_name}")
                return ExecutorConfig(
                    type=ExecutorType.RULE,
                    handler=handler,
                )
            elif det_result.tier == "constant" or det_result.tier == "sql":
                handler = default_handler or det_result.handler or f"connectors.{action_name}"
                return ExecutorConfig(
                    type=ExecutorType.CODE,
                    handler=handler,
                )
            elif det_result.tier == "http":
                handler = default_handler or det_result.handler or f"connectors.{action_name}"
                return ExecutorConfig(
                    type=ExecutorType.CODE,
                    handler=handler,
                )
            else:  # tier == "code"
                handler = default_handler or det_result.handler or f"services.{action_name}"
                return ExecutorConfig(
                    type=ExecutorType.CODE,
                    handler=handler,
                )

        # Priority 2: Model Lowering (Tiers 5-7 via PredictionAnalyzer & SLMAnalyzer)
        pred_result = self.prediction_analyzer.analyze_action(
            action_name=action_name,
            steps=steps,
            behaviors=behaviors,
        )

        if pred_result.is_predictive:
            if pred_result.tier == "ml":
                handler = default_handler or pred_result.handler or f"models.ml.{action_name}"
                preferred_model = f"models/ml/{target_name}-{action_name.replace('_', '-')}-xgb"
                return ExecutorConfig(
                    type=ExecutorType.ML,
                    handler=handler,
                    preferred=preferred_model,
                )
            elif pred_result.tier == "vector":
                handler = default_handler or pred_result.handler or f"connectors.vector.{action_name}"
                return ExecutorConfig(
                    type=ExecutorType.CODE,
                    handler=handler,
                )

        slm_result = self.slm_analyzer.analyze_action(
            action_name=action_name,
            steps=steps,
            target_name=target_name,
            behaviors=behaviors,
        )

        if slm_result.is_slm_candidate:
            if slm_result.training_candidate:
                self.training_candidates[action_name] = slm_result.training_candidate
            return ExecutorConfig(
                type=ExecutorType.SLM,
                preferred=slm_result.preferred_model,
                fallback=slm_result.fallback_chain,
            )

        # Priority 3: Residual Execution (Tier 8: Frontier LLM Fallback)
        return ExecutorConfig(
            type=ExecutorType.FRONTIER_LLM,
            preferred="claude-3-5-sonnet",
            fallback=["human"],
        )
