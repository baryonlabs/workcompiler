OpenAI Codex v0.150.1
--------
workdir: /Users/hongmartin/orca/projects/open-workflow
model: gpt-5.6-sol
provider: openworkflow
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR] (network access enabled)
reasoning effort: none
reasoning summaries: none
session id: 01a04b1d-5067-75a3-8382-64e7a10e9ff6
--------
user
$ow-bench codex-session
codex
I’m using the `ow-bench` skill to benchmark the existing `codex-session` build, then I’ll report its summary table and the remaining LLM escalations.
exec
/bin/zsh -lc 'python3 -m core.build bench build/codex_session' in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 179ms:
[bench] codex-session: tokens 46,460 -> 16,843 (-63.7%), wall 33.8s -> 23.13s (1.5x), outputs reproduced 2/2, compiled/escalated actions 2/1
  shell_python3        code          tokens  14,436 -> 0      latency    3.6s ->  0.10s  match 1/1
  shell_find           code          tokens  15,181 -> 0      latency    7.2s ->  0.01s  match 1/1
  respond              frontier_llm  tokens  16,843 -> 16,843 latency   23.0s -> 23.02s  match n/a
  report: build/codex_session/BENCHMARK.md

exec
/bin/zsh -lc "sed -n '1,25p' build/codex_session/BENCHMARK.md" in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 0ms:
# Benchmark — `codex-session`

Recorded agent session `01a04b1c-99ae-7733-8b77-814966c86046` (`codex_exec`) vs. compiled build `build/codex_session`.

| | recorded (agent) | compiled (build) | delta |
| :-- | --: | --: | --: |
| LLM tokens | 46,460 | 16,843 | −63.7% |
| wall time | 33.8 s | 23.13 s | 1.5× faster |
| outputs reproduced | — | 2/2 | |
| actions compiled / escalated | — | 2 / 1 | |

## Per action

| action | tier | executor used | tokens rec → comp | latency rec → comp | output match |
| :-- | :-- | :-- | --: | --: | :-- |
| `shell_python3` | code | code:codex_session/handlers | 14,436 → 0 | 3.6 s → 0.10 s | 1/1 |
| `shell_find` | code | code:codex_session/handlers | 15,181 → 0 | 7.2 s → 0.01 s | 1/1 |
| `respond` | frontier_llm | escalated:frontier_llm | 16,843 → 16,843 | 23.0 s → 23.02 s | n/a |

## Outputs

### `shell_python3` · step_1 — code:codex_session/handlers

recorded:


codex
```text
[bench] codex-session: tokens 46,460 -> 16,843 (-63.7%), wall 33.8s -> 23.13s (1.5x), outputs reproduced 2/2, compiled/escalated actions 2/1
  shell_python3        code          tokens  14,436 -> 0      latency    3.6s ->  0.10s  match 1/1
  shell_find           code          tokens  15,181 -> 0      latency    7.2s ->  0.01s  match 1/1
  respond              frontier_llm  tokens  16,843 -> 16,843 latency   23.0s -> 23.02s  match n/a
  report: build/codex_session/BENCHMARK.md
```

| Metric | Recorded agent | Compiled build | Delta |
| :-- | --: | --: | --: |
| LLM tokens | 46,460 | 16,843 | −63.7% |
| Wall time | 33.8 s | 23.13 s | 1.5× faster |
| Outputs reproduced | — | 2/2 | |
| Actions compiled / escalated | — | 2 / 1 | |

The compiled path saves 29,617 tokens because its two code-tier shell actions spend zero LLM tokens; both outputs were reproduced exactly. It runs 1.5× faster, while `respond` remains escalated to a frontier LLM and should become cheaper after its ML/SLM candidates are trained. 📊
tokens used
8,774
```text
[bench] codex-session: tokens 46,460 -> 16,843 (-63.7%), wall 33.8s -> 23.13s (1.5x), outputs reproduced 2/2, compiled/escalated actions 2/1
  shell_python3        code          tokens  14,436 -> 0      latency    3.6s ->  0.10s  match 1/1
  shell_find           code          tokens  15,181 -> 0      latency    7.2s ->  0.01s  match 1/1
  respond              frontier_llm  tokens  16,843 -> 16,843 latency   23.0s -> 23.02s  match n/a
  report: build/codex_session/BENCHMARK.md
```

| Metric | Recorded agent | Compiled build | Delta |
| :-- | --: | --: | --: |
| LLM tokens | 46,460 | 16,843 | −63.7% |
| Wall time | 33.8 s | 23.13 s | 1.5× faster |
| Outputs reproduced | — | 2/2 | |
| Actions compiled / escalated | — | 2 / 1 | |

The compiled path saves 29,617 tokens because its two code-tier shell actions spend zero LLM tokens; both outputs were reproduced exactly. It runs 1.5× faster, while `respond` remains escalated to a frontier LLM and should become cheaper after its ML/SLM candidates are trained. 📊
