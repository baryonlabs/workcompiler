# Benchmark — `customer-renewal-codex`

Recorded agent session `01a04b0b-3a8a-72b2-8905-cb600a9ad15a` (`codex_exec`) vs. compiled build `build/customer_renewal_codex`.

| | recorded (agent) | compiled (build) | delta |
| :-- | --: | --: | --: |
| LLM tokens (unique) | 23,614 | 4,208 | −82.2% |
| LLM tokens (cumulative-context sum; reference) | 139,437 | 4,208 | −97.0% |
| wall time | 82.6 s | 17.17 s | 4.8× faster |
| outputs reproduced | — | 8/8 | |
| actions compiled / escalated | — | 7 / 0 | |
| recorded window | 2026-08-29T01:03:46.209895+00:00 → 2026-08-29T01:05:06.342670+00:00 | | |

**Unique** is the headline metric: each token counted once — the first request's full prompt, then only each later request's prompt growth, plus every completion. The cumulative-context sum adds up every request's usage as reported by the provider — an agent session re-sends its whole context every turn, so that sum counts the same tokens once per turn and overstates the cost of the agent path. Escalated steps keep their full recorded per-request cost on the compiled side (conservative: a real escalation would send a smaller, rebuilt prompt).

## Per action

| action | tier | executor used | tokens rec (unique) → comp | latency rec → comp | output match |
| :-- | :-- | :-- | --: | --: | :-- |
| `shell_sed` | code | code:customer_renewal_codex/handlers | 14,031 → 0 | 3.2 s → 0.01 s | 1/1 |
| `shell_rg` | code | code:customer_renewal_codex/handlers | 983 → 0 | 6.7 s → 0.02 s | 1/1 |
| `shell_cat` | code | code:customer_renewal_codex/handlers | 659 → 0 | 5.8 s → 0.01 s | 1/1 |
| `shell_jq` | code | code:customer_renewal_codex/handlers | 3,867 → 0 | 26.3 s → 0.07 s | 2/2 |
| `shell_mkdir` | code | code:customer_renewal_codex/handlers | 1,521 → 0 | 5.3 s → 0.00 s | 1/1 |
| `write_pricing_cust_1001` | code | code:customer_renewal_codex/handlers | 1,305 → 0 | 24.2 s → 0.00 s | 1/1 |
| `respond` | slm | slm:qwen2.5:7b | 1,248 → 4,208 | 11.1 s → 17.05 s | 1/1 |

## SLM tier — small local model instead of the frontier LLM

| step | action | model | tokens (frontier → SLM) | latency | gate |
| :-- | :-- | :-- | --: | --: | :-- |
| step_8 | `respond` | qwen2.5:7b | 20,545 → 4,208 | 11.1 s → 17.1 s | gate PASS (recall 1.00; grounded 1.00; len ×1.0) |

## Token ledger — who spent what

Every recorded step, the model that produced it, and what runs it in the compiled build.

| step | action | recorded model | prompt (cached) + completion = total | unique | compiled executor | compiled tokens |
| :-- | :-- | :-- | --: | --: | :-- | --: |
| step_1 | `shell_sed` | ? | 13,938 (0) + 93 = 14,031 | 14,031 | code | 0 |
| step_2 | `shell_rg` | ? | 14,686 (0) + 235 = 14,921 | 983 | code | 0 |
| step_3 | `shell_cat` | ? | 15,130 (0) + 215 = 15,345 | 659 | code | 0 |
| step_4 | `shell_jq` | ? | 16,630 (0) + 1,001 = 17,631 | 2,501 | code | 0 |
| step_7 | `shell_jq` | ? | 19,297 (0) + 243 = 19,540 | 1,366 | code | 0 |
| step_5 | `shell_mkdir` | ? | 17,968 (0) + 183 = 18,151 | 1,521 | code | 0 |
| step_6 | `write_pricing_cust_1001` | ? | 18,174 (0) + 1,099 = 19,273 | 1,305 | code | 0 |
| step_8 | `respond` | ? | 20,443 (0) + 102 = 20,545 | 1,248 | qwen2.5:7b | 4,208 |

| model / executor | recorded tokens | compiled tokens |
| :-- | --: | --: |
| ? | 139,437 | 0 |
| code | 0 | 0 |
| qwen2.5:7b | 0 | 4,208 |

Recorded prompt tokens served from the provider cache: 0 (counted in the cumulative totals above; billed at the cached rate).
The per-model table sums every request's usage as reported by the provider (cumulative-context basis) — each agent turn re-sends its whole context, which is why it exceeds the agent CLI's own 'tokens used' figure. The *unique* column of the ledger counts each token once.

## Outputs

### `shell_sed` · step_1 — code:customer_renewal_codex/handlers

recorded:

```
# Task: renewal proposal for customer CUST-1001

You are the sales-ops assistant. Prepare the annual renewal proposal for **CUST-1001**.

Rules (from `behaviors/`): verify the *active* contract in the CRM before pricing, and price with the
*current* policy `data/pricing/pricing_v2.yaml` — never the legacy table.

Do the work with auditable shell commands (jq / python3 / cat), from the repository root:

1. **Lookup contract** — read `examples/customer-renewal/data/crm/contracts.json`, select the
   contract for CUST-1001 whose `status` is `active`, and print it.
2. **Calculate usage** — from `e
… (1015 more chars)
```

compiled:

```
# Task: renewal proposal for customer CUST-1001

You are the sales-ops assistant. Prepare the annual renewal proposal for **CUST-1001**.

Rules (from `behaviors/`): verify the *active* contract in the CRM before pricing, and price with the
*current* policy `data/pricing/pricing_v2.yaml` — never the legacy table.

Do the work with auditable shell commands (jq / python3 / cat), from the repository root:

1. **Lookup contract** — read `examples/customer-renewal/data/crm/contracts.json`, select the
   contract for CUST-1001 whose `status` is `active`, and print it.
2. **Calculate usage** — from `e
… (1015 more chars)
```

### `shell_rg` · step_2 — code:customer_renewal_codex/handlers (exit_code=5)

recorded:

```
examples/customer-renewal/domain.linkml.yaml
examples/customer-renewal/data/pricing/pricing_v1_legacy.yaml
examples/customer-renewal/data/pricing/pricing_v2.yaml
examples/customer-renewal/data/usage/usage-2026-07.csv
examples/customer-renewal/data/crm/contracts.json
examples/customer-renewal/TASK.md
examples/customer-renewal/behaviors/verify-current-contract/BEHAVIOR.md
examples/customer-renewal/behaviors/use-current-pricing-policy/BEHAVIOR.md
examples/customer-renewal/work.yaml
examples/customer-renewal/behaviors/use-current-pricing-policy/BEHAVIOR.md
examples/customer-renewal/behaviors/verif
… (146 more chars)
```

compiled:

```
examples/customer-renewal/domain.linkml.yaml
examples/customer-renewal/data/pricing/pricing_v1_legacy.yaml
examples/customer-renewal/data/pricing/pricing_v2.yaml
examples/customer-renewal/data/usage/usage-2026-07.csv
examples/customer-renewal/data/crm/contracts.json
examples/customer-renewal/TASK.md
examples/customer-renewal/behaviors/verify-current-contract/BEHAVIOR.md
examples/customer-renewal/behaviors/use-current-pricing-policy/BEHAVIOR.md
examples/customer-renewal/work.yaml
examples/customer-renewal/behaviors/use-current-pricing-policy/BEHAVIOR.md
examples/customer-renewal/behaviors/verif
… (146 more chars)
```

### `shell_cat` · step_3 — code:customer_renewal_codex/handlers

recorded:

```
{
  "generated_at": "2026-08-01",
  "contracts": [
    {
      "customer_id": "CUST-1001",
      "customer_name": "ACME Manufacturing Co.",
      "contract_id": "CTR-2024-0917",
      "status": "active",
      "plan": "enterprise",
      "seats": 240,
      "price_per_seat_month_usd": 38.0,
      "pricing_policy": "pricing_v1_legacy",
      "start_date": "2024-09-01",
      "end_date": "2026-09-30",
      "billing": "annual",
      "account_owner": "j.park@example.com",
      "special_terms": []
    },
    {
      "customer_id": "CUST-1002",
      "customer_name": "Bluebird Logistics",
      "
… (3879 more chars)
```

compiled:

```
{
  "generated_at": "2026-08-01",
  "contracts": [
    {
      "customer_id": "CUST-1001",
      "customer_name": "ACME Manufacturing Co.",
      "contract_id": "CTR-2024-0917",
      "status": "active",
      "plan": "enterprise",
      "seats": 240,
      "price_per_seat_month_usd": 38.0,
      "pricing_policy": "pricing_v1_legacy",
      "start_date": "2024-09-01",
      "end_date": "2026-09-30",
      "billing": "annual",
      "account_owner": "j.park@example.com",
      "special_terms": []
    },
    {
      "customer_id": "CUST-1002",
      "customer_name": "Bluebird Logistics",
      "
… (3879 more chars)
```

### `shell_jq` · step_4 — code:customer_renewal_codex/handlers

recorded:

```
{
  "customer_id": "CUST-1001",
  "customer_name": "ACME Manufacturing Co.",
  "contract_id": "CTR-2024-0917",
  "status": "active",
  "plan": "enterprise",
  "seats": 240,
  "price_per_seat_month_usd": 38.0,
  "pricing_policy": "pricing_v1_legacy",
  "start_date": "2024-09-01",
  "end_date": "2026-09-30",
  "billing": "annual",
  "account_owner": "j.park@example.com",
  "special_terms": []
}
{
  "usage": {
    "peak_seats_active": 262,
    "seats_growth_pct": 10.084,
    "average_api_calls": 2038333.33
  },
  "pricing": {
    "recommended_committed_seats": 270,
    "list_price_per_seat_month_
… (291 more chars)
```

compiled:

```
{
  "customer_id": "CUST-1001",
  "customer_name": "ACME Manufacturing Co.",
  "contract_id": "CTR-2024-0917",
  "status": "active",
  "plan": "enterprise",
  "seats": 240,
  "price_per_seat_month_usd": 38.0,
  "pricing_policy": "pricing_v1_legacy",
  "start_date": "2024-09-01",
  "end_date": "2026-09-30",
  "billing": "annual",
  "account_owner": "j.park@example.com",
  "special_terms": []
}
{
  "usage": {
    "peak_seats_active": 262,
    "seats_growth_pct": 10.084,
    "average_api_calls": 2038333.33
  },
  "pricing": {
    "recommended_committed_seats": 270,
    "list_price_per_seat_month_
… (291 more chars)
```

### `shell_jq` · step_7 — code:customer_renewal_codex/handlers

recorded:

```
JSON valid; all required clauses present verbatim.
{
  "customer_id": "CUST-1001",
  "contract_id": "CTR-2024-0917",
  "contract_status": "active",
  "plan": "enterprise",
  "proposal_date": "2026-08-29",
  "policy": "pricing_v2",
  "policy_effective_from": "2026-01-01",
  "currency": "USD",
  "renewal_term_months": 12,
  "usage": {
    "period_first_month": "2026-05",
    "period_last_month": "2026-07",
    "first_month_seats_active": 238,
    "last_month_seats_active": 262,
    "peak_seats_active": 262,
    "seats_active_growth_pct": 10.084,
    "average_api_calls": 2038333.33
  },
  "seat_r
… (2234 more chars)
```

compiled:

```
JSON valid; all required clauses present verbatim.
{
  "customer_id": "CUST-1001",
  "contract_id": "CTR-2024-0917",
  "contract_status": "active",
  "plan": "enterprise",
  "proposal_date": "2026-08-29",
  "policy": "pricing_v2",
  "policy_effective_from": "2026-01-01",
  "currency": "USD",
  "renewal_term_months": 12,
  "usage": {
    "period_first_month": "2026-05",
    "period_last_month": "2026-07",
    "first_month_seats_active": 238,
    "last_month_seats_active": 262,
    "peak_seats_active": 262,
    "seats_active_growth_pct": 10.084,
    "average_api_calls": 2038333.33
  },
  "seat_r
… (2234 more chars)
```

### `shell_mkdir` · step_5 — code:customer_renewal_codex/handlers

recorded:

```

```

compiled:

```

```

### `write_pricing_cust_1001` · step_6 — code:customer_renewal_codex/handlers (2 file(s) verified on disk)

recorded:

```
(files written by the agent's apply_patch)
```

compiled:

```
A /Users/hongmartin/orca/projects/open-workflow/build/renewal/pricing-CUST-1001.json
A /Users/hongmartin/orca/projects/open-workflow/build/renewal/proposal-CUST-1001.md

```

### `respond` · step_8 — slm:qwen2.5:7b (gate PASS (recall 1.00; grounded 1.00; len ×1.0))

recorded:

```
Renewal proposal completed.

- Recommended seats: **270**
- Annual price: **$116,640**
- Discounts: **10% volume**, **0% loyalty**

Files:

- [Pricing calculation](/Users/hongmartin/orca/projects/open-workflow/build/renewal/pricing-CUST-1001.json)
- [Renewal proposal](/Users/hongmartin/orca/projects/open-workflow/build/renewal/proposal-CUST-1001.md)
```

compiled:

```
Renewal proposal completed.

- Recommended seats: **270**
- Annual price: **$116,640**
- Discounts: **10% volume**, **0% loyalty**

Files:

- [Pricing calculation](/Users/hongmartin/orca/projects/open-workflow/build/renewal/pricing-CUST-1001.json)
- [Renewal proposal](/Users/hongmartin/orca/projects/open-workflow/build/renewal/proposal-CUST-1001.md)
```

## Final answer of the recorded agent

```
Renewal proposal completed.

- Recommended seats: **270**
- Annual price: **$116,640**
- Discounts: **10% volume**, **0% loyalty**

Files:

- [Pricing calculation](/Users/hongmartin/orca/projects/open-workflow/build/renewal/pricing-CUST-1001.json)
- [Renewal proposal](/Users/hongmartin/orca/projects/open-workflow/build/renewal/proposal-CUST-1001.md)
```
