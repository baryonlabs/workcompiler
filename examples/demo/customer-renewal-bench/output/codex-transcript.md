OpenAI Codex v0.150.1
--------
workdir: /Users/hongmartin/orca/projects/open-workflow
model: gpt-5.6-sol
provider: openworkflow
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR] (network access enabled)
reasoning effort: none
reasoning summaries: none
session id: 01a04b0b-3a8a-72b2-8905-cb600a9ad15a
--------
user
Read examples/customer-renewal/TASK.md and carry it out exactly as written.
codex
I’ll read the task file first, then follow its instructions precisely.
exec
/bin/zsh -lc "sed -n '1,240p' examples/customer-renewal/TASK.md" in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 0ms:
# Task: renewal proposal for customer CUST-1001

You are the sales-ops assistant. Prepare the annual renewal proposal for **CUST-1001**.

Rules (from `behaviors/`): verify the *active* contract in the CRM before pricing, and price with the
*current* policy `data/pricing/pricing_v2.yaml` — never the legacy table.

Do the work with auditable shell commands (jq / python3 / cat), from the repository root:

1. **Lookup contract** — read `examples/customer-renewal/data/crm/contracts.json`, select the
   contract for CUST-1001 whose `status` is `active`, and print it.
2. **Calculate usage** — from `examples/customer-renewal/data/usage/usage-2026-07.csv`, compute for
   CUST-1001 the peak `seats_active` over the 3 months, the growth of `seats_active` (last vs first
   month, in %) and the average `api_calls`.
3. **Price the offer** — apply `pricing_v2.yaml`: recommended committed seats per `seat_recommendation`,
   list price for the plan, volume discount band, loyalty discount if the customer has >= 2 years of
   continuous service (use the active contract's `start_date`, today is 2026-08-29), cap at
   `max_total_discount_pct`. Compute monthly and annual totals. Write the calculation as JSON to
   `build/renewal/pricing-CUST-1001.json`.
4. **Draft the proposal** — write `build/renewal/proposal-CUST-1001.md` with: customer & contract
   summary, usage summary, a pricing table (seats × list price − discounts = monthly / annual), and
   every clause from `required_clauses` verbatim.
5. Reply with a short summary (recommended seats, total annual price, discounts applied) and the two
   file paths.

codex
The task requires an auditable contract lookup and current-policy calculation. I’m now inspecting the active CRM record, usage inputs, pricing policy, and behavior clauses before creating the two deliverables.
exec
/bin/zsh -lc "rg --files examples/customer-renewal && find examples/customer-renewal/behaviors -type f -maxdepth 2 -print 2>/dev/null || true && jq '.[] | select(.customer_id == \"CUST-1001\" and .status == \"active\")' examples/customer-renewal/data/crm/contracts.json && cat examples/customer-renewal/data/usage/usage-2026-07.csv && cat examples/customer-renewal/data/pricing/pricing_v2.yaml" in /Users/hongmartin/orca/projects/open-workflow
 exited 5 in 0ms:
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
examples/customer-renewal/behaviors/verify-current-contract/BEHAVIOR.md
jq: error (at examples/customer-renewal/data/crm/contracts.json:50): Cannot index string with string "customer_id"

codex
The first lookup exposed that the CRM file is an object rather than a top-level array, so the literal array query was invalid. I’m resolving its schema and will select the active record from the correct collection without changing the selection rule.
exec
/bin/zsh -lc 'cat examples/customer-renewal/data/crm/contracts.json
cat examples/customer-renewal/data/usage/usage-2026-07.csv
cat examples/customer-renewal/data/pricing/pricing_v2.yaml
cat examples/customer-renewal/behaviors/verify-current-contract/BEHAVIOR.md
cat examples/customer-renewal/behaviors/use-current-pricing-policy/BEHAVIOR.md' in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 0ms:
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
      "contract_id": "CTR-2025-0142",
      "status": "active",
      "plan": "professional",
      "seats": 60,
      "price_per_seat_month_usd": 25.0,
      "pricing_policy": "pricing_v2",
      "start_date": "2025-11-15",
      "end_date": "2026-11-14",
      "billing": "annual",
      "account_owner": "m.lee@example.com",
      "special_terms": ["custom SLA 99.95%"]
    },
    {
      "customer_id": "CUST-1001",
      "customer_name": "ACME Manufacturing Co.",
      "contract_id": "CTR-2022-0311",
      "status": "expired",
      "plan": "professional",
      "seats": 120,
      "price_per_seat_month_usd": 22.0,
      "pricing_policy": "pricing_v1_legacy",
      "start_date": "2022-09-01",
      "end_date": "2024-08-31",
      "billing": "annual",
      "account_owner": "j.park@example.com",
      "special_terms": []
    }
  ]
}
customer_id,month,seats_active,api_calls,storage_gb,support_tickets
CUST-1001,2026-05,238,1840000,910,4
CUST-1001,2026-06,247,2010000,955,3
CUST-1001,2026-07,262,2265000,1010,5
CUST-1002,2026-05,54,310000,120,1
CUST-1002,2026-06,57,325000,128,2
CUST-1002,2026-07,58,331000,131,1
# Current enterprise pricing policy (rules.pricing_v2). Effective 2026-01-01.
# The renewal offer MUST be computed from this table (see behaviors/use-current-pricing-policy).
policy: pricing_v2
effective_from: "2026-01-01"
currency: USD
renewal_term_months: 12
list_price_per_seat_month:
  starter: 12.0
  professional: 25.0
  enterprise: 40.0
