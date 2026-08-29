OpenAI Codex v0.150.1
--------
workdir: /Users/hongmartin/orca/projects/open-workflow
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR]
reasoning effort: none
reasoning summaries: none
session id: 01a04b29-dd70-7e90-8134-4320c525d897
--------
user
$ow-define invoice refund approval decisions (customer support)

Context for this run: the requester is a complete beginner — no prompt-engineering knowledge — who only dropped their work materials into examples/cases/refund-approval/materials/ (a memo from their lead, their own notes, a previous finished deliverable, and the raw data files). They are NOT available to answer follow-up questions right now.

So run the grilling interview against the materials instead of the person: for every round, write the numbered questions AND take your own recommended answer, grounded in the memo/notes/previous deliverable. Record each question, the answer you chose and why in examples/cases/refund-approval/ASSUMPTIONS.md (so the requester can correct them later). Then write examples/cases/refund-approval/TASK.md (steps must reference files under examples/cases/refund-approval/materials/... and write outputs under build/refund-approval/), and one BEHAVIOR.md per rule under examples/cases/refund-approval/behaviors/<kebab-name>/ in the six-section format. Do not perform the task itself.
codex
I’m using `ow-define` and its required `grilling` skill. Since you’re unavailable, I’ll treat the supplied materials as the interviewee: each round will contain numbered questions, a recommended answer, and evidence-based rationale recorded in `ASSUMPTIONS.md`. I’ll produce only the specification artifacts, not execute the refund decisions.
exec
/bin/zsh -lc "sed -n '1,240p' .agents/skills/ow-define/SKILL.md && sed -n '1,260p' .agents/skills/grilling/SKILL.md && printf '\\nFILES\\n' && rg --files examples/cases/refund-approval/materials examples/customer-renewal adapters/agentbehavior | sort" in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 0ms:
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

FILES
adapters/agentbehavior/README.md
adapters/agentbehavior/__init__.py
adapters/agentbehavior/parser.py
examples/cases/refund-approval/materials/data/orders.json
examples/cases/refund-approval/materials/data/payments.csv
examples/cases/refund-approval/materials/data/refund-policy-v3.md
examples/cases/refund-approval/materials/data/refund-requests.json
examples/cases/refund-approval/materials/memo-from-manager.md
examples/cases/refund-approval/materials/notes.txt
examples/cases/refund-approval/materials/previous/decision-RR-2026-0712-01.md
examples/customer-renewal/TASK.md
examples/customer-renewal/behaviors/use-current-pricing-policy/BEHAVIOR.md
examples/customer-renewal/behaviors/verify-current-contract/BEHAVIOR.md
examples/customer-renewal/data/crm/contracts.json
examples/customer-renewal/data/pricing/pricing_v1_legacy.yaml
examples/customer-renewal/data/pricing/pricing_v2.yaml
examples/customer-renewal/data/usage/usage-2026-07.csv
examples/customer-renewal/domain.linkml.yaml
examples/customer-renewal/work.yaml

codex
The materials inventory is complete: manager memo, personal notes, a prior approved-style decision, four raw-data/policy files, and no need for synthetic fixtures. I’m now resolving the interview tree in dependency order—goal/consumer first, then inputs and workflow, then policy invariants, outputs, and failure handling.
exec
/bin/zsh -lc "for f in examples/cases/refund-approval/materials/memo-from-manager.md examples/cases/refund-approval/materials/notes.txt examples/cases/refund-approval/materials/previous/decision-RR-2026-0712-01.md examples/cases/refund-approval/materials/data/refund-policy-v3.md examples/cases/refund-approval/materials/data/orders.json examples/cases/refund-approval/materials/data/refund-requests.json examples/cases/refund-approval/materials/data/payments.csv examples/customer-renewal/TASK.md examples/customer-renewal/behaviors/use-current-pricing-policy/BEHAVIOR.md examples/customer-renewal/behaviors/verify-current-contract/BEHAVIOR.md adapters/agentbehavior/parser.py; do printf '\\n===== %s =====\\n' \""'$f"; sed -n '"'1,320p' \""'$f"; done' in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 0ms:

===== examples/cases/refund-approval/materials/memo-from-manager.md =====
# CS 팀장 메모

환불 요청 처리 이렇게 해왔어요. 규칙은 policy 폴더 v3 문서가 정식이고 아래는 요약.
- 결제일로부터 7일 이내: 전액 환불. 8~30일: 50% 부분 환불. 30일 넘으면 불가(단, 중복결제는 기간 상관없이 전액).
- 중복결제 판단: 같은 주문번호로 payments에 성공 결제가 2건 이상.
- 환불 금액이 100,000원 넘으면 재무팀 승인 대기로 넘김(우리가 확정 못 함). 그 밑은 우리가 확정.
- 증빙(영수증 번호)이 payments에 없으면 "증빙 불일치"로 보류.
- 판정서는 previous 폴더 양식대로. 요청 하나당 md 하나, 그리고 판정 근거 json.

===== examples/cases/refund-approval/materials/notes.txt =====
- 오늘 2026-08-29
- 이번 주 처리할 건: RR-2026-0827-03 (고객이 두 번 결제됐다고 화남)
- 파일명: decision-<요청ID>.md, decision-<요청ID>.json

===== examples/cases/refund-approval/materials/previous/decision-RR-2026-0712-01.md =====
# Refund Decision — RR-2026-0712-01

- Order: ORD-76550 (CUST-2150), paid 2026-07-01, 45,000 KRW, receipt RC-87001 (matched)
- Request date: 2026-07-12 → 11 days after payment

## Decision
Partial refund 50% = 22,500 KRW — Policy v3 clause 2. Under 100,000 KRW → finalized by CS (clause 4 not triggered).

## Next steps
Refund issued to original payment method within 5 business days. Customer notified with template CS-R2.

===== examples/cases/refund-approval/materials/data/refund-policy-v3.md =====
# Refund Policy v3 (effective 2026-04-01)
1. Full refund if the refund request date is within 7 days of the payment date.
2. 50% partial refund if within 8–30 days.
3. No refund after 30 days, EXCEPT duplicate charges: a duplicate charge (two or more successful payments for the same order_id) is refunded in full for the duplicate amount regardless of age.
4. Refund amount over 100,000 KRW requires Finance approval: status "pending_finance_approval" — CS may not finalize.
5. The receipt number in the request must match a payment record; otherwise status "on_hold_evidence_mismatch".
6. Every decision memo must cite the policy clause numbers applied.

===== examples/cases/refund-approval/materials/data/orders.json =====
{"orders": [
  {"order_id": "ORD-77001", "customer_id": "CUST-2201", "item": "Pro plan (annual)", "amount_krw": 264000, "ordered_at": "2026-08-20"},
  {"order_id": "ORD-77002", "customer_id": "CUST-2202", "item": "Add-on storage 1TB", "amount_krw": 36000, "ordered_at": "2026-07-15"},
  {"order_id": "ORD-77003", "customer_id": "CUST-2203", "item": "Team plan (monthly)", "amount_krw": 89000, "ordered_at": "2026-08-25"}
]}

===== examples/cases/refund-approval/materials/data/refund-requests.json =====
{"requests": [
  {"request_id": "RR-2026-0827-03", "order_id": "ORD-77001", "customer_id": "CUST-2201", "requested_at": "2026-08-27", "reason": "charged twice", "receipt_no": "RC-88102", "requested_amount_krw": 264000},
  {"request_id": "RR-2026-0826-01", "order_id": "ORD-77002", "customer_id": "CUST-2202", "requested_at": "2026-08-26", "reason": "no longer needed", "receipt_no": "RC-88103", "requested_amount_krw": 36000},
  {"request_id": "RR-2026-0828-02", "order_id": "ORD-77003", "customer_id": "CUST-2203", "requested_at": "2026-08-28", "reason": "wrong plan", "receipt_no": "RC-99999", "requested_amount_krw": 89000}
]}

===== examples/cases/refund-approval/materials/data/payments.csv =====
payment_id,order_id,status,amount_krw,paid_at,receipt_no
PAY-90011,ORD-77001,success,264000,2026-08-20,RC-88101
PAY-90012,ORD-77001,success,264000,2026-08-20,RC-88102
PAY-90013,ORD-77002,success,36000,2026-07-15,RC-88103
PAY-90014,ORD-77003,failed,89000,2026-08-25,
PAY-90015,ORD-77003,success,89000,2026-08-25,RC-88105

===== examples/customer-renewal/TASK.md =====
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

===== examples/customer-renewal/behaviors/use-current-pricing-policy/BEHAVIOR.md =====
# BEHAVIOR: use-current-pricing-policy

## 1. Intent
Guarantees that pricing calculations apply the current active enterprise pricing table (`rules.pricing_v2`) rather than legacy discount structures.

## 2. Evidence
Invocation of `rules.pricing_v2` with live policy parameters in the trajectory.

## 3. Decision
- `true`: Active pricing policy rule engine was queried and applied.
- `false`: Custom unverified pricing was hallucinated or legacy table was applied.
- `na`: Trajectory does not perform pricing calculations.

## 4. Execution
Enforced as a deterministic Rule engine executor step.

## 5. Recovery
Re-derive offer using standard rule engine `rules.pricing_v2`.

## 6. Failure Modes
LLM hallucinating custom percentage discounts outside authorized bands.

===== examples/customer-renewal/behaviors/verify-current-contract/BEHAVIOR.md =====
# BEHAVIOR: verify-current-contract

## 1. Intent
Ensure that any renewal offer or contract analysis looks up the active, current customer contract from the CRM before computing renewal terms.

## 2. Evidence
Evidence consists of a `crm.lookup_contract` step occurring before `services.usage.calculate` or `rules.pricing_v2` steps in the execution trajectory.

## 3. Decision
- `true`: `crm.lookup_contract` executed successfully and returned active contract data prior to pricing logic.
- `false`: Pricing or drafting occurred without querying the active contract, or queried a cached/stale record.
- `na`: Trajectory does not involve contract renewals.

## 4. Execution
Enforced at compile-time as a non-removable workflow transition dependency and verified by post-hoc trajectory judges.

## 5. Recovery
If missing, halt execution and escalate to CRM lookup connector or prompt reviewer.

## 6. Failure Modes
Using hardcoded contract terms or relying on LLM memory from previous turns.

