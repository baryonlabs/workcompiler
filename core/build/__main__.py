"""CLI for the build backend.

    python3 -m core.build from-work  build/x/work.yaml            [--build-dir build]
    python3 -m core.build from-trace trace.json --target NAME     [--build-dir build] [--behaviors DIR]
    python3 -m core.build show       build/<work>
    python3 -m core.build bench      build/<work> [--trace trace.json] [--no-replay]
    python3 -m core.build run        build/<work> --request "..." [--param k=v] [--escalate auto|claude|codex|…] [--binder regex|agent]
    python3 -m core.build promote    build/<work> <action> [--model qwen2.5:7b] [--dry-run]   # frontier → local SLM under the quality gate
    python3 -m core.build demote     build/<work> <action>
    python3 -m core.build harden     build/<work> [--escalate auto|…] [--budget-tokens N]   # harness loop: bench→fix→re-bench until reproducible
    python3 -m core.build cache      list|clear build/<work> [--action a]   # escalate-once replay cache
    python3 -m core.build dataset    build/<work> <action>              # recorded + cache + fleet truth → train/valid jsonl
    python3 -m core.build train      build/<work> <action> [--base-model …] [--iters N]   # mlx-lm LoRA
    python3 -m core.build fleet-eval build/<work> <action> --model M [--base-url U]       # held-out gate pass rate
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
    if isinstance(payload, dict) and "traces" in payload:      # a build's trace.json wraps a list
        payload = payload["traces"][0]
    trace = TraceIR.model_validate(payload.get("trace", payload) if isinstance(payload, dict) else payload)
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
    from core.build.bench import (BENCH_ACTIVE_ENV, PRICES_ENV, attach_unique_tokens, classify_completion,
                                  report_from_dict, run_benchmark, write_report)
    from core.work_ir import load_work_ir

    if getattr(args, "prices", None):
        os.environ[PRICES_ENV] = args.prices

    if os.environ.get(BENCH_ACTIVE_ENV):
        print("[bench] nested benchmark call skipped (a benchmark is already replaying this build)")
        return 0

    trace_path = Path(args.trace) if args.trace else Path(args.build_dir) / "trace.json"
    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    if "traces" in payload:
        payload = payload["traces"][0]
    trace = TraceIR.model_validate(payload.get("trace", payload))
    if args.recompute_totals:
        # No replay: rebuild the report from the existing benchmark.json, refresh the
        # unique-token columns from the trace, and rewrite BENCHMARK.md / benchmark.json.
        bench_path = Path(args.build_dir) / "benchmark.json"
        report = attach_unique_tokens(report_from_dict(json.loads(bench_path.read_text(encoding="utf-8"))), trace)
        try:  # the dependency graph is the compile-time form of the work's invariants
            deps = load_work_ir(Path(args.build_dir) / "work.yaml").to_dict().get("dependencies") or {}
        except Exception:
            deps = {}
        classify_completion(report, deps)
        paths = write_report(report, args.out or args.build_dir, append_to_ledger=False)
    else:
        report = run_benchmark(args.build_dir, trace, replay=not args.no_replay)
        paths = write_report(report, args.out or args.build_dir)
    t = report.totals()
    print(f"[bench] {report.work}: unique tokens {t['recorded_tokens_unique']:,} -> {t['compiled_tokens']:,} "
          f"(-{t['savings_unique_pct']}%; cumulative-context sum {t['recorded_tokens']:,}, -{t['token_savings_pct']}%), "
          f"wall {t['recorded_latency_ms']/1000:.1f}s -> {t['compiled_latency_ms']/1000:.2f}s"
          + (f" ({t['speedup_x']}x)" if t['speedup_x'] else "")
          + f", outputs reproduced {t['outputs_matched']}/{t['outputs_checked']}, "
          f"compiled/escalated actions {t['compiled_actions']}/{t['escalated_actions']}")
    for a in report.actions:
        print(f"  {a.action:20s} {a.tier:13s} tokens {a.recorded_tokens_unique:>7,} -> {a.compiled_tokens:<6,} "
              f"latency {a.recorded_latency_ms/1000:6.1f}s -> {a.compiled_latency_ms/1000:5.2f}s  match {a.matches}")
    print(f"  report: {paths['markdown']}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from core.build.run import run_build

    params = dict(kv.split("=", 1) for kv in (args.param or []))
    report = run_build(args.build_dir, request=args.request, params=params or None,
                       escalate=args.escalate, binder=args.binder, out_dir=args.out, model=getattr(args, "model", None),
                       use_cache=not getattr(args, "no_cache", False))
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


def cmd_promote(args) -> int:
    from core.build.slm import SLMRuntime, promote

    rt = SLMRuntime.defaults(model=args.model, base_url=args.base_url)
    if args.min_quality is not None:
        rt.min_quality = args.min_quality
    if args.min_recall is not None:
        rt.min_recall = args.min_recall
    report = promote(args.build_dir, args.action, rt, dry_run=args.dry_run)
    t = report.totals()
    verdict = "PROMOTED" if report.promoted else ("would promote (dry run)" if args.dry_run and t["pass_rate"] >= rt.min_quality else "NOT promoted")
    print(f"[promote] {report.work}.{args.action} → slm ({rt.model} @ {rt.base_url}): {verdict}")
    print(f"  pass rate {t['pass_rate']:.0%} over {t['evaluations']} recorded example(s); tokens {t['recorded_tokens']:,} -> {t['slm_tokens']:,}"
          + (f" ({-t['token_savings_pct']:+.1f}%)" if t["token_savings_pct"] is not None else "")
          + f"; latency {t['recorded_latency_ms']/1000:.1f}s -> {t['slm_latency_ms']/1000:.1f}s")
    for e in report.evaluations:
        print(f"  {e.step_id:8s} {e.verdict.summary()}  tokens {e.result.tokens:,} latency {e.result.latency_ms/1000:.1f}s")
    print(f"  report: {Path(args.build_dir) / 'models' / 'slm' / args.action / 'PROMOTION.md'}")
    return 0 if (report.promoted or args.dry_run) else 1


def cmd_demote(args) -> int:
    from core.build.slm import demote

    info = demote(args.build_dir, args.action)
    print(f"[demote] {args.action} restored to {info['restored'].get('type', 'frontier_llm')}")
    return 0


def cmd_harden(args) -> int:
    from core.build.harden import harden

    escalator, backend_name = None, "none"
    if args.escalate != "none":
        from core.agents import as_escalator, resolve_backend
        agent = resolve_backend(args.escalate)
        escalator, backend_name = as_escalator(agent, model=getattr(args, "model", None)), agent.name
    report = harden(args.build_dir, escalator=escalator, backend_name=backend_name,
                    max_iters=args.max_iters, budget_tokens=args.budget_tokens)
    print(f"[harden] {report.work}: {report.final_matched}/{report.final_checked} reproduced · "
          f"{'converged' if report.converged else report.stopped_because} · fix tokens {report.tokens_total:,}")
    for it in report.iterations:
        print(f"  iter {it.number}: attempted {', '.join(it.attempted) or '-'} | accepted {', '.join(it.accepted) or '-'} | "
              f"reverted {', '.join(it.reverted) or '-'} | {it.score_before[0]}/{it.score_before[1]} → {it.score_after[0]}/{it.score_after[1]}")
    if report.inherent:
        print(f"  inherent (not chased): {', '.join(report.inherent)}")
    if report.needs_human:
        print(f"  needs a human: {', '.join(report.needs_human)}")
    print(f"  report: {Path(args.build_dir) / 'HARDEN.md'}")
    return 0 if report.converged or report.final_matched == report.final_checked else 1


def cmd_cache(args) -> int:
    from core.build.cache import clear, entries

    if args.op == "clear":
        print(f"[cache] removed {clear(args.build_dir, args.action)} entr(ies)")
        return 0
    rows = entries(args.build_dir)
    if not rows:
        print("[cache] empty")
        return 0
    print(f"{'action':28s} {'params':30s} {'source':16s} {'at':20s} files upstream")
    for e in rows:
        params = ",".join(f"{k}={v}" for k, v in (e.get("params") or {}).items())[:30]
        print(f"{e.get('action', '?'):28s} {params:30s} {e.get('source', '?'):16s} {e.get('at', '?'):20s} "
              f"{len(e.get('files') or {}):5d} {(e.get('upstream_sha') or '')[:8]}")
    return 0


def cmd_dataset(args) -> int:
    from core.build.dataset import build_dataset

    rep = build_dataset(args.build_dir, args.action,
                        holdout_customers=args.holdout.split(",") if args.holdout else None,
                        cot=getattr(args, "cot", False))
    print(f"[dataset] {args.action} ({rep.mode}): {rep.rows} rows "
          f"({', '.join(f'{k} {v}' for k, v in rep.sources.items())}); held out: {', '.join(rep.eval_customers) or '-'}")
    print(f"  train: {rep.train_path}\n  valid: {rep.valid_path}")
    return 0


def cmd_train(args) -> int:
    import subprocess

    from core.build.dataset import build_dataset
    from core.build.slm import slm_dir

    rep = build_dataset(args.build_dir, args.action)
    data_dir = Path(rep.train_path).parent
    adapter = slm_dir(args.build_dir, args.action) / "adapter"
    argv = ["mlx_lm.lora", "--model", args.base_model, "--train", "--data", str(data_dir),
            "--adapter-path", str(adapter), "--iters", str(args.iters), "--batch-size", str(args.batch_size),
            "--num-layers", str(args.num_layers), "--max-seq-length", "4096",
            "--mask-prompt", "--learning-rate", str(args.learning_rate)]
    print(f"[train] {args.action}: {rep.rows} rows → LoRA on {args.base_model} ({args.iters} iters)")
    print("  $ " + " ".join(argv))
    proc = subprocess.run(argv)
    if proc.returncode:
        return proc.returncode
    meta = {"base_model": args.base_model, "adapter": str(adapter), "iters": args.iters,
            "rows": rep.rows, "sources": rep.sources, "holdout": rep.eval_customers,
            "at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S")}
    (adapter.parent / "training.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"[train] adapter: {adapter}\n  serve: mlx_lm.server --model {args.base_model} --adapter-path {adapter} --port 8080")
    return 0


def cmd_fleet_eval(args) -> int:
    from core.build.dataset import DatasetReport, eval_markdown, evaluate_fleet, fleet_dir
    from core.build.slm import SLMRuntime, slm_dir

    root = Path(args.build_dir)
    data_dir = slm_dir(root, args.action) / "data"
    eval_info = json.loads((data_dir / "eval.json").read_text(encoding="utf-8"))
    customers = args.customers.split(",") if args.customers else eval_info["holdout_customers"]
    rt = SLMRuntime.defaults(model=args.model, base_url=args.base_url)
    rt.max_tokens = 3600
    ev = evaluate_fleet(root, args.action, rt, customers)
    t = ev.totals()
    print(f"[fleet-eval] {args.action} · {t['model']}: {t['passed']}/{t['customers']} pass ({t['pass_rate']:.0%}), "
          f"avg {t['avg_tokens']:,} tokens · {t['avg_latency_ms']/1000:.1f}s")
    for r in ev.results:
        print(f"  {r['customer']}: {r['gate']}")
    history_path = slm_dir(root, args.action) / "fleet_evals.json"
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else []
    history = [h for h in history if h["totals"]["model"] != (args.label or t["model"])]
    t["model"] = args.label or t["model"]
    history.append({"totals": t, "results": ev.results})
    history_path.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rep = DatasetReport(action=args.action, mode="", rows=sum(eval_info.get("sources", {}).values()), sources=eval_info.get("sources", {}))

    class _E:
        def __init__(self, h): self._t, self.results = h["totals"], h["results"]
        def totals(self): return self._t
        model = property(lambda self: self._t["model"])

    md = eval_markdown(args.action, [_E(h) for h in history], customers, rep)
    (slm_dir(root, args.action) / "TRAINING.md").write_text(md, encoding="utf-8")
    print(f"  report: {slm_dir(root, args.action) / 'TRAINING.md'}")
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
    d.add_argument("--prices", help="JSON price table {model: {input, output, cache_read}} in USD per 1M tokens "
                                    "(or $OWC_PRICES); without it no cost figure is reported")
    d.add_argument("--recompute-totals", action="store_true",
                   help="No replay: recompute totals (incl. unique-token columns) from trace.json + the existing benchmark.json and rewrite the report")
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
    e.add_argument("--no-cache", action="store_true", help="Ignore cached escalation results for this run")
    e.add_argument("--out", help="Directory for run reports (default: <build_dir>/runs)")
    e.set_defaults(func=cmd_run)

    f = sub.add_parser("promote", help="Evaluate a small local model on an action's recorded examples and, if the gate passes, switch the action to the SLM tier")
    f.add_argument("build_dir")
    f.add_argument("action")
    f.add_argument("--to", choices=["slm"], default="slm")
    f.add_argument("--model", help="Model served by the OpenAI-compatible endpoint (default: $OPENWORKCOMPILER_SLM_MODEL or qwen2.5:3b)")
    f.add_argument("--base-url", help="Endpoint (default: $OPENWORKCOMPILER_SLM_BASE_URL or http://127.0.0.1:11434/v1 — Ollama)")
    f.add_argument("--min-quality", type=float, help="Fraction of recorded examples that must pass the gate (default 0.9)")
    f.add_argument("--min-recall", type=float, help="Anchor-fact recall each example must reach (default 0.9)")
    f.add_argument("--dry-run", action="store_true", help="Evaluate and write PROMOTION.md without changing the build")
    f.set_defaults(func=cmd_promote)

    g = sub.add_parser("demote", help="Roll a promoted action back to its previous executor")
    g.add_argument("build_dir")
    g.add_argument("action")
    g.set_defaults(func=cmd_demote)

    m = sub.add_parser("harden", help="Compile-time harness loop: bench → agent fixes build artifacts → re-bench, until reproducible")
    m.add_argument("build_dir")
    from core.agents import REGISTRY as _REG
    m.add_argument("--escalate", choices=["none", "auto", *_REG], default="none", help="Fix backend (producer); reviewer is the deterministic bench")
    m.add_argument("--model", help="Model for the fix backend")
    m.add_argument("--max-iters", type=int, default=3)
    m.add_argument("--budget-tokens", type=int, default=0, help="Stop when fix-token spend reaches this (0 = unlimited)")
    m.set_defaults(func=cmd_harden)

    h = sub.add_parser("cache", help="Escalation cache of a build: list entries or clear them")
    h.add_argument("op", choices=["list", "clear"])
    h.add_argument("build_dir")
    h.add_argument("--action", help="clear only this action's entries")
    h.set_defaults(func=cmd_cache)

    i = sub.add_parser("dataset", help="Build the action's supervised dataset (recorded + cache + fleet truth)")
    i.add_argument("build_dir"); i.add_argument("action")
    i.add_argument("--holdout", help="Comma-separated customers to pin as the held-out evaluation set")
    i.add_argument("--cot", action="store_true",
                   help="Prefix fleet targets with a deterministic computation walkthrough (writes to data-cot/)")
    i.set_defaults(func=cmd_dataset)

    j = sub.add_parser("train", help="LoRA-train a local base model on the action's dataset (mlx-lm, Apple Silicon)")
    j.add_argument("build_dir"); j.add_argument("action")
    j.add_argument("--base-model", default="mlx-community/Qwen2.5-3B-Instruct-4bit")
    j.add_argument("--iters", type=int, default=400)
    j.add_argument("--batch-size", type=int, default=1)
    j.add_argument("--num-layers", type=int, default=8)
    j.add_argument("--learning-rate", type=float, default=1e-4)
    j.set_defaults(func=cmd_train)

    k = sub.add_parser("fleet-eval", help="Gate a candidate model against held-out fleet customers (deterministic answer key)")
    k.add_argument("build_dir"); k.add_argument("action")
    k.add_argument("--model", required=True)
    k.add_argument("--base-url", help="OpenAI-compatible endpoint (default: Ollama)")
    k.add_argument("--customers", help="Comma-separated override of the held-out set")
    k.add_argument("--label", help="Name for the report row (default: model id)")
    k.set_defaults(func=cmd_fleet_eval)

    args = parser.parse_args(argv)
    from core import telemetry
    telemetry.notice("core.build")
    with telemetry.span("cli.core.build", command=getattr(args, "command", "")):
        return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
