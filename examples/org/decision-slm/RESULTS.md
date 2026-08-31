# 결정-SLM 훈련 결과 — 정책 적용 능력의 학습 (positive result)

규칙을 **프롬프트에 제공**하고(정책-인-컨텍스트) 적용을 훈련했습니다. 따라서 정책이 바뀌어도 재훈련 없이 동작하며,
가장 강한 평가는 **훈련에서 정책 자체를 본 적 없는 6개 사례**(eval_unseen)입니다. 게이트는 4중 완전 일치
(verdict·route·params·인용 규칙) + 인용한 규칙의 조건이 레코드에 실제로 성립하는지 검증(근거 날조 방지).

| 모델 | seen 정확 일치 | seen verdict | **unseen(미학습 정책) 정확 일치** | unseen verdict |
| :-- | --: | --: | --: | --: |
| qwen2.5:3b (raw) | 10/56 (17.9%) | 53.6% | **5/60 (8.3%)** | 45.0% |
| qwen2.5:7b (raw) | 20/56 (35.7%) | 64.3% | **10/60 (16.7%)** | 58.3% |
| qwen2.5-7b + QLoRA (decision-trained) | 50/56 (89.3%) | 96.4% | **41/60 (68.3%)** | 86.7% |

훈련: 28개 사례 × 인스턴스 40 (1,120행) → RTX 4090 QLoRA 2 epochs (~12분). 파생(산술) 실험의 0/6과 대비되는
재현 가능한 결론: **SFT는 계산은 못 배우지만 정책 적용(판단)은 배운다** — seen 2.5×, unseen 4.1× 향상.
미달 구간(unseen 68%)은 게이트가 걸러 에이전트/사람으로 에스컬레이션되므로, 수용된 판단의 정밀도가 지표입니다.

재현: `python3 examples/org/decision_dataset.py` → TRL QLoRA(`build/remote-train/train_remote.py`) → `python3 examples/org/decision_eval.py --model … --base-url …`.
원자료: [eval_history.json](eval_history.json) · [MANIFEST.json](MANIFEST.json)