===== adapters/agentbehavior/parser.py =====
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
The key trap is clear: the selected request is a valid duplicate charge for 264,000 KRW, but the workflow must not finalize it because the amount exceeds 100,000 KRW. I’m encoding that as separate process contracts—evidence validation, duplicate classification, eligibility calculation, and finance escalation—so a lucky final label cannot pass if the required checks were skipped.
apply patch
patch: completed
/Users/hongmartin/orca/projects/open-workflow/examples/cases/refund-approval/ASSUMPTIONS.md
/Users/hongmartin/orca/projects/open-workflow/examples/cases/refund-approval/TASK.md
/Users/hongmartin/orca/projects/open-workflow/examples/cases/refund-approval/behaviors/apply-refund-eligibility-rules/BEHAVIOR.md
/Users/hongmartin/orca/projects/open-workflow/examples/cases/refund-approval/behaviors/enforce-finance-approval-threshold/BEHAVIOR.md
/Users/hongmartin/orca/projects/open-workflow/examples/cases/refund-approval/behaviors/keep-decision-artifacts-auditable/BEHAVIOR.md
/Users/hongmartin/orca/projects/open-workflow/examples/cases/refund-approval/behaviors/prove-duplicate-from-successful-payments/BEHAVIOR.md
/Users/hongmartin/orca/projects/open-workflow/examples/cases/refund-approval/behaviors/use-authoritative-policy-v3/BEHAVIOR.md
/Users/hongmartin/orca/projects/open-workflow/examples/cases/refund-approval/behaviors/verify-receipt-before-decision/BEHAVIOR.md
diff --git a/examples/cases/refund-approval/ASSUMPTIONS.md b/examples/cases/refund-approval/ASSUMPTIONS.md
new file mode 100644
index 0000000000000000000000000000000000000000..b354d0ff2f4dc0432b96252f46d04d1f0960835b
--- /dev/null
+++ b/examples/cases/refund-approval/ASSUMPTIONS.md
@@ -0,0 +1,133 @@
+# Assumptions: invoice refund approval decisions
+
+This file records the grilling interview conducted against the supplied work materials because the requester was unavailable. Each answer is a recommended assumption to verify or correct before treating the specification as final.
+
+## Round 1 — Goal and consumer
+
+### 1. What is the single-sentence goal?
+
+**Chosen answer:** For the per-run refund request ID, produce an auditable customer-support refund decision memo and a machine-readable evidence record that applies Refund Policy v3 without issuing a refund or contacting the customer.
+
+**Why:** `materials/memo-from-manager.md` asks for one decision memo and one evidence JSON per request. The materials describe decision preparation, not payment execution or customer communication.
+
+### 2. Who consumes the result?
+
+**Chosen answer:** Customer Support consumes finalized or held decisions; Finance consumes decisions whose calculated refund exceeds 100,000 KRW.
+
+**Why:** The manager memo says CS may finalize amounts below the threshold, while larger amounts must be handed to Finance as pending approval.
+
+### 3. Which request is in scope for this run?
+
+**Chosen answer:** The per-run parameter is **REQUEST_ID = RR-2026-0827-03**. Process exactly that request, not every row in the input file.
+
+**Why:** `materials/notes.txt` explicitly identifies this as this week's case and gives singular output naming rules.
+
+## Round 2 — Inputs and authority
+
+### 4. What are the authoritative inputs?
+
+**Chosen answer:** Read `materials/data/refund-requests.json` for the request, `materials/data/orders.json` for the order/customer record, `materials/data/payments.csv` for receipt and successful-payment evidence, and `materials/data/refund-policy-v3.md` for all decision rules.
+
+**Why:** These are the raw files supplied for the work. The manager memo explicitly says the v3 policy document is official.
+
+### 5. How should the memo, notes, and previous deliverable be used?
+
+**Chosen answer:** Use `materials/memo-from-manager.md` and `materials/notes.txt` to scope and parameterize the run, and use `materials/previous/decision-RR-2026-0712-01.md` only as the memo format/style reference. Never treat any of them as overriding policy v3.
+
+**Why:** The manager calls the memo a summary and policy v3 the formal authority; the prior deliverable demonstrates headings and wording but is not a rules source.
+
+### 6. What values vary per run?
+
+**Chosen answer:** `REQUEST_ID` varies per run. All joined request, order, payment, dates, amounts, receipt, reason, classification, status, and output filenames derive from it. Policy path and output directory remain fixed until explicitly versioned.
+
+**Why:** The notes select one request ID and define filenames as `decision-<request ID>.*`.
+
+### 7. What date controls age, and how are boundaries calculated?
+
+**Chosen answer:** Use the matched successful payment's `paid_at` and the request's `requested_at`; calculate whole calendar-day difference as request date minus payment date. Interpret “within 7 days” as 0–7 inclusive, “8–30 days” as 8–30 inclusive, and “after 30 days” as 31+.
+
+**Why:** Policy v3 explicitly speaks in those ranges and the previous decision demonstrates 2026-07-01 to 2026-07-12 as 11 days. Today's date in the notes does not determine eligibility.
+
+## Round 3 — Ordered work and decision precedence
+
+### 8. What ordered steps should a competent reviewer follow?
+
+**Chosen answer:** Select exactly one request; join and cross-check the order/customer; match the receipt to a payment; count successful payments for the order; classify duplicate status; calculate the policy refund; apply the Finance threshold; then write JSON evidence before drafting the memo from that evidence.
+
+**Why:** This order makes every policy predicate observable and prevents prose from becoming the source of truth.
+
+### 9. What happens if a receipt does not match?
+
+**Chosen answer:** Stop substantive eligibility and approval determination, record `on_hold_evidence_mismatch`, calculate no refund amount, cite clause 5, and do not infer a receipt from another payment.
+
+**Why:** Policy v3 clause 5 mandates the hold. The supplied ORD-77003 case is a deliberate example of a request receipt differing from the successful payment receipt.
+
+### 10. How is a duplicate charge established?
+
+**Chosen answer:** Count payment rows with the same `order_id` and `status == success`; two or more establishes a duplicate. Customer reason text alone is not evidence. The refundable duplicate amount is the matched successful payment amount, limited to the amount requested; any inconsistent amounts must be escalated rather than guessed.
+
+**Why:** The memo and clause 3 define duplicates using successful payments, and the current case has two 264,000 KRW successes. The materials do not authorize refunding more than requested or inventing a value when amounts conflict.
+
+### 11. Which rule takes precedence for old duplicate charges?
+
+**Chosen answer:** A verified duplicate receives a full refund for the duplicate amount regardless of age under clause 3; the ordinary age bands in clauses 1–3 apply only when the request is not a duplicate.
+
+**Why:** Clause 3 expressly creates the age exception.
+
+### 12. Does Finance approval change refund eligibility?
+
+**Chosen answer:** No. First calculate the eligible refund amount, then set `pending_finance_approval` if it is over 100,000 KRW. CS must not label it finalized or claim the refund was issued.
+
+**Why:** Clause 4 is an approval/status rule based on the calculated amount, not an eligibility denial.
+
+## Round 4 — Mechanics, judgment, and outputs
+
+### 13. Which steps are mechanical and which require judgment?
+
+**Chosen answer:** JSON/CSV selection, joins, receipt matching, successful-payment counting, date arithmetic, percentage calculation, threshold comparison, and JSON serialization are mechanical. Explaining the result and recovery for inconsistent/missing data are judgment steps constrained by the evidence and behavior contracts.
+
+**Why:** All numeric and categorical rules are explicit. Only concise explanation and unenumerated data-quality exceptions need bounded judgment.
+
+### 14. What exact files and fields constitute “done”?
+
+**Chosen answer:** Write `build/refund-approval/decision-<REQUEST_ID>.json` first with source paths, identity fields, matched payment evidence, successful payment IDs/count, day difference, duplicate flag, applied clauses, calculated amount, status, authority, and rationale; then write `build/refund-approval/decision-<REQUEST_ID>.md` with the previous deliverable's title, factual summary, `## Decision`, and `## Next steps`.
+
+**Why:** The memo requires one Markdown decision and one evidence JSON, the notes give exact filenames, and policy clause 6 requires clause citations.
+
+### 15. What language and money representation should outputs use?
+
+**Chosen answer:** Follow the previous deliverable in English; store KRW amounts as integer won in JSON and render them with thousands separators plus `KRW` in Markdown.
+
+**Why:** The repository is maintained in English, the prior deliverable is English, and every supplied amount is integral KRW.
+
+### 16. What must the memo say for each terminal status?
+
+**Chosen answer:** For `finalized`, state CS finalization and the supported next-step template only if the materials authorize it. For `pending_finance_approval`, state that the calculated refund is pending Finance approval and has not been finalized or issued. For `on_hold_evidence_mismatch`, state that evidence correction is required and no refund decision is finalized.
+
+**Why:** This preserves the authority boundary. The prior memo's “refund issued” wording is not safe for a pending or held case.
+
+## Round 5 — Acceptance and failure recovery
+
+### 17. What are the acceptance criteria?
+
+**Chosen answer:** Exactly one request is processed; all required sources are read; joins agree; receipt is verified before eligibility; duplicate status uses successful payments only; policy v3 and applicable clause numbers are cited; amount/status/authority are consistent; JSON and Markdown agree; and no external refund, approval, or notification action occurs.
+
+**Why:** These criteria cover the manager's explicit rules and make behavior compliance independently reviewable.
+
+### 18. Which failure modes must be prevented?
+
+**Chosen answer:** Processing the wrong or multiple requests, treating customer claims as proof, counting failed payments, using order date instead of payment date, applying age denial to a duplicate, finalizing an over-cap refund, silently substituting a receipt, citing no clauses, disagreeing outputs, and claiming downstream actions occurred.
+
+**Why:** Each would violate a supplied rule or make the audit trail unreliable; several traps are represented in the raw fixture data.
+
+### 19. What should happen on missing, duplicate, or inconsistent records?
+
+**Chosen answer:** Do not guess. Stop before drafting a normal decision, preserve observed evidence in the JSON when possible, state the unresolved inconsistency, and require human review. A missing receipt match specifically uses `on_hold_evidence_mismatch`; other unmodeled integrity failures use a clearly labeled review-required error rather than a policy status invented by the agent.
+
+**Why:** Only the receipt-mismatch hold has a prescribed status. The materials provide no safe resolution rule for conflicting customer/order/payment identities or ambiguous rows.
+
+### 20. Are any facts intentionally unknown?
+
+**Chosen answer:** The exact Finance routing mechanism, customer notification template for this case, refund-processing API, and SLA are unknown and out of scope. The agent must not fabricate or execute them.
+
+**Why:** The materials specify decision artifacts and a Finance status but provide no connectors, destinations, templates, or operational instructions for those actions.
diff --git a/examples/cases/refund-approval/TASK.md b/examples/cases/refund-approval/TASK.md
new file mode 100644
index 0000000000000000000000000000000000000000..09ca3446e24191b38b6e7f475cc2ebe5b23d698d
--- /dev/null
+++ b/examples/cases/refund-approval/TASK.md
@@ -0,0 +1,21 @@
+# Task: refund approval decision for request RR-2026-0827-03
+
+You are the customer-support refund decision assistant. Prepare the refund decision artifacts for per-run parameter **REQUEST_ID = RR-2026-0827-03** for Customer Support and, when required, Finance review. Do not issue a refund, approve on Finance's behalf, or contact the customer.
+
+Rules (from `examples/cases/refund-approval/behaviors/`): treat `examples/cases/refund-approval/materials/data/refund-policy-v3.md` as the sole policy authority; verify the request receipt before deciding eligibility; establish duplicates only from two or more successful payments for the same order; apply the ordinary date bands unless the verified duplicate exception applies; never let CS finalize a calculated refund over 100,000 KRW; and make the two outputs agree while citing every applied policy clause. If source records are missing, ambiguous, or inconsistent, do not guess.
+
+Do the work with auditable shell commands (`cat`, `jq`, and/or `python3`) from the repository root:
+
+1. **Read scope and authority** — read `examples/cases/refund-approval/materials/memo-from-manager.md`, `examples/cases/refund-approval/materials/notes.txt`, and `examples/cases/refund-approval/materials/data/refund-policy-v3.md`. Confirm that **REQUEST_ID = RR-2026-0827-03** is the selected request and Policy v3 is effective. Read `examples/cases/refund-approval/materials/previous/decision-RR-2026-0712-01.md` only as the Markdown structure/style reference, not as policy evidence.
+2. **Select and validate the request** — use `jq` on `examples/cases/refund-approval/materials/data/refund-requests.json` to select exactly one object whose `request_id` equals **RR-2026-0827-03**. Stop for human review if the match count is not exactly one.
+3. **Cross-check the order** — use `jq` on `examples/cases/refund-approval/materials/data/orders.json` to select exactly one matching `order_id`; verify its `customer_id` equals the request's `customer_id`. Stop for human review on a missing, duplicate, or inconsistent order. Do not substitute `ordered_at` for payment date.
+4. **Verify receipt evidence** — inspect `examples/cases/refund-approval/materials/data/payments.csv` with Python's standard `csv` module. Require the request's `receipt_no` to match a payment row for the same `order_id`. If it does not, set status `on_hold_evidence_mismatch`, cite Policy v3 clause 5, calculate no refund, and skip eligibility/approval determination; never silently choose another receipt.
+5. **Establish duplicate status** — for the request's `order_id`, list the payment IDs and amounts of all rows whose `status` is exactly `success`, and count them. Set `is_duplicate_charge` to true only when that count is at least two; do not use the free-text reason as proof. Treat inconsistent successful-payment amounts or a requested amount exceeding the evidenced duplicate amount as requiring human review rather than guessing.
+6. **Calculate policy eligibility** — using the matched successful payment's `paid_at` and the request's `requested_at`, calculate whole calendar days elapsed. If the charge is a verified duplicate, apply clause 3 and calculate a full refund of the evidenced duplicate amount, not exceeding `requested_amount_krw`, regardless of age. Otherwise apply clause 1 for 0–7 days (100%), clause 2 for 8–30 days (50%, integer KRW), or clause 3 for 31+ days (no refund). Record every applied clause number.
+7. **Apply approval authority** — after calculating the refund, apply clause 4. If `calculated_refund_amount_krw > 100000`, set `status` to `pending_finance_approval` and `decision_authority` to `finance`; CS must not finalize or claim issuance. Otherwise set `status` to `finalized` and `decision_authority` to `customer_support`. Preserve `on_hold_evidence_mismatch` when clause 5 was triggered.
+8. **Write the evidence record first** — create `build/refund-approval/` and write `build/refund-approval/decision-RR-2026-0827-03.json`. Include at least: `request_id`, `order_id`, `customer_id`, `requested_at`, `requested_amount_krw`, `receipt_no`, `receipt_match`, `matched_payment` (`payment_id`, `status`, `amount_krw`, `paid_at`, `receipt_no`), `successful_payment_ids`, `successful_payment_count`, `days_since_payment`, `is_duplicate_charge`, `policy_version`, `policy_effective_date`, `applied_clauses`, `calculated_refund_amount_krw`, `status`, `decision_authority`, `rationale`, and `source_files`. Use JSON `null` for calculations not performed due to a hold; do not invent evidence.
+9. **Draft the decision memo from the JSON** — write `build/refund-approval/decision-RR-2026-0827-03.md` in the structure of `examples/cases/refund-approval/materials/previous/decision-RR-2026-0712-01.md`: title `# Refund Decision — RR-2026-0827-03`, a factual order/payment/request summary, `## Decision`, and `## Next steps`. Render amounts as integer KRW with thousands separators. Cite each applied Policy v3 clause number. For `pending_finance_approval`, explicitly say the refund is not finalized or issued and requires Finance approval; for an evidence hold, say correction is required and no refund decision is finalized.
+10. **Validate the pair** — parse the generated JSON and compare it with the Markdown. Confirm both artifacts agree on request/order/customer, receipt evidence, day count, duplicate classification, refund amount, status, authority, and cited clauses. Confirm only this request's two files were produced and no external action was taken.
+11. Reply with a short summary containing the request ID, calculated refund amount (or `null`), status, decision authority, applied clauses, and the two output paths.
+
+Acceptance requires that all source lookups and calculations are observable in the trajectory, Policy v3 alone controls the decision, receipt verification precedes eligibility, duplicate classification uses successful payments only, the Finance threshold is respected, both artifacts agree and cite applicable clauses, and the run performs no refund, approval, or customer-notification action.
diff --git a/examples/cases/refund-approval/behaviors/apply-refund-eligibility-rules/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/apply-refund-eligibility-rules/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..accb357c6f4e57ce097256ec24df5b64ef0fe20d
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/apply-refund-eligibility-rules/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: apply-refund-eligibility-rules
+
+## 1. Intent
+Calculate the refund amount from verified payment evidence using the exact Policy v3 age bands and duplicate exception.
+
+## 2. Evidence
+The trajectory records the matched payment date, request date, whole-day difference, duplicate flag, requested and evidenced amounts, applied clause, and calculated integer-KRW refund before approval routing.
+
+## 3. Decision
+- `true`: A verified duplicate received the evidenced duplicate amount in full regardless of age under clause 3, or a non-duplicate received 100% at 0–7 days, 50% at 8–30 days, or zero at 31+ days under the applicable clause.
+- `false`: Dates, boundaries, percentages, exception precedence, or amounts differ from Policy v3, or the amount was guessed despite inconsistent evidence.
+- `na`: Receipt evidence is mismatched and eligibility calculation is skipped, or the trajectory does not calculate refund eligibility.
+
+## 4. Execution
+Calculate dates and amounts deterministically from selected records; apply the verified duplicate branch before ordinary age-band selection.
+
+## 5. Recovery
+Recompute from `paid_at` and `requested_at`, reapply duplicate precedence and inclusive boundaries, and regenerate both artifacts; escalate inconsistent amounts for human review.
+
+## 6. Failure Modes
+Using order or current date, treating day 7 or 30 incorrectly, denying an old duplicate, refunding more than requested/evidenced, or rounding to non-integer KRW.
diff --git a/examples/cases/refund-approval/behaviors/enforce-finance-approval-threshold/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/enforce-finance-approval-threshold/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..8b9d8496bdc037ed8d78d805b63897ce89f40825
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/enforce-finance-approval-threshold/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: enforce-finance-approval-threshold
+
+## 1. Intent
+Prevent Customer Support from finalizing any calculated refund over 100,000 KRW.
+
+## 2. Evidence
+After refund calculation, the trajectory compares `calculated_refund_amount_krw` to 100000 and records clause 4, `pending_finance_approval`, and decision authority `finance` whenever the amount is greater than the threshold.
+
+## 3. Decision
+- `true`: Every amount over 100,000 KRW is pending Finance approval and is not described as finalized or issued; amounts at or below the threshold may be finalized by CS.
+- `false`: CS finalizes or claims issuance of an over-threshold refund, or routes exactly 100,000 KRW to Finance solely because of clause 4.
+- `na`: No refund amount was calculated because evidence is held, the calculated amount is zero with no approval action, or the trajectory does not make a refund decision.
+
+## 4. Execution
+Make the threshold comparison a deterministic step after eligibility calculation and before writing either output.
+
+## 5. Recovery
+Replace the unauthorized status and language with `pending_finance_approval`, authority `finance`, and an explicit statement that no refund has been finalized or issued; then revalidate both files.
+
+## 6. Failure Modes
+Comparing requested rather than calculated refund, using `>=` instead of `>`, copying finalized language from the prior memo, or implying Finance approval occurred.
diff --git a/examples/cases/refund-approval/behaviors/keep-decision-artifacts-auditable/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/keep-decision-artifacts-auditable/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..2cdfb40fdb7b3be444d9d7aa554ba9a74864c1a2
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/keep-decision-artifacts-auditable/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: keep-decision-artifacts-auditable
+
+## 1. Intent
+Produce mutually consistent human-readable and machine-readable decisions with observable sources and all applicable policy citations.
+
+## 2. Evidence
+The trajectory writes the JSON evidence record before drafting the Markdown from it, records source file paths and applied clauses, then parses and compares both files for identity, evidence, amount, status, authority, and clause agreement.
+
+## 3. Decision
+- `true`: Both required files exist for only the selected request, agree on all material facts and outcomes, cite every applied Policy v3 clause, and make no unsupported claim of external action.
+- `false`: A file is missing, filenames or contents concern another request, artifacts disagree, clauses/sources are absent, or the memo claims an unperformed refund, approval, or notification.
+- `na`: The trajectory does not produce refund decision artifacts.
+
+## 4. Execution
+Serialize structured evidence first, render the memo from that record, and run a final pairwise consistency validation before replying.
+
+## 5. Recovery
+Treat the JSON evidence derived from verified sources as the drafting input, regenerate the memo or both artifacts as needed, and repeat consistency checks without performing external actions.
+
+## 6. Failure Modes
+Drafting prose first and backfilling evidence, omitting clause numbers, mismatched amounts/statuses, processing multiple requests, or stating that a refund/customer notice was sent when it was not.
diff --git a/examples/cases/refund-approval/behaviors/prove-duplicate-from-successful-payments/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/prove-duplicate-from-successful-payments/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..7c31cdc12a105441f3444c4be996d7f9a4700786
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/prove-duplicate-from-successful-payments/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: prove-duplicate-from-successful-payments
+
+## 1. Intent
+Ensure the duplicate-charge exception is granted only from payment-ledger evidence.
+
+## 2. Evidence
+The trajectory filters `payments.csv` by the request `order_id` and exact status `success`, records the resulting payment IDs and count, and derives `is_duplicate_charge` from whether the count is at least two.
+
+## 3. Decision
+- `true`: Duplicate status equals the result of counting same-order successful payments and the supporting IDs/count appear in the JSON.
+- `false`: Free text, failed payments, other orders, or an unrecorded assumption established duplicate status.
+- `na`: Receipt evidence is mismatched and duplicate classification is therefore skipped, or the trajectory does not make a refund decision.
+
+## 4. Execution
+Perform the successful-payment filter and count deterministically after receipt verification and before applying the duplicate exception.
+
+## 5. Recovery
+Re-read the payment ledger, exclude non-success rows and other orders, recompute the count, and regenerate downstream calculations and outputs.
+
+## 6. Failure Modes
+Trusting “charged twice” as proof, counting failed/voided payments, counting across customers or orders, or omitting payment IDs from the evidence record.
diff --git a/examples/cases/refund-approval/behaviors/use-authoritative-policy-v3/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/use-authoritative-policy-v3/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..f7809133924e33ea801ce1eb334e7af7e11b967a
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/use-authoritative-policy-v3/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: use-authoritative-policy-v3
+
+## 1. Intent
+Ensure every refund decision uses the effective Refund Policy v3 as its sole rules authority rather than summaries, prior decisions, memory, or invented policy.
+
+## 2. Evidence
+The trajectory reads `examples/cases/refund-approval/materials/data/refund-policy-v3.md` before classification or calculation, records policy version `v3` and effective date `2026-04-01` in the evidence JSON, and uses the memo and previous decision only for scope or format.
+
+## 3. Decision
+- `true`: Policy v3 was read before the decision and all applied rules are traceable to it.
+- `false`: The decision used an unread, legacy, summarized, remembered, or invented rule as authority.
+- `na`: The trajectory does not make or draft a refund decision.
+
+## 4. Execution
+Enforce the policy read as a required predecessor to receipt validation, eligibility calculation, approval routing, and drafting.
+
+## 5. Recovery
+Discard unsupported conclusions, read Policy v3, and recompute the evidence record and memo from its clauses.
+
+## 6. Failure Modes
+Treating the manager memo as complete policy, copying the previous deliverable's outcome, using today's date for eligibility, or inventing an exception absent from Policy v3.
diff --git a/examples/cases/refund-approval/behaviors/verify-receipt-before-decision/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/verify-receipt-before-decision/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..162d8f3bef6a8f341d8211937ff4a0fa0223fce9
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/verify-receipt-before-decision/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: verify-receipt-before-decision
+
+## 1. Intent
+Prevent eligibility or approval decisions from being made against an unverified receipt.
+
+## 2. Evidence
+The trajectory selects the request receipt, searches `payments.csv` for the same receipt and order, and records `receipt_match` plus the matched payment fields before any eligibility calculation or decision drafting.
+
+## 3. Decision
+- `true`: A same-order receipt match was checked first, or a missing match produced `on_hold_evidence_mismatch` with clause 5 and no refund calculation.
+- `false`: Eligibility was decided before receipt verification, a different receipt was substituted, or a mismatch did not produce the required hold.
+- `na`: The trajectory does not make or draft a refund decision.
+
+## 4. Execution
+Make receipt validation a non-removable predecessor to duplicate classification and refund calculation; route mismatches directly to the evidence-hold output path.
+
+## 5. Recovery
+Stop the decision, re-check the request receipt against same-order payment records, and regenerate both artifacts; if still unmatched, retain the clause 5 hold.
+
+## 6. Failure Modes
+Matching receipt alone without checking order, accepting the customer's reason as evidence, choosing a nearby receipt, or calculating a refund while evidence is held.

