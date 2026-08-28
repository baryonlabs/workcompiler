"""Unit tests for QualityRecord, evaluate_quality_fold, ExecutorOptimizer, and generate_training_candidate."""

import yaml
import pytest

from core.validation.quality_record import (
    BehaviorVerdict,
    QualityFoldResult,
    QualityRecord,
    evaluate_quality_fold,
)
from core.optimizer.optimizer import (
    ExecutorOptimizer,
    TrainingCandidate,
    generate_training_candidate,
)


class TestQualityRecordAndFoldEvaluation:
    def test_passing_trace(self):
        """Test a clean trace where human approves, schema passes, and behavior is true."""
        record = QualityRecord(
            trace_id="tr-001",
            action_name="draft_proposal",
            executor_type="frontier_llm",
            human_ratings={"approved": True, "factual_accuracy": 1.0, "rating": 5.0},
            automated_checks={"schema_valid": True, "policy_pass": True},
            behavior_verdicts={
                "verify-current-contract": "true",
                "use-current-pricing-policy": BehaviorVerdict.TRUE,
            },
            execution_cost=0.04,
            execution_latency_ms=1200.0,
        )

        assert record.has_behavior_failures() is False
        assert record.has_automated_failures() is False
        assert record.is_lucky_correct() is False
        assert record.behavior_compliance_rate() == 1.0

        verdict = evaluate_quality_fold(record)
        assert verdict == "PASS"

    def test_lucky_correct_anomaly_rejected(self):
        """Test the critical Lucky-Correct defense: output rating is 5 stars approved,

        but a required process behavior was skipped (verdict is 'false').
        The fold MUST evaluate to FAIL.
        """
        record = QualityRecord(
            trace_id="tr-002",
            action_name="draft_proposal",
            executor_type="slm",
            human_ratings={"approved": True, "rating": 5.0},
            automated_checks={"schema_valid": True},
            behavior_verdicts={
                "verify-current-contract": "true",
                "use-current-pricing-policy": "false",  # Skipped required pricing check!
            },
            execution_cost=0.001,
            execution_latency_ms=250.0,
        )

        assert record.has_behavior_failures() is True
        assert record.is_lucky_correct() is True
        assert record.behavior_compliance_rate() == 0.5

        verdict = evaluate_quality_fold(record)
        assert verdict == "FAIL"

    def test_human_disapproval_fails(self):
        """Test that human disapproval results in FAIL even if behavior is true."""
        record = QualityRecord(
            trace_id="tr-003",
            action_name="draft_proposal",
            executor_type="frontier_llm",
            human_ratings={"approved": False, "rating": 1.0},
            automated_checks={"schema_valid": True},
            behavior_verdicts={"verify-current-contract": "true"},
        )

        assert record.has_behavior_failures() is False
        assert record.is_lucky_correct() is False
        assert evaluate_quality_fold(record) == "FAIL"

    def test_automated_check_failure_fails(self):
        """Test that schema or invariant check failure causes fold FAIL."""
        record = QualityRecord(
            trace_id="tr-004",
            action_name="draft_proposal",
            executor_type="slm",
            human_ratings={"approved": True},
            automated_checks={"schema_valid": False},
            behavior_verdicts={"verify-current-contract": "true"},
        )

        assert record.has_automated_failures() is True
        assert evaluate_quality_fold(record) == "FAIL"

    def test_na_behavior_verdicts(self):
        """Test unjudgeable / out-of-scope behaviors ('na')."""
        record = QualityRecord(
            trace_id="tr-005",
            action_name="lookup_contract",
            behavior_verdicts={"require-approval-before-send": "na"},
        )

        assert record.has_behavior_failures() is False
        assert record.behavior_compliance_rate() == 1.0
        assert evaluate_quality_fold(record) == "NA"

    def test_serialization_roundtrip(self):
        """Test QualityRecord to_dict and from_dict roundtrip."""
        record = QualityRecord(
            trace_id="tr-006",
            action_name="calculate_usage",
            executor_type="code",
            human_ratings={"approved": True},
            automated_checks={"math_valid": True},
            behavior_verdicts={"use-current-pricing-policy": BehaviorVerdict.TRUE},
            execution_cost=0.0001,
            execution_latency_ms=15.0,
            metadata={"connector": "crm_v2"},
        )

        data = record.to_dict()
        restored = QualityRecord.from_dict(data)

        assert restored.trace_id == record.trace_id
        assert restored.action_name == record.action_name
        assert restored.executor_type == record.executor_type
        assert restored.execution_cost == record.execution_cost
        assert restored.execution_latency_ms == record.execution_latency_ms
        assert restored.metadata == record.metadata
        assert evaluate_quality_fold(restored) == "PASS"


