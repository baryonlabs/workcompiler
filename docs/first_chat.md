LinkML은 OWL 중심 철학과 충돌하는 게 아니라, 오히려 “사람/개발자가 다루기 쉬운 상위 모델링 언어”로 매우 유용합니다.

제 판단은 이렇습니다.

OWL을 semantic truth layer로 두고, LinkML을 authoring/schema layer로 두는 조합이 좋습니다.

즉:

LinkML
= 사람이 작성하기 쉬운 업무 스키마 / 모델 DSL

OWL
= 의미론적 추론과 관계의 정식 표현

SHACL
= 데이터 제약 검증

OpenWorkflow
= 실행

정도로 역할을 나누면 깔끔합니다.

LinkML을 왜 넣어야 하나

OWL만 직접 작성하면 개발자 경험이 너무 무거워질 수 있습니다. 반면 LinkML은 YAML 기반으로 class, slot, enum, inheritance 등을 정의하고 여러 형식으로 생성할 수 있어서 OpenWorkflow의 업무 모델 작성 UX에 잘 맞습니다.

예를 들어:

classes:
  PurchaseRequest:
    slots:
      - amount
      - vendor
      - requester
      - status

slots:
  amount:
    range: decimal
    required: true

  vendor:
    range: Vendor
    required: true

이 정도는 일반 backend 개발자도 쉽게 이해할 수 있습니다.

이걸 컴파일해서:

LinkML
  ↓
JSON Schema
Pydantic
SHACL
OWL/RDF
API types

로 내리면 됩니다.

그래서 OpenWorkflow에서 LinkML은 상당히 좋은 Semantic Source Language 후보입니다.

하지만 LinkML을 ontology runtime으로 착각하면 안 됨

LinkML의 핵심 강점은:

schema modeling
data validation
generator ecosystem
developer-friendly YAML
여러 representation으로 변환

입니다.

반면 우리가 OWL에서 원하는:

logical entailment
classification
consistency checking
inferred types
description logic semantics
explanation/proof

는 OWL reasoner 쪽 역할입니다.

즉:

LinkML ≠ ELK
LinkML ≠ HermiT
LinkML ≠ OWLAPI

입니다.

LinkML이 이들을 대체하지는 않습니다.

OpenWorkflow에서는 이렇게 쓰는 게 가장 좋음
             Human / Developer
                    │
                    ▼
              LinkML Schema
                    │
             Semantic Compiler
                    │
      ┌─────────────┼─────────────┐
      ▼             ▼             ▼
   Pydantic       SHACL          OWL
      │             │             │
 Runtime types   Validation     Reasoning
                                  │
                              ELK/HermiT
                                  │
                                  ▼
                           OpenWorkflow

이 구조가 상당히 좋습니다.

예를 들면

LinkML:

classes:
  PurchaseRequest:
    slots:
      - vendor
      - amount

  HighRiskPurchase:
    is_a: PurchaseRequest

여기서 structural model은 LinkML이 담당하고,

OWL 쪽에서:

HighRiskPurchase
≡ PurchaseRequest
  ⊓ hasRiskScore some HighRiskScore

같은 더 강한 의미론을 추가합니다.

그러면:

LinkML = 기본 구조
OWL = 추론 가능한 의미

가 됩니다.

특히 LLM-as-Compiler와 궁합이 좋음

OpenWorkflow의 compiler가 agent trace를 보고 처음부터 OWL axiom만 만들어내게 하면 검증과 디버깅이 어렵습니다.

더 안전한 계층은:

Agent Trace
   ↓
LLM Compiler
   ↓
LinkML-level Domain Model
   ↓
Semantic Enrichment
   ↓
OWL axioms
   ↓
SHACL constraints
   ↓
Workflow

입니다.

즉 LLM이 먼저:

classes:
  CustomerRenewal:
    slots:
      - customer
      - current_contract
      - pricing_policy
      - proposal

같이 비교적 단순한 domain model을 만들고,

그다음:

current pricing policy must be used
external send requires approval

같은 behavior/invariant를 OWL/SHACL/policy로 승격시키는 겁니다.

이 방식이 훨씬 안정적입니다.

LinkML이 특히 좋은 이유 하나 더

우리 프로젝트는 OWL 전문가만 쓰는 시스템이 아니어야 합니다.

