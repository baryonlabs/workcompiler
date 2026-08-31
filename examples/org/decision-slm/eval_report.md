# Decision-model eval report

Generated 2026-08-31T17:26:14 from eval_history.json (4 run(s), 4 model(s)).

Gate = 4중 완전 일치(verdict·route·params·cited_rule) + 인용 규칙 조건이 레코드에 실제 성립.
완화 일치 = 인용 규칙이 first-match가 아니어도 조건이 실제 성립하면 인정. unseen 95% CI = 사례(정책) 클러스터 부트스트랩 (10,000회, seed 20250831).

| 모델 | seen 정확 | unseen 정확 [95% CI] | unseen verdict | unseen 완화 | 실행 이력 |
| :-- | --: | --: | --: | --: | :-- |
| qwen2.5:3b (raw) | 10/56 (17.9%) | 5/60 (8.3%) [1.7, 18.3] | 45.0% | 8.3% | 1회 |
| qwen2.5:7b (raw) | 20/56 (35.7%) | 10/60 (16.7%) [8.3, 25.0] | 58.3% | 16.7% | 1회 |
| qwen2.5-7b + QLoRA (decision-trained) | 50/56 (89.3%) | 41/60 (68.3%) [53.3, 83.3] | 86.7% | 71.7% | 1회 |
| qwen2.5-7b-raw-bf16 | 18/56 (32.1%) | 9/60 (15.0%) [3.3, 26.7] | 53.3% | 15.0% | 1회 |

## Unseen 정책별 성적표 (모델별 최신 실행, 정확 일치)

| 정책(사례) | qwen2.5:3b (raw) | qwen2.5:7b (raw) | qwen2.5-7b + QLoRA (decision-trained) | qwen2.5-7b-raw-bf16 |
| :-- | --: | --: | --: | --: |
| cs-goodwill-coupon | 0/10 | 3/10 | 10/10 | 0/10 |
| finance-budget-overrun | 0/10 | 3/10 | 8/10 | 1/10 |
| hr-overtime-approval | 1/10 | 1/10 | 5/10 | 1/10 |
| log-return-disposition | 3/10 | 2/10 | 4/10 | 3/10 |
| proc-price-increase | 0/10 | 0/10 | 7/10 | 0/10 |
| sec-sharing-exception | 1/10 | 1/10 | 7/10 | 4/10 |
