# BEHAVIOR: enforce-finance-approval-threshold

## 1. Intent
Prevent Customer Support from finalizing any calculated refund over 100,000 KRW.

## 2. Evidence
After refund calculation, the trajectory compares `calculated_refund_amount_krw` to 100000 and records clause 4, `pending_finance_approval`, and decision authority `finance` whenever the amount is greater than the threshold.

## 3. Decision
- `true`: Every amount over 100,000 KRW is pending Finance approval and is not described as finalized or issued; amounts at or below the threshold may be finalized by CS.
- `false`: CS finalizes or claims issuance of an over-threshold refund, or routes exactly 100,000 KRW to Finance solely because of clause 4.
- `na`: No refund amount was calculated because evidence is held, the calculated amount is zero with no approval action, or the trajectory does not make a refund decision.

## 4. Execution
Make the threshold comparison a deterministic step after eligibility calculation and before writing either output.

## 5. Recovery
Replace the unauthorized status and language with `pending_finance_approval`, authority `finance`, and an explicit statement that no refund has been finalized or issued; then revalidate both files.

## 6. Failure Modes
Comparing requested rather than calculated refund, using `>=` instead of `>`, copying finalized language from the prior memo, or implying Finance approval occurred.
