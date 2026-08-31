#!/usr/bin/env python3
"""Fleet corpus for the customer-renewal work: 30 synthetic customers + deterministic ground truth.

The single recorded session (CUST-1001) proves the pipeline; training and honest evaluation need
breadth. This generator emits, from one seed:

* ``data/crm/contracts.json`` and ``data/usage/usage-2026-07.csv`` — the same shapes as the
  recorded fixtures, with customers deliberately placed on the decision boundaries the small
  models got wrong (volume-band edges 49/50/199/200/499/500, loyalty eligibility around the
  2026-08-29 proposal date).
* ``truth/<ID>/pricing-<ID>.json``, ``proposal-<ID>.md``, ``respond.md`` — computed by
  implementing the semantics of ``../data/pricing/pricing_v2.yaml`` (read from the file, single
  source of truth) in the exact structure of the recorded CUST-1001 artifacts. These are the
  supervised targets for `owc build train` and the answer key for gate evaluation.

Deterministic: re-running produces byte-identical output.
"""

from __future__ import annotations

import csv
import io
import json
import math
import random
from datetime import date
from pathlib import Path

import yaml

HERE = Path(__file__).parent
POLICY_PATH = HERE.parent / "data" / "pricing" / "pricing_v2.yaml"
PROPOSAL_DATE = date(2026, 8, 29)          # fixed in TASK.md
MONTHS = ["2026-05", "2026-06", "2026-07"]

NAMES = ["Aurora Textiles", "Beacon Analytics", "Cobalt Freight", "Dunes Hospitality", "Everline Media",
         "Foxglove Pharma", "Granite Works", "Harbor Robotics", "Ivory Paper Co.", "Juniper Foods",
         "Kestrel Airways", "Lumen Grid", "Maple Insurance", "Nimbus Cloudware", "Orchid Retail",
         "Pinecone Labs", "Quartz Mining", "Riverstone Bank", "Saffron Studios", "Tundra Logistics",
         "Umber Energy", "Vellum Press", "Willow Health", "Xenon Motors", "Yarrow Farms",
         "Zephyr Telecom", "Alder Construction", "Briar Security", "Cedar Learning", "Delta Marine"]

# seats chosen to cover every band and its edges; loyalty starts straddle the 2y boundary
SEAT_PLAN = [(38, "starter"), (45, "professional"), (49, "professional"), (50, "professional"),
             (55, "starter"), (60, "professional"), (80, "enterprise"), (110, "professional"),
             (140, "enterprise"), (170, "professional"), (190, "enterprise"), (199, "professional"),
             (200, "enterprise"), (210, "professional"), (240, "enterprise"), (260, "professional"),
             (300, "enterprise"), (340, "enterprise"), (380, "professional"), (420, "enterprise"),
             (460, "enterprise"), (490, "professional"), (499, "enterprise"), (500, "enterprise"),
             (510, "enterprise"), (520, "enterprise"), (65, "starter"), (95, "professional"),
             (150, "enterprise"), (230, "professional")]
START_DATES = ["2023-04-10", "2024-08-15", "2024-08-29", "2024-08-30", "2024-09-15", "2025-01-20",
               "2022-11-05", "2024-02-14", "2025-06-01", "2023-09-09"]

# Extension beyond the original 30: appended AFTER the fixed plan so the first 30 customers (and the
# held-out evaluation set) stay byte-identical while the training pool grows to N.
EXTRA_CUSTOMERS = 270
_ext_rng = random.Random(99)
for _i in range(EXTRA_CUSTOMERS):
    SEAT_PLAN.append((_ext_rng.randint(12, 560), _ext_rng.choice(["starter", "professional", "enterprise"])))
    NAMES.append(f"Fleet Client {_i + 31:03d}")


def money(x: float) -> float:
    return round(x + 1e-9, 2)


def load_policy() -> dict:
    return yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))


