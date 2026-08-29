# Assumptions: security and operations incident alert triage notes

The requester was unavailable for an interactive interview. Following the requested material-driven variant of the `grilling` process, each round below records the full decision frontier, the recommended answer adopted for this definition, and why that answer is supported by the supplied materials. These are decisions to correct before the first run if the materials were incomplete or misleading.

## Round 1 — Goal, consumer, and run identity

❓ **Q1 — Single outcome:** What is the one-sentence goal of this work?

➡️ **Chosen answer:** Produce an auditable Markdown triage note and machine-readable JSON classification for one requested security or operations alert within 15 minutes of receipt, so the on-call engineer can decide or continue the response safely.

**Why:** `materials/memo.md` requires a triage note within 15 minutes and a Markdown note plus classification JSON. It also makes the on-call engineer the decision-maker for sensitive cases.

---

❓ **Q2 — Consumer:** Who consumes the outputs?

➡️ **Chosen answer:** The primary consumer is the on-call engineer; downstream automation may consume the JSON classification.

**Why:** The memo explicitly calls for paging the on-call engineer, while requiring a separate classification JSON strongly implies a machine-readable downstream consumer. The latter is an inference and should be corrected if the JSON serves another purpose.

---

❓ **Q3 — Per-run identity:** Which values vary per run, and what are their values in the first run?

➡️ **Chosen answer:** The main per-run parameter is `alert_id`; its first-run value is **ALR-2026-0828-17**. The reference date is **2026-08-29**, but correlation windows are calculated from the alert timestamp rather than midnight or the reference date.

**Why:** `materials/notes.txt` names the target alert and date. The memo defines a 24-hour relationship to an alert, so the alert's own timestamp is the least ambiguous anchor.

## Round 2 — Inputs and authority

❓ **Q4 — Complete input set:** Which files must be consulted, and are any APIs, tables, or missing parameters required?

➡️ **Chosen answer:** Use only the supplied files: `materials/notes.txt` for the requested ID and reference date; `materials/data/alerts-2026-08-28.json` for alert facts; `materials/data/signatures.yaml` for classification and runbook mapping; `materials/data/change-log.csv` for same-host change correlation; the mapped file under `materials/runbooks/` for runbook steps; `materials/previous/triage-ALR-2026-0810-04.md` as the Markdown format model; and `materials/memo.md` as the governing policy. No external API or additional table is assumed.

**Why:** These are all of the supplied work materials and collectively cover every step named by the lead. Restricting the run to them prevents unsupported enrichment.

---

❓ **Q5 — Source precedence:** What wins if the prior deliverable conflicts with the lead memo or current raw files?

➡️ **Chosen answer:** The lead memo governs process and escalation; current raw alert, signature, change, and runbook files govern facts; personal notes identify the requested run; the previous deliverable governs presentation only.

**Why:** The prior note is an example for a different alert and the memo calls it a format. Treating it as policy or current data could reproduce stale facts or unsafe decisions.

---

❓ **Q6 — Missing or duplicate target:** What happens if the requested alert ID is absent or occurs more than once?

➡️ **Chosen answer:** Stop without producing a normal classification, report the data-integrity problem, and require on-call review. Never silently select a similar or first matching alert.

**Why:** The memo says to find “the corresponding alert.” A unique exact match is necessary to avoid triaging the wrong incident. The stop-and-review handling is a safety inference because the materials do not specify this failure path.

## Round 3 — Ordered method and decision boundaries

❓ **Q7 — Competent-person workflow:** What ordered steps should the run follow, and which are mechanical versus judgment-based?

➡️ **Chosen answer:** (1) mechanically resolve the requested ID and uniquely extract its fields; (2) mechanically exact-match its `rule` in the signature registry; (3) mechanically compute same-host changes in the inclusive interval from 24 hours before the alert through the alert time; (4) apply the escalation rule deterministically; (5) when and only when the signature class is `known` and a runbook is present, mechanically extract its first three numbered steps; (6) synthesize the concise Markdown classification wording and serialize the fixed JSON record; (7) validate both outputs. Wording is the only substantive judgment step; classification and facts are rule/data driven.

**Why:** This is the memo's stated sequence, with validation added to make the run auditable and safe.

---

❓ **Q8 — Signature semantics:** Does any registry match count as a “known signature” eligible for runbook handling?

➡️ **Chosen answer:** No. Exact rule presence and class are separate. Only `class: known` is handled as a known signature. `class: privilege_escalation` must page immediately even though the rule exists in the registry. No fuzzy or semantic rule matching is allowed.

**Why:** `sudo-from-service-account` is present but explicitly classified `privilege_escalation`; the memo separately mandates immediate paging for privilege escalation. This is the main trap in the fixture.

---

❓ **Q9 — Escalation boundary:** May the triager recommend or execute remediation for a privilege-escalation or unmatched case?

➡️ **Chosen answer:** No. Classify it as `page-oncall-immediately`, state that the on-call engineer decides the response, and do not invent, recommend, or execute containment/remediation steps. A registry `default_action` may support the classification but cannot authorize action by the triager.

