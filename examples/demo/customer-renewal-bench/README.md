# customer-renewal 벤치마크 — 실제 업무 작업으로 에이전트 vs 컴파일된 빌드

작업: [`examples/customer-renewal/TASK.md`](../../customer-renewal/TASK.md) — 고객 **CUST-1001**의 연간 갱신 제안서 작성.
CRM에서 *활성* 계약을 확인하고, 3개월 사용량을 집계하고, *현행* 가격정책(`pricing_v2.yaml`, 레거시 금지)으로
가격을 산정해 `pricing-CUST-1001.json`과 `proposal-CUST-1001.md`를 작성합니다. 입력 데이터는
[`examples/customer-renewal/data/`](../../customer-renewal/data/)에 있습니다.

Codex가 이 작업을 한 번 수행한 세션(8 스텝)을 프록시가 캡처 → `POST /v1/workcompiler/compile` → 빌드 트리 →
**빈 상태(`build/renewal/` 삭제)에서 빌드를 재실행**해 같은 세션과 비교했습니다.

## 결과 ([`build/customer_renewal_codex/BENCHMARK.md`](build/customer_renewal_codex/BENCHMARK.md))

| | 기록된 에이전트 (Codex) | 컴파일된 빌드 | 차이 |
| :-- | --: | --: | --: |
| LLM 토큰 | 139,437 | 20,545 | **−85.3%** |
| 벽시계 시간 | 82.6 s | 11.2 s | **7.4× 빠름** |
| 결과 재현 | — | **7/7 일치** | |
| 최종 산출물 (`proposal-CUST-1001.md`, `pricing-CUST-1001.json`) | — | **바이트 단위 동일** | `diff` 무차이 |
| 컴파일 / 에스컬레이션 액션 | — | 6 / 1 | |

| action | tier | 토큰 rec → comp | 지연 rec → comp | 결과 |
| :-- | :-- | --: | --: | :-- |
| `shell_sed` (TASK.md 읽기) | code | 14,031 → 0 | 3.2 s → 0.01 s | 일치 |
| `shell_rg` (예제 파일 탐색) | code | 14,921 → 0 | 6.7 s → 0.02 s | 일치 |
| `shell_cat` (BEHAVIOR·가격정책·데이터 읽기) | code | 15,345 → 0 | 5.8 s → 0.01 s | 일치 |
| `shell_jq` ×2 (활성 계약 조회 · 결과 검증) | code | 37,171 → 0 | 26.3 s → 0.07 s | 2/2 일치 |
| `shell_mkdir` | code | 18,151 → 0 | 5.3 s → 0.00 s | 일치 |
| `write_pricing_cust_1001` (apply_patch: 가격 JSON + 제안서 작성) | code | 19,273 → 0 | 24.2 s → 0.00 s | 파일 2개 디스크 검증 일치 |
| `respond` (최종 요약 답변) | frontier_llm | 20,545 → 20,545 | 11.1 s → 11.1 s | 에스컬레이션(기록 비용 유지) |

읽는 법: 계약 조회·사용량 집계·가격 산정·제안서 작성까지 **업무 자체는 전부 code 계층으로 내려가 토큰 0**으로
재현됐고, 남은 20,545 토큰·11.1초는 사람에게 보여줄 최종 요약(`respond`)입니다. 이 스텝은 `models/slm/`
학습 후보가 승격되면 SLM 비용으로, 또는 요약이 템플릿화되면 code 계층으로 내려갑니다.

## 새 입력(CUST-1002): 앞단 에이전트 + 컴파일된 빌드 vs Codex 단독 ([`hybrid-CUST-1002/`](hybrid-CUST-1002/))

```bash
python3 -m core.build run build/customer_renewal_codex \
  --request "Prepare the annual renewal proposal for customer CUST-1002." --escalate codex
```

| CUST-1002 | Codex 단독 | 하이브리드 | 차이 |
| :-- | --: | --: | --: |
| LLM 토큰 | 32,572 | 26,481 | −19% |
| 벽시계 시간 | 83 s | 40.2 s | 2.1× |
| 스텝 | 에이전트 8턴 | code 6 (0 토큰) + Codex 에스컬레이션 2 (`write_pricing_cust_1001` 16,338 · `respond` 10,143) | |
| 결과 | 60석 · $17,100/yr · 볼륨 5% · 로열티 0% | 동일 | JSON 구조·문안은 다름(계약에 스키마 미지정) |

앞단 에이전트(`bind_parameters`)가 요청에서 `customer_id=CUST-1002`를 정규식으로 바인딩했고, `PARAMS.json`에 표시된 합성 스텝(`write_pricing_cust_1001`)과 llm 계층(`respond`)만 에스컬레이션됐습니다. 에스컬레이션 프롬프트에는 컴파일 스텝이 이미 만든 상류 출력(활성 계약 JSON, 사용량·가격 계산 결과)이 그대로 들어가므로 에이전트는 탐색 없이 문서 작성만 합니다. 산출물: `hybrid-outputs/`, 베이스라인: `baseline-outputs/` + `baseline-transcript.md`, 실행 리포트: `hybrid-RUN_REPORT.md`.

