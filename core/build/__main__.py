"""CLI for the build backend.

    python3 -m core.build from-work  build/x/work.yaml            [--build-dir build]
    python3 -m core.build from-trace trace.json --target NAME     [--build-dir build] [--behaviors DIR]
    python3 -m core.build show       build/<work>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.build.emitter import emit_build
from core.work_ir import TraceIR, load_work_ir


def _print_manifest(manifest) -> None:
    print(f"[build] {manifest.work} -> {manifest.build_dir}  ({len(manifest.artifacts)} artifacts)")
    for tier, paths in manifest.by_tier().items():
        print(f"  {tier:13s} " + ", ".join(paths))


def cmd_from_work(args: argparse.Namespace) -> int:
    work_ir = load_work_ir(args.work_yaml)
    _print_manifest(emit_build(work_ir, args.build_dir))
    return 0


def cmd_from_trace(args: argparse.Namespace) -> int:
    from adapters.agentbehavior import parse_behavior_md
    from core.compiler import WorkCompiler

    payload = json.loads(Path(args.trace_json).read_text(encoding="utf-8"))
    trace = TraceIR.model_validate(payload.get("trace", payload))
    behaviors = []
    if args.behaviors:
        for p in sorted(Path(args.behaviors).rglob("BEHAVIOR.md")):
            behaviors.append(parse_behavior_md(p.read_text(encoding="utf-8")))
    compiler = WorkCompiler()
    work_ir = compiler.compile_traces_to_work_ir(traces=[trace], behaviors=behaviors, target_name=args.target)
    manifest = emit_build(work_ir, args.build_dir, traces=[trace], training_candidates=compiler.training_candidates)
    _print_manifest(manifest)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    manifest = json.loads((Path(args.build_dir) / "MANIFEST.json").read_text(encoding="utf-8"))
    print(json.dumps(manifest["by_tier"], indent=2, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m core.build", description="OpenWorkflow build backend")
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("from-work", help="Emit the artifact tree for an existing work.yaml")
    a.add_argument("work_yaml")
    a.add_argument("--build-dir", default="build")
    a.set_defaults(func=cmd_from_work)

    b = sub.add_parser("from-trace", help="Compile a TraceIR JSON (e.g. from the proxy) and emit its artifact tree")
    b.add_argument("trace_json")
    b.add_argument("--target", required=True, help="Work name")
    b.add_argument("--build-dir", default="build")
    b.add_argument("--behaviors", help="Directory scanned recursively for BEHAVIOR.md contracts")
    b.set_defaults(func=cmd_from_trace)

    c = sub.add_parser("show", help="Print the artifact index of a build directory")
    c.add_argument("build_dir")
    c.set_defaults(func=cmd_show)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