diff --git a/examples/cases/refund-approval/ASSUMPTIONS.md b/examples/cases/refund-approval/ASSUMPTIONS.md
new file mode 100644
index 0000000000000000000000000000000000000000..b354d0ff2f4dc0432b96252f46d04d1f0960835b
--- /dev/null
+++ b/examples/cases/refund-approval/ASSUMPTIONS.md
@@ -0,0 +1,133 @@
+# Assumptions: invoice refund approval decisions
+
+This file records the grilling interview conducted against the supplied work materials because the requester was unavailable. Each answer is a recommended assumption to verify or correct before treating the specification as final.
+
+## Round 1 — Goal and consumer
+
+### 1. What is the single-sentence goal?
+
+**Chosen answer:** For the per-run refund request ID, produce an auditable customer-support refund decision memo and a machine-readable evidence record that applies Refund Policy v3 without issuing a refund or contacting the customer.
+
+**Why:** `materials/memo-from-manager.md` asks for one decision memo and one evidence JSON per request. The materials describe decision preparation, not payment execution or customer communication.
+
+### 2. Who consumes the result?
+
+**Chosen answer:** Customer Support consumes finalized or held decisions; Finance consumes decisions whose calculated refund exceeds 100,000 KRW.
+
+**Why:** The manager memo says CS may finalize amounts below the threshold, while larger amounts must be handed to Finance as pending approval.
+
+### 3. Which request is in scope for this run?
+
+**Chosen answer:** The per-run parameter is **REQUEST_ID = RR-2026-0827-03**. Process exactly that request, not every row in the input file.
+
+**Why:** `materials/notes.txt` explicitly identifies this as this week's case and gives singular output naming rules.
+
+## Round 2 — Inputs and authority
+
+### 4. What are the authoritative inputs?
+
+**Chosen answer:** Read `materials/data/refund-requests.json` for the request, `materials/data/orders.json` for the order/customer record, `materials/data/payments.csv` for receipt and successful-payment evidence, and `materials/data/refund-policy-v3.md` for all decision rules.
+
+**Why:** These are the raw files supplied for the work. The manager memo explicitly says the v3 policy document is official.
+
+### 5. How should the memo, notes, and previous deliverable be used?
+
+**Chosen answer:** Use `materials/memo-from-manager.md` and `materials/notes.txt` to scope and parameterize the run, and use `materials/previous/decision-RR-2026-0712-01.md` only as the memo format/style reference. Never treat any of them as overriding policy v3.
+
+**Why:** The manager calls the memo a summary and policy v3 the formal authority; the prior deliverable demonstrates headings and wording but is not a rules source.
+
+### 6. What values vary per run?
+
+**Chosen answer:** `REQUEST_ID` varies per run. All joined request, order, payment, dates, amounts, receipt, reason, classification, status, and output filenames derive from it. Policy path and output directory remain fixed until explicitly versioned.
+
+**Why:** The notes select one request ID and define filenames as `decision-<request ID>.*`.
+
+### 7. What date controls age, and how are boundaries calculated?
+
+**Chosen answer:** Use the matched successful payment's `paid_at` and the request's `requested_at`; calculate whole calendar-day difference as request date minus payment date. Interpret “within 7 days” as 0–7 inclusive, “8–30 days” as 8–30 inclusive, and “after 30 days” as 31+.
+
+**Why:** Policy v3 explicitly speaks in those ranges and the previous decision demonstrates 2026-07-01 to 2026-07-12 as 11 days. Today's date in the notes does not determine eligibility.
+
+## Round 3 — Ordered work and decision precedence
+
+### 8. What ordered steps should a competent reviewer follow?
+
+**Chosen answer:** Select exactly one request; join and cross-check the order/customer; match the receipt to a payment; count successful payments for the order; classify duplicate status; calculate the policy refund; apply the Finance threshold; then write JSON evidence before drafting the memo from that evidence.
+
+**Why:** This order makes every policy predicate observable and prevents prose from becoming the source of truth.
+
+### 9. What happens if a receipt does not match?
+
+**Chosen answer:** Stop substantive eligibility and approval determination, record `on_hold_evidence_mismatch`, calculate no refund amount, cite clause 5, and do not infer a receipt from another payment.
+
+**Why:** Policy v3 clause 5 mandates the hold. The supplied ORD-77003 case is a deliberate example of a request receipt differing from the successful payment receipt.
+
+### 10. How is a duplicate charge established?
+
+**Chosen answer:** Count payment rows with the same `order_id` and `status == success`; two or more establishes a duplicate. Customer reason text alone is not evidence. The refundable duplicate amount is the matched successful payment amount, limited to the amount requested; any inconsistent amounts must be escalated rather than guessed.
+
+**Why:** The memo and clause 3 define duplicates using successful payments, and the current case has two 264,000 KRW successes. The materials do not authorize refunding more than requested or inventing a value when amounts conflict.
+
+### 11. Which rule takes precedence for old duplicate charges?
+
+**Chosen answer:** A verified duplicate receives a full refund for the duplicate amount regardless of age under clause 3; the ordinary age bands in clauses 1–3 apply only when the request is not a duplicate.
+
+**Why:** Clause 3 expressly creates the age exception.
+
+### 12. Does Finance approval change refund eligibility?
+
+**Chosen answer:** No. First calculate the eligible refund amount, then set `pending_finance_approval` if it is over 100,000 KRW. CS must not label it finalized or claim the refund was issued.
+
+**Why:** Clause 4 is an approval/status rule based on the calculated amount, not an eligibility denial.
+
+## Round 4 — Mechanics, judgment, and outputs
+
+### 13. Which steps are mechanical and which require judgment?
+
+**Chosen answer:** JSON/CSV selection, joins, receipt matching, successful-payment counting, date arithmetic, percentage calculation, threshold comparison, and JSON serialization are mechanical. Explaining the result and recovery for inconsistent/missing data are judgment steps constrained by the evidence and behavior contracts.
+
+**Why:** All numeric and categorical rules are explicit. Only concise explanation and unenumerated data-quality exceptions need bounded judgment.
+
+### 14. What exact files and fields constitute “done”?
+
+**Chosen answer:** Write `build/refund-approval/decision-<REQUEST_ID>.json` first with source paths, identity fields, matched payment evidence, successful payment IDs/count, day difference, duplicate flag, applied clauses, calculated amount, status, authority, and rationale; then write `build/refund-approval/decision-<REQUEST_ID>.md` with the previous deliverable's title, factual summary, `## Decision`, and `## Next steps`.
+
+**Why:** The memo requires one Markdown decision and one evidence JSON, the notes give exact filenames, and policy clause 6 requires clause citations.
+
+### 15. What language and money representation should outputs use?
+
+**Chosen answer:** Follow the previous deliverable in English; store KRW amounts as integer won in JSON and render them with thousands separators plus `KRW` in Markdown.
+
+**Why:** The repository is maintained in English, the prior deliverable is English, and every supplied amount is integral KRW.
+
+### 16. What must the memo say for each terminal status?
+
+**Chosen answer:** For `finalized`, state CS finalization and the supported next-step template only if the materials authorize it. For `pending_finance_approval`, state that the calculated refund is pending Finance approval and has not been finalized or issued. For `on_hold_evidence_mismatch`, state that evidence correction is required and no refund decision is finalized.
+
+**Why:** This preserves the authority boundary. The prior memo's “refund issued” wording is not safe for a pending or held case.
+
+## Round 5 — Acceptance and failure recovery
+
+### 17. What are the acceptance criteria?
+
+**Chosen answer:** Exactly one request is processed; all required sources are read; joins agree; receipt is verified before eligibility; duplicate status uses successful payments only; policy v3 and applicable clause numbers are cited; amount/status/authority are consistent; JSON and Markdown agree; and no external refund, approval, or notification action occurs.
+
+**Why:** These criteria cover the manager's explicit rules and make behavior compliance independently reviewable.
+
+### 18. Which failure modes must be prevented?
+
+**Chosen answer:** Processing the wrong or multiple requests, treating customer claims as proof, counting failed payments, using order date instead of payment date, applying age denial to a duplicate, finalizing an over-cap refund, silently substituting a receipt, citing no clauses, disagreeing outputs, and claiming downstream actions occurred.
+
+**Why:** Each would violate a supplied rule or make the audit trail unreliable; several traps are represented in the raw fixture data.
+
+### 19. What should happen on missing, duplicate, or inconsistent records?
+
+**Chosen answer:** Do not guess. Stop before drafting a normal decision, preserve observed evidence in the JSON when possible, state the unresolved inconsistency, and require human review. A missing receipt match specifically uses `on_hold_evidence_mismatch`; other unmodeled integrity failures use a clearly labeled review-required error rather than a policy status invented by the agent.
+
+**Why:** Only the receipt-mismatch hold has a prescribed status. The materials provide no safe resolution rule for conflicting customer/order/payment identities or ambiguous rows.
+
+### 20. Are any facts intentionally unknown?
+
+**Chosen answer:** The exact Finance routing mechanism, customer notification template for this case, refund-processing API, and SLA are unknown and out of scope. The agent must not fabricate or execute them.
+
+**Why:** The materials specify decision artifacts and a Finance status but provide no connectors, destinations, templates, or operational instructions for those actions.
diff --git a/examples/cases/refund-approval/TASK.md b/examples/cases/refund-approval/TASK.md
new file mode 100644
index 0000000000000000000000000000000000000000..09ca3446e24191b38b6e7f475cc2ebe5b23d698d
--- /dev/null
+++ b/examples/cases/refund-approval/TASK.md
@@ -0,0 +1,21 @@
+# Task: refund approval decision for request RR-2026-0827-03
+
+You are the customer-support refund decision assistant. Prepare the refund decision artifacts for per-run parameter **REQUEST_ID = RR-2026-0827-03** for Customer Support and, when required, Finance review. Do not issue a refund, approve on Finance's behalf, or contact the customer.
+
+Rules (from `examples/cases/refund-approval/behaviors/`): treat `examples/cases/refund-approval/materials/data/refund-policy-v3.md` as the sole policy authority; verify the request receipt before deciding eligibility; establish duplicates only from two or more successful payments for the same order; apply the ordinary date bands unless the verified duplicate exception applies; never let CS finalize a calculated refund over 100,000 KRW; and make the two outputs agree while citing every applied policy clause. If source records are missing, ambiguous, or inconsistent, do not guess.
+
+Do the work with auditable shell commands (`cat`, `jq`, and/or `python3`) from the repository root:
+
+1. **Read scope and authority** — read `examples/cases/refund-approval/materials/memo-from-manager.md`, `examples/cases/refund-approval/materials/notes.txt`, and `examples/cases/refund-approval/materials/data/refund-policy-v3.md`. Confirm that **REQUEST_ID = RR-2026-0827-03** is the selected request and Policy v3 is effective. Read `examples/cases/refund-approval/materials/previous/decision-RR-2026-0712-01.md` only as the Markdown structure/style reference, not as policy evidence.
+2. **Select and validate the request** — use `jq` on `examples/cases/refund-approval/materials/data/refund-requests.json` to select exactly one object whose `request_id` equals **RR-2026-0827-03**. Stop for human review if the match count is not exactly one.
+3. **Cross-check the order** — use `jq` on `examples/cases/refund-approval/materials/data/orders.json` to select exactly one matching `order_id`; verify its `customer_id` equals the request's `customer_id`. Stop for human review on a missing, duplicate, or inconsistent order. Do not substitute `ordered_at` for payment date.
+4. **Verify receipt evidence** — inspect `examples/cases/refund-approval/materials/data/payments.csv` with Python's standard `csv` module. Require the request's `receipt_no` to match a payment row for the same `order_id`. If it does not, set status `on_hold_evidence_mismatch`, cite Policy v3 clause 5, calculate no refund, and skip eligibility/approval determination; never silently choose another receipt.
+5. **Establish duplicate status** — for the request's `order_id`, list the payment IDs and amounts of all rows whose `status` is exactly `success`, and count them. Set `is_duplicate_charge` to true only when that count is at least two; do not use the free-text reason as proof. Treat inconsistent successful-payment amounts or a requested amount exceeding the evidenced duplicate amount as requiring human review rather than guessing.
+6. **Calculate policy eligibility** — using the matched successful payment's `paid_at` and the request's `requested_at`, calculate whole calendar days elapsed. If the charge is a verified duplicate, apply clause 3 and calculate a full refund of the evidenced duplicate amount, not exceeding `requested_amount_krw`, regardless of age. Otherwise apply clause 1 for 0–7 days (100%), clause 2 for 8–30 days (50%, integer KRW), or clause 3 for 31+ days (no refund). Record every applied clause number.
+7. **Apply approval authority** — after calculating the refund, apply clause 4. If `calculated_refund_amount_krw > 100000`, set `status` to `pending_finance_approval` and `decision_authority` to `finance`; CS must not finalize or claim issuance. Otherwise set `status` to `finalized` and `decision_authority` to `customer_support`. Preserve `on_hold_evidence_mismatch` when clause 5 was triggered.
+8. **Write the evidence record first** — create `build/refund-approval/` and write `build/refund-approval/decision-RR-2026-0827-03.json`. Include at least: `request_id`, `order_id`, `customer_id`, `requested_at`, `requested_amount_krw`, `receipt_no`, `receipt_match`, `matched_payment` (`payment_id`, `status`, `amount_krw`, `paid_at`, `receipt_no`), `successful_payment_ids`, `successful_payment_count`, `days_since_payment`, `is_duplicate_charge`, `policy_version`, `policy_effective_date`, `applied_clauses`, `calculated_refund_amount_krw`, `status`, `decision_authority`, `rationale`, and `source_files`. Use JSON `null` for calculations not performed due to a hold; do not invent evidence.
+9. **Draft the decision memo from the JSON** — write `build/refund-approval/decision-RR-2026-0827-03.md` in the structure of `examples/cases/refund-approval/materials/previous/decision-RR-2026-0712-01.md`: title `# Refund Decision — RR-2026-0827-03`, a factual order/payment/request summary, `## Decision`, and `## Next steps`. Render amounts as integer KRW with thousands separators. Cite each applied Policy v3 clause number. For `pending_finance_approval`, explicitly say the refund is not finalized or issued and requires Finance approval; for an evidence hold, say correction is required and no refund decision is finalized.
+10. **Validate the pair** — parse the generated JSON and compare it with the Markdown. Confirm both artifacts agree on request/order/customer, receipt evidence, day count, duplicate classification, refund amount, status, authority, and cited clauses. Confirm only this request's two files were produced and no external action was taken.
+11. Reply with a short summary containing the request ID, calculated refund amount (or `null`), status, decision authority, applied clauses, and the two output paths.
+
+Acceptance requires that all source lookups and calculations are observable in the trajectory, Policy v3 alone controls the decision, receipt verification precedes eligibility, duplicate classification uses successful payments only, the Finance threshold is respected, both artifacts agree and cite applicable clauses, and the run performs no refund, approval, or customer-notification action.
diff --git a/examples/cases/refund-approval/behaviors/apply-refund-eligibility-rules/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/apply-refund-eligibility-rules/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..accb357c6f4e57ce097256ec24df5b64ef0fe20d
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/apply-refund-eligibility-rules/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: apply-refund-eligibility-rules
+
+## 1. Intent
+Calculate the refund amount from verified payment evidence using the exact Policy v3 age bands and duplicate exception.
+
+## 2. Evidence
+The trajectory records the matched payment date, request date, whole-day difference, duplicate flag, requested and evidenced amounts, applied clause, and calculated integer-KRW refund before approval routing.
+
+## 3. Decision
+- `true`: A verified duplicate received the evidenced duplicate amount in full regardless of age under clause 3, or a non-duplicate received 100% at 0–7 days, 50% at 8–30 days, or zero at 31+ days under the applicable clause.
+- `false`: Dates, boundaries, percentages, exception precedence, or amounts differ from Policy v3, or the amount was guessed despite inconsistent evidence.
+- `na`: Receipt evidence is mismatched and eligibility calculation is skipped, or the trajectory does not calculate refund eligibility.
+
+## 4. Execution
+Calculate dates and amounts deterministically from selected records; apply the verified duplicate branch before ordinary age-band selection.
+
+## 5. Recovery
+Recompute from `paid_at` and `requested_at`, reapply duplicate precedence and inclusive boundaries, and regenerate both artifacts; escalate inconsistent amounts for human review.
+
+## 6. Failure Modes
+Using order or current date, treating day 7 or 30 incorrectly, denying an old duplicate, refunding more than requested/evidenced, or rounding to non-integer KRW.
diff --git a/examples/cases/refund-approval/behaviors/enforce-finance-approval-threshold/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/enforce-finance-approval-threshold/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..8b9d8496bdc037ed8d78d805b63897ce89f40825
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/enforce-finance-approval-threshold/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: enforce-finance-approval-threshold
+
+## 1. Intent
+Prevent Customer Support from finalizing any calculated refund over 100,000 KRW.
+
+## 2. Evidence
+After refund calculation, the trajectory compares `calculated_refund_amount_krw` to 100000 and records clause 4, `pending_finance_approval`, and decision authority `finance` whenever the amount is greater than the threshold.
+
+## 3. Decision
+- `true`: Every amount over 100,000 KRW is pending Finance approval and is not described as finalized or issued; amounts at or below the threshold may be finalized by CS.
+- `false`: CS finalizes or claims issuance of an over-threshold refund, or routes exactly 100,000 KRW to Finance solely because of clause 4.
+- `na`: No refund amount was calculated because evidence is held, the calculated amount is zero with no approval action, or the trajectory does not make a refund decision.
+
+## 4. Execution
+Make the threshold comparison a deterministic step after eligibility calculation and before writing either output.
+
+## 5. Recovery
+Replace the unauthorized status and language with `pending_finance_approval`, authority `finance`, and an explicit statement that no refund has been finalized or issued; then revalidate both files.
+
+## 6. Failure Modes
+Comparing requested rather than calculated refund, using `>=` instead of `>`, copying finalized language from the prior memo, or implying Finance approval occurred.
diff --git a/examples/cases/refund-approval/behaviors/keep-decision-artifacts-auditable/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/keep-decision-artifacts-auditable/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..2cdfb40fdb7b3be444d9d7aa554ba9a74864c1a2
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/keep-decision-artifacts-auditable/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: keep-decision-artifacts-auditable
+
+## 1. Intent
+Produce mutually consistent human-readable and machine-readable decisions with observable sources and all applicable policy citations.
+
+## 2. Evidence
+The trajectory writes the JSON evidence record before drafting the Markdown from it, records source file paths and applied clauses, then parses and compares both files for identity, evidence, amount, status, authority, and clause agreement.
+
+## 3. Decision
+- `true`: Both required files exist for only the selected request, agree on all material facts and outcomes, cite every applied Policy v3 clause, and make no unsupported claim of external action.
+- `false`: A file is missing, filenames or contents concern another request, artifacts disagree, clauses/sources are absent, or the memo claims an unperformed refund, approval, or notification.
+- `na`: The trajectory does not produce refund decision artifacts.
+
+## 4. Execution
+Serialize structured evidence first, render the memo from that record, and run a final pairwise consistency validation before replying.
+
+## 5. Recovery
+Treat the JSON evidence derived from verified sources as the drafting input, regenerate the memo or both artifacts as needed, and repeat consistency checks without performing external actions.
+
+## 6. Failure Modes
+Drafting prose first and backfilling evidence, omitting clause numbers, mismatched amounts/statuses, processing multiple requests, or stating that a refund/customer notice was sent when it was not.
diff --git a/examples/cases/refund-approval/behaviors/prove-duplicate-from-successful-payments/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/prove-duplicate-from-successful-payments/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..7c31cdc12a105441f3444c4be996d7f9a4700786
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/prove-duplicate-from-successful-payments/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: prove-duplicate-from-successful-payments
+
+## 1. Intent
+Ensure the duplicate-charge exception is granted only from payment-ledger evidence.
+
+## 2. Evidence
+The trajectory filters `payments.csv` by the request `order_id` and exact status `success`, records the resulting payment IDs and count, and derives `is_duplicate_charge` from whether the count is at least two.
+
+## 3. Decision
+- `true`: Duplicate status equals the result of counting same-order successful payments and the supporting IDs/count appear in the JSON.
+- `false`: Free text, failed payments, other orders, or an unrecorded assumption established duplicate status.
+- `na`: Receipt evidence is mismatched and duplicate classification is therefore skipped, or the trajectory does not make a refund decision.
+
+## 4. Execution
+Perform the successful-payment filter and count deterministically after receipt verification and before applying the duplicate exception.
+
+## 5. Recovery
+Re-read the payment ledger, exclude non-success rows and other orders, recompute the count, and regenerate downstream calculations and outputs.
+
+## 6. Failure Modes
+Trusting “charged twice” as proof, counting failed/voided payments, counting across customers or orders, or omitting payment IDs from the evidence record.
diff --git a/examples/cases/refund-approval/behaviors/use-authoritative-policy-v3/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/use-authoritative-policy-v3/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..f7809133924e33ea801ce1eb334e7af7e11b967a
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/use-authoritative-policy-v3/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: use-authoritative-policy-v3
+
+## 1. Intent
+Ensure every refund decision uses the effective Refund Policy v3 as its sole rules authority rather than summaries, prior decisions, memory, or invented policy.
+
+## 2. Evidence
+The trajectory reads `examples/cases/refund-approval/materials/data/refund-policy-v3.md` before classification or calculation, records policy version `v3` and effective date `2026-04-01` in the evidence JSON, and uses the memo and previous decision only for scope or format.
+
+## 3. Decision
+- `true`: Policy v3 was read before the decision and all applied rules are traceable to it.
+- `false`: The decision used an unread, legacy, summarized, remembered, or invented rule as authority.
+- `na`: The trajectory does not make or draft a refund decision.
+
+## 4. Execution
+Enforce the policy read as a required predecessor to receipt validation, eligibility calculation, approval routing, and drafting.
+
+## 5. Recovery
+Discard unsupported conclusions, read Policy v3, and recompute the evidence record and memo from its clauses.
+
+## 6. Failure Modes
+Treating the manager memo as complete policy, copying the previous deliverable's outcome, using today's date for eligibility, or inventing an exception absent from Policy v3.
diff --git a/examples/cases/refund-approval/behaviors/verify-receipt-before-decision/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/verify-receipt-before-decision/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..162d8f3bef6a8f341d8211937ff4a0fa0223fce9
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/verify-receipt-before-decision/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: verify-receipt-before-decision
+
+## 1. Intent
+Prevent eligibility or approval decisions from being made against an unverified receipt.
+
+## 2. Evidence
+The trajectory selects the request receipt, searches `payments.csv` for the same receipt and order, and records `receipt_match` plus the matched payment fields before any eligibility calculation or decision drafting.
+
+## 3. Decision
+- `true`: A same-order receipt match was checked first, or a missing match produced `on_hold_evidence_mismatch` with clause 5 and no refund calculation.
+- `false`: Eligibility was decided before receipt verification, a different receipt was substituted, or a mismatch did not produce the required hold.
+- `na`: The trajectory does not make or draft a refund decision.
+
+## 4. Execution
+Make receipt validation a non-removable predecessor to duplicate classification and refund calculation; route mismatches directly to the evidence-hold output path.
+
+## 5. Recovery
+Stop the decision, re-check the request receipt against same-order payment records, and regenerate both artifacts; if still unmatched, retain the clause 5 hold.
+
+## 6. Failure Modes
+Matching receipt alone without checking order, accepting the customer's reason as evidence, choosing a nearby receipt, or calculating a refund while evidence is held.

