"""Distribute the canonical skills (``.agents/skills/``) into each agent's convention directory.

Only ``.agents/skills/`` is committed; ``owc skills install`` copies (or links) the skills into
``.claude/skills/`` (Claude Code), ``.gemini/skills/`` (Gemini CLI), ``.opencode/skills/`` … and
records what it did in ``.owc-skills.json`` so ``owc skills doctor`` can report drift.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

SOURCE_DIR = ".agents/skills"
MANIFEST = ".owc-skills.json"
VENDOR_ONLY = {"agents"}          # per-vendor override subdirs (grill-me/agents/openai.yaml) are not copied


@dataclass
class SkillInfo:
    name: str
    description: str
    path: str
    sha256: str


def _frontmatter(text: str) -> Dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    meta: Dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"\'')
    return meta


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def list_skills(root: Path | str = ".") -> List[SkillInfo]:
    src = Path(root) / SOURCE_DIR
    out: List[SkillInfo] = []
    for skill_md in sorted(src.glob("*/SKILL.md")):
        meta = _frontmatter(skill_md.read_text(encoding="utf-8"))
        out.append(SkillInfo(meta.get("name") or skill_md.parent.name, meta.get("description", ""),
                             str(skill_md.parent.relative_to(root)), _sha(skill_md)))
    return out


def _target_dirs(agents: List[str]) -> Dict[str, Optional[str]]:
    from core.agents import REGISTRY

    names = list(REGISTRY) if agents == ["all"] else agents
    return {n: REGISTRY[n].skills_dir for n in names if n in REGISTRY}


def install(root: Path | str = ".", agents: Optional[List[str]] = None, *, mode: str = "copy", force: bool = False) -> Dict:
    root = Path(root)
    agents = agents or ["claude"]
    manifest = _load_manifest(root)
    skills = list_skills(root)
    result: Dict[str, Dict] = {}
    for agent, target in _target_dirs(agents).items():
        if not target or target == SOURCE_DIR:
            result[agent] = {"dir": target, "status": "canonical" if target == SOURCE_DIR else "unsupported"}
            continue
        dst_root = root / target
        dst_root.mkdir(parents=True, exist_ok=True)
        installed: Dict[str, Dict[str, str]] = {}
        for skill in skills:
            src = root / skill.path
            dst = dst_root / src.name
            if dst.is_symlink() or dst.exists():
                if not force and dst.is_dir() and not dst.is_symlink() and mode == "copy":
                    pass
                if dst.is_symlink() or dst.is_file():
                    dst.unlink()
                elif dst.is_dir():
                    shutil.rmtree(dst)
            if mode == "link":
                dst.symlink_to(os.path.relpath(src, dst.parent), target_is_directory=True)
            else:
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*VENDOR_ONLY))
            installed[skill.name] = {"sha256": skill.sha256}
        manifest.setdefault("installed", {})[agent] = {"dir": target, "mode": mode,
                                                        "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "skills": installed}
        result[agent] = {"dir": target, "status": "installed", "count": len(installed), "mode": mode}
    manifest["version"] = 1
    manifest["source"] = SOURCE_DIR
    (root / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return result


def _load_manifest(root: Path) -> Dict:
    path = root / MANIFEST
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def doctor(root: Path | str = ".", *, check: bool = False) -> Dict:
    from core.agents import detect_all

    root = Path(root)
    skills = {s.name: s for s in list_skills(root)}
    report: Dict = {"source": SOURCE_DIR, "skills": sorted(skills), "agents": {}, "drift": False}
    for backend, version in detect_all():
        entry: Dict = {"installed_cli": version is not None, "version": version, "skills_dir": backend.skills_dir, "skills": {}}
        if backend.skills_dir and backend.skills_dir != SOURCE_DIR:
            dst_root = root / backend.skills_dir
            for name, skill in skills.items():
                dst = dst_root / Path(skill.path).name / "SKILL.md"
                if not dst.exists():
                    entry["skills"][name] = "missing"
                elif _sha(dst) != skill.sha256:
                    entry["skills"][name] = "stale"; report["drift"] = True
                else:
                    entry["skills"][name] = "ok"
            if dst_root.exists():
                for extra in dst_root.iterdir():
                    if extra.is_dir() and extra.name not in {Path(s.path).name for s in skills.values()}:
                        entry["skills"][extra.name] = "extra"
        elif backend.skills_dir == SOURCE_DIR:
            entry["skills"] = {n: "canonical" for n in skills}
        report["agents"][backend.name] = entry
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="owc skills", description="Sync .agents/skills into each agent's skills directory")
    sub = parser.add_subparsers(dest="command", required=True)
    i = sub.add_parser("install", help="Copy (or link) the canonical skills into an agent's directory")
    i.add_argument("--agent", action="append", help="claude | gemini | opencode | all (default: claude)")
    i.add_argument("--link", action="store_true", help="Symlink instead of copying")
    i.add_argument("--force", action="store_true")
    sub.add_parser("list", help="List canonical skills")
    d = sub.add_parser("doctor", help="Report installed agents and skill drift")
    d.add_argument("--check", action="store_true", help="Exit 1 when an installed copy is stale")
    args = parser.parse_args(argv)

    if args.command == "list":
        for s in list_skills():
            print(f"{s.name:20s} {s.description[:90]}")
        return 0
    if args.command == "install":
        res = install(".", args.agent or ["claude"], mode="link" if args.link else "copy", force=args.force)
        for agent, info in res.items():
            print(f"{agent:10s} {info.get('status'):10s} {info.get('dir') or '-'}" + (f"  ({info.get('count')} skills, {info.get('mode')})" if info.get('count') else ""))
        return 0
    rep = doctor(".", check=args.check)
    for agent, info in rep["agents"].items():
        cli = f"v{info['version']}" if info["version"] else ("installed" if info["installed_cli"] else "not installed")
        summary = ", ".join(f"{k}:{v}" for k, v in info["skills"].items()) if info["skills"] else "-"
        print(f"{agent:10s} cli={cli:30s} dir={info['skills_dir'] or '-':18s} {summary}")
    if args.check and rep["drift"]:
        print("skills drift detected: run `owc skills install`", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
