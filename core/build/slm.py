"""SLM tier: run an action with a small local model, gate its output, promote / demote.

The 8-tier lowering promises that a step which stays with a frontier LLM after compilation
(typically the final ``respond`` summary) moves down to a *small language model* once its
quality is proven. This module makes that promise concrete without any training run:

* **inference** — any OpenAI-compatible endpoint serving a small model (Ollama by default,
  ``OPENWORKCOMPILER_SLM_BASE_URL`` / ``OPENWORKCOMPILER_SLM_MODEL``); real token counts and
  latency come back from the server, cost is 0.
* **prompt** — the compiled *upstream outputs* of the run plus the action's prompt contract
  (``prompts/<action>.prompt.md``) and a *masked* recorded example: numbers, ids and paths in the
  example are blanked so the model must ground every fact in this run's outputs instead of
  copying the recording. The prompt is a few thousand tokens instead of the agent's full
  session context (17k–33k tokens per ``respond`` in the recorded sessions).
* **gate** — deterministic, evidence-based: *anchor recall* (facts the frontier model stated
  that exist in the upstream data must appear again), *grounding precision* (no numbers that
  exist neither in the upstream outputs nor in the recording), length bounds. Each evaluation
  becomes a ``QualityRecord`` and the existing ``ExecutorOptimizer.evaluate_promotion`` gate
  decides.
* **promotion** — writes ``models/slm/<action>/{runtime.json, promotion.json, PROMOTION.md,
  quality_records.jsonl}`` and flips the executor in ``work.yaml`` and the ``.work`` source
  (``respond: slm``) with the previous executor kept for ``demote``.

Fine-tuning (``models/slm/<action>/train.py``, TRL) stays the next stage once a dataset larger
than a handful of recorded examples exists; nothing here pretends one example trains a model.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from core.validation.quality_record import QualityRecord, evaluate_quality_fold

DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_MODEL = "qwen2.5:3b"
ENV_BASE_URL = "OPENWORKCOMPILER_SLM_BASE_URL"
ENV_MODEL = "OPENWORKCOMPILER_SLM_MODEL"
RUNTIME_FILE = "runtime.json"
PROMOTION_FILE = "promotion.json"


# --------------------------------------------------------------------------- runtime + inference

@dataclass
class SLMRuntime:
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    max_tokens: int = 700
    temperature: float = 0.0
    timeout_s: int = 240
    min_quality: float = 0.9          # promotion gate: fraction of evaluations that must PASS
    min_recall: float = 0.9           # per evaluation: anchor facts of the recording that must reappear
    min_precision: float = 0.9        # per evaluation: numbers/ids that must be grounded in the inputs
    max_length_ratio: float = 3.0     # output may be at most this many times the recorded length

    @classmethod
    def defaults(cls, model: Optional[str] = None, base_url: Optional[str] = None) -> "SLMRuntime":
        return cls(model=model or os.environ.get(ENV_MODEL) or DEFAULT_MODEL,
                   base_url=(base_url or os.environ.get(ENV_BASE_URL) or DEFAULT_BASE_URL).rstrip("/"))

    @classmethod
    def load(cls, build_dir: Path | str, action: str) -> Optional["SLMRuntime"]:
        path = slm_dir(build_dir, action) / RUNTIME_FILE
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self, build_dir: Path | str, action: str) -> Path:
        path = slm_dir(build_dir, action) / RUNTIME_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"backend": "openai_compat", **asdict(self)}, indent=2) + "\n", encoding="utf-8")
        return path


@dataclass
class SLMResult:
    output: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    model: str = ""
    error: str = ""

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def ok(self) -> bool:
        return not self.error

    def to_escalation_dict(self) -> Dict[str, Any]:
        return {"output": self.output, "tokens": self.tokens, "latency_ms": self.latency_ms,
                "exit_code": 0 if self.ok else 1, "model": self.model, "raw": self.error,
                "prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens,
                "cached_tokens": 0, "cost_usd": 0.0}


Transport = Callable[[str, Dict[str, Any], int], Dict[str, Any]]


def _http_post_json(url: str, payload: Dict[str, Any], timeout_s: int) -> Dict[str, Any]:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 — localhost model server
        return json.loads(resp.read().decode("utf-8"))


def slm_dir(build_dir: Path | str, action: str) -> Path:
    return Path(build_dir) / "models" / "slm" / action


def is_promoted(build_dir: Path | str, action: str) -> bool:
    return (slm_dir(build_dir, action) / RUNTIME_FILE).exists()


def infer(system: str, user: str, runtime: SLMRuntime, transport: Optional[Transport] = None) -> SLMResult:
    """One chat completion against the runtime's endpoint; usage/latency are measured, never estimated."""
    transport = transport or _http_post_json
    payload = {"model": runtime.model, "temperature": runtime.temperature, "max_tokens": runtime.max_tokens,
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    t0 = time.perf_counter()
    try:
        data = transport(f"{runtime.base_url}/chat/completions", payload, runtime.timeout_s)
    except urllib.error.URLError as exc:
        return SLMResult("", model=runtime.model, latency_ms=(time.perf_counter() - t0) * 1000.0,
                         error=f"SLM endpoint unreachable at {runtime.base_url}: {exc.reason}")
    except Exception as exc:  # noqa: BLE001
        return SLMResult("", model=runtime.model, latency_ms=(time.perf_counter() - t0) * 1000.0, error=f"SLM call failed: {exc}")
    latency = (time.perf_counter() - t0) * 1000.0
    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return SLMResult("", model=runtime.model, latency_ms=latency, error=f"unexpected SLM response: {str(data)[:200]}")
    usage = data.get("usage") or {}
    return SLMResult(str(text).strip(), int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0),
                     latency, str(data.get("model") or runtime.model))