OpenWorkflow의 사용자층은 오히려:

Python 개발자
backend engineer
AI engineer
workflow designer
data engineer

일 가능성이 높습니다.

이들에게:

EquivalentClasses
ObjectSomeValuesFrom
SubClassOf
QualifiedCardinality

부터 요구하면 진입장벽이 큽니다.

LinkML을 앞단에 두면:

required: true
range: Vendor
multivalued: false

같은 친숙한 개념으로 시작할 수 있습니다.

그리고 필요한 부분만 OWL semantic extension을 붙이면 됩니다.

그래서 저는 계층을 이렇게 정합니다
계층	역할	추천
Authoring DSL	사람이 업무 모델 작성	LinkML
Semantic ontology	의미/관계/추론	OWL 2
Constraint validation	허용 가능한 데이터 검증	SHACL
Reasoner	inferred knowledge	ELK / HermiT
Runtime graph	RDF/SPARQL	Jena / RDF4J / RDFLib
Execution	workflow/action/state	OpenWorkflow

이 조합이 가장 균형이 좋습니다.

한 가지 주의점

LinkML → OWL 변환이 있다고 해서 모든 LinkML 제약이 OWL 의미론으로 완벽히 동일하게 변환되는 것은 아닙니다.

왜냐하면 LinkML은 schema/validation 중심이고 OWL은 open-world logical semantics이기 때문입니다.

예를 들어:

required = true
exactly one

같은 비즈니스 데이터 제약은 OWL보다 SHACL로 보내는 게 더 적합한 경우가 많습니다.

그래서 compiler가:

LinkML
 ↓
OWL: semantic meaning
SHACL: closed-world validation

로 나눠야 합니다.

이 구분이 중요합니다.

최종적으로

저라면 LinkML을 빼지 않습니다. 오히려 적극적으로 넣습니다.

다만 포지션은:

OpenWorkflow의 ontology가 LinkML이다

가 아니라

LinkML은 OpenWorkflow Semantic Model의 편리한 authoring language 중 하나다

입니다.

그리고 내부 canonical model은 별도의 Semantic IR로 두는 게 좋습니다.

LinkML
Protégé/OWL
JSON Schema
LLM-generated model
       ↓
   Semantic IR
       ↓
OWL / SHACL / Runtime Types / Workflow

이렇게 해두면 나중에 LinkML이 아니어도 모델 입력을 받을 수 있습니다.

즉 LinkML은 매우 유용하지만 core truth는 아니고, 가장 좋은 front door 중 하나라고 보는 게 맞습니다.

이제 우리가 구현하고 검증해야하는 최소 부분이 정리되었을것 같은데 

네. 이제는 꽤 명확합니다. 우리가 직접 구현·검증해야 할 최소 코어는 생각보다 작습니다.

핵심은 **“좋은 agent 수행 trace를 받아서, 반복 가능한 업무로 컴파일하고, 더 싼 executor로 치환하며, 품질을 계속 검증하는 루프”**입니다.

OpenWorkflow 최소 구현 범위
영역	우리가 직접 구현해야 하나	최소 검증 포인트
Trace IR	예	서로 다른 agent trace를 공통 형식으로 변환 가능한가
Work IR	예	업무를 state/action/invariant/quality로 표현 가능한가
Work Compiler	예, 핵심	trace → 반복 가능한 workflow로 추출 가능한가
Behavior Contract	예, 단 AgentBehavior 호환	결과뿐 아니라 과정 제약을 표현/평가 가능한가
Executor Abstraction	예	code/ML/SLM/LLM/human을 같은 action으로 취급 가능한가
Optimizer	예, 핵심	LLM step을 rule/code/SLM으로 안전하게 치환 가능한가
Quality Loop	예, 핵심	사람 1명이 결과 품질만 평가해도 개선 루프가 작동하는가
Durable Runtime	최소 구현 또는 Temporal 활용	retry/pause/resume/signal이 되는가
Semantic Model	최소	LinkML → Semantic IR 정도
OWL/SHACL	adapter 중심	필요한 invariant를 OWL/SHACL로 내릴 수 있는가
UI	직접 최소화	OpenWorker/OpenTag 활용
Slack/Teams	직접 X	OpenTag
Desktop/local execution	직접 X	OpenWorker
Agent behavior format	직접 X	AgentBehavior 호환
Full ontology editor	X	Protégé/LinkML
Fine-tuning infra	X	기존 training stack