volume_discount_bands:            # applied on list price, by committed seats
  - min_seats: 50
    pct: 5
  - min_seats: 200
    pct: 10
  - min_seats: 500
    pct: 15
loyalty_discount:                 # customers with >= min_years continuous service
  min_years: 2
  pct: 3
max_total_discount_pct: 20        # hard cap; anything beyond needs sales-director approval
seat_recommendation:
  rule: "commit seats = max(current contract seats, peak seats_active of last 3 months) rounded up to next 10"
required_clauses:
  - "12-month term with 60-day auto-renewal notice"
  - "Data Processing Addendum v3 attached"
  - "Price valid for 30 days from proposal date"
# BEHAVIOR: verify-current-contract

## 1. Intent
Ensure that any renewal offer or contract analysis looks up the active, current customer contract from the CRM before computing renewal terms.

## 2. Evidence
Evidence consists of a `crm.lookup_contract` step occurring before `services.usage.calculate` or `rules.pricing_v2` steps in the execution trajectory.

## 3. Decision
- `true`: `crm.lookup_contract` executed successfully and returned active contract data prior to pricing logic.
- `false`: Pricing or drafting occurred without querying the active contract, or queried a cached/stale record.
- `na`: Trajectory does not involve contract renewals.

## 4. Execution
Enforced at compile-time as a non-removable workflow transition dependency and verified by post-hoc trajectory judges.

## 5. Recovery
If missing, halt execution and escalate to CRM lookup connector or prompt reviewer.

## 6. Failure Modes
Using hardcoded contract terms or relying on LLM memory from previous turns.
# BEHAVIOR: use-current-pricing-policy

## 1. Intent
Guarantees that pricing calculations apply the current active enterprise pricing table (`rules.pricing_v2`) rather than legacy discount structures.

## 2. Evidence
Invocation of `rules.pricing_v2` with live policy parameters in the trajectory.

## 3. Decision
- `true`: Active pricing policy rule engine was queried and applied.
- `false`: Custom unverified pricing was hallucinated or legacy table was applied.
- `na`: Trajectory does not perform pricing calculations.

## 4. Execution
Enforced as a deterministic Rule engine executor step.

## 5. Recovery
Re-derive offer using standard rule engine `rules.pricing_v2`.

## 6. Failure Modes
LLM hallucinating custom percentage discounts outside authorized bands.

