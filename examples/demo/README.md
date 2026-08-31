# examples/demo — Codex TUI 데모 자료와 결과물

README 상단 "30초 데모"에 쓰인 입력과 산출물, 그리고 **원래 에이전트 세션 vs 컴파일된 빌드의 벤치마크(결과·토큰·속도)** 를 한곳에 모았습니다.

| 폴더/파일 | 내용 |
| :--- | :--- |
| [`prompt.md`](prompt.md) | Codex에 입력한 네 줄(`$ow-compile-work`, `$ow-traces`, `$ow-compile-trace`, `$ow-bench`)과 각 스킬이 Codex에 전달하는 지시문 |
| [`output/`](output/) | Codex의 실제 출력 transcript(단계별 `step*.md`), 컴파일 API 응답, 프록시가 캡처한 세션 목록·TraceIR JSON(도구 실행 결과 포함) |
| [`openworkcompiled/quality_analyst/`](openworkcompiled/quality_analyst/) | 1단계 산출물 — OpenWorkLang `examples/quality_analysis.work` → 빌드 트리: `work.yaml`, `handlers/collect_data.py`(code), `rules/detect_anomaly.rule.yaml`(rule), `models/ml/find_correlation/`(model card·dataset·train.py), `models/slm/{determine_root_cause,create_report}/`(training_candidate·dataset·train.py), `schema/*.linkml.yaml`, `MANIFEST.json` |
| [`build/codex_session/`](build/codex_session/) | 3단계 산출물 — 1단계 Codex 세션 → 빌드 트리: `work.yaml`, `handlers/shell_python3.py`·`shell_find.py`(기록된 명령을 재실행하는 code 핸들러), `prompts/respond.prompt.md`(frontier_llm 계약), `trace.json`(원본 세션), **[`BENCHMARK.md`](build/codex_session/BENCHMARK.md)** / `benchmark.json`(4단계 벤치마크) |

입력 소스: [`examples/quality_analysis.work`](../quality_analysis.work) · 스킬 정의: [`.agents/skills/`](../../.agents/skills/) · 녹화 스크립트: [`docs/demo/openworkcompiler-codex-demo.tape`](../../docs/demo/openworkcompiler-codex-demo.tape)

## 벤치마크: 같은 작업, 에이전트 vs 컴파일된 빌드

작업: "`examples/quality_analysis.work`를 컴파일하고 빌드 트리를 살펴본 뒤 요약" — Codex가 한 번 수행한 세션(1단계)을 컴파일한 빌드를 같은 세션에 대해 재실행한 결과입니다 ([`build/codex_session/BENCHMARK.md`](build/codex_session/BENCHMARK.md)).

토큰의 주 지표는 **유니크 토큰**입니다: 각 토큰을 한 번만 세는 기준 — 첫 요청의 프롬프트 전체 + 이후 요청마다 새로 늘어난 프롬프트 증분 + 모든 completion. 에이전트 세션은 매 턴 누적 컨텍스트를 다시 보내므로, 요청별 usage를 단순 합산한 값(아래 "누적 합산")은 같은 토큰을 턴 수만큼 중복 계상해 에이전트 비용을 과대평가합니다.

| | 기록된 에이전트 (Codex) | 컴파일된 빌드 | 차이 |
| :-- | --: | --: | --: |
| LLM 토큰 (유니크) | 20,506 | 6,551 | **−68.1%** |
| LLM 토큰 (누적 합산; 참고) | 147,288 | 6,551 | −95.6% |
| 벽시계 시간 | 106.1 s | 31.6 s | **3.4× 빠름** |
| 결과 재현 | — | **6/8 일치** | |
| 컴파일 / 에스컬레이션 액션 | — | 5 / 0 (SLM 1) | |

