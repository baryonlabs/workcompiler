"""Unit tests for OpenWorkCompiler Work IR and Trace IR modules."""

import json
import tempfile
import unittest
from pathlib import Path

from core.work_ir.trace_ir import (
    Provenance,
    TokenUsage,
    TraceIR,
    TraceResult,
    TraceStatus,
    TraceStep,
    normalize_custom_agent_trace,
    normalize_langgraph_trace,
    normalize_openworker_trace,
    normalize_trace,
    parse_trace_from_json,
)
from core.work_ir.work_ir import (
    ActionDef,
    BehaviorRef,
    EscalationDef,
    ExecutorDef,
    ExecutorType,
    InvariantDef,
    WorkIR,
    WorkIRValidationError,
    load_work_ir,
    save_work_ir,
    to_yaml,
    validate_work_ir,
)


class TestTraceIR(unittest.TestCase):
    """Tests for Trace IR model creation, serialization, and metrics."""

    def test_trace_step_and_result_creation(self):
        step = TraceStep(
            actor="agent",
            action="call_crm",
            input={"customer_id": "C-100"},
            output={"name": "Acme Corp"},
            latency_ms=150.0,
            token_usage=TokenUsage(prompt_tokens=50, completion_tokens=25, total_tokens=75),
        )
        self.assertEqual(step.actor, "agent")
        self.assertEqual(step.action, "call_crm")
        self.assertEqual(step.latency_ms, 150.0)
        self.assertIsNotNone(step.token_usage)
        self.assertEqual(step.token_usage.total_tokens, 75)

        res = TraceResult(status="success", summary="Completed successfully", outputs={"pdf": "doc.pdf"})
        self.assertEqual(res.status, TraceStatus.SUCCESS)

    def test_trace_metrics_and_filters(self):
        steps = [
            TraceStep(
                step_id="step_1",
                actor="agent",
                action="lookup",
                latency_ms=100.0,
                token_usage=TokenUsage(prompt_tokens=20, completion_tokens=30),
            ),
            TraceStep(
                step_id="step_2",
                actor="tool",
                action="execute_sql",
                latency_ms=200.0,
                token_usage=TokenUsage(prompt_tokens=10, completion_tokens=15, total_tokens=25),
            ),
            TraceStep(
                step_id="step_3",
                actor="agent",
                action="draft_response",
                latency_ms=300.0,
                token_usage=TokenUsage(prompt_tokens=50, completion_tokens=50, total_tokens=100),
            ),
        ]
        trace = TraceIR(
            run_id="run_test_01",
            source_agent="custom",
            steps=steps,
            result=TraceResult(status=TraceStatus.SUCCESS),
        )

        self.assertEqual(trace.total_latency_ms(), 600.0)
        # step_1: 50, step_2: 25, step_3: 100 -> 175 tokens
        self.assertEqual(trace.total_tokens(), 175)

        self.assertEqual(len(trace.get_steps_by_actor("agent")), 2)
        self.assertEqual(len(trace.get_steps_by_actor("tool")), 1)
        self.assertEqual(len(trace.get_steps_by_action("lookup")), 1)
        self.assertIsNotNone(trace.get_step_by_id("step_2"))
        self.assertIsNone(trace.get_step_by_id("step_nonexistent"))

    def test_openworker_normalization(self):
        raw_ow = {
            "task_id": "ow_task_99",
            "created_at": "2026-08-28T10:00:00Z",
            "completed_at": "2026-08-28T10:00:05Z",
            "steps": [
                {
                    "worker_id": "desktop_worker",
                    "command": "click_ui_element",
                    "args": {"selector": "#btn-renew"},
                    "result": {"clicked": True},
                    "duration_seconds": 1.25,
                },
                {
                    "worker_id": "desktop_worker",
                    "tool_name": "read_screen_text",
                    "params": {"region": [0, 0, 800, 600]},
                    "response": {"text": "Renewal Confirmed"},
                    "duration_ms": 250.0,
                },
            ],
            "result": {
                "status": "success",
                "message": "Desktop workflow finished",
                "data": {"success": True},
            },
            "files": ["/tmp/screenshot.png"],
        }
        trace = normalize_openworker_trace(raw_ow)
        self.assertEqual(trace.run_id, "ow_task_99")
        self.assertEqual(trace.source_agent, "openworker")
        self.assertEqual(len(trace.steps), 2)
        self.assertEqual(trace.steps[0].latency_ms, 1250.0)
        self.assertEqual(trace.steps[1].latency_ms, 250.0)
        self.assertEqual(trace.steps[0].action, "click_ui_element")
        self.assertEqual(trace.steps[1].action, "read_screen_text")
        self.assertEqual(trace.result.status, TraceStatus.SUCCESS)
        self.assertIn("/tmp/screenshot.png", trace.artifacts)

    def test_langgraph_normalization(self):
        raw_lg = {
            "id": "lg_run_77",
            "name": "renewal_graph",
            "start_time": "2026-08-28T12:00:00Z",
            "end_time": "2026-08-28T12:00:02Z",
            "nodes": [
                {
                    "node": "crm_node",
                    "inputs": {"customer_id": "C-123"},
                    "outputs": {"contract_id": "K-456"},
                    "start_time": "2026-08-28T12:00:00Z",
                    "end_time": "2026-08-28T12:00:01Z",
                    "token_usage": {"prompt_tokens": 40, "completion_tokens": 10, "total_tokens": 50},
                },
                {
                    "node": "draft_node",
                    "inputs": {"contract_id": "K-456"},
                    "outputs": {"draft": "Proposal text"},
                    "latency_ms": 500.0,
                },
            ],
            "output": {"final_draft": "Proposal text"},
            "status": "success",
        }
        trace = normalize_langgraph_trace(raw_lg)
        self.assertEqual(trace.run_id, "lg_run_77")
        self.assertEqual(trace.source_agent, "langgraph")
        self.assertEqual(len(trace.steps), 2)
        self.assertEqual(trace.steps[0].actor, "crm_node")
        self.assertEqual(trace.steps[0].latency_ms, 1000.0)
        self.assertEqual(trace.steps[0].token_usage.total_tokens, 50)
        self.assertEqual(trace.result.status, TraceStatus.SUCCESS)

    def test_parse_trace_from_json_and_file(self):
        trace_dict = {
            "run_id": "trace_canonical_1",
            "source_agent": "openai",
            "steps": [
                {
                    "actor": "assistant",
                    "action": "reply",
                    "input": {"prompt": "ping"},
                    "output": {"response": "pong"},
                    "timestamp": "2026-08-28T14:00:00Z",
                }
            ],
            "result": {"status": "success", "summary": "done"},
        }
        json_str = json.dumps(trace_dict)
        trace_from_str = parse_trace_from_json(json_str)
        self.assertEqual(trace_from_str.run_id, "trace_canonical_1")
        self.assertEqual(trace_from_str.source_agent, "openai")

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write(json_str)
            temp_path = f.name

        try:
            trace_from_file = parse_trace_from_json(temp_path)
            self.assertEqual(trace_from_file.run_id, "trace_canonical_1")
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestWorkIR(unittest.TestCase):
    """Tests for Work IR loading, validation, DAG processing, and YAML export."""

    def test_load_example_customer_renewal(self):
        example_path = Path("examples/customer-renewal/work.yaml")
        self.assertTrue(example_path.is_file(), "example customer-renewal/work.yaml must exist")

        work_ir = load_work_ir(example_path)
        self.assertEqual(work_ir.work, "customer-renewal")
        self.assertEqual(work_ir.version, "3.0")
        self.assertIn("customer_id", work_ir.inputs)
        self.assertIn("renewal_proposal_pdf", work_ir.outputs)
        self.assertEqual(len(work_ir.actions), 5)
        self.assertEqual(len(work_ir.states), 6)
        self.assertEqual(len(work_ir.invariants), 3)

        # Invariants normalized
        self.assertIn("verify_current_contract", work_ir.invariants)

        # Executors
        self.assertIn("lookup_contract", work_ir.executors)
        self.assertEqual(work_ir.executors["lookup_contract"].type, ExecutorType.CODE)
        self.assertEqual(work_ir.executors["price_offer"].type, ExecutorType.RULE)
        self.assertEqual(work_ir.executors["draft_proposal"].type, ExecutorType.SLM)
        self.assertIn("frontier_llm", work_ir.executors["draft_proposal"].fallback)

        # Behaviors
        self.assertIsNotNone(work_ir.behaviors)
        self.assertEqual(len(work_ir.behaviors), 2)
        self.assertEqual(work_ir.behaviors[0].name, "verify-current-contract")

        # Escalation
        self.assertIsNotNone(work_ir.escalation)
        self.assertEqual(work_ir.escalation.on_error, "fallback_to_frontier_llm")

    def test_topological_sort_and_dag_queries(self):
        work_ir = load_work_ir("examples/customer-renewal/work.yaml")
        order = work_ir.topological_sort()
        self.assertEqual(order, [
            "lookup_contract",
            "calculate_usage",
            "price_offer",
            "draft_proposal",
            "send_email",
        ])

        prereqs = work_ir.get_prerequisites("send_email")
        self.assertEqual(prereqs, ["draft_proposal"])

        all_prereqs = work_ir.get_all_prerequisites("send_email")
        self.assertEqual(
            all_prereqs,
            {"lookup_contract", "calculate_usage", "price_offer", "draft_proposal"},
        )

        downstream = work_ir.get_downstream("price_offer")
        self.assertEqual(downstream, ["draft_proposal"])

        act_def = work_ir.get_action_def("price_offer")
        self.assertEqual(act_def.name, "price_offer")
        self.assertEqual(act_def.prerequisites, ["calculate_usage"])
        self.assertEqual(act_def.executor.type, ExecutorType.RULE)

    def test_dag_cycle_detection(self):
        bad_data = {
            "work": "cyclic-test",
            "version": "3.0",
            "inputs": ["x"],
            "outputs": ["y"],
            "states": ["s1", "s2"],
            "actions": ["a1", "a2", "a3"],
            "dependencies": {
                "a2": ["a1"],
                "a3": ["a2"],
                "a1": ["a3"],  # Cycle: a1 -> a2 -> a3 -> a1
            },
            "invariants": ["inv1"],
            "quality": {"score": ">=0.9"},
            "executors": {
                "a1": {"type": "code"},
                "a2": {"type": "rule"},
                "a3": {"type": "slm"},
            },
        }
        with self.assertRaises(WorkIRValidationError) as ctx:
            load_work_ir(bad_data)
        self.assertIn("Cycle detected", str(ctx.exception))

    def test_invalid_action_references(self):
        # Action in dependency not in actions list
        bad_data = {
            "work": "missing-action-test",
            "version": "3.0",
            "inputs": ["x"],
            "outputs": ["y"],
            "states": ["s1"],
            "actions": ["a1"],
            "dependencies": {
                "a1": ["missing_prereq"],
            },
            "invariants": [],
            "quality": {},
            "executors": {"a1": {"type": "code"}},
        }
        with self.assertRaises(WorkIRValidationError):
            load_work_ir(bad_data)

    def test_invalid_executor_type(self):
        bad_data = {
            "work": "invalid-executor-test",
            "version": "3.0",
            "inputs": ["x"],
            "outputs": ["y"],
            "states": ["s1"],
            "actions": ["a1"],
            "dependencies": {},
            "invariants": [],
            "quality": {},
            "executors": {"a1": {"type": "quantum_computer"}},
        }
        with self.assertRaises(WorkIRValidationError):
            load_work_ir(bad_data)

    def test_yaml_export_and_roundtrip(self):
        work_ir = load_work_ir("examples/customer-renewal/work.yaml")
        yaml_str = to_yaml(work_ir)
        self.assertIn("work: customer-renewal", yaml_str)
        self.assertIn("actions:", yaml_str)
        self.assertIn("type: slm", yaml_str)

        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            save_work_ir(work_ir, temp_path)
            reloaded = load_work_ir(temp_path)
            self.assertEqual(reloaded.work, work_ir.work)
            self.assertEqual(reloaded.actions, work_ir.actions)
            self.assertEqual(reloaded.dependencies, work_ir.dependencies)
            self.assertEqual(reloaded.executors["price_offer"].type, ExecutorType.RULE)
        finally:
            Path(temp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
