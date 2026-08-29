---
name: ow-traces
description: List agent sessions captured by the OpenWorkCompiler zero-code proxy (localhost:8787). Use when the user asks what the proxy has captured, or for TraceIR sessions.
---

# ow-traces — captured agent sessions

Invoked as `$ow-traces`.

Run:

```bash
curl -s localhost:8787/v1/workcompiler/traces | jq
```

Summarize every captured session in one line each: run_id, source_agent, steps_count and actions. Mention that the current Codex session itself is being captured through the proxy, so its own shell calls appear as steps. For details of one session use `curl -s localhost:8787/v1/workcompiler/traces/<run_id> | jq`. End your reply with 📡.