즉 우리 IP는 사실 4개입니다.

Trace → Work IR → Compile → Optimize

그리고 그 뒤에 Quality feedback → Recompile이 붙습니다.

1. 첫 번째로 구현할 것: Trace IR

모든 시작점입니다.

OpenWorker든 LangGraph든 frontier agent든 상관없이 수행 기록을 이것으로 바꿉니다.

run:
  id: run_123

input:
  type: CustomerRenewalRequest
  data: ...

steps:

  - id: s1
    actor: agent
    action: crm.lookup
    input: ...
    output: ...
    duration_ms: 120

  - id: s2
    actor: agent
    action: pricing.lookup
    input: ...
    output: ...

  - id: s3
    actor: llm
    capability: draft_proposal
    input: ...
    output: ...

result:
  artifact: renewal.pdf

provenance:
  ...
첫 번째 검증

서로 다른 3개 source trace를 받아보면 됩니다.

OpenWorker trace
LangGraph/agent trace
직접 만든 simple agent trace
       ↓
동일 Trace IR

여기까지 되면 생태계 종속성이 크게 줄어듭니다.

2. 두 번째: Work IR

이게 OpenWorkflow의 가장 중요한 내부 자산입니다.

Trace는 무슨 일이 일어났는가이고,

Work IR은:

이 업무는 무엇인가

입니다.

최소 모델은 이 정도면 됩니다.

work: customer-renewal

inputs:
  - customer

outputs:
  - proposal

actions:
  - lookup_customer
  - lookup_contract
  - calculate_usage
  - lookup_pricing
  - draft_proposal
  - approve
  - send

dependencies:
  draft_proposal:
    requires:
      - lookup_contract
      - lookup_pricing

invariants:
  - current_contract_required
  - current_pricing_required
  - approval_before_external_send

quality:
  reviewer_acceptance: "&gt;= 0.95"

escalation:
  uncertain:
    - frontier_llm
    - human

처음부터 OWL을 canonical representation으로 만들 필요는 없습니다.

Semantic IR를 우리 canonical model로 두고, 여기서 필요하면:

Semantic IR
 ├→ LinkML
 ├→ OWL
 ├→ SHACL
 ├→ JSON Schema
 └→ Runtime types

로 컴파일하면 됩니다.

3. 세 번째: LLM-as-Compiler

여기가 진짜 차별화입니다.

좋은 trace 여러 개를 주면:

Trace 1
Trace 2
Trace 3
...
+
Human-approved results
+
Behavior Contracts

Compiler가:

반복되는 action
필수 dependency
항상 지켜야 하는 invariant
변동성이 큰 단계
결정형으로 바꿀 수 있는 단계

를 찾아야 합니다.

출력:

Compiled Work IR

예:

CRM lookup          → HTTP deterministic
Usage calculation   → Python
Pricing             → Rule
Draft               → LLM candidate
Approval            → Human interrupt
Send                → deterministic action
여기서 첫 번째 PoC 성공 기준

처음부터 완전 자동화를 목표로 하면 안 됩니다.

Compiler가 사람이 만든 정답 workflow의 80% 정도를 구조적으로 복원하는가를 보면 됩니다.

예를 들어 10개의 검증된 trace에서:

action 7/8개 발견
dependency 6/7개 발견
invariant 4/5개 발견

정도면 이미 의미 있습니다.

4. 네 번째: Behavior Contract

AgentBehavior를 적극 활용하면 됩니다.

우리 포맷을 새로 만들기보다는:

BEHAVIOR.md

를 읽어들여 내부 Behavior Contract로 변환합니다.

예:

Before sending a customer-facing proposal,
the current pricing policy must have been checked.

Compiler는 이를 분류합니다.

Behavior
   ↓
Classifier
   ├→ OWL semantic invariant
   ├→ SHACL constraint
   ├→ Workflow dependency
   ├→ Policy rule
   └→ Runtime behavior evaluator

이 분류기가 작은데도 매우 중요한 구성요소입니다.

5. 다섯 번째: Executor abstraction

이건 일부러 아주 작게 만들어야 합니다.

