# AGENTS.md

Project-specific guidance for AI coding agents working on OpenWorkflow.

## Project overview

OpenWorkflow is **the execution layer for AI work**: a system that turns proven agent executions into reliable, optimized, compiled workflows.

- An agent performs work → a human approves the output → OpenWorkflow compiles the trace into deterministic workflow + rules + code + SLMs → the runtime executes it → the system measures quality and optimizes itself.
- One core philosophy: **"Build the kernel, integrate the ecosystem, enrich with semantic truth."**
  - *"LinkML is the front door for human/LLM model authoring; OWL is the semantic truth layer; SHACL validates constraints; OpenWorkflow executes durable work."*
- Full vision and architecture live in `README.md` and `docs/v4-architecture-semantic-layer.md`. Read them before making design decisions.
- Behavior Contract design: `docs/behavior-contracts-v2.md` (integration of the AgentBehavior standard).

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

## Repository layout (v4)

```
README.md          Product vision, core vs ecosystem loops, architecture
AGENTS.md          This file — agent instructions
core/              Thin, strong OpenWorkflow kernel
  semantic_ir/     LinkML parser, Semantic IR AST, OWL/SHACL generators
  work_ir/         Work IR schema, AST parser, work.yaml validator
  compiler/        Trace IR → Work IR compilation & invariant extraction
  runtime/         Durable state machine, checkpointing, signals, timers, interrupts
  policy/          Permissions, approvals, write locks, and confidence thresholds
  validation/      Behavior contract judges & outcome quality evaluation
  optimizer/       Executor routing, SLM promotion gate, model/behavior consolidation
protocols/         Standard protocol contract definitions
  events/          Ingress Protocol (webhooks, cron, Slack events)
  traces/          Trace/Eval Protocol (Trace IR & import adapters)
  workers/         Worker Protocol (local/remote worker orchestration)
  surfaces/        Surface Protocol (AG-UI real-time streaming)
adapters/          Ecosystem & Semantic integration adapters
  linkml/          LinkML authoring & generator adapter
  owl/             OWL 2 ontology & ELK/HermiT reasoner adapter
  shacl/           SHACL constraint validator adapter
  agui/            AG-UI surface adapter for OpenTag / CopilotKit
  mcp/             MCP tool protocol adapter for OpenWorker / Claude
  proxy/           Zero-code LLM API proxy adapter
  opentag/         OpenTag channel & approval adapter
  openworker/      OpenWorker desktop & local execution adapter
  agentbehavior/   AgentBehavior BEHAVIOR.md spec importer
  braintrust/      Braintrust trace import & eval telemetry adapter
  opentelemetry/   OpenTelemetry export adapter
agents/            Sub-agent definitions (guide + measurement fleet)
docs/              Design docs, diagrams, and rendered assets
conversations/     Archived design conversations (ChatGPT share exports + assets)
examples/          Sample workflows, LinkML schemas, traces, and behavior contracts
```

## Before you write code

- **Keep `core/` thin and clean**: Do NOT import external vendor libraries, Slack SDKs, Desktop UI shells, or LLM observability frameworks into `core/`. Everything external belongs in `adapters/`.
- Confirm the change only touches the layer you intend (`core/`, `protocols/`, or `adapters/`). If it crosses layers, define the protocol boundary in `protocols/` first.
- Ask yourself: does this add a knob the backend cannot already turn? If a design exposes FSM, thresholds, or model choice to a human, that is a red flag, not a feature.

## Conventions

- Repo is maintained in English (README, AGENTS.md, code comments, and commit messages). Team conversation may happen in Korean; summarize into English for artifacts.
- Ask before committing; do not push or open PRs unprompted.
