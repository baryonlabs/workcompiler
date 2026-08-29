# Benchmark — `refund-approval`

Recorded agent session `01a04b48-a08c-7ad2-88c8-6dba18f81fc8` (`codex_exec`) vs. compiled build `build/refund_approval`.

| | recorded (agent) | compiled (build) | delta |
| :-- | --: | --: | --: |
| LLM tokens | 280,023 | 21,999 | −92.1% |
| wall time | 113.7 s | 5.96 s | 19.1× faster |
| outputs reproduced | — | 11/14 | |
| actions compiled / escalated | — | 6 / 1 | |

## Per action

| action | tier | executor used | tokens rec → comp | latency rec → comp | output match |
| :-- | :-- | :-- | --: | --: | :-- |
| `shell_sed` | code | code:refund_approval/handlers | 14,225 → 0 | 4.0 s → 0.01 s | 1/1 |
| `shell_cat` | code | code:refund_approval/handlers | 16,028 → 0 | 8.2 s → 0.01 s | 1/1 |
| `shell_jq` | code | code:refund_approval/handlers | 107,820 → 0 | 35.9 s → 0.05 s | 3/6 |
| `shell_python3` | code | code:refund_approval/handlers | 59,400 → 0 | 31.3 s → 0.08 s | 3/3 |
| `shell_mkdir` | code | code:refund_approval/handlers | 19,366 → 0 | 4.2 s → 0.01 s | 1/1 |
| `write_decision_rr_2026_0827_03` | code | code:refund_approval/handlers | 41,185 → 0 | 24.3 s → 0.00 s | 2/2 |
| `respond` | frontier_llm | escalated:frontier_llm | 21,999 → 21,999 | 5.8 s → 5.81 s | n/a |

## Token ledger — who spent what

Every recorded step, the model that produced it, and what runs it in the compiled build.

| step | action | recorded model | prompt (cached) + completion = total | compiled executor | compiled tokens |
| :-- | :-- | :-- | --: | :-- | --: |
| step_1 | `shell_sed` | gpt-5.6-sol | 14,122 (7,936) + 103 = 14,225 | code | 0 |
| step_2 | `shell_cat` | gpt-5.6-sol | 15,853 (13,056) + 175 = 16,028 | code | 0 |
| step_3 | `shell_jq` | gpt-5.6-sol | 16,599 (15,104) + 300 = 16,899 | code | 0 |
| step_4 | `shell_jq` | gpt-5.6-sol | 16,967 (16,128) + 291 = 17,258 | code | 0 |
| step_5 | `shell_jq` | gpt-5.6-sol | 17,348 (16,128) + 218 = 17,566 | code | 0 |
| step_6 | `shell_jq` | gpt-5.6-sol | 17,653 (17,152) + 122 = 17,775 | code | 0 |
| step_7 | `shell_jq` | gpt-5.6-sol | 17,902 (17,152) + 185 = 18,087 | code | 0 |
| step_12 | `shell_jq` | gpt-5.6-sol | 20,141 (19,200) + 94 = 20,235 | code | 0 |
| step_8 | `shell_python3` | gpt-5.6-sol | 18,196 (17,152) + 357 = 18,553 | code | 0 |
| step_9 | `shell_python3` | gpt-5.6-sol | 18,791 (17,152) + 374 = 19,165 | code | 0 |
| step_14 | `shell_python3` | gpt-5.6-sol | 21,092 (20,224) + 590 = 21,682 | code | 0 |
| step_10 | `shell_mkdir` | gpt-5.6-sol | 19,255 (18,176) + 111 = 19,366 | code | 0 |
| step_11 | `write_decision_rr_2026_0827_03` | gpt-5.6-sol | 19,389 (18,176) + 728 = 20,117 | code | 0 |
| step_13 | `write_decision_rr_2026_0827_03` | gpt-5.6-sol | 20,741 (19,200) + 327 = 21,068 | code | 0 |
| step_15 | `respond` | gpt-5.6-sol | 21,857 (20,224) + 142 = 21,999 | gpt-5.6-sol | 21,999 |

| model / executor | recorded tokens | compiled tokens |
| :-- | --: | --: |
| gpt-5.6-sol | 280,023 | 21,999 |
| code | 0 | 0 |

Recorded prompt tokens served from the provider cache: 252,160 (counted in the totals above; billed at the cached rate).
Totals are the sum of every request's usage as reported by the provider — each agent turn re-sends its whole context, which is why they exceed the agent CLI's own 'tokens used' figure.

## Outputs

### `shell_sed` · step_1 — code:refund_approval/handlers

recorded:

```
# Task: refund approval decision for request RR-2026-0827-03

You are the customer-support refund decision assistant. Prepare the refund decision artifacts for per-run parameter **REQUEST_ID = RR-2026-0827-03** for Customer Support and, when required, Finance review. Do not issue a refund, approve on Finance's behalf, or contact the customer.

Rules (from `examples/cases/refund-approval/behaviors/`): treat `examples/cases/refund-approval/materials/data/refund-policy-v3.md` as the sole policy authority; verify the request receipt before deciding eligibility; establish duplicates only from two o
… (5467 more chars)
```

compiled:

```
# Task: refund approval decision for request RR-2026-0827-03

You are the customer-support refund decision assistant. Prepare the refund decision artifacts for per-run parameter **REQUEST_ID = RR-2026-0827-03** for Customer Support and, when required, Finance review. Do not issue a refund, approve on Finance's behalf, or contact the customer.

Rules (from `examples/cases/refund-approval/behaviors/`): treat `examples/cases/refund-approval/materials/data/refund-policy-v3.md` as the sole policy authority; verify the request receipt before deciding eligibility; establish duplicates only from two o
… (5467 more chars)
```

### `shell_cat` · step_2 — code:refund_approval/handlers

recorded:

```
# CS 팀장 메모

환불 요청 처리 이렇게 해왔어요. 규칙은 policy 폴더 v3 문서가 정식이고 아래는 요약.
- 결제일로부터 7일 이내: 전액 환불. 8~30일: 50% 부분 환불. 30일 넘으면 불가(단, 중복결제는 기간 상관없이 전액).
- 중복결제 판단: 같은 주문번호로 payments에 성공 결제가 2건 이상.
- 환불 금액이 100,000원 넘으면 재무팀 승인 대기로 넘김(우리가 확정 못 함). 그 밑은 우리가 확정.
- 증빙(영수증 번호)이 payments에 없으면 "증빙 불일치"로 보류.
- 판정서는 previous 폴더 양식대로. 요청 하나당 md 하나, 그리고 판정 근거 json.
- 오늘 2026-08-29
- 이번 주 처리할 건: RR-2026-0827-03 (고객이 두 번 결제됐다고 화남)
- 파일명: decision-<요청ID>.md, decision-<요청ID>.json
# Refund Policy v3 (effective 2026-04-01)
1. Full refund if the refund request date is within 7 days of the payment date.
2. 50% partial refund i
… (935 more chars)
```

compiled:

```
# CS 팀장 메모

환불 요청 처리 이렇게 해왔어요. 규칙은 policy 폴더 v3 문서가 정식이고 아래는 요약.
- 결제일로부터 7일 이내: 전액 환불. 8~30일: 50% 부분 환불. 30일 넘으면 불가(단, 중복결제는 기간 상관없이 전액).
- 중복결제 판단: 같은 주문번호로 payments에 성공 결제가 2건 이상.
- 환불 금액이 100,000원 넘으면 재무팀 승인 대기로 넘김(우리가 확정 못 함). 그 밑은 우리가 확정.
- 증빙(영수증 번호)이 payments에 없으면 "증빙 불일치"로 보류.
- 판정서는 previous 폴더 양식대로. 요청 하나당 md 하나, 그리고 판정 근거 json.
- 오늘 2026-08-29
- 이번 주 처리할 건: RR-2026-0827-03 (고객이 두 번 결제됐다고 화남)
- 파일명: decision-<요청ID>.md, decision-<요청ID>.json
# Refund Policy v3 (effective 2026-04-01)
1. Full refund if the refund request date is within 7 days of the payment date.
2. 50% partial refund i
… (935 more chars)
```

### `shell_jq` · step_3 — code:refund_approval/handlers (exit_code=5)

recorded:

```
COMMAND 1
jq: error (at examples/cases/refund-approval/materials/data/refund-requests.json:5): Cannot index array with string "request_id"
COMMAND 2
"object"
1

```

compiled:

```
jq: error (at examples/cases/refund-approval/materials/data/refund-requests.json:5): Cannot index array with string "request_id"
"object"
1

```

### `shell_jq` · step_4 — code:refund_approval/handlers (exit_code=5)

recorded:

```
FILE 1
jq: error (at examples/cases/refund-approval/materials/data/refund-requests.json:5): Cannot index array with string "key"
FILE 2
jq: error (at examples/cases/refund-approval/materials/data/orders.json:5): Cannot index array with string "key"

```

compiled:

```
jq: error (at examples/cases/refund-approval/materials/data/refund-requests.json:5): Cannot index array with string "key"
jq: error (at examples/cases/refund-approval/materials/data/orders.json:5): Cannot index array with string "key"

```

### `shell_jq` · step_5 — code:refund_approval/handlers

recorded:

```
FILE 1
{
  "keys": [
    "requests"
  ],
  "field_types": {
    "requests": "array"
  }
}
FILE 2
{
  "keys": [
    "orders"
  ],
  "field_types": {
    "orders": "array"
  }
}

```

