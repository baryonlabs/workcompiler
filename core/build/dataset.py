"""Dataset builder + fleet evaluation for the trained SLM tier.

"Escalate once, replay forever" makes every successful escalation a *training example*; the fleet
corpus (``examples/<work>/fleet/``) adds deterministic ground truth at scale. This module merges
the three evidence sources of a build into one supervised dataset and evaluates candidate models
against held-out customers with the same deterministic gate used for promotion:

* **recorded trace** — the frontier session the build was compiled from,
* **cache entries** — results of past escalations (params, upstream outputs, produced files/answer),
* **fleet truth** — ``fleet/truth/<ID>/`` files computed by the corpus generator.

The dataset rows are chat messages built with the *same* prompt builders the runtime uses
(``slm.build_prompt`` / ``slm.build_file_prompt``), so training and inference distributions match.
Output: ``models/slm/<action>/data/{train,valid}.jsonl`` (mlx-lm LoRA format) plus
``eval.json`` naming the held-out customers.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.build import slm

EVAL_HOLDOUT = 6


# --------------------------------------------------------------------------- fleet corpus access

def fleet_dir(build_dir: Path | str) -> Optional[Path]:
    """The fleet corpus conventionally lives next to the work's example directory."""
    marker = Path(build_dir) / "FLEET"
    if marker.exists():
        path = Path(marker.read_text(encoding="utf-8").strip())
        return path if path.exists() else None
    default = Path("examples/customer-renewal/fleet")
    return default if (default / "truth" / "INDEX.json").exists() else None


def _fleet_upstream(fleet: Path, customer_id: str) -> List[Tuple[str, str]]:
    """What the compiled code steps would print for this customer: the active contract record,
    the customer's usage rows, and the pricing policy."""
    crm = json.loads((fleet / "data" / "crm" / "contracts.json").read_text(encoding="utf-8"))
    contract = next(c for c in crm["contracts"] if c["customer_id"] == customer_id and c["status"] == "active")
    usage_lines = [l for i, l in enumerate((fleet / "data" / "usage" / "usage-2026-07.csv").read_text(encoding="utf-8").splitlines())
                   if i == 0 or l.startswith(customer_id + ",")]
    policy = (fleet.parent / "data" / "pricing" / "pricing_v2.yaml").read_text(encoding="utf-8")
    return [("shell_jq", json.dumps(contract, indent=2)),
            ("shell_cat", "\n".join(usage_lines) + "\n\n" + policy)]


def _fleet_truth_files(fleet: Path, customer_id: str) -> Dict[str, str]:
    tdir = fleet / "truth" / customer_id
    return {f"build/renewal/{p.name}": p.read_text(encoding="utf-8") for p in sorted(tdir.glob("*"))
            if p.name != "respond.md"}


def _file_blocks(files: Dict[str, str]) -> str:
    return "\n".join(f"===FILE {path}===\n{content if content.endswith(chr(10)) else content + chr(10)}===END==="
                     for path, content in sorted(files.items()))


# --------------------------------------------------------------------------- rows

@dataclass
class DatasetReport:
    action: str
    mode: str                          # "files" | "text"
    rows: int = 0
    sources: Dict[str, int] = field(default_factory=dict)
    train_path: str = ""
    valid_path: str = ""
    eval_customers: List[str] = field(default_factory=list)


def _recorded_write_step(build_dir: Path) -> Tuple[Optional[Any], Optional[Any]]:
    from core.build.bench import _normalizer
    from core.work_ir import TraceIR

    trace_path = Path(build_dir) / "trace.json"
    if not trace_path.exists():
        return None, None
    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    trace = TraceIR.model_validate(payload["traces"][0] if "traces" in payload else payload)
    return trace, _normalizer()


