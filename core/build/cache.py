"""Escalate once, replay forever.

A synthesized derivation (the agent computes values and writes files) cannot always be lowered to
code or a gated SLM — but its *result for a given parameter set* is a proven execution the moment it
succeeds. This cache stores that result keyed by the bound parameters; every later run with the same
parameters replays it locally: 0 tokens, 0 cost, deterministic. The cache lives inside the build
(``cache/<action>/<params-key>.json``) so it ships with it and appears in MANIFEST-adjacent tooling.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

DIRNAME = "cache"


def fingerprint(upstream) -> str:
    """Freshness key of a run: sha1 over the ordered (action, output) pairs of the code-tier steps
    executed so far. When the source data changes, the replayed outputs change, and so does this —
    a cached result from other data must not be replayed."""
    h = hashlib.sha1()
    for action, output in upstream or []:
        h.update(str(action).encode()); h.update(b"\x00")
        h.update(str(output).encode()); h.update(b"\x01")
    return h.hexdigest()


def entries(build_dir: Path | str) -> list:
    """Every cache entry in the build, for `owc build cache list`."""
    root = Path(build_dir) / DIRNAME
    out = []
    for path in sorted(root.glob("*/*.json")):
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        entry["_path"] = str(path)
        out.append(entry)
    return out


def clear(build_dir: Path | str, action: Optional[str] = None) -> int:
    root = Path(build_dir) / DIRNAME
    removed = 0
    for path in list(root.glob(f"{action or '*'}/*.json")):
        path.unlink(); removed += 1
    return removed


def _key(params: Dict[str, Any]) -> str:
    canon = json.dumps({k: str(v) for k, v in sorted((params or {}).items())}, ensure_ascii=False)
    slug = "-".join(re.sub(r"[^\w.-]+", "_", str(v))[:24] for _, v in sorted((params or {}).items())) or "noparams"
    return f"{slug}-{hashlib.sha1(canon.encode()).hexdigest()[:10]}"


def _path(build_dir: Path | str, action: str, params: Dict[str, Any]) -> Path:
    return Path(build_dir) / DIRNAME / action / f"{_key(params)}.json"


def lookup_any(build_dir: Path | str, action: str, params: Dict[str, Any],
               upstream_sha: Optional[str] = None) -> tuple[Optional[Dict[str, Any]], str]:
    """(entry, "hit" | "stale" | "miss"). ``stale`` = the parameters match but the upstream outputs
    this run produced differ from the ones the cached result was computed from."""
    path = _path(build_dir, action, params)
    if not path.exists():
        return None, "miss"
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None, "miss"
    if entry.get("params") != {k: str(v) for k, v in (params or {}).items()}:
        return None, "miss"
    if upstream_sha is not None and entry.get("upstream_sha") and entry["upstream_sha"] != upstream_sha:
        return entry, "stale"
    return entry, "hit"


def lookup(build_dir: Path | str, action: str, params: Dict[str, Any],
           upstream_sha: Optional[str] = None) -> Optional[Dict[str, Any]]:
    entry, status = lookup_any(build_dir, action, params, upstream_sha)
    return entry if status == "hit" else None


def store(build_dir: Path | str, action: str, params: Dict[str, Any], *, output: str, source: str,
          files: Optional[Dict[str, str]] = None, recorded_patch: Optional[str] = None,
          recorded_params: Optional[Dict[str, Any]] = None, upstream_sha: str = "") -> Optional[Path]:
    """Persist a successful escalation/SLM result. When the recorded step wrote files (``recorded_patch``)
    and the escalating agent wrote them to disk itself, the current on-disk content of the
    parameter-substituted paths is captured."""
    captured: Dict[str, str] = dict(files or {})
    if not captured and recorded_patch:
        from core.work_ir import patchfmt

        for block in patchfmt.parse_patch(recorded_patch):
            if block.op != "Add":
                continue
            rel = block.path
            for name, value in (params or {}).items():
                rec = str((recorded_params or {}).get(name, ""))
                if rec:
                    rel = rel.replace(rec, str(value))
            target = Path(rel)
            if target.is_file():
                try:
                    captured[rel] = target.read_text(encoding="utf-8")
                except Exception:
                    continue
    if not captured and not output.strip():
        return None
    path = _path(build_dir, action, params)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"action": action, "params": {k: str(v) for k, v in (params or {}).items()},
                                "source": source, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                "upstream_sha": upstream_sha, "output": output, "files": captured},
                               indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path
