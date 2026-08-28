"""OpenWorkflow Durable Runtime Engine.

Implements the stateful workflow execution state machine:
- WorkflowStatus & StepStatus: Lifecycle state enumerations.
- WaitType & WaitCondition: Structured wait condition models (EVENT, HUMAN, TIMER).
- StepExecutionRecord: Execution history and attempt tracker for each action.
- WorkflowInstance: Serializable, durable snapshot of a running workflow.
- DurableRuntimeEngine: Temporal-like durable execution engine supporting:
    * Workflow lifecycle (start, step execution, retry, pause, resume, complete, fail)
    * 3 key wait states (WAITING_EVENT, WAITING_HUMAN, WAITING_TIMER)
    * Full JSON checkpointing & recovery
    * DAG dependency resolution and automated step progression
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

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

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    """Return current UTC timestamp as ISO 8601 string."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class WorkflowStatus(str, Enum):
    """Lifecycle statuses for a durable workflow instance."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_EVENT = "WAITING_EVENT"
    WAITING_HUMAN = "WAITING_HUMAN"
    WAITING_TIMER = "WAITING_TIMER"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class StepStatus(str, Enum):
    """Lifecycle statuses for individual workflow step actions."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    WAITING = "WAITING"
    SKIPPED = "SKIPPED"


class WaitType(str, Enum):
    """Categories of durable wait states."""

    EVENT = "EVENT"
    HUMAN = "HUMAN"
    TIMER = "TIMER"


