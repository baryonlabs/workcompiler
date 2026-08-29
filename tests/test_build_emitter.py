"""Tests for the build backend: artifact tree emission and runtime loading."""

import json
from pathlib import Path

import yaml

from core.build import emit_build, load_build_into_engine
from core.openworklang import OpenWorkLangCompiler, parse_openworklang
from core.runtime.engine import DurableRuntimeEngine
from core.work_ir import TraceIR

WORK_FILE = Path(__file__).resolve().parents[1] / "examples" / "quality_analysis.work"


def _quality_work_ir():
    compiler = OpenWorkLangCompiler()
    ast = parse_openworklang(WORK_FILE)
    return compiler.compile_ast_to_work_ir(ast), compiler.compile_to_linkml_yaml(ast)


def test_emit_build_creates_one_artifact_family_per_tier(tmp_path):
    work_ir, linkml = _quality_work_ir()
    manifest = emit_build(work_ir, tmp_path, linkml_yaml=linkml)
    root = Path(manifest.build_dir)

    assert root == tmp_path / "quality_analyst"
    assert (root / "work.yaml").exists()
    assert (root / "MANIFEST.json").exists()
    assert (root / "schema" / "quality_analyst.linkml.yaml").exists()

    tiers = manifest.by_tier()
    assert "handlers/collect_data.py" in tiers["code"]
    assert "rules/detect_anomaly.rule.yaml" in tiers["rule"]
    assert "models/ml/find_correlation/model_card.yaml" in tiers["ml"]
    assert "models/slm/determine_root_cause/training_candidate.yaml" in tiers["slm"]
    assert "models/slm/create_report/train.py" in tiers["slm"]

    manifest_json = json.loads((root / "MANIFEST.json").read_text())
    assert manifest_json["work"] == "quality_analyst"
    assert manifest_json["artifact_count"] == len(manifest.artifacts)

    rule = yaml.safe_load((root / "rules" / "detect_anomaly.rule.yaml").read_text())
    assert rule["rules"][0]["when"][0]["op"] == "exists"
    card = yaml.safe_load((root / "models" / "ml" / "find_correlation" / "model_card.yaml").read_text())
    assert card["dataset"]["num_samples"] == 0  # no traces yet


def test_emit_build_from_trace_fills_datasets_and_shell_handlers(tmp_path):
    trace = TraceIR.model_validate({
        "run_id": "r1",
        "source_agent": "codex-tui",
        "steps": [
            {"step_id": "s1", "actor": "agent", "action": "shell_ls",
             "input": {"cmd": "ls examples", "content": "list files"}, "output": {"content": "demo\n"}},
            {"step_id": "s2", "actor": "agent", "action": "price_offer",
             "input": {"usage": 120}, "output": {"discount": 0.1}},
            {"step_id": "s3", "actor": "agent", "action": "draft_proposal",
             "input": {"content": "draft"}, "output": {"content": "Dear customer ..."}},
        ],
        "result": {"status": "success", "outputs": {}},
    })
    from core.work_ir import WorkIR
    work_ir = WorkIR.model_validate({
        "work": "renewal-bot", "version": "3.0",
        "inputs": ["cmd"], "outputs": ["content"],
        "states": ["initialized", "ls_shelled", "price_offer_completed", "draft_proposal_completed"],
        "actions": ["shell_ls", "price_offer", "draft_proposal"],
        "dependencies": {"price_offer": ["shell_ls"], "draft_proposal": ["price_offer"]},
        "invariants": ["verify_current_contract"],
        "executors": {
            "shell_ls": {"type": "code", "handler": "handlers.shell_ls"},
            "price_offer": {"type": "ml"},
            "draft_proposal": {"type": "slm", "preferred": "models/renewal-draft-slm-v1"},
        },
    })
    manifest = emit_build(work_ir, tmp_path, traces=[trace])
    root = Path(manifest.build_dir)

    handler = (root / "handlers" / "shell_ls.py").read_text()
    assert "COMMANDS = ['ls examples']" in handler and "subprocess.run" in handler

    ml_rows = [json.loads(l) for l in (root / "models/ml/price_offer/dataset.jsonl").read_text().splitlines()]
    assert ml_rows == [{"features": {"usage": 120}, "label": {"discount": 0.1}}]

    slm_rows = [json.loads(l) for l in (root / "models/slm/draft_proposal/dataset.jsonl").read_text().splitlines()]
    assert slm_rows[0]["completion"] == json.dumps({"content": "Dear customer ..."}, ensure_ascii=False)
    cand = yaml.safe_load((root / "models/slm/draft_proposal/training_candidate.yaml").read_text())
    assert cand["behavior_invariants"] == ["verify_current_contract"]
    assert cand["dataset"]["num_samples"] == 1


