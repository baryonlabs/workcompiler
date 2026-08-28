---
name: ow-compile-trace
description: Compile the agent session captured by the OpenWorkflow proxy (the one with the most steps) into Work IR plus an executable build tree (code handlers that replay recorded shell commands, ML/SLM datasets, prompt contracts). Use when the user asks to compile a captured trace or turn a session into a workflow.
---

# ow-compile-trace — captured session → build tree

Invoked as `$ow-compile-trace <target_name>`.

1. Run `curl -s localhost:8787/v1/workcompiler/traces` and pick the run_id with the largest steps_count.
2. Compile it (substitute TARGET with the requested target name):

   ```bash
   curl -s -X POST localhost:8787/v1/workcompiler/compile -H 'Content-Type: application/json' \
     -d '{"run_id":"<run_id>","target_name":"TARGET","build_dir":"build"}' \
     | jq '{status, work_name, actions, executors_summary, build}'
   ```

3. Show that JSON, then run `find build/<work dir from build.build_dir> -type f | sort` and print the first 30 lines of `<build_dir>/work.yaml` plus one generated `handlers/*.py`.
4. In one or two sentences, explain that the session's shell steps became replayable code handlers (`handlers/shell_*.py` re-run the recorded command), and non-deterministic steps became prompt contracts / training packages.

End your reply with ✅.
