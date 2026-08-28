# OpenWorkflow Behavior Contract Layer (v2)

Status: design · Supersedes the v1 integration analysis of [AgentBehavior](https://github.com/braintrustdata/agentbehavior)

AgentBehavior is **not** a competing execution layer. It is a standard layer that sits in front of OpenWorkflow's Work Compilation: it defines and validates what a *good execution* is, before compilation. This document improves the v1 analysis into a concrete, buildable design and lands the decisions.

## 1. The gap v1 left open

The loop we had:

```text
Frontier Agent performs work
        ↓
Human evaluates result quality
        ↓
Approved Trace
        ↓
LLM-as-Compiler → Rule/Code/ML/SLM workflow
        ↓
Production → quality eval → recompile
```

had exactly one blank: **"the result was good" and "the way it was done was good" are not the same.**

A frontier agent can land a correct contract analysis while skipping the primary-source check, querying data without permission checks, or using a cached price table instead of the live one. v1 named this problem correctly ("lucky-correct negative") but did not decide how OpenWorkflow opens, owns, and operates a behavior layer. v2 decides that.

## 2. The one-sentence correction

> **Humans evaluate outcome quality. The system evaluates behavior and outcome quality together.**

This replaces the old phrasing "humans only evaluate outputs" as the system philosophy. The product UX principle stays intact — humans still *see* a single output card — but the system no longer trusts a correct-looking output without a behavior check.

## 3. Core separation

Three things must never be merged.

```text
Behavior   = what it means for the work to be done well (implementation-independent)
Workflow   = how the work is executed (steps, transitions)
Executor   = who/what actually runs each step (code • rule • ML • SLM • LLM)
```

- Behavior survives any executor swap: SLM, LLM, or code must satisfy the same behavior.
- Workflow can be recompiled; Behavior is the invariant set it must never violate.

## 4. Behavior Contract — native format

OpenWorkflow supports AgentBehavior's `BEHAVIOR.md` format natively and stores it under a work definition. Full compat with AgentBehavior spec + Apache-2.0 borrow is intentional, but the registry and lifecycle are OpenWorkflow-owned.

```text
work: renewal-proposal

quality:
  - factual_accuracy >= 0.99
  - reviewer_acceptance >= 0.95

behaviors:
  - verify-current-contract
  - use-current-pricing-policy
  - cite-financial-source
  - require-approval-before-send
```

Each behavior is a `BEHAVIOR.md` file (AgentBehavior format), authored with the recommended six sections: `Intent / Evidence / Decision / Execution / Recovery / Failure modes`.

### Discovery rule

Behavior specs live where the work is compiled, alongside the workflow definition, so the compiler, the runtime judges, and the human review surface all read the same source of truth:

```text
workflows/renewal-proposal/
├── work.yaml                 # work definition (schema → behaviors → quality → executors)
├── workflow.yaml             # compiled workflow graph
├── behaviors/
│   ├── verify-current-contract/BEHAVIOR.md
│   ├── use-current-pricing-policy/BEHAVIOR.md
│   └── require-approval-before-send/BEHAVIOR.md
└── executors/
    └── model-registry.yaml
```

## 5. Compilation: how the compiler decides the behavior's target

Not every behavior compiles to the same thing. The LLM-as-Compiler classifies each behavior with an explicit decision procedure:

```text
1. Is the trigger observable in the trace?            → no  → preserve as evaluator-only spec
2. Can the conduct be expressed as a deterministic rule?  → yes → Rule / Policy
3. Does the conduct impose an ordering/dependency between steps? → yes → Workflow transition constraint
4. Otherwise (semantic/qualitative conduct)           → SLM/LLM judge at runtime
```

| Behavior type                            | Compiles to              | Enforced by                |
| ---------------------------------------- | ------------------------ | -------------------------- |
| Deterministic invariant (approval-before-send) | Rule / Policy            | Runtime policy engine      |
| Structural procedure (CRM-lookup → price calc)  | Workflow transition      | Workflow graph dependency  |
| Semantic / qualitative (don't over-infer)        | Runtime judge            | SLM/LLM behavior judge     |

The compiler must **not** treat an AgentBehavior text as a *hint* that trace statistics happened to show. A behavior declared in the contract is a **non-removable invariant** during workflow synthesis.

## 6. Compiler invariants

```text
Agent Trace
   ├── Output Quality
   └── Behavior Compliance
            ↓
     Accepted Trace Set
            ↓
       Work Compiler
            ├── Workflow synthesis
            └── Invariants (locked behaviors)
            └── Executor candidates (code / ML / SLM)
```

Compiled output is therefore `workflow + invariants + executor model`, not workflow alone.

## 7. Behavior evaluation model (judges)

Per-behavior verdicts over a trajectory, using the `true / false / na` convention:

- `true`  — trigger fired and required conduct observed
- `false` — trigger fired, conduct missing/failed
- `na`    — no trigger in this trajectory, or unjudgeable

Judge each behavior independently, and **fold** into a per-workflow result with a deterministic rule (adopt the calibrated convention from AgentBehavior rather than inventing a score):

```text
any behavior false  → FAIL (regardless of outcome or others)
else any true       → PASS with evidence
else                → na
```

This keeps debugging at the granularity of `verify-contract: true / approval-before-send: false` instead of a single opaque `98%`, and prevents a lucky-correct outcome from passing a behavior it did not perform.

### Calibration discipline (adopted from AgentBehavior)

Before a behavior ships, it must pass a fixture matrix:

```text
Positive            trigger fires, conduct present → judge true
Negative            trigger fires, conduct absent  → judge false
Lucky-correct       outcome correct, process wrong → judge false (MUST stay false)
Outside scope       no trigger                     → na
Allowed boundary    permitted alternative path     → PASS (not penalized)
```

Disagreement diagnosis happens at the owning layer (wording / fixture / judge / telemetry / policy), never by contorting the behavior text to satisfy a broken judge.

### Separation of evaluated agent and judge

The evaluated agent does **not** receive the behavior spec merely because it is being evaluated — otherwise the eval measures promptability, not conduct. (Behaviors are injected as runtime instruction only when that is the deliberate, documented experiment.)

## 8. Where behavior evaluation runs

Behaviors split into three enforcement layers:

```text
Compile-time    rule/policy expressions
Runtime         dedicated approval gates, workflow dependencies
Post-hoc        behavior judges over recorded trajectories
```

Post-hoc judges run on both:

- **Discovery traces** — before compilation (result quality + behavior compliance → accepted trace set)
- **Production traces** — after deployment (drift / regression detection → recompile trigger)

## 9. Behavior Registry (sparse + lifecycle)

Adopt AgentBehavior's sparse principle: a behavior belongs only if it is recurring, consequential, a real choice, observable, durable, and debuggable. 1 workflow → 214 behaviors → 72 rules → 28 evaluators is the failure mode.

Registry lifecycle, run by the compiler continuously:

```text
add → deduplicate → merge → generalize → retire
```

Cross-workflow consolidation is first-class, mirroring Model Consolidation:

```text
Behavior A: check customer identity
Behavior B: verify customer's CRM record
Behavior C: confirm customer before contract query
        →  merge →  verify-customer-identity
```

Three consolidation loops run in parallel in the backend: **Workflow Consolidation · Model Consolidation · Behavior Consolidation**.

## 10. Executor Optimizer gate (SLM/LLM/code swap)

v1 said "just slot behavior checks into the optimizer." v2 specifies the promotion gate:

```text
output_quality >= threshold                (result)
AND behavior_compliance >= threshold       (process — new, mandatory)
AND cost_improves
AND latency_acceptable
```

Behavior compliance is measured on **held-out production-ish traces**, not the training set, using the fold rule above. A frontier→SLM swap that keeps 98% output accuracy while dropping the "use-current-pricing-policy" check 40% of the time is rejected.

```text
behavior: always-check-current-pricing-policy
   Frontier Agent Trace   PASS
   SLM Trace              FAIL   ← swap blocked
```

## 11. Dependency posture

- **Format**: support AgentBehavior `BEHAVIOR.md` natively + provide an importer/exporter so specs are portable.
- **Execution**: OpenWorkflow owns the registry, runtime policy, and judges. AgentBehavior provides the standard, not the engine.
- **License**: Apache-2.0 — borrow with attribution, no structural risk.

## 12. Human review surface (unchanged UX, richer backend)

People still review one output card; the behavior layer stays behind it.

```text
                  Production Trace
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
       Automated Behavior      Output Quality
            Judges
              │                     │
              │                     ▼
              │              Human Reviewer
              │                     │
              └─────────┬───────────┘
                        ▼
                   Quality Record
```

Human card:

```text
계약 갱신안 #182

결과 품질
★★★★★
[승인]

자동 검증
✓ 최신 계약 확인
✓ 최신 가격 정책 사용
✓ 가격 계산 검증
✓ 외부 발송 전 승인
```

Behavior verdicts surface as **explainable checkmarks**; the full per-behavior `true/false/na` record is available on drill-down for review, not as a required reading surface.

## 13. Updated loop (v2)

```text
              Frontier Agent
                    │
                    ▼
             Raw Work Trace
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
    Result Quality       Behavior Eval
       Human             Automated
          │                   │
          └────────┬──────────┘
                   ▼
            Approved Traces
                   │
                   ▼
           LLM-as-Compiler
                   │
       ┌───────────┼────────────┐
       ▼           ▼            ▼
   Behavior      Workflow     Executor
  Invariants    Graph        Candidates
       │           │            │
       │           │      Code / ML / SLM
       └───────────┼────────────┘
                   ▼
             OpenWorkflow
                 Runtime
                   │
                   ▼
               Production
                   │
          ┌────────┴────────┐
          ▼                 ▼
    Behavior Judge      Human Sample
          │             Quality Review
          └────────┬────────┘
                   ▼
               Feedback
                   │
                   ▼
          Recompile / Optimize
```

## 14. Owner agents in this repo

The behavior layer maps onto the sub-agents defined under `agents/`:

```text
guide_agent                     → prompts users to define behaviors explicitly (side panel)
definition_measurer             → flags behaviors missing from work.yaml
compilation_readiness_measurer  → classifies each behavior into rule / transition / judge
quality_measurer                → judges outcome quality per quality criteria
optimization_impact_measurer    → applies the 4-condition executor gate (now includes behavior compliance)
improvement_reporter            → folds per-behavior verdicts into the user summary
```

## 15. Key decisions (v2 summary)

| # | Decision |
| - | - |
| 1 | Compliment system philosophy: humans evaluate outcomes; the system evaluates behavior + outcomes |
| 2 | Native Behavior Contract (AgentBehavior-format) under each work definition |
| 3 | Three-way compile classification with an explicit compiler decision procedure |
| 4 | Deterministic `true/false/na` fold; per-behavior records, not aggregate scores |
| 5 | Calibration fixture matrix mandatory before a behavior ships (lucky-correct stays false) |
| 6 | Executor swap gate adds mandatory `behavior_compliance` |
| 7 | Behavior Registry with add/dedupe/merge/generalize/retire lifecycle + cross-workflow consolidation |
| 8 | Behavior judges run on discovery + production traces |
| 9 | Runtime enforcement only where deterministic; semantic behaviors stay judge-based |
| 10 | Support AgentBehavior format; do not depend on it as a runtime |
```