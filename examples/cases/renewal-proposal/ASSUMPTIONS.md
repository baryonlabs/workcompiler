# Assumptions: customer contract renewal proposals

The requester was unavailable for follow-up questions. The interview below was therefore answered from the supplied memo, personal notes, previous deliverable, and raw data. Each answer is provisional and should be corrected before the first run if it does not match sales-operations policy.

## Round 1 — Outcome and scope

❓ **Q1 — What is the single-sentence goal, and who consumes the result?** Prepare an auditable annual renewal proposal and its pricing calculation for the customer due for renewal, for review and sending by sales operations/account ownership.

➡️ **Chosen answer:** Prepare the annual renewal proposal and pricing evidence for **CUST-1001 (ACME Manufacturing Co.)**, for the sales-ops requester and account owner to review before customer delivery.

**Why:** `materials/notes.txt` identifies ACME/CUST-1001 as expiring at the end of September and needing action this week. The memo assigns the work to sales ops, while the active contract identifies `j.park@example.com` as account owner. The materials do not authorize sending anything externally.

---

❓ **Q2 — Which values vary per run?** Is this a one-off ACME task, or a reusable customer-renewal task with bound parameters?

➡️ **Chosen answer:** Define a reusable renewal task whose per-run parameters are **customer_id = CUST-1001** and **proposal_date = 2026-08-29** for this first run. The input file paths are fixed for this case definition.

**Why:** The requested work is plural/generic, but the notes identify the immediate customer. Explicit values make the first trace reproducible and allow later compilation to discover parameters.

---

❓ **Q3 — What exactly must the run produce?**

➡️ **Chosen answer:** Produce exactly two artifacts: `build/renewal-proposal/proposal-CUST-1001.md` and `build/renewal-proposal/pricing-CUST-1001.json`; then reply with a short summary and both paths. Do not send the proposal.

**Why:** The memo requires one Markdown proposal and one JSON calculation, and `materials/notes.txt` fixes their naming convention. The user explicitly requested all outputs under `build/renewal-proposal/`.

## Round 2 — Inputs, authority, and calculations

❓ **Q4 — Which inputs are authoritative, and how should conflicts be resolved?**

➡️ **Chosen answer:** Use `materials/data/contracts.json` for contract identity/status/term, `materials/data/usage-2026-07.csv` for recent usage, and `materials/data/pricing_v2.yaml` for every new-offer price, discount, term, seat, and clause rule. Use the memo and notes as task instructions. Use `materials/previous/proposal-CUST-0993.md` only as a formatting precedent. Never use `pricing_v1_legacy.yaml` or the active contract's legacy `pricing_policy`/stored seat price to price the offer.

**Why:** The memo explicitly says v1 was retired and v2 is mandatory. The v1 file marks itself retired. The ACME contract still references v1, creating the exact stale-policy trap the process must catch.

---

❓ **Q5 — How is the current contract selected?**

➡️ **Chosen answer:** Select the record matching **CUST-1001** whose `status` is exactly `active`; require exactly one match. Stop without drafting if none or more than one exists.

**Why:** The lead cites a prior incident caused by using an expired contract. The file contains both active and expired ACME contracts, so customer ID alone is unsafe. Uniqueness is not stated explicitly, but it is the safest deterministic interpretation of “current live contract.”

---

❓ **Q6 — What does “recent three months” mean and which usage metrics belong in the output?**

➡️ **Chosen answer:** Filter the supplied usage CSV to **CUST-1001**, require exactly the three rows `2026-05`, `2026-06`, and `2026-07`, then calculate peak active seats, first-to-last active-seat growth percentage, and average API calls. Include all three in the proposal usage summary.

**Why:** Those are the only three ACME months in the dated July snapshot. The reference task calculates these three metrics; peak seats directly drives the seat recommendation. Requiring three rows avoids silently presenting an incomplete window.

---

❓ **Q7 — How are committed seats calculated, especially when usage falls?**

➡️ **Chosen answer:** Compute `max(active contract seats, three-month peak seats_active)`, then round upward to a multiple of 10. For ACME this is `max(240, 262) = 262`, rounded to **270 seats**.

**Why:** This is stated verbatim in `pricing_v2.yaml`; the memo’s shorthand (“if seats increased, capture the increase”) is consistent with it. The current contract creates a floor, so the proposal does not automatically contract seat count.

---

