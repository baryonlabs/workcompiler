from __future__ import annotations

"""OpenWorkflow Zero-Code Agent Proxy Server.

FastAPI / Uvicorn async HTTP reverse proxy intercepting OpenAI (/v1/chat/completions)
and Anthropic (/v1/messages) traffic to capture trajectories and compile WorkIR.
"""

import os
import json
import glob
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request, Header, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from starlette.responses import Response

from adapters.proxy.interceptor import TrajectoryInterceptor
from adapters.agentbehavior import parse_behavior_md
from core.compiler import WorkCompiler
from core.work_ir import save_work_ir, WorkIR

app = FastAPI(
    title="OpenWorkflow Zero-Code Agent Proxy",
    version="4.0.0",
    description="Transparent reverse proxy converting standard LLM API calls into compiled WorkIR workflows.",
)

# Active session interceptors indexed by session run_id
active_interceptors: Dict[str, TrajectoryInterceptor] = {}
compiled_workflows_history: Dict[str, Dict[str, Any]] = {}

UPSTREAM_OPENAI_URL = os.getenv("OPENAI_UPSTREAM_URL", "https://api.openai.com/v1")
UPSTREAM_ANTHROPIC_URL = os.getenv("ANTHROPIC_UPSTREAM_URL", "https://api.anthropic.com/v1")


def _workspace_root() -> Path:
    """Return the only directory the proxy may write compiled workflows into."""
    return Path(os.getenv("OPENWORKFLOW_WORKSPACE_DIR", os.getcwd())).resolve()


