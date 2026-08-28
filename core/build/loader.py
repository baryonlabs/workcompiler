"""Load a build tree produced by :func:`core.build.emit_build` into a runtime engine."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Dict

import yaml

from core.work_ir import load_work_ir


def _import_handler(path: Path):
    spec = importlib.util.spec_from_file_location(f"openworkflow_build_handlers.{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import handler module {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run = getattr(module, "run", None)
    if not callable(run):
        raise ImportError(f"{path} does not define run(**inputs)")
    return run


def load_build_into_engine(engine: Any, build_dir: Path | str) -> Dict[str, Any]:
    """Register handlers/rules from ``build_dir`` on ``engine`` and return the Work IR dict.

    * ``handlers/<action>.py`` → CodeExecutor.register_handler(action, run)
    * ``rules/<action>.rule.yaml`` → RuleExecutor.register_rule(action, branches)
    * ``prompts/<action>.prompt.md`` are left for the LLM/SLM executors' clients.
    """
    root = Path(build_dir)
    work_ir = load_work_ir(root / "work.yaml")
    summary: Dict[str, Any] = {"work": work_ir.work, "handlers": [], "rules": [], "prompts": []}

    code_exec = engine.get_executor("code")
    for path in sorted((root / "handlers").glob("*.py")):
        if path.name == "__init__.py":
            continue
        code_exec.register_handler(path.stem, _import_handler(path))
        summary["handlers"].append(path.stem)

    rule_exec = engine.get_executor("rule")
    for path in sorted((root / "rules").glob("*.rule.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        action = spec.get("action") or path.name.replace(".rule.yaml", "")
        rule_exec.register_rule(action, spec.get("rules", []))
        summary["rules"].append(action)

    summary["prompts"] = [p.name.replace(".prompt.md", "") for p in sorted((root / "prompts").glob("*.prompt.md"))]
    manifest_path = root / "MANIFEST.json"
    if manifest_path.exists():
        summary["manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary["work_ir"] = work_ir.to_dict()
    return summary
