# OpenWorkflow

**The execution layer for AI work.**

Let AI do the work once. OpenWorkflow learns how to run it reliably thereafter.

> **"Build the kernel, integrate the ecosystem, enrich with semantic truth."**
> 
> *"LinkML is the front door for human/LLM model authoring; OWL is the semantic truth layer; SHACL validates constraints; OpenWorkflow executes durable work."*

---

## Why OpenWorkflow

Coding agents and frontier LLMs can perform work, but their output is not repeatable, cost-effective, or observable. Every run re-derives the same result at the same frontier cost, and quality is unmeasured.

OpenWorkflow inverts this: an agent performs the work once, a human evaluates the output, and the system compiles that proven execution into a reliable, optimized workflow that runs deterministically behind the scenes.

**AI performs. Humans evaluate outcome quality. OpenWorkflow evaluates behavior, compiles the work, and continuously optimizes execution.**

The result being correct and the way it was done being correct are not the same. OpenWorkflow supervises the process, not only the outcome — see [Behavior Contract Layer](docs/behavior-contracts-v2.md) and [v4 Architecture Spec](docs/v4-architecture-semantic-layer.md).

---

## Semantic Stack Architecture (v4)

OpenWorkflow v4 introduces a multi-tiered semantic stack. It uses **LinkML** as the developer-friendly YAML authoring language, compiles into internal **Semantic IR**, enriches with **OWL 2** DL semantics, and validates closed-world constraints via **SHACL**:

| Layer | Role | Target Technology |
| :--- | :--- | :--- |
| **Authoring DSL** | Human/Developer/LLM business model authoring | **LinkML (YAML DSL)** |
| **Semantic Canonical IR** | Internal unified semantic model | **Semantic IR** |
| **Semantic Ontology** | Open-world reasoning & relationship semantics | **OWL 2 (DL)** |
| **Constraint Validation** | Closed-world data verification & cardinalities | **SHACL** |
| **Reasoner** | Inferred classification & consistency checking | **ELK / HermiT** |
| **Runtime Graph** | Knowledge Graph & RDF triples | **Jena / RDF4J / RDFLib** |
| **Execution Engine** | Stateful workflow, action DAG & durable runtime | **OpenWorkflow Kernel** |

---

## Compiler Pipeline: Trace → LinkML → Semantic IR → Execution

The **LLM-as-Compiler** does not generate raw OWL axioms directly. Instead, it extracts a developer-friendly LinkML domain model first, which is then enriched into formal OWL semantics and SHACL constraints.

```text
               Agent Trace
                    │
                    ▼
              LLVM / LLM Compiler
                    │
              LinkML Domain Model (YAML)
                    │
             Semantic Compiler
                    │
              Semantic IR (Canonical)
                    │
   ┌────────────────┼────────────────┬────────────────┐
   ▼                ▼                ▼                ▼
Pydantic          SHACL             OWL           Work IR
(Runtime Types) (Closed-World)  (Open-World)    (Durable DAG)
                    │                │
                    ▼                ▼
             Validation Gate     ELK / HermiT Reasoner
                    │                │
                    └────────┬───────┘
                             ▼
                    OpenWorkflow Runtime
```

---

## Core concept: Work Compilation & `Work IR`

```
Agent Trace  ──▶  Trace IR  ──▶  Work Compiler  ──▶  Work IR  ──▶  Durable Runtime
```

The **Work IR** (`work.yaml`) is OpenWorkflow's primary native asset. It represents the compiled, executable definition of business work, decoupled from any specific LLM, UI, or cloud infrastructure.

