# OpenWorkflow

**AI 작업을 위한 실행 레이어 (The execution layer for AI work)**

AI가 한 번 작업하게 하세요. OpenWorkflow는 이후 작업을 안정적으로 실행하는 방법을 배웁니다.

> **"코어 커널을 구축하고, 생태계를 통합하며, 시맨틱 진실을 강화하라 (Build the kernel, integrate the ecosystem, enrich with semantic truth.)"**
> 
> *"LinkML은 모델 작성의 관문이며, OWL은 시맨틱 진실 레이어이고, SHACL은 제약 조건을 검증하며, OpenWorkflow는 지속적 작업을 실행합니다."*

---

## 왜 OpenWorkflow인가?

코딩 에이전트와 프론티어 LLM은 뛰어난 수행 능력을 갖추었지만, 그 출력은 반복 가능하지 않고, 비용 효율적이지 않으며, 관측 가능하지 않습니다. 매 요청마다 프론티어 비용을 지불하며 동일한 추론을 처음부터 다시 수행하지만, 품질은 지속적으로 측정되지 않습니다.

OpenWorkflow는 이를 역전시킵니다: 에이전트가 1회 작업을 수행하고 인간이 결과를 평가하면, 시스템은 검증된 실행 과정을 백그라운드에서 결정론적으로 실행되는 안정적이고 최적화된 워크플로우로 컴파일합니다.

**AI는 실행합니다. 인간은 결과 품질을 평가합니다. OpenWorkflow는 행위를 감독하고, 작업을 컴파일하며, 실행을 지속적으로 최적화합니다.**

결과물이 올바른 것과 작업을 수행한 방식이 올바른 것은 동일하지 않습니다. OpenWorkflow는 결과물뿐만 아니라 과정(행위)을 감독합니다 — [Behavior Contract Layer](docs/behavior-contracts-v2.md) 및 [v4 아키텍처 명세](docs/v4-architecture-semantic-layer.md)를 참고하세요.

---

## 시맨틱 스택 아키텍처 (v4)

OpenWorkflow v4는 멀티 티어 시맨틱 스택을 도입합니다. **LinkML**을 개발자 친화적인 YAML 저작 언어로 활용하고, 이를 내장 **Semantic IR**로 컴파일한 뒤, **OWL 2** DL 의미론으로 풍부화하고 **SHACL**을 통해 폐쇄 세계(Closed-World) 데이터 제약조건을 검증합니다.

| 계층 | 역할 | 추천 기술 |
| :--- | :--- | :--- |
| **Authoring DSL** | 사람이 업무 모델 작성 | **LinkML (YAML DSL)** |
| **Semantic Canonical IR** | 내부 통일 시맨틱 모델 | **Semantic IR** |
| **Semantic Ontology** | 개방 세계 의미/관계/추론 | **OWL 2 (DL)** |
| **Constraint Validation** | 폐쇄 세계 데이터 제약 검증 | **SHACL** |
| **Reasoner** | 추론 및 일관성 검사 | **ELK / HermiT** |
| **Runtime Graph** | 지식 그래프 및 RDF 트리플 | **Jena / RDF4J / RDFLib** |
| **Execution Engine** | 지속성 워크플로우 실행 엔진 | **OpenWorkflow Kernel** |

---

## 컴파일 파이프라인: Trace → LinkML → Semantic IR → Execution

**LLM-as-Compiler**는 직접 복잡한 OWL 공리를 생성하지 않습니다. 대신 개발자 친화적인 LinkML 도메인 모델을 먼저 추출하고, 이를 정식 OWL 의미론 및 SHACL 제약조건으로 풍부화합니다.

```text
               Agent Trace
                    │
                    ▼
              LLVM / LLM Compiler
                    │
              LinkML Domain Model (YAML)
                    │
             Semantic Compiler
                    │
              Semantic IR (Canonical)
                    │
   ┌────────────────┼────────────────┬────────────────┐
   ▼                ▼                ▼                ▼
Pydantic          SHACL             OWL           Work IR
(Runtime Types) (Closed-World)  (Open-World)    (Durable DAG)
                    │                │
                    ▼                ▼
             Validation Gate     ELK / HermiT Reasoner
                    │                │
                    └────────┬───────┘
                             ▼
                    OpenWorkflow Runtime
```

---

## 핵심 개념: 작업 컴파일 & `Work IR`

```
Agent Trace  ──▶  Trace IR  ──▶  Work Compiler  ──▶  Work IR  ──▶  Durable Runtime
```

**Work IR** (`work.yaml`)은 OpenWorkflow의 핵심 고유 자산입니다. 특정 LLM, UI, 클라우드 인프라에 독립적인 결합 가능한 비즈니스 작업의 결정론적 실행 정의서입니다.