class WaitCondition:
    """Represents a suspended wait condition for a workflow step."""

    def __init__(
        self,
        wait_type: Union[WaitType, str],
        step_name: str,
        event_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        timer_expires_at: Optional[str] = None,
        human_prompt: Optional[str] = None,
        human_assignee: Optional[str] = None,
        required_fields: Optional[List[str]] = None,
        created_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.wait_type = WaitType(wait_type) if isinstance(wait_type, str) else wait_type
        self.step_name = step_name
        self.event_name = event_name
        self.timeout_seconds = timeout_seconds
        self.timer_expires_at = timer_expires_at
        self.human_prompt = human_prompt
        self.human_assignee = human_assignee
        self.required_fields = required_fields or []
        self.created_at = created_at or _utc_now_iso()
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize WaitCondition to dictionary."""
        return {
            "wait_type": self.wait_type.value,
            "step_name": self.step_name,
            "event_name": self.event_name,
            "timeout_seconds": self.timeout_seconds,
            "timer_expires_at": self.timer_expires_at,
            "human_prompt": self.human_prompt,
            "human_assignee": self.human_assignee,
            "required_fields": self.required_fields,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WaitCondition:
        """Construct WaitCondition from dictionary."""
        return cls(
            wait_type=data["wait_type"],
            step_name=data["step_name"],
            event_name=data.get("event_name"),
            timeout_seconds=data.get("timeout_seconds"),
            timer_expires_at=data.get("timer_expires_at"),
            human_prompt=data.get("human_prompt"),
            human_assignee=data.get("human_assignee"),
            required_fields=data.get("required_fields", []),
            created_at=data.get("created_at"),
            metadata=data.get("metadata", {}),
        )


class StepExecutionRecord:
    """Tracks execution details, retry attempts, and results for an action step."""

    def __init__(
        self,
        step_name: str,
        status: Union[StepStatus, str] = StepStatus.PENDING,
        executor_type: str = "code",
        attempt: int = 1,
        max_attempts: int = 3,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        result: Optional[ActionResult] = None,
        error: Optional[str] = None,
        logs: Optional[List[str]] = None,
    ) -> None:
        self.step_name = step_name
        self.status = StepStatus(status) if isinstance(status, str) else status
        self.executor_type = executor_type
        self.attempt = attempt
        self.max_attempts = max_attempts
        self.started_at = started_at
        self.completed_at = completed_at
        self.inputs = inputs or {}
        self.result = result
        self.error = error
        self.logs = logs or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert StepExecutionRecord to dictionary."""
        return {
            "step_name": self.step_name,
            "status": self.status.value,
            "executor_type": self.executor_type,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "inputs": self.inputs,
            "result": self.result.to_dict() if self.result else None,
            "error": self.error,
            "logs": self.logs,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StepExecutionRecord:
        """Construct StepExecutionRecord from dictionary."""
        res_data = data.get("result")
        res = ActionResult.from_dict(res_data) if res_data else None
        return cls(
            step_name=data["step_name"],
            status=data.get("status", StepStatus.PENDING),
            executor_type=data.get("executor_type", "code"),
            attempt=data.get("attempt", 1),
            max_attempts=data.get("max_attempts", 3),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            inputs=data.get("inputs", {}),
            result=res,
            error=data.get("error"),
            logs=data.get("logs", []),
        )


class WorkflowInstance:
    """Represents a stateful, durable workflow execution instance."""

    def __init__(
        self,
        workflow_id: str,
        work_name: str,
        definition: Dict[str, Any],
        status: Union[WorkflowStatus, str] = WorkflowStatus.PENDING,
        current_step: Optional[str] = None,
        completed_steps: Optional[List[str]] = None,
        failed_steps: Optional[List[str]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None,
        state_data: Optional[Dict[str, Any]] = None,
        step_records: Optional[Dict[str, StepExecutionRecord]] = None,
        pending_wait: Optional[WaitCondition] = None,
        signals: Optional[List[Dict[str, Any]]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> None:
        self.workflow_id = workflow_id
        self.work_name = work_name
        self.definition = definition
        self.status = WorkflowStatus(status) if isinstance(status, str) else status
        self.current_step = current_step
        self.completed_steps: List[str] = completed_steps or []
        self.failed_steps: List[str] = failed_steps or []
        self.inputs: Dict[str, Any] = inputs or {}
        self.outputs: Dict[str, Any] = outputs or {}
        self.state_data: Dict[str, Any] = state_data or {}
        self.step_records: Dict[str, StepExecutionRecord] = step_records or {}
        self.pending_wait: Optional[WaitCondition] = pending_wait
        self.signals: List[Dict[str, Any]] = signals or []
        self.history: List[Dict[str, Any]] = history or []
        self.created_at = created_at or _utc_now_iso()
        self.updated_at = updated_at or self.created_at

    def log_event(self, event_type: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Append an event to the workflow history audit trail."""
        timestamp = _utc_now_iso()
        self.updated_at = timestamp
        entry = {
            "timestamp": timestamp,
            "event_type": event_type,
            "status": self.status.value,
            "current_step": self.current_step,
            "details": details or {},
        }
        self.history.append(entry)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the entire workflow state into a JSON-serializable dictionary."""
        return {
            "workflow_id": self.workflow_id,
            "work_name": self.work_name,
            "definition": self.definition,
            "status": self.status.value,
            "current_step": self.current_step,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "state_data": self.state_data,
            "step_records": {k: v.to_dict() for k, v in self.step_records.items()},
            "pending_wait": self.pending_wait.to_dict() if self.pending_wait else None,
            "signals": self.signals,
            "history": self.history,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize workflow state snapshot to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WorkflowInstance:
        """Reconstruct a WorkflowInstance from a dictionary."""
        step_records = {}
        for k, v in data.get("step_records", {}).items():
            step_records[k] = StepExecutionRecord.from_dict(v)

        pending_wait = None
        if data.get("pending_wait"):
            pending_wait = WaitCondition.from_dict(data["pending_wait"])

        return cls(
            workflow_id=data["workflow_id"],
            work_name=data.get("work_name", ""),
            definition=data.get("definition", {}),
            status=data.get("status", WorkflowStatus.PENDING),
            current_step=data.get("current_step"),
            completed_steps=data.get("completed_steps", []),
            failed_steps=data.get("failed_steps", []),
            inputs=data.get("inputs", {}),
            outputs=data.get("outputs", {}),
            state_data=data.get("state_data", {}),
            step_records=step_records,
            pending_wait=pending_wait,
            signals=data.get("signals", []),
            history=data.get("history", []),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> WorkflowInstance:
        """Reconstruct a WorkflowInstance from a JSON string."""
        return cls.from_dict(json.loads(json_str))


class DurableRuntimeEngine:
    """Stateful execution engine orchestrating workflow DAGs, executors, and checkpoints.

    Features:
    - Full workflow lifecycle management (start, execute_step, retry_step, pause, resume, complete, fail).
    - First-class support for 3 wait states: WAITING_EVENT, WAITING_HUMAN, WAITING_TIMER.
    - Checkpointing to JSON state and file restoration.
    - Dependency graph validation and automatic step resolution.
    """

    def __init__(
        self,
        executors: Optional[Dict[str, BaseExecutor]] = None,
        storage_dir: Optional[Union[str, Path]] = None,
        auto_checkpoint: bool = True,
    ) -> None:
        """Initialize DurableRuntimeEngine.

        Args:
            executors: Custom mapping of executor types to BaseExecutor instances.
            storage_dir: Directory path where workflow checkpoint JSON files are saved.
            auto_checkpoint: If True, automatically persists state snapshots on each transition.
        """
        self.storage_dir = Path(storage_dir) if storage_dir else None
        if self.storage_dir:
            self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.auto_checkpoint = auto_checkpoint
        self._workflows: Dict[str, WorkflowInstance] = {}

        # Default executor registry
        self._executors: Dict[str, BaseExecutor] = {
            "code": CodeExecutor(),
            "rule": RuleExecutor(),
            "http": HTTPExecutor(),
            "ml": MLExecutor(),
            "slm": SLMExecutor(),
            "frontier_llm": LLMExecutor(),
            "llm": LLMExecutor(),
            "human": HumanExecutor(),
        }
        if executors:
            self._executors.update(executors)

    def register_executor(self, executor_type: str, executor: BaseExecutor) -> None:
        """Register or replace an executor for a specific type identifier."""
        self._executors[executor_type] = executor

    def get_executor(self, executor_type: str) -> BaseExecutor:
        """Retrieve an executor by type.

        Raises:
            KeyError: If no executor is registered for the specified type.
        """
        if executor_type in self._executors:
            return self._executors[executor_type]
        raise KeyError(
            f"No executor registered for type '{executor_type}'. "
            f"Available executors: {list(self._executors.keys())}"
        )

    def get_workflow(self, workflow_id: str) -> WorkflowInstance:
        """Get an active workflow instance by its ID."""
        if workflow_id in self._workflows:
            return self._workflows[workflow_id]
        raise KeyError(f"Workflow with ID '{workflow_id}' not found in engine.")

    def list_workflows(self) -> List[WorkflowInstance]:
        """Return a list of all loaded workflow instances."""
        return list(self._workflows.values())

    # -------------------------------------------------------------------------
    # Lifecycle Operations
    # -------------------------------------------------------------------------

    def start_workflow(
        self,
        workflow_id: str,
        work_definition: Dict[str, Any],
        initial_inputs: Optional[Dict[str, Any]] = None,
    ) -> WorkflowInstance:
        """Start a new workflow instance and transition it to RUNNING.

        Args:
            workflow_id: Unique identifier for this execution run.
            work_definition: Work IR dictionary containing actions, dependencies, executors.
            initial_inputs: Initial input payload for the workflow.

        Returns:
            The initialized WorkflowInstance.
        """
        if workflow_id in self._workflows:
            raise ValueError(f"Workflow with ID '{workflow_id}' already exists.")

        if hasattr(work_definition, "to_dict"):
            work_definition = work_definition.to_dict()

        self._validate_work_definition(work_definition)

        work_name = work_definition.get("work", "unnamed_workflow")
        inputs = initial_inputs or {}

        instance = WorkflowInstance(
            workflow_id=workflow_id,
            work_name=work_name,
            definition=work_definition,
            status=WorkflowStatus.RUNNING,
            inputs=inputs,
            state_data=inputs.copy(),
        )

        instance.log_event("WORKFLOW_STARTED", {"inputs": inputs, "work_name": work_name})
        self._workflows[workflow_id] = instance

        if self.auto_checkpoint:
            self._save_checkpoint_to_disk(instance)

        return instance

    def execute_step(
        self,
        workflow_id: str,
        step_name: str,
        step_inputs: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        """Execute a specific step within a workflow instance.

        Validates prerequisites, resolves inputs, calls the registered executor,
        handles wait conditions (WAITING_EVENT, WAITING_HUMAN, WAITING_TIMER),
        and updates state.

        Args:
            workflow_id: Workflow instance identifier.
            step_name: Action step name to execute.
            step_inputs: Optional explicit input overrides for this step.

        Returns:
            ActionResult representing the execution outcome.
        """
        instance = self.get_workflow(workflow_id)

        if instance.status not in (
            WorkflowStatus.RUNNING,
            WorkflowStatus.WAITING_EVENT,
            WorkflowStatus.WAITING_HUMAN,
            WorkflowStatus.WAITING_TIMER,
        ):
            raise RuntimeError(
                f"Cannot execute step '{step_name}' because workflow '{workflow_id}' "
                f"is in state '{instance.status.value}'."
            )

        # Check action dependencies
        dependencies = instance.definition.get("dependencies", {})
        required_deps = dependencies.get(step_name, [])
        unmet = [dep for dep in required_deps if dep not in instance.completed_steps]
        if unmet:
            raise RuntimeError(
                f"Cannot execute step '{step_name}': unmet dependencies {unmet}."
            )

        instance.current_step = step_name

        # Resolve executor configuration
        executor_configs = instance.definition.get("executors", {})
        step_exec_cfg = executor_configs.get(step_name, {})
        if isinstance(step_exec_cfg, str):
            executor_type = step_exec_cfg
            step_exec_cfg = {}
        else:
            executor_type = step_exec_cfg.get("type", "code")

        executor = self.get_executor(executor_type)

        # Assemble effective step inputs:
        # 1. Base workflow inputs
        # 2. Accumulated state data from previous actions
        # 3. Config fields from Work IR executor block (handler, preferred, etc.)
        # 4. Explicit step_inputs
        effective_inputs: Dict[str, Any] = instance.inputs.copy()
        effective_inputs.update(instance.state_data)
        effective_inputs.update(step_exec_cfg)
        if step_inputs:
            effective_inputs.update(step_inputs)

        # Initialize or retrieve step record
        record = instance.step_records.get(step_name)
        if record is None:
            record = StepExecutionRecord(
                step_name=step_name,
                status=StepStatus.RUNNING,
                executor_type=executor_type,
                attempt=1,
                started_at=_utc_now_iso(),
                inputs=effective_inputs,
            )
            instance.step_records[step_name] = record
        else:
            record.status = StepStatus.RUNNING
            record.started_at = _utc_now_iso()
            record.inputs = effective_inputs

        instance.log_event("STEP_STARTED", {"step": step_name, "executor_type": executor_type})

        # Execute the action
        result = executor.execute(
            action_name=step_name,
            inputs=effective_inputs,
            context={"workflow_id": workflow_id, "state_data": instance.state_data},
        )

        record.result = result
        record.completed_at = _utc_now_iso()
        record.logs.extend(result.logs)

        # Check for suspended wait state
        if result.is_waiting and result.wait_condition:
            cond_data = result.wait_condition
            wait_type_str = cond_data.get("wait_type", "EVENT").upper()

            if wait_type_str == "HUMAN":
                target_status = WorkflowStatus.WAITING_HUMAN
                wait_type = WaitType.HUMAN
            elif wait_type_str == "TIMER":
                target_status = WorkflowStatus.WAITING_TIMER
                wait_type = WaitType.TIMER
            else:
                target_status = WorkflowStatus.WAITING_EVENT
                wait_type = WaitType.EVENT

            instance.status = target_status
            record.status = StepStatus.WAITING

            expires_at = cond_data.get("expires_at")
            delay = cond_data.get("delay_seconds")
            if delay and not expires_at:
                expires_at = (
                    datetime.datetime.now(datetime.timezone.utc)
                    + datetime.timedelta(seconds=delay)
                ).isoformat()

            instance.pending_wait = WaitCondition(
                wait_type=wait_type,
                step_name=step_name,
                event_name=cond_data.get("event_name"),
                timeout_seconds=cond_data.get("timeout_seconds"),
                timer_expires_at=expires_at,
                human_prompt=cond_data.get("prompt"),
                human_assignee=cond_data.get("assignee"),
                required_fields=cond_data.get("required_fields", []),
                metadata=cond_data.get("metadata", {}),
            )

            instance.log_event(
                "STEP_WAITING",
                {"step": step_name, "wait_type": wait_type.value, "condition": cond_data},
            )

        elif result.success:
            record.status = StepStatus.COMPLETED
            record.error = None
            if step_name not in instance.completed_steps:
                instance.completed_steps.append(step_name)
            if step_name in instance.failed_steps:
                instance.failed_steps.remove(step_name)

            # Accumulate result into workflow state
            if result.output is not None:
                if isinstance(result.output, dict):
                    instance.state_data.update(result.output)
                instance.state_data[step_name] = result.output

            instance.status = WorkflowStatus.RUNNING
            instance.pending_wait = None
            instance.log_event(
                "STEP_COMPLETED",
                {
                    "step": step_name,
                    "execution_time_ms": result.execution_time_ms,
                    "output_preview": str(result.output)[:120],
                },
            )

            # Check if all actions in DAG are completed
            all_actions = instance.definition.get("actions", [])
            if all_actions and all(a in instance.completed_steps for a in all_actions):
                self._finalize_auto_complete(instance)

        else:
            record.status = StepStatus.FAILED
            record.error = result.error
            if step_name not in instance.failed_steps:
                instance.failed_steps.append(step_name)

            instance.log_event("STEP_FAILED", {"step": step_name, "error": result.error})

        if self.auto_checkpoint:
            self._save_checkpoint_to_disk(instance)

        return result

    def retry_step(
        self,
        workflow_id: str,
        step_name: str,
        step_inputs: Optional[Dict[str, Any]] = None,
        reset_attempt: bool = False,
    ) -> ActionResult:
        """Retry a failed or pending step in the workflow.

        Args:
            workflow_id: Workflow identifier.
            step_name: Name of the step to retry.
            step_inputs: Optional updated inputs for the retry attempt.
            reset_attempt: If True, reset attempt count to 1.

        Returns:
            ActionResult of the retried execution.
        """
        instance = self.get_workflow(workflow_id)
        record = instance.step_records.get(step_name)

        if record is None:
            return self.execute_step(workflow_id, step_name, step_inputs)

        if reset_attempt:
            record.attempt = 1
        else:
            record.attempt += 1

        if record.attempt > record.max_attempts:
            err_msg = (
                f"Step '{step_name}' exceeded maximum retry attempts ({record.max_attempts})."
            )
            instance.log_event("STEP_MAX_RETRIES_EXCEEDED", {"step": step_name, "attempts": record.attempt})
            return ActionResult.fail(error=err_msg)

        instance.log_event("STEP_RETRY", {"step": step_name, "attempt": record.attempt})

        # Ensure workflow is runnable
        if instance.status in (WorkflowStatus.FAILED, WorkflowStatus.PAUSED):
            instance.status = WorkflowStatus.RUNNING

        return self.execute_step(workflow_id, step_name, step_inputs)

    def signal_event(
        self,
        workflow_id: str,
        event_name: str,
        payload: Any = None,
    ) -> WorkflowInstance:
        """Deliver an external signal/event to a workflow instance.

        If the workflow is in WAITING_EVENT or WAITING_HUMAN, matching signals
        resume execution.

        Args:
            workflow_id: Workflow instance identifier.
            event_name: Name/identifier of the signal event.
            payload: Optional payload data associated with the event.

        Returns:
            Updated WorkflowInstance.
        """
        instance = self.get_workflow(workflow_id)

        # A rejected human response must not become part of workflow state or
        # audit history as if it had been accepted.
        if instance.status == WorkflowStatus.WAITING_HUMAN and instance.pending_wait:
            self._validate_human_signal_payload(instance.pending_wait, payload)

        signal_record = {
            "timestamp": _utc_now_iso(),
            "event_name": event_name,
            "payload": payload,
        }
        instance.signals.append(signal_record)
        instance.log_event("SIGNAL_RECEIVED", signal_record)

        # Merge payload into state if dictionary
        if isinstance(payload, dict):
            instance.state_data.update(payload)

        # Check if workflow is waiting for this signal
        if instance.status == WorkflowStatus.WAITING_EVENT and instance.pending_wait:
            expected = instance.pending_wait.event_name
            if expected is None or expected == event_name:
                waiting_step = instance.pending_wait.step_name
                instance.pending_wait = None
                instance.status = WorkflowStatus.RUNNING

                # Mark waiting step as completed if pending
                if waiting_step in instance.step_records:
                    rec = instance.step_records[waiting_step]
                    rec.status = StepStatus.COMPLETED
                    rec.result = ActionResult.ok(output=payload)
                    if waiting_step not in instance.completed_steps:
                        instance.completed_steps.append(waiting_step)

                instance.log_event("WAIT_EVENT_RESOLVED", {"step": waiting_step, "event": event_name})

        # Check if workflow is waiting for human response
        elif instance.status == WorkflowStatus.WAITING_HUMAN and instance.pending_wait:
            waiting_step = instance.pending_wait.step_name
            instance.pending_wait = None
            instance.status = WorkflowStatus.RUNNING

            # Complete step with human decision
            if waiting_step in instance.step_records:
                rec = instance.step_records[waiting_step]
                rec.status = StepStatus.COMPLETED
                rec.result = ActionResult.ok(
                    output=payload,
                    metadata={"completed_by_human": True, "event": event_name},
                )
                if waiting_step not in instance.completed_steps:
                    instance.completed_steps.append(waiting_step)

            instance.log_event("WAIT_HUMAN_RESOLVED", {"step": waiting_step, "payload": payload})

        if self.auto_checkpoint:
            self._save_checkpoint_to_disk(instance)

        return instance

    def trigger_timer(
        self,
        workflow_id: str,
        timer_id: Optional[str] = None,
    ) -> WorkflowInstance:
        """Trigger timer expiration for a workflow in WAITING_TIMER state."""
        instance = self.get_workflow(workflow_id)

        if instance.status == WorkflowStatus.WAITING_TIMER and instance.pending_wait:
            waiting_step = instance.pending_wait.step_name
            instance.pending_wait = None
            instance.status = WorkflowStatus.RUNNING

            if waiting_step in instance.step_records:
                rec = instance.step_records[waiting_step]
                rec.status = StepStatus.COMPLETED
                rec.result = ActionResult.ok(
                    output={"timer_expired": True, "timer_id": timer_id},
                    metadata={"resumed_from_timer": True},
                )
                if waiting_step not in instance.completed_steps:
                    instance.completed_steps.append(waiting_step)

            instance.log_event("WAIT_TIMER_RESOLVED", {"step": waiting_step, "timer_id": timer_id})

            if self.auto_checkpoint:
                self._save_checkpoint_to_disk(instance)

        return instance

    def pause(self, workflow_id: str, reason: str = "") -> WorkflowInstance:
        """Pause execution of an active or waiting workflow instance."""
        instance = self.get_workflow(workflow_id)
        if instance.status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELED):
            raise RuntimeError(f"Cannot pause workflow in terminal state '{instance.status.value}'.")

        instance.log_event("WORKFLOW_PAUSED", {"previous_status": instance.status.value, "reason": reason})
        instance.status = WorkflowStatus.PAUSED

        if self.auto_checkpoint:
            self._save_checkpoint_to_disk(instance)

        return instance

    def resume(self, workflow_id: str) -> WorkflowInstance:
        """Resume execution of a paused workflow instance."""
        instance = self.get_workflow(workflow_id)
        if instance.status != WorkflowStatus.PAUSED:
            raise RuntimeError(f"Cannot resume workflow that is not PAUSED (current: '{instance.status.value}').")

        # If there is a pending wait condition, restore that specific wait state
        if instance.pending_wait:
            if instance.pending_wait.wait_type == WaitType.HUMAN:
                instance.status = WorkflowStatus.WAITING_HUMAN
            elif instance.pending_wait.wait_type == WaitType.TIMER:
                instance.status = WorkflowStatus.WAITING_TIMER
            else:
                instance.status = WorkflowStatus.WAITING_EVENT
        else:
            instance.status = WorkflowStatus.RUNNING

        instance.log_event("WORKFLOW_RESUMED", {"restored_status": instance.status.value})

        if self.auto_checkpoint:
            self._save_checkpoint_to_disk(instance)

        return instance

    def complete(
        self,
        workflow_id: str,
        final_outputs: Optional[Dict[str, Any]] = None,
    ) -> WorkflowInstance:
        """Mark a workflow instance as successfully COMPLETED."""
        instance = self.get_workflow(workflow_id)
        instance.status = WorkflowStatus.COMPLETED
        if final_outputs is not None:
            instance.outputs = final_outputs
        else:
            # Extract expected outputs from state_data based on definition
            expected = instance.definition.get("outputs", [])
            instance.outputs = {
                k: instance.state_data.get(k) for k in expected if k in instance.state_data
            } or instance.state_data.copy()

        instance.log_event("WORKFLOW_COMPLETED", {"outputs": instance.outputs})

        if self.auto_checkpoint:
            self._save_checkpoint_to_disk(instance)

        return instance

    def fail(self, workflow_id: str, reason: str) -> WorkflowInstance:
        """Mark a workflow instance as FAILED with an error reason."""
        instance = self.get_workflow(workflow_id)
        instance.status = WorkflowStatus.FAILED
        instance.log_event("WORKFLOW_FAILED", {"reason": reason})

        if self.auto_checkpoint:
            self._save_checkpoint_to_disk(instance)

        return instance

    def cancel(self, workflow_id: str, reason: str = "") -> WorkflowInstance:
        """Cancel a workflow instance."""
        instance = self.get_workflow(workflow_id)
        instance.status = WorkflowStatus.CANCELED
        instance.log_event("WORKFLOW_CANCELED", {"reason": reason})

        if self.auto_checkpoint:
            self._save_checkpoint_to_disk(instance)

        return instance

    # -------------------------------------------------------------------------
    # DAG & Auto Execution Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _validate_work_definition(work_definition: Dict[str, Any]) -> None:
        """Reject malformed dependency graphs before creating durable state.

        WorkIR objects normally provide this validation at compile time, but the
        runtime also accepts raw dictionaries from protocol adapters and restored
        integrations.  Validating here prevents workflows that can never make
        progress from being checkpointed as RUNNING.
        """
        actions = work_definition.get("actions", [])
        dependencies = work_definition.get("dependencies", {})
        if not isinstance(actions, list) or not all(isinstance(action, str) for action in actions):
            raise ValueError("Work definition 'actions' must be a list of action names.")
        if len(actions) != len(set(actions)):
            raise ValueError("Work definition 'actions' must not contain duplicate action names.")
        if not isinstance(dependencies, dict):
            raise ValueError("Work definition 'dependencies' must be a mapping of action names.")

        action_set = set(actions)
        in_degree = {action: 0 for action in actions}
        downstream: Dict[str, List[str]] = {action: [] for action in actions}
        for action, prerequisites in dependencies.items():
            if action not in action_set:
                raise ValueError(f"Dependency target '{action}' is not listed in actions.")
            if not isinstance(prerequisites, list):
                raise ValueError(f"Dependencies for '{action}' must be a list.")
            for prerequisite in prerequisites:
                if prerequisite not in action_set:
                    raise ValueError(
                        f"Prerequisite '{prerequisite}' for '{action}' is not listed in actions."
                    )
                in_degree[action] += 1
                downstream[prerequisite].append(action)

        ready = [action for action in actions if in_degree[action] == 0]
        visited = 0
        while ready:
            action = ready.pop()
            visited += 1
            for dependent in downstream[action]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    ready.append(dependent)
        if visited != len(actions):
            cyclic = [action for action in actions if in_degree[action] > 0]
            raise ValueError(f"Work definition dependency DAG contains a cycle: {cyclic}.")

    @staticmethod
    def _validate_human_signal_payload(wait: WaitCondition, payload: Any) -> None:
        """Ensure a human response satisfies the fields requested by its wait."""
        required_fields = wait.required_fields
        if not required_fields:
            return
        if not isinstance(payload, dict):
            raise ValueError(
                "Human response payload must be an object containing the required fields: "
                f"{required_fields}."
            )
        missing = [field for field in required_fields if field not in payload]
        if missing:
            raise ValueError(
                f"Human response for step '{wait.step_name}' is missing required fields: {missing}."
            )

    def get_executable_steps(self, workflow_id: str) -> List[str]:
        """Return the list of actions whose dependencies are fulfilled and are not yet completed."""
        instance = self.get_workflow(workflow_id)
        actions = instance.definition.get("actions", [])
        dependencies = instance.definition.get("dependencies", {})
        executable: List[str] = []

        for action in actions:
            if action in instance.completed_steps:
                continue
            deps = dependencies.get(action, [])
            if all(d in instance.completed_steps for d in deps):
                executable.append(action)

        return executable

    def run_until_blocked_or_complete(self, workflow_id: str) -> WorkflowInstance:
        """Execute executable steps sequentially until the workflow is blocked or completes.

        Stops when:
        - Workflow enters a wait state (WAITING_EVENT, WAITING_HUMAN, WAITING_TIMER)
        - Workflow completes, fails, or pauses
        - No further steps are ready to execute
        """
        instance = self.get_workflow(workflow_id)

        while instance.status == WorkflowStatus.RUNNING:
            ready_steps = self.get_executable_steps(workflow_id)
            if not ready_steps:
                # If all actions finished, complete workflow
                all_actions = instance.definition.get("actions", [])
                if all_actions and all(a in instance.completed_steps for a in all_actions):
                    self.complete(workflow_id)
                break

            for step in ready_steps:
                res = self.execute_step(workflow_id, step)
                if not res.success or res.is_waiting:
                    break
                if instance.status != WorkflowStatus.RUNNING:
                    break

        return instance

    def _finalize_auto_complete(self, instance: WorkflowInstance) -> None:
        """Auto-complete workflow if all defined actions are satisfied."""
        expected = instance.definition.get("outputs", [])
        instance.outputs = {
            k: instance.state_data.get(k) for k in expected if k in instance.state_data
        } or instance.state_data.copy()
        instance.status = WorkflowStatus.COMPLETED
        instance.log_event("WORKFLOW_COMPLETED_AUTO", {"outputs": instance.outputs})

    # -------------------------------------------------------------------------
    # Checkpointing & Persistence
    # -------------------------------------------------------------------------

    def checkpoint(self, workflow_id: str) -> str:
        """Generate a JSON state checkpoint string for the specified workflow."""
        instance = self.get_workflow(workflow_id)
        return instance.to_json()

    def save_checkpoint(
        self, workflow_id: str, filepath: Optional[Union[str, Path]] = None
    ) -> str:
        """Save workflow state snapshot to a JSON file."""
        instance = self.get_workflow(workflow_id)
        target_path = Path(filepath) if filepath else None
        return self._save_checkpoint_to_disk(instance, target_path)

    def load_checkpoint(
        self, checkpoint_data: Union[str, Path, Dict[str, Any]]
    ) -> WorkflowInstance:
        """Restore and register a workflow instance from a JSON string, file, or dictionary."""
        if isinstance(checkpoint_data, dict):
            instance = WorkflowInstance.from_dict(checkpoint_data)
        elif isinstance(checkpoint_data, Path) or (
            isinstance(checkpoint_data, str) and os.path.exists(checkpoint_data)
        ):
            with open(checkpoint_data, "r", encoding="utf-8") as f:
                data = json.load(f)
            instance = WorkflowInstance.from_dict(data)
        elif isinstance(checkpoint_data, str):
            instance = WorkflowInstance.from_json(checkpoint_data)
        else:
            raise TypeError(f"Unsupported checkpoint data type: {type(checkpoint_data)}")

        instance.log_event("CHECKPOINT_LOADED", {"workflow_id": instance.workflow_id})
        self._workflows[instance.workflow_id] = instance
        return instance

    def _save_checkpoint_to_disk(
        self, instance: WorkflowInstance, filepath: Optional[Path] = None
    ) -> str:
        """Internal helper to write checkpoint JSON to disk."""
        if filepath is None and self.storage_dir is not None:
            filepath = self.storage_dir / f"{instance.workflow_id}.json"

        if filepath is not None:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            temp_path: Optional[Path] = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=filepath.parent,
                    prefix=f".{filepath.name}.", suffix=".tmp", delete=False,
                ) as f:
                    temp_path = Path(f.name)
                    f.write(instance.to_json())
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_path, filepath)
            except Exception:
                if temp_path is not None:
                    temp_path.unlink(missing_ok=True)
                raise
            instance.log_event("CHECKPOINT_SAVED", {"filepath": str(filepath)})
            return str(filepath)

        return ""
