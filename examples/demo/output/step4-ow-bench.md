OpenAI Codex v0.150.1
--------
workdir: /Users/hongmartin/orca/projects/open-workflow
model: gpt-5.6-sol
provider: openworkflow
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR] (network access enabled)
reasoning effort: none
reasoning summaries: none
session id: 01a04b02-ef5c-7443-beda-7983468cfb01
--------
user
$ow-bench codex-session
codex
I’m using the `ow-bench` skill to benchmark the existing `codex-session` build and summarize its report.
exec
/bin/zsh -lc 'python3 -m core.build bench build/codex_session' in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 116ms:
[bench] codex-session: tokens 46,680 -> 16,782 (-64.0%), wall 29.9s -> 17.43s (1.7x), outputs reproduced 1/2, compiled/escalated actions 2/1
  shell_python3        code          tokens  14,520 -> 0      latency    5.9s ->  0.11s  match 1/1
  shell_find           code          tokens  15,378 -> 0      latency    6.7s ->  0.02s  match 0/1
  respond              frontier_llm  tokens  16,782 -> 16,782 latency   17.3s -> 17.31s  match n/a
  report: build/codex_session/BENCHMARK.md

codex
The benchmark completed successfully. I’m reading the generated report’s first 25 lines now, as required by the skill.
exec
/bin/zsh -lc "sed -n '1,25p' build/codex_session/BENCHMARK.md" in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 0ms:
# Benchmark — `codex-session`

Recorded agent session `01a04b02-4d50-71d1-8112-430bb6ede9c1` (`codex_exec`) vs. compiled build `build/codex_session`.

| | recorded (agent) | compiled (build) | delta |
| :-- | --: | --: | --: |
| LLM tokens | 46,680 | 16,782 | −64.0% |
| wall time | 29.9 s | 17.43 s | 1.7× faster |
| outputs reproduced | — | 1/2 | |
| actions compiled / escalated | — | 2 / 1 | |

## Per action

| action | tier | executor used | tokens rec → comp | latency rec → comp | output match |
| :-- | :-- | :-- | --: | --: | :-- |
| `shell_python3` | code | code:codex_session/handlers | 14,520 → 0 | 5.9 s → 0.11 s | 1/1 |
| `shell_find` | code | code:codex_session/handlers | 15,378 → 0 | 6.7 s → 0.02 s | 0/1 |
| `respond` | frontier_llm | escalated:frontier_llm | 16,782 → 16,782 | 17.3 s → 17.31 s | n/a |

## Outputs

### `shell_python3` · step_1 — code:codex_session/handlers

recorded:


codex
```text
[bench] codex-session: tokens 46,680 -> 16,782 (-64.0%), wall 29.9s -> 17.43s (1.7x), outputs reproduced 1/2, compiled/escalated actions 2/1
  shell_python3        code          tokens 14,520 -> 0   latency 5.9s -> 0.11s   match 1/1
  shell_find           code          tokens 15,378 -> 0   latency 6.7s -> 0.02s   match 0/1
  respond              frontier_llm  tokens 16,782 -> 16,782 latency 17.3s -> 17.31s match n/a
  report: build/codex_session/BENCHMARK.md
```

| Metric | Recorded agent | Compiled build | Delta |
|---|---:|---:|---:|
| LLM tokens | 46,680 | 16,782 | −64.0% |
| Wall time | 29.9 s | 17.43 s | 1.7× faster |
| Outputs reproduced | — | 1/2 | |
| Actions compiled / escalated | — | 2 / 1 | |

The compiled path saves 29,898 tokens because both code-tier shell actions consume zero LLM tokens, and it runs 1.7× faster. It exactly reproduced 1 of 2 outputs; `respond` remains escalated to a frontier LLM and should become cheaper once ML/SLM candidates are trained. See [BENCHMARK.md](/Users/hongmartin/orca/projects/open-workflow/build/codex_session/BENCHMARK.md). 📊
tokens used
7,567
```text
[bench] codex-session: tokens 46,680 -> 16,782 (-64.0%), wall 29.9s -> 17.43s (1.7x), outputs reproduced 1/2, compiled/escalated actions 2/1
  shell_python3        code          tokens 14,520 -> 0   latency 5.9s -> 0.11s   match 1/1
  shell_find           code          tokens 15,378 -> 0   latency 6.7s -> 0.02s   match 0/1
  respond              frontier_llm  tokens 16,782 -> 16,782 latency 17.3s -> 17.31s match n/a
  report: build/codex_session/BENCHMARK.md
```

| Metric | Recorded agent | Compiled build | Delta |
|---|---:|---:|---:|
| LLM tokens | 46,680 | 16,782 | −64.0% |
| Wall time | 29.9 s | 17.43 s | 1.7× faster |
| Outputs reproduced | — | 1/2 | |
| Actions compiled / escalated | — | 2 / 1 | |

The compiled path saves 29,898 tokens because both code-tier shell actions consume zero LLM tokens, and it runs 1.7× faster. It exactly reproduced 1 of 2 outputs; `respond` remains escalated to a frontier LLM and should become cheaper once ML/SLM candidates are trained. See [BENCHMARK.md](/Users/hongmartin/orca/projects/open-workflow/build/codex_session/BENCHMARK.md). 📊
