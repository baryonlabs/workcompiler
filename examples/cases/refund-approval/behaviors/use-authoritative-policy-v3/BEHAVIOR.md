# BEHAVIOR: use-authoritative-policy-v3

## 1. Intent
Ensure every refund decision uses the effective Refund Policy v3 as its sole rules authority rather than summaries, prior decisions, memory, or invented policy.

## 2. Evidence
The trajectory reads `examples/cases/refund-approval/materials/data/refund-policy-v3.md` before classification or calculation, records policy version `v3` and effective date `2026-04-01` in the evidence JSON, and uses the memo and previous decision only for scope or format.

## 3. Decision
- `true`: Policy v3 was read before the decision and all applied rules are traceable to it.
- `false`: The decision used an unread, legacy, summarized, remembered, or invented rule as authority.
- `na`: The trajectory does not make or draft a refund decision.

## 4. Execution
Enforce the policy read as a required predecessor to receipt validation, eligibility calculation, approval routing, and drafting.

## 5. Recovery
Discard unsupported conclusions, read Policy v3, and recompute the evidence record and memo from its clauses.

## 6. Failure Modes
Treating the manager memo as complete policy, copying the previous deliverable's outcome, using today's date for eligibility, or inventing an exception absent from Policy v3.
