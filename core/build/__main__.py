"""CLI for the build backend.

    python3 -m core.build from-work  build/x/work.yaml            [--build-dir build]
    python3 -m core.build from-trace trace.json --target NAME     [--build-dir build] [--behaviors DIR]
    python3 -m core.build show       build/<work>
    python3 -m core.build bench      build/<work> [--trace trace.json] [--no-replay]
    python3 -m core.build run        build/<work> --request "..." [--param k=v] [--escalate auto|claude|codex|…] [--binder regex|agent]
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


def cmd_bench(args: argparse.Namespace) -> int:
    import os
    from core.build.bench import BENCH_ACTIVE_ENV, run_benchmark, write_report

    if os.environ.get(BENCH_ACTIVE_ENV):
        print("[bench] nested benchmark call skipped (a benchmark is already replaying this build)")
        return 0

    trace_path = Path(args.trace) if args.trace else Path(args.build_dir) / "trace.json"
    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    if "traces" in payload:
        payload = payload["traces"][0]
    trace = TraceIR.model_validate(payload.get("trace", payload))
    report = run_benchmark(args.build_dir, trace, replay=not args.no_replay)
    paths = write_report(report, args.out or args.build_dir)
    t = report.totals()
    print(f"[bench] {report.work}: tokens {t['recorded_tokens']:,} -> {t['compiled_tokens']:,} "
          f"(-{t['token_savings_pct']}%), wall {t['recorded_latency_ms']/1000:.1f}s -> {t['compiled_latency_ms']/1000:.2f}s"
          + (f" ({t['speedup_x']}x)" if t['speedup_x'] else "")
          + f", outputs reproduced {t['outputs_matched']}/{t['outputs_checked']}, "
          f"compiled/escalated actions {t['compiled_actions']}/{t['escalated_actions']}")
    for a in report.actions:
        print(f"  {a.action:20s} {a.tier:13s} tokens {a.recorded_tokens:>7,} -> {a.compiled_tokens:<6,} "
              f"latency {a.recorded_latency_ms/1000:6.1f}s -> {a.compiled_latency_ms/1000:5.2f}s  match {a.matches}")
    print(f"  report: {paths['markdown']}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from core.build.run import run_build

    params = dict(kv.split("=", 1) for kv in (args.param or []))
    report = run_build(args.build_dir, request=args.request, params=params or None,
                       escalate=args.escalate, binder=args.binder, out_dir=args.out, model=getattr(args, "model", None))
    t = report.totals()
    print(f"[run] {report.work}: params={json.dumps(report.params, ensure_ascii=False)} ({', '.join(f'{k}:{v}' for k, v in report.binding.items())})")
    print(f"  tokens {t['tokens']:,} (recorded session {t['recorded_tokens']:,}), wall {t['latency_ms']/1000:.1f}s "
          f"(recorded {t['recorded_latency_ms']/1000:.1f}s), steps code/escalated/needs-agent {t['code_steps']}/{t['escalated_steps']}/{t['needs_agent_steps']}")
    for s in report.steps:
        print(f"  {s.step_id:8s} {s.action:26s} {s.mode:18s} tokens {s.tokens:>7,} latency {s.latency_ms/1000:6.2f}s {'ok' if s.ok else 'FAIL'} {s.note}")
    print(f"  report: {Path(args.out or Path(args.build_dir) / 'runs') / 'RUN_REPORT.md'}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    manifest = json.loads((Path(args.build_dir) / "MANIFEST.json").read_text(encoding="utf-8"))
    print(json.dumps(manifest["by_tier"], indent=2, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m core.build", description="OpenWorkCompiler build backend")
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

    d = sub.add_parser("bench", help="Replay a build against the trace it came from: result, tokens, speed")
    d.add_argument("build_dir")
    d.add_argument("--trace", help="TraceIR JSON (default: <build_dir>/trace.json written at compile time)")
    d.add_argument("--no-replay", action="store_true", help="Only account costs; do not execute handlers")
    d.add_argument("--out", help="Directory for BENCHMARK.md / benchmark.json (default: build dir)")
    d.set_defaults(func=cmd_bench)

    e = sub.add_parser("run", help="Run the build for new inputs: front agent binds params, code runs free, rest escalates")
    e.add_argument("build_dir")
    e.add_argument("--request", help="Natural-language request the front agent binds parameters from")
    e.add_argument("--param", action="append", help="Explicit parameter, name=value (repeatable)")
    from core.agents import REGISTRY
    e.add_argument("--escalate", choices=["none", "auto", *REGISTRY], default="none",
                   help="Backend for steps that need an agent: auto picks the recorded agent or the first installed CLI")
    e.add_argument("--binder", choices=["regex", "agent", "codex"], default="regex", help="How the front agent extracts parameters")
    e.add_argument("--model", help="Model for the escalation backend")
    e.add_argument("--out", help="Directory for run reports (default: <build_dir>/runs)")
    e.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    from core import telemetry
    telemetry.notice("core.build")
    with telemetry.span("cli.core.build", command=getattr(args, "command", "")):
        return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