class Executor:
    async def execute(action, input, context) -&gt; ActionResult:
        ...

구현체:

CodeExecutor
RuleExecutor
HTTPExecutor
MLExecutor
SLMExecutor
LLMExecutor
HumanExecutor

Workflow 입장에서는 전부 동일합니다.

Action
 ↓
Executor
 ↓
Result

이렇게 해야 다음 핵심 기능인 치환이 가능합니다.

6. 여섯 번째: Executor Optimizer

여기가 OpenWorkflow의 두 번째 핵심 IP입니다.

예를 들어 현재:

draft_category
executor = frontier_llm

이고 trace가 5,000건 쌓였다고 합시다.

Optimizer가:

classification 문제인가?
결정형 rule로 충분한가?
기존 ML 모델로 가능한가?
SLM fine-tuning의 가치가 있는가?

를 판단합니다.

후보:

A: Frontier LLM
accuracy 98.5
cost 1.00

B: SLM
accuracy 98.2
cost 0.08

C: classifier
accuracy 96.3
cost 0.01

Quality policy:

min quality = 98.0

이면:

Frontier LLM → SLM

으로 promotion합니다.

이걸 자동화하는 것이 핵심입니다.

7. SLM Factory는 처음부터 만들 필요 없음

여기는 중요합니다.

우리가 직접:

GPU scheduler
training infrastructure
model registry
distributed fine-tuning

을 만들 필요가 없습니다.

우리 역할은:

TrainingCandidate

를 생성하는 데까지입니다.

예:

candidate:
  task: proposal_classification

training_set:
  trace_query: ...

teacher:
  frontier_model: ...

evaluation:
  output_quality: "&gt;= .98"
  behavior_compliance: "&gt;= .99"

deployment:
  shadow: true
  canary: 0.05

그 뒤 실제 training은 Hugging Face/TRL/외부 inference/training provider를 사용하면 됩니다.

OpenWorkflow는 Model Factory orchestrator이지 ML platform이 아닙니다.

8. Quality Loop

여기가 제품 UX상 가장 중요합니다.

사람이 봐야 할 건 이것뿐입니다.

┌──────────────────────────────┐
│ 고객 갱신안 #438            │
│                              │
│ [결과 보기]                  │
│                              │
│ 품질                         │
│ ★★★★★                        │
│                              │
│ □ 사실 오류                  │
│ □ 정책 위반                  │
│ □ 표현 문제                  │
│ □ 기타                       │
│                              │
│ [승인] [수정 필요]           │
└──────────────────────────────┘

뒤에서는 자동으로:

Output Quality
+
Behavior Compliance
+
Execution Trace
+
Cost
+
Latency

를 합칩니다.

즉 사람이 workflow graph를 평가하지 않습니다.

9. Quality Record를 first-class object로

이것도 꼭 필요합니다.

quality_record:

  work_run: run_381

  human:
    accepted: true
    score: 4.8

  automated:
    schema: pass
    business_rules: pass

  behaviors:
    verify_contract: true
    current_pricing: true
    approval_before_send: true

  execution:
    cost: 0.13
    latency_ms: 4210

이게 compiler/optimizer의 학습 신호입니다.

10. Runtime은 최소만

여기서 욕심내면 Temporal을 다시 만드는 프로젝트가 됩니다.

v1은:

start
state
action
retry
signal
pause
resume
complete
fail

이면 충분합니다.

특히:

WAITING_EVENT
WAITING_HUMAN
WAITING_TIMER

세 가지가 중요합니다.

나중에 production durability 요구가 커지면 Temporal adapter를 붙일 수 있습니다.

우리의 핵심은 durable runtime 자체가 아닙니다.

runtime 위에서 돌아가는 compiled work model입니다.

11. OWL은 최소 검증으로 시작

OWL도 크게 시작하지 않는 게 좋습니다.

첫 번째 목표는:

Behavior / invariant
      ↓
Semantic Compiler
      ↓
OWL / SHACL

이 가능한지만 봅니다.

예:

"외부 발송 전 승인이 필요하다."

에서:

ExternalWriteAction
⊑ requiresApproval some Approval

그리고 SHACL/policy:

external write
→ approval required

까지 자동 생성할 수 있는지 실험합니다.