# --------------------------------------------------------------------------- facts + gate

_NUM_RE = re.compile(r"(?<![\w./-])[-+]?\d[\d,]*(?:\.\d+)?%?(?![\w-])")
_ID_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,}-[A-Z0-9-]*\d[A-Z0-9-]*\b")
_PATH_RE = re.compile(r"(?<![\w-])(?:[\w.-]+/)+[\w.-]+\.(?:md|json|ya?ml|csv|txt|py|xml|html)\b")
_MASK = "<value>"


def _norm_number(token: str) -> Optional[str]:
    t = token.replace(",", "").rstrip("%").lstrip("+")
    if not any(ch.isdigit() for ch in t):
        return None
    try:
        value = float(t)
    except ValueError:
        return None
    if abs(value) < 10 and "." not in t:      # single digits are list markers / step numbers, not facts
        return None
    return f"{value:.4f}".rstrip("0").rstrip(".")


_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def extract_facts(text: str) -> Dict[str, set]:
    """Grounding units of a text: numbers (normalized), ids like CUST-1001, file paths, ISO dates."""
    numbers = {n for n in (_norm_number(m.group(0)) for m in _NUM_RE.finditer(text)) if n}
    dates = {m.group(0) for m in _DATE_RE.finditer(text)}
    numbers |= {m.group(1) for m in _DATE_RE.finditer(text)}      # a re-formatted date still names its year
    ids = set(_ID_RE.findall(text))
    paths = {p.lstrip("./") for p in _PATH_RE.findall(text)}
    return {"numbers": numbers, "ids": ids, "paths": paths, "dates": dates}


def _flat(facts: Dict[str, set]) -> set:
    return {f"{k}:{v}" for k, vs in facts.items() for v in vs}


def anchors(recorded_output: str, context: str) -> set:
    """Facts the recorded (frontier) answer stated that are grounded in the upstream outputs —
    the checklist a cheaper executor must reproduce."""
    rec, ctx = _flat(extract_facts(recorded_output)), _flat(extract_facts(context))
    return rec & ctx


