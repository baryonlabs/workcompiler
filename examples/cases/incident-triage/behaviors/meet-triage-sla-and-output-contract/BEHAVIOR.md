# BEHAVIOR: meet-triage-sla-and-output-contract

## 1. Intent
Deliver a timely, mutually consistent human-readable note and machine-readable classification whose completion can be objectively verified.

## 2. Evidence
The trajectory records a UTC start time, writes both required `build/incident-triage/triage-<alert_id>` files, parses and type-checks the JSON, checks required Markdown content and cross-file agreement, prints validation status, and calculates elapsed time.

## 3. Decision
- `true`: Both exact-path outputs pass schema, content, source-grounding, and cross-file checks and are completed within 15 minutes of recorded work receipt.
- `false`: An output is missing/malformed, required facts or escalation wording are absent, the files disagree, validation is skipped or fails, or elapsed time exceeds 15 minutes while success is claimed.
- `na`: The run is stopped before normal output because the target alert cannot be uniquely established, and that failure is explicitly reported for on-call review.

## 4. Execution
Start the SLA clock before investigation, write the fixed Markdown and JSON contracts, validate types and policy-sensitive content with an auditable script, calculate elapsed time, and report failures honestly.

## 5. Recovery
Correct source or consistency errors and rerun validation; if the 15-minute limit is already exceeded, finish the safest evidence-backed handoff but mark the SLA breach rather than resetting the clock or claiming compliance.

## 6. Failure Modes
Starting the clock late, omitting one artifact, malformed JSON, missing fields, Markdown/JSON divergence, silently overwriting evidence with guessed values, skipping validation, or hiding an SLA miss.