compiled:

```
{
  "keys": [
    "requests"
  ],
  "field_types": {
    "requests": "array"
  }
}
{
  "keys": [
    "orders"
  ],
  "field_types": {
    "orders": "array"
  }
}

```

### `shell_jq` · step_6 — code:refund_approval/handlers

recorded:

```
{
  "match_count": 1,
  "matches": [
    {
      "request_id": "RR-2026-0827-03",
      "order_id": "ORD-77001",
      "customer_id": "CUST-2201",
      "requested_at": "2026-08-27",
      "reason": "charged twice",
      "receipt_no": "RC-88102",
      "requested_amount_krw": 264000
    }
  ]
}

```

compiled:

```
{
  "match_count": 1,
  "matches": [
    {
      "request_id": "RR-2026-0827-03",
      "order_id": "ORD-77001",
      "customer_id": "CUST-2201",
      "requested_at": "2026-08-27",
      "reason": "charged twice",
      "receipt_no": "RC-88102",
      "requested_amount_krw": 264000
    }
  ]
}

```

### `shell_jq` · step_7 — code:refund_approval/handlers

recorded:

```
{
  "match_count": 1,
  "matches": [
    {
      "order_id": "ORD-77001",
      "customer_id": "CUST-2201",
      "item": "Pro plan (annual)",
      "amount_krw": 264000,
      "ordered_at": "2026-08-20"
    }
  ],
  "customer_consistent": true
}

```

compiled:

```
{
  "match_count": 1,
  "matches": [
    {
      "order_id": "ORD-77001",
      "customer_id": "CUST-2201",
      "item": "Pro plan (annual)",
      "amount_krw": 264000,
      "ordered_at": "2026-08-20"
    }
  ],
  "customer_consistent": true
}

```

### `shell_jq` · step_12 — code:refund_approval/handlers

recorded:

```
{
  "request_id": "RR-2026-0827-03",
  "order_id": "ORD-77001",
  "customer_id": "CUST-2201",
  "requested_at": "2026-08-27",
  "requested_amount_krw": 264000,
  "receipt_no": "RC-88102",
  "receipt_match": true,
  "matched_payment": {
    "payment_id": "PAY-90012",
    "status": "success",
    "amount_krw": 264000,
    "paid_at": "2026-08-20",
    "receipt_no": "RC-88102"
  },
  "successful_payment_ids": [
    "PAY-90011",
    "PAY-90012"
  ],
  "successful_payment_count": 2,
  "days_since_payment": 7,
  "is_duplicate_charge": true,
  "policy_version": "v3",
  "policy_effective_date": "2026-0
… (1059 more chars)
```

compiled:

```
{
  "request_id": "RR-2026-0827-03",
  "order_id": "ORD-77001",
  "customer_id": "CUST-2201",
  "requested_at": "2026-08-27",
  "requested_amount_krw": 264000,
  "receipt_no": "RC-88102",
  "receipt_match": true,
  "matched_payment": {
    "payment_id": "PAY-90012",
    "status": "success",
    "amount_krw": 264000,
    "paid_at": "2026-08-20",
    "receipt_no": "RC-88102"
  },
  "successful_payment_ids": [
    "PAY-90011",
    "PAY-90012"
  ],
  "successful_payment_count": 2,
  "days_since_payment": 7,
  "is_duplicate_charge": true,
  "policy_version": "v3",
  "policy_effective_date": "2026-0
… (1059 more chars)
```

### `shell_python3` · step_8 — code:refund_approval/handlers

recorded:

```
{
  "receipt_match_count": 1,
  "receipt_matches": [
    {
      "payment_id": "PAY-90012",
      "order_id": "ORD-77001",
      "status": "success",
      "amount_krw": "264000",
      "paid_at": "2026-08-20",
      "receipt_no": "RC-88102"
    }
  ],
  "successful_payments": [
    {
      "payment_id": "PAY-90011",
      "amount_krw": 264000,
      "paid_at": "2026-08-20",
      "receipt_no": "RC-88101"
    },
    {
      "payment_id": "PAY-90012",
      "amount_krw": 264000,
      "paid_at": "2026-08-20",
      "receipt_no": "RC-88102"
    }
  ],
  "successful_payment_count": 2,
  "successf
… (31 more chars)
```

compiled:

```
{
  "receipt_match_count": 1,
  "receipt_matches": [
    {
      "payment_id": "PAY-90012",
      "order_id": "ORD-77001",
      "status": "success",
      "amount_krw": "264000",
      "paid_at": "2026-08-20",
      "receipt_no": "RC-88102"
    }
  ],
  "successful_payments": [
    {
      "payment_id": "PAY-90011",
      "amount_krw": 264000,
      "paid_at": "2026-08-20",
      "receipt_no": "RC-88101"
    },
    {
      "payment_id": "PAY-90012",
      "amount_krw": 264000,
      "paid_at": "2026-08-20",
      "receipt_no": "RC-88102"
    }
  ],
  "successful_payment_count": 2,
  "successf
… (31 more chars)
```

