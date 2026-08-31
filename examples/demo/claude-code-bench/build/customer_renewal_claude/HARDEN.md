# Harden — `customer-renewal-claude`

Compile-time harness loop (producer: `codex` · reviewer: deterministic benchmark).

**Result: 5/6 outputs reproduced — converged.**

Stop reason: all reproducible failures fixed. Fix tokens spent: 0 / budget 150,000.

Inherently run-dependent outputs (reported, not chased): `shell_cat`

| iter | failures | attempted | accepted | reverted | fix tokens | score |
| --: | --: | :-- | :-- | :-- | --: | :-- |
| 1 | 1 | read_contracts | read_contracts | — | 0 | 4/6 → 5/6 |
