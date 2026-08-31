#!/usr/bin/env python3
"""Two remaining audit controls for the arithmetic (derivation) experiment, in one pass:

* **Frontier control** (`--frontier`): the *same compiled prompt* the SLM tier uses, answered by a
  frontier model (`claude -p`). Separates "compilation effect" from "small-model effect" — if the
  frontier passes the deterministic gate where every SFT arm scored 0/6, the failure is model
  capability, not the prompt/task framing.
* **Field-level partial credit** (always): instead of the all-or-nothing gate verdict, the fraction
  of numeric leaf fields in the truth pricing JSON that the model got exactly right — the
  resolution the 0/6 headline lacks.

Candidates: any OpenAI-compatible endpoint (`--base-url`, e.g. the 4090 shim) and/or `--frontier`.
Results append to models/slm/<action>/controls.json in the build.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from core.build import slm  # noqa: E402
from core.build.dataset import _fleet_truth_files, _fleet_upstream, fleet_dir  # noqa: E402
from core.work_ir import patchfmt  # noqa: E402


def numeric_field_accuracy(model_files: dict, truth_files: dict) -> dict:
    """Per-file fraction of numeric leaves matching the answer key exactly."""
    out = {}
    for path, truth_text in truth_files.items():
        if not path.endswith(".json"):
            continue
        try:
            truth_flat = slm._json_flat(json.loads(truth_text))
            got_flat = slm._json_flat(json.loads(model_files.get(path, "")))
        except Exception:
            out[path] = {"ok": 0, "total": None, "note": "unparseable"}
            continue
        nums = {k: v for k, v in truth_flat.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
        ok = sum(1 for k, v in nums.items() if k in got_flat and got_flat[k] == v)
        wrong = sorted(k for k, v in nums.items() if got_flat.get(k) != v)[:8]
        out[path] = {"ok": ok, "total": len(nums), "wrong_fields": wrong}
    return out


def ask_frontier(system: str, user: str, model: str) -> str:
    r = subprocess.run(["claude", "-p", "--model", model, "--append-system-prompt", system, user],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"claude -p failed: {r.stderr[:400]}")
    return r.stdout


def ask_openai(base_url: str, model: str, system: str, user: str) -> str:
    import urllib.request
    req = urllib.request.Request(f"{base_url.rstrip('/')}/chat/completions",
                                 data=json.dumps({"model": model, "max_tokens": 4096, "messages": [
                                     {"role": "system", "content": system},
                                     {"role": "user", "content": user}]}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("build_dir")
    ap.add_argument("action")
    ap.add_argument("--label", required=True)
    ap.add_argument("--base-url", default=None, help="OpenAI-compatible endpoint for the candidate")
    ap.add_argument("--model", default="candidate")
    ap.add_argument("--frontier", default=None, metavar="CLAUDE_MODEL",
                    help="use `claude -p --model <this>` instead of an endpoint")
    args = ap.parse_args()

    root = Path(args.build_dir)
    fleet = fleet_dir(root)
    holdout = json.loads((slm.slm_dir(root, args.action) / "data" / "eval.json").read_text())["holdout_customers"]
    params_spec = json.loads((root / "PARAMS.json").read_text())
    recorded_params = {p["name"]: p["recorded_value"] for p in params_spec.get("params", [])}
    param_name = next(iter(recorded_params), "customer_id")
    work = root.name

    rows = []
    for cid in holdout:
        upstream = _fleet_upstream(fleet, cid)
        truth = {p.replace(str(recorded_params.get(param_name, "CUST-1001")), cid): c
                 for p, c in _fleet_truth_files(fleet, cid).items()}
        truth_patch = patchfmt.wrap([patchfmt.render_add(p, c) for p, c in sorted(truth.items())])
        system, user = slm.build_file_prompt(args.action, work, {param_name: cid}, upstream, truth_patch)
        t0 = time.time()
        text = (ask_frontier(system, user, args.frontier) if args.frontier
                else ask_openai(args.base_url, args.model, system, user))
        latency = round(time.time() - t0, 1)
        files = slm.parse_file_blocks(text)
        context = "\n".join(o for _, o in upstream)
        verdict = slm.gate_files(files, recorded_patch=truth_patch, context=context,
                                 params={param_name: cid}, recorded_params={param_name: cid}, exact=True)
        acc = numeric_field_accuracy(files, truth)
        rows.append({"customer": cid, "passed": verdict.passed, "gate": verdict.summary(),
                     "field_accuracy": acc, "latency_s": latency})
        pct = [f"{p.split('/')[-1]} {a['ok']}/{a['total']}" for p, a in acc.items() if a["total"]]
        print(f"[{args.label}] {cid}: {'PASS' if verdict.passed else 'FAIL'} · fields {'; '.join(pct)}", flush=True)

    ok_sum = sum(a["ok"] for r in rows for a in r["field_accuracy"].values() if a["total"])
    tot_sum = sum(a["total"] for r in rows for a in r["field_accuracy"].values() if a["total"])
    summary = {"label": args.label, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "passed": sum(r["passed"] for r in rows), "n": len(rows),
               "field_accuracy_pct": round(100 * ok_sum / tot_sum, 1) if tot_sum else None,
               "fields": f"{ok_sum}/{tot_sum}", "results": rows}
    out = slm.slm_dir(root, args.action) / "controls.json"
    history = json.loads(out.read_text()) if out.exists() else []
    history.append(summary)
    out.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
