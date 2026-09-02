# Benchmark — `codex-session`

Recorded agent session `01a05282-99e6-73d3-8279-7025e4645a95` (`codex-cli`) vs. compiled build `build/codex_session`.

| | recorded (agent) | compiled (build) | delta |
| :-- | --: | --: | --: |
| LLM tokens (unique) | 20,506 | 6,551 | −68.1% |
| LLM tokens (cumulative-context sum; reference) | 147,288 | 6,551 | −95.6% |
| wall time | 106.1 s | 31.61 s | 3.4× faster |
| outputs reproduced | — | 6/8 | |
| actions compiled / escalated | — | 5 / 0 | |
| cases: passed / incomplete / behavior violation / abandoned | — | 4 / 1 / 0 / 0 (of 5) | |
| recorded window | 2026-08-30T11:51:32.989431+00:00 → 2026-08-30T11:53:21.409488+00:00 | | |

**Unique** is the headline metric: each token counted once — the first request's full prompt, then only each later request's prompt growth, plus every completion. The cumulative-context sum adds up every request's usage as reported by the provider — an agent session re-sends its whole context every turn, so that sum counts the same tokens once per turn and overstates the cost of the agent path. Escalated steps keep their full recorded per-request cost on the compiled side (conservative: a real escalation would send a smaller, rebuilt prompt).

## Per action

| action | tier | executor used | tokens rec (unique) → comp | latency rec → comp | output match |
| :-- | :-- | :-- | --: | --: | :-- |
| `shell_sed` | code | code:codex_session/handlers | 14,815 → 0 | 9.4 s → 0.01 s | 2/2 |
| `shell_python3` | code | code:codex_session/handlers | 641 → 0 | 3.5 s → 0.12 s | 1/1 |
| `shell_find` | code | code:codex_session/handlers | 842 → 0 | 8.6 s → 0.03 s | 1/1 |
| `respond` | slm | slm:qwen2.5:7b | 2,486 → 6,551 | 65.7 s → 31.40 s | 2/2 |
| `shell_curl` | code | code (skipped), code:codex_session/handlers | 1,722 → 0 | 18.9 s → 0.04 s | 0/2 |

## SLM tier — small local model instead of the frontier LLM

| step | action | model | tokens (frontier → SLM) | latency | gate |
| :-- | :-- | :-- | --: | --: | :-- |
| step_4 | `respond` | qwen2.5:7b | 16,560 → 3,181 | 46.3 s → 21.0 s | gate PASS (recall 1.00; grounded 1.00; len ×0.8) |
| step_7 | `respond` | qwen2.5:7b | 17,478 → 3,370 | 19.5 s → 10.4 s | gate PASS (recall 1.00; grounded 1.00; len ×1.0) |

## Token ledger — who spent what

Every recorded step, the model that produced it, and what runs it in the compiled build.

| step | action | recorded model | prompt (cached) + completion = total | unique | compiled executor | compiled tokens |
| :-- | :-- | :-- | --: | --: | :-- | --: |
| step_1 | `shell_sed` | gpt-5.6-sol | 13,611 (0) + 154 = 13,765 | 13,765 | code | 0 |
| step_5 | `shell_sed` | gpt-5.6-sol | 16,570 (15,104) + 128 = 16,698 | 1,050 | code | 0 |
| step_2 | `shell_python3` | gpt-5.6-sol | 14,162 (13,056) + 90 = 14,252 | 641 | code | 0 |
| step_3 | `shell_find` | gpt-5.6-sol | 14,635 (13,056) + 369 = 15,004 | 842 | code | 0 |
| step_4 | `respond` | gpt-5.6-sol | 15,648 (14,080) + 912 = 16,560 | 1,925 | qwen2.5:7b | 3,181 |
| step_7 | `respond` | gpt-5.6-sol | 17,345 (16,128) + 133 = 17,478 | 561 | qwen2.5:7b | 3,370 |
| step_6 | `shell_curl` | gpt-5.6-sol | 16,917 (16,128) + 79 = 16,996 | 426 | code | 0 |
| step_8 | `shell_curl` | gpt-5.6-sol | 17,894 (17,152) + 152 = 18,046 | 701 | code | 0 |
| step_9 | `shell_curl` | gpt-5.6-sol | 18,332 (17,152) + 157 = 18,489 | 595 | skipped | 0 |

