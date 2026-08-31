"""SLM tier: local small-model inference, the grounded-fact gate, promotion/demotion, bench + run dispatch."""

import json
from pathlib import Path

import pytest

from core.build import slm
from core.build.emitter import emit_build
from core.work_ir import TraceIR, WorkIR

RECORDED = ("Renewal proposal completed.\n\n- Recommended seats: **270**\n- Annual price: **$116,640**\n"
            "- Discounts: **10% volume**, **0% loyalty**\n\nFiles:\n\n- [Pricing](build/renewal/pricing-CUST-1001.json)\n")
CONTEXT = ('{"customer_id": "CUST-1001", "seats": 240, "start_date": "2024-09-01"}\n'
           '{"recommended_committed_seats": 270, "volume_discount_pct": 10, "annual_total_usd": 116640.0}\n'
           "A build/renewal/pricing-CUST-1001.json (written)\n")


def _fake_transport(reply, usage=(1200, 80), model="fake-slm"):
    calls = []

    def transport(url, payload, timeout):
        calls.append({"url": url, "payload": payload})
        text = reply(payload) if callable(reply) else reply
        return {"model": model, "choices": [{"message": {"role": "assistant", "content": text}}],
                "usage": {"prompt_tokens": usage[0], "completion_tokens": usage[1]}}

    transport.calls = calls
    return transport


# --------------------------------------------------------------------------- facts + gate

def test_extract_facts_and_masking():
    facts = slm.extract_facts(RECORDED + " on 2024-09-01")
    assert {"270", "116640", "10"} <= facts["numbers"] and "2024" in facts["numbers"]
    assert facts["ids"] == {"CUST-1001"} and "build/renewal/pricing-CUST-1001.json" in facts["paths"]
    assert "2024-09-01" in facts["dates"]
    masked = slm.mask_facts(RECORDED)
    assert "270" not in masked and "CUST-1001" not in masked and "<value>" in masked
    assert "Recommended seats" in masked            # structure survives


def test_gate_rewards_grounded_recall_and_punishes_hallucination():
    good = RECORDED.replace("$116,640", "$116,640.00")          # same value, different formatting
    v = slm.gate(good, context=CONTEXT, recorded_output=RECORDED)
    assert v.passed and v.recall == 1.0 and v.precision == 1.0
    missing = "Renewal proposal completed.\n- Recommended seats: **270**\n"
    v = slm.gate(missing, context=CONTEXT, recorded_output=RECORDED)
    assert not v.passed and v.recall < 0.9 and "116640" in v.missing
    hallucinated = RECORDED + "\nAlso 12 support tickets and $99,999 credit."
    v = slm.gate(hallucinated, context=CONTEXT, recorded_output=RECORDED)
    assert not v.passed and v.checks["grounded"] is False and "99999" in v.ungrounded
    assert not slm.gate(RECORDED * 4, context=CONTEXT, recorded_output=RECORDED).checks["length"]
    # new-parameter runs: no recording → only grounding + the parameter values themselves are required
    v = slm.gate("Offer for CUST-1002: 60 seats, $17,100.", context='{"customer_id":"CUST-1002","seats":60,"annual":17100}',
                 params={"customer_id": "CUST-1002"})
    assert v.passed and v.recall == 1.0
    v = slm.gate("Offer ready.", context="{}", params={"customer_id": "CUST-1002"})
    assert not v.passed and v.missing == ["CUST-1002"]