codex
The specification artifacts are written. I made one conservative boundary explicit: the workflow prepares decisions only; Finance routing mechanics, refund execution, and customer notification remain unknown and must not be fabricated. I’m validating the six-section contracts and checking that every task path stays within the supplied materials and `build/refund-approval/`.
exec
/bin/zsh -lc "python3 - <<'PY'
from pathlib import Path
from adapters.agentbehavior.parser import load_behavior_file
root = Path('examples/cases/refund-approval')
files = sorted((root / 'behaviors').glob('*/BEHAVIOR.md'))
assert files, 'no behavior files'
for path in files:
    doc = load_behavior_file(path)
    missing = [k for k in ('intent','evidence','execution','recovery','failure_modes') if not doc[k]]
    missing += [f'decision.{k}' for k in ('true','false','na') if not doc['decision'][k]]
    assert not missing, f'{path}: missing {missing}'
    print(f'OK {path}: {doc[\"name\"]}')
for path in [root/'ASSUMPTIONS.md', root/'TASK.md']:
    assert path.stat().st_size > 0
    print(f'OK {path}')
task = (root/'TASK.md').read_text()
assert 'build/refund-approval/' in task
assert 'examples/cases/refund-approval/materials/' in task
assert 'Do not issue a refund' in task
print(f'Validated {len(files)} behavior contracts')
PY

