# BEHAVIOR: verify-bound-mes-anomaly

## 1. Intent
Prevent a response report from being finalized for an unverified, wrong, ambiguous, or internally inconsistent shift record.

## 2. Evidence
The trajectory filters `examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv` by the bound date, line, and shift; records a match count of one; recomputes the defect rate from units and defects; and compares the recorded rate strictly with the configured threshold before sensor analysis.

## 3. Decision
- `true`: Exactly one bound MES row is selected, its recorded and recomputed rates agree within 0.05 percentage point, and the rate is strictly above the configured threshold before downstream analysis proceeds.
- `false`: The wrong or multiple shifts are used, the rate is assumed from notes, inconsistent counts are ignored, or a non-anomalous shift receives a finalized anomaly report.
- `na`: The trajectory does not produce a shift-level quality-anomaly response.

## 4. Execution
Make bound-key selection, uniqueness, rate reproduction, and threshold classification non-removable predecessors to sensor analysis and artifact creation.

## 5. Recovery
Stop downstream work, re-read the MES and threshold sources, reselect by all bound keys, and continue only when a unique, consistent, above-threshold row is established; otherwise report the evidence problem for human review.

## 6. Failure Modes
Scanning and reporting unrelated shifts, matching date without line/shift, trusting a precomputed rate despite inconsistent counts, or using `>=` instead of `>`.
