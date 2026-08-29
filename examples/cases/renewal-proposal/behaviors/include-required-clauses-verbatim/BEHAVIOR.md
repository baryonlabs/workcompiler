# BEHAVIOR: include-required-clauses-verbatim

## 1. Intent
Ensure the renewal proposal contains every standard clause mandated by the current pricing policy, exactly and without semantic drift.

## 2. Evidence
The trajectory reads `required_clauses` from `examples/cases/renewal-proposal/materials/data/pricing_v2.yaml` and validates that each source string occurs exactly once, unchanged, in the proposal's `## Required clauses` section.

## 3. Decision
- `true`: Every current-policy required clause appears exactly once and verbatim in the designated proposal section.
- `false`: Any clause is missing, duplicated, paraphrased, altered, sourced from legacy material, or placed only in pricing JSON rather than the proposal.
- `na`: The trajectory does not draft a renewal proposal.

## 4. Execution
Copy the clause strings directly from the validated v2 policy during drafting, then perform an exact string and occurrence-count check before completion.

## 5. Recovery
Reload `required_clauses` from the current policy, replace the entire required-clauses section with the authoritative strings, and rerun exact-match validation.

## 6. Failure Modes
Paraphrasing legal text; omitting the 60-day notice, DPA v3, or 30-day validity clause; copying legacy wording; inserting a clause twice; claiming clause compliance without checking the written file.
