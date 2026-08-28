"""OpenWorkflow Core Kernel - Work IR Models, Validation, and YAML Engine.

This module defines the canonical Work Intermediate Representation (Work IR)
specification conforming to `core/work_ir/schema.json`. It provides AST models,
dependency DAG validation, cycle detection, topological sorting, and YAML I/O.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class WorkIRValidationError(ValueError):
    """Raised when Work IR schema or DAG structural invariants are violated."""

    pass


class ExecutorType(str, Enum):
    """Execution tier type according to the 5-tier routing model."""

    CODE = "code"
    RULE = "rule"
    SLM = "slm"
    FRONTIER_LLM = "frontier_llm"
    HUMAN = "human"


class ExecutorDef(BaseModel):
    """Execution strategy configuration for a specific action step."""

    model_config = ConfigDict(extra="allow")

    type: ExecutorType = Field(
        ...,
        description="Executor tier type (code, rule, slm, frontier_llm, human)",
    )
    handler: Optional[str] = Field(
        default=None,
        description="Path or module identifier for deterministic code/rule handlers",
    )
    preferred: Optional[str] = Field(
        default=None,
        description="Preferred model identifier or checkpoint for SLM execution",
    )
    fallback: Optional[List[str]] = Field(
        default=None,
        description="Ordered fallback chain of executor types or models if preferred fails",
    )

    @field_validator("type", mode="before")
    @classmethod
    def _validate_type(cls, v: Any) -> ExecutorType:
        if isinstance(v, ExecutorType):
            return v
        if isinstance(v, str):
            v_lower = v.lower().strip()
            for member in ExecutorType:
                if member.value == v_lower:
                    return member
        raise ValueError(
            f"Invalid executor type: '{v}'. Expected one of: {[e.value for e in ExecutorType]}"
        )


# Alias for backward compatibility
ExecutorConfig = ExecutorDef


class BehaviorRef(BaseModel):
    """Reference to an attached AgentBehavior specification."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(
        ...,
        description="Unique identifier of the behavior contract",
    )
    path: str = Field(
        ...,
        description="Relative file path to BEHAVIOR.md specification",
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional human-readable description of the behavior constraint",
    )


class InvariantDef(BaseModel):
    """Process invariant extracted from approved behavior contracts."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(
        ...,
        description="Identifier of the invariant",
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of what this invariant enforces",
    )
    rule: Optional[str] = Field(
        default=None,
        description="Formal expression, assertion, or SHACL constraint rule",
    )
    behavior_ref: Optional[str] = Field(
        default=None,
        description="Associated behavior contract name",
    )

    @classmethod
    def from_str(cls, name: str) -> InvariantDef:
        """Create InvariantDef from a string name."""
        return cls(name=name)


class EscalationDef(BaseModel):
    """Escalation policies for runtime exceptions and quality drops."""

    model_config = ConfigDict(extra="allow")

    on_error: Optional[str] = Field(
        default=None,
        description="Escalation target on unhandled execution error (e.g., 'fallback_to_frontier_llm')",
    )
    on_quality_drop: Optional[str] = Field(
        default=None,
        description="Escalation target when quality drops below threshold (e.g., 'require_human_review')",
    )
    on_timeout: Optional[str] = Field(
        default=None,
        description="Escalation target on SLA / deadline timeout",
    )


class ActionDef(BaseModel):
    """Comprehensive AST representation of an atomic action in Work IR."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(..., description="Action name identifier")
    description: Optional[str] = Field(default=None, description="Action description")
    prerequisites: List[str] = Field(
        default_factory=list,
        description="Direct prerequisite action dependencies",
    )
    executor: Optional[ExecutorDef] = Field(
        default=None,
        description="Assigned executor configuration",
    )
    invariants: List[str] = Field(
        default_factory=list,
        description="Invariants applicable to this action",
    )


# Type alias for Executors mapping dictionary
ExecutorsDef = Dict[str, ExecutorDef]


