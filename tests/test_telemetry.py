"""Telemetry: on by default, local only, metadata only, and easy to switch off."""

import json

from core import telemetry


def test_span_writes_local_jsonl_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENWORKCOMPILER_TELEMETRY", raising=False)
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setenv("OPENWORKCOMPILER_TELEMETRY_DIR", str(tmp_path))
    assert telemetry.enabled()
    with telemetry.span("unit.test", action="shell_ls", model="gpt-x", total_tokens=12, secret_prompt=None) as extra:
        extra["success"] = True
    rows = [json.loads(l) for l in (tmp_path / "spans.jsonl").read_text().splitlines()]
    assert rows[-1]["span"] == "unit.test" and rows[-1]["status"] == "ok"
    assert rows[-1]["attributes"] == {"action": "shell_ls", "model": "gpt-x", "total_tokens": 12, "success": True}


def test_env_switch_disables_everything(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENWORKCOMPILER_TELEMETRY_DIR", str(tmp_path))
    for var, val in [("OPENWORKCOMPILER_TELEMETRY", "off"), ("OTEL_SDK_DISABLED", "true")]:
        monkeypatch.delenv("OPENWORKCOMPILER_TELEMETRY", raising=False)
        monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
        monkeypatch.setenv(var, val)
        assert not telemetry.enabled()
        with telemetry.span("unit.off", x=1):
            pass
        assert not (tmp_path / "spans.jsonl").exists()


def test_errors_are_recorded_and_re_raised(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENWORKCOMPILER_TELEMETRY", raising=False)
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    monkeypatch.setenv("OPENWORKCOMPILER_TELEMETRY_DIR", str(tmp_path))
    try:
        with telemetry.span("unit.err"):
            raise ValueError("boom")
    except ValueError:
        pass
    row = json.loads((tmp_path / "spans.jsonl").read_text().splitlines()[-1])
    assert row["status"] == "error" and row["error"].startswith("ValueError")
