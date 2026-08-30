# Changelog

## Unreleased

- **SLM tier is real** (`core/build/slm.py`): `owc build promote <build> <action> [--model qwen2.5:7b]` runs a small local model (any OpenAI-compatible endpoint; Ollama by default, `OPENWORKCOMPILER_SLM_BASE_URL` / `OPENWORKCOMPILER_SLM_MODEL`) on the action's recorded examples with the compiled upstream outputs as context and a *masked* recorded example for style, gates the output deterministically (anchor-fact recall, grounding precision — no numbers/ids/paths that exist nowhere in the inputs —, length, placeholder, fact density), folds each evaluation into a `QualityRecord` and lets `ExecutorOptimizer.evaluate_promotion` decide. On pass it flips the executor in `work.yaml` and the `.work` source (`respond: slm`), writes `models/slm/<action>/{runtime.json, promotion.json, PROMOTION.md, quality_records.jsonl}`; `owc build demote` rolls back.
- `owc build bench` executes promoted SLM steps for real (server-reported tokens, latency, gate verdict as the match; per-model ledger separates the SLM from the frontier model); `owc build run` runs them before any agent escalation and falls back to the agent when the gate fails; the runtime loader gives `SLMExecutor` a real inference handler.
- Measured: customer-renewal `respond` promoted to `qwen2.5:7b` (3b failed the gate — it left placeholders) → full build **−97.0% tokens** (139,437 → 4,208), 4.8×, 8/8 outputs, 0 escalated actions; codex-session `respond` promoted to `qwen2.5:3b` → −94.8%; hybrid CUST-1002 with `respond` on the SLM: identical pricing, respond 4,205 tokens at $0 (`examples/demo/customer-renewal-bench/hybrid-CUST-1002-slm/`).

## v0.3.0 — 2026-08-29

One compiler, many agents — Claude Code and OpenAI-compatible agents join Codex on both sides of the loop.

