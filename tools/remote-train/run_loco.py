#!/usr/bin/env python3
"""Leave-case-out (LOCO) evaluation of the decision SLM — every one of the 34 policies
becomes unseen exactly once, answering the "cluster n=6" power objection.

Runs from the laptop; the 4090 box (ssh host, default `linux-builder`) does training and
serving. Per fold: build the dataset with that fold's cases held out → scp → QLoRA train
(2 epochs, fixed seed, adapter only — no 15GB merge) → serve base+adapter via serve_shim
→ grade the fold's eval_unseen locally through the ssh tunnel. Results accumulate in
examples/org/decision-slm/loco/results.json so an interrupted run resumes at the next fold.

Prereq: an ssh tunnel `ssh -f -N -L 18399:localhost:8399 linux-builder` (or --base-url).
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
ORG = REPO / "examples" / "org"
sys.path.insert(0, str(ORG))
import decision_eval  # noqa: E402  (ask/grade/cluster helpers)
import decision_dataset  # noqa: E402

SEED = 20260831
EPOCHS = "2.0"  # matches the original decision run (confirmed from its train.log)
BASE_MODEL = "Qwen/Qwen2.5-7B-Instruct"
REMOTE_DIR = "owc-train/loco"
LOCO_OUT = ORG / "decision-slm" / "loco"


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def folds(n_folds: int) -> list[list[str]]:
    catalog = yaml.safe_load((ORG / "catalog.yaml").read_text(encoding="utf-8"))
    ids = [c["id"] for c in catalog["cases"]]
    random.Random(SEED).shuffle(ids)
    out: list[list[str]] = [[] for _ in range(n_folds)]
    for i, cid in enumerate(ids):
        out[i % n_folds].append(cid)
    return out


def wait_serving(host: str, log: str, timeout: int = 300) -> None:
    for _ in range(timeout // 5):
        r = subprocess.run(["ssh", host, f"grep -c '^serving' {log} 2>/dev/null || true"],
                           capture_output=True, text=True)
        if r.stdout.strip() not in ("", "0"):
            return
        time.sleep(5)
    raise RuntimeError(f"shim did not come up; check {log}")


def eval_fold(base_url: str, model_label: str, items: list[dict], rules_by_case: dict) -> dict:
    results, exact, verdict_ok, relaxed_ok = [], 0, 0, 0
    for item in items:
        reply, _ = decision_eval.ask(base_url, model_label, item["system"], item["user"])
        g = decision_eval.grade(item, reply, rules_by_case)
        exact += g["ok"]
        verdict_ok += g.get("verdict_ok", False)
        relaxed_ok += g.get("relaxed_ok", False)
        results.append({"case_id": item["case_id"], "instance": item["instance_id"], "ok": g["ok"],
                        "verdict_ok": g.get("verdict_ok", False), "relaxed_ok": g.get("relaxed_ok", False)})
    n = len(items)
    return {"n": n, "exact": exact, "verdict_ok": verdict_ok, "relaxed_ok": relaxed_ok, "results": results}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="linux-builder")
    ap.add_argument("--base-url", default="http://127.0.0.1:18399/v1")
    ap.add_argument("--n-folds", type=int, default=6)
    ap.add_argument("--folds", default="", help="comma-separated fold indexes to run (default: all missing)")
    args = ap.parse_args()

    LOCO_OUT.mkdir(parents=True, exist_ok=True)
    results_path = LOCO_OUT / "results.json"
    done: dict = json.loads(results_path.read_text()) if results_path.exists() else {"folds": {}}
    plan = folds(args.n_folds)
    (LOCO_OUT / "folds.json").write_text(json.dumps({"seed": SEED, "folds": plan}, indent=2) + "\n")
    catalog = yaml.safe_load((ORG / "catalog.yaml").read_text(encoding="utf-8"))
    rules_by_case = {c["id"]: c["rules"] for c in catalog["cases"]}
    todo = [int(x) for x in args.folds.split(",") if x] or [i for i in range(args.n_folds)
                                                           if str(i) not in done["folds"]]

    for i in todo:
        holdout = plan[i]
        print(f"=== fold {i}: holdout {holdout}", flush=True)
        local = Path("/tmp") / f"owc-loco-fold{i}"
        stats = decision_dataset.main(holdout=holdout, out=local)
        print("dataset:", stats, flush=True)
        remote = f"{REMOTE_DIR}/fold{i}"
        sh(["ssh", args.host, f"rm -rf {remote} && mkdir -p {remote}"])
        sh(["scp", "-q", "-r", str(local / "data"), f"{args.host}:{remote}/data"])
        # train (adapter only), then serve base+adapter; both under nohup so ssh returns
        sh(["ssh", args.host,
            f"cd ~/owc-train && nohup ~/owc-train-venv/bin/python train_remote.py {BASE_MODEL} "
            f"~/{remote}/data ~/{remote}/out {EPOCHS} {SEED} no-merge > ~/{remote}/train.log 2>&1"])
        sh(["ssh", args.host, f"pkill -f '[s]erve_shim' || true; sleep 3"])
        sh(["ssh", "-f", args.host,
            f"nohup ~/owc-train-venv/bin/python ~/owc-train/serve_shim.py {BASE_MODEL} 8399 "
            f"~/{remote}/out/adapter > ~/{remote}/serve.log 2>&1 &"])
        wait_serving(args.host, f"~/{remote}/serve.log")
        items = [json.loads(l) for l in (local / "eval_unseen.jsonl").read_text().splitlines()]
        fold_res = eval_fold(args.base_url, f"loco-fold{i}", items, rules_by_case)
        fold_res["holdout"] = holdout
        done["folds"][str(i)] = fold_res
        results_path.write_text(json.dumps(done, indent=2, ensure_ascii=False) + "\n")
        print(f"fold {i}: exact {fold_res['exact']}/{fold_res['n']}", flush=True)
        sh(["ssh", args.host, "pkill -f '[s]erve_shim' || true"])

    # pooled: every case is unseen exactly once → 34 clusters
    per_case: dict[str, list[int]] = {}
    tot_n = tot_exact = tot_verdict = tot_relaxed = 0
    for f in done["folds"].values():
        tot_n += f["n"]; tot_exact += f["exact"]
        tot_verdict += f["verdict_ok"]; tot_relaxed += f["relaxed_ok"]
        for r in f["results"]:
            per_case.setdefault(r["case_id"], []).append(int(r["ok"]))
    clusters = {c: (sum(v), len(v)) for c, v in per_case.items()}
    ci = decision_eval.cluster_bootstrap_ci(clusters) if clusters else None
    summary = {"folds_done": len(done["folds"]), "cases": len(per_case), "n": tot_n,
               "exact": tot_exact, "exact_pct": round(100 * tot_exact / tot_n, 1) if tot_n else 0,
               "verdict_pct": round(100 * tot_verdict / tot_n, 1) if tot_n else 0,
               "relaxed_pct": round(100 * tot_relaxed / tot_n, 1) if tot_n else 0,
               "ci95_cluster": list(ci) if ci else None}
    done["summary"] = summary
    results_path.write_text(json.dumps(done, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