def mask_facts(text: str) -> str:
    """Blank numbers, ids and paths so an example conveys structure and tone, not answers."""
    out = _ID_RE.sub(_MASK, text)
    out = _PATH_RE.sub(_MASK, out)
    out = _DATE_RE.sub(_MASK, out)
    return _NUM_RE.sub(lambda m: m.group(0) if _norm_number(m.group(0)) is None else _MASK, out)


@dataclass
class GateResult:
    passed: bool
    recall: float
    precision: float
    length_ratio: float
    missing: List[str] = field(default_factory=list)
    ungrounded: List[str] = field(default_factory=list)
    checks: Dict[str, bool] = field(default_factory=dict)

    @property
    def score(self) -> float:
        return round(min(self.recall, self.precision), 3)

    def summary(self) -> str:
        parts = [f"recall {self.recall:.2f}", f"grounded {self.precision:.2f}", f"len ×{self.length_ratio:.1f}"]
        for name, ok in self.checks.items():
            if not ok and name in ("no_placeholder", "fact_density", "non_empty"):
                parts.append(name.replace("_", " ") + " failed")
        if self.missing:
            parts.append("missing " + ", ".join(self.missing[:4]))
        if self.ungrounded:
            parts.append("ungrounded " + ", ".join(self.ungrounded[:4]))
        return ("PASS" if self.passed else "FAIL") + " (" + "; ".join(parts) + ")"


def gate(output: str, *, context: str, recorded_output: str = "", required: Optional[set] = None,
         runtime: Optional[SLMRuntime] = None, params: Optional[Dict[str, Any]] = None, min_facts: int = 0) -> GateResult:
    """Deterministic quality gate for a generated text.

    * recall — every anchor (fact of the recording grounded in the context, or ``required``) reappears
    * precision — every number/id/path the output states exists in the context or the recording
    * length — bounded relative to the recording (when one is given)
    * min_facts — for new-parameter runs (no recording to anchor on): the message must state at least
      as many grounded facts as the recorded answer did, and never the literal placeholder
    """
    rt = runtime or SLMRuntime()
    req = set(required) if required is not None else anchors(recorded_output, context)
    for value in (params or {}).values():
        req |= _flat(extract_facts(str(value)))
    got = _flat(extract_facts(output))
    allowed = _flat(extract_facts(context)) | _flat(extract_facts(recorded_output)) | req
    missing = sorted(req - got)
    ungrounded = sorted(got - allowed)
    recall = 1.0 if not req else 1.0 - len(missing) / len(req)
    precision = 1.0 if not got else 1.0 - len(ungrounded) / len(got)
    length_ratio = (len(output) / len(recorded_output)) if recorded_output else 1.0
    checks = {
        "non_empty": bool(output.strip()),
        "anchor_recall": recall >= rt.min_recall,
        "grounded": precision >= rt.min_precision,
        "length": length_ratio <= rt.max_length_ratio,
        "no_placeholder": _MASK not in output,
        "fact_density": len(got & allowed) >= min_facts,
    }
    return GateResult(all(checks.values()), round(recall, 3), round(precision, 3), round(length_ratio, 2),
                      [m.split(":", 1)[1] for m in missing], [u.split(":", 1)[1] for u in ungrounded], checks)


def quality_record(trace_id: str, action: str, result: SLMResult, verdict: GateResult,
                   invariants: Sequence[str] = ()) -> QualityRecord:
    """Fold one SLM evaluation into the project's QualityRecord so the optimizer's gate can judge it."""
    behavior = {"grounded_in_upstream_outputs": "true" if verdict.checks.get("grounded") else "false"}
    for inv in invariants:
        behavior[inv] = "na"      # process invariants were enforced by the compiled upstream steps, not by the text
    return QualityRecord(trace_id=trace_id, action_name=action, executor_type="slm",
                         automated_checks=dict(verdict.checks) | {"inference_ok": result.ok},
                         behavior_verdicts=behavior, execution_cost=0.0, execution_latency_ms=result.latency_ms,
                         metadata={"model": result.model, "prompt_tokens": result.prompt_tokens,
                                   "completion_tokens": result.completion_tokens, "score": verdict.score,
                                   "recall": verdict.recall, "precision": verdict.precision,
                                   "missing": verdict.missing, "ungrounded": verdict.ungrounded})


