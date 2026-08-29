# BEHAVIOR: select-exact-current-alert

## 1. Intent
Ensure every triage result is grounded in exactly one current raw alert selected by the requested alert ID, never in a nearby record or facts copied from a previous deliverable.

## 2. Evidence
The trajectory reads `materials/notes.txt`, performs an exact `alert_id` selection against `materials/data/alerts-2026-08-28.json`, prints a match count of one and the selected object, and uses `materials/previous/triage-ALR-2026-0810-04.md` only after current facts are established and only as a format reference.

## 3. Decision
- `true`: Exactly one raw alert matches the requested ID and every alert fact in both outputs equals that selected record.
- `false`: The selection is non-exact or non-unique, a different alert is used, previous-deliverable facts are reused, or either output changes or invents a source alert fact.
- `na`: The trajectory does not produce an alert triage result.

## 4. Execution
Resolve the requested ID, count exact matches in the current alerts file, stop on any count other than one, and preserve the selected `time`, `host`, `user`, `rule`, and `severity` strings in both deliverables.

## 5. Recovery
Discard outputs based on an ambiguous or incorrect record, repeat the exact-ID lookup, and escalate a missing or duplicate match as a data-integrity problem without guessing.

## 6. Failure Modes
Selecting the first alert, substring matching an ID, silently accepting duplicates, copying the previous note's host or classification, or normalizing source values inconsistently across Markdown and JSON.

