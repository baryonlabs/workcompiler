#!/usr/bin/env python3
"""Decision-case factory: 30 organizational decisions from one declarative catalog.

The lecture claim this makes executable: *"조직에 필요한 것은 좋은 답 하나가 아니라, 좋은 판단이
반복될 수 있는 구조다."* A judgment call ("이 고객 몇 %까지 할인?") becomes an organizational asset
only when the policy, the meaning of the data, and the escalation path are explicit. So here:

* **온톨로지** — each case declares its entities, attributes and relations (`ontology:` block,
  emitted per case as `ontology.yaml`); "전략고객", "이탈위험", "본부장 승인 필요" are structure,
  not prompt text.
* **규칙** — explicit policy is data: ordered `when → outcome` rules in a tiny condition DSL
  (`field op value`, `and`-conjunctions). One generic engine evaluates every case; no per-case code.
* **AI 추천 + 사람 승인** — a rule may resolve to `defer: slm_recommend` (policy deliberately leaves
  a band open: the model recommends inside declared bounds) and any outcome may carry
  `route:` (who must approve). The engine labels these too, so the corpus trains and *gates*
  the recommender; approvals stay human by construction.
* **실행 / 결과 학습** — the decision record is the input of a `.work` execution flow, and every
  decided instance appends to the corpus (`cases.jsonl`) the same way the runtime cache does.

Deterministic: same catalog + seed → byte-identical corpus.
"""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

HERE = Path(__file__).parent
CATALOG = HERE / "catalog.yaml"

_COND_RE = re.compile(r"^\s*(\w+)(?:\s*([-+])\s*(\w+))?\s*(<=|>=|==|!=|<|>|in|not_in)\s*(.+?)\s*$")


def _value(token: str) -> Any:
    token = token.strip()
    if token.startswith("[") and token.endswith("]"):
        return [_value(t) for t in token[1:-1].split("|")]
    if token.lower() in ("true", "false"):
        return token.lower() == "true"
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        return token.strip("'\"")


def check(cond: str, record: Dict[str, Any]) -> bool:
    """`field op value [and field op value …]` against a flat record."""
    for part in cond.split(" and "):
        m = _COND_RE.match(part)
        if not m:
            raise ValueError(f"bad condition: {part!r}")
        field, arith, field2, op, raw = m.groups()
        left, right = record.get(field), _value(raw)
        if left is None:
            return False
        if arith:
            other = record.get(field2)
            if other is None:
                return False
            left = left - other if arith == "-" else left + other
        ok = {"<=": lambda: left <= right, ">=": lambda: left >= right, "<": lambda: left < right,
              ">": lambda: left > right, "==": lambda: left == right, "!=": lambda: left != right,
              "in": lambda: left in right, "not_in": lambda: left not in right}[op]()
        if not ok:
            return False
    return True


def decide(case: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
    """First matching rule wins (rules are ordered most-specific-first, like the policy document)."""
    for i, rule in enumerate(case["rules"]):
        if check(rule["when"], record):
            out = {k: v for k, v in rule.items() if k not in ("when",)}
            return {"case_id": case["id"], "verdict": out.get("verdict", "defer"),
                    "route": out.get("route", "auto"), "params": out.get("set", {}),
                    "defer_to": out.get("defer"), "cited_rule": rule.get("name", f"rule_{i + 1}"),
                    "cited_condition": rule["when"], "rationale": rule.get("why", "")}
    fallback = case.get("fallback", {"verdict": "escalate", "route": "human"})
    return {"case_id": case["id"], "verdict": fallback.get("verdict", "escalate"),
            "route": fallback.get("route", "human"), "params": {}, "defer_to": None,
            "cited_rule": "fallback", "cited_condition": "(no rule matched)",
            "rationale": "정책이 정하지 않은 상황 — 사람에게 에스컬레이션"}


def sample(case: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    record: Dict[str, Any] = {}
    for name, spec in case["features"].items():
        kind = spec["type"]
        if kind == "choice":
            record[name] = rng.choice(spec["values"])
        elif kind == "int":
            record[name] = rng.randint(spec["min"], spec["max"])
        elif kind == "float":
            record[name] = round(rng.uniform(spec["min"], spec["max"]), spec.get("round", 2))
        elif kind == "bool":
            record[name] = rng.random() < spec.get("p", 0.5)
        else:
            raise ValueError(f"unknown feature type {kind}")
    return record


def build_case(case: Dict[str, Any], out_root: Path, n: int, seed: int) -> Dict[str, Any]:
    rng = random.Random(f"{seed}:{case['id']}")
    out = out_root / case["id"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "ontology.yaml").write_text(yaml.safe_dump({"case": case["id"], "org": case["org"], "role": case["role"],
                                                       "decision": case["decision"], "ontology": case.get("ontology", {})},
                                                      allow_unicode=True, sort_keys=False), encoding="utf-8")
    (out / "policy.yaml").write_text(yaml.safe_dump({"case": case["id"], "rules": case["rules"],
                                                     "fallback": case.get("fallback")}, allow_unicode=True,
                                                    sort_keys=False), encoding="utf-8")
    counts: Dict[str, int] = {}
    routes: Dict[str, int] = {}
    with (out / "cases.jsonl").open("w", encoding="utf-8") as fh:
        for i in range(n):
            record = sample(case, rng)
            decision = decide(case, record)
            counts[decision["verdict"]] = counts.get(decision["verdict"], 0) + 1
            routes[decision["route"]] = routes.get(decision["route"], 0) + 1
            fh.write(json.dumps({"instance_id": f"{case['id']}-{i + 1:04d}", "record": record,
                                 "decision": decision}, ensure_ascii=False) + "\n")
    return {"id": case["id"], "org": case["org"], "role": case["role"], "decision": case["decision"],
            "instances": n, "verdicts": counts, "routes": routes,
            "rules": len(case["rules"]), "has_slm_band": any(r.get("defer") for r in case["rules"])}


def main(n: int = 100, seed: int = 20260831) -> Dict[str, Any]:
    catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    out_root = HERE / "corpus"
    stats = [build_case(case, out_root, n, seed) for case in catalog["cases"]]
    orgs: Dict[str, int] = {}
    for s in stats:
        orgs[s["org"]] = orgs.get(s["org"], 0) + 1
    index = {"cases": len(stats), "instances": sum(s["instances"] for s in stats), "orgs": orgs, "stats": stats}
    (out_root / "INDEX.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# 조직 결정 코퍼스 — 카탈로그 요약", "",
             f"{len(stats)}개 결정 사례 × {n} 인스턴스 = {index['instances']:,}건의 라벨된 판단 (규칙 스펙에서 결정론적으로 생성).", "",
             "| 사례 | 조직 | 담당자 | 결정 | 규칙 수 | AI 추천 밴드 | 판정 분포 | 승인 라우팅 |",
             "| :-- | :-- | :-- | :-- | --: | :-- | :-- | :-- |"]
    for s in stats:
        verdicts = ", ".join(f"{k} {v}" for k, v in sorted(s["verdicts"].items()))
        routes = ", ".join(f"{k} {v}" for k, v in sorted(s["routes"].items()))
        lines.append(f"| `{s['id']}` | {s['org']} | {s['role']} | {s['decision']} | {s['rules']} | "
                     f"{'예' if s['has_slm_band'] else '—'} | {verdicts} | {routes} |")
    (out_root / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return index


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    index = main(n)
    print(json.dumps({"cases": index["cases"], "instances": index["instances"], "orgs": index["orgs"]},
                     ensure_ascii=False))