# --------------------------------------------------------------------------- prompt

def _contract(build_dir: Path | str, action: str) -> Tuple[str, List[str]]:
    """(system prompt lines, invariants) from prompts/<action>.prompt.md."""
    path = Path(build_dir) / "prompts" / f"{action}.prompt.md"
    if not path.exists():
        return "", []
    text = path.read_text(encoding="utf-8")
    inv: List[str] = []
    m = re.search(r"## Invariants \(must hold\)\n\n(.*?)(?:\n## |\Z)", text, re.S)
    if m:
        inv = [l[2:].strip() for l in m.group(1).splitlines() if l.startswith("- ") and "(none" not in l]
    sm = re.search(r"## System prompt\n\n(.*?)(?:\n## |\Z)", text, re.S)
    return (sm.group(1).strip() if sm else ""), inv


def _clip(text: str, limit: int) -> str:
    text = str(text)
    return text if len(text) <= limit else text[:limit] + f"\n… [{len(text) - limit} more chars]"


def build_prompt(build_dir: Path | str, action: str, work: str, params: Dict[str, Any],
                 upstream: Sequence[Tuple[str, str]], example_output: str = "", request: str = "",
                 per_output_chars: int = 2500) -> Tuple[str, str]:
    """(system, user) for the SLM: contract invariants, the request, this run's upstream outputs, and —
    last, so a small model keeps it in focus — the masked example with an explicit length target."""
    _contract_text, invariants = _contract(build_dir, action)
    inv = "\n".join(f"- {i}" for i in invariants) or "- (none declared)"
    system = (f"You are the `{action}` step of the compiled work `{work}`: you write the final message a person reads.\n"
              "Rules:\n"
              "1. Every number, id, date and file path in your message must be copied from the OUTPUTS section. Never invent, "
              "recompute, convert or round values.\n"
              f"2. Follow the EXAMPLE's structure, tone, formatting and length exactly. In the example every value was replaced "
              f"by the placeholder {_MASK}; fill each one with the matching value from the OUTPUTS. Never write the placeholder itself.\n"
              "3. Output only the message: no reasoning, no preamble, no code fences around the whole message, nothing after it.\n"
              f"\nInvariants that the earlier steps already enforced:\n{inv}")
    ctx = "\n\n".join(f"### {name}\n```\n{_clip(out, per_output_chars)}\n```" for name, out in upstream if str(out).strip())
    parts = [f"## PARAMETERS of this run\n```json\n{json.dumps(params, ensure_ascii=False)}\n```"]
    if request:
        parts.append(f"## REQUEST this message answers\n{_clip(request, 1500)}")
    parts.append(f"## OUTPUTS produced by the earlier steps of this run\n{ctx or '(none)'}")
    if example_output:
        words = len(example_output.split())
        parts.append(f"## EXAMPLE (previous run, values masked with {_MASK}) — your message must have the same shape and "
                     f"about {words} words\n{mask_facts(example_output)}")
    parts.append(f"Write the `{action}` message for this run now.")
    return system, "\n\n".join(parts)


# --------------------------------------------------------------------------- execute (bench / run seam)

@dataclass
class SLMStep:
    result: SLMResult
    verdict: GateResult
    record: QualityRecord
    system: str
    user: str


