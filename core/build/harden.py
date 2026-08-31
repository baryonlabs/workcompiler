"""Compile-time harness loop: raise a build's completeness before it ships.

The harness/agent-team idea (specialists + reviewer + orchestrator with verification loops —
cf. revfactory/harness's Producer-Reviewer pattern) applied at *compiler time*, with one twist
that this codebase can afford: **the reviewer is deterministic**. The benchmark replays the build
against its own trace, so "did the fix help?" is not another LLM's opinion — it is output equality,
token and latency numbers.

Loop (Supervisor = this module, Producer = a coding-agent backend, Reviewer = the bench):

    bench → failure list → for each failure: snapshot artifacts → agent edits the build
    (handler/prompt files only) → re-bench → keep the fix only if the score improved,
    otherwise restore the snapshot → iterate until clean, stalled, or budget exhausted.

Failures the loop will not chase (marked ``inherent``): outputs that differ per run by nature
(timestamps, live listings) — detected by note/content heuristics and reported, not "fixed" into
lies. Everything is written to ``HARDEN.md`` as the loop transcript.

Long-horizon governance (cf. huangruiteng/loopx — durable control state, bounded turns, human as
final authority): attempt history persists in ``harden.json`` keyed by the failure's signature, so a
re-run never re-spends budget on a fix that already failed for the same reason; ``budget_tokens``
bounds the loop; whatever remains unresolved lands in an explicit ``needs_human`` gate list instead
of a vague retry.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core import telemetry
from core.build.bench import _strip_read_numbers, run_benchmark
from core.work_ir import TraceIR, load_work_ir

Escalator = Callable[[str, Dict[str, Any]], Dict[str, Any]]

# month abbreviations need a word boundary on the left and no letter on the right — otherwise
# "Decision"/"Margin" (substring) and "September" ("Sep" prefix) get misclassified as run-dependent
_INHERENT_RE = re.compile(
    r"\b\d{2}:\d{2}\b|\btotal \d+\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(?![A-Za-z])")


@dataclass
class Failure:
    action: str
    step_id: str
    executor: str
    note: str
    recorded: str
    replayed: str
    inherent: bool = False

    def summary(self) -> str:
        return f"{self.action} ({self.step_id}): {self.note or 'output mismatch'}"

    @property
    def signature(self) -> str:
        """Stable id of *this* failure mode — action + hashes of both outputs' first lines."""
        h = hashlib.sha1()
        h.update(self.action.encode())
        h.update("\n".join(self.recorded.splitlines()[:5]).encode())
        h.update("\n".join(self.replayed.splitlines()[:5]).encode())
        return h.hexdigest()[:12]


@dataclass
class Iteration:
    number: int
    failures_before: int
    attempted: List[str] = field(default_factory=list)
    accepted: List[str] = field(default_factory=list)
    reverted: List[str] = field(default_factory=list)
    tokens_spent: int = 0
    score_before: Tuple[int, int] = (0, 0)      # (matched, checked)
    score_after: Tuple[int, int] = (0, 0)


@dataclass
class HardenReport:
    work: str
    build_dir: str
    iterations: List[Iteration] = field(default_factory=list)
    final_matched: int = 0
    final_checked: int = 0
    inherent: List[str] = field(default_factory=list)
    converged: bool = False
    backend: str = "none"
    needs_human: List[str] = field(default_factory=list)
    tokens_total: int = 0
    budget_tokens: int = 0
    stopped_because: str = ""

    def to_markdown(self) -> str:
        lines = [f"# Harden — `{self.work}`", "",
                 f"Compile-time harness loop (producer: `{self.backend}` · reviewer: deterministic benchmark).", "",
                 f"**Result: {self.final_matched}/{self.final_checked} outputs reproduced"
                 + (" — converged" if self.converged else " — budget/progress limit reached") + ".**", ""]
        if self.stopped_because:
            lines += [f"Stop reason: {self.stopped_because}. Fix tokens spent: {self.tokens_total:,}"
                      + (f" / budget {self.budget_tokens:,}" if self.budget_tokens else "") + ".", ""]
        if self.inherent:
            lines += ["Inherently run-dependent outputs (reported, not chased): " + ", ".join(f"`{a}`" for a in self.inherent), ""]
        if self.needs_human:
            lines += ["**Needs a human** (explicit gate — automated fixes exhausted or excluded): "
                      + ", ".join(f"`{a}`" for a in self.needs_human), ""]
        lines += ["| iter | failures | attempted | accepted | reverted | fix tokens | score |", "| --: | --: | :-- | :-- | :-- | --: | :-- |"]
        for it in self.iterations:
            lines.append(f"| {it.number} | {it.failures_before} | {', '.join(it.attempted) or '—'} | "
                         f"{', '.join(it.accepted) or '—'} | {', '.join(it.reverted) or '—'} | {it.tokens_spent:,} | "
                         f"{it.score_before[0]}/{it.score_before[1]} → {it.score_after[0]}/{it.score_after[1]} |")
        return "\n".join(lines) + "\n"


