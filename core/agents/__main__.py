"""``owc agent list | doctor | setup <name> | exec [--agent auto] <prompt>``"""

from __future__ import annotations

import argparse
import json
import os
import sys

from core.agents import ENV_AGENT, PRIORITY, REGISTRY, detect_all, get_backend, resolve_backend


def cmd_list(_args) -> int:
    print(f"{'agent':10s} {'installed':28s} {'skills dir':18s} {'capture':12s} invoke")
    for backend, version in detect_all():
        ver = version if version else ("yes" if version == "" else "-")
        print(f"{backend.name:10s} {ver:28s} {backend.skills_dir or '-':18s} {backend.capture:12s} {backend.invocation}")
    return 0


def cmd_doctor(args) -> int:
    cmd_list(args)
    try:
        auto = resolve_backend("auto")
        print(f"\nauto → {auto.name}" + (f" (from {ENV_AGENT}={os.environ[ENV_AGENT]})" if os.environ.get(ENV_AGENT) else " (first installed in priority order)"))
    except RuntimeError as exc:
        print(f"\nauto → none: {exc}")
    hints = []
    if os.environ.get("ANTHROPIC_BASE_URL"):
        hints.append(f"ANTHROPIC_BASE_URL={os.environ['ANTHROPIC_BASE_URL']}")
    if os.environ.get("OPENAI_BASE_URL"):
        hints.append(f"OPENAI_BASE_URL={os.environ['OPENAI_BASE_URL']}")
    print("proxy routing in env: " + (", ".join(hints) if hints else "none (see `owc agent setup <name>`)"))
    return 0


def cmd_setup(args) -> int:
    print(get_backend(args.name).describe_setup(args.proxy_url))
    return 0


def cmd_exec(args) -> int:
    backend = resolve_backend(args.agent or "auto")
    result = backend.run(args.prompt, cwd=args.cwd, read_only=args.read_only, model=args.model)
    if args.json:
        print(json.dumps({"agent": backend.name, **result.to_escalation_dict()}, ensure_ascii=False, indent=2))
    else:
        print(result.output)
        print(f"\n[owc agent exec] {backend.name} · model={result.model} · tokens={result.tokens:,} · {result.latency_ms/1000:.1f}s", file=sys.stderr)
    return result.exit_code


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="owc agent", description="Coding-agent backends (escalation, front agent, setup)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="Installed agents and their conventions").set_defaults(func=cmd_list)
    sub.add_parser("doctor", help="What `auto` would pick and how the proxy is wired").set_defaults(func=cmd_doctor)
    s = sub.add_parser("setup", help="Print how to route an agent through the proxy")
    s.add_argument("name", choices=list(REGISTRY))
    s.add_argument("--proxy-url", default="http://127.0.0.1:8787")
    s.set_defaults(func=cmd_setup)
    e = sub.add_parser("exec", help="Run a prompt with any backend non-interactively")
    e.add_argument("prompt")
    e.add_argument("--agent", default="auto", help="auto | " + " | ".join(PRIORITY))
    e.add_argument("--read-only", action="store_true")
    e.add_argument("--model")
    e.add_argument("--cwd")
    e.add_argument("--json", action="store_true")
    e.set_defaults(func=cmd_exec)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
