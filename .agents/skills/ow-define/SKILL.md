---
name: ow-define
description: Turn a raw, unrefined request into the WHAT of an OpenWorkflow work — a relentless interview (grill-me / grilling) that produces TASK.md (goal, inputs, steps, acceptance criteria) and BEHAVIOR.md contracts, then hands off to the agent run + compile pipeline. Use when someone has a business task in mind but cannot yet state the goal, rules or acceptance criteria precisely.
---

# ow-define — WHAT before HOW

Invoked as `$ow-define <short description of the work>` (e.g. `$ow-define customer renewal proposals`).

OpenWorkflow compiles a *verified* agent session into an executable build. That only pays off when the goal,
the rules and the acceptance criteria are written down first — otherwise the compiler faithfully freezes a
vague run. This skill produces those two artifacts:

| artifact | what it fixes | consumed by |
| :-- | :-- | :-- |
| `examples/<work>/TASK.md` | goal, inputs (data/paths), ordered steps, required outputs, acceptance criteria | the agent's first run (`codex exec 'Read examples/<work>/TASK.md and carry it out exactly as written.'`) |
| `examples/<work>/behaviors/<rule>/BEHAVIOR.md` (one per rule) | non-negotiable process rules with evidence and decision criteria | the compiler (`invariants`), the Oracle Gate, the benchmark |

## Procedure

1. **Grill.** Run the `$grilling` interview (installed from mattpocock/skills; `$grill-me` is its alias) on the
   user's description. Do not stop at the first plausible plan — keep asking until every item below has a
   concrete answer or an explicit "unknown / decided by the agent":
   - the single sentence goal and who consumes the result
   - every input: file, API, table, parameter (which values change per run → these become **params**)
   - the ordered steps a competent person would take, and which of them are mechanical (lookup, calculation,
     formatting) vs. judgment (wording, exceptions)
   - the rules that must never be violated (source of truth, current vs. legacy policy, approvals, caps)
   - what "done" looks like: exact output files, fields, clauses that must appear verbatim
   - the failure modes the user has seen or fears (stale data, hallucinated numbers, skipped approvals)
2. **Write `examples/<work>/TASK.md`** in the style of `examples/customer-renewal/TASK.md`: a title, the role,
   the rules in one paragraph with a pointer to `behaviors/`, then numbered steps that name the exact files and
   commands-level detail (jq / python3 / cat) so the run is auditable, and finally the required reply.
   Mark per-run values explicitly (e.g. **CUST-1001**) so parameter discovery can find them later.
3. **Write one `BEHAVIOR.md` per rule** under `examples/<work>/behaviors/<kebab-name>/`, using exactly the six
   sections the parser expects (see `adapters/agentbehavior/parser.py`):
   `## 1. Intent`, `## 2. Evidence`, `## 3. Decision` (bullets `true:` / `false:` / `na:`), `## 4. Execution`,
   `## 5. Recovery`, `## 6. Failure Modes`. Evidence must be observable in a trajectory (a step name, a file
   read, a rule invoked) — not a feeling.
4. **Add fixture data if the task needs it** under `examples/<work>/data/` (small, realistic, containing at
   least one trap the rules must catch — e.g. a retired policy or an expired contract).
5. **Hand off.** Print the next commands verbatim:

   ```bash
   python3 -m uvicorn adapters.proxy.server:app --port 8787 &
   codex exec 'Read examples/<work>/TASK.md and carry it out exactly as written.'   # first run, captured by the proxy
   # verify the outputs by hand, then:
   $ow-traces · $ow-compile-trace <work> · $ow-bench <work>
   python3 -m core.build run build/<work_dir> --request "..." --escalate codex        # new inputs via the front agent
   ```

   and explain that the compiled `build/<work_dir>/<work_dir>.work` is the HOW: it states which steps became
   deterministic code, which stay with an agent, and can be edited and recompiled.

Do not run the task yourself in this skill; its job ends when the WHAT is written and verified with the user.
End your reply with 🎯.