git diff --check -- examples/cases/refund-approval
git status --short -- examples/cases/refund-approval" in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 0ms:
OK examples/cases/refund-approval/behaviors/apply-refund-eligibility-rules/BEHAVIOR.md: apply-refund-eligibility-rules
OK examples/cases/refund-approval/behaviors/enforce-finance-approval-threshold/BEHAVIOR.md: enforce-finance-approval-threshold
OK examples/cases/refund-approval/behaviors/keep-decision-artifacts-auditable/BEHAVIOR.md: keep-decision-artifacts-auditable
OK examples/cases/refund-approval/behaviors/prove-duplicate-from-successful-payments/BEHAVIOR.md: prove-duplicate-from-successful-payments
OK examples/cases/refund-approval/behaviors/use-authoritative-policy-v3/BEHAVIOR.md: use-authoritative-policy-v3
OK examples/cases/refund-approval/behaviors/verify-receipt-before-decision/BEHAVIOR.md: verify-receipt-before-decision
OK examples/cases/refund-approval/ASSUMPTIONS.md
OK examples/cases/refund-approval/TASK.md
Validated 6 behavior contracts
?? examples/cases/refund-approval/

diff --git a/examples/cases/refund-approval/ASSUMPTIONS.md b/examples/cases/refund-approval/ASSUMPTIONS.md
new file mode 100644
index 0000000000000000000000000000000000000000..b354d0ff2f4dc0432b96252f46d04d1f0960835b
--- /dev/null
+++ b/examples/cases/refund-approval/ASSUMPTIONS.md
@@ -0,0 +1,133 @@
+# Assumptions: invoice refund approval decisions
+
+This file records the grilling interview conducted against the supplied work materials because the requester was unavailable. Each answer is a recommended assumption to verify or correct before treating the specification as final.
+
+## Round 1 — Goal and consumer
+
+### 1. What is the single-sentence goal?
+
+**Chosen answer:** For the per-run refund request ID, produce an auditable customer-support refund decision memo and a machine-readable evidence record that applies Refund Policy v3 without issuing a refund or contacting the customer.
+
+**Why:** `materials/memo-from-manager.md` asks for one decision memo and one evidence JSON per request. The materials describe decision preparation, not payment execution or customer communication.
+
+### 2. Who consumes the result?
+
+**Chosen answer:** Customer Support consumes finalized or held decisions; Finance consumes decisions whose calculated refund exceeds 100,000 KRW.
+
+**Why:** The manager memo says CS may finalize amounts below the threshold, while larger amounts must be handed to Finance as pending approval.
+
+### 3. Which request is in scope for this run?
+
+**Chosen answer:** The per-run parameter is **REQUEST_ID = RR-2026-0827-03**. Process exactly that request, not every row in the input file.
+
+**Why:** `materials/notes.txt` explicitly identifies this as this week's case and gives singular output naming rules.
+
+## Round 2 — Inputs and authority
+
+### 4. What are the authoritative inputs?
+
+**Chosen answer:** Read `materials/data/refund-requests.json` for the request, `materials/data/orders.json` for the order/customer record, `materials/data/payments.csv` for receipt and successful-payment evidence, and `materials/data/refund-policy-v3.md` for all decision rules.
+
+**Why:** These are the raw files supplied for the work. The manager memo explicitly says the v3 policy document is official.
+
+### 5. How should the memo, notes, and previous deliverable be used?
+
+**Chosen answer:** Use `materials/memo-from-manager.md` and `materials/notes.txt` to scope and parameterize the run, and use `materials/previous/decision-RR-2026-0712-01.md` only as the memo format/style reference. Never treat any of them as overriding policy v3.
+
+**Why:** The manager calls the memo a summary and policy v3 the formal authority; the prior deliverable demonstrates headings and wording but is not a rules source.
+
+### 6. What values vary per run?
+
+**Chosen answer:** `REQUEST_ID` varies per run. All joined request, order, payment, dates, amounts, receipt, reason, classification, status, and output filenames derive from it. Policy path and output directory remain fixed until explicitly versioned.
+
+**Why:** The notes select one request ID and define filenames as `decision-<request ID>.*`.
+
+### 7. What date controls age, and how are boundaries calculated?
+
+**Chosen answer:** Use the matched successful payment's `paid_at` and the request's `requested_at`; calculate whole calendar-day difference as request date minus payment date. Interpret “within 7 days” as 0–7 inclusive, “8–30 days” as 8–30 inclusive, and “after 30 days” as 31+.
+
+**Why:** Policy v3 explicitly speaks in those ranges and the previous decision demonstrates 2026-07-01 to 2026-07-12 as 11 days. Today's date in the notes does not determine eligibility.
+
+## Round 3 — Ordered work and decision precedence
+
+### 8. What ordered steps should a competent reviewer follow?
+
+**Chosen answer:** Select exactly one request; join and cross-check the order/customer; match the receipt to a payment; count successful payments for the order; classify duplicate status; calculate the policy refund; apply the Finance threshold; then write JSON evidence before drafting the memo from that evidence.
+
+**Why:** This order makes every policy predicate observable and prevents prose from becoming the source of truth.
+
+### 9. What happens if a receipt does not match?
+
+**Chosen answer:** Stop substantive eligibility and approval determination, record `on_hold_evidence_mismatch`, calculate no refund amount, cite clause 5, and do not infer a receipt from another payment.
+
+**Why:** Policy v3 clause 5 mandates the hold. The supplied ORD-77003 case is a deliberate example of a request receipt differing from the successful payment receipt.
+
+### 10. How is a duplicate charge established?
+
+**Chosen answer:** Count payment rows with the same `order_id` and `status == success`; two or more establishes a duplicate. Customer reason text alone is not evidence. The refundable duplicate amount is the matched successful payment amount, limited to the amount requested; any inconsistent amounts must be escalated rather than guessed.
+
+**Why:** The memo and clause 3 define duplicates using successful payments, and the current case has two 264,000 KRW successes. The materials do not authorize refunding more than requested or inventing a value when amounts conflict.
+
+### 11. Which rule takes precedence for old duplicate charges?
+
+**Chosen answer:** A verified duplicate receives a full refund for the duplicate amount regardless of age under clause 3; the ordinary age bands in clauses 1–3 apply only when the request is not a duplicate.
+
+**Why:** Clause 3 expressly creates the age exception.
+
+### 12. Does Finance approval change refund eligibility?
+
+**Chosen answer:** No. First calculate the eligible refund amount, then set `pending_finance_approval` if it is over 100,000 KRW. CS must not label it finalized or claim the refund was issued.
+
+**Why:** Clause 4 is an approval/status rule based on the calculated amount, not an eligibility denial.
+
+## Round 4 — Mechanics, judgment, and outputs
+
+### 13. Which steps are mechanical and which require judgment?
+
+**Chosen answer:** JSON/CSV selection, joins, receipt matching, successful-payment counting, date arithmetic, percentage calculation, threshold comparison, and JSON serialization are mechanical. Explaining the result and recovery for inconsistent/missing data are judgment steps constrained by the evidence and behavior contracts.
+
+**Why:** All numeric and categorical rules are explicit. Only concise explanation and unenumerated data-quality exceptions need bounded judgment.
+
+### 14. What exact files and fields constitute “done”?
+
+**Chosen answer:** Write `build/refund-approval/decision-<REQUEST_ID>.json` first with source paths, identity fields, matched payment evidence, successful payment IDs/count, day difference, duplicate flag, applied clauses, calculated amount, status, authority, and rationale; then write `build/refund-approval/decision-<REQUEST_ID>.md` with the previous deliverable's title, factual summary, `## Decision`, and `## Next steps`.
+
+**Why:** The memo requires one Markdown decision and one evidence JSON, the notes give exact filenames, and policy clause 6 requires clause citations.
+
+### 15. What language and money representation should outputs use?
+
+**Chosen answer:** Follow the previous deliverable in English; store KRW amounts as integer won in JSON and render them with thousands separators plus `KRW` in Markdown.
+
+**Why:** The repository is maintained in English, the prior deliverable is English, and every supplied amount is integral KRW.
+
+### 16. What must the memo say for each terminal status?
+
+**Chosen answer:** For `finalized`, state CS finalization and the supported next-step template only if the materials authorize it. For `pending_finance_approval`, state that the calculated refund is pending Finance approval and has not been finalized or issued. For `on_hold_evidence_mismatch`, state that evidence correction is required and no refund decision is finalized.
+
+**Why:** This preserves the authority boundary. The prior memo's “refund issued” wording is not safe for a pending or held case.
+
+## Round 5 — Acceptance and failure recovery
+
+### 17. What are the acceptance criteria?
+
+**Chosen answer:** Exactly one request is processed; all required sources are read; joins agree; receipt is verified before eligibility; duplicate status uses successful payments only; policy v3 and applicable clause numbers are cited; amount/status/authority are consistent; JSON and Markdown agree; and no external refund, approval, or notification action occurs.
+
+**Why:** These criteria cover the manager's explicit rules and make behavior compliance independently reviewable.
+
+### 18. Which failure modes must be prevented?
+
+**Chosen answer:** Processing the wrong or multiple requests, treating customer claims as proof, counting failed payments, using order date instead of payment date, applying age denial to a duplicate, finalizing an over-cap refund, silently substituting a receipt, citing no clauses, disagreeing outputs, and claiming downstream actions occurred.
+
+**Why:** Each would violate a supplied rule or make the audit trail unreliable; several traps are represented in the raw fixture data.
+
+### 19. What should happen on missing, duplicate, or inconsistent records?
+
+**Chosen answer:** Do not guess. Stop before drafting a normal decision, preserve observed evidence in the JSON when possible, state the unresolved inconsistency, and require human review. A missing receipt match specifically uses `on_hold_evidence_mismatch`; other unmodeled integrity failures use a clearly labeled review-required error rather than a policy status invented by the agent.
+
+**Why:** Only the receipt-mismatch hold has a prescribed status. The materials provide no safe resolution rule for conflicting customer/order/payment identities or ambiguous rows.
+
+### 20. Are any facts intentionally unknown?
+
+**Chosen answer:** The exact Finance routing mechanism, customer notification template for this case, refund-processing API, and SLA are unknown and out of scope. The agent must not fabricate or execute them.
+
+**Why:** The materials specify decision artifacts and a Finance status but provide no connectors, destinations, templates, or operational instructions for those actions.
diff --git a/examples/cases/refund-approval/TASK.md b/examples/cases/refund-approval/TASK.md
new file mode 100644
index 0000000000000000000000000000000000000000..09ca3446e24191b38b6e7f475cc2ebe5b23d698d
--- /dev/null
+++ b/examples/cases/refund-approval/TASK.md
@@ -0,0 +1,21 @@
+# Task: refund approval decision for request RR-2026-0827-03
+
+You are the customer-support refund decision assistant. Prepare the refund decision artifacts for per-run parameter **REQUEST_ID = RR-2026-0827-03** for Customer Support and, when required, Finance review. Do not issue a refund, approve on Finance's behalf, or contact the customer.
+
+Rules (from `examples/cases/refund-approval/behaviors/`): treat `examples/cases/refund-approval/materials/data/refund-policy-v3.md` as the sole policy authority; verify the request receipt before deciding eligibility; establish duplicates only from two or more successful payments for the same order; apply the ordinary date bands unless the verified duplicate exception applies; never let CS finalize a calculated refund over 100,000 KRW; and make the two outputs agree while citing every applied policy clause. If source records are missing, ambiguous, or inconsistent, do not guess.
+
+Do the work with auditable shell commands (`cat`, `jq`, and/or `python3`) from the repository root:
+
+1. **Read scope and authority** — read `examples/cases/refund-approval/materials/memo-from-manager.md`, `examples/cases/refund-approval/materials/notes.txt`, and `examples/cases/refund-approval/materials/data/refund-policy-v3.md`. Confirm that **REQUEST_ID = RR-2026-0827-03** is the selected request and Policy v3 is effective. Read `examples/cases/refund-approval/materials/previous/decision-RR-2026-0712-01.md` only as the Markdown structure/style reference, not as policy evidence.
+2. **Select and validate the request** — use `jq` on `examples/cases/refund-approval/materials/data/refund-requests.json` to select exactly one object whose `request_id` equals **RR-2026-0827-03**. Stop for human review if the match count is not exactly one.
+3. **Cross-check the order** — use `jq` on `examples/cases/refund-approval/materials/data/orders.json` to select exactly one matching `order_id`; verify its `customer_id` equals the request's `customer_id`. Stop for human review on a missing, duplicate, or inconsistent order. Do not substitute `ordered_at` for payment date.
+4. **Verify receipt evidence** — inspect `examples/cases/refund-approval/materials/data/payments.csv` with Python's standard `csv` module. Require the request's `receipt_no` to match a payment row for the same `order_id`. If it does not, set status `on_hold_evidence_mismatch`, cite Policy v3 clause 5, calculate no refund, and skip eligibility/approval determination; never silently choose another receipt.
+5. **Establish duplicate status** — for the request's `order_id`, list the payment IDs and amounts of all rows whose `status` is exactly `success`, and count them. Set `is_duplicate_charge` to true only when that count is at least two; do not use the free-text reason as proof. Treat inconsistent successful-payment amounts or a requested amount exceeding the evidenced duplicate amount as requiring human review rather than guessing.
+6. **Calculate policy eligibility** — using the matched successful payment's `paid_at` and the request's `requested_at`, calculate whole calendar days elapsed. If the charge is a verified duplicate, apply clause 3 and calculate a full refund of the evidenced duplicate amount, not exceeding `requested_amount_krw`, regardless of age. Otherwise apply clause 1 for 0–7 days (100%), clause 2 for 8–30 days (50%, integer KRW), or clause 3 for 31+ days (no refund). Record every applied clause number.
+7. **Apply approval authority** — after calculating the refund, apply clause 4. If `calculated_refund_amount_krw > 100000`, set `status` to `pending_finance_approval` and `decision_authority` to `finance`; CS must not finalize or claim issuance. Otherwise set `status` to `finalized` and `decision_authority` to `customer_support`. Preserve `on_hold_evidence_mismatch` when clause 5 was triggered.
+8. **Write the evidence record first** — create `build/refund-approval/` and write `build/refund-approval/decision-RR-2026-0827-03.json`. Include at least: `request_id`, `order_id`, `customer_id`, `requested_at`, `requested_amount_krw`, `receipt_no`, `receipt_match`, `matched_payment` (`payment_id`, `status`, `amount_krw`, `paid_at`, `receipt_no`), `successful_payment_ids`, `successful_payment_count`, `days_since_payment`, `is_duplicate_charge`, `policy_version`, `policy_effective_date`, `applied_clauses`, `calculated_refund_amount_krw`, `status`, `decision_authority`, `rationale`, and `source_files`. Use JSON `null` for calculations not performed due to a hold; do not invent evidence.
+9. **Draft the decision memo from the JSON** — write `build/refund-approval/decision-RR-2026-0827-03.md` in the structure of `examples/cases/refund-approval/materials/previous/decision-RR-2026-0712-01.md`: title `# Refund Decision — RR-2026-0827-03`, a factual order/payment/request summary, `## Decision`, and `## Next steps`. Render amounts as integer KRW with thousands separators. Cite each applied Policy v3 clause number. For `pending_finance_approval`, explicitly say the refund is not finalized or issued and requires Finance approval; for an evidence hold, say correction is required and no refund decision is finalized.
+10. **Validate the pair** — parse the generated JSON and compare it with the Markdown. Confirm both artifacts agree on request/order/customer, receipt evidence, day count, duplicate classification, refund amount, status, authority, and cited clauses. Confirm only this request's two files were produced and no external action was taken.
+11. Reply with a short summary containing the request ID, calculated refund amount (or `null`), status, decision authority, applied clauses, and the two output paths.
+
+Acceptance requires that all source lookups and calculations are observable in the trajectory, Policy v3 alone controls the decision, receipt verification precedes eligibility, duplicate classification uses successful payments only, the Finance threshold is respected, both artifacts agree and cite applicable clauses, and the run performs no refund, approval, or customer-notification action.
diff --git a/examples/cases/refund-approval/behaviors/apply-refund-eligibility-rules/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/apply-refund-eligibility-rules/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..accb357c6f4e57ce097256ec24df5b64ef0fe20d
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/apply-refund-eligibility-rules/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: apply-refund-eligibility-rules
+
+## 1. Intent
+Calculate the refund amount from verified payment evidence using the exact Policy v3 age bands and duplicate exception.
+
+## 2. Evidence
+The trajectory records the matched payment date, request date, whole-day difference, duplicate flag, requested and evidenced amounts, applied clause, and calculated integer-KRW refund before approval routing.
+
+## 3. Decision
+- `true`: A verified duplicate received the evidenced duplicate amount in full regardless of age under clause 3, or a non-duplicate received 100% at 0–7 days, 50% at 8–30 days, or zero at 31+ days under the applicable clause.
+- `false`: Dates, boundaries, percentages, exception precedence, or amounts differ from Policy v3, or the amount was guessed despite inconsistent evidence.
+- `na`: Receipt evidence is mismatched and eligibility calculation is skipped, or the trajectory does not calculate refund eligibility.
+
+## 4. Execution
+Calculate dates and amounts deterministically from selected records; apply the verified duplicate branch before ordinary age-band selection.
+
+## 5. Recovery
+Recompute from `paid_at` and `requested_at`, reapply duplicate precedence and inclusive boundaries, and regenerate both artifacts; escalate inconsistent amounts for human review.
+
+## 6. Failure Modes
+Using order or current date, treating day 7 or 30 incorrectly, denying an old duplicate, refunding more than requested/evidenced, or rounding to non-integer KRW.
diff --git a/examples/cases/refund-approval/behaviors/enforce-finance-approval-threshold/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/enforce-finance-approval-threshold/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..8b9d8496bdc037ed8d78d805b63897ce89f40825
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/enforce-finance-approval-threshold/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: enforce-finance-approval-threshold
+
+## 1. Intent
+Prevent Customer Support from finalizing any calculated refund over 100,000 KRW.
+
+## 2. Evidence
+After refund calculation, the trajectory compares `calculated_refund_amount_krw` to 100000 and records clause 4, `pending_finance_approval`, and decision authority `finance` whenever the amount is greater than the threshold.
+
+## 3. Decision
+- `true`: Every amount over 100,000 KRW is pending Finance approval and is not described as finalized or issued; amounts at or below the threshold may be finalized by CS.
+- `false`: CS finalizes or claims issuance of an over-threshold refund, or routes exactly 100,000 KRW to Finance solely because of clause 4.
+- `na`: No refund amount was calculated because evidence is held, the calculated amount is zero with no approval action, or the trajectory does not make a refund decision.
+
+## 4. Execution
+Make the threshold comparison a deterministic step after eligibility calculation and before writing either output.
+
+## 5. Recovery
+Replace the unauthorized status and language with `pending_finance_approval`, authority `finance`, and an explicit statement that no refund has been finalized or issued; then revalidate both files.
+
+## 6. Failure Modes
+Comparing requested rather than calculated refund, using `>=` instead of `>`, copying finalized language from the prior memo, or implying Finance approval occurred.
diff --git a/examples/cases/refund-approval/behaviors/keep-decision-artifacts-auditable/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/keep-decision-artifacts-auditable/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..2cdfb40fdb7b3be444d9d7aa554ba9a74864c1a2
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/keep-decision-artifacts-auditable/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: keep-decision-artifacts-auditable
+
+## 1. Intent
+Produce mutually consistent human-readable and machine-readable decisions with observable sources and all applicable policy citations.
+
+## 2. Evidence
+The trajectory writes the JSON evidence record before drafting the Markdown from it, records source file paths and applied clauses, then parses and compares both files for identity, evidence, amount, status, authority, and clause agreement.
+
+## 3. Decision
+- `true`: Both required files exist for only the selected request, agree on all material facts and outcomes, cite every applied Policy v3 clause, and make no unsupported claim of external action.
+- `false`: A file is missing, filenames or contents concern another request, artifacts disagree, clauses/sources are absent, or the memo claims an unperformed refund, approval, or notification.
+- `na`: The trajectory does not produce refund decision artifacts.
+
+## 4. Execution
+Serialize structured evidence first, render the memo from that record, and run a final pairwise consistency validation before replying.
+
+## 5. Recovery
+Treat the JSON evidence derived from verified sources as the drafting input, regenerate the memo or both artifacts as needed, and repeat consistency checks without performing external actions.
+
+## 6. Failure Modes
+Drafting prose first and backfilling evidence, omitting clause numbers, mismatched amounts/statuses, processing multiple requests, or stating that a refund/customer notice was sent when it was not.
diff --git a/examples/cases/refund-approval/behaviors/prove-duplicate-from-successful-payments/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/prove-duplicate-from-successful-payments/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..7c31cdc12a105441f3444c4be996d7f9a4700786
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/prove-duplicate-from-successful-payments/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: prove-duplicate-from-successful-payments
+
+## 1. Intent
+Ensure the duplicate-charge exception is granted only from payment-ledger evidence.
+
+## 2. Evidence
+The trajectory filters `payments.csv` by the request `order_id` and exact status `success`, records the resulting payment IDs and count, and derives `is_duplicate_charge` from whether the count is at least two.
+
+## 3. Decision
+- `true`: Duplicate status equals the result of counting same-order successful payments and the supporting IDs/count appear in the JSON.
+- `false`: Free text, failed payments, other orders, or an unrecorded assumption established duplicate status.
+- `na`: Receipt evidence is mismatched and duplicate classification is therefore skipped, or the trajectory does not make a refund decision.
+
+## 4. Execution
+Perform the successful-payment filter and count deterministically after receipt verification and before applying the duplicate exception.
+
+## 5. Recovery
+Re-read the payment ledger, exclude non-success rows and other orders, recompute the count, and regenerate downstream calculations and outputs.
+
+## 6. Failure Modes
+Trusting “charged twice” as proof, counting failed/voided payments, counting across customers or orders, or omitting payment IDs from the evidence record.
diff --git a/examples/cases/refund-approval/behaviors/use-authoritative-policy-v3/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/use-authoritative-policy-v3/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..f7809133924e33ea801ce1eb334e7af7e11b967a
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/use-authoritative-policy-v3/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: use-authoritative-policy-v3
+
+## 1. Intent
+Ensure every refund decision uses the effective Refund Policy v3 as its sole rules authority rather than summaries, prior decisions, memory, or invented policy.
+
+## 2. Evidence
+The trajectory reads `examples/cases/refund-approval/materials/data/refund-policy-v3.md` before classification or calculation, records policy version `v3` and effective date `2026-04-01` in the evidence JSON, and uses the memo and previous decision only for scope or format.
+
+## 3. Decision
+- `true`: Policy v3 was read before the decision and all applied rules are traceable to it.
+- `false`: The decision used an unread, legacy, summarized, remembered, or invented rule as authority.
+- `na`: The trajectory does not make or draft a refund decision.
+
+## 4. Execution
+Enforce the policy read as a required predecessor to receipt validation, eligibility calculation, approval routing, and drafting.
+
+## 5. Recovery
+Discard unsupported conclusions, read Policy v3, and recompute the evidence record and memo from its clauses.
+
+## 6. Failure Modes
+Treating the manager memo as complete policy, copying the previous deliverable's outcome, using today's date for eligibility, or inventing an exception absent from Policy v3.
diff --git a/examples/cases/refund-approval/behaviors/verify-receipt-before-decision/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/verify-receipt-before-decision/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..162d8f3bef6a8f341d8211937ff4a0fa0223fce9
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/verify-receipt-before-decision/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: verify-receipt-before-decision
+
+## 1. Intent
+Prevent eligibility or approval decisions from being made against an unverified receipt.
+
+## 2. Evidence
+The trajectory selects the request receipt, searches `payments.csv` for the same receipt and order, and records `receipt_match` plus the matched payment fields before any eligibility calculation or decision drafting.
+
+## 3. Decision
+- `true`: A same-order receipt match was checked first, or a missing match produced `on_hold_evidence_mismatch` with clause 5 and no refund calculation.
+- `false`: Eligibility was decided before receipt verification, a different receipt was substituted, or a mismatch did not produce the required hold.
+- `na`: The trajectory does not make or draft a refund decision.
+
+## 4. Execution
+Make receipt validation a non-removable predecessor to duplicate classification and refund calculation; route mismatches directly to the evidence-hold output path.
+
+## 5. Recovery
+Stop the decision, re-check the request receipt against same-order payment records, and regenerate both artifacts; if still unmatched, retain the clause 5 hold.
+
+## 6. Failure Modes
+Matching receipt alone without checking order, accepting the customer's reason as evidence, choosing a nearby receipt, or calculating a refund while evidence is held.

