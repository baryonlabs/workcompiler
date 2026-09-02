"""Unique (incremental) token accounting of the benchmark.

An agent session re-sends its whole cumulative context every turn, so summing
per-request usage counts the same tokens once per turn. ``unique_step_tokens``
counts each token once: the first request's prompt, each later request's prompt
growth, plus every completion.
"""

import pytest

from core.build.bench import attach_unique_tokens, report_from_dict, unique_step_tokens
from core.work_ir import TraceIR


def _trace(steps):
    return TraceIR(run_id="run_test", source_agent="test", steps=steps,
                   result={"status": "success"})


def _step(step_id, usage=None, **extra):
    s = {"step_id": step_id, "actor": "agent", "action": "act", "input": {}, "output": {}}
    if usage is not None:
        s["token_usage"] = usage
    s.update(extra)
    return s


class TestUniqueStepTokens:
    def test_prompt_delta_counts_growth_plus_completions(self):
        trace = _trace([
            _step("s1", {"prompt_tokens": 1000, "completion_tokens": 50, "total_tokens": 1050}),
            _step("s2", {"prompt_tokens": 1200, "completion_tokens": 30, "total_tokens": 1230}),
            _step("s3", {"prompt_tokens": 1200, "completion_tokens": 10, "total_tokens": 1210}),
        ])
        uniq = unique_step_tokens(trace)
        assert uniq["s1"] == (1050, "prompt_delta")      # first prompt counts in full
        assert uniq["s2"] == (200 + 30, "prompt_delta")  # only the prompt growth
        assert uniq["s3"] == (0 + 10, "prompt_delta")    # unchanged prompt: completion only

    def test_prompt_reset_counts_uncached_part(self):
        # Context shrank (compaction / subagent): count the fresh prompt minus its cached part.
        trace = _trace([
            _step("s1", {"prompt_tokens": 5000, "completion_tokens": 10, "total_tokens": 5010}),
            _step("s2", {"prompt_tokens": 800, "completion_tokens": 20, "total_tokens": 820}, cached_tokens=600),
        ])
        uniq = unique_step_tokens(trace)
        assert uniq["s2"] == (200 + 20, "prompt_delta")

    def test_total_delta_fallback_without_split(self):
        trace = _trace([
            _step("s1", {"total_tokens": 900}),
            _step("s2", {"total_tokens": 1400}),
            _step("s3", {"total_tokens": 1300}),  # never negative
        ])
        uniq = unique_step_tokens(trace)
        assert uniq["s1"] == (900, "total_delta")
        assert uniq["s2"] == (500, "total_delta")
        assert uniq["s3"] == (0, "total_delta")

    def test_step_without_usage(self):
        trace = _trace([_step("s1")])
        assert unique_step_tokens(trace)["s1"] == (0, "")

    def test_matches_codex_demo_arithmetic(self):
        # The shape of the shipped codex trace: monotonic prompts, full split.
        prompts = [13938, 14686, 15130, 16630]
        completions = [93, 235, 215, 1001]
        steps = [_step(f"s{i}", {"prompt_tokens": p, "completion_tokens": c, "total_tokens": p + c})
                 for i, (p, c) in enumerate(zip(prompts, completions))]
        uniq = unique_step_tokens(_trace(steps))
        total_unique = sum(v[0] for v in uniq.values())
        assert total_unique == prompts[-1] + sum(completions)  # 16630 + 1544