### 같은 빌드, 다른 에이전트: Claude Code로 에스컬레이션 ([`hybrid-CUST-1002-claude/`](hybrid-CUST-1002-claude/))

Codex가 녹화한 빌드를 그대로 두고, 남은 두 스텝만 **Claude Code**(`claude -p`)에 맡겼습니다 — 코드·빌드 변경 없이 `--escalate claude`만 바꿨습니다.

```bash
python3 -m core.build run build/customer_renewal_codex \
  --request "Prepare the annual renewal proposal for customer CUST-1002." --escalate claude
```

| CUST-1002 | 하이브리드 (빌드 + Codex 에스컬레이션) | 하이브리드 (빌드 + **Claude Code** 에스컬레이션) |
| :-- | --: | --: |
| LLM 토큰 | 26,481 | 517,720 (캐시 읽기 363,523 · 비캐시 154,197) |
| 벽시계 시간 | 40.2 s | 60.7 s |
| 스텝 | code 6 (0 토큰) + 에스컬레이션 2 | code 6 (0 토큰) + 에스컬레이션 2 (`write_pricing_cust_1001` 179,687 · `respond` 338,033) |
| `pricing-CUST-1002.json` | 60석 · $17,100/yr · 볼륨 5% | **Codex 결과와 JSON 동일** (`hybrid-outputs/`) |
| 백엔드가 보고한 비용 | — | $3.56 (`total_cost_usd`) |

토큰이 큰 이유는 에이전트 차이가 아니라 실행 환경 차이입니다: `claude -p`는 매 호출마다 이 머신의 전역 `CLAUDE.md`(수천 줄)와 도구 스키마를 프롬프트 캐시에서 읽습니다(`RUN_REPORT.md`의 cached/uncached 분리 참고). 결과는 동일하므로, 에스컬레이션 백엔드는 비용·정책에 따라 골라 쓰면 됩니다(`--escalate auto`는 `OWC_AGENT` → 녹화한 에이전트 → 설치된 첫 에이전트 순).

### `respond`를 frontier LLM에서 로컬 SLM으로 승격 ([`build/customer_renewal_codex/models/slm/respond/PROMOTION.md`](build/customer_renewal_codex/models/slm/respond/PROMOTION.md))

첫 벤치에서 유일하게 남아 있던 비용(최종 요약 `respond`, 20,545 토큰)을 **품질 게이트 아래에서 소형 로컬 모델**로 내렸습니다 — 학습이 아니라 라우팅입니다(예시 1개로 파인튜닝은 근거가 없음).

```bash
ollama pull qwen2.5:7b
python3 -m core.build promote build/customer_renewal_codex respond --model qwen2.5:7b   # 게이트 통과 → work.yaml/.work에 respond: slm
python3 -m core.build bench   build/customer_renewal_codex                               # SLM이 실제로 실행되고 토큰 원장에 모델별로 잡힘
```

| 후보 | 게이트 | 이유 |
| :-- | :-- | :-- |
| `qwen2.5:3b` | **FAIL** | 파일 경로의 자리표시자를 채우지 못함 (`pricing-<value>.json`) → 근거 재현율 0.50 |
| `qwen2.5:7b` | **PASS** (재현율 1.00 · 근거 1.00 · 길이 ×1.0) | 기록된 답변의 사실 6개(270석·$116,640·10%·CUST-1001·파일 2개) 모두 상류 출력에서 재현, 환각 0 |

| 승격 후 전체 벤치 | 기록된 에이전트 (Codex) | 컴파일된 빌드 (code 6 + **SLM 1**) | 차이 |
| :-- | --: | --: | --: |
| LLM 토큰 | 139,437 | **4,208** (전부 로컬 SLM, $0) | **−97.0%** |
| 벽시계 시간 | 82.6 s | 17.2 s | **4.8×** |
| 결과 재현 | — | **8/8** (SLM 스텝은 게이트 PASS가 "일치") | |
| 에스컬레이션 액션 | 1 | **0** | |

게이트: SLM의 답변에서 숫자·ID·파일경로를 뽑아 (1) frontier 답변이 말했고 상류 데이터에 실재하는 사실(anchor)을 모두 다시 말했는지, (2) 입력 어디에도 없는 숫자를 지어내지 않았는지, (3) 길이·자리표시자를 검사합니다. SLM에게는 기록된 답변을 **값을 가린 채** 예시로만 보여주므로 베끼기가 불가능합니다. 각 평가는 `QualityRecord`가 되어 `ExecutorOptimizer.evaluate_promotion`(기존 승격 게이트)을 통과해야 합니다.

