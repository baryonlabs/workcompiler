# 조직 결정 카탈로그 — "판단하는 방법"을 실행 가능한 자산으로

> **"AI는 답을 줄 수 있다. 하지만 조직이 필요한 것은 좋은 답 하나가 아니라, 좋은 판단이 반복될 수 있는 구조다."**

영업사원이 "이 고객에게 몇 %까지 할인해도 될까?"라고 물으면 AI는 12%라고 답할 수 있습니다. 문제는 그 답이
그 순간으로 끝난다는 것 — 왜 12%였는지, 어떤 정책이 적용됐는지, 다음 담당자도 같은 결론을 낼지, 정책이 바뀌면
판단이 어떻게 달라지는지가 조직의 자산으로 남지 않습니다. 이 디렉터리는 그 문제의 실행 가능한 답입니다:
**10개 조직 · 34개 결정 사례**를 선언적 스펙([`catalog.yaml`](catalog.yaml)) 하나로 정의하고, 공용 엔진
([`engine.py`](engine.py))이 사례마다 온톨로지·정책·라벨된 판단 코퍼스를 결정론적으로 생성합니다.

## 흐름과 저장소 구조의 대응

| 강의 흐름 | 카탈로그에서 | OpenWorkCompiler에서 |
| :-- | :-- | :-- |
| 데이터 — 무슨 일이 일어나는가 | `features:` 분포로 샘플된 인스턴스 레코드 | 프록시가 캡처한 트레이스, CRM/사용량 fixture |
| **온톨로지 — 그게 어떤 의미인가** | `ontology:` 개체·속성·관계 ("전략고객", "이탈위험 높음", "10% 초과는 본부장 승인") | LinkML/시맨틱 계층 (`core/semantic_ir`, 빌드의 `schema/`) |
| **의사결정 — 무엇을 할 것인가** | `rules:` 명문 정책(첫 일치 우선) + `defer: slm_recommend`(정책이 열어둔 재량 밴드는 AI 추천) + `route:`(승인 권한) + `fallback`(규칙이 침묵하면 사람 — escalate, don't guess) | rule 계층(RuleExecutor) + 게이트 달린 SLM + human 계층 |
| 실행 — 결정한 일을 실제로 | 판정 레코드(verdict·route·params·cited_rule)가 실행의 입력 | OpenWorkLang `.work` (할인안 작성 → 승인 요청 → 계약서 → 기록) |
| 결과 학습 | `corpus/<사례>/cases.jsonl` — 판단 1건 = 훈련 예시 1건 | escalate-once 캐시 = 데이터셋 (`owc build dataset`) |

핵심: **AI가 모든 것을 판단하지 않습니다.** 명문 정책은 규칙으로(34개 사례 중 규칙만으로 닫히는 판정이 대부분),
의미와 관계는 온톨로지로, 정책이 의도적으로 열어둔 밴드(할인 5–10%, 협상 구간, 애매한 신호)만 AI가 추천하고,
그 추천도 `route:`의 사람이 승인합니다. 판정마다 `cited_rule`·`cited_condition`·`rationale`이 남으므로
"왜 12%였는지"가 조직의 기록이 됩니다 — 정책이 바뀌면 `catalog.yaml`의 규칙을 고치고 재생성하면 전체 판단이
일관되게 갱신됩니다.

## 만들어지는 것

```bash
python3 examples/org/engine.py 100      # 34개 사례 × 100 인스턴스, 결정론적
```

```
corpus/<case-id>/
├── ontology.yaml    # 이 결정의 개체·관계 (의미 구조)
├── policy.yaml      # 규칙 (명문 정책 그대로)
└── cases.jsonl      # {record, decision{verdict, route, params, cited_rule, rationale}} × N
corpus/INDEX.md      # 사례 × 판정 분포 × 승인 라우팅 요약표
```

사례 목록·분포는 [`corpus/INDEX.md`](corpus/INDEX.md). 대표 사례 `sales-discount-approval`은 강의 예시
그대로입니다: 최소 마진 위반 → reject / 전략고객·고이탈위험 → 12%까지·본부장 승인 / 10% 초과 → 본부장 /
5% 이하 → 자동 / **5–10% → AI 추천 + 팀장 승인**.

## 다음 단계 (customer-renewal에서 이미 검증된 파이프라인 재사용)

1. 사례별 `cases.jsonl` → `owc build dataset` 형식(결정 SLM 훈련) — 판단은 분류라 파생(산술)과 달리
   SFT가 잘 배우는 영역입니다 ([실측 비교](../demo/customer-renewal-bench/slm-training/)).
2. 게이트: verdict/route 일치(held-out) + `cited_rule`의 조건이 실제 레코드에 성립하는지 검증(근거 날조 방지)
   + defer 밴드는 `set:` 범위 준수.
3. 대표 사례 1–2개를 `.work` 실행 흐름(결정 → 승인 요청 → 문서 생성 → 기록)으로 컴파일해 엔드투엔드 데모.
