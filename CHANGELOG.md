# Changelog

## Unreleased

- **Rename**: OpenWorkflow → **OpenWorkCompiler** (package `openworkcompiler`, `X-OpenWorkCompiler-*` headers, `OPENWORKCOMPILER_*` env vars, demo assets). Recorded transcripts/traces kept verbatim.
- **OpenWorkLang split out** into [baryonlabs/openworklang](https://github.com/baryonlabs/openworklang) (pure `.work` parser/compiler → Work IR dict + LinkML, CLI, spec, tests), vendored as the `vendor/openworklang` submodule; `core/openworklang` is now a thin adapter.
- GitHub Pages landing page (`docs/index.html`, SEO metadata, sitemap), repository About/topics.
- LICENSE (MIT, © Baryon Labs, Seungwoo Hong), CONTRIBUTING.md (DCO), reference-papers section, adoption-case call (hello@baryon.ai).

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
