# examples/demo — Codex TUI 데모 자료와 결과물

README 상단 "30초 데모"에 쓰인 입력과 산출물을 한곳에 모았습니다.

| 폴더/파일 | 내용 |
| :--- | :--- |
| [`prompt.md`](prompt.md) | Codex에 입력한 세 줄(`$ow-compile-work`, `$ow-traces`, `$ow-compile-trace`)과 각 스킬이 Codex에 전달하는 지시문 |
| [`output/`](output/) | Codex의 실제 출력 transcript(단계별 `step*.md`)와 프록시가 캡처한 세션 목록·TraceIR JSON |
| [`openworkcompiled/quality_analyst/`](openworkcompiled/quality_analyst/) | 1단계 산출물 — OpenWorkLang `examples/quality_analysis.work` → 빌드 트리: `work.yaml`, `handlers/collect_data.py`(code), `rules/detect_anomaly.rule.yaml`(rule), `models/ml/find_correlation/`(model card·dataset·train.py), `models/slm/{determine_root_cause,create_report}/`(training_candidate·dataset·train.py), `schema/*.linkml.yaml`, `MANIFEST.json` |
| [`build/codex_session/`](build/codex_session/) | 3단계 산출물 — 프록시가 캡처한 Codex 세션 → 빌드 트리: `work.yaml`, `handlers/shell_curl.py`(기록된 명령을 재실행하는 code 핸들러), `prompts/respond.prompt.md`(frontier_llm 계약), `MANIFEST.json` |

입력 소스: [`examples/quality_analysis.work`](../quality_analysis.work) · 스킬 정의: [`.agents/skills/`](../../.agents/skills/) · 녹화 스크립트: [`docs/demo/openworkflow-codex-demo.tape`](../../docs/demo/openworkflow-codex-demo.tape)

## 흐름

```text
-compile-work examples/quality_analysis.work
  └─ python3 -m core.openworklang compile … ──▶ openworkcompiled/quality_analyst/ (work.yaml · handlers/ · rules/ · models/ml|slm/ · schema/)

-traces
  └─ GET /v1/workcompiler/traces ──▶ output/proxy-traces.json   (이 Codex 세션 자체가 shell_python3 → shell_sed → respond 로 캡처됨)

-compile-trace codex-session
  └─ POST /v1/workcompiler/compile (build_dir) ──▶ build/codex_session/ (work.yaml · handlers/shell_curl.py · prompts/respond.prompt.md)
```

## output/ 파일

- `step1-ow-compile-work.md`, `step2-ow-traces.md`, `step3-ow-compile-trace.md` — 각 단계에서 Codex가 실행한 명령과 답변 (`codex exec` 출력 원문)
- `proxy-traces.json` — 세 단계가 끝난 뒤 프록시의 세션 목록 (`GET /v1/workcompiler/traces`)
- `proxy-trace-01a0489f-6bba-7990-af04-f8cbe38505a8.json` — 3단계가 컴파일한 세션(가장 스텝이 많은 세션)의 TraceIR 전체 (`GET /v1/workcompiler/traces/<run_id>`)

## 재현

```bash
python3 -m uvicorn adapters.proxy.server:app --port 8787 &
codex                                  # TUI에서 prompt.md의 세 줄 입력
# 또는 비대화형:
codex exec '$ow-compile-work examples/quality_analysis.work'
codex exec '$ow-traces'
codex exec '$ow-compile-trace codex-session'
```

산출물 트리는 프록시 없이도 재생성할 수 있습니다:

```bash
python3 -m core.openworklang compile examples/quality_analysis.work --build-dir examples/demo/openworkcompiled
python3 -m core.build from-trace examples/demo/output/proxy-trace-*.json --target codex-session \
  --build-dir examples/demo/build --behaviors examples/customer-renewal
```

> 참고: GIF는 대화형 TUI 세션을 녹화한 것이고, `output/`의 transcript는 같은 스킬을 `codex exec`로 다시 실행해 수집한 것입니다(녹화용 임시 CODEX_HOME은 인증 토큰 사본 때문에 녹화 후 삭제). 따라서 run_id·토큰 수는 GIF와 다르지만 단계·명령·산출물 구조는 동일합니다.