def test_quality_record_feeds_the_optimizer_gate():
    from core.optimizer.optimizer import ExecutorOptimizer
    from core.validation.quality_record import evaluate_quality_fold

    ok = slm.quality_record("t:1", "respond", slm.SLMResult("x", 10, 5, 100.0, "m"),
                            slm.gate(RECORDED, context=CONTEXT, recorded_output=RECORDED), invariants=["verify_current_contract"])
    bad = slm.quality_record("t:2", "respond", slm.SLMResult("x", 10, 5, 100.0, "m"),
                             slm.gate("nothing here", context=CONTEXT, recorded_output=RECORDED))
    assert evaluate_quality_fold(ok) == "PASS" and evaluate_quality_fold(bad) == "FAIL"
    assert ok.behavior_verdicts["verify_current_contract"] == "na" and ok.behavior_verdicts["grounded_in_upstream_outputs"] == "true"
    assert ExecutorOptimizer().evaluate_promotion("respond", "slm", [ok], min_quality=0.9) is True
    assert ExecutorOptimizer().evaluate_promotion("respond", "slm", [ok, bad], min_quality=0.9) is False


# --------------------------------------------------------------------------- inference + prompt

def test_infer_measures_usage_and_reports_endpoint_errors(monkeypatch):
    rt = slm.SLMRuntime(model="fake", base_url="http://127.0.0.1:1/v1")
    res = slm.infer("sys", "user", rt, transport=_fake_transport("hello", usage=(321, 45)))
    assert res.output == "hello" and res.tokens == 366 and res.model == "fake-slm" and res.ok and res.latency_ms >= 0
    assert res.to_escalation_dict()["cost_usd"] == 0.0 and res.to_escalation_dict()["exit_code"] == 0
    down = slm.infer("sys", "user", rt)            # nothing listens on port 1
    assert not down.ok and "unreachable" in down.error and down.to_escalation_dict()["exit_code"] == 1
    monkeypatch.setenv(slm.ENV_MODEL, "env-model"); monkeypatch.setenv(slm.ENV_BASE_URL, "http://x/v1/")
    assert slm.SLMRuntime.defaults().model == "env-model" and slm.SLMRuntime.defaults().base_url == "http://x/v1"


def test_prompt_contains_masked_example_upstream_outputs_and_request(tmp_path):
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "respond.prompt.md").write_text("# respond\n\n## System prompt\n\nx\n\n## Invariants (must hold)\n\n- verify_current_contract\n- use_current_pricing_policy\n")
    system, user = slm.build_prompt(tmp_path, "respond", "renewal", {"customer_id": "CUST-1002"},
                                    [("shell_jq", '{"seats": 60}'), ("write_pricing", "A build/renewal/pricing-CUST-1002.json")],
                                    example_output=RECORDED, request="Prepare the renewal for CUST-1002")
    assert "verify_current_contract" in system and "<value>" in system
    assert user.index("## OUTPUTS") < user.index("## EXAMPLE")          # example last: small models keep it in focus
    assert "270" not in user and '"seats": 60' in user and "Prepare the renewal for CUST-1002" in user
    assert f"about {len(RECORDED.split())} words" in user


# --------------------------------------------------------------------------- build fixture

