"""Integration tests for ObjectiveOracleGate and WorkCompiler 8-Tier Lowering Pipeline.

Tests:
1. ObjectiveOracleGate Frugal-style schema and behavior contract validation & escalation.
2. WorkCompiler integration with DeterminismAnalyzer, PredictionAnalyzer, and SLMAnalyzer.
3. Automatic lowering across the 8-tier executor hierarchy (Code/Rule -> ML -> SLM -> Frontier LLM -> Human).
4. End-to-end compiled Work IR validation and YAML serialization.
"""

import unittest
from typing import Any, Dict, List

from core.compiler.compiler import WorkCompiler
from core.runtime.executors import ActionResult
from core.runtime.oracle_gate import ObjectiveOracleGate
from core.validation.classifier import BehaviorCategory
from core.validation.quality_record import BehaviorVerdict
from core.work_ir.work_ir import ExecutorType, load_work_ir, to_yaml, validate_work_ir
from protocols.traces.trace_ir import TraceIR, TraceResult, TraceStep


class TestObjectiveOracleGate(unittest.TestCase):
    """Tests for ObjectiveOracleGate validation and Frugal escalation."""

    def setUp(self) -> None:
        self.oracle = ObjectiveOracleGate()

    def test_oracle_success_clean_output(self) -> None:
        """Test that a valid result passing schema and behaviors returns True."""
        result = ActionResult.ok(
            output={
                "contract_id": "CTR-101",
                "customer_name": "Acme Corp",
                "annual_value": 50000.0,
                "status": "active",
            }
        )
        schema = {
            "type": "object",
            "required": ["contract_id", "customer_name", "annual_value"],
            "properties": {
                "contract_id": {"type": "string"},
                "customer_name": {"type": "string"},
                "annual_value": {"type": "number"},
            },
        }
        passed = self.oracle.evaluate_oracle(
            action_name="lookup_contract",
            step_result=result,
            schema=schema,
        )
        self.assertTrue(passed)
        self.assertEqual(len(self.oracle.last_failure_reasons), 0)

    def test_oracle_fails_on_execution_error(self) -> None:
        """Test that ActionResult failure immediately fails oracle and triggers escalation."""
        result = ActionResult.fail(error="Connection timeout to CRM database")
        passed = self.oracle.evaluate_oracle(
            action_name="lookup_contract",
            step_result=result,
        )
        self.assertFalse(passed)
        self.assertTrue(any("Execution failed" in r for r in self.oracle.last_failure_reasons))

    def test_oracle_fails_on_missing_schema_field(self) -> None:
        """Test that missing required fields fail schema validation (Frugal escalation)."""
        result = ActionResult.ok(
            output={"contract_id": "CTR-101"}  # Missing required 'customer_name'
        )
        schema = {
            "type": "object",
            "required": ["contract_id", "customer_name"],
        }
        passed = self.oracle.evaluate_oracle(
            action_name="lookup_contract",
            step_result=result,
            schema=schema,
        )
        self.assertFalse(passed)
        self.assertTrue(any("Missing required field" in r for r in self.oracle.last_failure_reasons))

    def test_oracle_fails_on_schema_type_mismatch(self) -> None:
        """Test that field type mismatches fail schema validation."""
        result = ActionResult.ok(
            output={"contract_id": "CTR-101", "annual_value": "not-a-number"}
        )
        schema = {
            "type": "object",
            "required": ["contract_id", "annual_value"],
            "properties": {
                "contract_id": {"type": "string"},
                "annual_value": {"type": "number"},
            },
        }
        passed = self.oracle.evaluate_oracle(
            action_name="lookup_contract",
            step_result=result,
            schema=schema,
        )
        self.assertFalse(passed)
        self.assertTrue(any("annual_value" in r for r in self.oracle.last_failure_reasons))

    def test_oracle_nested_array_and_numeric_bounds(self) -> None:
        """Test array length constraints and numeric range validations."""
        schema = {
            "type": "object",
            "required": ["items", "discount_rate"],
            "properties": {
                "items": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "items": {"type": "string"},
                },
                "discount_rate": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 0.25,
                },
            },
        }

        # Valid payload
        valid_res = ActionResult.ok(
            output={"items": ["pro_license", "support_addon"], "discount_rate": 0.15}
        )
        self.assertTrue(self.oracle.evaluate_oracle("price_offer", valid_res, schema=schema))

        # Invalid discount exceeding max bound
        invalid_res = ActionResult.ok(
            output={"items": ["pro_license"], "discount_rate": 0.35}
        )
        self.assertFalse(self.oracle.evaluate_oracle("price_offer", invalid_res, schema=schema))
        self.assertTrue(any("greater than maximum" in r for r in self.oracle.last_failure_reasons))

    def test_oracle_behavior_prohibition_check(self) -> None:
        """Test that forbidden terms or hallucinated keywords trigger behavior failure."""
        result = ActionResult.ok(
            output={"proposal": "We guarantee a 99% discount with undefined terms."}
        )
        behavior_specs = [
            {
                "name": "no-undefined-terms",
                "action": "draft_proposal",
                "forbidden_terms": ["undefined", "NaN", "null_pointer"],
            }
        ]
        passed = self.oracle.evaluate_oracle(
            action_name="draft_proposal",
            step_result=result,
            behavior_specs=behavior_specs,
        )
        self.assertFalse(passed)
        self.assertTrue(any("forbidden term 'undefined'" in r for r in self.oracle.last_failure_reasons))

    def test_oracle_behavior_custom_assertion(self) -> None:
        """Test evaluating custom callable assertion rules in behavior contracts."""
        result = ActionResult.ok(output={"discount_percent": 35.0})
        behavior_specs = [
            {
                "name": "max-discount-policy",
                "action": "price_offer",
                "assertion": lambda out: out.get("discount_percent", 0) <= 20.0,
            }
        ]
        passed = self.oracle.evaluate_oracle(
            action_name="price_offer",
            step_result=result,
            behavior_specs=behavior_specs,
        )
        self.assertFalse(passed)
        self.assertTrue(any("assertion callable returned False" in r for r in self.oracle.last_failure_reasons))

    def test_oracle_behavior_rule_expression_evaluation(self) -> None:
        """Test evaluating string comparison rule expressions in behavior contracts."""
        behavior_specs = [
            {
                "name": "status-active-rule",
                "action": "lookup_contract",
                "rule": "status == active",
            }
        ]
        # Matching active status
        ok_res = ActionResult.ok(output={"status": "active", "id": "100"})
        self.assertTrue(self.oracle.evaluate_oracle("lookup_contract", ok_res, behavior_specs=behavior_specs))

        # Non-matching expired status
        bad_res = ActionResult.ok(output={"status": "expired", "id": "100"})
        self.assertFalse(self.oracle.evaluate_oracle("lookup_contract", bad_res, behavior_specs=behavior_specs))

    def test_oracle_behavior_explicit_verdict_false(self) -> None:
        """Test that an explicit behavior verdict of 'false' in metadata triggers escalation."""
        result = ActionResult.ok(
            output={"price": 100.0},
            metadata={"behavior_verdicts": {"verify-contract": BehaviorVerdict.FALSE}},
        )
        passed = self.oracle.evaluate_oracle(
            action_name="price_offer",
            step_result=result,
            behavior_specs=[{"name": "verify-contract"}],
        )
        self.assertFalse(passed)
        self.assertTrue(any("verdict: false" in r for r in self.oracle.last_failure_reasons))

    def test_oracle_explain_verdict(self) -> None:
        """Test explain_verdict breakdown report."""
        result = ActionResult.ok(output={"total": 100.0})
        schema = {"type": "object", "required": ["total"]}
        explanation = self.oracle.explain_verdict(
            action_name="calculate_total",
            step_result=result,
            schema=schema,
        )
        self.assertTrue(explanation["passed"])
        self.assertTrue(explanation["schema_valid"])
        self.assertFalse(explanation["escalation_required"])


