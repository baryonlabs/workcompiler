# Contributing to OpenWorkCompiler

Thanks for helping turn verified agent work into deterministic execution. This guide covers how to
set up, what we accept, and the licensing terms for contributions.

## Ways to contribute

| Kind | Where | Notes |
| :-- | :-- | :-- |
| **Adoption cases** — you compiled a real business task | email **hello@baryon.ai** or open a `case` issue | We are actively collecting real-world cases (see below). Anonymized numbers are welcome. |
| Bug reports / feature requests | GitHub Issues | Include the trace or build (`build/<work>/trace.json`, `BENCHMARK.md`) when relevant. |
| Code: proxy, compiler, build backend, benchmark, front agent | this repository | See *Development* below. |
| The `.work` language (parser, compiler, spec) | [baryonlabs/openworklang](https://github.com/baryonlabs/openworklang) | Vendored here as the `vendor/openworklang` submodule; language changes go there first. |
| Codex skills (`.agents/skills/ow-*`) | this repository | Keep skills deterministic: exact commands, an emoji terminator, no task execution inside `$ow-define`. |
| Docs, examples, translations (ko/en) | this repository | Keep README.md (ko) and README.en.md in sync. |

### We are collecting adoption cases

If you have applied OpenWorkCompiler to a real task — even a small one — we would like to hear
about it: what the WHAT looked like (`TASK.md` / `BEHAVIOR.md`), what the compiler lowered to code /
rule / ml / slm, the before/after token and time figures from `BENCHMARK.md`, and what still
escalates to an agent. Write to **hello@baryon.ai** or open an issue with the `case` label. Cases
may be featured (with permission, anonymized on request) in `examples/cases/`.

## Development

```bash
git clone --recurse-submodules https://github.com/baryonlabs/workcompiler.git
cd workcompiler
python3 -m pip install -e ".[dev]"          # fastapi, pydantic, PyYAML, httpx, pytest
python3 -m pytest -q                       # must stay green
```

- Python 3.10+. Standard library first; new dependencies need a reason in the PR.
- Code lives under `core/` (compiler, build backend, runtime), `adapters/` (proxy, behaviors),
  `.agents/skills/` (Codex skills), `examples/` (real, reproducible runs).
- Every behavior change needs a test in `tests/`. The suite runs in well under a second; keep it so.
- Benchmarks and examples must be **real**: no fabricated transcripts, traces or numbers. If you
  regenerate an example, regenerate its transcript, trace and `BENCHMARK.md` together.
- Recorded artifacts (`*transcript.md`, `proxy-trace-*.json`, `trace.json`, `conversations/`) are
  historical records — do not edit them by hand.
- Demo GIFs are recorded with [vhs](https://github.com/charmbracelet/vhs) from the tapes in
  `docs/demo/`; the tape header documents the setup and post-processing.

### Pull requests

1. Open an issue or a short discussion for anything larger than a fix.
2. Branch from `main`; keep PRs focused (one feature or fix).
3. Run `python3 -m pytest -q`; update README (ko + en) and `CHANGELOG.md` when user-visible.
4. Commit messages: `type: summary` (`feat`, `fix`, `docs`, `refactor`, `test`, `release`).
5. Sign off every commit (see below).

## Licensing of contributions — DCO

OpenWorkCompiler is released under the [MIT License](LICENSE). Copyright in the original work is
held by **Baryon Labs (Seungwoo Hong)**. Contributors keep the copyright to their own contributions
and license them to the project under the same MIT terms.

We use the [Developer Certificate of Origin 1.1](https://developercertificate.org/) instead of a
CLA. Certify it by signing off each commit:

```bash
git commit -s -m "feat: …"
# adds: Signed-off-by: Your Name <you@example.com>
```

By signing off you state that you wrote the change (or have the right to submit it) and that you
submit it under the MIT License.

## Code of conduct

Be respectful and specific. Review the work, not the person. Disagreements are resolved with
evidence — a failing test, a benchmark, a trace.

## Contact

- Adoption cases, partnerships, questions: **hello@baryon.ai**
- Issues and PRs: https://github.com/baryonlabs/workcompiler