처음부터 giant ontology는 필요 없습니다.

제가 권하는 첫 PoC는 딱 하나

Customer Renewal 같은 업무 하나를 고릅니다.

먼저 frontier agent가 50~100번 처리하게 합니다.

Email
↓
CRM
↓
Contract
↓
Usage
↓
Pricing
↓
Proposal
↓
Human review

사람 한 명이:

good / bad

및 간단한 품질 평가만 합니다.

그 데이터를 OpenWorkflow에 넣습니다.

그리고 OpenWorkflow가 자동으로
Trace normalization
        ↓
Work extraction
        ↓
Behavior extraction
        ↓
Workflow synthesis
        ↓
Executor selection
        ↓
Compiled workflow

을 수행합니다.

성공 여부를 측정하는 지표도 명확해야 합니다

예를 들어 초기 agent baseline:

Quality          97%
Frontier calls   100%
Human touches    100%
Cost             $1.00 / run

OpenWorkflow compile 후:

Quality          &gt;= 96.5%
Frontier calls   &lt; 20%
Human touches    &lt; 10%
Cost             &lt; $0.25 / run

이 나오면 엄청난 성공입니다.

그때부터:

Frontier 20%
↓
SLM candidate
↓
Frontier 8%

으로 내려갑니다.

그래서 MVP 아키텍처는 정말 이 정도
                  Existing Agent
                       │
                       ▼
                    Trace
                       │
                       ▼
                  Trace IR
                       │
                       ▼
               Human Quality
                       │
                 AgentBehavior
                       │
                       ▼
                Work Compiler
                       │
                       ▼
                    Work IR
             ┌─────────┼──────────┐
             ▼         ▼          ▼
           Rules      Workflow   Behavior
             │         │          │
             └─────────┼──────────┘
                       ▼
                Executor Router
             ┌─────┬────┬────┬─────┐
             ▼     ▼    ▼    ▼     ▼
           Code   ML   SLM   LLM  Human
             │
             ▼
                   Result
                     │
                Quality Record
                     │
                     ▼
                  Optimizer
                     │
                     └────→ Recompile
직접 만드는 코드는 결국 7개 모듈
trace/
work_ir/
compiler/
behavior/
runtime/
optimizer/
quality/

그리고 adapter:

adapters/
  openworker/
  opentag/
  agentbehavior/
  agui/
  mcp/
  linkml/
  owl/

입니다.

이 이상을 v1에서 직접 만들면 범위가 커질 가능성이 높습니다.

OpenWorkflow의 첫 번째 기술적 질문도 이제 명확합니다.

“검증된 agent trajectory 몇 개만으로, 품질을 유지하면서 얼마나 많은 실행을 deterministic/SLM workflow로 컴파일할 수 있는가?”

이걸 하나의 실제 업무에서 증명하면 OpenWorkflow의 존재 이유가 검증됩니다.

claude code plugin "llmcompiler" 검색 업무자동화에서 부분적 ml, slm을 포괄하는 파이프라인으로 업그레이드 한다면 , 기존에 sota llm agents로 했던것을 &lt;- 인터넷 검색해보자. 

검색해보니, 우리가 생각한 방향과 가까운 조각들은 이미 여러 곳에 있습니다. 다만 **“기존 SOTA LLM agent가 수행한 업무 trace를 받아서 → 반복 가능한 부분을 rule/code/ML/SLM으로 자동 컴파일하고 → 품질 검증 후 runtime에 승격”**까지 통합한 프로젝트는 제가 찾은 범위에서는 거의 없습니다.

먼저 이름부터 구분할 필요가 있습니다. LLMCompiler로 가장 유명한 것은 ICML 2024의 SqueezeAILab/LLMCompiler입니다. 이 프로젝트는 Claude Code plugin이 아니라, LLM이 tool-call DAG를 만들고 병렬 실행하여 latency/cost를 줄이는 agent architecture입니다. Planner → Task Fetching Unit → Executor 구조이고, 핵심은 동일한 LLM-agent 계획을 더 효율적으로 실행하는 것입니다.

우리가 말하는 OpenWorkflow의 compiler는 이보다 한 단계 더 아래로 내려갑니다.

기존 LLMCompiler

User task
  ↓
LLM Planner
  ↓
Tool DAG
  ↓
parallel execution


