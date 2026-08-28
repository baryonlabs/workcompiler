# OpenWorkflow v3 Architecture: Kernel & Ecosystem Strategy

Status: Design Spec (v3) · Supersedes v2 Architecture

## Executive Summary

OpenWorkflow v3 establishes the core architectural philosophy:

> **Build the kernel, integrate the ecosystem.**
> 
> *"Bring your agent. Bring your UI. Bring your evals. OpenWorkflow compiles the work."*

OpenWorkflow does not replace existing agent frameworks, desktop shells, Slack bots, or evaluation platforms. Instead, OpenWorkflow acts as a **thin, robust execution and compilation kernel** that converts proven AI agent traces into reliable, durable, optimized workflows, while seamlessly delegating surface UX, tool exposure, tracing, and model fine-tuning to the broader ecosystem via standard protocol adapters.

---

## 1. Core Principles

1. **Kernel Focus**: OpenWorkflow owns **Work Compilation**, **Durable Execution**, **Behavior/Policy Commit**, and **Autonomous Optimization**.
2. **Ecosystem Delegated**: User interfaces (OpenWorker, OpenTag), protocol transport (AG-UI, MCP), telemetry (Braintrust, Langfuse, OpenTelemetry), and model training (Hugging Face, TRL) are attached via thin protocol adapters.
3. **Trace → Work IR Compilation**: The central asset of OpenWorkflow is the **Work IR (Intermediate Representation)**—a vendor-agnostic, framework-agnostic definition of compiled business work.
4. **Behavior Contract Invariance**: Behavior specs (`BEHAVIOR.md` in AgentBehavior format) are non-negotiable process invariants preserved across all executor swaps (Code, Rule, SLM, LLM).
5. **Humans Evaluate Outcomes Only**: Users interact via standard result cards (`Input → Output → Expected quality`); they never construct or operate workflow graphs.

---

## 2. OpenWorkflow Core Kernel (6 Core Modules)

The kernel is intentionally kept minimal, cohesive, and decoupled from external frameworks.

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                           OPENWORKFLOW CORE                             │
│                                                                         │
│  1. Work Trace               2. Quality & Behavior Contract             │
│     - Agent trajectory          - Human outcome rating                  │
│     - Action/Result history     - Automated behavior evaluation         │
│     - Provenance                - Acceptance criteria                   │
│                                                                         │
│  3. Work Compiler            4. Durable Runtime                         │
│     - Trace → Work IR           - State persistence & checkpointing     │
│     - Invariant extraction      - Retry, timer, signal                  │
│     - Executor candidates       - Interrupt & resume                    │
│                                                                         │
│  5. Policy / Commit          6. Optimizer                               │
│     - Permissions & validation  - Executor routing (Code/Rule/SLM/LLM) │
│     - Confidence thresholds     - SLM promotion gate                    │
│     - Human approval gates      - Model & Behavior consolidation        │
└─────────────────────────────────────────────────────────────────────────┘
```

### Module Responsibilities

1. **Work Trace**: Ingests, normalizes, and indexes raw execution trajectories from any agent framework.
2. **Quality & Behavior Contract**: Enforces outcome quality metrics alongside process invariants (`true / false / na`).
3. **Work Compiler**: Analyzes accepted traces, extracts deterministic states and actions, and synthesizes `Work IR`.
4. **Durable Runtime**: Provides fault-tolerant, stateful execution with Temporal-like semantics (checkpointing, signals, timers, interrupts, resume).
5. **Policy / Commit**: Controls state mutations, permission validation, confidence thresholds, and human-in-the-loop approval gates.
6. **Optimizer**: Dynamically routes step execution across Code, Rules, SLMs, and LLMs, manages SLM promotion, and consolidates models/behaviors across workflows.

---

## 3. Ecosystem Integration Matrix

OpenWorkflow explicitly avoids re-inventing existing open-source tools. Everything outside the core kernel is connected via adapters.

| Subsystem / Domain | Strategy | Integration Target / Standard |
| :--- | :---: | :--- |
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

## 4. The 5 Standard Protocol Boundaries

To enable seamless ecosystem integration, OpenWorkflow defines 5 standardized protocol contracts:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                        5 STANDARD PROTOCOLS                             │
│                                                                         │
│  1. Ingress Protocol     ──▶ Webhooks, Email, Cron, Slack Events        │
│  2. Surface Protocol     ──▶ AG-UI (OpenTag, CopilotKit)                │
│  3. Tool Protocol        ──▶ MCP (OpenWorker, Claude, Custom Agents)    │
│  4. Trace/Eval Protocol  ──▶ Trace IR (Braintrust, LangGraph, OTel)     │
│  5. Worker Protocol      ──▶ Local/Remote Workers (OpenWorker Desktop)  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1) Ingress Protocol
Standardized event format for external triggers (webhooks, cron timers, Slack events, email notifications):

```json
{
  "type": "message.received",
  "source": "slack",
  "actor": "user_123",
  "timestamp": "2026-08-28T16:20:00Z",
  "payload": {
    "channel": "C123456",
    "text": "Generate annual renewal proposal for Customer ACME"
  },
  "correlation": {
    "trace_id": "tr_98765"
  }
}
```

### 2) Surface Protocol (AG-UI)
Streams real-time workflow lifecycle events to UI surfaces (OpenTag, CopilotKit, Web UI):

* `workflow.started`
* `step.started`
* `artifact.created`
* `approval.requested`
* `workflow.interrupted`
* `workflow.completed`

### 3) Tool Protocol (MCP)
Exposes OpenWorkflow control endpoints to external agents via Model Context Protocol:

* `start_work`
* `get_work`
* `signal_work`
* `list_approvals`
* `approve`
* `get_artifact`
* `get_business_object`

### 4) Trace/Eval Protocol & Trace IR
Import adapters translate raw agent traces (OpenAI, LangGraph, Braintrust, OpenWorker) into **OpenWorkflow Trace IR**:

```json
{
  "run_id": "run_abc123",
  "steps": [
    {
      "actor": "agent",
      "action": "crm.search",
      "input": { "query": "ACME Corp" },
      "output": { "contract_id": "ct_456" },
      "timestamp": "2026-08-28T16:20:05Z"
    }
  ],
  "result": { "status": "success" },
  "artifacts": [ "file:///tmp/proposal.pdf" ],
  "provenance": { "agent_version": "v1.2.0" }
}
```

### 5) Worker Protocol
Orchestrates remote or local execution workers (e.g. OpenWorker Desktop executing file/shell operations locally).

---


### 6) Zero-Code Agent Proxy Adapter (`adapters/proxy/`)
Inspired by transparent LLM proxy architectures (e.g. `opencodex`), OpenWorkflow provides a lightweight reverse proxy interceptor:

```text
Existing Agent (Cursor, Claude Code, AutoGen, LangChain)
                      │
  API Request (OPENAI_BASE_URL=http://localhost:8080/v1)
                      │
                      ▼
       OpenWorkflow Proxy Adapter (adapters/proxy/)
         ├── 1. Forward request to Upstream LLM (OpenAI / Anthropic)
         ├── 2. Intercept trajectory (Tool Calls, Prompts, Outputs)
         └── 3. Stream trajectory into Trace IR
                      │
                      ▼
            OpenWorkflow Work Compiler  ──▶  Work IR (work.yaml)
```

Existing agents require **zero code modifications**—simply changing the API base URL allows OpenWorkflow to capture agent trajectories and compile them into deterministic `Work IR`.

## 5. Core Native Abstraction: `Work IR``)

