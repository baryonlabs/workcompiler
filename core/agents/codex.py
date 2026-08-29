"""OpenAI Codex CLI backend (``codex exec``)."""

from __future__ import annotations

import re
from typing import List, Optional

from core.agents.base import AgentBackend, AgentResult


class CodexBackend(AgentBackend):
    name = "codex"
    display_name = "Codex CLI"
    executable = "codex"
    skills_dir = ".agents/skills"
    source_agent_prefixes = ("codex",)
    install_hint = "Install with: npm i -g @openai/codex"
    capture = "passthrough"
    invocation = "$ow-<skill>"

    def build_argv(self, prompt, *, read_only=False, files_allowed=True, model=None):
        argv = ["codex", "exec", "--skip-git-repo-check", "-c", "notify=[]",
                "--sandbox", "read-only" if read_only or not files_allowed else "workspace-write"]
        if model:
            argv += ["-m", model]
        return argv + [prompt]

    def parse(self, stdout, stderr, returncode):
        text = stdout + ("\n" + stderr if stderr else "")   # codex prints the transcript on stderr
        tokens = 0
        m = re.search(r"tokens used\n([\d,]+)", text)
        if m:
            tokens = int(m.group(1).replace(",", ""))
        model_m = re.search(r"^model:\s*(\S+)", text, re.M)
        parts = re.split(r"^codex\n", text, flags=re.M)
        answer = parts[-1].split("\ntokens used\n")[0].strip() if len(parts) > 1 else text.strip()
        return AgentResult(output=answer, tokens=tokens, completion_tokens=0, prompt_tokens=tokens,
                           model=model_m.group(1) if model_m else "codex", exit_code=returncode,
                           raw=text if returncode else "")

    def describe_setup(self, proxy_url="http://127.0.0.1:8787"):
        return f'''# ~/.codex/config.toml (or a dedicated CODEX_HOME with auth.json copied in)
model_provider = "openworkcompiler"
approval_policy = "never"
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = true            # lets Codex curl the local proxy

[model_providers.openworkcompiler]
name = "OpenWorkCompiler Proxy"
base_url = "{proxy_url}/backend-api/codex"
wire_api = "responses"
requires_openai_auth = true      # reuse the ChatGPT login token as-is
'''
