"""Unit tests for PredictionAnalyzer in OpenWorkflow WorkCompiler.

Tests detection of traditional ML lowering candidates:
- Categorical classification (ticket classification, fraud detection, churn tiers)
- Numerical score outputs (lead scoring, priority rating, risk scores)
- Extraction of training datasets (X features, y targets)
- Trace-level multi-action analysis
- Negative cases (generative text, high cardinality UUIDs, insufficient samples)
"""

import pytest

from core.compiler.analyzers.prediction import PredictionAnalyzer
from protocols.traces.trace_ir import TraceIR, TraceResult, TraceStep


class TestPredictionAnalyzerCategorical:
    """Tests for categorical classification candidate detection."""

    def test_ticket_classification_categorical(self):
        """Test multi-class ticket classification with mixed structured features."""
        analyzer = PredictionAnalyzer(min_samples=3)
        steps = [
            TraceStep(
                actor="agent",
                action="classify_ticket",
                timestamp="2026-08-28T10:00:00Z",
                input={
                    "ticket_id": "T-101",
                    "subject": "Billing issue with monthly invoice",
                    "customer_tier": "enterprise",
                    "account_age_days": 180,
                    "previous_tickets": 2,
                },
                output={"category": "billing"},
            ),
            TraceStep(
                actor="agent",
                action="classify_ticket",
                timestamp="2026-08-28T10:01:00Z",
                input={
                    "ticket_id": "T-102",
                    "subject": "Feature request for dark mode UI",
                    "customer_tier": "starter",
                    "account_age_days": 15,
                    "previous_tickets": 0,
                },
                output={"category": "product"},
            ),
            TraceStep(
                actor="agent",
                action="classify_ticket",
                timestamp="2026-08-28T10:02:00Z",
                input={
                    "ticket_id": "T-103",
                    "subject": "500 Internal Server Error on API webhook",
                    "customer_tier": "pro",
                    "account_age_days": 450,
                    "previous_tickets": 8,
                },
                output={"category": "technical"},
            ),
            TraceStep(
                actor="agent",
                action="classify_ticket",
                timestamp="2026-08-28T10:03:00Z",
                input={
                    "ticket_id": "T-104",
                    "subject": "Payment failed for annual renewal",
                    "customer_tier": "enterprise",
                    "account_age_days": 365,
                    "previous_tickets": 1,
                },
                output={"category": "billing"},
            ),
        ]

        result = analyzer.analyze_steps("classify_ticket", steps)
        assert result is not None
        assert result["target_executor"] == "ml"
        assert result["model_type"] in ["scikit_learn", "xgboost"]
        assert result["task_type"] == "classification"
        assert result["target_field"] == "category"
        assert result["training_sample_count"] == 4
        assert sorted(result["label_space"]) == ["billing", "product", "technical"]
        assert "customer_tier" in result["feature_names"]
        assert "account_age_days" in result["feature_names"]
        assert "subject" in result["feature_names"]

    def test_fraud_check_binary_classification(self):
        """Test binary classification for fraud detection on tabular features."""
        analyzer = PredictionAnalyzer(min_samples=2)
        steps = [
            TraceStep(
                actor="agent",
                action="fraud_check",
                timestamp="2026-08-28T11:00:00Z",
                input={
                    "transaction_amount": 1500.0,
                    "location_country": "US",
                    "card_present": False,
                    "velocity_last_24h": 8,
                    "is_new_device": True,
                },
                output={"is_fraud": True},
            ),
            TraceStep(
                actor="agent",
                action="fraud_check",
                timestamp="2026-08-28T11:01:00Z",
                input={
                    "transaction_amount": 25.50,
                    "location_country": "US",
                    "card_present": True,
                    "velocity_last_24h": 1,
                    "is_new_device": False,
                },
                output={"is_fraud": False},
            ),
            TraceStep(
                actor="agent",
                action="fraud_check",
                timestamp="2026-08-28T11:02:00Z",
                input={
                    "transaction_amount": 3400.0,
                    "location_country": "RU",
                    "card_present": False,
                    "velocity_last_24h": 14,
                    "is_new_device": True,
                },
                output={"is_fraud": True},
            ),
            TraceStep(
                actor="agent",
                action="fraud_check",
                timestamp="2026-08-28T11:03:00Z",
                input={
                    "transaction_amount": 42.00,
                    "location_country": "CA",
                    "card_present": True,
                    "velocity_last_24h": 2,
                    "is_new_device": False,
                },
                output={"is_fraud": False},
            ),
        ]

        result = analyzer.analyze_steps("fraud_check", steps)
        assert result is not None
        assert result["target_executor"] == "ml"
        assert result["model_type"] == "xgboost"  # Dense numerical/boolean tabular data
        assert result["task_type"] == "classification"
        assert result["target_field"] == "is_fraud"
        assert result["training_sample_count"] == 4
        assert result["label_space"] == [False, True]
        assert "transaction_amount" in result["feature_names"]
        assert "card_present" in result["feature_names"]

    def test_nested_input_feature_extraction(self):
        """Test extraction of nested dictionary fields into flattened feature names."""
        analyzer = PredictionAnalyzer(min_samples=2)
        steps = [
            TraceStep(
                actor="agent",
                action="predict_churn",
                timestamp="2026-08-28T12:00:00Z",
                input={
                    "user": {"age": 34, "country": "US"},
                    "metrics": {"monthly_spend": 250.0, "active_days": 28},
                },
                output={"churn_risk": "low"},
            ),
            TraceStep(
                actor="agent",
                action="predict_churn",
                timestamp="2026-08-28T12:01:00Z",
                input={
                    "user": {"age": 22, "country": "UK"},
                    "metrics": {"monthly_spend": 10.0, "active_days": 2},
                },
                output={"churn_risk": "high"},
            ),
        ]

        result = analyzer.analyze_steps("predict_churn", steps)
        assert result is not None
        assert result["target_executor"] == "ml"
        assert result["task_type"] == "classification"
        assert sorted(result["label_space"]) == ["high", "low"]
        assert "user.age" in result["feature_names"]
        assert "user.country" in result["feature_names"]
        assert "metrics.monthly_spend" in result["feature_names"]
        assert "metrics.active_days" in result["feature_names"]


