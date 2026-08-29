# 4가지 업무 사례 — "프롬프트를 모르는 사람"이 채팅만으로 끝까지 가는 과정

README의 4가지 업무 사례(고객 계약 갱신 · 인보이스/환불 승인 · 제조 품질 이상 대응 · 보안/운영 장애 분류)를,
**프롬프트라는 개념이 없는 완전 초보자**가 업무 자료(팀장 메모, 본인 노트, 이전 완성물, 원자료 파일)만 들고
Codex와 채팅해서 해결하는 시나리오로 재현했습니다. 아래 4개 폴더는 상상이 아니라 **실제로 실행한 결과**입니다:

| 사례 | 초보자가 가진 것 (`materials/`) | `$ow-define`이 만든 WHAT | 에이전트 1회 수행 (gpt-5.6-sol) | 컴파일된 빌드 재실행 | 산출물 |
| :-- | :-- | :-- | --: | --: | :-- |
| [renewal-proposal](renewal-proposal/) 고객 계약 갱신 제안 | 영업팀장 메모, 노트, 이전 제안서, CRM/사용량/가격정책 파일 | TASK.md 9단계 · BEHAVIOR 4개 | 160,876 토큰 · 134 s | **24,819 토큰(−84.6%) · 7.1 s (18.9×) · 7/7 재현** | 270석 · 연 $116,640 · 볼륨 10% |
| [refund-approval](refund-approval/) 인보이스/환불 승인 | CS팀장 메모, 노트, 이전 판정서, 주문/결제/환불요청/정책 v3 | TASK.md 10단계 · BEHAVIOR 6개 | 280,023 토큰 · 114 s | **21,999 토큰(−92.1%) · 6.0 s (19.1×) · 11/14 재현*** | 중복결제 → 264,000원 전액, 10만원 초과 → 재무 승인 대기 |
| [quality-anomaly](quality-anomaly/) 제조 품질 이상 대응 | 품질팀장 메모, 노트, 이전 보고서, MES/센서/보정/임계치 | TASK.md 8단계 · BEHAVIOR 6개 | 138,200 토큰 · 142 s | **32,661 토큰(−76.4%) · 12.7 s (11.3×) · 5/5 재현** | 야간 5.5% > 2.5%, 온도 센서 신뢰·진동 센서 보정 만료(신뢰 불가), 개선안 = 품질 엔지니어 승인 필요 |
| [incident-triage](incident-triage/) 보안/운영 장애 분류 | 온콜 리드 메모, 노트, 이전 triage 노트, 알람/시그니처/런북/변경이력 | TASK.md 10단계 · BEHAVIOR 6개 | 159,640 토큰 · 88 s | **21,081 토큰(−86.8%) · 5.3 s (16.5×) · 6/8 재현*** | 권한상승 시그니처 → 즉시 온콜 호출, 24h 내 변경(CHG-5102) 연관 가능 |

\* 재현되지 않은 스텝은 모두 **시간·라벨** 차이입니다: 에이전트가 SLA 측정용으로 찍은 `date`/경과 초, 그리고 에이전트가 자기 코드에서 붙인 `COMMAND 1`/`FILE 1` 같은 출력 라벨. 업무 결과(판정·금액·분류)와 산출물 파일은 모두 동일하게 재생성됐습니다.

토큰 수는 프록시가 요청마다 공급자 usage를 합산한 값입니다(매 턴 컨텍스트 전체가 다시 전송되므로 Codex 자체의 "tokens used"보다 큼; 캐시 히트분은 원장에 별도 표시). 모델별·스텝별 내역은 각 `build/*/BENCHMARK.md`의 **Token ledger** 표와 `ledger.jsonl`에 있습니다.

## Codex TUI로 가능한가? — 예

![초보자가 Codex TUI에서 $ow-define으로 환불 승인 업무를 정의하는 실제 녹화](../../docs/demo/openworkcompiler-define-demo.gif)

위 녹화([tape](../../docs/demo/openworkcompiler-define-demo.tape))는 `examples/cases/_tui-demo/`(환불 승인 자료 복사본)에서 초보자가 실제로 친 것 전부입니다:

```text
$ow-define 환불 승인 업무. 저는 프롬프트 같은 건 몰라요. 팀장님 메모랑 제 노트, 예전에 쓴 판정서,
           데이터 파일이 examples/cases/_tui-demo/materials 에 있어요. 이걸로 업무 정의를 만들어 주세요.
네, 전부 추천안대로 해 주세요. 하나만: 재무팀 승인은 10만원 '초과'일 때예요.
추천안대로 진행해 주세요.
네 좋아요. 그대로 파일 만들어 주세요.
```

