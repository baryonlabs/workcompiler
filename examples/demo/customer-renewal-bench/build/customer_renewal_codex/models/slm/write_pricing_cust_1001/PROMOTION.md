# SLM promotion — `write_pricing_cust_1001` of `customer-renewal-codex`

Candidate: `qwen2.5:14b` at `http://127.0.0.1:11434/v1` (local, cost $0) · gate: ≥90% of evaluations PASS, anchor recall ≥90%, grounding ≥90%.

**Result: NOT promoted** — pass rate 0% over 1 recorded example(s).

| | recorded (frontier) | SLM | delta |
| :-- | --: | --: | --: |
| tokens | 19,273 | 4,200 | −78.2% |
| latency | 24.2 s | 67.9 s | 0.36× |

## Evaluations

| step | recorded model → tokens | SLM tokens (prompt + completion) | latency | gate |
| :-- | :-- | --: | --: | :-- |
| step_6 | ? → 19,273 | 4,200 (3,154 + 1,046) | 67.9 s | FAIL (recall 0.89; grounded 0.89; len ×1.0) |

### step_6 — SLM output

```
===FILE build/renewal/pricing-CUST-1001.json===
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
  "seat_recommendation": {
    "current_contract_seats": 240,
    "peak_seats_active": 262,
    "base_seats": 100,
    "rounding": "up to next 100",
    "recommended_committed_seats": 270
  },
  "list_price_per_seat_month_usd": 40.0,
  "gross_monthly_usd": 10800.0,
  "discounts": {
    "volume_band_min_seats": 200,
    "volume_discount_pct": 10,
    "loyalty_min_years": 2,
    "continuous_service_start_date": "2024-09-01",
    "loyalty_eligibility_date": "2026-09-01",
    "loyalty_eligible_on_proposal_date": false,
    "loyalty_discount_pct": 0,
    "uncapped_total_discount_pct": 10,
    "max_total_discount_pct": 20,
    "total_discount_pct": 10,
    "monthly_discount_usd": 1080.0
  },
  "monthly_total_usd": 9720.0,
  "annual_total_usd": 116640.0
}
===END===
===FILE build/renewal/proposal-CUST-1001.md===
# Annual Renewal Proposal — ACME Manufacturing Co.

Proposal date: 2026-08-29

## Customer and contract summary

- Customer: ACME Manufacturing Co. (CUST-1001)
- Active contract: CTR-2024-0917
- Current plan: Enterprise
- Current committed seats: 240
- Contract term: 2024-09-01 through 2026-09-30
- Billing: Annual
- Account owner: j.park@example.com
- Renewal pricing policy: pricing_v2 (effective 2026-01-01)

## Usage summary

For May through July, active seats increased from 238 to 262, a 10.084% increase. Peak active seats were 262 and average API usage was 2,038,333 calls per month. Under the current policy, the greater of the current 240-seat commitment and the 262-seat peak is rounded up to the next 100 seats, producing a recommended commitment of 270 seats.

## Pricing

All amounts are in USD.

| Calculation | Monthly | Annual |
| --- | ---: | ---: |
| 270 seats × $40.0 list price | $10800.0 | $129600.0 |
| Less 10% volume discount | −$1080.0 | −$12960.0 |
| Less 0% loyalty discount | −$0.0 | −$0.0 |
| **Total after discounts** | **$9720.0** | **$116640.0** |

The 10% volum
… [375 more chars]
```

Recorded (frontier) output:

```
*** Begin Patch
*** Add File: /Users/hongmartin/orca/projects/open-workflow/build/renewal/pricing-CUST-1001.json
+{
+  "customer_id": "CUST-1001",
+  "contract_id": "CTR-2024-0917",
+  "contract_status": "active",
+  "plan": "enterprise",
+  "proposal_date": "2026-08-29",
+  "policy": "pricing_v2",
+  "policy_effective_from": "2026-01-01",
+  "currency": "USD",
+  "renewal_term_months": 12,
+  "usage": {
+    "period_first_month": "2026-05",
+    "period_last_month": "2026-07",
+    "first_month_seats_active": 238,
+    "last_month_seats_active": 262,
+    "peak_seats_active": 262,
+    "seats_active_growth_pct": 10.084,
+    "average_api_calls": 2038333.33
+  },
+  "seat_recommendation": {
+    "current_contract_seats": 240,
+    "peak_seats_active": 262,
+    "base_seats": 262,
+    "rounding": "up to next 10",
+    "recommended_committed_seats": 270
+  },
+  "list_price_per_seat_month_usd": 40.0,
+  "gross_monthly_usd": 10800.0,
+  "discounts": {
+    "volume_band_min_seats": 200,
+    "volume_discount_pct": 10,
+    "loyalty_min_years": 2,
+    "continuous_service_start_date": "2024-09-01",
+    "loyalty_eligibility_date": "2026-09-01",
+    "loyalty_eligible_on_proposal_date": false,
+    "loyalty_discount_pct": 0,
+    "uncapped_total_discount_pct": 10,
+    "max_total_discount_pct": 20,
+    "total_discount_pct": 10,
+    "monthly_discount_usd": 1080.0
+  },
+  "monthly_total_usd": 9720.0,
+  "annual_total_usd": 116640.0
+}
*** Add File: /Users/hongmartin/orca/projects/open-workflow/build/renewal/proposal-CUST-1001.md
+# Annual Renewal Proposal — ACME Manufacturing Co.
+
+Proposal date: 2026-08-29
+
+## Customer and contract summary
+
+- Customer: ACME Manufacturing Co. (CUST-1001)
+- Active contract: CTR-2024-0917
+- Current plan: Enterprise
+- Current committed seats: 240
+- Contract term: 2024-09-01 through 2026-09-30
+- Billing: Annual
+- Account owner: j.park@example.com
+- Renewal pricing policy: pricing_v2 (effective 2026-01-01)
+
+## Usage summary
+
+For May through July 2026, active seats increased from 238 to 262, a 10.084% increase. Peak active seats were 262, and average API usage was 2,038,333.33 calls per month. Under the current policy, the greater of the current 240-seat commitment and the 262-seat peak is rounded up to the next 10 seats, producing a recommended commitment of 270 seats.
+
+## Pricing
+
+All amounts are in USD.
+
+| Calculation | Monthly | Annual |
+| --- | ---: | ---: |
+| 270 seats × $40.00 list price | $10,800.00 |
… [19 more chars]
```

How the gate works: *anchors* are the numbers / ids / file paths the frontier answer stated that also exist in the upstream step outputs; the SLM must restate them (recall) and must not state numbers that exist nowhere in its inputs (grounding). Process invariants are enforced by the compiled upstream steps.
