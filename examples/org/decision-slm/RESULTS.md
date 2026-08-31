# 결정-SLM 훈련 결과 — 정책 적용 능력의 학습 (positive result)

규칙을 **프롬프트에 제공**하고(정책-인-컨텍스트) 적용을 훈련했습니다. 따라서 정책이 바뀌어도 재훈련 없이 동작하며,
가장 강한 평가는 **훈련에서 정책 자체를 본 적 없는 6개 사례**(eval_unseen)입니다. 게이트는 4중 완전 일치
(verdict·route·params·인용 규칙) + 인용한 규칙의 조건이 레코드에 실제로 성립하는지 검증(근거 날조 방지).
완화 일치는 인용 규칙이 first-match가 아니어도 그 조건이 레코드에 실제 성립하고 나머지가 정답과 일치하면 인정합니다.

홀드아웃이 정책(사례) 6개 클러스터이므로, unseen 정확도의 95% CI는 **사례 단위 클러스터 부트스트랩**
(사례 복원추출, 10,000회, seed 20250831)으로 계산했습니다. 인스턴스 단위 부트스트랩은 같은 정책을 공유하는
인스턴스 간 상관 때문에 분산을 과소평가합니다.

| 모델 | seen 정확 일치 | seen verdict | **unseen(미학습 정책) 정확 일치 [95% CI]** | unseen verdict | unseen 완화 일치 |
| :-- | --: | --: | --: | --: | --: |
| qwen2.5:3b (raw) | 10/56 (17.9%) | 53.6% | **5/60 (8.3%)** [1.7, 18.3] | 45.0% | 5/60 (8.3%) |
| qwen2.5:7b (raw) | 20/56 (35.7%) | 64.3% | **10/60 (16.7%)** [8.3, 25.0] | 58.3% | 10/60 (16.7%) |
| qwen2.5-7b + QLoRA (decision-trained) | 50/56 (89.3%) | 96.4% | **41/60 (68.3%)** [53.3, 83.3] | 86.7% | 43/60 (71.7%) |

CI·완화 지표는 eval_history.json에 저장된 인스턴스별 채점 결과에서 재계산한 값입니다(재추론 없음).
클러스터가 6개뿐이라 CI가 넓습니다 — 68.3%라는 점추정은 [53.3, 83.3] 범위로 읽어야 하며,
raw 7b의 [8.3, 25.0]과는 겹치지 않으므로 훈련 효과 자체는 CI를 감안해도 유지됩니다.

## Unseen 정책별 성적표 (정확 일치)

| 정책(사례) | 3b raw | 7b raw | 7b + QLoRA |
| :-- | --: | --: | --: |
| cs-goodwill-coupon | 0/10 | 3/10 | 10/10 |
| finance-budget-overrun | 0/10 | 3/10 | 8/10 |
| hr-overtime-approval | 1/10 | 1/10 | 5/10 |
| log-return-disposition | 3/10 | 2/10 | 4/10 |
| proc-price-increase | 0/10 | 0/10 | 7/10 |
| sec-sharing-exception | 1/10 | 1/10 | 7/10 |

정책별 편차가 큽니다(튜닝 모델 4/10 ~ 10/10) — unseen 성능은 정책의 규칙 구조 난이도에 크게 의존하며,
이것이 클러스터 CI가 넓은 이유이기도 합니다.

훈련: 28개 사례 × 인스턴스 40 (1,120행) → RTX 4090 QLoRA 2 epochs (~12분). 파생(산술) 실험의 0/6과 대비되는
재현 가능한 결론: **SFT는 계산은 못 배우지만 정책 적용(판단)은 배운다** — seen 2.5×, unseen 4.1× 향상.
미달 구간(unseen 68%)은 게이트가 걸러 에이전트/사람으로 에스컬레이션되므로, 수용된 판단의 정밀도가 지표입니다.

재현: `python3 examples/org/decision_dataset.py` → TRL QLoRA(`build/remote-train/train_remote.py`) → `python3 examples/org/decision_eval.py --model … --base-url …`.
평가 이력은 append-only로 누적되며(같은 라벨의 반복 실행 보존), 실행 이력이 2개 이상인 모델은
[eval_report.md](eval_report.md)에 평균±표준편차가 병기됩니다.
원자료: [eval_history.json](eval_history.json) · [MANIFEST.json](MANIFEST.json) · 자동 리포트: [eval_report.md](eval_report.md)
