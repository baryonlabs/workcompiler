# BEHAVIOR: keep-report-evidence-auditable

## 1. Intent
Produce mutually consistent structured and human-readable anomaly artifacts whose facts can be reproduced from the supplied incident sources.

## 2. Evidence
The trajectory writes `build/quality-anomaly/anomaly-2026-08-27.json` before rendering `build/quality-anomaly/anomaly-report-2026-08-27.md`, records all source paths and derivations, parses the JSON, and mechanically compares MES facts, sensor intervals/peaks, calibration trust, causal support, remediation, and approval status across sources and outputs.

## 3. Decision
- `true`: Both incident-dated files exist, parse, concern only the bound incident, reproduce the source calculations, agree on every material fact and decision, and record a passed validation.
- `false`: A file is missing or malformed, prose is drafted from memory, the files disagree, sources/derivations are absent, unrelated shifts appear, or validation passes despite a mismatch.
- `na`: The trajectory does not produce the anomaly JSON and report pair.

## 4. Execution
Serialize source-derived structured evidence first, render the report from it in the previous deliverable's section format, then run source-to-JSON and JSON-to-Markdown consistency checks before replying.

## 5. Recovery
Treat freshly recomputed source evidence as authoritative, correct or regenerate the JSON, re-render Markdown, and repeat all validations without modifying source materials or performing remediation.

## 6. Failure Modes
Drafting prose first and backfilling JSON, copying prior-incident values, mismatched dates/rates/peaks/trust labels, omitting limitations or approval status, or declaring success before mechanical validation.
