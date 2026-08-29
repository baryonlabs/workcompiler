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
