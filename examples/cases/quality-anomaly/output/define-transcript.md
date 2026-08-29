OpenAI Codex v0.150.1
--------
workdir: /Users/hongmartin/orca/projects/open-workflow
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR]
reasoning effort: none
reasoning summaries: none
session id: 01a04b2c-5e85-7e63-9840-8558f4b3c826
--------
user
$ow-define manufacturing line quality anomaly response reports

Context for this run: the requester is a complete beginner — no prompt-engineering knowledge — who only dropped their work materials into examples/cases/quality-anomaly/materials/ (a memo from their lead, their own notes, a previous finished deliverable, and the raw data files). They are NOT available to answer follow-up questions right now.

So run the grilling interview against the materials instead of the person: for every round, write the numbered questions AND take your own recommended answer, grounded in the memo/notes/previous deliverable. Record each question, the answer you chose and why in examples/cases/quality-anomaly/ASSUMPTIONS.md (so the requester can correct them later). Then write examples/cases/quality-anomaly/TASK.md (steps must reference files under examples/cases/quality-anomaly/materials/... and write outputs under build/quality-anomaly/), and one BEHAVIOR.md per rule under examples/cases/quality-anomaly/behaviors/<kebab-name>/ in the six-section format. Do not perform the task itself.
codex
I’m using `ow-define` and its required `grilling` skill. Since the requester is unavailable, I’ll treat the supplied materials as the interview subject, record every numbered question plus my evidence-based answer and rationale in `ASSUMPTIONS.md`, then produce only the task and behavior specifications—not the anomaly report itself.
exec
/bin/zsh -lc "sed -n '1,240p' .agents/skills/grilling/SKILL.md && find examples/cases/quality-anomaly/materials -maxdepth 2 -type f -print | sort && sed -n '1,240p' examples/customer-renewal/TASK.md && sed -n '1,220p' adapters/agentbehavior/parser.py" in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 0ms:
---
name: grilling
description: Grill the user relentlessly about a plan, decision, or idea. Use when the user wants to stress-test their thinking, or uses any 'grill' trigger phrases.
---

Interview the user relentlessly until you reach a shared understanding. Map this as a **design tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round: number each question and give your recommended answer. Then wait for the user's answers before the next round.

Format a round like so:

```
❓ **Q1** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>

---

❓ **Q2** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>
```

Each round the user answers reshapes the tree: settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, tools, etc.), dispatch a sub-agent to find it; don't ask the user for anything you could look up yourself. Don't block on it: a running exploration is an unsettled prerequisite, so only the questions downstream of it wait for the sub-agent to report; ask the rest of the frontier now. The _decisions_ are the user's: put each to them and wait.

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Do not act on it until the user confirms you have reached a shared understanding.
examples/cases/quality-anomaly/materials/data/calibration-log.csv
examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv
examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv
examples/cases/quality-anomaly/materials/data/thresholds.yaml
examples/cases/quality-anomaly/materials/memo.md
examples/cases/quality-anomaly/materials/notes.txt
examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md
# Task: renewal proposal for customer CUST-1001

You are the sales-ops assistant. Prepare the annual renewal proposal for **CUST-1001**.

Rules (from `behaviors/`): verify the *active* contract in the CRM before pricing, and price with the
*current* policy `data/pricing/pricing_v2.yaml` — never the legacy table.

Do the work with auditable shell commands (jq / python3 / cat), from the repository root:

1. **Lookup contract** — read `examples/customer-renewal/data/crm/contracts.json`, select the
   contract for CUST-1001 whose `status` is `active`, and print it.
2. **Calculate usage** — from `examples/customer-renewal/data/usage/usage-2026-07.csv`, compute for
   CUST-1001 the peak `seats_active` over the 3 months, the growth of `seats_active` (last vs first
   month, in %) and the average `api_calls`.
