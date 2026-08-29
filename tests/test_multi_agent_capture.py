"""Capture of non-Codex agents through the proxy: Claude Code (Anthropic Messages) and
OpenAI-compatible clients (chat/completions). Fixtures mimic the real wire shapes."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from adapters.proxy import server as proxy_server
from adapters.proxy.agents import conversation_fingerprint, detect_source_agent, resolve_run_id
from adapters.proxy.interceptor import (TrajectoryInterceptor, anthropic_message_from_sse, chat_completion_from_sse,
                                        strip_line_numbers)
from adapters.proxy.server import active_interceptors, app, compiled_workflows_history
from adapters.proxy.tools import ToolKind, classify_tool, merge_calls, normalize_call
from core.work_ir import patchfmt

SESSION = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
CLAUDE_HEADERS = {
    "x-api-key": "sk-ant-test",
    "anthropic-version": "2023-06-01",
    "anthropic-beta": "claude-code-20250219,interleaved-thinking-2025-05-14",
    "user-agent": "claude-cli/2.1.251 (external, cli)",
    "x-app": "cli",
}
CLAUDE_TOOLS = [
    {"name": "Bash", "description": "run a command", "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}}},
    {"name": "Read", "input_schema": {"type": "object", "properties": {"file_path": {"type": "string"}}}},
    {"name": "Write", "input_schema": {"type": "object", "properties": {"file_path": {"type": "string"}, "content": {"type": "string"}}}},
    {"name": "Edit", "input_schema": {"type": "object"}},
    {"name": "TodoWrite", "input_schema": {"type": "object"}},
]


@pytest.fixture
def client():
    active_interceptors.clear()
    compiled_workflows_history.clear()
    return TestClient(app)


def _install(monkeypatch, handler):
    monkeypatch.setattr(proxy_server, "_upstream_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def _sse(events):
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


def _claude_sse(blocks, *, model="claude-sonnet-4-5", stop_reason="tool_use", usage=None, msg_id="msg_1"):
    usage = usage or {"input_tokens": 12, "cache_creation_input_tokens": 3000, "cache_read_input_tokens": 20000, "output_tokens": 0}
    events = [{"type": "message_start", "message": {"id": msg_id, "type": "message", "role": "assistant", "model": model,
                                                   "content": [], "stop_reason": None, "usage": usage}}]
    for i, block in enumerate(blocks):
        if block["type"] == "text":
            events.append({"type": "content_block_start", "index": i, "content_block": {"type": "text", "text": ""}})
            for piece in (block["text"][:5], block["text"][5:]):
                events.append({"type": "content_block_delta", "index": i, "delta": {"type": "text_delta", "text": piece}})
        else:
            events.append({"type": "content_block_start", "index": i, "content_block": {"type": "tool_use", "id": block["id"], "name": block["name"], "input": {}}})
            raw = json.dumps(block["input"])
            third = max(1, len(raw) // 3)
            for piece in (raw[:third], raw[third:2 * third], raw[2 * third:]):
                events.append({"type": "content_block_delta", "index": i, "delta": {"type": "input_json_delta", "partial_json": piece}})
        events.append({"type": "content_block_stop", "index": i})
    events.append({"type": "ping"})
    events.append({"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None}, "usage": {"output_tokens": 87}})
    events.append({"type": "message_stop"})
    return _sse(events)


def _claude_request(messages, *, tools=CLAUDE_TOOLS, session=SESSION, model="claude-sonnet-4-5", max_tokens=32000):
    return {
        "model": model, "max_tokens": max_tokens, "stream": True,
        "system": [{"type": "text", "text": "You are Claude Code.", "cache_control": {"type": "ephemeral"}}],
        "messages": messages, "tools": tools,
        "metadata": {"user_id": f"user_ab12cd_account_11111111-2222-3333-4444-555555555555_session_{session}"},
    }


def _user(text, extra_blocks=None):
    content = [{"type": "text", "text": text}]
    if extra_blocks:
        content = extra_blocks + content
    return {"role": "user", "content": content}


# --------------------------------------------------------------------------- SSE + tools units

def test_anthropic_sse_reconstruction_assembles_split_tool_input_and_usage():
    body = _claude_sse([{"type": "text", "text": "Let me look."},
                        {"type": "tool_use", "id": "toolu_1", "name": "Bash", "input": {"command": "ls examples", "description": "list"}}])
    msg = anthropic_message_from_sse(body.decode())
    assert msg["stop_reason"] == "tool_use" and msg["usage"]["output_tokens"] == 87
    assert msg["content"][0] == {"type": "text", "text": "Let me look."}
    assert msg["content"][1]["input"] == {"command": "ls examples", "description": "list"}
    assert anthropic_message_from_sse("event: error\ndata: {\"type\":\"error\"}\n\n") is None


def test_chat_completion_sse_reconstruction_merges_tool_call_fragments():
    chunks = [
        {"id": "c1", "object": "chat.completion.chunk", "model": "gpt-4.1", "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}}]},
        {"id": "c1", "choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "id": "call_9", "type": "function", "function": {"name": "run_terminal_cmd", "arguments": "{\"command\": \"ls"}}]}}]},
        {"id": "c1", "choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "function": {"arguments": " -la\"}"}}]}}]},
        {"id": "c1", "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
        {"id": "c1", "choices": [], "usage": {"prompt_tokens": 500, "completion_tokens": 20, "prompt_tokens_details": {"cached_tokens": 400}}},
    ]
    text = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
    obj = chat_completion_from_sse(text)
    call = obj["choices"][0]["message"]["tool_calls"][0]
    assert call["id"] == "call_9" and call["function"]["arguments"] == '{"command": "ls -la"}'
    assert obj["choices"][0]["finish_reason"] == "tool_calls" and obj["usage"]["prompt_tokens"] == 500


def test_strip_line_numbers_handles_arrow_and_tab_renderings():
    assert strip_line_numbers("     1→a\n     2→b") == "a\nb"
    assert strip_line_numbers("1\t# Task\n2\t\n3\tbody") == "# Task\n\nbody"      # Claude Code 2.1.x renders "N<TAB>"
    assert strip_line_numbers("1\tnumbered\nplain line") == "1\tnumbered\nplain line"  # data with a numbered first line is left alone


def test_tool_registry_maps_agent_tools_onto_compiler_vocabulary():
    assert classify_tool("Bash") == ToolKind.SHELL and classify_tool("run_terminal_cmd") == ToolKind.SHELL
    shell = normalize_call("Bash", {"command": "jq '.x' a.json", "description": "read"})
    assert shell.action == "shell_jq" and shell.input["cmd"] == "jq '.x' a.json"
    read = normalize_call("Read", {"file_path": "examples/customer-renewal/TASK.md", "offset": 10, "limit": 5})
    assert read.action == "read_task" and read.input["cmd"] == "sed -n '11,15p' examples/customer-renewal/TASK.md"
    write = normalize_call("Write", {"file_path": "build/out/report.md", "content": "# R\nline\n"})
    assert write.action == "write_report" and "*** Add File: build/out/report.md" in write.patch
    edit = normalize_call("Edit", {"file_path": "cfg.yaml", "old_string": "a: 1", "new_string": "a: 2"})
    assert "*** Update File: cfg.yaml" in edit.patch and "-a: 1" in edit.patch and "+a: 2" in edit.patch
    multi = normalize_call("MultiEdit", {"file_path": "cfg.yaml", "edits": [{"old_string": "x", "new_string": "y", "replace_all": True}]})
    assert "@@ replace_all" in multi.patch
    glob_cmd = normalize_call("Glob", {"pattern": "**/*.py", "path": "core"}).input["cmd"]
    assert glob_cmd.startswith("find core") and glob_cmd.endswith("| sort") and "sed 's#^\\./##'" in glob_cmd
    assert normalize_call("Grep", {"pattern": "def run", "path": "core", "output_mode": "content"}).action.startswith("grep_def_run")
    assert normalize_call("TodoWrite", {"todos": []}).action == "plan"
    merged = merge_calls([normalize_call("Read", {"file_path": "a.md"}), normalize_call("Read", {"file_path": "b.md"})])
    assert merged.input["cmds"] == ["cat a.md", "cat b.md"]


def test_source_agent_detection_and_run_id_resolution():
    assert detect_source_agent(CLAUDE_HEADERS, "anthropic") == ("claude-code", "2.1.251")
    assert detect_source_agent({"originator": "codex_cli_rs"}, "responses")[0] == "codex-cli"
    assert detect_source_agent({"user-agent": "Cursor/1.2.3"}, "chat")[0] == "cursor"
    assert detect_source_agent({"user-agent": "python-httpx/0.28"}, "anthropic")[0] == "anthropic-client"
    req = _claude_request([_user("start")])
    assert resolve_run_id({}, req, "anthropic") == f"claude_{SESSION}"
    # current Claude Code: metadata.user_id is a JSON string carrying session_id
    json_meta = {"model": "claude-x", "messages": [_user("start")],
                 "metadata": {"user_id": json.dumps({"device_id": "6fa4", "account_uuid": "801f", "session_id": "c9c6c630-9e17-43db-8fc0-6f7d2a5f2784"})}}
    assert resolve_run_id({}, json_meta, "anthropic") == "claude_c9c6c630-9e17-43db-8fc0-6f7d2a5f2784"
    assert resolve_run_id({"x-openworkcompiler-run-id": "mine"}, req, "anthropic") == "mine"
    plain = {"model": "claude-x", "system": "s", "messages": [_user("start")]}
    fp1 = resolve_run_id({}, plain, "anthropic")
    plain2 = {"model": "claude-x", "system": "s", "messages": [_user("start"), {"role": "assistant", "content": "ok"}, _user("next")]}
    assert fp1.startswith("conv_") and resolve_run_id({}, plain2, "anthropic") == fp1
    assert resolve_run_id({}, {"model": "claude-x", "system": "s", "messages": [_user("other")]}, "anthropic") != fp1
    assert conversation_fingerprint({"messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "hi"}]}, "u") == \
        conversation_fingerprint({"messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "hi"}, {"role": "user", "content": "more"}]}, "u")


# --------------------------------------------------------------------------- Claude Code through the proxy

def test_claude_code_messages_passthrough_streams_and_captures(client, monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        return httpx.Response(200, content=_claude_sse([{"type": "tool_use", "id": "toolu_1", "name": "Bash",
                                                          "input": {"command": "ls examples", "description": "list"}}]),
                              headers={"content-type": "text/event-stream"})

    _install(monkeypatch, handler)
    body = _claude_sse([{"type": "tool_use", "id": "toolu_1", "name": "Bash", "input": {"command": "ls examples", "description": "list"}}])
    res = client.post("/v1/messages", json=_claude_request([_user("List the example folder")]), headers=CLAUDE_HEADERS)
    assert res.status_code == 200 and res.content == body
    assert res.headers["X-OpenWorkCompiler-Response-Mode"] == "passthrough"
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["headers"]["x-api-key"] == "sk-ant-test" and seen["headers"]["anthropic-beta"].startswith("claude-code")

    interceptor = active_interceptors[f"claude_{SESSION}"]
    assert interceptor.source_agent == "claude-code" and interceptor.agent_version == "2.1.251" and interceptor.protocol == "anthropic"
    step = interceptor.steps[0]
    assert step.action == "shell_ls" and step.input["cmd"] == "ls examples"
    assert step.input["content"] == "List the example folder"
    assert step.model == "claude-sonnet-4-5"
    assert step.token_usage.prompt_tokens == 12 + 3000 + 20000 and step.token_usage.completion_tokens == 87
    assert step.cached_tokens == 20000


def test_claude_tool_results_attach_to_calling_step_and_side_calls_are_not_steps(client, monkeypatch):
    turn = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        turn["n"] += 1
        payload = json.loads(request.content)
        if not payload.get("tools"):
            return httpx.Response(200, json={"id": "msg_side", "type": "message", "role": "assistant", "model": "claude-haiku-4-5",
                                             "content": [{"type": "text", "text": "Title"}], "stop_reason": "end_turn",
                                             "usage": {"input_tokens": 40, "output_tokens": 5}})
        blocks = [{"type": "tool_use", "id": "toolu_r", "name": "Read", "input": {"file_path": "examples/customer-renewal/TASK.md"}}] if turn["n"] == 1 \
            else [{"type": "text", "text": "Done."}]
        return httpx.Response(200, content=_claude_sse(blocks, stop_reason="tool_use" if turn["n"] == 1 else "end_turn"),
                              headers={"content-type": "text/event-stream"})

    _install(monkeypatch, handler)
    first = _claude_request([_user("Summarize TASK.md")])
    client.post("/v1/messages", json=first, headers=CLAUDE_HEADERS)
    # bookkeeping call: haiku, no tools, non-streaming
    side = {"model": "claude-haiku-4-5", "max_tokens": 200, "messages": [_user("Write a 5 word title")], "stream": False,
            "metadata": first["metadata"]}
    client.post("/v1/messages", json=side, headers=CLAUDE_HEADERS)
    result_block = {"type": "tool_result", "tool_use_id": "toolu_r",
                    "content": [{"type": "text", "text": "     1→# Task: renewal\n     2→line two\n\n<system-reminder>\nnoise\n</system-reminder>"}]}
    second = _claude_request([_user("Summarize TASK.md"),
                              {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_r", "name": "Read", "input": {"file_path": "examples/customer-renewal/TASK.md"}}]},
                              {"role": "user", "content": [result_block]}])
    client.post("/v1/messages", json=second, headers=CLAUDE_HEADERS)

    interceptor = active_interceptors[f"claude_{SESSION}"]
    assert [s.action for s in interceptor.steps] == ["read_task", "respond"]
    read = interceptor.steps[0]
    assert read.output["tool_result"] == "# Task: renewal\nline two"
    assert read.output["tool_calls"][0]["result"] == read.output["tool_result"]
    assert interceptor.aux_prompt_tokens == 40 and interceptor.aux_completion_tokens == 5
    assert interceptor.steps[1].output["content"] == "Done." and interceptor.steps[1].input == {}
    assert strip_line_numbers("  10→x\n  11→y") == "x\ny"


def test_claude_session_compiles_into_a_replayable_build(client, monkeypatch, tmp_path):
    monkeypatch.setenv("OPENWORKCOMPILER_WORKSPACE_DIR", str(tmp_path))
    (tmp_path / "notes.txt").write_text("alpha\nbeta\n")
    turns = iter([
        [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "printf 'alpha\\nbeta\\n'"}}],
        [{"type": "tool_use", "id": "t2", "name": "Edit", "input": {"file_path": str(tmp_path / "notes.txt"), "old_string": "beta", "new_string": "gamma"}}],
        [{"type": "text", "text": "Replaced beta with gamma."}],
    ])

    def handler(request: httpx.Request) -> httpx.Response:
        blocks = next(turns)
        return httpx.Response(200, content=_claude_sse(blocks, stop_reason="end_turn" if blocks[0]["type"] == "text" else "tool_use"),
                              headers={"content-type": "text/event-stream"})

    _install(monkeypatch, handler)
    msgs = [_user("Change beta to gamma in notes.txt")]
    client.post("/v1/messages", json=_claude_request(msgs), headers=CLAUDE_HEADERS)
    msgs += [{"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "printf 'alpha\\nbeta\\n'"}}]},
             {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "alpha\nbeta\n"}]}]
    client.post("/v1/messages", json=_claude_request(msgs), headers=CLAUDE_HEADERS)
    msgs += [{"role": "assistant", "content": [{"type": "tool_use", "id": "t2", "name": "Edit", "input": {"file_path": str(tmp_path / "notes.txt"), "old_string": "beta", "new_string": "gamma"}}]},
             {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t2", "content": "The file has been updated."}]}]
    client.post("/v1/messages", json=_claude_request(msgs), headers=CLAUDE_HEADERS)

    traces = client.get("/v1/workcompiler/traces").json()["traces"][0]
    assert traces["source_agent"] == "claude-code" and traces["actions"] == ["shell_printf", "write_notes", "respond"]
    compiled = client.post("/v1/workcompiler/compile", json={"run_id": f"claude_{SESSION}", "target_name": "claude-notes", "build_dir": "build"})
    assert compiled.status_code == 200, compiled.text
    body = compiled.json()
    assert body["executors_summary"] == {"shell_printf": "code", "write_notes": "code", "respond": "frontier_llm"}
    handler_py = (tmp_path / "build" / "claude_notes" / "handlers" / "write_notes.py").read_text()
    assert "*** Update File: notes.txt" in handler_py and "-beta" in handler_py and "+gamma" in handler_py

    from core.build.bench import run_benchmark
    from core.work_ir import TraceIR
    trace = TraceIR.model_validate(json.loads((tmp_path / "build" / "claude_notes" / "trace.json").read_text())["traces"][0])
    monkeypatch.chdir(tmp_path)
    report = run_benchmark(tmp_path / "build" / "claude_notes", trace)
    steps = {s.step_id: s for a in report.actions for s in a.steps}
    assert steps["step_1"].output_match is True
    assert steps["step_2"].output_match is True and "verified" in steps["step_2"].note
    assert (tmp_path / "notes.txt").read_text() == "alpha\ngamma\n"
    assert report.totals()["compiled_tokens"] == report.actions[-1].compiled_tokens  # only respond still costs


def test_catch_all_forwards_to_the_right_upstream(client, monkeypatch):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"ok": True})

    _install(monkeypatch, handler)
    assert client.post("/v1/messages/count_tokens", json={"model": "x"}, headers=CLAUDE_HEADERS).json() == {"ok": True}
    assert client.get("/v1/models", headers={"authorization": "Bearer sk-openai"}).status_code == 200
    assert client.get("/backend-api/codex/models?client_version=1", headers={"originator": "codex_cli_rs"}).status_code == 200
    assert seen == ["https://api.anthropic.com/v1/messages/count_tokens", "https://api.openai.com/v1/models",
                    "https://chatgpt.com/backend-api/codex/models?client_version=1"]


# --------------------------------------------------------------------------- OpenAI-compatible clients

def test_chat_completions_passthrough_reconstructs_tool_calls_and_attaches_results(client, monkeypatch):
    turn = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        turn["n"] += 1
        if turn["n"] == 1:
            chunks = [
                {"id": "c1", "object": "chat.completion.chunk", "model": "gpt-4.1", "choices": [{"index": 0, "delta": {"role": "assistant"}}]},
                {"id": "c1", "choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "id": "call_1", "type": "function", "function": {"name": "run_terminal_cmd", "arguments": "{\"command\": \"ls"}}]}}]},
                {"id": "c1", "choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "function": {"arguments": " examples\"}"}}]}}]},
                {"id": "c1", "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
                {"id": "c1", "choices": [], "usage": {"prompt_tokens": 300, "completion_tokens": 12, "prompt_tokens_details": {"cached_tokens": 200}}},
            ]
        else:
            chunks = [{"id": "c2", "object": "chat.completion.chunk", "model": "gpt-4.1", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "two entries"}, "finish_reason": "stop"}]},
                      {"id": "c2", "choices": [], "usage": {"prompt_tokens": 320, "completion_tokens": 3}}]
        text = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, content=text.encode(), headers={"content-type": "text/event-stream"})

    _install(monkeypatch, handler)
    headers = {"authorization": "Bearer sk-openai", "user-agent": "Cursor/1.2.3"}
    msgs = [{"role": "system", "content": "You are an IDE agent."}, {"role": "user", "content": "list examples"}]
    client.post("/v1/chat/completions", json={"model": "gpt-4.1", "stream": True, "messages": msgs, "tools": [{"type": "function", "function": {"name": "run_terminal_cmd"}}]}, headers=headers)
    msgs += [{"role": "assistant", "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "run_terminal_cmd", "arguments": "{\"command\": \"ls examples\"}"}}]},
             {"role": "tool", "tool_call_id": "call_1", "content": "cases\ndemo\n"}]
    client.post("/v1/chat/completions", json={"model": "gpt-4.1", "stream": True, "messages": msgs}, headers=headers)

    interceptor = next(iter(active_interceptors.values()))
    assert interceptor.source_agent == "cursor" and interceptor.protocol == "chat"
    assert [s.action for s in interceptor.steps] == ["shell_ls", "respond"]
    assert interceptor.steps[0].output["tool_result"] == "cases\ndemo\n"
    assert interceptor.steps[0].cached_tokens == 200 and interceptor.steps[0].token_usage.prompt_tokens == 300


def test_synthetic_mode_requires_the_header(client, monkeypatch):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"id": "x", "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}], "usage": {}})

    _install(monkeypatch, handler)
    client.post("/v1/chat/completions", json={"model": "gpt-4.1", "messages": [{"role": "user", "content": "hi"}]})
    assert calls == ["/v1/chat/completions"]  # went upstream
    res = client.post("/v1/chat/completions", json={"model": "gpt-4.1", "messages": [{"role": "user", "content": "hi"}]},
                      headers={"X-OpenWorkCompiler-Response-Mode": "synthetic"})
    assert res.headers["X-OpenWorkCompiler-Response-Mode"] == "synthetic" and calls == ["/v1/chat/completions"]