우리가 원하는 Work Compiler

SOTA Agent가 이미 성공한 업무
  ↓
Trace + Quality + Behavior
  ↓
업무 의미/구조 추출
  ↓
Rule / Code / ML / SLM / LLM 로 분해
  ↓
Compiled Workflow
  ↓
품질 유지 여부 검증
  ↓
Production

즉 LLMCompiler는 execution-plan compiler, 우리는 workload compiler에 가깝습니다.

그런데 Claude Code 생태계에서 아주 중요한 프로젝트를 찾았습니다

현재 가장 가까운 건 Frugal입니다.

Frugal은 Claude Code의 상위 모델을 router로 두고 각 하위 작업을 가장 싼 capable tier로 내려보냅니다.

구조가:

shell command
   ↓
Haiku
   ↓
Sonnet
   ↓
main model
   ↓
Fable

이고, grep/jq/git/test 같은 것으로 해결 가능하면 아예 모델을 호출하지 않습니다. 중요한 점은 cheap model이 스스로 “불확실하다”고 말해서 escalation하는 게 아니라 test/compiler/schema 같은 외부 검증기가 실패할 때만 상위 tier로 올린다는 것입니다.

이건 OpenWorkflow 철학과 거의 같습니다.

우리가 말했던:

Rule / Code
↓
ML
↓
SLM
↓
Frontier LLM
↓
Human

의 축소판입니다.

차이는 Frugal은 한 Claude Code session 안에서 즉석 routing하고,

OpenWorkflow는:

반복되는 업무 자체를 장기적으로 컴파일해서 다음부터는 더 싼 executor가 기본이 되게 한다.

는 점입니다.

또 하나: ModelRouter

Scylla23/modelrouter도 재미있습니다.

이 프로젝트는 작업마다 가장 싼 Claude 모델로 routing하고, 사용자가 /router:redo로 한 단계 올리면 그 correction을 기억하여 routing rule을 학습합니다. 통계로 down-route 비율, redo rate, learned routing rules까지 보여줍니다.

이것도 우리가 가져올 아이디어가 있습니다.

OpenWorkflow Optimizer

task type
  ↓
current executor
  ↓
quality result
  ↓
human correction
  ↓
routing memory
  ↓
future executor selection

하지만 우리는 모델 tier뿐 아니라:

LLM → SLM
LLM → ML
LLM → Rule
LLM → Code

까지 내려가야 합니다.

Agent Distillation은 더 직접적입니다

Nardien/agent-distillation은 large agent의 trajectory를 사용해 작은 1.5B 모델을 agent로 distill하는 실제 pipeline입니다.

프로세스가:

Teacher Agent trajectory 생성
↓
Student SLM training
↓
Benchmark evaluation

입니다. retrieval과 code tools까지 포함한 agent behavior를 작은 모델이 흉내 내도록 학습합니다.

이건 우리가 생각한 SLM Factory의 거의 직접적인 reference implementation입니다.

즉 OpenWorkflow에서:

Approved Trace Set
      ↓
Task cluster
      ↓
SLM candidate
      ↓
agent-distillation style training
      ↓
Evaluation
      ↓
Shadow
      ↓
Promotion

을 만들 수 있습니다.

우리가 training framework 자체를 만들 필요는 없습니다.

Claude Code plugin을 만든다면 오히려 굉장히 좋은 실험 환경입니다

저라면 OpenWorkflow 본체를 만들기 전에 Claude Code plugin 형태의 llmcompiler 또는 work-compiler prototype을 먼저 만듭니다.

왜냐하면 Claude Code에는 이미:

SOTA agent
tool calls
hooks
subagents
compiler/test oracle
session transcript
task delegation
MCP

가 있기 때문입니다.

즉 OpenWorkflow의 핵심 가설을 매우 싸게 검증할 수 있습니다.

Plugin의 역할

예를 들어 사용자가 Claude Code에서 평소처럼 일합니다.

사용자:
"지난달 고객 churn 분석하고,
위험 고객 분류해서 보고서를 만들어."

SOTA agent가 처음에는 그냥 수행합니다.

Claude
├─ DB 조회
├─ pandas 분석
├─ churn scoring
├─ 고객 분류
├─ 그래프 생성
└─ report 작성

결과를 사람이 확인합니다.

