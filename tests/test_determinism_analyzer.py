"""Unit tests for DeterminismAnalyzer in OpenWorkCompiler WorkCompiler."""

import unittest
from typing import Any, Dict, List

from core.compiler.analyzers.determinism import DeterminismAnalyzer
from core.work_ir.trace_ir import TraceIR, TraceResult, TraceStatus
from core.work_ir.trace_ir import TraceStep as CoreTraceStep
from protocols.traces.trace_ir import TraceStep as ProtocolTraceStep


class TestDeterminismAnalyzerArithmetic(unittest.TestCase):
    """Test suite for arithmetic calculation and math operation detection."""

    def setUp(self) -> None:
        self.analyzer = DeterminismAnalyzer()

    def test_detect_addition(self) -> None:
        step = CoreTraceStep(
            actor="agent",
            action="calculate_total",
            input={"subtotal": 100.0, "shipping": 15.5},
            output={"total": 115.5},
        )
        res = self.analyzer.analyze_step(step)
        self.assertIsNotNone(res)
        self.assertEqual(res["target_executor"], "code")
        self.assertEqual(res["pattern_type"], "arithmetic")
        self.assertEqual(res["confidence_score"], 1.0)
        self.assertIn("subtotal + shipping", res["details"]["formula"])

    def test_detect_subtraction(self) -> None:
        step = {
            "actor": "worker",
            "action": "compute_net_profit",
            "input": {"revenue": 5000, "expenses": 3200},
            "output": {"net_profit": 1800},
        }
        res = self.analyzer.analyze_step(step)
        self.assertIsNotNone(res)
        self.assertEqual(res["target_executor"], "code")
        self.assertEqual(res["pattern_type"], "arithmetic")
        self.assertEqual(res["confidence_score"], 1.0)
        self.assertIn("revenue - expenses", res["details"]["formula"])

    def test_detect_multiplication(self) -> None:
        step = ProtocolTraceStep(
            actor="agent",
            action="calculate_line_item",
            timestamp="2026-08-28T00:00:00Z",
            input={"unit_price": 24.5, "quantity": 4},
            output={"total_price": 98.0},
        )
        res = self.analyzer.analyze_step(step)
        self.assertIsNotNone(res)
        self.assertEqual(res["target_executor"], "code")
        self.assertEqual(res["pattern_type"], "arithmetic")
        self.assertEqual(res["confidence_score"], 1.0)
        self.assertIn("unit_price * quantity", res["details"]["formula"])

    def test_detect_division(self) -> None:
        step = {
            "actor": "tool",
            "action": "calc_average_rate",
            "input": {"total_cost": 500.0, "hours": 10.0},
            "output": {"hourly_rate": 50.0},
        }
        res = self.analyzer.analyze_step(step)
        self.assertIsNotNone(res)
        self.assertEqual(res["target_executor"], "code")
        self.assertEqual(res["pattern_type"], "arithmetic")
        self.assertEqual(res["confidence_score"], 1.0)
        self.assertIn("total_cost / hours", res["details"]["formula"])

    def test_detect_discount_percentage(self) -> None:
        step = {
            "actor": "agent",
            "action": "apply_discount",
            "input": {"original_price": 200.0, "discount_rate": 0.15},
            "output": {"discounted_price": 170.0},
        }
        res = self.analyzer.analyze_step(step)
        self.assertIsNotNone(res)
        self.assertEqual(res["pattern_type"], "arithmetic")
        self.assertEqual(res["confidence_score"], 1.0)
        self.assertEqual(res["details"]["operation"], "discount")

    def test_detect_tax_markup(self) -> None:
        step = {
            "actor": "agent",
            "action": "apply_tax",
            "input": {"amount": 100.0, "tax_rate": 0.08},
            "output": {"final_amount": 108.0},
        }
        res = self.analyzer.analyze_step(step)
        self.assertIsNotNone(res)
        self.assertEqual(res["pattern_type"], "arithmetic")
        self.assertEqual(res["confidence_score"], 1.0)
        self.assertEqual(res["details"]["operation"], "markup_or_tax")

    def test_detect_list_sum(self) -> None:
        step = {
            "actor": "tool",
            "action": "sum_invoices",
            "input": {"amounts": [100.0, 250.0, 50.0, 100.0]},
            "output": {"grand_total": 500.0},
        }
        res = self.analyzer.analyze_step(step)
        self.assertIsNotNone(res)
        self.assertEqual(res["target_executor"], "code")
        self.assertEqual(res["pattern_type"], "arithmetic")
        self.assertEqual(res["details"]["operation"], "sum_list")
        self.assertEqual(res["confidence_score"], 1.0)

    def test_detect_list_average(self) -> None:
        step = {
            "actor": "tool",
            "action": "compute_average",
            "input": {"scores": [80.0, 90.0, 100.0]},
            "output": {"mean_score": 90.0},
        }
        res = self.analyzer.analyze_step(step)
        self.assertIsNotNone(res)
        self.assertEqual(res["pattern_type"], "arithmetic")
        self.assertEqual(res["details"]["operation"], "average_list")
        self.assertEqual(res["confidence_score"], 1.0)

    def test_detect_pricing_rule_executor(self) -> None:
        step = {
            "actor": "agent",
            "action": "pricing_discount_policy",
            "input": {"price": 1000.0, "discount_rate": 0.20},
            "output": {"price_after_discount": 800.0},
        }
        res = self.analyzer.analyze_step(step)
        self.assertIsNotNone(res)
        self.assertEqual(res["target_executor"], "rule")
        self.assertTrue(res["handler"].startswith("rules."))


