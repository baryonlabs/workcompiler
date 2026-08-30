# Benchmark — `codex-session`

Recorded agent session `01a04c51-c1ca-7512-8b81-20d832a84b85` (`codex-cli`) vs. compiled build `build/codex_session`.

| | recorded (agent) | compiled (build) | delta |
| :-- | --: | --: | --: |
| LLM tokens | 119,974 | 6,292 | −94.8% |
| wall time | 65.0 s | 14.76 s | 4.4× faster |
| outputs reproduced | — | 4/6 | |
| actions compiled / escalated | — | 4 / 0 | |

## Per action

| action | tier | executor used | tokens rec → comp | latency rec → comp | output match |
| :-- | :-- | :-- | --: | --: | :-- |
| `shell_python3` | code | code:codex_session/handlers | 14,041 → 0 | 4.6 s → 0.12 s | 1/1 |
| `shell_find` | code | code:codex_session/handlers | 14,772 → 0 | 10.7 s → 0.03 s | 1/1 |
| `respond` | slm | slm:qwen2.5:3b | 35,510 → 6,292 | 29.5 s → 14.53 s | 2/2 |
| `shell_curl` | code | code (skipped), code:codex_session/handlers | 55,651 → 0 | 20.1 s → 0.08 s | 0/2 |

## SLM tier — small local model instead of the frontier LLM

| step | action | model | tokens (frontier → SLM) | latency | gate |
| :-- | :-- | :-- | --: | --: | :-- |
| step_3 | `respond` | qwen2.5:3b | 17,344 → 3,503 | 20.5 s → 10.9 s | gate PASS (recall 0.94; grounded 1.00; len ×0.7; missing schema/quality_analyst.linkml.yaml) |
| step_5 | `respond` | qwen2.5:3b | 18,166 → 2,789 | 9.0 s → 3.6 s | gate PASS (recall 1.00; grounded 1.00; len ×1.0) |

## Token ledger — who spent what

Every recorded step, the model that produced it, and what runs it in the compiled build.

| step | action | recorded model | prompt (cached) + completion = total | compiled executor | compiled tokens |
| :-- | :-- | :-- | --: | :-- | --: |
| step_1 | `shell_python3` | gpt-5.6-sol | 13,933 (0) + 108 = 14,041 | code | 0 |
| step_2 | `shell_find` | gpt-5.6-sol | 14,423 (13,056) + 349 = 14,772 | code | 0 |
| step_3 | `respond` | gpt-5.6-sol | 16,295 (14,080) + 1,049 = 17,344 | qwen2.5:3b | 3,503 |
| step_5 | `respond` | gpt-5.6-sol | 18,035 (17,152) + 131 = 18,166 | qwen2.5:3b | 2,789 |
| step_4 | `shell_curl` | gpt-5.6-sol | 17,598 (16,128) + 100 = 17,698 | code | 0 |
| step_6 | `shell_curl` | gpt-5.6-sol | 18,582 (17,152) + 119 = 18,701 | code | 0 |
| step_7 | `shell_curl` | gpt-5.6-sol | 19,053 (18,176) + 199 = 19,252 | skipped | 0 |

| model / executor | recorded tokens | compiled tokens |
| :-- | --: | --: |
| gpt-5.6-sol | 119,974 | 0 |
| code | 0 | 0 |
| qwen2.5:3b | 0 | 6,292 |
| skipped | 0 | 0 |

Recorded prompt tokens served from the provider cache: 95,744 (counted in the totals above; billed at the cached rate).
Totals are the sum of every request's usage as reported by the provider — each agent turn re-sends its whole context, which is why they exceed the agent CLI's own 'tokens used' figure.

## Outputs

### `shell_python3` · step_1 — code:codex_session/handlers

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

