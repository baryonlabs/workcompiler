"""Tests for the `python3 -m core.openworklang` command-line entry point."""

import json

import yaml

from core.openworklang.__main__ import main


def test_cli_compiles_work_file_to_yaml_and_linkml(tmp_path, capsys):
    out = tmp_path / "quality.work.yaml"
    linkml = tmp_path / "quality.linkml.yaml"
    code = main(["compile", "examples/quality_analysis.work", "--out", str(out), "--linkml", str(linkml), "--json"])
    assert code == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["work"] == "quality_analyst"
    assert "collect_data" in summary["actions"]
    assert "verify_sensor_calibration" in summary["invariants"]
    assert set(summary["executors"].values()) <= {"code", "rule", "ml", "slm", "frontier", "human", "http", "connector"}

    saved = yaml.safe_load(out.read_text())
    assert saved["work"] == "quality_analyst"
    assert saved["actions"] == summary["actions"]
    assert linkml.read_text().startswith("id: https://w3id.org/openworkflow/schemas/quality_analyst")


def test_cli_reports_missing_source(tmp_path, capsys):
    code = main(["compile", str(tmp_path / "missing.work")])
    assert code == 2
    assert "not found" in capsys.readouterr().err
