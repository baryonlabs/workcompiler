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
