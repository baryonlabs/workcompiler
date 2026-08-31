"""Organizational decision catalog: DSL, first-match policy, fallback, deterministic corpus."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("examples/org")))
import engine  # noqa: E402


def test_condition_dsl():
    r = {"a": 5, "b": 3, "grade": "C", "flag": True}
    assert engine.check("a > 4", r) and not engine.check("a > 5", r)
    assert engine.check("a - b < 3", r) and engine.check("a + b >= 8", r)
    assert engine.check("grade in [C|D]", r) and engine.check("grade not_in [A|B]", r)
    assert engine.check("flag == true", r) and engine.check("a > 4 and b <= 3", r)
    assert not engine.check("missing > 1", r)


def test_first_match_fallback_and_defer():
    case = {"id": "t", "rules": [
        {"name": "specific", "when": "x > 10 and y == hot", "verdict": "approve", "route": "auto"},
        {"name": "band", "when": "x > 10", "defer": "slm_recommend", "route": "lead", "set": {"cap": 5}},
    ], "fallback": {"verdict": "escalate", "route": "boss"}}
    d = engine.decide(case, {"x": 20, "y": "hot"})
    assert d["cited_rule"] == "specific" and d["verdict"] == "approve"
    d = engine.decide(case, {"x": 20, "y": "cold"})
    assert d["defer_to"] == "slm_recommend" and d["route"] == "lead" and d["params"] == {"cap": 5}
    d = engine.decide(case, {"x": 1, "y": "cold"})
    assert d["cited_rule"] == "fallback" and d["verdict"] == "escalate" and d["route"] == "boss"


def test_catalog_generates_deterministic_labeled_corpus(tmp_path):
    import yaml

    catalog = yaml.safe_load((Path("examples/org/catalog.yaml")).read_text(encoding="utf-8"))
    assert len(catalog["cases"]) >= 30
    ids = [c["id"] for c in catalog["cases"]]
    assert len(ids) == len(set(ids))
    for case in catalog["cases"]:
        assert case.get("ontology"), case["id"]              # 의미 구조 없는 결정은 카탈로그에 못 들어온다
        stats = engine.build_case(case, tmp_path, 40, seed=7)
        again = engine.build_case(case, tmp_path, 40, seed=7)
        assert stats == again                               # deterministic
        rows = [json.loads(l) for l in (tmp_path / case["id"] / "cases.jsonl").read_text().splitlines()]
        assert len(rows) == 40
        for row in rows:
            d = row["decision"]
            assert d["verdict"] and d["route"] and d["cited_rule"]
            if d["cited_rule"] not in ("fallback",):        # the cited condition must actually hold — no fabricated grounds
                assert engine.check(d["cited_condition"], row["record"]), (case["id"], d)


def test_flagship_discount_case_matches_the_lecture_example():
    import yaml

    catalog = yaml.safe_load(Path("examples/org/catalog.yaml").read_text(encoding="utf-8"))
    case = next(c for c in catalog["cases"] if c["id"] == "sales-discount-approval")
    strategic = {"segment": "strategic", "churn_risk": "high", "years_active": 4,
                 "requested_discount_pct": 12, "margin_pct": 30}
    d = engine.decide(case, strategic)
    assert d["verdict"] == "approve" and d["route"] == "본부장" and d["params"]["max_discount_pct"] == 12
    gray = dict(strategic, segment="mid", churn_risk="low", requested_discount_pct=8)
    d = engine.decide(case, gray)
    assert d["defer_to"] == "slm_recommend" and d["route"] == "팀장"       # AI 추천 + 사람 승인
    thin = dict(strategic, margin_pct=15, requested_discount_pct=8)
    assert engine.decide(case, thin)["verdict"] == "reject"               # 최소 마진 정책
