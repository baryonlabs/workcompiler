# 지표 정의 — 무엇을 어떤 기준으로 세는가

대외 보고서·대시보드·논문이 같은 실행을 두고 다른 숫자를 말하지 않도록, 각 지표의 **정의와 분모**를
여기서 한 번만 정한다. 코드가 이 문서의 근거다(파일·필드명 병기).

## 1. 토큰 절감 — 기준이 둘이고, 섞으면 안 된다

에이전트 세션은 턴마다 누적 컨텍스트를 다시 보낸다. 그래서 같은 실행에도 세는 방식이 둘이다.

| 기준 | 필드 | 뜻 | 쓰는 곳 |
| :-- | :-- | :-- | :-- |
| **유니크** | `recorded_tokens_unique`, `savings_unique_pct` | 세션의 각 토큰을 한 번만 셈(스텝별 프롬프트 증분 + 완성) | **대외 절감 주장의 기본값** |
| 누적 합산(참고) | `recorded_tokens`, `token_savings_pct` | 요청별 usage 단순 합 — 누적 컨텍스트가 턴 수만큼 중복 계상됨 | 청구서 대조, 참고 열 |

같은 빌드에서 두 값은 크게 갈린다:

| 빌드 | 유니크 | 누적 합산 |
| :-- | --: | --: |
| customer_renewal_codex | **−82.2%** (23,614 → 4,208) | −97.0% (139,437 → 4,208) |
| customer_renewal_claude | **−2.3%** (218,118 → 213,044) | −85.1% (1,426,098 → 213,044) |

claude 빌드는 respond가 frontier 에스컬레이션으로 남아 있어 **절감 사례가 아니라 재현·검증
사례**다. 누적 기준 −85.1%만 인용하면 절감이 없는 실행을 절감 사례로 만든다.

- `unique_token_basis`가 `prompt_delta`면 실측, `total_delta`면 추정(프롬프트/완성 분리가 없는
  트레이스)이므로 리포트에 "추정"으로 표기한다.
- 근거: `core/build/bench.py`(`unique_step_tokens`, `totals`), `core/build/run.py`(`RunReport.totals`),
  `core/org.py`(`status`).

## 2. 비용으로 환산할 때 지켜야 할 것

저장소에는 단가표가 없다(`cost_usd`는 백엔드 자가보고, SLM은 0.0). 비용을 계산하려면 **단가표를
외부에서 주입**해야 하며, 그때 세 가지를 지킨다.

1. **기준을 명시한다.** 청구액 추정은 누적 합산에, "정보량 절감"은 유니크에 곱한다. 한 숫자로
   합치지 않는다.
2. **캐시 읽기를 분리한다.** 캐시 읽기 단가는 통상 입력의 1/10 수준이다. 원장이
   `run_cached_tokens` / `run_uncached_tokens`, 벤치가 `recorded_cached_tokens`를 분리해 두었으니
   같은 단가로 뭉뚱그리지 않는다.
3. **모델별로 나눈다.** `by_model()`이 recorded/compiled 토큰을 모델별로 이미 분리한다.

## 3. 완료율 — 분모가 무엇인지 밝힌다

우리 `outputs_matched / outputs_checked`는 **출력 스텝 단위 재현율**이다(예: codex 8/8, claude 4/6).
"업무 건 단위 완료율"이 아니다. 건 단위 지표(완료/미완료/행위 위반/중단)를 보고하려면 별도의
분류가 필요하며, 지금 `quality_record`의 behavior 판정은 `benchmark.json`에 연결되어 있지 않다.
두 숫자를 같은 이름으로 부르지 않는다.

층별로 재는 것이 다르다는 점도 함께 밝힌다.

| 층 | 지표 | 파일 |
| :-- | :-- | :-- |
| 출력 재현 | `outputs_matched/outputs_checked`(본질적 비재현 분리) | `benchmark.json` |
| SLM 승격 게이트 | 체크별 통과(`recall`·`grounded`·`negation_cues` 등), `pass_rate` | `promotion_eval.json` |
| 자동 수리 | `converged`, `needs_human`, iteration별 accepted/reverted | `harden.json` |
| 판단 정확도 | `exact_pct`·`verdict_pct`·`relaxed_pct`·`ci95` | `eval_history.json` |

## 4. 점추정 단독 인용 금지

판단 정확도는 정책 단위로 군집하므로 **사례-클러스터 부트스트랩 신뢰구간**을 함께 낸다. 예:
unseen 정확 일치 72.9% **[64.7, 80.9]**, 시드 3회 평균 62.8% ± 4.8pp. 대외 문서에서 점추정만
인용하지 않는다 — 구간이 곧 주장이다.

## 5. 아직 못 재는 것 (입력이 없어서)

| 지표 | 막힌 이유 | 필요한 입력 |
| :-- | :-- | :-- |
| 원화·달러 절감액 | 단가표 부재 | 모델별 입력/출력/캐시읽기 단가 |
| 절감 시간(사람 기준) | 인간 기준시간 부재 | `work.yaml`의 `baseline_minutes` |
| 팀별 집계 | 신원이 git user 하나 | ledger 항목의 team/seat |
| 주간·일간 추이 | 값은 트레이스에 있으나 집계면에 미노출 | `bench` totals·대시보드에 timestamp 전달 |

이 넷은 코드 문제가 아니라 입력 데이터 문제다. 채우기 전에는 ROI를 계산하지 않는다.