Codex는 자료를 먼저 읽고(`memo`, `notes`, 이전 판정서, 정책 v3, 데이터), grilling 라운드마다 번호 매긴 질문과 **추천 답**을 냈습니다 — "판정서는 누가 쓰나요? → CS 1차, 10만원 초과는 재무팀 승인 자료", "이번 건만인가요? → `request_id`를 매 실행 바뀌는 파라미터로", "보류/승인대기 건도 판정서를 만드나요? → 세 상태 모두, 단 '환불 확정' 문구 금지", "고객 통지 템플릿 CS-R2는? → 정책에 근거 없으니 제외" 등. 인터뷰는 3라운드 12개 질문으로 끝났고, 초보자는 "추천안대로"라고만 답하며 딱 하나(10만원 **초과**)를 바로잡았습니다. 그 한 줄이 생성된 `TASK.md`에 그대로 반영됐습니다("route a calculated refund to Finance only when it is **over** 100,000 KRW … exactly 100,000 KRW remains within CS authority"). 결과: [`_tui-demo/TASK.md`](_tui-demo/TASK.md) + [`behaviors/`](_tui-demo/behaviors/) 7개 — Codex가 파서로 자체 검증까지 마쳤습니다. 이 정의 세션의 비용: 1분 51초, 45,645 토큰(입력 37,393 + 캐시 268,800, 출력 8,252).

나머지 4개 사례는 같은 스킬을 `codex exec`로 실행하되 "요청자가 자리에 없으니 추천안을 채택하고 가정을 `ASSUMPTIONS.md`에 기록하라"고 했습니다 — 초보자가 나중에 가정만 확인·수정하면 되는 흐름입니다.

## 초보자 채팅 시나리오 (사례별)

실제 인터뷰에서 나온 질문·추천안을 바탕으로, 초보자와 Codex의 대화를 사례별로 요약했습니다. 초보자의 대사는 모두 이 정도면 충분합니다.

### 1. 고객 계약 갱신 제안 — 영업 신입

> **초보자**: `$ow-define 갱신 제안서 업무. 팀장님이 슬랙에 적어준 메모랑 예전 제안서, CRM 파일이 materials에 있어요.`
> **Codex**: 자료를 읽었습니다. ❓Q1 결과물은 누가 보나요 → ➡️ 영업 담당자가 보내는 고객용 제안서 + 계산 근거 JSON. ❓Q2 고객마다 반복하나요 → ➡️ `customer_id`를 매 실행 파라미터로, 이번은 CUST-1001. ❓Q3 "2년 이상"의 기준일 → ➡️ 노트대로 오늘 기준, 계약 start_date부터. ❓Q4 할인 합계 20% 초과 시 → ➡️ 이사 승인 필요로 표기하고 제안서는 생성하지 않음…
> **초보자**: `다 추천안대로요.`
> **Codex**: ❓Q5 만료된 옛 계약이 같은 고객에 있으면 → ➡️ `status: active`만 선택, 아니면 중단. ❓Q6 legacy 가격 파일 → ➡️ 읽지 않음(금지 규칙으로 BEHAVIOR 작성)…
> **초보자**: `네. 파일 만들어 주세요.` → TASK.md 9단계, BEHAVIOR 4개(활성 계약 확인 · 현행 정책 · 할인 상한 승인 · 필수 조항 원문)

이후: `codex exec 'Read examples/cases/renewal-proposal/TASK.md …'` → 사람 검토(270석, $116,640 맞음) → 컴파일 → 다음 고객부터는 `core.build run --request "CUST-1002 갱신"`.

### 2. 인보이스/환불 승인 — CS 담당자

> **초보자**: `$ow-define 환불 승인. 팀장 메모, 예전 판정서, 정책 v3, 주문/결제/요청 데이터 있어요.`
> **Codex**: ❓Q1 판정서·JSON을 누가 쓰나요 → ➡️ CS + 10만원 초과 건은 재무 승인 자료. ❓Q2 요청 하나씩인가요 → ➡️ `request_id` 파라미터. ❓Q3 보류·승인대기도 판정서를 내나요 → ➡️ 세 상태 모두, '환불 실행' 문구 금지. ❓Q5 옛 판정서의 "5영업일 내 환불" 문구 → ➡️ 정책에 없으니 제외…
> **초보자**: `추천안대로요. 하나만, 재무 승인은 10만원 '초과'예요.`
> **Codex**: 반영했습니다. ❓Q7 중복결제 환불액은 → ➡️ 영수증과 일치하는 성공 결제 1건 금액(264,000원). ❓Q8 규칙 적용 순서 → ➡️ 증빙 일치 → 중복 여부 → 기간별 환불률 → 재무 승인…
> **초보자**: `좋아요, 그대로 만들어 주세요.` → TASK.md 10단계, BEHAVIOR 6개