def execute(build_dir: Path | str, action: str, work: str, params: Dict[str, Any], upstream: Sequence[Tuple[str, str]],
            *, runtime: SLMRuntime, recorded_output: str = "", example_output: str = "", trace_id: str = "",
            transport: Optional[Transport] = None, invariants: Sequence[str] = (), request: str = "",
            min_facts: int = 0) -> SLMStep:
    """Run the action with the SLM and gate it. ``recorded_output`` (same inputs) enables anchor recall;
    ``example_output`` is shown masked as a style example (use the recording for new-parameter runs)."""
    system, user = build_prompt(build_dir, action, work, params, upstream, example_output, request=request)
    result = infer(system, user, runtime, transport)
    context = "\n".join(str(out) for _, out in upstream)
    verdict = gate(result.output, context=context, recorded_output=recorded_output, runtime=runtime, params=params,
                   min_facts=min_facts) if result.ok \
        else GateResult(False, 0.0, 0.0, 0.0, checks={"inference_ok": False})
    return SLMStep(result, verdict, quality_record(trace_id, action, result, verdict, invariants), system, user)


# --------------------------------------------------------------------------- promotion

@dataclass
class Evaluation:
    step_id: str
    result: SLMResult
    verdict: GateResult
    recorded_tokens: int
    recorded_latency_ms: float
    recorded_model: str
    recorded_output: str

    def to_dict(self) -> Dict[str, Any]:
        return {"step_id": self.step_id, "model": self.result.model, "output": self.result.output,
                "prompt_tokens": self.result.prompt_tokens, "completion_tokens": self.result.completion_tokens,
                "tokens": self.result.tokens, "latency_ms": round(self.result.latency_ms, 1), "error": self.result.error,
                "gate": self.verdict.summary(), "score": self.verdict.score, "checks": self.verdict.checks,
                "missing": self.verdict.missing, "ungrounded": self.verdict.ungrounded,
                "recorded_model": self.recorded_model, "recorded_tokens": self.recorded_tokens,
                "recorded_latency_ms": round(self.recorded_latency_ms, 1)}