def test_load_build_into_engine_registers_handlers_and_rules(tmp_path):
    work_ir, _ = _quality_work_ir()
    manifest = emit_build(work_ir, tmp_path)
    root = Path(manifest.build_dir)
    # Give the code scaffold a real body so the engine can run it.
    (root / "handlers" / "collect_data.py").write_text(
        "def run(**inputs):\n    return {'rows': 3, 'source': inputs.get('production_data')}\n"
    )

    engine = DurableRuntimeEngine(storage_dir=tmp_path / "ckpt")
    summary = load_build_into_engine(engine, root)
    assert summary["handlers"] == ["collect_data"]
    assert summary["rules"] == ["detect_anomaly"]
    assert summary["work_ir"]["work"] == "quality_analyst"

    code_result = engine.get_executor("code").execute("collect_data", {"production_data": "mes://line-1"})
    assert code_result.success and code_result.output == {"rows": 3, "source": "mes://line-1"}

    rule_result = engine.get_executor("rule").execute("detect_anomaly", {"production_data": "x"})
    assert rule_result.success and rule_result.metadata["matched_rules"][0]["name"] == "detect_anomaly_default"


def test_benchmark_replays_code_tier_with_zero_tokens_and_matching_output(tmp_path):
    from core.build.bench import run_benchmark, write_report
    from core.work_ir import WorkIR

    trace = TraceIR.model_validate({
        "run_id": "bench-run", "source_agent": "codex-tui",
        "steps": [
            {"step_id": "s1", "actor": "agent", "action": "shell_printf", "latency_ms": 2500.0,
             "token_usage": {"prompt_tokens": 900, "completion_tokens": 40, "total_tokens": 940},
             "input": {"cmd": "printf 'alpha\\nbeta\\n'", "content": "show"},
             "output": {"content": None, "tool_calls": [{"id": "c1", "name": "exec", "result": "alpha\nbeta\n"}],
                        "tool_result": "alpha\nbeta\n"}},
            {"step_id": "s2", "actor": "agent", "action": "respond", "latency_ms": 1800.0,
             "token_usage": {"prompt_tokens": 1000, "completion_tokens": 60, "total_tokens": 1060},
             "input": {"content": "show"}, "output": {"content": "alpha and beta", "tool_calls": []}},
        ],
        "result": {"status": "success", "outputs": {}},
    })
    work_ir = WorkIR.model_validate({
        "work": "bench-work", "version": "3.0", "inputs": ["cmd"], "outputs": ["content"],
        "states": ["initialized", "printf_shelled", "respond_completed"],
        "actions": ["shell_printf", "respond"], "dependencies": {"respond": ["shell_printf"]},
        "executors": {"shell_printf": {"type": "code"}, "respond": {"type": "frontier_llm"}},
    })
    manifest = emit_build(work_ir, tmp_path, traces=[trace])
    report = run_benchmark(manifest.build_dir, trace)

    totals = report.totals()
    assert totals["recorded_tokens"] == 2000
    assert totals["compiled_tokens"] == 1060           # only the escalated respond step still costs tokens
    assert totals["token_savings_pct"] == 47.0
    assert totals["outputs_matched"] == 1 and totals["outputs_checked"] == 1
    assert totals["compiled_actions"] == 1 and totals["escalated_actions"] == 1
    code_action = report.actions[0]
    assert code_action.steps[0].output_match is True
    assert code_action.compiled_latency_ms < code_action.recorded_latency_ms
    assert report.final_answer == "alpha and beta"

    paths = write_report(report, tmp_path / "report")
    md = Path(paths["markdown"]).read_text()
    assert "| LLM tokens | 2,000 | 1,060 | −47.0% |" in md


