# Telemetry (OpenTelemetry) — what it records, where it goes, how to turn it off

OpenWorkCompiler ships with OpenTelemetry-style tracing **enabled by default**, because the whole
point of the project is to *measure* the shift from agent turns to compiled execution. It is
**local by default**: nothing leaves your machine unless you configure an OTLP endpoint.

## What is recorded

Spans with **metadata only** — never prompts, tool outputs, file contents, request bodies or
credentials:

| span | emitted by | attributes |
| :-- | :-- | :-- |
| `proxy.turn` | zero-code proxy, one per captured agent turn | run_id, source_agent, action, model, prompt/completion/total/cached tokens, latency_ms, upstream_status |
| `proxy.compile` | `POST /v1/workcompiler/compile` | run_id, target, steps, build_dir |
| `bench.step`, `bench.report` | `python3 -m core.build bench` | work, run_id, step, action, tier, recorded_model, recorded_tokens, success; totals (tokens, savings %, speedup, outputs matched) |
| `run.step`, `run.escalation`, `run.report` | `python3 -m core.build run` | work, step, action, tier, mode / backend, model, tokens, exit_code; totals |
| `cli.core.build`, `cli.core.openworklang` | the CLIs | command |

Every record also carries `service=openworkcompiler`, a random `trace_id`, start time, duration and status.

## Where it goes

- **Default:** appended as JSON lines to `build/telemetry/spans.jsonl` (override the directory with
  `OPENWORKCOMPILER_TELEMETRY_DIR`). `build/` is git-ignored. Delete the file any time.
- **OTLP export:** install the extra and set the standard OpenTelemetry endpoint variable — spans are
  then also exported through the OpenTelemetry SDK (HTTP/protobuf) to your collector, Jaeger, Tempo,
  Honeycomb, Langfuse, etc.:

  ```bash
  pip install -e ".[telemetry]"
  export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
  # optional: OTEL_EXPORTER_OTLP_HEADERS="authorization=Bearer …"
  ```

  If the endpoint is set but the SDK is not installed, a warning is printed and spans stay local.

## The startup notice

The proxy and the CLIs print one line to stderr when telemetry is on:

```
[telemetry] proxy: OpenTelemetry-style spans are ON (local file build/telemetry/spans.jsonl); metadata only, no prompts or outputs. Disable with OPENWORKCOMPILER_TELEMETRY=off — details: docs/TELEMETRY.md
```

## How to disable

Any one of these turns telemetry off completely (no file, no export, no notice):

```bash
export OPENWORKCOMPILER_TELEMETRY=off        # project switch (accepted: off / 0 / false / no / disabled)
export OTEL_SDK_DISABLED=true                # standard OpenTelemetry switch, also honored
```

Put the line in your shell profile, `.env`, CI environment or the service unit. To disable only the
export but keep local files, unset `OTEL_EXPORTER_OTLP_ENDPOINT`. To remove what was collected:
`rm -rf build/telemetry`.

## Guarantees

- Telemetry never blocks or fails the work: write errors are swallowed.
- Attribute values are truncated to 200 characters and only scalars are kept.
- No endpoint is configured by default and the project does not run its own collector; the
  authors do not receive any data unless you point the exporter at them.