@dataclass
class PromotionReport:
    work: str
    action: str
    build_dir: str
    runtime: SLMRuntime
    evaluations: List[Evaluation] = field(default_factory=list)
    records: List[QualityRecord] = field(default_factory=list)
    promoted: bool = False
    previous_executor: Dict[str, Any] = field(default_factory=dict)
    dry_run: bool = False

    @property
    def pass_rate(self) -> float:
        if not self.records:
            return 0.0
        return sum(1 for r in self.records if evaluate_quality_fold(r) == "PASS") / len(self.records)

    def totals(self) -> Dict[str, Any]:
        rt = sum(e.recorded_tokens for e in self.evaluations)
        st = sum(e.result.tokens for e in self.evaluations)
        rl = sum(e.recorded_latency_ms for e in self.evaluations)
        sl = sum(e.result.latency_ms for e in self.evaluations)
        return {"evaluations": len(self.evaluations), "pass_rate": round(self.pass_rate, 3),
                "recorded_tokens": rt, "slm_tokens": st, "token_savings_pct": round(100.0 * (rt - st) / rt, 1) if rt else None,
                "recorded_latency_ms": round(rl, 1), "slm_latency_ms": round(sl, 1),
                "speedup_x": round(rl / sl, 2) if sl else None, "promoted": self.promoted}

    def to_dict(self) -> Dict[str, Any]:
        return {"work": self.work, "action": self.action, "build_dir": self.build_dir, "runtime": asdict(self.runtime),
                "totals": self.totals(), "evaluations": [e.to_dict() for e in self.evaluations],
                "previous_executor": self.previous_executor, "dry_run": self.dry_run,
                "at": time.strftime("%Y-%m-%dT%H:%M:%S")}

    def to_markdown(self) -> str:
        t = self.totals()
        lines = [f"# SLM promotion — `{self.action}` of `{self.work}`", "",
                 f"Candidate: `{self.runtime.model}` at `{self.runtime.base_url}` (local, cost $0) · "
                 f"gate: ≥{self.runtime.min_quality:.0%} of evaluations PASS, anchor recall ≥{self.runtime.min_recall:.0%}, "
                 f"grounding ≥{self.runtime.min_precision:.0%}.", "",
                 f"**Result: {'PROMOTED' if self.promoted else ('would promote (dry run)' if self.dry_run and t['pass_rate'] >= self.runtime.min_quality else 'NOT promoted')}** — "
                 f"pass rate {t['pass_rate']:.0%} over {t['evaluations']} recorded example(s).", "",
                 "| | recorded (frontier) | SLM | delta |", "| :-- | --: | --: | --: |",
                 f"| tokens | {t['recorded_tokens']:,} | {t['slm_tokens']:,} | " + (f"−{t['token_savings_pct']}%" if t['token_savings_pct'] is not None else "n/a") + " |",
                 f"| latency | {t['recorded_latency_ms']/1000:.1f} s | {t['slm_latency_ms']/1000:.1f} s | " + (f"{t['speedup_x']}×" if t['speedup_x'] else "n/a") + " |",
                 "", "## Evaluations", "",
                 "| step | recorded model → tokens | SLM tokens (prompt + completion) | latency | gate |", "| :-- | :-- | --: | --: | :-- |"]
        for e in self.evaluations:
            lines.append(f"| {e.step_id} | {e.recorded_model or '?'} → {e.recorded_tokens:,} | "
                         f"{e.result.tokens:,} ({e.result.prompt_tokens:,} + {e.result.completion_tokens:,}) | "
                         f"{e.result.latency_ms/1000:.1f} s | {e.verdict.summary()} |")
        for e in self.evaluations:
            lines += ["", f"### {e.step_id} — SLM output", "", "```", _clip(e.result.output or e.result.error, 2500), "```",
                      "", "Recorded (frontier) output:", "", "```", _clip(e.recorded_output, 2500), "```"]
        lines += ["", "How the gate works: *anchors* are the numbers / ids / file paths the frontier answer stated that also exist "
                  "in the upstream step outputs; the SLM must restate them (recall) and must not state numbers that exist "
                  "nowhere in its inputs (grounding). Process invariants are enforced by the compiled upstream steps."]
        return "\n".join(lines) + "\n"


def expand_files(text: str, cwd: Path | str = ".", per_file_chars: int = 3000, limit: int = 6) -> str:
    """Append the content of files mentioned in ``text`` (written by earlier steps) so the model sees the
    data itself, not just the line that says it was written."""
    seen: List[str] = []
    for m in _PATH_RE.finditer(text):
        rel = m.group(0)
        if rel in seen:
            continue
        candidates = [Path(cwd) / rel, Path(rel)]
        for path in candidates:
            if path.is_file():
                seen.append(rel)
                break
    parts = [text]
    for rel in seen[:limit]:
        path = (Path(cwd) / rel) if (Path(cwd) / rel).is_file() else Path(rel)
        try:
            parts.append(f"\n[file {rel}]\n{_clip(path.read_text(encoding='utf-8'), per_file_chars)}")
        except Exception:  # noqa: BLE001
            continue
    return "\n".join(parts)


def step_context(step_input: Dict[str, Any], output_text: str, cwd: Path | str = ".") -> str:
    """What a downstream SLM should see for one executed step: its output, the patch it applied (the
    data the agent wrote), and the current content of files it mentions."""
    parts = [output_text or ""]
    patch = step_input.get("patch") if isinstance(step_input, dict) else None
    if isinstance(patch, str) and patch.strip():
        parts.append("[written by this step]\n" + _clip(patch, 4000))
    return expand_files("\n".join(parts), cwd)