| action | tier | 토큰 rec(유니크) → comp | 지연 rec → comp | 결과 |
| :-- | :-- | --: | --: | :-- |
| `shell_sed` | code | 14,815 → 0 | 9.4 s → 0.01 s | 2/2 일치 |
| `shell_python3` (OpenWorkLang 컴파일) | code | 641 → 0 | 3.5 s → 0.12 s | 일치 |
| `shell_find` (트리 조회 + work.yaml/핸들러 읽기) | code | 842 → 0 | 8.6 s → 0.03 s | 일치 |
| `respond` (요약, SLM 승격됨) | slm | 2,486 → 6,551 | 65.7 s → 31.4 s | 게이트 2/2 통과 |
| `shell_curl` | code | 1,722 → 0 | 18.9 s → 0.04 s | 0/2 (프록시 응답이 실행마다 다름) |

읽는 법: 셸 스텝들은 code 계층으로 내려가 **토큰 0, 밀리초 단위**로 같은 출력을 재현했고, `respond`(요약)는 frontier LLM 대신 로컬 SLM(qwen2.5:7b)이 품질 게이트를 통과하며 실행됩니다. SLM 스텝의 comp 토큰(6,551)은 로컬 모델이 쓰는 토큰이라 frontier API 과금 대상이 아닙니다.

실제 업무 작업(고객 계약 갱신 제안서)으로 돌린 벤치마크는 [`customer-renewal-bench/`](customer-renewal-bench/)에 있습니다 — 8 스텝 세션, 유니크 토큰 **−82.2%** (누적 합산 기준 −97.0%), 4.8× 빠름, 8/8 재현.

## 흐름

```text
$ow-compile-work examples/quality_analysis.work
  └─ python3 -m core.openworklang compile … ──▶ openworkcompiled/quality_analyst/ (work.yaml · handlers/ · rules/ · models/ml|slm/ · schema/)

$ow-traces
  └─ GET /v1/workcompiler/traces ──▶ output/proxy-traces.json   (1단계 세션이 shell_python3 → shell_find → respond 로 캡처됨)

$ow-compile-trace codex-session
  └─ POST /v1/workcompiler/compile (build_dir) ──▶ build/codex_session/ (work.yaml · handlers/shell_*.py · prompts/respond.prompt.md · trace.json)

$ow-bench codex-session
  └─ python3 -m core.build bench build/codex_session ──▶ build/codex_session/BENCHMARK.md (결과 · 토큰 · 속도 비교)
```

## output/ 파일

- `step1-ow-compile-work.md`, `step2-ow-traces.md`, `step4-ow-bench.md` — 각 단계에서 Codex가 실행한 명령과 답변 (`codex exec` 출력 원문)
- `step3-compile-response.json` — 3단계 `POST /v1/workcompiler/compile` 응답(actions · executors)
- `proxy-traces.json` — 프록시의 세션 목록 (`GET /v1/workcompiler/traces`)
- `proxy-trace-01a04b1c-99ae-7733-8b77-814966c86046.json` — 컴파일된 1단계 세션의 TraceIR 전체 — 각 스텝의 토큰·지연과 **도구 실행 결과(`tool_result`)** 포함 (`GET /v1/workcompiler/traces/<run_id>`)

## 재현

```bash
python3 -m uvicorn adapters.proxy.server:app --port 8787 &
codex                                  # TUI에서 prompt.md의 세 줄 입력
# 또는 비대화형:
codex exec '$ow-compile-work examples/quality_analysis.work'
codex exec '$ow-traces'
codex exec '$ow-compile-trace codex-session'
codex exec '$ow-bench codex-session'
```

산출물 트리는 프록시 없이도 재생성할 수 있습니다:

```bash
python3 -m core.openworklang compile examples/quality_analysis.work --build-dir examples/demo/openworkcompiled
python3 -m core.build from-trace examples/demo/output/proxy-trace-*.json --target codex-session \
  --build-dir examples/demo/build --behaviors examples/customer-renewal
python3 -m core.build bench examples/demo/build/codex_session      # BENCHMARK.md 재생성
```

> 참고: GIF는 대화형 TUI 세션을 녹화한 것이고, `output/`의 transcript는 같은 스킬을 `codex exec`로 다시 실행해 수집한 것입니다(녹화용 임시 CODEX_HOME은 인증 토큰 사본 때문에 녹화 후 삭제). 따라서 run_id·토큰 수는 GIF와 다르지만 단계·명령·산출물 구조는 동일합니다.
