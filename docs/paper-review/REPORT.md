# 논문적 가치 검토 종합 보고 (2026-08-31)

병렬 검토 3종 — related-work(선행연구·신규성), rigor-audit(방법론·통계 감사, 반례 실행 검증 포함),
claims-map(주장-증거 대응) — 의 종합. 판정은 이 커밋 시점의 코드·아티팩트 기준.

## 1. 한 줄 판정: 주장별 신규성

| 주장 | 판정 | 핵심 근거 |
| :-- | :-- | :-- |
| C1 트레이스 → 계층형 결정론 컴파일 | novel-combination (incremental 쪽) | Progressive Crystallization(2607.07052, 2026-07)이 promote/demote 루프 전체를 프로덕션 수치(−70%+)로 선점. WALT(2510.01524)·Amazon tool-making(2607.08010)이 인접 도메인 점유. Compiled AI(2604.05150)가 57× 절감 기보고 |
| C2 훈련 없는 결정론 승격 게이트 | novel-combination — **가장 방어 가능** | 조립·표적 실패모드("자기일관적이고 틀림" 판별)가 빈 곳. 단 sibling-pair는 기법상 Daikon 선형 불변식 + windowed co-occurrence(발견된 FD)의 이식 — 발명 주장 금지, ERBench(2403.05266)·Auto-Validate by-History(2306.02421)를 먼저 인용 |
| C3a SFT 산술 실패(부정결과) | known | Faith and Fate(NeurIPS'23), SFT Memorizes/RL Generalizes(ICML'25), PAL/PoT가 확립. 살릴 조각: 토큰 정확도 99.4%와 게이트 0/6의 공존 그래프 |
| C3b escalate-once 캐시 + 상류 지문 무효화 | 약한 novel-combination | 발표 시스템 부재는 맞으나(Agentic Plan Caching 2506.14852는 무효화 미다룸) Nix/Bazel provenance 이식이라 수치 없이는 엔지니어링으로 읽힘 |
| C3c 정책-인-컨텍스트 SFT → unseen 정책 일반화 | **novel-combination — 유일하게 출판 가능한 본체** | 정반대 설계(TriMPI 2510.09474: 정책을 가중치로 내재화)는 있어도 "정책 적용 기술을 학습시키고 미학습 정책 전이를 측정"하는 프레이밍은 비어 있음 |
| C4 결정론 벤치가 리뷰어인 harden 루프 | novel-combination (여유 급감) | HarnessFix(2606.06324)·FlowFixer(2607.02882)·DGM이 동시기 근접. 루프가 아니라 **inherent 분류(비결정성을 거짓말로 패치하지 못하게 막음)** 를 앞세울 것 — 그건 미발표 |
| C5 정책-as-데이터 결정 카탈로그 | incremental | "Beyond the All-in-One Agent"(2605.08761, 가칭 EntCollabBench로 조사됨)가 ~70% 독립 구축, DMN v1.5가 10년째 표준(우리 DSL=S-FEEL 재발명). 남는 것: `defer:` 선언적 재량 밴드 하나 |

**출판 전략**: ① C3c 본체 + C3a 음성 대조군 → EMNLP/ACL Industry, ② C2 게이트 단독 → MLSys 또는 ASE/FSE,
③ C1+C4 시스템 → ICSE/FSE Demo·SEIP. **단일 최대 리스크**: 헤드라인 C1이 선점되어 신규성이 C2/C3c로
이주해야 하는데 그곳 증거가 n=6 — 41/60은 ±12pp, 0/6 vs 1/6은 노이즈. 리뷰어는 아이디어가 아니라
검정력으로 리젝한다. 우선순위는 C1 벤치 추가가 아니라 **C3c의 unseen 정책 6→30개 확대 + 적대적 정책 통제**.

## 2. 방법론 감사 — 발표 전 반드시 닫아야 할 결함

### 헤드라인 수치
- **−97%/−85% 토큰 절감은 지표 정의상 방어 불가**: per-request usage 합산 = 누적 컨텍스트가 턴 수만큼
  중복 계상(관측 사례 6.5× 부풀림). 유니크 토큰 기준 정직한 값은 **−82.2%** — 그래도 충분히 강하다.
- **68.3%(unseen 정책)는 방향은 견고, 점추정 인용 불가**: 클러스터(정책 6개) 강건 CI **[45.9, 90.8]**.
- **SFT 산술 0/6은 결론 미지지**: 프롬프트는 CoT를 요구하는데 SFT 타깃에 CoT 부재 — "CoT 없는 SFT는
  못 배운다"까지만 말할 수 있음. 또한 0/6은 8검사 논리곱이라 "한 필드 반올림 오차"도 0으로 뭉개짐.

