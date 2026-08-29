"""V4A-style patch text: parse / render / apply / verify round-trips."""

from core.work_ir import patchfmt as pf


def test_add_round_trip_keeps_trailing_newline_semantics(tmp_path):
    with_nl = pf.render_add("a/one.txt", "x\ny\n")
    without = pf.render_add("a/two.txt", "x\ny")
    blocks = pf.parse_patch(pf.wrap([with_nl, without]))
    assert [b.op for b in blocks] == ["Add", "Add"]
    assert pf.add_content(blocks[0]) == "x\ny\n"
    assert blocks[1].no_trailing_newline and pf.add_content(blocks[1]) == "x\ny"
    for b in blocks:
        assert pf.apply_block(b, tmp_path)["status"] == "written"
    assert (tmp_path / "a/one.txt").read_text() == "x\ny\n"
    assert (tmp_path / "a/two.txt").read_text() == "x\ny"
    assert all(pf.verify_block(b, tmp_path)[0] for b in blocks)


def test_update_hunks_apply_verify_and_detect_already_applied(tmp_path):
    (tmp_path / "cfg.yaml").write_text("name: old\nseats: 10\nseats: 10\n")
    patch = pf.wrap([pf.render_update("cfg.yaml", [("name: old", "name: new", False), ("seats: 10", "seats: 20", True)])])
    blocks = pf.parse_patch(patch)
    assert len(blocks[0].hunks) == 2 and blocks[0].hunks[1].replace_all
    assert pf.apply_block(blocks[0], tmp_path)["status"] == "written"
    assert (tmp_path / "cfg.yaml").read_text() == "name: new\nseats: 20\nseats: 20\n"
    assert pf.verify_block(blocks[0], tmp_path)[0]
    # replaying in a workspace where the edit already happened is fine
    assert pf.apply_block(blocks[0], tmp_path)["status"] == "already_applied"


def test_delete_and_missing_update_target(tmp_path):
    (tmp_path / "tmp.txt").write_text("x")
    blocks = pf.parse_patch(pf.wrap([pf.render_delete("tmp.txt")]))
    assert pf.apply_block(blocks[0], tmp_path)["status"] == "deleted"
    assert pf.verify_block(blocks[0], tmp_path)[0]
    upd = pf.parse_patch(pf.render_update("nope.txt", [("a", "b", False)]))[0]
    try:
        pf.apply_block(upd, tmp_path)
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass


def test_codex_v4a_add_file_text_still_parses():
    text = "*** Begin Patch\n*** Add File: build/x.json\n+{\n+  \"a\": 1\n+}\n*** End Patch"
    blocks = pf.parse_patch(text)
    assert blocks[0].op == "Add" and pf.add_content(blocks[0]) == '{\n  "a": 1\n}\n'
    ok, n, _ = pf.verify_patch_text(text, "/nonexistent")
    assert not ok and n == 1
