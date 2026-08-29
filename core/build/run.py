"""Run a compiled build for *new* inputs: a front agent binds parameters, code tiers execute
for free, and only synthesized / model-tier steps are escalated to an agent.

    report = run_build("build/customer_renewal_codex", request="renewal proposal for CUST-1002",
                       escalate="codex")

Flexibility stays with the (small) agent in front; efficiency comes from everything it can hand
to deterministic code. The report accounts tokens and wall time per step so the split is visible.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.build.bench import BENCH_ACTIVE_ENV, _clip, _is_self_referential, _normalizer, append_ledger
from core.build.loader import load_build_into_engine
from core import telemetry
from core.work_ir import TraceIR, load_work_ir, normalize_tool_output

Escalator = Callable[[str, Dict[str, Any]], Dict[str, Any]]   # (prompt, context) -> {"output", "tokens", "files"}


# --------------------------------------------------------------------------- front agent: binding

def _id_pattern(recorded: str) -> re.Pattern:
    prefix = recorded.split("-", 1)[0]
    return re.compile(rf"\b{re.escape(prefix)}-[A-Z0-9-]+\b")


def bind_parameters(build_dir: Path | str, request: Optional[str] = None,
                    overrides: Optional[Dict[str, str]] = None, binder: str = "regex") -> Dict[str, Any]:
    """Front agent: decide the parameter values for this run.

    * ``overrides`` win.
    * ``binder="regex"`` finds values shaped like the recorded ones in the request text.
    * ``binder="codex"`` asks Codex to extract the values (for requests the regex cannot read).
    Unbound parameters fall back to the recorded value and are reported as ``defaulted``.
    """
    spec = json.loads((Path(build_dir) / "PARAMS.json").read_text(encoding="utf-8"))
    params = spec.get("params", [])
    bound: Dict[str, Any] = {}
    detail: Dict[str, str] = {}
    pending = []
    for p in params:
        name = p["name"]
        if overrides and name in overrides:
            bound[name], detail[name] = overrides[name], "override"
            continue
        if request and p.get("kind") == "id":
            m = _id_pattern(p["recorded_value"]).search(request)
            if m:
                bound[name], detail[name] = m.group(0), "regex"
                continue
        pending.append(p)
    if pending and request and binder == "codex":
        extracted = _codex_extract(request, pending)
        for p in pending:
            if p["name"] in extracted:
                bound[p["name"]], detail[p["name"]] = extracted[p["name"]], "codex"
    for p in params:
        if p["name"] not in bound:
            bound[p["name"]], detail[p["name"]] = p["recorded_value"], "defaulted"
    return {"values": bound, "how": detail, "synthesized_actions": spec.get("synthesized_actions", [])}


def _codex_extract(request: str, params: List[Dict[str, Any]]) -> Dict[str, str]:
    prompt = ("Extract parameter values from the request below. Reply with a single JSON object mapping "
              "parameter name to value (string); omit parameters that are not present.\n\nParameters:\n"
              + "\n".join(f"- {p['name']} (example: {p['recorded_value']})" for p in params)
              + f"\n\nRequest:\n{request}\n")
    result = codex_escalator(prompt, {"read_only": True})
    m = re.search(r"\{.*\}", result.get("output", ""), re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
    except Exception:
        data = {}
    return {k: str(v) for k, v in data.items() if isinstance(v, (str, int, float))}


# --------------------------------------------------------------------------- escalation backends

def codex_escalator(prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Escalate to Codex CLI (non-interactive). Returns output text and the tokens it reports."""
    if shutil.which("codex") is None:
        raise RuntimeError("codex CLI not found on PATH")
    cmd = ["codex", "exec", "--skip-git-repo-check", "-c", "notify=[]"]
    if context.get("read_only"):
        cmd += ["--sandbox", "read-only"]
    else:
        cmd += ["--sandbox", "workspace-write"]
    t0 = time.perf_counter()
    # codex prints the transcript (incl. "tokens used") on stderr; merge both streams
    proc = subprocess.run(cmd + [prompt], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                          timeout=900, stdin=subprocess.DEVNULL)
    elapsed = (time.perf_counter() - t0) * 1000.0
    text = proc.stdout
    tokens = 0
    m = re.search(r"tokens used\n([\d,]+)", text)
    if m:
        tokens = int(m.group(1).replace(",", ""))
    model_m = re.search(r"^model:\s*(\S+)", text, re.M)
    model = model_m.group(1) if model_m else "codex"
    # the final assistant message follows the last "codex" marker
    parts = re.split(r"^codex\n", text, flags=re.M)
    answer = parts[-1].split("\ntokens used\n")[0].strip() if len(parts) > 1 else text.strip()
    return {"output": answer, "tokens": tokens, "latency_ms": elapsed, "exit_code": proc.returncode,
            "model": model, "raw": text if proc.returncode else ""}