def test_benchmark_skips_self_referential_steps(tmp_path, monkeypatch):
    from core.build.bench import BENCH_ACTIVE_ENV, run_benchmark
    from core.build.__main__ import main
    from core.work_ir import WorkIR

    trace = TraceIR.model_validate({
        "run_id": "self", "source_agent": "codex-tui",
        "steps": [
            {"step_id": "s1", "actor": "agent", "action": "shell_python3", "latency_ms": 1000.0,
             "token_usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
             "input": {"cmd": "python3 -m core.build bench build/self"}, "output": {"tool_calls": [], "tool_result": "x"}},
            {"step_id": "s2", "actor": "agent", "action": "shell_curl", "latency_ms": 1000.0,
             "token_usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
             "input": {"cmd": "curl -s -X POST localhost:8787/v1/workcompiler/compile -d '{}'"}, "output": {"tool_calls": [], "tool_result": "y"}},
        ],
        "result": {"status": "success", "outputs": {}},
    })
    work_ir = WorkIR.model_validate({
        "work": "self", "version": "3.0", "inputs": ["cmd"], "outputs": ["content"],
        "states": ["initialized", "python3_shelled", "curl_shelled"],
        "actions": ["shell_python3", "shell_curl"], "dependencies": {"shell_curl": ["shell_python3"]},
        "executors": {"shell_python3": {"type": "code"}, "shell_curl": {"type": "code"}},
    })
    manifest = emit_build(work_ir, tmp_path, traces=[trace])
    report = run_benchmark(manifest.build_dir, trace)
    assert all(s.executor_used.endswith("(skipped)") for a in report.actions for s in a.steps)
    assert report.totals()["outputs_checked"] == 0

    monkeypatch.setenv(BENCH_ACTIVE_ENV, "1")
    assert main(["bench", manifest.build_dir]) == 0  # nested call is a no-op


def test_benchmark_compare_unwraps_json_repacked_outputs():
    from core.build.bench import _compare

    recorded = json.dumps({"tree": "a/x.py\na/y.py\n", "work_yaml": "work: w\nversion: '1'\n", "exits": [0, 0]})
    compiled = "a/x.py\na/y.py\nwork: w\nversion: '1'\n"
    assert _compare(recorded, compiled) == (True, "")
    assert _compare("b\na\n", "a\nb\n") == (True, "same lines, different order")
    assert _compare("a\n", "a\nb\n") == (False, "")


def test_patch_steps_compile_to_file_writing_handlers_and_bench_verifies_files(tmp_path, monkeypatch):
    from core.build.bench import run_benchmark
    from core.work_ir import WorkIR

    monkeypatch.chdir(tmp_path)
    patch = ("*** Begin Patch\n*** Add File: " + str(tmp_path / "out/proposal.md") +
             "\n+# Proposal\n+Total: $116,640\n*** End Patch")
    trace = TraceIR.model_validate({
        "run_id": "p", "source_agent": "codex_exec",
        "steps": [{"step_id": "s1", "actor": "agent", "action": "write_proposal", "latency_ms": 9000.0,
                   "token_usage": {"prompt_tokens": 18000, "completion_tokens": 600, "total_tokens": 18600},
                   "input": {"patch": patch, "files": [str(tmp_path / "out/proposal.md")]},
                   "output": {"tool_calls": [{"id": "c", "name": "exec", "result": "{}"}], "tool_result": "{}"}}],
        "result": {"status": "success", "outputs": {}},
    })
    work_ir = WorkIR.model_validate({
        "work": "renewal", "version": "3.0", "inputs": ["patch"], "outputs": ["files"],
        "states": ["initialized", "write_proposal_completed"], "actions": ["write_proposal"], "dependencies": {},
        "executors": {"write_proposal": {"type": "code"}},
    })
    manifest = emit_build(work_ir, tmp_path / "build", traces=[trace])
    handler = (Path(manifest.build_dir) / "handlers" / "write_proposal.py").read_text()
    assert "*** Add File: out/proposal.md" in handler  # absolute path relativized to the workspace

    report = run_benchmark(manifest.build_dir, trace)
    step = report.actions[0].steps[0]
    assert step.output_match is True and "verified on disk" in step.note
    assert (tmp_path / "out/proposal.md").read_text() == "# Proposal\nTotal: $116,640\n"
    assert report.totals()["compiled_tokens"] == 0


