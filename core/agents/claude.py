"""Anthropic Claude Code backend (``claude -p``)."""

from __future__ import annotations

import json
from typing import List, Optional

from core.agents.base import AgentBackend, AgentResult, _int

READ_ONLY_TOOLS = ["Read", "Grep", "Glob", "LS", "Bash(cat:*)", "Bash(jq:*)", "Bash(sed:*)", "Bash(ls:*)"]
WRITE_TOOLS = ["Bash", "Read", "Write", "Edit", "MultiEdit", "Grep", "Glob", "LS"]


class ClaudeBackend(AgentBackend):
    name = "claude"
    display_name = "Claude Code"
    executable = "claude"
    skills_dir = ".claude/skills"
    source_agent_prefixes = ("claude",)
    install_hint = "Install with: npm i -g @anthropic-ai/claude-code"
    capture = "passthrough"
    invocation = "/ow-<skill>"

    def build_argv(self, prompt, *, read_only=False, files_allowed=True, model=None):
        argv = ["claude", "-p", prompt, "--output-format", "json", "--no-session-persistence"]
        if read_only or not files_allowed:
            argv += ["--allowedTools", *READ_ONLY_TOOLS]
        else:
            argv += ["--permission-mode", "acceptEdits", "--allowedTools", *WRITE_TOOLS]
        if model:
            argv += ["--model", model]
        return argv

    def subprocess_env(self):
        env = super().subprocess_env()
        for key in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"):   # allow escalation from inside a Claude Code session
            env.pop(key, None)
        return env

    def parse(self, stdout, stderr, returncode):
        text = stdout.strip()
        try:
            data = json.loads(text) if text else {}
        except Exception:
            data = {}
        if not isinstance(data, dict) or "result" not in data:
            return AgentResult(output=text, exit_code=returncode or (1 if not data else 0), raw=(stdout + "\n" + stderr)[-4000:],
                               model="claude")
        usage = data.get("usage") or {}
        cache_read = _int(usage.get("cache_read_input_tokens"))
        prompt = _int(usage.get("input_tokens")) + cache_read + _int(usage.get("cache_creation_input_tokens"))
        completion = _int(usage.get("output_tokens"))
        model = "claude"
        model_usage = data.get("modelUsage")
        if isinstance(model_usage, dict) and model_usage:
            model = next(iter(model_usage))
        return AgentResult(output=str(data.get("result", "")), tokens=prompt + completion, prompt_tokens=prompt,
                           completion_tokens=completion, cached_tokens=cache_read, model=model,
                           latency_ms=float(data.get("duration_ms") or 0.0),
                           exit_code=1 if data.get("is_error") else returncode, raw="" if not data.get("is_error") else text[-4000:],
                           cost_usd=data.get("total_cost_usd"), session_id=str(data.get("session_id") or ""))

    def describe_setup(self, proxy_url="http://127.0.0.1:8787"):
        return f'''# Route Claude Code through the proxy (works with API keys and subscription/OAuth logins):
export ANTHROPIC_BASE_URL={proxy_url}
claude            # skills: owc skills install --agent claude   → /ow-define … /ow-bench in the slash menu
'''