# --------------------------------------------------------------------------- run

@dataclass
class RunStep:
    step_id: str
    action: str
    mode: str                     # code | escalated:<backend> | needs_agent | skipped
    tokens: int
    latency_ms: float
    ok: bool
    output: str
    note: str = ""
    model: str = ""               # what executed this step now: "code" / "rule" / a model id
    recorded_model: str = ""      # what executed it in the recorded session
    recorded_tokens: int = 0


@dataclass
class RunReport:
    work: str
    build_dir: str
    request: str
    params: Dict[str, Any]
    binding: Dict[str, str]
    steps: List[RunStep] = field(default_factory=list)
    recorded_tokens: int = 0
    recorded_latency_ms: float = 0.0

    def totals(self) -> Dict[str, Any]:
        tokens = sum(s.tokens for s in self.steps)
        latency = sum(s.latency_ms for s in self.steps)
        return {
            "tokens": tokens, "latency_ms": round(latency, 1),
            "code_steps": sum(1 for s in self.steps if s.mode == "code"),
            "escalated_steps": sum(1 for s in self.steps if s.mode.startswith("escalated")),
            "needs_agent_steps": sum(1 for s in self.steps if s.mode == "needs_agent"),
            "recorded_tokens": self.recorded_tokens, "recorded_latency_ms": round(self.recorded_latency_ms, 1),
            "token_savings_pct": round(100.0 * (self.recorded_tokens - tokens) / self.recorded_tokens, 1) if self.recorded_tokens else None,
            "speedup_x": round(self.recorded_latency_ms / latency, 1) if latency and self.recorded_latency_ms else None,
        }

    def by_model(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for s in self.steps:
            out.setdefault(s.recorded_model or "?", {"recorded_tokens": 0, "run_tokens": 0})["recorded_tokens"] += s.recorded_tokens
            out.setdefault(s.model or "?", {"recorded_tokens": 0, "run_tokens": 0})["run_tokens"] += s.tokens
        return out

    def ledger_rows(self) -> List[Dict[str, Any]]:
        return [{"step": s.step_id, "action": s.action, "recorded_model": s.recorded_model, "recorded_tokens": s.recorded_tokens,
                 "run_executor": s.model, "run_tokens": s.tokens, "mode": s.mode, "params": self.params} for s in self.steps]

    def to_dict(self) -> Dict[str, Any]:
        return {"work": self.work, "build_dir": self.build_dir, "request": self.request, "params": self.params,
                "binding": self.binding, "totals": self.totals(), "by_model": self.by_model(), "ledger": self.ledger_rows(),
                "steps": [s.__dict__ for s in self.steps]}

    def to_markdown(self) -> str:
        t = self.totals()
        lines = [f"# Run report — `{self.work}`", "",
                 f"Request: `{self.request or '(parameters given directly)'}`", "",
                 "## Parameters bound by the front agent", "",
                 "| parameter | value | how |", "| :-- | :-- | :-- |"]
        lines += [f"| `{k}` | `{v}` | {self.binding.get(k, '')} |" for k, v in self.params.items()]
        lines += ["", "## Totals", "", "| | this run (compiled build + front agent) | recorded agent session |", "| :-- | --: | --: |",
                  f"| LLM tokens | {t['tokens']:,} | {t['recorded_tokens']:,} |",
                  f"| wall time | {t['latency_ms']/1000:.1f} s | {t['recorded_latency_ms']/1000:.1f} s |",
                  f"| steps: code / escalated / needs agent | {t['code_steps']} / {t['escalated_steps']} / {t['needs_agent_steps']} | — |"]
        if t["token_savings_pct"] is not None:
            lines.append(f"| token savings | −{t['token_savings_pct']}% | |")
        if t["speedup_x"]:
            lines.append(f"| speedup | {t['speedup_x']}× | |")
        lines += ["", "## Steps", "", "| step | action | mode | recorded model → tokens | this run: executor → tokens | latency | ok | note |",
                  "| :-- | :-- | :-- | :-- | :-- | --: | :-- | :-- |"]
        lines += [f"| {s.step_id} | `{s.action}` | {s.mode} | {s.recorded_model or '?'} → {s.recorded_tokens:,} | {s.model or '?'} → {s.tokens:,} | "
                  f"{s.latency_ms/1000:.2f} s | {'✓' if s.ok else '✗'} | {s.note} |" for s in self.steps]
        lines += ["", "## Token ledger by model / executor", "", "| model / executor | recorded session | this run |", "| :-- | --: | --: |"]
        lines += [f"| {k} | {v['recorded_tokens']:,} | {v['run_tokens']:,} |" for k, v in self.by_model().items()]
        lines += ["", "## Outputs", ""]
        for s in self.steps:
            lines += [f"### {s.step_id} · `{s.action}` — {s.mode}", "", "```", _clip(s.output, 800), "```", ""]
        return "\n".join(lines)


def _escalation_prompt(build_dir: Path, action: str, params: Dict[str, Any], upstream: List[RunStep], recorded_example: str) -> str:
    contract = build_dir / "prompts" / f"{action}.prompt.md"
    contract_text = contract.read_text(encoding="utf-8") if contract.exists() else f"Execute action {action}."
    ctx = "\n\n".join(f"### {s.action} ({s.step_id})\n```\n{_clip(s.output, 4000)}\n```" for s in upstream if s.output)
    return (f"{contract_text}\n\n## This run's parameters\n```json\n{json.dumps(params, ensure_ascii=False)}\n```\n\n"
            f"## Outputs already produced by the compiled steps of this run (use these; do not recompute or re-read files)\n{ctx}\n\n"
            f"## Instruction\nDo exactly what the recorded example did, for this run's parameters. Where the example wrote files "
            f"(apply_patch), write the corresponding files for these parameters (same directory, parameter values substituted in "
            f"file names) with the same structure, using the numbers from the outputs above. Then reply with a short summary.\n")


def run_build(build_dir: Path | str, request: Optional[str] = None, params: Optional[Dict[str, str]] = None,
              escalate: str = "none", binder: str = "regex", escalator: Optional[Escalator] = None,
              out_dir: Optional[Path | str] = None) -> RunReport:
    root = Path(build_dir)
    work_ir = load_work_ir(root / "work.yaml")
    binding = bind_parameters(root, request, params, binder=binder)
    values, synthesized = binding["values"], set(binding["synthesized_actions"])

    from core.runtime.engine import DurableRuntimeEngine
    engine = DurableRuntimeEngine(auto_checkpoint=False)
    load_build_into_engine(engine, root)
    executors = work_ir.to_dict().get("executors", {})
    norm = _normalizer()

    trace_path = root / "trace.json"
    trace = None
    if trace_path.exists():
        payload = json.loads(trace_path.read_text(encoding="utf-8"))
        trace = TraceIR.model_validate(payload["traces"][0] if "traces" in payload else payload.get("trace", payload))

    report = RunReport(work=work_ir.work, build_dir=str(root), request=request or "", params=values, binding=binding["how"])
    if trace is not None:
        report.recorded_tokens = sum(int(getattr(s.token_usage, "total_tokens", 0) or 0) for s in trace.steps)
        report.recorded_latency_ms = sum(float(getattr(s, "latency_ms", 0.0) or 0.0) for s in trace.steps)

    backend = escalator or (codex_escalator if escalate == "codex" else None)
    steps_src = trace.steps if trace is not None else []

    for step in steps_src:
        action = norm(step.action) if step.action else ""
        if action not in work_ir.actions:
            continue
        tier = str(executors.get(action, {}).get("type", "frontier_llm"))
        inputs = step.input if isinstance(step.input, dict) else {}
        recorded_example = normalize_tool_output(step.output.get("tool_result")) if isinstance(step.output, dict) and step.output.get("tool_result") is not None else ""

        if tier in ("code", "rule", "http") and action not in synthesized:
            if _is_self_referential(inputs):
                report.steps.append(RunStep(step.step_id, action, "skipped", 0, 0.0, True, "", "self-referential step not replayed",
                                            model="skipped", recorded_model=str(getattr(step, "model", "") or ""),
                                            recorded_tokens=int(getattr(getattr(step, "token_usage", None), "total_tokens", 0) or 0)))
                continue
            t0 = time.perf_counter()
            os.environ[BENCH_ACTIVE_ENV] = "1"
            try:
                # only bound parameters are passed: recorded cmd/patch must be re-rendered, not reused verbatim
                with telemetry.span("run.step", work=work_ir.work, step=step.step_id, action=action, tier=tier, mode="code") as tspan:
                    result = engine.get_executor(tier).execute(action, dict(values))
                    tspan["success"] = bool(result.success)
            finally:
                os.environ.pop(BENCH_ACTIVE_ENV, None)
            elapsed = (time.perf_counter() - t0) * 1000.0
            out = result.output if isinstance(result.output, dict) else {"value": result.output}
            text = str(out.get("stdout") if "stdout" in out else out.get("content") or json.dumps(out, ensure_ascii=False, default=str))
            note = "" if result.success else f"executor failed: {result.error}"
            if out.get("exit_code") not in (None, 0):
                note = (note + "; " if note else "") + f"exit_code={out.get('exit_code')}"
            report.steps.append(RunStep(step.step_id, action, "code", 0, elapsed, bool(result.success), text, note,
                                        model=tier, recorded_model=str(getattr(step, "model", "") or ""),
                                        recorded_tokens=int(getattr(getattr(step, "token_usage", None), "total_tokens", 0) or 0)))
            continue

        reason = "synthesized content (agent computed it)" if action in synthesized else f"{tier} tier"
        if backend is None:
            report.steps.append(RunStep(step.step_id, action, "needs_agent", 0, 0.0, True, "",
                                        f"{reason}; run with --escalate codex to execute", model="(not run)",
                                        recorded_model=str(getattr(step, "model", "") or ""),
                                        recorded_tokens=int(getattr(getattr(step, "token_usage", None), "total_tokens", 0) or 0)))
            continue
        prompt = _escalation_prompt(root, action, values, report.steps, recorded_example)
        try:
            with telemetry.span("run.escalation", work=work_ir.work, step=step.step_id, action=action, tier=tier,
                                backend=escalate) as tspan:
                res = backend(prompt, {"action": action, "params": values})
                tspan.update({"model": res.get("model"), "tokens": res.get("tokens", 0), "exit_code": res.get("exit_code", 0)})
            ok = res.get("exit_code", 0) == 0
            report.steps.append(RunStep(step.step_id, action, f"escalated:{escalate}", int(res.get("tokens", 0)),
                                        float(res.get("latency_ms", 0.0)), ok, str(res.get("output", "")),
                                        reason if ok else f"{reason}; escalation failed: {_clip(res.get('raw', ''), 300)}",
                                        model=str(res.get("model") or escalate), recorded_model=str(getattr(step, "model", "") or ""),
                                        recorded_tokens=int(getattr(getattr(step, "token_usage", None), "total_tokens", 0) or 0)))
        except Exception as exc:  # noqa: BLE001
            report.steps.append(RunStep(step.step_id, action, f"escalated:{escalate}", 0, 0.0, False, "", f"{reason}; {exc}"))

    t = report.totals()
    telemetry.event("run.report", work=work_ir.work, tokens=t["tokens"], latency_ms=t["latency_ms"], code_steps=t["code_steps"],
                    escalated_steps=t["escalated_steps"], params=json.dumps(values, ensure_ascii=False)[:200])
    out = Path(out_dir) if out_dir else root / "runs"
    out.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (out / f"RUN-{stamp}.md").write_text(report.to_markdown(), encoding="utf-8")
    (out / f"run-{stamp}.json").write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    (out / "RUN_REPORT.md").write_text(report.to_markdown(), encoding="utf-8")
    append_ledger(root, "run", stamp, report.ledger_rows())
    return report
