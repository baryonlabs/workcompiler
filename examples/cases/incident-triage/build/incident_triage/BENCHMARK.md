# Benchmark — `incident-triage`

Recorded agent session `01a04b4c-ca16-7543-a38f-4e6e4a913f9f` (`codex_exec`) vs. compiled build `build/incident_triage`.

| | recorded (agent) | compiled (build) | delta |
| :-- | --: | --: | --: |
| LLM tokens | 159,640 | 21,081 | −86.8% |
| wall time | 88.0 s | 5.29 s | 16.6× faster |
| outputs reproduced | — | 6/8 | |
| actions compiled / escalated | — | 5 / 1 | |

## Per action

| action | tier | executor used | tokens rec → comp | latency rec → comp | output match |
| :-- | :-- | :-- | --: | --: | :-- |
| `shell_sed` | code | code:incident_triage/handlers | 14,231 → 0 | 3.3 s → 0.01 s | 1/1 |
| `shell_python3` | code | code:incident_triage/handlers | 16,080 → 0 | 6.2 s → 0.03 s | 0/1 |
| `shell_jq` | code | code:incident_triage/handlers | 33,886 → 0 | 15.2 s → 0.04 s | 2/2 |
| `shell_cat` | code | code:incident_triage/handlers | 55,255 → 0 | 40.0 s → 0.07 s | 2/3 |
| `write_triage_alr_2026_0828_17` | code | code:incident_triage/handlers | 19,107 → 0 | 18.0 s → 0.00 s | 1/1 |
| `respond` | frontier_llm | escalated:frontier_llm | 21,081 → 21,081 | 5.1 s → 5.15 s | n/a |

## Token ledger — who spent what

Every recorded step, the model that produced it, and what runs it in the compiled build.

| step | action | recorded model | prompt (cached) + completion = total | compiled executor | compiled tokens |
| :-- | :-- | :-- | --: | :-- | --: |
| step_1 | `shell_sed` | gpt-5.6-sol | 14,128 (0) + 103 = 14,231 | code | 0 |
| step_2 | `shell_python3` | gpt-5.6-sol | 15,851 (13,056) + 229 = 16,080 | code | 0 |
| step_3 | `shell_jq` | gpt-5.6-sol | 16,363 (15,104) + 120 = 16,483 | code | 0 |
| step_5 | `shell_jq` | gpt-5.6-sol | 16,967 (7,936) + 436 = 17,403 | code | 0 |
| step_4 | `shell_cat` | gpt-5.6-sol | 16,544 (16,128) + 144 = 16,688 | code | 0 |
| step_6 | `shell_cat` | gpt-5.6-sol | 17,693 (16,128) + 371 = 18,064 | code | 0 |
| step_8 | `shell_cat` | gpt-5.6-sol | 19,131 (18,176) + 1,372 = 20,503 | code | 0 |
| step_7 | `write_triage_alr_2026_0828_17` | gpt-5.6-sol | 18,440 (17,152) + 667 = 19,107 | code | 0 |
| step_9 | `respond` | gpt-5.6-sol | 20,919 (18,176) + 162 = 21,081 | gpt-5.6-sol | 21,081 |

| model / executor | recorded tokens | compiled tokens |
| :-- | --: | --: |
| gpt-5.6-sol | 159,640 | 21,081 |
| code | 0 | 0 |

Recorded prompt tokens served from the provider cache: 121,856 (counted in the totals above; billed at the cached rate).
Totals are the sum of every request's usage as reported by the provider — each agent turn re-sends its whole context, which is why they exceed the agent CLI's own 'tokens used' figure.

## Outputs

### `shell_sed` · step_1 — code:incident_triage/handlers

recorded:

```
# Task: security and operations incident triage for alert ALR-2026-0828-17

You are the on-call triage assistant. Within 15 minutes of receiving the work, prepare an evidence-grounded triage note and machine-readable classification for alert **ALR-2026-0828-17** (per-run parameter: `alert_id`) for the on-call engineer. The reference date supplied for this run is **2026-08-29** (per-run parameter: `reference_date`), but calculate the change window from the alert timestamp.

Rules (from `behaviors/`): select exactly one alert by exact ID and use current source files rather than the previous deli
… (5305 more chars)
```

