# OpenWorkCompiler 전체 프로젝트 리뷰

검토일: 2026-08-28
검토 방식: 아키텍처·품질/보안·제품 도식 관점의 병렬 검토
검토 범위: `core/`, `adapters/`, `protocols/`, `tests/`, `docs/`, `examples/`

## 결론

OpenWorkCompiler의 핵심 설계 방향은 명확하다.

`Agent/API Trace → TraceIR → Behavior Contract → WorkCompiler → WorkIR → Durable Runtime → Quality/Oracle → Optimizer`

Work IR을 실행의 canonical asset으로 삼고, 결정형 코드·규칙·ML·SLM을 우선 사용한 뒤 예외에만 Frontier LLM/Human을 호출하는 전략은 프로젝트의 가장 강한 차별점이다. 테스트는 현재 111개가 모두 통과한다.

다만 문서가 약속하는 제품 수준과 실제 구현 사이에는 다음 네 가지 큰 간극이 있다.

1. 프록시는 실제 upstream 전달 계층이 아니라 synthetic 응답을 생성한다.
2. Semantic v4 계층과 일부 policy/adapter는 스키마·문서 단계에 머문다.
3. 인증, 경로 제한, 실행 샌드박스, SSRF 방어가 부족하다.
4. checkpoint와 런타임이 단일 프로세스/파일 기반이라 분산 내구성을 보장하지 않는다.

## This change

The first safety slice is now implemented and covered by regression tests.

- Proxy compilation writes are restricted to `OPENWORKCOMPILER_WORKSPACE_DIR` (or the current workspace), malformed JSON returns a client error, and demo responses declare `X-OpenWorkCompiler-Response-Mode: synthetic`.
- Runtime startup rejects malformed/cyclic dependency DAGs, human responses must satisfy required fields before changing state, and checkpoints use `fsync` plus atomic replacement.
- Dynamic Python imports are disabled by default; an operator must opt in and allowlist module prefixes. HTTP executors reject private, loopback, link-local, reserved, and redirect-to-private destinations unless the operator explicitly enables private-network access.
- `pyproject.toml` now declares the package metadata and runtime/test dependencies.

These changes intentionally do not make the proxy a live upstream forwarding service. The synthetic mode is now explicit so it cannot be mistaken for a production passthrough.

## 강점

- `core`와 `adapters`/`protocols`의 경계가 분명해 외부 연동이 커널을 오염시키지 않는다.
- Work IR에 dependency DAG, cycle detection, retry, pause/resume, checkpoint, human/event/timer 대기 상태가 표현되어 있다.
- Determinism → ML/Vector → SLM → Frontier/Human 순의 lowering 철학이 compiler analyzer와 optimizer에 반영되어 있다.
- Behavior contract와 결과 품질을 분리하고, lucky-correct 결과를 차단하려는 품질 모델이 있다.
- compiler/runtime/optimizer/proxy/trace/DAG를 포괄하는 111개 테스트가 있다.
- `docs/pipeline.mmd`와 `docs/behavior-loop.mmd`가 제품의 좌우 비교와 백그라운드 최적화 루프를 설명하는 좋은 기반이다.

## 우선순위가 높은 위험

### P0 — 실제 제품 경로와 안전성

- `adapters/proxy/server.py`는 선언된 `UPSTREAM_*_URL`을 호출하지 않고 synthetic 응답을 반환한다. 실제 agent trajectory 캡처와 문서의 transparent proxy 약속이 불일치한다.
- 프록시 엔드포인트에 인증·인가·tenant ownership·rate limit·body size 제한이 없다.
- `server.py`의 `output_path`를 요청자가 지정할 수 있어 허용 workspace 밖의 임의 파일 쓰기 위험이 있다.
- `core/runtime/executors.py`의 dynamic import는 비신뢰 Work IR에서 임의 Python callable 실행으로 이어질 수 있다.
- `HTTPExecutor`는 private IP/metadata endpoint 차단과 redirect 제한이 없어 SSRF 위험이 있다.
- `signal_event()`는 `WAITING_HUMAN`에서 event/assignee/required_fields를 충분히 검증하지 않아 승인 계약 우회 가능성이 있다.

