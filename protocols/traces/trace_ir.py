"""Trace IR data models and serialization.

Implements the OpenWorkCompiler Trace/Eval Protocol contract for representing
raw or normalized agent trajectories across diverse agent frameworks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class TraceStep:
    """Represents a single atomic execution step within an agent trajectory."""

    actor: str
    action: str
    timestamp: str
    step_id: Optional[str] = None
    input: Dict[str, Any] = field(default_factory=dict)
    output: Dict[str, Any] = field(default_factory=dict)
    latency_ms: Optional[float] = None
    token_usage: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TraceStep:
        """Create a TraceStep from a dictionary."""
        return cls(
            actor=data.get("actor", "agent"),
            action=data.get("action", ""),
            timestamp=data.get("timestamp", ""),
            step_id=data.get("step_id"),
            input=data.get("input") or {},
            output=data.get("output") or {},
            latency_ms=data.get("latency_ms"),
            token_usage=data.get("token_usage"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert TraceStep to dictionary."""
        res: Dict[str, Any] = {
            "actor": self.actor,
            "action": self.action,
            "timestamp": self.timestamp,
        }
        if self.step_id is not None:
            res["step_id"] = self.step_id
        if self.input:
            res["input"] = self.input
        if self.output:
            res["output"] = self.output
        if self.latency_ms is not None:
            res["latency_ms"] = self.latency_ms
        if self.token_usage is not None:
            res["token_usage"] = self.token_usage
        return res


@dataclass
class TraceResult:
    """Outcome status and summary of an execution trace."""

    status: str  # 'success' | 'failure' | 'cancelled'
    summary: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TraceResult:
        """Create a TraceResult from a dictionary."""
        return cls(
            status=data.get("status", "success"),
            summary=data.get("summary"),
            error=data.get("error"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert TraceResult to dictionary."""
        res: Dict[str, Any] = {"status": self.status}
        if self.summary is not None:
            res["summary"] = self.summary
        if self.error is not None:
            res["error"] = self.error
        return res


@dataclass
class TraceIR:
    """OpenWorkCompiler Trace IR data model.

    Represents a full recorded run trajectory from a frontier or local agent.
    """

    run_id: str
    source_agent: str
    steps: List[TraceStep]
    result: TraceResult
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TraceIR:
        """Create TraceIR from dictionary."""
        raw_steps = data.get("steps", [])
        steps = [TraceStep.from_dict(s) if isinstance(s, dict) else s for s in raw_steps]

        raw_result = data.get("result", {})
        if isinstance(raw_result, dict):
            result = TraceResult.from_dict(raw_result)
        elif isinstance(raw_result, TraceResult):
            result = raw_result
        else:
            result = TraceResult(status="success")

        return cls(
            run_id=data.get("run_id", ""),
            source_agent=data.get("source_agent", "custom"),
            steps=steps,
            result=result,
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            artifacts=list(data.get("artifacts", [])),
            provenance=dict(data.get("provenance", {})),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert TraceIR to dictionary."""
        res: Dict[str, Any] = {
            "run_id": self.run_id,
            "source_agent": self.source_agent,
            "steps": [s.to_dict() for s in self.steps],
            "result": self.result.to_dict(),
            "artifacts": self.artifacts,
            "provenance": self.provenance,
        }
        if self.start_time is not None:
            res["start_time"] = self.start_time
        if self.end_time is not None:
            res["end_time"] = self.end_time
        return res

    @classmethod
    def load_json(cls, path: str | Path) -> TraceIR:
        """Load TraceIR from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
