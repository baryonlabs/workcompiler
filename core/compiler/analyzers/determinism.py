"""Determinism Analyzer for OpenWorkflow WorkCompiler.

Detects deterministic operation patterns in agent execution trace steps:
- Arithmetic calculation (unary, binary, aggregations, linear combinations)
- String formatting and transformations (templates, case conversions, slugification, concatenation)
- Dictionary, table, CRM, and database lookups
- Exact pattern matching and rule-based branching
- JSON schema formatting and structured data projections
- Direct HTTP / REST API calls

Provides lowering target recommendations for 8-tier executor synthesis
(CodeExecutor, RuleExecutor, HTTPExecutor).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from core.validation.classifier import BehaviorCategory, classify_behavior
from protocols.traces.trace_ir import TraceStep


@dataclass
class DeterminismAnalysisResult:
    """Outcome of determinism analysis for a workflow action step."""

    is_deterministic: bool
    tier: str  # 'constant', 'sql', 'rule', 'code', 'http', or 'none'
    confidence: float = 1.0
    handler: Optional[str] = None
    reasoning: str = ""
    extracted_rules: List[str] = field(default_factory=list)


class DeterminismAnalyzer:
    """Analyzes execution trace steps and actions to detect deterministic operation patterns."""

    # Action keywords indicating database queries
    SQL_KEYWORDS = {"sql", "query", "crm", "db", "fetch_record", "lookup_contract", "database"}

    # Action keywords indicating constant or dictionary lookup
    CONSTANT_KEYWORDS = {"constant", "config", "static", "lookup_table", "dict_lookup"}

    # Action keywords indicating rule engines and policy checks
    RULE_KEYWORDS = {
        "rule", "policy", "price", "pricing", "discount", "eligibility",
        "tax", "limit", "tier_rate", "check_policy", "validate_rule"
    }

    # Action keywords indicating external HTTP/REST connectors or notifications
    HTTP_KEYWORDS = {
        "http", "api", "webhook", "rest", "send_email", "email", "slack",
        "notify", "notification", "post_webhook", "call_api"
    }

    # Action keywords indicating deterministic code transformations and arithmetic
    CODE_KEYWORDS = {
        "calculate", "compute", "format", "transform", "parse", "extract",
        "sum", "multiply", "aggregate", "hash", "convert", "validate_schema"
    }

    def __init__(self, confidence_threshold: float = 0.70) -> None:
        """Initialize DeterminismAnalyzer.

        Args:
            confidence_threshold: Minimum confidence score (0.0 - 1.0) required
                to consider a step deterministic. Defaults to 0.70.
        """
        self.confidence_threshold = confidence_threshold

    def analyze_step(
        self,
        step: Union[TraceStep, Dict[str, Any], Any],
        previous_steps: Optional[List[Union[TraceStep, Dict[str, Any], Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze a single TraceStep for deterministic patterns.

        Args:
            step: TraceStep instance (Protocols or Core IR) or dict representing an execution step.
            previous_steps: Optional list of preceding TraceSteps in the same trajectory.

        Returns:
            Lowering target dictionary containing:
                - target_executor: "code" | "rule" | "http"
                - handler: Suggested handler path or module identifier
                - confidence_score: Confidence level between 0.0 and 1.0
                - pattern_type: Detected pattern category ("arithmetic", "string_formatting",
                  "lookup", "pattern_matching", "json_transform", "http_call")
                - details: Additional diagnostic information
            Or None if no deterministic pattern is detected with sufficient confidence.
        """
        actor, action, input_data, output_data = self._extract_step_components(step)

        # Empty outputs or steps with no data are not lowerable
        if not output_data:
            return None

        # Check detectors in order of specificity
        detectors = [
            lambda: self.detect_http_call(input_data, output_data, action),
            lambda: self.detect_arithmetic(input_data, output_data, action),
            lambda: self.detect_string_formatting(input_data, output_data, action),
            lambda: self.detect_lookup(input_data, output_data, previous_steps, action),
            lambda: self.detect_pattern_matching(input_data, output_data, action),
            lambda: self.detect_json_transform(input_data, output_data, previous_steps, action),
        ]

        best_result: Optional[Dict[str, Any]] = None
        highest_confidence = 0.0

        for detector in detectors:
            result = detector()
            if result and result.get("confidence_score", 0.0) >= self.confidence_threshold:
                score = result["confidence_score"]
                if score > highest_confidence:
                    highest_confidence = score
                    best_result = result
                    # Short-circuit on absolute certainty
                    if highest_confidence >= 0.99:
                        break

        return best_result

    def analyze_trace(
        self, trace: Any
    ) -> List[Tuple[Any, Optional[Dict[str, Any]]]]:
        """Analyze an entire execution trace and return lowering recommendations for each step.

        Args:
            trace: TraceIR instance or dictionary with 'steps' list.

        Returns:
            List of tuples (step, lowering_dict_or_none) for all steps in the trace.
        """
        raw_steps = (
            trace.get("steps", [])
            if isinstance(trace, dict)
            else getattr(trace, "steps", [])
        )
        results: List[Tuple[Any, Optional[Dict[str, Any]]]] = []
        preceding: List[Any] = []

        for step in raw_steps:
            res = self.analyze_step(step, previous_steps=preceding)
            results.append((step, res))
            preceding.append(step)

        return results

    # =========================================================================
    # Pattern Detectors
    # =========================================================================

    def detect_http_call(
        self,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        action: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Detect HTTP / REST / Webhook requests."""
        act_lower = action.lower().strip()
        url = input_data.get("url") or input_data.get("endpoint") or input_data.get("uri")
        method = str(input_data.get("method", "GET")).upper() if input_data.get("method") else None

        is_http_action = (
            act_lower.startswith(("http.", "http_", "rest.", "rest_", "api.", "api_", "webhook."))
            or act_lower in {"http_request", "call_api", "fetch_url", "send_webhook", "rest_call", "fetch_api"}
            or ("request" in act_lower and ("http" in act_lower or "api" in act_lower))
        )

        has_url = isinstance(url, str) and (
            url.startswith(("http://", "https://", "/api/", "api/"))
            or ("." in url and "/" in url)
        )

        if has_url or (is_http_action and (url or "status_code" in output_data or "response" in output_data)):
            http_method = (method or "GET").lower()
            handler_name = f"connectors.http.{http_method}" if http_method in {"get", "post", "put", "delete", "patch"} else "connectors.http.request"
            if act_lower and "." in act_lower and not act_lower.startswith("http"):
                handler_name = f"connectors.{act_lower}"

            confidence = 0.98 if (has_url and is_http_action) else (0.92 if has_url else 0.85)
            return {
                "target_executor": "http",
                "handler": handler_name,
                "confidence_score": confidence,
                "pattern_type": "http_call",
                "details": {
                    "url": url,
                    "method": method or "GET",
                    "status_code": output_data.get("status_code"),
                },
            }

        return None

    def detect_arithmetic(
        self,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        action: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Detect arithmetic calculations and numerical transformations."""
        flat_inputs = self._extract_numbers(input_data)
        list_inputs = self._extract_number_lists(input_data)
        flat_outputs = self._extract_numbers(output_data)

        if not flat_outputs or (not flat_inputs and not list_inputs):
            return None

        act_lower = action.lower()
        math_keywords = {
            "calc", "compute", "math", "sum", "add", "multiply", "divide",
            "discount", "rate", "pricing", "subtotal", "total", "average", "avg",
            "tax", "markup", "balance", "percentage", "diff", "difference", "usage"
        }
        has_math_action = any(kw in act_lower for kw in math_keywords)

        # 1. Check array aggregations (e.g. sum([10, 20, 30]) -> 60)
        for in_key, in_val in list_inputs.items():
            if in_val:
                nums = [float(x) for x in in_val]
                for out_key, out_val in flat_outputs.items():
                    out_num = float(out_val)
                    # Sum
                    if math.isclose(sum(nums), out_num, rel_tol=1e-4, abs_tol=1e-4):
                        return self._build_arithmetic_result(
                            op="sum_list",
                            formula=f"sum({in_key})",
                            action=action,
                            confidence=1.0,
                            target_field=out_key,
                        )
                    # Average
                    if len(nums) > 0 and math.isclose(sum(nums) / len(nums), out_num, rel_tol=1e-4, abs_tol=1e-4):
                        return self._build_arithmetic_result(
                            op="average_list",
                            formula=f"sum({in_key}) / len({in_key})",
                            action=action,
                            confidence=1.0,
                            target_field=out_key,
                        )
                    # Min / Max
                    if math.isclose(min(nums), out_num, rel_tol=1e-4, abs_tol=1e-4):
                        return self._build_arithmetic_result(
                            op="min_list",
                            formula=f"min({in_key})",
                            action=action,
                            confidence=0.95,
                            target_field=out_key,
                        )
                    if math.isclose(max(nums), out_num, rel_tol=1e-4, abs_tol=1e-4):
                        return self._build_arithmetic_result(
                            op="max_list",
                            formula=f"max({in_key})",
                            action=action,
                            confidence=0.95,
                            target_field=out_key,
                        )

        # 2. Check binary operations between pairs of input numbers
        in_items = list(flat_inputs.items())
        for out_key, out_val in flat_outputs.items():
            out_num = float(out_val)

            # Unary operations (e.g. round, percentage, negation)
            for k, val in in_items:
                v = float(val)
                if math.isclose(v * 0.01, out_num, rel_tol=1e-4, abs_tol=1e-4):
                    return self._build_arithmetic_result("percentage", f"{k} * 0.01", action, 1.0, out_key)
                if math.isclose(1.0 - v, out_num, rel_tol=1e-4, abs_tol=1e-4) or math.isclose(100.0 - v, out_num, rel_tol=1e-4, abs_tol=1e-4):
                    return self._build_arithmetic_result("complement", f"1 - {k}", action, 0.95, out_key)
                if math.isclose(abs(v), out_num, rel_tol=1e-4, abs_tol=1e-4) and v < 0:
                    return self._build_arithmetic_result("abs", f"abs({k})", action, 1.0, out_key)

            # Binary operations
            for i in range(len(in_items)):
                k1, v1_raw = in_items[i]
                v1 = float(v1_raw)
                for j in range(len(in_items)):
                    if i == j:
                        continue
                    k2, v2_raw = in_items[j]
                    v2 = float(v2_raw)

                    # Addition: v1 + v2
                    if math.isclose(v1 + v2, out_num, rel_tol=1e-4, abs_tol=1e-4):
                        return self._build_arithmetic_result("add", f"{k1} + {k2}", action, 1.0, out_key)

                    # Subtraction: v1 - v2
                    if math.isclose(v1 - v2, out_num, rel_tol=1e-4, abs_tol=1e-4):
                        return self._build_arithmetic_result("subtract", f"{k1} - {k2}", action, 1.0, out_key)

                    # Multiplication: v1 * v2
                    if math.isclose(v1 * v2, out_num, rel_tol=1e-4, abs_tol=1e-4):
                        return self._build_arithmetic_result("multiply", f"{k1} * {k2}", action, 1.0, out_key)

                    # Division: v1 / v2
                    if abs(v2) > 1e-9 and math.isclose(v1 / v2, out_num, rel_tol=1e-4, abs_tol=1e-4):
                        return self._build_arithmetic_result("divide", f"{k1} / {k2}", action, 1.0, out_key)

                    # Compound: Discount v1 * (1 - v2) or v1 * (1 - v2/100)
                    if math.isclose(v1 * (1.0 - v2), out_num, rel_tol=1e-4, abs_tol=1e-4) or (
                        v2 > 0 and math.isclose(v1 * (1.0 - v2 / 100.0), out_num, rel_tol=1e-4, abs_tol=1e-4)
                    ):
                        return self._build_arithmetic_result("discount", f"{k1} * (1 - {k2})", action, 1.0, out_key)

                    # Compound: Tax / Markup v1 * (1 + v2) or v1 * (1 + v2/100)
                    if math.isclose(v1 * (1.0 + v2), out_num, rel_tol=1e-4, abs_tol=1e-4) or (
                        v2 > 0 and math.isclose(v1 * (1.0 + v2 / 100.0), out_num, rel_tol=1e-4, abs_tol=1e-4)
                    ):
                        return self._build_arithmetic_result("markup_or_tax", f"{k1} * (1 + {k2})", action, 1.0, out_key)

            # Ternary operations (e.g. (a + b + c) or a * b + c)
            if len(in_items) >= 3:
                for i in range(len(in_items)):
                    k1, v1 = in_items[i][0], float(in_items[i][1])
                    for j in range(len(in_items)):
                        if i == j:
                            continue
                        k2, v2 = in_items[j][0], float(in_items[j][1])
                        for m in range(len(in_items)):
                            if m == i or m == j:
                                continue
                            k3, v3 = in_items[m][0], float(in_items[m][1])

                            # a + b + c
                            if math.isclose(v1 + v2 + v3, out_num, rel_tol=1e-4, abs_tol=1e-4):
                                return self._build_arithmetic_result("sum_3", f"{k1} + {k2} + {k3}", action, 1.0, out_key)

                            # a * b + c (e.g. base * rate + fee)
                            if math.isclose(v1 * v2 + v3, out_num, rel_tol=1e-4, abs_tol=1e-4):
                                return self._build_arithmetic_result("linear_scale", f"({k1} * {k2}) + {k3}", action, 1.0, out_key)

        # 3. Fallback: Action is explicitly math-oriented and both input/output have pure numbers
        if has_math_action and len(flat_inputs) > 0 and len(flat_outputs) > 0:
            return self._build_arithmetic_result(
                op="custom_calculation",
                formula=f"{action}({', '.join(flat_inputs.keys())})",
                action=action,
                confidence=0.88,
                target_field=list(flat_outputs.keys())[0],
            )

        return None

    def detect_string_formatting(
        self,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        action: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Detect string formatting, interpolation templates, and case transformations."""
        str_inputs = self._extract_strings(input_data)
        str_outputs = self._extract_strings(output_data)

        if not str_outputs or not str_inputs:
            return None

        act_lower = action.lower()
        fmt_keywords = {"format", "template", "concat", "render", "slug", "email_template", "build_str", "transform_str"}
        has_fmt_action = any(kw in act_lower for kw in fmt_keywords)

        for out_key, out_val in str_outputs.items():
            if not out_val:
                continue

            # 1. Single string standard transformations
            for in_key, in_val in str_inputs.items():
                if not in_val:
                    continue

                if in_val.upper() == out_val and in_val != out_val:
                    return self._build_string_result("transformers.str.upper", action, 1.0, {"transform": "upper", "field": in_key})
                if in_val.lower() == out_val and in_val != out_val:
                    return self._build_string_result("transformers.str.lower", action, 1.0, {"transform": "lower", "field": in_key})
                if in_val.strip() == out_val and in_val != out_val:
                    return self._build_string_result("transformers.str.strip", action, 1.0, {"transform": "strip", "field": in_key})
                if in_val.title() == out_val and in_val != out_val:
                    return self._build_string_result("transformers.str.title", action, 1.0, {"transform": "title", "field": in_key})

                # Slugify / snake_case
                slugified = re.sub(r"[^\w\s-]", "", in_val.lower()).strip()
                slugified = re.sub(r"[-\s]+", "_", slugified)
                if slugified == out_val and in_val != out_val:
                    return self._build_string_result("transformers.str.slugify", action, 1.0, {"transform": "slugify", "field": in_key})

            # 2. String Concatenation: output is join of multiple input values
            if len(str_inputs) >= 2:
                for sep in [" ", ", ", "-", "_", "/", ""]:
                    joined = sep.join([v for v in str_inputs.values() if v])
                    if joined == out_val:
                        return self._build_string_result(
                            "transformers.string_concat",
                            action,
                            1.0,
                            {"separator": sep, "fields": list(str_inputs.keys()), "result": out_val},
                        )

            # 3. Template interpolation (e.g. "Hello {name}, your ticket {id} is ready")
            matched_vars: List[Tuple[int, int, str, str]] = []  # (start, end, key, val)
            for in_key, in_val in str_inputs.items():
                if len(in_val) >= 2 and in_val in out_val:
                    # Find all non-overlapping occurrences
                    for m in re.finditer(re.escape(in_val), out_val):
                        matched_vars.append((m.start(), m.end(), in_key, in_val))

            # Also check numeric inputs in template string
            for num_k, num_v in self._extract_numbers(input_data).items():
                num_str = str(int(num_v) if isinstance(num_v, float) and num_v.is_integer() else num_v)
                if len(num_str) >= 1 and num_str in out_val:
                    for m in re.finditer(re.escape(num_str), out_val):
                        matched_vars.append((m.start(), m.end(), num_k, num_str))

            if matched_vars:
                # Sort by start index and filter overlapping matches
                matched_vars.sort(key=lambda x: (x[0], -(x[1] - x[0])))
                non_overlapping: List[Tuple[int, int, str, str]] = []
                last_end = 0
                for start, end, k, v in matched_vars:
                    if start >= last_end:
                        non_overlapping.append((start, end, k, v))
                        last_end = end

                # If 2 or more variables match, or 1 variable with surrounding static text
                if len(non_overlapping) >= 2 or (
                    len(non_overlapping) == 1
                    and len(out_val) > len(non_overlapping[0][3]) + 4
                    and has_fmt_action
                ):
                    # Synthesize template
                    template_parts = []
                    curr_pos = 0
                    for start, end, k, v in non_overlapping:
                        template_parts.append(out_val[curr_pos:start])
                        template_parts.append(f"{{{k}}}")
                        curr_pos = end
                    template_parts.append(out_val[curr_pos:])
                    synth_template = "".join(template_parts)

                    confidence = 0.98 if len(non_overlapping) >= 2 else 0.88
                    return self._build_string_result(
                        "transformers.template_render",
                        action,
                        confidence,
                        {
                            "template": synth_template,
                            "variables": [k for _, _, k, _ in non_overlapping],
                            "output_field": out_key,
                        },
                    )

        # 4. Fallback on formatting action
        if has_fmt_action and str_outputs:
            return self._build_string_result(
                "transformers.string_formatter",
                action,
                0.80,
                {"action": action},
            )

        return None

    def detect_lookup(
        self,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        previous_steps: Optional[List[Any]] = None,
        action: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Detect dictionary, database, CRM, or cross-step table lookups."""
        act_lower = action.lower()
        lookup_keywords = {
            "lookup", "get_", "fetch_", "find_", "query_", "search_", "select_",
            "db.", "crm.", "table.", "cache."
        }
        is_lookup_action = any(kw in act_lower for kw in lookup_keywords)

        # 1. In-step lookup: input contains table/map dictionary + key
        for in_k, in_v in input_data.items():
            if isinstance(in_v, dict):
                for key_k, key_v in input_data.items():
                    if key_k != in_k and isinstance(key_v, (str, int)) and str(key_v) in in_v:
                        matched_val = in_v[str(key_v)]
                        # Check if matched_val matches output
                        if matched_val == output_data or (
                            isinstance(output_data, dict) and any(v == matched_val for v in output_data.values())
                        ):
                            return {
                                "target_executor": "code",
                                "handler": "connectors.lookup_table",
                                "confidence_score": 1.0,
                                "pattern_type": "lookup",
                                "details": {
                                    "table_key": in_k,
                                    "lookup_key": key_k,
                                    "matched_value": matched_val,
                                },
                            }

        # 2. Cross-step lookup: previous step returned a list/dict of records, current step filters by ID
        if previous_steps:
            id_values = {
                str(v)
                for k, v in input_data.items()
                if ("id" in k.lower() or "key" in k.lower() or "code" in k.lower())
                and isinstance(v, (str, int))
            }
            if id_values:
                for prev in previous_steps:
                    _, _, _, prev_out = self._extract_step_components(prev)
                    # Search inside list of dicts in prev_out
                    for p_key, p_val in prev_out.items():
                        if isinstance(p_val, list):
                            for item in p_val:
                                if isinstance(item, dict):
                                    # Check if item matches any id
                                    for item_k, item_v in item.items():
                                        if str(item_v) in id_values:
                                            # Check if current output is this item or subset of item
                                            if isinstance(output_data, dict):
                                                matching_keys = set(output_data.keys()).intersection(set(item.keys()))
                                                if len(matching_keys) >= 1 and all(
                                                    output_data[k] == item[k] for k in matching_keys
                                                ):
                                                    return {
                                                        "target_executor": "code",
                                                        "handler": f"connectors.{action}" if action else "connectors.db.lookup",
                                                        "confidence_score": 0.98,
                                                        "pattern_type": "lookup",
                                                        "details": {
                                                            "source_step_field": p_key,
                                                            "lookup_id": str(item_v),
                                                            "matched_fields": list(matching_keys),
                                                        },
                                                    }

        # 3. Action name indicates database / CRM lookup with identifier input
        has_id_input = any(
            ("id" in k.lower() or "key" in k.lower() or "code" in k.lower() or "email" in k.lower())
            for k in input_data.keys()
        )
        if is_lookup_action and (has_id_input or len(input_data) <= 3):
            handler_name = f"connectors.{action}" if action else "connectors.db.lookup"
            if not handler_name.startswith("connectors."):
                handler_name = f"connectors.{handler_name}"
            return {
                "target_executor": "code",
                "handler": handler_name,
                "confidence_score": 0.92 if has_id_input else 0.82,
                "pattern_type": "lookup",
                "details": {
                    "action": action,
                    "query_keys": list(input_data.keys()),
                },
            }

        return None

    def detect_pattern_matching(
        self,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        action: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Detect rule-based branching, discrete state maps, and policy evaluation."""
        act_lower = action.lower()
        # Ignore connector / notification / query actions for rule pattern matching
        if any(kw in act_lower for kw in ("email", "send", "notify", "slack", "query", "fetch", "lookup", "http", "api", "webhook")):
            return None

        rule_keywords = {"rule", "policy", "check_", "validate_", "match_", "decision", "permission", "tier"}
        is_rule_action = any(kw in act_lower for kw in rule_keywords)

        # Check for boolean / decision flag outputs
        has_boolean_output = any(isinstance(v, bool) for v in output_data.values())

        # Check for discrete enum / category outputs
        has_category_output = any(
            isinstance(v, str) and v.lower() in {"approved", "rejected", "allowed", "denied", "eligible", "ineligible", "valid", "invalid", "high", "medium", "low", "ok", "error"}
            for v in output_data.values()
        )

        if is_rule_action or has_boolean_output or has_category_output:
            handler_name = f"rules.{action}" if action else "rules.pattern_match"
            if not handler_name.startswith("rules."):
                handler_name = f"rules.{handler_name}"

            confidence = 0.95 if (is_rule_action and (has_boolean_output or has_category_output)) else (
                0.90 if is_rule_action else 0.78
            )

            return {
                "target_executor": "rule",
                "handler": handler_name,
                "confidence_score": confidence,
                "pattern_type": "pattern_matching",
                "details": {
                    "rule_action": action,
                    "decision_fields": list(output_data.keys()),
                },
            }

        return None

    def detect_json_transform(
        self,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        previous_steps: Optional[List[Any]] = None,
        action: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Detect JSON schema restructuring, field projections, and renaming."""
        act_lower = action.lower()
        transform_keywords = {"transform", "map", "schema", "reshape", "adapt", "project", "convert_json", "format_json"}
        is_transform_action = any(kw in act_lower for kw in transform_keywords)

        # Collect all leaf primitive values from input
        input_leaves = self._extract_leaf_values(input_data)
        output_leaves = self._extract_leaf_values(output_data)

        if not output_leaves:
            return None

        # Check what percentage of output leaves come directly from input
        matched_leaves = [v for v in output_leaves if v in input_leaves]
        coverage = len(matched_leaves) / len(output_leaves) if output_leaves else 0.0

        if coverage >= 0.75 and len(output_leaves) >= 2:
            handler_name = f"transformers.{action}" if action else "transformers.json_schema_mapper"
            if not handler_name.startswith("transformers."):
                handler_name = f"transformers.{handler_name}"

            confidence = 0.95 if (is_transform_action or coverage >= 0.99) else 0.85
            return {
                "target_executor": "code",
                "handler": handler_name,
                "confidence_score": confidence,
                "pattern_type": "json_transform",
                "details": {
                    "field_coverage": round(coverage, 2),
                    "output_fields": list(output_data.keys()),
                },
            }

        if is_transform_action and output_data:
            return {
                "target_executor": "code",
                "handler": f"transformers.{action}" if action else "transformers.json_schema_mapper",
                "confidence_score": 0.80,
                "pattern_type": "json_transform",
                "details": {"action": action},
            }

        return None

    # =========================================================================
    # Action-Level & Backward Compatible Analysis
    # =========================================================================

    def analyze_action(
        self,
        action_name: str,
        steps: Optional[List[TraceStep]] = None,
        behaviors: Optional[List[Dict[str, Any]]] = None,
    ) -> DeterminismAnalysisResult:
        """Analyze an action name and its trace steps to detect deterministic execution potential.

        Args:
            action_name: Canonical name of the action step.
            steps: Optional list of TraceStep instances recorded for this action.
            behaviors: Optional list of parsed AgentBehavior contract dictionaries.

        Returns:
            DeterminismAnalysisResult specifying determinism status, lowering tier, and handler.
        """
        act_lower = action_name.lower()
        steps = steps or []
        behaviors = behaviors or []

        # 0. Replayable evidence wins: a recorded shell command or file patch is deterministic code
        #    regardless of what the action is called or which behavior contracts mention it.
        if steps and all(self._shell_command_of(step) or self._patch_of(step) for step in steps):
            return DeterminismAnalysisResult(
                is_deterministic=True,
                tier="code",
                confidence=0.9,
                handler=f"handlers.{action_name}",
                reasoning=f"Action '{action_name}' replays a recorded shell command / file patch",
            )

        # 1. Check attached behavior contracts for Rule/Policy categorization
        extracted_rules: List[str] = []
        for b in behaviors:
            classification = classify_behavior(b)
            if classification.category == BehaviorCategory.RULE_POLICY:
                b_text = f"{b.get('name', '')} {b.get('evidence', '')} {b.get('intent', '')}".lower()
                b_name_clean = b.get("name", "").replace("-", "_").lower()
                if act_lower in b_text or b_name_clean in act_lower or (any(k in act_lower for k in ["price", "rule", "policy"]) and any(k in b_text for k in ["price", "rule", "policy"])):
                    extracted_rules.append(b.get("name", ""))
                    return DeterminismAnalysisResult(
                        is_deterministic=True,
                        tier="rule",
                        confidence=1.0,
                        handler=f"rules.{action_name}",
                        reasoning=f"Enforced by Rule/Policy behavior contract '{b.get('name')}'",
                        extracted_rules=extracted_rules,
                    )

        # 2. Analyze step traces if available
        if steps:
            for step in steps:
                step_res = self.analyze_step(step)
                if step_res:
                    tier_map = {"code": "code", "rule": "rule", "http": "http"}
                    return DeterminismAnalysisResult(
                        is_deterministic=True,
                        tier=tier_map.get(step_res["target_executor"], "code"),
                        confidence=step_res["confidence_score"],
                        handler=step_res["handler"],
                        reasoning=f"Step analysis detected deterministic pattern: {step_res['pattern_type']}",
                    )

        # 3. Heuristic Action Name Analysis
        if any(k in act_lower for k in self.RULE_KEYWORDS):
            return DeterminismAnalysisResult(
                is_deterministic=True,
                tier="rule",
                confidence=0.95,
                handler=f"rules.{action_name}",
                reasoning=f"Action '{action_name}' matches deterministic business rule pattern",
                extracted_rules=extracted_rules,
            )

        if any(k in act_lower for k in self.CONSTANT_KEYWORDS):
            return DeterminismAnalysisResult(
                is_deterministic=True,
                tier="constant",
                confidence=0.95,
                handler=f"connectors.{action_name}",
                reasoning=f"Action '{action_name}' represents static configuration or constant lookup",
            )

        if any(k in act_lower for k in self.SQL_KEYWORDS):
            return DeterminismAnalysisResult(
                is_deterministic=True,
                tier="sql",
                confidence=0.95,
                handler=f"connectors.{action_name}",
                reasoning=f"Action '{action_name}' matches SQL/database query pattern",
            )

        if any(k in act_lower for k in self.HTTP_KEYWORDS):
            return DeterminismAnalysisResult(
                is_deterministic=True,
                tier="http",
                confidence=0.95,
                handler=f"connectors.{action_name}",
                reasoning=f"Action '{action_name}' matches external API / HTTP connector pattern",
            )

        if any(k in act_lower for k in self.CODE_KEYWORDS):
            return DeterminismAnalysisResult(
                is_deterministic=True,
                tier="code",
                confidence=0.95,
                handler=f"services.{action_name}",
                reasoning=f"Action '{action_name}' matches deterministic math / transformation code",
            )

        return DeterminismAnalysisResult(
            is_deterministic=False,
            tier="none",
            confidence=0.0,
            handler=None,
            reasoning=f"Action '{action_name}' did not match deterministic patterns",
        )

    @staticmethod
    def _shell_command_of(step: Any) -> Optional[str]:
        """Return the shell command recorded in a step's input, if any."""
        inp = getattr(step, "input", None) if not isinstance(step, dict) else step.get("input")
        if hasattr(inp, "model_dump"):
            inp = inp.model_dump()
        if not isinstance(inp, dict):
            return None
        cmd = inp.get("cmd") or inp.get("command")
        if isinstance(cmd, list) and cmd:
            return " ".join(str(c) for c in cmd)
        return cmd if isinstance(cmd, str) and cmd.strip() else None

    @staticmethod
    def _patch_of(step: Any) -> Optional[str]:
        inp = getattr(step, "input", None) if not isinstance(step, dict) else step.get("input")
        if hasattr(inp, "model_dump"):
            inp = inp.model_dump()
        patch = inp.get("patch") if isinstance(inp, dict) else None
        return patch if isinstance(patch, str) and patch.strip() else None

    def is_deterministic(
        self,
        action_name: str,
        steps: Optional[List[TraceStep]] = None,
        behaviors: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """Helper returning True if action is detected as deterministic."""
        res = self.analyze_action(action_name, steps, behaviors)
        return res.is_deterministic

    def detect_tier(
        self,
        action_name: str,
        steps: Optional[List[TraceStep]] = None,
        behaviors: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[str]:
        """Helper returning the detected lowering tier if deterministic, else None."""
        res = self.analyze_action(action_name, steps, behaviors)
        return res.tier if res.is_deterministic else None

    # =========================================================================
    # Helper & Extraction Utilities
    # =========================================================================

    def _extract_step_components(
        self, step: Any
    ) -> Tuple[str, str, Dict[str, Any], Dict[str, Any]]:
        """Safely extract (actor, action, input_data, output_data) from step object or dict."""
        if isinstance(step, dict):
            actor = step.get("actor", "agent")
            action = step.get("action", "")
            inp = step.get("input") or {}
            out = step.get("output") or {}
        else:
            actor = getattr(step, "actor", "agent")
            action = getattr(step, "action", "")
            inp = getattr(step, "input", {}) or {}
            out = getattr(step, "output", {}) or {}

        if not isinstance(inp, dict):
            inp = {"value": inp}
        if not isinstance(out, dict):
            out = {"value": out}

        return actor, action, dict(inp), dict(out)

    def _extract_numbers(self, d: Any, prefix: str = "") -> Dict[str, Union[int, float]]:
        """Recursively extract numeric values with their dotted key paths."""
        res: Dict[str, Union[int, float]] = {}
        if isinstance(d, dict):
            for k, v in d.items():
                path = f"{prefix}.{k}" if prefix else str(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    res[path] = v
                elif isinstance(v, dict):
                    res.update(self._extract_numbers(v, path))
                elif isinstance(v, list):
                    for i, item in enumerate(v):
                        if isinstance(item, (int, float)) and not isinstance(item, bool):
                            res[f"{path}.{i}"] = item
                        elif isinstance(item, dict):
                            res.update(self._extract_numbers(item, f"{path}.{i}"))
        return res

    def _extract_number_lists(self, d: Any, prefix: str = "") -> Dict[str, List[Union[int, float]]]:
        """Recursively extract lists containing numeric values."""
        res: Dict[str, List[Union[int, float]]] = {}
        if isinstance(d, dict):
            for k, v in d.items():
                path = f"{prefix}.{k}" if prefix else str(k)
                if isinstance(v, list) and v and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
                    res[path] = v
                elif isinstance(v, dict):
                    res.update(self._extract_number_lists(v, path))
        return res

    def _extract_strings(self, d: Any, prefix: str = "") -> Dict[str, str]:
        """Recursively extract string values with their dotted key paths."""
        res: Dict[str, str] = {}
        if isinstance(d, dict):
            for k, v in d.items():
                path = f"{prefix}.{k}" if prefix else str(k)
                if isinstance(v, str):
                    res[path] = v
                elif isinstance(v, dict):
                    res.update(self._extract_strings(v, path))
        return res

    def _extract_leaf_values(self, d: Any) -> List[Any]:
        """Recursively extract all primitive leaf values."""
        leaves: List[Any] = []
        if isinstance(d, dict):
            for v in d.values():
                leaves.extend(self._extract_leaf_values(v))
        elif isinstance(d, list):
            for item in d:
                leaves.extend(self._extract_leaf_values(item))
        elif d is not None:
            leaves.append(d)
        return leaves

    def _build_arithmetic_result(
        self,
        op: str,
        formula: str,
        action: str,
        confidence: float,
        target_field: str,
    ) -> Dict[str, Any]:
        """Construct lowering target for arithmetic operations."""
        act_lower = action.lower()
        if "rule" in act_lower or "policy" in act_lower or "pricing" in act_lower:
            executor = "rule"
            handler = f"rules.{action}" if action else "rules.pricing_calculator"
        else:
            executor = "code"
            handler = f"services.{action}" if action else f"code.math.{op}"

        return {
            "target_executor": executor,
            "handler": handler,
            "confidence_score": confidence,
            "pattern_type": "arithmetic",
            "details": {
                "operation": op,
                "formula": formula,
                "target_field": target_field,
            },
        }

    def _build_string_result(
        self,
        handler: str,
        action: str,
        confidence: float,
        details: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Construct lowering target for string transformations."""
        if action and ("template" in action or "format" in action):
            if "." in action:
                handler = f"transformers.{action}"

        return {
            "target_executor": "code",
            "handler": handler,
            "confidence_score": confidence,
            "pattern_type": "string_formatting",
            "details": details,
        }