def build_rows(build_dir: Path | str, action: str, *, fleet: Optional[Path] = None,
               seed: int = 20260831) -> Tuple[List[Dict[str, Any]], DatasetReport]:
    """One chat row per example. For a derivation step the assistant message is the ===FILE blocks;
    for a text step it is the answer text."""
    root = Path(build_dir)
    trace, norm = _recorded_write_step(root)
    work = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8")).get("work", root.name) \
        if (root / "MANIFEST.json").exists() else root.name
    recorded_step = None
    if trace is not None:
        for s in trace.steps:
            if (norm(s.action) if s.action else "") == action:
                recorded_step = s
                break
    recorded_patch = recorded_step.input.get("patch") if recorded_step is not None and isinstance(recorded_step.input, dict) else None
    mode = "files" if isinstance(recorded_patch, str) and recorded_patch.strip() else "text"
    params_spec = json.loads((root / "PARAMS.json").read_text(encoding="utf-8")) if (root / "PARAMS.json").exists() else {}
    recorded_params = {p["name"]: p["recorded_value"] for p in params_spec.get("params", [])}
    param_name = next(iter(recorded_params), "customer_id")

    rows: List[Dict[str, Any]] = []
    report = DatasetReport(action=action, mode=mode)

    def add(system: str, user: str, assistant: str, source: str, customer: str = "") -> None:
        rows.append({"messages": [{"role": "system", "content": system}, {"role": "user", "content": user},
                                  {"role": "assistant", "content": assistant}], "_source": source, "_customer": customer})
        report.sources[source] = report.sources.get(source, 0) + 1

    # 1) recorded trace example
    if recorded_step is not None and trace is not None:
        idx = trace.steps.index(recorded_step)
        upstream = slm._upstream_from_trace(trace, idx, [norm(s.action) for s in trace.steps if s.action], norm)
        if mode == "files":
            from core.work_ir import patchfmt
            files = {b.path: patchfmt.add_content(b) for b in patchfmt.parse_patch(recorded_patch) if b.op == "Add"}
            system, user = slm.build_file_prompt(action, work, recorded_params, upstream, recorded_patch)
            add(system, user, _file_blocks(files), "recorded", str(recorded_params.get(param_name, "")))
        else:
            content = recorded_step.output.get("content", "") if isinstance(recorded_step.output, dict) else ""
            system, user = slm.build_prompt(root, action, work, recorded_params, upstream, example_output=content,
                                            request=slm.step_request(recorded_step))
            add(system, user, str(content), "recorded", str(recorded_params.get(param_name, "")))

    # 2) cache entries that stored their upstream context
    from core.build import cache as cache_mod
    for entry in cache_mod.entries(root):
        if entry.get("action") != action or not entry.get("upstream"):
            continue
        upstream = [tuple(x) for x in entry["upstream"]]
        params = entry.get("params") or {}
        if mode == "files" and entry.get("files"):
            system, user = slm.build_file_prompt(action, work, params, upstream, recorded_patch or "")
            add(system, user, _file_blocks(entry["files"]), "cache", str(params.get(param_name, "")))
        elif mode == "text" and entry.get("output"):
            example = recorded_step.output.get("content", "") if recorded_step is not None and isinstance(recorded_step.output, dict) else ""
            system, user = slm.build_prompt(root, action, work, params, upstream, example_output=example)
            add(system, user, str(entry["output"]), "cache", str(params.get(param_name, "")))

    # 3) fleet ground truth
    if fleet is not None and (fleet / "truth" / "INDEX.json").exists():
        index = json.loads((fleet / "truth" / "INDEX.json").read_text(encoding="utf-8"))
        for rec in index:
            cid = rec["customer_id"]
            upstream = _fleet_upstream(fleet, cid)
            params = {param_name: cid}
            if mode == "files":
                truth = {p.replace(str(recorded_params.get(param_name, "CUST-1001")), cid): c
                         for p, c in _fleet_truth_files(fleet, cid).items()}
                system, user = slm.build_file_prompt(action, work, params, upstream, recorded_patch or "")
                add(system, user, _file_blocks(truth), "fleet", cid)
            else:
                respond = (fleet / "truth" / cid / "respond.md").read_text(encoding="utf-8")
                pricing = (fleet / "truth" / cid / f"pricing-{cid}.json").read_text(encoding="utf-8")
                example = recorded_step.output.get("content", "") if recorded_step is not None and isinstance(recorded_step.output, dict) else respond
                system, user = slm.build_prompt(root, action, work, params,
                                                upstream + [("write_pricing", f"A build/renewal/pricing-{cid}.json (written)\n[file build/renewal/pricing-{cid}.json]\n{pricing}")],
                                                example_output=example)
                add(system, user, respond.strip(), "fleet", cid)

    report.rows = len(rows)
    return rows, report


