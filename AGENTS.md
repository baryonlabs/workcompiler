# AGENTS.md

Project-specific guidance for AI coding agents working on OpenWorkflow.

## Project overview

OpenWorkflow is **the execution layer for AI work**: a system that turns proven agent executions into reliable, optimized, compiled workflows.

- An agent performs work → a human approves the output → OpenWorkflow compiles the trace into deterministic workflow + rules + code + SLMs → the runtime executes it → the system measures quality and optimizes itself.
- One core phrase: **AI performs. Humans evaluate outcome quality. OpenWorkflow evaluates behavior, compiles the work, and continuously optimizes execution.**
- Full vision and architecture live in `README.md`. Read it before making design decisions.
- Behavior Contract design: `docs/behavior-contracts-v2.md` (integration of the AgentBehavior standard). Read it before making decisions that touch evaluation, compilation, or executor selection.

## Non-negotiable product principles

These constraints must survive every change. If a change violates one, flag it and explain the tradeoff instead of silently proceeding.

1. **Humans only evaluate outcome quality.** The human unit is `Input → Output → Expected quality`. Never make end users design/review workflow graphs, FSM, rules, thresholds, model routers, ontology, or event mappings.
2. **The system supervises behavior, not only outcomes.** Approved traces must satisfy their Behavior Contracts (`BEHAVIOR.md` specs). A lucky-correct result that skipped a required process is a failure, not a pass.
3. **Behavior, workflow, and executor stay separate.** Behavior is implementation-independent. Any executor swap must satisfy the same behavior contracts; behavior compliance is a mandatory gate for SLM/LLM/code promotion.
4. **Behavior specs are sparse.** Registry lifecycle is add → deduplicate → merge → generalize → retire. Keep the count healthy; do not save every instruction or tool-argument detail as a behavior.
5. **The optimization loop never blocks the execution loop.**
6. **Model count must stay healthy.** No per-workflow SLM sprawl; consolidation (merge/split/retire/promote/rollback) is a first-class backend concern.
7. **Escalate, don't duplicate.** Exceptions and quality degradation escalate to frontier LLM + human; everything else runs compiled.
8. **The loop is visible, but no one operates it.** Users see automation level / quality / cost / execution mix as outcomes, not internals.

## Repository layout

```
README.md          Product vision, loops, architecture
AGENTS.md          This file — agent instructions
agents/            Sub-agent definitions (guide + measurement fleet)
conversations/     Archived design conversations (ChatGPT share exports + assets)
docs/              Design docs, diagrams, and rendered assets
```

Behavior specs live under `workflows/<name>/behaviors/<name>/BEHAVIOR.md` once the first workflow lands (see `docs/behavior-contracts-v2.md`).

Code directories will be added as the stack lands; keep layout changes documented here.

## Before you write code

- Confirm the change only touches the layer you intend (workflow / executor / model factory / runtime / UI). If it crosses layers, propose where the boundary should be first.
- Ask yourself: does this add a knob the backend cannot already turn? If a design exposes FSM, thresholds, or model choice to a human, that is a red flag, not a feature.

## Conventions (apply once a stack is introduced)

- This file is authoring guidance for the repo as it stands today; update the commands and style sections below as the stack lands.

### Commands

- No build system exists yet. Do not invent `npm`/`pnpm`/`cargo` commands that are not defined in this repo. When the stack lands, document: setup commands, dev server, tests, lint, and build here.

### Code style

- To be defined with the first commit. Prefer explicit, boring, testable code over clever abstractions.

## Archiving design conversations

- Design/vision discussions (e.g. ChatGPT shares) are archived under `conversations/` as dated Markdown files with any referenced images as siblings.
- Naming: `YYYY-MM-DD_short-title.md`. Include the source URL and archive date in a blockquote header.
- Agent-generated images from such conversations are stored alongside and referenced by relative path.

## Communication

- Repo is maintained in English (README, AGENTS.md, and commit messages). Team conversation may happen in Korean; summarize into English for artifacts.
- Ask before committing; do not push or open PRs unprompted.