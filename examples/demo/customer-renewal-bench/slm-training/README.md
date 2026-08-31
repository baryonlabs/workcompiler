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


## CoT 타깃 절제 — 부정 결과는 CoT로도 뒤집히지 않는다

"프롬프트는 추론을 요구하는데 SFT 타깃에 계산 과정이 없어서 못 배운 것 아니냐"는 반론을 검증했습니다.
`owc build dataset <build> <action> --cot`가 fleet 정답에 **결정론적 계산 과정 프리픽스**(좌석 올림 →
성장률 → 월 총액 → 할인 자격·상한 → 월/연 총액 → API 평균; truth JSON의 중간값에서 유도)를 붙인
`data-cot/`를 생성하고, 동일 조건(3 epochs, seed 20260831, 동일 홀드아웃 6명)으로 7b를 재훈련했습니다.

결과: **0/6 — 동일**. 모델은 계산 과정을 실제로 출력하지만(평균 3,087 토큰) 실패 서명이 비-CoT와
같습니다: 6/6 전부 `json_values`(계산된 수치가 정답과 다름), 5/6에서 컨텍스트·파생 어디에도 없는
숫자를 날조(예: CUST-2017의 15360·4608). 즉 실패 원인은 타깃 형식이 아니라 **산술 그 자체**이며,
"파생 스텝은 code 계층이 맡는다"는 결론은 CoT 반론을 통과했습니다
(원자료: `models/slm/write_pricing_cust_1001/fleet_evals.json`의 `qwen2.5-7b-cot-tuned` 항목).


## 대조군 2종 — "0/6"의 진짜 의미 (`tools/remote-train/run_controls.py`)

같은 컴파일 프롬프트로 두 대조군을 돌리고, 게이트 판정 옆에 **필드 단위 부분점수**(truth pricing
JSON의 수치 리프 일치율)를 병기했습니다 (원자료: [controls.json](controls.json)):

| 팔 | 게이트 (exact) | 수치 필드 정확도 | 틀리는 곳 |
| :-- | --: | --: | :-- |
| CoT-tuned 7b | 0/6 | 86.4% (114/132) | 나눗셈 2필드(성장률·API 평균) + 1명은 볼륨 밴드 연쇄 오류 |
| **프런티어(Sonnet, 도구 없는 1-shot)** | **0/6** | 93.6% (103/110) | 거의 전부 나눗셈 2필드(4소수 성장률, 3개월 평균), 밴드·할인 로직은 전부 정답, 1명은 파일 블록 미출력 |

이 결과가 결론을 더 날카롭게 만듭니다: 문제는 "소형 모델이라서"가 아니라 **도구 없는 1-shot 추론
자체가 바이트 정확 산술(긴 나눗셈)을 못 한다**는 것입니다. 원 기록 세션의 에이전트가 이 파일들을
맞힌 이유는 도구(코드 실행)로 계산했기 때문입니다. 따라서 파생 스텝의 정착지는 모델 크기와 무관하게
**code 계층**이고, 게이트의 exact 기준은 프런티어도 통과 못 하는 것이 맞습니다 — 컴파일된 code
핸들러만이 통과합니다(그것이 이 계층 지도의 요점입니다).
