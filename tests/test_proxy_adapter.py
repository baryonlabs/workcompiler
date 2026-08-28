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
