"""Organizational registry: individuals' compiled work merges into one shared asset.

Every person keeps their own agent (Codex, Claude Code, Cursor …) and their own machine; what they
*produce* — compiled builds, escalate-once cache entries, benchmark ledgers — flows into a single
shared git repository, and flows back out to teammates:

* ``owc org init <git-url|path>`` — point this machine at the registry (cloned under ``~/.owc/org``).
* ``owc org publish build/<work>`` — copy the build's durable artifacts into ``works/<name>/``,
  **merge** cache entries by parameter key (a fresher ``upstream_sha`` wins, an existing fresh entry
  is never clobbered), append the benchmark totals + provenance to ``ledger/<name>.jsonl``, commit
  and push.
* ``owc org pull <work>`` — copy a colleague's build into the local ``build/`` (cache entries merge,
  never overwrite fresh local ones). Code tiers replay at zero tokens; a parameter set any teammate
  escalated once replays from their cached result.
* ``owc org status`` — the works on the registry and the organization-wide savings ledger.

Governance stays as the product principles demand: only human-approved runs should be published,
and a publish is an explicit act (or a scheduled job), never a silent side effect.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

CONFIG_PATH = Path.home() / ".owc" / "org.json"
ENV_REPO = "OWC_ORG_REPO"

# what a build contributes to the organization (durable, reviewable artifacts only)
PUBLISH_GLOBS = ["work.yaml", "*.work", "MANIFEST.json", "PARAMS.json", "trace.json",
                 "BENCHMARK.md", "benchmark.json", "HARDEN.md", "harden.json", "ledger.jsonl",
                 "handlers/*.py", "prompts/*.prompt.md", "rules/*.rule.yaml",
                 "models/slm/*/runtime.json", "models/slm/*/promotion.json", "models/slm/*/PROMOTION.md",
                 "models/slm/*/TRAINING.md", "models/slm/*/fleet_evals.json", "schema/*"]
EXCLUDE_NAMES = {"__pycache__", "runs", "checkpoints", "adapter", "adapter-7b", "data"}


def _run_git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout


ENV_TEAM = "OWC_TEAM"              # optional: the team a publish belongs to
ENV_SEAT = "OWC_SEAT"              # optional: seat/licence id, for per-seat rollups


def _identity() -> str:
    try:
        return subprocess.run(["git", "config", "user.name"], capture_output=True, text=True).stdout.strip() or os.environ.get("USER", "unknown")
    except Exception:
        return os.environ.get("USER", "unknown")


def registry_path(create: bool = False) -> Path:
    """The local clone of the org registry; clones on first use when a remote is configured."""
    source = os.environ.get(ENV_REPO)
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else {}
    source = source or config.get("repo")
    if not source:
        raise RuntimeError("no org registry configured — run `owc org init <git-url|path>` (or set OWC_ORG_REPO)")
    clone = Path(config.get("clone") or (Path.home() / ".owc" / "org"))
    if not (clone / ".git").exists():
        if not create:
            raise RuntimeError(f"registry not cloned yet at {clone} — run `owc org init {source}`")
        clone.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", source, str(clone)], check=True, capture_output=True, text=True)
    return clone


def init(source: str, clone: Optional[str] = None) -> Path:
    clone_path = Path(clone) if clone else Path.home() / ".owc" / "org"
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({"repo": source, "clone": str(clone_path)}, indent=2) + "\n", encoding="utf-8")
    if not (clone_path / ".git").exists():
        clone_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", source, str(clone_path)], check=True, capture_output=True, text=True)
    return clone_path


def _sync(repo: Path) -> None:
    try:
        _run_git(repo, "pull", "--rebase", "--quiet")
    except RuntimeError:
        pass          # offline or no upstream — local registry still works


def _push(repo: Path) -> bool:
    try:
        _run_git(repo, "push", "--quiet")
        return True
    except RuntimeError:
        return False  # offline: the commit stays local, next publish/pull pushes it


def merge_cache(src_dir: Path, dst_dir: Path) -> Dict[str, int]:
    """Merge escalate-once cache entries by parameter key. An entry replaces an existing one only
    when the existing one is stale-able (different upstream_sha) and older."""
    stats = {"added": 0, "kept": 0, "replaced": 0}
    for src in sorted(src_dir.glob("*/*.json")):
        rel = src.relative_to(src_dir)
        dst = dst_dir / rel
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            stats["added"] += 1
            continue
        try:
            new, old = json.loads(src.read_text(encoding="utf-8")), json.loads(dst.read_text(encoding="utf-8"))
        except Exception:
            stats["kept"] += 1
            continue
        if new.get("upstream_sha") != old.get("upstream_sha") and str(new.get("at", "")) > str(old.get("at", "")):
            shutil.copy2(src, dst)
            stats["replaced"] += 1
        else:
            stats["kept"] += 1
    return stats


def _copy_artifacts(src: Path, dst: Path) -> int:
    copied = 0
    for pattern in PUBLISH_GLOBS:
        for path in sorted(src.glob(pattern)):
            if any(part in EXCLUDE_NAMES for part in path.relative_to(src).parts):
                continue
            target = dst / path.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            copied += 1
    return copied


def publish(build_dir: Path | str, work: Optional[str] = None, cache_contrib: bool = True) -> Dict[str, Any]:
    src = Path(build_dir)
    name = work or src.name
    repo = registry_path(create=True)
    _sync(repo)
    dst = repo / "works" / name
    dst.mkdir(parents=True, exist_ok=True)
    copied = _copy_artifacts(src, dst)
    cache_stats = merge_cache(src / "cache", dst / "cache") if cache_contrib and (src / "cache").exists() else {}

    totals: Dict[str, Any] = {}
    bench_path = src / "benchmark.json"
    if bench_path.exists():
        try:
            totals = json.loads(bench_path.read_text(encoding="utf-8")).get("totals", {})
        except Exception:
            totals = {}
    entry = {"work": name, "by": _identity(), "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
             **{k: v for k, v in (("team", os.environ.get(ENV_TEAM)), ("seat", os.environ.get(ENV_SEAT))) if v},
             "artifacts": copied, "cache": cache_stats, "totals": totals}
    ledger = repo / "ledger" / f"{name}.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    _run_git(repo, "add", "-A")
    if _run_git(repo, "status", "--porcelain").strip():
        _run_git(repo, "commit", "--quiet", "-m", f"publish {name} by {entry['by']} ({copied} artifacts)")
    entry["pushed"] = _push(repo)
    return entry


def pull(work: str, build_dir: Path | str = "build") -> Dict[str, Any]:
    repo = registry_path(create=True)
    _sync(repo)
    src = repo / "works" / work
    if not src.exists():
        raise RuntimeError(f"work '{work}' not found in the registry ({sorted(p.name for p in (repo / 'works').glob('*')) if (repo / 'works').exists() else 'empty'})")
    dst = Path(build_dir) / work
    dst.mkdir(parents=True, exist_ok=True)
    copied = _copy_artifacts(src, dst)
    cache_stats = merge_cache(src / "cache", dst / "cache") if (src / "cache").exists() else {}
    return {"work": work, "to": str(dst), "artifacts": copied, "cache": cache_stats}


def status() -> Dict[str, Any]:
    repo = registry_path(create=True)
    _sync(repo)
    works: List[Dict[str, Any]] = []
    total_recorded = total_unique = total_compiled = total_cache = 0
    for wdir in sorted((repo / "works").glob("*")) if (repo / "works").exists() else []:
        ledger = repo / "ledger" / f"{wdir.name}.jsonl"
        entries = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines()] if ledger.exists() else []
        last = entries[-1] if entries else {}
        totals = last.get("totals", {})
        caches = len(list((wdir / "cache").glob("*/*.json")))
        works.append({"work": wdir.name, "publishes": len(entries), "last_by": last.get("by", "?"),
                      "last_at": last.get("at", "?"), "recorded_tokens": totals.get("recorded_tokens", 0),
                      "recorded_tokens_unique": totals.get("recorded_tokens_unique", 0),
                      "compiled_tokens": totals.get("compiled_tokens", 0),
                      "outputs": f"{totals.get('outputs_matched', '?')}/{totals.get('outputs_checked', '?')}",
                      "cache_entries": caches})
        total_recorded += int(totals.get("recorded_tokens", 0) or 0)
        total_unique += int(totals.get("recorded_tokens_unique", 0) or 0)
        total_compiled += int(totals.get("compiled_tokens", 0) or 0)
        total_cache += caches
    teams: Dict[str, Dict[str, Any]] = {}
    for wdir in sorted((repo / "works").glob("*")) if (repo / "works").exists() else []:
        ledger = repo / "ledger" / f"{wdir.name}.jsonl"
        for line in (ledger.read_text(encoding="utf-8").splitlines() if ledger.exists() else []):
            e = json.loads(line)
            if not e.get("team"):
                continue
            row = teams.setdefault(e["team"], {"publishes": 0, "recorded_tokens_unique": 0, "compiled_tokens": 0})
            row["publishes"] += 1
            row["recorded_tokens_unique"] += int((e.get("totals") or {}).get("recorded_tokens_unique", 0) or 0)
            row["compiled_tokens"] += int((e.get("totals") or {}).get("compiled_tokens", 0) or 0)
    return {"registry": str(repo), "works": works, "teams": teams,
            # the savings the org can claim are the *unique* ones: summing per-request usage would
            # count a session's cumulative context once per turn. The cumulative sum stays as reference.
            "org_totals": {"works": len(works), "recorded_tokens": total_recorded,
                           "recorded_tokens_unique": total_unique, "compiled_tokens": total_compiled,
                           "savings_unique_pct": round(100 * (total_unique - total_compiled) / total_unique, 1) if total_unique else None,
                           "token_savings_pct": round(100 * (total_recorded - total_compiled) / total_recorded, 1) if total_recorded else None,
                           "cache_entries": total_cache}}


def main(argv=None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="owc org", description="Shared registry: individuals' compiled work merges into one org asset")
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("init", help="Configure (and clone) the org registry")
    a.add_argument("repo", help="git URL or local path of the registry repository")
    a.add_argument("--clone", help="Where to keep the local clone (default ~/.owc/org)")
    b = sub.add_parser("publish", help="Publish a build (artifacts, merged cache, ledger entry)")
    b.add_argument("build_dir")
    b.add_argument("--work", help="Registry name (default: build dir name)")
    b.add_argument("--no-cache-contrib", action="store_true")
    c = sub.add_parser("pull", help="Pull a work from the registry into the local build directory")
    c.add_argument("work")
    c.add_argument("--build-dir", default="build")
    sub.add_parser("status", help="Works and the organization-wide savings ledger")
    args = parser.parse_args(argv)

    if args.command == "init":
        path = init(args.repo, args.clone)
        print(f"[org] registry: {args.repo}\n[org] local clone: {path}")
        return 0
    if args.command == "publish":
        entry = publish(args.build_dir, work=args.work, cache_contrib=not args.no_cache_contrib)
        cache = entry.get("cache") or {}
        print(f"[org] published {entry['work']} by {entry['by']}: {entry['artifacts']} artifacts"
              + (f", cache +{cache.get('added', 0)}/~{cache.get('replaced', 0)}/={cache.get('kept', 0)}" if cache else "")
              + ("" if entry.get("pushed") else "  (push pending — offline)"))
        return 0
    if args.command == "pull":
        res = pull(args.work, args.build_dir)
        cache = res.get("cache") or {}
        print(f"[org] pulled {res['work']} → {res['to']}: {res['artifacts']} artifacts"
              + (f", cache +{cache.get('added', 0)}" if cache else ""))
        return 0
    st = status()
    print(f"[org] registry {st['registry']}")
    print(f"{'work':28s} {'pubs':>4s} {'last by':14s} {'unique tokens rec→comp':>22s} {'outputs':>8s} {'cache':>6s}")
    for w in st["works"]:
        print(f"{w['work']:28s} {w['publishes']:4d} {w['last_by']:14s} "
              f"{w['recorded_tokens_unique']:>10,} → {w['compiled_tokens']:<9,} {w['outputs']:>8s} {w['cache_entries']:6d}")
    if st.get("teams"):
        print(f"{'team':28s} {'pubs':>4s} {'unique tokens rec→comp':>28s}")
        for team, row in sorted(st["teams"].items()):
            print(f"{team:28s} {row['publishes']:4d} {row['recorded_tokens_unique']:>14,} → {row['compiled_tokens']:<11,}")
    t = st["org_totals"]
    savings = f" (−{t['savings_unique_pct']}% unique)" if t["savings_unique_pct"] is not None else ""
    ref = f", cumulative-context sum {t['recorded_tokens']:,} −{t['token_savings_pct']}%" if t["token_savings_pct"] is not None else ""
    print(f"org total: {t['works']} works · {t['recorded_tokens_unique']:,} → {t['compiled_tokens']:,} unique tokens{savings}{ref} · {t['cache_entries']} cached escalations")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
