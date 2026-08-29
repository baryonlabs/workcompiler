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


def test_owc_agent_and_skills_delegate(monkeypatch, capsys):
    import shutil
    import subprocess
    from types import SimpleNamespace

    monkeypatch.setattr(shutil, "which", lambda exe: "/bin/x" if exe == "codex" else None)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(stdout="codex 0.150.1\n", stderr="", returncode=0))
    assert main(["agent", "list"]) == 0
    out = capsys.readouterr().out
    assert "codex      codex 0.150.1" in out and "claude     -" in out
    assert main(["agent", "setup", "claude", "--proxy-url", "http://127.0.0.1:8788"]) == 0
    assert "ANTHROPIC_BASE_URL=http://127.0.0.1:8788" in capsys.readouterr().out
    assert main(["skills", "list"]) == 0
    assert "ow-define" in capsys.readouterr().out
    assert main(["skills", "doctor"]) == 0
    assert "codex      cli=vcodex 0.150.1" in capsys.readouterr().out
