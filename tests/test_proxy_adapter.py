"""Unit and Integration Tests for OpenWorkflow Zero-Code Agent Proxy Adapter."""

import json
import pytest
from fastapi.testclient import TestClient

from adapters.proxy.server import app, active_interceptors, compiled_workflows_history
from adapters.proxy.interceptor import TrajectoryInterceptor


@pytest.fixture
def client():
    """Create FastAPI test client."""
    active_interceptors.clear()
    compiled_workflows_history.clear()
    return TestClient(app)


def test_health_check(client):
    """Test proxy healthcheck endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["active_sessions"] == 0


def test_openai_chat_completions_interception(client):
    """Test OpenAI /v1/chat/completions endpoint proxying and trajectory interception."""
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "Fetch active contract for customer CUST-1001"}
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "lookup_contract",
                    "description": "Lookup active customer contract in CRM",
                    "parameters": {
                        "type": "object",
                        "properties": {"customer_id": {"type": "string"}},
                    },
                },
            }
        ],
    }

    headers = {
        "X-OpenWorkflow-Run-ID": "test_run_openai_01",
        "User-Agent": "Claude-Code/1.0",
    }

    response = client.post("/v1/chat/completions", json=payload, headers=headers)
    assert response.status_code == 200
    res_data = response.json()
    assert "choices" in res_data
    assert res_data["choices"][0]["message"]["role"] == "assistant"
    assert response.headers["X-OpenWorkflow-Response-Mode"] == "synthetic"

    # Verify session interceptor recorded the turn
    assert "test_run_openai_01" in active_interceptors
    interceptor = active_interceptors["test_run_openai_01"]
    assert len(interceptor.steps) == 1
    step = interceptor.steps[0]
    assert step.action == "lookup_contract"
    assert step.actor == "agent"
    assert step.token_usage.prompt_tokens == 120


def test_anthropic_messages_interception(client):
    """Test Anthropic /v1/messages endpoint proxying and trajectory interception."""
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "messages": [
            {"role": "user", "content": "Calculate current resource usage"}
        ],
        "tools": [
            {
                "name": "calculate_usage",
                "description": "Calculate monthly usage units",
                "input_schema": {
                    "type": "object",
                    "properties": {"contract_id": {"type": "string"}},
                },
            }
        ],
    }

    headers = {
        "X-OpenWorkflow-Run-ID": "test_run_anthropic_01",
        "User-Agent": "Anthropic-SDK/python",
    }

    response = client.post("/v1/messages", json=payload, headers=headers)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["type"] == "message"
    assert response.headers["X-OpenWorkflow-Response-Mode"] == "synthetic"

    assert "test_run_anthropic_01" in active_interceptors
    interceptor = active_interceptors["test_run_anthropic_01"]
    assert len(interceptor.steps) == 1
    step = interceptor.steps[0]
    assert step.action == "calculate_usage"


def test_list_traces_and_compile_trigger(client):
    """Test listing active traces and triggering WorkCompiler compilation."""
    # 1. Send OpenAI turn
    payload_1 = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Check CRM contract"}],
        "tools": [{"type": "function", "function": {"name": "lookup_contract"}}],
    }
    client.post("/v1/chat/completions", json=payload_1, headers={"X-OpenWorkflow-Run-ID": "session_demo"})

    # 2. Send Anthropic turn
    payload_2 = {
        "model": "claude-3-5-sonnet-20241022",
        "messages": [{"role": "user", "content": "Compute pricing offer"}],
        "tools": [{"name": "price_offer"}],
    }
    client.post("/v1/messages", json=payload_2, headers={"X-OpenWorkflow-Run-ID": "session_demo"})

    # 3. List active traces
    traces_res = client.get("/v1/workcompiler/traces")
    assert traces_res.status_code == 200
    traces_list = traces_res.json()["traces"]
    assert len(traces_list) == 1
    assert traces_list[0]["run_id"] == "session_demo"
    assert traces_list[0]["steps_count"] == 2

    # 4. Trigger WorkIR Compilation
    compile_req = {
        "run_id": "session_demo",
        "target_name": "customer-renewal-proxy",
    }
    compile_res = client.post("/v1/workcompiler/compile", json=compile_req)
    assert compile_res.status_code == 200
    compile_data = compile_res.json()
    assert compile_data["status"] == "compiled"
    assert compile_data["work_name"] == "customer-renewal-proxy"
    assert "lookup_contract" in compile_data["actions"]
    assert "price_offer" in compile_data["actions"]
    assert "executors_summary" in compile_data


@pytest.mark.parametrize("endpoint", ["/v1/chat/completions", "/v1/messages", "/v1/workcompiler/compile"])
def test_proxy_returns_4xx_for_malformed_json(client, endpoint):
    """Invalid JSON is a client error and must never become a 500 response."""
    response = client.post(endpoint, content=b'{"model":', headers={"Content-Type": "application/json"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Request body must contain valid JSON."


def test_compile_output_path_is_restricted_to_workspace(client, tmp_path, monkeypatch):
    """Compilation may write artifacts only beneath the explicit workspace root."""
    monkeypatch.setenv("OPENWORKFLOW_WORKSPACE_DIR", str(tmp_path))
    client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [], "tools": []},
        headers={"X-OpenWorkflow-Run-ID": "workspace_path_test"},
    )

    blocked = client.post(
        "/v1/workcompiler/compile",
        json={
            "run_id": "workspace_path_test",
            "target_name": "path-test",
            "output_path": "../outside.yaml",
        },
    )
    assert blocked.status_code == 403

    allowed = client.post(
        "/v1/workcompiler/compile",
        json={
            "run_id": "workspace_path_test",
            "target_name": "path-test",
            "output_path": "compiled/path-test.yaml",
        },
    )
    assert allowed.status_code == 200
    assert (tmp_path / "compiled" / "path-test.yaml").is_file()


# ---------------------------------------------------------------------------
# Responses API passthrough (Codex CLI path)
# ---------------------------------------------------------------------------

def _sse(events):
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


def _codex_like_sse(response_id="resp_1", tool_call=True):
    output = []
    if tool_call:
        output.append({
            "type": "function_call",
            "id": "fc_1",
            "call_id": "call_1",
            "name": "shell",
            "arguments": json.dumps({"command": ["bash", "-lc", "cat examples/customer-renewal/BEHAVIOR.md"]}),
        })
    output.append({
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": "Reading the behavior contract."}],
    })
    response = {
        "id": response_id,
        "object": "response",
        "status": "completed",
        "output": output,
        "usage": {"input_tokens": 300, "output_tokens": 25, "total_tokens": 325},
    }
    return _sse([
        {"type": "response.created", "response": {"id": response_id, "status": "in_progress"}},
        {"type": "response.output_item.done", "item": output[0]},
        {"type": "response.completed", "response": response},
    ])


def _install_mock_upstream(monkeypatch, handler):
    import httpx
    from adapters.proxy import server as proxy_server

    def factory():
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(proxy_server, "_upstream_client", factory)


def test_codex_backend_responses_passthrough_streams_and_captures(client, monkeypatch):
    import httpx

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["account"] = request.headers.get("chatgpt-account-id")
        return httpx.Response(200, content=_codex_like_sse(), headers={"content-type": "text/event-stream"})

    _install_mock_upstream(monkeypatch, handler)

    payload = {
        "model": "gpt-5-codex",
        "stream": True,
        "prompt_cache_key": "thread_abc",
        "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Summarize the behavior contract"}]}],
        "tools": [{"type": "function", "name": "shell"}],
    }
    headers = {"Authorization": "Bearer chatgpt-token", "chatgpt-account-id": "acct_1", "originator": "codex_cli_rs"}

    response = client.post("/backend-api/codex/responses", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.headers["X-OpenWorkflow-Response-Mode"] == "passthrough"
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.content == _codex_like_sse()  # relayed byte-for-byte
    assert seen["url"].endswith("/backend-api/codex/responses")
    assert seen["auth"] == "Bearer chatgpt-token"
    assert seen["account"] == "acct_1"

    interceptor = active_interceptors["thread_abc"]
    assert interceptor.source_agent == "codex_cli_rs"
    assert len(interceptor.steps) == 1
    step = interceptor.steps[0]
    assert step.action == "shell_cat"
    assert step.input["content"] == "Summarize the behavior contract"
    assert step.output["tool_calls"][0]["name"] == "shell"
    assert step.token_usage.prompt_tokens == 300
    assert interceptor.completion_tokens_accumulated == 25


def test_v1_responses_passthrough_non_streaming_json(client, monkeypatch):
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).endswith("/v1/responses")
        return httpx.Response(200, json={
            "id": "resp_json",
            "object": "response",
            "status": "completed",
            "output": [{"type": "message", "role": "assistant",
                        "content": [{"type": "output_text", "text": "pong"}]}],
            "usage": {"input_tokens": 10, "output_tokens": 1, "total_tokens": 11},
        })

    _install_mock_upstream(monkeypatch, handler)

    response = client.post(
        "/v1/responses",
        json={"model": "gpt-5", "input": "ping"},
        headers={"X-OpenWorkflow-Run-ID": "run_json"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == "resp_json"
    step = active_interceptors["run_json"].steps[0]
    assert step.action == "respond"
    assert step.input == {"content": "ping"}
    assert step.output["content"] == "pong"


def test_passthrough_reports_upstream_failure_as_502(client, monkeypatch):
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("upstream down")

    _install_mock_upstream(monkeypatch, handler)
    response = client.post("/v1/responses", json={"model": "gpt-5", "input": "ping"})
    assert response.status_code == 502
    assert active_interceptors == {} or all(len(i.steps) == 0 for i in active_interceptors.values())


def test_codex_session_compiles_into_distinct_shell_actions(client, monkeypatch):
    """Several Codex turns in one thread become separate workflow actions."""
    import httpx

    commands = iter(["ls examples/customer-renewal", "cat examples/customer-renewal/work.yaml", None])

    def handler(request: httpx.Request) -> httpx.Response:
        cmd = next(commands)
        if cmd is None:
            return httpx.Response(200, content=_codex_like_sse("resp_final", tool_call=False),
                                  headers={"content-type": "text/event-stream"})
        output = [{"type": "function_call", "call_id": "c", "name": "shell",
                   "arguments": json.dumps({"command": ["bash", "-lc", cmd]})}]
        body = _sse([{"type": "response.completed", "response": {"id": "r", "status": "completed", "output": output,
                                                                  "usage": {"input_tokens": 1, "output_tokens": 1}}}])
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    _install_mock_upstream(monkeypatch, handler)
    for _ in range(3):
        client.post("/backend-api/codex/responses",
                    json={"model": "gpt-5-codex", "stream": True, "input": "Review the renewal example"},
                    headers={"session_id": "codex-thread-1"})

    traces = client.get("/v1/workcompiler/traces").json()["traces"]
    assert traces[0]["run_id"] == "codex-thread-1" and traces[0]["steps_count"] == 3

    compiled = client.post("/v1/workcompiler/compile", json={"run_id": "codex-thread-1", "target_name": "codex-review"}).json()
    assert compiled["status"] == "compiled"
    assert compiled["actions"][:2] == ["shell_ls", "shell_cat"]
    assert "respond" in compiled["actions"]


def test_codex_code_mode_custom_tool_call_is_captured_as_shell_action():
    """Codex 'code mode' issues custom_tool_call items whose input is a JS exec_command snippet."""
    interceptor = TrajectoryInterceptor(run_id="code_mode")
    response = {
        "id": "resp_cm",
        "status": "completed",
        "output": [
            {"type": "reasoning", "summary": []},
            {
                "type": "custom_tool_call",
                "name": "exec",
                "call_id": "call_1",
                "input": 'const r = await tools.exec_command({cmd:"ls && sed -n \'1,40p\' work.yaml","workdir":"/repo"});\ntext(r.output);\n',
            },
        ],
        "usage": {"input_tokens": 50, "output_tokens": 5},
    }
    step = interceptor.intercept_responses_request_response({"input": "Read work.yaml"}, response)
    assert step.action == "shell_ls"
    assert step.input["cmd"].startswith("ls && sed")
    assert step.output["tool_calls"][0]["name"] == "exec"


@pytest.mark.parametrize("snippet,expected_prefix", [
    ('tools.exec_command({cmd:"ls -la", workdir:"/x"})', "ls"),
    ('tools.exec_command({ "cmd": "python3 -m core.openworklang compile a.work", "workdir": "/x" })', "python3"),
    ("tools.exec_command({ workdir: '/x', cmd: 'curl -s localhost:8787/v1/workcompiler/traces | jq' })", "curl"),
    ('tools.exec_command({cmd: `curl -s -X POST localhost:8787/x -d \'{"run_id":"a"}\' | jq \'{status}\'`, yield_time_ms: 1})', "curl"),
])
def test_code_mode_command_extraction_handles_quote_styles(snippet, expected_prefix):
    from adapters.proxy.interceptor import _code_mode_command, _shell_program

    assert _code_mode_command(snippet).startswith(expected_prefix)
    assert _shell_program({"raw_args": snippet}) == expected_prefix


def test_looping_agent_session_compiles_without_dependency_cycle(client, monkeypatch):
    """shell -> shell -> respond -> shell (a typical Codex loop) must not raise a DAG cycle."""
    import httpx

    cmds = iter(["python3 -m core.openworklang compile a.work", "sed -n '1,25p' build/a.work.yaml", None,
                 "curl -s localhost:8787/v1/workcompiler/traces", None])

    def handler(request: httpx.Request) -> httpx.Response:
        cmd = next(cmds)
        if cmd is None:
            output = [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "ok"}]}]
        else:
            output = [{"type": "custom_tool_call", "name": "exec", "call_id": "c",
                       "input": f'await tools.exec_command({{ "cmd": {json.dumps(cmd)}, "workdir": "/r" }})'}]
        body = _sse([{"type": "response.output_item.done", "item": output[0]},
                     {"type": "response.completed", "response": {"id": "r", "status": "completed", "output": [],
                                                                  "usage": {"input_tokens": 1, "output_tokens": 1}}}])
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    _install_mock_upstream(monkeypatch, handler)
    for _ in range(5):
        client.post("/backend-api/codex/responses", json={"model": "gpt-5-codex", "stream": True, "input": "go"},
                    headers={"session_id": "loop-thread"})

    traces = client.get("/v1/workcompiler/traces").json()["traces"][0]
    assert traces["actions"] == ["shell_python3", "shell_sed", "respond", "shell_curl", "respond"]

    compiled = client.post("/v1/workcompiler/compile", json={"run_id": "loop-thread", "target_name": "codex-session"})
    assert compiled.status_code == 200, compiled.text
    body = compiled.json()
    assert body["actions"] == ["shell_python3", "shell_sed", "respond", "shell_curl"]
    assert body["build"] is None
    # recorded shell commands lower to replayable code handlers
    assert body["executors_summary"]["shell_python3"] == "code"
    deps = body["work_ir"]["dependencies"]
    assert deps["respond"] == ["shell_sed"]
    assert deps["shell_curl"] == ["respond"]
    assert "respond" not in deps.get("shell_python3", [])


def test_compile_emits_build_tree_when_build_dir_given(client, monkeypatch, tmp_path):
    import httpx
    from adapters.proxy import server as proxy_server

    monkeypatch.setenv("OPENWORKFLOW_WORKSPACE_DIR", str(tmp_path))

    def handler(request: httpx.Request) -> httpx.Response:
        output = [{"type": "custom_tool_call", "name": "exec", "call_id": "c",
                   "input": 'await tools.exec_command({ "cmd": "ls examples", "workdir": "/r" })'}]
        body = _sse([{"type": "response.output_item.done", "item": output[0]},
                     {"type": "response.completed", "response": {"id": "r", "status": "completed", "output": [],
                                                                  "usage": {"input_tokens": 1, "output_tokens": 1}}}])
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    _install_mock_upstream(monkeypatch, handler)
    client.post("/backend-api/codex/responses", json={"model": "gpt-5-codex", "stream": True, "input": "go"},
                headers={"session_id": "build-thread"})

    compiled = client.post("/v1/workcompiler/compile",
                           json={"run_id": "build-thread", "target_name": "ls-bot", "build_dir": "build"})
    assert compiled.status_code == 200, compiled.text
    build = compiled.json()["build"]
    assert build["by_tier"]["code"] == ["handlers/shell_ls.py"]
    handler_py = (tmp_path / "build" / "ls_bot" / "handlers" / "shell_ls.py").read_text()
    assert "COMMANDS = ['ls examples']" in handler_py

    # build_dir must stay inside the workspace
    escaped = client.post("/v1/workcompiler/compile",
                          json={"run_id": "build-thread", "target_name": "ls-bot", "build_dir": "../outside"})
    assert escaped.status_code == 403


def test_tool_outputs_from_next_request_are_attached_to_the_calling_step():
    interceptor = TrajectoryInterceptor(run_id="tool-results")
    call = {"type": "custom_tool_call", "name": "exec", "call_id": "call_9",
            "input": 'await tools.exec_command({ "cmd": "ls examples", "workdir": "/r" })'}
    interceptor.intercept_responses_request_response(
        {"input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "list"}]}]},
        {"id": "r1", "status": "completed", "output": [call], "usage": {"input_tokens": 10, "output_tokens": 2}},
        duration_ms=1200.0,
    )
    interceptor.intercept_responses_request_response(
        {"input": [{"type": "custom_tool_call_output", "call_id": "call_9", "output": "demo\nquality_analysis.work\n"}]},
        {"id": "r2", "status": "completed",
         "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "two files"}]}],
         "usage": {"input_tokens": 12, "output_tokens": 3}},
        duration_ms=800.0,
    )
    first, second = interceptor.steps
    assert first.action == "shell_ls"
    assert first.output["tool_result"] == "demo\nquality_analysis.work\n"
    assert first.output["tool_calls"][0]["result"] == first.output["tool_result"]
    assert second.action == "respond" and "tool_result" not in second.output


def test_codex_code_mode_tool_output_envelope_is_unwrapped():
    from core.work_ir import normalize_tool_output

    envelope = [
        {"type": "input_text", "text": "Script completed\nWall time 0.2 seconds\nOutput:\n"},
        {"type": "input_text", "text": json.dumps({"chunk_id": "e1f6", "exit_code": 0, "output": "line1\nline2\n"})},
    ]
    assert normalize_tool_output(envelope) == "line1\nline2\n"
    assert normalize_tool_output("plain stdout") == "plain stdout"
    assert normalize_tool_output("Script completed\nOutput:\nraw") == "raw"


def test_batched_code_mode_calls_record_every_command_and_concatenate_results():
    from adapters.proxy.interceptor import _shell_program
    from core.work_ir import normalize_tool_output

    snippet = ('const a = await tools.exec_command({cmd:"find build -type f | sort"});\n'
               'const b = await tools.exec_command({cmd:"sed -n \'1,5p\' build/work.yaml"});\n'
               'text(a.output + b.output);')
    args = {"raw_args": snippet}
    assert _shell_program(args) == "find"
    assert args["cmds"] == ["find build -type f | sort", "sed -n '1,5p' build/work.yaml"]

    envelope = [{"type": "input_text", "text": (
        "---RESULT 1---\n" + json.dumps({"chunk_id": "a", "exit_code": 0, "output": "x\ny\n"}) + "\n"
        "---RESULT 2---\n" + json.dumps({"chunk_id": "b", "exit_code": 0, "output": "work: w\n"}))}]
    assert normalize_tool_output(envelope) == "x\ny\nwork: w\n"


def test_concatenated_code_mode_chunks_without_markers_are_unwrapped():
    from core.work_ir import normalize_tool_output

    chunks = json.dumps({"chunk_id": "a", "output": "one\n"}) + json.dumps({"chunk_id": "b", "output": "two\n"})
    envelope = [{"type": "input_text", "text": "Script completed\nOutput:\n"}, {"type": "input_text", "text": chunks}]
    assert normalize_tool_output(envelope) == "one\ntwo\n"