class TestPredictionAnalyzerNumericalScore:
    """Tests for numerical score / continuous regression candidate detection."""

    def test_lead_scoring_numerical(self):
        """Test lead scoring with continuous numerical probability/score output."""
        analyzer = PredictionAnalyzer(min_samples=3)
        steps = [
            TraceStep(
                actor="agent",
                action="score_lead",
                timestamp="2026-08-28T13:00:00Z",
                input={
                    "company_size": 250,
                    "annual_revenue": 10000000,
                    "website_visits": 45,
                    "industry": "fintech",
                    "decision_maker_title": "CTO",
                },
                output={"lead_score": 0.88},
            ),
            TraceStep(
                actor="agent",
                action="score_lead",
                timestamp="2026-08-28T13:01:00Z",
                input={
                    "company_size": 10,
                    "annual_revenue": 200000,
                    "website_visits": 3,
                    "industry": "retail",
                    "decision_maker_title": "Intern",
                },
                output={"lead_score": 0.12},
            ),
            TraceStep(
                actor="agent",
                action="score_lead",
                timestamp="2026-08-28T13:02:00Z",
                input={
                    "company_size": 1200,
                    "annual_revenue": 85000000,
                    "website_visits": 110,
                    "industry": "enterprise_saas",
                    "decision_maker_title": "VP_Eng",
                },
                output={"lead_score": 0.95},
            ),
            TraceStep(
                actor="agent",
                action="score_lead",
                timestamp="2026-08-28T13:03:00Z",
                input={
                    "company_size": 60,
                    "annual_revenue": 3000000,
                    "website_visits": 18,
                    "industry": "healthcare",
                    "decision_maker_title": "Director_IT",
                },
                output={"lead_score": 0.54},
            ),
        ]

        result = analyzer.analyze_steps("score_lead", steps)
        assert result is not None
        assert result["target_executor"] == "ml"
        assert result["model_type"] == "xgboost"
        assert result["task_type"] == "regression"
        assert result["target_field"] == "lead_score"
        assert result["label_space"] == ["continuous"]
        assert result["training_sample_count"] == 4
        assert "annual_revenue" in result["feature_names"]
        assert "company_size" in result["feature_names"]
        assert "website_visits" in result["feature_names"]

    def test_priority_rating_numerical_score(self):
        """Test continuous priority rating score detection."""
        analyzer = PredictionAnalyzer(min_samples=3)
        steps = [
            TraceStep(
                actor="agent",
                action="rate_priority",
                timestamp="2026-08-28T14:00:00Z",
                input={
                    "sla_remaining_hours": 2.5,
                    "customer_mrr": 5000.0,
                    "severity_code": 1,
                },
                output={"priority_rating": 9.4},
            ),
            TraceStep(
                actor="agent",
                action="rate_priority",
                timestamp="2026-08-28T14:01:00Z",
                input={
                    "sla_remaining_hours": 48.0,
                    "customer_mrr": 50.0,
                    "severity_code": 4,
                },
                output={"priority_rating": 1.2},
            ),
            TraceStep(
                actor="agent",
                action="rate_priority",
                timestamp="2026-08-28T14:02:00Z",
                input={
                    "sla_remaining_hours": 12.0,
                    "customer_mrr": 1200.0,
                    "severity_code": 2,
                },
                output={"priority_rating": 6.8},
            ),
        ]

        result = analyzer.analyze_steps("rate_priority", steps)
        assert result is not None
        assert result["target_executor"] == "ml"
        assert result["model_type"] == "xgboost"
        assert result["task_type"] == "regression"
        assert result["target_field"] == "priority_rating"
        assert result["label_space"] == ["continuous"]
        assert result["training_sample_count"] == 3


