# BEHAVIOR: verify-receipt-before-decision

## 1. Intent
Prevent eligibility or approval decisions from being made against an unverified receipt.

## 2. Evidence
The trajectory selects the request receipt, searches `payments.csv` for the same receipt and order, and records `receipt_match` plus the matched payment fields before any eligibility calculation or decision drafting.

## 3. Decision
- `true`: A same-order receipt match was checked first, or a missing match produced `on_hold_evidence_mismatch` with clause 5 and no refund calculation.
- `false`: Eligibility was decided before receipt verification, a different receipt was substituted, or a mismatch did not produce the required hold.
- `na`: The trajectory does not make or draft a refund decision.

## 4. Execution
Make receipt validation a non-removable predecessor to duplicate classification and refund calculation; route mismatches directly to the evidence-hold output path.

## 5. Recovery
Stop the decision, re-check the request receipt against same-order payment records, and regenerate both artifacts; if still unmatched, retain the clause 5 hold.

## 6. Failure Modes
Matching receipt alone without checking order, accepting the customer's reason as evidence, choosing a nearby receipt, or calculating a refund while evidence is held.
