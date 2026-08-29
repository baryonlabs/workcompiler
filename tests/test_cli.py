"""The owc console entry point delegates to the sub-CLIs."""

from core.cli import main


def test_owc_version(capsys):
    assert main(["version"]) == 0
    assert capsys.readouterr().out.startswith("owc ")


def test_owc_compile_delegates(tmp_path, capsys):
    assert main(["compile", "examples/quality_analysis.work", "--build-dir", str(tmp_path)]) == 0
    assert (tmp_path / "quality_analyst" / "work.yaml").exists()


def test_owc_build_show_delegates(tmp_path, capsys):
    main(["compile", "examples/quality_analysis.work", "--build-dir", str(tmp_path)])
    assert main(["build", "show", str(tmp_path / "quality_analyst")]) == 0
    assert "handlers/collect_data.py" in capsys.readouterr().out