def price(policy: dict, contract: dict, usage_rows: list[dict]) -> dict:
    """The pricing_v2 semantics, implemented once, deterministically."""
    seats_series = [int(r["seats_active"]) for r in usage_rows]
    first, last, peak = seats_series[0], seats_series[-1], max(seats_series)
    growth = round((last - first) / first * 100, 4)
    avg_calls = money(sum(int(r["api_calls"]) for r in usage_rows) / len(usage_rows))

    base = max(int(contract["seats"]), peak)
    committed = math.ceil(base / 10) * 10

    band_min, band_pct = 0, 0
    for band in policy["volume_discount_bands"]:
        if committed >= band["min_seats"] and band["min_seats"] >= band_min:
            band_min, band_pct = band["min_seats"], band["pct"]

    start = date.fromisoformat(contract["start_date"])
    eligibility = start.replace(year=start.year + policy["loyalty_discount"]["min_years"])
    loyal = eligibility <= PROPOSAL_DATE
    loyalty_pct = policy["loyalty_discount"]["pct"] if loyal else 0

    uncapped = band_pct + loyalty_pct
    cap = policy["max_total_discount_pct"]
    total_pct = min(uncapped, cap)

    list_price = float(policy["list_price_per_seat_month"][contract["plan"]])
    gross = money(committed * list_price)
    discount = money(gross * total_pct / 100)
    monthly = money(gross - discount)
    annual = money(monthly * 12)

    return {
        "customer_id": contract["customer_id"],
        "contract_id": contract["contract_id"],
        "contract_status": "active",
        "plan": contract["plan"],
        "proposal_date": PROPOSAL_DATE.isoformat(),
        "policy": policy["policy"],
        "policy_effective_from": str(policy["effective_from"]),
        "currency": policy["currency"],
        "renewal_term_months": policy["renewal_term_months"],
        "usage": {
            "period_first_month": MONTHS[0], "period_last_month": MONTHS[-1],
            "first_month_seats_active": first, "last_month_seats_active": last,
            "peak_seats_active": peak, "seats_active_growth_pct": growth,
            "average_api_calls": avg_calls,
        },
        "seat_recommendation": {
            "current_contract_seats": int(contract["seats"]), "peak_seats_active": peak,
            "base_seats": base, "rounding": "up to next 10", "recommended_committed_seats": committed,
        },
        "list_price_per_seat_month_usd": list_price,
        "gross_monthly_usd": gross,
        "discounts": {
            "volume_band_min_seats": band_min, "volume_discount_pct": band_pct,
            "loyalty_min_years": policy["loyalty_discount"]["min_years"],
            "continuous_service_start_date": contract["start_date"],
            "loyalty_eligibility_date": eligibility.isoformat(),
            "loyalty_eligible_on_proposal_date": loyal,
            "loyalty_discount_pct": loyalty_pct,
            "uncapped_total_discount_pct": uncapped,
            "max_total_discount_pct": cap,
            "total_discount_pct": total_pct,
            "monthly_discount_usd": discount,
        },
        "monthly_total_usd": monthly,
        "annual_total_usd": annual,
    }


def _usd(x: float) -> str:
    return f"${x:,.2f}"


def proposal_md(p: dict, contract: dict, policy: dict) -> str:
    u, s, d = p["usage"], p["seat_recommendation"], p["discounts"]
    vol_m = money(p["gross_monthly_usd"] * d["volume_discount_pct"] / 100)
    loy_m = money(p["gross_monthly_usd"] * d["loyalty_discount_pct"] / 100)
    loyalty_line = (f"A {d['loyalty_discount_pct']}% loyalty discount applies (continuous service since "
                    f"{d['continuous_service_start_date']})." if d["loyalty_eligible_on_proposal_date"] else
                    f"No loyalty discount applies on the proposal date because two years of continuous service "
                    f"will be reached on {d['loyalty_eligibility_date']}.")
    band_line = (f"The {d['volume_discount_pct']}% volume discount applies at the {d['volume_band_min_seats']}-seat band."
                 if d["volume_discount_pct"] else "No volume discount applies at this commitment level.")
    clauses = "\n\n".join(policy["required_clauses"])
    return f"""# Annual Renewal Proposal — {contract['customer_name']}

Proposal date: {p['proposal_date']}

## Customer and contract summary

- Customer: {contract['customer_name']} ({p['customer_id']})
- Active contract: {p['contract_id']}
- Current plan: {p['plan'].capitalize()}
- Current committed seats: {s['current_contract_seats']}
- Contract term: {contract['start_date']} through {contract['end_date']}
- Billing: Annual
- Account owner: {contract['account_owner']}
- Renewal pricing policy: {p['policy']} (effective {p['policy_effective_from']})

## Usage summary

For May through July 2026, active seats went from {u['first_month_seats_active']} to {u['last_month_seats_active']}, a {u['seats_active_growth_pct']}% change. Peak active seats were {u['peak_seats_active']}, and average API usage was {u['average_api_calls']:,.2f} calls per month. Under the current policy, the greater of the current {s['current_contract_seats']}-seat commitment and the {s['peak_seats_active']}-seat peak is rounded up to the next 10 seats, producing a recommended commitment of {s['recommended_committed_seats']} seats.

## Pricing

All amounts are in USD.

| Calculation | Monthly | Annual |
| --- | ---: | ---: |
| {s['recommended_committed_seats']} seats × {_usd(p['list_price_per_seat_month_usd'])} list price | {_usd(p['gross_monthly_usd'])} | {_usd(money(p['gross_monthly_usd'] * 12))} |
| Less {d['volume_discount_pct']}% volume discount | −{_usd(vol_m)} | −{_usd(money(vol_m * 12))} |
| Less {d['loyalty_discount_pct']}% loyalty discount | −{_usd(loy_m)} | −{_usd(money(loy_m * 12))} |
| **Total after discounts** | **{_usd(p['monthly_total_usd'])}** | **{_usd(p['annual_total_usd'])}** |

{band_line} {loyalty_line} The combined {d['total_discount_pct']}% discount is below the {d['max_total_discount_pct']}% policy cap.

## Required clauses

{clauses}
"""


