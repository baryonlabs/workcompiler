# OpenWorkflow

**The execution layer for AI work.**

Let AI do the work once. OpenWorkflow learns how to run it reliably thereafter.

> **"Build the kernel, integrate the ecosystem."**
> 
> *"Bring your agent. Bring your UI. Bring your evals. OpenWorkflow compiles the work."*

---

## Why OpenWorkflow

Coding agents and frontier LLMs can perform work, but their output is not repeatable, cost-effective, or observable. Every run re-derives the same result at the same frontier cost, and quality is unmeasured.

OpenWorkflow inverts this: an agent performs the work once, a human evaluates the output, and the system compiles that proven execution into a reliable, optimized workflow that runs deterministically behind the scenes.

**AI performs. Humans evaluate outcome quality. OpenWorkflow evaluates behavior, compiles the work, and continuously optimizes execution.**

The result being correct and the way it was done being correct are not the same. OpenWorkflow supervises the process, not only the outcome — see [Behavior Contract Layer](docs/behavior-contracts-v2.md) and [v3 Architecture Spec](docs/v3-architecture-kernel-ecosystem.md).

---

## Core Strategy: Kernel vs Ecosystem

OpenWorkflow acts as a **thin, strong execution & compilation kernel**. It does not replace your desktop UI, Slack bots, agent frameworks, or eval platforms. Instead, it owns the compilation and durable execution kernel while connecting to the ecosystem via standard adapters.

| Subsystem / Domain | Strategy | Integration Target / Standard |
| :--- | :---: | :--- |
| **Core Execution Kernel** | **Build Direct** | Work Compiler, Durable Runtime, Policy/Commit, Optimizer |
| **Desktop UI / Local Agent** | Minimal | **OpenWorker** (Desktop shell & local execution) |
| **Slack / Teams UX** | Minimal | **OpenTag / CopilotKit** |
| **Agent UI Protocol** | Adapter | **AG-UI Protocol** |
| **Agent Tool Exposure** | Adapter | **MCP (Model Context Protocol)** |
| **Behavior Specification** | Native Compat | **AgentBehavior** (`BEHAVIOR.md` spec) |
| **LLM Tracing & Evals** | Adapter | **Braintrust / Langfuse / OpenTelemetry** |
| **Workflow Canvas** | Future / Embed | n8n / Windmill reference embedding |
| **Durable Semantics** | Core Concept | Temporal-inspired durable state machine |
| **Human Interrupt UX** | Adapter | OpenTag / CopilotKit approval cards |
| **Local Tool Execution** | Adapter | OpenWorker (Local workspace, shell, files) |
| **Model Training Infra** | External | Hugging Face TRL / Unsloth / Cloud Fine-Tuning |

---

## Core concept: Work Compilation & `Work IR`

```
Agent Trace  ──▶  Trace IR  ──▶  Work Compiler  ──▶  Work IR  ──▶  Durable Runtime
```

The **Work IR** (`work.yaml`) is OpenWorkflow's primary native asset. It represents the compiled, executable definition of business work, decoupled from any specific LLM, UI, or cloud infrastructure.

```yaml
work: customer-renewal
version: 3.0

inputs:
  - customer_id

outputs:
  - renewal_proposal_pdf

states:
  - initialized
  - contract_verified
  - usage_calculated
  - proposal_drafted
  - approved
  - sent

actions:
  - lookup_contract
  - calculate_usage
  - price_offer
  - draft_proposal
  - send_email

dependencies:
  calculate_usage: [lookup_contract]
  price_offer: [calculate_usage]
  draft_proposal: [price_offer]
  send_email: [draft_proposal]

invariants:
  - verify_current_contract
  - use_current_pricing_policy
  - require_approval_before_send

quality:
  reviewer_acceptance: ">=0.95"

executors:
  draft_proposal:
    type: slm
    preferred: models/renewal-draft-slm-v1
    fallback:
      - frontier_llm
      - human
```

---

## The 5 Standard Protocol Boundaries

OpenWorkflow connects to external surfaces and tools through 5 standardized protocol contracts:

1. **Ingress Protocol**: Standardized event format for external triggers (webhooks, cron timers, Slack events, email notifications).
2. **Surface Protocol (AG-UI)**: Real-time workflow streaming (`workflow.started`, `step.started`, `approval.requested`, `workflow.completed`) to UI surfaces like OpenTag or CopilotKit.
3. **Tool Protocol (MCP)**: Exposes control endpoints (`start_work`, `get_work`, `list_approvals`, `approve`) to agents via Model Context Protocol.
4. **Trace/Eval Protocol (Trace IR)**: Import adapters converting agent trajectories (OpenAI, LangGraph, Braintrust, OpenWorker) into **Trace IR**.
5. **Worker Protocol**: Orchestrates remote or local execution workers (OpenWorker Desktop executing file/shell actions).

