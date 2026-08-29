"""Unit and Integration Tests for OpenWorkLang Parser and Compiler."""

import pytest
from pathlib import Path

from core.openworklang import (
    OpenWorkLangAST,
    parse_openworklang,
    OpenWorkLangCompiler,
)
from core.work_ir import WorkIR, ExecutorType


def test_parse_openworklang_file():
    """Test parsing an OpenWorkLang (.work) file into OpenWorkLangAST."""
    example_path = Path(__file__).resolve().parents[1] / "examples" / "quality_analysis.work"
    ast: OpenWorkLangAST = parse_openworklang(example_path)

    assert ast.name == "quality_analyst"
    assert ast.version == "4.0"
    assert "production_data" in ast.inputs
    assert "root_cause" in ast.outputs
    assert "query_mes()" in ast.tools
    assert "verify_sensor_calibration" in ast.invariants
    assert ast.workflow == [
        "collect_data",
        "detect_anomaly",
        "find_correlation",
        "determine_root_cause",
        "create_report",
    ]
    assert ast.executors["detect_anomaly"] == "rule"
    assert ast.executors["find_correlation"] == "ml"


def test_compile_openworklang_to_work_ir():
    """Test compiling OpenWorkLangAST to executable WorkIR."""
    example_path = Path(__file__).resolve().parents[1] / "examples" / "quality_analysis.work"
    ast = parse_openworklang(example_path)

    compiler = OpenWorkLangCompiler()
    work_ir: WorkIR = compiler.compile_ast_to_work_ir(ast)

    assert work_ir.work == "quality_analyst"
    assert work_ir.version == "4.0"
    assert work_ir.actions == [
        "collect_data",
        "detect_anomaly",
        "find_correlation",
        "determine_root_cause",
        "create_report",
    ]
    assert "verify_sensor_calibration" in work_ir.invariants
    assert work_ir.executors["collect_data"].type == ExecutorType.CODE
    assert work_ir.executors["detect_anomaly"].type == ExecutorType.RULE
    assert work_ir.executors["find_correlation"].type == ExecutorType.ML
    assert work_ir.executors["determine_root_cause"].type == ExecutorType.SLM

    # Verify DAG validity via topological sort
    sorted_steps = work_ir.topological_sort()
    assert len(sorted_steps) == 5
    assert sorted_steps[0] == "collect_data"


def test_compile_openworklang_to_linkml():
    """Test compiling OpenWorkLangAST to LinkML YAML schema."""
    example_path = Path(__file__).resolve().parents[1] / "examples" / "quality_analysis.work"
    ast = parse_openworklang(example_path)

    compiler = OpenWorkLangCompiler()
    linkml_yaml = compiler.compile_to_linkml_yaml(ast)

    assert "name: quality_analyst" in linkml_yaml
    assert "QualityAnalystInput:" in linkml_yaml
    assert "QualityAnalystOutput:" in linkml_yaml
    assert "production_data" in linkml_yaml