The **Work IR** (`work.yaml`) is OpenWorkflow's primary asset. It represents the compiled, executable definition of business work, decoupled from any specific LLM, UI, or infrastructure.

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
  factual_accuracy: ">=0.99"
  reviewer_acceptance: ">=0.95"

behaviors:
  - name: verify-current-contract
    path: behaviors/verify-current-contract/BEHAVIOR.md
  - name: use-current-pricing-policy
    path: behaviors/use-current-pricing-policy/BEHAVIOR.md
  - name: require-approval-before-send
    path: behaviors/require-approval-before-send/BEHAVIOR.md

escalation:
  on_error: fallback_to_frontier_llm
  on_quality_drop: require_human_review

executors:
  lookup_contract:
    type: code
    handler: connectors.crm.lookup_contract
  calculate_usage:
    type: code
    handler: services.usage.calculate
  price_offer:
    type: rule
    handler: rules.pricing_v2
  draft_proposal:
    type: slm
    preferred: models/renewal-draft-slm-v1
    fallback:
      - frontier_llm
      - human
  send_email:
    type: code
    handler: connectors.email.send
```

---

## 6. Subsystem Integration Strategies

### OpenWorker (Desktop & Local Worker)
* **Phase 1**: Connect OpenWorker to OpenWorkflow via **MCP**.
* **Phase 2**: Introduce a native adapter for deep state synchronization.
* **Phase 3**: Position OpenWorker as the primary **Local Worker** for desktop file system, local shell, and local app automation under the Worker Protocol.

### OpenTag (Slack / Teams Surface)
```text
Slack / Teams  ──▶  OpenTag  ──▶  AG-UI Adapter  ──▶  OpenWorkflow Core
```
OpenTag handles enterprise channel UX and user notifications; OpenWorkflow owns workflow state, behavior compliance, and execution routing.

### AgentBehavior Integration
OpenWorkflow reads native `.agents/behaviors/*/BEHAVIOR.md` files without re-implementation. The Work Compiler classifies each behavior into:
1. **Rule / Policy Engine** (deterministic check)
2. **Workflow Transition Constraint** (ordering dependency)
3. **Runtime Evaluator Judge** (semantic quality check)

---

## 7. Explicit Non-Negotiable Boundaries

To maintain focus and high engineering quality, OpenWorkflow strictly defines what to build versus what NOT to build.

### ❌ What OpenWorkflow Will NOT Build
* Custom Slack / Teams bot frameworks
* Proprietary desktop shell / GUI application
* Drag-and-drop visual workflow canvas (reference/embed n8n/Windmill if needed)
* Full LLM observability / tracing platform (use Braintrust / Langfuse / OpenTelemetry)
* Fine-tuning & GPU cluster infrastructure (use Hugging Face TRL / Cloud APIs)
* Proprietary Vector Database
* General-purpose conversational agent framework

### ✅ What OpenWorkflow WILL Build & Own
* **Trace → Work IR Compiler**: Decomposing agent traces into deterministic Work IR.
* **Work IR → Compiled Workflow**: Synthesizing optimized execution DAGs.
* **Behavior → Executable Invariants**: Compiling `BEHAVIOR.md` into rules, constraints, and judges.
* **Executor Optimization & Consolidation**: Routing across Code, Rules, SLMs, LLMs and consolidating models/behaviors.
* **Durable Runtime & Human Approval Loop**: Managing stateful execution, interrupts, signals, and human outcome evaluation.
* **Continuous Recompilation**: Automated feedback loop driven by quality signals and drift.

---

## 8. Target Repository Architecture

```text
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
