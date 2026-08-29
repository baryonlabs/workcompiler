# BEHAVIOR: keep-decision-artifacts-auditable

## 1. Intent
Produce mutually consistent human-readable and machine-readable decisions with observable sources and all applicable policy citations.

## 2. Evidence
The trajectory writes the JSON evidence record before drafting the Markdown from it, records source file paths and applied clauses, then parses and compares both files for identity, evidence, amount, status, authority, and clause agreement.

## 3. Decision
- `true`: Both required files exist for only the selected request, agree on all material facts and outcomes, cite every applied Policy v3 clause, and make no unsupported claim of external action.
- `false`: A file is missing, filenames or contents concern another request, artifacts disagree, clauses/sources are absent, or the memo claims an unperformed refund, approval, or notification.
- `na`: The trajectory does not produce refund decision artifacts.

## 4. Execution
Serialize structured evidence first, render the memo from that record, and run a final pairwise consistency validation before replying.

## 5. Recovery
Treat the JSON evidence derived from verified sources as the drafting input, regenerate the memo or both artifacts as needed, and repeat consistency checks without performing external actions.

## 6. Failure Modes
Drafting prose first and backfilling evidence, omitting clause numbers, mismatched amounts/statuses, processing multiple requests, or stating that a refund/customer notice was sent when it was not.
