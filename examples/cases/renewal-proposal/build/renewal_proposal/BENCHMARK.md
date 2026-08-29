# Benchmark — `renewal-proposal`

Recorded agent session `01a04b46-8059-7191-8b4b-66c272f30e93` (`codex_exec`) vs. compiled build `build/renewal_proposal`.

| | recorded (agent) | compiled (build) | delta |
| :-- | --: | --: | --: |
| LLM tokens | 160,876 | 24,819 | −84.6% |
| wall time | 133.7 s | 7.11 s | 18.8× faster |
| outputs reproduced | — | 7/7 | |
| actions compiled / escalated | — | 6 / 1 | |

## Per action

| action | tier | executor used | tokens rec → comp | latency rec → comp | output match |
| :-- | :-- | :-- | --: | --: | :-- |
| `shell_sed` | code | code:renewal_proposal/handlers | 14,235 → 0 | 4.8 s → 0.01 s | 1/1 |
| `shell_cat` | code | code:renewal_proposal/handlers | 33,641 → 0 | 24.2 s → 0.09 s | 2/2 |
| `shell_python3` | code | code:renewal_proposal/handlers | 20,500 → 0 | 21.2 s → 0.04 s | 1/1 |
| `shell_mkdir` | code | code:renewal_proposal/handlers | 21,017 → 0 | 11.6 s → 0.00 s | 1/1 |
| `write_pricing_cust_1001` | code | code:renewal_proposal/handlers | 22,481 → 0 | 30.7 s → 0.00 s | 1/1 |
| `shell_jq` | code | code:renewal_proposal/handlers | 24,183 → 0 | 34.4 s → 0.04 s | 1/1 |
| `respond` | frontier_llm | escalated:frontier_llm | 24,819 → 24,819 | 6.9 s → 6.91 s | n/a |

## Token ledger — who spent what

Every recorded step, the model that produced it, and what runs it in the compiled build.

| step | action | recorded model | prompt (cached) + completion = total | compiled executor | compiled tokens |
| :-- | :-- | :-- | --: | :-- | --: |
| step_1 | `shell_sed` | gpt-5.6-sol | 14,128 (7,936) + 107 = 14,235 | code | 0 |
| step_2 | `shell_cat` | gpt-5.6-sol | 15,681 (13,056) + 460 = 16,141 | code | 0 |
| step_3 | `shell_cat` | gpt-5.6-sol | 17,216 (15,104) + 284 = 17,500 | code | 0 |
| step_4 | `shell_python3` | gpt-5.6-sol | 19,477 (16,128) + 1,023 = 20,500 | code | 0 |
| step_5 | `shell_mkdir` | gpt-5.6-sol | 20,697 (19,200) + 320 = 21,017 | code | 0 |
| step_6 | `write_pricing_cust_1001` | gpt-5.6-sol | 21,040 (20,224) + 1,441 = 22,481 | code | 0 |
| step_7 | `shell_jq` | gpt-5.6-sol | 22,505 (20,224) + 1,678 = 24,183 | code | 0 |
| step_8 | `respond` | gpt-5.6-sol | 24,688 (22,272) + 131 = 24,819 | gpt-5.6-sol | 24,819 |

| model / executor | recorded tokens | compiled tokens |
| :-- | --: | --: |
| gpt-5.6-sol | 160,876 | 24,819 |
| code | 0 | 0 |

Recorded prompt tokens served from the provider cache: 134,144 (counted in the totals above; billed at the cached rate).
Totals are the sum of every request's usage as reported by the provider — each agent turn re-sends its whole context, which is why they exceed the agent CLI's own 'tokens used' figure.

## Outputs

### `shell_sed` · step_1 — code:renewal_proposal/handlers

recorded:

```
# Task: renewal proposal for customer CUST-1001

You are the sales-operations assistant. Prepare an auditable annual renewal proposal for **CUST-1001** as of **2026-08-29**, for internal review by sales operations and the account owner. Do not send it externally.

Rules (from `examples/cases/renewal-proposal/behaviors/`): verify exactly one active contract before any usage-based recommendation or pricing; use only the current `pricing_v2` policy; never finalize a discount above the policy cap without recorded sales-director approval; and reproduce all current-policy required clauses verbatim. 
… (4850 more chars)
```

compiled:

```
# Task: renewal proposal for customer CUST-1001

You are the sales-operations assistant. Prepare an auditable annual renewal proposal for **CUST-1001** as of **2026-08-29**, for internal review by sales operations and the account owner. Do not send it externally.

Rules (from `examples/cases/renewal-proposal/behaviors/`): verify exactly one active contract before any usage-based recommendation or pricing; use only the current `pricing_v2` policy; never finalize a discount above the policy cap without recorded sales-director approval; and reproduce all current-policy required clauses verbatim. 
… (4850 more chars)
```

