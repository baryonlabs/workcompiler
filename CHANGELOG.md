# Changelog

## Unreleased

- **Cache freshness**: every cache entry now stores a fingerprint of the upstream step outputs it was computed from; a run whose replayed code outputs differ (the CRM record changed, the policy was replaced) skips the entry as *stale* and escalates again, noting why in the report. `owc build run --no-cache` bypasses the cache; `owc build cache list|clear <build> [--action a]` inspects and prunes it. Entries written before v0.5.1 carry no fingerprint and stay valid until refreshed.

## Unreleased

- **Training loop, measured** (`core/build/dataset.py`, `owc build dataset|train|fleet-eval`): a fleet corpus generator scales a work to 300 deterministic, policy-true cases; datasets merge the recorded trace + cache entries (every escalation is a training example) + fleet truth using the runtime's own prompt builders; `train` runs mlx-lm LoRA locally (`--mask-prompt`, tuned defaults) and the same dataset trains on CUDA via TRL/QLoRA; `fleet-eval` scores any candidate on pinned held-out customers with the promotion gate. Cache entries now store their upstream context.
- **Replicated negative result** (kept in `examples/demo/customer-renewal-bench/slm-training/`): SFT (3b/7b × 24/300 examples, up to 99.4% token accuracy) fixes format and lookup patterns completely but does not generalize multi-step arithmetic — held-out gate 0/6 in every configuration, with the residual errors being exactly the computed numbers (e.g. one large-number mean). Derivation steps therefore lower to the code tier or the escalate-once cache, never to an SLM; restatement (`respond`) needs no training at all (raw 3b 6/6 held-out).
- **Organizational decision catalog** (`examples/org/`): 34 decision cases across 10 departments (영업 할인 승인, 재무 경비/연장/예산, CS 환불/보상/티어링, 인사, 구매, 법무, IT운영, 마케팅, 물류, 보안, 경영지원, 제품/품질) defined declaratively — per case an `ontology` (entities/relations), ordered policy `rules` in a tiny condition DSL, deliberate `defer: slm_recommend` bands (AI recommends inside declared bounds, a named `route:` approves), and an escalate-don't-guess `fallback`. One generic engine turns the catalog into a deterministic corpus of 3,400 labeled judgments with cited rules and rationale — "판단하는 방법"을 실행 가능한 자산으로 (데이터 → 온톨로지 → 의사결정 → 실행 → 결과 학습).
- Demo GIF condensed with mpdecimate (487 s → ~67 s viewing; vhs cannot wait on the Codex alt-screen).

## v0.5.0 — 2026-08-31

Escalate once, replay forever — and a gate honest enough to refuse.

- **Escalate once, replay forever** (`core/build/cache.py`): a successful escalation or SLM result of a run is cached inside the build keyed by the bound parameters (files a derivation step wrote are captured too); a later run with the same parameters replays it locally. Measured on the promoted customer-renewal build for CUST-1002: cold run 184,454 tokens · 58.9 s (Claude writes the files once, the SLM answers) → **repeat run 0 LLM tokens · 0.1 s**, all 8 steps local (6 code + 2 cache), deliverables identical.
- **Derivation (file-writing) steps on the SLM tier, gated** (`slm.execute_files` / `gate_files`): the model regenerates the recorded files for new parameters from a masked template; the gate checks the file set, JSON key tree, parameter substitution, mined arithmetic identities (a+b, a−b, a×b, %, ×12) and **sibling-pair grounding** — number pairs that were jointly grounded in the recording (a discount band's min-seats↔pct) must co-occur in this run's inputs, which catches a wrong band choice that every self-consistency check would pass. `owc build promote <build> <action>` evaluates derivation steps by exact reproduction of the recorded files.
- Honest negative result, kept as evidence in `models/slm/write_pricing_cust_1001/PROMOTION.md`: qwen2.5:7b chose the wrong discount band and qwen2.5:14b invented a rounding detail, so the write step's promotion was **refused** by the gate — derivations stay with the agent (escalated once, then cached); restatement steps (`respond`) stay promoted.
- `bind_parameters` now keeps explicit `--param` values that have no PARAMS.json entry.

## v0.4.1 — 2026-08-30

- `ow-promote` skill (`$ow-promote <target> <action> [model]` in Codex, `/ow-promote` in Claude Code) and the README demo re-recorded with the pipx 0.4.0 install: `$ow-bench` → `$ow-promote codex-session respond qwen2.5:7b` (gate PASS 2/2, PROMOTED) → `$ow-bench` again with `respond` on the local SLM — 147,288 → 6,551 tokens (−95.6%), 3.4×, zero frontier escalations. `ow-bench` now points at `$ow-promote` for steps still on the frontier LLM.

## v0.4.0 — 2026-08-30

The last tier, measured — a frontier-LLM step promoted to a local small model under a deterministic quality gate.

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