```yaml
work: customer-renewal
version: "4.0"

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

## 리포지토리 레이아웃 (v4)

```
openworkflow/
├── core/                        # 얇고 강력한 OpenWorkflow 커널
│   ├── semantic_ir/             # [v4] LinkML 파서, Semantic IR AST, OWL/SHACL 생성기
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
├── adapters/                    # 생태계 및 시맨틱 연동 어댑터
│   ├── linkml/                  # [v4] LinkML 저작 & 생성기 어댑터
│   ├── owl/                     # [v4] OWL 2 온톨로지 & ELK/HermiT 추론기 어댑터
│   ├── shacl/                   # [v4] SHACL 데이터 제약 검증기 어댑터
│   ├── agui/                    # AG-UI 스트리밍 어댑터
│   ├── mcp/                     # MCP 도구 어댑터
│   ├── proxy/                   # Zero-code LLM API 프록시 어댑터
│   ├── opentag/                 # OpenTag 슬랙/팀즈 어댑터
│   ├── openworker/              # OpenWorker 데스크톱 어댑터
│   ├── agentbehavior/           # AgentBehavior BEHAVIOR.md 임포터
│   ├── braintrust/              # Braintrust 트레이스/평가 어댑터
│   └── opentelemetry/           # OpenTelemetry 내보내기 어댑터
│
├── agents/                      # 가이드 및 측정 에이전트 규격
├── docs/                        # 명세서, 아키텍처, 다이어그램
├── conversations/               # 설계 아카이브
└── examples/                    # Sample Work IR, LinkML 스키마, Behavior specs
```

---


---

## 사용 가이드 & 데모 실행

전체 파이프라인 개발자 가이드 및 상세 사용법은 **[사용 가이드(docs/usage.md)](docs/usage.md)**를 참조하세요.

고객 계약 갱신 엔드투엔드 파이프라인 실시간 데모 실행:

```bash
python3 examples/run_customer_renewal_demo.py
```


## 생태계 및 참고 오픈소스 링크

OpenWorkflow는 다음 오픈소스 프로젝트, 표준 규격 및 연구 이니셔티브와 연동되거나 참고하여 개발됩니다.

| 카테고리 | 프로젝트 / 표준 | 링크 | 설명 |
| :--- | :--- | :--- | :--- |
| **모델 저작 DSL** | **LinkML** | [linkml/linkml](https://github.com/linkml/linkml) | YAML 모델링 기반 시맨틱 schema 표현 언어 |
| **시맨틱 온톨로지** | **OWL 2 / W3C** | [w3.org/TR/owl2-overview](https://www.w3.org/TR/owl2-overview/) | W3C 웹 온톨로지 시맨틱 추론 언어 표준 |
| **제약 조건 검증** | **SHACL / W3C** | [w3.org/TR/shacl](https://www.w3.org/TR/shacl/) | W3C RDF 폐쇄 세계 데이터 제약 조건 검증 규격 |
| **데스크톱 쉘 / 로컬 워커** | **OpenWorker** | [baryonlabs/openworker](https://github.com/baryonlabs/openworker) | 데스크톱 AI 에이전트 쉘 및 로컬 실행 워커 |
| **엔터프라이즈 채널 UX** | **OpenTag** | [baryonlabs/opentag](https://github.com/baryonlabs/opentag) | 슬랙 및 팀즈 채널 연동 AI 워크플로우 인터페이스 |
| **UI 스트리밍 프로토콜** | **AG-UI** | [agui-protocol/agui](https://github.com/agui-protocol/agui) | AI 워크플로우 상태를 UI에 스트리밍하는 표준 프로토콜 |
| **도구 연동 프로토콜** | **Model Context Protocol (MCP)** | [modelcontextprotocol.io](https://modelcontextprotocol.io) | AI 모델과 도구를 연결하는 Anthropic 표준 프로토콜 |
| **행위 규격 사양** | **AgentBehavior** | [braintrustdata/agentbehavior](https://github.com/braintrustdata/agentbehavior) | 프로세스 검증 사양(`BEHAVIOR.md`) 표준 규격 |
| **Zero-Code 에이전트 프록시** | **OpenCodex** | [lidge-jun/opencodex](https://github.com/lidge-jun/opencodex) | 에이전트 트레이스 가로채기용 투명 LLM API 프록시 |
| **LLM 트레이싱 & 평가** | **Braintrust** | [braintrustdata/braintrust](https://github.com/braintrustdata/braintrust) | 엔터프라이즈 LLM 평가 및 트레이싱 플랫폼 |
| **LLM 트레이싱 & 평가** | **Langfuse** | [langfuse/langfuse](https://github.com/langfuse/langfuse) | 오픈소스 LLM 엔지니어링 및 관측 플랫폼 |
| **관측성** | **OpenTelemetry** | [opentelemetry.io](https://opentelemetry.io) | 텔레메트리 데이터를 위한 클라우드 네이티브 관측 프레임워크 |
| **지속성 실행 엔진** | **Temporal** | [temporalio/temporal](https://github.com/temporalio/temporal) | 내결함성 지속성 상태 머신 및 워크플로우 실행 엔진 |
| **컴파일러 선행 연구** | **LLMCompiler** | [SqueezeAILab/LLMCompiler](https://github.com/SqueezeAILab/LLMCompiler) | ICML 2024 병렬 LLM 함수 호출 컴파일러 연구 |

---

## 라이선스

MIT
