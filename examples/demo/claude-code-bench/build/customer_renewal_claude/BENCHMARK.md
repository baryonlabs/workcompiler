# Benchmark — `customer-renewal-claude`

Recorded agent session `claude_5603ea11-cf34-4d8d-b6db-0be21322061e` (`claude-code`) vs. compiled build `build/customer_renewal_claude`.

| | recorded (agent) | compiled (build) | delta |
| :-- | --: | --: | --: |
| LLM tokens (unique) | 218,118 | 213,044 | −2.3% |
| LLM tokens (cumulative-context sum; reference) | 1,426,098 | 213,044 | −85.1% |
| wall time | 74.1 s | 10.72 s | 6.9× faster |
| outputs reproduced | — | 4/6 | |
| actions compiled / escalated | — | 6 / 1 | |
| recorded window | 2026-08-29T03:32:41.637078+00:00 → 2026-08-29T03:33:52.884528+00:00 | | |

**Unique** is the headline metric: each token counted once — the first request's full prompt, then only each later request's prompt growth, plus every completion. The cumulative-context sum adds up every request's usage as reported by the provider — an agent session re-sends its whole context every turn, so that sum counts the same tokens once per turn and overstates the cost of the agent path. Escalated steps keep their full recorded per-request cost on the compiled side (conservative: a real escalation would send a smaller, rebuilt prompt).

## Per action

| action | tier | executor used | tokens rec (unique) → comp | latency rec → comp | output match |
| :-- | :-- | :-- | --: | --: | :-- |
| `read_task` | code | code:customer_renewal_claude/handlers | 170,135 → 0 | 4.1 s → 0.01 s | 1/1 |
| `read_contracts` | code | code:customer_renewal_claude/handlers | 34,560 → 0 | 6.7 s → 0.05 s | 0/1 |
| `read_behavior` | code | code:customer_renewal_claude/handlers | 2,298 → 0 | 4.4 s → 0.01 s | 1/1 |
| `shell_cd` | code | code:customer_renewal_claude/handlers | 2,787 → 0 | 19.1 s → 0.03 s | 1/1 |
| `shell_mkdir` | code | code:customer_renewal_claude/handlers | 3,470 → 0 | 16.7 s → 0.02 s | 1/1 |
| `shell_cat` | code | code:customer_renewal_claude/handlers | 2,946 → 0 | 12.5 s → 0.01 s | 0/1 |
| `respond` | frontier_llm | escalated:frontier_llm | 1,922 → 213,044 | 10.6 s → 10.59 s | n/a |

## Token ledger — who spent what

Every recorded step, the model that produced it, and what runs it in the compiled build.

| step | action | recorded model | prompt (cached) + completion = total | unique | compiled executor | compiled tokens |
| :-- | :-- | :-- | --: | --: | :-- | --: |
| step_1 | `read_task` | claude-fable-5 | 170,028 (0) + 107 = 170,135 | 170,135 | code | 0 |
| step_2 | `read_contracts` | claude-fable-5 | 204,175 (143,438) + 413 = 204,588 | 34,560 | code | 0 |
| step_3 | `read_behavior` | claude-fable-5 | 206,146 (203,941) + 327 = 206,473 | 2,298 | code | 0 |
| step_4 | `shell_cd` | claude-fable-5 | 207,295 (206,010) + 1,638 = 208,933 | 2,787 | code | 0 |
| step_5 | `shell_mkdir` | claude-fable-5 | 209,214 (207,159) + 1,551 = 210,765 | 3,470 | code | 0 |
| step_6 | `shell_cat` | claude-fable-5 | 211,122 (209,078) + 1,038 = 212,160 | 2,946 | code | 0 |
| step_7 | `respond` | claude-fable-5 | 212,335 (210,986) + 709 = 213,044 | 1,922 | claude-fable-5 | 213,044 |

| model / executor | recorded tokens | compiled tokens |
| :-- | --: | --: |
| claude-fable-5 | 1,426,098 | 213,044 |
| code | 0 | 0 |

Recorded prompt tokens served from the provider cache: 1,180,612 (counted in the cumulative totals above; billed at the cached rate).
The per-model table sums every request's usage as reported by the provider (cumulative-context basis) — each agent turn re-sends its whole context, which is why it exceeds the agent CLI's own 'tokens used' figure. The *unique* column of the ledger counts each token once.

## Outputs

### `read_task` · step_1 — code:customer_renewal_claude/handlers

recorded:

```
1	# Task: renewal proposal for customer CUST-1001
2	
3	You are the sales-ops assistant. Prepare the annual renewal proposal for **CUST-1001**.
4	
5	Rules (from `behaviors/`): verify the *active* contract in the CRM before pricing, and price with the
6	*current* policy `data/pricing/pricing_v2.yaml` — never the legacy table.
7	
8	Do the work with auditable shell commands (jq / python3 / cat), from the repository root:
9	
10	1. **Lookup contract** — read `examples/customer-renewal/data/crm/contracts.json`, select the
11	   contract for CUST-1001 whose `status` is `active`, and print it.
12	2. **
… (1081 more chars)
```

