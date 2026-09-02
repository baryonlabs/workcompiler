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
import re
import os
import time
from dataclasses import dataclass, field, fields as dataclass_fields, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.build.loader import load_build_into_engine
from core import telemetry
from core.work_ir import TraceIR, TraceStep, load_work_ir, normalize_tool_output
from core.validation.quality_record import QualityRecord, evaluate_quality_fold


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
    recorded_tokens_unique: int = 0   # unique cost of this step: prompt growth over the previous request + completion
    unique_basis: str = ""            # "prompt_delta" (exact split) or "total_delta" (estimated from total_tokens increments)
    recorded_at: str = ""             # ISO 8601 wall-clock of the recorded step (from the trace) — the time axis
    quality: Optional[float] = None   # SLM tier: gate score (min of anchor recall / grounding precision)


@dataclass
class ActionBench:
    action: str
    tier: str
    steps: List[StepBench] = field(default_factory=list)
    completion: str = ""              # passed | incomplete | behavior_violation | abandoned (see classify_completion)
    behavior_verdicts: Dict[str, str] = field(default_factory=dict)

    @property
    def recorded_tokens(self) -> int:
        return sum(s.recorded_tokens for s in self.steps)

    @property
    def compiled_tokens(self) -> int:
        return sum(s.compiled_tokens for s in self.steps)

    @property
    def recorded_tokens_unique(self) -> int:
        return sum(s.recorded_tokens_unique for s in self.steps)

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
            "recorded_tokens": self.recorded_tokens, "recorded_tokens_unique": self.recorded_tokens_unique,
            "compiled_tokens": self.compiled_tokens,
            "recorded_latency_ms": round(self.recorded_latency_ms, 1),
            "compiled_latency_ms": round(self.compiled_latency_ms, 1),
            "output_matches": self.matches,
            "completion": self.completion, "behavior_verdicts": dict(self.behavior_verdicts),
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
    baseline_minutes: float = 0.0     # how long a person takes for this work (from work.yaml); 0 = unknown

    def _window(self) -> tuple[str, str]:
        stamps = sorted(s.recorded_at for a in self.actions for s in a.steps if s.recorded_at)
        return (stamps[0], stamps[-1]) if stamps else ("", "")

    def costs(self, prices: Optional[Dict[str, Dict[str, float]]] = None) -> Optional[Dict[str, Any]]:
        """Recorded vs compiled cost in USD, per the supplied price table.

        Cache reads are billed separately (typically ~1/10 of input), so they are priced with
        ``cache_read`` rather than folded into the input rate. Unpriced models are reported by
        name so a cost figure is never quietly computed from a partial table.
        """
        prices = prices if prices is not None else load_prices()
        if not prices:
            return None
        rec = comp = 0.0
        missing: set[str] = set()
        unpriced_tokens = 0

        def rate(model: str, kind: str) -> Optional[float]:
            row = prices.get(model) or prices.get(model.split(":", 1)[0])
            if row is None:
                missing.add(model or "?")
                return None
            return float(row.get(kind, 0.0))

        for a in self.actions:
            for st in a.steps:
                # some agents record no per-step model; fall back to the session's agent so a
                # table keyed by agent ("codex") still prices it, and report what stayed unpriced
                rec_model = st.recorded_model or self.source_agent or "?"
                r_in = rate(rec_model, "input")
                r_out = rate(rec_model, "output")
                r_cache = rate(rec_model, "cache_read")
                if r_in is not None:
                    fresh = max(st.recorded_prompt_tokens - st.recorded_cached_tokens, 0)
                    rec += (fresh * r_in + st.recorded_cached_tokens * (r_cache or 0.0)
                            + st.recorded_completion_tokens * (r_out or 0.0)) / 1e6
                c_in = rate(st.compiled_model or "?", "input")
                if c_in is not None:
                    comp += st.compiled_tokens * c_in / 1e6
                else:
                    unpriced_tokens += st.compiled_tokens
        out: Dict[str, Any] = {"currency": "USD", "recorded": round(rec, 4), "compiled": round(comp, 4),
                               "unpriced_models": sorted(missing)}
        if missing:
            # a step nobody could price is not a free step: reporting a delta here would credit
            # the build with savings it did not make (an escalation still on a frontier model, say)
            out["saved"] = None
            out["partial"] = True
            out["unpriced_compiled_tokens"] = unpriced_tokens
        else:
            out["saved"] = round(rec - comp, 4)
        return out

    def totals(self) -> Dict[str, Any]:
        rt = sum(a.recorded_tokens for a in self.actions)
        ru = sum(a.recorded_tokens_unique for a in self.actions)
        ct = sum(a.compiled_tokens for a in self.actions)
        rl = sum(a.recorded_latency_ms for a in self.actions)
        cl = sum(a.compiled_latency_ms for a in self.actions)
        checked = [s for a in self.actions for s in a.steps if s.output_match is not None]
        bases = sorted({s.unique_basis for a in self.actions for s in a.steps if s.unique_basis})
        return {
            "recorded_tokens": rt, "recorded_tokens_unique": ru, "compiled_tokens": ct,
            "token_savings_pct": round(100.0 * (rt - ct) / rt, 1) if rt else 0.0,
            "savings_unique_pct": round(100.0 * (ru - ct) / ru, 1) if ru else 0.0,
            "unique_token_basis": "+".join(bases) or "n/a",
            "recorded_latency_ms": round(rl, 1), "compiled_latency_ms": round(cl, 1),
            "speedup_x": round(rl / cl, 1) if cl else None,
            "outputs_checked": len(checked),
            "outputs_matched": sum(1 for s in checked if s.output_match),
            "compiled_actions": sum(1 for a in self.actions if a.tier in ("code", "rule", "http") or any(s.executor_used.startswith("slm:") for s in a.steps)),
            "escalated_actions": sum(1 for a in self.actions if a.tier not in ("code", "rule", "http") and not any(s.executor_used.startswith("slm:") for s in a.steps)),
            "slm_actions": sum(1 for a in self.actions if any(s.executor_used.startswith("slm:") for s in a.steps)),
            "recorded_from": self._window()[0], "recorded_to": self._window()[1],
            **({"completion": {c: sum(1 for a in self.actions if a.completion == c) for c in COMPLETION_CLASSES}
                | {"cases": len(self.actions)}}
               if any(a.completion for a in self.actions) else {}),
            **({"cost": c} if (c := self.costs()) else {}),
            **({"baseline_minutes": self.baseline_minutes,
                "saved_minutes": round(self.baseline_minutes - cl / 60000.0, 1)}
               if self.baseline_minutes else {}),
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
                 "recorded_tokens": s.recorded_tokens, "recorded_tokens_unique": s.recorded_tokens_unique,
                 "compiled_executor": s.compiled_model, "compiled_tokens": s.compiled_tokens}
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
            f"| LLM tokens (unique) | {t['recorded_tokens_unique']:,} | {t['compiled_tokens']:,} | −{t['savings_unique_pct']}% |",
            f"| LLM tokens (cumulative-context sum; reference) | {t['recorded_tokens']:,} | {t['compiled_tokens']:,} | −{t['token_savings_pct']}% |",
            f"| wall time | {t['recorded_latency_ms']/1000:.1f} s | {t['compiled_latency_ms']/1000:.2f} s | "
            + (f"{t['speedup_x']}× faster" if t['speedup_x'] else "n/a") + " |",
            f"| outputs reproduced | — | {t['outputs_matched']}/{t['outputs_checked']} | |",
            f"| actions compiled / escalated | — | {t['compiled_actions']} / {t['escalated_actions']} | |",
        ]
        if t.get("completion"):
            c = t["completion"]
            lines.append(f"| cases: passed / incomplete / behavior violation / abandoned | — | "
                         f"{c['passed']} / {c['incomplete']} / {c['behavior_violation']} / {c['abandoned']} "
                         f"(of {c['cases']}) | |")
        if t.get("cost"):
            c = t["cost"]
            if c.get("partial"):
                delta = (f"not computed — {', '.join(c['unpriced_models'])} unpriced "
                         f"({c['unpriced_compiled_tokens']:,} compiled tokens)")
            else:
                delta = f"${c['saved']:.4f} saved"
            lines.append(f"| cost ({c['currency']}, supplied price table) | ${c['recorded']:.4f} | "
                         f"${c['compiled']:.4f}{'+' if c.get('partial') else ''} | {delta} |")
        if t.get("baseline_minutes"):
            lines.append(f"| person-minutes (declared baseline) | {t['baseline_minutes']:g} min | "
                         f"{t['compiled_latency_ms']/60000.0:.1f} min | {t['saved_minutes']:g} min saved |")
        if t.get("recorded_from"):
            lines.append(f"| recorded window | {t['recorded_from']} → {t['recorded_to']} | | |")
        lines += [
            "",
            "**Unique** is the headline metric: each token counted once — the first request's full prompt, "
            "then only each later request's prompt growth, plus every completion"
            + (" (this trace has no prompt/completion split, so unique is estimated from `total_tokens` increments)"
               if "total_delta" in t["unique_token_basis"] else "")
            + ". The cumulative-context sum adds up every request's usage as reported by the provider — an agent "
            "session re-sends its whole context every turn, so that sum counts the same tokens once per turn "
            "and overstates the cost of the agent path. Escalated steps keep their full recorded per-request "
            "cost on the compiled side (conservative: a real escalation would send a smaller, rebuilt prompt).",
            "",
            "## Per action",
            "",
            "| action | tier | executor used | tokens rec (unique) → comp | latency rec → comp | output match |",
            "| :-- | :-- | :-- | --: | --: | :-- |",
        ]
        for a in self.actions:
            used = ", ".join(sorted({s.executor_used for s in a.steps}))
            lines.append(
                f"| `{a.action}` | {a.tier} | {used} | {a.recorded_tokens_unique:,} → {a.compiled_tokens:,} | "
                f"{a.recorded_latency_ms/1000:.1f} s → {a.compiled_latency_ms/1000:.2f} s | {a.matches} |"
            )
        slm_steps = [(a, s) for a in self.actions for s in a.steps if s.executor_used.startswith("slm:")]
        if slm_steps:
            lines += ["", "## SLM tier — small local model instead of the frontier LLM", "",
                      "| step | action | model | tokens (frontier → SLM) | latency | gate |", "| :-- | :-- | :-- | --: | --: | :-- |"]
            for a, s in slm_steps:
                lines.append(f"| {s.step_id} | `{a.action}` | {s.compiled_model} | {s.recorded_tokens:,} → {s.compiled_tokens:,} | "
                             f"{s.recorded_latency_ms/1000:.1f} s → {s.compiled_latency_ms/1000:.1f} s | {s.note} |")
        lines += ["", "## Token ledger — who spent what", "",
                  "Every recorded step, the model that produced it, and what runs it in the compiled build.", "",
                  "| step | action | recorded model | prompt (cached) + completion = total | unique | compiled executor | compiled tokens |",
                  "| :-- | :-- | :-- | --: | --: | :-- | --: |"]
        for a in self.actions:
            for s in a.steps:
                lines.append(f"| {s.step_id} | `{a.action}` | {s.recorded_model or '?'} | "
                             f"{s.recorded_prompt_tokens:,} ({s.recorded_cached_tokens:,}) + {s.recorded_completion_tokens:,} = {s.recorded_tokens:,} | "
                             f"{s.recorded_tokens_unique:,} | {s.compiled_model} | {s.compiled_tokens:,} |")
        cached = sum(s.recorded_cached_tokens for a in self.actions for s in a.steps)
        lines += ["", "| model / executor | recorded tokens | compiled tokens |", "| :-- | --: | --: |"]
        for key, (rt, ct) in self.by_model().items():
            lines.append(f"| {key} | {rt:,} | {ct:,} |")
        lines += ["", f"Recorded prompt tokens served from the provider cache: {cached:,} (counted in the cumulative totals above; billed at the cached rate).",
                  "The per-model table sums every request's usage as reported by the provider (cumulative-context basis) — each agent turn re-sends its whole context, which is why it exceeds the agent CLI's own 'tokens used' figure. The *unique* column of the ledger counts each token once."]
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
    """After replaying a file-writing handler, check the workspace matches the recorded patch."""
    import os
    from core.work_ir.patchfmt import verify_patch_text

    text = patch.replace(str(Path.cwd().resolve()) + "/", "")
    ws = os.environ.get("OPENWORKCOMPILER_WORKSPACE_DIR")
    if ws:
        text = text.replace(str(Path(ws).resolve()) + "/", "")
    ok, checked, note = verify_patch_text(text, ".")
    return ok, (f"{checked} file(s) verified on disk" if ok else f"written files differ from recorded patch ({note})")


