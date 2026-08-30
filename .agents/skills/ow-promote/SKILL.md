---
name: ow-promote
description: Promote an action of a compiled OpenWorkCompiler build from the frontier LLM to a small local model (SLM) under the deterministic quality gate — evaluates the model on the recorded examples, and on pass switches the executor in work.yaml/.work. Use when the user asks to lower the remaining LLM step, promote to an SLM, or make the build cheaper.
---

# ow-promote — frontier LLM → local SLM, gated

Invoked as `$ow-promote <target_name> <action> [model]` in Codex, `/ow-promote <target_name> <action> [model]` in Claude Code (any agent: ask for the skill by name). Default model: `qwen2.5:3b`; the endpoint is a local OpenAI-compatible server (Ollama at `http://127.0.0.1:11434/v1`, or `$OPENWORKCOMPILER_SLM_BASE_URL`).

1. The build directory is `build/<target_name with - replaced by _>/`. Run the promotion (it evaluates every recorded example of the action with the small model, gates the output on grounded facts, and only then edits the build):

   ```bash
   python3 -m core.build promote build/TARGET_DIR ACTION --model MODEL
   ```

2. Show the command output (verdict, pass rate, tokens/latency recorded → SLM, per-example gate line), then print the first 20 lines of `build/TARGET_DIR/models/slm/ACTION/PROMOTION.md`.
3. In two or three sentences, state: whether the action was promoted, what the gate checked (anchor-fact recall, grounding — no invented numbers/ids/paths —, length), and that `$ow-bench TARGET` will now execute the SLM for real and split it from the frontier model in the token ledger. If it was NOT promoted, say which check failed and suggest a larger model (e.g. `qwen2.5:7b`).
4. Do not edit `work.yaml` or the `.work` file by hand — only the promotion command changes the executor (and `python3 -m core.build demote build/TARGET_DIR ACTION` rolls it back).

End your reply with 🪜.
