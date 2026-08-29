# claude-code-bench — Claude Code 세션을 프록시로 캡처 → 컴파일 → 벤치마크

[`customer-renewal-bench/`](../customer-renewal-bench/)와 **같은 업무**([`examples/customer-renewal/TASK.md`](../../customer-renewal/TASK.md): CUST-1001 연간 갱신 제안서)를
이번에는 **Claude Code**(v2.1.251, 구독 로그인)로 수행한 실제 세션입니다. Codex 때와 달리 어떤 코드도 바꾸지 않았습니다 —
`ANTHROPIC_BASE_URL`만 프록시로 향하게 했습니다.

```bash
owc proxy --port 8788 &
rm -rf build/renewal                                   # 빈 상태에서 시작
ANTHROPIC_BASE_URL=http://127.0.0.1:8788 claude -p 'Read examples/customer-renewal/TASK.md and carry it out exactly as written.' \
  --output-format json --permission-mode acceptEdits --allowedTools "Bash,Read,Write,Edit,Glob,Grep" --no-session-persistence
curl -s localhost:8788/v1/workcompiler/traces | jq       # source_agent: claude-code, run_id: claude_<session_id>
curl -s -X POST localhost:8788/v1/workcompiler/compile -H 'Content-Type: application/json' \
  -d '{"run_id":"claude_5603ea11-…","target_name":"customer-renewal-claude","build_dir":"build"}'
rm -rf build/renewal && owc build bench build/customer_renewal_claude
```

## 캡처된 것 ([`output/proxy-trace-claude_5603ea11-….json`](output/))

| 항목 | 값 |
| :-- | :-- |
| `source_agent` / `agent_version` / `protocol` | `claude-code` / `2.1.251` / `anthropic` (`user-agent: claude-cli/2.1.251`) |
| `run_id` | `claude_5603ea11-cf34-4d8d-b6db-0be21322061e` — 요청의 `metadata.user_id`(JSON)에 든 `session_id` |
| 스텝 | 7 (Claude Code 12턴 중 병렬 `Read`×3+`Glob`은 한 스텝으로 병합, 최종 답변은 `respond`) |
| 액션 | `read_task` · `read_contracts` · `read_behavior` · `shell_cd` · `shell_mkdir` · `shell_cat` · `respond` |
| 도구 정규화 | `Read` → `cat <file>` · `Glob` → `find … \| sort` · `Bash` → `shell_<prog>`(jq / mkdir+python3 heredoc / cat heredoc) |
| 도구 결과 | 각 `tool_result` 블록이 호출 스텝에 부착(`Read`의 줄번호 `N<TAB>` 제거) |
| 토큰 | 스텝별 `input + cache_read + cache_creation` (첫 턴 170k 중 cache_creation이 대부분: 사용자 전역 `CLAUDE.md`·도구 스키마) |

## 결과 ([`build/customer_renewal_claude/BENCHMARK.md`](build/customer_renewal_claude/BENCHMARK.md))

| | 기록된 에이전트 (Claude Code, 7 스텝) | 컴파일된 빌드 (빈 상태에서 재실행) | 차이 |
| :-- | --: | --: | --: |
| LLM 토큰 (캐시 읽기 포함) | 1,426,098 | 213,044 | **−85.1%** |
| 벽시계 시간 | 74.1 s | 10.7 s | **6.9×** |
| 결과 재현 (code 계층 스텝) | — | **4/6 일치** (아래 참고) | |
| 최종 산출물 `pricing-CUST-1001.json` · `proposal-CUST-1001.md` | — | **바이트 단위 동일** ([`agent-outputs/`](agent-outputs/) vs 재실행) | |

| action | tier | 토큰 rec → comp | 지연 rec → comp | 결과 |
| :-- | :-- | --: | --: | :-- |
| `read_task` (Read TASK.md) | code | 170,135 → 0 | 4.1 s → 0.01 s | 일치 |
| `read_contracts` (Read×3 + Glob, 병렬) | code | 204,588 → 0 | 6.7 s → 0.05 s | 불일치 — `Glob` 결과는 `examples/…`, 캡처 당시 합성된 `find .`는 `./examples/…`(이후 수정, 새 캡처부터 일치) |
| `read_behavior` (Read×2) | code | 206,473 → 0 | 4.4 s → 0.01 s | 일치 |
| `shell_cd` (jq 활성 계약 조회 + 사용량 집계) | code | 208,933 → 0 | 19.1 s → 0.03 s | 일치 |
| `shell_mkdir` (python3 heredoc으로 가격 JSON 산정·작성) | code | 210,765 → 0 | 16.7 s → 0.02 s | 일치 |
| `shell_cat` (cat heredoc으로 제안서 작성 + `ls -la`) | code | 212,160 → 0 | 12.5 s → 0.01 s | 불일치 — `ls -la`의 시각(12:33 vs 12:34); 파일 내용은 동일 |
| `respond` (최종 요약) | frontier_llm | 213,044 → 213,044 | 10.6 s → 10.6 s | 에스컬레이션(기록 비용 유지) |

읽는 법: Codex 벤치([`customer-renewal-bench/`](../customer-renewal-bench/), −85%, 7.4×)와 **같은 구조의 결과**입니다. 에이전트가 달라도
업무 자체(계약 조회·집계·산정·파일 작성)는 전부 code 계층으로 내려가 토큰 0으로 재현되고, 남는 것은 사람에게 보여줄 요약 한 스텝입니다.
토큰 절대값이 Codex보다 큰 이유는 Claude Code가 매 턴 사용자 전역 `CLAUDE.md`와 도구 스키마를 프롬프트 캐시에서 읽기 때문이며(스텝별 `recorded_cached_tokens` 참고),
컴파일된 빌드는 그 비용을 통째로 없앱니다.

## 폴더

| 경로 | 내용 |
| :-- | :-- |
| `output/claude-transcript.json` | `claude -p --output-format json`의 결과(최종 답변·usage·cost·session_id) |
| `output/proxy-trace-claude_….json` | 세션 TraceIR 전체 — 스텝별 도구 호출·정규화된 명령·토큰·도구 결과·provenance |
| `output/compile-response.json` | `POST /v1/workcompiler/compile` 응답 |
| `agent-outputs/` | Claude Code가 직접 만든 산출물 (재실행 결과와 diff 무차이) |
| `build/customer_renewal_claude/` | 컴파일된 빌드 트리(`handlers/read_*.py`, `shell_*.py`, `prompts/respond.prompt.md`, `.work`) + `BENCHMARK.md` |
