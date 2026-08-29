# BEHAVIOR: use-current-pricing-policy

## 1. Intent
Guarantee that every new renewal offer uses the effective `pricing_v2` policy as the sole authority for list price, seat recommendation, discounts, term, cap, and required clauses.

## 2. Evidence
The trajectory shows `examples/cases/renewal-proposal/materials/data/pricing_v2.yaml` read and validated as `policy: pricing_v2` with an effective date no later than the proposal date before pricing; calculation fields in the JSON trace to its values and do not trace to the legacy file, stored contract price, or previous proposal.

## 3. Decision
- `true`: The effective v2 policy was validated and all offer calculations and required clauses were derived from it.
- `false`: Legacy v1, the contract's historical price/policy, the previous proposal, invented terms, or an ineffective/unvalidated policy supplied any new-offer value.
- `na`: The trajectory performs no renewal pricing or proposal drafting.

## 4. Execution
Enforce policy validation before price calculation and proposal drafting, with deterministic checks of the policy identifier, effective date, plan price, highest qualifying volume band, loyalty eligibility, term, and clause list.

## 5. Recovery
Discard affected calculations and prose, reload and validate `pricing_v2.yaml`, recompute the complete offer, and rerun arithmetic and clause validation.

## 6. Failure Modes
Using `pricing_v1_legacy.yaml`; retaining the active contract's $38 historical enterprise price instead of v2's current price; stacking volume bands; granting loyalty before two full years; copying another customer's price or clauses.
