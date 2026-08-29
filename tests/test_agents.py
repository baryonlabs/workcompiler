"""Agent backend registry: detection, auto-resolution, per-CLI argv/parsers, escalator adapter."""

import json
import os
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from core import agents
from core.agents import PRIORITY, REGISTRY, as_escalator, get_backend, resolve_backend
from core.agents.claude import ClaudeBackend
from core.agents.codex import CodexBackend
from core.agents.gemini import GeminiBackend
from core.agents.openai_compat import AiderBackend, OpencodeBackend


def _installed(monkeypatch, *names):
    """Pretend exactly ``names`` are on PATH (version probe short-circuited)."""
    monkeypatch.setattr(shutil, "which", lambda exe: f"/usr/local/bin/{exe}" if exe in names else None)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=f"{a[0][0]} 9.9.9\n", stderr="", returncode=0))


def test_registry_and_priority_are_consistent():
    assert list(REGISTRY) == PRIORITY == ["claude", "codex", "gemini", "opencode", "aider"]
    for name, cls in REGISTRY.items():
        assert cls.name == name and cls.executable
    with pytest.raises(ValueError, match="unknown agent"):
        get_backend("copilot")


def test_detect_reports_version_or_none(monkeypatch):
    _installed(monkeypatch, "claude", "codex")
    assert ClaudeBackend().detect() == "claude 9.9.9"
    assert CodexBackend().detect() == "codex 9.9.9"
    assert GeminiBackend().detect() is None


def test_resolve_backend_rules(monkeypatch):
    monkeypatch.delenv(agents.ENV_AGENT, raising=False)
    _installed(monkeypatch, "codex", "opencode")
    assert resolve_backend("none") is None and resolve_backend(None) is None
    assert resolve_backend("auto").name == "codex"                                   # first installed in priority order
    assert resolve_backend("auto", trace_source_agent="opencode").name == "opencode"  # the agent that recorded the trace
    assert resolve_backend("auto", trace_source_agent="claude-code").name == "codex"  # recorded agent absent → fallback
    assert resolve_backend("opencode").name == "opencode"
    with pytest.raises(RuntimeError, match="not installed"):
        resolve_backend("claude")
    monkeypatch.setenv(agents.ENV_AGENT, "opencode")
    assert resolve_backend("auto", trace_source_agent="codex-cli").name == "opencode"  # env wins over the trace
    _installed(monkeypatch)
    monkeypatch.delenv(agents.ENV_AGENT)
    with pytest.raises(RuntimeError, match="no coding-agent CLI"):
        resolve_backend("auto")


def test_argv_shapes_for_each_backend():
    claude_ro = ClaudeBackend().build_argv("hi", read_only=True)
    assert claude_ro[:5] == ["claude", "-p", "hi", "--output-format", "json"] and "--allowedTools" in claude_ro
    assert "Write" not in claude_ro and "Bash(cat:*)" in claude_ro
    claude_rw = ClaudeBackend().build_argv("hi", model="claude-sonnet-4-5")
    assert "acceptEdits" in claude_rw and "Write" in claude_rw and claude_rw[-2:] == ["--model", "claude-sonnet-4-5"]
    codex = CodexBackend().build_argv("hi", read_only=True, model="gpt-5")
    assert codex[:2] == ["codex", "exec"] and "read-only" in codex and codex[-3:] == ["-m", "gpt-5", "hi"]
    assert "workspace-write" in CodexBackend().build_argv("hi")
    gem = GeminiBackend().build_argv("hi", read_only=True)
    assert gem[:3] == ["gemini", "-p", "hi"] and "plan" in gem and "yolo" in GeminiBackend().build_argv("hi")
    assert OpencodeBackend().build_argv("hi")[:4] == ["opencode", "run", "--format", "json"]
    aider = AiderBackend().build_argv("hi", read_only=True)
    assert aider[:3] == ["aider", "--message", "hi"] and "--dry-run" in aider and "--no-auto-commits" in aider


def test_claude_env_strips_nested_session_markers(monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1"); monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli"); monkeypatch.setenv("HOME_KEEP", "x")
    env = ClaudeBackend().subprocess_env()
    assert "CLAUDECODE" not in env and "CLAUDE_CODE_ENTRYPOINT" not in env and env["HOME_KEEP"] == "x"


