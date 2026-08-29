# Benchmark — `codex-session`

Recorded agent session `01a04b02-4d50-71d1-8112-430bb6ede9c1` (`codex_exec`) vs. compiled build `build/codex_session`.

| | recorded (agent) | compiled (build) | delta |
| :-- | --: | --: | --: |
| LLM tokens | 46,680 | 16,782 | −64.0% |
| wall time | 29.9 s | 17.43 s | 1.7× faster |
| outputs reproduced | — | 2/2 | |
| actions compiled / escalated | — | 2 / 1 | |

## Per action

| action | tier | executor used | tokens rec → comp | latency rec → comp | output match |
| :-- | :-- | :-- | --: | --: | :-- |
| `shell_python3` | code | code:codex_session/handlers | 14,520 → 0 | 5.9 s → 0.11 s | 1/1 |
| `shell_find` | code | code:codex_session/handlers | 15,378 → 0 | 6.7 s → 0.02 s | 1/1 |
| `respond` | frontier_llm | escalated:frontier_llm | 16,782 → 16,782 | 17.3 s → 17.31 s | n/a |

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
… (633 more chars)
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
… (633 more chars)
```

### `shell_find` · step_2 — code:codex_session/handlers

recorded:

```
{"tree":"build/quality_analyst/MANIFEST.json\nbuild/quality_analyst/handlers/__init__.py\nbuild/quality_analyst/handlers/collect_data.py\nbuild/quality_analyst/models/ml/find_correlation/dataset.jsonl\nbuild/quality_analyst/models/ml/find_correlation/model_card.yaml\nbuild/quality_analyst/models/ml/find_correlation/train.py\nbuild/quality_analyst/models/slm/create_report/dataset.jsonl\nbuild/quality_analyst/models/slm/create_report/train.py\nbuild/quality_analyst/models/slm/create_report/training_candidate.yaml\nbuild/quality_analyst/models/slm/determine_root_cause/dataset.jsonl\nbuild/quality
… (1566 more chars)
```

compiled:

```
build/quality_analyst/MANIFEST.json
build/quality_analyst/handlers/__init__.py
build/quality_analyst/handlers/collect_data.py
build/quality_analyst/models/ml/find_correlation/dataset.jsonl
build/quality_analyst/models/ml/find_correlation/model_card.yaml
build/quality_analyst/models/ml/find_correlation/train.py
build/quality_analyst/models/slm/create_report/dataset.jsonl
build/quality_analyst/models/slm/create_report/train.py
build/quality_analyst/models/slm/create_report/training_candidate.yaml
build/quality_analyst/models/slm/determine_root_cause/dataset.jsonl
build/quality_analyst/models/slm
… (1438 more chars)
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
  actions:    collect_data, detect_anomaly, find_correlation,
              determine_root_cause, create_report
  invariants: verify_sensor_calibration,
              require_human_approval_for_remediation
  executors:  collect_data=code, detect_anomaly=rule,
              find_correlation=ml, determine_root_cause=s
… (2817 more chars)
```

compiled:

```
Compilation succeeded.

```text
[OpenWorkLang] examples/quality_analysis.work -> build/quality_analyst/
  work:       quality_analyst (v4.0)
  inputs:     production_data, quality_inspection_data, equipment_logs
  outputs:    root_cause, evidence, confidence_score, remediation_plan
  actions:    collect_data, detect_anomaly, find_correlation,
              determine_root_cause, create_report
  invariants: verify_sensor_calibration,
              require_human_approval_for_remediation
  executors:  collect_data=code, detect_anomaly=rule,
              find_correlation=ml, determine_root_cause=s
… (2817 more chars)
```

## Final answer of the recorded agent

```
Compilation succeeded.

```text
[OpenWorkLang] examples/quality_analysis.work -> build/quality_analyst/
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
  linkml:     build/quality_analyst/schema/quality_analyst.linkml.yaml
```

Generated tree:

```text
build/quality_analyst/MANIFEST.json
build/quality_analyst/handlers/__init__.py
build/quality_analyst/handlers/collect_data.py
build/quality_analyst/models/ml/find_correlation/dataset.jsonl
build/quality_analyst/models/ml/find_correlation/model_card.yaml
build/quality_analyst/models/ml/find_correlation/train.py
build/quality_analyst/models/slm/create_report/dataset.jsonl
build/quality_analyst/models/slm/create_report/train.py
build/quality_analyst/models/slm/c
… (2217 more chars)
```
