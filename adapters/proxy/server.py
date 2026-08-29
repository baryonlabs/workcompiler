from __future__ import annotations

"""OpenWorkCompiler Zero-Code Agent Proxy Server.

FastAPI / Uvicorn async HTTP reverse proxy intercepting OpenAI (/v1/chat/completions),
OpenAI Responses API (/v1/responses — used by Codex CLI) and Anthropic (/v1/messages)
traffic to capture trajectories and compile WorkIR.

Two modes coexist:

* ``/v1/chat/completions`` and ``/v1/messages`` answer with a *synthetic* response
  (development/demo only, flagged by ``X-OpenWorkCompiler-Response-Mode: synthetic``).
* ``/v1/responses`` and ``/backend-api/codex/*`` are *transparent passthroughs*:
  the request (headers included) is forwarded to the real upstream, the SSE stream
  is relayed byte-for-byte to the client, and the completed turn is captured into
  TraceIR in the background. This is what lets Codex CLI run unmodified through
  OpenWorkCompiler (``X-OpenWorkCompiler-Response-Mode: passthrough``).
"""

import os
import json
import glob
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, Request, Header, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.responses import Response

from adapters.proxy.interceptor import TrajectoryInterceptor, responses_object_from_sse
from core.build.emitter import emit_build
from core import telemetry
from adapters.agentbehavior import parse_behavior_md
from core.compiler import WorkCompiler
from core.work_ir import save_work_ir, WorkIR

telemetry.notice("proxy")

app = FastAPI(
    title="OpenWorkCompiler Zero-Code Agent Proxy",
    version="4.0.0",
    description="Transparent reverse proxy converting standard LLM API calls into compiled WorkIR workflows.",
)

# Active session interceptors indexed by session run_id
active_interceptors: Dict[str, TrajectoryInterceptor] = {}
compiled_workflows_history: Dict[str, Dict[str, Any]] = {}

UPSTREAM_OPENAI_URL = os.getenv("OPENAI_UPSTREAM_URL", "https://api.openai.com/v1")
UPSTREAM_ANTHROPIC_URL = os.getenv("ANTHROPIC_UPSTREAM_URL", "https://api.anthropic.com/v1")
# Codex CLI with ChatGPT login talks to this backend instead of api.openai.com.
UPSTREAM_CHATGPT_CODEX_URL = os.getenv("CHATGPT_CODEX_UPSTREAM_URL", "https://chatgpt.com/backend-api/codex")
UPSTREAM_TIMEOUT_SECONDS = float(os.getenv("OPENWORKCOMPILER_UPSTREAM_TIMEOUT", "600"))

# Hop-by-hop / transport headers that must not be forwarded verbatim.
_STRIP_REQUEST_HEADERS = {"host", "content-length", "connection", "accept-encoding", "transfer-encoding"}
_STRIP_RESPONSE_HEADERS = {"content-length", "content-encoding", "transfer-encoding", "connection"}


def _workspace_root() -> Path:
    """Return the only directory the proxy may write compiled workflows into."""
    return Path(os.getenv("OPENWORKCOMPILER_WORKSPACE_DIR", os.getcwd())).resolve()


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
            detail="output_path must resolve inside OPENWORKCOMPILER_WORKSPACE_DIR.",
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
    return {"X-OpenWorkCompiler-Response-Mode": "synthetic"}


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
            "actions": [step.action for step in interceptor.steps],
            "prompt_tokens": interceptor.prompt_tokens_accumulated,
            "completion_tokens": interceptor.completion_tokens_accumulated,
        })
    return {"traces": traces_summary}


@app.get("/v1/workcompiler/traces/{run_id}")
async def get_intercepted_trace(run_id: str, include_raw: bool = False) -> Dict[str, Any]:
    """Return the TraceIR captured so far for one session (optionally with raw API payloads)."""
    interceptor = active_interceptors.get(run_id)
    if interceptor is None:
        raise HTTPException(status_code=404, detail=f"Unknown trajectory session '{run_id}'.")
    trace = interceptor.finalize_trace(status="success")
    body: Dict[str, Any] = {"trace": trace.model_dump(mode="json")}
    if include_raw:
        body["raw_requests"] = interceptor.raw_requests
        body["raw_responses"] = interceptor.raw_responses
    return body


