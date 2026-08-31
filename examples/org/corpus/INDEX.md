# 조직 결정 코퍼스 — 카탈로그 요약

34개 결정 사례 × 100 인스턴스 = 3,400건의 라벨된 판단 (규칙 스펙에서 결정론적으로 생성).

| 사례 | 조직 | 담당자 | 결정 | 규칙 수 | AI 추천 밴드 | 판정 분포 | 승인 라우팅 |
| :-- | :-- | :-- | :-- | --: | :-- | :-- | :-- |
| `sales-discount-approval` | 영업 | 영업대표 | 고객 할인율 승인·라우팅 | 5 | 예 | approve 21, defer 7, escalate 32, reject 40 | auto 55, 본부장 38, 팀장 7 |
| `sales-quote-expedite` | 영업 | 영업운영 | 특가 견적 처리 우선순위 | 4 | 예 | classified 38, defer 62 | auto 38, 팀장 62 |
| `sales-renewal-priority` | 영업 | 계정관리자 | 갱신 대상 우선순위 분류 | 4 | — | classified 100 | auto 100 |
| `finance-expense-approval` | 재무 | 재무담당자 | 경비 승인 | 6 | — | approve 14, escalate 78, hold 8 | auto 2, 부서장 15, 재무팀장 63, 제출자 8, 팀장 12 |
| `finance-payment-extension` | 재무 | 채권담당자 | 지급기한 연장 승인 | 4 | 예 | approve 1, defer 10, escalate 56, reject 33 | CFO 49, auto 34, 재무팀장 17 |
| `finance-budget-overrun` | 재무 | 예산관리자 | 예산 초과 결재 라우팅 | 4 | — | approve 16, escalate 84 | CFO 77, 본부장 21, 팀장 2 |
| `cs-refund-decision` | 고객지원 | CS상담원 | 환불 승인 (examples/cases/refund-approval 의 정책 요약판) | 5 | — | approve 43, hold 6, reject 51 | auto 94, 고객 6 |
| `cs-goodwill-coupon` | 고객지원 | CS상담원 | 보상 쿠폰 지급 | 4 | 예 | approve 19, defer 29, escalate 41, reject 11 | CS팀장 41, auto 30, 팀장 29 |
| `cs-ticket-tiering` | 고객지원 | CS운영 | 문의 에스컬레이션 티어 분류 | 4 | — | classified 100 | CS팀장 8, auto 89, 법무 3 |
| `hr-leave-approval` | 인사 | 팀장 | 휴가 승인 | 5 | — | approve 37, escalate 18, hold 38, reject 7 | auto 19, 부서장 18, 팀장 63 |
| `hr-overtime-approval` | 인사 | 인사담당자 | 초과근무 승인 | 4 | — | approve 18, escalate 51, reject 31 | auto 38, 인사팀장 51, 팀장 11 |
| `hr-resume-screening` | 인사 | 채용담당자 | 서류 전형 라우팅 | 5 | 예 | classified 45, defer 37, escalate 18 | auto 45, human 2, 채용담당자 37, 채용위원회 16 |
| `proc-po-approval` | 구매 | 구매담당자 | 발주 승인 라우팅 | 5 | — | approve 3, escalate 81, hold 16 | CFO 62, 구매위원회 6, 구매팀 16, 구매팀장 3, 재무 13 |
| `proc-vendor-onboarding` | 구매 | 공급망관리자 | 공급사 등록 심사 | 4 | — | approve 7, escalate 37, reject 56 | auto 56, 구매위원회 6, 구매팀장 7, 법무 31 |
| `proc-price-increase` | 구매 | 카테고리매니저 | 공급 단가 인상 수용 | 4 | 예 | approve 13, defer 39, reject 48 | auto 58, 구매팀장 42 |
| `legal-contract-routing` | 법무 | 법무담당자 | 계약 검토 라우팅 | 4 | — | approve 1, escalate 99 | auto 1, 법무담당자 3, 법무총괄 11, 사내변호사 85 |
| `legal-nda-fastpass` | 법무 | 법무운영 | NDA 자동 승인 | 3 | — | approve 39, escalate 61 | auto 39, 법무담당자 61 |
| `legal-privacy-incident` | 법무 | 개인정보보호책임 | 개인정보 이슈 등급 분류 | 3 | — | classified 100 | DPO 31, auto 69 |
| `it-incident-priority` | IT운영 | 온콜엔지니어 | 장애 우선순위 분류 (examples/cases/incident-triage 의 정책 요약판) | 5 | — | classified 100 | auto 88, 보안팀 12 |
| `it-access-request` | IT운영 | 보안운영 | 시스템 접근권한 승인 | 4 | — | approve 22, escalate 49, hold 29 | CISO 15, auto 22, 보안팀장 34, 요청자 29 |
| `it-change-approval` | IT운영 | 변경관리자 | 배포(변경) 승인 | 5 | — | approve 65, escalate 2, hold 29, reject 4 | CAB 2, auto 67, 변경관리자 2, 요청자 29 |
| `mkt-lead-scoring` | 마케팅 | 마케팅운영 | 리드 등급 분류·이관 | 4 | — | classified 100 | auto 82, 영업 18 |
| `mkt-campaign-topup` | 마케팅 | 퍼포먼스마케터 | 캠페인 예산 증액 승인 | 4 | 예 | approve 16, defer 23, escalate 57, reject 4 | auto 20, 마케팅본부장 57, 팀장 23 |
| `mkt-influencer-vetting` | 마케팅 | 브랜드매니저 | 인플루언서 계약 심사 | 4 | — | approve 3, escalate 50, reject 47 | auto 47, 마케팅본부장 43, 팀장 10 |
| `log-delay-compensation` | 물류 | 물류CS | 배송지연 보상 판정 | 4 | 예 | approve 69, defer 10, escalate 11, reject 10 | auto 31, 물류팀장 59, 팀장 10 |
| `log-reorder-point` | 물류 | 재고관리자 | 재주문 발주 트리거 | 4 | — | approve 18, hold 82 | auto 40, 재고관리자 60 |
| `log-return-disposition` | 물류 | 반품검수자 | 반품 입고 판정 | 4 | — | classified 65, escalate 35 | CS팀장 35, auto 33, 반품검수자 20, 품질팀 12 |
| `sec-phishing-response` | 보안 | 보안분석가 | 피싱 신고 대응 등급 | 4 | — | classified 100 | auto 72, 보안팀장 28 |
| `sec-sharing-exception` | 보안 | 보안운영 | 외부 공유 예외 승인 | 4 | — | approve 8, escalate 67, reject 25 | CISO 16, auto 33, 보안팀장 51 |
| `ga-travel-approval` | 경영지원 | 총무담당자 | 출장 승인 | 4 | — | approve 10, escalate 90 | 본부장 21, 팀장 79 |
| `ga-asset-disposal` | 경영지원 | 자산관리자 | 자산 폐기·매각 판정 | 4 | — | classified 4, escalate 59, hold 37 | auto 1, 보안팀 37, 자산관리자 3, 재무 59 |
| `ga-donation-request` | 경영지원 | 대외협력 | 기부·후원 요청 심사 | 4 | — | escalate 68, reject 32 | auto 32, 감사 9, 경영위원회 43, 대외협력팀장 16 |
| `pq-feature-flag-rollout` | 제품 | 프로덕트매니저 | 기능 점진 배포 승인 | 3 | 예 | approve 3, defer 14, hold 3, reject 80 | PM 17, auto 83 |
| `pq-defect-batch-hold` | 품질 | 품질관리자 | 생산 배치 출하 보류 판정 | 4 | — | approve 10, escalate 4, hold 86 | auto 10, 품질위원회 12, 품질팀장 78 |
