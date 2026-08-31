# 지속적·조직적 활용 가이드 — 개인의 실행이 조직의 자산으로

각 구성원은 자기 에이전트(Codex·Claude Code·Cursor…)로 평소처럼 일합니다. OpenWorkCompiler가 하는 일은
그 실행의 결과물(트레이스→빌드, escalate-once 캐시, 벤치 원장, 판단 기록)을 **합류 가능한 형태**로 만들고,
`owc org`가 그것을 **공유 git 레지스트리 하나**로 모으는 것입니다. 새 인프라는 없습니다.

## 합류 경로 5개

| 개인이 만드는 것 | 명령/시점 | 조직이 얻는 것 |
| :-- | :-- | :-- |
| 컴파일된 빌드 | `owc org publish build/<work>` | 동료가 `owc org pull <work>` 즉시 0토큰 재실행 |
| escalate-once 캐시 | publish에 포함(파라미터 키 merge, 신선한 upstream_sha 승) | A가 처리한 파라미터는 B의 반복 실행도 0원 |
| 판단 기록·평가 | 결정 코퍼스 append → 주기 재훈련(fleet-eval 게이트) | 판단 정확도가 조직 규모로 상승 |
| 정책(catalog.yaml) | 레지스트리 단일 원본 수정 → 재생성 | 정책 개정이 전 조직의 판단에 일관 반영 |
| 벤치 totals | publish 시 `ledger/<work>.jsonl` append | `owc org status` 절감 원장, CI 대시보드 |

## 3단계 도입

1. **개인 (1주)** — `pipx install git+…` → `owc proxy` 상시 기동, `owc agent setup <cli>`,
   `owc skills install --agent <cli>`. 습관 변화 없음: 평소처럼 에이전트로 일하면 캡처는 자동.
2. **팀 (1개월)** — 레지스트리 repo 생성 → 전원 `owc org init <repo>`. 규칙: **사람이 결과를 승인한
   실행만 publish**. 주간 루틴(CI/cron): 모든 works `owc build bench`(결정론이라 무료·회귀 감지),
   데이터셋 병합 → 재훈련 → `fleet-eval`, `owc build harden --budget-tokens N`.
3. **조직 (분기)** — 결정 카탈로그를 레지스트리로 중앙화(정책 소유자 지정), `owc org status` 절감
   원장을 경영 지표로, `owc-inspect`(tools/inspect)로 레이어별 검증 상태를 누구나 열람.

## 역할과 거버넌스

- **작업 소유자**: WHAT(TASK/BEHAVIOR)과 publish 승인. **정책 소유자**: catalog 규칙 개정.
  **레지스트리 관리자**: 주기 루틴·회귀 대응.
- 승인된 실행만 자산화(원칙: 사람은 결과 품질만 평가). publish 전 트레이스의 PII/비밀 확인은
  작업 소유자 책임. 자동 수정이 못 넘는 결함은 `needs_human` 게이트로 명시된다(뭉개지 않음).
- 캐시는 상류 출력 지문으로 자동 무효화되므로 낡은 결과 재생 위험이 통제된다(`--no-cache`, `owc build cache list|clear`).

## 측정 지표

절감 원장(recorded vs compiled 토큰, `owc org status`) · 재현율(벤치, run-dependent 출력 분리) ·
캐시 적중률 · unseen 정책 정확도(fleet-eval) · needs_human 잔여 수. 전부 파일로 남고
`owc-inspect`가 시각화한다.
