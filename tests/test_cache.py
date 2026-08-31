"""Escalate once, replay forever: parameter-keyed cache of agent/SLM results inside the build."""

import json
from pathlib import Path

from core.build import cache
from tests.test_slm import PATCH, GOOD_1002, _fake_transport, _write_build
from core.build import slm


def test_store_and_lookup_roundtrip_with_file_capture(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "pricing-CUST-1002.json").write_text('{"annual_total_usd": 17100.0}\n')
    (tmp_path / "out" / "proposal-CUST-1002.md").write_text("# P\n")
    path = cache.store(tmp_path / "b", "write_pricing", {"customer_id": "CUST-1002"}, output="done", source="claude",
                       recorded_patch=PATCH, recorded_params={"customer_id": "CUST-1001"})
    assert path and path.parent.name == "write_pricing"
    entry = cache.lookup(tmp_path / "b", "write_pricing", {"customer_id": "CUST-1002"})
    assert entry["source"] == "claude" and set(entry["files"]) == {"out/pricing-CUST-1002.json", "out/proposal-CUST-1002.md"}
    assert cache.lookup(tmp_path / "b", "write_pricing", {"customer_id": "CUST-1003"}) is None
    assert cache.store(tmp_path / "b", "x", {}, output="", source="s") is None      # nothing to keep


def test_second_run_replays_the_first_escalation_at_zero_tokens(tmp_path, monkeypatch):
    from core.build.run import run_build

    root, _ = _write_build(tmp_path, monkeypatch)

    def agent(prompt, ctx):
        # the agent writes the files itself (like a real CLI escalation), then summarizes
        for path, content in slm.parse_file_blocks(GOOD_1002).items():
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(content + "\n")
        return {"output": "wrote CUST-1002 files", "tokens": 9000, "latency_ms": 1200.0, "exit_code": 0, "model": "agent-x"}

    first = run_build(root, params={"customer_id": "CUST-1002"}, escalate="codex", escalator=agent, out_dir=tmp_path / "r1")
    assert first.steps[1].mode == "escalated:codex" and first.totals()["tokens"] == 9000
    entry = cache.lookup(root, "write_pricing", {"customer_id": "CUST-1002"})
    assert entry and "out/pricing-CUST-1002.json" in entry["files"]

    # wipe the outputs; the second run must restore them from the cache without any backend
    (tmp_path / "out" / "pricing-CUST-1002.json").unlink()
    second = run_build(root, params={"customer_id": "CUST-1002"}, out_dir=tmp_path / "r2")
    assert second.steps[1].mode == "cache" and second.steps[1].tokens == 0 and second.steps[1].ok
    assert second.totals()["tokens"] == 0 and second.totals()["cache_steps"] == 1 and second.totals()["needs_agent_steps"] == 0
    assert json.loads((tmp_path / "out" / "pricing-CUST-1002.json").read_text())["annual_total_usd"] == 17100.0
    assert "cache" in second.to_markdown() and "escalation of" in second.steps[1].note

    # different parameters do not hit the cache
    third = run_build(root, params={"customer_id": "CUST-1003"}, out_dir=tmp_path / "r3")
    assert third.steps[1].mode == "needs_agent"


def test_successful_slm_respond_is_cached_for_repeat_runs(tmp_path, monkeypatch):
    from core.build.run import run_build
    from tests.test_slm import RECORDED, _build

    root, _ = _build(tmp_path, monkeypatch)
    slm.promote(root, "respond", slm.SLMRuntime(model="fake-7b"), transport=_fake_transport(RECORDED))
    # a reply grounded in the fixture's upstream output (the gate must PASS for the result to be cached)
    grounded = "Renewal ready for CUST-1001: 240 seats, $116,640.00 total."
    monkeypatch.setattr(slm, "_http_post_json", _fake_transport(grounded, usage=(900, 60)))
    first = run_build(root, request="Prepare the renewal proposal for CUST-1001", out_dir=tmp_path / "r1")
    assert first.steps[1].mode == "slm:fake-7b" and first.steps[1].tokens == 960 and first.steps[1].ok

    def boom(url, payload, timeout):      # the endpoint must not be consulted on the second run
        raise AssertionError("SLM called despite cache")

    monkeypatch.setattr(slm, "_http_post_json", boom)
    second = run_build(root, request="Prepare the renewal proposal for CUST-1001", out_dir=tmp_path / "r2")
    assert second.steps[1].mode == "cache" and second.totals()["tokens"] == 0


def test_stale_cache_is_skipped_when_upstream_data_changes(tmp_path, monkeypatch):
    from core.build.run import run_build

    root, _ = _write_build(tmp_path, monkeypatch)

    def agent(prompt, ctx):
        for path, content in slm.parse_file_blocks(GOOD_1002).items():
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(content + "\n")
        return {"output": "wrote files", "tokens": 9000, "latency_ms": 1200.0, "exit_code": 0, "model": "agent-x"}

    run_build(root, params={"customer_id": "CUST-1002"}, escalate="codex", escalator=agent, out_dir=tmp_path / "r1")
    entry = cache.lookup_any(root, "write_pricing", {"customer_id": "CUST-1002"})[0]
    assert entry and entry["upstream_sha"]

    # the source data changes → the replayed code output changes → the entry is stale, not replayed
    (tmp_path / "ctx.txt").write_text((tmp_path / "ctx.txt").read_text().replace("seats 60", "seats 90"))
    stale = run_build(root, params={"customer_id": "CUST-1002"}, out_dir=tmp_path / "r2")
    assert stale.steps[1].mode == "needs_agent" and "cache stale" in stale.steps[1].note

    # a fresh escalation refreshes the entry; the next run hits again
    run_build(root, params={"customer_id": "CUST-1002"}, escalate="codex", escalator=agent, out_dir=tmp_path / "r3")
    again = run_build(root, params={"customer_id": "CUST-1002"}, out_dir=tmp_path / "r4")
    assert again.steps[1].mode == "cache" and again.totals()["tokens"] == 0

    # --no-cache ignores a valid entry
    nocache = run_build(root, params={"customer_id": "CUST-1002"}, out_dir=tmp_path / "r5", use_cache=False)
    assert nocache.steps[1].mode == "needs_agent"


def test_cache_cli_list_and_clear(tmp_path, monkeypatch, capsys):
    from core.build.__main__ import main
    from core.build.run import run_build

    root, _ = _write_build(tmp_path, monkeypatch)

    def agent(prompt, ctx):
        for path, content in slm.parse_file_blocks(GOOD_1002).items():
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(content + "\n")
        return {"output": "ok", "tokens": 100, "latency_ms": 10.0, "exit_code": 0, "model": "agent-x"}

    run_build(root, params={"customer_id": "CUST-1002"}, escalate="codex", escalator=agent, out_dir=tmp_path / "r1")
    assert main(["cache", "list", str(root)]) == 0
    out = capsys.readouterr().out
    assert "write_pricing" in out and "customer_id=CUST-1002" in out and "agent-x" not in out  # source column is the backend name
    assert main(["cache", "clear", str(root), "--action", "write_pricing"]) == 0
    assert "removed" in capsys.readouterr().out
    assert cache.entries(root) == [] or all(e["action"] != "write_pricing" for e in cache.entries(root))
    assert main(["cache", "list", str(root)]) == 0
