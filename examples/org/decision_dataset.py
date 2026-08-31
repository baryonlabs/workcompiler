#!/usr/bin/env python3
"""Decision-SLM dataset from the organizational catalog corpus.

Regime: **policy-in-context**. The model is given the case's ontology and its ordered rules and must
apply them to one instance record (first match wins, fallback otherwise), answering with a single
JSON decision. This trains *policy application*, not policy memorization — so a rule change in
`catalog.yaml` changes the behavior without retraining, and the hard evaluation can hold out six
whole cases (policies never seen in training).

Splits (deterministic):
* train  — 28 cases × instances 1..40
* valid  — 28 cases × instances 41..45
* eval_seen   — the same 28 cases × instances 91..92  (unseen instances, seen policies)
* eval_unseen — 6 held-out cases × instances 1..10    (unseen policies)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).parent
CORPUS = HERE / "corpus"
OUT = HERE / "decision-slm"

HOLDOUT_CASES = ["finance-budget-overrun", "cs-goodwill-coupon", "hr-overtime-approval",
                 "proc-price-increase", "log-return-disposition", "sec-sharing-exception"]

SYSTEM = ("당신은 {org} 조직의 {role}입니다. 결정: {decision}.\n"
          "아래 정책 규칙을 위에서부터 순서대로 검사해 첫 번째로 조건이 성립하는 규칙 하나를 적용하십시오. "
          "어떤 규칙도 성립하지 않으면 fallback을 적용하십시오. 값을 지어내지 말고, 이번 건의 레코드에 "
          "실제로 성립하는 조건만 인용하십시오.\n"
          "출력은 JSON 객체 하나만 (다른 텍스트 금지): "
          '{{"verdict": "...", "route": "...", "params": {{...}}, "cited_rule": "...", "rationale": "근거 한 문장"}}')


def _case_spec(case_id: str) -> dict:
    catalog = yaml.safe_load((HERE / "catalog.yaml").read_text(encoding="utf-8"))
    return next(c for c in catalog["cases"] if c["id"] == case_id)


def prompt_for(case: dict, record: dict) -> tuple[str, str]:
    system = SYSTEM.format(org=case["org"], role=case["role"], decision=case["decision"])
    policy = yaml.safe_dump({"rules": case["rules"], "fallback": case.get("fallback")},
                            allow_unicode=True, sort_keys=False)
    ontology = yaml.safe_dump(case.get("ontology", {}), allow_unicode=True, sort_keys=False)
    user = (f"## 온톨로지 (이 결정의 의미 구조)\n{ontology}\n## 정책 (순서대로 첫 일치 적용)\n{policy}\n"
            f"## 이번 건의 레코드\n```json\n{json.dumps(record, ensure_ascii=False)}\n```\n\n결정하십시오.")
    return system, user


def target_for(decision: dict) -> str:
    return json.dumps({"verdict": decision["verdict"], "route": decision["route"],
                       "params": decision.get("params", {}), "cited_rule": decision["cited_rule"],
                       "rationale": decision.get("rationale", "")}, ensure_ascii=False)


def main(holdout: list[str] | None = None, out: Path | None = None) -> dict:
    holdout = holdout or HOLDOUT_CASES
    out = out or OUT
    out.mkdir(parents=True, exist_ok=True)
    catalog = yaml.safe_load((HERE / "catalog.yaml").read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in catalog["cases"]}
    unknown = set(holdout) - set(cases)
    if unknown:
        raise SystemExit(f"unknown holdout case ids: {sorted(unknown)}")
    rows = {"train": [], "valid": [], "eval_seen": [], "eval_unseen": []}
    for case_id, case in cases.items():
        lines = [json.loads(l) for l in (CORPUS / case_id / "cases.jsonl").read_text(encoding="utf-8").splitlines()]
        held = case_id in holdout
        for i, row in enumerate(lines, start=1):
            system, user = prompt_for(case, row["record"])
            item = {"case_id": case_id, "instance_id": row["instance_id"], "system": system, "user": user,
                    "truth": json.loads(target_for(row["decision"]))}
            if held:
                if i <= 10:
                    rows["eval_unseen"].append(item)
                continue
            if i <= 40:
                rows["train"].append({"messages": [{"role": "system", "content": system},
                                                   {"role": "user", "content": user},
                                                   {"role": "assistant", "content": target_for(row["decision"])}]})
            elif i <= 45:
                rows["valid"].append({"messages": [{"role": "system", "content": system},
                                                   {"role": "user", "content": user},
                                                   {"role": "assistant", "content": target_for(row["decision"])}]})
            elif i in (91, 92):
                rows["eval_seen"].append(item)
    (out / "data").mkdir(exist_ok=True)
    for name in ("train", "valid"):
        (out / "data" / f"{name}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows[name]), encoding="utf-8")
    for name in ("eval_seen", "eval_unseen"):
        (out / f"{name}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows[name]), encoding="utf-8")
    stats = {k: len(v) for k, v in rows.items()}
    (out / "MANIFEST.json").write_text(json.dumps({"holdout_cases": holdout, **stats}, indent=2,
                                                  ensure_ascii=False) + "\n", encoding="utf-8")
    return stats


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", default=None, help="comma-separated case ids to hold out (default: the pinned 6)")
    ap.add_argument("--out", default=None, help="output directory (default: examples/org/decision-slm)")
    args = ap.parse_args()
    print(json.dumps(main(holdout=args.holdout.split(",") if args.holdout else None,
                          out=Path(args.out) if args.out else None), ensure_ascii=False))
