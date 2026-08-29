"""Parameter discovery and templating for compiled builds.

A recorded session is one concrete run (customer CUST-1001, date 2026-08-29, ...).
To make the compiled build reusable, literals that look like *inputs* are discovered
in the recorded commands/patches, named, and replaced by ``{name}`` placeholders. At
run time a front agent binds fresh values (from a new request) and the handlers render
the templates before executing — flexibility from the agent, efficiency from the code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Optional, Sequence

from core.work_ir import TraceIR

# (regex, namer) — order matters; first match wins
_ID_RE = re.compile(r"\b([A-Z]{2,8})-(\d{2,}[A-Z0-9-]*)\b")
_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

_PREFIX_NAMES = {
    "CUST": "customer_id", "CTR": "contract_id", "ORD": "order_id", "INV": "invoice_id",
    "TKT": "ticket_id", "PO": "po_number", "SKU": "sku", "ACC": "account_id", "USR": "user_id",
}


@dataclass
class Parameter:
    name: str
    recorded_value: str
    kind: str                       # "id" | "date" | "email"
    steps: List[str] = field(default_factory=list)   # step ids whose command/patch mention it
    source: str = "command"         # "request" if it appears in the user's request, else "command"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _command_text(step: Any) -> str:
    inp = step.input if isinstance(step.input, dict) else {}
    cmds = inp.get("cmds") or ([inp["cmd"]] if inp.get("cmd") else [])
    return "\n".join(str(c) for c in cmds)


def _step_text(step: Any) -> str:
    inp = step.input if isinstance(step.input, dict) else {}
    parts = [_command_text(step)]
    if isinstance(inp.get("patch"), str):
        parts.append(inp["patch"])
    return "\n".join(parts)


def _upstream_text(trace: TraceIR, upto_index: int) -> str:
    """Everything the agent had read before a step: request text and earlier tool results."""
    chunks: List[str] = []
    for step in trace.steps[:upto_index]:
        inp = step.input if isinstance(step.input, dict) else {}
        if inp.get("content"):
            chunks.append(str(inp["content"]))
        out = step.output if isinstance(step.output, dict) else {}
        if out.get("tool_result") is not None:
            chunks.append(str(out["tool_result"]))
    return "\n".join(chunks)


def discover_parameters(trace: TraceIR, explicit: Optional[Dict[str, str]] = None) -> List[Parameter]:
    """Find input-like literals used by the recorded commands/patches.

    ``explicit`` ({name: value}) pins parameters the caller already knows; discovered
    literals are added after them. Values that only appear in upstream *outputs* (data
    the agent read) are not parameters — they are derived from the inputs at run time.
    """
    params: Dict[str, Parameter] = {}
    for name, value in (explicit or {}).items():
        params[name] = Parameter(name=name, recorded_value=str(value), kind="explicit", source="explicit")

    request_text = ""
    for step in trace.steps:
        inp = step.input if isinstance(step.input, dict) else {}
        if inp.get("content"):
            request_text = str(inp["content"])
            break

    seen_values = {p.recorded_value for p in params.values()}
    # Candidates come from *commands* the agent typed (a jq filter, a file path): those are the
    # knobs a caller turns. Literals that only appear inside written files (a contract id copied
    # from the CRM) are derived data, not inputs.
    for step in trace.steps:
        for match in _ID_RE.finditer(_command_text(step)):
            value, prefix = match.group(0), match.group(1)
            if value in seen_values:
                continue
            base = _PREFIX_NAMES.get(prefix, prefix.lower() + "_id")
            name, n = base, 2
            while name in params:
                name = f"{base}_{n}"; n += 1
            params[name] = Parameter(name=name, recorded_value=value, kind="id",
                                     source="request" if value in request_text else "command")
            seen_values.add(value)
    for step in trace.steps:
        text = _step_text(step)
        for p in params.values():
            if p.recorded_value in text and step.step_id not in p.steps:
                p.steps.append(step.step_id)
    return list(params.values())


def templatize(text: str, params: Sequence[Parameter]) -> str:
    """Replace recorded parameter values in ``text`` with ``{name}`` placeholders."""
    # longest values first so e.g. CUST-1001-X is not shadowed by CUST-1001
    for p in sorted(params, key=lambda p: -len(p.recorded_value)):
        text = text.replace(p.recorded_value, "{" + p.name + "}")
    return text


def render(template: str, values: Dict[str, Any], defaults: Dict[str, Any]) -> str:
    """Fill ``{name}`` placeholders from values (falling back to recorded defaults)."""
    merged = {**defaults, **{k: v for k, v in values.items() if v is not None}}
    out = template
    for name, value in merged.items():
        out = out.replace("{" + name + "}", str(value))
    return out


_NUMBER_RE = re.compile(r"(?<![\w.-])\d[\d,]*(?:\.\d+)?(?![\w-])")


def synthesized_literals(patch: str, trace: TraceIR, step_index: int, params: Sequence[Parameter]) -> List[str]:
    """Numbers in a written file that neither the inputs nor any upstream tool output contain.

    Such values were computed by the agent (a price, a seat count): replaying the patch
    for different inputs would silently reuse stale numbers, so the step must escalate.
    """
    upstream = _upstream_text(trace, step_index) + "\n" + "\n".join(p.recorded_value for p in params)
    upstream_numbers = set(_NUMBER_RE.findall(upstream))
    found: List[str] = []
    for num in _NUMBER_RE.findall(patch):
        plain = num.replace(",", "")
        if len(plain.replace(".", "")) < 2:
            continue
        if num in upstream_numbers or plain in upstream_numbers or plain in upstream:
            continue
        if num not in found:
            found.append(num)
    return found