compiled:

```
# Task: security and operations incident triage for alert ALR-2026-0828-17

You are the on-call triage assistant. Within 15 minutes of receiving the work, prepare an evidence-grounded triage note and machine-readable classification for alert **ALR-2026-0828-17** (per-run parameter: `alert_id`) for the on-call engineer. The reference date supplied for this run is **2026-08-29** (per-run parameter: `reference_date`), but calculate the change window from the alert timestamp.

Rules (from `behaviors/`): select exactly one alert by exact ID and use current source files rather than the previous deli
… (5305 more chars)
```

### `shell_python3` · step_2 — code:incident_triage/handlers

recorded:

```
2026-08-29T02:15:30.652252+00:00
- 지금 처리할 것: ALR-2026-0828-17
- 파일명: triage-<알람ID>.md, triage-<알람ID>.json
- 오늘 2026-08-29 (알람은 어제 밤)
# 온콜 리드 메모

알람 오면 15분 안에 분류(triage) 노트 남겨야 함. 순서:
1. alerts json에서 해당 알람 찾아서 필드 정리 (host, user, rule, severity, 시간)
2. signatures.yaml에 알려진 시그니처면 매칭된 런북(runbooks 폴더) 링크 + 런북 첫 3단계 적기
3. 최근 변경 이력(change-log)에서 같은 host의 24시간 내 변경 있으면 "변경 연관 가능" 표시
4. 권한 상승(privilege escalation) 징후거나 시그니처 미매칭이면 즉시 온콜 엔지니어 호출로 분류 — 우리가 조치 결정 안 함
5. 노트는 previous 폴더 양식 + 분류 결과 json

```

compiled:

```
2026-08-29T02:18:02.657741+00:00
- 지금 처리할 것: ALR-2026-0828-17
- 파일명: triage-<알람ID>.md, triage-<알람ID>.json
- 오늘 2026-08-29 (알람은 어제 밤)
# 온콜 리드 메모

알람 오면 15분 안에 분류(triage) 노트 남겨야 함. 순서:
1. alerts json에서 해당 알람 찾아서 필드 정리 (host, user, rule, severity, 시간)
2. signatures.yaml에 알려진 시그니처면 매칭된 런북(runbooks 폴더) 링크 + 런북 첫 3단계 적기
3. 최근 변경 이력(change-log)에서 같은 host의 24시간 내 변경 있으면 "변경 연관 가능" 표시
4. 권한 상승(privilege escalation) 징후거나 시그니처 미매칭이면 즉시 온콜 엔지니어 호출로 분류 — 우리가 조치 결정 안 함
5. 노트는 previous 폴더 양식 + 분류 결과 json

```

### `shell_jq` · step_3 — code:incident_triage/handlers (exit_code=5)

recorded:

```
jq: error (at examples/cases/incident-triage/materials/data/alerts-2026-08-28.json:5): Cannot index array with string "alert_id"

```

compiled:

```
jq: error (at examples/cases/incident-triage/materials/data/alerts-2026-08-28.json:5): Cannot index array with string "alert_id"

```

### `shell_jq` · step_5 — code:incident_triage/handlers

recorded:

```
{
  "match_count": 1,
  "selected": [
    {
      "alert_id": "ALR-2026-0828-17",
      "time": "2026-08-28T23:41:00Z",
      "host": "db-01",
      "user": "app-reader",
      "rule": "sudo-from-service-account",
      "severity": "high",
      "detail": "sudo -i executed by app-reader on db-01; new user 'backup2' created"
    }
  ]
}
signatures:
  - rule: ssh-bruteforce
    class: known
    runbook: runbooks/RB-ssh-bruteforce.md
    default_action: block-source-ip
  - rule: disk-usage-high
    class: known
    runbook: runbooks/RB-disk-usage.md
    default_action: cleanup-logs
  - rule: sudo
… (252 more chars)
```

compiled:

```
{
  "match_count": 1,
  "selected": [
    {
      "alert_id": "ALR-2026-0828-17",
      "time": "2026-08-28T23:41:00Z",
      "host": "db-01",
      "user": "app-reader",
      "rule": "sudo-from-service-account",
      "severity": "high",
      "detail": "sudo -i executed by app-reader on db-01; new user 'backup2' created"
    }
  ]
}
signatures:
  - rule: ssh-bruteforce
    class: known
    runbook: runbooks/RB-ssh-bruteforce.md
    default_action: block-source-ip
  - rule: disk-usage-high
    class: known
    runbook: runbooks/RB-disk-usage.md
    default_action: cleanup-logs
  - rule: sudo
… (252 more chars)
```

### `shell_cat` · step_4 — code:incident_triage/handlers

recorded:

```
{"alerts": [
  {"alert_id": "ALR-2026-0828-15", "time": "2026-08-28T21:05:00Z", "host": "web-03", "user": "svc-deploy", "rule": "ssh-bruteforce", "severity": "medium", "detail": "37 failed ssh logins in 5m from 203.0.113.9"},
  {"alert_id": "ALR-2026-0828-17", "time": "2026-08-28T23:41:00Z", "host": "db-01", "user": "app-reader", "rule": "sudo-from-service-account", "severity": "high", "detail": "sudo -i executed by app-reader on db-01; new user 'backup2' created"},
  {"alert_id": "ALR-2026-0828-18", "time": "2026-08-29T00:10:00Z", "host": "web-03", "user": "-", "rule": "disk-usage-high", "sev
… (45 more chars)
```

compiled:

```
{"alerts": [
  {"alert_id": "ALR-2026-0828-15", "time": "2026-08-28T21:05:00Z", "host": "web-03", "user": "svc-deploy", "rule": "ssh-bruteforce", "severity": "medium", "detail": "37 failed ssh logins in 5m from 203.0.113.9"},
  {"alert_id": "ALR-2026-0828-17", "time": "2026-08-28T23:41:00Z", "host": "db-01", "user": "app-reader", "rule": "sudo-from-service-account", "severity": "high", "detail": "sudo -i executed by app-reader on db-01; new user 'backup2' created"},
  {"alert_id": "ALR-2026-0828-18", "time": "2026-08-29T00:10:00Z", "host": "web-03", "user": "-", "rule": "disk-usage-high", "sev
… (45 more chars)
```

### `shell_cat` · step_6 — code:incident_triage/handlers

recorded:

```
change_id,host,changed_at,author,summary
CHG-5101,web-03,2026-08-28T18:30:00Z,svc-deploy,deploy web v2.14.0
CHG-5102,db-01,2026-08-28T22:55:00Z,dba-kim,rotate replication credentials
CHG-5103,cache-02,2026-08-27T09:00:00Z,ops-lee,upgrade redis 7.2
interval_utc: [2026-08-27T23:41:00Z, 2026-08-28T23:41:00Z]
selected_count: 1
{'change_id': 'CHG-5102', 'host': 'db-01', 'changed_at': '2026-08-28T22:55:00Z', 'author': 'dba-kim', 'summary': 'rotate replication credentials'}
change_correlation_possible: True
# Triage Note — ALR-2026-0810-04

- Time: 2026-08-10T14:02Z · Host: web-02 · User: - · Rule: d
… (336 more chars)
```

compiled:

```
change_id,host,changed_at,author,summary
CHG-5101,web-03,2026-08-28T18:30:00Z,svc-deploy,deploy web v2.14.0
CHG-5102,db-01,2026-08-28T22:55:00Z,dba-kim,rotate replication credentials
CHG-5103,cache-02,2026-08-27T09:00:00Z,ops-lee,upgrade redis 7.2
interval_utc: [2026-08-27T23:41:00Z, 2026-08-28T23:41:00Z]
selected_count: 1
{'change_id': 'CHG-5102', 'host': 'db-01', 'changed_at': '2026-08-28T22:55:00Z', 'author': 'dba-kim', 'summary': 'rotate replication credentials'}
change_correlation_possible: True
# Triage Note — ALR-2026-0810-04

- Time: 2026-08-10T14:02Z · Host: web-02 · User: - · Rule: d
… (336 more chars)
```

