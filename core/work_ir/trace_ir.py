"""OpenWorkCompiler Core Kernel - Trace IR Models and Normalization.

This module defines the canonical Trace Intermediate Representation (Trace IR)
used to capture, normalize, and parse execution trajectories from diverse agent
frameworks (OpenWorker, LangGraph, Braintrust, OpenAI, and custom agents).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TraceStatus(str, Enum):
    """Execution status for a trace run."""

    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"


class TokenUsage(BaseModel):
    """Token consumption statistics for a step or run."""

    model_config = ConfigDict(extra="allow")

    prompt_tokens: Optional[int] = Field(default=None, description="Input / prompt token count")
    completion_tokens: Optional[int] = Field(default=None, description="Output / completion token count")
    total_tokens: Optional[int] = Field(default=None, description="Total token count")


class Provenance(BaseModel):
    """Provenance metadata describing agent environment and origin."""

    model_config = ConfigDict(extra="allow")

    agent_version: Optional[str] = Field(default=None, description="Version of the agent or harness")
    model_name: Optional[str] = Field(default=None, description="Base foundation model name")
    environment: Optional[str] = Field(default=None, description="Execution environment (e.g., prod, sandbox)")
    framework: Optional[str] = Field(default=None, description="Agent framework origin name")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary framework-specific metadata")


class TraceStep(BaseModel):
    """Atomic step in an agent execution trajectory."""

    model_config = ConfigDict(extra="allow")

    step_id: str = Field(
        default_factory=lambda: f"step_{uuid.uuid4().hex[:8]}",
        description="Unique identifier for the step",
    )
    actor: str = Field(
        ...,
        description="Executing entity (e.g., 'agent', 'worker', 'user', 'tool', 'system')",
    )
    action: str = Field(
        ...,
        description="Action performed (e.g., 'lookup_contract', 'call_llm', 'write_file')",
    )
    input: Dict[str, Any] = Field(
        default_factory=dict,
        description="Input parameters or payload for the step",
    )
    output: Dict[str, Any] = Field(
        default_factory=dict,
        description="Output payload or return value produced by the step",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp when step began or executed",
    )
    latency_ms: Optional[float] = Field(
        default=None,
        description="Step latency / duration in milliseconds",
    )
    token_usage: Optional[TokenUsage] = Field(
        default=None,
        description="Token usage associated with this step",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if step failed",
    )

    @field_validator("input", "output", mode="before")
    @classmethod
    def _coerce_dict(cls, v: Any) -> Dict[str, Any]:
        """Ensure input/output are dictionaries."""
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        return {"value": v}


class TraceResult(BaseModel):
    """Final outcome summary of the trace execution."""

    model_config = ConfigDict(extra="allow")

    status: TraceStatus = Field(
        ...,
        description="Outcome status: success, failure, or cancelled",
    )
    summary: Optional[str] = Field(
        default=None,
        description="Human-readable summary of the outcome",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error details if the trace ended with failure",
    )
    outputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Final returned outputs or state artifacts",
    )

    @field_validator("status", mode="before")
    @classmethod
    def _validate_status(cls, v: Any) -> TraceStatus:
        if isinstance(v, TraceStatus):
            return v
        if isinstance(v, str):
            v_lower = v.lower().strip()
            if v_lower in {"success", "succeeded", "ok", "passed", "done"}:
                return TraceStatus.SUCCESS
            if v_lower in {"failure", "failed", "error", "errored"}:
                return TraceStatus.FAILURE
            if v_lower in {"cancelled", "canceled", "aborted", "interrupted"}:
                return TraceStatus.CANCELLED
        return TraceStatus.SUCCESS


class TraceIR(BaseModel):
    """Canonical OpenWorkCompiler Trace Intermediate Representation.

    Represents a full execution trajectory conforming to
    `protocols/traces/trace_ir_schema.json`.
    """

    model_config = ConfigDict(extra="allow")

    run_id: str = Field(
        default_factory=lambda: f"run_{uuid.uuid4().hex[:12]}",
        description="Unique run identifier",
    )
    source_agent: str = Field(
        ...,
        description="Agent framework origin ('openworker', 'langgraph', 'braintrust', 'openai', 'custom')",
    )
    start_time: Optional[str] = Field(
        default=None,
        description="ISO 8601 start timestamp",
    )
    end_time: Optional[str] = Field(
        default=None,
        description="ISO 8601 completion timestamp",
    )
    steps: List[TraceStep] = Field(
        default_factory=list,
        description="Sequential list of trace execution steps",
    )
    result: TraceResult = Field(
        ...,
        description="Execution outcome result and status",
    )
    artifacts: List[str] = Field(
        default_factory=list,
        description="List of artifact paths, URIs, or IDs generated during run",
    )
    provenance: Optional[Provenance] = Field(
        default=None,
        description="Provenance and environment metadata",
    )

    def total_latency_ms(self) -> float:
        """Calculate total step latency in milliseconds."""
        return sum(s.latency_ms or 0.0 for s in self.steps)

    def total_tokens(self) -> int:
        """Calculate total tokens consumed across all steps."""
        total = 0
        for s in self.steps:
            if s.token_usage:
                if s.token_usage.total_tokens is not None:
                    total += s.token_usage.total_tokens
                else:
                    total += (s.token_usage.prompt_tokens or 0) + (s.token_usage.completion_tokens or 0)
        return total

    def get_step_by_id(self, step_id: str) -> Optional[TraceStep]:
        """Find a step by its step_id."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def get_steps_by_actor(self, actor: str) -> List[TraceStep]:
        """Filter steps by actor."""
        return [s for s in self.steps if s.actor == actor]

    def get_steps_by_action(self, action: str) -> List[TraceStep]:
        """Filter steps by action name."""
        return [s for s in self.steps if s.action == action]

    def to_json(self, indent: int = 2) -> str:
        """Serialize TraceIR instance to JSON string."""
        return self.model_dump_json(indent=indent)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize TraceIR instance to Python dictionary."""
        return self.model_dump()


# ============================================================================
# Normalization Adapters
# ============================================================================


def normalize_openworker_trace(data: Union[Dict[str, Any], Any]) -> TraceIR:
    """Normalize OpenWorker desktop/local execution traces into canonical TraceIR.

    Handles OpenWorker task logs, action journals, session traces, and desktop tool calls.
    """
    if not isinstance(data, dict):
        raise TypeError(f"Expected dict for OpenWorker trace, got {type(data).__name__}")

    run_id = data.get("run_id") or data.get("task_id") or data.get("session_id") or f"ow_{uuid.uuid4().hex[:8]}"
    start_time = data.get("start_time") or data.get("created_at")
    end_time = data.get("end_time") or data.get("completed_at")

    raw_steps = data.get("steps") or data.get("actions") or data.get("events") or []
    normalized_steps: List[TraceStep] = []

    for i, s in enumerate(raw_steps):
        if not isinstance(s, dict):
            continue
        step_id = s.get("step_id") or s.get("action_id") or s.get("id") or f"ow_step_{i+1}"
        actor = s.get("actor") or s.get("worker_id") or "openworker"
        action = s.get("action") or s.get("tool_name") or s.get("command") or s.get("name") or "execute"
        
        # Extract inputs and outputs
        inp = s.get("input") or s.get("args") or s.get("params") or s.get("parameters") or {}
        out = s.get("output") or s.get("result") or s.get("response") or {}

        # Latency & tokens
        latency_ms = s.get("latency_ms")
        if latency_ms is None and s.get("duration_seconds") is not None:
            latency_ms = float(s["duration_seconds"]) * 1000.0
        elif latency_ms is None and s.get("duration_ms") is not None:
            latency_ms = float(s["duration_ms"])

        tokens_data = s.get("token_usage") or s.get("tokens")
        token_usage = TokenUsage(**tokens_data) if isinstance(tokens_data, dict) else None

        timestamp = s.get("timestamp") or s.get("created_at") or datetime.now(timezone.utc).isoformat()

        normalized_steps.append(
            TraceStep(
                step_id=str(step_id),
                actor=str(actor),
                action=str(action),
                input=inp if isinstance(inp, dict) else {"raw": inp},
                output=out if isinstance(out, dict) else {"raw": out},
                timestamp=str(timestamp),
                latency_ms=latency_ms,
                token_usage=token_usage,
                error=s.get("error"),
            )
        )

    # Result normalization
    raw_result = data.get("result")
    if isinstance(raw_result, dict):
        status_val = raw_result.get("status", "success")
        summary = raw_result.get("summary") or raw_result.get("message")
        error = raw_result.get("error")
        outputs = raw_result.get("outputs") or raw_result.get("data") or {}
    else:
        status_val = data.get("status") or "success"
        summary = data.get("summary") or data.get("message")
        error = data.get("error")
        outputs = data.get("outputs") or data.get("data") or {}

    result = TraceResult(
        status=status_val,
        summary=summary,
        error=error,
        outputs=outputs if isinstance(outputs, dict) else {"value": outputs},
    )

    artifacts = data.get("artifacts") or data.get("files") or []
    if isinstance(artifacts, dict):
        artifacts = list(artifacts.values())

    provenance_data = data.get("provenance") or {
        "agent_version": data.get("version"),
        "model_name": data.get("model"),
        "environment": data.get("environment", "desktop"),
        "framework": "openworker",
    }
    provenance = Provenance(**provenance_data) if isinstance(provenance_data, dict) else None

    return TraceIR(
        run_id=str(run_id),
        source_agent="openworker",
        start_time=str(start_time) if start_time else None,
        end_time=str(end_time) if end_time else None,
        steps=normalized_steps,
        result=result,
        artifacts=[str(a) for a in artifacts],
        provenance=provenance,
    )


def normalize_langgraph_trace(data: Union[Dict[str, Any], Any]) -> TraceIR:
    """Normalize LangGraph state graphs and run trajectories into canonical TraceIR.

    Handles node transitions, tool executions, graph state updates, and LangChain Run specs.
    """
    if not isinstance(data, dict):
        raise TypeError(f"Expected dict for LangGraph trace, got {type(data).__name__}")

    run_id = data.get("run_id") or data.get("id") or f"lg_{uuid.uuid4().hex[:8]}"
    start_time = data.get("start_time") or data.get("start")
    end_time = data.get("end_time") or data.get("end")

    normalized_steps: List[TraceStep] = []

    # Case 1: Standard LangGraph / LangChain child_runs or steps
    raw_steps = data.get("steps") or data.get("child_runs") or data.get("nodes") or data.get("events") or []
    
    # Case 2: Intermediate steps list
    if not raw_steps and "intermediate_steps" in data:
        raw_steps = data["intermediate_steps"]

    for i, s in enumerate(raw_steps):
        if not isinstance(s, dict):
            continue
        step_id = s.get("id") or s.get("step_id") or s.get("name") or f"lg_step_{i+1}"
        actor = s.get("actor") or s.get("node") or s.get("name") or "langgraph_node"
        action = s.get("action") or s.get("run_type") or s.get("node") or "node_execution"

        inp = s.get("inputs") or s.get("input") or s.get("state_in") or {}
        out = s.get("outputs") or s.get("output") or s.get("state_out") or {}

        latency_ms = s.get("latency_ms")
        if latency_ms is None and s.get("start_time") and s.get("end_time"):
            try:
                t0 = datetime.fromisoformat(str(s["start_time"]))
                t1 = datetime.fromisoformat(str(s["end_time"]))
                latency_ms = (t1 - t0).total_seconds() * 1000.0
            except Exception:
                pass

        # Extract token usage if available in LangChain / LangGraph run format
        token_usage = None
        extra = s.get("extra") or {}
        if isinstance(extra, dict) and "token_usage" in extra:
            token_usage = TokenUsage(**extra["token_usage"])
        elif "token_usage" in s and isinstance(s["token_usage"], dict):
            token_usage = TokenUsage(**s["token_usage"])

        timestamp = s.get("start_time") or s.get("timestamp") or datetime.now(timezone.utc).isoformat()

        normalized_steps.append(
            TraceStep(
                step_id=str(step_id),
                actor=str(actor),
                action=str(action),
                input=inp if isinstance(inp, dict) else {"data": inp},
                output=out if isinstance(out, dict) else {"data": out},
                timestamp=str(timestamp),
                latency_ms=latency_ms,
                token_usage=token_usage,
                error=s.get("error"),
            )
        )

    # Result extraction
    err = data.get("error")
    raw_status = data.get("status") or ("failure" if err else "success")
    summary = data.get("summary") or data.get("name")
    outputs = data.get("outputs") or data.get("output") or data.get("final_state") or {}

    result = TraceResult(
        status=raw_status,
        summary=str(summary) if summary else None,
        error=str(err) if err else None,
        outputs=outputs if isinstance(outputs, dict) else {"result": outputs},
    )

    artifacts = data.get("artifacts") or []
    provenance_data = data.get("provenance") or {
        "agent_version": data.get("graph_version") or data.get("version"),
        "model_name": data.get("model_name"),
        "environment": data.get("environment", "langgraph"),
        "framework": "langgraph",
    }
    provenance = Provenance(**provenance_data) if isinstance(provenance_data, dict) else None

    return TraceIR(
        run_id=str(run_id),
        source_agent="langgraph",
        start_time=str(start_time) if start_time else None,
        end_time=str(end_time) if end_time else None,
        steps=normalized_steps,
        result=result,
        artifacts=[str(a) for a in artifacts],
        provenance=provenance,
    )


def normalize_custom_agent_trace(
    data: Union[Dict[str, Any], Any],
    source_agent: str = "custom",
) -> TraceIR:
    """Normalize arbitrary custom agent trajectories, message logs, and tool calls into canonical TraceIR."""
    if not isinstance(data, dict):
        raise TypeError(f"Expected dict for custom agent trace, got {type(data).__name__}")

    run_id = data.get("run_id") or data.get("id") or data.get("trace_id") or f"trace_{uuid.uuid4().hex[:8]}"
    start_time = data.get("start_time") or data.get("started_at")
    end_time = data.get("end_time") or data.get("ended_at") or data.get("completed_at")

    raw_steps = (
        data.get("steps")
        or data.get("trajectory")
        or data.get("history")
        or data.get("messages")
        or data.get("actions")
        or []
    )

    normalized_steps: List[TraceStep] = []
    for i, s in enumerate(raw_steps):
        if not isinstance(s, dict):
            # If item is string or raw object
            s = {"content": s}

        step_id = s.get("step_id") or s.get("id") or f"step_{i+1}"
        actor = s.get("actor") or s.get("role") or s.get("source") or "agent"
        action = (
            s.get("action")
            or s.get("type")
            or s.get("tool")
            or s.get("name")
            or s.get("function")
            or "message"
        )

        inp = s.get("input") or s.get("args") or s.get("arguments") or s.get("prompt") or {}
        out = s.get("output") or s.get("response") or s.get("content") or s.get("result") or {}

        latency_ms = s.get("latency_ms") or s.get("duration_ms")
        tokens_data = s.get("token_usage") or s.get("tokens") or s.get("usage")
        token_usage = TokenUsage(**tokens_data) if isinstance(tokens_data, dict) else None

        timestamp = s.get("timestamp") or s.get("time") or datetime.now(timezone.utc).isoformat()

        normalized_steps.append(
            TraceStep(
                step_id=str(step_id),
                actor=str(actor),
                action=str(action),
                input=inp if isinstance(inp, dict) else {"value": inp},
                output=out if isinstance(out, dict) else {"value": out},
                timestamp=str(timestamp),
                latency_ms=float(latency_ms) if latency_ms is not None else None,
                token_usage=token_usage,
                error=s.get("error"),
            )
        )

    # Outcome result
    raw_result = data.get("result")
    if isinstance(raw_result, dict):
        status_val = raw_result.get("status", "success")
        summary = raw_result.get("summary")
        error = raw_result.get("error")
        outputs = raw_result.get("outputs") or {}
    else:
        status_val = data.get("status") or ("failure" if data.get("error") else "success")
        summary = data.get("summary") or data.get("description")
        error = data.get("error")
        outputs = data.get("outputs") or data.get("output") or {}

    result = TraceResult(
        status=status_val,
        summary=str(summary) if summary else None,
        error=str(error) if error else None,
        outputs=outputs if isinstance(outputs, dict) else {"result": outputs},
    )

    artifacts = data.get("artifacts") or []
    provenance_data = data.get("provenance") or {
        "agent_version": data.get("version"),
        "model_name": data.get("model"),
        "environment": data.get("environment", "custom"),
        "framework": source_agent,
    }
    provenance = Provenance(**provenance_data) if isinstance(provenance_data, dict) else None

    return TraceIR(
        run_id=str(run_id),
        source_agent=data.get("source_agent") or source_agent,
        start_time=str(start_time) if start_time else None,
        end_time=str(end_time) if end_time else None,
        steps=normalized_steps,
        result=result,
        artifacts=[str(a) for a in artifacts],
        provenance=provenance,
    )


def normalize_trace(
    data: Union[Dict[str, Any], Any],
    source_hint: Optional[str] = None,
) -> TraceIR:
    """Auto-detect trace format and normalize into canonical TraceIR.

    Inspects metadata, source_agent fields, and key structural heuristics to route
    to the matching normalizer.
    """
    if not isinstance(data, dict):
        raise TypeError(f"Trace data must be a dictionary, got {type(data).__name__}")

    # Check if already canonical TraceIR
    if (
        "run_id" in data
        and "source_agent" in data
        and "steps" in data
        and "result" in data
        and isinstance(data.get("result"), dict)
        and "status" in data["result"]
    ):
        return TraceIR.model_validate(data)

    # Determine framework source
    src = (
        source_hint
        or data.get("source_agent")
        or data.get("framework")
        or data.get("source")
        or ""
    ).lower()

    if src in {"openworker", "open_worker", "worker"}:
        return normalize_openworker_trace(data)
    elif src in {"langgraph", "langchain", "graph"}:
        return normalize_langgraph_trace(data)
    elif src in {"custom", "agent", "braintrust", "openai"}:
        return normalize_custom_agent_trace(data, source_agent=src or "custom")

    # Structural heuristics
    if "worker_id" in data or any("worker_id" in s for s in data.get("steps", []) if isinstance(s, dict)):
        return normalize_openworker_trace(data)
    if "child_runs" in data or "intermediate_steps" in data or "graph_id" in data:
        return normalize_langgraph_trace(data)

    return normalize_custom_agent_trace(data, source_agent=src or "custom")


def parse_trace_from_json(
    json_str: Union[str, Path],
    source_hint: Optional[str] = None,
) -> TraceIR:
    """Parse TraceIR from a JSON string or file path.

    Args:
        json_str: Raw JSON string or file path to JSON file.
        source_hint: Optional hint for framework ('openworker', 'langgraph', 'custom', etc.).

    Returns:
        Validated canonical TraceIR instance.
    """
    if isinstance(json_str, Path) or (isinstance(json_str, str) and (json_str.endswith(".json") and "\n" not in json_str)):
        path = Path(json_str)
        if path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return normalize_trace(data, source_hint=source_hint)

    data = json.loads(json_str)
    return normalize_trace(data, source_hint=source_hint)