def _build(tmp_path, monkeypatch):
    """A compiled build whose final `respond` step is frontier-tier, with a real trace."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "contract.json").write_text(json.dumps({"customer_id": "CUST-1001", "seats": 240, "annual_total_usd": 116640.0}))
    trace = TraceIR.model_validate({
        "run_id": "run-1", "source_agent": "codex-cli", "result": {"status": "success", "outputs": {}},
        "steps": [
            {"step_id": "step_1", "actor": "agent", "action": "shell_cat",
             "input": {"cmd": "cat examples/contract.json"},
             "output": {"content": "", "tool_result": json.dumps({"customer_id": "CUST-1001", "seats": 240, "annual_total_usd": 116640.0})},
             "token_usage": {"prompt_tokens": 15000, "completion_tokens": 100, "total_tokens": 15100}, "latency_ms": 4000.0, "model": "gpt-x"},
            {"step_id": "step_2", "actor": "agent", "action": "respond",
             "input": {"content": "Prepare the renewal proposal for CUST-1001 and reply with a short summary."},
             "output": {"content": RECORDED, "tool_calls": [], "role": "assistant"},
             "token_usage": {"prompt_tokens": 20000, "completion_tokens": 120, "total_tokens": 20120}, "latency_ms": 11000.0, "model": "gpt-x"},
        ],
    })
    work_ir = WorkIR.model_validate({
        "work": "renewal", "version": "3.0", "inputs": ["customer_id"], "outputs": ["content"],
        "states": ["initialized", "cat_shelled", "respond_completed"], "actions": ["shell_cat", "respond"],
        "dependencies": {"respond": ["shell_cat"]}, "invariants": ["verify_current_contract"],
        "executors": {"shell_cat": {"type": "code"}, "respond": {"type": "frontier_llm", "preferred": "gpt-x", "fallback": ["human"]}},
    })
    manifest = emit_build(work_ir, tmp_path / "build", traces=[trace])
    return Path(manifest.build_dir), trace


def test_promote_flips_executor_when_gate_passes_and_demote_restores(tmp_path, monkeypatch):
    root, trace = _build(tmp_path, monkeypatch)
    rt = slm.SLMRuntime(model="fake-7b", base_url="http://fake/v1")
    good = _fake_transport(RECORDED.replace("$116,640", "$116,640.00"))

    dry = slm.promote(root, "respond", rt, dry_run=True, transport=good)
    assert dry.pass_rate == 1.0 and not dry.promoted and not slm.is_promoted(root, "respond")
    assert (root / "models/slm/respond/PROMOTION.md").exists()
    assert "gpt-x" in (root / "models/slm/respond/PROMOTION.md").read_text() and "fake-7b" in (root / "models/slm/respond/PROMOTION.md").read_text()

    rep = slm.promote(root, "respond", rt, transport=good)
    assert rep.promoted and slm.is_promoted(root, "respond")
    assert rep.totals()["slm_tokens"] == 1280 and rep.totals()["token_savings_pct"] > 90
    work = (root / "work.yaml").read_text()
    assert "type: slm" in work and "preferred: fake-7b" in work
    assert "    respond: slm," in (root / "renewal.work").read_text()
    manifest = json.loads((root / "MANIFEST.json").read_text())
    assert manifest["promotions"][0]["from"] == "frontier_llm" and manifest["promotions"][0]["to"] == "slm"
    runtime = slm.SLMRuntime.load(root, "respond")
    assert runtime.model == "fake-7b" and runtime.base_url == "http://fake/v1"
    assert (root / "models/slm/respond/quality_records.jsonl").read_text().count("\n") == 2   # dry run + real

    # the masked example must not leak the answer: the prompt the SLM saw had no recorded values
    user_prompt = good.calls[-1]["payload"]["messages"][1]["content"]
    assert "270" not in user_prompt.split("## EXAMPLE")[1] and "<value>" in user_prompt

    info = slm.demote(root, "respond")
    assert info["restored"]["type"] == "frontier_llm" and not slm.is_promoted(root, "respond")
    assert "type: frontier_llm" in (root / "work.yaml").read_text() and "    respond: llm," in (root / "renewal.work").read_text()


def test_promote_refuses_when_the_gate_fails(tmp_path, monkeypatch):
    root, _ = _build(tmp_path, monkeypatch)
    bad = _fake_transport("Renewal proposal completed. Recommended seats: <value>. Annual price: $99,999.")
    rep = slm.promote(root, "respond", slm.SLMRuntime(model="fake-3b"), transport=bad)
    assert not rep.promoted and rep.pass_rate == 0.0 and not slm.is_promoted(root, "respond")
    assert "type: frontier_llm" in (root / "work.yaml").read_text()
    md = (root / "models/slm/respond/PROMOTION.md").read_text()
    assert "NOT promoted" in md and "ungrounded 99999" in md


def test_bench_and_run_execute_promoted_slm_steps(tmp_path, monkeypatch):
    from core.build.bench import run_benchmark
    from core.build.run import run_build

    root, trace = _build(tmp_path, monkeypatch)
    rt = slm.SLMRuntime(model="fake-7b", base_url="http://fake/v1")
    good = _fake_transport(RECORDED, usage=(900, 60))
    slm.promote(root, "respond", rt, transport=good)

    # bench: the SLM really runs (fake endpoint), its tokens replace the frontier cost, the gate is the match
    monkeypatch.setattr(slm, "_http_post_json", good)
    report = run_benchmark(root, trace)
    respond = next(a for a in report.actions if a.action == "respond")
    step = respond.steps[0]
    assert step.executor_used == "slm:fake-7b" and step.compiled_tokens == 960 and step.output_match is True and step.quality == 1.0
    t = report.totals()
    assert t["compiled_tokens"] == 960 and t["slm_actions"] == 1 and t["escalated_actions"] == 0
    assert report.by_model()["fake-7b"] == (0, 960) and report.by_model()["gpt-x"][1] == 0
    md = report.to_markdown()
    assert "## SLM tier" in md and "20,120 → 960" in md
    payload = good.calls[-1]["payload"]
    assert '"seats": 240' in payload["messages"][1]["content"]        # replayed upstream output fed to the SLM

    # run: new parameters → SLM answers with $0 before any agent is consulted
    report2 = run_build(root, request="Prepare the renewal proposal for CUST-1001", out_dir=tmp_path / "runs")
    modes = [s.mode for s in report2.steps]
    assert modes == ["code", "slm:fake-7b"] and report2.steps[1].tokens == 960 and report2.steps[1].cost_usd == 0.0
    assert report2.totals()["slm_steps"] == 1 and report2.totals()["needs_agent_steps"] == 0

    # run: gate failure falls back to the escalation backend when one is given, else is reported as failed
    monkeypatch.setattr(slm, "_http_post_json", _fake_transport("Done. Seats: <value>."))
    seen = {}

    def agent(prompt, ctx):
        seen["prompt"] = prompt
        return {"output": "agent wrote it", "tokens": 5000, "latency_ms": 900.0, "exit_code": 0, "model": "agent-x"}

    report3 = run_build(root, request="Prepare the renewal proposal for CUST-1001", escalate="codex", escalator=agent, out_dir=tmp_path / "runs3")
    assert report3.steps[1].mode == "escalated:codex" and "slm gate failed" in report3.steps[1].note and seen["prompt"]
    # the successful escalation of report3 was cached: the same request now replays at 0 tokens
    report4 = run_build(root, request="Prepare the renewal proposal for CUST-1001", out_dir=tmp_path / "runs4")
    assert report4.steps[1].mode == "cache" and report4.steps[1].tokens == 0 and report4.steps[1].ok
    # a different request misses the cache; with the SLM failing and no backend, the failure is recorded
    report5 = run_build(root, request="Summarize the renewal status instead", out_dir=tmp_path / "runs5")
    assert report5.steps[1].mode == "slm:fake-7b" and report5.steps[1].ok is False


def test_loader_registers_inference_handler_for_promoted_actions(tmp_path, monkeypatch):
    from core.build.loader import load_build_into_engine
    from core.runtime.engine import DurableRuntimeEngine

    root, _ = _build(tmp_path, monkeypatch)
    slm.promote(root, "respond", slm.SLMRuntime(model="fake-7b"), transport=_fake_transport(RECORDED))
    monkeypatch.setattr(slm, "_http_post_json", _fake_transport("from the engine", usage=(50, 5)))
    engine = DurableRuntimeEngine(auto_checkpoint=False)
    summary = load_build_into_engine(engine, root)
    assert summary["slm"] == ["respond"]
    result = engine.get_executor("slm").execute("respond", {"content": "hi", "preferred": "fake-7b"})
    assert result.success and result.output["text"] == "from the engine"


def test_cli_promote_dry_run_and_demote(tmp_path, monkeypatch, capsys):
    from core.build.__main__ import main

    root, _ = _build(tmp_path, monkeypatch)
    monkeypatch.setattr(slm, "_http_post_json", _fake_transport(RECORDED))
    assert main(["promote", str(root), "respond", "--model", "fake-7b", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "would promote (dry run)" in out and "pass rate 100%" in out
    assert main(["promote", str(root), "respond", "--model", "fake-7b"]) == 0
    assert "PROMOTED" in capsys.readouterr().out and slm.is_promoted(root, "respond")
    assert main(["demote", str(root), "respond"]) == 0
    assert "restored to frontier_llm" in capsys.readouterr().out
    monkeypatch.setattr(slm, "_http_post_json", _fake_transport("Seats: <value>"))
    assert main(["promote", str(root), "respond", "--model", "fake-3b"]) == 1


# --------------------------------------------------------------------------- file mode (derivation steps)

PATCH = """*** Begin Patch
*** Add File: out/pricing-CUST-1001.json
+{
+  "customer_id": "CUST-1001",
+  "seats": 270,
+  "list_price": 40.0,
+  "gross_monthly_usd": 10800.0,
+  "discounts": {"volume_band_min_seats": 200, "volume_discount_pct": 10, "monthly_discount_usd": 1080.0},
+  "monthly_total_usd": 9720.0,
+  "annual_total_usd": 116640.0
+}
*** Add File: out/proposal-CUST-1001.md
+# Proposal CUST-1001
+Seats 270 at $40.00 -> $10,800.00/mo, 10% volume discount -> $9,720.00/mo, $116,640.00/yr.
*** End Patch"""
FILE_CTX = ("contract: CUST-1002 professional seats 60 price 25.0\n"
            "volume_discount_bands:\n  - min_seats: 50\n    pct: 5\n  - min_seats: 200\n    pct: 10\n"
            "list_price_per_seat_month: {professional: 25.0, enterprise: 40.0}\ncontract CUST-1001 seats 240 enterprise 40.0 seats peak 270\n")

GOOD_1002 = """===FILE out/pricing-CUST-1002.json===
{
  "customer_id": "CUST-1002",
  "seats": 60,
  "list_price": 25.0,
  "gross_monthly_usd": 1500.0,
  "discounts": {"volume_band_min_seats": 50, "volume_discount_pct": 5, "monthly_discount_usd": 75.0},
  "monthly_total_usd": 1425.0,
  "annual_total_usd": 17100.0
}
===END===
===FILE out/proposal-CUST-1002.md===
# Proposal CUST-1002
Seats 60 at $25.00 -> $1,500.00/mo, 5% volume discount -> $1,425.00/mo, $17,100.00/yr.
===END==="""


def test_file_gate_passes_a_correct_derivation_and_catches_the_wrong_band():
    files = slm.parse_file_blocks(GOOD_1002)
    assert set(files) == {"out/pricing-CUST-1002.json", "out/proposal-CUST-1002.md"}
    v = slm.gate_files(files, recorded_patch=PATCH, context=FILE_CTX, params={"customer_id": "CUST-1002"},
                       recorded_params={"customer_id": "CUST-1001"})
    assert v.passed, v.summary()
    # wrong discount band: 10% at the 50-seat band — arithmetically self-consistent, caught by pair grounding
    wrong = GOOD_1002.replace('"volume_discount_pct": 5', '"volume_discount_pct": 10') \
                     .replace('"monthly_discount_usd": 75.0', '"monthly_discount_usd": 150.0') \
                     .replace('"monthly_total_usd": 1425.0', '"monthly_total_usd": 1350.0') \
                     .replace('"annual_total_usd": 17100.0', '"annual_total_usd": 16200.0') \
                     .replace("5% volume discount -> $1,425.00/mo, $17,100.00/yr", "10% volume discount -> $1,350.00/mo, $16,200.00/yr")
    v = slm.gate_files(slm.parse_file_blocks(wrong), recorded_patch=PATCH, context=FILE_CTX,
                       params={"customer_id": "CUST-1002"}, recorded_params={"customer_id": "CUST-1001"})
    assert not v.passed and v.checks["json_pairs_grounded"] is False
    # broken arithmetic (annual != monthly*12) is caught by the mined relations
    bad_math = GOOD_1002.replace('"annual_total_usd": 17100.0', '"annual_total_usd": 17000.0').replace("$17,100.00/yr", "$17,000.00/yr")
    v = slm.gate_files(slm.parse_file_blocks(bad_math), recorded_patch=PATCH, context=FILE_CTX,
                       params={"customer_id": "CUST-1002"}, recorded_params={"customer_id": "CUST-1001"})
    assert not v.passed and v.checks["json_relations"] is False
    # a missing file fails the set check
    only_json = GOOD_1002.split("===FILE out/proposal")[0]
    v = slm.gate_files(slm.parse_file_blocks(only_json), recorded_patch=PATCH, context=FILE_CTX,
                       params={"customer_id": "CUST-1002"}, recorded_params={"customer_id": "CUST-1001"})
    assert not v.passed and v.checks["file_set"] is False
    # exact mode: the recording reproduces itself
    from core.work_ir import patchfmt
    rec = {b.path: patchfmt.add_content(b) for b in patchfmt.parse_patch(PATCH) if b.op == "Add"}
    v = slm.gate_files(rec, recorded_patch=PATCH, context=FILE_CTX, params={"customer_id": "CUST-1001"},
                       recorded_params={"customer_id": "CUST-1001"}, exact=True)
    assert v.passed, v.summary()


def test_mine_relations_finds_the_recorded_arithmetic():
    import json as _json
    flat = slm._json_flat(_json.loads(slm.parse_file_blocks(GOOD_1002)["out/pricing-CUST-1002.json"]))
    rels = slm.mine_relations(flat)
    ops = {(op, c.split(".")[-1]) for op, a, b, c in rels}
    assert ("x12", "annual_total_usd") in ops          # monthly*12 = annual


def _write_build(tmp_path, monkeypatch):
    """Build whose synthesized write step carries a recorded patch (agent-computed values)."""
    monkeypatch.chdir(tmp_path)
    trace = TraceIR.model_validate({
        "run_id": "run-2", "source_agent": "codex-cli", "result": {"status": "success", "outputs": {}},
        "steps": [
            {"step_id": "step_1", "actor": "agent", "action": "shell_cat", "input": {"cmd": "cat ctx.txt # renewal inputs for CUST-1001"},
             "output": {"content": "", "tool_result": FILE_CTX.replace("CUST-1002", "CUST-1001")},
             "token_usage": {"prompt_tokens": 9000, "completion_tokens": 50, "total_tokens": 9050}, "latency_ms": 3000.0, "model": "gpt-x"},
            {"step_id": "step_2", "actor": "agent", "action": "write_pricing", "input": {"cmd": "apply_patch", "patch": PATCH},
             "output": {"content": "written", "tool_calls": [{"id": "c1", "name": "exec", "result": "Done"}], "tool_result": "Done"},
             "token_usage": {"prompt_tokens": 19000, "completion_tokens": 400, "total_tokens": 19400}, "latency_ms": 22000.0, "model": "gpt-x"},
        ],
    })
    (tmp_path / "ctx.txt").write_text(FILE_CTX.replace("CUST-1002", "CUST-1001"))
    work_ir = WorkIR.model_validate({
        "work": "pricing", "version": "3.0", "inputs": ["customer_id"], "outputs": ["files"],
        "states": ["initialized", "cat_shelled", "write_pricing_completed"], "actions": ["shell_cat", "write_pricing"],
        "dependencies": {"write_pricing": ["shell_cat"]},
        "executors": {"shell_cat": {"type": "code"}, "write_pricing": {"type": "code"}},
    })
    manifest = emit_build(work_ir, tmp_path / "build", traces=[trace])
    return Path(manifest.build_dir), trace


def test_run_uses_slm_for_promoted_synthesized_write_step(tmp_path, monkeypatch):
    from core.build.run import run_build

    root, _ = _write_build(tmp_path, monkeypatch)
    assert "write_pricing" in json.loads((root / "PARAMS.json").read_text())["synthesized_actions"]
    # promote via exact reproduction of the recorded files
    reply = PATCH.replace("*** Begin Patch\n", "").replace("*** End Patch", "")
    exact_reply = "\n".join(  # rebuild ===FILE blocks from the patch content
        f"===FILE {b.path}===\n{__import__('core.work_ir.patchfmt', fromlist=['x']).add_content(b)}===END==="
        for b in __import__('core.work_ir.patchfmt', fromlist=['x']).parse_patch(PATCH) if b.op == "Add")
    rep = slm.promote(root, "write_pricing", slm.SLMRuntime(model="fake-14b"), transport=_fake_transport(exact_reply, usage=(2000, 600)))
    assert rep.promoted and slm.is_promoted(root, "write_pricing")
    assert "type: code" in (root / "work.yaml").read_text()            # code tier untouched; runtime.json is the front-agent hint
    assert "write_pricing: slm_then_agent," in (root / "pricing.work").read_text()

    # new params: the SLM regenerates the files, the gate passes, files land on disk, cost 0
    monkeypatch.setattr(slm, "_http_post_json", _fake_transport(GOOD_1002, usage=(2100, 650)))
    report = run_build(root, params={"customer_id": "CUST-1002"}, out_dir=tmp_path / "runs")
    step = report.steps[1]
    assert step.mode == "slm:fake-14b" and step.tokens == 2750 and step.cost_usd == 0.0 and step.ok
    assert json.loads((tmp_path / "out" / "pricing-CUST-1002.json").read_text())["annual_total_usd"] == 17100.0
    assert (tmp_path / "out" / "proposal-CUST-1002.md").exists()
    assert report.totals()["slm_steps"] == 1 and report.totals()["escalated_steps"] == 0

    # the successful SLM result was cached: the same parameters replay at 0 tokens
    report = run_build(root, params={"customer_id": "CUST-1002"}, out_dir=tmp_path / "runs_cache")
    assert report.steps[1].mode == "cache" and report.steps[1].tokens == 0

    # wrong band (fresh params → no cache) → gate fails → falls back to the agent backend
    wrong = GOOD_1002.replace('"volume_discount_pct": 5', '"volume_discount_pct": 10').replace('"monthly_discount_usd": 75.0', '"monthly_discount_usd": 150.0')
    monkeypatch.setattr(slm, "_http_post_json", _fake_transport(wrong))
    agent_called = {}

    def agent(prompt, ctx):
        agent_called["yes"] = True
        return {"output": "agent wrote it", "tokens": 8000, "latency_ms": 1500.0, "exit_code": 0, "model": "agent-x"}

    report = run_build(root, params={"customer_id": "CUST-1003"}, escalate="codex", escalator=agent, out_dir=tmp_path / "runs2")
    assert report.steps[1].mode == "escalated:codex" and "slm file gate failed" in report.steps[1].note and agent_called["yes"]


def test_promote_write_step_refuses_wrong_values(tmp_path, monkeypatch):
    root, _ = _write_build(tmp_path, monkeypatch)
    wrong = GOOD_1002        # CUST-1002 values offered for the CUST-1001 evaluation → exact match fails
    rep = slm.promote(root, "write_pricing", slm.SLMRuntime(model="fake-7b"), transport=_fake_transport(wrong))
    assert not rep.promoted and not slm.is_promoted(root, "write_pricing")
