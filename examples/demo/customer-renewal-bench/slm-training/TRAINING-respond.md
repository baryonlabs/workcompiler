# Fleet evaluation — `respond`

Held-out customers (never in the training split): CUST-2007, CUST-2010, CUST-2015, CUST-2017, CUST-2022, CUST-2030.
Dataset: 31 rows (recorded 1, fleet 30).

| model | pass | pass rate | avg tokens | avg latency |
| :-- | :-- | --: | --: | --: |
| qwen2.5:3b (raw) | 6/6 | 100% | 1,556 | 2.9 s |

## Per customer

### qwen2.5:3b (raw)

| customer | gate |
| :-- | :-- |
| CUST-2007 | PASS (recall 1.00; grounded 1.00; len ×1.0) |
| CUST-2010 | PASS (recall 1.00; grounded 1.00; len ×1.0) |
| CUST-2015 | PASS (recall 1.00; grounded 1.00; len ×1.0) |
| CUST-2017 | PASS (recall 1.00; grounded 1.00; len ×1.0) |
| CUST-2022 | PASS (recall 1.00; grounded 1.00; len ×1.0) |
| CUST-2030 | PASS (recall 1.00; grounded 1.00; len ×1.0) |
