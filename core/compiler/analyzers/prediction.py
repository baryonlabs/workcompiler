"""Prediction Analyzer for OpenWorkflow WorkCompiler.

Detects traditional Machine Learning (ML) execution candidates from recorded
agent trace steps: structured inputs, finite categorical labels, or numerical
score outputs (e.g. ticket classification, fraud check, lead score, priority rating).
Lowers qualifying steps to the ML execution tier (Scikit-Learn / XGBoost).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple, Union

try:
    from protocols.traces.trace_ir import TraceIR, TraceStep
except ImportError:  # pragma: no cover
    from core.work_ir.trace_ir import TraceIR, TraceStep  # type: ignore[assignment]


@dataclass
class PredictionAnalysisResult:
    """Outcome of prediction and ML lowering analysis for an action step."""

    is_predictive: bool
    tier: str  # 'ml', 'vector', or 'none'
    confidence: float = 1.0
    model_type: str = "scikit_learn"
    handler: Optional[str] = None
    training_samples_count: int = 0
    extracted_dataset: Optional[Dict[str, Any]] = None
    reasoning: str = ""


class PredictionAnalyzer:
    """Analyzes agent trace steps to detect traditional Machine Learning lowering candidates.

    Examines step inputs and outputs across trace executions to identify:
    1. Structured tabular features (numbers, booleans, categories, discrete strings).
    2. Finite categorical classification targets (e.g., ticket categories, fraud flags, churn tiers).
    3. Numerical score / continuous regression targets (e.g., lead scores, priority ratings, risk scores).

    When candidate patterns are detected, returns an ML lowering target dictionary
    specifying the target executor, model framework (Scikit-Learn or XGBoost),
    extracted feature names, label space, and training sample count.
    """

    # Keywords commonly identifying classification or prediction targets
    CLASSIFICATION_KEYWORDS: Set[str] = {
        "category",
        "label",
        "class",
        "classification",
        "tier",
        "tag",
        "segment",
        "type",
        "status",
        "decision",
        "intent",
        "topic",
        "department",
        "fraud",
        "is_fraud",
        "churn",
        "is_churn",
        "priority",
        "urgency",
        "risk_level",
        "sentiment",
        "prediction",
        "target",
        "is_",
        "has_",
    }

    # Keywords commonly identifying continuous numerical scores or ratings
    SCORE_KEYWORDS: Set[str] = {
        "score",
        "rating",
        "risk_score",
        "lead_score",
        "fraud_score",
        "priority_rating",
        "probability",
        "prob",
        "confidence",
        "risk",
        "pct",
        "percent",
        "amount",
        "value",
        "price",
        "estimate",
        "cost",
    }

    # Keywords indicating vector / embedding retrieval (RAG)
    VECTOR_KEYWORDS: Set[str] = {
        "vector_search",
        "semantic_search",
        "rag_retrieve",
        "embedding_lookup",
        "find_similar",
        "similarity_search",
        "vector_query",
        "retrieve_documents",
    }

    def __init__(
        self,
        min_samples: int = 2,
        max_categorical_cardinality: int = 50,
        max_text_feature_length: int = 500,
        max_output_text_length: int = 150,
        default_tabular_model: str = "xgboost",
        default_text_model: str = "scikit_learn",
    ) -> None:
        """Initialize the PredictionAnalyzer.

        Args:
            min_samples: Minimum number of step executions required to perform analysis.
            max_categorical_cardinality: Maximum number of unique classes for categorical targets.
            max_text_feature_length: Maximum length of string values considered structured features.
            max_output_text_length: Maximum length of string output before considering it generative text.
            default_tabular_model: Preferred model framework for numerical/tabular features ('xgboost').
            default_text_model: Preferred model framework for text/discrete classification ('scikit_learn').
        """
        self.min_samples = min_samples
        self.max_categorical_cardinality = max_categorical_cardinality
        self.max_text_feature_length = max_text_feature_length
        self.max_output_text_length = max_output_text_length
        self.default_tabular_model = default_tabular_model
        self.default_text_model = default_text_model

    def analyze_steps(
        self, action_name: str, steps: List[Union[TraceStep, Dict[str, Any]]]
    ) -> Optional[Dict[str, Any]]:
        """Analyze execution steps for an action to determine if it is an ML prediction candidate.

        Args:
            action_name: The name or identifier of the action being analyzed.
            steps: List of TraceStep instances or dicts recorded for this action.

        Returns:
            A lowering target dictionary if the action qualifies for ML execution:
            {
                "target_executor": "ml",
                "model_type": "scikit_learn" | "xgboost",
                "task_type": "classification" | "regression",
                "feature_names": list[str],
                "label_space": list[Any] | None,
                "training_sample_count": int,
                "target_field": str,
                "action_name": str,
            }
            Returns None if the action is not a traditional ML candidate.
        """
        if not steps:
            return None

        # Filter steps matching action_name if provided
        matching_steps = self._filter_action_steps(action_name, steps)
        if len(matching_steps) < self.min_samples:
            return None

        # 1. Extract and validate structured input features across steps
        feature_sets: List[Dict[str, Any]] = []
        for s in matching_steps:
            _, inp, _ = self._extract_step_info(s)
            features = self._extract_features(inp)
            if not features:
                return None
            feature_sets.append(features)

        all_feature_keys: Set[str] = set()
        for f in feature_sets:
            all_feature_keys.update(f.keys())

        if not all_feature_keys:
            return None

        feature_names = sorted(list(all_feature_keys))

        # 2. Identify the target output field and determine candidate task type
        target_info = self._identify_target(matching_steps)
        if target_info is None:
            return None

        target_field, task_type, label_space, target_values = target_info

        # 3. Determine recommended model type (scikit_learn vs xgboost)
        model_type = self._recommend_model_type(
            task_type=task_type,
            feature_sets=feature_sets,
            target_values=target_values,
        )

        return {
            "target_executor": "ml",
            "model_type": model_type,
            "task_type": task_type,
            "feature_names": feature_names,
            "label_space": label_space,
            "training_sample_count": len(matching_steps),
            "target_field": target_field,
            "action_name": action_name,
        }

    def analyze_action(
        self,
        action_name: str,
        steps: Optional[List[Union[TraceStep, Dict[str, Any]]]] = None,
        behaviors: Optional[List[Dict[str, Any]]] = None,
    ) -> PredictionAnalysisResult:
        """Analyze action characteristics for ML or vector retrieval lowering.

        Args:
            action_name: Canonical name of the action step.
            steps: Optional list of recorded TraceStep instances for this action.
            behaviors: Optional list of behavior specifications.

        Returns:
            PredictionAnalysisResult containing lowering tier, model type, and metadata.
        """
        act_lower = action_name.lower()
        steps = steps or []

        # Check Vector Retrieval Keywords
        if any(k in act_lower for k in self.VECTOR_KEYWORDS):
            return PredictionAnalysisResult(
                is_predictive=True,
                tier="vector",
                confidence=0.95,
                model_type="vector_search",
                handler=f"connectors.vector.{action_name}",
                reasoning=f"Action '{action_name}' matches vector/embedding semantic search pattern",
            )

        analysis = self.analyze_steps(action_name, steps) if steps else None
        if analysis is not None:
            return PredictionAnalysisResult(
                is_predictive=True,
                tier="ml",
                confidence=0.95,
                model_type=analysis["model_type"],
                handler=f"models.ml.{action_name}",
                training_samples_count=analysis["training_sample_count"],
                extracted_dataset=None,
                reasoning=f"Action '{action_name}' matches {analysis['task_type']} pattern on {len(analysis['feature_names'])} structured features",
            )

        # Keyword-based ML fallback for single-trace or cold-start compilation
        ml_action_keywords = {
            "classify", "classification", "predict", "prediction", "score", "scoring",
            "rank", "ranking", "categorize", "categorization", "churn", "fraud",
            "sentiment", "priority_rating", "risk_score"
        }
        if any(k in act_lower for k in ml_action_keywords):
            return PredictionAnalysisResult(
                is_predictive=True,
                tier="ml",
                confidence=0.90,
                model_type=self.default_text_model,
                handler=f"models.ml.{action_name}",
                training_samples_count=len(steps),
                extracted_dataset=None,
                reasoning=f"Action '{action_name}' matches statistical ML classification/scoring pattern",
            )

        return PredictionAnalysisResult(
            is_predictive=False,
            tier="none",
            confidence=0.0,
            model_type="",
            handler=None,
            training_samples_count=0,
            extracted_dataset=None,
            reasoning=f"Action '{action_name}' did not match statistical prediction or ML patterns",
        )

    def analyze_trace(self, trace: Union[TraceIR, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Analyze all distinct actions within a single trace for ML candidates.

        Args:
            trace: A TraceIR instance or trace dictionary.

        Returns:
            Dictionary mapping candidate action names to their lowering target dictionaries.
        """
        return self.analyze_traces([trace])

    def analyze_traces(
        self, traces: List[Union[TraceIR, Dict[str, Any]]]
    ) -> Dict[str, Dict[str, Any]]:
        """Analyze steps grouped by action across multiple traces.

        Args:
            traces: List of TraceIR instances or trace dictionaries.

        Returns:
            Dictionary mapping candidate action names to their lowering target dictionaries.
        """
        steps_by_action: Dict[str, List[Any]] = {}
        for trace in traces:
            raw_steps = (
                trace.get("steps", [])
                if isinstance(trace, dict)
                else getattr(trace, "steps", [])
            )
            for step in raw_steps:
                action, _, _ = self._extract_step_info(step)
                if not action:
                    continue
                norm_action = self._normalize_action_name(action)
                if norm_action not in steps_by_action:
                    steps_by_action[norm_action] = []
                steps_by_action[norm_action].append(step)

        results: Dict[str, Dict[str, Any]] = {}
        for action_name, steps in steps_by_action.items():
            analysis = self.analyze_steps(action_name, steps)
            if analysis is not None:
                results[action_name] = analysis

        return results

    def extract_training_dataset(
        self,
        action_name_or_steps: Union[str, List[Union[TraceStep, Dict[str, Any]]]],
        steps: Optional[List[Union[TraceStep, Dict[str, Any]]]] = None,
    ) -> Optional[Union[Tuple[List[Dict[str, Any]], List[Any]], Dict[str, Any]]]:
        """Extract paired (X_features, y_target) dataset ready for model training.

        Can be called as:
        1. extract_training_dataset(action_name, steps) -> Optional[Tuple[list[dict], list[Any]]]
        2. extract_training_dataset(steps) -> Dict[str, Any] with 'features', 'targets', 'num_samples'

        Args:
            action_name_or_steps: Either action name string or list of steps.
            steps: Optional list of steps when first argument is action name.

        Returns:
            Tuple of (features_list, targets_list), or dataset dictionary, or None.
        """
        if isinstance(action_name_or_steps, str):
            action_name = action_name_or_steps
            step_list = steps or []
            analysis = self.analyze_steps(action_name, step_list)
            if analysis is None:
                return None

            target_field = analysis["target_field"]
            matching_steps = self._filter_action_steps(action_name, step_list)

            X: List[Dict[str, Any]] = []
            y: List[Any] = []

            for step in matching_steps:
                _, inp, out = self._extract_step_info(step)
                features = self._extract_features(inp)
                target_val = self._extract_field_value(out, target_field)
                if target_val is not None:
                    X.append(features)
                    y.append(target_val)

            return X, y

        # Single argument: list of steps
        step_list = action_name_or_steps
        features_list: List[Dict[str, Any]] = []
        targets_list: List[Any] = []

        if not step_list:
            return {"features": [], "targets": [], "num_samples": 0}

        first_action, _, _ = self._extract_step_info(step_list[0])
        extracted = self.extract_training_dataset(first_action or "action", step_list)
        if extracted is not None and isinstance(extracted, tuple):
            X_data, y_data = extracted
            return {
                "features": X_data,
                "targets": y_data,
                "num_samples": len(X_data),
            }

        return {"features": [], "targets": [], "num_samples": 0}

    def is_predictive(
        self,
        action_name: str,
        steps: Optional[List[Union[TraceStep, Dict[str, Any]]]] = None,
    ) -> bool:
        """Helper returning True if action is detected as predictive ML task."""
        res = self.analyze_action(action_name, steps)
        return res.is_predictive

    def detect_tier(
        self,
        action_name: str,
        steps: Optional[List[Union[TraceStep, Dict[str, Any]]]] = None,
    ) -> Optional[str]:
        """Helper returning detected lowering tier ('ml' or 'vector') if predictive, else None."""
        res = self.analyze_action(action_name, steps)
        return res.tier if res.is_predictive else None

    def _extract_step_info(
        self, step: Any
    ) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        """Extract (action, input, output) from step object or dictionary."""
        if isinstance(step, dict):
            action = step.get("action", "")
            inp = step.get("input") or {}
            out = step.get("output") or {}
            return str(action), dict(inp), dict(out)

        action = getattr(step, "action", "")
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

        return str(action), dict(inp), dict(out)

    def _filter_action_steps(
        self, action_name: str, steps: List[Any]
    ) -> List[Any]:
        """Filter steps matching the given action name."""
        norm_target = self._normalize_action_name(action_name)
        matching: List[Any] = []
        for s in steps:
            action, _, _ = self._extract_step_info(s)
            if not action or action == action_name or self._normalize_action_name(action) == norm_target:
                matching.append(s)

        # If no explicit matches found, fallback to all steps
        return matching if matching else steps

    def _normalize_action_name(self, raw_action: str) -> str:
        """Normalize action string to standard snake_case identifier."""
        if not raw_action:
            return ""
        parts = [p.strip().lower() for p in raw_action.split(".") if p.strip()]
        if not parts:
            return ""
        last = parts[-1]
        if "_" in last:
            return re.sub(r"[^\w]+", "_", last)
        verbs = {
            "calculate",
            "compute",
            "send",
            "search",
            "query",
            "get",
            "lookup",
            "fetch",
            "check",
            "verify",
            "price",
            "classify",
            "score",
            "rate",
            "predict",
        }
        if len(parts) >= 2 and last in verbs:
            return f"{last}_{parts[-2]}"
        elif len(parts) >= 2 and parts[-2] in verbs:
            return f"{parts[-2]}_{last}"
        return re.sub(r"[^\w]+", "_", last)

    def _extract_features(self, data: Any, prefix: str = "") -> Dict[str, Any]:
        """Extract and flatten structured tabular feature fields from input data.

        Scalar primitives (int, float, bool, short string) are retained.
        Long unstructured text, binary data, or complex objects are excluded.
        """
        features: Dict[str, Any] = {}
        if not isinstance(data, dict):
            return features

        for key, val in data.items():
            full_key = f"{prefix}.{key}" if prefix else str(key)

            if isinstance(val, dict):
                nested = self._extract_features(val, prefix=full_key)
                features.update(nested)
            elif isinstance(val, bool):
                features[full_key] = val
            elif isinstance(val, (int, float)):
                features[full_key] = val
            elif isinstance(val, str):
                clean_str = val.strip()
                if len(clean_str) <= self.max_text_feature_length and "\n\n" not in clean_str:
                    features[full_key] = clean_str

        return features

    def _extract_field_value(self, data: Any, field_path: str) -> Any:
        """Retrieve a field value from nested dict using dot-notation path."""
        if not isinstance(data, dict):
            return None
        parts = field_path.split(".")
        curr: Any = data
        for p in parts:
            if isinstance(curr, dict) and p in curr:
                curr = curr[p]
            else:
                return None
        return curr

    def _identify_target(
        self, steps: List[Any]
    ) -> Optional[Tuple[str, str, Optional[List[Any]], List[Any]]]:
        """Identify candidate target field from step outputs.

        Returns:
            Tuple of (target_field_name, task_type, label_space, target_values)
            or None if no valid ML target is found.
        """
        # Gather all output fields across steps
        candidate_fields: Set[str] = set()
        for step in steps:
            _, _, out = self._extract_step_info(step)
            if not out or not isinstance(out, dict):
                return None
            flat_outputs = self._flatten_dict(out)
            candidate_fields.update(flat_outputs.keys())

        if not candidate_fields:
            return None

        # Score and evaluate each candidate field
        scored_candidates: List[Tuple[float, str, str, Optional[List[Any]], List[Any]]] = []

        for field in candidate_fields:
            values: List[Any] = []
            has_all_values = True
            for step in steps:
                _, _, out = self._extract_step_info(step)
                flat_outputs = self._flatten_dict(out)
                if field not in flat_outputs:
                    has_all_values = False
                    break
                values.append(flat_outputs[field])

            if not has_all_values or len(values) < self.min_samples:
                continue

            # Evaluate field as Categorical Classification
            cat_result = self._evaluate_categorical_target(field, values)
            if cat_result is not None:
                priority, task_type, label_space = cat_result
                scored_candidates.append((priority, field, task_type, label_space, values))
                continue

            # Evaluate field as Numerical Score / Regression
            score_result = self._evaluate_score_target(field, values)
            if score_result is not None:
                priority, task_type, label_space = score_result
                scored_candidates.append((priority, field, task_type, label_space, values))
                continue

        if not scored_candidates:
            return None

        # Sort candidates by priority score descending and pick best candidate
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        _, best_field, task_type, label_space, target_values = scored_candidates[0]
        return best_field, task_type, label_space, target_values

    def _flatten_dict(self, data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        """Flatten nested dictionary keys with dot notation."""
        res: Dict[str, Any] = {}
        for k, v in data.items():
            full_k = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                res.update(self._flatten_dict(v, prefix=full_k))
            else:
                res[full_k] = v
        return res

    def _evaluate_categorical_target(
        self, field_name: str, values: List[Any]
    ) -> Optional[Tuple[float, str, List[Any]]]:
        """Evaluate if values form a valid categorical classification target.

        Returns:
            Tuple of (priority_score, "classification", sorted_label_space) or None.
        """
        # Reject non-primitive or complex types
        if not all(isinstance(v, (bool, str, int)) for v in values):
            return None

        # Reject long text output (generative drafts/summaries)
        if any(
            isinstance(v, str) and (len(v) > self.max_output_text_length or "\n\n" in v)
            for v in values
        ):
            return None

        # Check unique classes
        try:
            unique_classes = set(values)
        except TypeError:
            return None

        num_unique = len(unique_classes)
        total_samples = len(values)

        # Require at least 2 unique classes for classification, up to max cardinality
        if num_unique < 2 or num_unique > self.max_categorical_cardinality:
            return None

        # Distinguish categorical string labels from unique identifiers/uuids/tokens
        field_lower = field_name.lower()
        is_keyword_match = any(kw in field_lower for kw in self.CLASSIFICATION_KEYWORDS)

        # If every single sample has a unique string value and sample count >= 4 without keyword match,
        # it's likely an identifier/token, not a category
        if (
            num_unique == total_samples
            and total_samples >= 4
            and not is_keyword_match
            and all(isinstance(v, str) for v in values)
        ):
            return None

        # Check boolean targets (binary classification)
        if all(isinstance(v, bool) for v in values):
            sorted_labels = sorted(list(unique_classes), key=lambda x: str(x))
            priority = 10.0 if is_keyword_match else 8.0
            return priority, "classification", sorted_labels

        # Check string categorical labels
        if all(isinstance(v, str) for v in values):
            sorted_labels = sorted(list(unique_classes))
            priority = 9.0 if is_keyword_match else 6.0
            return priority, "classification", sorted_labels

        # Check discrete integer classes (e.g. 0/1/2 or ratings 1-5 with low cardinality)
        if all(isinstance(v, int) and not isinstance(v, bool) for v in values):
            if num_unique <= 10 or is_keyword_match:
                sorted_labels = sorted(list(unique_classes))
                priority = 7.0 if is_keyword_match else 5.0
                return priority, "classification", sorted_labels

        return None

    def _evaluate_score_target(
        self, field_name: str, values: List[Any]
    ) -> Optional[Tuple[float, str, Optional[List[Any]]]]:
        """Evaluate if values form a numerical score or continuous regression target.

        Returns:
            Tuple of (priority_score, "regression", label_space) or None.
        """
        # All values must be numbers (float or int) and not bool
        if not all(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in values
        ):
            return None

        field_lower = field_name.lower()
        is_score_keyword = any(kw in field_lower for kw in self.SCORE_KEYWORDS)
        has_float_values = any(isinstance(v, float) for v in values)
        num_unique = len(set(values))

        # High confidence numerical score: has float values or matches score keywords or varied numbers
        if is_score_keyword or has_float_values or num_unique > 5:
            priority = 9.5 if is_score_keyword else 7.5
            label_space = ["continuous"]
            return priority, "regression", label_space

        return None

    def _recommend_model_type(
        self,
        task_type: str,
        feature_sets: List[Dict[str, Any]],
        target_values: List[Any],
    ) -> str:
        """Recommend model framework ('scikit_learn' vs 'xgboost') based on feature/task characteristics."""
        numeric_count = 0
        text_count = 0
        total_features = 0

        for fset in feature_sets:
            for val in fset.values():
                total_features += 1
                if isinstance(val, (int, float, bool)):
                    numeric_count += 1
                elif isinstance(val, str):
                    text_count += 1

        # Continuous regression on tabular data -> XGBoost
        if task_type == "regression":
            return "xgboost"

        # Classification with predominantly numeric tabular features -> XGBoost
        if total_features > 0 and (numeric_count / total_features) >= 0.7:
            return self.default_tabular_model

        # Classification with text or mixed categorical features -> Scikit-Learn
        return self.default_text_model
