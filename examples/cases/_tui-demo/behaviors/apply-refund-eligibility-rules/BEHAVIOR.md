# BEHAVIOR: apply-refund-eligibility-rules

## 1. Intent
Calculate the refund amount from verified payment evidence using the exact Policy v3 age bands and duplicate exception.

## 2. Evidence
The trajectory records the matched payment date, request date, whole-day difference, duplicate flag, requested and evidenced amounts, applicable clause, and calculated integer-KRW refund before approval routing.

## 3. Decision
- `true`: A verified duplicate received the lesser of the evidenced duplicate amount and requested amount in full regardless of age under clause 3, or a non-duplicate received 100% at 0–7 days, 50% at 8–30 days, or zero at 31 or more days under the applicable clause.
- `false`: Dates, boundaries, percentages, exception precedence, caps, or amounts differ from Policy v3, or an amount was guessed despite inconsistent evidence.
- `na`: Receipt evidence is held, source evidence requires human review, or the trajectory does not calculate refund eligibility.

## 4. Execution
Calculate dates and amounts deterministically from selected records; apply the verified duplicate branch before ordinary age-band selection.

## 5. Recovery
Recompute from `paid_at` and `requested_at`, reapply duplicate precedence and inclusive boundaries, and regenerate both artifacts; escalate inconsistent evidence rather than estimating.

## 6. Failure Modes
Using order or current date, treating day 7 or 30 incorrectly, denying an old duplicate, refunding more than requested or evidenced, or rounding to non-integer KRW.