@app.post("/v1/workcompiler/compile")
async def trigger_work_compilation(
    request: Request,
    x_openworkcompiler_behavior: Optional[str] = Header(None, alias="X-OpenWorkCompiler-Behavior"),
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
    telemetry.event("proxy.compile", run_id=run_id, target=target_name, steps=len(trace_ir.steps),
                    build_dir=bool(request_data.get("build_dir")))

    # Discover behaviors from workspace + custom header
    behaviors = discover_behavior_contracts()
    if x_openworkcompiler_behavior:
        behaviors.append(parse_behavior_md(x_openworkcompiler_behavior))

    # Trigger WorkCompiler
    compiler = WorkCompiler()
    try:
        work_ir = compiler.compile_traces_to_work_ir(
            traces=[trace_ir],
            behaviors=behaviors,
            target_name=target_name
        )
    except ValueError as exc:
        # Invalid Work IR (e.g. dependency cycle) is a client-visible compile error, not a crash.
        raise HTTPException(status_code=422, detail={"status": "error", "work_name": target_name, "error": str(exc)}) from exc

    compiled_dict = work_ir.to_dict()
    compiled_workflows_history[target_name] = compiled_dict

    # Optionally save to disk if output_path is provided
    output_path = request_data.get("output_path")
    if output_path:
        save_work_ir(work_ir, _workspace_output_path(output_path))

    # Optionally emit the full artifact tree (handlers/, rules/, models/, prompts/ ...)
    build_info: Optional[Dict[str, Any]] = None
    build_dir = request_data.get("build_dir")
    if build_dir:
        manifest = emit_build(
            work_ir,
            _workspace_output_path(build_dir),
            traces=[trace_ir],
            training_candidates=compiler.training_candidates,
        )
        build_info = {"build_dir": manifest.build_dir, "artifact_count": len(manifest.artifacts), "by_tier": manifest.by_tier()}

    return {
        "status": "compiled",
        "work_name": work_ir.work,
        "actions_count": len(work_ir.actions),
        "actions": work_ir.actions,
        "executors_summary": {act: cfg.type.value for act, cfg in work_ir.executors.items()},
        "build": build_info,
        "work_ir": compiled_dict,
    }


def _passthrough_headers() -> Dict[str, str]:
    return {"X-OpenWorkCompiler-Response-Mode": "passthrough"}


def _upstream_client() -> httpx.AsyncClient:
    """Factory for the upstream HTTP client (patched in tests with a MockTransport)."""
    return httpx.AsyncClient(timeout=httpx.Timeout(UPSTREAM_TIMEOUT_SECONDS, connect=30.0))


def _resolve_run_id(request: Request, payload: Dict[str, Any]) -> Optional[str]:
    """Group Responses API calls into one trajectory per agent conversation.

    Priority: explicit ``X-OpenWorkCompiler-Run-ID`` header → Codex ``session_id`` /
    ``conversation_id`` headers → ``prompt_cache_key`` in the payload (Codex sets it
    to the thread id) → ``previous_response_id`` chain is not stable, so fall back to a
    fresh per-process session.
    """
    for header in ("x-openworkcompiler-run-id", "session_id", "conversation_id"):
        value = request.headers.get(header)
        if value:
            return value
    cache_key = payload.get("prompt_cache_key")
    if isinstance(cache_key, str) and cache_key:
        return cache_key
    return None


def _source_agent(request: Request, default: str) -> str:
    originator = request.headers.get("originator")
    if originator:
        return originator
    return request.headers.get("user-agent", default)


async def _relay_responses_api(request: Request, upstream_url: str) -> Response:
    """Forward a Responses API call upstream, relay the (SSE) reply, capture the turn."""
    body = await request.body()
    try:
        payload = json.loads(body) if body else {}
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Request body must contain valid JSON.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Request JSON body must be an object.")

    forward_headers = {k: v for k, v in request.headers.items() if k.lower() not in _STRIP_REQUEST_HEADERS}
    interceptor = get_or_create_interceptor(
        run_id=_resolve_run_id(request, payload),
        source_agent=_source_agent(request, "openai-responses-client"),
    )

    client = _upstream_client()
    start_time = time.perf_counter()
    try:
        upstream_request = client.build_request("POST", upstream_url, content=body, headers=forward_headers)
        upstream_response = await client.send(upstream_request, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"Upstream request failed: {exc}") from exc

    response_headers = {
        k: v for k, v in upstream_response.headers.items() if k.lower() not in _STRIP_RESPONSE_HEADERS
    }
    response_headers.update(_passthrough_headers())
    content_type = upstream_response.headers.get("content-type", "")
    is_stream = "text/event-stream" in content_type or bool(payload.get("stream"))

    async def relay():
        chunks: List[bytes] = []
        try:
            async for chunk in upstream_response.aiter_bytes():
                chunks.append(chunk)
                yield chunk
        finally:
            await upstream_response.aclose()
            await client.aclose()
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            if upstream_response.status_code < 400:
                raw = b"".join(chunks).decode("utf-8", errors="replace")
                final_response: Optional[Dict[str, Any]] = None
                if is_stream:
                    final_response = responses_object_from_sse(raw)
                else:
                    try:
                        parsed = json.loads(raw)
                        final_response = parsed if isinstance(parsed, dict) else None
                    except Exception:
                        final_response = None
                if final_response is not None:
                    step = interceptor.intercept_responses_request_response(payload, final_response, duration_ms=duration_ms)
                    usage = step.token_usage
                    telemetry.event("proxy.turn", run_id=interceptor.run_id, source_agent=interceptor.source_agent,
                                    action=step.action, model=getattr(step, "model", ""),
                                    prompt_tokens=usage.prompt_tokens, completion_tokens=usage.completion_tokens,
                                    total_tokens=usage.total_tokens, cached_tokens=getattr(step, "cached_tokens", 0),
                                    latency_ms=round(duration_ms, 1), upstream_status=upstream_response.status_code)

    return StreamingResponse(
        relay(),
        status_code=upstream_response.status_code,
        headers=response_headers,
        media_type=content_type or None,
    )


@app.post("/v1/responses")
async def proxy_openai_responses(request: Request) -> Response:
    """Transparent passthrough for the OpenAI Responses API (API-key clients, Agents SDK)."""
    return await _relay_responses_api(request, f"{UPSTREAM_OPENAI_URL.rstrip('/')}/responses")


@app.post("/backend-api/codex/responses")
async def proxy_chatgpt_codex_responses(request: Request) -> Response:
    """Transparent passthrough for Codex CLI signed in with a ChatGPT account.

    Point Codex at this proxy with a custom provider::

        [model_providers.openworkcompiler]
        name = "OpenWorkCompiler Proxy"
        base_url = "http://127.0.0.1:8787/backend-api/codex"
        wire_api = "responses"
        requires_openai_auth = true
    """
    return await _relay_responses_api(request, f"{UPSTREAM_CHATGPT_CODEX_URL.rstrip('/')}/responses")


@app.api_route("/backend-api/codex/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_chatgpt_codex_other(path: str, request: Request) -> Response:
    """Forward any other Codex backend call (usage, config bundles, ...) untouched."""
    body = await request.body()
    forward_headers = {k: v for k, v in request.headers.items() if k.lower() not in _STRIP_REQUEST_HEADERS}
    url = f"{UPSTREAM_CHATGPT_CODEX_URL.rstrip('/')}/{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"
    async with _upstream_client() as client:
        try:
            upstream = await client.request(request.method, url, content=body, headers=forward_headers)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Upstream request failed: {exc}") from exc
    headers = {k: v for k, v in upstream.headers.items() if k.lower() not in _STRIP_RESPONSE_HEADERS}
    headers.update(_passthrough_headers())
    return Response(content=upstream.content, status_code=upstream.status_code, headers=headers)


@app.post("/v1/chat/completions")
async def proxy_openai_chat_completions(
    request: Request,
    x_openworkcompiler_run_id: Optional[str] = Header(None, alias="X-OpenWorkCompiler-Run-ID"),
    x_openworkcompiler_behavior: Optional[str] = Header(None, alias="X-OpenWorkCompiler-Behavior"),
) -> JSONResponse:
    """Reverse proxy interceptor for OpenAI /v1/chat/completions."""
    payload = await _json_object(request)
    start_time = time.perf_counter()

    interceptor = get_or_create_interceptor(
        run_id=x_openworkcompiler_run_id,
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
    x_openworkcompiler_run_id: Optional[str] = Header(None, alias="X-OpenWorkCompiler-Run-ID"),
    x_openworkcompiler_behavior: Optional[str] = Header(None, alias="X-OpenWorkCompiler-Behavior"),
) -> JSONResponse:
    """Reverse proxy interceptor for Anthropic /v1/messages."""
    payload = await _json_object(request)
    start_time = time.perf_counter()

    interceptor = get_or_create_interceptor(
        run_id=x_openworkcompiler_run_id,
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