exec
/bin/zsh -lc "jq '.contracts[] | select(.customer_id == \"CUST-1001\" and .status == \"active\")' examples/customer-renewal/data/crm/contracts.json
python3 - <<'PY'
import csv, json, math
from datetime import date
from pathlib import Path
import yaml

root = Path('examples/customer-renewal')
contracts = json.loads((root / 'data/crm/contracts.json').read_text())['contracts']
contract = next(c for c in contracts if c['customer_id'] == 'CUST-1001' and c['status'] == 'active')
with (root / 'data/usage/usage-2026-07.csv').open(newline='') as f:
    usage = [r for r in csv.DictReader(f) if r['customer_id'] == 'CUST-1001']
usage.sort(key=lambda r: r['month'])
peak = max(int(r['seats_active']) for r in usage)
growth = (int(usage[-1]['seats_active']) / int(usage[0]['seats_active']) - 1) * 100
avg_api = sum(int(r['api_calls']) for r in usage) / len(usage)
policy = yaml.safe_load((root / 'data/pricing/pricing_v2.yaml').read_text())
base_seats = max(contract['seats'], peak)
recommended = math.ceil(base_seats / 10) * 10
volume = max((b['pct'] for b in policy['volume_discount_bands'] if recommended >= b['min_seats']), default=0)
today = date(2026, 8, 29)
start = date.fromisoformat(contract['start_date'])
anniversary = start.replace(year=start.year + policy['loyalty_discount']['min_years'])
loyalty = policy['loyalty_discount']['pct'] if today >= anniversary else 0
total_discount = min(volume + loyalty, policy['max_total_discount_pct'])
list_price = policy['list_price_per_seat_month'][contract['plan']]
gross = recommended * list_price
monthly = gross * (1 - total_discount / 100)
annual = monthly * policy['renewal_term_months']
print(json.dumps({
    'usage': {'peak_seats_active': peak, 'seats_growth_pct': round(growth, 4), 'average_api_calls': round(avg_api, 2)},
    'pricing': {'recommended_committed_seats': recommended, 'list_price_per_seat_month_usd': list_price,
                'gross_monthly_usd': gross, 'volume_discount_pct': volume, 'loyalty_discount_pct': loyalty,
                'total_discount_pct': total_discount, 'monthly_total_usd': monthly, 'annual_total_usd': annual,
                'loyalty_eligible_as_of': str(today >= anniversary), 'two_year_anniversary': anniversary.isoformat()}
}, indent=2))
PY" in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 0ms:
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
    "list_price_per_seat_month_usd": 40.0,
    "gross_monthly_usd": 10800.0,
    "volume_discount_pct": 10,
    "loyalty_discount_pct": 0,
    "total_discount_pct": 10,
    "monthly_total_usd": 9720.0,
    "annual_total_usd": 116640.0,
    "loyalty_eligible_as_of": "False",
    "two_year_anniversary": "2026-09-01"
  }
}

codex
The calculation is complete: 270 committed seats, 10% volume discount, and no loyalty discount because the two-year anniversary is 2026-09-01—three days after the specified proposal date. I’m writing the auditable calculation and proposal now.
exec
/bin/zsh -lc 'mkdir -p build/renewal' in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 0ms:
apply patch
patch: completed
/Users/hongmartin/orca/projects/open-workflow/build/renewal/pricing-CUST-1001.json
/Users/hongmartin/orca/projects/open-workflow/build/renewal/proposal-CUST-1001.md
diff --git a/build/renewal/pricing-CUST-1001.json b/build/renewal/pricing-CUST-1001.json
new file mode 100644
index 0000000000000000000000000000000000000000..57ffb294fc6a0b7aa43fc5e8eff447a196899565
--- /dev/null
+++ b/build/renewal/pricing-CUST-1001.json
@@ -0,0 +1,44 @@
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
diff --git a/build/renewal/proposal-CUST-1001.md b/build/renewal/proposal-CUST-1001.md
new file mode 100644
index 0000000000000000000000000000000000000000..23c99f1dd2310d6dfbe4c0c8896defb850d4c48a
--- /dev/null
+++ b/build/renewal/proposal-CUST-1001.md
@@ -0,0 +1,39 @@
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
+| 270 seats × $40.00 list price | $10,800.00 | $129,600.00 |
+| Less 10% volume discount | −$1,080.00 | −$12,960.00 |
+| Less 0% loyalty discount | −$0.00 | −$0.00 |
+| **Total after discounts** | **$9,720.00** | **$116,640.00** |
+
+The 10% volume discount applies at the 200-seat band. No loyalty discount applies on the proposal date because two years of continuous service will be reached on 2026-09-01. The combined 10% discount is below the 20% policy cap.
+
+## Required clauses
+
+12-month term with 60-day auto-renewal notice
+
+Data Processing Addendum v3 attached
+
+Price valid for 30 days from proposal date