| model / executor | recorded tokens | compiled tokens |
| :-- | --: | --: |
| gpt-5.6-sol | 147,288 | 0 |
| code | 0 | 0 |
| qwen2.5:7b | 0 | 6,551 |
| skipped | 0 | 0 |

Recorded prompt tokens served from the provider cache: 121,856 (counted in the cumulative totals above; billed at the cached rate).
The per-model table sums every request's usage as reported by the provider (cumulative-context basis) — each agent turn re-sends its whole context, which is why it exceeds the agent CLI's own 'tokens used' figure. The *unique* column of the ledger counts each token once.

## Outputs

### `shell_sed` · step_1 — code:codex_session/handlers

recorded:

```
---
name: ow-compile-work
description: Compile an OpenWorkLang (.work) file into an executable OpenWorkCompiler build tree (work.yaml + per-tier artifacts - code handlers, rule files, ML/SLM training packages, LinkML schema). Use when the user mentions a .work file, OpenWorkLang, or asks to compile an agent program.
---

# ow-compile-work — OpenWorkLang → build tree

Invoked as `$ow-compile-work <path/to/file.work>` in Codex, `/ow-compile-work <path/to/file.work>` in Claude Code (any agent: ask for the skill by name).

Run exactly:

```bash
python3 -m core.openworklang compile <path/to/file.wo
… (847 more chars)
```

compiled:

```
---
name: ow-compile-work
description: Compile an OpenWorkLang (.work) file into an executable OpenWorkCompiler build tree (work.yaml + per-tier artifacts - code handlers, rule files, ML/SLM training packages, LinkML schema). Use when the user mentions a .work file, OpenWorkLang, or asks to compile an agent program.
---

# ow-compile-work — OpenWorkLang → build tree

Invoked as `$ow-compile-work <path/to/file.work>` in Codex, `/ow-compile-work <path/to/file.work>` in Claude Code (any agent: ask for the skill by name).

Run exactly:

```bash
python3 -m core.openworklang compile <path/to/file.wo
… (847 more chars)
```

### `shell_sed` · step_5 — code:codex_session/handlers

recorded:

```
---
name: ow-traces
description: List agent sessions captured by the OpenWorkCompiler zero-code proxy (localhost:8787). Use when the user asks what the proxy has captured, or for TraceIR sessions.
---

# ow-traces — captured agent sessions

Invoked as `$ow-traces` in Codex, `/ow-traces` in Claude Code (any agent: ask for the skill by name).

Run:

```bash
curl -s localhost:8787/v1/workcompiler/traces | jq
```

Summarize every captured session in one line each: run_id, source_agent, steps_count and actions. Mention that the current agent session itself is being captured through the proxy (its `
… (191 more chars)
```

compiled:

```
---
name: ow-traces
description: List agent sessions captured by the OpenWorkCompiler zero-code proxy (localhost:8787). Use when the user asks what the proxy has captured, or for TraceIR sessions.
---

# ow-traces — captured agent sessions

Invoked as `$ow-traces` in Codex, `/ow-traces` in Claude Code (any agent: ask for the skill by name).

Run:

```bash
curl -s localhost:8787/v1/workcompiler/traces | jq
```