class TestDeterminismAnalyzerStringFormatting(unittest.TestCase):
    """Test suite for string formatting, interpolation, and transformations."""

    def setUp(self) -> None:
        self.analyzer = DeterminismAnalyzer()

    def test_detect_case_transforms(self) -> None:
        # Uppercase
        step_upper = {
            "actor": "worker",
            "action": "to_uppercase",
            "input": {"code": "us_east_1"},
            "output": {"upper_code": "US_EAST_1"},
        }
        res_upper = self.analyzer.analyze_step(step_upper)
        self.assertIsNotNone(res_upper)
        self.assertEqual(res_upper["target_executor"], "code")
        self.assertEqual(res_upper["pattern_type"], "string_formatting")
        self.assertEqual(res_upper["details"]["transform"], "upper")

        # Lowercase
        step_lower = {
            "actor": "worker",
            "action": "normalize_email",
            "input": {"raw_email": "ALICE@EXAMPLE.COM"},
            "output": {"email": "alice@example.com"},
        }
        res_lower = self.analyzer.analyze_step(step_lower)
        self.assertIsNotNone(res_lower)
        self.assertEqual(res_lower["details"]["transform"], "lower")

        # Strip whitespace
        step_strip = {
            "actor": "worker",
            "action": "clean_input",
            "input": {"text": "  some messy text \t "},
            "output": {"cleaned": "some messy text"},
        }
        res_strip = self.analyzer.analyze_step(step_strip)
        self.assertIsNotNone(res_strip)
        self.assertEqual(res_strip["details"]["transform"], "strip")

    def test_detect_slugify(self) -> None:
        step = {
            "actor": "worker",
            "action": "generate_slug",
            "input": {"title": "Open Workflow 2026 Architecture"},
            "output": {"slug": "open_workflow_2026_architecture"},
        }
        res = self.analyzer.analyze_step(step)
        self.assertIsNotNone(res)
        self.assertEqual(res["target_executor"], "code")
        self.assertEqual(res["details"]["transform"], "slugify")

    def test_detect_string_concatenation(self) -> None:
        step = {
            "actor": "worker",
            "action": "build_full_name",
            "input": {"first_name": "Ada", "last_name": "Lovelace"},
            "output": {"full_name": "Ada Lovelace"},
        }
        res = self.analyzer.analyze_step(step)
        self.assertIsNotNone(res)
        self.assertEqual(res["target_executor"], "code")
        self.assertEqual(res["pattern_type"], "string_formatting")
        self.assertEqual(res["details"]["separator"], " ")

    def test_detect_template_interpolation(self) -> None:
        step = {
            "actor": "agent",
            "action": "render_confirmation",
            "input": {"user": "Bob", "order_id": "ORD-7890"},
            "output": {"message": "Hello Bob, your order ORD-7890 has been received!"},
        }
        res = self.analyzer.analyze_step(step)
        self.assertIsNotNone(res)
        self.assertEqual(res["target_executor"], "code")
        self.assertEqual(res["pattern_type"], "string_formatting")
        self.assertIn("{user}", res["details"]["template"])
        self.assertIn("{order_id}", res["details"]["template"])
        self.assertGreaterEqual(res["confidence_score"], 0.95)

    def test_detect_email_template_action(self) -> None:
        step = {
            "actor": "agent",
            "action": "format_email_template",
            "input": {"customer": "Acme Corp", "renewal_date": "2026-12-31"},
            "output": {"body": "Dear Acme Corp, renewal deadline is 2026-12-31."},
        }
        res = self.analyzer.analyze_step(step)
        self.assertIsNotNone(res)
        self.assertEqual(res["target_executor"], "code")
        self.assertEqual(res["pattern_type"], "string_formatting")


