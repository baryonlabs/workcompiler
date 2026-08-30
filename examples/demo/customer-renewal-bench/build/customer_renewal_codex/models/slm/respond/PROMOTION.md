# SLM promotion — `respond` of `customer-renewal-codex`

Candidate: `qwen2.5:7b` at `http://127.0.0.1:11434/v1` (local, cost $0) · gate: ≥90% of evaluations PASS, anchor recall ≥90%, grounding ≥90%.

**Result: PROMOTED** — pass rate 100% over 1 recorded example(s).

| | recorded (frontier) | SLM | delta |
| :-- | --: | --: | --: |
| tokens | 20,545 | 4,208 | −79.5% |
| latency | 11.1 s | 14.3 s | 0.78× |

## Evaluations

| step | recorded model → tokens | SLM tokens (prompt + completion) | latency | gate |
| :-- | :-- | --: | --: | :-- |
| step_8 | ? → 20,545 | 4,208 (4,095 + 113) | 14.3 s | PASS (recall 1.00; grounded 1.00; len ×1.0) |

### step_8 — SLM output

```
Renewal proposal completed.

- Recommended seats: **270**
- Annual price: **$116,640**
- Discounts: **10% volume**, **0% loyalty**

Files:

- [Pricing calculation](/Users/hongmartin/orca/projects/open-workflow/build/renewal/pricing-CUST-1001.json)
- [Renewal proposal](/Users/hongmartin/orca/projects/open-workflow/build/renewal/proposal-CUST-1001.md)
```

Recorded (frontier) output:

```
Renewal proposal completed.

- Recommended seats: **270**
- Annual price: **$116,640**
- Discounts: **10% volume**, **0% loyalty**

Files:

- [Pricing calculation](/Users/hongmartin/orca/projects/open-workflow/build/renewal/pricing-CUST-1001.json)
- [Renewal proposal](/Users/hongmartin/orca/projects/open-workflow/build/renewal/proposal-CUST-1001.md)
```

How the gate works: *anchors* are the numbers / ids / file paths the frontier answer stated that also exist in the upstream step outputs; the SLM must restate them (recall) and must not state numbers that exist nowhere in its inputs (grounding). Process invariants are enforced by the compiled upstream steps.