---

## Architecture (v3 Kernel & Ecosystem)

```
                               ECOSYSTEM
┌────────────────────┐   ┌────────────────────┐   ┌────────────────────┐
│   OpenWorker Desktop│   │   OpenTag / Slack  │   │  Custom Agents     │
│   (Local Worker)   │   │   (CopilotKit)     │   │  (LangGraph, etc.) │
└─────────┬──────────┘   └─────────┬──────────┘   └─────────┬──────────┘
          │ Tool (MCP)             │ Surface (AG-UI)        │ Trace / Ingress
          ▼                        ▼                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    OPENWORKFLOW GATEWAY ADAPTERS                     │
│   Ingress Protocol · Surface Protocol (AG-UI) · Tool Protocol (MCP)  │
│   Trace/Eval Protocol (Trace IR) · Worker Protocol                   │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │ Trace IR / Event IR
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         OPENWORKFLOW CORE                            │
│                                                                      │
│   ┌──────────────────────┐               ┌──────────────────────┐    │
│   │    Work Compiler     │               │ Quality & Behavior   │    │
│   │  Trace → Work IR     │               │ Contracts            │    │
│   └──────────┬───────────┘               │ (AgentBehavior spec) │    │
│              │                           └──────────┬───────────┘    │
│              ▼                                      │                │
│       ┌──────────────┐                              │                │
│       │   Work IR    │                              │                │
│       └──────┬───────┘                              │                │
│              ▼                                      ▼                │
│   ┌──────────────────────┐               ┌──────────────────────┐    │
│   │   Durable Runtime    │ ◄──────────── │      Optimizer       │    │
│   │ (State/Timer/Signal) │               │ Routing / SLM Promo  │    │
│   └──────────┬───────────┘               └──────────────────────┘    │
│              │                                                       │
│              ▼                                                       │
│   ┌──────────────────────┐                                           │
│   │   Policy / Commit    │                                           │
│   │ Validation/Approvals │                                           │
│   └──────────────────────┘                                           │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │ Execution & Telemetry
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    EXTERNAL EVAL & INFRA ADAPTERS                    │
│   Braintrust / Langfuse / OTel  ·  HuggingFace/TRL  ·  Temporal    │
└──────────────────────────────────────────────────────────────────────┘
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

---

## Non-Negotiable Boundaries

### ❌ What OpenWorkflow Will NOT Build
- Custom Slack / Teams bot frameworks
- Proprietary desktop shell / GUI application
- Drag-and-drop visual workflow canvas
- Full LLM observability / tracing platform
- Fine-tuning & GPU cluster infrastructure
- Proprietary Vector Database

### ✅ What OpenWorkflow WILL Build & Own
- **Trace → Work IR Compiler**: Decomposing agent traces into deterministic Work IR.
- **Work IR → Compiled Workflow**: Synthesizing optimized execution DAGs.
- **Behavior → Executable Invariants**: Compiling `BEHAVIOR.md` into rules, constraints, and judges.
- **Executor Optimization & Consolidation**: Dynamic routing across Code, Rules, SLMs, LLMs.
- **Durable Runtime & Human Approval Loop**: Managing stateful execution, interrupts, signals, and human outcome evaluation.
- **Continuous Recompilation**: Automated feedback loop driven by quality signals.

---

## Repository Layout (v3)

```
openworkflow/
├── core/                        # Thin, strong OpenWorkflow kernel
│   ├── work_ir/                 # Work IR schema, parser, and AST
│   ├── compiler/                # Trace decomposition & workflow synthesis
│   ├── runtime/                 # Durable state machine & checkpointing
│   ├── policy/                  # Permissions, approvals, and confidence gates
│   ├── validation/              # Behavior & outcome validation judges
│   └── optimizer/               # Executor routing, SLM promotion & consolidation
│
├── protocols/                   # Standard protocol contract definitions
│   ├── events/                  # Ingress protocol schemas
│   ├── traces/                  # Trace IR import schemas
│   ├── workers/                 # Worker protocol contracts
│   └── surfaces/                # AG-UI surface event contracts
│
├── adapters/                    # Ecosystem integration adapters
│   ├── agui/                    # Surface protocol adapter for AG-UI
│   ├── mcp/                     # MCP tool protocol adapter
│   ├── opentag/                 # OpenTag channel adapter
│   ├── openworker/              # OpenWorker desktop adapter
│   ├── agentbehavior/           # AgentBehavior BEHAVIOR.md importer
│   ├── braintrust/              # Braintrust trace/eval adapter
│   └── opentelemetry/           # OpenTelemetry export adapter
│
├── agents/                      # Guide and measurement fleet specs
├── docs/                        # Specifications, architecture, and diagrams
├── conversations/               # Design conversation archives
└── examples/                    # Sample workflows, traces, and behavior specs
```

---

## License

MIT
