#!/usr/bin/env python3
"""
OpenWorkflow End-to-End Customer Renewal Demonstration
Runs the full pipeline: Trace Normalization -> BEHAVIOR Parsing -> Work Compilation -> 
Durable Runtime Execution -> Oracle Gate Validation -> Quality Record Evaluation -> Executor Optimization.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.work_ir import normalize_trace, TraceIR
from adapters.agentbehavior import parse_behavior_md
from core.validation import classify_behavior, QualityRecord, evaluate_quality_fold
from core.compiler import WorkCompiler
from core.runtime import (
    DurableRuntimeEngine,
    CodeExecutor,
    RuleExecutor,
    SLMExecutor,
    LLMExecutor,
    ObjectiveOracleGate,
    ActionResult
)
from core.optimizer import ExecutorOptimizer, generate_training_candidate


def main():
    print("=" * 70)
    print("🚀 OpenWorkflow v4: End-to-End Customer Renewal Demonstration")
    print("=" * 70)

    # 1. Simulate Raw Trajectory Ingestion
    print("\n1️⃣  Ingesting Raw Agent Trajectory into TraceIR...")
    raw_trace_data = {
        "run_id": "run_customer_renewal_demo_101",
        "source_agent": "claude-code-agent",
        "steps": [
            {
                "step_id": "s1",
                "actor": "agent",
                "action": "lookup_contract",
                "input": {"customer_id": "CUST-8831"},
                "output": {"contract_id": "CTR-991", "status": "active", "tier": "enterprise"},
                "latency_ms": 115
            },
            {
                "step_id": "s2",
                "actor": "agent",
                "action": "calculate_usage",
                "input": {"contract_id": "CTR-991"},
                "output": {"monthly_gb": 620, "overage_units": 4},
                "latency_ms": 50
            },
            {
                "step_id": "s3",
                "actor": "rule",
                "action": "price_offer",
                "input": {"tier": "enterprise", "overage_units": 4},
                "output": {"base_price": 6000, "discount_pct": 15, "final_price": 5100},
                "latency_ms": 12
            },
            {
                "step_id": "s4",
                "actor": "llm",
                "action": "draft_proposal",
                "input": {"customer_name": "Global Tech", "final_price": 5100},
                "output": {"proposal_text": "Dear Global Tech, your enterprise renewal rate is $5,100/mo."},
                "latency_ms": 1420
            }
        ],
        "result": {"status": "success", "outputs": {"proposal_pdf": "renewal_5100.pdf"}}
    }

    trace: TraceIR = normalize_trace(raw_trace_data)
    print(f"   [SUCCESS] Normalized Trace '{trace.run_id}' with {len(trace.steps)} steps.")
    print(f"   [STATS] Total Latency: {trace.total_latency_ms()}ms")

    # 2. Ingest Behavior Contract Specs
    print("\n2️⃣  Parsing Behavior Contracts (BEHAVIOR.md)...")
    behavior_content_1 = """# BEHAVIOR: verify-current-contract

## 1. Intent
Ensure active customer contract is fetched before computing pricing.

## 2. Evidence
Invocation of `lookup_contract` before pricing or proposal drafting.