def respond_md(p: dict) -> str:
    d = p["discounts"]
    cid = p["customer_id"]
    return (f"Renewal proposal completed.\n\n- Recommended seats: **{p['seat_recommendation']['recommended_committed_seats']}**\n"
            f"- Annual price: **${p['annual_total_usd']:,.0f}**\n"
            f"- Discounts: **{d['volume_discount_pct']}% volume**, **{d['loyalty_discount_pct']}% loyalty**\n\n"
            f"Files:\n\n- [Pricing calculation](build/renewal/pricing-{cid}.json)\n"
            f"- [Renewal proposal](build/renewal/proposal-{cid}.md)\n")


def generate(out_dir: Path = HERE) -> dict:
    rng = random.Random(20260831)
    policy = load_policy()
    contracts, usage_rows = [], []
    for i, (seats, plan) in enumerate(SEAT_PLAN):
        cid = f"CUST-{2001 + i}"
        start = START_DATES[i % len(START_DATES)]
        contract = {
            "customer_id": cid, "customer_name": NAMES[i],
            "contract_id": f"CTR-{start[:4]}-{1000 + i}", "status": "active", "plan": plan,
            "seats": seats, "price_per_seat_month_usd": float(policy["list_price_per_seat_month"][plan]),
            "pricing_policy": rng.choice(["pricing_v2", "pricing_v1_legacy"]),   # legacy noise the policy says to ignore
            "start_date": start, "end_date": f"2026-{rng.randint(9, 12):02d}-28",
            "billing": "annual", "account_owner": f"owner{i}@example.com",
            "special_terms": ["custom SLA 99.9%"] if rng.random() < 0.2 else [],
        }
        contracts.append(contract)
        base = max(10, seats + rng.randint(-25, 20))
        drift = rng.choice([-4, -2, 1, 3, 5, 8])
        for m, month in enumerate(MONTHS):
            active = max(5, base + drift * m + rng.randint(-3, 3))
            usage_rows.append({"customer_id": cid, "month": month, "seats_active": active,
                               "api_calls": active * rng.randint(2500, 9000), "storage_gb": active * 4,
                               "support_tickets": rng.randint(0, 6)})
        if rng.random() < 0.2:      # expired older contract, like the recorded fixture's CUST-1001
            contracts.append({**contract, "contract_id": f"CTR-2022-{1500 + i}", "status": "expired",
                              "seats": max(10, seats - 40), "start_date": "2022-03-01", "end_date": "2024-02-29"})

    (out_dir / "data" / "crm").mkdir(parents=True, exist_ok=True)
    (out_dir / "data" / "usage").mkdir(parents=True, exist_ok=True)
    (out_dir / "data" / "crm" / "contracts.json").write_text(
        json.dumps({"generated_at": "2026-08-01", "contracts": contracts}, indent=2) + "\n", encoding="utf-8")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["customer_id", "month", "seats_active", "api_calls", "storage_gb", "support_tickets"])
    writer.writeheader()
    writer.writerows(usage_rows)
    (out_dir / "data" / "usage" / "usage-2026-07.csv").write_text(buf.getvalue(), encoding="utf-8")

    index = []
    for contract in contracts:
        if contract["status"] != "active":
            continue
        cid = contract["customer_id"]
        rows = [r for r in usage_rows if r["customer_id"] == cid]
        p = price(policy, contract, rows)
        tdir = out_dir / "truth" / cid
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / f"pricing-{cid}.json").write_text(json.dumps(p, indent=2) + "\n", encoding="utf-8")
        (tdir / f"proposal-{cid}.md").write_text(proposal_md(p, contract, policy), encoding="utf-8")
        (tdir / "respond.md").write_text(respond_md(p), encoding="utf-8")
        index.append({"customer_id": cid, "plan": contract["plan"], "seats": contract["seats"],
                      "recommended": p["seat_recommendation"]["recommended_committed_seats"],
                      "volume_pct": p["discounts"]["volume_discount_pct"],
                      "loyalty_pct": p["discounts"]["loyalty_discount_pct"],
                      "annual_total_usd": p["annual_total_usd"]})
    (out_dir / "truth" / "INDEX.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return {"customers": len(index), "contracts": len(contracts), "usage_rows": len(usage_rows)}


if __name__ == "__main__":
    print(json.dumps(generate()))
