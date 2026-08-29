# Assumptions: invoice refund approval decisions

This file records the grilling interview conducted against the supplied work materials because the requester was unavailable. Each answer is a recommended assumption to verify or correct before treating the specification as final.

## Round 1 — Goal and consumer

### 1. What is the single-sentence goal?

**Chosen answer:** For the per-run refund request ID, produce an auditable customer-support refund decision memo and a machine-readable evidence record that applies Refund Policy v3 without issuing a refund or contacting the customer.

**Why:** `materials/memo-from-manager.md` asks for one decision memo and one evidence JSON per request. The materials describe decision preparation, not payment execution or customer communication.

### 2. Who consumes the result?

**Chosen answer:** Customer Support consumes finalized or held decisions; Finance consumes decisions whose calculated refund exceeds 100,000 KRW.

**Why:** The manager memo says CS may finalize amounts below the threshold, while larger amounts must be handed to Finance as pending approval.

### 3. Which request is in scope for this run?

**Chosen answer:** The per-run parameter is **REQUEST_ID = RR-2026-0827-03**. Process exactly that request, not every row in the input file.

**Why:** `materials/notes.txt` explicitly identifies this as this week's case and gives singular output naming rules.

## Round 2 — Inputs and authority

### 4. What are the authoritative inputs?

**Chosen answer:** Read `materials/data/refund-requests.json` for the request, `materials/data/orders.json` for the order/customer record, `materials/data/payments.csv` for receipt and successful-payment evidence, and `materials/data/refund-policy-v3.md` for all decision rules.

**Why:** These are the raw files supplied for the work. The manager memo explicitly says the v3 policy document is official.

### 5. How should the memo, notes, and previous deliverable be used?

**Chosen answer:** Use `materials/memo-from-manager.md` and `materials/notes.txt` to scope and parameterize the run, and use `materials/previous/decision-RR-2026-0712-01.md` only as the memo format/style reference. Never treat any of them as overriding policy v3.

**Why:** The manager calls the memo a summary and policy v3 the formal authority; the prior deliverable demonstrates headings and wording but is not a rules source.

### 6. What values vary per run?

**Chosen answer:** `REQUEST_ID` varies per run. All joined request, order, payment, dates, amounts, receipt, reason, classification, status, and output filenames derive from it. Policy path and output directory remain fixed until explicitly versioned.

**Why:** The notes select one request ID and define filenames as `decision-<request ID>.*`.

### 7. What date controls age, and how are boundaries calculated?

**Chosen answer:** Use the matched successful payment's `paid_at` and the request's `requested_at`; calculate whole calendar-day difference as request date minus payment date. Interpret “within 7 days” as 0–7 inclusive, “8–30 days” as 8–30 inclusive, and “after 30 days” as 31+.

**Why:** Policy v3 explicitly speaks in those ranges and the previous decision demonstrates 2026-07-01 to 2026-07-12 as 11 days. Today's date in the notes does not determine eligibility.

## Round 3 — Ordered work and decision precedence

### 8. What ordered steps should a competent reviewer follow?

**Chosen answer:** Select exactly one request; join and cross-check the order/customer; match the receipt to a payment; count successful payments for the order; classify duplicate status; calculate the policy refund; apply the Finance threshold; then write JSON evidence before drafting the memo from that evidence.

**Why:** This order makes every policy predicate observable and prevents prose from becoming the source of truth.

### 9. What happens if a receipt does not match?

**Chosen answer:** Stop substantive eligibility and approval determination, record `on_hold_evidence_mismatch`, calculate no refund amount, cite clause 5, and do not infer a receipt from another payment.

**Why:** Policy v3 clause 5 mandates the hold. The supplied ORD-77003 case is a deliberate example of a request receipt differing from the successful payment receipt.

### 10. How is a duplicate charge established?

**Chosen answer:** Count payment rows with the same `order_id` and `status == success`; two or more establishes a duplicate. Customer reason text alone is not evidence. The refundable duplicate amount is the matched successful payment amount, limited to the amount requested; any inconsistent amounts must be escalated rather than guessed.

**Why:** The memo and clause 3 define duplicates using successful payments, and the current case has two 264,000 KRW successes. The materials do not authorize refunding more than requested or inventing a value when amounts conflict.