def test_claude_parser_reads_result_usage_and_model():
    payload = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 4321, "num_turns": 3,
               "result": "done: wrote report", "session_id": "c9c6c630-9e17-43db-8fc0-6f7d2a5f2784", "total_cost_usd": 0.0421,
               "usage": {"input_tokens": 12, "cache_creation_input_tokens": 3000, "cache_read_input_tokens": 20000, "output_tokens": 150},
               "modelUsage": {"claude-sonnet-4-5-20250929": {"inputTokens": 12, "outputTokens": 150}}}
    r = ClaudeBackend().parse(json.dumps(payload), "", 0)
    assert r.output == "done: wrote report" and r.prompt_tokens == 23012 and r.completion_tokens == 150
    assert r.tokens == 23162 and r.cached_tokens == 20000 and r.model == "claude-sonnet-4-5-20250929"
    assert r.latency_ms == 4321 and r.cost_usd == 0.0421 and r.session_id.startswith("c9c6") and r.exit_code == 0
    err = ClaudeBackend().parse(json.dumps({**payload, "is_error": True}), "", 0)
    assert err.exit_code == 1 and err.raw
    garbage = ClaudeBackend().parse("not json", "boom", 2)
    assert garbage.exit_code == 2 and garbage.output == "not json"


def test_codex_parser_reads_transcript_and_token_line():
    transcript = "OpenAI Codex v0.150.1\nmodel: gpt-5-codex\n--------\nuser\nhi\ncodex\nThe answer is 42.\ntokens used\n1,234\n"
    r = CodexBackend().parse("", transcript, 0)
    assert r.output == "The answer is 42." and r.tokens == 1234 and r.model == "gpt-5-codex"


def test_gemini_opencode_aider_parsers():
    gem = {"response": "ok from gemini", "stats": {"models": {"gemini-2.5-pro": {"tokens": {"prompt": 900, "candidates": 40, "cached": 300}}}}}
    r = GeminiBackend().parse(json.dumps(gem), "", 0)
    assert r.output == "ok from gemini" and r.tokens == 940 and r.cached_tokens == 300 and r.model == "gemini-2.5-pro"
    lines = [json.dumps({"type": "text", "part": {"type": "text", "text": "hello "}}),
             json.dumps({"type": "text", "part": {"type": "text", "text": "world"}}),
             json.dumps({"type": "step_finish", "modelID": "gpt-4.1", "tokens": {"input": 500, "output": 20, "cache": {"read": 100}}})]
    r = OpencodeBackend().parse("\n".join(lines), "", 0)
    assert r.output == "hello world" and r.tokens == 520 and r.cached_tokens == 100 and r.model == "gpt-4.1"
    r = AiderBackend().parse("Applied edit to a.py\nTokens: 4.2k sent, 350 received. Cost: $0.01", "", 0)
    assert r.prompt_tokens == 4200 and r.completion_tokens == 350 and r.tokens == 4550


def test_run_invokes_cli_and_escalator_adapter_yields_ledger_keys(monkeypatch):
    calls = {}
    monkeypatch.setattr(shutil, "which", lambda exe: "/usr/local/bin/claude")

    def fake_run(argv, **kwargs):
        if argv[1:2] == ["--version"]:
            return SimpleNamespace(stdout="claude 2.1.251\n", stderr="", returncode=0)
        calls["argv"], calls["kwargs"] = argv, kwargs
        body = {"result": "wrote it", "usage": {"input_tokens": 10, "output_tokens": 5}, "duration_ms": 12}
        return SimpleNamespace(stdout=json.dumps(body), stderr="", returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv("CLAUDECODE", "1")
    esc = as_escalator(ClaudeBackend(), model="claude-haiku-4-5")
    out = esc("do the thing", {"read_only": True, "cwd": "/tmp/x"})
    assert calls["argv"][2] == "do the thing" and "Write" not in calls["argv"] and calls["argv"][-1] == "claude-haiku-4-5"
    assert calls["kwargs"]["cwd"] == "/tmp/x" and "CLAUDECODE" not in calls["kwargs"]["env"]
    assert out["output"] == "wrote it" and out["tokens"] == 15 and out["exit_code"] == 0
    assert {"output", "tokens", "latency_ms", "exit_code", "model", "raw", "prompt_tokens", "completion_tokens", "cached_tokens", "cost_usd"} <= set(out)
    with pytest.raises(RuntimeError, match="not found on PATH"):
        monkeypatch.setattr(shutil, "which", lambda exe: None)
        ClaudeBackend().run("x")


def test_setup_text_points_each_agent_at_the_proxy():
    assert "ANTHROPIC_BASE_URL=http://127.0.0.1:8787" in ClaudeBackend().describe_setup()
    assert 'base_url = "http://127.0.0.1:9999/backend-api/codex"' in CodexBackend().describe_setup("http://127.0.0.1:9999")
    assert "OPENAI_BASE_URL=http://127.0.0.1:8787/v1" in OpencodeBackend().describe_setup()