class TestTrainingDatasetExtraction:
    """Tests for extracting (X, y) datasets for model training."""

    def test_extract_training_dataset_success(self):
        """Test paired X and y extraction from valid trace steps."""
        analyzer = PredictionAnalyzer(min_samples=2)
        steps = [
            TraceStep(
                actor="agent",
                action="classify_ticket",
                timestamp="2026-08-28T10:00:00Z",
                input={"tier": "enterprise", "age": 100},
                output={"category": "billing"},
            ),
            TraceStep(
                actor="agent",
                action="classify_ticket",
                timestamp="2026-08-28T10:01:00Z",
                input={"tier": "starter", "age": 10},
                output={"category": "sales"},
            ),
        ]

        dataset = analyzer.extract_training_dataset("classify_ticket", steps)
        assert dataset is not None
        X, y = dataset
        assert len(X) == 2
        assert len(y) == 2
        assert X[0] == {"tier": "enterprise", "age": 100}
        assert y[0] == "billing"
        assert X[1] == {"tier": "starter", "age": 10}
        assert y[1] == "sales"

    def test_extract_training_dataset_non_ml_returns_none(self):
        """Test dataset extraction returns None for non-ML steps."""
        analyzer = PredictionAnalyzer()
        steps = [
            TraceStep(
                actor="agent",
                action="draft_proposal",
                timestamp="2026-08-28T10:00:00Z",
                input={"client": "Acme"},
                output={"draft": "Long free-form text paragraph " * 10},
            )
        ]
        assert analyzer.extract_training_dataset("draft_proposal", steps) is None


class TestPredictionAnalyzerNegativeCases:
    """Negative test cases ensuring non-ML steps return None."""

    def test_generative_long_text_returns_none(self):
        """Test free-form generative drafting outputs are not flagged as traditional ML."""
        analyzer = PredictionAnalyzer(min_samples=2)
        steps = [
            TraceStep(
                actor="agent",
                action="draft_proposal",
                timestamp="2026-08-28T10:00:00Z",
                input={"customer_id": "C-1", "plan": "Enterprise"},
                output={
                    "proposal_text": (
                        "Dear Customer,\n\nBased on your usage history of 500GB, "
                        "we are pleased to offer you our Enterprise Plan with a 20% discount. "
                        "Please review the attached terms."
                    )
                },
            ),
            TraceStep(
                actor="agent",
                action="draft_proposal",
                timestamp="2026-08-28T10:01:00Z",
                input={"customer_id": "C-2", "plan": "Pro"},
                output={
                    "proposal_text": (
                        "Dear Customer,\n\nWe have prepared your customized Pro renewal offer "
                        "with increased API rate limits and 24/7 support coverage."
                    )
                },
            ),
        ]

        result = analyzer.analyze_steps("draft_proposal", steps)
        assert result is None

    def test_high_cardinality_unique_ids_returns_none(self):
        """Test that random unique UUIDs or tokens are rejected as non-categorical."""
        analyzer = PredictionAnalyzer(min_samples=4)
        steps = [
            TraceStep(
                actor="agent",
                action="generate_session",
                timestamp=f"2026-08-28T10:0{i}:00Z",
                input={"user_id": f"u_{i}"},
                output={"session_id": f"sess_token_{i * 987654321}"},
            )
            for i in range(5)
        ]

        result = analyzer.analyze_steps("generate_session", steps)
        assert result is None

    def test_insufficient_samples_returns_none(self):
        """Test analysis returns None when step count is below min_samples."""
        analyzer = PredictionAnalyzer(min_samples=5)
        steps = [
            TraceStep(
                actor="agent",
                action="classify_ticket",
                timestamp="2026-08-28T10:00:00Z",
                input={"subject": "Help", "tier": "gold"},
                output={"category": "support"},
            )
        ]

        result = analyzer.analyze_steps("classify_ticket", steps)
        assert result is None

    def test_empty_input_or_output_returns_none(self):
        """Test steps with empty input or output dictionaries return None."""
        analyzer = PredictionAnalyzer(min_samples=2)
        steps = [
            TraceStep(
                actor="agent",
                action="check_status",
                timestamp="2026-08-28T10:00:00Z",
                input={},
                output={"status": "active"},
            ),
            TraceStep(
                actor="agent",
                action="check_status",
                timestamp="2026-08-28T10:01:00Z",
                input={},
                output={"status": "inactive"},
            ),
        ]

        result = analyzer.analyze_steps("check_status", steps)
        assert result is None