class TestCompiler8TierLowering(unittest.TestCase):
    """Integration tests for WorkCompiler 8-tier hierarchy lowering pipeline."""

    def setUp(self) -> None:
        self.compiler = WorkCompiler()

    def test_compile_pipeline_lowering_all_tiers(self) -> None:
        """Test full pipeline compiling traces across Code, Rule, ML, SLM, and Human tiers."""
        # Recorded trace covering multiple tiers
        steps = [
            # Tier 1 / 2: SQL / Database query -> Code
            TraceStep(
                actor="tool",
                action="crm.lookup_contract",
                timestamp="2026-08-28T10:00:00Z",
                input={"customer_id": "C-901"},
                output={"contract_id": "K-901", "tier": "enterprise", "mrr": 5000},
                latency_ms=80.0,
            ),
            # Tier 4: Deterministic calculation -> Code
            TraceStep(
                actor="agent",
                action="services.usage.calculate",
                timestamp="2026-08-28T10:01:00Z",
                input={"mrr": 5000, "overage_units": 100},
                output={"total_usage_cost": 5200.0},
                latency_ms=10.0,
            ),
            # Tier 3: Business rule / pricing -> Rule
            TraceStep(
                actor="agent",
                action="rules.price_offer",
                timestamp="2026-08-28T10:02:00Z",
                input={"tier": "enterprise", "usage": 5200.0},
                output={"discount_percent": 10.0, "final_annual_price": 56160.0},
                latency_ms=5.0,
            ),
            # Tier 5: Statistical ML prediction -> ML
            TraceStep(
                actor="agent",
                action="classify_ticket",
                timestamp="2026-08-28T10:03:00Z",
                input={"subject": "Urgent renewal upgrade", "tier": "enterprise"},
                output={"category": "billing"},
                latency_ms=30.0,
            ),
            # Tier 7: Generative text drafting -> SLM
            TraceStep(
                actor="agent",
                action="draft_proposal",
                timestamp="2026-08-28T10:04:00Z",
                input={"customer": "Acme", "price": 56160.0},
                output={"proposal": "Dear Acme, we present your renewal offer at $56,160/year."},
                latency_ms=650.0,
                token_usage={"prompt_tokens": 150, "completion_tokens": 80, "total_tokens": 230},
            ),
            # Tier 9: Human approval gate -> Human
            TraceStep(
                actor="human",
                action="approve_proposal",
                timestamp="2026-08-28T10:05:00Z",
                input={"proposal_id": "P-901"},
                output={"approved": True},
                latency_ms=3600.0,
            ),
            # Tier 4: HTTP Connector -> Code / HTTP
            TraceStep(
                actor="tool",
                action="connectors.email.send",
                timestamp="2026-08-28T10:06:00Z",
                input={"to": "client@acme.com", "subject": "Renewal"},
                output={"sent": True},
                latency_ms=120.0,
            ),
        ]

        trace = TraceIR(
            run_id="run-pipeline-01",
            source_agent="openworker",
            steps=steps,
            result=TraceResult(status="success"),
        )

        behaviors = [
            {
                "name": "pricing-policy-check",
                "category": BehaviorCategory.RULE_POLICY.value,
                "evidence": "Pricing discount must follow policy rules",
            },
            {
                "name": "approval-before-send",
                "category": BehaviorCategory.WORKFLOW_TRANSITION.value,
                "evidence": "approve_proposal before send_email",
            },
        ]

        work_ir = self.compiler.compile_traces_to_work_ir(
            traces=[trace],
            behaviors=behaviors,
            target_name="enterprise-renewal",
            description="End-to-end compiled enterprise renewal pipeline",
        )

        self.assertIsNotNone(work_ir)
        self.assertEqual(work_ir.work, "enterprise-renewal")

        # Verify executors lowered according to 8-tier hierarchy:
        execs = work_ir.executors

        # 1. lookup_contract -> CODE
        self.assertIn("lookup_contract", execs)
        self.assertEqual(execs["lookup_contract"].type, ExecutorType.CODE)

        # 2. calculate_usage -> CODE
        self.assertIn("calculate_usage", execs)
        self.assertEqual(execs["calculate_usage"].type, ExecutorType.CODE)

        # 3. price_offer -> RULE
        self.assertIn("price_offer", execs)
        self.assertEqual(execs["price_offer"].type, ExecutorType.RULE)

        # 4. classify_ticket -> ML
        self.assertIn("classify_ticket", execs)
        self.assertEqual(execs["classify_ticket"].type, ExecutorType.ML)

        # 5. draft_proposal -> SLM
        self.assertIn("draft_proposal", execs)
        self.assertEqual(execs["draft_proposal"].type, ExecutorType.SLM)
        self.assertIn("frontier_llm", execs["draft_proposal"].fallback)

        # 6. approve_proposal -> HUMAN
        self.assertIn("approve_proposal", execs)
        self.assertEqual(execs["approve_proposal"].type, ExecutorType.HUMAN)

        # 7. send_email -> CODE
        self.assertIn("send_email", execs)
        self.assertEqual(execs["send_email"].type, ExecutorType.CODE)

        # Verify SLM training candidate was synthesized
        self.assertIn("draft_proposal", self.compiler.training_candidates)
        candidate = self.compiler.training_candidates["draft_proposal"]
        self.assertEqual(candidate.action_name, "draft_proposal")
        self.assertEqual(candidate.target_executor_type, "slm")

        # Verify WorkIR validation and YAML roundtrip
        validate_work_ir(work_ir)
        yaml_str = to_yaml(work_ir)
        self.assertIn("work: enterprise-renewal", yaml_str)
        self.assertIn("price_offer", yaml_str)
        reloaded = load_work_ir(yaml_str)
        self.assertEqual(reloaded.work, "enterprise-renewal")

    def test_vector_search_lowering(self) -> None:
        """Test lowering vector / semantic search actions to Tier 6."""
        steps = [
            TraceStep(
                actor="agent",
                action="vector_search_kb",
                timestamp="2026-08-28T12:00:00Z",
                input={"query": "how to handle late invoice payment"},
                output={"top_doc": "KB-291: Payment Grace Period Policy"},
            )
        ]
        trace = TraceIR(
            run_id="run-vector-01",
            source_agent="custom",
            steps=steps,
            result=TraceResult(status="success"),
        )
        work_ir = self.compiler.compile_traces_to_work_ir(
            traces=[trace],
            behaviors=[],
            target_name="kb-search",
        )
        exec_cfg = work_ir.executors["vector_search_kb"]
        self.assertEqual(exec_cfg.type, ExecutorType.CODE)
        self.assertIn("vector", exec_cfg.handler)

    def test_residual_frontier_llm_for_unconstrained_tasks(self) -> None:
        """Test that open-ended complex reasoning steps fallback to Frontier LLM."""
        steps = [
            TraceStep(
                actor="agent",
                action="reason_strategic_pivot",
                timestamp="2026-08-28T11:00:00Z",
                input={"context": "Market shift detected"},
                output={"strategy": "Explore alternative pivot options"},
                token_usage={"prompt_tokens": 500, "completion_tokens": 300, "total_tokens": 800},
            )
        ]
        trace = TraceIR(
            run_id="run-complex-01",
            source_agent="custom",
            steps=steps,
            result=TraceResult(status="success"),
        )

        work_ir = self.compiler.compile_traces_to_work_ir(
            traces=[trace],
            behaviors=[],
            target_name="strategy-pivot",
        )

        exec_cfg = work_ir.executors["reason_strategic_pivot"]
        self.assertEqual(exec_cfg.type, ExecutorType.FRONTIER_LLM)
        self.assertEqual(exec_cfg.fallback, ["human"])


if __name__ == "__main__":
    unittest.main()