**Why:** The memo says “we do not decide the action.” This also prevents the `default_action` field from being misread as permission to act.

---

❓ **Q10 — Change window:** What exactly counts as a related change?

➡️ **Chosen answer:** Include every change for the exact same host whose timestamp is in `[alert_time - 24 hours, alert_time]`, using the timestamps as UTC. Label the result “possible change correlation,” list supporting change details, and never claim causation.

**Why:** The memo specifies same host and within 24 hours. Anchoring the interval to the alert and limiting the claim to possibility follows its wording. For the first run, `CHG-5102` on `db-01` at `2026-08-28T22:55:00Z` is 46 minutes before the alert and therefore qualifies.

## Round 4 — Outputs and exact completion criteria

❓ **Q11 — Output paths:** What exact files constitute the deliverable?

➡️ **Chosen answer:** For **ALR-2026-0828-17**, write `build/incident-triage/triage-ALR-2026-0828-17.md` and `build/incident-triage/triage-ALR-2026-0828-17.json`. Generalize both names as `triage-<alert_id>` for later runs.

**Why:** `materials/notes.txt` gives both filename patterns, and the requester explicitly requires outputs under `build/incident-triage/`.

---

❓ **Q12 — Markdown contract:** Which sections and facts must the note contain?

➡️ **Chosen answer:** Follow the previous note's structure: title; normalized alert line with time, host, user, rule, and severity; signature status/class and runbook reference when applicable; related-change status and details; `## Classification`; and `## Runbook first steps` only for a `known` signature with a valid mapped runbook. For escalations, the classification must say “Page on-call immediately” and “The on-call engineer decides the response.”

**Why:** The prior deliverable supplies the layout, while the memo supplies required facts and the non-decision boundary. The two escalation sentences are fixed wording chosen to make compliance unambiguous; the materials do not prescribe exact English text.

---

❓ **Q13 — JSON contract:** What exact machine-readable fields are required?

➡️ **Chosen answer:** Use a single JSON object with `alert_id`, `time`, `host`, `user`, `rule`, `severity`, `signature` (`matched`, `class`, `runbook`), `related_changes_within_24h` (array of `change_id`, `changed_at`, `author`, `summary`), `change_correlation_possible`, `classification`, `page_oncall`, and `action_decision_owner`. Preserve source strings; use booleans and arrays as typed values; use JSON `null` when no runbook exists.

**Why:** The memo requires the five alert fields, signature/runbook result, change correlation, classification JSON, and escalation ownership. It does not define a schema, so this minimal explicit schema is a chosen assumption intended to keep Markdown and JSON consistent.

---

❓ **Q14 — Definition of done:** What validation proves completion?

➡️ **Chosen answer:** Both files exist at the exact paths; the JSON parses; all required fields exist; both artifacts agree with the uniquely selected alert and each other; signature classification is derived by exact rule lookup; all related changes satisfy host and time predicates; runbook text, if applicable, is verbatim from the mapped current file; escalation wording and flags obey policy; no unsupported facts or response actions appear; and the elapsed trajectory from work receipt to completed files is no more than 15 minutes.

**Why:** These checks cover the memo's SLA and content rules and make the output objectively reviewable.

## Round 5 — Failure modes and recovery

❓ **Q15 — Known and feared failures:** Which failures must the definition explicitly guard against?

➡️ **Chosen answer:** Wrong/duplicate alert selection; copying facts from the previous note; fuzzy signature matching; treating any registry hit as `known`; skipping immediate paging for privilege escalation or an unmatched signature; following a `default_action` as if authorized; using the reference date instead of alert time for the 24-hour window; matching changes on the wrong host; claiming a change caused the alert; inventing or paraphrasing runbook steps; adding runbook steps to an escalation case without an eligible runbook; Markdown/JSON disagreement; malformed JSON; unsupported facts; and missing the 15-minute SLA.

**Why:** Several arise directly from the memo's prohibitions and supplied trap; the rest are predictable ways to corrupt evidence or make the paired deliverables disagree.

---

❓ **Q16 — Recovery behavior:** What should happen when evidence is missing, malformed, inconsistent, or a mapped runbook cannot be read?

➡️ **Chosen answer:** Do not guess. Record the evidence problem, classify for immediate on-call review where a safe normal classification cannot be established, omit unsupported runbook instructions, preserve the raw facts that can be verified, and surface the failure in the final reply.

**Why:** The memo prioritizes escalation over autonomous decisions for unknown or sensitive conditions. This is a conservative extension to unspecified data-quality failures.

## Resolved first-run expectations (for later correction, not task execution)

These are expected consequences of the adopted rules, included only to make assumptions reviewable:

- Exact target: `ALR-2026-0828-17`.
- Registry result: matched, class `privilege_escalation`, no runbook.
- Related change: `CHG-5102`, same host, 46 minutes before the alert; correlation is possible, causation is not established.
- Required classification: immediate on-call page; the triager does not decide or perform remediation.

