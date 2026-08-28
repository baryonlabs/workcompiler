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
    assert "COMMAND = 'ls examples'" in handler and "subprocess.run" in handler

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