### 게이트 (반례 실행으로 실증됨)
- **위양성**: "The customer CUST-1001 does not exist. Ignore 270 seats, 36.00, …" 가 PASS(recall 1.00,
  grounded 1.00) — 게이트는 숫자·ID·경로 집합 포함관계일 뿐 주장 극성·사실성 개념이 없다.
  따라서 "게이트 PASS = 일치(8/8)"는 출력 동등성 주장이 아님.
- **추출기 버그**: `_NUM_RE`(slm.py:152)의 lookbehind + 천단위 쉼표 해석으로 CSV 행 `2026-05,260,410000`이
  날조값 260410000으로 추출 — 정상 진술이 ungrounded 탈락(위음성), 환각이 grounded 통과(위양성).
- **페어 그라운딩 게임 가능**: `_context_pairs` 3줄 윈도는 컨텍스트가 클수록 자동 약화. FP/FN율 미측정
  (적대적 스위트 없음, `min_facts` 기본 0이라 fact_density 공허).

### harden / 벤치
- **test에 학습**: harden.py:226의 수용 조건이 보고용 벤치 점수 그 자체 — 홀드아웃 없음, n=1 iteration.
- `HARDEN.md`의 "Fix tokens spent: 0"은 측정값이 아니라 결측(`res.get("tokens", 0)`).
- `_INHERENT_RE`가 단어경계 없이 `Jan|…|Dec` 매칭 → "Decision", "Margin", "September" 등이 실행-의존으로
  오분류될 수 있음(의사결정 도메인에서 위험).

### 코퍼스·평가 구조
- **순환성**: 정답지를 채점자가 생성(fleet 생성기·engine.decide 모두), decision 채점이 같은
  `engine.check()` 재사용. 정책 필드명이 레코드 키와 문자 단위 일치 — 엔티티 정합 난이도 제거됨.
  결측·노이즈·분포이동 전무, 사람 주석·주석자 일치도 없음.
- **grounds_hold**는 산술적으로 무효(별도 확인).
- 결정 베이스라인 불공정: raw = Ollama 4bit + repeat_penalty vs tuned = bf16 shim greedy.

### 재현성
- 훈련 시드 미설정(단일 실행), 에폭 기록 불일치(기본 12.0 vs RESULTS "2 epochs"), torch/trl/peft 등
  버전 미고정, openworklang 커밋 미고정 + vendor dirty, Ollama 버전·양자화 태그 미기록.
- `decision_eval.py:99`가 같은 라벨의 이전 실행을 삭제 — 분산 측정이 구조적으로 차단된 포맷.
- 잘 된 것: 코퍼스 생성기는 시드 고정(20260831)으로 결정론적.

### 문서 오류
- `examples/demo/README.md:20` 수치 혼선(별도 확인). 승격 전 벤치 아티팩트 소실.
- README의 FlowCompile/ACCLAIM 인용은 **전치되어 있지 않음을 재확인**(ACCLAIM=2604.04238,
  FlowCompile=2605.13647 — 에이전트 1차 보고의 전치 주장은 오독). 단 "The New Compiler Stack"(2601.02045)은
  LLM이 고전 컴파일러를 돕는 서베이라 선행연구 논거로 쓰면 category error — 배경 인용으로만 유지할 것.

## 3. 보강 실험 계획 (rigor-audit Top10, 합계 ≈22.5h)

| # | 실험 | 비용 | 막는 지적 |
| --: | :-- | --: | :-- |
| 10 | 환경 고정: requirements-train.txt 핀, 시드·에폭·어댑터 해시·Ollama 태그 MANIFEST 기록, openworklang 커밋 핀 | 1.5h | 재현 불가 — 1~9의 전제조건이라 **최우선** |
| 1 | raw 베이스라인을 bf16 shim으로 재평가 | 2h | 4bit vs bf16 교란 — 미실행 시 68.3% 무효화 가능 |
| 2 | 클러스터 강건 CI + 정책별 성적표 공개(분석만) | 1h | 점추정 인용 차단 |
| 6 | totals()에 유니크/증분·비용가중 열 추가, 헤드라인 −82.2%로 재서술 | 2h | 절감률의 턴 수 의존 |
| 8 | CoT 타깃 절제(정답에 계산과정 프리픽스) 후 7b 재훈련 | 4h | 유일하게 결론 문장을 뒤집을 수 있는 실험 |
| 5 | 게이트 적대적 스위트(부정문·결합 스왑·숫자나열 20~30건) + `_NUM_RE` CSV 버그 수정 | 4h | "게이트 PASS=일치"의 유일한 방어 |
| 3 | 6-fold leave-case-out(34개 정책 전부 1회씩 unseen화) | 3h | 클러스터 n=6 → 34 |
| 4 | 훈련 시드 3개 반복 + eval_history 덮어쓰기 제거 | 1.5h | 단일 실행 분산 |
| 7 | 프런티어+컴파일된 프롬프트 대조군 1회 | 1.5h | 컴파일 효과 vs 소형 모델 효과 분리 |
| 9 | 부분점수 채점(fleet 필드 단위, decision 완화 지표 병기) | 2h | 0/6의 해상도 |