### P1 — 내구성과 운영

- checkpoint를 직접 덮어쓰므로 중단 시 잘린 JSON이 남을 수 있다. temp file + fsync + atomic rename, schema/version/hash 검증이 필요하다.
- workflow registry와 interceptor/history가 프로세스 메모리에만 있고 TTL/상한/lock이 없다.
- event log와 state snapshot, idempotency key, step attempt token, side-effect dedupe, worker lease가 없다.
- cyclic/invalid dependency가 start 시점에 거부되지 않아 workflow가 RUNNING에 남을 수 있다.

### P1 — Semantic v4 실행 연결

`core/semantic_ir/`, `adapters/linkml/`, `adapters/owl/`, `adapters/shacl/`, `core/policy/`는 현재 대부분 README/schema 수준이다. 문서의 `Trace → LinkML → Semantic IR → OWL/SHACL → Runtime`은 목표 아키텍처로 표시하고, LinkML parser → Semantic IR AST → 최소 OWL/SHACL vertical slice를 실제 compiler gate에 연결해야 한다. 또한 compiler가 생성하는 Work IR `3.0`과 v4 문서/schema의 버전 정책 및 migration 규칙을 명시해야 한다.

### P2 — 컴파일러 신뢰성

- OpenWorkLang parser의 regex fallback은 중첩 brace, escaped quote, 주석, nested config와 병렬 DAG 표현에 취약하다.
- invalid/partial parse를 조용히 수용하지 말고 명시적으로 reject해야 한다.
- executor analyzer의 keyword 휴리스틱에는 sample count, confidence calibration, canary/rollback evidence gate가 필요하다.

## 권장 실행 순서

1. 실제 upstream forwarding과 명시적 `SYNTHETIC_MODE=dev` 분리
2. 인증/인가, output workspace canonicalization, SSRF/private-IP 차단, dynamic import allowlist
3. atomic checkpoint와 durable trace/artifact 저장소 도입
4. DAG 사전 검증, human signal 계약 검증, idempotency/lease semantics 정의
5. Semantic v4 최소 vertical slice와 Work IR 버전/migration 정책 구현
6. parser를 canonical YAML/JSON 또는 tokenizer 기반 AST parser로 교체
7. production trace와 demo/synthetic trace namespace 분리, provenance·cost·latency·redaction telemetry 표준화

## 파이프라인 도식 피드백

현재 도식은 방향이 맞다. 발표용으로는 다음 대비를 더 선명하게 하면 된다.

- 왼쪽: `Frontier LLM + Agent → 매번 재추론 → tool calls → 결과(품질 미측정)`
- 오른쪽: `Approved trace → LLM-as-Compiler → Work IR/Policy/Behavior invariants → Code/Rule/ML/SLM routing → Durable Runtime → Output + Quality`
- 오른쪽 아래 점선 영역: `Trace analysis → Compiler → Optimizer → SLM consolidation → Canary → Production`
- 정상 경로에는 Frontier 모델을 넣지 말고 `quality drop / violation / timeout`에서만 `Frontier/Human escalation`을 표시한다.
- 문서에서 아직 구현되지 않은 Semantic v4 및 distributed durability는 “planned/target” 레이어로 구분해 표현한다.

## 검증 기록

```text
pytest -q                                      111 passed
python3 -m compileall -q core protocols adapters examples   passed
```

현재 테스트가 직접 검증하지 않는 영역: 실제 upstream proxy forwarding, malformed JSON/HTTP timeout, auth/tenant isolation, SSRF 방어, atomic checkpoint 복구, concurrent worker claim, Semantic adapter 구현, cycle-at-start rejection.

## 참고 파일

- `README.md`
- `docs/pipeline.mmd`
- `docs/behavior-loop.mmd`
- `docs/v4-architecture-semantic-layer.md`
- `core/compiler/compiler.py`
- `core/runtime/engine.py`
- `core/runtime/executors.py`
- `adapters/proxy/server.py`
- `core/openworklang/parser.py`
- `conversations/2026-08-28_결정형-온톨로지와-LLM.md`
