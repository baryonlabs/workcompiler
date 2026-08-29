"""Common interface for coding-agent CLIs used as escalation / front-agent backends."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class AgentResult:
    output: str
    tokens: int = 0                  # prompt + completion (cached counted inside prompt, like the proxy ledger)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    model: str = ""
    latency_ms: float = 0.0
    exit_code: int = 0
    raw: str = ""                    # merged stdout/stderr when something went wrong
    cost_usd: Optional[float] = None
    session_id: str = ""

    def to_escalation_dict(self) -> Dict[str, Any]:
        """The shape ``core.build.run`` consumes from an escalator."""
        return {"output": self.output, "tokens": self.tokens, "latency_ms": self.latency_ms,
                "exit_code": self.exit_code, "model": self.model, "raw": self.raw,
                "prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens,
                "cached_tokens": self.cached_tokens, "cost_usd": self.cost_usd}


class AgentBackend:
    """One coding agent CLI. Subclasses override argv construction, output parsing and setup text."""

    name: str = "agent"
    display_name: str = "Agent"
    executable: str = "agent"
    skills_dir: Optional[str] = None                   # project-relative convention dir for SKILL.md skills
    source_agent_prefixes: Tuple[str, ...] = ()        # proxy `source_agent` values meaning "this agent"
    install_hint: str = ""
    capture: str = "none"                              # how the proxy captures it: passthrough | none
    invocation: str = ""                               # how a skill is invoked explicitly in this agent's UI

    def detect(self) -> Optional[str]:
        """Path-installed? Returns the version string ("" if unknown) or None when absent."""
        if shutil.which(self.executable) is None:
            return None
        try:
            proc = subprocess.run([self.executable, "--version"], capture_output=True, text=True, timeout=5,
                                  stdin=subprocess.DEVNULL, env=self.subprocess_env())
            text = (proc.stdout or proc.stderr).strip().splitlines()
            return text[0][:60] if text else ""
        except Exception:
            return ""

    def build_argv(self, prompt: str, *, read_only: bool = False, files_allowed: bool = True,
                   model: Optional[str] = None) -> List[str]:
        raise NotImplementedError

    def subprocess_env(self) -> Dict[str, str]:
        return dict(os.environ)

    def parse(self, stdout: str, stderr: str, returncode: int) -> AgentResult:
        raise NotImplementedError

    def run(self, prompt: str, *, cwd: Optional[str] = None, read_only: bool = False, files_allowed: bool = True,
            model: Optional[str] = None, timeout: int = 900) -> AgentResult:
        if self.detect() is None:
            raise RuntimeError(f"{self.display_name} CLI ('{self.executable}') not found on PATH. {self.install_hint}".strip())
        argv = self.build_argv(prompt, read_only=read_only, files_allowed=files_allowed, model=model)
        t0 = time.perf_counter()
        proc = subprocess.run(argv, cwd=cwd, env=self.subprocess_env(), stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=timeout)
        result = self.parse(proc.stdout, proc.stderr, proc.returncode)
        if not result.latency_ms:
            result.latency_ms = (time.perf_counter() - t0) * 1000.0
        if proc.returncode and not result.raw:
            result.raw = (proc.stdout + "\n" + proc.stderr)[-4000:]
        return result

    def describe_setup(self, proxy_url: str = "http://127.0.0.1:8787") -> str:
        raise NotImplementedError

    def matches_source_agent(self, source_agent: Optional[str]) -> bool:
        src = (source_agent or "").lower()
        return any(src.startswith(p) for p in self.source_agent_prefixes)


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