def _workspace_output_path(output_path: Any) -> Path:
    """Resolve an output path and reject paths outside the configured workspace."""
    if not isinstance(output_path, str) or not output_path.strip():
        raise HTTPException(status_code=422, detail="output_path must be a non-empty string.")

    workspace = _workspace_root()
    candidate = Path(output_path)
    resolved = (workspace / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    try:
        resolved.relative_to(workspace)
    except ValueError as exc:
        raise HTTPException(
            status_code=403,
            detail="output_path must resolve inside OPENWORKFLOW_WORKSPACE_DIR.",
        ) from exc
    return resolved


async def _json_object(request: Request) -> Dict[str, Any]:
    """Parse a JSON object, returning a client error instead of a server error."""
    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Request body must contain valid JSON.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Request JSON body must be an object.")
    return payload


def _synthetic_headers() -> Dict[str, str]:
    """Make the development-only synthetic response mode visible to callers."""
    return {"X-OpenWorkflow-Response-Mode": "synthetic"}


def discover_behavior_contracts(workspace_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Auto-scan local workspace for BEHAVIOR.md specifications."""
    search_paths = []
    if workspace_dir:
        search_paths.append(os.path.join(workspace_dir, "**", "BEHAVIOR.md"))
    
    # Standard workspace search paths
    search_paths.extend([
        os.path.join(os.getcwd(), ".agents", "behaviors", "**", "BEHAVIOR.md"),
        os.path.join(os.getcwd(), "behaviors", "**", "BEHAVIOR.md"),
        os.path.join(os.getcwd(), "examples", "**", "BEHAVIOR.md"),
    ])

    discovered_behaviors: List[Dict[str, Any]] = []
    seen_names = set()

    for pattern in search_paths:
        for filepath in glob.glob(pattern, recursive=True):
            try:
                content = Path(filepath).read_text(encoding="utf-8")
                behavior_dict = parse_behavior_md(content)
                name = behavior_dict.get("name")
                if name and name not in seen_names:
                    seen_names.add(name)
                    behavior_dict["_filepath"] = filepath
                    discovered_behaviors.append(behavior_dict)
            except Exception:
                continue

    return discovered_behaviors


def get_or_create_interceptor(
    run_id: Optional[str] = None,
    source_agent: str = "zero-code-proxy"
) -> TrajectoryInterceptor:
    """Retrieve existing session interceptor or create a new session."""
    session_id = run_id or f"session_{time.strftime('%Y%m%d_%H%M%S')}"
    if session_id not in active_interceptors:
        active_interceptors[session_id] = TrajectoryInterceptor(
            run_id=session_id, source_agent=source_agent
        )
    return active_interceptors[session_id]


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Healthcheck endpoint."""
    return {
        "status": "healthy",
        "active_sessions": len(active_interceptors),
        "compiled_workflows": len(compiled_workflows_history),
    }


@app.get("/v1/workcompiler/traces")
async def list_intercepted_traces() -> Dict[str, Any]:
    """List active and finalized intercepted trajectory sessions."""
    traces_summary = []
    for run_id, interceptor in active_interceptors.items():
        traces_summary.append({
            "run_id": run_id,
            "source_agent": interceptor.source_agent,
            "steps_count": len(interceptor.steps),
            "prompt_tokens": interceptor.prompt_tokens_accumulated,
            "completion_tokens": interceptor.completion_tokens_accumulated,
        })
    return {"traces": traces_summary}


@app.post("/v1/workcompiler/compile")
async def trigger_work_compilation(
    request: Request,
    x_openworkflow_behavior: Optional[str] = Header(None, alias="X-OpenWorkflow-Behavior"),
) -> Dict[str, Any]:
    """Dual-Trigger: Compile intercepted trajectory into WorkIR (work.yaml)."""
    request_data = await _json_object(request)
    run_id = request_data.get("run_id")
    target_name = request_data.get("target_name", "compiled-proxy-work")

    if not run_id or run_id not in active_interceptors:
        if active_interceptors:
            run_id = list(active_interceptors.keys())[-1]
        else:
            raise HTTPException(status_code=400, detail="No active trajectory session available to compile.")

    interceptor = active_interceptors[run_id]
    trace_ir = interceptor.finalize_trace(status="success")

    # Discover behaviors from workspace + custom header
    behaviors = discover_behavior_contracts()
    if x_openworkflow_behavior:
        behaviors.append(parse_behavior_md(x_openworkflow_behavior))

    # Trigger WorkCompiler
    compiler = WorkCompiler()
    work_ir = compiler.compile_traces_to_work_ir(
        traces=[trace_ir],
        behaviors=behaviors,
        target_name=target_name
    )

    compiled_dict = work_ir.to_dict()
    compiled_workflows_history[target_name] = compiled_dict

    # Optionally save to disk if output_path is provided
    output_path = request_data.get("output_path")
    if output_path:
        save_work_ir(work_ir, _workspace_output_path(output_path))

    return {
        "status": "compiled",
        "work_name": work_ir.work,
        "actions_count": len(work_ir.actions),
        "actions": work_ir.actions,
        "executors_summary": {act: cfg.type.value for act, cfg in work_ir.executors.items()},
        "work_ir": compiled_dict,
    }


@app.post("/v1/chat/completions")
async def proxy_openai_chat_completions(
    request: Request,
    x_openworkflow_run_id: Optional[str] = Header(None, alias="X-OpenWorkflow-Run-ID"),
    x_openworkflow_behavior: Optional[str] = Header(None, alias="X-OpenWorkflow-Behavior"),
) -> JSONResponse:
    """Reverse proxy interceptor for OpenAI /v1/chat/completions."""
    payload = await _json_object(request)
    start_time = time.perf_counter()

    interceptor = get_or_create_interceptor(
        run_id=x_openworkflow_run_id,
        source_agent=request.headers.get("user-agent", "openai-client")
    )

    # For mock/demonstration or local passthrough without live upstream API key:
    # Build synthetic compliant response if upstream API call is simulated
    model = payload.get("model", "gpt-4o")
    messages = payload.get("messages", [])

    # Check if tool calls exist in request
    tools = payload.get("tools", [])
    action_name = "call_llm"
    tool_args = {}

    if tools and isinstance(tools, list):
        first_fn = tools[0].get("function", {})
        action_name = first_fn.get("name", "tool_call")

    synthetic_response = {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": f"Intercepted response for action '{action_name}'",
                    "tool_calls": [
                        {
                            "id": f"call_{uuid.uuid4().hex[:8]}",
                            "type": "function",
                            "function": {
                                "name": action_name,
                                "arguments": json.dumps({"status": "ok", "action": action_name})
                            }
                        }
                    ] if tools else None
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 45,
            "total_tokens": 165
        }
    }

    duration_ms = (time.perf_counter() - start_time) * 1000.0
    interceptor.intercept_openai_request_response(payload, synthetic_response, duration_ms=duration_ms)

    return JSONResponse(content=synthetic_response, headers=_synthetic_headers())


@app.post("/v1/messages")
async def proxy_anthropic_messages(
    request: Request,
    x_openworkflow_run_id: Optional[str] = Header(None, alias="X-OpenWorkflow-Run-ID"),
    x_openworkflow_behavior: Optional[str] = Header(None, alias="X-OpenWorkflow-Behavior"),
) -> JSONResponse:
    """Reverse proxy interceptor for Anthropic /v1/messages."""
    payload = await _json_object(request)
    start_time = time.perf_counter()

    interceptor = get_or_create_interceptor(
        run_id=x_openworkflow_run_id,
        source_agent=request.headers.get("user-agent", "anthropic-client")
    )

    model = payload.get("model", "claude-3-5-sonnet-20241022")
    tools = payload.get("tools", [])
    action_name = "call_llm"

    if tools and isinstance(tools, list):
        action_name = tools[0].get("name", "tool_use")

    synthetic_response = {
        "id": f"msg_{uuid.uuid4().hex[:12]}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [
            {
                "type": "text",
                "text": f"Intercepted Anthropic response for action '{action_name}'"
            },
            {
                "type": "tool_use",
                "id": f"toolu_{uuid.uuid4().hex[:8]}",
                "name": action_name,
                "input": {"status": "ok", "action": action_name}
            } if tools else None
        ],
        "stop_reason": "tool_use" if tools else "end_turn",
        "usage": {
            "input_tokens": 140,
            "output_tokens": 60
        }
    }

    # Clean null content blocks if no tools
    synthetic_response["content"] = [c for c in synthetic_response["content"] if c is not None]

    duration_ms = (time.perf_counter() - start_time) * 1000.0
    interceptor.intercept_anthropic_request_response(payload, synthetic_response, duration_ms=duration_ms)

    return JSONResponse(content=synthetic_response, headers=_synthetic_headers())
