"""Compile-time harness loop: deterministic reviewer, revert-on-regression, budget/gate governance."""

import json
from pathlib import Path

from core.build.harden import _INHERENT_RE, harden
from tests.test_slm import _build  # build whose shell_cat handler replays `cat examples/contract.json`


def test_inherent_re_does_not_misclassify_month_lookalikes():
    # regression: month abbreviations must not fire inside ordinary words
    for text in ["Decision: approve", "profit Margin 12%", "September report", "Marker set",
                 "Junction table", "AugmentedReality", "Decades of data", "MARGIN", "Decoder"]:
        assert not _INHERENT_RE.search(text), text
    # genuinely run-dependent outputs still detected
    for text in ["-rw-r--r--  1 u  staff  42 Aug 31 15:29 f.txt", "Sep 3 backup", "total 648",
                 "last run at 12:30", "Dec 25", "Jan  1 00:00"]:
        assert _INHERENT_RE.search(text), text


def _break_handler(root: Path) -> Path:
    """Simulate handler drift: the file forces a wrong command (FORCE_COMMANDS wins over replay inputs)."""
    handler = root / "handlers" / "shell_cat.py"
    text = handler.read_text().replace("'cat examples/contract.json'", "'cat examples/wrong.json'") \
                              .replace("FORCE_COMMANDS = False", "FORCE_COMMANDS = True")
    assert "wrong.json" in text and "FORCE_COMMANDS = True" in text
    handler.write_text(text)
    return handler


def _fixing_escalator(root: Path, tokens: int = 700):
    calls = []

    def fix(prompt, ctx):
        calls.append(prompt)
        handler = root / "handlers" / "shell_cat.py"
        handler.write_text(handler.read_text().replace("cat examples/wrong.json", "cat examples/contract.json"))
        return {"output": "fixed the replayed command path", "tokens": tokens, "latency_ms": 50.0, "exit_code": 0}

    fix.calls = calls
    return fix


def test_harden_fixes_a_broken_handler_and_reports_the_loop(tmp_path, monkeypatch):
    root, _ = _build(tmp_path, monkeypatch)
    (tmp_path / "examples" / "wrong.json").write_text("{}")
    _break_handler(root)
    fix = _fixing_escalator(root)
    report = harden(root, escalator=fix, backend_name="fake", max_iters=3)
    assert report.converged and report.final_matched == report.final_checked == 1
    assert report.iterations[0].accepted == ["shell_cat"] and len(fix.calls) == 1
    assert "Recorded output" in fix.calls[0] and "handlers/shell_cat.py" in fix.calls[0]
    md = (root / "HARDEN.md").read_text()
    assert "reviewer: deterministic benchmark" in md and "0/1 → 1/1" in md
    history = json.loads((root / "harden.json").read_text())
    assert history["attempts"][0]["outcome"] == "accepted" and history["converged"] is True


def test_harden_reverts_a_useless_fix_and_gates_it_for_humans(tmp_path, monkeypatch):
    root, _ = _build(tmp_path, monkeypatch)
    (tmp_path / "examples" / "wrong.json").write_text("{}")
    broken = _break_handler(root)
    before = broken.read_text()

    def useless(prompt, ctx):
        broken.write_text(before.replace("cat examples/wrong.json", "cat examples/still_wrong.json"))
        return {"output": "tried something", "tokens": 500, "latency_ms": 10.0, "exit_code": 0}

    report = harden(root, escalator=useless, backend_name="fake", max_iters=3)
    assert not report.converged and report.final_matched == 0
    assert report.iterations[0].reverted == ["shell_cat"]
    assert broken.read_text() == before                          # reverted to the snapshot
    assert report.stopped_because == "no progress in this iteration"

    # durable governance: a re-run recognizes the failure signature and refuses to re-spend budget on it
    report2 = harden(root, escalator=useless, backend_name="fake", max_iters=3)
    assert report2.needs_human == ["shell_cat"] and report2.tokens_total == 0
    assert report2.stopped_because == "no actionable failures left"


def test_harden_budget_and_no_backend(tmp_path, monkeypatch):
    root, _ = _build(tmp_path, monkeypatch)
    (tmp_path / "examples" / "wrong.json").write_text("{}")
    _break_handler(root)
    report = harden(root, escalator=None, backend_name="none")
    assert report.stopped_because == "no fix backend (--escalate)" and report.tokens_total == 0
    report = harden(root, escalator=_fixing_escalator(root, tokens=5000), backend_name="fake", budget_tokens=1)
    # first fix runs (budget checked before each attempt), then the loop stops on budget
    assert report.tokens_total == 5000 and report.final_matched == 1


def test_harden_cli(tmp_path, monkeypatch, capsys):
    from core.build.__main__ import main

    root, _ = _build(tmp_path, monkeypatch)
    assert main(["harden", str(root)]) == 0
    out = capsys.readouterr().out
    assert "[harden]" in out and "1/1 reproduced" in out
