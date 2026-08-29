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
