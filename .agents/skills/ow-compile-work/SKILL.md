---
name: ow-compile-work
description: Compile an OpenWorkLang (.work) file into an executable OpenWorkCompiler build tree (work.yaml + per-tier artifacts - code handlers, rule files, ML/SLM training packages, LinkML schema). Use when the user mentions a .work file, OpenWorkLang, or asks to compile an agent program.
---

# ow-compile-work — OpenWorkLang → build tree

Invoked as `$ow-compile-work <path/to/file.work>`.

Run exactly:

```bash
python3 -m core.openworklang compile <path/to/file.work>
```

It writes `build/<work>/` with one artifact family per executor tier and prints a summary. Then:

1. Show the summary the command prints (work, inputs, outputs, actions, invariants, executors, artifacts).
2. Run `find build/<work> -type f | sort` and show the tree.
3. Print the first 25 lines of `build/<work>/work.yaml` and the full `build/<work>/handlers/<first code action>.py` if a code handler exists.
4. In two or three sentences, explain what each tier's artifact is for: `handlers/*.py` (code, run(**inputs)), `rules/*.rule.yaml` (RuleExecutor branches), `models/ml/<action>/` (model card + dataset + train.py), `models/slm/<action>/` (training_candidate.yaml + dataset.jsonl + TRL train.py), `prompts/*.prompt.md` (frontier LLM contract), and which invariants are locked.

Do not modify any source files. End your reply with 🧩.
