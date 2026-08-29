"""OpenTelemetry-compatible telemetry for OpenWorkCompiler — on by default, local by default.

What is recorded: spans for proxy passthrough turns, compilations, benchmark/run steps and
CLI compiles, with *metadata only* — action names, executor tiers, model ids, token counts,
latencies, exit codes, run ids. Prompts, tool outputs, file contents and request bodies are
never recorded.

Where it goes:
* default — a local JSON-lines file, ``build/telemetry/spans.jsonl`` (nothing leaves the machine);
* ``OTEL_EXPORTER_OTLP_ENDPOINT`` set *and* the ``telemetry`` extra installed — exported via OTLP
  through the OpenTelemetry SDK (the local file is still written unless disabled).

How to turn it off: ``OPENWORKCOMPILER_TELEMETRY=off`` (or the standard ``OTEL_SDK_DISABLED=true``).
See docs/TELEMETRY.md.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

SERVICE_NAME = "openworkcompiler"
ENV_SWITCH = "OPENWORKCOMPILER_TELEMETRY"
ENV_DIR = "OPENWORKCOMPILER_TELEMETRY_DIR"
_OFF_VALUES = {"0", "off", "false", "no", "disabled"}
_notice_printed = False
_otel_tracer = None
_otel_checked = False


def enabled() -> bool:
    if os.environ.get("OTEL_SDK_DISABLED", "").lower() in {"1", "true", "yes"}:
        return False
    return os.environ.get(ENV_SWITCH, "on").strip().lower() not in _OFF_VALUES


def telemetry_dir() -> Path:
    return Path(os.environ.get(ENV_DIR, "build/telemetry"))


def _spans_file() -> Path:
    return telemetry_dir() / "spans.jsonl"


def _otlp_endpoint() -> Optional[str]:
    return os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")


def _otel() -> Any:
    """Return an OpenTelemetry tracer when the SDK is installed and an OTLP endpoint is configured."""
    global _otel_tracer, _otel_checked
    if _otel_checked:
        return _otel_tracer
    _otel_checked = True
    if not _otlp_endpoint():
        return None
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        print("[telemetry] OTEL_EXPORTER_OTLP_ENDPOINT is set but the OpenTelemetry SDK is not installed; "
              "run: pip install 'openworkcompiler[telemetry]' (spans stay local meanwhile)", file=sys.stderr)
        return None
    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    _otel_tracer = trace.get_tracer(SERVICE_NAME)
    return _otel_tracer


def notice(component: str) -> None:
    """Print the one-time startup notice (stderr) so users know telemetry is on and how to disable it."""
    global _notice_printed
    if _notice_printed or not enabled():
        return
    _notice_printed = True
    where = f"OTLP → {_otlp_endpoint()}" if _otlp_endpoint() else f"local file {_spans_file()}"
    print(f"[telemetry] {component}: OpenTelemetry-style spans are ON ({where}); metadata only, no prompts or "
          f"outputs. Disable with {ENV_SWITCH}=off — details: docs/TELEMETRY.md", file=sys.stderr)


def _write_local(record: Dict[str, Any]) -> None:
    try:
        path = _spans_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass  # telemetry must never break the work


def _clean(attrs: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in attrs.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            out[k] = v if not isinstance(v, str) else v[:200]
        else:
            out[k] = str(v)[:200]
    return out


@contextmanager
def span(name: str, **attrs: Any) -> Iterator[Dict[str, Any]]:
    """Record a span. Yields a dict; keys added to it become attributes when the span ends."""
    if not enabled():
        yield {}
        return
    extra: Dict[str, Any] = {}
    start = time.time()
    t0 = time.perf_counter()
    otel = _otel()
    status = "ok"
    error = None
    if otel is not None:
        cm = otel.start_as_current_span(name)
        otel_span = cm.__enter__()
    else:
        cm = otel_span = None
    try:
        yield extra
    except BaseException as exc:  # noqa: BLE001 - re-raised below
        status, error = "error", f"{type(exc).__name__}: {exc}"[:200]
        raise
    finally:
        duration_ms = (time.perf_counter() - t0) * 1000.0
        attributes = _clean({**attrs, **extra})
        record = {"service": SERVICE_NAME, "span": name, "trace_id": uuid.uuid4().hex[:16],
                  "start": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(start)), "duration_ms": round(duration_ms, 2),
                  "status": status, "error": error, "attributes": attributes}
        _write_local(record)
        if otel_span is not None:
            for k, v in attributes.items():
                try:
                    otel_span.set_attribute(k, v)
                except Exception:
                    pass
            cm.__exit__(None, None, None)


def event(name: str, **attrs: Any) -> None:
    """Record a zero-duration span (a point event), e.g. tokens spent by one escalation."""
    with span(name, **attrs):
        pass