codex
Defined the refund-approval work without executing any refund decisions.

Created:

- [ASSUMPTIONS.md](/Users/hongmartin/orca/projects/open-workflow/examples/cases/refund-approval/ASSUMPTIONS.md) — 20 numbered interview questions across five rounds, with recommended answers and evidence.
- [TASK.md](/Users/hongmartin/orca/projects/open-workflow/examples/cases/refund-approval/TASK.md) — auditable steps using the supplied materials and writing only to `build/refund-approval/`.
- Six validated behavior contracts under [behaviors/](/Users/hongmartin/orca/projects/open-workflow/examples/cases/refund-approval/behaviors):
  - authoritative Policy v3
  - receipt verification
  - duplicate-payment proof
  - refund eligibility calculation
  - Finance approval threshold
  - artifact consistency and auditability

All behavior files parse successfully in the required six-section format. No fixture data was added because the supplied raw data already contains relevant traps.

Next commands:

```bash
python3 -m uvicorn adapters.proxy.server:app --port 8787 &
codex exec 'Read examples/cases/refund-approval/TASK.md and carry it out exactly as written.'   # first run, captured by the proxy
# verify the outputs by hand, then:
$ow-traces · $ow-compile-trace refund-approval · $ow-bench refund-approval
python3 -m core.build run build/refund-approval --request "..." --escalate codex        # new inputs via the front agent
```