class TestExecutorOptimizer:
    def test_evaluate_promotion_success(self):
        """Test successful promotion when candidate passes quality and behavior compliance."""
        optimizer = ExecutorOptimizer()

        records = [
            QualityRecord(
                trace_id=f"tr-eval-{i}",
                action_name="draft_proposal",
                executor_type="slm",
                human_ratings={"approved": True, "rating": 5.0},
                automated_checks={"schema_valid": True},
                behavior_verdicts={
                    "verify-current-contract": "true",
                    "use-current-pricing-policy": "true",
                },
                execution_cost=0.002,
                execution_latency_ms=300.0,
            )
            for i in range(20)
        ]

        can_promote = optimizer.evaluate_promotion(
            action_name="draft_proposal",
            candidate_executor="models/renewal-draft-slm-v1",
            quality_records=records,
            min_quality=0.95,
            min_behavior_compliance=1.0,
            max_latency_ms=500.0,
        )

        assert can_promote is True

        # Test promote method
        promoted = optimizer.promote(
            action_name="draft_proposal",
            candidate_executor="models/renewal-draft-slm-v1",
            quality_records=records,
        )
        assert promoted is True
        assert optimizer.get_active_executor("draft_proposal") == "models/renewal-draft-slm-v1"

    def test_evaluate_promotion_blocked_by_lucky_correct(self):
        """Test promotion blocked when candidate exhibits lucky-correct failures."""
        optimizer = ExecutorOptimizer()

        records = []
        # 18 passing records
        for i in range(18):
            records.append(
                QualityRecord(
                    trace_id=f"tr-pass-{i}",
                    action_name="draft_proposal",
                    executor_type="slm",
                    human_ratings={"approved": True},
                    automated_checks={"schema_valid": True},
                    behavior_verdicts={"verify-current-contract": "true"},
                )
            )

        # 2 lucky-correct records (approved outcome, but skipped behavior)
        for i in range(2):
            records.append(
                QualityRecord(
                    trace_id=f"tr-lucky-{i}",
                    action_name="draft_proposal",
                    executor_type="slm",
                    human_ratings={"approved": True},
                    automated_checks={"schema_valid": True},
                    behavior_verdicts={"verify-current-contract": "false"},
                )
            )

        can_promote = optimizer.evaluate_promotion(
            action_name="draft_proposal",
            candidate_executor="models/flawed-slm",
            quality_records=records,
            min_quality=0.95,
            min_behavior_compliance=1.0,
        )

        # 18/20 = 90% < 95% quality threshold AND 90% behavior compliance < 100% threshold
        assert can_promote is False

    def test_evaluate_promotion_latency_gate(self):
        """Test promotion blocked when latency exceeds maximum threshold."""
        optimizer = ExecutorOptimizer()

        records = [
            QualityRecord(
                trace_id=f"tr-slow-{i}",
                action_name="draft_proposal",
                executor_type="slm",
                human_ratings={"approved": True},
                automated_checks={"schema_valid": True},
                behavior_verdicts={"verify-current-contract": "true"},
                execution_latency_ms=2500.0,
            )
            for i in range(10)
        ]

        can_promote = optimizer.evaluate_promotion(
            action_name="draft_proposal",
            candidate_executor="models/slow-slm",
            quality_records=records,
            max_latency_ms=1000.0,
        )

        assert can_promote is False

    def test_evaluate_batch_metrics(self):
        """Test evaluate_batch aggregate stats."""
        optimizer = ExecutorOptimizer()
        records = [
            QualityRecord(
                trace_id="tr-1",
                human_ratings={"approved": True},
                automated_checks={"ok": True},
                behavior_verdicts={"b1": "true"},
                execution_cost=0.01,
                execution_latency_ms=100.0,
            ),
            QualityRecord(
                trace_id="tr-2",
                human_ratings={"approved": True},
                automated_checks={"ok": True},
                behavior_verdicts={"b1": "false"},  # Lucky-correct
                execution_cost=0.02,
                execution_latency_ms=200.0,
            ),
            QualityRecord(
                trace_id="tr-3",
                behavior_verdicts={"b1": "na"},
                execution_cost=0.03,
                execution_latency_ms=300.0,
            ),
        ]

        stats = optimizer.evaluate_batch(records)
        assert stats["total_records"] == 3
        assert stats["pass_count"] == 1
        assert stats["fail_count"] == 1
        assert stats["na_count"] == 1
        assert stats["lucky_correct_count"] == 1
        assert stats["avg_latency_ms"] == 200.0
        assert stats["avg_cost"] == 0.02


class TestGenerateTrainingCandidate:
    def test_generate_training_candidate_multi_step(self):
        """Test extracting training data from multi-step traces and producing YAML candidate definition."""
        approved_traces = [
            {
                "run_id": "run-001",
                "behaviors": ["verify-current-contract", "use-current-pricing-policy"],
                "steps": [
                    {
                        "action": "lookup_contract",
                        "input": {"customer_id": "cust-101"},
                        "output": {"contract_id": "ct-999"},
                    },
                    {
                        "action": "draft_proposal",
                        "input": {"contract_id": "ct-999", "tier": "enterprise"},
                        "output": {"proposal_text": "Enterprise renewal drafted."},
                    },
                ],
            },
            {
                "run_id": "run-002",
                "behaviors": ["verify-current-contract"],
                "steps": [
                    {
                        "action": "draft_proposal",
                        "input": {"contract_id": "ct-1000", "tier": "standard"},
                        "output": {"proposal_text": "Standard renewal drafted."},
                    },
                ],
            },
        ]

        candidate_dict = generate_training_candidate(
            action_name="draft_proposal",
            approved_traces=approved_traces,
            base_model="Qwen/Qwen2.5-Coder-7B-Instruct",
        )

        assert candidate_dict["action_name"] == "draft_proposal"
        assert candidate_dict["base_model"] == "Qwen/Qwen2.5-Coder-7B-Instruct"
        assert candidate_dict["dataset"]["num_samples"] == 2
        assert "verify-current-contract" in candidate_dict["behavior_invariants"]
        assert len(candidate_dict["dataset"]["examples"]) == 2
        assert candidate_dict["dataset"]["examples"][0]["messages"][1]["role"] == "user"
        assert candidate_dict["dataset"]["examples"][0]["messages"][2]["role"] == "assistant"

        # Verify YAML serialization works cleanly
        candidate_obj = TrainingCandidate(**candidate_dict)
        yaml_str = candidate_obj.to_yaml()
        parsed = yaml.safe_load(yaml_str)

        assert "training_candidate" in parsed
        assert parsed["training_candidate"]["action_name"] == "draft_proposal"
        assert parsed["training_candidate"]["target_executor_type"] == "slm"
        assert parsed["training_candidate"]["framework"] == "trl"