❓ **Q8 — How are price and discounts calculated?**

➡️ **Chosen answer:** Use the v2 enterprise list price of **$40 per seat per month**. Apply the single highest qualifying volume band, plus the 3% loyalty discount when service from the active contract `start_date` to proposal date reaches two years. Add applicable percentages, enforce the 20% cap, and calculate monthly and 12-month annual totals from list price less the combined discount. Round currency to two decimals.

**Why:** The v2 policy describes volume bands by committed seats, a loyalty add-on, a total cap, and a 12-month term. Selecting the highest band avoids incorrectly stacking 5% and 10%. ACME qualifies for 10% volume and, on 2026-08-29, does **not yet** reach two full years from 2024-09-01, so the expected combined discount is **10%**, monthly total **$9,720.00**, and annual total **$116,640.00**.

## Round 3 — Judgment, exceptions, and acceptance

❓ **Q9 — What happens when proposed discounts exceed the policy cap?**

➡️ **Chosen answer:** Never silently apply more than 20%. If any policy/custom combination requests more than 20%, stop proposal finalization and report that sales-director approval is required; record the requested discount and approval-required status in pricing JSON. Do not invent or assume approval.

**Why:** Both the memo and v2 policy establish a hard cap and director approval above it. No approval artifact or approval source is present in the materials.

---

❓ **Q10 — What content and tone should the proposal use?**

➡️ **Chosen answer:** Follow the prior proposal’s concise structure: title/date, customer and active-contract summary, usage summary with recommended seats, pricing table, and required clauses. Use professional, factual sales-ops language and do not introduce unsupported claims, concessions, or terms.

**Why:** The previous finished deliverable is the only supplied presentation precedent. Its facts belong to another customer, so only its structure and tone are reusable.

---

❓ **Q11 — Which text must appear verbatim?**

➡️ **Chosen answer:** Include each string in `pricing_v2.yaml.required_clauses` exactly once and unchanged under `## Required clauses`:

- `12-month term with 60-day auto-renewal notice`
- `Data Processing Addendum v3 attached`
- `Price valid for 30 days from proposal date`

**Why:** The memo requires all three standard clauses, the policy provides their authoritative English wording, and the reference deliverable reproduces them verbatim.

---

❓ **Q12 — What must pricing JSON contain to be auditable?**

➡️ **Chosen answer:** Record customer/proposal identifiers; source paths and policy/version; active-contract identifiers and dates; usage window and calculated metrics; seat-recommendation inputs/result; list price; each discount and reason; combined/capped discount; monthly and annual list/subtotal/final totals; currency and term; and approval status.

**Why:** The memo calls the JSON the calculation basis. These fields allow a reviewer to recompute every decision without relying on narrative prose.

---

❓ **Q13 — What are the principal failure modes and stop conditions?**

➡️ **Chosen answer:** Stop without producing a final proposal when the active contract is absent/ambiguous, the three-month usage window is incomplete, the current policy cannot be read or is not `pricing_v2`, a plan lacks a v2 list price, calculations cannot be reconciled, or an above-cap discount lacks director approval. Explicitly guard against stale/expired contracts, legacy pricing, stacked volume bands, premature loyalty eligibility, invented data/discounts, altered/missing clauses, and accidental external sending.

**Why:** These cover the incident named by the lead, the deliberate traps in the files, and the main ways a plausible-looking proposal could be lucky-correct or commercially unauthorized.

---

❓ **Q14 — What is the exact definition of done?**

➡️ **Chosen answer:** Done means both named files exist under `build/renewal-proposal/`; all values trace to the supplied inputs; JSON arithmetic recomputes exactly; proposal values agree with JSON; the active contract and v2 policy were read before calculation; every required clause appears verbatim; no approval-required exception remains unresolved; and the final reply names recommended seats, annual price, discounts, and both output paths.

**Why:** This combines the requested outputs with observable behavior and cross-file consistency, preventing a polished but unauditable result from passing.

## Explicit unknowns left for later correction

- Whether sales-director approval has a specific file/API source and whether an approved exception may exceed 20% rather than merely requiring escalation.
- Whether “recent three months” should eventually be derived dynamically from proposal date instead of using the supplied dated snapshot.
- Whether growth percentage should be rounded to a prescribed precision; this definition uses two decimal places.
- Whether the proposal requires a named recipient, branding, signature block, or an approval workflow before external delivery.