def build_dataset(build_dir: Path | str, action: str, *, fleet: Optional[Path] = None, seed: int = 20260831,
                  holdout: int = EVAL_HOLDOUT, holdout_customers: Optional[Sequence[str]] = None) -> DatasetReport:
    """Write train/valid jsonl (mlx-lm chat format) and eval.json under models/slm/<action>/data/.
    ``holdout_customers`` pins the evaluation set (so it stays comparable when the corpus grows)."""
    root = Path(build_dir)
    fleet = fleet or fleet_dir(root)
    rows, report = build_rows(root, action, fleet=fleet, seed=seed)
    fleet_customers = sorted({r["_customer"] for r in rows if r["_source"] == "fleet" and r["_customer"]})
    rng = random.Random(seed)
    if holdout_customers:
        eval_customers = sorted(holdout_customers)
    else:
        eval_customers = sorted(rng.sample(fleet_customers, min(holdout, len(fleet_customers)))) if fleet_customers else []
    train_rows = [r for r in rows if r["_customer"] not in eval_customers]
    rng.shuffle(train_rows)
    n_valid = max(1, len(train_rows) // 10) if len(train_rows) > 3 else 0
    valid_rows, train_rows = train_rows[:n_valid], train_rows[n_valid:]

    out = slm.slm_dir(root, action) / "data"
    out.mkdir(parents=True, exist_ok=True)
    for name, subset in (("train", train_rows), ("valid", valid_rows or train_rows[:1])):
        path = out / f"{name}.jsonl"
        path.write_text("".join(json.dumps({"messages": r["messages"]}, ensure_ascii=False) + "\n" for r in subset),
                        encoding="utf-8")
        setattr(report, f"{name}_path", str(path))
    (out / "eval.json").write_text(json.dumps({"holdout_customers": eval_customers, "seed": seed,
                                               "sources": report.sources}, indent=2) + "\n", encoding="utf-8")
    report.eval_customers = eval_customers
    report.rows = len(train_rows) + len(valid_rows)
    return report


# --------------------------------------------------------------------------- fleet evaluation

@dataclass
class FleetEval:
    model: str
    action: str
    results: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return sum(1 for r in self.results if r["passed"]) / len(self.results) if self.results else 0.0

    def totals(self) -> Dict[str, Any]:
        toks = [r["tokens"] for r in self.results]
        return {"model": self.model, "customers": len(self.results), "passed": sum(1 for r in self.results if r["passed"]),
                "pass_rate": round(self.pass_rate, 3), "avg_tokens": int(sum(toks) / len(toks)) if toks else 0,
                "avg_latency_ms": round(sum(r["latency_ms"] for r in self.results) / len(self.results), 1) if self.results else 0}


def evaluate_fleet(build_dir: Path | str, action: str, runtime: "slm.SLMRuntime", customers: Sequence[str],
                   *, fleet: Optional[Path] = None, transport=None) -> FleetEval:
    """Run the candidate on held-out fleet customers and gate each output against the deterministic
    ground truth (exact values — we generated the answer key)."""
    root = Path(build_dir)
    fleet = fleet or fleet_dir(root)
    trace, norm = _recorded_write_step(root)
    work = root.name
    recorded_step = next((s for s in (trace.steps if trace else []) if (norm(s.action) if s.action else "") == action), None)
    recorded_patch = recorded_step.input.get("patch") if recorded_step is not None and isinstance(recorded_step.input, dict) else None
    mode = "files" if isinstance(recorded_patch, str) and recorded_patch.strip() else "text"
    params_spec = json.loads((root / "PARAMS.json").read_text(encoding="utf-8")) if (root / "PARAMS.json").exists() else {}
    recorded_params = {p["name"]: p["recorded_value"] for p in params_spec.get("params", [])}
    param_name = next(iter(recorded_params), "customer_id")

    ev = FleetEval(model=runtime.model, action=action)
    for cid in customers:
        upstream = _fleet_upstream(fleet, cid)
        params = {param_name: cid}
        truth_respond = (fleet / "truth" / cid / "respond.md").read_text(encoding="utf-8")
        if mode == "files":
            truth = {p.replace(str(recorded_params.get(param_name, "CUST-1001")), cid): c
                     for p, c in _fleet_truth_files(fleet, cid).items()}
            truth_patch = "\n".join(  # exact-mode gate compares against the truth as "recorded"
                slm.patchfmt.render_add(p, c) if hasattr(slm, "patchfmt") else "" for p, c in truth.items())
            from core.work_ir import patchfmt
            truth_patch = patchfmt.wrap([patchfmt.render_add(p, c) for p, c in sorted(truth.items())])
            done = slm.execute_files(root, action, work, params, upstream, runtime=runtime,
                                     recorded_patch=truth_patch, recorded_params=params, exact=True,
                                     trace_id=f"fleet:{cid}", transport=transport)
            ev.results.append({"customer": cid, "passed": done.verdict.passed, "gate": done.verdict.summary(),
                               "tokens": done.result.tokens, "latency_ms": round(done.result.latency_ms, 1),
                               "files": sorted(done.files)})
        else:
            pricing = (fleet / "truth" / cid / f"pricing-{cid}.json").read_text(encoding="utf-8")
            ups = upstream + [("write_pricing", f"A build/renewal/pricing-{cid}.json (written)\n[file build/renewal/pricing-{cid}.json]\n{pricing}")]
            done = slm.execute(root, action, work, params, ups, runtime=runtime, recorded_output=truth_respond,
                               example_output=truth_respond, trace_id=f"fleet:{cid}", transport=transport)
            ev.results.append({"customer": cid, "passed": done.verdict.passed and done.result.ok,
                               "gate": done.verdict.summary(), "tokens": done.result.tokens,
                               "latency_ms": round(done.result.latency_ms, 1)})
    return ev


def eval_markdown(action: str, evals: Sequence[FleetEval], customers: Sequence[str], report: DatasetReport) -> str:
    lines = [f"# Fleet evaluation — `{action}`", "",
             f"Held-out customers (never in the training split): {', '.join(customers)}.",
             f"Dataset: {report.rows} rows ({', '.join(f'{k} {v}' for k, v in report.sources.items())}).", "",
             "| model | pass | pass rate | avg tokens | avg latency |", "| :-- | :-- | --: | --: | --: |"]
    for ev in evals:
        t = ev.totals()
        lines.append(f"| {t['model']} | {t['passed']}/{t['customers']} | {t['pass_rate']:.0%} | {t['avg_tokens']:,} | {t['avg_latency_ms']/1000:.1f} s |")
    lines += ["", "## Per customer", ""]
    for ev in evals:
        lines += [f"### {ev.model}", "", "| customer | gate |", "| :-- | :-- |"]
        lines += [f"| {r['customer']} | {r['gate']} |" for r in ev.results]
        lines.append("")
    return "\n".join(lines)
