"""Tool semantics shared by every agent protocol.

Coding agents expose different tool names for the same work — Codex ``exec_command`` /
``apply_patch``, Claude Code ``Bash`` / ``Read`` / ``Write`` / ``Edit`` / ``MultiEdit`` /
``Glob`` / ``Grep``, Cursor ``run_terminal_cmd``, opencode ``bash`` … This module maps a tool
call onto the *one* vocabulary the compiler, build emitter and benchmark understand:

* ``cmd`` / ``cmds`` — a replayable shell command (also synthesized for Read/Glob/Grep)
* ``patch`` + ``files`` — a V4A-style file mutation (``core.work_ir.patchfmt``)
* an action name: ``shell_<program>``, ``write_<stem>``, ``read_<stem>``, ``glob_files``,
  ``grep_<pattern>``, ``fetch_<host>``, ``plan`` (bookkeeping tools) or the tool name.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlparse

from core.work_ir import patchfmt


class ToolKind(str, Enum):
    SHELL = "shell"
    WRITE = "write"
    EDIT = "edit"
    MULTI_EDIT = "multi_edit"
    READ = "read"
    GLOB = "glob"
    GREP = "grep"
    FETCH = "fetch"
    IGNORED = "ignored"
    OTHER = "other"


SHELL_TOOLS = {"bash", "shell", "shell_command", "exec_command", "local_shell", "container.exec", "exec",
               "run_terminal_cmd", "execute_command", "run_command", "terminal", "run_shell_command"}
WRITE_TOOLS = {"write", "write_file", "create_file", "write_to_file"}
EDIT_TOOLS = {"edit", "edit_file", "str_replace_editor", "str_replace_based_edit_tool", "replace_in_file",
              "apply_diff", "replace"}
MULTI_EDIT_TOOLS = {"multiedit", "multi_edit"}
READ_TOOLS = {"read", "read_file", "view_file", "cat"}
GLOB_TOOLS = {"glob", "list_dir", "ls", "list_directory"}
GREP_TOOLS = {"grep", "grep_search", "codebase_search", "search_file_content"}
FETCH_TOOLS = {"webfetch", "web_fetch", "fetch"}
IGNORED_TOOLS = {"todowrite", "todoread", "askuserquestion", "exitplanmode", "enterplanmode", "task",
                 "notebookedit", "websearch", "web_search"}


def classify_tool(name: str) -> ToolKind:
    n = (name or "").strip().lower()
    if n in SHELL_TOOLS:
        return ToolKind.SHELL
    if n in WRITE_TOOLS:
        return ToolKind.WRITE
    if n in MULTI_EDIT_TOOLS:
        return ToolKind.MULTI_EDIT
    if n in EDIT_TOOLS:
        return ToolKind.EDIT
    if n in READ_TOOLS:
        return ToolKind.READ
    if n in GLOB_TOOLS:
        return ToolKind.GLOB
    if n in GREP_TOOLS:
        return ToolKind.GREP
    if n in FETCH_TOOLS:
        return ToolKind.FETCH
    if n in IGNORED_TOOLS:
        return ToolKind.IGNORED
    return ToolKind.OTHER


@dataclass
class NormalizedCall:
    kind: ToolKind
    action: str
    input: Dict[str, Any] = field(default_factory=dict)
    files: List[str] = field(default_factory=list)
    patch: Optional[str] = None


_SLUG_RE = re.compile(r"[^\w]+")


def _slug(text: str, limit: int = 40) -> str:
    return _SLUG_RE.sub("_", str(text)).strip("_").lower()[:limit] or "x"


def _stem(path: str) -> str:
    base = str(path).replace("\\", "/").rsplit("/", 1)[-1]
    return _slug(base.rsplit(".", 1)[0] if "." in base else base)


def _shell_program(command: Any) -> Optional[str]:
    if isinstance(command, list) and command:
        tokens = [str(t) for t in command]
        if len(tokens) >= 3 and tokens[0] in {"bash", "sh", "zsh"} and tokens[1] in {"-lc", "-c"}:
            command = tokens[2]
        else:
            return tokens[0].rsplit("/", 1)[-1]
    if isinstance(command, str) and command.strip():
        try:
            tokens = shlex.split(command)
        except ValueError:
            tokens = command.split()
        for tok in tokens:
            if "=" in tok and not tok.startswith("="):
                continue
            return tok.rsplit("/", 1)[-1]
    return None


def _command_string(command: Any) -> Optional[str]:
    if isinstance(command, list) and command:
        tokens = [str(t) for t in command]
        if len(tokens) >= 3 and tokens[0] in {"bash", "sh", "zsh"} and tokens[1] in {"-lc", "-c"}:
            return tokens[2]
        return " ".join(shlex.quote(t) for t in tokens)
    return command if isinstance(command, str) and command.strip() else None


def normalize_call(name: str, arguments: Any) -> NormalizedCall:
    """Map one tool call (name + arguments) onto the compiler's vocabulary."""
    args: Dict[str, Any] = arguments if isinstance(arguments, dict) else {"raw_args": arguments}
    kind = classify_tool(name)
    inp: Dict[str, Any] = dict(args)

    # Pre-normalized arguments (Codex code mode, Responses ``apply_patch``): the arguments already
    # carry a V4A patch or a shell command; they decide the kind regardless of the tool's name.
    if isinstance(args.get("patch"), str) and args["patch"].strip():
        patch = args["patch"]
        files = list(args.get("files") or [b.path for b in patchfmt.parse_patch(patch)])
        inp["files"] = files
        stem = _stem(files[0]) if files else "files"
        return NormalizedCall(ToolKind.WRITE, f"write_{stem}", inp, files, patch)
    if kind not in (ToolKind.SHELL,) and (args.get("cmds") or args.get("cmd")) and kind in (ToolKind.OTHER, ToolKind.IGNORED):
        kind = ToolKind.SHELL

    if kind == ToolKind.SHELL:
        cmds = args.get("cmds")
        if isinstance(cmds, list) and cmds:
            cmd = str(cmds[0])
            inp["cmd"] = cmd
            inp["cmds"] = [str(c) for c in cmds]
        else:
            cmd = _command_string(args.get("cmd") or args.get("command"))
            if cmd is not None:
                inp["cmd"] = cmd
        program = _shell_program(cmd) if cmd else None
        return NormalizedCall(kind, f"shell_{program}" if program else _slug(name), inp)

    if kind in (ToolKind.WRITE, ToolKind.EDIT, ToolKind.MULTI_EDIT):
        path = str(args.get("file_path") or args.get("path") or args.get("filename") or "")
        if not path:
            return NormalizedCall(ToolKind.OTHER, _slug(name), inp)
        if kind == ToolKind.WRITE:
            block = patchfmt.render_add(path, str(args.get("content", "")))
        elif kind == ToolKind.EDIT:
            block = patchfmt.render_update(path, [(str(args.get("old_string", "")), str(args.get("new_string", "")),
                                                   bool(args.get("replace_all", False)))])
        else:
            edits = [(str(e.get("old_string", "")), str(e.get("new_string", "")), bool(e.get("replace_all", False)))
                     for e in (args.get("edits") or []) if isinstance(e, dict)]
            block = patchfmt.render_update(path, edits)
        patch = patchfmt.wrap([block])
        inp["patch"] = patch
        inp["files"] = [path]
        return NormalizedCall(kind, f"write_{_stem(path)}", inp, [path], patch)

    if kind == ToolKind.READ:
        path = str(args.get("file_path") or args.get("path") or "")
        if not path:
            return NormalizedCall(ToolKind.OTHER, _slug(name), inp)
        offset, limit = args.get("offset"), args.get("limit")
        if isinstance(offset, int) or isinstance(limit, int):
            start = int(offset or 0) + 1
            end = start + int(limit) - 1 if isinstance(limit, int) else "$"
            cmd = f"sed -n '{start},{end}p' {shlex.quote(path)}"
        else:
            cmd = f"cat {shlex.quote(path)}"
        inp["cmd"] = cmd
        return NormalizedCall(kind, f"read_{_stem(path)}", inp, [path])

    if kind == ToolKind.GLOB:
        pattern = str(args.get("pattern") or args.get("glob") or "*")
        root = str(args.get("path") or ".")
        # Claude Code's Glob returns repo-relative paths (no "./"), newest first; the replay sorts by name
        # and the benchmark compares glob output order-insensitively.
        inp["cmd"] = f"find {shlex.quote(root)} -path {shlex.quote('*' + pattern.lstrip('*'))} -type f | sed 's#^\\./##' | sort"
        return NormalizedCall(kind, "glob_files", inp)

    if kind == ToolKind.GREP:
        pattern = str(args.get("pattern") or args.get("query") or "")
        root = str(args.get("path") or ".")
        mode = str(args.get("output_mode") or "files_with_matches")
        flags = "-rnE" if mode == "content" else "-rlE"
        include = f" --include={shlex.quote(str(args['glob']))}" if args.get("glob") else ""
        inp["cmd"] = f"grep {flags}{include} {shlex.quote(pattern)} {shlex.quote(root)} | sort"
        return NormalizedCall(kind, f"grep_{_slug(pattern, 20)}", inp)

    if kind == ToolKind.FETCH:
        url = str(args.get("url") or "")
        host = urlparse(url).netloc.split(":")[0] if url else "url"
        return NormalizedCall(kind, f"fetch_{_slug(host)}", inp)

    if kind == ToolKind.IGNORED:
        inp["__ignored_tool__"] = name
        return NormalizedCall(kind, "plan", inp)

    return NormalizedCall(ToolKind.OTHER, _slug(name), inp)


