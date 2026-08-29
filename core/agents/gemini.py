"""Google Gemini CLI backend (``gemini -p``) — escalation only; the proxy does not capture it yet."""

from __future__ import annotations

import json

from core.agents.base import AgentBackend, AgentResult, _int


class GeminiBackend(AgentBackend):
    name = "gemini"
    display_name = "Gemini CLI"
    executable = "gemini"
    skills_dir = ".gemini/skills"
    source_agent_prefixes = ("gemini",)
    install_hint = "Install with: npm i -g @google/gemini-cli"
    capture = "none"
    invocation = "/ow-<skill>"

    def build_argv(self, prompt, *, read_only=False, files_allowed=True, model=None):
        argv = ["gemini", "-p", prompt, "--output-format", "json",
                "--approval-mode", "plan" if read_only or not files_allowed else "yolo"]
        if model:
            argv += ["-m", model]
        return argv

    def parse(self, stdout, stderr, returncode):
        try:
            data = json.loads(stdout.strip() or "{}")
        except Exception:
            data = {}
        if not isinstance(data, dict) or "response" not in data:
            return AgentResult(output=stdout.strip(), exit_code=returncode, raw=(stdout + "\n" + stderr)[-4000:], model="gemini")
        prompt = completion = cached = 0
        model = "gemini"
        for name, stats in ((data.get("stats") or {}).get("models") or {}).items():
            tok = (stats or {}).get("tokens") or {}
            prompt += _int(tok.get("prompt")); completion += _int(tok.get("candidates")); cached += _int(tok.get("cached"))
            model = name
        return AgentResult(output=str(data.get("response", "")), tokens=prompt + completion, prompt_tokens=prompt,
                           completion_tokens=completion, cached_tokens=cached, model=model, exit_code=returncode)

    def describe_setup(self, proxy_url="http://127.0.0.1:8787"):
        return "# Gemini CLI: escalation only for now (the proxy does not intercept the Gemini API yet).\n"