def _upstream_from_trace(trace: Any, upto_index: int, actions: Sequence[str], norm: Callable[[str], str]) -> List[Tuple[str, str]]:
    from core.build.bench import _recorded_output

    out: List[Tuple[str, str]] = []
    for s in trace.steps[:upto_index]:
        a = norm(s.action) if s.action else ""
        if a in actions:
            inp = s.input if isinstance(s.input, dict) else {}
            text = _recorded_output(s)
            patch = inp.get("patch")
            if text or (isinstance(patch, str) and patch.strip()):
                # recorded context: outputs + written data (files on disk may have changed since; use the patch)
                out.append((a, (text or "") + ("\n[written by this step]\n" + _clip(patch, 4000) if isinstance(patch, str) and patch.strip() else "")))
    return out


def evaluate(build_dir: Path | str, action: str, runtime: SLMRuntime, *, transport: Optional[Transport] = None,
             trace: Any = None) -> PromotionReport:
    """Run the SLM on every recorded occurrence of ``action`` (upstream = the recorded outputs of the
    earlier steps) and gate each against the recorded frontier answer."""
    from core.build.bench import _normalizer, _recorded_output, _step_model, _step_tokens
    from core.work_ir import TraceIR, load_work_ir

    root = Path(build_dir)
    work_ir = load_work_ir(root / "work.yaml")
    if trace is None:
        payload = json.loads((root / "trace.json").read_text(encoding="utf-8"))
        trace = TraceIR.model_validate(payload["traces"][0] if "traces" in payload else payload.get("trace", payload))
    executors = work_ir.to_dict().get("executors", {})
    report = PromotionReport(work_ir.work, action, str(root), runtime, previous_executor=dict(executors.get(action, {})))
    params_spec = json.loads((root / "PARAMS.json").read_text(encoding="utf-8")) if (root / "PARAMS.json").exists() else {}
    params = {p["name"]: p["recorded_value"] for p in params_spec.get("params", [])}
    norm = _normalizer()
    for idx, step in enumerate(trace.steps):
        if (norm(step.action) if step.action else "") != action:
            continue
        recorded = _recorded_output(step)
        upstream = _upstream_from_trace(trace, idx, work_ir.actions, norm)
        # the recording is the ground truth: it is shown only *masked* (structure/tone, no values), so every
        # fact in the SLM's answer has to come from the upstream outputs — that is what the gate checks
        done = execute(root, action, work_ir.work, params, upstream, runtime=runtime, recorded_output=recorded,
                       example_output=recorded, trace_id=f"{trace.run_id}:{step.step_id}", transport=transport,
                       invariants=work_ir.invariants or [], request=step_request(step))
        report.evaluations.append(Evaluation(step.step_id, done.result, done.verdict, _step_tokens(step),
                                             float(getattr(step, "latency_ms", 0.0) or 0.0), _step_model(step), recorded))
        report.records.append(done.record)
    return report


def expected_fact_count(trace: Any, step_index: int, actions: Sequence[str], norm: Callable[[str], str],
                        slack: float = 0.7) -> int:
    """How many grounded facts a new-parameter run must state: ``slack`` × the number the recorded answer
    of ``trace.steps[step_index]`` stated (other parameters legitimately have fewer multi-digit values)."""
    from core.build.bench import _recorded_output

    step = trace.steps[step_index]
    context = "\n".join(out for _, out in _upstream_from_trace(trace, step_index, actions, norm))
    n = len(anchors(_recorded_output(step), context))
    return max(1, int(round(n * slack))) if n else 0


def step_request(step: Any) -> str:
    """The instruction the recorded step answered (its ``input.content`` — the user's message or skill text)."""
    inp = step.input if isinstance(getattr(step, "input", None), dict) else {}
    text = inp.get("content") or inp.get("raw_args") or ""
    return str(text) if isinstance(text, (str, int, float)) else ""


def _flip_work_source(root: Path, action: str, tier: str) -> Optional[Path]:
    for path in root.glob("*.work"):
        text = path.read_text(encoding="utf-8")
        new, n = re.subn(rf"^(\s+){re.escape(action)}: \w+,$", rf"\g<1>{action}: {tier},", text, count=1, flags=re.M)
        if n:
            path.write_text(new, encoding="utf-8")
            return path
    return None


