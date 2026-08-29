# BEHAVIOR: verify-successful-payment-receipt

## 1. Intent
Prevent eligibility or approval decisions from being made against an unmatched receipt or a payment that was not successful.

## 2. Evidence
The trajectory selects the request receipt, searches `payments.csv` for that receipt on the same order, records `receipt_match` and matched payment fields, and confirms exact status `success` before any duplicate classification, eligibility calculation, or decision drafting.

## 3. Decision
- `true`: A same-order successful-payment receipt was verified first; an absent match produced `on_hold_evidence_mismatch` with clause 5; or a non-success match produced `needs_human_review`, with no refund calculation in either exceptional path.
- `false`: Eligibility was decided before verification, a different receipt was substituted, payment success was not checked, or a mismatch still led to a refund calculation.
- `na`: The trajectory does not make or draft a refund decision.

## 4. Execution
Make same-order receipt matching and successful status validation non-removable predecessors to duplicate classification and refund calculation; route failures directly to the appropriate non-decision output path.

## 5. Recovery
Stop the decision, re-check the requested receipt against same-order payment records, and regenerate both artifacts; retain the evidence hold or human-review status when successful-payment evidence cannot be established.

## 6. Failure Modes
Matching receipt alone without checking order or status, accepting the customer's reason as evidence, choosing a nearby receipt, or calculating a refund while evidence is held or unresolved.
