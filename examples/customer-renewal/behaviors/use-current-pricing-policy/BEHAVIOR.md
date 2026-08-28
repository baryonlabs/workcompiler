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