품질 OK

그 순간 plugin이 trace를 잡습니다.

Claude Code transcript
+
tool calls
+
files
+
tests
+
human acceptance
        ↓
Work Compiler

Compiler가 분석합니다.

DB 조회
→ SQL deterministic

데이터 정리
→ Python

churn score
→ sklearn/XGBoost candidate

segment classification
→ ML/SLM candidate

report narrative
→ SLM

complex anomaly explanation
→ frontier LLM fallback

그리고 다음 실행부터:

OpenWorkflow pipeline

으로 돌립니다.

이게 실제로 우리가 만들 plugin의 핵심 명령이 될 수 있습니다

예를 들어:

/work:observe

현재 작업을 관찰합니다.

/work:compile

검증된 trace에서 workflow를 생성합니다.

/work:benchmark

기존 frontier-agent baseline과 compiled version을 비교합니다.

/work:optimize

LLM step을 rule/code/ML/SLM 후보로 분석합니다.

/work:promote

품질 기준을 만족한 pipeline을 production workflow로 승격합니다.

중요한 점: ML을 별도의 1급 executor로 넣어야 합니다

지금까지 우리는 SLM을 많이 이야기했지만, 검색해본 결과 오히려 ML을 적극적으로 넣는 게 차별화에 더 중요해 보입니다.

예를 들어 기존 agent가 10,000번:

"이 티켓은 billing인가 technical인가?"

를 SOTA LLM으로 분류했다면,

굳이 SLM조차 필요하지 않을 수 있습니다.

Frontier LLM traces
       ↓
label dataset
       ↓
Logistic Regression
XGBoost
LightGBM
small transformer
       ↓
evaluation

으로 충분할 수도 있습니다.

그래서 compiler의 executor search space는:

constant / lookup
↓
SQL
↓
rule
↓
code
↓
traditional ML
↓
embedding / retrieval
↓
SLM
↓
frontier LLM
↓
human

이 되어야 합니다.

이게 Frugal보다 훨씬 넓습니다.

제가 생각하는 Compiler pipeline

이제 꽤 구체적으로 만들 수 있습니다.

                SOTA Agent Trace
                       │
                       ▼
                Trace Normalizer
                       │
                       ▼
                 Work Analyzer
                       │
       ┌───────────────┼────────────────┐
       ▼               ▼                ▼
 Determinism       Prediction       Generative
  Analyzer          Analyzer         Analyzer
       │               │                │
       ▼               ▼                ▼
 Rule / Code      ML Candidate     SLM Candidate
       │               │                │
       └───────────────┼────────────────┘
                       ▼
                Candidate Pipeline
                       │
                       ▼
                  Evaluation
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       Output       Behavior       Cost
       Quality      Compliance     Latency
          │            │            │
          └────────────┼────────────┘
                       ▼
                    Promote
                       │
                       ▼
                 OpenWorkflow
Determinism Analyzer가 특히 중요합니다

LLM trace 안에서:

"계산"
"format conversion"
"lookup"
"validation"
"exact matching"
"fixed transformation"

같은 걸 찾아야 합니다.

예:

Agent action:
"invoice total을 계산"

Compiler:

LLM 필요 없음
→ Python/SQL

또는:

"vendor가 approved 목록인지 확인"

→

lookup / rule

이런 식입니다.

가장 싼 모델을 고르는 게 아니라 모델을 없애는 것이 1순위여야 합니다.

Frugal의 “shell beats any model” 철학과 같습니다.

Prediction Analyzer

여기서 ML 여부를 판단합니다.

다음 특징이 있으면 ML 후보:

입력/출력이 구조화됨
label space가 유한함
대량의 반복 trace가 있음
결과가 statistical prediction임
semantic generation이 필요 없음

예:

fraud/not fraud
routing category
priority
lead score
churn probability
anomaly score

이 경우:

LLM
↓
training labels
↓
traditional ML

을 시도합니다.

SLM Analyzer

다음이면 SLM 후보입니다.

언어 이해/생성이 필요
task scope가 좁음
domain vocabulary가 안정적
많은 successful traces 존재
output schema가 명확

예:

메일 intent extraction
invoice field extraction
support summary
short proposal generation
ticket classification with nuance

여기서 agent-distillation 같은 pipeline을 활용할 수 있습니다.

