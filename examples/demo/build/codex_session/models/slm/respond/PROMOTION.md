# SLM promotion — `respond` of `codex-session`

Candidate: `qwen2.5:3b` at `http://127.0.0.1:11434/v1` (local, cost $0) · gate: ≥90% of evaluations PASS, anchor recall ≥90%, grounding ≥90%.

**Result: PROMOTED** — pass rate 100% over 2 recorded example(s).

| | recorded (frontier) | SLM | delta |
| :-- | --: | --: | --: |
| tokens | 35,510 | 6,124 | −82.8% |
| latency | 29.5 s | 18.3 s | 1.62× |

## Evaluations

| step | recorded model → tokens | SLM tokens (prompt + completion) | latency | gate |
| :-- | :-- | --: | --: | :-- |
| step_3 | gpt-5.6-sol → 17,344 | 3,274 (2,574 + 700) | 13.4 s | PASS (recall 0.94; grounded 1.00; len ×0.7; missing schema/quality_analyst.linkml.yaml) |
| step_5 | gpt-5.6-sol → 18,166 | 2,850 (2,704 + 146) | 4.8 s | PASS (recall 1.00; grounded 1.00; len ×1.0) |

### step_3 — SLM output

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
            determine_root_cause=slm
            create_report=slm
linkml:     build/quality_analyst/schema/quality_analyst.linkml.yaml
artifacts:
  work_ir       work.yaml
  code          handlers/collect_data.py
  rule          rules/detect_anomaly.rule.yaml
  ml            models/ml/find_correlation/model_card.yaml, models/ml/find_correlation/dataset.jsonl, models/ml/find_correlation/train.py
  slm           models/slm/determine_root_cause/training_candidate.yaml, models/slm/determine_root_cause/dataset.jsonl, models/slm/determine_root_cause/train.py, models/slm/create_report/training_candidate.yaml, models/slm/create_report/dataset.jsonl, models/slm/create_report/train.py
  params        PARAMS.json
  schema        build/quality_analyst/schema/quality_analyst.linkml.yaml
  openworklang  quality_analyst.work
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
wo
… [265 more chars]
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
executors:  collect_data=code
            detect_anomaly=rule
            find_correlation=ml
            determine_root_cause=slm
            create_report=slm
linkml:     build/quality_analyst/schema/quality_analyst.linkml.yaml
artifacts:
  work_ir       work.yaml
  code          handlers/collect_data.py
  rule          rules/detect_anomaly.rule.yaml
  ml            models/ml/find_correlation/{model_card.yaml,dataset.jsonl,train.py}
  slm           models/slm/determine_root_cause/{training_candidate.yaml,dataset.jsonl,train.py}
                models/slm/create_report/{training_candidate.yaml,dataset.jsonl,train.py}
  params        PARAMS.json
  schema        schema/quality_analyst.linkml.yaml
  openworklang  quality_analyst.work
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
  - quality_in
… [1614 more chars]
```

### step_5 — SLM output

```
Captured sessions:

- `01a04c51-c1ca-7512-8b81-20d832a84b85` — `codex-cli` — 4 steps — `shell_python3`, `shell_find`, `respond`, `shell_curl`
- `01a04c51-f7d2-7de0-9ae2-8ec624f02dfd` — `codex-cli` — 1 step — `respond`

This current Codex session is itself being captured through the proxy, so its shell calls—including this trace query—appear as steps. 📡
```

Recorded (frontier) output:

```
Captured sessions:

- `01a04c51-c1ca-7512-8b81-20d832a84b85` — `codex-cli` — 4 steps — `shell_python3`, `shell_find`, `respond`, `shell_curl`
- `01a04c51-f7d2-7de0-9ae2-8ec624f02dfd` — `codex-cli` — 1 step — `respond`

This current Codex session is itself being captured through the proxy, so its shell calls—including this trace query—appear as steps. 📡
```

How the gate works: *anchors* are the numbers / ids / file paths the frontier answer stated that also exist in the upstream step outputs; the SLM must restate them (recall) and must not state numbers that exist nowhere in its inputs (grounding). Process invariants are enforced by the compiled upstream steps.
