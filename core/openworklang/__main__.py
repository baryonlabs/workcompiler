"""Command-line entry point for the OpenWorkLang compiler.

Usage::

    python3 -m core.openworklang compile examples/quality_analysis.work \
        --out build/quality_analysis.work.yaml --linkml build/quality_analysis.linkml.yaml

Prints a compact summary (work name, actions, invariants, executors) so the
command is convenient to run from agent shells such as Codex CLI.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.openworklang.compiler import OpenWorkLangCompiler
from core.openworklang.parser import parse_openworklang
from core.work_ir import save_work_ir


def _cmd_compile(args: argparse.Namespace) -> int:
    source = Path(args.source)
    if not source.exists():
        print(f"error: OpenWorkLang source not found: {source}", file=sys.stderr)
        return 2

    ast = parse_openworklang(source)
    compiler = OpenWorkLangCompiler()
    work_ir = compiler.compile_ast_to_work_ir(ast)

    out = Path(args.out) if args.out else Path("build") / f"{source.stem}.work.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    save_work_ir(work_ir, out)

    linkml_path = None
    if args.linkml:
        linkml_path = Path(args.linkml)
        linkml_path.parent.mkdir(parents=True, exist_ok=True)
        linkml_path.write_text(compiler.compile_to_linkml_yaml(ast), encoding="utf-8")

    summary = {
        "work": work_ir.work,
        "version": work_ir.version,
        "inputs": list(work_ir.inputs),
        "outputs": list(work_ir.outputs),
        "actions": list(work_ir.actions),
        "invariants": list(work_ir.invariants),
        "executors": {name: cfg.type.value for name, cfg in work_ir.executors.items()},
        "work_yaml": str(out),
        "linkml_yaml": str(linkml_path) if linkml_path else None,
    }
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"[OpenWorkLang] {source} -> {out}")
        print(f"  work:       {summary['work']} (v{summary['version']})")
        print(f"  inputs:     {', '.join(summary['inputs']) or '-'}")
        print(f"  outputs:    {', '.join(summary['outputs']) or '-'}")
        print(f"  actions:    {', '.join(summary['actions']) or '-'}")
        print(f"  invariants: {', '.join(summary['invariants']) or '-'}")
        print("  executors:  " + (", ".join(f"{k}={v}" for k, v in summary["executors"].items()) or "-"))
        if linkml_path:
            print(f"  linkml:     {linkml_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m core.openworklang", description="OpenWorkLang (.work) compiler")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("compile", help="Compile a .work file into Work IR (work.yaml) and optionally a LinkML schema")
    c.add_argument("source", help="Path to the .work source file")
    c.add_argument("--out", "-o", help="Output work.yaml path (default: build/<name>.work.yaml)")
    c.add_argument("--linkml", help="Also write the generated LinkML schema YAML to this path")
    c.add_argument("--json", action="store_true", help="Print the summary as JSON")
    c.set_defaults(func=_cmd_compile)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
