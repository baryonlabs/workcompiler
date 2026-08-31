#!/usr/bin/env python3
"""Gate-evaluate a decision model (any OpenAI-compatible endpoint) on the catalog eval splits.

Exact-match gate per instance: verdict, route, params and the cited rule must all equal the
engine's deterministic label — and, independently, the cited rule's condition must actually hold
on the record (no fabricated grounds; checked with the same DSL the engine uses).
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import engine  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "decision-slm"
_JSON_RE = re.compile(r"\{.*\}", re.S)
_BOOTSTRAP_ITERS = 10_000
_BOOTSTRAP_SEED = 20250831


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
    # relaxed match: the cited rule need not be the engine's first match, as long as its
    # condition actually holds on the record and everything else agrees with the label
    relaxed = all(v for k, v in checks.items() if k != "cited_rule")
    return {"ok": all(checks.values()), "verdict_ok": checks["verdict"], "relaxed_ok": relaxed,
            "checks": checks, "why": ""}


def _per_case(results: list[dict]) -> dict[str, tuple[int, int]]:
    """Exact-match tally per holdout case (policy cluster): {case_id: (exact, n)}."""
    out: dict[str, tuple[int, int]] = {}
    for r in results:
        case = r["instance"].rsplit("-", 1)[0]
        exact, n = out.get(case, (0, 0))
        out[case] = (exact + bool(r.get("ok")), n + 1)
    return out


def _relaxed(result: dict) -> bool:
    """Relaxed match from a stored per-instance result (works on pre-existing history rows too)."""
    if "relaxed_ok" in result:
        return bool(result["relaxed_ok"])
    failed = result.get("failed")
    return bool(result.get("ok")) or (failed is not None and set(failed) == {"cited_rule"})


def cluster_bootstrap_ci(per_case: dict[str, tuple[int, int]],
                         iters: int = _BOOTSTRAP_ITERS, seed: int = _BOOTSTRAP_SEED) -> tuple[float, float]:
    """95% CI for accuracy, resampling *cases* (policy clusters) with replacement — instances within
    a case share a policy, so instance-level bootstrap would understate the variance."""
    rng = random.Random(seed)
    cases = sorted(per_case)
    stats = []
    for _ in range(iters):
        exact = n = 0
        for _ in cases:
            e, m = per_case[cases[rng.randrange(len(cases))]]
            exact += e
            n += m
        stats.append(100 * exact / n if n else 0.0)
    stats.sort()
    return round(stats[int(0.025 * iters)], 1), round(stats[int(0.975 * iters) - 1], 1)


def _split_line(model: str, split: str, s: dict) -> str:
    ci = s.get("ci95")
    return (f"[{model}] {split}: exact {s['exact']}/{s['n']} ({s['exact_pct']}%)"
            + (f" · 95% CI [{ci[0]}, {ci[1]}]" if ci else "")
            + f" · verdict {s['verdict_pct']}% · relaxed {s['relaxed_pct']}% · avg {s['avg_tokens']} tok")


def render_report(history: list[dict]) -> str:
    """Markdown report over the whole history: latest run per model as the main table
    (mean±std alongside when a model has 2+ runs), plus the per-policy unseen scoreboard."""
    by_model: dict[str, list[dict]] = {}
    for run in history:
        by_model.setdefault(run["model"], []).append(run)

    def stats(run: dict, split: str) -> dict:
        s = dict(run["splits"][split])
        results = s.get("results", [])
        per_case = _per_case(results)
        s.setdefault("ci95", list(cluster_bootstrap_ci(per_case)) if per_case else None)
        if "relaxed_pct" not in s:
            relaxed = sum(_relaxed(r) for r in results)
            s["relaxed_pct"] = round(100 * relaxed / s["n"], 1) if s["n"] else 0
        s["per_case"] = per_case
        return s

    lines = ["# Decision-model eval report", "",
             f"Generated {time.strftime('%Y-%m-%dT%H:%M:%S')} from eval_history.json "
             f"({len(history)} run(s), {len(by_model)} model(s)).", "",
             "Gate = 4중 완전 일치(verdict·route·params·cited_rule) + 인용 규칙 조건이 레코드에 실제 성립.",
             "완화 일치 = 인용 규칙이 first-match가 아니어도 조건이 실제 성립하면 인정. "
             f"unseen 95% CI = 사례(정책) 클러스터 부트스트랩 ({_BOOTSTRAP_ITERS:,}회, seed {_BOOTSTRAP_SEED}).", "",
             "| 모델 | seen 정확 | unseen 정확 [95% CI] | unseen verdict | unseen 완화 | 실행 이력 |",
             "| :-- | --: | --: | --: | --: | :-- |"]
    latest_unseen: dict[str, dict] = {}
    for model, runs in by_model.items():
        seen, unseen = stats(runs[-1], "eval_seen"), stats(runs[-1], "eval_unseen")
        latest_unseen[model] = unseen
        hist = f"{len(runs)}회"
        if len(runs) >= 2:
            seen_pcts = [r["splits"]["eval_seen"]["exact_pct"] for r in runs]
            unseen_pcts = [r["splits"]["eval_unseen"]["exact_pct"] for r in runs]
            hist += (f" · seen {statistics.mean(seen_pcts):.1f}±{statistics.stdev(seen_pcts):.1f}%"
                     f" · unseen {statistics.mean(unseen_pcts):.1f}±{statistics.stdev(unseen_pcts):.1f}%")
        ci = unseen["ci95"]
        lines.append(f"| {model} | {seen['exact']}/{seen['n']} ({seen['exact_pct']}%) "
                     f"| {unseen['exact']}/{unseen['n']} ({unseen['exact_pct']}%) "
                     + (f"[{ci[0]}, {ci[1]}] " if ci else "")
                     + f"| {unseen['verdict_pct']}% | {unseen['relaxed_pct']}% | {hist} |")

    cases = sorted({c for s in latest_unseen.values() for c in s["per_case"]})
    if cases:
        models = list(latest_unseen)
        lines += ["", "## Unseen 정책별 성적표 (모델별 최신 실행, 정확 일치)", "",
                  "| 정책(사례) | " + " | ".join(models) + " |",
                  "| :-- |" + " --: |" * len(models)]
        for case in cases:
            row = [f"{latest_unseen[m]['per_case'][case][0]}/{latest_unseen[m]['per_case'][case][1]}"
                   if case in latest_unseen[m]["per_case"] else "—" for m in models]
            lines.append(f"| {case} | " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


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

    report = {"model": args.label or args.model, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "splits": {}}
    for split in ("eval_seen", "eval_unseen"):
        items = [json.loads(l) for l in (OUT / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()]
        if args.limit:
            items = items[:args.limit]
        results, exact, verdict_ok, relaxed_ok, toks = [], 0, 0, 0, 0
        for item in items:
            try:
                reply, t = ask(args.base_url, args.model, item["system"], item["user"])
            except Exception as exc:  # noqa: BLE001
                results.append({"instance": item["instance_id"], "ok": False, "relaxed_ok": False,
                                "why": f"error: {exc}"})
                continue
            g = grade(item, reply, rules_by_case)
            toks += t
            exact += g["ok"]
            verdict_ok += g.get("verdict_ok", False)
            relaxed_ok += g.get("relaxed_ok", False)
            results.append({"instance": item["instance_id"], **{k: v for k, v in g.items() if k != "checks"},
                            "failed": [k for k, v in g.get("checks", {}).items() if not v]})
        n = len(items)
        per_case = _per_case(results)
        report["splits"][split] = {"n": n, "exact": exact, "exact_pct": round(100 * exact / n, 1) if n else 0,
                                  "verdict_pct": round(100 * verdict_ok / n, 1) if n else 0,
                                  "relaxed_pct": round(100 * relaxed_ok / n, 1) if n else 0,
                                  "ci95": list(cluster_bootstrap_ci(per_case)) if per_case else None,
                                  "avg_tokens": toks // n if n else 0, "results": results}
        print(_split_line(report["model"], split, report["splits"][split]))
    history_path = OUT / "eval_history.json"
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else []
    # append-only: repeated runs of the same label accumulate, so run-to-run variance stays measurable
    history.append(report)
    history_path.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report_path = OUT / "eval_report.md"
    report_path.write_text(render_report(history), encoding="utf-8")
    print(f"history → {history_path} · report → {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
