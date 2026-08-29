"""Benchmark a compiled build against the agent trace it was compiled from.

For every action the report answers three questions the README claims hinge on:

* **result** — does re-running the compiled artifact reproduce what the agent observed?
* **tokens** — how many LLM tokens does the compiled path spend (code/rule tiers: 0)?
* **speed**  — wall-clock of the compiled executor vs. the recorded agent round-trip.

Actions whose tier still needs a model (frontier_llm, untrained ml/slm, human) are
reported as *escalated*: they keep the recorded cost, which is exactly what the
runtime would pay before the SLM/ML candidates are trained and promoted.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.build.loader import load_build_into_engine
from core import telemetry
from core.work_ir import TraceIR, TraceStep, load_work_ir, normalize_tool_output


@dataclass
class StepBench:
    step_id: str
    recorded_tokens: int
    recorded_latency_ms: float
    compiled_tokens: int
    compiled_latency_ms: float
    executor_used: str
    output_match: Optional[bool]
    recorded_output: str
    compiled_output: str
    note: str = ""
    recorded_model: str = ""          # model that produced the recorded step (from the trace)
    compiled_model: str = ""          # what ran it in the build: "code", "rule", or a model id
    recorded_prompt_tokens: int = 0
    recorded_completion_tokens: int = 0
    recorded_cached_tokens: int = 0   # part of the prompt served from the provider's cache (billed cheaper)


@dataclass
class ActionBench:
    action: str
    tier: str
    steps: List[StepBench] = field(default_factory=list)

    @property
    def recorded_tokens(self) -> int:
        return sum(s.recorded_tokens for s in self.steps)

    @property
    def compiled_tokens(self) -> int:
        return sum(s.compiled_tokens for s in self.steps)

    @property
    def recorded_latency_ms(self) -> float:
        return sum(s.recorded_latency_ms for s in self.steps)

    @property
    def compiled_latency_ms(self) -> float:
        return sum(s.compiled_latency_ms for s in self.steps)

    @property
    def matches(self) -> str:
        checked = [s.output_match for s in self.steps if s.output_match is not None]
        if not checked:
            return "n/a"
        return f"{sum(1 for m in checked if m)}/{len(checked)}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action, "tier": self.tier,
            "recorded_tokens": self.recorded_tokens, "compiled_tokens": self.compiled_tokens,
            "recorded_latency_ms": round(self.recorded_latency_ms, 1),
            "compiled_latency_ms": round(self.compiled_latency_ms, 1),
            "output_matches": self.matches,
            "steps": [asdict(s) for s in self.steps],
        }


@dataclass
class BenchReport:
    work: str
    build_dir: str
    run_id: str
    source_agent: str
    actions: List[ActionBench] = field(default_factory=list)
    final_answer: str = ""

    def totals(self) -> Dict[str, Any]:
        rt = sum(a.recorded_tokens for a in self.actions)
        ct = sum(a.compiled_tokens for a in self.actions)
        rl = sum(a.recorded_latency_ms for a in self.actions)
        cl = sum(a.compiled_latency_ms for a in self.actions)
        checked = [s for a in self.actions for s in a.steps if s.output_match is not None]
        return {
            "recorded_tokens": rt, "compiled_tokens": ct,
            "token_savings_pct": round(100.0 * (rt - ct) / rt, 1) if rt else 0.0,
            "recorded_latency_ms": round(rl, 1), "compiled_latency_ms": round(cl, 1),
            "speedup_x": round(rl / cl, 1) if cl else None,
            "outputs_checked": len(checked),
            "outputs_matched": sum(1 for s in checked if s.output_match),
            "compiled_actions": sum(1 for a in self.actions if a.tier in ("code", "rule", "http")),
            "escalated_actions": sum(1 for a in self.actions if a.tier not in ("code", "rule", "http")),
        }

    def by_model(self) -> Dict[str, tuple[int, int]]:
        """{model-or-executor: (recorded tokens, compiled tokens)} — the per-model accounting."""
        out: Dict[str, List[int]] = {}
        for a in self.actions:
            for s in a.steps:
                rec_key = s.recorded_model or "?"
                out.setdefault(rec_key, [0, 0])[0] += s.recorded_tokens
                comp_key = s.compiled_model or "?"
                out.setdefault(comp_key, [0, 0])[1] += s.compiled_tokens
        return {k: (v[0], v[1]) for k, v in out.items()}

    def ledger_rows(self) -> List[Dict[str, Any]]:
        return [{"step": s.step_id, "action": a.action, "recorded_model": s.recorded_model,
                 "recorded_prompt_tokens": s.recorded_prompt_tokens, "recorded_cached_tokens": s.recorded_cached_tokens,
                 "recorded_completion_tokens": s.recorded_completion_tokens,
                 "recorded_tokens": s.recorded_tokens, "compiled_executor": s.compiled_model, "compiled_tokens": s.compiled_tokens}
                for a in self.actions for s in a.steps]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "work": self.work, "build_dir": self.build_dir, "run_id": self.run_id,
            "source_agent": self.source_agent, "totals": self.totals(),
            "by_model": {k: {"recorded_tokens": v[0], "compiled_tokens": v[1]} for k, v in self.by_model().items()},
            "ledger": self.ledger_rows(),
            "actions": [a.to_dict() for a in self.actions], "final_answer": self.final_answer,
        }

    def to_markdown(self) -> str:
        t = self.totals()
        lines = [
            f"# Benchmark — `{self.work}`",
            "",
            f"Recorded agent session `{self.run_id}` (`{self.source_agent}`) vs. compiled build `{self.build_dir}`.",
            "",
            "| | recorded (agent) | compiled (build) | delta |",
            "| :-- | --: | --: | --: |",
            f"| LLM tokens | {t['recorded_tokens']:,} | {t['compiled_tokens']:,} | −{t['token_savings_pct']}% |",
            f"| wall time | {t['recorded_latency_ms']/1000:.1f} s | {t['compiled_latency_ms']/1000:.2f} s | "
            + (f"{t['speedup_x']}× faster" if t['speedup_x'] else "n/a") + " |",
            f"| outputs reproduced | — | {t['outputs_matched']}/{t['outputs_checked']} | |",
            f"| actions compiled / escalated | — | {t['compiled_actions']} / {t['escalated_actions']} | |",
            "",
            "## Per action",
            "",
            "| action | tier | executor used | tokens rec → comp | latency rec → comp | output match |",
            "| :-- | :-- | :-- | --: | --: | :-- |",
        ]
        for a in self.actions:
            used = ", ".join(sorted({s.executor_used for s in a.steps}))
            lines.append(
                f"| `{a.action}` | {a.tier} | {used} | {a.recorded_tokens:,} → {a.compiled_tokens:,} | "
                f"{a.recorded_latency_ms/1000:.1f} s → {a.compiled_latency_ms/1000:.2f} s | {a.matches} |"
            )
        lines += ["", "## Token ledger — who spent what", "",
                  "Every recorded step, the model that produced it, and what runs it in the compiled build.", "",
                  "| step | action | recorded model | prompt (cached) + completion = total | compiled executor | compiled tokens |",
                  "| :-- | :-- | :-- | --: | :-- | --: |"]
        for a in self.actions:
            for s in a.steps:
                lines.append(f"| {s.step_id} | `{a.action}` | {s.recorded_model or '?'} | "
                             f"{s.recorded_prompt_tokens:,} ({s.recorded_cached_tokens:,}) + {s.recorded_completion_tokens:,} = {s.recorded_tokens:,} | "
                             f"{s.compiled_model} | {s.compiled_tokens:,} |")
        cached = sum(s.recorded_cached_tokens for a in self.actions for s in a.steps)
        lines += ["", "| model / executor | recorded tokens | compiled tokens |", "| :-- | --: | --: |"]
        for key, (rt, ct) in self.by_model().items():
            lines.append(f"| {key} | {rt:,} | {ct:,} |")
        lines += ["", f"Recorded prompt tokens served from the provider cache: {cached:,} (counted in the totals above; billed at the cached rate).",
                  "Totals are the sum of every request's usage as reported by the provider — each agent turn re-sends its whole context, which is why they exceed the agent CLI's own 'tokens used' figure."]
        lines += ["", "## Outputs", ""]
        for a in self.actions:
            for s in a.steps:
                lines += [f"### `{a.action}` · {s.step_id} — {s.executor_used}" + (f" ({s.note})" if s.note else ""), ""]
                lines += ["recorded:", "", "```", _clip(s.recorded_output, 600), "```", ""]
                lines += ["compiled:", "", "```", _clip(s.compiled_output, 600), "```", ""]
        if self.final_answer:
            lines += ["## Final answer of the recorded agent", "", "```", _clip(self.final_answer, 1200), "```", ""]
        return "\n".join(lines)


BENCH_ACTIVE_ENV = "OPENWORKCOMPILER_BENCH_ACTIVE"
_SELF_REFERENTIAL_MARKERS = ("core.build bench", "/v1/workcompiler/compile")


def _is_self_referential(inputs: Dict[str, Any]) -> bool:
    """True for recorded commands that would benchmark or recompile the build under test."""
    cmds = inputs.get("cmds") or ([inputs["cmd"]] if inputs.get("cmd") else [])
    return any(marker in str(c) for c in cmds for marker in _SELF_REFERENTIAL_MARKERS)


def _clip(text: str, n: int) -> str:
    text = text or ""
    return text if len(text) <= n else text[:n] + f"\n… ({len(text) - n} more chars)"


def _string_leaves(value: Any) -> List[str]:
    if isinstance(value, dict):
        return [leaf for v in value.values() for leaf in _string_leaves(v)]
    if isinstance(value, list):
        return [leaf for v in value for leaf in _string_leaves(v)]
    return [value] if isinstance(value, str) else []


def _lines(text: Any) -> List[str]:
    """Comparable line sequence of an output.

    Agents sometimes hand back stdout re-packed as JSON (``{"tree": "...", "work_yaml": "..."}``);
    the string leaves of such an object are unwrapped so they compare against raw stdout.
    """
    raw = str(text or "").strip()
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    if isinstance(parsed, (dict, list)):
        leaves = _string_leaves(parsed)
        if leaves:
            raw = "\n".join(leaves)
    return [line.rstrip() for line in raw.splitlines() if line.strip()]


def _norm(text: Any) -> str:
    return "\n".join(_lines(text))


def _verify_patch_files(patch: str, build_root: Path) -> tuple[bool, str]:
    """After replaying an apply_patch handler, check the files on disk equal the recorded patch."""
    cwd = str(Path.cwd().resolve()) + "/"
    ok, checked = True, 0
    current = None
    blocks: List[tuple[str, str, List[str]]] = []
    for line in patch.replace(cwd, "").splitlines():
        if line.startswith("*** Begin Patch") or line.startswith("*** End Patch"):
            continue
        if line.startswith("*** "):
            op, _, path = line[4:].partition(" File: ")
            current = (op, path.strip(), [])
            blocks.append(current)
        elif current is not None:
            current[2].append(line)
    for op, path, lines in blocks:
        if op != "Add":
            continue
        checked += 1
        expected = "\n".join(l[1:] if l.startswith("+") else l for l in lines) + "\n"
        actual = Path(path).read_text(encoding="utf-8") if Path(path).exists() else None
        ok = ok and actual == expected
    return (ok and checked > 0), f"{checked} file(s) verified on disk" if ok else "written file differs from recorded patch"


def _compare(recorded: str, compiled: str) -> tuple[bool, str]:
    """(match, note): exact line sequence first, then order-insensitive line multiset."""
    rec, comp = _lines(recorded), _lines(compiled)
    if rec == comp:
        return True, ""
    if sorted(rec) == sorted(comp):
        return True, "same lines, different order"
    return False, ""


def _recorded_output(step: TraceStep) -> str:
    out = step.output if isinstance(step.output, dict) else {}
    if out.get("tool_result") is not None:
        return normalize_tool_output(out["tool_result"])
    return str(out.get("content") or "")  # assistant text only; never compared against tool output


def _step_model(step: TraceStep) -> str:
    return str(getattr(step, "model", "") or "")


def _step_token_split(step: TraceStep) -> tuple[int, int]:
    usage = getattr(step, "token_usage", None)
    if usage is None:
        return 0, 0
    if hasattr(usage, "prompt_tokens"):
        return int(usage.prompt_tokens or 0), int(usage.completion_tokens or 0)
    return int((usage or {}).get("prompt_tokens", 0)), int((usage or {}).get("completion_tokens", 0))


def _step_cached(step: TraceStep) -> int:
    return int(getattr(step, "cached_tokens", 0) or 0)


def _step_tokens(step: TraceStep) -> int:
    usage = getattr(step, "token_usage", None)
    if usage is None:
        return 0
    if hasattr(usage, "total_tokens"):
        return int(usage.total_tokens or 0)
    return int((usage or {}).get("total_tokens", 0))


def _normalizer():
    from core.compiler.compiler import WorkCompiler

    compiler = WorkCompiler.__new__(WorkCompiler)
    return lambda name: WorkCompiler._normalize_action_name(compiler, name)


def run_benchmark(build_dir: Path | str, trace: TraceIR, replay: bool = True, engine: Any = None) -> BenchReport:
    """Replay the build's compiled tiers against ``trace`` and compare cost, speed and output."""
    from core.runtime.engine import DurableRuntimeEngine

    root = Path(build_dir)
    work_ir = load_work_ir(root / "work.yaml")
    engine = engine or DurableRuntimeEngine(auto_checkpoint=False)
    load_build_into_engine(engine, root)
    executors = work_ir.to_dict().get("executors", {})

    report = BenchReport(work=work_ir.work, build_dir=str(root), run_id=trace.run_id, source_agent=trace.source_agent)
    benches: Dict[str, ActionBench] = {
        action: ActionBench(action=action, tier=str(executors.get(action, {}).get("type", "frontier_llm")))
        for action in work_ir.actions
    }
    norm = _normalizer()

    # Replay in the order the agent worked: later steps may read files earlier steps wrote.
    for step in trace.steps:
        action = norm(step.action) if step.action else ""
        bench = benches.get(action)
        if bench is None:
            continue
        tier = bench.tier
        rec_out = _recorded_output(step)
        rec_tokens = _step_tokens(step)
        rec_latency = float(getattr(step, "latency_ms", 0.0) or 0.0)
        inputs = step.input if isinstance(step.input, dict) else {}
        executable = tier in ("code", "rule", "http")

        if executable and replay and _is_self_referential(inputs):
            pt, ct = _step_token_split(step)
            bench.steps.append(StepBench(step.step_id, rec_tokens, rec_latency, 0, 0.0, f"{tier} (skipped)",
                                         None, rec_out, "", "self-referential step (benchmarks/recompiles this build) not replayed",
                                         recorded_model=_step_model(step), compiled_model="skipped",
                                         recorded_prompt_tokens=pt, recorded_completion_tokens=ct, recorded_cached_tokens=_step_cached(step)))
        elif executable and replay:
            t0 = time.perf_counter()
            os.environ[BENCH_ACTIVE_ENV] = "1"
            try:
                with telemetry.span("bench.step", work=work_ir.work, run_id=trace.run_id, step=step.step_id,
                                    action=action, tier=tier, recorded_model=_step_model(step),
                                    recorded_tokens=rec_tokens) as tspan:
                    result = engine.get_executor(tier).execute(action, dict(inputs))
                    tspan["success"] = bool(result.success)
            finally:
                os.environ.pop(BENCH_ACTIVE_ENV, None)
            elapsed = (time.perf_counter() - t0) * 1000.0
            out = result.output if isinstance(result.output, dict) else {"value": result.output}
            comp_out = str(out.get("stdout") if "stdout" in out else out.get("content") or json.dumps(out, ensure_ascii=False, default=str))
            if not result.success:
                comp_out = f"ERROR: {result.error}"
            has_recorded = isinstance(step.output, dict) and step.output.get("tool_result") is not None
            match: Optional[bool] = None
            note = "" if result.success else "executor failed"
            if isinstance(inputs.get("patch"), str):
                match, cmp_note = _verify_patch_files(inputs["patch"], root)
                rec_out = "(files written by the agent's apply_patch)"
                note = note or cmp_note
            elif has_recorded:
                match, cmp_note = _compare(rec_out, comp_out)
                note = note or cmp_note
            else:
                note = "no recorded tool output to compare"
            if out.get("exit_code") not in (None, 0):
                note = (note + "; " if note else "") + f"exit_code={out.get('exit_code')}"
            pt, ct = _step_token_split(step)
            bench.steps.append(StepBench(step.step_id, rec_tokens, rec_latency, 0, elapsed,
                                         f"{tier}:{root.name}/handlers" if tier == "code" else tier,
                                         match, rec_out, comp_out, note,
                                         recorded_model=_step_model(step), compiled_model=tier,
                                         recorded_prompt_tokens=pt, recorded_completion_tokens=ct, recorded_cached_tokens=_step_cached(step)))
        elif executable:
            pt, ct = _step_token_split(step)
            bench.steps.append(StepBench(step.step_id, rec_tokens, rec_latency, 0, 0.0, f"{tier} (replay disabled)",
                                         None, rec_out, "", "not replayed", recorded_model=_step_model(step),
                                         compiled_model=tier, recorded_prompt_tokens=pt, recorded_completion_tokens=ct, recorded_cached_tokens=_step_cached(step)))
        else:
            reason = {"ml": "model not trained yet → fallback", "slm": "SLM not trained yet → fallback"}.get(tier, "")
            pt, ct = _step_token_split(step)
            bench.steps.append(StepBench(step.step_id, rec_tokens, rec_latency, rec_tokens, rec_latency,
                                         f"escalated:{tier}", None, rec_out, rec_out,
                                         reason or "kept recorded cost (frontier/human tier)",
                                         recorded_model=_step_model(step), compiled_model=_step_model(step) or tier,
                                         recorded_prompt_tokens=pt, recorded_completion_tokens=ct, recorded_cached_tokens=_step_cached(step)))

    report.actions = [benches[a] for a in work_ir.actions]
    t = report.totals()
    telemetry.event("bench.report", work=work_ir.work, run_id=trace.run_id, recorded_tokens=t["recorded_tokens"],
                    compiled_tokens=t["compiled_tokens"], token_savings_pct=t["token_savings_pct"],
                    speedup_x=t["speedup_x"], outputs_matched=t["outputs_matched"], outputs_checked=t["outputs_checked"])

    for step in reversed(trace.steps):
        out = step.output if isinstance(step.output, dict) else {}
        if out.get("content") and not out.get("tool_calls"):
            report.final_answer = str(out["content"])
            break
    return report


def write_report(report: BenchReport, out_dir: Path | str) -> Dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "BENCHMARK.md").write_text(report.to_markdown(), encoding="utf-8")
    (out / "benchmark.json").write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    append_ledger(out, "bench", report.run_id, report.ledger_rows())
    return {"markdown": str(out / "BENCHMARK.md"), "json": str(out / "benchmark.json")}


def append_ledger(out_dir: Path | str, kind: str, run_id: str, rows: List[Dict[str, Any]]) -> Path:
    """Append one JSON line per step to ``ledger.jsonl`` — the cumulative token/model history of a build."""
    path = Path(out_dir) / "ledger.jsonl"
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps({"at": stamp, "kind": kind, "run_id": run_id, **row}, ensure_ascii=False) + "\n")
    return path
