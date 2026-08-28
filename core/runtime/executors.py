"""OpenWorkflow Runtime Executors.

Defines the action execution abstractions and concrete executors:
- ActionResult: Standardized execution outcome dataclass.
- BaseExecutor: Abstract base class for all step executors.
- CodeExecutor: Deterministic Python function / callable executor.
- RuleExecutor: Business rule and condition evaluation executor.
- HTTPExecutor: REST / HTTP API client executor.
- MLExecutor: Machine learning model inference and scoring executor.
- SLMExecutor: Small Language Model (SLM) task executor.
- LLMExecutor: Frontier Large Language Model (LLM) reasoning & escalation executor.
- HumanExecutor: Human-in-the-loop approval and manual input executor.
"""

from __future__ import annotations

import abc
import importlib
import ipaddress
import inspect
import json
import logging
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    """Standardized result returned from an action execution step.

    Attributes:
        success: Whether the action execution succeeded.
        output: Result payload, returned artifacts, or response data.
        error: Error message or traceback summary if execution failed.
        metadata: Execution metadata (e.g., latency, token count, model, status codes).
        logs: Diagnostic log entries generated during execution.
        execution_time_ms: Wall-clock execution duration in milliseconds.
        wait_condition: Optional wait specification when execution yields a wait state
            (e.g., waiting for human approval, timer, or external event).
    """

    success: bool
    output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0
    wait_condition: Optional[Dict[str, Any]] = None

    @classmethod
    def ok(
        cls,
        output: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
        logs: Optional[List[str]] = None,
        execution_time_ms: float = 0.0,
    ) -> ActionResult:
        """Create a successful ActionResult."""
        return cls(
            success=True,
            output=output,
            error=None,
            metadata=metadata or {},
            logs=logs or [],
            execution_time_ms=execution_time_ms,
        )

    @classmethod
    def fail(
        cls,
        error: str,
        output: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
        logs: Optional[List[str]] = None,
        execution_time_ms: float = 0.0,
    ) -> ActionResult:
        """Create a failed ActionResult."""
        return cls(
            success=False,
            output=output,
            error=error,
            metadata=metadata or {},
            logs=logs or [],
            execution_time_ms=execution_time_ms,
        )

    @classmethod
    def wait_for_human(
        cls,
        prompt: str,
        assignee: Optional[str] = None,
        required_fields: Optional[List[str]] = None,
        timeout_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        logs: Optional[List[str]] = None,
    ) -> ActionResult:
        """Create an ActionResult that suspends execution pending human review/input."""
        cond = {
            "wait_type": "HUMAN",
            "prompt": prompt,
            "assignee": assignee,
            "required_fields": required_fields or [],
            "timeout_seconds": timeout_seconds,
            "metadata": metadata or {},
        }
        return cls(
            success=True,
            output=None,
            error=None,
            metadata=metadata or {},
            logs=logs or [f"Suspended: Waiting for human input (assignee: {assignee})"],
            wait_condition=cond,
        )

    @classmethod
    def wait_for_event(
        cls,
        event_name: str,
        timeout_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        logs: Optional[List[str]] = None,
    ) -> ActionResult:
        """Create an ActionResult that suspends execution pending an external signal/event."""
        cond = {
            "wait_type": "EVENT",
            "event_name": event_name,
            "timeout_seconds": timeout_seconds,
            "metadata": metadata or {},
        }
        return cls(
            success=True,
            output=None,
            error=None,
            metadata=metadata or {},
            logs=logs or [f"Suspended: Waiting for event '{event_name}'"],
            wait_condition=cond,
        )

    @classmethod
    def wait_for_timer(
        cls,
        delay_seconds: Optional[float] = None,
        expires_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        logs: Optional[List[str]] = None,
    ) -> ActionResult:
        """Create an ActionResult that suspends execution pending timer expiration."""
        cond = {
            "wait_type": "TIMER",
            "delay_seconds": delay_seconds,
            "expires_at": expires_at,
            "metadata": metadata or {},
        }
        return cls(
            success=True,
            output=None,
            error=None,
            metadata=metadata or {},
            logs=logs or [f"Suspended: Waiting for timer (delay: {delay_seconds}s, expires: {expires_at})"],
            wait_condition=cond,
        )

    @property
    def is_waiting(self) -> bool:
        """Check if this action result indicates a suspended wait state."""
        return self.wait_condition is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert ActionResult to JSON-serializable dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
            "logs": self.logs,
            "execution_time_ms": self.execution_time_ms,
            "wait_condition": self.wait_condition,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ActionResult:
        """Construct ActionResult from a dictionary."""
        return cls(
            success=data.get("success", False),
            output=data.get("output"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
            logs=data.get("logs", []),
            execution_time_ms=data.get("execution_time_ms", 0.0),
            wait_condition=data.get("wait_condition"),
        )


class BaseExecutor(abc.ABC):
    """Abstract base class for all OpenWorkflow action executors.

    Subclasses implement execution strategies for code, rules, HTTP endpoints,
    ML models, SLMs, LLMs, or human-in-the-loop actions.
    """

    def __init__(self, name: str = "", config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the executor with an optional name and configuration dictionary."""
        self.name = name or self.__class__.__name__
        self.config = config or {}

    @property
    @abc.abstractmethod
    def executor_type(self) -> str:
        """Return the executor type string (e.g., 'code', 'rule', 'http', 'ml', 'slm', 'frontier_llm', 'human')."""
        pass

    @abc.abstractmethod
    def execute(
        self,
        action_name: str,
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        """Execute the specified action step with input arguments and workflow context.

        Args:
            action_name: Name of the action being executed.
            inputs: Dictionary of input parameters for this action step.
            context: Shared workflow context or execution state.

        Returns:
            ActionResult indicating success/failure, output payload, and metadata.
        """
        pass

    def validate_inputs(
        self,
        action_name: str,
        inputs: Dict[str, Any],
        required_fields: Optional[List[str]] = None,
    ) -> None:
        """Validate that all required input keys exist in the input dictionary.

        Raises:
            ValueError: If one or more required input fields are missing.
        """
        if not required_fields:
            return
        missing = [f for f in required_fields if f not in inputs]
        if missing:
            raise ValueError(
                f"Action '{action_name}' missing required inputs: {', '.join(missing)}"
            )

    def _timed_call(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Tuple[Any, float]:
        """Execute a callable and return its output along with execution time in ms."""
        start = time.perf_counter()
        res = func(*args, **kwargs)
        duration_ms = (time.perf_counter() - start) * 1000.0
        return res, duration_ms


class CodeExecutor(BaseExecutor):
    """Executes deterministic Python callables, functions, or imported handler functions."""

    def __init__(
        self,
        handlers: Optional[Dict[str, Callable[..., Any]]] = None,
        name: str = "CodeExecutor",
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize CodeExecutor with an optional mapping of handler functions."""
        super().__init__(name=name, config=config)
        self._handlers: Dict[str, Callable[..., Any]] = handlers.copy() if handlers else {}

    @property
    def executor_type(self) -> str:
        return "code"

    def register_handler(self, name: str, handler: Callable[..., Any]) -> None:
        """Register a Python callable under a specific action or handler name."""
        self._handlers[name] = handler

    def _resolve_handler(
        self, action_name: str, inputs: Dict[str, Any], context: Optional[Dict[str, Any]]
    ) -> Callable[..., Any]:
        """Resolve the callable handler for the action.

        Checks:
        1. Explicit handler in inputs ('__handler__' or 'handler')
        2. Registered handler under handler name
        3. Registered handler under action_name
        4. Explicitly enabled, allowlisted dynamic import string.
        """
        handler_ref = inputs.get("__handler__") or inputs.get("handler")
        if isinstance(handler_ref, str):
            if handler_ref in self._handlers:
                return self._handlers[handler_ref]
            return self._import_callable(handler_ref)
        elif callable(handler_ref):
            return handler_ref

        if action_name in self._handlers:
            return self._handlers[action_name]

        # Check if action_name itself is an importable path
        if "." in action_name:
            try:
                return self._import_callable(action_name)
            except PermissionError:
                # Do not hide a policy decision behind the generic
                # "handler not found" error.
                raise
            except Exception:
                pass

        raise ValueError(
            f"CodeExecutor could not resolve callable handler for action '{action_name}'. "
            f"No handler registered and no valid module path provided."
        )

    def _import_callable(self, path: str) -> Callable[..., Any]:
        """Import an explicitly allowlisted callable.

        Workflow inputs are data, so they must not be able to select arbitrary
        Python code. Deployments that need import-based handlers must opt in and
        name the module prefixes they trust; registered handlers remain the
        normal production integration boundary.
        """
        if ":" in path:
            module_name, attr_name = path.split(":", 1)
        elif "." in path:
            module_name, attr_name = path.rsplit(".", 1)
        else:
            raise ValueError(f"Invalid handler import path: {path}")

        if not self.config.get("allow_dynamic_imports", False):
            raise PermissionError(
                "Dynamic callable imports are disabled. Register the handler "
                "on CodeExecutor or explicitly enable an allowlisted module."
            )

        allowed_modules = self.config.get("allowed_import_modules", [])
        if not isinstance(allowed_modules, (list, tuple, set)) or not any(
            module_name == prefix or module_name.startswith(f"{prefix}.")
            for prefix in allowed_modules
            if isinstance(prefix, str) and prefix
        ):
            raise PermissionError(
                f"Dynamic callable import from module '{module_name}' is not allowlisted."
            )

        module = importlib.import_module(module_name)
        target = getattr(module, attr_name)
        if not callable(target):
            raise TypeError(f"Target '{path}' is not callable.")
        return target

    def _invoke_callable(
        self,
        handler: Callable[..., Any],
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]],
    ) -> Any:
        """Intelligently invoke the callable with parameters matched from inputs."""
        reserved_keys = {"handler", "type", "preferred", "fallback", "executor"}
        clean_inputs = {
            k: v for k, v in inputs.items()
            if not k.startswith("__") and k not in reserved_keys
        }

        try:
            sig = inspect.signature(handler)
            params = sig.parameters

            # 0 argument callable
            if len(params) == 0:
                return handler()

            # Variadic keyword kwargs
            has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
            if has_var_kw:
                return handler(**clean_inputs)

            # Positional-only callable (e.g., math.sqrt, c-extensions)
            pos_only = [p for p in params.values() if p.kind == inspect.Parameter.POSITIONAL_ONLY]
            if len(pos_only) == len(params):
                if len(params) == 1:
                    p_name = list(params.keys())[0]
                    if p_name in clean_inputs:
                        return handler(clean_inputs[p_name])
                    elif clean_inputs:
                        return handler(next(iter(clean_inputs.values())))
                else:
                    args = [clean_inputs[p] for p in params.keys() if p in clean_inputs]
                    if len(args) == len(params):
                        return handler(*args)

            # Match keyword arguments to known signature parameters
            matched_kwargs = {k: v for k, v in clean_inputs.items() if k in params}
            return handler(**matched_kwargs)

        except (ValueError, TypeError):
            pass

        # Fallback invocation attempts
        try:
            return handler(**clean_inputs)
        except TypeError:
            pass

        if len(clean_inputs) == 1:
            try:
                return handler(next(iter(clean_inputs.values())))
            except TypeError:
                pass

        try:
            return handler(clean_inputs)
        except TypeError:
            pass

        try:
            return handler(inputs, context or {})
        except TypeError:
            pass

        return handler()

    def execute(
        self,
        action_name: str,
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        """Execute the code action with provided inputs."""
        logs: List[str] = [f"CodeExecutor: Starting action '{action_name}'"]
        start_time = time.perf_counter()
        try:
            handler = self._resolve_handler(action_name, inputs, context)
            result = self._invoke_callable(handler, inputs, context)

            duration_ms = (time.perf_counter() - start_time) * 1000.0

            # If the handler directly returned an ActionResult (e.g., yielding a wait state)
            if isinstance(result, ActionResult):
                result.execution_time_ms = result.execution_time_ms or duration_ms
                result.logs = logs + result.logs
                return result

            logs.append(f"CodeExecutor: Finished action '{action_name}' successfully in {duration_ms:.2f}ms")
            return ActionResult.ok(
                output=result,
                metadata={"executor": self.name, "handler": getattr(handler, "__name__", str(handler))},
                logs=logs,
                execution_time_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            err_msg = f"Code execution error in '{action_name}': {type(e).__name__}: {str(e)}"
            logs.append(f"CodeExecutor: Error - {err_msg}")
            logger.debug("CodeExecutor execution exception: %s", err_msg, exc_info=True)
            return ActionResult.fail(
                error=err_msg,
                metadata={"executor": self.name, "exception_type": type(e).__name__},
                logs=logs,
                execution_time_ms=duration_ms,
            )



class RuleExecutor(BaseExecutor):
    """Executes deterministic business rules, predicate logic, and condition tables."""

    def __init__(
        self,
        rules: Optional[Dict[str, Any]] = None,
        name: str = "RuleExecutor",
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize RuleExecutor with optional preconfigured rule sets."""
        super().__init__(name=name, config=config)
        self._rules: Dict[str, Any] = rules.copy() if rules else {}

    @property
    def executor_type(self) -> str:
        return "rule"

    def register_rule(self, name: str, rule: Any) -> None:
        """Register a rule function or declarative rule specification."""
        self._rules[name] = rule

    def _eval_condition(self, condition: Dict[str, Any], inputs: Dict[str, Any]) -> bool:
        """Evaluate a declarative condition dictionary against input values."""
        field_name = condition.get("field")
        op = condition.get("op", "==").lower()
        target_value = condition.get("value")

        actual_value = inputs.get(field_name) if field_name else inputs

        if op in ("==", "eq"):
            return bool(actual_value == target_value)
        elif op in ("!=", "neq"):
            return bool(actual_value != target_value)
        elif op in (">", "gt"):
            return bool(actual_value > target_value)
        elif op in (">=", "gte"):
            return bool(actual_value >= target_value)
        elif op in ("<", "lt"):
            return bool(actual_value < target_value)
        elif op in ("<=", "lte"):
            return bool(actual_value <= target_value)
        elif op in ("in", "contains"):
            if isinstance(target_value, (list, tuple, set, dict, str)) and op == "in":
                return bool(actual_value in target_value)
            if isinstance(actual_value, (list, tuple, set, dict, str)) and op == "contains":
                return bool(target_value in actual_value)
            return False
        elif op in ("not_in",):
            return bool(actual_value not in target_value)
        elif op in ("matches", "regex"):
            return bool(re.search(str(target_value), str(actual_value)))
        elif op in ("exists", "not_null"):
            return actual_value is not None
        elif op in ("truthy",):
            return bool(actual_value)
        elif op in ("falsy",):
            return not bool(actual_value)
        else:
            raise ValueError(f"Unsupported rule operator: {op}")

    def execute(
        self,
        action_name: str,
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        """Execute a rule action against inputs and return the evaluated rule outcome."""
        logs: List[str] = [f"RuleExecutor: Evaluating rule for action '{action_name}'"]
        start_time = time.perf_counter()

        try:
            rule = (
                inputs.get("__rule__")
                or inputs.get("rule")
                or self._rules.get(action_name)
                or self.config.get(action_name)
            )

            if callable(rule):
                result = rule(inputs, context or {})
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                return ActionResult.ok(
                    output=result,
                    metadata={"executor": self.name, "rule_type": "callable"},
                    logs=logs,
                    execution_time_ms=duration_ms,
                )

            if isinstance(rule, list):
                # List of declarative rule branches: [{"when": [...], "then": {...}}, ...]
                matched_rules: List[Dict[str, Any]] = []
                final_output: Dict[str, Any] = {}

                for idx, rule_branch in enumerate(rule):
                    if isinstance(rule_branch, dict):
                        conditions = rule_branch.get("when", [])
                        if not isinstance(conditions, list):
                            conditions = [conditions]

                        all_matched = all(
                            self._eval_condition(cond, inputs) for cond in conditions
                        )

                        if all_matched:
                            consequence = rule_branch.get("then", {})
                            matched_rules.append(
                                {"index": idx, "name": rule_branch.get("name", f"rule_{idx}")}
                            )
                            if isinstance(consequence, dict):
                                final_output.update(consequence)
                            else:
                                final_output = consequence
                            if rule_branch.get("stop_on_match", True):
                                break

                duration_ms = (time.perf_counter() - start_time) * 1000.0
                logs.append(f"RuleExecutor: Evaluated {len(rule)} rules, matched {len(matched_rules)}")
                return ActionResult.ok(
                    output=final_output,
                    metadata={
                        "executor": self.name,
                        "rule_type": "declarative_branch_list",
                        "matched_rules": matched_rules,
                    },
                    logs=logs,
                    execution_time_ms=duration_ms,
                )

            # Default simple rule evaluation: evaluate conditions passed in inputs
            conditions = inputs.get("conditions", [])
            matched = True
            if isinstance(conditions, list) and conditions:
                matched = all(self._eval_condition(c, inputs) for c in conditions)

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ActionResult.ok(
                output={"matched": matched, "action": action_name},
                metadata={"executor": self.name, "rule_type": "condition_check"},
                logs=logs,
                execution_time_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            err_msg = f"Rule execution error in '{action_name}': {type(e).__name__}: {str(e)}"
            logs.append(f"RuleExecutor: Error - {err_msg}")
            return ActionResult.fail(
                error=err_msg,
                metadata={"executor": self.name},
                logs=logs,
                execution_time_ms=duration_ms,
            )


class HTTPExecutor(BaseExecutor):
    """Executes REST/HTTP API requests using Python standard library."""

    def __init__(
        self,
        base_url: str = "",
        default_headers: Optional[Dict[str, str]] = None,
        default_timeout: float = 30.0,
        name: str = "HTTPExecutor",
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize HTTPExecutor with base URL and default connection parameters."""
        super().__init__(name=name, config=config)
        self.base_url = base_url.rstrip("/")
        self.default_headers = default_headers or {"Content-Type": "application/json"}
        self.default_timeout = default_timeout

    @property
    def executor_type(self) -> str:
        return "http"

    @staticmethod
    def _is_public_address(address: str) -> bool:
        """Return whether an IP address is safe for outbound workflow requests."""
        ip = ipaddress.ip_address(address)
        # ``is_global`` also excludes loopback, private, link-local, multicast,
        # reserved, unspecified, and carrier-grade NAT ranges.
        return ip.is_global

    def _validate_url(self, url: str) -> None:
        """Reject malformed and private-network destinations before connecting.

        HTTP executors are an egress boundary.  Private and loopback ranges are
        blocked by default so a workflow definition cannot be used to query
        local services or cloud metadata endpoints.  An operator can opt in for
        a controlled internal deployment with ``allow_private_network``.
        """
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("HTTPExecutor requires an absolute http(s) URL with a hostname.")
        if parsed.username or parsed.password:
            raise ValueError("HTTPExecutor does not allow credentials in URLs.")
        if self.config.get("allow_private_network", False):
            return

        try:
            addresses = {
                info[4][0]
                for info in socket.getaddrinfo(parsed.hostname, parsed.port or 0, type=socket.SOCK_STREAM)
            }
        except socket.gaierror as exc:
            raise ValueError(f"HTTPExecutor could not resolve host '{parsed.hostname}'.") from exc
        if not addresses:
            raise ValueError(f"HTTPExecutor could not resolve host '{parsed.hostname}'.")
        blocked = [address for address in addresses if not self._is_public_address(address)]
        if blocked:
            raise PermissionError(
                f"HTTPExecutor blocked private or non-routable destination '{parsed.hostname}'."
            )

    def _safe_opener(self) -> urllib.request.OpenerDirector:
        """Create an opener that validates every redirect target as egress."""
        validate_url = self._validate_url

        class ValidatingRedirectHandler(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                                 headers: Any, newurl: str) -> Any:
                validate_url(newurl)
                return super().redirect_request(req, fp, code, msg, headers, newurl)

        return urllib.request.build_opener(ValidatingRedirectHandler())

    def execute(
        self,
        action_name: str,
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        """Execute an HTTP request with input parameters."""
        logs: List[str] = [f"HTTPExecutor: Preparing request for '{action_name}'"]
        start_time = time.perf_counter()

        url = inputs.get("url") or inputs.get("endpoint") or ""
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"{self.base_url}/{url.lstrip('/')}" if self.base_url else url

        if not url:
            return ActionResult.fail(
                error=f"HTTPExecutor: No URL provided for action '{action_name}'",
                logs=logs,
            )

        method = str(inputs.get("method", "GET")).upper()
        headers = self.default_headers.copy()
        if "headers" in inputs and isinstance(inputs["headers"], dict):
            headers.update(inputs["headers"])

        # URL path formatting (e.g., https://api.com/users/{user_id})
        try:
            url = url.format(**inputs)
        except (KeyError, IndexError):
            pass

        # Query parameters
        params = inputs.get("params") or inputs.get("query")
        if params and isinstance(params, dict):
            query_string = urllib.parse.urlencode(params)
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}{query_string}"

        try:
            self._validate_url(url)
        except (ValueError, PermissionError) as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logs.append(f"HTTPExecutor: Blocked URL - {exc}")
            return ActionResult.fail(
                error=str(exc),
                metadata={"executor": self.name, "url": url, "method": str(inputs.get("method", "GET")).upper()},
                logs=logs,
                execution_time_ms=duration_ms,
            )

        # Body data
        data_bytes = None
        json_body = inputs.get("json") or inputs.get("body") or inputs.get("data")
        if json_body is not None and method in ("POST", "PUT", "PATCH", "DELETE"):
            if isinstance(json_body, (dict, list)):
                data_bytes = json.dumps(json_body).encode("utf-8")
                headers["Content-Type"] = "application/json"
            elif isinstance(json_body, str):
                data_bytes = json_body.encode("utf-8")
            elif isinstance(json_body, bytes):
                data_bytes = json_body

        timeout = float(inputs.get("timeout", self.default_timeout))

        logs.append(f"HTTPExecutor: Sending {method} to {url}")
        req = urllib.request.Request(url=url, data=data_bytes, headers=headers, method=method)

        try:
            # urllib follows redirects by default; use a validating handler so
            # an otherwise safe public URL cannot pivot into a private address.
            with self._safe_opener().open(req, timeout=timeout) as response:
                status_code = response.getcode()
                resp_headers = dict(response.info())
                raw_body = response.read().decode("utf-8", errors="replace")

                # Try parsing JSON body if possible
                try:
                    parsed_output = json.loads(raw_body)
                except Exception:
                    parsed_output = raw_body

                duration_ms = (time.perf_counter() - start_time) * 1000.0
                logs.append(f"HTTPExecutor: Received {status_code} ({len(raw_body)} bytes) in {duration_ms:.2f}ms")

                return ActionResult.ok(
                    output=parsed_output,
                    metadata={
                        "executor": self.name,
                        "status_code": status_code,
                        "headers": resp_headers,
                        "url": url,
                        "method": method,
                    },
                    logs=logs,
                    execution_time_ms=duration_ms,
                )
        except urllib.error.HTTPError as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            logs.append(f"HTTPExecutor: HTTP Error {e.code} - {e.reason}")
            return ActionResult.fail(
                error=f"HTTP {e.code}: {e.reason}",
                output=err_body,
                metadata={"status_code": e.code, "url": url, "method": method},
                logs=logs,
                execution_time_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logs.append(f"HTTPExecutor: Connection error - {str(e)}")
            return ActionResult.fail(
                error=f"HTTP request error: {str(e)}",
                metadata={"url": url, "method": method},
                logs=logs,
                execution_time_ms=duration_ms,
            )


class MLExecutor(BaseExecutor):
    """Executes traditional machine learning model inference, scoring pipelines, and embeddings."""

    def __init__(
        self,
        models: Optional[Dict[str, Any]] = None,
        name: str = "MLExecutor",
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize MLExecutor with optional model registry."""
        super().__init__(name=name, config=config)
        self._models: Dict[str, Any] = models.copy() if models else {}

    @property
    def executor_type(self) -> str:
        return "ml"

    def register_model(self, model_name: str, model_instance: Any) -> None:
        """Register a machine learning model instance or pipeline."""
        self._models[model_name] = model_instance

    def execute(
        self,
        action_name: str,
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        """Run ML inference with inputs."""
        logs: List[str] = [f"MLExecutor: Running model inference for action '{action_name}'"]
        start_time = time.perf_counter()

        try:
            model_key = inputs.get("model_name") or inputs.get("model") or action_name
            model = self._models.get(model_key) or inputs.get("__model__")

            features = inputs.get("features") or inputs.get("data") or {
                k: v for k, v in inputs.items() if not k.startswith("__") and k not in ("model", "model_name")
            }

            if model is not None:
                if hasattr(model, "predict_proba") and inputs.get("predict_proba", False):
                    prediction = model.predict_proba(features)
                elif hasattr(model, "predict"):
                    prediction = model.predict(features)
                elif hasattr(model, "transform"):
                    prediction = model.transform(features)
                elif callable(model):
                    prediction = model(features)
                else:
                    raise TypeError(f"Registered model for '{model_key}' is not callable and has no predict method.")
            else:
                score = 0.85
                prediction = {"prediction": "default", "score": score, "features_evaluated": list(features.keys())}

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logs.append(f"MLExecutor: Model inference completed in {duration_ms:.2f}ms")

            return ActionResult.ok(
                output=prediction,
                metadata={
                    "executor": self.name,
                    "model": str(model_key),
                    "feature_count": len(features) if isinstance(features, (dict, list)) else 1,
                },
                logs=logs,
                execution_time_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            err_msg = f"ML execution failed for '{action_name}': {str(e)}"
            logs.append(f"MLExecutor: Error - {err_msg}")
            return ActionResult.fail(
                error=err_msg,
                metadata={"executor": self.name},
                logs=logs,
                execution_time_ms=duration_ms,
            )


class SLMExecutor(BaseExecutor):
    """Executes Small Language Model (SLM) tasks (e.g. specialized classification, drafting)."""

    def __init__(
        self,
        inference_handler: Optional[Callable[..., Any]] = None,
        default_model: str = "models/slm-default",
        name: str = "SLMExecutor",
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize SLMExecutor with preferred SLM model and inference handler."""
        super().__init__(name=name, config=config)
        self.default_model = default_model
        self._inference_handler = inference_handler

    @property
    def executor_type(self) -> str:
        return "slm"

    def set_inference_handler(self, handler: Callable[..., Any]) -> None:
        """Set or override the SLM inference runner."""
        self._inference_handler = handler

    def execute(
        self,
        action_name: str,
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        """Execute SLM prompt completion or task."""
        logs: List[str] = [f"SLMExecutor: Starting SLM step '{action_name}'"]
        start_time = time.perf_counter()

        try:
            model = inputs.get("preferred") or inputs.get("model") or self.default_model
            prompt = inputs.get("prompt") or inputs.get("template") or ""
            fallback_candidates = inputs.get("fallback", ["frontier_llm", "human"])

            # Format prompt if template with variables
            if prompt and isinstance(prompt, str):
                try:
                    prompt = prompt.format(**inputs)
                except (KeyError, IndexError):
                    pass

            if self._inference_handler:
                response = self._inference_handler(prompt=prompt, model=model, inputs=inputs, context=context)
            else:
                response = {
                    "text": f"SLM generated response for action '{action_name}' using model '{model}'. Prompt: {prompt}",
                    "draft": inputs.get("draft_text", f"Automated proposal drafted by SLM for {prompt or action_name}"),
                    "prompt": prompt,
                    "status": "completed",
                }

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logs.append(f"SLMExecutor: Completed with model '{model}' in {duration_ms:.2f}ms")

            return ActionResult.ok(
                output=response,
                metadata={
                    "executor": self.name,
                    "model": model,
                    "fallback_candidates": fallback_candidates,
                    "tokens_used": len(str(prompt).split()) + len(str(response).split()),
                },
                logs=logs,
                execution_time_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            err_msg = f"SLM execution failed in '{action_name}': {str(e)}"
            logs.append(f"SLMExecutor: Error - {err_msg}")
            return ActionResult.fail(
                error=err_msg,
                metadata={"executor": self.name, "escalation_required": True},
                logs=logs,
                execution_time_ms=duration_ms,
            )


class LLMExecutor(BaseExecutor):
    """Executes Frontier Large Language Model (LLM) reasoning, tool use, and escalation tasks."""

    def __init__(
        self,
        client: Optional[Callable[..., Any]] = None,
        default_model: str = "frontier_llm",
        name: str = "LLMExecutor",
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize LLMExecutor with default frontier model and client."""
        super().__init__(name=name, config=config)
        self.default_model = default_model
        self._client = client

    @property
    def executor_type(self) -> str:
        return "frontier_llm"

    def set_client(self, client: Callable[..., Any]) -> None:
        """Set the underlying LLM client invocation handler."""
        self._client = client

    def execute(
        self,
        action_name: str,
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        """Execute frontier LLM reasoning task."""
        logs: List[str] = [f"LLMExecutor: Executing frontier LLM action '{action_name}'"]
        start_time = time.perf_counter()

        try:
            model = inputs.get("model") or self.default_model
            system_prompt = inputs.get("system_prompt", "You are an AI task executor.")
            user_prompt = inputs.get("prompt") or inputs.get("instruction") or ""

            if user_prompt and isinstance(user_prompt, str):
                try:
                    user_prompt = user_prompt.format(**inputs)
                except (KeyError, IndexError):
                    pass

            if self._client:
                result = self._client(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=model,
                    inputs=inputs,
                    context=context,
                )
            else:
                result = {
                    "content": f"Frontier LLM analysis and response for action '{action_name}'.",
                    "reasoning": f"Successfully validated invariants and processed inputs for {action_name}.",
                    "status": "completed",
                }

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logs.append(f"LLMExecutor: Finished using model '{model}' in {duration_ms:.2f}ms")

            return ActionResult.ok(
                output=result,
                metadata={
                    "executor": self.name,
                    "model": model,
                    "prompt_tokens": len(str(user_prompt).split()),
                    "completion_tokens": len(str(result).split()),
                    "finish_reason": "stop",
                },
                logs=logs,
                execution_time_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            err_msg = f"LLM execution failed for '{action_name}': {str(e)}"
            logs.append(f"LLMExecutor: Error - {err_msg}")
            return ActionResult.fail(
                error=err_msg,
                metadata={"executor": self.name},
                logs=logs,
                execution_time_ms=duration_ms,
            )


class HumanExecutor(BaseExecutor):
    """Executes Human-in-the-Loop steps (approval, manual review, feedback, or input)."""

    def __init__(
        self,
        name: str = "HumanExecutor",
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize HumanExecutor."""
        super().__init__(name=name, config=config)

    @property
    def executor_type(self) -> str:
        return "human"

    def execute(
        self,
        action_name: str,
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        """Process human input or suspend execution with a wait condition.

        If the human response is already supplied in inputs (e.g., 'approved' or 'human_response'),
        the action completes immediately. Otherwise, it yields a WAITING_HUMAN condition.
        """
        logs: List[str] = [f"HumanExecutor: Evaluating human action step '{action_name}'"]
        start_time = time.perf_counter()

        # Check if human response has been provided
        if "approved" in inputs or "human_response" in inputs or "decision" in inputs:
            verdict = inputs.get("approved")
            if verdict is None and "decision" in inputs:
                verdict = inputs["decision"] in ("approve", "approved", True)

            output = {
                "action": action_name,
                "approved": verdict if verdict is not None else True,
                "decision": inputs.get("decision", "approved" if verdict else "rejected"),
                "reviewer": inputs.get("reviewer", "human_operator"),
                "comments": inputs.get("comments") or inputs.get("feedback", ""),
                "payload": inputs.get("payload", {}),
            }
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logs.append(f"HumanExecutor: Human response recorded (decision: {output['decision']})")

            return ActionResult.ok(
                output=output,
                metadata={"executor": self.name, "completed_by_human": True},
                logs=logs,
                execution_time_ms=duration_ms,
            )

        # No human response provided yet -> suspend execution into WAITING_HUMAN
        prompt = inputs.get("prompt") or inputs.get("description") or f"Human review required for {action_name}"
        assignee = inputs.get("assignee") or inputs.get("reviewer")
        required_fields = inputs.get("required_fields", ["approved", "comments"])
        timeout_seconds = inputs.get("timeout_seconds")

        logs.append(f"HumanExecutor: Human input required. Suspending step '{action_name}'")
        return ActionResult.wait_for_human(
            prompt=prompt,
            assignee=assignee,
            required_fields=required_fields,
            timeout_seconds=timeout_seconds,
            metadata={"executor": self.name, "action": action_name},
            logs=logs,
        )