diff --git a/build/renewal/pricing-CUST-1001.json b/build/renewal/pricing-CUST-1001.json
new file mode 100644
index 0000000000000000000000000000000000000000..57ffb294fc6a0b7aa43fc5e8eff447a196899565
--- /dev/null
+++ b/build/renewal/pricing-CUST-1001.json
@@ -0,0 +1,44 @@
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
diff --git a/build/renewal/proposal-CUST-1001.md b/build/renewal/proposal-CUST-1001.md
new file mode 100644
index 0000000000000000000000000000000000000000..23c99f1dd2310d6dfbe4c0c8896defb850d4c48a
--- /dev/null
+++ b/build/renewal/proposal-CUST-1001.md
@@ -0,0 +1,39 @@
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
+| 270 seats × $40.00 list price | $10,800.00 | $129,600.00 |
+| Less 10% volume discount | −$1,080.00 | −$12,960.00 |
+| Less 0% loyalty discount | −$0.00 | −$0.00 |
+| **Total after discounts** | **$9,720.00** | **$116,640.00** |
+
+The 10% volume discount applies at the 200-seat band. No loyalty discount applies on the proposal date because two years of continuous service will be reached on 2026-09-01. The combined 10% discount is below the 20% policy cap.
+
+## Required clauses
+
+12-month term with 60-day auto-renewal notice
+
+Data Processing Addendum v3 attached
+
+Price valid for 30 days from proposal date