class TestDeterminismAnalyzerLookup(unittest.TestCase):
    """Test suite for dictionary, database, CRM, and cross-step lookups."""

    def setUp(self) -> None:
        self.analyzer = DeterminismAnalyzer()

    def test_detect_in_step_dictionary_lookup(self) -> None:
        step = {
            "actor": "worker",
            "action": "get_tier_rate",
            "input": {
                "rates": {"standard": 10.0, "pro": 25.0, "enterprise": 50.0},
                "tier": "enterprise",
            },
            "output": {"rate": 50.0},
        }
        res = self.analyzer.analyze_step(step)
        self.assertIsNotNone(res)
        self.assertEqual(res["target_executor"], "code")
        self.assertEqual(res["pattern_type"], "lookup")
        self.assertEqual(res["confidence_score"], 1.0)
        self.assertEqual(res["details"]["matched_value"], 50.0)

    def test_detect_cross_step_lookup_with_previous_steps(self) -> None:
        step_fetch = CoreTraceStep(
            actor="agent",
            action="crm.fetch_all_contracts",
            input={"org_id": "ORG-99"},
            output={
                "contracts": [
                    {"contract_id": "CTR-101", "name": "Alpha Tier", "seats": 10},
                    {"contract_id": "CTR-202", "name": "Beta Tier", "seats": 50},
                ]
            },
        )
        step_lookup = CoreTraceStep(
            actor="agent",
            action="get_selected_contract",
            input={"contract_id": "CTR-202"},
            output={"contract_id": "CTR-202", "name": "Beta Tier", "seats": 50},
        )

        res = self.analyzer.analyze_step(step_lookup, previous_steps=[step_fetch])
        self.assertIsNotNone(res)
        self.assertEqual(res["target_executor"], "code")
        self.assertEqual(res["pattern_type"], "lookup")
        self.assertEqual(res["details"]["lookup_id"], "CTR-202")
        self.assertGreaterEqual(res["confidence_score"], 0.95)

    def test_detect_action_based_crm_lookup(self) -> None:
        step = {
            "actor": "agent",
            "action": "crm.lookup_customer",
            "input": {"customer_id": "C-90210"},
            "output": {"name": "Wayne Enterprises", "tier": "enterprise"},
        }
        res = self.analyzer.analyze_step(step)
        self.assertIsNotNone(res)
        self.assertEqual(res["target_executor"], "code")
        self.assertEqual(res["pattern_type"], "lookup")
        self.assertIn("crm", res["handler"])