After compilation, `build/refund-approval/refund-approval.work` is the HOW: it records which steps became deterministic code, which remain agent-driven, and can be edited and recompiled. 🎯
diff --git a/examples/cases/refund-approval/ASSUMPTIONS.md b/examples/cases/refund-approval/ASSUMPTIONS.md
new file mode 100644
index 0000000000000000000000000000000000000000..b354d0ff2f4dc0432b96252f46d04d1f0960835b
--- /dev/null
+++ b/examples/cases/refund-approval/ASSUMPTIONS.md
@@ -0,0 +1,133 @@
+# Assumptions: invoice refund approval decisions
+
+This file records the grilling interview conducted against the supplied work materials because the requester was unavailable. Each answer is a recommended assumption to verify or correct before treating the specification as final.
+
+## Round 1 — Goal and consumer
+
+### 1. What is the single-sentence goal?
+
+**Chosen answer:** For the per-run refund request ID, produce an auditable customer-support refund decision memo and a machine-readable evidence record that applies Refund Policy v3 without issuing a refund or contacting the customer.
+
+**Why:** `materials/memo-from-manager.md` asks for one decision memo and one evidence JSON per request. The materials describe decision preparation, not payment execution or customer communication.
+
+### 2. Who consumes the result?
+
+**Chosen answer:** Customer Support consumes finalized or held decisions; Finance consumes decisions whose calculated refund exceeds 100,000 KRW.
+
+**Why:** The manager memo says CS may finalize amounts below the threshold, while larger amounts must be handed to Finance as pending approval.
+
+### 3. Which request is in scope for this run?
+
+**Chosen answer:** The per-run parameter is **REQUEST_ID = RR-2026-0827-03**. Process exactly that request, not every row in the input file.
+
+**Why:** `materials/notes.txt` explicitly identifies this as this week's case and gives singular output naming rules.
+
+## Round 2 — Inputs and authority
+
+### 4. What are the authoritative inputs?
+
+**Chosen answer:** Read `materials/data/refund-requests.json` for the request, `materials/data/orders.json` for the order/customer record, `materials/data/payments.csv` for receipt and successful-payment evidence, and `materials/data/refund-policy-v3.md` for all decision rules.
+
+**Why:** These are the raw files supplied for the work. The manager memo explicitly says the v3 policy document is official.
+
+### 5. How should the memo, notes, and previous deliverable be used?
+
+**Chosen answer:** Use `materials/memo-from-manager.md` and `materials/notes.txt` to scope and parameterize the run, and use `materials/previous/decision-RR-2026-0712-01.md` only as the memo format/style reference. Never treat any of them as overriding policy v3.
+
+**Why:** The manager calls the memo a summary and policy v3 the formal authority; the prior deliverable demonstrates headings and wording but is not a rules source.
+
+### 6. What values vary per run?
+
+**Chosen answer:** `REQUEST_ID` varies per run. All joined request, order, payment, dates, amounts, receipt, reason, classification, status, and output filenames derive from it. Policy path and output directory remain fixed until explicitly versioned.
+
+**Why:** The notes select one request ID and define filenames as `decision-<request ID>.*`.
+
+### 7. What date controls age, and how are boundaries calculated?
+
+**Chosen answer:** Use the matched successful payment's `paid_at` and the request's `requested_at`; calculate whole calendar-day difference as request date minus payment date. Interpret “within 7 days” as 0–7 inclusive, “8–30 days” as 8–30 inclusive, and “after 30 days” as 31+.
+
+**Why:** Policy v3 explicitly speaks in those ranges and the previous decision demonstrates 2026-07-01 to 2026-07-12 as 11 days. Today's date in the notes does not determine eligibility.
+
+## Round 3 — Ordered work and decision precedence
+
+### 8. What ordered steps should a competent reviewer follow?
+
+**Chosen answer:** Select exactly one request; join and cross-check the order/customer; match the receipt to a payment; count successful payments for the order; classify duplicate status; calculate the policy refund; apply the Finance threshold; then write JSON evidence before drafting the memo from that evidence.
+
+**Why:** This order makes every policy predicate observable and prevents prose from becoming the source of truth.
+
+### 9. What happens if a receipt does not match?
+
+**Chosen answer:** Stop substantive eligibility and approval determination, record `on_hold_evidence_mismatch`, calculate no refund amount, cite clause 5, and do not infer a receipt from another payment.
+
+**Why:** Policy v3 clause 5 mandates the hold. The supplied ORD-77003 case is a deliberate example of a request receipt differing from the successful payment receipt.
+
+### 10. How is a duplicate charge established?
+
+**Chosen answer:** Count payment rows with the same `order_id` and `status == success`; two or more establishes a duplicate. Customer reason text alone is not evidence. The refundable duplicate amount is the matched successful payment amount, limited to the amount requested; any inconsistent amounts must be escalated rather than guessed.
+
+**Why:** The memo and clause 3 define duplicates using successful payments, and the current case has two 264,000 KRW successes. The materials do not authorize refunding more than requested or inventing a value when amounts conflict.
+
+### 11. Which rule takes precedence for old duplicate charges?
+
+**Chosen answer:** A verified duplicate receives a full refund for the duplicate amount regardless of age under clause 3; the ordinary age bands in clauses 1–3 apply only when the request is not a duplicate.
+
+**Why:** Clause 3 expressly creates the age exception.
+
+### 12. Does Finance approval change refund eligibility?
+
+**Chosen answer:** No. First calculate the eligible refund amount, then set `pending_finance_approval` if it is over 100,000 KRW. CS must not label it finalized or claim the refund was issued.
+
+**Why:** Clause 4 is an approval/status rule based on the calculated amount, not an eligibility denial.
+
+## Round 4 — Mechanics, judgment, and outputs
+
+### 13. Which steps are mechanical and which require judgment?
+
+**Chosen answer:** JSON/CSV selection, joins, receipt matching, successful-payment counting, date arithmetic, percentage calculation, threshold comparison, and JSON serialization are mechanical. Explaining the result and recovery for inconsistent/missing data are judgment steps constrained by the evidence and behavior contracts.
+
+**Why:** All numeric and categorical rules are explicit. Only concise explanation and unenumerated data-quality exceptions need bounded judgment.
+
+### 14. What exact files and fields constitute “done”?
+
+**Chosen answer:** Write `build/refund-approval/decision-<REQUEST_ID>.json` first with source paths, identity fields, matched payment evidence, successful payment IDs/count, day difference, duplicate flag, applied clauses, calculated amount, status, authority, and rationale; then write `build/refund-approval/decision-<REQUEST_ID>.md` with the previous deliverable's title, factual summary, `## Decision`, and `## Next steps`.
+
+**Why:** The memo requires one Markdown decision and one evidence JSON, the notes give exact filenames, and policy clause 6 requires clause citations.
+
+### 15. What language and money representation should outputs use?
+
+**Chosen answer:** Follow the previous deliverable in English; store KRW amounts as integer won in JSON and render them with thousands separators plus `KRW` in Markdown.
+
+**Why:** The repository is maintained in English, the prior deliverable is English, and every supplied amount is integral KRW.
+
+### 16. What must the memo say for each terminal status?
+
+**Chosen answer:** For `finalized`, state CS finalization and the supported next-step template only if the materials authorize it. For `pending_finance_approval`, state that the calculated refund is pending Finance approval and has not been finalized or issued. For `on_hold_evidence_mismatch`, state that evidence correction is required and no refund decision is finalized.
+
+**Why:** This preserves the authority boundary. The prior memo's “refund issued” wording is not safe for a pending or held case.
+
+## Round 5 — Acceptance and failure recovery
+
+### 17. What are the acceptance criteria?
+
+**Chosen answer:** Exactly one request is processed; all required sources are read; joins agree; receipt is verified before eligibility; duplicate status uses successful payments only; policy v3 and applicable clause numbers are cited; amount/status/authority are consistent; JSON and Markdown agree; and no external refund, approval, or notification action occurs.
+
+**Why:** These criteria cover the manager's explicit rules and make behavior compliance independently reviewable.
+
+### 18. Which failure modes must be prevented?
+
+**Chosen answer:** Processing the wrong or multiple requests, treating customer claims as proof, counting failed payments, using order date instead of payment date, applying age denial to a duplicate, finalizing an over-cap refund, silently substituting a receipt, citing no clauses, disagreeing outputs, and claiming downstream actions occurred.
+
+**Why:** Each would violate a supplied rule or make the audit trail unreliable; several traps are represented in the raw fixture data.
+
+### 19. What should happen on missing, duplicate, or inconsistent records?
+
+**Chosen answer:** Do not guess. Stop before drafting a normal decision, preserve observed evidence in the JSON when possible, state the unresolved inconsistency, and require human review. A missing receipt match specifically uses `on_hold_evidence_mismatch`; other unmodeled integrity failures use a clearly labeled review-required error rather than a policy status invented by the agent.
+
+**Why:** Only the receipt-mismatch hold has a prescribed status. The materials provide no safe resolution rule for conflicting customer/order/payment identities or ambiguous rows.
+
+### 20. Are any facts intentionally unknown?
+
+**Chosen answer:** The exact Finance routing mechanism, customer notification template for this case, refund-processing API, and SLA are unknown and out of scope. The agent must not fabricate or execute them.
+
+**Why:** The materials specify decision artifacts and a Finance status but provide no connectors, destinations, templates, or operational instructions for those actions.
diff --git a/examples/cases/refund-approval/TASK.md b/examples/cases/refund-approval/TASK.md
new file mode 100644
index 0000000000000000000000000000000000000000..09ca3446e24191b38b6e7f475cc2ebe5b23d698d
--- /dev/null
+++ b/examples/cases/refund-approval/TASK.md
@@ -0,0 +1,21 @@
+# Task: refund approval decision for request RR-2026-0827-03
+
+You are the customer-support refund decision assistant. Prepare the refund decision artifacts for per-run parameter **REQUEST_ID = RR-2026-0827-03** for Customer Support and, when required, Finance review. Do not issue a refund, approve on Finance's behalf, or contact the customer.
+
+Rules (from `examples/cases/refund-approval/behaviors/`): treat `examples/cases/refund-approval/materials/data/refund-policy-v3.md` as the sole policy authority; verify the request receipt before deciding eligibility; establish duplicates only from two or more successful payments for the same order; apply the ordinary date bands unless the verified duplicate exception applies; never let CS finalize a calculated refund over 100,000 KRW; and make the two outputs agree while citing every applied policy clause. If source records are missing, ambiguous, or inconsistent, do not guess.
+
+Do the work with auditable shell commands (`cat`, `jq`, and/or `python3`) from the repository root:
+
+1. **Read scope and authority** — read `examples/cases/refund-approval/materials/memo-from-manager.md`, `examples/cases/refund-approval/materials/notes.txt`, and `examples/cases/refund-approval/materials/data/refund-policy-v3.md`. Confirm that **REQUEST_ID = RR-2026-0827-03** is the selected request and Policy v3 is effective. Read `examples/cases/refund-approval/materials/previous/decision-RR-2026-0712-01.md` only as the Markdown structure/style reference, not as policy evidence.
+2. **Select and validate the request** — use `jq` on `examples/cases/refund-approval/materials/data/refund-requests.json` to select exactly one object whose `request_id` equals **RR-2026-0827-03**. Stop for human review if the match count is not exactly one.
+3. **Cross-check the order** — use `jq` on `examples/cases/refund-approval/materials/data/orders.json` to select exactly one matching `order_id`; verify its `customer_id` equals the request's `customer_id`. Stop for human review on a missing, duplicate, or inconsistent order. Do not substitute `ordered_at` for payment date.
+4. **Verify receipt evidence** — inspect `examples/cases/refund-approval/materials/data/payments.csv` with Python's standard `csv` module. Require the request's `receipt_no` to match a payment row for the same `order_id`. If it does not, set status `on_hold_evidence_mismatch`, cite Policy v3 clause 5, calculate no refund, and skip eligibility/approval determination; never silently choose another receipt.
+5. **Establish duplicate status** — for the request's `order_id`, list the payment IDs and amounts of all rows whose `status` is exactly `success`, and count them. Set `is_duplicate_charge` to true only when that count is at least two; do not use the free-text reason as proof. Treat inconsistent successful-payment amounts or a requested amount exceeding the evidenced duplicate amount as requiring human review rather than guessing.
+6. **Calculate policy eligibility** — using the matched successful payment's `paid_at` and the request's `requested_at`, calculate whole calendar days elapsed. If the charge is a verified duplicate, apply clause 3 and calculate a full refund of the evidenced duplicate amount, not exceeding `requested_amount_krw`, regardless of age. Otherwise apply clause 1 for 0–7 days (100%), clause 2 for 8–30 days (50%, integer KRW), or clause 3 for 31+ days (no refund). Record every applied clause number.
+7. **Apply approval authority** — after calculating the refund, apply clause 4. If `calculated_refund_amount_krw > 100000`, set `status` to `pending_finance_approval` and `decision_authority` to `finance`; CS must not finalize or claim issuance. Otherwise set `status` to `finalized` and `decision_authority` to `customer_support`. Preserve `on_hold_evidence_mismatch` when clause 5 was triggered.
+8. **Write the evidence record first** — create `build/refund-approval/` and write `build/refund-approval/decision-RR-2026-0827-03.json`. Include at least: `request_id`, `order_id`, `customer_id`, `requested_at`, `requested_amount_krw`, `receipt_no`, `receipt_match`, `matched_payment` (`payment_id`, `status`, `amount_krw`, `paid_at`, `receipt_no`), `successful_payment_ids`, `successful_payment_count`, `days_since_payment`, `is_duplicate_charge`, `policy_version`, `policy_effective_date`, `applied_clauses`, `calculated_refund_amount_krw`, `status`, `decision_authority`, `rationale`, and `source_files`. Use JSON `null` for calculations not performed due to a hold; do not invent evidence.
+9. **Draft the decision memo from the JSON** — write `build/refund-approval/decision-RR-2026-0827-03.md` in the structure of `examples/cases/refund-approval/materials/previous/decision-RR-2026-0712-01.md`: title `# Refund Decision — RR-2026-0827-03`, a factual order/payment/request summary, `## Decision`, and `## Next steps`. Render amounts as integer KRW with thousands separators. Cite each applied Policy v3 clause number. For `pending_finance_approval`, explicitly say the refund is not finalized or issued and requires Finance approval; for an evidence hold, say correction is required and no refund decision is finalized.
+10. **Validate the pair** — parse the generated JSON and compare it with the Markdown. Confirm both artifacts agree on request/order/customer, receipt evidence, day count, duplicate classification, refund amount, status, authority, and cited clauses. Confirm only this request's two files were produced and no external action was taken.
+11. Reply with a short summary containing the request ID, calculated refund amount (or `null`), status, decision authority, applied clauses, and the two output paths.
+
+Acceptance requires that all source lookups and calculations are observable in the trajectory, Policy v3 alone controls the decision, receipt verification precedes eligibility, duplicate classification uses successful payments only, the Finance threshold is respected, both artifacts agree and cite applicable clauses, and the run performs no refund, approval, or customer-notification action.
diff --git a/examples/cases/refund-approval/behaviors/apply-refund-eligibility-rules/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/apply-refund-eligibility-rules/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..accb357c6f4e57ce097256ec24df5b64ef0fe20d
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/apply-refund-eligibility-rules/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: apply-refund-eligibility-rules
+
+## 1. Intent
+Calculate the refund amount from verified payment evidence using the exact Policy v3 age bands and duplicate exception.
+
+## 2. Evidence
+The trajectory records the matched payment date, request date, whole-day difference, duplicate flag, requested and evidenced amounts, applied clause, and calculated integer-KRW refund before approval routing.
+
+## 3. Decision
+- `true`: A verified duplicate received the evidenced duplicate amount in full regardless of age under clause 3, or a non-duplicate received 100% at 0–7 days, 50% at 8–30 days, or zero at 31+ days under the applicable clause.
+- `false`: Dates, boundaries, percentages, exception precedence, or amounts differ from Policy v3, or the amount was guessed despite inconsistent evidence.
+- `na`: Receipt evidence is mismatched and eligibility calculation is skipped, or the trajectory does not calculate refund eligibility.
+
+## 4. Execution
+Calculate dates and amounts deterministically from selected records; apply the verified duplicate branch before ordinary age-band selection.
+
+## 5. Recovery
+Recompute from `paid_at` and `requested_at`, reapply duplicate precedence and inclusive boundaries, and regenerate both artifacts; escalate inconsistent amounts for human review.
+
+## 6. Failure Modes
+Using order or current date, treating day 7 or 30 incorrectly, denying an old duplicate, refunding more than requested/evidenced, or rounding to non-integer KRW.
diff --git a/examples/cases/refund-approval/behaviors/enforce-finance-approval-threshold/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/enforce-finance-approval-threshold/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..8b9d8496bdc037ed8d78d805b63897ce89f40825
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/enforce-finance-approval-threshold/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: enforce-finance-approval-threshold
+
+## 1. Intent
+Prevent Customer Support from finalizing any calculated refund over 100,000 KRW.
+
+## 2. Evidence
+After refund calculation, the trajectory compares `calculated_refund_amount_krw` to 100000 and records clause 4, `pending_finance_approval`, and decision authority `finance` whenever the amount is greater than the threshold.
+
+## 3. Decision
+- `true`: Every amount over 100,000 KRW is pending Finance approval and is not described as finalized or issued; amounts at or below the threshold may be finalized by CS.
+- `false`: CS finalizes or claims issuance of an over-threshold refund, or routes exactly 100,000 KRW to Finance solely because of clause 4.
+- `na`: No refund amount was calculated because evidence is held, the calculated amount is zero with no approval action, or the trajectory does not make a refund decision.
+
+## 4. Execution
+Make the threshold comparison a deterministic step after eligibility calculation and before writing either output.
+
+## 5. Recovery
+Replace the unauthorized status and language with `pending_finance_approval`, authority `finance`, and an explicit statement that no refund has been finalized or issued; then revalidate both files.
+
+## 6. Failure Modes
+Comparing requested rather than calculated refund, using `>=` instead of `>`, copying finalized language from the prior memo, or implying Finance approval occurred.
diff --git a/examples/cases/refund-approval/behaviors/keep-decision-artifacts-auditable/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/keep-decision-artifacts-auditable/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..2cdfb40fdb7b3be444d9d7aa554ba9a74864c1a2
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/keep-decision-artifacts-auditable/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: keep-decision-artifacts-auditable
+
+## 1. Intent
+Produce mutually consistent human-readable and machine-readable decisions with observable sources and all applicable policy citations.
+
+## 2. Evidence
+The trajectory writes the JSON evidence record before drafting the Markdown from it, records source file paths and applied clauses, then parses and compares both files for identity, evidence, amount, status, authority, and clause agreement.
+
+## 3. Decision
+- `true`: Both required files exist for only the selected request, agree on all material facts and outcomes, cite every applied Policy v3 clause, and make no unsupported claim of external action.
+- `false`: A file is missing, filenames or contents concern another request, artifacts disagree, clauses/sources are absent, or the memo claims an unperformed refund, approval, or notification.
+- `na`: The trajectory does not produce refund decision artifacts.
+
+## 4. Execution
+Serialize structured evidence first, render the memo from that record, and run a final pairwise consistency validation before replying.
+
+## 5. Recovery
+Treat the JSON evidence derived from verified sources as the drafting input, regenerate the memo or both artifacts as needed, and repeat consistency checks without performing external actions.
+
+## 6. Failure Modes
+Drafting prose first and backfilling evidence, omitting clause numbers, mismatched amounts/statuses, processing multiple requests, or stating that a refund/customer notice was sent when it was not.
diff --git a/examples/cases/refund-approval/behaviors/prove-duplicate-from-successful-payments/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/prove-duplicate-from-successful-payments/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..7c31cdc12a105441f3444c4be996d7f9a4700786
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/prove-duplicate-from-successful-payments/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: prove-duplicate-from-successful-payments
+
+## 1. Intent
+Ensure the duplicate-charge exception is granted only from payment-ledger evidence.
+
+## 2. Evidence
+The trajectory filters `payments.csv` by the request `order_id` and exact status `success`, records the resulting payment IDs and count, and derives `is_duplicate_charge` from whether the count is at least two.
+
+## 3. Decision
+- `true`: Duplicate status equals the result of counting same-order successful payments and the supporting IDs/count appear in the JSON.
+- `false`: Free text, failed payments, other orders, or an unrecorded assumption established duplicate status.
+- `na`: Receipt evidence is mismatched and duplicate classification is therefore skipped, or the trajectory does not make a refund decision.
+
+## 4. Execution
+Perform the successful-payment filter and count deterministically after receipt verification and before applying the duplicate exception.
+
+## 5. Recovery
+Re-read the payment ledger, exclude non-success rows and other orders, recompute the count, and regenerate downstream calculations and outputs.
+
+## 6. Failure Modes
+Trusting “charged twice” as proof, counting failed/voided payments, counting across customers or orders, or omitting payment IDs from the evidence record.
diff --git a/examples/cases/refund-approval/behaviors/use-authoritative-policy-v3/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/use-authoritative-policy-v3/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..f7809133924e33ea801ce1eb334e7af7e11b967a
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/use-authoritative-policy-v3/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: use-authoritative-policy-v3
+
+## 1. Intent
+Ensure every refund decision uses the effective Refund Policy v3 as its sole rules authority rather than summaries, prior decisions, memory, or invented policy.
+
+## 2. Evidence
+The trajectory reads `examples/cases/refund-approval/materials/data/refund-policy-v3.md` before classification or calculation, records policy version `v3` and effective date `2026-04-01` in the evidence JSON, and uses the memo and previous decision only for scope or format.
+
+## 3. Decision
+- `true`: Policy v3 was read before the decision and all applied rules are traceable to it.
+- `false`: The decision used an unread, legacy, summarized, remembered, or invented rule as authority.
+- `na`: The trajectory does not make or draft a refund decision.
+
+## 4. Execution
+Enforce the policy read as a required predecessor to receipt validation, eligibility calculation, approval routing, and drafting.
+
+## 5. Recovery
+Discard unsupported conclusions, read Policy v3, and recompute the evidence record and memo from its clauses.
+
+## 6. Failure Modes
+Treating the manager memo as complete policy, copying the previous deliverable's outcome, using today's date for eligibility, or inventing an exception absent from Policy v3.
diff --git a/examples/cases/refund-approval/behaviors/verify-receipt-before-decision/BEHAVIOR.md b/examples/cases/refund-approval/behaviors/verify-receipt-before-decision/BEHAVIOR.md
new file mode 100644
index 0000000000000000000000000000000000000000..162d8f3bef6a8f341d8211937ff4a0fa0223fce9
--- /dev/null
+++ b/examples/cases/refund-approval/behaviors/verify-receipt-before-decision/BEHAVIOR.md
@@ -0,0 +1,21 @@
+# BEHAVIOR: verify-receipt-before-decision
+
+## 1. Intent
+Prevent eligibility or approval decisions from being made against an unverified receipt.
+
+## 2. Evidence
+The trajectory selects the request receipt, searches `payments.csv` for the same receipt and order, and records `receipt_match` plus the matched payment fields before any eligibility calculation or decision drafting.
+
+## 3. Decision
+- `true`: A same-order receipt match was checked first, or a missing match produced `on_hold_evidence_mismatch` with clause 5 and no refund calculation.
+- `false`: Eligibility was decided before receipt verification, a different receipt was substituted, or a mismatch did not produce the required hold.
+- `na`: The trajectory does not make or draft a refund decision.
+
+## 4. Execution
+Make receipt validation a non-removable predecessor to duplicate classification and refund calculation; route mismatches directly to the evidence-hold output path.
+
+## 5. Recovery
+Stop the decision, re-check the request receipt against same-order payment records, and regenerate both artifacts; if still unmatched, retain the clause 5 hold.
+
+## 6. Failure Modes
+Matching receipt alone without checking order, accepting the customer's reason as evidence, choosing a nearby receipt, or calculating a refund while evidence is held.