_READ_NUMBER_RE = re.compile(r"^\s*\d+(?:→|\t)")


def _strip_read_numbers(text: str) -> str:
    """Claude Code's Read tool prefixes every line with its number (``12→`` / ``12<TAB>``); the replay
    (``cat``) does not. A merged step (parallel Reads + a Glob) concatenates numbered and plain
    segments, so strip per *run*: maximal stretches of consecutively numbered lines that start
    again at 1 (two or more lines), leaving everything else untouched."""
    lines = text.splitlines()
    out, i = [], 0
    while i < len(lines):
        m = _READ_NUMBER_RE.match(lines[i])
        num = int(re.match(r"\s*(\d+)", lines[i]).group(1)) if m else None
        if m and num == 1:
            run = [i]
            expect = 2
            j = i + 1
            while j < len(lines):
                mj = _READ_NUMBER_RE.match(lines[j])
                if mj and int(re.match(r"\s*(\d+)", lines[j]).group(1)) == expect:
                    run.append(j); expect += 1; j += 1
                else:
                    break
            if len(run) >= 2:
                out.extend(_READ_NUMBER_RE.sub("", lines[k], count=1) for k in run)
                i = j
                continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def _compare(recorded: str, compiled: str) -> tuple[bool, str]:
    """(match, note): exact line sequence first, then order-insensitive line multiset."""
    rec, comp = _lines(_strip_read_numbers(recorded)), _lines(compiled)
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


