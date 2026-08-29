# adapters/proxy

OpenWorkCompiler Zero-Code Agent Proxy Adapter (LLM API & MCP Interceptor).

Inspired by transparent proxy architectures like `opencodex`, this adapter intercepts standard LLM API traffic (`/v1/responses`, the ChatGPT Codex backend, `/v1/chat/completions`, `/v1/messages`) between any existing AI agent (Codex CLI, Claude Code, Cursor, AutoGen, LangChain, CrewAI) and LLM providers.

## Modes

| Endpoint | Mode | Notes |
| :--- | :--- | :--- |
| `POST /v1/responses` | passthrough → `$OPENAI_UPSTREAM_URL/responses` (default `https://api.openai.com/v1`) | OpenAI Responses API clients (SDK, Agents SDK). Streaming SSE is relayed byte-for-byte. |
| `POST /backend-api/codex/responses` (+ any `/backend-api/codex/*`) | passthrough → `$CHATGPT_CODEX_UPSTREAM_URL` (default `https://chatgpt.com/backend-api/codex`) | Codex CLI signed in with a ChatGPT account. Auth headers are forwarded untouched. |
| `POST /v1/chat/completions`, `POST /v1/messages` | synthetic (`X-OpenWorkCompiler-Response-Mode: synthetic`) | Development/demo only. |

Passthrough turns are grouped into one trajectory per agent conversation using, in order: the
`X-OpenWorkCompiler-Run-ID` header, Codex's `session_id` / `conversation_id` headers, or the payload's
`prompt_cache_key`. Codex "code mode" tool calls (`custom_tool_call` → `tools.exec_command({cmd: ...})`)
are unwrapped so each shell step becomes a distinct action such as `shell_sed` or `shell_rg`.

### Codex CLI quick start

```toml
# ~/.codex/config.toml (or a dedicated CODEX_HOME with auth.json copied in)
model_provider = "openworkcompiler"

[model_providers.openworkcompiler]
name = "OpenWorkCompiler Proxy"
base_url = "http://127.0.0.1:8787/backend-api/codex"
wire_api = "responses"
requires_openai_auth = true
```

```bash
python3 -m uvicorn adapters.proxy.server:app --port 8787 &
codex                                                   # use it normally
curl -s localhost:8787/v1/workcompiler/traces | jq       # captured sessions + actions
curl -s localhost:8787/v1/workcompiler/traces/<run_id>   # full TraceIR (add ?include_raw=true for raw payloads)
curl -s -X POST localhost:8787/v1/workcompiler/compile -H 'Content-Type: application/json' \
  -d '{"run_id":"<run_id>","target_name":"my-work","build_dir":"build"}'   # -> build/my_work/ (work.yaml, handlers/, rules/, models/, prompts/)
```

Inside the Codex TUI the same operations are available as repository skills (`.agents/skills/`):
`$ow-compile-work <file.work>`, `$ow-traces`, `$ow-compile-trace <target>`, `$ow-bench <target>`.
Tool results that the agent feeds back (`*_call_output` items) are attached to the calling step as
`tool_result`, so a compiled build can be benchmarked against what the agent actually observed.

A real recording of this flow lives in `docs/demo/openworkcompiler-codex-demo.gif`
(regenerate with `vhs docs/demo/openworkcompiler-codex-demo.tape`).

## Key Capabilities

1. **Zero Agent Code Modification**: Existing agents simply set `OPENAI_BASE_URL=http://localhost:8787/v1` (or point Codex's model provider at the proxy, see above).
2. **Transparent Trajectory Capture**: Automatically records prompts, tool calls, tool outputs, and reasoning steps, streaming them into **Trace IR**.
3. **Instant Work Compilation**: Feeds recorded trajectories into the OpenWorkCompiler kernel for automated `Work IR` (`work.yaml`) compilation upon task approval.
