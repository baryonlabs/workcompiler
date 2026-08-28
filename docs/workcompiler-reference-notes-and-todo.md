# OpenWorkflow Workload Compiler: Ecosystem Reference & TODO Roadmap

Status: Reference & Actionable TODO Spec · Created 2026-08

## 1. Comparative Ecosystem Analysis

| Project / Reference | Type | Core Mechanism | OpenWorkflow Distinction |
| :--- | :--- | :--- | :--- |
| **SqueezeAILab/LLMCompiler** (ICML 2024) | Execution-Plan Compiler | Dynamic tool-call DAG parallelization inside LLM sessions | OpenWorkflow is a **Workload Compiler** compiling past successful traces into deterministic Code/Rule/ML/SLM pipelines. |
| **Frugal** (Claude Code Router) | Cost Router | Cheap model first (Haiku → Sonnet); escalates on external oracle failure | OpenWorkflow expands Frugal's 5-tier LLM routing into an **8-tier executor lowering** (Code/Rule/ML/SLM/LLM). |
| **Scylla23/modelrouter** | Adaptive Router | `/router:redo` user correction feedback loop | OpenWorkflow uses **QualityRecord** fold verdicts to adaptively route step execution. |
| **Nardien/agent-distillation** | Trajectory Distillation | Distills 1.5B student agent from teacher trajectory | Reference for OpenWorkflow's **TrainingCandidate Generator** (SLM Factory orchestrator). |
| **Claude Code Production Plugins** | Harness & Oracle | Test/typecheck/schema external oracles for step completion | OpenWorkflow quality loop uses external oracles + behavior contracts instead of LLM self-confidence. |

---

## 2. The 8-Tier Executor Lowering Hierarchy

OpenWorkflow's compiler prioritizes **model elimination** before model reduction:

```text
Priority 1: Model Elimination (Zero Token Cost)
   ├── 1. Constant / Lookup
   ├── 2. SQL / Database Query
   ├── 3. Rule Engine
   └── 4. Deterministic Code (Python / WASM)

Priority 2: Model Lowering (Statistical & Small Models)
   ├── 5. Traditional ML (XGBoost / LightGBM / Scikit-Learn)
   ├── 6. Embedding & Vector Retrieval (RAG)
   └── 7. Distilled SLM (1B–3B local student model)

Priority 3: Residual Execution (Fallback & Quality Assurance)
   ├── 8. Frontier LLM (OpenAI / Anthropic / Gemini)
   └── 9. Human-in-the-Loop (Approval / Interrupt / Review)
```

---

## 3. Work Compiler 3-Stage Architecture

```text
               Agent Trajectory (Trace IR)
                            │
                            ▼
                    Compiler Frontend
                (Trace Normalizer → Work IR)
                            │
                            ▼
                    Compiler Middle-End
     ┌──────────────────────┼──────────────────────┐
     ▼                      ▼                      ▼
Determinism Analyzer   Prediction Analyzer    SLM Analyzer
(Arithmetic/Formats)  (Classification/Scores) (Generation/Summaries)
     │                      │                      │
     └──────────────────────┼──────────────────────┘
                            ▼
                    Compiler Backend
              (8-Tier Executor Lowering)
                            │
                            ▼
                    Quality Oracle Gate
            (Schema / Test / Behavior Contract)
                            │
                            ▼
                     Production Workflow
```

---

## 4. WorkCompiler Implementation TODO Roadmap

### Phase 1: Compiler Middle-End Analyzers
- [ ] **TODO-1.1**: Implement `DeterminismAnalyzer` in `core/compiler/analyzers/determinism.py`
  - Detect exact math, string formatting, dictionary lookup, schema validation, and fixed transformations in `TraceStep` inputs/outputs.
  - Lower detected steps directly to `CodeExecutor`, `RuleExecutor`, or `HTTPExecutor`.
- [ ] **TODO-1.2**: Implement `PredictionAnalyzer` in `core/compiler/analyzers/prediction.py`
  - Identify steps with structured inputs, finite categorical labels, or numerical score outputs (e.g. ticket classification, churn risk, priority rating).
  - Extract labeled datasets for `MLExecutor` (Scikit-Learn / XGBoost).
- [ ] **TODO-1.3**: Implement `SLMAnalyzer` in `core/compiler/analyzers/slm.py`
  - Identify narrow generative tasks (summarization, structured email drafting, intent extraction).
  - Generate `TrainingCandidate` specs for external `SFTTrainer` pipelines.

### Phase 2: Claude Code Experiment Harness Plugin (`workcompiler-plugin`)
- [ ] **TODO-2.1**: Develop Claude Code slash commands:
  - `/work:observe`: Record active Claude Code session tool calls and prompts into `TraceIR`.
  - `/work:compile`: Trigger `WorkCompiler` to generate `work.yaml` from recorded session.
  - `/work:benchmark`: Compare baseline Claude Code session cost/latency against compiled pipeline.
  - `/work:optimize`: Analyze step lowering opportunities across the 8-tier hierarchy.
  - `/work:promote`: Promote qualified compiled pipelines to production.

### Phase 3: External Oracle Escalation Engine
- [ ] **TODO-3.1**: Implement objective oracle failure escalation (Frugal-style).
  - Do not rely on LLM self-confidence; escalate step execution to higher tiers ONLY when schema validation, test cases, or behavior contracts fail.

### Phase 4: Customer Renewal PoC Benchmark
- [ ] **TODO-4.1**: Benchmark 100 customer renewal runs:
  - Measure Baseline: 100% Frontier Agent ($1.20/run, 85s latency).
  - Target Post-Compilation: <20% Frontier LLM residual, <10% Human touch, <$0.25/run cost.