- **Multi-agent support.** The proxy now captures **Claude Code** (`/v1/messages` passthrough, `ANTHROPIC_BASE_URL`, API key or subscription login; session id from `metadata.user_id`, `tool_result` blocks attached, side calls counted as `aux_tokens`) and **OpenAI-compatible agents** (`/v1/chat/completions` passthrough for Cursor / Windsurf / opencode / Aider / SDKs; `role: tool` results attached) next to Codex; a catch-all route forwards every other path to the matching upstream. Synthetic responses now require `X-OpenWorkCompiler-Response-Mode: synthetic`.
- **One tool vocabulary** (`adapters/proxy/tools.py`): `Bash`/`exec_command`/`run_terminal_cmd` → `shell_<prog>`, `Write`/`Edit`/`MultiEdit`/`apply_patch` → `write_<stem>` with V4A patch text (`core/work_ir/patchfmt.py`: Add / Update hunks incl. `replace_all` / Delete, `already_applied` on replay), `Read`/`Glob`/`Grep` → replayable `cat`/`find`/`grep`, bookkeeping tools → `plan`. `source_agent` + `agent_version` + protocol recorded in provenance.
- **Agent backends** (`core/agents/`): `claude`, `codex`, `gemini` (escalation only), `opencode`, `aider` behind one `AgentBackend` interface; `owc build run … --escalate auto|claude|codex|…` (`auto` = `OWC_AGENT` → the agent that recorded the trace → first installed), `--binder agent`, `--model`; `owc agent list|doctor|setup <name>|exec`.
- **Skills for every agent**: `.agents/skills/` stays the only committed copy; `owc skills install --agent claude|gemini|opencode|all [--link]` syncs it into each agent's directory, `owc skills doctor --check` reports drift (CI runs it). Skill bodies are agent-neutral (`$ow-x` in Codex, `/ow-x` in Claude Code).
- Cross-agent proof: `examples/demo/customer-renewal-bench/hybrid-CUST-1002-claude/` — a build captured from Codex, re-run for CUST-1002 with Claude Code as the escalation backend.
- **Rename**: OpenWorkflow → **OpenWorkCompiler** (package `openworkcompiler`, `X-OpenWorkCompiler-*` headers, `OPENWORKCOMPILER_*` env vars, demo assets). Recorded transcripts/traces kept verbatim.
- **OpenWorkLang split out** into [baryonlabs/openworklang](https://github.com/baryonlabs/openworklang) (pure `.work` parser/compiler → Work IR dict + LinkML, CLI, spec, tests), vendored as the `vendor/openworklang` submodule; `core/openworklang` is now a thin adapter.
- GitHub Pages landing page (`docs/index.html`, SEO metadata, sitemap), repository About/topics.
- LICENSE (MIT, © Baryon Labs, Seungwoo Hong), CONTRIBUTING.md (DCO), reference-papers section, adoption-case call (hello@baryon.ai).
- **Telemetry**: OpenTelemetry-style spans (proxy turns, compiles, bench/run steps, CLIs), on by default, local JSONL by default, OTLP via the `telemetry` extra; `docs/TELEMETRY.md` documents the opt-out.
- `owc` console script (`pipx install git+https://github.com/baryonlabs/workcompiler.git`): proxy · compile · build (from-trace / bench / run); openworklang declared as a git dependency.
- OSS hygiene: CI (GitHub Actions, Python 3.10–3.13), issue/PR templates, CODE_OF_CONDUCT, SECURITY, CITATION.cff, CODEOWNERS, .editorconfig, README badges, `docs/OSS-CHECKLIST.md`.

## v0.2.0 — 2026-08-29

Human-defined WHAT, compiler-defined HOW — the full loop, measured.

### Added
- **Zero-code proxy passthrough** for the OpenAI Responses API and the ChatGPT Codex backend: Codex CLI runs unmodified, every turn (model, tokens, cached tokens, tool results) is captured into TraceIR.
- **Build backend (`core/build`)**: Work IR → `build/<work>/` with per-tier assets — `handlers/*.py` (code, replays recorded shell commands and file patches), `rules/*.rule.yaml`, `models/ml|slm/<action>/` (model card, dataset, train.py / TRL training candidate), `prompts/*.prompt.md`, `PARAMS.json`, `<work>.work`, `MANIFEST.json`; runtime loader.
- **OpenWorkLang `.work` as the HOW**: every build emits an editable, recompilable source with `executors`, `params` and `escalation` limits; parser/compiler support the new sections.
- **Benchmark (`core.build bench`)**: recorded agent session vs compiled build — output equality, tokens, latency per action, plus a **per-model token ledger** (`BENCHMARK.md`, `ledger.jsonl`).
- **Front agent (`core.build run`)**: binds parameters from a new request, runs code tiers for free and escalates only synthesized / model-tier steps (Codex backend), with a `RUN_REPORT.md`.
- **Codex skills** (`.agents/skills/`): `$ow-define` (WHAT via grill-me / grilling interview), `$ow-compile-work`, `$ow-traces`, `$ow-compile-trace`, `$ow-bench`; grill-me / grilling pinned in `skills-lock.json`.
- **OpenWorkLang CLI**: `python3 -m core.openworklang compile <file.work>`.
- **Examples**: `examples/demo` (Codex TUI demo + benchmark), `examples/customer-renewal` (task, fixtures, benchmark, hybrid CUST-1002 run), `examples/cases/` — four business cases driven end-to-end from a beginner's raw materials.
- README (ko/en): human/AI role-split diagram, 30-second Codex demo, benchmarks, WHAT → HOW, beginner cases; real TUI recordings.

### Measured (see `examples/`)
- customer renewal: compiled build −85% tokens, 7.4× faster, deliverables byte-identical; new customer via front agent 2.1× faster than Codex alone.
- four beginner cases: −76…−92% tokens, 11–19× faster on replay, same decisions.

### Fixed
- Dependency cycles on looping agent trajectories; Codex code-mode batched commands, `apply_patch` and result envelopes; replay order follows the trace.