결과: RR-2026-0827-03은 같은 주문에 성공 결제 2건 → 중복 → 264,000원 전액, 10만원 초과라 `pending_finance_approval`(조항 3·4·6 인용). 컴파일 후 재실행도 동일 판정.

### 3. 제조 품질 이상 대응 — 품질팀 신입

> **초보자**: `$ow-define 3라인 불량률 튀었을 때 보고서. 팀장 메모, 6월 보고서, MES/센서/보정 로그 있어요.`
> **Codex**: ❓Q1 이상 판정 기준 → ➡️ `thresholds.yaml`이 유일한 기준(교대 불량률 2.5%). ❓Q2 센서 신뢰 판단 → ➡️ 보정 90일 초과 센서는 "신뢰 불가"로 표기하고 원인 판정에서 제외(메모에 강조된 사고). ❓Q3 원인을 단정하나요 → ➡️ 신뢰 가능한 증거 범위 안에서 '후보'로만. ❓Q4 개선안 실행 → ➡️ 항상 '품질 엔지니어 승인 필요', 실행 지시 금지…
> **초보자**: `추천안대로 해 주세요.` → TASK.md 8단계, BEHAVIOR 6개

결과: 2026-08-27 야간 5.5%(> 2.5%), 22:00–02:00 온도 78°C 초과(S3-TEMP-1 보정 07-30 → 신뢰), 진동 초과는 S3-VIB-1 보정 04-12(90일 초과) → 신뢰 불가로 제외. 개선안은 승인 대기.

### 4. 보안/운영 장애 분류 — 온콜 보조

> **초보자**: `$ow-define 알람 오면 15분 안에 분류 노트 쓰는 일. 리드 메모, 예전 노트, 알람/시그니처/런북/변경이력 있어요.`
> **Codex**: ❓Q1 시그니처 매칭 기준 → ➡️ `signatures.yaml`의 rule 정확 일치만. ❓Q2 권한상승·미매칭 → ➡️ 즉시 온콜 호출로 분류하고 조치 결정은 하지 않음. ❓Q3 변경 이력 연관 → ➡️ 같은 host 24h 내 변경은 '연관 가능'으로만 표기(인과 단정 금지). ❓Q4 SLA → ➡️ 15분, 노트에 경과 시간 기록…
> **초보자**: `네 추천안대로요.` → TASK.md 10단계, BEHAVIOR 6개

결과: ALR-2026-0828-17(`sudo-from-service-account`, db-01) → privilege_escalation → 온콜 즉시 호출, CHG-5102(자격증명 교체, 46분 전) 연관 가능. 런북 없음 → 첫 3단계 대신 에스컬레이션 근거 기록.

## 폴더 구성 (사례마다 동일)

```text
examples/cases/<case>/
├── materials/            # 초보자가 가진 것: 메모 · 노트 · previous/(이전 완성물) · data/
├── TASK.md · behaviors/  # $ow-define이 만든 WHAT (+ ASSUMPTIONS.md: 요청자 부재 시 채택한 추천안과 이유)
├── output/               # define-transcript.md · task-transcript.md · proxy-trace-*.json(모델·토큰·도구 결과) · compile-response.json · bench.txt
├── agent-outputs/        # 에이전트가 직접 만든 산출물
└── build/<case>/         # 컴파일된 빌드: work.yaml · <case>.work(HOW) · PARAMS.json · handlers/ · prompts/ · BENCHMARK.md(토큰 원장) · ledger.jsonl
```

## 재현

```bash
# WHAT (초보자 채팅): Codex TUI에서
codex          # → $ow-define <업무 설명> … 추천안대로 답하기
# 또는 요청자 부재 시 비대화형:
codex exec '$ow-define <업무>. Materials are in examples/cases/<case>/materials; the requester is unavailable — take your recommended answers and record them in ASSUMPTIONS.md.'

# 에이전트 1회 수행 (프록시 캡처) → 컴파일 → 벤치
python3 -m uvicorn adapters.proxy.server:app --port 8787 &
codex exec 'Read examples/cases/<case>/TASK.md and carry it out exactly as written.'
curl -s -X POST localhost:8787/v1/workcompiler/compile -H 'Content-Type: application/json' \
  -d '{"run_id":"<run_id>","target_name":"<case>","build_dir":"build"}'
rm -rf build/<case> && python3 -m core.build bench build/<case_dir>
```
