# BEHAVIOR: prove-duplicate-from-successful-payments

## 1. Intent
Ensure the duplicate-charge exception is granted only from payment-ledger evidence.

## 2. Evidence
The trajectory filters `payments.csv` by the request `order_id` and exact status `success`, records the resulting payment IDs and count, and derives `is_duplicate_charge` from whether the count is at least two.

## 3. Decision
- `true`: Duplicate status equals the result of counting same-order successful payments and the supporting IDs/count appear in the JSON.
- `false`: Free text, failed payments, other orders, or an unrecorded assumption established duplicate status.
- `na`: Receipt evidence is mismatched and duplicate classification is therefore skipped, or the trajectory does not make a refund decision.

## 4. Execution
Perform the successful-payment filter and count deterministically after receipt verification and before applying the duplicate exception.

## 5. Recovery
Re-read the payment ledger, exclude non-success rows and other orders, recompute the count, and regenerate downstream calculations and outputs.

## 6. Failure Modes
Trusting “charged twice” as proof, counting failed/voided payments, counting across customers or orders, or omitting payment IDs from the evidence record.
