"""OpenAI-compatible clients: captured via OPENAI_BASE_URL; opencode / aider as escalation backends."""

from __future__ import annotations

import json
import re

from core.agents.base import AgentBackend, AgentResult, _int


class OpenAICompatBackend(AgentBackend):
    source_agent_prefixes = ("openai",)
    capture = "passthrough"

    def describe_setup(self, proxy_url="http://127.0.0.1:8787"):
        return f'''# Any OpenAI-compatible client (Cursor, Windsurf, opencode, Aider, Continue, SDKs):
export OPENAI_BASE_URL={proxy_url}/v1
# Cursor / Windsurf: Settings → Models → "Override OpenAI Base URL" = {proxy_url}/v1
'''


class OpencodeBackend(OpenAICompatBackend):
    name = "opencode"
    display_name = "opencode"
    executable = "opencode"
    skills_dir = ".opencode/skills"
    source_agent_prefixes = ("opencode",)
    install_hint = "Install with: curl -fsSL https://opencode.ai/install | bash"
    invocation = "/ow-<skill>"

    def build_argv(self, prompt, *, read_only=False, files_allowed=True, model=None):
        argv = ["opencode", "run", "--format", "json"]
        if model:
            argv += ["--model", model]
        return argv + [prompt]

    def parse(self, stdout, stderr, returncode):
        texts, prompt, completion, cached, model = [], 0, 0, 0, "opencode"
        for line in stdout.splitlines():
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if not isinstance(ev, dict):
                continue
            part = ev.get("part") or ev
            if part.get("type") == "text" and part.get("text"):
                texts.append(str(part["text"]))
            tok = ev.get("tokens") or part.get("tokens")
            if isinstance(tok, dict):
                prompt += _int(tok.get("input")); completion += _int(tok.get("output"))
                cached += _int((tok.get("cache") or {}).get("read"))
            if ev.get("modelID"):
                model = str(ev["modelID"])
        return AgentResult(output="".join(texts).strip() or stdout.strip(), tokens=prompt + completion, prompt_tokens=prompt,
                           completion_tokens=completion, cached_tokens=cached, model=model, exit_code=returncode,
                           raw=(stdout + "\n" + stderr)[-4000:] if returncode else "")


class AiderBackend(OpenAICompatBackend):
    name = "aider"
    display_name = "Aider"
    executable = "aider"
    skills_dir = None
    source_agent_prefixes = ("aider",)
    install_hint = "Install with: pipx install aider-chat"
    invocation = "(no skills; paste the SKILL.md instructions as the message)"

    def build_argv(self, prompt, *, read_only=False, files_allowed=True, model=None):
        argv = ["aider", "--message", prompt, "--yes", "--no-auto-commits"]
        if read_only or not files_allowed:
            argv += ["--dry-run"]
        if model:
            argv += ["--model", model]
        return argv

    def parse(self, stdout, stderr, returncode):
        text = stdout + "\n" + stderr
        sent = received = 0
        m = re.search(r"Tokens:\s*([\d.]+)(k?)\s*sent,\s*([\d.]+)(k?)\s*received", text)
        if m:
            sent = int(float(m.group(1)) * (1000 if m.group(2) else 1))
            received = int(float(m.group(3)) * (1000 if m.group(4) else 1))
        return AgentResult(output=stdout.strip(), tokens=sent + received, prompt_tokens=sent, completion_tokens=received,
                           model="aider", exit_code=returncode, raw=text[-4000:] if returncode else "")