3. **Price the offer** — apply `pricing_v2.yaml`: recommended committed seats per `seat_recommendation`,
   list price for the plan, volume discount band, loyalty discount if the customer has >= 2 years of
   continuous service (use the active contract's `start_date`, today is 2026-08-29), cap at
   `max_total_discount_pct`. Compute monthly and annual totals. Write the calculation as JSON to
   `build/renewal/pricing-CUST-1001.json`.
4. **Draft the proposal** — write `build/renewal/proposal-CUST-1001.md` with: customer & contract
   summary, usage summary, a pricing table (seats × list price − discounts = monthly / annual), and
   every clause from `required_clauses` verbatim.
5. Reply with a short summary (recommended seats, total annual price, discounts applied) and the two
   file paths.
"""AgentBehavior BEHAVIOR.md parser.

Parses AgentBehavior specification markdown files into structured dictionaries
containing Intent, Evidence, Decision, Execution, Recovery, and Failure Modes.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional


def _normalize_section_title(title: str) -> str:
    """Normalize a markdown section title to a standard snake_case key."""
    # Remove leading numbering like '1.', '1. ', 'Section 1:'
    cleaned = re.sub(r"^(?:section\s+)?\d+[\.\:\-\s]*", "", title.strip(), flags=re.IGNORECASE)
    # Convert spaces/hyphens to underscore and lowercase
    cleaned = re.sub(r"[\s\-]+", "_", cleaned.strip().lower())
    return cleaned


def _parse_decision_bullets(text: str) -> Dict[str, str]:
    """Parse Decision section bullets into true/false/na mapping."""
    decisions: Dict[str, str] = {
        "true": "",
        "false": "",
        "na": "",
        "raw": text.strip(),
    }

    # Match patterns like `- `true`: explanation` or `- true: explanation` or `* `true`: ...`
    pattern = re.compile(
        r"^[\*\-]\s*[`'\"]?(true|false|na)[`'\"]?\s*:\s*(.+)$",
        re.IGNORECASE | re.MULTILINE,
    )

    for match in pattern.finditer(text):
        verdict = match.group(1).lower()
        explanation = match.group(2).strip()
        decisions[verdict] = explanation

    return decisions


def parse_behavior_md(content: str) -> Dict[str, Any]:
    """Parse an AgentBehavior BEHAVIOR.md markdown document into a structured dict.

    Args:
        content: The raw markdown string content of a BEHAVIOR.md file.

    Returns:
        Dict[str, Any] containing:
            - name: The behavior name extracted from title.
            - intent: The intent section text.
            - evidence: The evidence section text.
            - decision: Dict containing true, false, na, and raw decision criteria.
            - execution: The execution section text.
            - recovery: The recovery section text.
            - failure_modes: The failure modes section text.
            - sections: Dictionary mapping all raw/custom section names to their text.
            - raw: The full original markdown content.
    """
    if not content or not content.strip():
        return {
            "name": "",
            "intent": "",
            "evidence": "",
            "decision": {"true": "", "false": "", "na": "", "raw": ""},
            "execution": "",
            "recovery": "",
            "failure_modes": "",
            "sections": {},
            "raw": content,
        }

    lines = content.splitlines()
    behavior_name = ""
    sections: Dict[str, str] = {}
    current_section: Optional[str] = None
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Check for top-level title: # BEHAVIOR: <name> or # <name>
        h1_match = re.match(r"^#\s+(?:BEHAVIOR\s*:\s*)?(.+)$", stripped, re.IGNORECASE)
        if h1_match and not behavior_name:
            behavior_name = h1_match.group(1).strip()
            continue

        # Check for section header (## or ###)
        h2_match = re.match(r"^#{2,3}\s+(.+)$", stripped)
        if h2_match:
            if current_section is not None:
                sections[current_section] = "\n".join(current_lines).strip()
                current_lines = []
            raw_title = h2_match.group(1).strip()
            current_section = _normalize_section_title(raw_title)
            continue

        if current_section is not None:
            current_lines.append(line)

    if current_section is not None:
        sections[current_section] = "\n".join(current_lines).strip()

    # Extract standard fields with fallbacks
    intent = sections.get("intent", "")
    evidence = sections.get("evidence", "")
    raw_decision = sections.get("decision", "")
    decision_dict = _parse_decision_bullets(raw_decision)
    execution = sections.get("execution", "")
    recovery = sections.get("recovery", "")
    failure_modes = (
        sections.get("failure_modes")
        or sections.get("failure_mode")
        or sections.get("failures")
        or ""
    )

    return {
        "name": behavior_name,
        "intent": intent,
        "evidence": evidence,
        "decision": decision_dict,
        "execution": execution,
        "recovery": recovery,
        "failure_modes": failure_modes,
        "sections": sections,
        "raw": content,
    }


def load_behavior_file(path: str | Path) -> Dict[str, Any]:
    """Load and parse an AgentBehavior BEHAVIOR.md file from disk.

    Args:
        path: Path to the BEHAVIOR.md file.

    Returns:
        Dict[str, Any] parsed behavior dictionary.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Behavior file not found: {file_path}")

    content = file_path.read_text(encoding="utf-8")
    parsed = parse_behavior_md(content)

    # If behavior name wasn't in H1 title, fallback to parent directory name
    if not parsed["name"]:
        parsed["name"] = file_path.parent.name

    return parsed

codex
The grilling rules normally pause for a person after each frontier round. Your instruction explicitly replaces that pause: I’m advancing round by round using the materials’ strongest supported answer, while preserving the unresolved choices as correctable assumptions. I’ve confirmed the available evidence set and am now extracting its rules, output schema, traps, and failure history.
exec
/bin/zsh -lc 'for f in examples/cases/quality-anomaly/materials/memo.md examples/cases/quality-anomaly/materials/notes.txt examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md examples/cases/quality-anomaly/materials/data/thresholds.yaml examples/cases/quality-anomaly/materials/data/calibration-log.csv examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv; do echo "FILE: $f"; sed -n '"'1,260p' \""'$f"; done' in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 0ms:
FILE: examples/cases/quality-anomaly/materials/memo.md
# 품질팀장 메모

3라인 불량률 튈 때마다 보고서 써왔는데, 순서는 이래:
1. MES 불량률(mes-defects csv)에서 임계치(thresholds.yaml) 넘은 교대(shift) 찾기
2. 그 시간대 센서 csv(temp, vibration)에서 임계치 넘는 구간 찾기
3. 센서 보정 로그(calibration-log) 확인 — 보정 기한 지난 센서면 그 센서 값은 "신뢰 불가"로 표시하고 원인 판정에서 빼기 (이거 안 하고 보고했다가 크게 혼남)
4. 원인 후보 정리 + 개선안. 개선안은 반드시 "품질 엔지니어 승인 필요"로 표기, 우리가 실행 지시 못 함
5. 보고서는 previous 폴더 형식. 원자료 요약 json도 같이.
FILE: examples/cases/quality-anomaly/materials/notes.txt
- 이번 건: 2026-08-27 3라인 야간 교대 불량률 급증
- 파일명: anomaly-report-<날짜>.md, anomaly-<날짜>.json
FILE: examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md
# Line 3 Quality Anomaly Report — 2026-06-14 (day shift)

## Anomaly
Defect rate 3.1% (threshold 2.5%), 4,180 units, 130 defects.

## Sensor evidence
Temperature exceeded 78 °C from 10:00 to 13:00 (peak 80.2 °C). Vibration within limits. Sensor S3-TEMP-1 calibrated 2026-05-02 (within 90 days) → trusted.

## Root cause (candidate)
Coolant flow restriction on station 3B raised die temperature.

## Remediation (requires Quality Engineer approval)
Flush coolant lines, re-run 200-unit trial. Approval: pending.
FILE: examples/cases/quality-anomaly/materials/data/thresholds.yaml
line: 3
defect_rate_pct_threshold: 2.5      # shift defect rate above this = anomaly
sensors:
  temp_c: {max: 78.0}
  vibration_mm_s: {max: 4.5}
calibration_interval_days: 90        # sensor calibration older than this = untrusted
FILE: examples/cases/quality-anomaly/materials/data/calibration-log.csv
sensor_id,measure,last_calibrated,technician
S3-TEMP-1,temp_c,2026-07-30,K. Han
S3-VIB-1,vibration_mm_s,2026-04-12,J. Cho
FILE: examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv
date,line,shift,units,defects,defect_rate_pct
2026-08-25,3,day,4200,63,1.5
2026-08-25,3,night,4100,70,1.7
2026-08-26,3,day,4250,68,1.6
2026-08-26,3,night,4050,77,1.9
2026-08-27,3,day,4300,73,1.7
2026-08-27,3,night,3900,215,5.5
FILE: examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv
timestamp,line,sensor_id,temp_c,vibration_mm_s
2026-08-27T20:00,3,S3-TEMP-1,71.2,3.1
2026-08-27T21:00,3,S3-TEMP-1,72.0,3.2
2026-08-27T22:00,3,S3-TEMP-1,79.4,3.3
2026-08-27T23:00,3,S3-TEMP-1,81.9,3.4
2026-08-28T00:00,3,S3-TEMP-1,82.5,5.1
2026-08-28T01:00,3,S3-TEMP-1,80.7,5.4
2026-08-28T02:00,3,S3-TEMP-1,76.3,4.9
2026-08-28T03:00,3,S3-TEMP-1,73.0,3.6

exec
/bin/zsh -lc "find examples -path '*/behaviors/*/BEHAVIOR.md' -type f | head -8 | xargs -I{} sh -c 'echo FILE:{}; sed -n \"1,220p\" \"{}\"'" in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 0ms:
FILE:examples/cases/refund-approval/behaviors/keep-decision-artifacts-auditable/BEHAVIOR.md
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
FILE:examples/cases/refund-approval/behaviors/apply-refund-eligibility-rules/BEHAVIOR.md
# BEHAVIOR: apply-refund-eligibility-rules

## 1. Intent
Calculate the refund amount from verified payment evidence using the exact Policy v3 age bands and duplicate exception.

## 2. Evidence
The trajectory records the matched payment date, request date, whole-day difference, duplicate flag, requested and evidenced amounts, applied clause, and calculated integer-KRW refund before approval routing.

## 3. Decision
- `true`: A verified duplicate received the evidenced duplicate amount in full regardless of age under clause 3, or a non-duplicate received 100% at 0–7 days, 50% at 8–30 days, or zero at 31+ days under the applicable clause.
- `false`: Dates, boundaries, percentages, exception precedence, or amounts differ from Policy v3, or the amount was guessed despite inconsistent evidence.
- `na`: Receipt evidence is mismatched and eligibility calculation is skipped, or the trajectory does not calculate refund eligibility.

## 4. Execution
Calculate dates and amounts deterministically from selected records; apply the verified duplicate branch before ordinary age-band selection.

## 5. Recovery
Recompute from `paid_at` and `requested_at`, reapply duplicate precedence and inclusive boundaries, and regenerate both artifacts; escalate inconsistent amounts for human review.

## 6. Failure Modes
Using order or current date, treating day 7 or 30 incorrectly, denying an old duplicate, refunding more than requested/evidenced, or rounding to non-integer KRW.
FILE:examples/cases/refund-approval/behaviors/enforce-finance-approval-threshold/BEHAVIOR.md
# BEHAVIOR: enforce-finance-approval-threshold

## 1. Intent
Prevent Customer Support from finalizing any calculated refund over 100,000 KRW.

## 2. Evidence
After refund calculation, the trajectory compares `calculated_refund_amount_krw` to 100000 and records clause 4, `pending_finance_approval`, and decision authority `finance` whenever the amount is greater than the threshold.

## 3. Decision
- `true`: Every amount over 100,000 KRW is pending Finance approval and is not described as finalized or issued; amounts at or below the threshold may be finalized by CS.
- `false`: CS finalizes or claims issuance of an over-threshold refund, or routes exactly 100,000 KRW to Finance solely because of clause 4.
- `na`: No refund amount was calculated because evidence is held, the calculated amount is zero with no approval action, or the trajectory does not make a refund decision.

## 4. Execution
Make the threshold comparison a deterministic step after eligibility calculation and before writing either output.

## 5. Recovery
Replace the unauthorized status and language with `pending_finance_approval`, authority `finance`, and an explicit statement that no refund has been finalized or issued; then revalidate both files.

## 6. Failure Modes
Comparing requested rather than calculated refund, using `>=` instead of `>`, copying finalized language from the prior memo, or implying Finance approval occurred.
FILE:examples/cases/refund-approval/behaviors/verify-receipt-before-decision/BEHAVIOR.md
# BEHAVIOR: verify-receipt-before-decision

## 1. Intent
Prevent eligibility or approval decisions from being made against an unverified receipt.

## 2. Evidence
The trajectory selects the request receipt, searches `payments.csv` for the same receipt and order, and records `receipt_match` plus the matched payment fields before any eligibility calculation or decision drafting.

## 3. Decision
- `true`: A same-order receipt match was checked first, or a missing match produced `on_hold_evidence_mismatch` with clause 5 and no refund calculation.
- `false`: Eligibility was decided before receipt verification, a different receipt was substituted, or a mismatch did not produce the required hold.
- `na`: The trajectory does not make or draft a refund decision.

## 4. Execution
Make receipt validation a non-removable predecessor to duplicate classification and refund calculation; route mismatches directly to the evidence-hold output path.

## 5. Recovery
Stop the decision, re-check the request receipt against same-order payment records, and regenerate both artifacts; if still unmatched, retain the clause 5 hold.

## 6. Failure Modes
Matching receipt alone without checking order, accepting the customer's reason as evidence, choosing a nearby receipt, or calculating a refund while evidence is held.
FILE:examples/cases/refund-approval/behaviors/prove-duplicate-from-successful-payments/BEHAVIOR.md
# BEHAVIOR: prove-duplicate-from-successful-payments

## 1. Intent
Ensure the duplicate-charge exception is granted only from payment-ledger evidence.

## 2. Evidence
The trajectory filters `payments.csv` by the request `order_id` and exact status `success`, records the resulting payment IDs and count, and derives `is_duplicate_charge` from whether the count is at least two.

## 3. Decision
- `true`: Duplicate status equals the result of counting same-order successful payments and the supporting IDs/count appear in the JSON.
- `false`: Free text, failed payments, other orders, or an unrecorded assumption established duplicate status.
- `na`: Receipt evidence is mismatched and duplicate classification is therefore skipped, or the trajectory does not make a refund decision.

## 4. Execution
Perform the successful-payment filter and count deterministically after receipt verification and before applying the duplicate exception.

## 5. Recovery
Re-read the payment ledger, exclude non-success rows and other orders, recompute the count, and regenerate downstream calculations and outputs.

## 6. Failure Modes
Trusting “charged twice” as proof, counting failed/voided payments, counting across customers or orders, or omitting payment IDs from the evidence record.
FILE:examples/cases/refund-approval/behaviors/use-authoritative-policy-v3/BEHAVIOR.md
# BEHAVIOR: use-authoritative-policy-v3

## 1. Intent
Ensure every refund decision uses the effective Refund Policy v3 as its sole rules authority rather than summaries, prior decisions, memory, or invented policy.

## 2. Evidence
The trajectory reads `examples/cases/refund-approval/materials/data/refund-policy-v3.md` before classification or calculation, records policy version `v3` and effective date `2026-04-01` in the evidence JSON, and uses the memo and previous decision only for scope or format.

## 3. Decision
- `true`: Policy v3 was read before the decision and all applied rules are traceable to it.
- `false`: The decision used an unread, legacy, summarized, remembered, or invented rule as authority.
- `na`: The trajectory does not make or draft a refund decision.

## 4. Execution
Enforce the policy read as a required predecessor to receipt validation, eligibility calculation, approval routing, and drafting.

## 5. Recovery
Discard unsupported conclusions, read Policy v3, and recompute the evidence record and memo from its clauses.

## 6. Failure Modes
Treating the manager memo as complete policy, copying the previous deliverable's outcome, using today's date for eligibility, or inventing an exception absent from Policy v3.
FILE:examples/cases/renewal-proposal/behaviors/enforce-discount-approval-cap/BEHAVIOR.md
# BEHAVIOR: enforce-discount-approval-cap

## 1. Intent
Prevent an unauthorized renewal proposal from being finalized when requested combined discounts exceed the current policy's maximum total discount.

## 2. Evidence
The trajectory records each discount and eligibility reason, the pre-cap combined percentage, the policy cap from `pricing_v2.yaml`, and `approval_required`/`approval_status` before proposal finalization; any above-cap case includes observable sales-director approval evidence or stops without a final proposal.

## 3. Decision
- `true`: The combined discount is at or below the policy cap, or an above-cap proposal is finalized only with recorded sales-director approval evidence.
- `false`: A proposal is finalized above the cap without approval, approval is invented or assumed, or discount components/cap comparison are absent.
- `na`: No discount is calculated, or the trajectory stops before an offer is proposed for reasons unrelated to the discount cap.

## 4. Execution
Evaluate the deterministic cap after all eligible discounts are assembled and before writing the final proposal. Treat missing approval evidence as not approved and halt above-cap finalization.

## 5. Recovery
Stop proposal finalization and report the requested discount and required sales-director approval; resume only when verifiable approval evidence is available or the offer is revised within the cap.

## 6. Failure Modes
Silently clipping an intended exception without disclosure; exceeding 20% without approval; claiming verbal or implied approval not present in evidence; omitting a discount component to evade the cap check.
FILE:examples/cases/renewal-proposal/behaviors/verify-active-contract/BEHAVIOR.md
# BEHAVIOR: verify-active-contract

## 1. Intent
Ensure every renewal proposal is based on exactly one current, active contract for the requested customer, never an expired or merely matching historical record.

## 2. Evidence
The trajectory shows `examples/cases/renewal-proposal/materials/data/contracts.json` being read and filtered by both the bound `customer_id` and `status == active`; it records a match count of one and the selected contract before usage calculation, pricing, or drafting.

## 3. Decision
- `true`: Exactly one active contract was selected from the contract source before recommendation, pricing, and drafting.
- `false`: Pricing or drafting used an expired, hardcoded, cached, missing, or ambiguously selected contract, or occurred before the active-contract check.
- `na`: The trajectory does not perform a customer contract renewal or contract-based pricing.

## 4. Execution
Enforce a non-removable dependency from active-contract lookup and uniqueness validation to usage recommendation, pricing, and proposal drafting.

## 5. Recovery
Stop downstream work, re-read the contract source, filter on customer and active status, and continue only after exactly one active record is established; otherwise report the missing or ambiguous contract for human resolution.

## 6. Failure Modes
Selecting the expired ACME record; matching customer ID without status; trusting the previous proposal; using contract details from memory; continuing when zero or multiple active records match.

codex
The materials settle the core design: Line 3’s 2026-08-27 night shift is the bound case; `thresholds.yaml` is the rule authority; MES establishes the anomaly; sensor evidence must be time-aligned; calibration age is evaluated as of the measurement/anomaly time; overdue measurements remain visible but cannot support causation; and every remediation stays pending Quality Engineer approval. The main ambiguity is the raw sensor layout (one row ID alongside two measures), so the specification will explicitly map calibration by `measure`, preventing vibration from inheriting the temperature sensor’s valid calibration.
apply patch
patch: completed
/Users/hongmartin/orca/projects/open-workflow/examples/cases/quality-anomaly/ASSUMPTIONS.md
/Users/hongmartin/orca/projects/open-workflow/examples/cases/quality-anomaly/TASK.md
/Users/hongmartin/orca/projects/open-workflow/examples/cases/quality-anomaly/behaviors/bound-cause-to-trusted-evidence/BEHAVIOR.md
/Users/hongmartin/orca/projects/open-workflow/examples/cases/quality-anomaly/behaviors/gate-causation-by-calibration/BEHAVIOR.md
/Users/hongmartin/orca/projects/open-workflow/examples/cases/quality-anomaly/behaviors/keep-report-evidence-auditable/BEHAVIOR.md
/Users/hongmartin/orca/projects/open-workflow/examples/cases/quality-anomaly/behaviors/require-quality-engineer-approval/BEHAVIOR.md
/Users/hongmartin/orca/projects/open-workflow/examples/cases/quality-anomaly/behaviors/use-authoritative-thresholds/BEHAVIOR.md
/Users/hongmartin/orca/projects/open-workflow/examples/cases/quality-anomaly/behaviors/verify-bound-mes-anomaly/BEHAVIOR.md
diff --git a/examples/cases/quality-anomaly/ASSUMPTIONS.md b/examples/cases/quality-anomaly/ASSUMPTIONS.md
new file mode 100644
index 0000000000000000000000000000000000000000..c7528a7d3de8b799f02939fcb4e7e71c5480872b
--- /dev/null
+++ b/examples/cases/quality-anomaly/ASSUMPTIONS.md
@@ -0,0 +1,95 @@
+# Assumptions: manufacturing line quality anomaly response reports
+
+The requester was unavailable for an interactive interview. Each grilling round below therefore records the frontier questions, the recommended answer adopted from the supplied materials, and why it was chosen. These are reviewable assumptions, not new source facts; the requester can correct them before the first run.
+
+## Round 1 — Outcome and scope
+
+1. **What is the single-sentence goal, and who consumes the result?**
+   - **Chosen answer:** Produce an auditable Line 3 quality-anomaly response report and structured evidence summary for the Quality Engineer, so they can review a detected shift-level defect spike, its trustworthy sensor evidence, candidate cause, and proposed remediation.
+   - **Why:** `materials/memo.md` describes the recurring report, requires Quality Engineer approval for improvements, and says both a report and raw-data summary JSON are required. The prior report is written for operational quality review.
+
+2. **Which incident is in scope for this run?**
+   - **Chosen answer:** **2026-08-27**, **Line 3**, **night shift** only.
+   - **Why:** `materials/notes.txt` names exactly this incident. No other line or shift was requested.
+
+3. **Should the task scan for all anomalies or merely assume the noted incident is anomalous?**
+   - **Chosen answer:** Bind the run to the noted line/date/shift, but independently verify that it exceeds the authoritative defect-rate threshold; do not report unrelated shifts.
+   - **Why:** The memo's first required step is to find shifts exceeding the threshold, while the notes identify “this case.” This preserves verification without broadening the deliverable.
+
+4. **What language and presentation style should the deliverable use?**
+   - **Chosen answer:** Use English and follow the headings and concise operational style of `materials/previous/anomaly-report-2026-06-14.md`.
+   - **Why:** The memo is Korean, but the repository and prior finished deliverable are English. The project instructions require English artifacts.
+
+## Round 2 — Inputs, authority, and boundaries
+
+5. **Which files are authoritative for facts and rules?**
+   - **Chosen answer:** Use `materials/data/thresholds.yaml` for thresholds and calibration interval, `materials/data/mes-defects-2026-08.csv` for shift production/defect facts, `materials/data/sensor-2026-08-27.csv` for measurements, and `materials/data/calibration-log.csv` for calibration status. Use `materials/memo.md` and `materials/notes.txt` for process/scope, and the prior report only for format.
+   - **Why:** These roles are stated directly in the memo and reflected by the file contents. The previous report is an example, not evidence for this incident.
+
+6. **Which values should be treated as per-run parameters?**
+   - **Chosen answer:** `incident_date=2026-08-27`, `line=3`, `shift=night`, the four input paths, and `output_dir=build/quality-anomaly/` are explicit run bindings. A future run may replace them.
+   - **Why:** The notes bind the first three values, while the requested task paths bind the inputs and output location. Making them explicit supports later parameter discovery.
+
+7. **What time window defines the night shift?**
+   - **Chosen answer:** Use all sensor rows supplied for the bound incident and line, spanning `2026-08-27T20:00` through `2026-08-28T03:00` inclusive; record this observed window in JSON rather than inventing a corporate shift schedule.
+   - **Why:** The sensor file contains exactly that continuous overnight window and the MES record labels the incident “night.” No formal shift timetable was supplied.
+
+8. **How is the strict threshold boundary interpreted?**
+   - **Chosen answer:** A value is anomalous only when it is strictly greater than the configured maximum (`>`), not equal to it.
+   - **Why:** `thresholds.yaml` says “above this = anomaly,” and the memo says “넘은” (exceeded).
+
+9. **At what date is calibration age evaluated, and how is expiry handled?**
+   - **Chosen answer:** Evaluate each measure's calibration age at the timestamp of each relevant measurement; it is trusted when age is at most 90 whole days and untrusted when older than 90 days. Record the dates and computed ages.
+   - **Why:** The memo says an overdue sensor must be marked untrustworthy and excluded from causal judgment. Incident-time evaluation avoids using the later workflow execution date. The “older than” wording makes day 90 inclusive/trusted.
+
+10. **How should calibration records map to a sensor CSV that has one `sensor_id` but both temperature and vibration columns?**
+    - **Chosen answer:** Map calibration status by the `measure` field: `temp_c` to the calibration row for `temp_c`, and `vibration_mm_s` to the row for `vibration_mm_s`. Preserve both calibration sensor IDs in JSON. Do not apply `S3-TEMP-1` calibration to vibration merely because it appears in the sensor row.
+    - **Why:** `calibration-log.csv` has distinct sensor IDs per measure, while every sensor-data row is labeled `S3-TEMP-1` despite carrying both values. Measure-based mapping is the only interpretation consistent with the calibration log and the memo's per-sensor trust rule.
+
+## Round 3 — Analysis and judgment
+
+11. **What is the ordered process, and which parts are mechanical versus judgment?**
+    - **Chosen answer:** Mechanically load bindings and thresholds; select and verify the MES row; filter the observed sensor window; find strict exceedances and contiguous intervals; join calibration by measure and compute trust; serialize JSON; then use judgment only to phrase a bounded candidate cause and approval-gated remediation from trustworthy evidence; render Markdown from JSON and validate consistency.
+    - **Why:** This follows the memo's five-step order and makes calculations reproducible while isolating the genuinely interpretive steps.
+
+12. **May an overdue sensor's exceedance appear in the report?**
+    - **Chosen answer:** Yes, disclose its observed values and exceedance interval, label it exactly **“untrusted”**, state why, and exclude it from causal support.
+    - **Why:** The memo requires overdue sensor values to be marked “신뢰 불가” (untrusted) and removed from causal determination—not silently discarded.
+
+13. **How strong may the root-cause claim be?**
+    - **Chosen answer:** Label it a **candidate**, tie it only to trusted evidence, distinguish correlation from confirmation, and do not name a specific failed component unless the supplied evidence identifies one.
+    - **Why:** The memo asks for cause candidates, and the prior report labels the section “Root cause (candidate).” The current files contain measurements, not inspection evidence proving a component failure.
+
+14. **What remediation may be proposed?**
+    - **Chosen answer:** Recommend investigation/containment steps proportionate to the trusted evidence (for example, inspect the thermal process and run a controlled verification trial), plus recalibration/verification of any overdue sensor; every action must say **“requires Quality Engineer approval”** and remain pending.
+    - **Why:** The memo forbids execution instructions without Quality Engineer approval. The evidence supports investigation, not autonomous maintenance action.
+
+15. **What happens if the MES row does not exceed the threshold, inputs are missing/ambiguous, or no trustworthy causal evidence remains?**
+    - **Chosen answer:** Stop normal report finalization and surface the condition for human review. If the anomaly is verified but causal evidence is insufficient, the report may still be produced, but the cause must be `undetermined` and remediation limited to approval-gated investigation/data recovery.
+    - **Why:** Inventing a cause or silently selecting ambiguous evidence would violate the memo's trust rule. A verified quality event still needs a response report even when causation is unresolved.
+
+## Round 4 — Deliverables, completeness, and failure checks
+
+16. **What exact files must be produced?**
+    - **Chosen answer:** `build/quality-anomaly/anomaly-2026-08-27.json` first, then `build/quality-anomaly/anomaly-report-2026-08-27.md` rendered from it. No source materials are modified.
+    - **Why:** `materials/notes.txt` specifies both filename patterns, and the requester requires outputs under `build/quality-anomaly/`.
+
+17. **What must the JSON contain?**
+    - **Chosen answer:** Run bindings and source paths; threshold values; selected MES row and anomaly verdict; sensor window; per-measure exceedance timestamps/intervals/peaks; calibration ID/date/age/status; whether each measure is eligible for causal use; candidate-cause statement with supporting trusted measures and limitations; approval-gated remediation items; and validation status.
+    - **Why:** This is the minimum structured evidence needed to audit every memo-required decision and keep the Markdown traceable to raw data.
+
+18. **What must the Markdown contain?**
+    - **Chosen answer:** The prior report's sections—title, `Anomaly`, `Sensor evidence`, `Root cause (candidate)`, and `Remediation (requires Quality Engineer approval)`—with source-grounded values, explicit trust labels, causal limitations, and approval status `pending`.
+    - **Why:** The memo explicitly requires the previous-folder format, and the previous deliverable supplies these headings and approval wording.
+
+19. **What exact acceptance checks define done?**
+    - **Chosen answer:** Both files exist and parse; filenames match the bound incident date; all reported numeric facts reproduce from the selected rows and configured thresholds; strict boundaries and contiguous intervals are correct; calibration is evaluated by measure at incident time; untrusted measures never support the cause; remediation explicitly requires Quality Engineer approval and remains pending; Markdown and JSON agree; only the requested incident is reported.
+    - **Why:** These checks cover the requested output, all memo rules, and the main data trap.
+
+20. **Which known or feared failure modes require explicit prevention?**
+    - **Chosen answer:** Using the prior report as incident evidence; trusting vibration under the temperature sensor ID; evaluating calibration at execution time; hiding or causally using overdue sensor values; treating equality as exceedance; inventing shift boundaries, component failures, or approvals; issuing remediation as an order; mismatching JSON/Markdown; and processing unrelated shifts.
+    - **Why:** The memo identifies missed calibration as a serious prior failure. The remaining risks follow directly from the supplied schemas, example, and requested dual outputs.
+
+## Deferred confirmations
+
+Before generalizing this workflow beyond the supplied fixture, the requester should confirm the official shift schedule, whether calibration validity is day- or timestamp-granular, the canonical JSON schema, and the organization-approved remediation vocabulary. None of these unknowns prevents a bounded first run under the assumptions above.
diff --git a/examples/cases/quality-anomaly/TASK.md b/examples/cases/quality-anomaly/TASK.md
new file mode 100644
index 0000000000000000000000000000000000000000..376b342e282524fabf4de36e67e46f0c8de11ed1
--- /dev/null
+++ b/examples/cases/quality-anomaly/TASK.md
@@ -0,0 +1,21 @@
+# Task: Line 3 quality anomaly response report for 2026-08-27 night shift
+
+You are the manufacturing quality-analysis assistant. Prepare the auditable anomaly evidence summary and response report for **incident_date=2026-08-27**, **line=3**, **shift=night** for review by the Quality Engineer.
+
+Rules (from `behaviors/`): use the supplied thresholds as the sole numeric rule authority; independently verify the bound MES anomaly before analysis; align sensor evidence only to the bound line and supplied overnight incident window; evaluate calibration by measure at measurement time and never use an overdue sensor to support causation; make only evidence-bounded candidate-cause claims; and leave every remediation pending with the exact statement **“requires Quality Engineer approval”**. Use `examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md` only as a format example, never as evidence. Assumptions adopted while the requester was unavailable are recorded in `examples/cases/quality-anomaly/ASSUMPTIONS.md`.
+
+Do the work with auditable shell commands (`cat`, `mkdir -p`, and `python3` using CSV/YAML/date/JSON handling) from the repository root. Do not modify anything under `examples/cases/quality-anomaly/materials/`.
+
+1. **Bind the run and inspect authority files** — set and print the per-run bindings **incident_date=2026-08-27**, **line=3**, **shift=night**, **MES=examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv**, **SENSORS=examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv**, **CALIBRATION=examples/cases/quality-anomaly/materials/data/calibration-log.csv**, **THRESHOLDS=examples/cases/quality-anomaly/materials/data/thresholds.yaml**, and **OUTPUT_DIR=build/quality-anomaly**. Read `examples/cases/quality-anomaly/materials/memo.md`, `examples/cases/quality-anomaly/materials/notes.txt`, the four data files, and `examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md`. Create `build/quality-anomaly/` with `mkdir -p`.
+2. **Verify the MES anomaly mechanically** — with `python3`, parse `examples/cases/quality-anomaly/materials/data/thresholds.yaml` and `examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv`; filter by all three bound keys (`date`, integer `line`, and `shift`); require exactly one row; recompute `100 * defects / units` and verify it agrees with `defect_rate_pct` within 0.05 percentage point; classify an anomaly only when the recorded rate is strictly greater than `defect_rate_pct_threshold`. Print the selected row, recomputed rate, threshold, and verdict. Stop without finalizing either deliverable if the row is missing/ambiguous, internally inconsistent, or not anomalous.
+3. **Extract time-aligned sensor exceedances mechanically** — with `python3`, parse `examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv`; keep only integer `line == 3` and the supplied continuous overnight rows from **2026-08-27T20:00 through 2026-08-28T03:00 inclusive**. Do not infer a broader corporate shift schedule. For `temp_c` and `vibration_mm_s`, compare each value strictly (`>`) with its configured maximum, record every exceedance timestamp/value, group consecutive hourly exceedances into inclusive intervals, and record each peak and peak timestamp. Print the filtered window and derived exceedances.
+4. **Gate evidence by calibration mechanically** — with `python3`, parse `examples/cases/quality-anomaly/materials/data/calibration-log.csv` and join each measure to the unique calibration row whose `measure` matches (`temp_c` or `vibration_mm_s`), regardless of the row-level `sensor_id` in the sensor CSV. At every relevant measurement timestamp, compute whole elapsed days since `last_calibrated`; classify the measure `trusted` when age is at most `calibration_interval_days` and `untrusted` when older. Record the calibration sensor ID, date, ages, status, and `eligible_for_causal_use`. An untrusted measure's observed exceedances must remain disclosed but must not enter causal support. Stop for human review if a measure has zero/multiple calibration records, a future calibration date, or inconsistent trust status across its relevant interval.
+5. **Write the structured evidence first** — create `build/quality-anomaly/anomaly-2026-08-27.json` containing: `incident` (`date`, `line`, `shift`, `observed_sensor_window`); `sources` (all input paths); `thresholds`; `mes` (selected row, recomputed rate, and `is_anomaly`); `sensor_evidence` keyed by measure (unit, maximum, exceedance samples, contiguous intervals, peak, calibration record/ages/status, and `eligible_for_causal_use`); `candidate_root_cause` (`status`, `statement`, `supporting_trusted_measures`, and `limitations`); `remediation` as a list of items each with `action`, `approval_required: true`, `approval_authority: "Quality Engineer"`, and `approval_status: "pending"`; and `validation`. The cause must be `undetermined` if no trustworthy evidence supports a bounded candidate. Do not assert a specific failed component without supplied evidence.
+6. **Render the response report from the JSON** — write `build/quality-anomaly/anomaly-report-2026-08-27.md` in the concise English format of `examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md`, using exactly these sections: title, `## Anomaly`, `## Sensor evidence`, `## Root cause (candidate)`, and `## Remediation (requires Quality Engineer approval)`. Include the selected production facts and threshold; each measure's exceedance interval/peak and calibration trust basis; explicit `untrusted` wording and exclusion from causal judgment where applicable; a correlation-bounded candidate or `undetermined`; and `Approval: pending`. Every remediation item must include the exact statement **“requires Quality Engineer approval”** and must not claim execution or approval.
+7. **Validate both artifacts mechanically** — parse the JSON with `python3 -m json.tool`; use `python3` to recompute the selected MES result, exceedance samples/intervals/peaks, calibration ages/statuses, and causal eligibility directly from the four data files; compare them with JSON; then verify that every material numeric fact, trust label, candidate-cause limitation, remediation action, approval authority/status, and source incident in Markdown agrees with JSON. Confirm that no untrusted measure appears in `supporting_trusted_measures`, no unrelated shift appears, and both filenames match **2026-08-27**. Set `validation.status` to `passed` only after all checks pass and re-run `python3 -m json.tool` after the update.
+8. **Do not perform remediation** — this task produces analysis artifacts only. Do not contact people, change manufacturing systems, issue work orders, recalibrate sensors, or state that any approval or action occurred.
+
+Reply with a short summary containing the verified incident and defect-rate verdict, which measures were trusted/untrusted, the candidate-cause status, the pending Quality Engineer approval status, and these two paths:
+
+- `build/quality-anomaly/anomaly-2026-08-27.json`
+- `build/quality-anomaly/anomaly-report-2026-08-27.md`
diff --git a/examples/cases/quality-anomaly/behaviors/bound-cause-to-trusted-evidence/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/bound-cause-to-trusted-evidence/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..ed9973689f0ea16d8ff850a90eb9ca7c90b9ee14
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/bound-cause-to-trusted-evidence/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: bound-cause-to-trusted-evidence
+
+## 1. Intent
+Keep root-cause language proportional to the supplied evidence and distinguish a correlated candidate from a confirmed equipment failure.
+
+## 2. Evidence
+The structured evidence records a candidate status, statement, explicit supporting trusted measures, and limitations after calibration gating; the report renders the same bounded claim under `Root cause (candidate)`.
+
+## 3. Decision
+- `true`: The cause is labeled a candidate, cites only trusted supporting measures, states material limitations, and becomes `undetermined` when no trustworthy causal evidence remains.
+- `false`: A cause is presented as confirmed, an unsupported component failure is named, an untrusted measure supplies support, or uncertainty is omitted.
+- `na`: The trajectory makes no causal assessment.
+
+## 4. Execution
+Draft the causal assessment only after MES verification, time alignment, exceedance calculation, and calibration gating; separate observed correlation from confirmation.
+
+## 5. Recovery
+Downgrade unsupported certainty, remove untrusted or absent support, add the evidence limitation, or set the cause to `undetermined`; regenerate both artifacts and revalidate them.
+
+## 6. Failure Modes
+Copying the coolant diagnosis from the previous report, equating threshold coincidence with proof, inventing a failed station/component, or masking insufficient evidence with confident prose.
diff --git a/examples/cases/quality-anomaly/behaviors/gate-causation-by-calibration/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/gate-causation-by-calibration/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..7d6687d35695584d296763add90d4fc6bb413d0a
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/gate-causation-by-calibration/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: gate-causation-by-calibration
+
+## 1. Intent
+Prevent expired or mismapped sensor calibration from supporting a root-cause candidate while keeping observed evidence transparent.
+
+## 2. Evidence
+The trajectory joins each analyzed measure to the unique `measure` row in `examples/cases/quality-anomaly/materials/data/calibration-log.csv`, computes elapsed whole days at relevant measurement timestamps using the configured interval, records the calibration sensor ID/date/ages and trust verdict, and records causal eligibility before drafting a cause.
+
+## 3. Decision
+- `true`: Every measure is mapped by measure, age is evaluated at measurement time, values older than the allowed interval are labeled `untrusted` and disclosed but absent from causal support, and only trusted measures support the candidate cause.
+- `false`: Calibration is skipped, evaluated at workflow execution time, mapped from the sensor row ID across measures, expired evidence is hidden, or an untrusted measure supports causation.
+- `na`: No sensor evidence is analyzed or no causal assessment is made.
+
+## 4. Execution
+Perform the calibration join and trust calculation after time-aligned exceedance extraction and before candidate-cause judgment; fail closed on missing, duplicate, future-dated, or inconsistent calibration evidence.
+
+## 5. Recovery
+Remove unsupported causal claims, remap calibration records by measure, recompute incident-time ages and trust, then regenerate the structured evidence and report; escalate unresolved calibration ambiguity for human review.
+
+## 6. Failure Modes
+Treating the row-level temperature sensor ID as vibration calibration, using today's date, treating day 90 as expired, silently dropping overdue readings, or describing untrusted vibration as causal.
diff --git a/examples/cases/quality-anomaly/behaviors/keep-report-evidence-auditable/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/keep-report-evidence-auditable/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..0b418a50e3aeea4b28fe8742f4f7b850a13a5771
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/keep-report-evidence-auditable/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: keep-report-evidence-auditable
+
+## 1. Intent
+Produce mutually consistent structured and human-readable anomaly artifacts whose facts can be reproduced from the supplied incident sources.
+
+## 2. Evidence
+The trajectory writes `build/quality-anomaly/anomaly-2026-08-27.json` before rendering `build/quality-anomaly/anomaly-report-2026-08-27.md`, records all source paths and derivations, parses the JSON, and mechanically compares MES facts, sensor intervals/peaks, calibration trust, causal support, remediation, and approval status across sources and outputs.
+
+## 3. Decision
+- `true`: Both incident-dated files exist, parse, concern only the bound incident, reproduce the source calculations, agree on every material fact and decision, and record a passed validation.
+- `false`: A file is missing or malformed, prose is drafted from memory, the files disagree, sources/derivations are absent, unrelated shifts appear, or validation passes despite a mismatch.
+- `na`: The trajectory does not produce the anomaly JSON and report pair.
+
+## 4. Execution
+Serialize source-derived structured evidence first, render the report from it in the previous deliverable's section format, then run source-to-JSON and JSON-to-Markdown consistency checks before replying.
+
+## 5. Recovery
+Treat freshly recomputed source evidence as authoritative, correct or regenerate the JSON, re-render Markdown, and repeat all validations without modifying source materials or performing remediation.
+
+## 6. Failure Modes
+Drafting prose first and backfilling JSON, copying prior-incident values, mismatched dates/rates/peaks/trust labels, omitting limitations or approval status, or declaring success before mechanical validation.
diff --git a/examples/cases/quality-anomaly/behaviors/require-quality-engineer-approval/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/require-quality-engineer-approval/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..94735f4fcc72cad618089dcb026e0ec3cf39ae25
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/require-quality-engineer-approval/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: require-quality-engineer-approval
+
+## 1. Intent
+Prevent the analysis assistant from authorizing or claiming execution of manufacturing remediation.
+
+## 2. Evidence
+Every structured remediation item records `approval_required: true`, `approval_authority: "Quality Engineer"`, and `approval_status: "pending"`; the report section and each action include “requires Quality Engineer approval,” and the trajectory performs no external operational action.
+
+## 3. Decision
+- `true`: All remediation remains a proposal pending Quality Engineer approval, the required statement is explicit for every action, and no approval or execution is invented.
+- `false`: Any action is issued as an order, marked approved/completed without evidence, omits the required approval statement, or is actually performed by the workflow.
+- `na`: The trajectory neither proposes nor performs manufacturing remediation.
+
+## 4. Execution
+Apply the approval gate while serializing each remediation item and preserve it verbatim when rendering Markdown; restrict the workflow to artifact creation.
+
+## 5. Recovery
+Stop any attempted operational step, change unauthorized language and statuses to pending proposals, add the required approval statement to every item, and regenerate and revalidate both artifacts.
+
+## 6. Failure Modes
+Copying imperative maintenance language, treating report generation as authorization, claiming verbal or assumed approval, contacting operations, changing equipment, or omitting approval from one of several actions.
diff --git a/examples/cases/quality-anomaly/behaviors/use-authoritative-thresholds/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/use-authoritative-thresholds/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..8e32cc42328707d5ee24d0963590ef9dee1e9421
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/use-authoritative-thresholds/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: use-authoritative-thresholds
+
+## 1. Intent
+Ensure anomaly, sensor, and calibration decisions use the supplied current threshold configuration rather than memory, the previous report, or invented limits.
+
+## 2. Evidence
+The trajectory reads `examples/cases/quality-anomaly/materials/data/thresholds.yaml` before classification and records its line, defect-rate threshold, per-measure maxima, calibration interval, and source path in the structured evidence.
+
+## 3. Decision
+- `true`: Every threshold and calibration interval used in the artifacts matches the read configuration, and strict exceedance is applied.
+- `false`: A limit is hardcoded, remembered, copied from the prior report, invented, or interpreted as inclusive despite the configuration's “above” rule.
+- `na`: The trajectory does not classify a manufacturing quality anomaly or sensor evidence.
+
+## 4. Execution
+Make the threshold-file read a required predecessor to MES classification, sensor comparison, calibration gating, and drafting.
+
+## 5. Recovery
+Discard derived classifications, re-read the threshold file, recompute all dependent evidence, and regenerate both artifacts.
+
+## 6. Failure Modes
+Using 3.1% or 80.2 °C from the prior report, treating equality as exceedance, applying a limit to the wrong measure, or using an undocumented calibration interval.
diff --git a/examples/cases/quality-anomaly/behaviors/verify-bound-mes-anomaly/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/verify-bound-mes-anomaly/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..08b18f1660f90ef47535da4d4c89dd201a5155ef
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/verify-bound-mes-anomaly/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: verify-bound-mes-anomaly
+
+## 1. Intent
+Prevent a response report from being finalized for an unverified, wrong, ambiguous, or internally inconsistent shift record.
+
+## 2. Evidence
+The trajectory filters `examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv` by the bound date, line, and shift; records a match count of one; recomputes the defect rate from units and defects; and compares the recorded rate strictly with the configured threshold before sensor analysis.
+
+## 3. Decision
+- `true`: Exactly one bound MES row is selected, its recorded and recomputed rates agree within 0.05 percentage point, and the rate is strictly above the configured threshold before downstream analysis proceeds.
+- `false`: The wrong or multiple shifts are used, the rate is assumed from notes, inconsistent counts are ignored, or a non-anomalous shift receives a finalized anomaly report.
+- `na`: The trajectory does not produce a shift-level quality-anomaly response.
+
+## 4. Execution
+Make bound-key selection, uniqueness, rate reproduction, and threshold classification non-removable predecessors to sensor analysis and artifact creation.
+
+## 5. Recovery
+Stop downstream work, re-read the MES and threshold sources, reselect by all bound keys, and continue only when a unique, consistent, above-threshold row is established; otherwise report the evidence problem for human review.
+
+## 6. Failure Modes
+Scanning and reporting unrelated shifts, matching date without line/shift, trusting a precomputed rate despite inconsistent counts, or using `>=` instead of `>`.

diff --git a/examples/cases/quality-anomaly/ASSUMPTIONS.md b/examples/cases/quality-anomaly/ASSUMPTIONS.md
new file mode 100644
index 0000000000000000000000000000000000000000..c7528a7d3de8b799f02939fcb4e7e71c5480872b
--- /dev/null
+++ b/examples/cases/quality-anomaly/ASSUMPTIONS.md
@@ -0,0 +1,95 @@
+# Assumptions: manufacturing line quality anomaly response reports
+
+The requester was unavailable for an interactive interview. Each grilling round below therefore records the frontier questions, the recommended answer adopted from the supplied materials, and why it was chosen. These are reviewable assumptions, not new source facts; the requester can correct them before the first run.
+
+## Round 1 — Outcome and scope
+
+1. **What is the single-sentence goal, and who consumes the result?**
+   - **Chosen answer:** Produce an auditable Line 3 quality-anomaly response report and structured evidence summary for the Quality Engineer, so they can review a detected shift-level defect spike, its trustworthy sensor evidence, candidate cause, and proposed remediation.
+   - **Why:** `materials/memo.md` describes the recurring report, requires Quality Engineer approval for improvements, and says both a report and raw-data summary JSON are required. The prior report is written for operational quality review.
+
+2. **Which incident is in scope for this run?**
+   - **Chosen answer:** **2026-08-27**, **Line 3**, **night shift** only.
+   - **Why:** `materials/notes.txt` names exactly this incident. No other line or shift was requested.
+
+3. **Should the task scan for all anomalies or merely assume the noted incident is anomalous?**
+   - **Chosen answer:** Bind the run to the noted line/date/shift, but independently verify that it exceeds the authoritative defect-rate threshold; do not report unrelated shifts.
+   - **Why:** The memo's first required step is to find shifts exceeding the threshold, while the notes identify “this case.” This preserves verification without broadening the deliverable.
+
+4. **What language and presentation style should the deliverable use?**
+   - **Chosen answer:** Use English and follow the headings and concise operational style of `materials/previous/anomaly-report-2026-06-14.md`.
+   - **Why:** The memo is Korean, but the repository and prior finished deliverable are English. The project instructions require English artifacts.
+
+## Round 2 — Inputs, authority, and boundaries
+
+5. **Which files are authoritative for facts and rules?**
+   - **Chosen answer:** Use `materials/data/thresholds.yaml` for thresholds and calibration interval, `materials/data/mes-defects-2026-08.csv` for shift production/defect facts, `materials/data/sensor-2026-08-27.csv` for measurements, and `materials/data/calibration-log.csv` for calibration status. Use `materials/memo.md` and `materials/notes.txt` for process/scope, and the prior report only for format.
+   - **Why:** These roles are stated directly in the memo and reflected by the file contents. The previous report is an example, not evidence for this incident.
+
+6. **Which values should be treated as per-run parameters?**
+   - **Chosen answer:** `incident_date=2026-08-27`, `line=3`, `shift=night`, the four input paths, and `output_dir=build/quality-anomaly/` are explicit run bindings. A future run may replace them.
+   - **Why:** The notes bind the first three values, while the requested task paths bind the inputs and output location. Making them explicit supports later parameter discovery.
+
+7. **What time window defines the night shift?**
+   - **Chosen answer:** Use all sensor rows supplied for the bound incident and line, spanning `2026-08-27T20:00` through `2026-08-28T03:00` inclusive; record this observed window in JSON rather than inventing a corporate shift schedule.
+   - **Why:** The sensor file contains exactly that continuous overnight window and the MES record labels the incident “night.” No formal shift timetable was supplied.
+
+8. **How is the strict threshold boundary interpreted?**
+   - **Chosen answer:** A value is anomalous only when it is strictly greater than the configured maximum (`>`), not equal to it.
+   - **Why:** `thresholds.yaml` says “above this = anomaly,” and the memo says “넘은” (exceeded).
+
+9. **At what date is calibration age evaluated, and how is expiry handled?**
+   - **Chosen answer:** Evaluate each measure's calibration age at the timestamp of each relevant measurement; it is trusted when age is at most 90 whole days and untrusted when older than 90 days. Record the dates and computed ages.
+   - **Why:** The memo says an overdue sensor must be marked untrustworthy and excluded from causal judgment. Incident-time evaluation avoids using the later workflow execution date. The “older than” wording makes day 90 inclusive/trusted.
+
+10. **How should calibration records map to a sensor CSV that has one `sensor_id` but both temperature and vibration columns?**
+    - **Chosen answer:** Map calibration status by the `measure` field: `temp_c` to the calibration row for `temp_c`, and `vibration_mm_s` to the row for `vibration_mm_s`. Preserve both calibration sensor IDs in JSON. Do not apply `S3-TEMP-1` calibration to vibration merely because it appears in the sensor row.
+    - **Why:** `calibration-log.csv` has distinct sensor IDs per measure, while every sensor-data row is labeled `S3-TEMP-1` despite carrying both values. Measure-based mapping is the only interpretation consistent with the calibration log and the memo's per-sensor trust rule.
+
+## Round 3 — Analysis and judgment
+
+11. **What is the ordered process, and which parts are mechanical versus judgment?**
+    - **Chosen answer:** Mechanically load bindings and thresholds; select and verify the MES row; filter the observed sensor window; find strict exceedances and contiguous intervals; join calibration by measure and compute trust; serialize JSON; then use judgment only to phrase a bounded candidate cause and approval-gated remediation from trustworthy evidence; render Markdown from JSON and validate consistency.
+    - **Why:** This follows the memo's five-step order and makes calculations reproducible while isolating the genuinely interpretive steps.
+
+12. **May an overdue sensor's exceedance appear in the report?**
+    - **Chosen answer:** Yes, disclose its observed values and exceedance interval, label it exactly **“untrusted”**, state why, and exclude it from causal support.
+    - **Why:** The memo requires overdue sensor values to be marked “신뢰 불가” (untrusted) and removed from causal determination—not silently discarded.
+
+13. **How strong may the root-cause claim be?**
+    - **Chosen answer:** Label it a **candidate**, tie it only to trusted evidence, distinguish correlation from confirmation, and do not name a specific failed component unless the supplied evidence identifies one.
+    - **Why:** The memo asks for cause candidates, and the prior report labels the section “Root cause (candidate).” The current files contain measurements, not inspection evidence proving a component failure.
+
+14. **What remediation may be proposed?**
+    - **Chosen answer:** Recommend investigation/containment steps proportionate to the trusted evidence (for example, inspect the thermal process and run a controlled verification trial), plus recalibration/verification of any overdue sensor; every action must say **“requires Quality Engineer approval”** and remain pending.
+    - **Why:** The memo forbids execution instructions without Quality Engineer approval. The evidence supports investigation, not autonomous maintenance action.
+
+15. **What happens if the MES row does not exceed the threshold, inputs are missing/ambiguous, or no trustworthy causal evidence remains?**
+    - **Chosen answer:** Stop normal report finalization and surface the condition for human review. If the anomaly is verified but causal evidence is insufficient, the report may still be produced, but the cause must be `undetermined` and remediation limited to approval-gated investigation/data recovery.
+    - **Why:** Inventing a cause or silently selecting ambiguous evidence would violate the memo's trust rule. A verified quality event still needs a response report even when causation is unresolved.
+
+## Round 4 — Deliverables, completeness, and failure checks
+
+16. **What exact files must be produced?**
+    - **Chosen answer:** `build/quality-anomaly/anomaly-2026-08-27.json` first, then `build/quality-anomaly/anomaly-report-2026-08-27.md` rendered from it. No source materials are modified.
+    - **Why:** `materials/notes.txt` specifies both filename patterns, and the requester requires outputs under `build/quality-anomaly/`.
+
+17. **What must the JSON contain?**
+    - **Chosen answer:** Run bindings and source paths; threshold values; selected MES row and anomaly verdict; sensor window; per-measure exceedance timestamps/intervals/peaks; calibration ID/date/age/status; whether each measure is eligible for causal use; candidate-cause statement with supporting trusted measures and limitations; approval-gated remediation items; and validation status.
+    - **Why:** This is the minimum structured evidence needed to audit every memo-required decision and keep the Markdown traceable to raw data.
+
+18. **What must the Markdown contain?**
+    - **Chosen answer:** The prior report's sections—title, `Anomaly`, `Sensor evidence`, `Root cause (candidate)`, and `Remediation (requires Quality Engineer approval)`—with source-grounded values, explicit trust labels, causal limitations, and approval status `pending`.
+    - **Why:** The memo explicitly requires the previous-folder format, and the previous deliverable supplies these headings and approval wording.
+
+19. **What exact acceptance checks define done?**
+    - **Chosen answer:** Both files exist and parse; filenames match the bound incident date; all reported numeric facts reproduce from the selected rows and configured thresholds; strict boundaries and contiguous intervals are correct; calibration is evaluated by measure at incident time; untrusted measures never support the cause; remediation explicitly requires Quality Engineer approval and remains pending; Markdown and JSON agree; only the requested incident is reported.
+    - **Why:** These checks cover the requested output, all memo rules, and the main data trap.
+
+20. **Which known or feared failure modes require explicit prevention?**
+    - **Chosen answer:** Using the prior report as incident evidence; trusting vibration under the temperature sensor ID; evaluating calibration at execution time; hiding or causally using overdue sensor values; treating equality as exceedance; inventing shift boundaries, component failures, or approvals; issuing remediation as an order; mismatching JSON/Markdown; and processing unrelated shifts.
+    - **Why:** The memo identifies missed calibration as a serious prior failure. The remaining risks follow directly from the supplied schemas, example, and requested dual outputs.
+
+## Deferred confirmations
+
+Before generalizing this workflow beyond the supplied fixture, the requester should confirm the official shift schedule, whether calibration validity is day- or timestamp-granular, the canonical JSON schema, and the organization-approved remediation vocabulary. None of these unknowns prevents a bounded first run under the assumptions above.
diff --git a/examples/cases/quality-anomaly/TASK.md b/examples/cases/quality-anomaly/TASK.md
new file mode 100644
index 0000000000000000000000000000000000000000..376b342e282524fabf4de36e67e46f0c8de11ed1
--- /dev/null
+++ b/examples/cases/quality-anomaly/TASK.md
@@ -0,0 +1,21 @@
+# Task: Line 3 quality anomaly response report for 2026-08-27 night shift
+
+You are the manufacturing quality-analysis assistant. Prepare the auditable anomaly evidence summary and response report for **incident_date=2026-08-27**, **line=3**, **shift=night** for review by the Quality Engineer.
+
+Rules (from `behaviors/`): use the supplied thresholds as the sole numeric rule authority; independently verify the bound MES anomaly before analysis; align sensor evidence only to the bound line and supplied overnight incident window; evaluate calibration by measure at measurement time and never use an overdue sensor to support causation; make only evidence-bounded candidate-cause claims; and leave every remediation pending with the exact statement **“requires Quality Engineer approval”**. Use `examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md` only as a format example, never as evidence. Assumptions adopted while the requester was unavailable are recorded in `examples/cases/quality-anomaly/ASSUMPTIONS.md`.
+
+Do the work with auditable shell commands (`cat`, `mkdir -p`, and `python3` using CSV/YAML/date/JSON handling) from the repository root. Do not modify anything under `examples/cases/quality-anomaly/materials/`.
+
+1. **Bind the run and inspect authority files** — set and print the per-run bindings **incident_date=2026-08-27**, **line=3**, **shift=night**, **MES=examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv**, **SENSORS=examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv**, **CALIBRATION=examples/cases/quality-anomaly/materials/data/calibration-log.csv**, **THRESHOLDS=examples/cases/quality-anomaly/materials/data/thresholds.yaml**, and **OUTPUT_DIR=build/quality-anomaly**. Read `examples/cases/quality-anomaly/materials/memo.md`, `examples/cases/quality-anomaly/materials/notes.txt`, the four data files, and `examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md`. Create `build/quality-anomaly/` with `mkdir -p`.
+2. **Verify the MES anomaly mechanically** — with `python3`, parse `examples/cases/quality-anomaly/materials/data/thresholds.yaml` and `examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv`; filter by all three bound keys (`date`, integer `line`, and `shift`); require exactly one row; recompute `100 * defects / units` and verify it agrees with `defect_rate_pct` within 0.05 percentage point; classify an anomaly only when the recorded rate is strictly greater than `defect_rate_pct_threshold`. Print the selected row, recomputed rate, threshold, and verdict. Stop without finalizing either deliverable if the row is missing/ambiguous, internally inconsistent, or not anomalous.
+3. **Extract time-aligned sensor exceedances mechanically** — with `python3`, parse `examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv`; keep only integer `line == 3` and the supplied continuous overnight rows from **2026-08-27T20:00 through 2026-08-28T03:00 inclusive**. Do not infer a broader corporate shift schedule. For `temp_c` and `vibration_mm_s`, compare each value strictly (`>`) with its configured maximum, record every exceedance timestamp/value, group consecutive hourly exceedances into inclusive intervals, and record each peak and peak timestamp. Print the filtered window and derived exceedances.
+4. **Gate evidence by calibration mechanically** — with `python3`, parse `examples/cases/quality-anomaly/materials/data/calibration-log.csv` and join each measure to the unique calibration row whose `measure` matches (`temp_c` or `vibration_mm_s`), regardless of the row-level `sensor_id` in the sensor CSV. At every relevant measurement timestamp, compute whole elapsed days since `last_calibrated`; classify the measure `trusted` when age is at most `calibration_interval_days` and `untrusted` when older. Record the calibration sensor ID, date, ages, status, and `eligible_for_causal_use`. An untrusted measure's observed exceedances must remain disclosed but must not enter causal support. Stop for human review if a measure has zero/multiple calibration records, a future calibration date, or inconsistent trust status across its relevant interval.
+5. **Write the structured evidence first** — create `build/quality-anomaly/anomaly-2026-08-27.json` containing: `incident` (`date`, `line`, `shift`, `observed_sensor_window`); `sources` (all input paths); `thresholds`; `mes` (selected row, recomputed rate, and `is_anomaly`); `sensor_evidence` keyed by measure (unit, maximum, exceedance samples, contiguous intervals, peak, calibration record/ages/status, and `eligible_for_causal_use`); `candidate_root_cause` (`status`, `statement`, `supporting_trusted_measures`, and `limitations`); `remediation` as a list of items each with `action`, `approval_required: true`, `approval_authority: "Quality Engineer"`, and `approval_status: "pending"`; and `validation`. The cause must be `undetermined` if no trustworthy evidence supports a bounded candidate. Do not assert a specific failed component without supplied evidence.
+6. **Render the response report from the JSON** — write `build/quality-anomaly/anomaly-report-2026-08-27.md` in the concise English format of `examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md`, using exactly these sections: title, `## Anomaly`, `## Sensor evidence`, `## Root cause (candidate)`, and `## Remediation (requires Quality Engineer approval)`. Include the selected production facts and threshold; each measure's exceedance interval/peak and calibration trust basis; explicit `untrusted` wording and exclusion from causal judgment where applicable; a correlation-bounded candidate or `undetermined`; and `Approval: pending`. Every remediation item must include the exact statement **“requires Quality Engineer approval”** and must not claim execution or approval.
+7. **Validate both artifacts mechanically** — parse the JSON with `python3 -m json.tool`; use `python3` to recompute the selected MES result, exceedance samples/intervals/peaks, calibration ages/statuses, and causal eligibility directly from the four data files; compare them with JSON; then verify that every material numeric fact, trust label, candidate-cause limitation, remediation action, approval authority/status, and source incident in Markdown agrees with JSON. Confirm that no untrusted measure appears in `supporting_trusted_measures`, no unrelated shift appears, and both filenames match **2026-08-27**. Set `validation.status` to `passed` only after all checks pass and re-run `python3 -m json.tool` after the update.
+8. **Do not perform remediation** — this task produces analysis artifacts only. Do not contact people, change manufacturing systems, issue work orders, recalibrate sensors, or state that any approval or action occurred.
+
+Reply with a short summary containing the verified incident and defect-rate verdict, which measures were trusted/untrusted, the candidate-cause status, the pending Quality Engineer approval status, and these two paths:
+
+- `build/quality-anomaly/anomaly-2026-08-27.json`
+- `build/quality-anomaly/anomaly-report-2026-08-27.md`
diff --git a/examples/cases/quality-anomaly/behaviors/bound-cause-to-trusted-evidence/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/bound-cause-to-trusted-evidence/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..ed9973689f0ea16d8ff850a90eb9ca7c90b9ee14
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/bound-cause-to-trusted-evidence/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: bound-cause-to-trusted-evidence
+
+## 1. Intent
+Keep root-cause language proportional to the supplied evidence and distinguish a correlated candidate from a confirmed equipment failure.
+
+## 2. Evidence
+The structured evidence records a candidate status, statement, explicit supporting trusted measures, and limitations after calibration gating; the report renders the same bounded claim under `Root cause (candidate)`.
+
+## 3. Decision
+- `true`: The cause is labeled a candidate, cites only trusted supporting measures, states material limitations, and becomes `undetermined` when no trustworthy causal evidence remains.
+- `false`: A cause is presented as confirmed, an unsupported component failure is named, an untrusted measure supplies support, or uncertainty is omitted.
+- `na`: The trajectory makes no causal assessment.
+
+## 4. Execution
+Draft the causal assessment only after MES verification, time alignment, exceedance calculation, and calibration gating; separate observed correlation from confirmation.
+
+## 5. Recovery
+Downgrade unsupported certainty, remove untrusted or absent support, add the evidence limitation, or set the cause to `undetermined`; regenerate both artifacts and revalidate them.
+
+## 6. Failure Modes
+Copying the coolant diagnosis from the previous report, equating threshold coincidence with proof, inventing a failed station/component, or masking insufficient evidence with confident prose.
diff --git a/examples/cases/quality-anomaly/behaviors/gate-causation-by-calibration/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/gate-causation-by-calibration/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..7d6687d35695584d296763add90d4fc6bb413d0a
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/gate-causation-by-calibration/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: gate-causation-by-calibration
+
+## 1. Intent
+Prevent expired or mismapped sensor calibration from supporting a root-cause candidate while keeping observed evidence transparent.
+
+## 2. Evidence
+The trajectory joins each analyzed measure to the unique `measure` row in `examples/cases/quality-anomaly/materials/data/calibration-log.csv`, computes elapsed whole days at relevant measurement timestamps using the configured interval, records the calibration sensor ID/date/ages and trust verdict, and records causal eligibility before drafting a cause.
+
+## 3. Decision
+- `true`: Every measure is mapped by measure, age is evaluated at measurement time, values older than the allowed interval are labeled `untrusted` and disclosed but absent from causal support, and only trusted measures support the candidate cause.
+- `false`: Calibration is skipped, evaluated at workflow execution time, mapped from the sensor row ID across measures, expired evidence is hidden, or an untrusted measure supports causation.
+- `na`: No sensor evidence is analyzed or no causal assessment is made.
+
+## 4. Execution
+Perform the calibration join and trust calculation after time-aligned exceedance extraction and before candidate-cause judgment; fail closed on missing, duplicate, future-dated, or inconsistent calibration evidence.
+
+## 5. Recovery
+Remove unsupported causal claims, remap calibration records by measure, recompute incident-time ages and trust, then regenerate the structured evidence and report; escalate unresolved calibration ambiguity for human review.
+
+## 6. Failure Modes
+Treating the row-level temperature sensor ID as vibration calibration, using today's date, treating day 90 as expired, silently dropping overdue readings, or describing untrusted vibration as causal.
diff --git a/examples/cases/quality-anomaly/behaviors/keep-report-evidence-auditable/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/keep-report-evidence-auditable/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..0b418a50e3aeea4b28fe8742f4f7b850a13a5771
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/keep-report-evidence-auditable/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: keep-report-evidence-auditable
+
+## 1. Intent
+Produce mutually consistent structured and human-readable anomaly artifacts whose facts can be reproduced from the supplied incident sources.
+
+## 2. Evidence
+The trajectory writes `build/quality-anomaly/anomaly-2026-08-27.json` before rendering `build/quality-anomaly/anomaly-report-2026-08-27.md`, records all source paths and derivations, parses the JSON, and mechanically compares MES facts, sensor intervals/peaks, calibration trust, causal support, remediation, and approval status across sources and outputs.
+
+## 3. Decision
+- `true`: Both incident-dated files exist, parse, concern only the bound incident, reproduce the source calculations, agree on every material fact and decision, and record a passed validation.
+- `false`: A file is missing or malformed, prose is drafted from memory, the files disagree, sources/derivations are absent, unrelated shifts appear, or validation passes despite a mismatch.
+- `na`: The trajectory does not produce the anomaly JSON and report pair.
+
+## 4. Execution
+Serialize source-derived structured evidence first, render the report from it in the previous deliverable's section format, then run source-to-JSON and JSON-to-Markdown consistency checks before replying.
+
+## 5. Recovery
+Treat freshly recomputed source evidence as authoritative, correct or regenerate the JSON, re-render Markdown, and repeat all validations without modifying source materials or performing remediation.
+
+## 6. Failure Modes
+Drafting prose first and backfilling JSON, copying prior-incident values, mismatched dates/rates/peaks/trust labels, omitting limitations or approval status, or declaring success before mechanical validation.
diff --git a/examples/cases/quality-anomaly/behaviors/require-quality-engineer-approval/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/require-quality-engineer-approval/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..94735f4fcc72cad618089dcb026e0ec3cf39ae25
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/require-quality-engineer-approval/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: require-quality-engineer-approval
+
+## 1. Intent
+Prevent the analysis assistant from authorizing or claiming execution of manufacturing remediation.
+
+## 2. Evidence
+Every structured remediation item records `approval_required: true`, `approval_authority: "Quality Engineer"`, and `approval_status: "pending"`; the report section and each action include “requires Quality Engineer approval,” and the trajectory performs no external operational action.
+
+## 3. Decision
+- `true`: All remediation remains a proposal pending Quality Engineer approval, the required statement is explicit for every action, and no approval or execution is invented.
+- `false`: Any action is issued as an order, marked approved/completed without evidence, omits the required approval statement, or is actually performed by the workflow.
+- `na`: The trajectory neither proposes nor performs manufacturing remediation.
+
+## 4. Execution
+Apply the approval gate while serializing each remediation item and preserve it verbatim when rendering Markdown; restrict the workflow to artifact creation.
+
+## 5. Recovery
+Stop any attempted operational step, change unauthorized language and statuses to pending proposals, add the required approval statement to every item, and regenerate and revalidate both artifacts.
+
+## 6. Failure Modes
+Copying imperative maintenance language, treating report generation as authorization, claiming verbal or assumed approval, contacting operations, changing equipment, or omitting approval from one of several actions.
diff --git a/examples/cases/quality-anomaly/behaviors/use-authoritative-thresholds/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/use-authoritative-thresholds/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..8e32cc42328707d5ee24d0963590ef9dee1e9421
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/use-authoritative-thresholds/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: use-authoritative-thresholds
+
+## 1. Intent
+Ensure anomaly, sensor, and calibration decisions use the supplied current threshold configuration rather than memory, the previous report, or invented limits.
+
+## 2. Evidence
+The trajectory reads `examples/cases/quality-anomaly/materials/data/thresholds.yaml` before classification and records its line, defect-rate threshold, per-measure maxima, calibration interval, and source path in the structured evidence.
+
+## 3. Decision
+- `true`: Every threshold and calibration interval used in the artifacts matches the read configuration, and strict exceedance is applied.
+- `false`: A limit is hardcoded, remembered, copied from the prior report, invented, or interpreted as inclusive despite the configuration's “above” rule.
+- `na`: The trajectory does not classify a manufacturing quality anomaly or sensor evidence.
+
+## 4. Execution
+Make the threshold-file read a required predecessor to MES classification, sensor comparison, calibration gating, and drafting.
+
+## 5. Recovery
+Discard derived classifications, re-read the threshold file, recompute all dependent evidence, and regenerate both artifacts.
+
+## 6. Failure Modes
+Using 3.1% or 80.2 °C from the prior report, treating equality as exceedance, applying a limit to the wrong measure, or using an undocumented calibration interval.
diff --git a/examples/cases/quality-anomaly/behaviors/verify-bound-mes-anomaly/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/verify-bound-mes-anomaly/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..08b18f1660f90ef47535da4d4c89dd201a5155ef
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/verify-bound-mes-anomaly/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: verify-bound-mes-anomaly
+
+## 1. Intent
+Prevent a response report from being finalized for an unverified, wrong, ambiguous, or internally inconsistent shift record.
+
+## 2. Evidence
+The trajectory filters `examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv` by the bound date, line, and shift; records a match count of one; recomputes the defect rate from units and defects; and compares the recorded rate strictly with the configured threshold before sensor analysis.
+
+## 3. Decision
+- `true`: Exactly one bound MES row is selected, its recorded and recomputed rates agree within 0.05 percentage point, and the rate is strictly above the configured threshold before downstream analysis proceeds.
+- `false`: The wrong or multiple shifts are used, the rate is assumed from notes, inconsistent counts are ignored, or a non-anomalous shift receives a finalized anomaly report.
+- `na`: The trajectory does not produce a shift-level quality-anomaly response.
+
+## 4. Execution
+Make bound-key selection, uniqueness, rate reproduction, and threshold classification non-removable predecessors to sensor analysis and artifact creation.
+
+## 5. Recovery
+Stop downstream work, re-read the MES and threshold sources, reselect by all bound keys, and continue only when a unique, consistent, above-threshold row is established; otherwise report the evidence problem for human review.
+
+## 6. Failure Modes
+Scanning and reporting unrelated shifts, matching date without line/shift, trusting a precomputed rate despite inconsistent counts, or using `>=` instead of `>`.

codex
All four interview rounds are now recorded, and the task plus six sparse behavior contracts are drafted. The contracts isolate the non-negotiable gates—authority, MES verification, calibration trust, causal restraint, approval, and artifact auditability—without turning every procedural detail into a separate behavior. I’m running structural and parser checks now; I will not execute any report-analysis step.
exec
/bin/zsh -lc "git status --short examples/cases/quality-anomaly && find examples/cases/quality-anomaly/behaviors -name BEHAVIOR.md -print | sort && python3 - <<'PY'
from pathlib import Path
from adapters.agentbehavior.parser import load_behavior_file
root = Path('examples/cases/quality-anomaly')
assert (root/'ASSUMPTIONS.md').exists()
assert (root/'TASK.md').exists()
behaviors = sorted((root/'behaviors').glob('*/BEHAVIOR.md'))
assert len(behaviors) == 6, len(behaviors)
for path in behaviors:
    parsed = load_behavior_file(path)
    missing = [k for k in ('intent','evidence','execution','recovery','failure_modes') if not parsed[k]]
    missing += [f'decision.{k}' for k in ('true','false','na') if not parsed['decision'][k]]
    assert not missing, (path, missing)
    print(path, 'OK')
task = (root/'TASK.md').read_text()
for required in [
    'examples/cases/quality-anomaly/materials/',
    'build/quality-anomaly/',
    'anomaly-2026-08-27.json',
    'anomaly-report-2026-08-27.md',
]:
    assert required in task, required
print('TASK references OK')
PY

git diff --check -- examples/cases/quality-anomaly" in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 0ms:
?? examples/cases/quality-anomaly/
examples/cases/quality-anomaly/behaviors/bound-cause-to-trusted-evidence/BEHAVIOR.md
examples/cases/quality-anomaly/behaviors/gate-causation-by-calibration/BEHAVIOR.md
examples/cases/quality-anomaly/behaviors/keep-report-evidence-auditable/BEHAVIOR.md
examples/cases/quality-anomaly/behaviors/require-quality-engineer-approval/BEHAVIOR.md
examples/cases/quality-anomaly/behaviors/use-authoritative-thresholds/BEHAVIOR.md
examples/cases/quality-anomaly/behaviors/verify-bound-mes-anomaly/BEHAVIOR.md
examples/cases/quality-anomaly/behaviors/bound-cause-to-trusted-evidence/BEHAVIOR.md OK
examples/cases/quality-anomaly/behaviors/gate-causation-by-calibration/BEHAVIOR.md OK
examples/cases/quality-anomaly/behaviors/keep-report-evidence-auditable/BEHAVIOR.md OK
examples/cases/quality-anomaly/behaviors/require-quality-engineer-approval/BEHAVIOR.md OK
examples/cases/quality-anomaly/behaviors/use-authoritative-thresholds/BEHAVIOR.md OK
examples/cases/quality-anomaly/behaviors/verify-bound-mes-anomaly/BEHAVIOR.md OK
TASK references OK

diff --git a/examples/cases/quality-anomaly/ASSUMPTIONS.md b/examples/cases/quality-anomaly/ASSUMPTIONS.md
new file mode 100644
index 0000000000000000000000000000000000000000..c7528a7d3de8b799f02939fcb4e7e71c5480872b
--- /dev/null
+++ b/examples/cases/quality-anomaly/ASSUMPTIONS.md
@@ -0,0 +1,95 @@
+# Assumptions: manufacturing line quality anomaly response reports
+
+The requester was unavailable for an interactive interview. Each grilling round below therefore records the frontier questions, the recommended answer adopted from the supplied materials, and why it was chosen. These are reviewable assumptions, not new source facts; the requester can correct them before the first run.
+
+## Round 1 — Outcome and scope
+
+1. **What is the single-sentence goal, and who consumes the result?**
+   - **Chosen answer:** Produce an auditable Line 3 quality-anomaly response report and structured evidence summary for the Quality Engineer, so they can review a detected shift-level defect spike, its trustworthy sensor evidence, candidate cause, and proposed remediation.
+   - **Why:** `materials/memo.md` describes the recurring report, requires Quality Engineer approval for improvements, and says both a report and raw-data summary JSON are required. The prior report is written for operational quality review.
+
+2. **Which incident is in scope for this run?**
+   - **Chosen answer:** **2026-08-27**, **Line 3**, **night shift** only.
+   - **Why:** `materials/notes.txt` names exactly this incident. No other line or shift was requested.
+
+3. **Should the task scan for all anomalies or merely assume the noted incident is anomalous?**
+   - **Chosen answer:** Bind the run to the noted line/date/shift, but independently verify that it exceeds the authoritative defect-rate threshold; do not report unrelated shifts.
+   - **Why:** The memo's first required step is to find shifts exceeding the threshold, while the notes identify “this case.” This preserves verification without broadening the deliverable.
+
+4. **What language and presentation style should the deliverable use?**
+   - **Chosen answer:** Use English and follow the headings and concise operational style of `materials/previous/anomaly-report-2026-06-14.md`.
+   - **Why:** The memo is Korean, but the repository and prior finished deliverable are English. The project instructions require English artifacts.
+
+## Round 2 — Inputs, authority, and boundaries
+
+5. **Which files are authoritative for facts and rules?**
+   - **Chosen answer:** Use `materials/data/thresholds.yaml` for thresholds and calibration interval, `materials/data/mes-defects-2026-08.csv` for shift production/defect facts, `materials/data/sensor-2026-08-27.csv` for measurements, and `materials/data/calibration-log.csv` for calibration status. Use `materials/memo.md` and `materials/notes.txt` for process/scope, and the prior report only for format.
+   - **Why:** These roles are stated directly in the memo and reflected by the file contents. The previous report is an example, not evidence for this incident.
+
+6. **Which values should be treated as per-run parameters?**
+   - **Chosen answer:** `incident_date=2026-08-27`, `line=3`, `shift=night`, the four input paths, and `output_dir=build/quality-anomaly/` are explicit run bindings. A future run may replace them.
+   - **Why:** The notes bind the first three values, while the requested task paths bind the inputs and output location. Making them explicit supports later parameter discovery.
+
+7. **What time window defines the night shift?**
+   - **Chosen answer:** Use all sensor rows supplied for the bound incident and line, spanning `2026-08-27T20:00` through `2026-08-28T03:00` inclusive; record this observed window in JSON rather than inventing a corporate shift schedule.
+   - **Why:** The sensor file contains exactly that continuous overnight window and the MES record labels the incident “night.” No formal shift timetable was supplied.
+
+8. **How is the strict threshold boundary interpreted?**
+   - **Chosen answer:** A value is anomalous only when it is strictly greater than the configured maximum (`>`), not equal to it.
+   - **Why:** `thresholds.yaml` says “above this = anomaly,” and the memo says “넘은” (exceeded).
+
+9. **At what date is calibration age evaluated, and how is expiry handled?**
+   - **Chosen answer:** Evaluate each measure's calibration age at the timestamp of each relevant measurement; it is trusted when age is at most 90 whole days and untrusted when older than 90 days. Record the dates and computed ages.
+   - **Why:** The memo says an overdue sensor must be marked untrustworthy and excluded from causal judgment. Incident-time evaluation avoids using the later workflow execution date. The “older than” wording makes day 90 inclusive/trusted.
+
+10. **How should calibration records map to a sensor CSV that has one `sensor_id` but both temperature and vibration columns?**
+    - **Chosen answer:** Map calibration status by the `measure` field: `temp_c` to the calibration row for `temp_c`, and `vibration_mm_s` to the row for `vibration_mm_s`. Preserve both calibration sensor IDs in JSON. Do not apply `S3-TEMP-1` calibration to vibration merely because it appears in the sensor row.
+    - **Why:** `calibration-log.csv` has distinct sensor IDs per measure, while every sensor-data row is labeled `S3-TEMP-1` despite carrying both values. Measure-based mapping is the only interpretation consistent with the calibration log and the memo's per-sensor trust rule.
+
+## Round 3 — Analysis and judgment
+
+11. **What is the ordered process, and which parts are mechanical versus judgment?**
+    - **Chosen answer:** Mechanically load bindings and thresholds; select and verify the MES row; filter the observed sensor window; find strict exceedances and contiguous intervals; join calibration by measure and compute trust; serialize JSON; then use judgment only to phrase a bounded candidate cause and approval-gated remediation from trustworthy evidence; render Markdown from JSON and validate consistency.
+    - **Why:** This follows the memo's five-step order and makes calculations reproducible while isolating the genuinely interpretive steps.
+
+12. **May an overdue sensor's exceedance appear in the report?**
+    - **Chosen answer:** Yes, disclose its observed values and exceedance interval, label it exactly **“untrusted”**, state why, and exclude it from causal support.
+    - **Why:** The memo requires overdue sensor values to be marked “신뢰 불가” (untrusted) and removed from causal determination—not silently discarded.
+
+13. **How strong may the root-cause claim be?**
+    - **Chosen answer:** Label it a **candidate**, tie it only to trusted evidence, distinguish correlation from confirmation, and do not name a specific failed component unless the supplied evidence identifies one.
+    - **Why:** The memo asks for cause candidates, and the prior report labels the section “Root cause (candidate).” The current files contain measurements, not inspection evidence proving a component failure.
+
+14. **What remediation may be proposed?**
+    - **Chosen answer:** Recommend investigation/containment steps proportionate to the trusted evidence (for example, inspect the thermal process and run a controlled verification trial), plus recalibration/verification of any overdue sensor; every action must say **“requires Quality Engineer approval”** and remain pending.
+    - **Why:** The memo forbids execution instructions without Quality Engineer approval. The evidence supports investigation, not autonomous maintenance action.
+
+15. **What happens if the MES row does not exceed the threshold, inputs are missing/ambiguous, or no trustworthy causal evidence remains?**
+    - **Chosen answer:** Stop normal report finalization and surface the condition for human review. If the anomaly is verified but causal evidence is insufficient, the report may still be produced, but the cause must be `undetermined` and remediation limited to approval-gated investigation/data recovery.
+    - **Why:** Inventing a cause or silently selecting ambiguous evidence would violate the memo's trust rule. A verified quality event still needs a response report even when causation is unresolved.
+
+## Round 4 — Deliverables, completeness, and failure checks
+
+16. **What exact files must be produced?**
+    - **Chosen answer:** `build/quality-anomaly/anomaly-2026-08-27.json` first, then `build/quality-anomaly/anomaly-report-2026-08-27.md` rendered from it. No source materials are modified.
+    - **Why:** `materials/notes.txt` specifies both filename patterns, and the requester requires outputs under `build/quality-anomaly/`.
+
+17. **What must the JSON contain?**
+    - **Chosen answer:** Run bindings and source paths; threshold values; selected MES row and anomaly verdict; sensor window; per-measure exceedance timestamps/intervals/peaks; calibration ID/date/age/status; whether each measure is eligible for causal use; candidate-cause statement with supporting trusted measures and limitations; approval-gated remediation items; and validation status.
+    - **Why:** This is the minimum structured evidence needed to audit every memo-required decision and keep the Markdown traceable to raw data.
+
+18. **What must the Markdown contain?**
+    - **Chosen answer:** The prior report's sections—title, `Anomaly`, `Sensor evidence`, `Root cause (candidate)`, and `Remediation (requires Quality Engineer approval)`—with source-grounded values, explicit trust labels, causal limitations, and approval status `pending`.
+    - **Why:** The memo explicitly requires the previous-folder format, and the previous deliverable supplies these headings and approval wording.
+
+19. **What exact acceptance checks define done?**
+    - **Chosen answer:** Both files exist and parse; filenames match the bound incident date; all reported numeric facts reproduce from the selected rows and configured thresholds; strict boundaries and contiguous intervals are correct; calibration is evaluated by measure at incident time; untrusted measures never support the cause; remediation explicitly requires Quality Engineer approval and remains pending; Markdown and JSON agree; only the requested incident is reported.
+    - **Why:** These checks cover the requested output, all memo rules, and the main data trap.
+
+20. **Which known or feared failure modes require explicit prevention?**
+    - **Chosen answer:** Using the prior report as incident evidence; trusting vibration under the temperature sensor ID; evaluating calibration at execution time; hiding or causally using overdue sensor values; treating equality as exceedance; inventing shift boundaries, component failures, or approvals; issuing remediation as an order; mismatching JSON/Markdown; and processing unrelated shifts.
+    - **Why:** The memo identifies missed calibration as a serious prior failure. The remaining risks follow directly from the supplied schemas, example, and requested dual outputs.
+
+## Deferred confirmations
+
+Before generalizing this workflow beyond the supplied fixture, the requester should confirm the official shift schedule, whether calibration validity is day- or timestamp-granular, the canonical JSON schema, and the organization-approved remediation vocabulary. None of these unknowns prevents a bounded first run under the assumptions above.
diff --git a/examples/cases/quality-anomaly/TASK.md b/examples/cases/quality-anomaly/TASK.md
new file mode 100644
index 0000000000000000000000000000000000000000..376b342e282524fabf4de36e67e46f0c8de11ed1
--- /dev/null
+++ b/examples/cases/quality-anomaly/TASK.md
@@ -0,0 +1,21 @@
+# Task: Line 3 quality anomaly response report for 2026-08-27 night shift
+
+You are the manufacturing quality-analysis assistant. Prepare the auditable anomaly evidence summary and response report for **incident_date=2026-08-27**, **line=3**, **shift=night** for review by the Quality Engineer.
+
+Rules (from `behaviors/`): use the supplied thresholds as the sole numeric rule authority; independently verify the bound MES anomaly before analysis; align sensor evidence only to the bound line and supplied overnight incident window; evaluate calibration by measure at measurement time and never use an overdue sensor to support causation; make only evidence-bounded candidate-cause claims; and leave every remediation pending with the exact statement **“requires Quality Engineer approval”**. Use `examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md` only as a format example, never as evidence. Assumptions adopted while the requester was unavailable are recorded in `examples/cases/quality-anomaly/ASSUMPTIONS.md`.
+
+Do the work with auditable shell commands (`cat`, `mkdir -p`, and `python3` using CSV/YAML/date/JSON handling) from the repository root. Do not modify anything under `examples/cases/quality-anomaly/materials/`.
+
+1. **Bind the run and inspect authority files** — set and print the per-run bindings **incident_date=2026-08-27**, **line=3**, **shift=night**, **MES=examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv**, **SENSORS=examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv**, **CALIBRATION=examples/cases/quality-anomaly/materials/data/calibration-log.csv**, **THRESHOLDS=examples/cases/quality-anomaly/materials/data/thresholds.yaml**, and **OUTPUT_DIR=build/quality-anomaly**. Read `examples/cases/quality-anomaly/materials/memo.md`, `examples/cases/quality-anomaly/materials/notes.txt`, the four data files, and `examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md`. Create `build/quality-anomaly/` with `mkdir -p`.
+2. **Verify the MES anomaly mechanically** — with `python3`, parse `examples/cases/quality-anomaly/materials/data/thresholds.yaml` and `examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv`; filter by all three bound keys (`date`, integer `line`, and `shift`); require exactly one row; recompute `100 * defects / units` and verify it agrees with `defect_rate_pct` within 0.05 percentage point; classify an anomaly only when the recorded rate is strictly greater than `defect_rate_pct_threshold`. Print the selected row, recomputed rate, threshold, and verdict. Stop without finalizing either deliverable if the row is missing/ambiguous, internally inconsistent, or not anomalous.
+3. **Extract time-aligned sensor exceedances mechanically** — with `python3`, parse `examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv`; keep only integer `line == 3` and the supplied continuous overnight rows from **2026-08-27T20:00 through 2026-08-28T03:00 inclusive**. Do not infer a broader corporate shift schedule. For `temp_c` and `vibration_mm_s`, compare each value strictly (`>`) with its configured maximum, record every exceedance timestamp/value, group consecutive hourly exceedances into inclusive intervals, and record each peak and peak timestamp. Print the filtered window and derived exceedances.
+4. **Gate evidence by calibration mechanically** — with `python3`, parse `examples/cases/quality-anomaly/materials/data/calibration-log.csv` and join each measure to the unique calibration row whose `measure` matches (`temp_c` or `vibration_mm_s`), regardless of the row-level `sensor_id` in the sensor CSV. At every relevant measurement timestamp, compute whole elapsed days since `last_calibrated`; classify the measure `trusted` when age is at most `calibration_interval_days` and `untrusted` when older. Record the calibration sensor ID, date, ages, status, and `eligible_for_causal_use`. An untrusted measure's observed exceedances must remain disclosed but must not enter causal support. Stop for human review if a measure has zero/multiple calibration records, a future calibration date, or inconsistent trust status across its relevant interval.
+5. **Write the structured evidence first** — create `build/quality-anomaly/anomaly-2026-08-27.json` containing: `incident` (`date`, `line`, `shift`, `observed_sensor_window`); `sources` (all input paths); `thresholds`; `mes` (selected row, recomputed rate, and `is_anomaly`); `sensor_evidence` keyed by measure (unit, maximum, exceedance samples, contiguous intervals, peak, calibration record/ages/status, and `eligible_for_causal_use`); `candidate_root_cause` (`status`, `statement`, `supporting_trusted_measures`, and `limitations`); `remediation` as a list of items each with `action`, `approval_required: true`, `approval_authority: "Quality Engineer"`, and `approval_status: "pending"`; and `validation`. The cause must be `undetermined` if no trustworthy evidence supports a bounded candidate. Do not assert a specific failed component without supplied evidence.
+6. **Render the response report from the JSON** — write `build/quality-anomaly/anomaly-report-2026-08-27.md` in the concise English format of `examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md`, using exactly these sections: title, `## Anomaly`, `## Sensor evidence`, `## Root cause (candidate)`, and `## Remediation (requires Quality Engineer approval)`. Include the selected production facts and threshold; each measure's exceedance interval/peak and calibration trust basis; explicit `untrusted` wording and exclusion from causal judgment where applicable; a correlation-bounded candidate or `undetermined`; and `Approval: pending`. Every remediation item must include the exact statement **“requires Quality Engineer approval”** and must not claim execution or approval.
+7. **Validate both artifacts mechanically** — parse the JSON with `python3 -m json.tool`; use `python3` to recompute the selected MES result, exceedance samples/intervals/peaks, calibration ages/statuses, and causal eligibility directly from the four data files; compare them with JSON; then verify that every material numeric fact, trust label, candidate-cause limitation, remediation action, approval authority/status, and source incident in Markdown agrees with JSON. Confirm that no untrusted measure appears in `supporting_trusted_measures`, no unrelated shift appears, and both filenames match **2026-08-27**. Set `validation.status` to `passed` only after all checks pass and re-run `python3 -m json.tool` after the update.
+8. **Do not perform remediation** — this task produces analysis artifacts only. Do not contact people, change manufacturing systems, issue work orders, recalibrate sensors, or state that any approval or action occurred.
+
+Reply with a short summary containing the verified incident and defect-rate verdict, which measures were trusted/untrusted, the candidate-cause status, the pending Quality Engineer approval status, and these two paths:
+
+- `build/quality-anomaly/anomaly-2026-08-27.json`
+- `build/quality-anomaly/anomaly-report-2026-08-27.md`
diff --git a/examples/cases/quality-anomaly/behaviors/bound-cause-to-trusted-evidence/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/bound-cause-to-trusted-evidence/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..ed9973689f0ea16d8ff850a90eb9ca7c90b9ee14
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/bound-cause-to-trusted-evidence/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: bound-cause-to-trusted-evidence
+
+## 1. Intent
+Keep root-cause language proportional to the supplied evidence and distinguish a correlated candidate from a confirmed equipment failure.
+
+## 2. Evidence
+The structured evidence records a candidate status, statement, explicit supporting trusted measures, and limitations after calibration gating; the report renders the same bounded claim under `Root cause (candidate)`.
+
+## 3. Decision
+- `true`: The cause is labeled a candidate, cites only trusted supporting measures, states material limitations, and becomes `undetermined` when no trustworthy causal evidence remains.
+- `false`: A cause is presented as confirmed, an unsupported component failure is named, an untrusted measure supplies support, or uncertainty is omitted.
+- `na`: The trajectory makes no causal assessment.
+
+## 4. Execution
+Draft the causal assessment only after MES verification, time alignment, exceedance calculation, and calibration gating; separate observed correlation from confirmation.
+
+## 5. Recovery
+Downgrade unsupported certainty, remove untrusted or absent support, add the evidence limitation, or set the cause to `undetermined`; regenerate both artifacts and revalidate them.
+
+## 6. Failure Modes
+Copying the coolant diagnosis from the previous report, equating threshold coincidence with proof, inventing a failed station/component, or masking insufficient evidence with confident prose.
diff --git a/examples/cases/quality-anomaly/behaviors/gate-causation-by-calibration/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/gate-causation-by-calibration/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..7d6687d35695584d296763add90d4fc6bb413d0a
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/gate-causation-by-calibration/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: gate-causation-by-calibration
+
+## 1. Intent
+Prevent expired or mismapped sensor calibration from supporting a root-cause candidate while keeping observed evidence transparent.
+
+## 2. Evidence
+The trajectory joins each analyzed measure to the unique `measure` row in `examples/cases/quality-anomaly/materials/data/calibration-log.csv`, computes elapsed whole days at relevant measurement timestamps using the configured interval, records the calibration sensor ID/date/ages and trust verdict, and records causal eligibility before drafting a cause.
+
+## 3. Decision
+- `true`: Every measure is mapped by measure, age is evaluated at measurement time, values older than the allowed interval are labeled `untrusted` and disclosed but absent from causal support, and only trusted measures support the candidate cause.
+- `false`: Calibration is skipped, evaluated at workflow execution time, mapped from the sensor row ID across measures, expired evidence is hidden, or an untrusted measure supports causation.
+- `na`: No sensor evidence is analyzed or no causal assessment is made.
+
+## 4. Execution
+Perform the calibration join and trust calculation after time-aligned exceedance extraction and before candidate-cause judgment; fail closed on missing, duplicate, future-dated, or inconsistent calibration evidence.
+
+## 5. Recovery
+Remove unsupported causal claims, remap calibration records by measure, recompute incident-time ages and trust, then regenerate the structured evidence and report; escalate unresolved calibration ambiguity for human review.
+
+## 6. Failure Modes
+Treating the row-level temperature sensor ID as vibration calibration, using today's date, treating day 90 as expired, silently dropping overdue readings, or describing untrusted vibration as causal.
diff --git a/examples/cases/quality-anomaly/behaviors/keep-report-evidence-auditable/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/keep-report-evidence-auditable/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..0b418a50e3aeea4b28fe8742f4f7b850a13a5771
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/keep-report-evidence-auditable/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: keep-report-evidence-auditable
+
+## 1. Intent
+Produce mutually consistent structured and human-readable anomaly artifacts whose facts can be reproduced from the supplied incident sources.
+
+## 2. Evidence
+The trajectory writes `build/quality-anomaly/anomaly-2026-08-27.json` before rendering `build/quality-anomaly/anomaly-report-2026-08-27.md`, records all source paths and derivations, parses the JSON, and mechanically compares MES facts, sensor intervals/peaks, calibration trust, causal support, remediation, and approval status across sources and outputs.
+
+## 3. Decision
+- `true`: Both incident-dated files exist, parse, concern only the bound incident, reproduce the source calculations, agree on every material fact and decision, and record a passed validation.
+- `false`: A file is missing or malformed, prose is drafted from memory, the files disagree, sources/derivations are absent, unrelated shifts appear, or validation passes despite a mismatch.
+- `na`: The trajectory does not produce the anomaly JSON and report pair.
+
+## 4. Execution
+Serialize source-derived structured evidence first, render the report from it in the previous deliverable's section format, then run source-to-JSON and JSON-to-Markdown consistency checks before replying.
+
+## 5. Recovery
+Treat freshly recomputed source evidence as authoritative, correct or regenerate the JSON, re-render Markdown, and repeat all validations without modifying source materials or performing remediation.
+
+## 6. Failure Modes
+Drafting prose first and backfilling JSON, copying prior-incident values, mismatched dates/rates/peaks/trust labels, omitting limitations or approval status, or declaring success before mechanical validation.
diff --git a/examples/cases/quality-anomaly/behaviors/require-quality-engineer-approval/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/require-quality-engineer-approval/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..94735f4fcc72cad618089dcb026e0ec3cf39ae25
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/require-quality-engineer-approval/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: require-quality-engineer-approval
+
+## 1. Intent
+Prevent the analysis assistant from authorizing or claiming execution of manufacturing remediation.
+
+## 2. Evidence
+Every structured remediation item records `approval_required: true`, `approval_authority: "Quality Engineer"`, and `approval_status: "pending"`; the report section and each action include “requires Quality Engineer approval,” and the trajectory performs no external operational action.
+
+## 3. Decision
+- `true`: All remediation remains a proposal pending Quality Engineer approval, the required statement is explicit for every action, and no approval or execution is invented.
+- `false`: Any action is issued as an order, marked approved/completed without evidence, omits the required approval statement, or is actually performed by the workflow.
+- `na`: The trajectory neither proposes nor performs manufacturing remediation.
+
+## 4. Execution
+Apply the approval gate while serializing each remediation item and preserve it verbatim when rendering Markdown; restrict the workflow to artifact creation.
+
+## 5. Recovery
+Stop any attempted operational step, change unauthorized language and statuses to pending proposals, add the required approval statement to every item, and regenerate and revalidate both artifacts.
+
+## 6. Failure Modes
+Copying imperative maintenance language, treating report generation as authorization, claiming verbal or assumed approval, contacting operations, changing equipment, or omitting approval from one of several actions.
diff --git a/examples/cases/quality-anomaly/behaviors/use-authoritative-thresholds/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/use-authoritative-thresholds/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..8e32cc42328707d5ee24d0963590ef9dee1e9421
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/use-authoritative-thresholds/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: use-authoritative-thresholds
+
+## 1. Intent
+Ensure anomaly, sensor, and calibration decisions use the supplied current threshold configuration rather than memory, the previous report, or invented limits.
+
+## 2. Evidence
+The trajectory reads `examples/cases/quality-anomaly/materials/data/thresholds.yaml` before classification and records its line, defect-rate threshold, per-measure maxima, calibration interval, and source path in the structured evidence.
+
+## 3. Decision
+- `true`: Every threshold and calibration interval used in the artifacts matches the read configuration, and strict exceedance is applied.
+- `false`: A limit is hardcoded, remembered, copied from the prior report, invented, or interpreted as inclusive despite the configuration's “above” rule.
+- `na`: The trajectory does not classify a manufacturing quality anomaly or sensor evidence.
+
+## 4. Execution
+Make the threshold-file read a required predecessor to MES classification, sensor comparison, calibration gating, and drafting.
+
+## 5. Recovery
+Discard derived classifications, re-read the threshold file, recompute all dependent evidence, and regenerate both artifacts.
+
+## 6. Failure Modes
+Using 3.1% or 80.2 °C from the prior report, treating equality as exceedance, applying a limit to the wrong measure, or using an undocumented calibration interval.
diff --git a/examples/cases/quality-anomaly/behaviors/verify-bound-mes-anomaly/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/verify-bound-mes-anomaly/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..08b18f1660f90ef47535da4d4c89dd201a5155ef
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/verify-bound-mes-anomaly/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: verify-bound-mes-anomaly
+
+## 1. Intent
+Prevent a response report from being finalized for an unverified, wrong, ambiguous, or internally inconsistent shift record.
+
+## 2. Evidence
+The trajectory filters `examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv` by the bound date, line, and shift; records a match count of one; recomputes the defect rate from units and defects; and compares the recorded rate strictly with the configured threshold before sensor analysis.
+
+## 3. Decision
+- `true`: Exactly one bound MES row is selected, its recorded and recomputed rates agree within 0.05 percentage point, and the rate is strictly above the configured threshold before downstream analysis proceeds.
+- `false`: The wrong or multiple shifts are used, the rate is assumed from notes, inconsistent counts are ignored, or a non-anomalous shift receives a finalized anomaly report.
+- `na`: The trajectory does not produce a shift-level quality-anomaly response.
+
+## 4. Execution
+Make bound-key selection, uniqueness, rate reproduction, and threshold classification non-removable predecessors to sensor analysis and artifact creation.
+
+## 5. Recovery
+Stop downstream work, re-read the MES and threshold sources, reselect by all bound keys, and continue only when a unique, consistent, above-threshold row is established; otherwise report the evidence problem for human review.
+
+## 6. Failure Modes
+Scanning and reporting unrelated shifts, matching date without line/shift, trusting a precomputed rate despite inconsistent counts, or using `>=` instead of `>`.

codex
Defined the quality-anomaly workflow without performing the task itself.

Created:

- [ASSUMPTIONS.md](/Users/hongmartin/orca/projects/open-workflow/examples/cases/quality-anomaly/ASSUMPTIONS.md) — 20 numbered questions across four grilling rounds, with chosen answers and evidence-based rationale.
- [TASK.md](/Users/hongmartin/orca/projects/open-workflow/examples/cases/quality-anomaly/TASK.md) — auditable steps using the supplied materials and writing only under `build/quality-anomaly/`.
- Six behavior contracts under [behaviors/](/Users/hongmartin/orca/projects/open-workflow/examples/cases/quality-anomaly/behaviors):
  - authoritative thresholds
  - bound MES anomaly verification
  - calibration-gated causation
  - evidence-bounded cause claims
  - Quality Engineer approval
  - auditable report/JSON consistency

All behavior files pass the repository parser with the required six sections and complete `true`/`false`/`na` decisions. No anomaly outputs or remediation actions were produced.

Next commands:

```bash
python3 -m uvicorn adapters.proxy.server:app --port 8787 &
codex exec 'Read examples/cases/quality-anomaly/TASK.md and carry it out exactly as written.'   # first run, captured by the proxy
# verify the outputs by hand, then:
$ow-traces · $ow-compile-trace quality-anomaly · $ow-bench quality-anomaly
python3 -m core.build run build/quality-anomaly --request "..." --escalate codex        # new inputs via the front agent
```

The compiled `build/quality-anomaly/quality-anomaly.work` will be the HOW: it identifies which verified steps became deterministic code, which remain agent-driven, and can be edited and recompiled. 🎯
diff --git a/examples/cases/quality-anomaly/ASSUMPTIONS.md b/examples/cases/quality-anomaly/ASSUMPTIONS.md
new file mode 100644
index 0000000000000000000000000000000000000000..c7528a7d3de8b799f02939fcb4e7e71c5480872b
--- /dev/null
+++ b/examples/cases/quality-anomaly/ASSUMPTIONS.md
@@ -0,0 +1,95 @@
+# Assumptions: manufacturing line quality anomaly response reports
+
+The requester was unavailable for an interactive interview. Each grilling round below therefore records the frontier questions, the recommended answer adopted from the supplied materials, and why it was chosen. These are reviewable assumptions, not new source facts; the requester can correct them before the first run.
+
+## Round 1 — Outcome and scope
+
+1. **What is the single-sentence goal, and who consumes the result?**
+   - **Chosen answer:** Produce an auditable Line 3 quality-anomaly response report and structured evidence summary for the Quality Engineer, so they can review a detected shift-level defect spike, its trustworthy sensor evidence, candidate cause, and proposed remediation.
+   - **Why:** `materials/memo.md` describes the recurring report, requires Quality Engineer approval for improvements, and says both a report and raw-data summary JSON are required. The prior report is written for operational quality review.
+
+2. **Which incident is in scope for this run?**
+   - **Chosen answer:** **2026-08-27**, **Line 3**, **night shift** only.
+   - **Why:** `materials/notes.txt` names exactly this incident. No other line or shift was requested.
+
+3. **Should the task scan for all anomalies or merely assume the noted incident is anomalous?**
+   - **Chosen answer:** Bind the run to the noted line/date/shift, but independently verify that it exceeds the authoritative defect-rate threshold; do not report unrelated shifts.
+   - **Why:** The memo's first required step is to find shifts exceeding the threshold, while the notes identify “this case.” This preserves verification without broadening the deliverable.
+
+4. **What language and presentation style should the deliverable use?**
+   - **Chosen answer:** Use English and follow the headings and concise operational style of `materials/previous/anomaly-report-2026-06-14.md`.
+   - **Why:** The memo is Korean, but the repository and prior finished deliverable are English. The project instructions require English artifacts.
+
+## Round 2 — Inputs, authority, and boundaries
+
+5. **Which files are authoritative for facts and rules?**
+   - **Chosen answer:** Use `materials/data/thresholds.yaml` for thresholds and calibration interval, `materials/data/mes-defects-2026-08.csv` for shift production/defect facts, `materials/data/sensor-2026-08-27.csv` for measurements, and `materials/data/calibration-log.csv` for calibration status. Use `materials/memo.md` and `materials/notes.txt` for process/scope, and the prior report only for format.
+   - **Why:** These roles are stated directly in the memo and reflected by the file contents. The previous report is an example, not evidence for this incident.
+
+6. **Which values should be treated as per-run parameters?**
+   - **Chosen answer:** `incident_date=2026-08-27`, `line=3`, `shift=night`, the four input paths, and `output_dir=build/quality-anomaly/` are explicit run bindings. A future run may replace them.
+   - **Why:** The notes bind the first three values, while the requested task paths bind the inputs and output location. Making them explicit supports later parameter discovery.
+
+7. **What time window defines the night shift?**
+   - **Chosen answer:** Use all sensor rows supplied for the bound incident and line, spanning `2026-08-27T20:00` through `2026-08-28T03:00` inclusive; record this observed window in JSON rather than inventing a corporate shift schedule.
+   - **Why:** The sensor file contains exactly that continuous overnight window and the MES record labels the incident “night.” No formal shift timetable was supplied.
+
+8. **How is the strict threshold boundary interpreted?**
+   - **Chosen answer:** A value is anomalous only when it is strictly greater than the configured maximum (`>`), not equal to it.
+   - **Why:** `thresholds.yaml` says “above this = anomaly,” and the memo says “넘은” (exceeded).
+
+9. **At what date is calibration age evaluated, and how is expiry handled?**
+   - **Chosen answer:** Evaluate each measure's calibration age at the timestamp of each relevant measurement; it is trusted when age is at most 90 whole days and untrusted when older than 90 days. Record the dates and computed ages.
+   - **Why:** The memo says an overdue sensor must be marked untrustworthy and excluded from causal judgment. Incident-time evaluation avoids using the later workflow execution date. The “older than” wording makes day 90 inclusive/trusted.
+
+10. **How should calibration records map to a sensor CSV that has one `sensor_id` but both temperature and vibration columns?**
+    - **Chosen answer:** Map calibration status by the `measure` field: `temp_c` to the calibration row for `temp_c`, and `vibration_mm_s` to the row for `vibration_mm_s`. Preserve both calibration sensor IDs in JSON. Do not apply `S3-TEMP-1` calibration to vibration merely because it appears in the sensor row.
+    - **Why:** `calibration-log.csv` has distinct sensor IDs per measure, while every sensor-data row is labeled `S3-TEMP-1` despite carrying both values. Measure-based mapping is the only interpretation consistent with the calibration log and the memo's per-sensor trust rule.
+
+## Round 3 — Analysis and judgment
+
+11. **What is the ordered process, and which parts are mechanical versus judgment?**
+    - **Chosen answer:** Mechanically load bindings and thresholds; select and verify the MES row; filter the observed sensor window; find strict exceedances and contiguous intervals; join calibration by measure and compute trust; serialize JSON; then use judgment only to phrase a bounded candidate cause and approval-gated remediation from trustworthy evidence; render Markdown from JSON and validate consistency.
+    - **Why:** This follows the memo's five-step order and makes calculations reproducible while isolating the genuinely interpretive steps.
+
+12. **May an overdue sensor's exceedance appear in the report?**
+    - **Chosen answer:** Yes, disclose its observed values and exceedance interval, label it exactly **“untrusted”**, state why, and exclude it from causal support.
+    - **Why:** The memo requires overdue sensor values to be marked “신뢰 불가” (untrusted) and removed from causal determination—not silently discarded.
+
+13. **How strong may the root-cause claim be?**
+    - **Chosen answer:** Label it a **candidate**, tie it only to trusted evidence, distinguish correlation from confirmation, and do not name a specific failed component unless the supplied evidence identifies one.
+    - **Why:** The memo asks for cause candidates, and the prior report labels the section “Root cause (candidate).” The current files contain measurements, not inspection evidence proving a component failure.
+
+14. **What remediation may be proposed?**
+    - **Chosen answer:** Recommend investigation/containment steps proportionate to the trusted evidence (for example, inspect the thermal process and run a controlled verification trial), plus recalibration/verification of any overdue sensor; every action must say **“requires Quality Engineer approval”** and remain pending.
+    - **Why:** The memo forbids execution instructions without Quality Engineer approval. The evidence supports investigation, not autonomous maintenance action.
+
+15. **What happens if the MES row does not exceed the threshold, inputs are missing/ambiguous, or no trustworthy causal evidence remains?**
+    - **Chosen answer:** Stop normal report finalization and surface the condition for human review. If the anomaly is verified but causal evidence is insufficient, the report may still be produced, but the cause must be `undetermined` and remediation limited to approval-gated investigation/data recovery.
+    - **Why:** Inventing a cause or silently selecting ambiguous evidence would violate the memo's trust rule. A verified quality event still needs a response report even when causation is unresolved.
+
+## Round 4 — Deliverables, completeness, and failure checks
+
+16. **What exact files must be produced?**
+    - **Chosen answer:** `build/quality-anomaly/anomaly-2026-08-27.json` first, then `build/quality-anomaly/anomaly-report-2026-08-27.md` rendered from it. No source materials are modified.
+    - **Why:** `materials/notes.txt` specifies both filename patterns, and the requester requires outputs under `build/quality-anomaly/`.
+
+17. **What must the JSON contain?**
+    - **Chosen answer:** Run bindings and source paths; threshold values; selected MES row and anomaly verdict; sensor window; per-measure exceedance timestamps/intervals/peaks; calibration ID/date/age/status; whether each measure is eligible for causal use; candidate-cause statement with supporting trusted measures and limitations; approval-gated remediation items; and validation status.
+    - **Why:** This is the minimum structured evidence needed to audit every memo-required decision and keep the Markdown traceable to raw data.
+
+18. **What must the Markdown contain?**
+    - **Chosen answer:** The prior report's sections—title, `Anomaly`, `Sensor evidence`, `Root cause (candidate)`, and `Remediation (requires Quality Engineer approval)`—with source-grounded values, explicit trust labels, causal limitations, and approval status `pending`.
+    - **Why:** The memo explicitly requires the previous-folder format, and the previous deliverable supplies these headings and approval wording.
+
+19. **What exact acceptance checks define done?**
+    - **Chosen answer:** Both files exist and parse; filenames match the bound incident date; all reported numeric facts reproduce from the selected rows and configured thresholds; strict boundaries and contiguous intervals are correct; calibration is evaluated by measure at incident time; untrusted measures never support the cause; remediation explicitly requires Quality Engineer approval and remains pending; Markdown and JSON agree; only the requested incident is reported.
+    - **Why:** These checks cover the requested output, all memo rules, and the main data trap.
+
+20. **Which known or feared failure modes require explicit prevention?**
+    - **Chosen answer:** Using the prior report as incident evidence; trusting vibration under the temperature sensor ID; evaluating calibration at execution time; hiding or causally using overdue sensor values; treating equality as exceedance; inventing shift boundaries, component failures, or approvals; issuing remediation as an order; mismatching JSON/Markdown; and processing unrelated shifts.
+    - **Why:** The memo identifies missed calibration as a serious prior failure. The remaining risks follow directly from the supplied schemas, example, and requested dual outputs.
+
+## Deferred confirmations
+
+Before generalizing this workflow beyond the supplied fixture, the requester should confirm the official shift schedule, whether calibration validity is day- or timestamp-granular, the canonical JSON schema, and the organization-approved remediation vocabulary. None of these unknowns prevents a bounded first run under the assumptions above.
diff --git a/examples/cases/quality-anomaly/TASK.md b/examples/cases/quality-anomaly/TASK.md
new file mode 100644
index 0000000000000000000000000000000000000000..376b342e282524fabf4de36e67e46f0c8de11ed1
--- /dev/null
+++ b/examples/cases/quality-anomaly/TASK.md
@@ -0,0 +1,21 @@
+# Task: Line 3 quality anomaly response report for 2026-08-27 night shift
+
+You are the manufacturing quality-analysis assistant. Prepare the auditable anomaly evidence summary and response report for **incident_date=2026-08-27**, **line=3**, **shift=night** for review by the Quality Engineer.
+
+Rules (from `behaviors/`): use the supplied thresholds as the sole numeric rule authority; independently verify the bound MES anomaly before analysis; align sensor evidence only to the bound line and supplied overnight incident window; evaluate calibration by measure at measurement time and never use an overdue sensor to support causation; make only evidence-bounded candidate-cause claims; and leave every remediation pending with the exact statement **“requires Quality Engineer approval”**. Use `examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md` only as a format example, never as evidence. Assumptions adopted while the requester was unavailable are recorded in `examples/cases/quality-anomaly/ASSUMPTIONS.md`.
+
+Do the work with auditable shell commands (`cat`, `mkdir -p`, and `python3` using CSV/YAML/date/JSON handling) from the repository root. Do not modify anything under `examples/cases/quality-anomaly/materials/`.
+
+1. **Bind the run and inspect authority files** — set and print the per-run bindings **incident_date=2026-08-27**, **line=3**, **shift=night**, **MES=examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv**, **SENSORS=examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv**, **CALIBRATION=examples/cases/quality-anomaly/materials/data/calibration-log.csv**, **THRESHOLDS=examples/cases/quality-anomaly/materials/data/thresholds.yaml**, and **OUTPUT_DIR=build/quality-anomaly**. Read `examples/cases/quality-anomaly/materials/memo.md`, `examples/cases/quality-anomaly/materials/notes.txt`, the four data files, and `examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md`. Create `build/quality-anomaly/` with `mkdir -p`.
+2. **Verify the MES anomaly mechanically** — with `python3`, parse `examples/cases/quality-anomaly/materials/data/thresholds.yaml` and `examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv`; filter by all three bound keys (`date`, integer `line`, and `shift`); require exactly one row; recompute `100 * defects / units` and verify it agrees with `defect_rate_pct` within 0.05 percentage point; classify an anomaly only when the recorded rate is strictly greater than `defect_rate_pct_threshold`. Print the selected row, recomputed rate, threshold, and verdict. Stop without finalizing either deliverable if the row is missing/ambiguous, internally inconsistent, or not anomalous.
+3. **Extract time-aligned sensor exceedances mechanically** — with `python3`, parse `examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv`; keep only integer `line == 3` and the supplied continuous overnight rows from **2026-08-27T20:00 through 2026-08-28T03:00 inclusive**. Do not infer a broader corporate shift schedule. For `temp_c` and `vibration_mm_s`, compare each value strictly (`>`) with its configured maximum, record every exceedance timestamp/value, group consecutive hourly exceedances into inclusive intervals, and record each peak and peak timestamp. Print the filtered window and derived exceedances.
+4. **Gate evidence by calibration mechanically** — with `python3`, parse `examples/cases/quality-anomaly/materials/data/calibration-log.csv` and join each measure to the unique calibration row whose `measure` matches (`temp_c` or `vibration_mm_s`), regardless of the row-level `sensor_id` in the sensor CSV. At every relevant measurement timestamp, compute whole elapsed days since `last_calibrated`; classify the measure `trusted` when age is at most `calibration_interval_days` and `untrusted` when older. Record the calibration sensor ID, date, ages, status, and `eligible_for_causal_use`. An untrusted measure's observed exceedances must remain disclosed but must not enter causal support. Stop for human review if a measure has zero/multiple calibration records, a future calibration date, or inconsistent trust status across its relevant interval.
+5. **Write the structured evidence first** — create `build/quality-anomaly/anomaly-2026-08-27.json` containing: `incident` (`date`, `line`, `shift`, `observed_sensor_window`); `sources` (all input paths); `thresholds`; `mes` (selected row, recomputed rate, and `is_anomaly`); `sensor_evidence` keyed by measure (unit, maximum, exceedance samples, contiguous intervals, peak, calibration record/ages/status, and `eligible_for_causal_use`); `candidate_root_cause` (`status`, `statement`, `supporting_trusted_measures`, and `limitations`); `remediation` as a list of items each with `action`, `approval_required: true`, `approval_authority: "Quality Engineer"`, and `approval_status: "pending"`; and `validation`. The cause must be `undetermined` if no trustworthy evidence supports a bounded candidate. Do not assert a specific failed component without supplied evidence.
+6. **Render the response report from the JSON** — write `build/quality-anomaly/anomaly-report-2026-08-27.md` in the concise English format of `examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md`, using exactly these sections: title, `## Anomaly`, `## Sensor evidence`, `## Root cause (candidate)`, and `## Remediation (requires Quality Engineer approval)`. Include the selected production facts and threshold; each measure's exceedance interval/peak and calibration trust basis; explicit `untrusted` wording and exclusion from causal judgment where applicable; a correlation-bounded candidate or `undetermined`; and `Approval: pending`. Every remediation item must include the exact statement **“requires Quality Engineer approval”** and must not claim execution or approval.
+7. **Validate both artifacts mechanically** — parse the JSON with `python3 -m json.tool`; use `python3` to recompute the selected MES result, exceedance samples/intervals/peaks, calibration ages/statuses, and causal eligibility directly from the four data files; compare them with JSON; then verify that every material numeric fact, trust label, candidate-cause limitation, remediation action, approval authority/status, and source incident in Markdown agrees with JSON. Confirm that no untrusted measure appears in `supporting_trusted_measures`, no unrelated shift appears, and both filenames match **2026-08-27**. Set `validation.status` to `passed` only after all checks pass and re-run `python3 -m json.tool` after the update.
+8. **Do not perform remediation** — this task produces analysis artifacts only. Do not contact people, change manufacturing systems, issue work orders, recalibrate sensors, or state that any approval or action occurred.
+
+Reply with a short summary containing the verified incident and defect-rate verdict, which measures were trusted/untrusted, the candidate-cause status, the pending Quality Engineer approval status, and these two paths:
+
+- `build/quality-anomaly/anomaly-2026-08-27.json`
+- `build/quality-anomaly/anomaly-report-2026-08-27.md`
diff --git a/examples/cases/quality-anomaly/behaviors/bound-cause-to-trusted-evidence/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/bound-cause-to-trusted-evidence/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..ed9973689f0ea16d8ff850a90eb9ca7c90b9ee14
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/bound-cause-to-trusted-evidence/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: bound-cause-to-trusted-evidence
+
+## 1. Intent
+Keep root-cause language proportional to the supplied evidence and distinguish a correlated candidate from a confirmed equipment failure.
+
+## 2. Evidence
+The structured evidence records a candidate status, statement, explicit supporting trusted measures, and limitations after calibration gating; the report renders the same bounded claim under `Root cause (candidate)`.
+
+## 3. Decision
+- `true`: The cause is labeled a candidate, cites only trusted supporting measures, states material limitations, and becomes `undetermined` when no trustworthy causal evidence remains.
+- `false`: A cause is presented as confirmed, an unsupported component failure is named, an untrusted measure supplies support, or uncertainty is omitted.
+- `na`: The trajectory makes no causal assessment.
+
+## 4. Execution
+Draft the causal assessment only after MES verification, time alignment, exceedance calculation, and calibration gating; separate observed correlation from confirmation.
+
+## 5. Recovery
+Downgrade unsupported certainty, remove untrusted or absent support, add the evidence limitation, or set the cause to `undetermined`; regenerate both artifacts and revalidate them.
+
+## 6. Failure Modes
+Copying the coolant diagnosis from the previous report, equating threshold coincidence with proof, inventing a failed station/component, or masking insufficient evidence with confident prose.
diff --git a/examples/cases/quality-anomaly/behaviors/gate-causation-by-calibration/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/gate-causation-by-calibration/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..7d6687d35695584d296763add90d4fc6bb413d0a
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/gate-causation-by-calibration/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: gate-causation-by-calibration
+
+## 1. Intent
+Prevent expired or mismapped sensor calibration from supporting a root-cause candidate while keeping observed evidence transparent.
+
+## 2. Evidence
+The trajectory joins each analyzed measure to the unique `measure` row in `examples/cases/quality-anomaly/materials/data/calibration-log.csv`, computes elapsed whole days at relevant measurement timestamps using the configured interval, records the calibration sensor ID/date/ages and trust verdict, and records causal eligibility before drafting a cause.
+
+## 3. Decision
+- `true`: Every measure is mapped by measure, age is evaluated at measurement time, values older than the allowed interval are labeled `untrusted` and disclosed but absent from causal support, and only trusted measures support the candidate cause.
+- `false`: Calibration is skipped, evaluated at workflow execution time, mapped from the sensor row ID across measures, expired evidence is hidden, or an untrusted measure supports causation.
+- `na`: No sensor evidence is analyzed or no causal assessment is made.
+
+## 4. Execution
+Perform the calibration join and trust calculation after time-aligned exceedance extraction and before candidate-cause judgment; fail closed on missing, duplicate, future-dated, or inconsistent calibration evidence.
+
+## 5. Recovery
+Remove unsupported causal claims, remap calibration records by measure, recompute incident-time ages and trust, then regenerate the structured evidence and report; escalate unresolved calibration ambiguity for human review.
+
+## 6. Failure Modes
+Treating the row-level temperature sensor ID as vibration calibration, using today's date, treating day 90 as expired, silently dropping overdue readings, or describing untrusted vibration as causal.
diff --git a/examples/cases/quality-anomaly/behaviors/keep-report-evidence-auditable/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/keep-report-evidence-auditable/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..0b418a50e3aeea4b28fe8742f4f7b850a13a5771
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/keep-report-evidence-auditable/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: keep-report-evidence-auditable
+
+## 1. Intent
+Produce mutually consistent structured and human-readable anomaly artifacts whose facts can be reproduced from the supplied incident sources.
+
+## 2. Evidence
+The trajectory writes `build/quality-anomaly/anomaly-2026-08-27.json` before rendering `build/quality-anomaly/anomaly-report-2026-08-27.md`, records all source paths and derivations, parses the JSON, and mechanically compares MES facts, sensor intervals/peaks, calibration trust, causal support, remediation, and approval status across sources and outputs.
+
+## 3. Decision
+- `true`: Both incident-dated files exist, parse, concern only the bound incident, reproduce the source calculations, agree on every material fact and decision, and record a passed validation.
+- `false`: A file is missing or malformed, prose is drafted from memory, the files disagree, sources/derivations are absent, unrelated shifts appear, or validation passes despite a mismatch.
+- `na`: The trajectory does not produce the anomaly JSON and report pair.
+
+## 4. Execution
+Serialize source-derived structured evidence first, render the report from it in the previous deliverable's section format, then run source-to-JSON and JSON-to-Markdown consistency checks before replying.
+
+## 5. Recovery
+Treat freshly recomputed source evidence as authoritative, correct or regenerate the JSON, re-render Markdown, and repeat all validations without modifying source materials or performing remediation.
+
+## 6. Failure Modes
+Drafting prose first and backfilling JSON, copying prior-incident values, mismatched dates/rates/peaks/trust labels, omitting limitations or approval status, or declaring success before mechanical validation.
diff --git a/examples/cases/quality-anomaly/behaviors/require-quality-engineer-approval/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/require-quality-engineer-approval/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..94735f4fcc72cad618089dcb026e0ec3cf39ae25
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/require-quality-engineer-approval/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: require-quality-engineer-approval
+
+## 1. Intent
+Prevent the analysis assistant from authorizing or claiming execution of manufacturing remediation.
+
+## 2. Evidence
+Every structured remediation item records `approval_required: true`, `approval_authority: "Quality Engineer"`, and `approval_status: "pending"`; the report section and each action include “requires Quality Engineer approval,” and the trajectory performs no external operational action.
+
+## 3. Decision
+- `true`: All remediation remains a proposal pending Quality Engineer approval, the required statement is explicit for every action, and no approval or execution is invented.
+- `false`: Any action is issued as an order, marked approved/completed without evidence, omits the required approval statement, or is actually performed by the workflow.
+- `na`: The trajectory neither proposes nor performs manufacturing remediation.
+
+## 4. Execution
+Apply the approval gate while serializing each remediation item and preserve it verbatim when rendering Markdown; restrict the workflow to artifact creation.
+
+## 5. Recovery
+Stop any attempted operational step, change unauthorized language and statuses to pending proposals, add the required approval statement to every item, and regenerate and revalidate both artifacts.
+
+## 6. Failure Modes
+Copying imperative maintenance language, treating report generation as authorization, claiming verbal or assumed approval, contacting operations, changing equipment, or omitting approval from one of several actions.
diff --git a/examples/cases/quality-anomaly/behaviors/use-authoritative-thresholds/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/use-authoritative-thresholds/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..8e32cc42328707d5ee24d0963590ef9dee1e9421
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/use-authoritative-thresholds/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: use-authoritative-thresholds
+
+## 1. Intent
+Ensure anomaly, sensor, and calibration decisions use the supplied current threshold configuration rather than memory, the previous report, or invented limits.
+
+## 2. Evidence
+The trajectory reads `examples/cases/quality-anomaly/materials/data/thresholds.yaml` before classification and records its line, defect-rate threshold, per-measure maxima, calibration interval, and source path in the structured evidence.
+
+## 3. Decision
+- `true`: Every threshold and calibration interval used in the artifacts matches the read configuration, and strict exceedance is applied.
+- `false`: A limit is hardcoded, remembered, copied from the prior report, invented, or interpreted as inclusive despite the configuration's “above” rule.
+- `na`: The trajectory does not classify a manufacturing quality anomaly or sensor evidence.
+
+## 4. Execution
+Make the threshold-file read a required predecessor to MES classification, sensor comparison, calibration gating, and drafting.
+
+## 5. Recovery
+Discard derived classifications, re-read the threshold file, recompute all dependent evidence, and regenerate both artifacts.
+
+## 6. Failure Modes
+Using 3.1% or 80.2 °C from the prior report, treating equality as exceedance, applying a limit to the wrong measure, or using an undocumented calibration interval.
diff --git a/examples/cases/quality-anomaly/behaviors/verify-bound-mes-anomaly/BEHAVIOR.md b/examples/cases/quality-anomaly/behaviors/verify-bound-mes-anomaly/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..08b18f1660f90ef47535da4d4c89dd201a5155ef
--- /dev/null
+++ b/examples/cases/quality-anomaly/behaviors/verify-bound-mes-anomaly/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: verify-bound-mes-anomaly
+
+## 1. Intent
+Prevent a response report from being finalized for an unverified, wrong, ambiguous, or internally inconsistent shift record.
+
+## 2. Evidence
+The trajectory filters `examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv` by the bound date, line, and shift; records a match count of one; recomputes the defect rate from units and defects; and compares the recorded rate strictly with the configured threshold before sensor analysis.
+
+## 3. Decision
+- `true`: Exactly one bound MES row is selected, its recorded and recomputed rates agree within 0.05 percentage point, and the rate is strictly above the configured threshold before downstream analysis proceeds.
+- `false`: The wrong or multiple shifts are used, the rate is assumed from notes, inconsistent counts are ignored, or a non-anomalous shift receives a finalized anomaly report.
+- `na`: The trajectory does not produce a shift-level quality-anomaly response.
+
+## 4. Execution
+Make bound-key selection, uniqueness, rate reproduction, and threshold classification non-removable predecessors to sensor analysis and artifact creation.
+
+## 5. Recovery
+Stop downstream work, re-read the MES and threshold sources, reselect by all bound keys, and continue only when a unique, consistent, above-threshold row is established; otherwise report the evidence problem for human review.
+
+## 6. Failure Modes
+Scanning and reporting unrelated shifts, matching date without line/shift, trusting a precomputed rate despite inconsistent counts, or using `>=` instead of `>`.

tokens used
42,327
Defined the quality-anomaly workflow without performing the task itself.

Created:

- [ASSUMPTIONS.md](/Users/hongmartin/orca/projects/open-workflow/examples/cases/quality-anomaly/ASSUMPTIONS.md) — 20 numbered questions across four grilling rounds, with chosen answers and evidence-based rationale.
- [TASK.md](/Users/hongmartin/orca/projects/open-workflow/examples/cases/quality-anomaly/TASK.md) — auditable steps using the supplied materials and writing only under `build/quality-anomaly/`.
- Six behavior contracts under [behaviors/](/Users/hongmartin/orca/projects/open-workflow/examples/cases/quality-anomaly/behaviors):
  - authoritative thresholds
  - bound MES anomaly verification
  - calibration-gated causation
  - evidence-bounded cause claims
  - Quality Engineer approval
  - auditable report/JSON consistency

All behavior files pass the repository parser with the required six sections and complete `true`/`false`/`na` decisions. No anomaly outputs or remediation actions were produced.

Next commands:

```bash
python3 -m uvicorn adapters.proxy.server:app --port 8787 &
codex exec 'Read examples/cases/quality-anomaly/TASK.md and carry it out exactly as written.'   # first run, captured by the proxy
# verify the outputs by hand, then:
$ow-traces · $ow-compile-trace quality-anomaly · $ow-bench quality-anomaly
python3 -m core.build run build/quality-anomaly --request "..." --escalate codex        # new inputs via the front agent
```

The compiled `build/quality-anomaly/quality-anomaly.work` will be the HOW: it identifies which verified steps became deterministic code, which remain agent-driven, and can be edited and recompiled. 🎯
