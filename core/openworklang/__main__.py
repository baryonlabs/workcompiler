"""Command-line entry point for the OpenWorkLang compiler.

Usage::

    python3 -m core.openworklang compile examples/quality_analysis.work [--build-dir build]

Emits the full artifact tree ``build/<work>/`` (work.yaml, handlers/, rules/,
models/ml|slm/, prompts/, schema/<work>.linkml.yaml, MANIFEST.json) and prints a
compact summary so the command is convenient to run from agent shells such as
Codex CLI. ``--out`` additionally writes a flat copy of work.yaml.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.build.emitter import emit_build
from core.openworklang import OpenWorkLangCompiler, parse_openworklang
from core.work_ir import save_work_ir


def _cmd_compile(args: argparse.Namespace) -> int:
    source = Path(args.source)
    if not source.exists():
        print(f"error: OpenWorkLang source not found: {source}", file=sys.stderr)
        return 2

    ast = parse_openworklang(source)
    compiler = OpenWorkLangCompiler()
    work_ir = compiler.compile_ast_to_work_ir(ast)
    linkml_text = compiler.compile_to_linkml_yaml(ast)

    manifest = emit_build(work_ir, args.build_dir, linkml_yaml=linkml_text)
    build_dir = Path(manifest.build_dir)
    out = build_dir / "work.yaml"
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        save_work_ir(work_ir, out)

    linkml_path = build_dir / "schema" / f"{build_dir.name}.linkml.yaml"
    if args.linkml:
        linkml_path = Path(args.linkml)
        linkml_path.parent.mkdir(parents=True, exist_ok=True)
        linkml_path.write_text(linkml_text, encoding="utf-8")

    summary = {
        "work": work_ir.work,
        "version": work_ir.version,
        "inputs": list(work_ir.inputs),
        "outputs": list(work_ir.outputs),
        "actions": list(work_ir.actions),
        "invariants": list(work_ir.invariants),
        "executors": {name: cfg.type.value for name, cfg in work_ir.executors.items()},
        "work_yaml": str(out),
        "linkml_yaml": str(linkml_path),
        "build_dir": str(build_dir),
        "artifacts": manifest.by_tier(),
    }
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"[OpenWorkLang] {source} -> {build_dir}/")
        print(f"  work:       {summary['work']} (v{summary['version']})")
        print(f"  inputs:     {', '.join(summary['inputs']) or '-'}")
        print(f"  outputs:    {', '.join(summary['outputs']) or '-'}")
        print(f"  actions:    {', '.join(summary['actions']) or '-'}")
        print(f"  invariants: {', '.join(summary['invariants']) or '-'}")
        print("  executors:  " + (", ".join(f"{k}={v}" for k, v in summary["executors"].items()) or "-"))
        print(f"  linkml:     {linkml_path}")
        print("  artifacts:")
        for tier, paths in manifest.by_tier().items():
            print(f"    {tier:13s} " + ", ".join(paths))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m core.openworklang", description="OpenWorkLang (.work) compiler")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("compile", help="Compile a .work file into Work IR (work.yaml) and optionally a LinkML schema")
    c.add_argument("source", help="Path to the .work source file")
    c.add_argument("--build-dir", default="build", help="Root for the artifact tree (default: build/<work>/)")
    c.add_argument("--out", "-o", help="Also write a flat copy of work.yaml to this path")
    c.add_argument("--linkml", help="Also write the LinkML schema YAML to this path")
    c.add_argument("--json", action="store_true", help="Print the summary as JSON")
    c.set_defaults(func=_cmd_compile)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
