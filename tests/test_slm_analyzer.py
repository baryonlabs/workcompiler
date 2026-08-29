"""Unit tests for SLMAnalyzer in OpenWorkCompiler WorkCompiler."""

import pytest
from core.compiler.analyzers.slm import SLMAnalyzer
from protocols.traces.trace_ir import TraceStep


class TestSLMAnalyzer:
    """Test suite for SLMAnalyzer detection and SFT dataset synthesis."""

    @pytest.fixture
    def analyzer(self) -> SLMAnalyzer:
        return SLMAnalyzer(candidate_model_size="1.5B", base_model="Qwen/Qwen2.5-1.5B-Instruct")

    def test_email_intent_extraction_steps(self, analyzer: SLMAnalyzer):
        """Test analyzing email intent extraction trace steps."""
        steps = [
            TraceStep(
                actor="agent",
                action="email_intent_extraction",
                timestamp="2026-08-28T10:00:00Z",
                step_id="step-01",
                input={
                    "email": "Hi Team, We want to upgrade our subscription to the Enterprise plan for 100 seats.",
                    "sender": "alice@acmecorp.com",
                },
                output={
                    "intent": "subscription_upgrade",
                    "plan": "Enterprise",
                    "seats": 100,
                    "confidence": 0.98,
                },
            ),
            TraceStep(
                actor="agent",
                action="email_intent_extraction",
                timestamp="2026-08-28T10:05:00Z",
                step_id="step-02",
                input={
                    "email": "Please cancel our account at the end of the current billing cycle.",
                    "sender": "bob@example.org",
                },
                output={
                    "intent": "subscription_cancellation",
                    "effective_date": "end_of_billing_cycle",
                    "confidence": 0.95,
                },
            ),
        ]

        result = analyzer.analyze_steps("email_intent_extraction", steps)

        assert result is not None
        assert result["target_executor"] == "slm"
        assert result["candidate_model_size"] == "1.5B"
        assert result["sft_pairs_count"] == 2
        assert len(result["sft_dataset_sample"]) == 2
        assert result["task_type"] == "intent_extraction"
        assert result["base_model"] == "Qwen/Qwen2.5-1.5B-Instruct"

        # Verify SFT sample structure
        sample = result["sft_dataset_sample"][0]
        assert "instruction" in sample
        assert "input" in sample
        assert "output" in sample
        assert "messages" in sample
        assert "subscription_upgrade" in sample["output"]

        # Verify chat messages format for SFT training
        messages = sample["messages"]
        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"
        assert "intent extraction" in messages[0]["content"].lower()

    def test_support_summary_steps(self, analyzer: SLMAnalyzer):
        """Test analyzing support ticket and conversation summarization steps."""
        steps = [
            TraceStep(
                actor="agent",
                action="support_summary",
                timestamp="2026-08-28T11:00:00Z",
                step_id="step-10",
                input={
                    "ticket_id": "TCK-8821",
                    "transcript": "User reported 504 gateway timeout on /api/v2/checkout. Support team cleared CDN cache and restarted service. User verified checkout works.",
                },
                output={
                    "summary": "Resolved 504 gateway timeout on checkout API by clearing CDN cache and restarting service. Verified working.",
                    "category": "infrastructure",
                    "status": "resolved",
                },
            ),
            TraceStep(
                actor="agent",
                action="support_summary",
                timestamp="2026-08-28T11:15:00Z",
                step_id="step-11",
                input={
                    "ticket_id": "TCK-8822",
                    "transcript": "User requested MFA reset due to lost authenticator device. Identity verified via backup email and MFA reset issued.",
                },
                output={
                    "summary": "MFA reset completed after verifying customer identity via backup email.",
                    "category": "account_security",
                    "status": "resolved",
                },
            ),
        ]

        result = analyzer.analyze_steps("support_summary", steps)

        assert result is not None
        assert result["target_executor"] == "slm"
        assert result["candidate_model_size"] == "1.5B"
        assert result["sft_pairs_count"] == 2
        assert len(result["sft_dataset_sample"]) == 2
        assert result["task_type"] == "support_summary"

        sample = result["sft_dataset_sample"][0]
        assert "504 gateway timeout" in sample["output"]
        assert sample["messages"][0]["role"] == "system"
        assert "support" in sample["messages"][0]["content"].lower()

    def test_short_proposal_drafting_steps(self, analyzer: SLMAnalyzer):
        """Test analyzing short renewal and commercial proposal drafting steps."""
        steps = [
            TraceStep(
                actor="agent",
                action="short_proposal_drafting",
                timestamp="2026-08-28T12:00:00Z",
                step_id="step-20",
                input={
                    "customer_name": "Globex Corp",
                    "current_annual_spend": 120000,
                    "renewal_offer": "Enterprise Plus with 15% discount for 2-year commitment ($102,000/yr)",
                },
                output={
                    "proposal": "Dear Globex Corp Team, We are thrilled to present your renewal proposal for Enterprise Plus with a 15% multi-year discount at $102,000/yr.",
                    "subject": "Enterprise Plus Renewal Proposal for Globex Corp",
                },
            )
        ]

        result = analyzer.analyze_steps("short_proposal_drafting", steps)

        assert result is not None
        assert result["target_executor"] == "slm"
        assert result["candidate_model_size"] == "1.5B"
        assert result["sft_pairs_count"] == 1
        assert result["task_type"] == "proposal_drafting"
        assert "Globex Corp" in result["sft_dataset_sample"][0]["output"]

    def test_deterministic_and_arithmetic_steps_rejected(self, analyzer: SLMAnalyzer):
        """Test that deterministic calculation, lookup, and rule steps return None."""
        calc_steps = [
            TraceStep(
                actor="agent",
                action="calculate_usage",
                timestamp="2026-08-28T13:00:00Z",
                input={"tier": "pro", "api_calls": 150000, "rate_per_k": 0.02},
                output={"total_cost": 3.0, "currency": "USD"},
            )
        ]
        assert analyzer.analyze_steps("calculate_usage", calc_steps) is None

        lookup_steps = [
            TraceStep(
                actor="agent",
                action="lookup_contract",
                timestamp="2026-08-28T13:05:00Z",
                input={"contract_id": "CTR-991"},
                output={"contract_id": "CTR-991", "status": "active", "tier": "enterprise"},
            )
        ]
        assert analyzer.analyze_steps("lookup_contract", lookup_steps) is None

        rule_steps = [
            TraceStep(
                actor="agent",
                action="validate_tax_id",
                timestamp="2026-08-28T13:10:00Z",
                input={"tax_id": "US123456789"},
                output={"valid": True, "country": "US"},
            )
        ]
        assert analyzer.analyze_steps("validate_tax_id", rule_steps) is None

    def test_empty_or_invalid_steps(self, analyzer: SLMAnalyzer):
        """Test edge cases with empty steps, empty action, or steps with empty inputs/outputs."""
        assert analyzer.analyze_steps("", []) is None
        assert analyzer.analyze_steps("support_summary", []) is None

        empty_content_steps = [
            TraceStep(
                actor="agent",
                action="support_summary",
                timestamp="2026-08-28T14:00:00Z",
                input={},
                output={},
            )
        ]
        assert analyzer.analyze_steps("support_summary", empty_content_steps) is None

    def test_dictionary_format_steps_support(self, analyzer: SLMAnalyzer):
        """Test that dictionary-formatted steps are supported alongside TraceStep dataclasses."""
        dict_steps = [
            {
                "actor": "agent",
                "action": "extract_intent",
                "timestamp": "2026-08-28T15:00:00Z",
                "input": {"text": "I want a refund for order #1234"},
                "output": {"intent": "refund_request", "order_id": "1234"},
            }
        ]

        result = analyzer.analyze_steps("extract_intent", dict_steps)
        assert result is not None
        assert result["target_executor"] == "slm"
        assert result["sft_pairs_count"] == 1
        assert "refund_request" in result["sft_dataset_sample"][0]["output"]

    def test_helper_methods(self, analyzer: SLMAnalyzer):
        """Test helper classification methods on SLMAnalyzer."""
        assert analyzer.is_generative_task("email_intent_extraction") is True
        assert analyzer.is_generative_task("support_summary") is True
        assert analyzer.is_generative_task("short_proposal_drafting") is True
        assert analyzer.is_generative_task("calculate_usage") is False
        assert analyzer.is_generative_task("lookup_contract") is False

        assert analyzer.detect_task_type("email_intent_extraction") == "intent_extraction"
        assert analyzer.detect_task_type("summarize_ticket") == "support_summary"
        assert analyzer.detect_task_type("draft_renewal_proposal") == "proposal_drafting"
        assert analyzer.detect_task_type("calculate_usage") is None

    def test_custom_model_configuration(self):
        """Test custom model size and base model configurations."""
        custom_analyzer = SLMAnalyzer(
            candidate_model_size="3B",
            base_model="meta-llama/Llama-3.2-3B-Instruct",
            max_sample_display=1,
        )

        steps = [
            TraceStep(
                actor="agent",
                action="draft_proposal",
                timestamp="2026-08-28T16:00:00Z",
                input={"client": "Acme", "quote": "$5,000"},
                output={"proposal": "Proposal for Acme: total quote $5,000."},
            ),
            TraceStep(
                actor="agent",
                action="draft_proposal",
                timestamp="2026-08-28T16:05:00Z",
                input={"client": "Beta", "quote": "$8,000"},
                output={"proposal": "Proposal for Beta: total quote $8,000."},
            ),
        ]

        result = custom_analyzer.analyze_steps("draft_proposal", steps)
        assert result is not None
        assert result["candidate_model_size"] == "3B"
        assert result["base_model"] == "meta-llama/Llama-3.2-3B-Instruct"
        assert result["sft_pairs_count"] == 2
        # max_sample_display was set to 1
        assert len(result["sft_dataset_sample"]) == 1
        # full dataset still contains all 2
        assert len(result["sft_dataset"]) == 2
