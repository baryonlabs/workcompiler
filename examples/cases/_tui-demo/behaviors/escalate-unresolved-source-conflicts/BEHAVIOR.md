# BEHAVIOR: escalate-unresolved-source-conflicts

## 1. Intent
Ensure missing, duplicated, ambiguous, or inconsistent source records never produce a guessed refund decision.

## 2. Evidence
The trajectory checks request uniqueness, order uniqueness and customer consistency, successful-payment status, and payment-amount consistency; any unresolved failure is recorded with status `needs_human_review`, a concrete rationale, null unperformed calculations, and no decision authority.

## 3. Decision
- `true`: Every unresolved source conflict stops downstream calculation, is named in both artifacts, and produces `needs_human_review` without a refund decision.
- `false`: The run substitutes a record, silently resolves a conflict, invents a value, or proceeds to finalization or Finance routing on ambiguous evidence.
- `na`: All required source records are unique, present, and consistent, or the trajectory does not process a refund request.

## 4. Execution
Place deterministic uniqueness and consistency gates before calculation; on failure, preserve verified facts, set unknown or unperformed fields to JSON `null`, and route to human review.

## 5. Recovery
Re-read the source records and identify the exact discrepancy; continue only after authoritative evidence resolves it, otherwise regenerate the non-decision artifacts with `needs_human_review`.

## 6. Failure Modes
Choosing the first duplicate record, treating an order date as a payment date, reconciling conflicting amounts without authority, or assigning a decision authority when no decision was made.