exec
/bin/zsh -lc "jq empty build/renewal/pricing-CUST-1001.json
python3 - <<'PY'
from pathlib import Path
import yaml
policy = yaml.safe_load(Path('examples/customer-renewal/data/pricing/pricing_v2.yaml').read_text())
proposal = Path('build/renewal/proposal-CUST-1001.md').read_text()
missing = [clause for clause in policy['required_clauses'] if clause not in proposal]
assert not missing, f'Missing required clauses: {missing}'
print('JSON valid; all required clauses present verbatim.')
PY
cat build/renewal/pricing-CUST-1001.json
cat build/renewal/proposal-CUST-1001.md" in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 0ms:
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
  "seat_recommendation": {
    "current_contract_seats": 240,
    "peak_seats_active": 262,
    "base_seats": 262,
    "rounding": "up to next 10",
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

For May through July 2026, active seats increased from 238 to 262, a 10.084% increase. Peak active seats were 262, and average API usage was 2,038,333.33 calls per month. Under the current policy, the greater of the current 240-seat commitment and the 262-seat peak is rounded up to the next 10 seats, producing a recommended commitment of 270 seats.

## Pricing

All amounts are in USD.

| Calculation | Monthly | Annual |
| --- | ---: | ---: |
| 270 seats × $40.00 list price | $10,800.00 | $129,600.00 |
| Less 10% volume discount | −$1,080.00 | −$12,960.00 |
| Less 0% loyalty discount | −$0.00 | −$0.00 |
| **Total after discounts** | **$9,720.00** | **$116,640.00** |

The 10% volume discount applies at the 200-seat band. No loyalty discount applies on the proposal date because two years of continuous service will be reached on 2026-09-01. The combined 10% discount is below the 20% policy cap.

## Required clauses

12-month term with 60-day auto-renewal notice

Data Processing Addendum v3 attached

Price valid for 30 days from proposal date

diff --git a/build/renewal/pricing-CUST-1001.json b/build/renewal/pricing-CUST-1001.json
new file mode 100644
index 0000000000000000000000000000000000000000..57ffb294fc6a0b7aa43fc5e8eff447a196899565
--- /dev/null
+++ b/build/renewal/pricing-CUST-1001.json
@@ -0,0 +1,44 @@
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
diff --git a/build/renewal/proposal-CUST-1001.md b/build/renewal/proposal-CUST-1001.md
new file mode 100644
index 0000000000000000000000000000000000000000..23c99f1dd2310d6dfbe4c0c8896defb850d4c48a
--- /dev/null
+++ b/build/renewal/proposal-CUST-1001.md
@@ -0,0 +1,39 @@
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
+| 270 seats × $40.00 list price | $10,800.00 | $129,600.00 |
+| Less 10% volume discount | −$1,080.00 | −$12,960.00 |
+| Less 0% loyalty discount | −$0.00 | −$0.00 |
+| **Total after discounts** | **$9,720.00** | **$116,640.00** |
+
+The 10% volume discount applies at the 200-seat band. No loyalty discount applies on the proposal date because two years of continuous service will be reached on 2026-09-01. The combined 10% discount is below the 20% policy cap.
+
+## Required clauses
+
+12-month term with 60-day auto-renewal notice
+
+Data Processing Addendum v3 attached
+
+Price valid for 30 days from proposal date

codex
Renewal proposal completed.

- Recommended seats: **270**
- Annual price: **$116,640**
- Discounts: **10% volume**, **0% loyalty**

Files:

- [Pricing calculation](/Users/hongmartin/orca/projects/open-workflow/build/renewal/pricing-CUST-1001.json)
- [Renewal proposal](/Users/hongmartin/orca/projects/open-workflow/build/renewal/proposal-CUST-1001.md)
diff --git a/build/renewal/pricing-CUST-1001.json b/build/renewal/pricing-CUST-1001.json
new file mode 100644
index 0000000000000000000000000000000000000000..57ffb294fc6a0b7aa43fc5e8eff447a196899565
--- /dev/null
+++ b/build/renewal/pricing-CUST-1001.json
@@ -0,0 +1,44 @@
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
diff --git a/build/renewal/proposal-CUST-1001.md b/build/renewal/proposal-CUST-1001.md
new file mode 100644
index 0000000000000000000000000000000000000000..23c99f1dd2310d6dfbe4c0c8896defb850d4c48a
--- /dev/null
+++ b/build/renewal/proposal-CUST-1001.md
@@ -0,0 +1,39 @@
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
+| 270 seats × $40.00 list price | $10,800.00 | $129,600.00 |
+| Less 10% volume discount | −$1,080.00 | −$12,960.00 |
+| Less 0% loyalty discount | −$0.00 | −$0.00 |
+| **Total after discounts** | **$9,720.00** | **$116,640.00** |
+
+The 10% volume discount applies at the 200-seat band. No loyalty discount applies on the proposal date because two years of continuous service will be reached on 2026-09-01. The combined 10% discount is below the 20% policy cap.
+
+## Required clauses
+
+12-month term with 60-day auto-renewal notice
+
+Data Processing Addendum v3 attached
+
+Price valid for 30 days from proposal date

tokens used
47,789
Renewal proposal completed.

- Recommended seats: **270**
- Annual price: **$116,640**
- Discounts: **10% volume**, **0% loyalty**

Files:

- [Pricing calculation](/Users/hongmartin/orca/projects/open-workflow/build/renewal/pricing-CUST-1001.json)
- [Renewal proposal](/Users/hongmartin/orca/projects/open-workflow/build/renewal/proposal-CUST-1001.md)
