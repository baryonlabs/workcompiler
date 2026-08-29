# BEHAVIOR: enforce-finance-approval-threshold

## 1. Intent
Prevent Customer Support from finalizing any calculated refund over 100,000 KRW while keeping exactly 100,000 KRW within CS authority.

## 2. Evidence
After refund calculation, the trajectory compares `calculated_refund_amount_krw` using the strict expression `> 100000` and records clause 4, `pending_finance_approval`, and decision authority `finance` only when that expression is true.

## 3. Decision
- `true`: Every amount over 100,000 KRW is pending Finance approval and is not described as finalized or issued, while amounts at or below 100,000 KRW may be finalized by CS.
- `false`: CS finalizes or claims issuance of an over-threshold refund, or routes exactly 100,000 KRW to Finance solely because of clause 4.
- `na`: No refund amount was calculated because evidence is held or requires human review, or the trajectory does not make a refund decision.

## 4. Execution
Make the strict threshold comparison a deterministic step after eligibility calculation and before writing either output.

## 5. Recovery
Reapply the strict `> 100000` comparison, correct status and authority, remove unsupported issuance or approval language, and revalidate both files.

## 6. Failure Modes
Comparing requested rather than calculated refund, using `>=` instead of `>`, copying finalized language from the prior memo, or implying Finance approval occurred.