### `shell_cat` · step_8 — code:incident_triage/handlers

recorded:

```
# Triage Note — ALR-2026-0828-17

- Time: 2026-08-28T23:41:00Z · Host: db-01 · User: app-reader · Rule: sudo-from-service-account · Severity: high
- Signature: matched; class `privilege_escalation`; mapped runbook: none
- Related change within 24h: change correlation possible; this does not establish causation.
  - CHG-5102 · 2026-08-28T22:55:00Z · dba-kim · rotate replication credentials

## Classification

Privilege escalation.

Page on-call immediately.

The on-call engineer decides the response.
{
  "alert_id": "ALR-2026-0828-17",
  "time": "2026-08-28T23:41:00Z",
  "host": "db-01",
  "use
… (687 more chars)
```

compiled:

```
# Triage Note — ALR-2026-0828-17

- Time: 2026-08-28T23:41:00Z · Host: db-01 · User: app-reader · Rule: sudo-from-service-account · Severity: high
- Signature: matched; class `privilege_escalation`; mapped runbook: none
- Related change within 24h: change correlation possible; this does not establish causation.
  - CHG-5102 · 2026-08-28T22:55:00Z · dba-kim · rotate replication credentials

## Classification

Privilege escalation.

Page on-call immediately.

The on-call engineer decides the response.
{
  "alert_id": "ALR-2026-0828-17",
  "time": "2026-08-28T23:41:00Z",
  "host": "db-01",
  "use
… (688 more chars)
```

### `write_triage_alr_2026_0828_17` · step_7 — code:incident_triage/handlers (2 file(s) verified on disk)

recorded:

```
(files written by the agent's apply_patch)
```

compiled:

```
A /Users/hongmartin/orca/projects/open-workflow/build/incident-triage/triage-ALR-2026-0828-17.md
A /Users/hongmartin/orca/projects/open-workflow/build/incident-triage/triage-ALR-2026-0828-17.json

```

### `respond` · step_9 — escalated:frontier_llm (kept recorded cost (frontier/human tier))

recorded:

```
Alert `ALR-2026-0828-17` classified as privilege escalation.

- Immediate on-call page required; decision owner: on-call engineer
- Eligible runbook included: No
- Related same-host change found: Yes; correlation only, no causation asserted
- Validation: Passed
- SLA: Passed in 73.8 seconds
- Outputs: [Markdown note](/Users/hongmartin/orca/projects/open-workflow/build/incident-triage/triage-ALR-2026-0828-17.md) and [classification JSON](/Users/hongmartin/orca/projects/open-workflow/build/incident-triage/triage-ALR-2026-0828-17.json)

No remediation was performed.
```

compiled:

```
Alert `ALR-2026-0828-17` classified as privilege escalation.

- Immediate on-call page required; decision owner: on-call engineer
- Eligible runbook included: No
- Related same-host change found: Yes; correlation only, no causation asserted
- Validation: Passed
- SLA: Passed in 73.8 seconds
- Outputs: [Markdown note](/Users/hongmartin/orca/projects/open-workflow/build/incident-triage/triage-ALR-2026-0828-17.md) and [classification JSON](/Users/hongmartin/orca/projects/open-workflow/build/incident-triage/triage-ALR-2026-0828-17.json)

No remediation was performed.
```

## Final answer of the recorded agent

```
Alert `ALR-2026-0828-17` classified as privilege escalation.

- Immediate on-call page required; decision owner: on-call engineer
- Eligible runbook included: No
- Related same-host change found: Yes; correlation only, no causation asserted
- Validation: Passed
- SLA: Passed in 73.8 seconds
- Outputs: [Markdown note](/Users/hongmartin/orca/projects/open-workflow/build/incident-triage/triage-ALR-2026-0828-17.md) and [classification JSON](/Users/hongmartin/orca/projects/open-workflow/build/incident-triage/triage-ALR-2026-0828-17.json)

No remediation was performed.
```
