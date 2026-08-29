# OpenWorkCompiler Usage Guide

This guide demonstrates how to use the **OpenWorkCompiler** core kernel in Python to ingest agent traces, enforce behavior contracts, compile work definitions, execute durable workflows, evaluate quality, and optimize step executors across the 8-tier lowering hierarchy.

---

## Prerequisites

Python 3.10+ installed.

Dependencies (built with standard library and Pydantic/PyYAML):

```bash
pip install pydantic pyyaml pytest
```

---

## Quickstart: The 6-Step Workflow Compilation Pipeline

### Step 1: Ingest Agent Trajectory (`Trace IR`)

Convert execution logs from OpenWorker, LangGraph, or custom agent frameworks into canonical `TraceIR`:

```python
from core.work_ir import normalize_trace, TraceIR

raw_trace_data = {
    "run_id": "run_renewal_001",
    "source_agent": "claude-code",
    "steps": [
        {
            "step_id": "s1",
            "actor": "agent",
            "action": "lookup_contract",
            "input": {"customer_id": "CUST-9921"},
            "output": {"contract_id": "CTR-102", "status": "active", "term_months": 12},
            "latency_ms": 120
        },
        {
            "step_id": "s2",
            "actor": "agent",
            "action": "calculate_usage",
            "input": {"contract_id": "CTR-102"},
            "output": {"monthly_gb": 450, "api_calls": 120000, "overage_units": 2},
            "latency_ms": 45
        },
        {
            "step_id": "s3",
            "actor": "rule",
            "action": "price_offer",
            "input": {"tier": "enterprise", "overage_units": 2},
            "output": {"base_price": 5000, "discount_pct": 10, "final_price": 4500},
            "latency_ms": 10
        },
        {
            "step_id": "s4",
            "actor": "llm",
            "action": "draft_proposal",
            "input": {"customer_name": "Acme Corp", "final_price": 4500},
            "output": {"proposal_text": "Dear Acme Corp, your renewal offer is $4,500/mo."},
            "latency_ms": 1850
        }
    ],
    "result": {"status": "success", "outputs": {"proposal_pdf": "renewal_4500.pdf"}}
}

# Normalize into canonical TraceIR
trace: TraceIR = normalize_trace(raw_trace_data)
print(f"Loaded Trace: {trace.run_id} with {len(trace.steps)} steps.")
```

---

### Step 2: Load Behavior Contracts (`BEHAVIOR.md`)

Ingest process evaluation specifications:

```python
from adapters.agentbehavior import parse_behavior_md
from core.validation import classify_behavior

behavior_content = """
# BEHAVIOR: verify-current-contract

## 1. Intent
Ensure active customer contract is fetched prior to pricing or proposal drafting.

## 2. Evidence
Invocation of `lookup_contract` step before pricing.

## 3. Decision
- `true`: `lookup_contract` executed successfully before pricing.
- `false`: Pricing or proposal drafting occurred without contract check.
"""

behavior_data = parse_behavior_md(behavior_content)
classification = classify_behavior(behavior_data)

print(f"Behavior: {behavior_data['name']}")
print(f"Execution Target: {classification.category.value}")  # e.g., "Workflow Transition Constraint"
```

---

### Step 3: Compile Work IR (`work.yaml`)

Invoke the **WorkCompiler** to analyze determinism, prediction, and SLM opportunities, synthesizing a validated `WorkIR`:

```python
from core.compiler import WorkCompiler
from core.work_ir import save_work_ir

compiler = WorkCompiler()
work_ir = compiler.compile_traces_to_work_ir(
    traces=[trace],
    behaviors=[behavior_data],
    target_name="customer-renewal"
)

# Export compiled Work IR to YAML
yaml_output = work_ir.to_yaml()
print(yaml_output)

# Save to file
save_work_ir(work_ir, "examples/customer-renewal/work.yaml")
```

---

### Step 4: Execute Workflow on Durable Runtime Engine

Run the compiled workflow step-by-step with state machine durability and checkpointing:

```python
from core.runtime import (
    DurableRuntimeEngine,
    CodeExecutor,
    RuleExecutor,
    SLMExecutor,
    LLMExecutor
)

# Initialize engine
engine = DurableRuntimeEngine()

# Register custom step handlers
engine.register_executor("code", CodeExecutor())
engine.register_executor("rule", RuleExecutor())
engine.register_executor("slm", SLMExecutor())
engine.register_executor("frontier_llm", LLMExecutor())

# Register Python code handlers
def lookup_contract_handler(inputs, context):
    return {"contract_id": "CTR-102", "status": "active"}

def calculate_usage_handler(inputs, context):
    return {"monthly_gb": 450, "overage_units": 2}

engine.register_code_handler("lookup_contract", lookup_contract_handler)
engine.register_code_handler("calculate_usage", calculate_usage_handler)

# Start workflow execution
instance = engine.start_workflow(
    workflow_id="wf_run_901",
    work_definition=work_ir,
    initial_inputs={"customer_id": "CUST-9921"}
)

# Execute steps until complete or blocked by Human approval / Event
instance = engine.run_until_blocked_or_complete("wf_run_901")
print(f"Workflow Status: {instance.status.value}")
```

---

### Step 5: Enforce Frugal Objective Oracle Escalation

Validate execution outputs against schema & behavior contracts, escalating on failure:

```python
from core.runtime import ObjectiveOracleGate, ActionResult

oracle_gate = ObjectiveOracleGate()

result = ActionResult.ok(output={"final_price": 4500})
is_valid = oracle_gate.evaluate_oracle(
    action_name="price_offer",
    step_result=result,
    schema={"type": "object", "required": ["final_price"]},
    behavior_specs=[{"name": "verify-current-contract", "verdict": "true"}]
)

if not is_valid:
    print("Oracle Gate Failed! Escalating to Frontier LLM...")
else:
    print("Oracle Gate PASSED. Proceeding with compiled result.")
```

---

### Step 6: Evaluate Quality Record & Optimize Executors

Enforce the **Lucky-Correct Defense** (rejecting correct outcomes that breached process behaviors) and evaluate step promotion:

```python
from core.validation import QualityRecord, evaluate_quality_fold
from core.optimizer import ExecutorOptimizer

# Build Quality Record
record = QualityRecord(
    trace_id="run_renewal_001",
    action_name="draft_proposal",
    executor_type="slm",
    human_ratings={"approved": True, "rating": 5},
    automated_checks={"schema_valid": True},
    behavior_verdicts={"verify-current-contract": "true", "approval-before-send": "true"},
    execution_cost=0.08,
    execution_latency_ms=420
)

# Evaluate Quality Fold
fold_verdict = evaluate_quality_fold(record)
print(f"Quality Fold Verdict: {fold_verdict}")  # "PASS"

# Evaluate Promotion from Frontier LLM -> SLM
optimizer = ExecutorOptimizer()
can_promote = optimizer.evaluate_promotion(
    action_name="draft_proposal",
    candidate_executor="slm",
    quality_records=[record],
    min_quality=0.95,
    min_behavior_compliance=1.0,
    max_latency_ms=1000,
    max_cost=0.50
)

print(f"Can promote draft_proposal to SLM? {can_promote}")
```

---

## Running Verification Test Suite

To run all unit and integration tests:

```bash
python3 -m pytest tests/
```

To run the end-to-end customer renewal demonstration:

```bash
python3 examples/run_customer_renewal_demo.py
```
