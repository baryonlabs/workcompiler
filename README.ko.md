# OpenWorkflow

**AI 작업을 위한 실행 레이어 (The execution layer for AI work)**

AI가 한 번 작업하게 하세요. OpenWorkflow는 이후 작업을 안정적으로 실행하는 방법을 배웁니다.

> **"코어 커널을 구축하고, 생태계를 통합하라 (Build the kernel, integrate the ecosystem.)"**
> 
> *"당신의 에이전트, UI, 평가 도구를 가져오세요. OpenWorkflow가 작업을 컴파일합니다."*

---

## 왜 OpenWorkflow인가?

코딩 에이전트와 프론티어 LLM은 뛰어난 수행 능력을 갖추었지만, 그 출력은 반복 가능하지 않고, 비용 효율적이지 않으며, 관측 가능하지 않습니다. 매 요청마다 프론티어 비용을 지불하며 동일한 추론을 처음부터 다시 수행하지만, 품질은 지속적으로 측정되지 않습니다.

OpenWorkflow는 이를 역전시킵니다: 에이전트가 1회 작업을 수행하고 인간이 결과를 평가하면, 시스템은 검증된 실행 과정을 백그라운드에서 결정론적으로 실행되는 안정적이고 최적화된 워크플로우로 컴파일합니다.

**AI는 실행합니다. 인간은 결과 품질을 평가합니다. OpenWorkflow는 행위를 감독하고, 작업을 컴파일하며, 실행을 지속적으로 최적화합니다.**

결과물이 올바른 것과 작업을 수행한 방식이 올바른 것은 동일하지 않습니다. OpenWorkflow는 결과물뿐만 아니라 과정(행위)을 감독합니다 — [Behavior Contract Layer](docs/behavior-contracts-v2.md) 및 [v3 아키텍처 명세](docs/v3-architecture-kernel-ecosystem.md)를 참고하세요.

---

## 핵심 전략: 커널 vs 생태계 (Kernel vs Ecosystem)

OpenWorkflow는 **얇고 강력한 실행 & 컴파일 커널(Kernel)**로 작동합니다. 데스크톱 UI, 슬랙 봇, 에이전트 프레임워크, 평가 플랫폼을 직접 재개발하지 않으며, 컴파일 및 지속적 실행 커널을 소유하면서 표준 어댑터를 통해 외부 생태계와 연결됩니다.

| 영역 | 전략 | 연동 대상 및 표준 |
| :--- | :---: | :--- |
| **코어 실행 커널** | **직접 개발** | Work Compiler, Durable Runtime, Policy/Commit, Optimizer |
| **데스크톱 UI / 로컬 에이전트** | 최소화 | **OpenWorker** (데스크톱 쉘 및 로컬 실행) |
| **Slack / Teams UX** | 최소화 | **OpenTag / CopilotKit** |
| **에이전트 UI 프로토콜** | 어댑터 | **AG-UI Protocol** |
| **에이전트 도구 노출** | 어댑터 | **MCP (Model Context Protocol)** |
| **행위 규격 사양** | 네이티브 호환 | **AgentBehavior** (`BEHAVIOR.md` spec) |
| **LLM 트레이싱 & 평가** | 어댑터 | **Braintrust / Langfuse / OpenTelemetry** |
| **워크플로우 캔버스** | 향후 / 임베딩 | n8n / Windmill 참조 및 임베딩 |
| **지속성 시맨틱** | 코어 개념 | Temporal 방식의 지속성 상태 머신 |
| **인간 중단 UX** | 어댑터 | OpenTag / CopilotKit 승인 카드 |
| **로컬 툴 실행** | 어댑터 | OpenWorker (로컬 워크스페이스, 쉘, 파일) |
| **모델 학습 인프라** | 외부 연동 | Hugging Face TRL / Unsloth / Cloud Fine-Tuning |

---

## 핵심 개념: 작업 컴파일 & `Work IR`

```
Agent Trace  ──▶  Trace IR  ──▶  Work Compiler  ──▶  Work IR  ──▶  Durable Runtime
```

