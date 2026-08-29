# Line 3 Quality Anomaly Report — 2026-08-27 (night shift)

## Anomaly
Defect rate 5.5% (threshold 2.5%), 3,900 units, 215 defects; recomputed rate 5.5128%. Verified anomaly: yes.

## Sensor evidence
Temperature exceeded 78.0 °C from 2026-08-27T22:00 through 2026-08-28T01:00 inclusive (peak 82.5 °C at 2026-08-28T00:00). Calibration sensor S3-TEMP-1 was calibrated 2026-07-30; measurement age 28–29 whole days within the 90-day interval → trusted and eligible for causal use.
Vibration exceeded 4.5 mm/s from 2026-08-28T00:00 through 2026-08-28T02:00 inclusive (peak 5.4 mm/s at 2026-08-28T01:00). Calibration sensor S3-VIB-1 was calibrated 2026-04-12; measurement age 137–138 whole days exceeds the 90-day interval → untrusted and excluded from causal judgment.

## Root cause (candidate)
Status: candidate. Elevated process temperature is a candidate contributor correlated with the Line 3 night-shift defect anomaly. Supporting trusted measure: temp_c. Limitations: Correlation does not establish causation. The supplied evidence does not identify or confirm a specific failed component. Vibration exceedances are untrusted because calibration was overdue and are excluded from causal judgment.

## Remediation (requires Quality Engineer approval)
- Inspect the Line 3 thermal process and temperature-control conditions. requires Quality Engineer approval. Approval: pending.
- Run a controlled verification trial after approved thermal-process inspection. requires Quality Engineer approval. Approval: pending.
- Recalibrate or independently verify the vibration measurement channel before causal use. requires Quality Engineer approval. Approval: pending.