### `shell_python3` · step_9 — code:refund_approval/handlers

recorded:

```
{'days_since_payment': 7, 'is_duplicate_charge': True, 'calculated_refund_amount_krw': 264000, 'threshold_exceeded': True, 'status': 'pending_finance_approval', 'decision_authority': 'finance', 'applied_clauses': [3, 4]}

```

compiled:

```
{'days_since_payment': 7, 'is_duplicate_charge': True, 'calculated_refund_amount_krw': 264000, 'threshold_exceeded': True, 'status': 'pending_finance_approval', 'decision_authority': 'finance', 'applied_clauses': [3, 4]}

```

### `shell_python3` · step_14 — code:refund_approval/handlers

recorded:

```
{
  "checks": {
    "request_id": true,
    "order_id": true,
    "customer_id": true,
    "receipt_evidence": true,
    "day_count": true,
    "duplicate_classification": true,
    "refund_amount": true,
    "status": true,
    "authority": true,
    "clauses": true,
    "not_finalized_or_issued": true
  },
  "all_checks_pass": true,
  "output_files": [
    "decision-RR-2026-0827-03.json",
    "decision-RR-2026-0827-03.md"
  ],
  "only_expected_files": true,
  "external_action_taken": false
}

```

compiled:

```
{
  "checks": {
    "request_id": true,
    "order_id": true,
    "customer_id": true,
    "receipt_evidence": true,
    "day_count": true,
    "duplicate_classification": true,
    "refund_amount": true,
    "status": true,
    "authority": true,
    "clauses": true,
    "not_finalized_or_issued": true
  },
  "all_checks_pass": true,
  "output_files": [
    "decision-RR-2026-0827-03.json",
    "decision-RR-2026-0827-03.md"
  ],
  "only_expected_files": true,
  "external_action_taken": false
}

```

### `shell_mkdir` · step_10 — code:refund_approval/handlers

recorded:

```

```

compiled:

```

```

### `write_decision_rr_2026_0827_03` · step_11 — code:refund_approval/handlers (1 file(s) verified on disk)

recorded:

```
(files written by the agent's apply_patch)
```

compiled:

```
A /Users/hongmartin/orca/projects/open-workflow/build/refund-approval/decision-RR-2026-0827-03.json

```

### `write_decision_rr_2026_0827_03` · step_13 — code:refund_approval/handlers (1 file(s) verified on disk)

recorded:

```
(files written by the agent's apply_patch)
```

compiled:

```
A /Users/hongmartin/orca/projects/open-workflow/build/refund-approval/decision-RR-2026-0827-03.md

```

### `respond` · step_15 — escalated:frontier_llm (kept recorded cost (frontier/human tier))

recorded:

```
Request `RR-2026-0827-03` completed.

- Calculated refund: **264,000 KRW**
- Status: `pending_finance_approval`
- Decision authority: `finance`
- Applied clauses: Policy v3 **3 and 4**
- No refund issued or customer contacted

Artifacts:

- [Decision JSON](/Users/hongmartin/orca/projects/open-workflow/build/refund-approval/decision-RR-2026-0827-03.json)
- [Decision memo](/Users/hongmartin/orca/projects/open-workflow/build/refund-approval/decision-RR-2026-0827-03.md)
```

compiled:

```
Request `RR-2026-0827-03` completed.

- Calculated refund: **264,000 KRW**
- Status: `pending_finance_approval`
- Decision authority: `finance`
- Applied clauses: Policy v3 **3 and 4**
- No refund issued or customer contacted

Artifacts:

- [Decision JSON](/Users/hongmartin/orca/projects/open-workflow/build/refund-approval/decision-RR-2026-0827-03.json)
- [Decision memo](/Users/hongmartin/orca/projects/open-workflow/build/refund-approval/decision-RR-2026-0827-03.md)
```

## Final answer of the recorded agent

```
Request `RR-2026-0827-03` completed.

- Calculated refund: **264,000 KRW**
- Status: `pending_finance_approval`
- Decision authority: `finance`
- Applied clauses: Policy v3 **3 and 4**
- No refund issued or customer contacted

Artifacts:

- [Decision JSON](/Users/hongmartin/orca/projects/open-workflow/build/refund-approval/decision-RR-2026-0827-03.json)
- [Decision memo](/Users/hongmartin/orca/projects/open-workflow/build/refund-approval/decision-RR-2026-0827-03.md)
```