**Work IR** (`work.yaml`)은 OpenWorkflow의 핵심 고유 자산입니다. 특정 LLM, UI, 클라우드 인프라에 독립적인 결합 가능한 비즈니스 작업의 결정론적 실행 정의서입니다.

```yaml
work: customer-renewal
version: 3.0

inputs:
  - customer_id

outputs:
  - renewal_proposal_pdf

states:
  - initialized
  - contract_verified
  - usage_calculated
  - proposal_drafted
  - approved
  - sent

actions:
  - lookup_contract
  - calculate_usage
  - price_offer
  - draft_proposal
  - send_email

dependencies:
  calculate_usage: [lookup_contract]
  price_offer: [calculate_usage]
  draft_proposal: [price_offer]
  send_email: [draft_proposal]

invariants:
  - verify_current_contract
  - use_current_pricing_policy
  - require_approval_before_send

quality:
  reviewer_acceptance: ">=0.95"

executors:
  draft_proposal:
    type: slm
    preferred: models/renewal-draft-slm-v1
    fallback:
      - frontier_llm
      - human
```

---

## 5대 표준 프로토콜 경계 (5 Standard Protocols)

OpenWorkflow는 5가지 표준화된 프로토콜 계약을 통해 외부 표면 및 도구와 연결됩니다.

1. **Ingress Protocol**: 외부 트리거(웹훅, cron 타이머, 슬랙 이벤트, 이메일 알림)를 위한 표준화된 이벤트 규격.
2. **Surface Protocol (AG-UI)**: OpenTag, CopilotKit과 같은 UI 표면에 실시간 워크플로우 이벤트를 스트리밍 (`workflow.started`, `step.started`, `approval.requested`, `workflow.completed`).
3. **Tool Protocol (MCP)**: 외부 에이전트에 제어 엔드포인트(`start_work`, `get_work`, `list_approvals`, `approve`)를 Model Context Protocol로 노출.
4. **Trace/Eval Protocol (Trace IR)**: 다양한 에이전트 트레이스(OpenAI, LangGraph, Braintrust, OpenWorker)를 **Trace IR**로 정규화 수집.
5. **Worker Protocol**: 로컬/원격 실행 워커(로컬 파일/쉘 작업을 수행하는 OpenWorker Desktop) 오케스트레이션.

---

## 전체 시스템 아키텍처 (v3 Kernel & Ecosystem)

```
                               ECOSYSTEM
┌────────────────────┐   ┌────────────────────┐   ┌────────────────────┐
│   OpenWorker Desktop│   │   OpenTag / Slack  │   │  Custom Agents     │
│   (Local Worker)   │   │   (CopilotKit)     │   │  (LangGraph, etc.) │
└─────────┬──────────┘   └─────────┬──────────┘   └─────────┬──────────┘
          │ Tool (MCP)             │ Surface (AG-UI)        │ Trace / Ingress
          ▼                        ▼                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    OPENWORKFLOW GATEWAY ADAPTERS                     │
│   Ingress Protocol · Surface Protocol (AG-UI) · Tool Protocol (MCP)  │
│   Trace/Eval Protocol (Trace IR) · Worker Protocol                   │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │ Trace IR / Event IR
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         OPENWORKFLOW CORE                            │
│                                                                      │
│   ┌──────────────────────┐               ┌──────────────────────┐    │
│   │    Work Compiler     │               │ Quality & Behavior   │    │
│   │  Trace → Work IR     │               │ Contracts            │    │
│   └──────────┬───────────┘               │ (AgentBehavior spec) │    │
│              │                           └──────────┬───────────┘    │
│              ▼                                      │                │
│       ┌──────────────┐                              │                │
│       │   Work IR    │                              │                │
│       └──────┬───────┘                              │                │
│              ▼                                      ▼                │
│   ┌──────────────────────┐               ┌──────────────────────┐    │
│   │   Durable Runtime    │ ◄──────────── │      Optimizer       │    │
│   │ (State/Timer/Signal) │               │ Routing / SLM Promo  │    │
│   └──────────┬───────────┘               └──────────────────────┘    │
│              │                                                       │
│              ▼                                                       │
│   ┌──────────────────────┐                                           │
│   │   Policy / Commit    │                                           │
│   │ Validation/Approvals │                                           │
│   └──────────────────────┘                                           │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │ Execution & Telemetry
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    EXTERNAL EVAL & INFRA ADAPTERS                    │
│   Braintrust / Langfuse / OTel  ·  HuggingFace/TRL  ·  Temporal    │
└──────────────────────────────────────────────────────────────────────┘
```