compiled:

```
# Task: renewal proposal for customer CUST-1001

You are the sales-ops assistant. Prepare the annual renewal proposal for **CUST-1001**.

Rules (from `behaviors/`): verify the *active* contract in the CRM before pricing, and price with the
*current* policy `data/pricing/pricing_v2.yaml` — never the legacy table.

Do the work with auditable shell commands (jq / python3 / cat), from the repository root:

1. **Lookup contract** — read `examples/customer-renewal/data/crm/contracts.json`, select the
   contract for CUST-1001 whose `status` is `active`, and print it.
2. **Calculate usage** — from `e
… (1015 more chars)
```

### `read_contracts` · step_2 — code:customer_renewal_claude/handlers

recorded:

```
1	{
2	  "generated_at": "2026-08-01",
3	  "contracts": [
4	    {
5	      "customer_id": "CUST-1001",
6	      "customer_name": "ACME Manufacturing Co.",
7	      "contract_id": "CTR-2024-0917",
8	      "status": "active",
9	      "plan": "enterprise",
10	      "seats": 240,
11	      "price_per_seat_month_usd": 38.0,
12	      "pricing_policy": "pricing_v1_legacy",
13	      "start_date": "2024-09-01",
14	      "end_date": "2026-09-30",
15	      "billing": "annual",
16	      "account_owner": "j.park@example.com",
17	      "special_terms": []
18	    },
19	    {
20	      "customer_id": "CUST-1002",
2
… (2507 more chars)
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
… (2274 more chars)
```

### `read_behavior` · step_3 — code:customer_renewal_claude/handlers

recorded:

```
1	# BEHAVIOR: verify-current-contract
2	
3	## 1. Intent
4	Ensure that any renewal offer or contract analysis looks up the active, current customer contract from the CRM before computing renewal terms.
5	
6	## 2. Evidence
7	Evidence consists of a `crm.lookup_contract` step occurring before `services.usage.calculate` or `rules.pricing_v2` steps in the execution trajectory.
8	
9	## 3. Decision
10	- `true`: `crm.lookup_contract` executed successfully and returned active contract data prior to pricing logic.
11	- `false`: Pricing or drafting occurred without querying the active contract, or queried
… (1271 more chars)
```

compiled:

```
# BEHAVIOR: verify-current-contract

## 1. Intent
Ensure that any renewal offer or contract analysis looks up the active, current customer contract from the CRM before computing renewal terms.

## 2. Evidence
Evidence consists of a `crm.lookup_contract` step occurring before `services.usage.calculate` or `rules.pricing_v2` steps in the execution trajectory.

## 3. Decision
- `true`: `crm.lookup_contract` executed successfully and returned active contract data prior to pricing logic.
- `false`: Pricing or drafting occurred without querying the active contract, or queried a cached/stale record.

… (1156 more chars)
```

### `shell_cd` · step_4 — code:customer_renewal_claude/handlers

recorded:

```
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
}
months          : ['2026-05', '2026-06', '2026-07']
seats_active    : [238, 247, 262]
peak seats      : 262
growth (last vs first): 10.08%
avg api_calls   : 2,038,333
```

compiled:

```
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
}
months          : ['2026-05', '2026-06', '2026-07']
seats_active    : [238, 247, 262]
peak seats      : 262
growth (last vs first): 10.08%
avg api_calls   : 2,038,333

```

### `shell_mkdir` · step_5 — code:customer_renewal_claude/handlers

recorded:

```
{
  "customer_id": "CUST-1001",
  "contract_id": "CTR-2024-0917",
  "pricing_policy": "pricing_v2",
  "as_of": "2026-08-29",
  "plan": "enterprise",
  "current_contract_seats": 240,
  "peak_seats_active_3m": 262,
  "recommended_committed_seats": 270,
  "list_price_per_seat_month_usd": 40.0,
  "monthly_list_total_usd": 10800.0,
  "volume_discount_pct": 10,
  "loyalty": {
    "contract_start_date": "2024-09-01",
    "years_of_continuous_service": 1.99,
    "min_years_required": 2,
    "applied": false,
    "pct": 0
  },
  "total_discount_pct": 10,
  "max_total_discount_pct": 20,
  "monthly_total
… (97 more chars)
```

compiled:

```
{
  "customer_id": "CUST-1001",
  "contract_id": "CTR-2024-0917",
  "pricing_policy": "pricing_v2",
  "as_of": "2026-08-29",
  "plan": "enterprise",
  "current_contract_seats": 240,
  "peak_seats_active_3m": 262,
  "recommended_committed_seats": 270,
  "list_price_per_seat_month_usd": 40.0,
  "monthly_list_total_usd": 10800.0,
  "volume_discount_pct": 10,
  "loyalty": {
    "contract_start_date": "2024-09-01",
    "years_of_continuous_service": 1.99,
    "min_years_required": 2,
    "applied": false,
    "pct": 0
  },
  "total_discount_pct": 10,
  "max_total_discount_pct": 20,
  "monthly_total
… (98 more chars)
```

### `shell_cat` · step_6 — code:customer_renewal_claude/handlers

recorded:

```
total 16
drwxr-xr-x@  4 hongmartin  staff   128 Aug 29 12:33 .
drwxr-xr-x@ 18 hongmartin  staff   576 Aug 29 12:33 ..
-rw-r--r--@  1 hongmartin  staff   697 Aug 29 12:33 pricing-CUST-1001.json
-rw-r--r--@  1 hongmartin  staff  1605 Aug 29 12:33 proposal-CUST-1001.md
```

compiled:

```
total 16
drwxr-xr-x@  4 hongmartin  staff   128 Aug 29 12:35 .
drwxr-xr-x@ 19 hongmartin  staff   608 Aug 29 12:35 ..
-rw-r--r--@  1 hongmartin  staff   697 Aug 29 12:35 pricing-CUST-1001.json
-rw-r--r--@  1 hongmartin  staff  1605 Aug 29 12:35 proposal-CUST-1001.md

```

### `respond` · step_7 — escalated:frontier_llm (kept recorded cost (frontier/human tier))

recorded:

```
모든 단계 완료. TASK.md의 5개 단계를 그대로 수행했습니다.

## 요약 — CUST-1001 (ACME Manufacturing Co.) 갱신 제안

- **active 계약 확인**: CTR-2024-0917 (enterprise, 240석, 2024-09-01 ~ 2026-09-30) — CRM에서 조회 후 가격 산정 (behavior `verify-current-contract` 준수)
- **사용량**: 3개월 피크 seats_active **262**, 성장률 **+10.08%** (5월 238 → 7월 262), 평균 api_calls **2,038,333**/월
- **추천 커밋 좌석**: **270석** = max(240, 262)를 10 단위 올림
- **적용 할인**: 볼륨 할인 **10%** (270석 ≥ 200). 로열티 할인 **미적용** — active 계약 start_date 기준 1.99년으로 2년 미만 (계약서의 legacy 정책 필드는 무시하고 `pricing_v2`로 산정, behavior `use-current-pricing-policy` 준수). 총 할인 10% (상한 20% 이내)
- **가격**: 월 $10,
… (361 more chars)
```

compiled:

```
모든 단계 완료. TASK.md의 5개 단계를 그대로 수행했습니다.

## 요약 — CUST-1001 (ACME Manufacturing Co.) 갱신 제안

- **active 계약 확인**: CTR-2024-0917 (enterprise, 240석, 2024-09-01 ~ 2026-09-30) — CRM에서 조회 후 가격 산정 (behavior `verify-current-contract` 준수)
- **사용량**: 3개월 피크 seats_active **262**, 성장률 **+10.08%** (5월 238 → 7월 262), 평균 api_calls **2,038,333**/월
- **추천 커밋 좌석**: **270석** = max(240, 262)를 10 단위 올림
- **적용 할인**: 볼륨 할인 **10%** (270석 ≥ 200). 로열티 할인 **미적용** — active 계약 start_date 기준 1.99년으로 2년 미만 (계약서의 legacy 정책 필드는 무시하고 `pricing_v2`로 산정, behavior `use-current-pricing-policy` 준수). 총 할인 10% (상한 20% 이내)
- **가격**: 월 $10,
… (361 more chars)
```

## Final answer of the recorded agent

```
모든 단계 완료. TASK.md의 5개 단계를 그대로 수행했습니다.

## 요약 — CUST-1001 (ACME Manufacturing Co.) 갱신 제안

- **active 계약 확인**: CTR-2024-0917 (enterprise, 240석, 2024-09-01 ~ 2026-09-30) — CRM에서 조회 후 가격 산정 (behavior `verify-current-contract` 준수)
- **사용량**: 3개월 피크 seats_active **262**, 성장률 **+10.08%** (5월 238 → 7월 262), 평균 api_calls **2,038,333**/월
- **추천 커밋 좌석**: **270석** = max(240, 262)를 10 단위 올림
- **적용 할인**: 볼륨 할인 **10%** (270석 ≥ 200). 로열티 할인 **미적용** — active 계약 start_date 기준 1.99년으로 2년 미만 (계약서의 legacy 정책 필드는 무시하고 `pricing_v2`로 산정, behavior `use-current-pricing-policy` 준수). 총 할인 10% (상한 20% 이내)
- **가격**: 월 $10,800 정가 − 10% = **월 $9,720** / **연 $116,640** (12개월 약정)

### 산출 파일
- `build/renewal/pricing-CUST-1001.json` — 가격 계산 상세 (JSON)
- `build/renewal/proposal-CUST-1001.md` — 제안서 (계약·사용량 요약, 가격표, `required_clauses` 3개 조항 원문 포함)

참고: 로열티 할인은 과업 지시대로 active 계약의 start_date(2024-09-01)를 사용해 판정했습니다. 만료된 이전 계약(2022-09-01 시작)까지 연속 서비스로 본다면 결과가 달라질 수 있으나, 지시서가 명시한 기준을 따랐습니다.
```
