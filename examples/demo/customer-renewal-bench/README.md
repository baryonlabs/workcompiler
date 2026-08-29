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
