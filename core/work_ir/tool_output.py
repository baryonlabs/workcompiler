"""Normalize tool-call outputs recorded from agent APIs into plain text.

Agents wrap the raw stdout of a tool call in transport envelopes. Codex "code mode",
for example, returns a list of text parts whose last part is a JSON chunk::

    [{"type": "input_text", "text": "Script completed\\nWall time 0.2 seconds\\nOutput:\\n"},
     {"type": "input_text", "text": "{\\"chunk_id\\": \\"e1f6\\", \\"exit_code\\": 0, \\"output\\": \\"<stdout>\\"}"}]

``normalize_tool_output`` unwraps such envelopes so a recorded result can be compared
with what a compiled handler produces.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

_RESULT_MARKER_RE = re.compile(r"---RESULT \d+---\n?")
_DECODER = json.JSONDecoder()


def _join_parts(output: Any) -> str:
    if isinstance(output, list):
        texts = []
        for part in output:
            if isinstance(part, dict):
                texts.append(str(part.get("text") or part.get("output") or ""))
            else:
                texts.append(str(part))
        return "".join(texts)
    if isinstance(output, dict):
        if "output" in output:
            return _join_parts(output["output"])
        return json.dumps(output, ensure_ascii=False)
    return "" if output is None else str(output)


def _json_chunks(text: str) -> list:
    """Decode every top-level JSON object embedded in ``text`` (chunks may be concatenated)."""
    chunks = []
    pos = 0
    while True:
        start = text.find("{", pos)
        if start < 0:
            break
        try:
            obj, end = _DECODER.raw_decode(text, start)
        except ValueError:
            pos = start + 1
            continue
        chunks.append(obj)
        pos = end
    return chunks


def normalize_tool_output(output: Any) -> str:
    """Best-effort plain-text view of a recorded tool result.

    Codex code-mode wraps stdout in JSON chunks (``{"chunk_id": ..., "output": "..."}``);
    a batched call yields several chunks, optionally separated by ``---RESULT N---``
    markers. Their ``output`` fields are concatenated in order, mirroring the stdout
    of running the commands back to back.
    """
    text = _RESULT_MARKER_RE.sub("", _join_parts(output))
    outputs = [c["output"] for c in _json_chunks(text) if isinstance(c, dict) and isinstance(c.get("output"), str)]
    if outputs:
        return "".join(outputs)
    marker = "Output:\n"
    if marker in text:
        return text.split(marker, 1)[1]
    return text