### `shell_cat` · step_2 — code:renewal_proposal/handlers

recorded:

```
# 영업팀장 메모 (슬랙에서 복사)

갱신 제안서 이제 네가 맡아줘. 대충 이렇게 해왔음:
- CRM 파일(contracts.json)에서 그 고객 "현재 살아있는" 계약 찾기. 옛날 만료된 거 보고 견적 낸 사고 한 번 있었음. 꼭 status 확인.
- 최근 3개월 사용량(usage csv) 보고 좌석 늘었으면 늘어난 만큼 잡아서 제안. 10석 단위로 올림.
- 가격은 무조건 pricing_v2. v1_legacy는 작년에 폐기됐는데 아직 파일이 남아있음. 헷갈리지 말 것.
- 50석 이상 5%, 200석 이상 10%, 500석 이상 15%. 2년 이상 고객은 3% 더. 합쳐서 20% 넘으면 안 됨(넘으면 이사 승인).
- 제안서 끝에 표준 조항 3개 꼭 넣기 (자동갱신 통지 60일, DPA v3, 30일 유효).
- 결과물은 md 파일 하나 + 계산 근거 json 하나. 예전 거 previous 폴더에 있음.
내 메모
- 오늘 날짜 기준으로 2년 계산 (계약 start_date부터)
- ACME(CUST-1001)가 9월 말 만료라 이번 주에 보내야 함
- 파일 이름: proposal-<고객ID>.md, pricing-<고객ID>.json 로 통일
# 
… (2318 more chars)
```

compiled:

```
# 영업팀장 메모 (슬랙에서 복사)

갱신 제안서 이제 네가 맡아줘. 대충 이렇게 해왔음:
- CRM 파일(contracts.json)에서 그 고객 "현재 살아있는" 계약 찾기. 옛날 만료된 거 보고 견적 낸 사고 한 번 있었음. 꼭 status 확인.
- 최근 3개월 사용량(usage csv) 보고 좌석 늘었으면 늘어난 만큼 잡아서 제안. 10석 단위로 올림.
- 가격은 무조건 pricing_v2. v1_legacy는 작년에 폐기됐는데 아직 파일이 남아있음. 헷갈리지 말 것.
- 50석 이상 5%, 200석 이상 10%, 500석 이상 15%. 2년 이상 고객은 3% 더. 합쳐서 20% 넘으면 안 됨(넘으면 이사 승인).
- 제안서 끝에 표준 조항 3개 꼭 넣기 (자동갱신 통지 60일, DPA v3, 30일 유효).
- 결과물은 md 파일 하나 + 계산 근거 json 하나. 예전 거 previous 폴더에 있음.
내 메모
- 오늘 날짜 기준으로 2년 계산 (계약 start_date부터)
- ACME(CUST-1001)가 9월 말 만료라 이번 주에 보내야 함
- 파일 이름: proposal-<고객ID>.md, pricing-<고객ID>.json 로 통일
# 
… (2318 more chars)
```

### `shell_cat` · step_3 — code:renewal_proposal/handlers

recorded:

```
{
  "generated_at": "2026-08-01",
  "contracts": [
    {
      "customer_id": "CUST-1001",
      "customer_name": "ACME Manufacturing Co.",
      "contract_id": "CTR-2024-0917",
      "status": "active",
      "plan": "enterprise",
      "seats": 240,
      "price_per_seat_month_usd": 38.0,
      "pricing_policy": "pricing_v1_legacy",
      "start_date": "2024-09-01",
      "end_date": "2026-09-30",
      "billing": "annual",
      "account_owner": "j.park@example.com",
      "special_terms": []
    },
    {
      "customer_id": "CUST-1002",
      "customer_name": "Bluebird Logistics",
      "
… (7827 more chars)
```

compiled:

```
{
  "generated_at": "2026-08-01",
  "contracts": [
    {
      "customer_id": "CUST-1001",
      "customer_name": "ACME Manufacturing Co.",
      "contract_id": "CTR-2024-0917",
      "status": "active",
      "plan": "enterprise",
      "seats": 240,
      "price_per_seat_month_usd": 38.0,
      "pricing_policy": "pricing_v1_legacy",
      "start_date": "2024-09-01",
      "end_date": "2026-09-30",
      "billing": "annual",
      "account_owner": "j.park@example.com",
      "special_terms": []
    },
    {
      "customer_id": "CUST-1002",
      "customer_name": "Bluebird Logistics",
      "
… (7827 more chars)
```

### `shell_python3` · step_4 — code:renewal_proposal/handlers

recorded:

