---
name: ow-compile-work
description: Compile an OpenWorkLang (.work) file into OpenWorkflow Work IR (work.yaml) plus a LinkML schema. Use when the user mentions a .work file, OpenWorkLang, or asks to compile an agent program.
---

# ow-compile-work — OpenWorkLang → Work IR

Invoked as `$ow-compile-work <path/to/file.work>`.

Let NAME be the source file stem (e.g. `quality_analysis` for `examples/quality_analysis.work`) and run exactly:

```bash
python3 -m core.openworklang compile <path/to/file.work> --linkml build/NAME.linkml.yaml
```

Then:

1. Show the summary the command prints (work, inputs, outputs, actions, invariants, executors).
2. Print the first 25 lines of `build/NAME.work.yaml`.
3. In two or three sentences, explain how the actions were lowered across executor tiers (code / rule / ml / slm) and which invariants are locked.

Do not modify any source files. End your reply with 🧩.