### 컴파일 비유: LLVM IR & Late-Binding Provider Adapters

OpenWorkflow는 LLVM이 개척한 전형적인 컴파일러 아키텍처 패러다임을 따릅니다:

```text
[ Classical Compiler (LLVM) ]             [ OpenWorkflow Work Compiler ]

      C / C++ Source Code                       Frontier Agent Trace
               │                                         │
               ▼                                         ▼
         LLVM Frontend                             Work Compiler
               │                                         │
               ▼                                         ▼
   LLVM IR (Target-Agnostic)              Workflow IR + BEHAVIOR.md (Vendor-Agnostic)
               │                                         │
    ┌──────────┴──────────┐                   ┌──────────┴──────────┐
    ▼                     ▼                   ▼                     ▼
x86 Target           ARM Target          GCP Provider          AWS Provider / On-Prem
```

---

## 비타협적 개발 경계

### ❌ OpenWorkflow가 직접 만들지 않는 것
- 커스텀 Slack / Teams 봇 프레임워크
- 독자적인 데스크톱 쉘 / GUI 애플리케이션
- 시각적 드래그 앤 드롭 워크플로우 캔버스
- 전용 LLM 관측성 / 트레이싱 플랫폼
- 파인튜닝 & GPU 클러스터 인프라
- 자체 벡터 데이터베이스

### ✅ OpenWorkflow가 직접 만들고 소유하는 핵심
- **Trace → Work IR 컴파일러**: 에이전트 트레이스를 결정론적 Work IR로 분해
- **Work IR → Compiled Workflow**: 최적화된 실행 DAG 합성
- **Behavior → 실행 불변식**: `BEHAVIOR.md`를 룰, 제약조건, 검증 판정기로 컴파일
- **실행 주체 최적화 및 통합**: Code, Rule, SLM, LLM 간 동적 라우팅 및 모델/행위 통합
- **Durable Runtime & 인간 승인 루프**: 지속적 상태 관리, 중단, 시그널, 인간 결과 품질 평가
- **지속적 재컴파일 백엔드**: 품질 신호 및 드리프트에 따른 백그라운드 재컴파일 루프

---

## 리포지토리 레이아웃 (v3)

```
openworkflow/
├── core/                        # 얇고 강력한 OpenWorkflow 커널
│   ├── work_ir/                 # Work IR 스키마, 파서, AST
│   ├── compiler/                # Trace IR → Work IR 컴파일러
│   ├── runtime/                 # Durable 상태 머신 & 체크포인팅
│   ├── policy/                  # 권한, 승인, 신뢰도 임계치
│   ├── validation/              # Behavior & Outcome 검증기
│   └── optimizer/               # 실행 라우팅 & SLM 승격/통합
│
├── protocols/                   # 5대 표준 프로토콜 규격
│   ├── events/                  # Ingress Protocol
│   ├── traces/                  # Trace IR 규격
│   ├── workers/                 # Worker Protocol
│   └── surfaces/                # AG-UI Surface Protocol
│
├── adapters/                    # 생태계 연동 어댑터
│   ├── agui/                    # AG-UI 스트리밍 어댑터
│   ├── mcp/                     # MCP 도구 어댑터
│   ├── opentag/                 # OpenTag 슬랙/티어스 어댑터
│   ├── openworker/              # OpenWorker 데스크톱 어댑터
│   ├── agentbehavior/           # AgentBehavior BEHAVIOR.md 임포터
│   ├── braintrust/              # Braintrust 트레이스/평가 어댑터
│   └── opentelemetry/           # OpenTelemetry 내보내기 어댑터
│
├── agents/                      # 가이드 및 측정 에이전트 규격
├── docs/                        # 명세서, 아키텍처, 다이어그램
├── conversations/               # 설계 아카이브
└── examples/                    # Sample Work IR, Traces & Behavior specs
```

---

## 라이선스

MIT
