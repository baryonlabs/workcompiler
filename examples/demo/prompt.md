# Codex에 입력한 프롬프트

README 상단 데모(`docs/demo/openworkcompiler-codex-demo.gif`)에서 Codex TUI에 입력한 것은 아래 네 줄이 전부입니다.
`$ow-…`는 저장소 `.agents/skills/`에 있는 스킬을 명시적으로 호출하는 멘션입니다 (Codex가 리포지토리를 열면 자동 탐지).

```text
$ow-compile-work examples/quality_analysis.work
$ow-traces
$ow-compile-trace codex-session
$ow-bench codex-session
```

사전 조건은 프록시 한 줄뿐입니다 (Codex는 `~/.codex/config.toml` 또는 별도 `CODEX_HOME`에서 프록시를 provider로 지정 — README "Zero-Code 에이전트 프록시" 참고):

```bash
python3 -m uvicorn adapters.proxy.server:app --port 8787 &
codex
```

## 각 멘션이 Codex에 전달하는 지시문

스킬 파일 원문이 그대로 컨텍스트에 들어갑니다.

### 1. `$ow-compile-work <file.work>` — [.agents/skills/ow-compile-work/SKILL.md](../../.agents/skills/ow-compile-work/SKILL.md)

- `python3 -m core.openworklang compile <file.work> --linkml build/NAME.linkml.yaml` 실행
- 요약(work / inputs / outputs / actions / invariants / executors) 표시, `build/NAME.work.yaml` 앞 25줄 출력
- executor 계층(code / rule / ml / slm) 하위 통합과 잠긴 invariants를 2~3문장으로 설명, 끝에 🧩

### 2. `$ow-traces` — [.agents/skills/ow-traces/SKILL.md](../../.agents/skills/ow-traces/SKILL.md)

- `curl -s localhost:8787/v1/workcompiler/traces | jq` 실행
- 세션별 한 줄 요약(run_id, source_agent, steps_count, actions) — 현재 Codex 세션 자체가 캡처되고 있음을 언급, 끝에 📡

### 3. `$ow-compile-trace <target>` — [.agents/skills/ow-compile-trace/SKILL.md](../../.agents/skills/ow-compile-trace/SKILL.md)

- traces 중 steps_count가 가장 큰 run_id 선택
- `POST /v1/workcompiler/compile` (`target_name`, `output_path: build/<target>.work.yaml`) 실행 후 `{status, work_name, actions, executors_summary}` 표시
- `build/<target>.work.yaml` 앞 30줄 출력, 셸 스텝이 워크플로우 액션이 됐음을 설명, 끝에 ✅

### 4. `$ow-bench <target>` — [.agents/skills/ow-bench/SKILL.md](../../.agents/skills/ow-bench/SKILL.md)

- `python3 -m core.build bench build/<target>` 실행 — 빌드에 동봉된 `trace.json`(원본 세션)에 대해 code/rule 계층 핸들러를 재실행
- 액션별 토큰(기록 → 컴파일), 지연, 결과 일치 여부를 표로 출력하고 `BENCHMARK.md`/`benchmark.json` 저장
- 절감 토큰·속도·재현 수와 아직 에스컬레이션되는 액션을 설명, 끝에 📊
