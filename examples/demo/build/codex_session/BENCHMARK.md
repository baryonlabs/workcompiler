# Benchmark — `codex-session`

Recorded agent session `01a04b1c-99ae-7733-8b77-814966c86046` (`codex_exec`) vs. compiled build `build/codex_session`.

| | recorded (agent) | compiled (build) | delta |
| :-- | --: | --: | --: |
| LLM tokens | 46,460 | 16,843 | −63.7% |
| wall time | 33.8 s | 23.13 s | 1.5× faster |
| outputs reproduced | — | 2/2 | |
| actions compiled / escalated | — | 2 / 1 | |

## Per action

| action | tier | executor used | tokens rec → comp | latency rec → comp | output match |
| :-- | :-- | :-- | --: | --: | :-- |
| `shell_python3` | code | code:codex_session/handlers | 14,436 → 0 | 3.6 s → 0.10 s | 1/1 |
| `shell_find` | code | code:codex_session/handlers | 15,181 → 0 | 7.2 s → 0.01 s | 1/1 |
| `respond` | frontier_llm | escalated:frontier_llm | 16,843 → 16,843 | 23.0 s → 23.02 s | n/a |

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

### `shell_find` · step_2 — code:codex_session/handlers

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
… (1515 more chars)
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
… (1515 more chars)
```

### `respond` · step_3 — escalated:frontier_llm (kept recorded cost (frontier/human tier))

recorded:

```
Compilation succeeded.

```text
[OpenWorkLang] examples/quality_analysis.work -> build/quality_analyst/
  work:       quality_analyst (v4.0)
  inputs:     production_data, quality_inspection_data, equipment_logs
  outputs:    root_cause, evidence, confidence_score, remediation_plan
  actions:    collect_data, detect_anomaly, find_correlation, determine_root_cause, create_report
  invariants: verify_sensor_calibration, require_human_approval_for_remediation
  executors:  collect_data=code, detect_anomaly=rule, find_correlation=ml, determine_root_cause=slm, create_report=slm
  linkml:     build/
… (3583 more chars)
```

compiled:

```
Compilation succeeded.

```text
[OpenWorkLang] examples/quality_analysis.work -> build/quality_analyst/
  work:       quality_analyst (v4.0)
  inputs:     production_data, quality_inspection_data, equipment_logs
  outputs:    root_cause, evidence, confidence_score, remediation_plan
  actions:    collect_data, detect_anomaly, find_correlation, determine_root_cause, create_report
  invariants: verify_sensor_calibration, require_human_approval_for_remediation
  executors:  collect_data=code, detect_anomaly=rule, find_correlation=ml, determine_root_cause=slm, create_report=slm
  linkml:     build/
… (3583 more chars)
```

## Final answer of the recorded agent

```
Compilation succeeded.

```text
[OpenWorkLang] examples/quality_analysis.work -> build/quality_analyst/
  work:       quality_analyst (v4.0)
  inputs:     production_data, quality_inspection_data, equipment_logs
  outputs:    root_cause, evidence, confidence_score, remediation_plan
  actions:    collect_data, detect_anomaly, find_correlation, determine_root_cause, create_report
  invariants: verify_sensor_calibration, require_human_approval_for_remediation
  executors:  collect_data=code, detect_anomaly=rule, find_correlation=ml, determine_root_cause=slm, create_report=slm
  linkml:     build/quality_analyst/schema/quality_analyst.linkml.yaml
  artifacts:
    work_ir       work.yaml
    code          handlers/collect_data.py
    rule          rules/detect_anomaly.rule.yaml
    ml            models/ml/find_correlation/model_card.yaml, models/ml/find_correlation/dataset.jsonl, models/ml/find_correlation/train.py
    slm           models/slm/determine_root_cause/training_candidate.yaml, models/slm/determine_root_cause/dataset.jsonl, models/slm/determine_root_cause/train.py, models/slm/create_report/training_candidate.yaml, models/slm/create_report/dataset.jsonl, models/slm/create_repo
… (2983 more chars)
```