### `shell_find` · step_2 — code:codex_session/handlers (same lines, different order)

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
… (4920 more chars)
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
… (4920 more chars)
```

### `respond` · step_3 — slm:qwen2.5:3b (gate PASS (recall 0.94; grounded 1.00; len ×0.7; missing schema/quality_analyst.linkml.yaml))

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
executors:  collect_data=code
            detect_anomaly=rule
            find_correlation=ml
       
… (3514 more chars)
```

compiled:

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
executors:  collect_data=code
             detect_anomaly=rule
             find_correlation=ml
    
… (2201 more chars)
```

### `respond` · step_5 — slm:qwen2.5:3b (gate PASS (recall 1.00; grounded 1.00; len ×1.0))

recorded:

```
Captured sessions:

- `01a04c51-c1ca-7512-8b81-20d832a84b85` — `codex-cli` — 4 steps — `shell_python3`, `shell_find`, `respond`, `shell_curl`
- `01a04c51-f7d2-7de0-9ae2-8ec624f02dfd` — `codex-cli` — 1 step — `respond`

This current Codex session is itself being captured through the proxy, so its shell calls—including this trace query—appear as steps. 📡
```

compiled:

```
Captured sessions:

- `01a04c51-c1ca-7512-8b81-20d832a84b85` — `codex-cli` — 4 steps — `shell_python3`, `shell_find`, `respond`, `shell_curl`
- `01a04c51-f7d2-7de0-9ae2-8ec624f02dfd` — `codex-cli` — 1 step — `respond`

This current Codex session is itself being captured through the proxy, so its shell calls—including this trace query—appear as steps. 📡
```

### `shell_curl` · step_4 — code:codex_session/handlers

recorded:

```
{
  "traces": [
    {
      "run_id": "01a04c51-c1ca-7512-8b81-20d832a84b85",
      "source_agent": "codex-cli",
      "protocol": "responses",
      "agent_version": "0.150.1",
      "steps_count": 4,
      "actions": [
        "shell_python3",
        "shell_find",
        "respond",
        "shell_curl"
      ],
      "aux_tokens": 0,
      "prompt_tokens": 62249,
      "completion_tokens": 1606
    },
    {
      "run_id": "01a04c51-f7d2-7de0-9ae2-8ec624f02dfd",
      "source_agent": "codex-cli",
      "protocol": "responses",
      "agent_version": "0.150.1",
      "steps_count": 1,
     
… (135 more chars)
```

compiled:

```

```

### `shell_curl` · step_6 — code:codex_session/handlers

recorded:

```
{
  "traces": [
    {
      "run_id": "01a04c51-c1ca-7512-8b81-20d832a84b85",
      "source_agent": "codex-cli",
      "protocol": "responses",
      "agent_version": "0.150.1",
      "steps_count": 6,
      "actions": [
        "shell_python3",
        "shell_find",
        "respond",
        "shell_curl",
        "respond",
        "shell_curl"
      ],
      "aux_tokens": 0,
      "prompt_tokens": 98866,
      "completion_tokens": 1856
    },
    {
      "run_id": "01a04c51-f7d2-7de0-9ae2-8ec624f02dfd",
      "source_agent": "codex-cli",
      "protocol": "responses",
      "agent_version":
… (176 more chars)
```

compiled:

```

```

### `shell_curl` · step_7 — code (skipped) (self-referential step (benchmarks/recompiles this build) not replayed)

recorded:

```
The selected run is `01a04c51-c1ca-7512-8b81-20d832a84b85` with 6 captured steps. I’m compiling that run now.
```

compiled:

```

```

## Final answer of the recorded agent

```
Captured sessions:

- `01a04c51-c1ca-7512-8b81-20d832a84b85` — `codex-cli` — 4 steps — `shell_python3`, `shell_find`, `respond`, `shell_curl`
- `01a04c51-f7d2-7de0-9ae2-8ec624f02dfd` — `codex-cli` — 1 step — `respond`

This current Codex session is itself being captured through the proxy, so its shell calls—including this trace query—appear as steps. 📡
```