## 3. Decision
- `true`: `lookup_contract` executed before pricing.
- `false`: Pricing occurred without contract check.
"""
    behavior_1 = parse_behavior_md(behavior_content_1)
    class_1 = classify_behavior(behavior_1)
    print(f"   [BEHAVIOR] '{behavior_1['name']}' -> Category: {class_1.category.value}")

    # 3. Work Compiler Execution
    print("\n3️⃣  Executing WorkCompiler (Trace + Behaviors -> WorkIR)...")
    compiler = WorkCompiler()
    work_ir = compiler.compile_traces_to_work_ir(
        traces=[trace],
        behaviors=[behavior_1],
        target_name="customer-renewal"
    )
    print(f"   [WORK IR] Compiled Work: '{work_ir.work}' v{work_ir.version}")
    print(f"   [DAG ACTIONS] Executable Actions: {work_ir.actions}")
    print(f"   [INVARIANTS] Locked Invariants: {work_ir.invariants}")

    # 4. Durable Runtime Execution
    print("\n4️⃣  Executing Workflow on DurableRuntimeEngine...")
    engine = DurableRuntimeEngine()

    def lookup_contract_code(inputs, context):
        return {"contract_id": "CTR-991", "status": "active", "tier": "enterprise"}

    def calculate_usage_code(inputs, context):
        return {"monthly_gb": 620, "overage_units": 4}

    def price_offer_rule(inputs, context):
        return {"base_price": 6000, "discount_pct": 15, "final_price": 5100}

    def draft_proposal_code(inputs, context):
        return {"proposal_text": "Dear Global Tech, your enterprise renewal rate is $5,100/mo."}

    code_exec = CodeExecutor(handlers={
        "lookup_contract": lookup_contract_code,
        "services.lookup_contract": lookup_contract_code,
        "calculate_usage": calculate_usage_code,
        "services.calculate_usage": calculate_usage_code,
        "draft_proposal": draft_proposal_code,
        "services.draft_proposal": draft_proposal_code,
    })
    rule_exec = RuleExecutor(rules={
        "price_offer": price_offer_rule,
        "rules.price_offer": price_offer_rule,
    })

    engine.register_executor("code", code_exec)
    engine.register_executor("rule", rule_exec)
    engine.register_executor("slm", code_exec)  # Fallback code execution for demo

    wf_instance = engine.start_workflow(
        workflow_id="wf_demo_session_01",
        work_definition=work_ir,
        initial_inputs={"customer_id": "CUST-8831"}
    )
    wf_instance = engine.run_until_blocked_or_complete("wf_demo_session_01")
    print(f"   [RUNTIME] Instance Final Status: {wf_instance.status.value}")
    print(f"   [RUNTIME] Executed Step Outputs: {list(wf_instance.outputs.keys())}")

    # 5. Objective Oracle Gate Validation
    print("\n5️⃣  Evaluating Objective Oracle Gate (Frugal Escalation)...")
    oracle = ObjectiveOracleGate()
    step_res = ActionResult.ok(output={"base_price": 6000, "final_price": 5100})
    is_valid = oracle.evaluate_oracle(
        action_name="price_offer",
        step_result=step_res,
        schema={"type": "object", "required": ["final_price"]},
        behavior_specs=[{"name": "verify-current-contract", "verdict": "true"}]
    )
    print(f"   [ORACLE GATE] Oracle Gate Result: {'PASSED (Accept Compiled Step)' if is_valid else 'FAILED (Escalate to Frontier)'}")

    # 6. Quality Record & Optimizer Promotion
    print("\n6️⃣  Evaluating Quality Record & Executor Promotion Gate...")
    q_record = QualityRecord(
        trace_id=trace.run_id,
        action_name="draft_proposal",
        executor_type="slm",
        human_ratings={"approved": True, "rating": 5},
        automated_checks={"schema_valid": True},
        behavior_verdicts={"verify-current-contract": "true"},
        execution_cost=0.07,
        execution_latency_ms=380
    )
    fold_verdict = evaluate_quality_fold(q_record)
    print(f"   [QUALITY FOLD] Fold Verdict (Lucky-Correct Check): {fold_verdict}")

    optimizer = ExecutorOptimizer()
    can_promote = optimizer.evaluate_promotion(
        action_name="draft_proposal",
        candidate_executor="slm",
        quality_records=[q_record],
        min_quality=0.95,
        min_behavior_compliance=1.0,
        max_latency_ms=1000,
        max_cost=0.50
    )
    print(f"   [OPTIMIZER] Promotion Evaluation (Frontier -> SLM): {'APPROVED' if can_promote else 'REJECTED'}")

    # Generate Training Candidate Dataset
    training_candidate = generate_training_candidate(
        action_name="draft_proposal",
        approved_traces=[trace],
        base_model="Qwen/Qwen2.5-1.5B-Instruct"
    )
    print(f"   [SLM FACTORY] Generated Training Candidate for '{training_candidate['action_name']}'")
    print(f"   [SLM FACTORY] Training Sample Pairs: {len(training_candidate['dataset']['examples'])}")

    print("\n" + "=" * 70)
    print("🎉 OpenWorkflow End-to-End Test Completed Successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
