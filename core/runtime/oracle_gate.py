"""Objective Oracle Gate for OpenWorkCompiler Runtime.

Implements Frugal-style objective verification and failure escalation:
validates step execution results against external schemas and behavior contracts,
triggering escalation to Frontier LLMs or Humans only when objective criteria fail.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from core.runtime.executors import ActionResult
from core.validation.quality_record import BehaviorVerdict

logger = logging.getLogger(__name__)


class ObjectiveOracleGate:
    """Evaluates step execution outcomes against objective schemas and behavior contracts.

    Implements Frugal-style escalation:
    - Output passes schema validation & behavior invariants -> Return True (Proceed with compiled executor).
    - Schema validation or behavior contracts fail -> Return False (Trigger escalation to Frontier LLM / Human).
    """

    def __init__(self) -> None:
        self.last_failure_reasons: List[str] = []

    def evaluate_oracle(
        self,
        action_name: str,
        step_result: ActionResult,
        schema: Optional[Dict[str, Any]] = None,
        behavior_specs: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """Evaluate an action execution result against schema constraints and behavior contracts.

        Args:
            action_name: Name of the executed workflow action.
            step_result: ActionResult returned by the action executor.
            schema: Optional JSON Schema or dictionary structure specification.
            behavior_specs: Optional list of AgentBehavior contract specifications.

        Returns:
            True if the execution succeeded and passed all schema and behavior checks.
            False if execution failed or violated any schema / behavior contract,
            signaling that runtime escalation is required.
        """
        self.last_failure_reasons = []

        # 1. Base execution success check
        if not step_result.success:
            err_msg = step_result.error or "Action execution reported failure without error message"
            self.last_failure_reasons.append(f"Execution failed for action '{action_name}': {err_msg}")
            return False

        # 2. Schema validation
        if schema is not None:
            schema_ok, schema_err = self.validate_schema(step_result.output, schema)
            if not schema_ok:
                self.last_failure_reasons.append(
                    f"Schema validation failed for action '{action_name}': {schema_err}"
                )
                return False

        # 3. Behavior contract verification
        if behavior_specs:
            behaviors_ok, behavior_errs = self.validate_behavior(
                action_name=action_name,
                step_result=step_result,
                behavior_specs=behavior_specs,
            )
            if not behaviors_ok:
                self.last_failure_reasons.extend(behavior_errs)
                return False

        return True

    def validate_schema(
        self, output: Any, schema: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Validate output payload against a schema specification.

        Supports standard JSON Schema constructs (type, required, properties, enum, min/max)
        as well as simple key-type mappings.

        Args:
            output: The action output payload to validate.
            schema: The schema dictionary.

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str]).
        """
        if output is None:
            if schema.get("nullable", False) or schema.get("type") == "null":
                return True, None
            return False, "Output is None but schema requires non-null payload"

        # Check JSON Schema 'type'
        expected_type = schema.get("type")
        if expected_type:
            type_ok, type_err = self._check_type(output, expected_type)
            if not type_ok:
                return False, type_err

        # Check 'enum'
        if "enum" in schema:
            if output not in schema["enum"]:
                return False, f"Output '{output}' not in allowed enum values: {schema['enum']}"

        # Check object constraints
        if isinstance(output, dict):
            # Check 'required' fields
            required_fields = schema.get("required", [])
            for field_name in required_fields:
                if field_name not in output:
                    return False, f"Missing required field: '{field_name}'"
                if output[field_name] is None and not schema.get("allow_null_fields", False):
                    # Check if property schema allows nullable
                    prop_schema = schema.get("properties", {}).get(field_name, {})
                    if not prop_schema.get("nullable", False):
                        return False, f"Required field '{field_name}' cannot be null"

            # Check 'properties'
            properties = schema.get("properties", {})
            for prop_name, prop_spec in properties.items():
                if prop_name in output and isinstance(prop_spec, dict):
                    prop_val = output[prop_name]
                    prop_ok, prop_err = self.validate_schema(prop_val, prop_spec)
                    if not prop_ok:
                        return False, f"Field '{prop_name}' invalid: {prop_err}"

            # Direct key-to-type validation for simple non-JSON-schema dicts
            for key, val in schema.items():
                if key not in ("type", "required", "properties", "enum", "description", "title", "nullable", "allow_null_fields"):
                    if isinstance(val, type):
                        if key not in output or not isinstance(output[key], val):
                            return False, f"Field '{key}' expected type {val.__name__}, got {type(output.get(key)).__name__}"

        # Check array constraints
        elif isinstance(output, (list, tuple)):
            if "minItems" in schema and len(output) < schema["minItems"]:
                return False, f"Array length {len(output)} is less than minItems {schema['minItems']}"
            if "maxItems" in schema and len(output) > schema["maxItems"]:
                return False, f"Array length {len(output)} exceeds maxItems {schema['maxItems']}"
            if "items" in schema and isinstance(schema["items"], dict):
                for idx, item in enumerate(output):
                    item_ok, item_err = self.validate_schema(item, schema["items"])
                    if not item_ok:
                        return False, f"Array item at index {idx} invalid: {item_err}"

        # Check string constraints
        elif isinstance(output, str):
            if "minLength" in schema and len(output) < schema["minLength"]:
                return False, f"String length {len(output)} is less than minLength {schema['minLength']}"
            if "maxLength" in schema and len(output) > schema["maxLength"]:
                return False, f"String length {len(output)} exceeds maxLength {schema['maxLength']}"
            if "pattern" in schema:
                if not re.search(schema["pattern"], output):
                    return False, f"String does not match required regex pattern '{schema['pattern']}'"

        # Check numeric constraints
        elif isinstance(output, (int, float)) and not isinstance(output, bool):
            if "minimum" in schema and output < schema["minimum"]:
                return False, f"Numeric value {output} is less than minimum {schema['minimum']}"
            if "maximum" in schema and output > schema["maximum"]:
                return False, f"Numeric value {output} is greater than maximum {schema['maximum']}"

        return True, None

    def _check_type(self, value: Any, expected_type: Union[str, List[str]]) -> Tuple[bool, Optional[str]]:
        """Verify type of value against JSON Schema type identifier."""
        type_list = [expected_type] if isinstance(expected_type, str) else expected_type

        type_map = {
            "object": dict,
            "array": (list, tuple),
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "null": type(None),
        }

        matched = False
        for t_name in type_list:
            py_type = type_map.get(t_name)
            if py_type is None:
                continue
            if t_name == "integer" and isinstance(value, bool):
                continue
            if t_name == "number" and isinstance(value, bool):
                continue
            if isinstance(value, py_type):
                matched = True
                break

        if not matched:
            return False, f"Expected type '{expected_type}', got '{type(value).__name__}'"
        return True, None

    def validate_behavior(
        self,
        action_name: str,
        step_result: ActionResult,
        behavior_specs: List[Dict[str, Any]],
    ) -> Tuple[bool, List[str]]:
        """Validate an action outcome against attached AgentBehavior contract specifications.

        Checks:
        - Explicit behavior verdicts in execution metadata or outputs (rejects 'false').
        - Required output fields specified by behavior invariants.
        - Forbidden substrings or prohibited conduct in output and execution logs.
        - Required terms and patterns.
        - Custom assertion rules and condition expressions.

        Args:
            action_name: Name of the action step.
            step_result: ActionResult of the execution.
            behavior_specs: List of behavior contract dictionaries.

        Returns:
            Tuple of (is_valid: bool, failure_messages: List[str]).
        """
        errors: List[str] = []

        # 1. Check explicit metadata behavior verdicts
        metadata = step_result.metadata or {}
        verdicts = metadata.get("behavior_verdicts") or metadata.get("verdicts") or {}
        if isinstance(verdicts, dict):
            for b_name, verdict in verdicts.items():
                v_str = verdict.value if isinstance(verdict, BehaviorVerdict) else str(verdict).lower()
                if v_str == BehaviorVerdict.FALSE.value:
                    errors.append(
                        f"Behavior contract '{b_name}' failed explicit verification (verdict: false)"
                    )

        # 2. Iterate through provided behavior specs
        output_str = ""
        if step_result.output is not None:
            output_str = str(step_result.output)
        logs_str = " ".join(step_result.logs)

        for spec in behavior_specs:
            if not isinstance(spec, dict):
                continue

            b_name = spec.get("name", "unnamed_behavior")
            target_action = spec.get("action") or spec.get("target_action")

            # If behavior specifically targets another action, skip
            if target_action and target_action != action_name:
                continue

            # Check required fields
            req_fields = spec.get("required_fields", [])
            if req_fields and isinstance(step_result.output, dict):
                for rf in req_fields:
                    if rf not in step_result.output:
                        errors.append(
                            f"Behavior '{b_name}' invariant violated: missing required output field '{rf}'"
                        )

            # Check forbidden terms / prohibitions
            prohibitions = (
                spec.get("forbidden_terms", [])
                + spec.get("prohibitions", [])
                + spec.get("forbidden_patterns", [])
            )
            for term in prohibitions:
                if term and (term in output_str or term in logs_str):
                    errors.append(
                        f"Behavior '{b_name}' violated prohibition: forbidden term '{term}' detected"
                    )

            # Check required terms
            req_terms = spec.get("required_terms", []) + spec.get("required_patterns", [])
            for term in req_terms:
                if term and term not in output_str:
                    errors.append(
                        f"Behavior '{b_name}' invariant violated: required term '{term}' missing from output"
                    )

            # Check assertions / rule expressions
            assertion = spec.get("assertion") or spec.get("rule") or spec.get("condition")
            if assertion:
                if callable(assertion):
                    try:
                        res = assertion(step_result.output)
                        if not res:
                            errors.append(
                                f"Behavior '{b_name}' assertion callable returned False"
                            )
                    except Exception as e:
                        errors.append(
                            f"Behavior '{b_name}' assertion evaluation raised exception: {e}"
                        )
                elif isinstance(assertion, str) and isinstance(step_result.output, dict):
                    eval_ok, eval_err = self._evaluate_rule_expression(assertion, step_result.output)
                    if not eval_ok:
                        errors.append(
                            f"Behavior '{b_name}' rule assertion '{assertion}' failed: {eval_err}"
                        )

            # Check custom numeric limits (e.g. max_discount, min_confidence)
            if isinstance(step_result.output, dict):
                if "max_discount" in spec:
                    disc = step_result.output.get("discount_percent") or step_result.output.get("discount", 0)
                    if isinstance(disc, (int, float)) and disc > spec["max_discount"]:
                        errors.append(
                            f"Behavior '{b_name}' limit violated: discount {disc}% exceeds allowed {spec['max_discount']}%"
                        )
                if "min_confidence" in spec:
                    conf = step_result.output.get("confidence", 1.0)
                    if isinstance(conf, (int, float)) and conf < spec["min_confidence"]:
                        errors.append(
                            f"Behavior '{b_name}' threshold violated: confidence {conf} < required {spec['min_confidence']}"
                        )

        return (len(errors) == 0, errors)

    def _evaluate_rule_expression(self, rule_str: str, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Safely evaluate simple comparison rules against output data dictionary."""
        # Supported operators: ==, !=, >=, <=, >, <, in
        ops_pattern = r"^([\w\.\_]+)\s*(==|!=|>=|<=|>|<|\bin\b)\s*(.+)$"
        match = re.match(ops_pattern, rule_str.strip())
        if not match:
            # Fallback: if rule is simple field presence check
            field_name = rule_str.strip()
            if field_name in data:
                return bool(data[field_name]), None
            return False, f"Rule syntax '{rule_str}' could not be evaluated"

        field_name, op, raw_val = match.groups()
        if field_name not in data:
            return False, f"Field '{field_name}' not found in output"

        actual_val = data[field_name]
        raw_val = raw_val.strip().strip("'\"")

        # Type conversion for comparison
        try:
            if isinstance(actual_val, (int, float)):
                cmp_val: Any = float(raw_val) if "." in raw_val else int(raw_val)
            elif isinstance(actual_val, bool):
                cmp_val = raw_val.lower() in ("true", "1")
            else:
                cmp_val = raw_val

            if op == "==":
                ok = actual_val == cmp_val
            elif op == "!=":
                ok = actual_val != cmp_val
            elif op == ">=":
                ok = actual_val >= cmp_val
            elif op == "<=":
                ok = actual_val <= cmp_val
            elif op == ">":
                ok = actual_val > cmp_val
            elif op == "<":
                ok = actual_val < cmp_val
            elif op == "in":
                ok = str(actual_val) in raw_val
            else:
                return False, f"Unsupported operator '{op}'"

            if not ok:
                return False, f"Assertion '{actual_val} {op} {cmp_val}' is False"
            return True, None
        except Exception as e:
            return False, f"Failed evaluating '{rule_str}': {e}"

    def explain_verdict(
        self,
        action_name: str,
        step_result: ActionResult,
        schema: Optional[Dict[str, Any]] = None,
        behavior_specs: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Provide detailed diagnostic breakdown of oracle evaluation."""
        passed = self.evaluate_oracle(
            action_name=action_name,
            step_result=step_result,
            schema=schema,
            behavior_specs=behavior_specs,
        )

        schema_valid = True
        schema_err = None
        if schema:
            schema_valid, schema_err = self.validate_schema(step_result.output, schema)

        behavior_valid = True
        behavior_errs: List[str] = []
        if behavior_specs:
            behavior_valid, behavior_errs = self.validate_behavior(
                action_name, step_result, behavior_specs
            )

        return {
            "action_name": action_name,
            "passed": passed,
            "execution_success": step_result.success,
            "schema_valid": schema_valid,
            "schema_error": schema_err,
            "behavior_valid": behavior_valid,
            "behavior_errors": behavior_errs,
            "reasons": list(self.last_failure_reasons),
            "escalation_required": not passed,
        }