class TestReportRecompute:
    BENCH = {
        "work": "w", "build_dir": "b", "run_id": "run_test", "source_agent": "test",
        "final_answer": "done",
        "actions": [
            {"action": "shell", "tier": "code", "steps": [
                {"step_id": "s1", "recorded_tokens": 1050, "recorded_latency_ms": 100.0,
                 "compiled_tokens": 0, "compiled_latency_ms": 1.0, "executor_used": "code",
                 "output_match": True, "recorded_output": "x", "compiled_output": "x"},
                {"step_id": "s2", "recorded_tokens": 1230, "recorded_latency_ms": 100.0,
                 "compiled_tokens": 0, "compiled_latency_ms": 1.0, "executor_used": "code",
                 "output_match": True, "recorded_output": "y", "compiled_output": "y",
                 "legacy_unknown_key": 1},
            ]},
            {"action": "respond", "tier": "slm", "steps": [
                {"step_id": "s3", "recorded_tokens": 1210, "recorded_latency_ms": 100.0,
                 "compiled_tokens": 400, "compiled_latency_ms": 50.0, "executor_used": "slm:m",
                 "output_match": True, "recorded_output": "z", "compiled_output": "z"},
            ]},
        ],
    }
    TRACE = _trace([
        _step("s1", {"prompt_tokens": 1000, "completion_tokens": 50, "total_tokens": 1050}),
        _step("s2", {"prompt_tokens": 1200, "completion_tokens": 30, "total_tokens": 1230}),
        _step("s3", {"prompt_tokens": 1200, "completion_tokens": 10, "total_tokens": 1210}),
    ])

    def _report(self):
        return attach_unique_tokens(report_from_dict(self.BENCH), self.TRACE)

    def test_totals_have_unique_columns(self):
        t = self._report().totals()
        assert t["recorded_tokens_unique"] == 1050 + 230 + 10  # 1290
        assert t["recorded_tokens"] == 3490
        assert t["compiled_tokens"] == 400
        assert t["savings_unique_pct"] == pytest.approx(round(100 * (1290 - 400) / 1290, 1))
        assert t["token_savings_pct"] == pytest.approx(round(100 * (3490 - 400) / 3490, 1))
        assert t["unique_token_basis"] == "prompt_delta"

    def test_markdown_leads_with_unique(self):
        md = self._report().to_markdown()
        unique_row = next(l for l in md.splitlines() if "LLM tokens (unique)" in l)
        reference_row = next(l for l in md.splitlines() if "cumulative-context sum" in l and l.startswith("|"))
        assert "1,290" in unique_row
        assert "3,490" in reference_row and "reference" in reference_row
        assert md.index(unique_row) < md.index(reference_row)

    def test_json_round_trip_carries_unique(self):
        data = self._report().to_dict()
        assert data["totals"]["recorded_tokens_unique"] == 1290
        assert data["actions"][0]["recorded_tokens_unique"] == 1280
        assert data["ledger"][0]["recorded_tokens_unique"] == 1050
        # a re-load of the new json keeps the columns without re-attaching
        assert report_from_dict(data).totals()["recorded_tokens_unique"] == 1290

    def test_total_delta_basis_is_flagged_in_markdown(self):
        trace = _trace([_step("s1", {"total_tokens": 900}), _step("s2", {"total_tokens": 1400}),
                        _step("s3", {"total_tokens": 1500})])
        report = attach_unique_tokens(report_from_dict(self.BENCH), trace)
        assert report.totals()["unique_token_basis"] == "total_delta"
        assert "estimated from `total_tokens` increments" in report.to_markdown()


# --------------------------------------------------------------------------- basis consistency

def test_run_totals_lead_with_the_unique_basis(tmp_path):
    """A run report must expose both bases explicitly: the unique one (what the org can claim)
    and the cumulative-context sum (what a per-request bill looks like). Reporting only the
    latter is what let a −85% headline stand next to a −2.3% reality."""
    from core.build.run import RunReport, RunStep

    r = RunReport(work="w", build_dir="b", request="", params={}, binding={})
    r.steps = [RunStep(step_id="s1", action="a", mode="code", tokens=100, latency_ms=10.0, ok=True, output="")]
    r.recorded_tokens = 1000          # per-request usage summed (context re-counted each turn)
    r.recorded_tokens_unique = 200    # each token counted once
    r.unique_basis = "prompt_delta"
    t = r.totals()
    assert t["savings_unique_pct"] == 50.0          # 200 → 100
    assert t["token_savings_pct"] == 90.0           # kept, but as the reference basis
    assert t["unique_token_basis"] == "prompt_delta"
    md = r.to_markdown()
    assert "token savings (unique)" in md and "cumulative-context sum; reference" in md


