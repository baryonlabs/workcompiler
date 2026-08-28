# OpenWorkflow

**The execution layer for AI work.**

Let AI do the work once. OpenWorkflow learns how to run it reliably thereafter.

From agent execution to compiled automation.

## Why OpenWorkflow

Coding agents and frontier LLMs can perform work, but their output is not repeatable, cost-effective, or observable. Every run re-derives the same result at the same frontier cost, and quality is unmeasured.

OpenWorkflow inverts this: an agent performs the work once, a human evaluates the output, and the system compiles that proven execution into a reliable, optimized workflow that runs deterministically behind the scenes.

**AI performs. Humans evaluate outcome quality. OpenWorkflow evaluates behavior, compiles the work, and continuously optimizes execution.**

The result being correct and the way it was done being correct are not the same. OpenWorkflow supervises the process, not only the outcome — see [Behavior Contract Layer](docs/behavior-contracts-v2.md).

## Core concept: Work Compilation

```
Agent Trace
      ↓
Work Compilation
      ↓
Optimized Workflow (Compiled Workflow)
```

A frontier agent produces an execution trace. Once a human approves the result, the **Work Compiler** decomposes the trace, discovers states and actions, extracts the deterministic parts, synthesizes rules and workflow structure, and produces a **Compiled Workflow**.

## Legacy vs OpenWorkflow

![Legacy vs OpenWorkflow pipeline](docs/pipeline.png)

The pipeline contrasts the two ways of getting AI work done:

- **Left — Legacy:** A frontier LLM + agent re-derives each task from scratch on every request. Reasoning, tools, and execution repeat every time, quality is unmeasured, and cost stays at frontier rates.
- **Right — OpenWorkflow:** A workflow is compiled once and executed deterministically (code, rules, ML, SLM). Frontier LLMs and humans are reserved for the exception path, and every output carries a measured quality signal.
- **Bottom — Background:** The invisible optimization loop. The Work Compiler, Executor Optimizer, and SLM Factory/Consolidation constantly feed, tune, and serve the compiled pipeline, and quality signals drive recompilation — all without blocking execution and without anyone operating the loop.

One approved example is enough to bridge from left to right: it is compiled into the workflow, and the background loop takes over from there.

## The two loops

### Execution Loop

```
Event
  ↓
Workflow
  ↓
Action
  ↓
Result
  ↓
Validation
  ↓
Output
```

### Optimization Loop

```
Output
  ↓
Quality Evaluation
  ↓
Trace Analysis
  ↓
Compiler Agent
  ↓
Workflow Revision
  ↓
Model / Rule / SLM Revision
  ↓
Canary
  ↓
Production
```

The loops are separate. The optimization loop never blocks the execution loop.

## Evaluation model: outcome + behavior

A correct-looking output is not enough. OpenWorkflow evaluates the outcome and the behavior that produced it:

```
Production Trace
   │
   ├── Output Quality      ← human evaluates the result card
   └── Behavior Compliance ← system judges, per contract (true / false / na)
```

Behavior contracts (invariant + process expectations) are compiled alongside workflows. Judges verify `verify-contract`, `use-current-pricing-policy`, `approval-before-send`, etc. — and a lucky-correct result that skipped the required process stays **FAIL**. See [Behavior Contract Layer](docs/behavior-contracts-v2.md).

![OpenWorkflow v2 loop](docs/behavior-loop.png)

## Product principles

1. **One human can evaluate quality.** No matter how complex the internals, the human unit of evaluation is always `Input → Output → Expected quality`. People evaluate outcomes, never workflow graphs.
2. **The system supervises behavior, not only outcomes.** An approved trace must pass its behavior contracts (verify, consult, escalate, require approval — written as `BEHAVIOR.md` specs). A lucky-correct result that skips a required process is still a failure.
3. **Behavior is implementation-independent.** Behavior, workflow, and executor stay separate. Any executor swap (LLM → SLM → code) must satisfy the same behavior contracts.
4. **Users do not design workflows.** FSM, rules, thresholds, model routers, SLM selection, fallbacks, retries, confidence policies, ontology, event mapping — all managed by backend compiler agents, invisible to users.
5. **The loop is visible, but no one operates it.** Users see automation level, quality, cost reduction, and execution mix. The system maintains itself.
6. **SLM Factory.** When a frontier LLM is overkill for a task, the backend generates the training data, distills and fine-tunes an SLM, evaluates it under a quality/latency/cost policy, then ships it through shadow → canary → production. Promotion additionally requires behavior-compliance parity on held-out traces.
7. **Model consolidation.** Model count stays at a healthy level. The backend continuously evaluates merge / split / retire / promote / rollback across tasks so `300 workflows` never becomes `280 runaway SLMs`.
8. **Escalate, don't duplicate.** Quality degradation and exceptions escalate to frontier LLM + human. Everything else is compiled.

## Architecture & Multi-Vendor Infrastructure

