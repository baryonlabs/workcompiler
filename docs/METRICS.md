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

## 5. 조직이 입력을 주면 재는 것

넷 다 **코드가 아니라 입력**의 문제였고, 이제 입력을 주면 계산된다. 입력이 없으면 해당 항목은
리포트에 아예 나타나지 않는다 — 없는 값을 0이나 추정치로 채우지 않는다.

| 지표 | 입력 | 결과 |
| :-- | :-- | :-- |
| 비용·절감액 | `owc build bench --prices table.json`(또는 `$OWC_PRICES`) — `{모델: {input, output, cache_read}}`, USD/1M | totals의 `cost{recorded, compiled, saved, unpriced_models}` |
| 절감 시간(사람 기준) | `work.yaml`의 `baseline_minutes` | totals의 `baseline_minutes`·`saved_minutes` |
| 팀·좌석별 집계 | publish 시 `OWC_TEAM`, `OWC_SEAT` 환경변수 | ledger 항목의 `team`/`seat`, `owc org status`의 팀별 표 |
| 주간·일간 추이 | (추가 입력 불필요) | totals의 `recorded_from`·`recorded_to`, 스텝별 `recorded_at` |

비용 계산의 두 가지 안전장치: 캐시 읽기는 `cache_read` 단가로 따로 곱하고, 단가표에 없는 모델은
0원으로 조용히 계산하지 않고 `unpriced_models`에 이름을 남긴다. 스텝에 모델 표기가 없는 트레이스는
세션의 에이전트 이름(`source_agent`)으로 조회하므로, 단가표를 에이전트 단위로 써도 된다.

예시:

```bash
cat > prices.json <<'JSON'
{"claude-fable-5": {"input": 3.0, "output": 15.0, "cache_read": 0.3},
 "codex_exec":     {"input": 1.25, "output": 10.0, "cache_read": 0.125},
 "qwen2.5:7b":     {"input": 0.0, "output": 0.0, "cache_read": 0.0},
 "code": {"input": 0.0}, "rule": {"input": 0.0}}
JSON
owc build bench build/customer_renewal_codex --recompute-totals --prices prices.json
# → cost (USD, supplied price table) | $0.2020 | $0.0000 | $0.2020 saved

OWC_TEAM=sales OWC_SEAT=seat-12 owc org publish build/customer_renewal_codex
```

여전히 못 재는 것: **업무 건 단위 완료 4분류**(완료/미완료/행위 위반/중단). `quality_record`의 행위
판정이 `benchmark.json`에 연결되어 있지 않다 — 이건 입력이 아니라 구현이 남은 항목이다.
