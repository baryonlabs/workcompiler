"""``owc`` — the OpenWorkCompiler command line (installed by pip/pipx).

    owc proxy [--port 8787]                 start the zero-code proxy (Codex / Responses API passthrough)
    owc compile <file.work> [...]           OpenWorkLang → build/<work>/ (same as python -m core.openworklang compile)
    owc build <from-work|from-trace|bench|run|show> ...   the build backend (same as python -m core.build)
    owc agent <list|doctor|setup|exec> ...  coding-agent backends (Claude Code, Codex, Gemini, opencode, Aider)
    owc skills <install|list|doctor> ...    sync .agents/skills into each agent's skills directory
    owc version
"""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import PackageNotFoundError, version as _pkg_version


def _version() -> str:
    try:
        return _pkg_version("openworkcompiler")
    except PackageNotFoundError:
        return "0.0.0+source"


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog="owc", description="OpenWorkCompiler — compile verified agent work into deterministic execution")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("proxy", help="Start the zero-code proxy (bind to localhost only)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8787)
    p.add_argument("--workspace", help="Directory builds/outputs may be written to (default: current directory)")

    sub.add_parser("compile", help="Compile an OpenWorkLang .work file into a build tree", add_help=False)
    sub.add_parser("build", help="Build backend: from-work | from-trace | bench | run | show", add_help=False)
    sub.add_parser("agent", help="Agent backends: list | doctor | setup <name> | exec <prompt>", add_help=False)
    sub.add_parser("skills", help="Skills sync: install [--agent …] | list | doctor [--check]", add_help=False)
    sub.add_parser("version", help="Print the version")

    # let sub-CLIs own their arguments
    if argv and argv[0] in ("compile", "build", "agent", "skills"):
        rest = argv[1:]
        if argv[0] == "compile":
            from core.openworklang.__main__ import main as compile_main
            return compile_main(["compile", *rest])
        if argv[0] == "agent":
            from core.agents.__main__ import main as agent_main
            return agent_main(rest)
        if argv[0] == "skills":
            from core.skills import main as skills_main
            return skills_main(rest)
        from core.build.__main__ import main as build_main
        return build_main(rest)

    args = parser.parse_args(argv)
    if args.command == "version":
        print(f"owc {_version()}")
        return 0
    if args.command == "proxy":
        import os
        import uvicorn
        from core import telemetry

        if args.workspace:
            os.environ["OPENWORKCOMPILER_WORKSPACE_DIR"] = args.workspace
        telemetry.notice("proxy")
        base = f"http://{args.host}:{args.port}"
        print(f"[owc] proxy on {base}", file=sys.stderr)
        print(f"[owc]   Claude Code:      ANTHROPIC_BASE_URL={base}", file=sys.stderr)
        print(f"[owc]   Codex CLI:        base_url = \"{base}/backend-api/codex\"   (owc agent setup codex)", file=sys.stderr)
        print(f"[owc]   OpenAI-compatible: OPENAI_BASE_URL={base}/v1   (Cursor, opencode, Aider, SDKs)", file=sys.stderr)
        uvicorn.run("adapters.proxy.server:app", host=args.host, port=args.port, log_level="info")
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
