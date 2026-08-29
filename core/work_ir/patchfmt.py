"""V4A-style patch text: the canonical representation of file mutations in a trace.

Every agent writes files differently — Codex sends ``apply_patch`` text, Claude Code calls
``Write`` / ``Edit`` / ``MultiEdit``, others send full-file writes. All of them are normalized
into this one text format so the compiler, the generated handlers and the benchmark share a
single parser::

    *** Begin Patch
    *** Add File: build/out/report.md
    +line one
    +line two
    *** Update File: config.yaml
    @@
    -old line
    +new line
    @@ replace_all
    -foo
    +bar
    *** Delete File: tmp.txt
    *** End Patch

Add blocks keep the exact content (``\\ No newline at end of file`` is honored). Update blocks
are *V4A-lite*: each ``@@`` hunk is an ``old`` block (``-`` lines) replaced by a ``new`` block
(``+`` lines); no context lines are required because only our own handlers consume it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

BEGIN = "*** Begin Patch"
END = "*** End Patch"
NO_NEWLINE = "\\ No newline at end of file"


@dataclass
class Hunk:
    old: List[str] = field(default_factory=list)
    new: List[str] = field(default_factory=list)
    replace_all: bool = False

    @property
    def old_text(self) -> str:
        return "\n".join(self.old)

    @property
    def new_text(self) -> str:
        return "\n".join(self.new)


@dataclass
class FileBlock:
    op: str                     # "Add" | "Update" | "Delete"
    path: str
    lines: List[str] = field(default_factory=list)      # Add: raw lines (without the leading '+')
    hunks: List[Hunk] = field(default_factory=list)     # Update
    no_trailing_newline: bool = False


# --------------------------------------------------------------------------- parse / render

def parse_patch(text: str) -> List[FileBlock]:
    """Parse patch text (with or without the Begin/End envelope) into file blocks."""
    blocks: List[FileBlock] = []
    current: FileBlock | None = None
    hunk: Hunk | None = None
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if line.startswith(BEGIN) or line.startswith(END):
            continue
        if line.startswith("*** "):
            op, _, path = line[4:].partition(" File: ")
            current = FileBlock(op=op.strip(), path=path.strip())
            hunk = None
            blocks.append(current)
            continue
        if current is None:
            continue
        if current.op == "Update":
            if line.startswith("@@"):
                hunk = Hunk(replace_all="replace_all" in line)
                current.hunks.append(hunk)
            elif hunk is not None:
                if line.startswith("-"):
                    hunk.old.append(line[1:])
                elif line.startswith("+"):
                    hunk.new.append(line[1:])
                elif line.startswith(" "):
                    hunk.old.append(line[1:]); hunk.new.append(line[1:])
            continue
        if current.op == "Add":
            if line == NO_NEWLINE:
                current.no_trailing_newline = True
            elif line.startswith("+"):
                current.lines.append(line[1:])
            else:
                current.lines.append(line)
    return blocks


def render_add(path: str, content: str) -> str:
    body = content
    no_newline = not body.endswith("\n") and body != ""
    lines = body[:-1].split("\n") if body.endswith("\n") else body.split("\n")
    out = [f"*** Add File: {path}"] + [f"+{l}" for l in lines]
    if no_newline:
        out.append(NO_NEWLINE)
    return "\n".join(out)


def render_update(path: str, edits: Sequence[Tuple[str, str, bool]]) -> str:
    """edits: (old_string, new_string, replace_all) in application order."""
    out = [f"*** Update File: {path}"]
    for old, new, replace_all in edits:
        out.append("@@ replace_all" if replace_all else "@@")
        out += [f"-{l}" for l in old.split("\n")]
        out += [f"+{l}" for l in new.split("\n")]
    return "\n".join(out)


def render_delete(path: str) -> str:
    return f"*** Delete File: {path}"


def wrap(blocks: Sequence[str]) -> str:
    return "\n".join([BEGIN, *blocks, END])


def add_content(block: FileBlock) -> str:
    text = "\n".join(block.lines)
    return text if block.no_trailing_newline else text + "\n"


# --------------------------------------------------------------------------- apply / verify

def apply_block(block: FileBlock, cwd: Path | str = ".") -> Dict[str, str]:
    """Apply one block relative to ``cwd``. Update hunks whose old text is already gone but whose
    new text is present are reported as ``already_applied`` (replays inside a workspace where the
    agent's session already made the edit)."""
    target = Path(cwd) / block.path
    if block.op == "Add":
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(add_content(block), encoding="utf-8")
        return {"path": block.path, "op": "Add", "status": "written"}
    if block.op == "Delete":
        existed = target.exists()
        if existed:
            target.unlink()
        return {"path": block.path, "op": "Delete", "status": "deleted" if existed else "already_applied"}
    if block.op == "Update":
        if not target.exists():
            raise FileNotFoundError(f"Update target does not exist: {block.path}")
        text = target.read_text(encoding="utf-8")
        status = "written"
        for h in block.hunks:
            if h.old_text in text and h.old_text != "":
                text = text.replace(h.old_text, h.new_text) if h.replace_all else text.replace(h.old_text, h.new_text, 1)
            elif h.new_text and h.new_text in text:
                status = "already_applied"
            else:
                raise ValueError(f"Update hunk not found in {block.path}: {h.old_text[:60]!r}")
        target.write_text(text, encoding="utf-8")
        return {"path": block.path, "op": "Update", "status": status}
    raise NotImplementedError(f"unsupported patch op '{block.op}' for {block.path}")


def verify_block(block: FileBlock, cwd: Path | str = ".") -> Tuple[bool, str]:
    target = Path(cwd) / block.path
    if block.op == "Add":
        if not target.exists():
            return False, f"{block.path}: missing"
        ok = target.read_text(encoding="utf-8") == add_content(block)
        return ok, f"{block.path}: {'identical' if ok else 'content differs'}"
    if block.op == "Delete":
        return (not target.exists()), f"{block.path}: {'deleted' if not target.exists() else 'still present'}"
    if block.op == "Update":
        if not target.exists():
            return False, f"{block.path}: missing"
        text = target.read_text(encoding="utf-8")
        for h in block.hunks:
            if h.new_text and h.new_text not in text:
                return False, f"{block.path}: expected text not found"
            if h.old_text and h.old_text in text and h.old_text not in h.new_text:
                return False, f"{block.path}: old text still present"
        return True, f"{block.path}: hunks applied"
    return False, f"{block.path}: unknown op {block.op}"


def apply_patch_text(patch: str, cwd: Path | str = ".") -> List[Dict[str, str]]:
    return [apply_block(b, cwd) for b in parse_patch(patch)]


def verify_patch_text(patch: str, cwd: Path | str = ".") -> Tuple[bool, int, str]:
    """(all ok, blocks checked, note)."""
    blocks = parse_patch(patch)
    notes = []
    ok = True
    for b in blocks:
        good, note = verify_block(b, cwd)
        ok = ok and good
        notes.append(note)
    return ok and bool(blocks), len(blocks), "; ".join(notes)
