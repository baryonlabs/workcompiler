---
name: ow-bench
description: Benchmark a compiled OpenWorkCompiler build against the agent session it was compiled from — compares final outputs, LLM token usage and wall-clock speed of the compiled tiers vs. the recorded agent. Use when the user asks how much cheaper/faster the compiled workflow is, or whether it reproduces the agent's results.
---

# ow-bench — recorded agent vs. compiled build

Invoked as `$ow-bench <target_name>` in Codex, `/ow-bench <target_name>` in Claude Code (any agent: ask for the skill by name).

1. The build directory is `build/<target_name with - replaced by _>/`; it already contains `trace.json` (the session it was compiled from), so no proxy call is needed.
2. Run the benchmark:

   ```bash
   python3 -m core.build bench build/TARGET_DIR
   ```

3. Show the command output, then print the top table of `build/TARGET_DIR/BENCHMARK.md` (first 25 lines).
4. In two or three sentences, state: how many tokens the compiled path saves and why (code/rule tiers spend 0), the speedup, how many outputs were reproduced exactly, and which actions are still escalated to a frontier LLM — those can be lowered to a small local model with `$ow-promote <target> <action>`; if an action already runs on the SLM tier, say so and quote its gate verdict from the SLM section of the report.

End your reply with 📊.