def _load_trace(root: Path) -> TraceIR:
    payload = json.loads((root / "trace.json").read_text(encoding="utf-8"))
    return TraceIR.model_validate(payload["traces"][0] if "traces" in payload else payload)


def _failures(bench_report) -> Tuple[List[Failure], Tuple[int, int]]:
    out: List[Failure] = []
    matched = checked = 0
    for action in bench_report.actions:
        for step in action.steps:
            if step.output_match is None:
                continue
            checked += 1
            if step.output_match:
                matched += 1
                continue
            inherent = bool(_INHERENT_RE.search(step.recorded_output[:400])) and \
                bool(_INHERENT_RE.search(step.compiled_output[:400]))
            # the fix target is what the comparator actually compares: the normalized recording
            out.append(Failure(action.action, step.step_id, step.executor_used, step.note,
                               _strip_read_numbers(step.recorded_output), step.compiled_output, inherent))
    return out, (matched, checked)


def _artifacts_for(root: Path, action: str) -> List[Path]:
    candidates = [root / "handlers" / f"{action}.py", root / "prompts" / f"{action}.prompt.md",
                  root / "rules" / f"{action}.rule.yaml"]
    return [p for p in candidates if p.exists()]


def _fix_prompt(root: Path, failure: Failure, artifacts: List[Path]) -> str:
    files = "\n\n".join(f"### {p.relative_to(root)}\n```python\n{p.read_text(encoding='utf-8')}\n```" for p in artifacts)
    def clip(t: str, n: int = 2500) -> str:
        return t if len(t) <= n else t[:n] + f"\n… [{len(t) - n} more chars]"
    return (f"You are hardening the compiled build at `{root}`. The replayed handler for action "
            f"`{failure.action}` does not reproduce the recorded output.\n\n"
            f"## Recorded output (normalized — this exact text is the comparison target)\n```\n{clip(failure.recorded)}\n```\n\n"
            f"## Replayed output (what the handler produced)\n```\n{clip(failure.replayed)}\n```\n\n"
            f"## Note\n{failure.note or '(none)'}\n\n## Current artifact(s)\n{files}\n\n"
            f"## Instruction\nEdit ONLY the artifact file(s) above (use your file-editing tool with these exact "
            f"paths) so that replaying reproduces the recorded output for the same inputs. Preserve the handler "
            f"contract (module-level `run(**inputs) -> dict`) and parameter templating (`{{param}}` placeholders). "
            f"Prefer the smallest change. Note: during replay the recorded step input carries the original command and "
            f"takes precedence — to change what gets executed, set FORCE_COMMANDS = True and edit COMMANDS, or modify run() itself. If the difference "
            f"is inherently run-dependent (timestamps, live system state), instead make the handler's output "
            f"deterministic in a way that stays faithful (e.g. drop the volatile flag) and say so. "
            f"Do not touch trace.json or any file outside the build directory. Reply with one line describing the change.")


def _load_history(root: Path) -> Dict[str, Any]:
    path = root / "harden.json"
    if not path.exists():
        return {}
    try:
        return {a["signature"]: a for a in json.loads(path.read_text(encoding="utf-8")).get("attempts", [])}
    except Exception:
        return {}


