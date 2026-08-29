"""Unit tests for OpenWorkCompiler Durable Runtime Engine and Executors."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from core.runtime.engine import (
    DurableRuntimeEngine,
    StepExecutionRecord,
    StepStatus,
    WaitCondition,
    WaitType,
    WorkflowInstance,
    WorkflowStatus,
)
from core.runtime.executors import (
    ActionResult,
    BaseExecutor,
    CodeExecutor,
    HumanExecutor,
    HTTPExecutor,
    LLMExecutor,
    MLExecutor,
    RuleExecutor,
    SLMExecutor,
)


class TestActionResult(unittest.TestCase):
    """Test ActionResult factory methods and serialization."""

    def test_ok_result(self):
        res = ActionResult.ok(output={"result": 42}, metadata={"duration": 10})
        self.assertTrue(res.success)
        self.assertEqual(res.output, {"result": 42})
        self.assertIsNone(res.error)
        self.assertFalse(res.is_waiting)

    def test_fail_result(self):
        res = ActionResult.fail(error="Something failed", metadata={"attempt": 1})
        self.assertFalse(res.success)
        self.assertEqual(res.error, "Something failed")
        self.assertFalse(res.is_waiting)

    def test_wait_conditions(self):
        human_wait = ActionResult.wait_for_human(
            prompt="Approve invoice",
            assignee="manager@company.com",
            required_fields=["approved", "comments"],
        )
        self.assertTrue(human_wait.is_waiting)
        self.assertEqual(human_wait.wait_condition["wait_type"], "HUMAN")
        self.assertEqual(human_wait.wait_condition["assignee"], "manager@company.com")

        event_wait = ActionResult.wait_for_event(event_name="payment_webhook", timeout_seconds=300)
        self.assertTrue(event_wait.is_waiting)
        self.assertEqual(event_wait.wait_condition["wait_type"], "EVENT")
        self.assertEqual(event_wait.wait_condition["event_name"], "payment_webhook")

        timer_wait = ActionResult.wait_for_timer(delay_seconds=60)
        self.assertTrue(timer_wait.is_waiting)
        self.assertEqual(timer_wait.wait_condition["wait_type"], "TIMER")
        self.assertEqual(timer_wait.wait_condition["delay_seconds"], 60)

    def test_serialization(self):
        res = ActionResult.ok(output={"k": "v"}, metadata={"source": "unit_test"}, logs=["log 1"])
        d = res.to_dict()
        restored = ActionResult.from_dict(d)
        self.assertEqual(restored.output, {"k": "v"})
        self.assertEqual(restored.metadata, {"source": "unit_test"})
        self.assertEqual(restored.logs, ["log 1"])


class TestExecutors(unittest.TestCase):
    """Test all 7 concrete executor implementations."""

    def test_code_executor_registered_handler(self):
        executor = CodeExecutor()
        executor.register_handler("double_number", lambda number: number * 2)

        res = executor.execute(action_name="double_number", inputs={"number": 21})
        self.assertTrue(res.success)
        self.assertEqual(res.output, 42)

    def test_code_executor_dynamic_import(self):
        executor = CodeExecutor(
            config={"allow_dynamic_imports": True, "allowed_import_modules": ["math"]}
        )
        res = executor.execute(action_name="math.sqrt", inputs={"x": 16})
        self.assertTrue(res.success)
        self.assertEqual(res.output, 4.0)

    def test_code_executor_blocks_dynamic_import_by_default(self):
        res = CodeExecutor().execute(action_name="math.sqrt", inputs={"x": 16})
        self.assertFalse(res.success)
        self.assertIn("Dynamic callable imports are disabled", res.error)

    def test_code_executor_blocks_non_allowlisted_dynamic_import(self):
        executor = CodeExecutor(
            config={"allow_dynamic_imports": True, "allowed_import_modules": ["math"]}
        )
        res = executor.execute(action_name="os.system", inputs={"command": "echo unsafe"})
        self.assertFalse(res.success)
        self.assertIn("not allowlisted", res.error)

    def test_code_executor_error_handling(self):
        executor = CodeExecutor()
        executor.register_handler("divide", lambda a, b: a / b)

        res = executor.execute(action_name="divide", inputs={"a": 10, "b": 0})
        self.assertFalse(res.success)
        self.assertIn("ZeroDivisionError", res.error)

    def test_rule_executor_declarative(self):
        rules = [
            {
                "name": "enterprise_discount",
                "when": [{"field": "tier", "op": "==", "value": "enterprise"}, {"field": "seats", "op": ">=", "value": 50}],
                "then": {"discount_rate": 0.25, "policy": "volume_discount"},
            },
            {
                "name": "standard_discount",
                "when": [{"field": "tier", "op": "==", "value": "pro"}],
                "then": {"discount_rate": 0.10, "policy": "standard_pro"},
            },
        ]
        executor = RuleExecutor(rules={"pricing_rules": rules})

        res = executor.execute(action_name="pricing_rules", inputs={"tier": "enterprise", "seats": 100})
        self.assertTrue(res.success)
        self.assertEqual(res.output.get("discount_rate"), 0.25)
        self.assertEqual(res.output.get("policy"), "volume_discount")

    def test_rule_executor_callable(self):
        executor = RuleExecutor()
        executor.register_rule("custom_policy", lambda inputs, ctx: {"eligible": inputs["score"] > 80})

        res = executor.execute(action_name="custom_policy", inputs={"score": 95})
        self.assertTrue(res.success)
        self.assertEqual(res.output, {"eligible": True})

    def test_http_executor_formatting(self):
        executor = HTTPExecutor(base_url="https://httpbin.org")
        # Test input formatting without making a network call by checking validation
        executor_no_url = HTTPExecutor()
        res = executor_no_url.execute(action_name="bad_action", inputs={})
        self.assertFalse(res.success)
        self.assertIn("No URL provided", res.error)

    def test_http_executor_blocks_loopback_ssrf_before_request(self):
        executor = HTTPExecutor()
        res = executor.execute(action_name="probe", inputs={"url": "http://127.0.0.1:8080/health"})
        self.assertFalse(res.success)
        self.assertIn("blocked private or non-routable", res.error)

    def test_http_executor_blocks_private_hostname_ssrf_before_request(self):
        executor = HTTPExecutor()
        res = executor.execute(action_name="probe", inputs={"url": "http://localhost:8080/health"})
        self.assertFalse(res.success)
        self.assertIn("blocked private or non-routable", res.error)

    def test_ml_executor(self):
        class MockModel:
            def predict(self, features):
                return [1 if f.get("credit_score", 0) > 700 else 0 for f in features]

        executor = MLExecutor()
        executor.register_model("credit_scoring_model", MockModel())

        res = executor.execute(
            action_name="credit_scoring_model",
            inputs={"features": [{"credit_score": 750}, {"credit_score": 620}]},
        )
        self.assertTrue(res.success)
        self.assertEqual(res.output, [1, 0])

    def test_slm_executor(self):
        executor = SLMExecutor()
        res = executor.execute(
            action_name="draft_renewal",
            inputs={
                "preferred": "models/renewal-slm-v1",
                "prompt": "Draft renewal proposal for customer {customer_name}",
                "customer_name": "Acme Corp",
            },
        )
        self.assertTrue(res.success)
        self.assertEqual(res.metadata["model"], "models/renewal-slm-v1")
        self.assertIn("Acme Corp", str(res.output) + res.metadata["model"])

    def test_llm_executor(self):
        def mock_llm_client(system_prompt, user_prompt, model, inputs, context):
            return {"analysis": f"Evaluated {inputs.get('subject')} with {model}", "decision": "APPROVE"}

        executor = LLMExecutor(client=mock_llm_client)
        res = executor.execute(
            action_name="analyze_risk",
            inputs={"subject": "Contract #1234", "model": "frontier_llm"},
        )
        self.assertTrue(res.success)
        self.assertEqual(res.output["decision"], "APPROVE")
        self.assertEqual(res.metadata["model"], "frontier_llm")

    def test_human_executor_suspension_and_approval(self):
        executor = HumanExecutor()

        # Without decision -> yields wait
        suspend_res = executor.execute(
            action_name="approve_refund",
            inputs={"prompt": "Please review refund for $5,000", "assignee": "finance_lead"},
        )
        self.assertTrue(suspend_res.is_waiting)
        self.assertEqual(suspend_res.wait_condition["wait_type"], "HUMAN")
        self.assertEqual(suspend_res.wait_condition["assignee"], "finance_lead")

        # With decision -> completes
        approve_res = executor.execute(
            action_name="approve_refund",
            inputs={"approved": True, "reviewer": "finance_lead", "comments": "Approved per SLA"},
        )
        self.assertTrue(approve_res.success)
        self.assertFalse(approve_res.is_waiting)
        self.assertTrue(approve_res.output["approved"])
        self.assertEqual(approve_res.output["reviewer"], "finance_lead")


class TestDurableRuntimeEngine(unittest.TestCase):
    """Test stateful DurableRuntimeEngine lifecycle, wait states, and checkpointing."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.engine = DurableRuntimeEngine(storage_dir=self.temp_dir.name)

        # Register custom test handlers
        code_exec: CodeExecutor = self.engine.get_executor("code")  # type: ignore
        code_exec.register_handler("lookup_contract", lambda customer_id: {"contract_id": f"CTR-{customer_id}", "status": "active"})
        code_exec.register_handler("calculate_usage", lambda contract_id: {"usage_hours": 120, "tier": "enterprise"})
        code_exec.register_handler("send_email", lambda proposal_text, recipient: {"email_sent": True, "recipient": recipient})

        rule_exec: RuleExecutor = self.engine.get_executor("rule")  # type: ignore
        rule_exec.register_rule("price_offer", lambda inputs, ctx: {"discount": 0.20, "total_price": 40000})

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_full_workflow_lifecycle(self):
        work_def = {
            "work": "customer-renewal",
            "version": "4.0",
            "inputs": ["customer_id"],
            "outputs": ["contract_id", "total_price"],
            "actions": ["lookup_contract", "calculate_usage", "price_offer"],
            "dependencies": {
                "calculate_usage": ["lookup_contract"],
                "price_offer": ["calculate_usage"],
            },
            "executors": {
                "lookup_contract": {"type": "code"},
                "calculate_usage": {"type": "code"},
                "price_offer": {"type": "rule"},
            },
        }

        # 1. Start workflow
        wf = self.engine.start_workflow(
            workflow_id="wf-001",
            work_definition=work_def,
            initial_inputs={"customer_id": "CUST-999"},
        )
        self.assertEqual(wf.status, WorkflowStatus.RUNNING)
        self.assertEqual(wf.workflow_id, "wf-001")

        # 2. Check executable steps (only lookup_contract should be ready initially)
        ready = self.engine.get_executable_steps("wf-001")
        self.assertEqual(ready, ["lookup_contract"])

        # 3. Execute step 1
        res1 = self.engine.execute_step("wf-001", "lookup_contract")
        self.assertTrue(res1.success)
        self.assertIn("contract_id", wf.state_data)
        self.assertEqual(wf.state_data["contract_id"], "CTR-CUST-999")

        # 4. Next executable step
        ready = self.engine.get_executable_steps("wf-001")
        self.assertEqual(ready, ["calculate_usage"])

        # 5. Run until complete
        self.engine.run_until_blocked_or_complete("wf-001")
        self.assertEqual(wf.status, WorkflowStatus.COMPLETED)
        self.assertEqual(wf.completed_steps, ["lookup_contract", "calculate_usage", "price_offer"])
        self.assertEqual(wf.outputs.get("total_price"), 40000)

    def test_wait_states_waiting_event(self):
        work_def = {
            "work": "payment-approval",
            "actions": ["initiate_payment", "await_webhook", "send_receipt"],
            "dependencies": {
                "await_webhook": ["initiate_payment"],
                "send_receipt": ["await_webhook"],
            },
            "executors": {
                "initiate_payment": {"type": "code"},
                "await_webhook": {"type": "code"},
                "send_receipt": {"type": "code"},
            },
        }
        code_exec: CodeExecutor = self.engine.get_executor("code")  # type: ignore
        code_exec.register_handler("initiate_payment", lambda order_id: {"order_id": order_id, "status": "pending"})
        code_exec.register_handler("await_webhook", lambda **kwargs: ActionResult.wait_for_event("payment_confirmed"))
        code_exec.register_handler("send_receipt", lambda order_id, **kwargs: {"receipt_sent": True})

        wf = self.engine.start_workflow("wf-event-01", work_def, {"order_id": "ORD-123"})

        # Step 1
        self.engine.execute_step("wf-event-01", "initiate_payment")
        self.assertEqual(wf.status, WorkflowStatus.RUNNING)

        # Step 2 -> Suspends into WAITING_EVENT
        self.engine.execute_step("wf-event-01", "await_webhook")
        self.assertEqual(wf.status, WorkflowStatus.WAITING_EVENT)
        self.assertIsNotNone(wf.pending_wait)
        self.assertEqual(wf.pending_wait.wait_type, WaitType.EVENT)
        self.assertEqual(wf.pending_wait.event_name, "payment_confirmed")

        # External signal received
        self.engine.signal_event("wf-event-01", "payment_confirmed", {"transaction_id": "TX-999"})
        self.assertEqual(wf.status, WorkflowStatus.RUNNING)
        self.assertIn("await_webhook", wf.completed_steps)

        # Step 3 completes workflow
        self.engine.run_until_blocked_or_complete("wf-event-01")
        self.assertEqual(wf.status, WorkflowStatus.COMPLETED)

    def test_wait_states_waiting_human(self):
        work_def = {
            "work": "loan-application",
            "actions": ["evaluate_risk", "human_review", "disburse_funds"],
            "dependencies": {
                "human_review": ["evaluate_risk"],
                "disburse_funds": ["human_review"],
            },
            "executors": {
                "evaluate_risk": {"type": "code"},
                "human_review": {"type": "human"},
                "disburse_funds": {"type": "code"},
            },
        }
        code_exec: CodeExecutor = self.engine.get_executor("code")  # type: ignore
        code_exec.register_handler("evaluate_risk", lambda applicant_id: {"risk_score": 720})
        code_exec.register_handler("disburse_funds", lambda applicant_id, **kwargs: {"disbursed": True})

        wf = self.engine.start_workflow("wf-human-01", work_def, {"applicant_id": "APP-500"})

        # Execute risk evaluation
        self.engine.execute_step("wf-human-01", "evaluate_risk")

        # Execute human review -> enters WAITING_HUMAN
        self.engine.execute_step("wf-human-01", "human_review")
        self.assertEqual(wf.status, WorkflowStatus.WAITING_HUMAN)
        self.assertIsNotNone(wf.pending_wait)
        self.assertEqual(wf.pending_wait.wait_type, WaitType.HUMAN)

        # Human submits approval via signal
        self.engine.signal_event(
            "wf-human-01",
            "human_approval",
            {
                "approved": True,
                "reviewer": "underwriter_bob",
                "decision": "approve",
                "comments": "Risk review passed.",
            },
        )
        self.assertEqual(wf.status, WorkflowStatus.RUNNING)
        self.assertIn("human_review", wf.completed_steps)

        # Finalize
        self.engine.execute_step("wf-human-01", "disburse_funds")
        self.assertEqual(wf.status, WorkflowStatus.COMPLETED)

    def test_wait_states_waiting_timer(self):
        work_def = {
            "work": "delayed-reminder",
            "actions": ["schedule_reminder", "send_notification"],
            "dependencies": {"send_notification": ["schedule_reminder"]},
            "executors": {
                "schedule_reminder": {"type": "code"},
                "send_notification": {"type": "code"},
            },
        }
        code_exec: CodeExecutor = self.engine.get_executor("code")  # type: ignore
        code_exec.register_handler("schedule_reminder", lambda **kwargs: ActionResult.wait_for_timer(delay_seconds=3600))
        code_exec.register_handler("send_notification", lambda **kwargs: {"notified": True})

        wf = self.engine.start_workflow("wf-timer-01", work_def, {})
        self.engine.execute_step("wf-timer-01", "schedule_reminder")

        self.assertEqual(wf.status, WorkflowStatus.WAITING_TIMER)
        self.assertEqual(wf.pending_wait.wait_type, WaitType.TIMER)

        # Trigger timer wake-up
        self.engine.trigger_timer("wf-timer-01", "timer-1")
        self.assertEqual(wf.status, WorkflowStatus.RUNNING)
        self.assertIn("schedule_reminder", wf.completed_steps)

    def test_pause_and_resume(self):
        work_def = {
            "work": "sample",
            "actions": ["step1", "step2"],
            "executors": {"step1": {"type": "code"}, "step2": {"type": "code"}},
        }
        code_exec: CodeExecutor = self.engine.get_executor("code")  # type: ignore
        code_exec.register_handler("step1", lambda: {"s1": 1})
        code_exec.register_handler("step2", lambda: {"s2": 2})

        wf = self.engine.start_workflow("wf-pause-01", work_def)
        self.engine.execute_step("wf-pause-01", "step1")

        # Pause
        self.engine.pause("wf-pause-01", reason="Maintenance window")
        self.assertEqual(wf.status, WorkflowStatus.PAUSED)

        # Trying to execute during pause raises RuntimeError
        with self.assertRaises(RuntimeError):
            self.engine.execute_step("wf-pause-01", "step2")

        # Resume
        self.engine.resume("wf-pause-01")
        self.assertEqual(wf.status, WorkflowStatus.RUNNING)

        # Execute remaining
        self.engine.execute_step("wf-pause-01", "step2")
        self.assertEqual(wf.status, WorkflowStatus.COMPLETED)

    def test_retry_step(self):
        work_def = {
            "work": "flaky-service",
            "actions": ["unstable_call"],
            "executors": {"unstable_call": {"type": "code"}},
        }
        call_count = {"count": 0}

        def flaky_fn():
            call_count["count"] += 1
            if call_count["count"] < 3:
                raise ConnectionError("Temporary network glitch")
            return {"connected": True}

        code_exec: CodeExecutor = self.engine.get_executor("code")  # type: ignore
        code_exec.register_handler("unstable_call", flaky_fn)

        wf = self.engine.start_workflow("wf-retry-01", work_def)

        # Attempt 1 -> fails
        res1 = self.engine.execute_step("wf-retry-01", "unstable_call")
        self.assertFalse(res1.success)
        self.assertIn("unstable_call", wf.failed_steps)

        # Attempt 2 -> retry (fails again)
        res2 = self.engine.retry_step("wf-retry-01", "unstable_call")
        self.assertFalse(res2.success)

        # Attempt 3 -> succeeds
        res3 = self.engine.retry_step("wf-retry-01", "unstable_call")
        self.assertTrue(res3.success)
        self.assertEqual(wf.status, WorkflowStatus.COMPLETED)

    def test_checkpoint_persistence_and_restore(self):
        work_def = {
            "work": "order-fulfillment",
            "actions": ["validate_order", "reserve_inventory"],
            "executors": {"validate_order": {"type": "code"}, "reserve_inventory": {"type": "code"}},
        }
        code_exec: CodeExecutor = self.engine.get_executor("code")  # type: ignore
        code_exec.register_handler("validate_order", lambda order_id: {"order_valid": True})
        code_exec.register_handler("reserve_inventory", lambda item_id: {"reserved": True})

        wf = self.engine.start_workflow(
            "wf-ckpt-01", work_def, {"order_id": "ORD-777", "item_id": "SKU-99"}
        )
        self.engine.execute_step("wf-ckpt-01", "validate_order")

        # Check JSON checkpoint string
        json_str = self.engine.checkpoint("wf-ckpt-01")
        data = json.loads(json_str)
        self.assertEqual(data["workflow_id"], "wf-ckpt-01")
        self.assertIn("validate_order", data["completed_steps"])

        # Checkpoint file exists on disk
        ckpt_file = Path(self.temp_dir.name) / "wf-ckpt-01.json"
        self.assertTrue(ckpt_file.exists())

        # Create a fresh engine and load the checkpoint
        fresh_engine = DurableRuntimeEngine(storage_dir=self.temp_dir.name)
        fresh_code: CodeExecutor = fresh_engine.get_executor("code")  # type: ignore
        fresh_code.register_handler("reserve_inventory", lambda item_id: {"reserved": True})

        restored_wf = fresh_engine.load_checkpoint(ckpt_file)
        self.assertEqual(restored_wf.workflow_id, "wf-ckpt-01")
        self.assertEqual(restored_wf.completed_steps, ["validate_order"])

        # Continue execution on restored engine
        fresh_engine.execute_step("wf-ckpt-01", "reserve_inventory")
        self.assertEqual(restored_wf.status, WorkflowStatus.COMPLETED)
        self.assertIn("reserve_inventory", restored_wf.completed_steps)

    def test_manual_complete_and_fail(self):
        work_def = {"work": "test-fail", "actions": ["step1"]}
        wf = self.engine.start_workflow("wf-fail-01", work_def)
        self.engine.fail("wf-fail-01", reason="Unrecoverable system state")
        self.assertEqual(wf.status, WorkflowStatus.FAILED)

        wf2 = self.engine.start_workflow("wf-comp-01", work_def)
        self.engine.complete("wf-comp-01", final_outputs={"success": True})
        self.assertEqual(wf2.status, WorkflowStatus.COMPLETED)
        self.assertEqual(wf2.outputs, {"success": True})

    def test_dependency_violation(self):
        work_def = {
            "work": "dep-check",
            "actions": ["step1", "step2"],
            "dependencies": {"step2": ["step1"]},
            "executors": {"step1": {"type": "code"}, "step2": {"type": "code"}},
        }
        self.engine.start_workflow("wf-dep-01", work_def)
        with self.assertRaises(RuntimeError) as ctx:
            self.engine.execute_step("wf-dep-01", "step2")
        self.assertIn("unmet dependencies", str(ctx.exception))

    def test_start_rejects_invalid_dependency_dag(self):
        with self.assertRaises(ValueError) as ctx:
            self.engine.start_workflow(
                "wf-cycle-01",
                {
                    "work": "invalid-cycle",
                    "actions": ["first", "second"],
                    "dependencies": {"first": ["second"], "second": ["first"]},
                },
            )
        self.assertIn("contains a cycle", str(ctx.exception))
        self.assertEqual(self.engine.list_workflows(), [])

    def test_human_signal_requires_contract_fields_before_resuming(self):
        work_def = {
            "work": "contracted-human-review",
            "actions": ["human_review"],
            "executors": {
                "human_review": {
                    "type": "human",
                    "required_fields": ["approved", "reviewer"],
                }
            },
        }
        workflow = self.engine.start_workflow("wf-human-contract-01", work_def)
        self.engine.execute_step("wf-human-contract-01", "human_review")

        with self.assertRaises(ValueError) as ctx:
            self.engine.signal_event("wf-human-contract-01", "human_approval", {"approved": True})
        self.assertIn("missing required fields", str(ctx.exception))
        self.assertEqual(workflow.status, WorkflowStatus.WAITING_HUMAN)
        self.assertEqual(workflow.signals, [])

        self.engine.signal_event(
            "wf-human-contract-01", "human_approval", {"approved": True, "reviewer": "alice"}
        )
        self.assertEqual(workflow.status, WorkflowStatus.RUNNING)
        self.assertEqual(workflow.completed_steps, ["human_review"])

    def test_checkpoint_write_leaves_no_partial_temp_file(self):
        work_def = {"work": "checkpoint", "actions": ["step"]}
        self.engine.start_workflow("wf-atomic-checkpoint", work_def)
        checkpoint_path = Path(self.temp_dir.name) / "wf-atomic-checkpoint.json"
        self.assertTrue(checkpoint_path.exists())
        self.assertEqual(list(Path(self.temp_dir.name).glob("*.tmp")), [])

    def test_customer_renewal_end_to_end(self):
        work_def = {
            "work": "customer-renewal",
            "version": "4.0",
            "inputs": ["customer_id"],
            "outputs": ["contract_id", "usage_calculated", "pricing", "draft_proposal"],
            "actions": ["lookup_contract", "calculate_usage", "price_offer", "draft_proposal"],
            "dependencies": {
                "calculate_usage": ["lookup_contract"],
                "price_offer": ["calculate_usage"],
                "draft_proposal": ["price_offer"],
            },
            "executors": {
                "lookup_contract": {"type": "code"},
                "calculate_usage": {"type": "code"},
                "price_offer": {"type": "rule"},
                "draft_proposal": {"type": "slm", "preferred": "models/renewal-slm-v1"},
            },
        }
        code_exec: CodeExecutor = self.engine.get_executor("code")  # type: ignore
        code_exec.register_handler("lookup_contract", lambda customer_id: {"contract_id": f"CTR-{customer_id}"})
        code_exec.register_handler("calculate_usage", lambda contract_id: {"usage_calculated": True, "tier": "enterprise"})

        rule_exec: RuleExecutor = self.engine.get_executor("rule")  # type: ignore
        rule_exec.register_rule("price_offer", lambda inputs, ctx: {"pricing": {"discount": 0.15, "base_price": 50000}})

        wf = self.engine.start_workflow("wf-renewal-full", work_def, {"customer_id": "ACME-100"})
        self.engine.run_until_blocked_or_complete("wf-renewal-full")

        self.assertEqual(wf.status, WorkflowStatus.COMPLETED)
        self.assertEqual(len(wf.completed_steps), 4)
        self.assertEqual(wf.outputs["contract_id"], "CTR-ACME-100")
        self.assertTrue(wf.outputs["usage_calculated"])
        self.assertEqual(wf.outputs["pricing"]["discount"], 0.15)
        self.assertIn("draft_proposal", wf.outputs)



if __name__ == "__main__":
    unittest.main()
