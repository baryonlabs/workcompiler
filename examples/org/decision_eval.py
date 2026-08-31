#!/usr/bin/env python3
"""Gate-evaluate a decision model (any OpenAI-compatible endpoint) on the catalog eval splits.

Exact-match gate per instance: verdict, route, params and the cited rule must all equal the
engine's deterministic label — and, independently, the cited rule's condition must actually hold
on the record (no fabricated grounds; checked with the same DSL the engine uses).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import engine  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "decision-slm"
_JSON_RE = re.compile(r"\{.*\}", re.S)


def ask(base_url: str, model: str, system: str, user: str, timeout: int = 240) -> tuple[str, int]:
    payload = {"model": model, "temperature": 0, "max_tokens": 400,
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    req = urllib.request.Request(f"{base_url.rstrip('/')}/chat/completions",
                                 data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    usage = data.get("usage") or {}
    return data["choices"][0]["message"]["content"], int(usage.get("total_tokens") or 0)


def grade(item: dict, reply: str, rules_by_case: dict) -> dict:
    truth = item["truth"]
    m = _JSON_RE.search(reply or "")
    if not m:
        return {"ok": False, "why": "no_json"}
    try:
        got = json.loads(m.group(0))
    except Exception:
        return {"ok": False, "why": "bad_json"}
    checks = {
        "verdict": got.get("verdict") == truth["verdict"],
        "route": got.get("route") == truth["route"],
        "params": (got.get("params") or {}) == (truth.get("params") or {}),
        "cited_rule": got.get("cited_rule") == truth["cited_rule"],
    }
    # no fabricated grounds: the cited rule's condition must hold on the record
    case_rules = rules_by_case[item["case_id"]]
    cited = next((r for r in case_rules if r.get("name") == got.get("cited_rule")), None)
    record = json.loads(re.search(r"```json\n(.*?)\n```", item["user"], re.S).group(1))
    checks["grounds_hold"] = bool(cited) and engine.check(cited["when"], record) if got.get("cited_rule") != "fallback" \
        else got.get("cited_rule") == truth["cited_rule"]
    return {"ok": all(checks.values()), "verdict_ok": checks["verdict"], "checks": checks, "why": ""}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:11434/v1")
    ap.add_argument("--model", required=True)
    ap.add_argument("--label", default=None)
    ap.add_argument("--limit", type=int, default=0, help="cap instances per split (0 = all)")
    args = ap.parse_args()

    import yaml
    catalog = yaml.safe_load((HERE / "catalog.yaml").read_text(encoding="utf-8"))
    rules_by_case = {c["id"]: c["rules"] for c in catalog["cases"]}

    report = {"model": args.label or args.model, "splits": {}}
    for split in ("eval_seen", "eval_unseen"):
        items = [json.loads(l) for l in (OUT / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()]
        if args.limit:
            items = items[:args.limit]
        results, exact, verdict_ok, toks = [], 0, 0, 0
        for item in items:
            try:
                reply, t = ask(args.base_url, args.model, item["system"], item["user"])
            except Exception as exc:  # noqa: BLE001
                results.append({"instance": item["instance_id"], "ok": False, "why": f"error: {exc}"})
                continue
            g = grade(item, reply, rules_by_case)
            toks += t
            exact += g["ok"]
            verdict_ok += g.get("verdict_ok", False)
            results.append({"instance": item["instance_id"], **{k: v for k, v in g.items() if k != "checks"},
                            "failed": [k for k, v in g.get("checks", {}).items() if not v]})
        n = len(items)
        report["splits"][split] = {"n": n, "exact": exact, "exact_pct": round(100 * exact / n, 1) if n else 0,
                                  "verdict_pct": round(100 * verdict_ok / n, 1) if n else 0,
                                  "avg_tokens": toks // n if n else 0, "results": results}
        print(f"[{report['model']}] {split}: exact {exact}/{n} ({report['splits'][split]['exact_pct']}%) · "
              f"verdict {report['splits'][split]['verdict_pct']}% · avg {report['splits'][split]['avg_tokens']} tok")
    history_path = OUT / "eval_history.json"
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else []
    history = [h for h in history if h["model"] != report["model"]]
    history.append(report)
    history_path.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