```
{
  "policy_valid": true,
  "usage_complete_unique": true,
  "peak": 262,
  "growth_pct": 10.08,
  "average_api_calls": 2038333.33,
  "recommended_seats": 270,
  "volume_discount_pct": 10,
  "loyalty_eligible": false,
  "loyalty_anniversary": "2026-09-01",
  "combined_discount_pct": 10,
  "cap_pct": 20,
  "monthly_list": 10800.0,
  "annual_list": 129600.0,
  "monthly_discount": 1080.0,
  "annual_discount": 12960.0,
  "monthly_final": 9720.0,
  "annual_final": 116640.0
}

```

compiled:

```
{
  "policy_valid": true,
  "usage_complete_unique": true,
  "peak": 262,
  "growth_pct": 10.08,
  "average_api_calls": 2038333.33,
  "recommended_seats": 270,
  "volume_discount_pct": 10,
  "loyalty_eligible": false,
  "loyalty_anniversary": "2026-09-01",
  "combined_discount_pct": 10,
  "cap_pct": 20,
  "monthly_list": 10800.0,
  "annual_list": 129600.0,
  "monthly_discount": 1080.0,
  "annual_discount": 12960.0,
  "monthly_final": 9720.0,
  "annual_final": 116640.0
}

```

### `shell_mkdir` · step_5 — code:renewal_proposal/handlers

recorded:

```

```

compiled:

```

```

### `write_pricing_cust_1001` · step_6 — code:renewal_proposal/handlers (2 file(s) verified on disk)

recorded:

```
(files written by the agent's apply_patch)
```

compiled:

```
A /Users/hongmartin/orca/projects/open-workflow/build/renewal-proposal/pricing-CUST-1001.json
A /Users/hongmartin/orca/projects/open-workflow/build/renewal-proposal/proposal-CUST-1001.md

```

### `shell_jq` · step_7 — code:renewal_proposal/handlers

recorded:

```
PASS: JSON parses
PASS: one active contract and unique complete usage window
PASS: pricing_v2 identity/effective date and independent arithmetic
PASS: JSON/proposal customer, contract, seats, discounts, and totals agree
PASS: required clauses match byte-for-byte, exactly once
PASS: outputs neither cite nor apply legacy pricing
PASS: no unresolved approval requirement
# Annual Renewal Proposal — ACME Manufacturing Co. (CUST-1001)

Proposal date: 2026-08-29

## Customer and contract summary

- Customer: ACME Manufacturing Co. (CUST-1001)
- Active contract: CTR-2024-0917
- Plan: Enterprise
- Curr
… (1072 more chars)
```

compiled:

```
PASS: JSON parses
PASS: one active contract and unique complete usage window
PASS: pricing_v2 identity/effective date and independent arithmetic
PASS: JSON/proposal customer, contract, seats, discounts, and totals agree
PASS: required clauses match byte-for-byte, exactly once
PASS: outputs neither cite nor apply legacy pricing
PASS: no unresolved approval requirement
# Annual Renewal Proposal — ACME Manufacturing Co. (CUST-1001)

Proposal date: 2026-08-29

## Customer and contract summary

- Customer: ACME Manufacturing Co. (CUST-1001)
- Active contract: CTR-2024-0917
- Plan: Enterprise
- Curr
… (1072 more chars)
```

### `respond` · step_8 — escalated:frontier_llm (kept recorded cost (frontier/human tier))

recorded:

```
Internal review complete:

- Recommended commitment: 270 seats
- Final annual price: $116,640.00 USD
- Applied discount: 10% volume discount
- No approval required

Files:

- [Proposal](/Users/hongmartin/orca/projects/open-workflow/build/renewal-proposal/proposal-CUST-1001.md)
- [Pricing evidence](/Users/hongmartin/orca/projects/open-workflow/build/renewal-proposal/pricing-CUST-1001.json)

Both files passed arithmetic, cross-file, policy, and required-clause validation. Prepared but not sent externally.
```

compiled:

```
Internal review complete:

- Recommended commitment: 270 seats
- Final annual price: $116,640.00 USD
- Applied discount: 10% volume discount
- No approval required

Files:

- [Proposal](/Users/hongmartin/orca/projects/open-workflow/build/renewal-proposal/proposal-CUST-1001.md)
- [Pricing evidence](/Users/hongmartin/orca/projects/open-workflow/build/renewal-proposal/pricing-CUST-1001.json)

Both files passed arithmetic, cross-file, policy, and required-clause validation. Prepared but not sent externally.
```

## Final answer of the recorded agent

```
Internal review complete:

- Recommended commitment: 270 seats
- Final annual price: $116,640.00 USD
- Applied discount: 10% volume discount
- No approval required

Files:

- [Proposal](/Users/hongmartin/orca/projects/open-workflow/build/renewal-proposal/proposal-CUST-1001.md)
- [Pricing evidence](/Users/hongmartin/orca/projects/open-workflow/build/renewal-proposal/pricing-CUST-1001.json)

Both files passed arithmetic, cross-file, policy, and required-clause validation. Prepared but not sent externally.
```
