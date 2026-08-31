# SLM 훈련 실험 — 사례 300개, 4090(QLoRA), 결정론 게이트로 평가

"훈련이 가미된 형태"의 실측 기록입니다. 플릿 생성기([`../../../customer-renewal/fleet/generate.py`](../../../customer-renewal/fleet/generate.py))가
정책 의미론을 구현해 고객 300명(밴드 경계·로열티 경계 포함)과 정답 파일을 결정론적으로 만들고, `owc build dataset`이
기록 트레이스 + 캐시 항목 + 플릿 정답을 하나의 chat 데이터셋(295행)으로 병합하며, `owc build train`(mlx-lm, Apple Silicon) 또는
linux-builder의 RTX 4090(TRL QLoRA, completion-only loss)에서 훈련하고, `owc build fleet-eval`이 **훈련에 쓰이지 않은 6개 고객**을
승격과 같은 결정론 게이트로 채점합니다.

## 결과 (write 스텝 = 파생/계산, held-out 6 고객)

| 후보 | 게이트 통과 | 남은 실패 |
| :-- | :-- | :-- |
| qwen2.5:3b raw | 0/6 | 형식 붕괴 + 값 오답 + 플레이스홀더 |
| qwen2.5:7b raw | 0/6 | proposal 미출력 + 값 오답 |
| 3b + LoRA (24예시, M4 Pro/mlx) | 0/6 | **형식 전부 해결** — `json_values`(산술)만 남음 |
| 7b + QLoRA (24예시, 4090) | 0/6 | 동일 — 형식 OK, 산술 오답 (토큰 정확도 99.4%의 나머지 0.6%가 계산 숫자) |
| **7b + QLoRA (300예시, 4090)** | 0/6 | 밴드 선택·로열티·금액 체인 **패턴은 학습됨** — 남은 오답은 순수 산술(예: CUST-2015는 `average_api_calls` 큰 수 평균 1개 필드만 오답) |

**결론 (재현된 부정 결과):** SFT는 형식과 조회 패턴을 배우지만 다단계 산술은 일반화하지 못합니다(모델 2개 × 데이터 2규모에서 재현).
파생(계산) 스텝의 올바른 하향은 SLM이 아니라 **code 계층**이고, 코드로 못 내린 파생은 **escalate-once 캐시**가 맡습니다 —
게이트는 다섯 번 모두 오답 승격을 정확히 거부했습니다. 반면 재진술 스텝(`respond`)은 raw 3b도 held-out 6/6 통과
([TRAINING-respond.md](TRAINING-respond.md)) — 훈련이 필요조차 없었습니다. 다음 승부처는 **의사결정형 업무**(출력 공간이 작아
분류 SFT가 유리; `examples/cases/refund-approval` 참조)입니다.

재현: `owc build dataset <build> <action> [--holdout …]` → `owc build train …`(로컬) 또는 TRL 스크립트(원격) → `owc build fleet-eval <build> <action> --model M [--base-url U]`.
전체 평가 이력: [TRAINING.md](TRAINING.md) · [fleet_evals.json](fleet_evals.json)
