# Benchmark — `quality-anomaly`

Recorded agent session `01a04b4a-85ef-7891-a7f3-7673fec23942` (`codex_exec`) vs. compiled build `build/quality_anomaly`.

| | recorded (agent) | compiled (build) | delta |
| :-- | --: | --: | --: |
| LLM tokens | 138,200 | 32,661 | −76.4% |
| wall time | 142.4 s | 12.67 s | 11.2× faster |
| outputs reproduced | — | 5/5 | |
| actions compiled / escalated | — | 2 / 1 | |

## Per action

| action | tier | executor used | tokens rec → comp | latency rec → comp | output match |
| :-- | :-- | :-- | --: | --: | :-- |
| `shell_sed` | code | code:quality_anomaly/handlers | 14,221 → 0 | 3.8 s → 0.01 s | 1/1 |
| `shell_python3` | code | code:quality_anomaly/handlers | 91,318 → 0 | 126.2 s → 0.29 s | 4/4 |
| `respond` | frontier_llm | escalated:frontier_llm | 32,661 → 32,661 | 12.4 s → 12.38 s | n/a |

## Token ledger — who spent what

Every recorded step, the model that produced it, and what runs it in the compiled build.

| step | action | recorded model | prompt (cached) + completion = total | compiled executor | compiled tokens |
| :-- | :-- | :-- | --: | :-- | --: |
| step_1 | `shell_sed` | gpt-5.6-sol | 14,117 (7,936) + 104 = 14,221 | code | 0 |
| step_2 | `shell_python3` | gpt-5.6-sol | 16,099 (0) + 466 = 16,565 | code | 0 |
| step_3 | `shell_python3` | gpt-5.6-sol | 19,844 (15,104) + 1,241 = 21,085 | code | 0 |
| step_4 | `shell_python3` | gpt-5.6-sol | 22,191 (13,056) + 2,526 = 24,717 | code | 0 |
| step_5 | `shell_python3` | gpt-5.6-sol | 26,616 (21,248) + 2,335 = 28,951 | code | 0 |
| step_6 | `respond` | gpt-5.6-sol | 32,290 (26,368) + 371 = 32,661 | gpt-5.6-sol | 32,661 |

| model / executor | recorded tokens | compiled tokens |
| :-- | --: | --: |
| gpt-5.6-sol | 138,200 | 32,661 |
| code | 0 | 0 |

Recorded prompt tokens served from the provider cache: 83,712 (counted in the totals above; billed at the cached rate).
Totals are the sum of every request's usage as reported by the provider — each agent turn re-sends its whole context, which is why they exceed the agent CLI's own 'tokens used' figure.

## Outputs

### `shell_sed` · step_1 — code:quality_anomaly/handlers

recorded:

```
# Task: Line 3 quality anomaly response report for 2026-08-27 night shift

You are the manufacturing quality-analysis assistant. Prepare the auditable anomaly evidence summary and response report for **incident_date=2026-08-27**, **line=3**, **shift=night** for review by the Quality Engineer.

Rules (from `behaviors/`): use the supplied thresholds as the sole numeric rule authority; independently verify the bound MES anomaly before analysis; align sensor evidence only to the bound line and supplied overnight incident window; evaluate calibration by measure at measurement time and never use an 
… (6564 more chars)
```

compiled:

```
# Task: Line 3 quality anomaly response report for 2026-08-27 night shift

You are the manufacturing quality-analysis assistant. Prepare the auditable anomaly evidence summary and response report for **incident_date=2026-08-27**, **line=3**, **shift=night** for review by the Quality Engineer.

Rules (from `behaviors/`): use the supplied thresholds as the sole numeric rule authority; independently verify the bound MES anomaly before analysis; align sensor evidence only to the bound line and supplied overnight incident window; evaluate calibration by measure at measurement time and never use an 
… (6564 more chars)
```

### `shell_python3` · step_2 — code:quality_anomaly/handlers

recorded:

```
incident_date=2026-08-27
line=3
shift=night
MES=examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv
SENSORS=examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv
CALIBRATION=examples/cases/quality-anomaly/materials/data/calibration-log.csv
THRESHOLDS=examples/cases/quality-anomaly/materials/data/thresholds.yaml
OUTPUT_DIR=build/quality-anomaly
# 품질팀장 메모

3라인 불량률 튈 때마다 보고서 써왔는데, 순서는 이래:
1. MES 불량률(mes-defects csv)에서 임계치(thresholds.yaml) 넘은 교대(shift) 찾기
2. 그 시간대 센서 csv(temp, vibration)에서 임계치 넘는 구간 찾기
3. 센서 보정 로그(calibration-log) 확인 — 보정 기한 지난 센서면 그 센서 값은 "신뢰 불가"로 
… (12699 more chars)
```

compiled:

```
incident_date=2026-08-27
line=3
shift=night
MES=examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv
SENSORS=examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv
CALIBRATION=examples/cases/quality-anomaly/materials/data/calibration-log.csv
THRESHOLDS=examples/cases/quality-anomaly/materials/data/thresholds.yaml
OUTPUT_DIR=build/quality-anomaly
# 품질팀장 메모

3라인 불량률 튈 때마다 보고서 써왔는데, 순서는 이래:
1. MES 불량률(mes-defects csv)에서 임계치(thresholds.yaml) 넘은 교대(shift) 찾기
2. 그 시간대 센서 csv(temp, vibration)에서 임계치 넘는 구간 찾기
3. 센서 보정 로그(calibration-log) 확인 — 보정 기한 지난 센서면 그 센서 값은 "신뢰 불가"로 
… (12699 more chars)
```

### `shell_python3` · step_3 — code:quality_anomaly/handlers

recorded:

```
selected_row= {'date': '2026-08-27', 'line': '3', 'shift': 'night', 'units': '3900', 'defects': '215', 'defect_rate_pct': '5.5'}
recomputed_rate_pct= 5.512820512820513
threshold_pct= 2.5
rate_consistent_within_0.05_pp= True
verdict= ANOMALY
filtered_window=
{'timestamp': '2026-08-27T20:00', 'line': '3', 'sensor_id': 'S3-TEMP-1', 'temp_c': '71.2', 'vibration_mm_s': '3.1'}
{'timestamp': '2026-08-27T21:00', 'line': '3', 'sensor_id': 'S3-TEMP-1', 'temp_c': '72.0', 'vibration_mm_s': '3.2'}
{'timestamp': '2026-08-27T22:00', 'line': '3', 'sensor_id': 'S3-TEMP-1', 'temp_c': '79.4', 'vibration_mm_s': '
… (1749 more chars)
```

compiled:

```
selected_row= {'date': '2026-08-27', 'line': '3', 'shift': 'night', 'units': '3900', 'defects': '215', 'defect_rate_pct': '5.5'}
recomputed_rate_pct= 5.512820512820513
threshold_pct= 2.5
rate_consistent_within_0.05_pp= True
verdict= ANOMALY
filtered_window=
{'timestamp': '2026-08-27T20:00', 'line': '3', 'sensor_id': 'S3-TEMP-1', 'temp_c': '71.2', 'vibration_mm_s': '3.1'}
{'timestamp': '2026-08-27T21:00', 'line': '3', 'sensor_id': 'S3-TEMP-1', 'temp_c': '72.0', 'vibration_mm_s': '3.2'}
{'timestamp': '2026-08-27T22:00', 'line': '3', 'sensor_id': 'S3-TEMP-1', 'temp_c': '79.4', 'vibration_mm_s': '
… (1749 more chars)
```

### `shell_python3` · step_4 — code:quality_anomaly/handlers

recorded:

```
build/quality-anomaly/anomaly-2026-08-27.json
build/quality-anomaly/anomaly-report-2026-08-27.md
{
    "incident": {
        "date": "2026-08-27",
        "line": 3,
        "shift": "night",
        "observed_sensor_window": {
            "start": "2026-08-27T20:00",
            "end": "2026-08-28T03:00",
            "inclusive": true
        }
    },
    "sources": {
        "memo": "examples/cases/quality-anomaly/materials/memo.md",
        "notes": "examples/cases/quality-anomaly/materials/notes.txt",
        "mes": "examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv",
 
… (7571 more chars)
```

compiled:

```
build/quality-anomaly/anomaly-2026-08-27.json
build/quality-anomaly/anomaly-report-2026-08-27.md
{
    "incident": {
        "date": "2026-08-27",
        "line": 3,
        "shift": "night",
        "observed_sensor_window": {
            "start": "2026-08-27T20:00",
            "end": "2026-08-28T03:00",
            "inclusive": true
        }
    },
    "sources": {
        "memo": "examples/cases/quality-anomaly/materials/memo.md",
        "notes": "examples/cases/quality-anomaly/materials/notes.txt",
        "mes": "examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv",
 
… (7571 more chars)
```

### `shell_python3` · step_5 — code:quality_anomaly/handlers

recorded:

```
validation.status=passed
PASS filenames_match_incident_date
PASS source_incident_binding_matches
PASS mes_unique_bound_row
PASS mes_selected_row_recomputed
PASS mes_rate_recomputed_and_consistent
PASS mes_strict_anomaly_verdict
PASS thresholds_match_authority
PASS sensor_window_bound_line_and_time
PASS temp_c_strict_exceedance_samples
PASS temp_c_contiguous_intervals
PASS temp_c_peak
PASS temp_c_unique_calibration_by_measure
PASS temp_c_no_future_calibration
PASS temp_c_no_future_calibration
PASS temp_c_no_future_calibration
PASS temp_c_no_future_calibration
PASS temp_c_no_future_calibration
P
… (14212 more chars)
```

compiled:

```
validation.status=passed
PASS filenames_match_incident_date
PASS source_incident_binding_matches
PASS mes_unique_bound_row
PASS mes_selected_row_recomputed
PASS mes_rate_recomputed_and_consistent
PASS mes_strict_anomaly_verdict
PASS thresholds_match_authority
PASS sensor_window_bound_line_and_time
PASS temp_c_strict_exceedance_samples
PASS temp_c_contiguous_intervals
PASS temp_c_peak
PASS temp_c_unique_calibration_by_measure
PASS temp_c_no_future_calibration
PASS temp_c_no_future_calibration
PASS temp_c_no_future_calibration
PASS temp_c_no_future_calibration
PASS temp_c_no_future_calibration
P
… (14212 more chars)
```

### `respond` · step_6 — escalated:frontier_llm (kept recorded cost (frontier/human tier))

recorded:

```
Verified Line 3 night shift on 2026-08-27: 5.5% recorded defect rate (5.5128% recomputed), exceeding the 2.5% threshold.

- Temperature: trusted
- Vibration: untrusted and excluded from causal support
- Candidate cause: elevated process temperature, correlation only
- Remediation: pending; requires Quality Engineer approval
- Mechanical validation: passed

Artifacts:

- [anomaly-2026-08-27.json](/Users/hongmartin/orca/projects/open-workflow/build/quality-anomaly/anomaly-2026-08-27.json)
- [anomaly-report-2026-08-27.md](/Users/hongmartin/orca/projects/open-workflow/build/quality-anomaly/anomaly
… (22 more chars)
```

compiled:

```
Verified Line 3 night shift on 2026-08-27: 5.5% recorded defect rate (5.5128% recomputed), exceeding the 2.5% threshold.

- Temperature: trusted
- Vibration: untrusted and excluded from causal support
- Candidate cause: elevated process temperature, correlation only
- Remediation: pending; requires Quality Engineer approval
- Mechanical validation: passed

Artifacts:

- [anomaly-2026-08-27.json](/Users/hongmartin/orca/projects/open-workflow/build/quality-anomaly/anomaly-2026-08-27.json)
- [anomaly-report-2026-08-27.md](/Users/hongmartin/orca/projects/open-workflow/build/quality-anomaly/anomaly
… (22 more chars)
```

## Final answer of the recorded agent

```
Verified Line 3 night shift on 2026-08-27: 5.5% recorded defect rate (5.5128% recomputed), exceeding the 2.5% threshold.

- Temperature: trusted
- Vibration: untrusted and excluded from causal support
- Candidate cause: elevated process temperature, correlation only
- Remediation: pending; requires Quality Engineer approval
- Mechanical validation: passed

Artifacts:

- [anomaly-2026-08-27.json](/Users/hongmartin/orca/projects/open-workflow/build/quality-anomaly/anomaly-2026-08-27.json)
- [anomaly-report-2026-08-27.md](/Users/hongmartin/orca/projects/open-workflow/build/quality-anomaly/anomaly-report-2026-08-27.md)
```