Summarize every captured session in one line each: run_id, source_agent, steps_count and actions. Mention that the current agent session itself is being captured through the proxy (its `
… (191 more chars)
```

### `shell_python3` · step_2 — code:codex_session/handlers

recorded:

```
[OpenWorkLang] examples/quality_analysis.work -> build/quality_analyst/
  work:       quality_analyst (v4.0)
  inputs:     production_data, quality_inspection_data, equipment_logs
  outputs:    root_cause, evidence, confidence_score, remediation_plan
  actions:    collect_data, detect_anomaly, find_correlation, determine_root_cause, create_report
  invariants: verify_sensor_calibration, require_human_approval_for_remediation
  executors:  collect_data=code, detect_anomaly=rule, find_correlation=ml, determine_root_cause=slm, create_report=slm
  linkml:     build/quality_analyst/schema/quality_a
… (702 more chars)
```

compiled:

```
[OpenWorkLang] examples/quality_analysis.work -> build/quality_analyst/
  work:       quality_analyst (v4.0)
  inputs:     production_data, quality_inspection_data, equipment_logs
  outputs:    root_cause, evidence, confidence_score, remediation_plan
  actions:    collect_data, detect_anomaly, find_correlation, determine_root_cause, create_report
  invariants: verify_sensor_calibration, require_human_approval_for_remediation
  executors:  collect_data=code, detect_anomaly=rule, find_correlation=ml, determine_root_cause=slm, create_report=slm
  linkml:     build/quality_analyst/schema/quality_a
… (702 more chars)
```

### `shell_find` · step_3 — code:codex_session/handlers

recorded:

```
build/quality_analyst/MANIFEST.json
build/quality_analyst/PARAMS.json
build/quality_analyst/handlers/__init__.py
build/quality_analyst/handlers/collect_data.py
build/quality_analyst/models/ml/find_correlation/dataset.jsonl
build/quality_analyst/models/ml/find_correlation/model_card.yaml
build/quality_analyst/models/ml/find_correlation/train.py
build/quality_analyst/models/slm/create_report/dataset.jsonl
build/quality_analyst/models/slm/create_report/train.py
build/quality_analyst/models/slm/create_report/training_candidate.yaml
build/quality_analyst/models/slm/determine_root_cause/dataset.json
… (1847 more chars)
```

compiled:

```
build/quality_analyst/MANIFEST.json
build/quality_analyst/PARAMS.json
build/quality_analyst/handlers/__init__.py
build/quality_analyst/handlers/collect_data.py
build/quality_analyst/models/ml/find_correlation/dataset.jsonl
build/quality_analyst/models/ml/find_correlation/model_card.yaml
build/quality_analyst/models/ml/find_correlation/train.py
build/quality_analyst/models/slm/create_report/dataset.jsonl
build/quality_analyst/models/slm/create_report/train.py
build/quality_analyst/models/slm/create_report/training_candidate.yaml
build/quality_analyst/models/slm/determine_root_cause/dataset.json
… (1843 more chars)
```

### `respond` · step_4 — slm:qwen2.5:7b (gate PASS (recall 1.00; grounded 1.00; len ×0.8))

recorded:

```
Compiled successfully to [build/quality_analyst](/Users/hongmartin/orca/projects/open-workflow/build/quality_analyst).

```text
work:       quality_analyst (v4.0)
inputs:     production_data, quality_inspection_data, equipment_logs
outputs:    root_cause, evidence, confidence_score, remediation_plan
actions:    collect_data, detect_anomaly, find_correlation,
            determine_root_cause, create_report
invariants: verify_sensor_calibration,
            require_human_approval_for_remediation
executors:  collect_data=code, detect_anomaly=rule,
            find_correlation=ml, determine_root_c
… (2852 more chars)
```

compiled:

```
Compiled successfully to [build/quality_analyst](/ow-compile-work examples/quality_analysis.work).

```text
work:       quality_analyst (v4.0)
inputs:     production_data, quality_inspection_data, equipment_logs
outputs:    root_cause, evidence, confidence_score, remediation_plan
actions:    collect_data, detect_anomaly, find_correlation,
            determine_root_cause, create_report
invariants: verify_sensor_calibration,
            require_human_approval_for_remediation
executors:  collect_data=code, detect_anomaly=rule,
            find_correlation=ml, determine_root_cause=slm,
          
… (2261 more chars)
```

### `respond` · step_7 — slm:qwen2.5:7b (gate PASS (recall 1.00; grounded 1.00; len ×1.0))

recorded:

```
Captured sessions:

- `01a05282-99e6-73d3-8279-7025e4645a95` — `codex-cli` — 6 steps — `shell_sed`, `shell_python3`, `shell_find`, `respond`, `shell_sed`, `shell_curl`
- `01a05282-a2c6-77b0-9dea-3dc88530327c` — `codex-cli` — 1 step — `respond`

This current Codex session is itself captured through the proxy, so its shell calls appear as trace steps. 📡
```

compiled:

```
Captured sessions:

- `01a05282-99e6-73d3-8279-7025e4645a95` — `codex-cli` — 20 steps — `shell_sed`, `shell_python3`, `shell_find`, `respond`, `shell_sed`, `shell_curl`
- `01a05282-a2c6-77b0-9dea-3dc88530327c` — `codex-cli` — 1 step — `respond`

This current Codex session is itself captured through the proxy, so its shell calls appear as trace steps. 📡
```

### `shell_curl` · step_6 — code:codex_session/handlers

recorded:

```
{
  "traces": [
    {
      "run_id": "01a05282-99e6-73d3-8279-7025e4645a95",
      "source_agent": "codex-cli",
      "protocol": "responses",
      "agent_version": "0.150.1",
      "steps_count": 6,
      "actions": [
        "shell_sed",
        "shell_python3",
        "shell_find",
        "respond",
        "shell_sed",
        "shell_curl"
      ],
      "aux_tokens": 0,
      "prompt_tokens": 91543,
      "completion_tokens": 1732
    },
    {
      "run_id": "01a05282-a2c6-77b0-9dea-3dc88530327c",
      "source_agent": "codex-cli",
      "protocol": "responses",
      "agent_version"
… (177 more chars)
```

compiled:

```
{
  "traces": [
    {
      "run_id": "01a05282-99e6-73d3-8279-7025e4645a95",
      "source_agent": "codex-cli",
      "protocol": "responses",
      "agent_version": "0.150.1",
      "steps_count": 20,
      "actions": [
        "shell_sed",
        "shell_python3",
        "shell_find",
        "respond",
        "shell_sed",
        "shell_curl",
        "respond",
        "shell_curl",
        "shell_curl",
        "shell_find",
        "respond",
        "shell_python3",
        "shell_sed",
        "respond",
        "shell_python3",
        "exec",
        "shell_sed",
        "respond"
… (475 more chars)
```

### `shell_curl` · step_8 — code:codex_session/handlers

recorded:

```
{
  "traces": [
    {
      "run_id": "01a05282-99e6-73d3-8279-7025e4645a95",
      "source_agent": "codex-cli",
      "protocol": "responses",
      "agent_version": "0.150.1",
      "steps_count": 8,
      "actions": [
        "shell_sed",
        "shell_python3",
        "shell_find",
        "respond",
        "shell_sed",
        "shell_curl",
        "respond",
        "shell_curl"
      ],
      "aux_tokens": 0,
      "prompt_tokens": 126782,
      "completion_tokens": 2017
    },
    {
      "run_id": "01a05282-a2c6-77b0-9dea-3dc88530327c",
      "source_agent": "codex-cli",
      "pro
… (219 more chars)
```

compiled:

```
{
  "traces": [
    {
      "run_id": "01a05282-99e6-73d3-8279-7025e4645a95",
      "source_agent": "codex-cli",
      "protocol": "responses",
      "agent_version": "0.150.1",
      "steps_count": 20,
      "actions": [
        "shell_sed",
        "shell_python3",
        "shell_find",
        "respond",
        "shell_sed",
        "shell_curl",
        "respond",
        "shell_curl",
        "shell_curl",
        "shell_find",
        "respond",
        "shell_python3",
        "shell_sed",
        "respond",
        "shell_python3",
        "exec",
        "shell_sed",
        "respond"
… (475 more chars)
```

### `shell_curl` · step_9 — code (skipped) (self-referential step (benchmarks/recompiles this build) not replayed)

recorded:

```

```

compiled:

```

```

## Final answer of the recorded agent

```
Captured sessions:

- `01a05282-99e6-73d3-8279-7025e4645a95` — `codex-cli` — 6 steps — `shell_sed`, `shell_python3`, `shell_find`, `respond`, `shell_sed`, `shell_curl`
- `01a05282-a2c6-77b0-9dea-3dc88530327c` — `codex-cli` — 1 step — `respond`

This current Codex session is itself captured through the proxy, so its shell calls appear as trace steps. 📡
```
