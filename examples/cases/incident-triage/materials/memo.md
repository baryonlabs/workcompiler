# 온콜 리드 메모

알람 오면 15분 안에 분류(triage) 노트 남겨야 함. 순서:
1. alerts json에서 해당 알람 찾아서 필드 정리 (host, user, rule, severity, 시간)
2. signatures.yaml에 알려진 시그니처면 매칭된 런북(runbooks 폴더) 링크 + 런북 첫 3단계 적기
3. 최근 변경 이력(change-log)에서 같은 host의 24시간 내 변경 있으면 "변경 연관 가능" 표시
4. 권한 상승(privilege escalation) 징후거나 시그니처 미매칭이면 즉시 온콜 엔지니어 호출로 분류 — 우리가 조치 결정 안 함
5. 노트는 previous 폴더 양식 + 분류 결과 json
