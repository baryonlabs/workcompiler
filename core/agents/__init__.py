"""Registry of coding-agent backends (escalation, front-agent binder, `owc agent …`)."""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from core.agents.base import AgentBackend, AgentResult
from core.agents.claude import ClaudeBackend
from core.agents.codex import CodexBackend
from core.agents.gemini import GeminiBackend
from core.agents.openai_compat import AiderBackend, OpencodeBackend

REGISTRY: Dict[str, Type[AgentBackend]] = {
    "claude": ClaudeBackend, "codex": CodexBackend, "gemini": GeminiBackend, "opencode": OpencodeBackend, "aider": AiderBackend,
}
PRIORITY = ["claude", "codex", "gemini", "opencode", "aider"]
ENV_AGENT = "OWC_AGENT"


def get_backend(name: str) -> AgentBackend:
    try:
        return REGISTRY[name.lower()]()
    except KeyError as exc:
        raise ValueError(f"unknown agent '{name}'; known: {', '.join(REGISTRY)}") from exc


def detect_all() -> List[Tuple[AgentBackend, Optional[str]]]:
    out = []
    for name in PRIORITY:
        backend = REGISTRY[name]()
        out.append((backend, backend.detect()))
    return out


def resolve_backend(spec: Optional[str], *, trace_source_agent: Optional[str] = None) -> Optional[AgentBackend]:
    """Pick a backend: explicit name → must be installed; "auto" → OWC_AGENT env, then the agent
    that recorded the trace (if installed), then the first installed in PRIORITY order."""
    if not spec or spec == "none":
        return None
    if spec != "auto":
        backend = get_backend(spec)
        if backend.detect() is None:
            raise RuntimeError(f"{backend.display_name} ('{backend.executable}') is not installed. {backend.install_hint}".strip())
        return backend
    env_name = os.environ.get(ENV_AGENT)
    if env_name:
        return resolve_backend(env_name)
    detected = detect_all()
    if trace_source_agent:
        for backend, version in detected:
            if version is not None and backend.matches_source_agent(trace_source_agent):
                return backend
    for backend, version in detected:
        if version is not None:
            return backend
    raise RuntimeError("no coding-agent CLI found on PATH; install one of: " + ", ".join(PRIORITY))


Escalator = Callable[[str, Dict[str, Any]], Dict[str, Any]]


def as_escalator(backend: AgentBackend, *, model: Optional[str] = None) -> Escalator:
    def _call(prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return backend.run(prompt, read_only=bool(context.get("read_only")), model=model,
                           cwd=context.get("cwd")).to_escalation_dict()
    return _call


__all__ = ["AgentBackend", "AgentResult", "REGISTRY", "PRIORITY", "ENV_AGENT", "get_backend", "detect_all",
           "resolve_backend", "as_escalator", "Escalator"]