def harden(build_dir: Path | str, *, escalator: Optional[Escalator] = None, backend_name: str = "none",
           max_iters: int = 3, fixes_per_iter: int = 3, budget_tokens: int = 0,
           trace: Optional[TraceIR] = None) -> HardenReport:
    root = Path(build_dir)
    work_ir = load_work_ir(root / "work.yaml")
    trace = trace or _load_trace(root)
    report = HardenReport(work=work_ir.work, build_dir=str(root), backend=backend_name, budget_tokens=budget_tokens)
    attempts = _load_history(root)          # durable across runs: never re-spend budget on the same failure mode

    bench = run_benchmark(root, trace)
    failures, score = _failures(bench)
    report.inherent = sorted({f.action for f in failures if f.inherent})

    for number in range(1, max_iters + 1):
        actionable, gated = [], []
        for f in failures:
            if f.inherent:
                continue
            if not _artifacts_for(root, f.action):
                gated.append(f.action)
            elif attempts.get(f.signature, {}).get("outcome") == "reverted":
                gated.append(f.action)      # this exact failure mode already resisted a fix — hand it to a human
            else:
                actionable.append(f)
        report.needs_human = sorted(set(report.needs_human) | set(gated))
        it = Iteration(number=number, failures_before=len(actionable), score_before=score, score_after=score)
        report.iterations.append(it)
        if not actionable:
            report.converged = not gated
            report.stopped_because = "no actionable failures left"
            break
        if escalator is None:
            it.attempted = [f"{f.action} (no backend — run with --escalate)" for f in actionable[:fixes_per_iter]]
            report.stopped_because = "no fix backend (--escalate)"
            break
        progressed = False
        for failure in actionable[:fixes_per_iter]:
            if budget_tokens and report.tokens_total >= budget_tokens:
                report.stopped_because = f"token budget exhausted ({report.tokens_total:,}/{budget_tokens:,})"
                break
            artifacts = _artifacts_for(root, failure.action)
            snapshots = {p: p.read_text(encoding="utf-8") for p in artifacts}
            it.attempted.append(failure.action)
            with telemetry.span("harden.fix", work=work_ir.work, action=failure.action, backend=backend_name) as tspan:
                res = escalator(_fix_prompt(root, failure, artifacts), {"action": failure.action, "cwd": str(Path.cwd())})
                spent = int(res.get("tokens", 0) or 0)
                it.tokens_spent += spent
                report.tokens_total += spent
                tspan.update({"tokens": spent, "exit_code": res.get("exit_code", 0)})
            bench = run_benchmark(root, trace)
            new_failures, new_score = _failures(bench)
            accepted = new_score[0] > score[0] and res.get("exit_code", 0) == 0
            attempts[failure.signature] = {"signature": failure.signature, "action": failure.action,
                                           "outcome": "accepted" if accepted else "reverted",
                                           "tokens": spent, "reply": str(res.get("output", ""))[:200],
                                           "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            if accepted:
                it.accepted.append(failure.action)
                failures, score = new_failures, new_score
                progressed = True
            else:
                for p, text in snapshots.items():
                    p.write_text(text, encoding="utf-8")
                it.reverted.append(failure.action)
        it.score_after = score
        if report.stopped_because:
            break
        if not progressed:
            report.stopped_because = "no progress in this iteration"
            break
        if not [f for f in failures if not f.inherent]:
            report.converged = True
            report.stopped_because = "all reproducible failures fixed"
            break
    if not report.stopped_because:
        report.stopped_because = f"iteration limit ({max_iters}) reached"

    report.final_matched, report.final_checked = score
    (root / "HARDEN.md").write_text(report.to_markdown(), encoding="utf-8")
    (root / "harden.json").write_text(json.dumps({
        "work": report.work, "backend": backend_name, "converged": report.converged,
        "final": {"matched": report.final_matched, "checked": report.final_checked},
        "inherent": report.inherent, "needs_human": report.needs_human,
        "tokens_total": report.tokens_total, "stopped_because": report.stopped_because,
        "attempts": sorted(attempts.values(), key=lambda a: a["at"]),
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "iterations": [{"n": i.number, "failures": i.failures_before, "attempted": i.attempted,
                        "accepted": i.accepted, "reverted": i.reverted, "tokens": i.tokens_spent,
                        "score_before": i.score_before, "score_after": i.score_after} for i in report.iterations],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report
