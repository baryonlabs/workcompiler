# SLM promotion — `respond` of `codex-session`

Candidate: `qwen2.5:7b` at `http://127.0.0.1:11434/v1` (local, cost $0) · gate: ≥90% of evaluations PASS, anchor recall ≥90%, grounding ≥90%.

**Result: PROMOTED** — pass rate 100% over 2 recorded example(s).

| | recorded (frontier) | SLM | delta |
| :-- | --: | --: | --: |
| tokens | 34,038 | 5,926 | −82.6% |
| latency | 65.7 s | 35.7 s | 1.84× |

## Evaluations

| step | recorded model → tokens | SLM tokens (prompt + completion) | latency | gate |
| :-- | :-- | --: | --: | :-- |
| step_4 | gpt-5.6-sol → 16,560 | 2,873 (2,225 + 648) | 24.3 s | PASS (recall 1.00; grounded 1.00; len ×0.8) |
| step_7 | gpt-5.6-sol → 17,478 | 3,053 (2,898 + 155) | 11.4 s | PASS (recall 1.00; grounded 1.00; len ×1.0) |

### step_4 — SLM output

```
Compiled successfully to [build/quality_analyst](/ow-compile-work <path/to/file.work>).

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
            create_report=slm
```

Generated tree:

```text
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
build/quality_analyst/models/slm/determine_root_cause/dataset.jsonl
build/quality_analyst/models/slm/determine_root_cause/train.py
build/quality_analyst/models/slm/determine_root_cause/training_candidate.yaml
build/quality_analyst/quality_analyst.work
build/quality_analyst/rules/detect_anomaly.rule.yaml
build/quality_analyst/schema/quality_analyst.linkml.yaml
build/quality_analyst/work.yaml
```

First 25 lines of [work.yaml](/build/quality_analyst/work.yaml):

```yaml
work: quality_analyst
version: '4.0'
description: Analyze production line quality anomaly root causes and generate remediation
  plans
inputs:
  - production_data
  - quality_inspection_data
  - equipment_logs
outputs:
  - root_cause
  - evidence
  - confidence_score
  - remediation_plan
states:
  - initialized
  - collect_data_completed
  - detect_anomaly_completed
  - find_correlation_completed
  - determine_root_cause_completed
  - create_report_completed
actions:
  - collect_data
  - detect_anomaly
  - find_correlation
  - determine_root_cause
```

The handler provides the deterministic `run(**inputs)` scaffold; the rule artifact encodes anomaly-detection branches; the ML package supplies its model card, dataset, and trainer; and the SLM packages supply promotion metadata, datasets, and TRL trainers. No frontier-LLM prompt was generated, 
… [100 more chars]
```

Recorded (frontier) output:

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
            find_correlation=ml, determine_root_cause=slm,
            create_report=slm
```

Generated tree:

```text
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
build/quality_analyst/models/slm/determine_root_cause/dataset.jsonl
build/quality_analyst/models/slm/determine_root_cause/train.py
build/quality_analyst/models/slm/determine_root_cause/training_candidate.yaml
build/quality_analyst/quality_analyst.work
build/quality_analyst/rules/detect_anomaly.rule.yaml
build/quality_analyst/schema/quality_analyst.linkml.yaml
build/quality_analyst/work.yaml
```

First 25 lines of [work.yaml](/Users/hongmartin/orca/projects/open-workflow/build/quality_analyst/work.yaml):

```yaml
work: quality_analyst
version: '4.0'
description: Analyze production line quality anomaly root causes and generate remediation
  plans
inputs:
  - production_data
  - quality_inspection_data
  - equipment_logs
outputs:
  - root_cause
  - evidence
  - confidence_score
  - remediation_plan
states:
  - initialized
  - collect_data_completed
  - detect_anomaly_completed
  - find_correlation_completed
  - determine_root_cause_completed
  - create_report_completed
actions:
  - collect_data
  - detect_anomaly
  - find_correlation
  - determine_root_cause
```

Generated [collect_data.py](/Users/hongmartin/orca/projects/open-workflow/build/quality_analyst/handlers/collect_data.py):

```python
"""collect_data — code-tier handler for work 'quality_analyst'.

generated by OpenWor
… [952 more chars]
```

### step_7 — SLM output

```
Captured sessions:

- `01a05282-99e6-73d3-8279-7025e4645a95` — `codex-cli` — 6 steps — `shell_sed`, `shell_python3`, `shell_find`, `respond`, `shell_sed`, `shell_curl`
- `01a05282-a2c6-77b0-9dea-3dc88530327c` — `codex-cli` — 1 step — `respond`

This current Codex session is itself captured through the proxy, so its shell calls appear as trace steps. 📡
```

Recorded (frontier) output:

```
Captured sessions:

- `01a05282-99e6-73d3-8279-7025e4645a95` — `codex-cli` — 6 steps — `shell_sed`, `shell_python3`, `shell_find`, `respond`, `shell_sed`, `shell_curl`
- `01a05282-a2c6-77b0-9dea-3dc88530327c` — `codex-cli` — 1 step — `respond`

This current Codex session is itself captured through the proxy, so its shell calls appear as trace steps. 📡
```

How the gate works: *anchors* are the numbers / ids / file paths the frontier answer stated that also exist in the upstream step outputs; the SLM must restate them (recall) and must not state numbers that exist nowhere in its inputs (grounding). Process invariants are enforced by the compiled upstream steps.