def _update_manifest(root: Path, entry: Dict[str, Any]) -> None:
    path = root / "MANIFEST.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("promotions", []).append(entry)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def promote(build_dir: Path | str, action: str, runtime: Optional[SLMRuntime] = None, *, dry_run: bool = False,
            transport: Optional[Transport] = None, trace: Any = None) -> PromotionReport:
    """Evaluate and, when the gate passes, switch ``action`` to the SLM tier in the build."""
    from core.optimizer.optimizer import ExecutorOptimizer
    from core.work_ir import load_work_ir, save_work_ir

    root = Path(build_dir)
    rt = runtime or SLMRuntime.defaults()
    report = evaluate(root, action, rt, transport=transport, trace=trace)
    report.dry_run = dry_run
    passed = ExecutorOptimizer().evaluate_promotion(action, "slm", report.records, min_quality=rt.min_quality,
                                                    min_behavior_compliance=1.0)
    out_dir = slm_dir(root, action)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "quality_records.jsonl").open("a", encoding="utf-8").write(
        "".join(json.dumps(r.to_dict() if hasattr(r, "to_dict") else asdict(r), ensure_ascii=False, default=str) + "\n" for r in report.records))
    if passed and not dry_run:
        rt.save(root, action)
        work_ir = load_work_ir(root / "work.yaml")
        executors = work_ir.executors if isinstance(getattr(work_ir, "executors", None), dict) else {}
        previous = executors.get(action)
        prev_dict = previous.model_dump() if hasattr(previous, "model_dump") else dict(previous or {})
        report.previous_executor = prev_dict
        new_spec = {"type": "slm", "preferred": rt.model, "fallback": ["frontier_llm", "human"],
                    "runtime": str((out_dir / RUNTIME_FILE).relative_to(root))}
        executors[action] = type(previous)(**new_spec) if previous is not None and hasattr(previous, "model_dump") else new_spec
        save_work_ir(work_ir, root / "work.yaml")
        _flip_work_source(root, action, "slm")
        (out_dir / PROMOTION_FILE).write_text(json.dumps({"action": action, "to": "slm", "model": rt.model,
                                                          "previous_executor": prev_dict, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                                          "totals": report.totals()}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _update_manifest(root, {"action": action, "from": prev_dict.get("type", "frontier_llm"), "to": "slm", "model": rt.model,
                                "pass_rate": report.pass_rate, "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
        report.promoted = True
    (out_dir / "PROMOTION.md").write_text(report.to_markdown(), encoding="utf-8")
    (out_dir / "promotion_eval.json").write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def demote(build_dir: Path | str, action: str) -> Dict[str, Any]:
    """Roll the action back to the executor recorded in promotion.json."""
    from core.work_ir import load_work_ir, save_work_ir

    root = Path(build_dir)
    out_dir = slm_dir(root, action)
    info_path = out_dir / PROMOTION_FILE
    if not info_path.exists():
        raise FileNotFoundError(f"{action} is not promoted in {root} (no {info_path})")
    info = json.loads(info_path.read_text(encoding="utf-8"))
    previous = info.get("previous_executor") or {"type": "frontier_llm", "fallback": ["human"]}
    work_ir = load_work_ir(root / "work.yaml")
    current = work_ir.executors.get(action)
    work_ir.executors[action] = type(current)(**previous) if current is not None and hasattr(current, "model_dump") else previous
    save_work_ir(work_ir, root / "work.yaml")
    tier = str(previous.get("type", "frontier_llm"))
    _flip_work_source(root, action, "llm" if tier == "frontier_llm" else tier)
    for name in (RUNTIME_FILE, PROMOTION_FILE):
        p = out_dir / name
        if p.exists():
            p.unlink()
    _update_manifest(root, {"action": action, "from": "slm", "to": tier, "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    return {"action": action, "restored": previous}
