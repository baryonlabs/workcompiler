#!/usr/bin/env python3
"""C3c hardening controls: rule out the two remaining alternative explanations for the
unseen-policy result (tuned 7b 72.9% LOCO / 68.3% pinned split).

* **Counterfactual policies** (`cf`): the six pinned holdout cases with approve/reject flipped
  in every rule (and the fallback). The ground truth follows the *flipped* policy, common-sense
  priors point the old way. A model that actually applies the policy-in-context keeps its
  accuracy; a model guessing from priors inverts and collapses.
* **k-shot ICL baseline** (`icl`): raw (untrained) 7b with 3 worked policy-application examples
  from other cases prepended as chat turns, evaluated on the standard eval_unseen split. If
  prompting alone matched SFT, the training would be unnecessary.

Results append to examples/org/decision-slm/c3c_controls.json.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.request
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
ORG = REPO / "examples" / "org"
sys.path.insert(0, str(ORG))
import decision_dataset  # noqa: E402
import decision_eval  # noqa: E402
import engine  # noqa: E402

SEED = 20260831
N_PER_CASE = 10
OUT = ORG / "decision-slm" / "c3c_controls.json"

FLIP = {"approve": "reject", "reject": "approve"}


def counterfactual_case(case: dict) -> dict:
    cf = json.loads(json.dumps(case, ensure_ascii=False))
    cf["id"] = case["id"] + "-cf"
    for rule in cf["rules"]:
        if rule.get("verdict") in FLIP:
            rule["verdict"] = FLIP[rule["verdict"]]
    fb = cf.get("fallback") or {}
    if fb.get("verdict") in FLIP:
        fb["verdict"] = FLIP[fb["verdict"]]
    return cf


def cf_items(catalog: dict) -> tuple[list, dict]:
    items, rules_by_case = [], {}
    for case in catalog["cases"]:
        if case["id"] not in decision_dataset.HOLDOUT_CASES:
            continue
        cf = counterfactual_case(case)
        rules_by_case[cf["id"]] = cf["rules"]
        rng = random.Random(f"{SEED}:cf:{case['id']}")
        # only records where the flipped policy actually decides differently — on these,
        # answering from priors (= the original policy's behavior) scores zero by construction
        found = 0
        for _ in range(800):
            if found >= N_PER_CASE:
                break
            record = engine.sample(cf, rng)
            decision = engine.decide(cf, record)
            if decision["verdict"] == engine.decide(case, record)["verdict"]:
                continue
            found += 1
            system, user = decision_dataset.prompt_for(cf, record)
            items.append({"case_id": cf["id"], "instance_id": f"{cf['id']}-{found:04d}",
                          "system": system, "user": user,
                          "truth": json.loads(decision_dataset.target_for(decision))})
    return items, rules_by_case


def icl_shots(catalog: dict, k: int = 3) -> list:
    """k worked examples from non-holdout cases, as alternating user/assistant turns."""
    shots = []
    pool = [c for c in catalog["cases"] if c["id"] not in decision_dataset.HOLDOUT_CASES]
    rng = random.Random(f"{SEED}:icl")
    for case in rng.sample(pool, k):
        record = engine.sample(case, rng)
        decision = engine.decide(case, record)
        system, user = decision_dataset.prompt_for(case, record)
        shots.append({"system": system, "user": user, "assistant": decision_dataset.target_for(decision)})
    return shots


def ask_messages(base_url: str, model: str, messages: list, timeout: int = 240) -> str:
    payload = {"model": model, "temperature": 0, "max_tokens": 400, "messages": messages}
    req = urllib.request.Request(f"{base_url.rstrip('/')}/chat/completions",
                                 data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]


def run_eval(label: str, items: list, rules_by_case: dict, base_url: str, shots: list | None = None) -> dict:
    per_case: dict[str, list[int]] = {}
    exact = verdict_ok = relaxed_ok = 0
    for item in items:
        messages = [{"role": "system", "content": item["system"]}]
        for s in shots or []:
            # each shot carries its own case's policy inside the user turn; the system turn stays the target's
            messages += [{"role": "user", "content": f"(예시 — 다른 결정의 정책 적용)\n{s['user']}"},
                         {"role": "assistant", "content": s["assistant"]}]
        messages.append({"role": "user", "content": item["user"]})
        reply = ask_messages(base_url, label, messages)
        g = decision_eval.grade(item, reply, rules_by_case)
        exact += g["ok"]
        verdict_ok += g.get("verdict_ok", False)
        relaxed_ok += g.get("relaxed_ok", False)
        per_case.setdefault(item["case_id"], []).append(int(g["ok"]))
    n = len(items)
    clusters = {c: (sum(v), len(v)) for c, v in per_case.items()}
    ci = decision_eval.cluster_bootstrap_ci(clusters)
    res = {"label": label, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "n": n,
           "exact": exact, "exact_pct": round(100 * exact / n, 1),
           "verdict_pct": round(100 * verdict_ok / n, 1), "relaxed_pct": round(100 * relaxed_ok / n, 1),
           "ci95_cluster": list(ci) if ci else None,
           "per_case": {c: f"{sum(v)}/{len(v)}" for c, v in sorted(per_case.items())}}
    print(json.dumps(res, ensure_ascii=False), flush=True)
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["cf", "icl"])
    ap.add_argument("--base-url", default="http://127.0.0.1:18399/v1")
    ap.add_argument("--label", required=True)
    args = ap.parse_args()

    catalog = yaml.safe_load((ORG / "catalog.yaml").read_text(encoding="utf-8"))
    if args.mode == "cf":
        items, cf_rules = cf_items(catalog)
        res = run_eval(args.label, items, cf_rules, args.base_url)
    else:
        items = [json.loads(l) for l in (ORG / "decision-slm" / "eval_unseen.jsonl").read_text().splitlines()]
        rules_by_case = {c["id"]: c["rules"] for c in catalog["cases"]}
        res = run_eval(args.label, items, rules_by_case, args.base_url, shots=icl_shots(catalog))
    res["mode"] = args.mode
    history = json.loads(OUT.read_text()) if OUT.exists() else []
    history.append(res)
    OUT.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