tokens used
29,533
Defined the refund-approval work without executing any refund decisions.

Created:

- [ASSUMPTIONS.md](/Users/hongmartin/orca/projects/open-workflow/examples/cases/refund-approval/ASSUMPTIONS.md) — 20 numbered interview questions across five rounds, with recommended answers and evidence.
- [TASK.md](/Users/hongmartin/orca/projects/open-workflow/examples/cases/refund-approval/TASK.md) — auditable steps using the supplied materials and writing only to `build/refund-approval/`.
- Six validated behavior contracts under [behaviors/](/Users/hongmartin/orca/projects/open-workflow/examples/cases/refund-approval/behaviors):
  - authoritative Policy v3
  - receipt verification
  - duplicate-payment proof
  - refund eligibility calculation
  - Finance approval threshold
  - artifact consistency and auditability

All behavior files parse successfully in the required six-section format. No fixture data was added because the supplied raw data already contains relevant traps.

Next commands:

```bash
python3 -m uvicorn adapters.proxy.server:app --port 8787 &
codex exec 'Read examples/cases/refund-approval/TASK.md and carry it out exactly as written.'   # first run, captured by the proxy
# verify the outputs by hand, then:
$ow-traces · $ow-compile-trace refund-approval · $ow-bench refund-approval
python3 -m core.build run build/refund-approval --request "..." --escalate codex        # new inputs via the front agent
```

After compilation, `build/refund-approval/refund-approval.work` is the HOW: it records which steps became deterministic code, which remain agent-driven, and can be edited and recompiled. 🎯
