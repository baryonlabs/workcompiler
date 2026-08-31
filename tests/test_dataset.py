"""Dataset builder + fleet evaluation: recorded/cache/fleet sources, held-out split, gate scoring."""

import json
from pathlib import Path

from core.build import cache, dataset, slm
from tests.test_slm import GOOD_1002, PATCH, _fake_transport, _write_build

FLEET_TRUTH_PRICING = {
    "customer_id": "CUST-9001", "seats": 60, "list_price": 25.0, "gross_monthly_usd": 1500.0,
    "discounts": {"volume_band_min_seats": 50, "volume_discount_pct": 5, "monthly_discount_usd": 75.0},
    "monthly_total_usd": 1425.0, "annual_total_usd": 17100.0,
}


def _mini_fleet(tmp_path):
    fleet = tmp_path / "fleet"
    (fleet / "data" / "crm").mkdir(parents=True)
    (fleet / "data" / "usage").mkdir(parents=True)
    (fleet.parent / "data" / "pricing").mkdir(parents=True, exist_ok=True)
    (fleet.parent / "data" / "pricing" / "pricing_v2.yaml").write_text(
        "volume_discount_bands:\n  - min_seats: 50\n    pct: 5\n  - min_seats: 200\n    pct: 10\n")
    contracts = [{"customer_id": f"CUST-{9001 + i}", "customer_name": f"C{i}", "contract_id": f"CTR-{i}",
                  "status": "active", "plan": "professional", "seats": 60, "start_date": "2025-01-01",
                  "end_date": "2026-12-31", "account_owner": "o@example.com"} for i in range(8)]
    (fleet / "data" / "crm" / "contracts.json").write_text(json.dumps({"contracts": contracts}))
    rows = ["customer_id,month,seats_active,api_calls"] + \
        [f"CUST-{9001 + i},2026-0{m},58,300000" for i in range(8) for m in (5, 6, 7)]
    (fleet / "data" / "usage" / "usage-2026-07.csv").write_text("\n".join(rows) + "\n")
    for i in range(8):
        cid = f"CUST-{9001 + i}"
        tdir = fleet / "truth" / cid
        tdir.mkdir(parents=True)
        pricing = dict(FLEET_TRUTH_PRICING, customer_id=cid)
        (tdir / f"pricing-{cid}.json").write_text(json.dumps(pricing, indent=2) + "\n")
        (tdir / f"proposal-{cid}.md").write_text(f"# Proposal {cid}\nSeats 60, $1,500.00/mo, 5% volume, $1,425.00/mo, $17,100.00/yr.\n")
        (tdir / "respond.md").write_text(f"Done for {cid}: **60** seats, **$17,100**, **5% volume**.\n")
    (fleet / "truth" / "INDEX.json").write_text(json.dumps(
        [{"customer_id": f"CUST-{9001 + i}"} for i in range(8)]))
    return fleet


def test_build_dataset_merges_sources_and_holds_out_customers(tmp_path, monkeypatch):
    root, _ = _write_build(tmp_path, monkeypatch)
    fleet = _mini_fleet(tmp_path)
    # a cache entry with stored upstream doubles as a training row
    cache.store(root, "write_pricing", {"customer_id": "CUST-1002"}, output="", source="claude",
                files=slm.parse_file_blocks(GOOD_1002), upstream=[("shell_cat", "ctx for 1002")])
    rep = dataset.build_dataset(root, "write_pricing", fleet=fleet, holdout=2)
    assert rep.mode == "files" and rep.sources == {"recorded": 1, "cache": 1, "fleet": 8}
    assert len(rep.eval_customers) == 2
    train = [json.loads(l) for l in Path(rep.train_path).read_text().splitlines()]
    valid = [json.loads(l) for l in Path(rep.valid_path).read_text().splitlines()]
    assert rep.rows == len(train) + len(valid) == 10 - 2
    text = Path(rep.train_path).read_text() + Path(rep.valid_path).read_text()
    for held in rep.eval_customers:
        assert held not in text                      # the answer key never leaks into training
    assert all(set(m["role"] for m in r["messages"]) == {"system", "user", "assistant"} for r in train)
    assert "===FILE" in train[0]["messages"][2]["content"]
    eval_info = json.loads((Path(rep.train_path).parent / "eval.json").read_text())
    assert eval_info["holdout_customers"] == rep.eval_customers


def test_evaluate_fleet_scores_with_the_exact_gate(tmp_path, monkeypatch):
    root, _ = _write_build(tmp_path, monkeypatch)
    fleet = _mini_fleet(tmp_path)
    rt = slm.SLMRuntime(model="fake-tuned")
    correct = "\n".join(
        f"===FILE build/renewal/{name}-CUST-9001.{ext}===\n{content}===END===" for name, ext, content in (
            ("pricing", "json", json.dumps(dict(FLEET_TRUTH_PRICING, customer_id="CUST-9001"), indent=2) + "\n"),
            ("proposal", "md", "# Proposal CUST-9001\nSeats 60, $1,500.00/mo, 5% volume, $1,425.00/mo, $17,100.00/yr.\n")))
    ev = dataset.evaluate_fleet(root, "write_pricing", rt, ["CUST-9001"], fleet=fleet, transport=_fake_transport(correct))
    assert ev.totals()["passed"] == 1 and ev.pass_rate == 1.0
    wrong = correct.replace('"monthly_total_usd": 1425.0', '"monthly_total_usd": 1350.0')
    ev = dataset.evaluate_fleet(root, "write_pricing", rt, ["CUST-9001"], fleet=fleet, transport=_fake_transport(wrong))
    assert ev.totals()["passed"] == 0
    md = dataset.eval_markdown("write_pricing", [ev], ["CUST-9001"], dataset.DatasetReport("write_pricing", "files", 8, {"fleet": 8}))
    assert "| fake-tuned | 0/1" in md