class WorkIR(BaseModel):
    """Canonical OpenWorkflow Work IR AST Model.

    Conforms to `core/work_ir/schema.json` and `work.yaml` specifications.
    """

    model_config = ConfigDict(extra="allow")

    work: str = Field(
        ...,
        description="Unique identifier for the compiled work definition",
    )
    version: str = Field(
        default="3.0",
        description="Work IR specification version (e.g., '3.0')",
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of the work",
    )
    inputs: List[str] = Field(
        ...,
        description="Required input parameters for the work",
    )
    outputs: List[str] = Field(
        ...,
        description="Expected output artifacts or schema fields",
    )
    states: List[str] = Field(
        ...,
        description="States defined in the durable runtime state machine",
    )
    actions: List[str] = Field(
        ...,
        description="Atomic action steps executed within the workflow",
    )
    dependencies: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Dependency DAG mapping each action to its required prerequisite actions",
    )
    invariants: List[str] = Field(
        default_factory=list,
        description="Non-removable process invariants extracted from approved behavior contracts",
    )
    quality: Dict[str, str] = Field(
        default_factory=dict,
        description="Outcome quality thresholds (e.g., reviewer_acceptance: '>=0.95')",
    )
    behaviors: Optional[List[BehaviorRef]] = Field(
        default=None,
        description="Behavior Contract BEHAVIOR.md specifications attached to this work",
    )
    escalation: Optional[EscalationDef] = Field(
        default=None,
        description="Escalation rules when execution fails or quality degrades",
    )
    executors: Dict[str, ExecutorDef] = Field(
        ...,
        description="Routing definition for step execution across Code, Rule, SLM, LLM, and Human",
    )

    @field_validator("invariants", mode="before")
    @classmethod
    def _normalize_invariants(cls, v: Any) -> List[str]:
        """Allow list of InvariantDef or strings."""
        if v is None:
            return []
        if isinstance(v, list):
            res = []
            for item in v:
                if isinstance(item, str):
                    res.append(item)
                elif isinstance(item, dict) and "name" in item:
                    res.append(item["name"])
                elif isinstance(item, InvariantDef):
                    res.append(item.name)
                else:
                    res.append(str(item))
            return res
        return [str(v)]

    @model_validator(mode="after")
    def _validate_ast_integrity(self) -> WorkIR:
        """Validate structural consistency, reference integrity, and DAG acyclicity."""
        action_set = set(self.actions)

        # 1. Check dependencies reference existing actions
        for target, prereqs in self.dependencies.items():
            if target not in action_set:
                raise WorkIRValidationError(
                    f"Dependency target action '{target}' is not listed in actions: {self.actions}"
                )
            for prereq in prereqs:
                if prereq not in action_set:
                    raise WorkIRValidationError(
                        f"Prerequisite action '{prereq}' for '{target}' is not listed in actions: {self.actions}"
                    )

        # 2. Check executors reference existing actions
        for action_name in self.executors.keys():
            if action_name not in action_set:
                raise WorkIRValidationError(
                    f"Executor defined for action '{action_name}' which is not listed in actions: {self.actions}"
                )

        # 3. Check DAG cycle detection
        self.topological_sort()

        return self

    def topological_sort(self) -> List[str]:
        """Compute topological ordering of actions based on dependency DAG.

        Raises:
            WorkIRValidationError: If a dependency cycle is detected.

        Returns:
            List of action names in executable topological order.
        """
        # Graph: prereq -> downstream actions
        adj: Dict[str, List[str]] = defaultdict(list)
        in_degree: Dict[str, int] = {action: 0 for action in self.actions}

        for action, prereqs in self.dependencies.items():
            in_degree[action] = len(prereqs)
            for prereq in prereqs:
                adj[prereq].append(action)

        queue = deque([act for act, deg in in_degree.items() if deg == 0])
        ordered: List[str] = []

        while queue:
            curr = queue.popleft()
            ordered.append(curr)
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(ordered) != len(self.actions):
            cycle_nodes = [act for act, deg in in_degree.items() if deg > 0]
            raise WorkIRValidationError(
                f"Cycle detected in Work IR dependency DAG involving actions: {cycle_nodes}"
            )

        return ordered

    def get_action_def(self, action_name: str) -> ActionDef:
        """Construct full ActionDef representation for an action."""
        if action_name not in self.actions:
            raise KeyError(f"Action '{action_name}' not found in Work IR actions")

        prereqs = self.dependencies.get(action_name, [])
        executor = self.executors.get(action_name)
        return ActionDef(
            name=action_name,
            prerequisites=list(prereqs),
            executor=executor,
            invariants=list(self.invariants),
        )

    def get_prerequisites(self, action: str) -> List[str]:
        """Get direct prerequisite actions for given action."""
        return self.dependencies.get(action, [])

    def get_all_prerequisites(self, action: str) -> Set[str]:
        """Get transitive set of prerequisite actions for given action."""
        visited: Set[str] = set()

        def _traverse(act: str) -> None:
            for p in self.dependencies.get(act, []):
                if p not in visited:
                    visited.add(p)
                    _traverse(p)

        _traverse(action)
        return visited

    def get_downstream(self, action: str) -> List[str]:
        """Get direct downstream actions that depend on given action."""
        return [act for act, prereqs in self.dependencies.items() if action in prereqs]

    def to_dict(self) -> Dict[str, Any]:
        """Convert WorkIR instance to dictionary matching schema.json."""
        data = self.model_dump(exclude_none=True)
        # Convert Enum types to string values
        if "executors" in data:
            for act, exec_data in data["executors"].items():
                if isinstance(exec_data.get("type"), ExecutorType):
                    exec_data["type"] = exec_data["type"].value
        return data

    def to_yaml(self) -> str:
        """Serialize WorkIR instance to YAML string."""
        return to_yaml(self)