def test_org_status_totals_claim_only_unique_savings(tmp_path, monkeypatch):
    """`owc org status` aggregates published benchmark totals; the org-wide number it prints
    must be the unique-basis one, with the cumulative sum kept beside it as reference."""
    import json
    from core import org

    repo = tmp_path / "registry"
    (repo / "works" / "renewal").mkdir(parents=True)
    (repo / "ledger").mkdir()
    (repo / "ledger" / "renewal.jsonl").write_text(json.dumps({
        "work": "renewal", "by": "alice", "at": "2026-09-02T00:00:00",
        "totals": {"recorded_tokens": 1_000_000, "recorded_tokens_unique": 200_000,
                   "compiled_tokens": 50_000, "outputs_matched": 6, "outputs_checked": 6},
    }) + "\n", encoding="utf-8")
    monkeypatch.setattr(org, "registry_path", lambda create=False: repo)

    st = org.status()
    t = st["org_totals"]
    assert t["recorded_tokens_unique"] == 200_000
    assert t["savings_unique_pct"] == 75.0     # 200k → 50k, the claimable number
    assert t["token_savings_pct"] == 95.0      # 1M → 50k, reference only


# --------------------------------------------------------------------------- business inputs

def _report_with(steps, **kw):
    from core.build.bench import ActionBench, BenchReport, StepBench
    a = ActionBench(action="act", tier="llm", steps=[StepBench(**s) for s in steps])
    return BenchReport(work="w", build_dir="b", run_id="r", source_agent="codex", actions=[a], **kw)


BASE_STEP = dict(recorded_tokens=0, recorded_latency_ms=0.0, compiled_tokens=0, compiled_latency_ms=0.0,
                 executor_used="code:x", output_match=True, recorded_output="", compiled_output="")


def test_cost_prices_cache_reads_separately_and_names_unpriced_models():
    """A price table is supplied, never shipped. Cache reads bill at their own rate, so folding
    them into the input rate would overstate what compiling saved."""
    r = _report_with([{**BASE_STEP, "step_id": "s1", "recorded_model": "big", "compiled_model": "code",
                       "recorded_prompt_tokens": 1_000_000, "recorded_cached_tokens": 900_000,
                       "recorded_completion_tokens": 100_000, "compiled_tokens": 0},
                      {**BASE_STEP, "step_id": "s2", "recorded_model": "mystery", "compiled_model": "code"}])
    c = r.costs({"big": {"input": 3.0, "output": 15.0, "cache_read": 0.3}, "code": {"input": 0.0}})
    # 100k fresh input @3 + 900k cache @0.3 + 100k output @15 = 0.3 + 0.27 + 1.5
    assert c["recorded"] == 2.07 and c["compiled"] == 0.0 and c["saved"] == 2.07
    assert c["unpriced_models"] == ["mystery"]      # never silently priced at zero


def test_no_price_table_means_no_cost_figure():
    r = _report_with([{**BASE_STEP, "step_id": "s1", "recorded_model": "big", "compiled_model": "code"}])
    assert r.costs({}) is None and "cost" not in r.totals()


def test_time_window_and_person_minutes_appear_only_when_known():
    r = _report_with([{**BASE_STEP, "step_id": "s1", "recorded_at": "2026-09-02T10:00:00Z"},
                      {**BASE_STEP, "step_id": "s2", "recorded_at": "2026-09-02T10:04:00Z",
                       "compiled_latency_ms": 60_000.0}])
    t = r.totals()
    assert t["recorded_from"] == "2026-09-02T10:00:00Z" and t["recorded_to"] == "2026-09-02T10:04:00Z"
    assert "baseline_minutes" not in t              # undeclared: no invented human baseline

    r.baseline_minutes = 45.0
    t = r.totals()
    assert t["saved_minutes"] == 44.0               # 45 min baseline − 1 min compiled run