class TestTraceLevelAnalysis:
    """Tests for multi-action and multi-trace analysis."""

    def test_analyze_trace_with_mixed_actions(self):
        """Test analyzing a complete trace with deterministic, ML, and generative steps."""
        analyzer = PredictionAnalyzer(min_samples=2)
        trace = TraceIR(
            run_id="run-100",
            source_agent="support-agent",
            steps=[
                TraceStep(
                    actor="agent",
                    action="crm.lookup_customer",
                    timestamp="2026-08-28T10:00:00Z",
                    input={"customer_id": "C-1"},
                    output={"name": "Acme", "plan": "Enterprise"},
                ),
                TraceStep(
                    actor="agent",
                    action="classify_ticket",
                    timestamp="2026-08-28T10:01:00Z",
                    input={"subject": "Invoice error", "priority": "high", "mrr": 5000},
                    output={"category": "billing"},
                ),
                TraceStep(
                    actor="agent",
                    action="classify_ticket",
                    timestamp="2026-08-28T10:02:00Z",
                    input={"subject": "API bug", "priority": "urgent", "mrr": 2000},
                    output={"category": "technical"},
                ),
                TraceStep(
                    actor="agent",
                    action="score_lead",
                    timestamp="2026-08-28T10:03:00Z",
                    input={"company_size": 500, "revenue": 10000000},
                    output={"lead_score": 0.89},
                ),
                TraceStep(
                    actor="agent",
                    action="score_lead",
                    timestamp="2026-08-28T10:04:00Z",
                    input={"company_size": 20, "revenue": 100000},
                    output={"lead_score": 0.21},
                ),
            ],
            result=TraceResult(status="success"),
        )

        results = analyzer.analyze_trace(trace)
        assert "classify_ticket" in results
        assert results["classify_ticket"]["target_executor"] == "ml"
        assert results["classify_ticket"]["task_type"] == "classification"

        assert "score_lead" in results
        assert results["score_lead"]["target_executor"] == "ml"
        assert results["score_lead"]["task_type"] == "regression"

        # Lookup customer should not be in ML results (it is lookup/deterministic or single sample)
        assert "lookup_customer" not in results

    def test_dict_trace_compatibility(self):
        """Test compatibility with raw dictionary traces."""
        analyzer = PredictionAnalyzer(min_samples=2)
        dict_trace = {
            "run_id": "tr-200",
            "steps": [
                {
                    "actor": "agent",
                    "action": "rate_risk",
                    "timestamp": "2026-08-28T10:00:00Z",
                    "input": {"credit_score": 750, "debt_ratio": 0.2},
                    "output": {"risk_score": 0.15},
                },
                {
                    "actor": "agent",
                    "action": "rate_risk",
                    "timestamp": "2026-08-28T10:01:00Z",
                    "input": {"credit_score": 580, "debt_ratio": 0.65},
                    "output": {"risk_score": 0.82},
                },
            ],
        }

        results = analyzer.analyze_trace(dict_trace)
        assert "rate_risk" in results
        assert results["rate_risk"]["target_executor"] == "ml"
        assert results["rate_risk"]["task_type"] == "regression"