class TestDeterminismAnalyzerOtherPatterns(unittest.TestCase):
    """Test suite for rules, JSON transformations, HTTP calls, and negative cases."""

    def setUp(self) -> None:
        self.analyzer = DeterminismAnalyzer()

    def test_detect_rule_policy_evaluation(self) -> None:
        step = {
            "actor": "agent",
            "action": "rules.validate_eligibility",
            "input": {"credit_score": 750, "years_in_business": 5},
            "output": {"eligible": True, "status": "approved"},
        }
        res = self.analyzer.analyze_step(step)
        self.assertIsNotNone(res)
        self.assertEqual(res["target_executor"], "rule")
        self.assertEqual(res["pattern_type"], "pattern_matching")
        self.assertTrue(res["handler"].startswith("rules."))

    def test_detect_json_schema_transform(self) -> None:
        step = {
            "actor": "worker",
            "action": "transform_user_payload",
            "input": {
                "user_id": "U-1234",
                "raw_info": {"first": "Grace", "last": "Hopper", "role": "admin"},
                "extra_metadata": 999,
            },
            "output": {
                "id": "U-1234",
                "first_name": "Grace",
                "last_name": "Hopper",
                "admin_role": "admin",
            },
        }
        res = self.analyzer.analyze_step(step)
        self.assertIsNotNone(res)
        self.assertEqual(res["target_executor"], "code")
        self.assertEqual(res["pattern_type"], "json_transform")

    def test_detect_http_rest_call(self) -> None:
        step = {
            "actor": "tool",
            "action": "http_request",
            "input": {
                "url": "https://api.stripe.com/v1/charges",
                "method": "POST",
                "data": {"amount": 5000},
            },
            "output": {"status_code": 200, "charge_id": "ch_123"},
        }
        res = self.analyzer.analyze_step(step)
        self.assertIsNotNone(res)
        self.assertEqual(res["target_executor"], "http")
        self.assertEqual(res["pattern_type"], "http_call")
        self.assertIn("post", res["handler"].lower())

    def test_reject_non_deterministic_creative_generation(self) -> None:
        step = {
            "actor": "agent",
            "action": "draft_creative_essay",
            "input": {"topic": "The future of autonomous workflows in 2030"},
            "output": {
                "essay": (
                    "In a world where digital orchestration reigns supreme, autonomous "
                    "agents weave through complex decision spaces with unprecedented grace..."
                )
            },
        }
        res = self.analyzer.analyze_step(step)
        self.assertIsNone(res)

    def test_reject_open_ended_summarization(self) -> None:
        step = {
            "actor": "agent",
            "action": "summarize_discussion_notes",
            "input": {"raw_transcript": "Alice proposed X. Bob objected because of Y. Charlie suggested Z."},
            "output": {
                "summary": "The team deliberated on options X and Y before converging on Charlie's Z compromise."
            },
        }
        res = self.analyzer.analyze_step(step)
        self.assertIsNone(res)

    def test_empty_step_handling(self) -> None:
        empty_step = {"actor": "agent", "action": "noop", "input": {}, "output": {}}
        self.assertIsNone(self.analyzer.analyze_step(empty_step))

    def test_analyze_full_trace(self) -> None:
        steps = [
            CoreTraceStep(
                actor="agent",
                action="crm.lookup_customer",
                input={"customer_id": "C-1"},
                output={"name": "Acme", "plan": "Enterprise"},
            ),
            CoreTraceStep(
                actor="agent",
                action="calculate_total",
                input={"base": 100, "tax": 10},
                output={"total": 110},
            ),
            CoreTraceStep(
                actor="agent",
                action="draft_custom_summary",
                input={"notes": "Long meeting about renewal terms"},
                output={"summary": "Detailed strategic synthesis of meeting outcomes"},
            ),
        ]
        trace = TraceIR(
            run_id="run_test_det",
            source_agent="custom",
            steps=steps,
            result=TraceResult(status=TraceStatus.SUCCESS),
        )
        analyzed = self.analyzer.analyze_trace(trace)
        self.assertEqual(len(analyzed), 3)

        # Step 0: lookup -> deterministic
        self.assertIsNotNone(analyzed[0][1])
        self.assertEqual(analyzed[0][1]["pattern_type"], "lookup")

        # Step 1: math -> deterministic
        self.assertIsNotNone(analyzed[1][1])
        self.assertEqual(analyzed[1][1]["pattern_type"], "arithmetic")

        # Step 2: freeform synthesis -> non-deterministic (None)
        self.assertIsNone(analyzed[2][1])


if __name__ == "__main__":
    unittest.main()
