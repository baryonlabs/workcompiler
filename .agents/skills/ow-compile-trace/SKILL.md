---
name: ow-compile-trace
description: Compile the agent session captured by the OpenWorkflow proxy (the one with the most steps) into Work IR (work.yaml). Use when the user asks to compile a captured trace or turn a session into a workflow.
---

# ow-compile-trace — captured session → Work IR

Invoked as `$ow-compile-trace <target_name>`.

1. Run `curl -s localhost:8787/v1/workcompiler/traces` and pick the run_id with the largest steps_count.
2. Compile it (substitute TARGET with the requested target name):

   ```bash
   curl -s -X POST localhost:8787/v1/workcompiler/compile -H 'Content-Type: application/json' \
     -d '{"run_id":"<run_id>","target_name":"TARGET","output_path":"build/TARGET.work.yaml"}' \
     | jq '{status, work_name, actions, executors_summary}'
   ```

3. Show that JSON, then print the first 30 lines of `build/TARGET.work.yaml`.
4. In one or two sentences, explain that the shell steps of the agent session became workflow actions with executor tiers assigned.

End your reply with ✅.