그리고 최종적으로 Frontier LLM은 Residual입니다

이게 가장 중요한 관점입니다.

처음에는:

100% Frontier Agent

입니다.

Compiler가 내려가면서:

100%
 ↓
70% deterministic/code
 ↓
15% ML
 ↓
10% SLM
 ↓
4% frontier LLM
 ↓
1% human

같이 바뀝니다.

즉 우리가 최적화하려는 target은:

Frontier LLM usage를 0으로 만드는 것

이 아니라,

설명 가능한 품질 조건을 유지하면서 frontier LLM의 residual share를 최소화하는 것

입니다.

Claude Code plugin 형태가 왜 특히 좋은가

검색해보니 2026년 Claude Code 생태계에서도 이미 **“prompt를 믿지 말고 hook과 oracle로 강제하라”**는 패턴이 많이 나타납니다.

예를 들어 production-grade plugin은:

agent가 “완료했다”고 말해서 끝나는 게 아니라 test/type-check/compiler 같은 반박할 수 없는 oracle이 통과해야 완료

라는 loop를 둡니다.

Frugal도 escalation을 모델의 자기 확신이 아니라 외부 oracle 실패로 결정합니다.

이것은 OpenWorkflow quality loop에 그대로 가져와야 합니다.

Candidate executor
      ↓
Oracle
 ├ test
 ├ schema
 ├ behavior
 ├ reference output
 └ human sample
      ↓
PASS
그리고 기존 LLMCompiler 연구에서 가져올 부분도 있습니다

ICML LLMCompiler는 dependency를 발견해서 DAG로 만들고 executable task를 즉시 병렬 실행합니다. 연구에서는 ReAct 대비 최대 3.7× latency speedup, 최대 6.7× cost saving, 약 9% accuracy improvement를 보고했습니다.

우리는 이 DAG extraction logic을 Work Compiler의 한 단계로 사용할 수 있습니다.

즉:

Trace
↓
Task decomposition
↓
Dependency graph
↓
Parallelization
↓
Executor lowering

입니다.

Compiler 용어로 보면:

Frontend:
Agent trace → Work IR

Middle-end:
dependency analysis
common subtask elimination
parallelization
invariant extraction

Backend:
Rule
Code
ML
SLM
LLM
Human

정말 compiler architecture가 됩니다.

그래서 저는 이름도 이렇게 잡는 게 좋다고 봅니다

Claude Code plugin:

LLMCompiler for OpenWorkflow

보다는 조금 더 명확하게

WorkCompiler

가 좋습니다.

왜냐하면 우리가 하는 것은 LLM을 compile하는 게 아니라 LLM이 했던 work를 compile하는 것이기 때문입니다.

Claude Code
   +
WorkCompiler plugin
        ↓
Observe SOTA agent work
        ↓
Verify
        ↓
Compile
        ↓
OpenWorkflow

그리고 OpenWorkflow에서는:

WorkCompiler
= compiler frontend + optimizer

OpenWorkflow
= compiled workload runtime

로 분리합니다.

제 판단

이 검색을 하고 나니 OpenWorkflow의 핵심 가설이 더 강해졌습니다.

이미 각각은 증명되고 있습니다.

LLMCompiler → LLM task graph/DAG compilation이 가능하다.
Frugal → cheap executor first + objective escalation이 실제 Claude Code plugin으로 가능하다.
ModelRouter → routing 결과를 feedback으로 개선하는 게 가능하다.
Agent Distillation → large agent trajectory를 SLM으로 distill할 수 있다.
Claude Code plugins → compiler/test/schema를 hard oracle로 사용한 자동 quality loop가 가능하다.

아직 비어 있는 연결 고리가 바로 우리의 영역입니다.

SOTA Agent Trajectory → Quality-approved Work → Compiler → Rule/Code/ML/SLM/LLM mixed pipeline → Continuous evaluation → Recompile

이게 OpenWorkflow의 가장 독창적인 부분이 될 가능성이 높습니다.

그리고 이걸 검증하기 위한 가장 작은 실험은 Claude Code WorkCompiler plugin 하나를 만들어 실제 반복 업무 1개에서 Frontier-only baseline 대비 품질·비용·latency·human-touch를 비교하는 것입니다.