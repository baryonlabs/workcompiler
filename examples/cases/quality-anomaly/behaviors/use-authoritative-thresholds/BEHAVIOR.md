# BEHAVIOR: use-authoritative-thresholds

## 1. Intent
Ensure anomaly, sensor, and calibration decisions use the supplied current threshold configuration rather than memory, the previous report, or invented limits.

## 2. Evidence
The trajectory reads `examples/cases/quality-anomaly/materials/data/thresholds.yaml` before classification and records its line, defect-rate threshold, per-measure maxima, calibration interval, and source path in the structured evidence.

## 3. Decision
- `true`: Every threshold and calibration interval used in the artifacts matches the read configuration, and strict exceedance is applied.
- `false`: A limit is hardcoded, remembered, copied from the prior report, invented, or interpreted as inclusive despite the configuration's “above” rule.
- `na`: The trajectory does not classify a manufacturing quality anomaly or sensor evidence.

## 4. Execution
Make the threshold-file read a required predecessor to MES classification, sensor comparison, calibration gating, and drafting.

## 5. Recovery
Discard derived classifications, re-read the threshold file, recompute all dependent evidence, and regenerate both artifacts.

## 6. Failure Modes
Using 3.1% or 80.2 °C from the prior report, treating equality as exceedance, applying a limit to the wrong measure, or using an undocumented calibration interval.