새 입력 CUST-1002 하이브리드([`hybrid-CUST-1002-slm/`](hybrid-CUST-1002-slm/)): code 6 + `respond`는 **SLM(qwen2.5:7b, 4,205 토큰, $0, 게이트 PASS)** + 합성 스텝 1개만 Claude Code — `pricing-CUST-1002.json`은 Codex/Claude 하이브리드와 동일. SLM이 게이트에 걸리면 자동으로 에이전트 에스컬레이션으로 넘어갑니다(`RUN_REPORT.md`에 SLM 시도와 사유가 남음).

### 한 번 에스컬레이션하면, 반복 실행은 $0 ([`hybrid-CUST-1002-repeat/`](hybrid-CUST-1002-repeat/))

파일을 *산출*하는 합성 스텝(`write_pricing_cust_1001`)도 SLM으로 내려보려 했지만 게이트가 거부했습니다 — 7b는 할인 밴드를 잘못 골랐고(산술 자기일관성 검사는 전부 통과하는 오답), 14b는 반올림 규칙 문구를 지어냈습니다. 그 증거는 [`models/slm/write_pricing_cust_1001/PROMOTION.md`](build/customer_renewal_codex/models/slm/write_pricing_cust_1001/PROMOTION.md)(NOT promoted)에 그대로 남겼습니다. 대신 이 오답을 잡는 검사(기록에서 함께 근거했던 숫자 쌍은 새 실행의 입력에도 쌍으로 실재해야 함)를 게이트에 넣었고, 파생 스텝은 **한 번만 에이전트에 에스컬레이션한 뒤 파라미터 키로 캐시**됩니다:

| CUST-1002 | 1차 실행 (콜드) | **2차 실행 (같은 요청)** |
| :-- | --: | --: |
| LLM 토큰 | 184,454 (Claude가 파일 작성 180k + SLM respond 4,181) | **0** |
| 벽시계 시간 | 58.9 s | **0.1 s** |
| 스텝 | code 6 + escalated:claude 1 + slm 1 | code 6 + **cache 2** |
| 산출물 | Codex 하이브리드와 동일 | 동일 (캐시에서 복원) |

캐시는 빌드 안(`cache/<action>/<params>.json`)에 살고, 에이전트가 쓴 파일 내용까지 캡처하므로 산출물을 지워도 복원됩니다. 다른 파라미터(CUST-1003)는 캐시를 지나쳐 정상적으로 에스컬레이션됩니다.

HOW 명세: [`build/customer_renewal_codex/customer_renewal_codex.work`](build/customer_renewal_codex/customer_renewal_codex.work) — executors(어떤 스텝이 code/llm인지)와 escalation(어떤 스텝이 `agent`로 남는지) 블록을 고쳐 재컴파일하면 분할을 바꿀 수 있습니다.

## 컴파일된 빌드가 하는 일

```text
build/customer_renewal_codex/
├── work.yaml · MANIFEST.json · trace.json
├── handlers/shell_sed.py · shell_rg.py · shell_cat.py · shell_jq.py · shell_mkdir.py   # 기록된 셸 명령 재실행
├── handlers/write_pricing_cust_1001.py    # 에이전트의 apply_patch를 재적용해 pricing JSON + 제안서 파일 생성
├── prompts/respond.prompt.md              # 최종 요약: frontier LLM 프롬프트 계약 + invariants + 기록 예시
└── BENCHMARK.md · benchmark.json
```

## 폴더

| 경로 | 내용 |
| :-- | :-- |
| `output/codex-transcript.md` | Codex가 작업을 수행한 실제 transcript (`codex exec`) |
| `output/compile-response.json` | `POST /v1/workcompiler/compile` 응답 (actions · executors) |
| `output/proxy-trace-01a04b0b-3a8a-72b2-8905-cb600a9ad15a.json` | 세션 TraceIR 전체 — 스텝별 명령·토큰·지연·도구 실행 결과 |
| `agent-outputs/` | 에이전트가 직접 만든 `pricing-CUST-1001.json`, `proposal-CUST-1001.md` (재실행 결과와 diff 무차이) |
| `build/customer_renewal_codex/` | 컴파일된 빌드 트리 + 벤치마크 리포트 |

## 재현

```bash
python3 -m uvicorn adapters.proxy.server:app --port 8787 &
codex exec 'Read examples/customer-renewal/TASK.md and carry it out exactly as written.'   # Codex가 프록시를 통해 수행
# 세션 컴파일 (run_id는 GET /v1/workcompiler/traces 참고)
curl -s -X POST localhost:8787/v1/workcompiler/compile -H 'Content-Type: application/json' \\
  -d '{"run_id":"<run_id>","target_name":"customer-renewal-codex","build_dir":"build"}'
rm -rf build/renewal && python3 -m core.build bench build/customer_renewal_codex             # 빈 상태에서 재실행·비교
```

프록시 없이 여기 저장된 트레이스로 바로 재현하려면:

```bash
python3 -m core.build from-trace examples/demo/customer-renewal-bench/output/proxy-trace-*.json \\
  --target customer-renewal-codex --build-dir build --behaviors examples/customer-renewal
rm -rf build/renewal && python3 -m core.build bench build/customer_renewal_codex
```
