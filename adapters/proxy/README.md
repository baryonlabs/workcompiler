# adapters/proxy

OpenWorkCompiler Zero-Code Agent Proxy Adapter (LLM API & MCP Interceptor).

Inspired by transparent proxy architectures like `opencodex`, this adapter intercepts standard LLM API traffic (`/v1/responses`, the ChatGPT Codex backend, `/v1/chat/completions`, `/v1/messages`) between any existing AI agent (Codex CLI, Claude Code, Cursor, AutoGen, LangChain, CrewAI) and LLM providers.

## Modes

| Endpoint | Mode | Who speaks it |
| :--- | :--- | :--- |
| `POST /v1/responses` | passthrough → `$OPENAI_UPSTREAM_URL/responses` (default `https://api.openai.com/v1`) | OpenAI Responses API clients (SDK, Agents SDK). Streaming SSE is relayed byte-for-byte. |
| `POST /backend-api/codex/responses` (+ any `/backend-api/codex/*`) | passthrough → `$CHATGPT_CODEX_UPSTREAM_URL` (default `https://chatgpt.com/backend-api/codex`) | **Codex CLI** signed in with a ChatGPT account. Auth headers are forwarded untouched. |
| `POST /v1/messages` (+ `?beta=true`, `/v1/messages/count_tokens`, …) | passthrough → `$ANTHROPIC_UPSTREAM_URL` (default `https://api.anthropic.com`) | **Claude Code** (`ANTHROPIC_BASE_URL`, API key *or* subscription/OAuth login) and Anthropic SDK clients. |
| `POST /v1/chat/completions` | passthrough → `$OPENAI_UPSTREAM_URL/chat/completions` | **OpenAI-compatible agents** — Cursor, Windsurf, opencode, Aider, Continue, SDKs (`OPENAI_BASE_URL`). |
| anything else (`/{path}`) | passthrough to the upstream that matches the auth headers / path | model listings, `HEAD /api/hello`, token counting … nothing is dropped. |

Every passthrough route becomes a synthetic (offline) endpoint when the request carries
`X-OpenWorkCompiler-Response-Mode: synthetic` — used by the tests and demos only.

Turns are grouped into one trajectory per agent conversation using, in order: the
`X-OpenWorkCompiler-Run-ID` header, Codex's `session_id` / `conversation_id` headers, the payload's
`prompt_cache_key` (Codex), Claude Code's `metadata.user_id` session id, or a fingerprint of the
system prompt + first user message (chat clients). The originating agent is detected from the
headers (`originator: codex_cli_rs` → `codex-cli`, `user-agent: claude-cli/2.1.x` → `claude-code`,
Cursor / Windsurf / opencode / Aider user agents) and recorded as `source_agent` + `agent_version`.

Tool calls of every protocol are mapped onto one vocabulary (`adapters/proxy/tools.py`): shell
tools (`exec_command`, `Bash`, `run_terminal_cmd`, …) become `shell_<program>` steps with a
replayable `cmd`; file tools (`apply_patch`, `Write` / `Edit` / `MultiEdit`, `write_file`, …)
become `write_<stem>` steps whose `patch` is V4A-style text (`core/work_ir/patchfmt.py`);
`Read` / `Glob` / `Grep` are synthesized into `cat` / `find` / `grep` commands so the build can
replay them; bookkeeping tools (`TodoWrite`, …) are kept as `plan` steps. Tool results — Responses
`*_call_output` items, Anthropic `tool_result` blocks, chat `role: tool` messages — are attached to
the calling step as `tool_result`, so a compiled build can be benchmarked against what the agent
actually observed. Claude Code's short side calls (title/suggestion requests with no tools) are
relayed but counted as `aux_tokens` instead of steps.

### Claude Code quick start

```bash
owc proxy --port 8787 &                      # or: python3 -m uvicorn adapters.proxy.server:app --port 8787
owc skills install --agent claude            # .agents/skills → .claude/skills (/ow-define … /ow-bench)
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787
claude                                       # use it normally; every turn is captured
curl -s localhost:8787/v1/workcompiler/traces | jq   # source_agent: claude-code, actions, model, tokens
```

### OpenAI-compatible quick start (Cursor, Windsurf, opencode, Aider, SDKs)

```bash
export OPENAI_BASE_URL=http://127.0.0.1:8787/v1     # Cursor/Windsurf: Settings → Models → "Override OpenAI Base URL"
opencode run "Read examples/customer-renewal/TASK.md and carry it out."
```

`owc agent setup <claude|codex|opencode|aider>` prints the exact configuration for each agent.

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

Inside the agent's TUI the same operations are available as repository skills (`.agents/skills/`, canonical;
`owc skills install` copies them into `.claude/skills/` etc.): `$ow-compile-work <file.work>` / `/ow-compile-work …`,
`$ow-traces`, `$ow-compile-trace <target>`, `$ow-bench <target>`.

A real recording of this flow lives in `docs/demo/openworkcompiler-codex-demo.gif`
(regenerate with `vhs docs/demo/openworkcompiler-codex-demo.tape`).

## Key Capabilities

1. **Zero Agent Code Modification**: Existing agents simply set `OPENAI_BASE_URL=http://localhost:8787/v1` (or point Codex's model provider at the proxy, see above).
2. **Transparent Trajectory Capture**: Automatically records prompts, tool calls, tool outputs, and reasoning steps, streaming them into **Trace IR**.
3. **Instant Work Compilation**: Feeds recorded trajectories into the OpenWorkCompiler kernel for automated `Work IR` (`work.yaml`) compilation upon task approval.