def test_benchmark_replays_steps_in_trace_order(tmp_path, monkeypatch):
    """A later step of an *earlier-listed* action must not run before the steps that precede it."""
    from core.build.bench import run_benchmark
    from core.work_ir import WorkIR

    monkeypatch.chdir(tmp_path)
    trace = TraceIR.model_validate({
        "run_id": "order", "source_agent": "codex_exec",
        "steps": [
            {"step_id": "s1", "actor": "agent", "action": "shell_ls", "latency_ms": 1.0,
             "input": {"cmd": "ls ."}, "output": {"tool_calls": [], "tool_result": ""}},
            {"step_id": "s2", "actor": "agent", "action": "shell_printf", "latency_ms": 1.0,
             "input": {"cmd": "printf 'hello' > note.txt"}, "output": {"tool_calls": [], "tool_result": ""}},
            {"step_id": "s3", "actor": "agent", "action": "shell_ls", "latency_ms": 1.0,
             "input": {"cmd": "cat note.txt"}, "output": {"tool_calls": [], "tool_result": "hello"}},
        ],
        "result": {"status": "success", "outputs": {}},
    })
    work_ir = WorkIR.model_validate({
        "work": "order", "version": "3.0", "inputs": ["cmd"], "outputs": ["content"],
        "states": ["initialized", "ls_shelled", "printf_shelled"],
        "actions": ["shell_ls", "shell_printf"], "dependencies": {"shell_printf": ["shell_ls"]},
        "executors": {"shell_ls": {"type": "code"}, "shell_printf": {"type": "code"}},
    })
    manifest = emit_build(work_ir, tmp_path / "build", traces=[trace])
    report = run_benchmark(manifest.build_dir, trace)
    ls_steps = report.actions[0].steps
    assert [s.step_id for s in ls_steps] == ["s1", "s3"]
    assert ls_steps[1].output_match is True  # cat ran after printf wrote the file


def _renewal_like_trace(tmp_path):
    data = tmp_path / "data.json"
    data.write_text(json.dumps({"rows": [{"id": "CUST-1001", "seats": 240}, {"id": "CUST-1002", "seats": 60}]}))
    patch = ("*** Begin Patch\n*** Add File: " + str(tmp_path / "out/offer-CUST-1001.md") +
             "\n+# Offer CUST-1001\n+Seats: 240\n+Total: 9,600.00\n*** End Patch")
    return TraceIR.model_validate({
        "run_id": "r", "source_agent": "codex_exec",
        "steps": [
            {"step_id": "s1", "actor": "agent", "action": "shell_jq", "latency_ms": 4000.0,
             "token_usage": {"prompt_tokens": 12000, "completion_tokens": 100, "total_tokens": 12100},
             "input": {"cmd": f"jq -c '.rows[] | select(.id == \"CUST-1001\")' {data}", "content": "renewal for CUST-1001"},
             "output": {"tool_calls": [], "tool_result": '{"id":"CUST-1001","seats":240}\n'}},
            {"step_id": "s2", "actor": "agent", "action": "write_offer_cust_1001", "latency_ms": 9000.0,
             "token_usage": {"prompt_tokens": 15000, "completion_tokens": 500, "total_tokens": 15500},
             "input": {"patch": patch, "files": [str(tmp_path / "out/offer-CUST-1001.md")]},
             "output": {"tool_calls": [], "tool_result": "{}"}},
        ],
        "result": {"status": "success", "outputs": {}},
    })


def test_parameters_are_discovered_templated_and_synthesized_steps_flagged(tmp_path, monkeypatch):
    from core.work_ir import WorkIR

    monkeypatch.chdir(tmp_path)
    trace = _renewal_like_trace(tmp_path)
    work_ir = WorkIR.model_validate({
        "work": "offer", "version": "3.0", "inputs": ["customer_id"], "outputs": ["files"],
        "states": ["initialized", "jq_shelled", "write_offer_cust_1001_completed"],
        "actions": ["shell_jq", "write_offer_cust_1001"], "dependencies": {"write_offer_cust_1001": ["shell_jq"]},
        "executors": {"shell_jq": {"type": "code"}, "write_offer_cust_1001": {"type": "code"}},
    })
    manifest = emit_build(work_ir, tmp_path / "build", traces=[trace])
    root = Path(manifest.build_dir)

    params = json.loads((root / "PARAMS.json").read_text())
    assert params["params"][0]["name"] == "customer_id"
    assert params["params"][0]["recorded_value"] == "CUST-1001"
    assert params["synthesized_actions"] == ["write_offer_cust_1001"]   # 9,600.00 was computed by the agent
    assert '"{customer_id}"' in (root / "handlers" / "shell_jq.py").read_text()
    assert (root / "prompts" / "write_offer_cust_1001.prompt.md").exists()


