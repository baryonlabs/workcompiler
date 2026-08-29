# BEHAVIOR: gate-causation-by-calibration

## 1. Intent
Prevent expired or mismapped sensor calibration from supporting a root-cause candidate while keeping observed evidence transparent.

## 2. Evidence
The trajectory joins each analyzed measure to the unique `measure` row in `examples/cases/quality-anomaly/materials/data/calibration-log.csv`, computes elapsed whole days at relevant measurement timestamps using the configured interval, records the calibration sensor ID/date/ages and trust verdict, and records causal eligibility before drafting a cause.

## 3. Decision
- `true`: Every measure is mapped by measure, age is evaluated at measurement time, values older than the allowed interval are labeled `untrusted` and disclosed but absent from causal support, and only trusted measures support the candidate cause.
- `false`: Calibration is skipped, evaluated at workflow execution time, mapped from the sensor row ID across measures, expired evidence is hidden, or an untrusted measure supports causation.
- `na`: No sensor evidence is analyzed or no causal assessment is made.

## 4. Execution
Perform the calibration join and trust calculation after time-aligned exceedance extraction and before candidate-cause judgment; fail closed on missing, duplicate, future-dated, or inconsistent calibration evidence.

## 5. Recovery
Remove unsupported causal claims, remap calibration records by measure, recompute incident-time ages and trust, then regenerate the structured evidence and report; escalate unresolved calibration ambiguity for human review.

## 6. Failure Modes
Treating the row-level temperature sensor ID as vibration calibration, using today's date, treating day 90 as expired, silently dropping overdue readings, or describing untrusted vibration as causal.