```
                       FRONTIER AGENT
             (OpenAI / Anthropic / Gemini / Bedrock)
                            │
                     performs new work
                            │
                            ▼
                    Execution Trace                 │
                            │                       │
                            ▼                       │
                    Human Quality Gate              │
                            │                       │
                     approved example               │
                            │                       │
                            ▼                       │
        ┌────────────────────────────────┐          │
        │        WORK COMPILER           │          ◀──── feedback: recompile
        │  decomposition / rules /       │          │
        │  synthesis of Workflow IR      │          │
        │  & Behavior Specs (BEHAVIOR.md)│          │
        └──────────────┬─────────────────┘          │
                       │ Vendor-Agnostic IR         │
                       ▼                            │
┌──────────────────────────────────────────────────────────────┐
│       PLUGGABLE INFRASTRUCTURE PROVIDER ADAPTER              │
│       (Late-Binding Target Provider: GCP / AWS / Azure / On-Prem)│
├──────────────┬──────────────┬───────────────┬────────────────┤
│ GCP Vertex   │ AWS Bedrock  │ Azure AI      │ On-Prem /      │
│ AI (Gemma)   │ / SageMaker  │ Studio        │ vLLM / Ollama  │
└──────────────┴───────┬──────┴───────────────┴────────────────┘
                       │ Provider Pricing & Native APIs
                       ▼                            │
        ┌────────────────────────────────┐          │
        │      EXECUTOR OPTIMIZER        │          ◀──── feedback: retune
        │  code vs rule vs ML / SLM /    │          │
        │  provider cost & latency policy│          │
        └──────────────┬─────────────────┘          │
                       ▼                            │
        ┌────────────────────────────────┐          │
        │         MODEL FACTORY          │          │
        │  dataset / distill / fine-tune │          │
        │  provider-native SLM pipeline  │          │
        └──────────────┬─────────────────┘          │
                       ▼                            │
        ┌────────────────────────────────┐          │
        │      OpenWorkflow Runtime      │          │
        │  deterministic engine on target│          │
        └──────────────┬─────────────────┘          │
                       ▼                            │
                    Outputs                         │
                       │                            │
                       ▼                            │
                 Quality Eval                       ┘
```

### Compilation Analogy: LLVM IR & Late-Binding Provider Adapters

OpenWorkflow adopts the classic compiler architecture pioneered by LLVM:

```text
[ Classical Compiler (LLVM) ]             [ OpenWorkflow Work Compiler ]

      C / C++ Source Code                       Frontier Agent Trace
               │                                         │
               ▼                                         ▼
         LLVM Frontend                             Work Compiler
               │                                         │
               ▼                                         ▼
   LLVM IR (Target-Agnostic)              Workflow IR + BEHAVIOR.md (Vendor-Agnostic)
               │                                         │
    ┌──────────┴──────────┐                   ┌──────────┴──────────┐
    ▼                     ▼                   ▼                     ▼
x86 Target           ARM Target          GCP Provider          AWS Provider / On-Prem
```

1. **Vendor-Agnostic Compilation**: The **Work Compiler** translates an agent trace into a vendor-independent **Workflow Intermediate Representation (IR)** and **Behavior Contract (`BEHAVIOR.md`)**.
2. **Late-Binding Infrastructure**: Vendor adapters (**GCP Vertex AI**, **AWS SageMaker/Bedrock**, **Azure AI Studio**, **On-Prem vLLM/Ollama**) attach late in the optimization and execution loop.
3. **Seamless Portability**: Moving a compiled workflow from a local testbed (Ollama) to cloud production (Vertex AI or SageMaker) requires zero changes to the compiled workflow IR or behavior contracts.

### Provider-Aware Work Compilation & SLM Lifecycle

OpenWorkflow decouples behavior specifications (`BEHAVIOR.md`) from vendor implementation while making the compilation and optimization layers **Infrastructure-Aware**:

1. **Work Compiler (Vendor-Agnostic Synthesis)**:
   Synthesizes vendor-independent Workflow IR and Behavior Contracts (`BEHAVIOR.md`) from approved execution traces.
2. **Pluggable Infrastructure Adapter (Late-Binding)**:
   Binds the Workflow IR to the selected cloud or on-premise provider (GCP, AWS, Azure, On-Prem), supplying target pricing matrices, latency profiles, and native SDK adapters.
3. **Executor Optimizer (Provider Cost & Latency Profiles)**:
   Evaluates trade-offs using the selected provider's exact pricing matrix and latency profiles (e.g., Vertex AI Gemma pricing vs SageMaker Llama endpoints vs local GPU cluster cost).
4. **Model Factory (Provider-Native Pipelines)**:
   Triggers vendor-native training, distillation, and deployment pipelines (Vertex Fine-Tuning, SageMaker Training Jobs, Azure Fine-Tuning, or vLLM/KServe on-premise clusters).
5. **Behavior Immunity**:
   Changing the target infrastructure provider requires zero updates to Behavior Contracts (`BEHAVIOR.md`) or human evaluation cards—the system automatically recompiles the IR for the new target substrate.

## Pillars

- **Work Compilation** — from agent trace to compiled workflow
- **Behavior Contracts** — what a good execution means, enforced across executor swaps
- **Autonomous Optimization** — the system tunes itself
- **Human Quality Loop** — humans evaluate outcomes; the system supervises behavior
- **SLM Factory** — build small models when frontier is overkill

## Status

Early-stage. Repo scaffolds the vision; runtime, compiler, and model factory are under construction.

## License

MIT