PRICES_ENV = "OWC_PRICES"          # path to {model: {input, output, cache_read}} USD per 1M tokens


def load_prices(path: Optional[str] = None) -> Dict[str, Dict[str, float]]:
    """Model price table, in USD per 1M tokens, from ``--prices`` or ``$OWC_PRICES``.

    Absent by design: the repository ships no prices, so a cost figure only ever appears when
    someone supplies the table their organization actually pays. Shape::

        {"claude-fable-5": {"input": 3.0, "output": 15.0, "cache_read": 0.3}, "code": {...}}
    """
    src = path or os.environ.get(PRICES_ENV)
    if not src:
        return {}
    try:
        data = json.loads(Path(src).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {str(k): {kk: float(vv) for kk, vv in v.items()} for k, v in data.items() if isinstance(v, dict)}


def unique_step_tokens(trace: TraceIR) -> Dict[str, tuple[int, str]]:
    """``{step_id: (unique tokens, basis)}`` — each token of the session counted once.

    An agent session re-sends its whole cumulative context on every request, so summing
    per-request usage counts the same tokens once per turn. The *unique* cost of a step is
    its prompt growth over the previous request plus its completion; the first request's
    prompt counts in full. When the prompt shrinks (context reset / compaction / subagent),
    the uncached part of the fresh prompt is counted (conservative). Traces without a
    prompt/completion split fall back to increments of ``total_tokens`` (basis
    ``total_delta`` — an estimate, flagged in the report).
    """
    out: Dict[str, tuple[int, str]] = {}
    prev_prompt: Optional[int] = None
    prev_total: Optional[int] = None
    for step in trace.steps:
        pt, ct = _step_token_split(step)
        tt = _step_tokens(step)
        if pt or ct:
            if prev_prompt is None:
                new_input = pt
            elif pt >= prev_prompt:
                new_input = pt - prev_prompt
            else:
                new_input = max(pt - _step_cached(step), 0)
            out[step.step_id] = (new_input + ct, "prompt_delta")
            prev_prompt, prev_total = pt, tt
        elif tt:
            out[step.step_id] = (tt if prev_total is None else max(tt - prev_total, 0), "total_delta")
            prev_total = tt
        else:
            out[step.step_id] = (0, "")
    return out


COMPLETION_CLASSES = ("passed", "incomplete", "behavior_violation", "abandoned")


def classify_completion(report: BenchReport, dependencies: Optional[Dict[str, List[str]]] = None) -> BenchReport:
    """Classify each action as a *case*: passed / incomplete / behavior_violation / abandoned.

    The reproduction score (``outputs_matched/outputs_checked``) counts output steps; an
    organization asks a different question — of the work items attempted, how many actually
    completed, and how many merely *looked* complete? This routes each action through the
    project's own ``QualityRecord`` fold, so the lucky-correct rule (a required process was
    skipped ⇒ FAIL, however good the output looks) governs both paths.

    Behavior evidence is the declared dependency graph of ``work.yaml``: the compile-time form
    of the work's invariants. An action whose declared predecessor never ran successfully before
    it violated the process, even when its output matches the recording.

    * ``abandoned`` — the action never executed in the compiled build (no steps).
    * ``incomplete`` — it ran but stopped short: an unresolved escalation (``needs_agent``) or a
      step whose output could not be produced.
    * ``behavior_violation`` — it ran (and may even match) with a declared predecessor missing.
    * ``passed`` — it ran, honored its declared order, and nothing was checked-and-wrong.
    """
    deps = dependencies or {}
    ran_ok = {a.action for a in report.actions
              if a.steps and not any(s.executor_used == "needs_agent" for s in a.steps)}
    for a in report.actions:
        if not a.steps:
            a.completion, a.behavior_verdicts = "abandoned", {}
            continue
        missing = [d for d in deps.get(a.action, []) if d not in ran_ok]
        a.behavior_verdicts = {f"after:{d}": ("true" if d in ran_ok else "false") for d in deps.get(a.action, [])}
        checked = [s.output_match for s in a.steps if s.output_match is not None]
        record = QualityRecord(
            trace_id=f"{report.run_id}:{a.action}", action_name=a.action, executor_type=a.tier,
            behavior_verdicts=dict(a.behavior_verdicts),
            automated_checks={"outputs_reproduced": all(checked)} if checked else {},
        )
        fold = evaluate_quality_fold(record)
        if missing:
            a.completion = "behavior_violation"       # process skipped — the lucky-correct case
        elif any(s.executor_used == "needs_agent" for s in a.steps):
            a.completion = "incomplete"               # an escalation the build could not resolve
        else:
            a.completion = "passed" if fold != "FAIL" else "incomplete"
    return report


def attach_unique_tokens(report: BenchReport, trace: TraceIR) -> BenchReport:
    """Fill trace-derived per-step fields: unique tokens, wall-clock, and the recorded model.

    Also backfills reports written before these columns existed, so ``bench --recompute-totals``
    upgrades an old ``benchmark.json`` instead of reporting blanks.
    """
    uniq = unique_step_tokens(trace)
    by_id = {st.step_id: st for st in trace.steps}
    for a in report.actions:
        for s in a.steps:
            s.recorded_tokens_unique, s.unique_basis = uniq.get(s.step_id, (0, ""))
            st = by_id.get(s.step_id)
            if st is not None:
                s.recorded_at = s.recorded_at or str(getattr(st, "timestamp", "") or "")
                s.recorded_model = s.recorded_model or str(getattr(st, "model", "") or "")
    return report


def report_from_dict(data: Dict[str, Any]) -> BenchReport:
    """Rebuild a :class:`BenchReport` from a previously written ``benchmark.json``.

    Lets totals (e.g. the unique-token columns) be recomputed from the trace without
    replaying the build. Unknown / missing step keys are ignored / defaulted, so reports
    written before a column existed load fine.
    """
    step_keys = {f.name for f in dataclass_fields(StepBench)}
    actions = [ActionBench(action=a["action"], tier=a["tier"],
                           steps=[StepBench(**{k: v for k, v in s.items() if k in step_keys})
                                  for s in a.get("steps", [])])
               for a in data.get("actions", [])]
    return BenchReport(work=data["work"], build_dir=data["build_dir"], run_id=data["run_id"],
                       source_agent=data["source_agent"], actions=actions,
                       final_answer=data.get("final_answer", ""))


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
    from core.build import slm as slm_tier
    upstream: List[tuple[str, str]] = []      # (action, context text) of the steps replayed so far, in order

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
        runtime = slm_tier.SLMRuntime.load(root, action) if tier == "slm" else None

        if runtime is not None and replay:
            # promoted SLM: really run the small model on this run's upstream outputs and gate it
            pt, ct = _step_token_split(step)
            with telemetry.span("bench.slm", work=work_ir.work, run_id=trace.run_id, step=step.step_id, action=action,
                                model=runtime.model, recorded_tokens=rec_tokens) as tspan:
                done = slm_tier.execute(root, action, work_ir.work, {}, upstream, runtime=runtime, recorded_output=rec_out,
                                        example_output=rec_out, trace_id=f"{trace.run_id}:{step.step_id}",
                                        invariants=work_ir.invariants or [], request=slm_tier.step_request(step))
                tspan.update({"tokens": done.result.tokens, "passed": done.verdict.passed})
            bench.steps.append(StepBench(step.step_id, rec_tokens, rec_latency, done.result.tokens, done.result.latency_ms,
                                         f"slm:{runtime.model}", done.verdict.passed if done.result.ok else False, rec_out,
                                         done.result.output or done.result.error, "gate " + done.verdict.summary(),
                                         recorded_model=_step_model(step), compiled_model=runtime.model,
                                         recorded_prompt_tokens=pt, recorded_completion_tokens=ct, recorded_cached_tokens=_step_cached(step),
                                         quality=done.verdict.score))
            upstream.append((action, done.result.output))
            continue

        if executable and replay and _is_self_referential(inputs):
            pt, ct = _step_token_split(step)
            bench.steps.append(StepBench(step.step_id, rec_tokens, rec_latency, 0, 0.0, f"{tier} (skipped)",
                                         None, rec_out, "", "self-referential step (benchmarks/recompiles this build) not replayed",
                                         recorded_model=_step_model(step), compiled_model="skipped",
                                         recorded_prompt_tokens=pt, recorded_completion_tokens=ct, recorded_cached_tokens=_step_cached(step),
                                         recorded_at=str(getattr(step, "timestamp", "") or "")))
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
            upstream.append((action, slm_tier.step_context(inputs, comp_out)))
        elif executable:
            pt, ct = _step_token_split(step)
            bench.steps.append(StepBench(step.step_id, rec_tokens, rec_latency, 0, 0.0, f"{tier} (replay disabled)",
                                         None, rec_out, "", "not replayed", recorded_model=_step_model(step),
                                         compiled_model=tier, recorded_prompt_tokens=pt, recorded_completion_tokens=ct, recorded_cached_tokens=_step_cached(step)))
        else:
            reason = {"ml": "model not trained yet → fallback", "slm": "SLM not promoted yet (owc build promote) → fallback"}.get(tier, "")
            pt, ct = _step_token_split(step)
            bench.steps.append(StepBench(step.step_id, rec_tokens, rec_latency, rec_tokens, rec_latency,
                                         f"escalated:{tier}", None, rec_out, rec_out,
                                         reason or "kept recorded cost (frontier/human tier)",
                                         recorded_model=_step_model(step), compiled_model=_step_model(step) or tier,
                                         recorded_prompt_tokens=pt, recorded_completion_tokens=ct, recorded_cached_tokens=_step_cached(step)))
            upstream.append((action, rec_out))

    report.actions = [benches[a] for a in work_ir.actions]
    attach_unique_tokens(report, trace)
    classify_completion(report, work_ir.to_dict().get("dependencies") or {})
    try:  # a person-minutes baseline is declared in the work spec, when the org knows it
        report.baseline_minutes = float(work_ir.to_dict().get("baseline_minutes") or 0.0)
    except Exception:
        report.baseline_minutes = 0.0
    t = report.totals()
    telemetry.event("bench.report", work=work_ir.work, run_id=trace.run_id, recorded_tokens=t["recorded_tokens"],
                    recorded_tokens_unique=t["recorded_tokens_unique"],
                    compiled_tokens=t["compiled_tokens"], token_savings_pct=t["token_savings_pct"],
                    savings_unique_pct=t["savings_unique_pct"],
                    speedup_x=t["speedup_x"], outputs_matched=t["outputs_matched"], outputs_checked=t["outputs_checked"])

    for step in reversed(trace.steps):
        out = step.output if isinstance(step.output, dict) else {}
        if out.get("content") and not out.get("tool_calls"):
            report.final_answer = str(out["content"])
            break
    return report


def write_report(report: BenchReport, out_dir: Path | str, append_to_ledger: bool = True) -> Dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "BENCHMARK.md").write_text(report.to_markdown(), encoding="utf-8")
    (out / "benchmark.json").write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    if append_to_ledger:
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
