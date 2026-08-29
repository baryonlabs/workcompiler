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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "work": self.work, "build_dir": self.build_dir, "run_id": self.run_id,
            "source_agent": self.source_agent, "totals": self.totals(),
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
        lines += ["", "## Outputs", ""]
        for a in self.actions:
            for s in a.steps:
                lines += [f"### `{a.action}` · {s.step_id} — {s.executor_used}" + (f" ({s.note})" if s.note else ""), ""]
                lines += ["recorded:", "", "```", _clip(s.recorded_output, 600), "```", ""]
                lines += ["compiled:", "", "```", _clip(s.compiled_output, 600), "```", ""]
        if self.final_answer:
            lines += ["## Final answer of the recorded agent", "", "```", _clip(self.final_answer, 1200), "```", ""]
        return "\n".join(lines)


BENCH_ACTIVE_ENV = "OPENWORKFLOW_BENCH_ACTIVE"
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


def _step_tokens(step: TraceStep) -> int:
    usage = getattr(step, "token_usage", None)
    if usage is None:
        return 0
    if hasattr(usage, "total_tokens"):
        return int(usage.total_tokens or 0)
    return int((usage or {}).get("total_tokens", 0))


def _group_steps(trace: TraceIR) -> Dict[str, List[TraceStep]]:
    from core.compiler.compiler import WorkCompiler

    norm = WorkCompiler._normalize_action_name
    grouped: Dict[str, List[TraceStep]] = {}
    for step in trace.steps:
        if step.action:
            grouped.setdefault(norm(WorkCompiler.__new__(WorkCompiler), step.action), []).append(step)
    return grouped


def run_benchmark(build_dir: Path | str, trace: TraceIR, replay: bool = True, engine: Any = None) -> BenchReport:
    """Replay the build's compiled tiers against ``trace`` and compare cost, speed and output."""
    from core.runtime.engine import DurableRuntimeEngine

    root = Path(build_dir)
    work_ir = load_work_ir(root / "work.yaml")
    engine = engine or DurableRuntimeEngine(auto_checkpoint=False)
    load_build_into_engine(engine, root)
    executors = work_ir.to_dict().get("executors", {})
    grouped = _group_steps(trace)

    report = BenchReport(work=work_ir.work, build_dir=str(root), run_id=trace.run_id, source_agent=trace.source_agent)

    for action in work_ir.actions:
        tier = str(executors.get(action, {}).get("type", "frontier_llm"))
        bench = ActionBench(action=action, tier=tier)
        for step in grouped.get(action, []):
            rec_out = _recorded_output(step)
            rec_tokens = _step_tokens(step)
            rec_latency = float(getattr(step, "latency_ms", 0.0) or 0.0)
            inputs = step.input if isinstance(step.input, dict) else {}
            executable = tier in ("code", "rule", "http")

            if executable and replay and _is_self_referential(inputs):
                bench.steps.append(StepBench(step.step_id, rec_tokens, rec_latency, 0, 0.0, f"{tier} (skipped)",
                                             None, rec_out, "", "self-referential step (benchmarks/recompiles this build) not replayed"))
            elif executable and replay:
                t0 = time.perf_counter()
                os.environ[BENCH_ACTIVE_ENV] = "1"
                try:
                    result = engine.get_executor(tier).execute(action, dict(inputs))
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
                if has_recorded:
                    match, cmp_note = _compare(rec_out, comp_out)
                    note = note or cmp_note
                else:
                    note = "no recorded tool output to compare"
                if out.get("exit_code") not in (None, 0):
                    note = f"exit_code={out.get('exit_code')}"
                bench.steps.append(StepBench(step.step_id, rec_tokens, rec_latency, 0, elapsed,
                                             f"{tier}:{root.name}/handlers" if tier == "code" else tier,
                                             match, rec_out, comp_out, note))
            elif executable:
                bench.steps.append(StepBench(step.step_id, rec_tokens, rec_latency, 0, 0.0, f"{tier} (replay disabled)",
                                             None, rec_out, "", "not replayed"))
            else:
                reason = {"ml": "model not trained yet → fallback", "slm": "SLM not trained yet → fallback"}.get(tier, "")
                bench.steps.append(StepBench(step.step_id, rec_tokens, rec_latency, rec_tokens, rec_latency,
                                             f"escalated:{tier}", None, rec_out, rec_out,
                                             reason or "kept recorded cost (frontier/human tier)"))
        report.actions.append(bench)

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
    return {"markdown": str(out / "BENCHMARK.md"), "json": str(out / "benchmark.json")}
