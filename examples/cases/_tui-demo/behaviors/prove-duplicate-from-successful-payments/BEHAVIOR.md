# BEHAVIOR: prove-duplicate-from-successful-payments

## 1. Intent
Ensure the duplicate-charge exception is granted only from unambiguous payment-ledger evidence.

## 2. Evidence
The trajectory filters `payments.csv` by the request `order_id` and exact status `success`, records the resulting payment IDs and amounts plus their count, checks amount consistency, and derives `is_duplicate_charge` from whether the count is at least two.

## 3. Decision
- `true`: Duplicate status equals the result of counting same-order successful payments, supporting IDs and amounts appear in the JSON, and ambiguous duplicate amounts route to `needs_human_review`.
- `false`: Free text, failed payments, other orders, or an unrecorded assumption established duplicate status, or conflicting amounts were guessed.
- `na`: Successful-payment receipt evidence was not established and duplicate classification was skipped, or the trajectory does not make a refund decision.

## 4. Execution
Perform the successful-payment filter, count, and amount-consistency check deterministically after receipt verification and before applying the duplicate exception.

## 5. Recovery
Re-read the payment ledger, exclude non-success rows and other orders, recompute the count, and regenerate downstream calculations and outputs; escalate unresolved amount conflicts to human review.

## 6. Failure Modes
Trusting “charged twice” as proof, counting failed or other-order payments, omitting payment evidence from the JSON, or selecting a duplicate amount despite conflicting successful payments.