### 11. Which rule takes precedence for old duplicate charges?

**Chosen answer:** A verified duplicate receives a full refund for the duplicate amount regardless of age under clause 3; the ordinary age bands in clauses 1–3 apply only when the request is not a duplicate.

**Why:** Clause 3 expressly creates the age exception.

### 12. Does Finance approval change refund eligibility?

**Chosen answer:** No. First calculate the eligible refund amount, then set `pending_finance_approval` if it is over 100,000 KRW. CS must not label it finalized or claim the refund was issued.

**Why:** Clause 4 is an approval/status rule based on the calculated amount, not an eligibility denial.

## Round 4 — Mechanics, judgment, and outputs

### 13. Which steps are mechanical and which require judgment?

**Chosen answer:** JSON/CSV selection, joins, receipt matching, successful-payment counting, date arithmetic, percentage calculation, threshold comparison, and JSON serialization are mechanical. Explaining the result and recovery for inconsistent/missing data are judgment steps constrained by the evidence and behavior contracts.

**Why:** All numeric and categorical rules are explicit. Only concise explanation and unenumerated data-quality exceptions need bounded judgment.

### 14. What exact files and fields constitute “done”?

**Chosen answer:** Write `build/refund-approval/decision-<REQUEST_ID>.json` first with source paths, identity fields, matched payment evidence, successful payment IDs/count, day difference, duplicate flag, applied clauses, calculated amount, status, authority, and rationale; then write `build/refund-approval/decision-<REQUEST_ID>.md` with the previous deliverable's title, factual summary, `## Decision`, and `## Next steps`.

**Why:** The memo requires one Markdown decision and one evidence JSON, the notes give exact filenames, and policy clause 6 requires clause citations.

### 15. What language and money representation should outputs use?

**Chosen answer:** Follow the previous deliverable in English; store KRW amounts as integer won in JSON and render them with thousands separators plus `KRW` in Markdown.

**Why:** The repository is maintained in English, the prior deliverable is English, and every supplied amount is integral KRW.

### 16. What must the memo say for each terminal status?

**Chosen answer:** For `finalized`, state CS finalization and the supported next-step template only if the materials authorize it. For `pending_finance_approval`, state that the calculated refund is pending Finance approval and has not been finalized or issued. For `on_hold_evidence_mismatch`, state that evidence correction is required and no refund decision is finalized.

**Why:** This preserves the authority boundary. The prior memo's “refund issued” wording is not safe for a pending or held case.

## Round 5 — Acceptance and failure recovery

### 17. What are the acceptance criteria?

**Chosen answer:** Exactly one request is processed; all required sources are read; joins agree; receipt is verified before eligibility; duplicate status uses successful payments only; policy v3 and applicable clause numbers are cited; amount/status/authority are consistent; JSON and Markdown agree; and no external refund, approval, or notification action occurs.

**Why:** These criteria cover the manager's explicit rules and make behavior compliance independently reviewable.

### 18. Which failure modes must be prevented?

**Chosen answer:** Processing the wrong or multiple requests, treating customer claims as proof, counting failed payments, using order date instead of payment date, applying age denial to a duplicate, finalizing an over-cap refund, silently substituting a receipt, citing no clauses, disagreeing outputs, and claiming downstream actions occurred.

**Why:** Each would violate a supplied rule or make the audit trail unreliable; several traps are represented in the raw fixture data.

### 19. What should happen on missing, duplicate, or inconsistent records?

**Chosen answer:** Do not guess. Stop before drafting a normal decision, preserve observed evidence in the JSON when possible, state the unresolved inconsistency, and require human review. A missing receipt match specifically uses `on_hold_evidence_mismatch`; other unmodeled integrity failures use a clearly labeled review-required error rather than a policy status invented by the agent.

**Why:** Only the receipt-mismatch hold has a prescribed status. The materials provide no safe resolution rule for conflicting customer/order/payment identities or ambiguous rows.

### 20. Are any facts intentionally unknown?

**Chosen answer:** The exact Finance routing mechanism, customer notification template for this case, refund-processing API, and SLA are unknown and out of scope. The agent must not fabricate or execute them.

**Why:** The materials specify decision artifacts and a Finance status but provide no connectors, destinations, templates, or operational instructions for those actions.