def merge_calls(calls: Sequence[NormalizedCall]) -> NormalizedCall:
    """Combine the parallel tool calls of one turn into a single step description.

    * all shell-like (shell/read/glob/grep) → one step with ``cmds`` in call order
    * all write-like → one step whose ``patch`` concatenates the file blocks
    * otherwise the first call decides; the others are still recorded in ``tool_calls``.
    """
    if not calls:
        return NormalizedCall(ToolKind.OTHER, "respond")
    if len(calls) == 1:
        return calls[0]
    shellish = {ToolKind.SHELL, ToolKind.READ, ToolKind.GLOB, ToolKind.GREP}
    if all(c.kind in shellish and c.input.get("cmd") for c in calls):
        first = calls[0]
        cmds: List[str] = []
        for c in calls:
            cmds.extend(c.input.get("cmds") or [c.input["cmd"]])
        inp = dict(first.input); inp["cmd"] = cmds[0]; inp["cmds"] = cmds
        return NormalizedCall(first.kind, first.action, inp, [f for c in calls for f in c.files])
    writeish = {ToolKind.WRITE, ToolKind.EDIT, ToolKind.MULTI_EDIT}
    if all(c.kind in writeish and c.patch for c in calls):
        blocks = []
        for c in calls:
            blocks.extend(b for b in patchfmt_blocks(c.patch))
        patch = patchfmt.wrap(blocks)
        files = [f for c in calls for f in c.files]
        inp = dict(calls[0].input); inp["patch"] = patch; inp["files"] = files
        return NormalizedCall(calls[0].kind, calls[0].action, inp, files, patch)
    return calls[0]


def patchfmt_blocks(patch: str) -> List[str]:
    """Split a wrapped patch back into its per-file block texts."""
    out: List[str] = []
    current: List[str] = []
    for line in patch.splitlines():
        if line.startswith(patchfmt.BEGIN) or line.startswith(patchfmt.END):
            continue
        if line.startswith("*** ") and current:
            out.append("\n".join(current)); current = []
        current.append(line)
    if current:
        out.append("\n".join(current))
    return out
