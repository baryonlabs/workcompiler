# BEHAVIOR: bound-cause-to-trusted-evidence

## 1. Intent
Keep root-cause language proportional to the supplied evidence and distinguish a correlated candidate from a confirmed equipment failure.

## 2. Evidence
The structured evidence records a candidate status, statement, explicit supporting trusted measures, and limitations after calibration gating; the report renders the same bounded claim under `Root cause (candidate)`.

## 3. Decision
- `true`: The cause is labeled a candidate, cites only trusted supporting measures, states material limitations, and becomes `undetermined` when no trustworthy causal evidence remains.
- `false`: A cause is presented as confirmed, an unsupported component failure is named, an untrusted measure supplies support, or uncertainty is omitted.
- `na`: The trajectory makes no causal assessment.

## 4. Execution
Draft the causal assessment only after MES verification, time alignment, exceedance calculation, and calibration gating; separate observed correlation from confirmation.

## 5. Recovery
Downgrade unsupported certainty, remove untrusted or absent support, add the evidence limitation, or set the cause to `undetermined`; regenerate both artifacts and revalidate them.

## 6. Failure Modes
Copying the coolant diagnosis from the previous report, equating threshold coincidence with proof, inventing a failed station/component, or masking insufficient evidence with confident prose.