def test_run_build_binds_new_parameters_and_escalates_only_synthesized_steps(tmp_path, monkeypatch):
    from core.build.run import run_build
    from core.work_ir import WorkIR

    monkeypatch.chdir(tmp_path)
    trace = _renewal_like_trace(tmp_path)
    work_ir = WorkIR.model_validate({
        "work": "offer", "version": "3.0", "inputs": ["customer_id"], "outputs": ["files"],
        "states": ["initialized", "jq_shelled", "write_offer_cust_1001_completed"],
        "actions": ["shell_jq", "write_offer_cust_1001"], "dependencies": {"write_offer_cust_1001": ["shell_jq"]},
        "executors": {"shell_jq": {"type": "code"}, "write_offer_cust_1001": {"type": "code"}},
    })
    manifest = emit_build(work_ir, tmp_path / "build", traces=[trace])

    seen = {}

    def fake_agent(prompt, context):
        seen["prompt"] = prompt
        return {"output": "wrote offer for " + context["params"]["customer_id"], "tokens": 3000, "latency_ms": 2500.0, "exit_code": 0}

    report = run_build(manifest.build_dir, request="Please prepare the renewal offer for CUST-1002",
                       escalate="codex", escalator=fake_agent, out_dir=tmp_path / "runs")

    assert report.params == {"customer_id": "CUST-1002"} and report.binding == {"customer_id": "regex"}
    jq_step, write_step = report.steps
    assert jq_step.mode == "code" and jq_step.tokens == 0 and '"seats":60' in jq_step.output   # re-rendered for CUST-1002
    assert write_step.mode == "escalated:codex" and write_step.tokens == 3000
    assert '"seats":60' in seen["prompt"] and "CUST-1002" in seen["prompt"]        # agent gets compiled upstream outputs
    totals = report.totals()
    assert totals["tokens"] == 3000 and totals["recorded_tokens"] == 27600
    assert (tmp_path / "runs" / "RUN_REPORT.md").exists()

    # without an escalation backend the synthesized step is reported, not faked
    report2 = run_build(manifest.build_dir, params={"customer_id": "CUST-1002"}, out_dir=tmp_path / "runs2")
    assert report2.steps[1].mode == "needs_agent" and report2.binding == {"customer_id": "override"}


def test_build_emits_editable_openworklang_source_that_round_trips(tmp_path, monkeypatch):
    from core.openworklang import OpenWorkLangCompiler, parse_openworklang
    from core.work_ir import WorkIR

    monkeypatch.chdir(tmp_path)
    trace = _renewal_like_trace(tmp_path)
    work_ir = WorkIR.model_validate({
        "work": "offer", "version": "3.0", "inputs": ["customer_id"], "outputs": ["files"],
        "states": ["initialized", "jq_shelled", "write_offer_cust_1001_completed"],
        "actions": ["shell_jq", "write_offer_cust_1001"], "dependencies": {"write_offer_cust_1001": ["shell_jq"]},
        "executors": {"shell_jq": {"type": "code"}, "write_offer_cust_1001": {"type": "code"}},
    })
    manifest = emit_build(work_ir, tmp_path / "build", traces=[trace])
    src = Path(manifest.build_dir) / "offer.work"
    text = src.read_text()
    assert "work offer {" in text and "write_offer_cust_1001: agent" in text and "- customer_id" in text

    ast = parse_openworklang(src)
    assert ast.params == ["customer_id"]
    assert ast.workflow == ["shell_jq", "write_offer_cust_1001"]
    assert ast.executors == {"shell_jq": "code", "write_offer_cust_1001": "code"}
    assert ast.escalation["write_offer_cust_1001"] == "agent"

    recompiled = OpenWorkLangCompiler().compile_ast_to_work_ir(ast)
    assert recompiled.actions == work_ir.actions
    assert recompiled.inputs[0] == "customer_id"
    assert recompiled.to_dict()["escalation"]["write_offer_cust_1001"] == "agent"