```yaml
work: customer-renewal
version: "4.0"

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

## Repository Layout (v4)

```
openworkflow/
├── core/                        # Thin, strong OpenWorkflow kernel
│   ├── semantic_ir/             # [v4] LinkML parser, Semantic IR AST, OWL/SHACL generators
│   ├── work_ir/                 # Work IR schema, parser, and AST
│   ├── compiler/                # Trace IR → Work IR compilation
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
├── adapters/                    # Ecosystem & Semantic Adapters
│   ├── linkml/                  # [v4] LinkML authoring & generator adapter
│   ├── owl/                     # [v4] OWL 2 ontology & ELK/HermiT reasoner adapter
│   ├── shacl/                   # [v4] SHACL constraint validator adapter
│   ├── agui/                    # Surface protocol adapter for AG-UI
│   ├── mcp/                     # MCP tool protocol adapter
│   ├── proxy/                   # Zero-code LLM API proxy adapter
│   ├── opentag/                 # OpenTag channel adapter
│   ├── openworker/              # OpenWorker desktop adapter
│   ├── agentbehavior/           # AgentBehavior BEHAVIOR.md importer
│   ├── braintrust/              # Braintrust trace/eval adapter
│   └── opentelemetry/           # OpenTelemetry export adapter
│
├── agents/                      # Guide and measurement fleet specs
├── docs/                        # Specifications, architecture, and diagrams
├── conversations/               # Design conversation archives
└── examples/                    # Sample workflows, LinkML schemas, and behavior specs
```

---


---

## Usage & Demonstration

For complete API documentation and a step-by-step developer guide, see **[Usage Guide](docs/usage.md)**.

Run the end-to-end customer renewal demonstration script:

```bash
python3 examples/run_customer_renewal_demo.py
```


## Ecosystem & Reference Links

OpenWorkflow builds upon and integrates with the following open-source projects, standards, and research initiatives:

| Category | Project / Standard | Link | Description |
| :--- | :--- | :--- | :--- |
| **Model Authoring DSL** | **LinkML** | [linkml/linkml](https://github.com/linkml/linkml) | Linked Open Data Modeling Language for YAML schema modeling |
| **Semantic Ontology** | **OWL 2 / W3C** | [w3.org/TR/owl2-overview](https://www.w3.org/TR/owl2-overview/) | W3C Web Ontology Language for semantic reasoning |
| **Constraint Validation** | **SHACL / W3C** | [w3.org/TR/shacl](https://www.w3.org/TR/shacl/) | W3C Shapes Constraint Language for RDF data validation |
| **Desktop Shell / Local Worker** | **OpenWorker** | [baryonlabs/openworker](https://github.com/baryonlabs/openworker) | Desktop AI agent shell & local execution worker |
| **Enterprise Channel UX** | **OpenTag** | [baryonlabs/opentag](https://github.com/baryonlabs/opentag) | Slack & Teams channel integration for AI workflows |
| **UI Streaming Protocol** | **AG-UI** | [agui-protocol/agui](https://github.com/agui-protocol/agui) | Protocol for streaming AI workflow lifecycle events to UIs |
| **Tool Protocol** | **Model Context Protocol (MCP)** | [modelcontextprotocol.io](https://modelcontextprotocol.io) | Anthropic's standard protocol for connecting AI models to tools |
| **Behavior Contracts** | **AgentBehavior** | [braintrustdata/agentbehavior](https://github.com/braintrustdata/agentbehavior) | Open standard format for process evaluation specs (`BEHAVIOR.md`) |
| **Zero-Code Agent Proxy** | **OpenCodex** | [lidge-jun/opencodex](https://github.com/lidge-jun/opencodex) | Transparent LLM API proxy for intercepting agent trajectories |
| **LLM Tracing & Evals** | **Braintrust** | [braintrustdata/braintrust](https://github.com/braintrustdata/braintrust) | Enterprise LLM evaluation & tracing platform |
| **LLM Tracing & Evals** | **Langfuse** | [langfuse/langfuse](https://github.com/langfuse/langfuse) | Open-source LLM engineering & observability platform |
| **Observability** | **OpenTelemetry** | [opentelemetry.io](https://opentelemetry.io) | Cloud-native observability framework for telemetry data |
| **Durable Execution** | **Temporal** | [temporalio/temporal](https://github.com/temporalio/temporal) | Durable state machine & workflow execution engine |
| **Compiler Research** | **LLMCompiler** | [SqueezeAILab/LLMCompiler](https://github.com/SqueezeAILab/LLMCompiler) | ICML 2024 compiler for parallel LLM function calling |

---

## License

MIT
