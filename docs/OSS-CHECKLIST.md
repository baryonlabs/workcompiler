# Open-source project checklist

Status of the things an open-source project is expected to have, and where each lives.

| # | Item | Status | Where |
| :-- | :-- | :-- | :-- |
| 1 | License file with a clear copyright holder | ✅ | `LICENSE` (MIT, © 2026 Baryon Labs, Seungwoo Hong) |
| 2 | README in the primary language + English | ✅ | `README.md` (ko), `README.en.md` |
| 3 | Contributing guide + contribution licensing (DCO) | ✅ | `CONTRIBUTING.md` |
| 4 | Code of conduct | ✅ | `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1) |
| 5 | Security policy and private reporting channel | ✅ | `SECURITY.md` → hello@baryon.ai |
| 6 | Issue templates (bug / feature / adoption case) and PR template | ✅ | `.github/ISSUE_TEMPLATE/`, `.github/PULL_REQUEST_TEMPLATE.md` |
| 7 | Continuous integration on every push / PR | ✅ | `.github/workflows/ci.yml` (pytest on Python 3.10–3.13, submodules, CLI smoke) |
| 8 | Changelog and tagged releases | ✅ | `CHANGELOG.md`, GitHub Releases (`v0.2.0`, …) |
| 9 | Citation metadata | ✅ | `CITATION.cff` |
| 10 | Project website with SEO metadata | ✅ | `docs/index.html` → https://baryonlabs.github.io/workcompiler/ |
| 11 | Repository description, homepage and topics | ✅ | GitHub About (topics: ai-agents, llm, compiler, workflow-automation, codex, …) |
| 12 | Code owners / maintainers | ✅ | `.github/CODEOWNERS` |
| 13 | Editor configuration | ✅ | `.editorconfig` |
| 14 | Dependencies declared, install in one command | ✅ | `pyproject.toml` — `pipx install git+https://github.com/baryonlabs/workcompiler.git` → `owc`; extras: `dev`, `telemetry` |
| 15 | Tests that run fast and green | ✅ | `tests/` (150+ tests, < 1 s) |
| 16 | Telemetry disclosed, local by default, documented opt-out | ✅ | `docs/TELEMETRY.md`, startup notice |
| 17 | Reproducible examples with real data and numbers | ✅ | `examples/` (transcripts, traces, builds, BENCHMARK) |
| 18 | Sub-projects with their own repo and versioning | ✅ | `vendor/openworklang` → baryonlabs/openworklang |
| 19 | Discussions / community channel | ✅ | GitHub Discussions enabled; email hello@baryon.ai |
| 20 | Governance / roadmap | ◻️ planned | `docs/` — to be written once external contributors join |

Re-check this list before each release.
