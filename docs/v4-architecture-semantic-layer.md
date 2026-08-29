# OpenWorkCompiler v4 Architecture: Semantic Layer & LinkML/OWL Integration

Status: Master Architecture Specification (v4) · Supersedes v3 Architecture

## Executive Summary

OpenWorkCompiler v4 introduces the **Semantic Layer Stack**, establishing a clear separation of concerns between developer-friendly domain modeling, semantic reasoning, closed-world constraint validation, and durable workflow execution.

> **"Build the kernel, integrate the ecosystem, enrich with semantic truth."**
>
> *"LinkML is the front door for human/LLM model authoring; OWL is the semantic truth layer; SHACL validates constraints; OpenWorkCompiler executes durable work."*

---

## 1. The Core Semantic Philosophy

A common architectural trap in AI systems is forcing developers or LLMs to write raw Description Logic axioms (OWL 2) directly, or assuming schema validation tools (LinkML) can perform open-world reasoning.

OpenWorkCompiler v4 resolves this by separating roles into a multi-tiered semantic stack:

| Layer | Role | Target Technology |
| :--- | :--- | :--- |
| **Authoring DSL** | Human/Developer/LLM business model authoring | **LinkML (YAML DSL)** |
| **Semantic Canonical IR** | Unified internal representation | **Semantic IR** |
| **Semantic Ontology** | Open-world reasoning & relationship semantics | **OWL 2 (DL)** |
| **Constraint Validation** | Closed-world data verification & cardinalities | **SHACL** |
| **Reasoner** | Inferred classification & consistency checking | **ELK / HermiT** |
| **Runtime Graph** | Knowledge Graph & RDF triples | **Jena / RDF4J / RDFLib** |
| **Execution Engine** | Stateful workflow, action DAG & durable runtime | **OpenWorkCompiler Kernel** |

---

## 2. Compilation Pipeline: Trace → LinkML → Semantic IR → Execution

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
                    OpenWorkCompiler Runtime
```

### Why LinkML as the Authoring Front Door?
1. **Developer Experience**: Backend engineers and LLMs can write intuitive YAML classes, slots, and enums without knowing Description Logic terms (`SubClassOf`, `ObjectSomeValuesFrom`).
2. **Polyglot Code Generation**: LinkML natively compiles into Pydantic models, JSON Schema, TypeScript types, SHACL shapes, and OWL ontologies.
3. **LLM Safety**: LLMs produce structured LinkML schemas with far higher accuracy and lower hallucination rates than raw OWL DL syntax.

---

## 3. Closed-World vs Open-World Separation

LinkML models are split by the Semantic Compiler into two distinct validation engines:

```text
                  LinkML Model
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
     SHACL                            OWL
(Closed-World Validation)    (Open-World Reasoning)
  - required: true             - Class subsumption
  - cardinality: exactly 1     - Property chain inference
  - regex patterns             - Disjointness & equivalence
```

- **SHACL (Closed-World)**: Enforces business constraints (`amount` must be a positive decimal, `vendor` is required).
- **OWL 2 (Open-World)**: Enforces semantic inferencing (e.g. `HighRiskPurchase ≡ PurchaseRequest ⊓ hasRiskScore some HighRiskScore`).

---

## 4. OpenWorkCompiler Core Kernel (7 Modules in v4)

v4 expands the core kernel to include the **Semantic IR** module:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                           OPENWORKCOMPILER CORE (v4)                        │
│                                                                         │
│  1. Work Trace               2. Quality & Behavior Contract             │
│     - Trajectory indexing       - Human outcome rating                  │
│     - Provenance                - BEHAVIOR.md compliance                │
│                                                                         │
│  3. Semantic IR              4. Work Compiler                           │
│     - LinkML parser             - Trace → Work IR                       │
│     - OWL/SHACL mapper          - Invariant extraction                  │
│     - Canonical domain AST      - Executor candidates                   │
│                                                                         │
│  5. Durable Runtime          6. Policy / Commit                         │
│     - Checkpointing & state     - Approvals & permission validation     │
│     - Timers, signals, resume   - Write locks & confidence gates        │
│                                                                         │
│  7. Optimizer                                                           │
│     - Code/Rule/SLM/LLM routing                                         │
│     - Provider cost & latency optimization                              │
│     - Model & Behavior consolidation                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Repository Layout (v4)

```text
openworkcompiler/
├── core/                        # Thin, strong OpenWorkCompiler kernel
│   ├── semantic_ir/             # [v4] LinkML parser, Semantic IR AST, OWL/SHACL generators
│   ├── work_ir/                 # Work IR schema, parser, and AST
│   ├── compiler/                # Trace IR → Work IR compilation
│   ├── runtime/                 # Durable state machine & checkpointing
│   ├── policy/                  # Permissions, approvals, and confidence gates
│   ├── validation/              # Behavior & outcome validation judges
│   └── optimizer/               # Executor routing, SLM promotion & consolidation
│
├── protocols/                   # Standard protocol contract definitions
│   ├── events/                  # Ingress Protocol
│   ├── traces/                  # Trace IR
│   ├── workers/                 # Worker Protocol
│   └── surfaces/                # AG-UI Surface Protocol
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
└── examples/                    # Sample Work IR, LinkML schemas, and behavior specs
```