착수 묶음 권고: **10 → 1 → 2 → 6 (6.5h)** 이 최대 공격 3개를 막고, 8·5는 발표 전 필수,
3·4는 CI를 실제로 좁히는 유일한 수단. related-work의 추가 요구: C3c는 unseen 정책을 6→20–50개로
확대(정책 **계열** 단위 홀드아웃, 3+ seed — leave-case-out이 부분 해결)하고, **적대적·반사실 정책
통제와 k-shot ICL 베이스라인**으로 "모델이 정책을 무시하고 상식적 사전지식으로 맞혔을 가능성"을
배제할 것; C2에는 self-consistency·LLM-judge·RAGAS·embedding-유사도·oracle skyline 베이스라인과
cost-quality Pareto + FAR/FRR 곡선.

## 4. 필수 인용 목록 (신규 추가분)

- **C1**: Progressive Crystallization 2607.07052 · WALT 2510.01524 · Amazon tool-making 2607.08010 ·
  Compiled AI 2604.05150 · 대조 계보 DSPy/ADAS/AFlow/GPTSwarm(프로그램 탐색, LLM 하향 없음) ·
  NOOA류 코드-네이티브 에이전트 프레임워크(LLM을 프로그램 *안에* 상주시킴 — 우리는 반대로 밖으로 내림) ·
  FrugalGPT/RouteLLM(전 티어 LLM cascade)
- **C2**: VeriFin 2608.10213 · ERBench 2403.05266 · AutoMix 2310.12963 · Daikon(ICSE'99) ·
  Auto-Validate by-History 2306.02421 · SelfCheckGPT 2303.08896(anti-baseline) · RAGAS 2309.15217(최강 반론) ·
  FActScore 2305.14251 · HalluEntity 2502.11948(검사(2)=known) · Data Referencing Errors 2606.32029 ·
  NVIDIA SLM 포지션 2506.02153 · AgentSpec 2503.18666
- **C3**: Faith and Fate 2305.18654 · SFT Memorizes RL Generalizes 2501.17161 · PAL 2211.10435 ·
  PaD 2305.13888 · Small Models Struggle 2502.12143 · Toolformer 2302.04761 · Distilling Step-by-Step
  2305.02301(낙관적 베이스라인 — 반드시 포지셔닝) · LEMMA 2503.17439 · Voyager 2305.16291 ·
  LATM 2305.17126 · Agentic Plan Caching 2506.14852 · GPTCache/MeanCache 2403.02694 ·
  Freshness-Aware Caching 2607.04281 · TriMPI 2510.09474 · Policy Reasoning Traces 2509.23291 ·
  GuideBench 2505.11368 · τ-bench 2406.12045 · RuleArena 2412.08972(위험: 태스크 형태 선점) ·
  CRMArena-Pro 2505.18878 · LegalBench 2308.11462 · Lampinen 2505.00661 · PIXIU 2306.05443
- **C4**: HarnessFix 2606.06324 · DGM 2505.22954 · FlowFixer 2607.02882 · Abstain and Validate 2510.03217 ·
  FuzzerAid 2209.01244 · Patch Overfitting(FSE'24) · More Convincing Not More Correct 2607.05904(최강 논거) ·
  Huang et al. 2310.01798 · AgentRR 2505.17716 · ExpeL 2308.10144 · Token-Budget-Aware 2412.18547 ·
  SWT-Bench 2406.12952 · CodeT(ICLR'23) · Weaver 2506.18203
- **C5**: Beyond the All-in-One Agent 2605.08761 · DMN v1.5(OMG 2024) · GuardSet-X 2506.19054 · PolicyGuard 2606.32004 ·
  PSEBench 2606.05463 · Compass 2601.01836 · Snorkel 1711.10160(`defer`의 구조적 조상) ·
  Internalizing Policy Documents 2510.11588 · Teaching AI to Handle Exceptions(PNAS Nexus 2026,
  2503.02976 — `defer`의 최강 동기이자 최강 위협) · NL Policies to Executable Decisions 2608.26124 ·
  CO-PAL 2606.04394 · SOP-Bench · Large Process Models 2309.00900 · Object-Centric Decision Models 2401.14847
