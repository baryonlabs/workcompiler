"""Org registry: publish/pull/status over a git repo; caches from different people merge by key."""

import json
import subprocess
from pathlib import Path

import pytest

from core import org
from core.build import cache
from tests.test_slm import GOOD_1002, _write_build
from core.build import slm


@pytest.fixture()
def registry(tmp_path, monkeypatch):
    bare = tmp_path / "registry.git"
    subprocess.run(["git", "init", "--bare", "--quiet", str(bare)], check=True)
    clone = tmp_path / "org-clone"
    monkeypatch.setenv(org.ENV_REPO, str(bare))
    monkeypatch.setattr(org, "CONFIG_PATH", tmp_path / "owc-org.json")
    org.init(str(bare), clone=str(clone))
    # the bare repo needs an initial commit for pulls to rebase cleanly
    (clone / ".keep").write_text("")
    subprocess.run(["git", "-C", str(clone), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(clone), "commit", "--quiet", "-m", "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(clone), "push", "--quiet"], check=True, capture_output=True)
    return bare, clone


def test_publish_pull_status_roundtrip(tmp_path, monkeypatch, registry, capsys):
    bare, clone = registry
    (tmp_path / "alice").mkdir()
    root, _ = _write_build(tmp_path / "alice", monkeypatch)
    # alice escalated CUST-1002 once: her cache entry ships with the build
    cache.store(root, "write_pricing", {"customer_id": "CUST-1002"}, output="done", source="claude",
                files=slm.parse_file_blocks(GOOD_1002), upstream=[("shell_cat", "ctx")], upstream_sha="sha-a")

    entry = org.publish(root, work="renewal")
    assert entry["artifacts"] > 5 and entry["cache"]["added"] == 1 and entry["pushed"]
    assert (clone / "works" / "renewal" / "work.yaml").exists()
    assert (clone / "works" / "renewal" / "trace.json").exists()
    ledger = (clone / "ledger" / "renewal.jsonl").read_text().splitlines()
    assert len(ledger) == 1 and json.loads(ledger[0])["work"] == "renewal"

    # bob pulls into his own machine: artifacts + alice's cache arrive
    bob_dir = tmp_path / "bob-build"
    res = org.pull("renewal", build_dir=bob_dir)
    assert res["artifacts"] > 5 and res["cache"]["added"] == 1
    got = cache.lookup(bob_dir / "renewal", "write_pricing", {"customer_id": "CUST-1002"})
    assert got and got["source"] == "claude" and "out/pricing-CUST-1002.json" in got["files"]

    st = org.status()
    assert st["org_totals"]["works"] == 1 and st["org_totals"]["cache_entries"] == 1
    assert org.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "renewal" in out and "org total: 1 works" in out


def test_cache_merge_prefers_fresher_upstream(tmp_path, monkeypatch, registry):
    bare, clone = registry
    (tmp_path / "alice").mkdir()
    root, _ = _write_build(tmp_path / "alice", monkeypatch)
    cache.store(root, "write_pricing", {"customer_id": "CUST-1002"}, output="v1", source="claude",
                files={"out/a.json": "1"}, upstream_sha="sha-old")
    org.publish(root, work="renewal")

    # bob publishes a fresher result for the same parameters (different upstream, later timestamp)
    (tmp_path / "bob").mkdir()
    bob, _ = _write_build(tmp_path / "bob", monkeypatch)
    path = cache.store(bob, "write_pricing", {"customer_id": "CUST-1002"}, output="v2", source="codex",
                       files={"out/a.json": "2"}, upstream_sha="sha-new")
    data = json.loads(path.read_text()); data["at"] = "2099-01-01T00:00:00"
    path.write_text(json.dumps(data))
    entry = org.publish(bob, work="renewal")
    assert entry["cache"]["replaced"] == 1
    merged = json.loads(next((clone / "works" / "renewal" / "cache" / "write_pricing").glob("*.json")).read_text())
    assert merged["output"] == "v2" and merged["upstream_sha"] == "sha-new"

    # an older publish never clobbers the fresher entry
    entry = org.publish(root, work="renewal")
    assert entry["cache"]["kept"] == 1
    merged = json.loads(next((clone / "works" / "renewal" / "cache" / "write_pricing").glob("*.json")).read_text())
    assert merged["output"] == "v2"


def test_registry_not_configured_is_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.delenv(org.ENV_REPO, raising=False)
    monkeypatch.setattr(org, "CONFIG_PATH", tmp_path / "nope.json")
    with pytest.raises(RuntimeError, match="owc org init"):
        org.registry_path()
