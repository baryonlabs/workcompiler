"""`owc skills`: one canonical `.agents/skills/` copied/linked into each agent's directory."""

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import skills


def _repo(tmp_path):
    src = tmp_path / ".agents" / "skills"
    (src / "ow-bench").mkdir(parents=True)
    (src / "ow-bench" / "SKILL.md").write_text("---\nname: ow-bench\ndescription: Benchmark a build\n---\n# ow-bench\n")
    (src / "grill-me" / "agents").mkdir(parents=True)
    (src / "grill-me" / "SKILL.md").write_text("---\nname: grill-me\ndescription: Interview\n---\nbody\n")
    (src / "grill-me" / "agents" / "openai.yaml").write_text("interface: x\n")
    return tmp_path


def test_list_reads_frontmatter(tmp_path):
    root = _repo(tmp_path)
    names = {s.name: s for s in skills.list_skills(root)}
    assert set(names) == {"ow-bench", "grill-me"} and names["ow-bench"].description == "Benchmark a build"


def test_install_copies_skipping_vendor_dirs_and_is_idempotent(tmp_path):
    root = _repo(tmp_path)
    res = skills.install(root, ["claude", "gemini", "codex", "aider"])
    assert res["claude"] == {"dir": ".claude/skills", "status": "installed", "count": 2, "mode": "copy"}
    assert res["gemini"]["status"] == "installed" and res["codex"]["status"] == "canonical" and res["aider"]["status"] == "unsupported"
    assert (root / ".claude/skills/ow-bench/SKILL.md").read_text().startswith("---\nname: ow-bench")
    assert not (root / ".claude/skills/grill-me/agents").exists()          # vendor-only override stays canonical
    manifest = json.loads((root / skills.MANIFEST).read_text())
    assert set(manifest["installed"]) == {"claude", "gemini"} and manifest["source"] == ".agents/skills"
    again = skills.install(root, ["claude"])
    assert again["claude"]["count"] == 2 and (root / ".claude/skills/ow-bench/SKILL.md").exists()


def test_install_link_mode_symlinks_to_canonical(tmp_path):
    root = _repo(tmp_path)
    skills.install(root, ["claude"], mode="link")
    link = root / ".claude/skills/ow-bench"
    assert link.is_symlink() and (link / "SKILL.md").read_text().startswith("---")
    skills.install(root, ["claude"])            # switching back to copy replaces the symlink
    assert not link.is_symlink() and link.is_dir()


def test_doctor_reports_ok_stale_missing_and_extra(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    monkeypatch.setattr(shutil, "which", lambda exe: "/bin/x" if exe in ("claude", "codex") else None)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(stdout="v1\n", stderr="", returncode=0))
    skills.install(root, ["claude"])
    rep = skills.doctor(root)
    assert rep["agents"]["claude"]["skills"] == {"ow-bench": "ok", "grill-me": "ok"} and rep["drift"] is False
    assert rep["agents"]["codex"]["skills"] == {"ow-bench": "canonical", "grill-me": "canonical"}
    assert rep["agents"]["gemini"]["installed_cli"] is False and rep["agents"]["gemini"]["skills"]["ow-bench"] == "missing"
    (root / ".agents/skills/ow-bench/SKILL.md").write_text("---\nname: ow-bench\ndescription: changed\n---\n")
    (root / ".claude/skills/old-thing").mkdir()
    rep = skills.doctor(root)
    assert rep["agents"]["claude"]["skills"]["ow-bench"] == "stale" and rep["agents"]["claude"]["skills"]["old-thing"] == "extra"
    assert rep["drift"] is True


def test_cli_install_then_doctor_check(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.setattr(shutil, "which", lambda exe: None)
    assert skills.main(["install", "--agent", "claude"]) == 0
    assert "claude     installed" in capsys.readouterr().out
    assert skills.main(["doctor", "--check"]) == 0
    (root / ".agents/skills/ow-bench/SKILL.md").write_text("---\nname: ow-bench\n---\nnew\n")
    assert skills.main(["doctor", "--check"]) == 1
    assert "drift" in capsys.readouterr().err
    assert skills.main(["list"]) == 0 and "ow-bench" in capsys.readouterr().out