# ============================================================================
# YAML Serialization / Loading
# ============================================================================


class WorkIRYAMLDumper(yaml.SafeDumper):
    """Custom YAML SafeDumper with clean indentation for sequences and mappings."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        return super().increase_indent(flow=flow, indentless=False)


def to_yaml(work_ir: WorkIR) -> str:
    """Serialize WorkIR instance to formatted YAML string.

    Args:
        work_ir: WorkIR instance to serialize.

    Returns:
        Formatted YAML string.
    """
    raw_dict = work_ir.to_dict()
    return yaml.dump(
        raw_dict,
        Dumper=WorkIRYAMLDumper,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )


def load_work_ir(
    source: Union[str, Path, Dict[str, Any]],
    validate: bool = True,
) -> WorkIR:
    """Load and validate Work IR from YAML/JSON file path, string, or dictionary.

    Args:
        source: File path (str/Path), YAML/JSON string, or dictionary.
        validate: Whether to run validation checks.

    Returns:
        Validated WorkIR instance.
    """
    if isinstance(source, dict):
        data = source
    elif isinstance(source, Path) or (
        isinstance(source, str)
        and ("\n" not in source)
        and (source.endswith(".yaml") or source.endswith(".yml") or source.endswith(".json"))
    ):
        path = Path(source)
        if not path.is_file():
            raise FileNotFoundError(f"Work IR file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            if path.suffix == ".json":
                data = json.load(f)
            else:
                data = yaml.safe_load(f)
    elif isinstance(source, str):
        # Parse from string
        try:
            data = yaml.safe_load(source)
        except yaml.YAMLError:
            data = json.loads(source)
    else:
        raise TypeError(f"Unsupported source type for load_work_ir: {type(source).__name__}")

    if not isinstance(data, dict):
        raise WorkIRValidationError(f"Expected dictionary at root of Work IR, got {type(data).__name__}")

    try:
        work_ir = WorkIR.model_validate(data)
    except Exception as e:
        if isinstance(e, WorkIRValidationError):
            raise
        raise WorkIRValidationError(f"Invalid Work IR structure: {e}") from e

    if validate:
        work_ir.topological_sort()
    return work_ir


def validate_work_ir(source: Union[str, Path, Dict[str, Any], WorkIR]) -> WorkIR:
    """Validate a Work IR source and return the validated WorkIR instance.

    Args:
        source: File path, YAML/JSON string, dictionary, or existing WorkIR.

    Returns:
        Validated WorkIR instance.

    Raises:
        WorkIRValidationError: If any schema, constraint, or DAG rule is violated.
    """
    if isinstance(source, WorkIR):
        source.topological_sort()
        return source
    return load_work_ir(source, validate=True)



def save_work_ir(work_ir: WorkIR, file_path: Union[str, Path]) -> None:
    """Save WorkIR instance to a YAML file.

    Args:
        work_ir: WorkIR instance to save.
        file_path: Output file path.
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml_content = to_yaml(work_ir)
    with open(path, "w", encoding="utf-8") as f:
        f.write(yaml_content)
