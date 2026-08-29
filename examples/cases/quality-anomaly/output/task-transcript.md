OpenAI Codex v0.150.1
--------
workdir: /Users/hongmartin/orca/projects/open-workflow
model: gpt-5.6-sol
provider: openworkflow
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR] (network access enabled)
reasoning effort: none
reasoning summaries: none
session id: 01a04b4a-85ef-7891-a7f3-7673fec23942
--------
user
Read examples/cases/quality-anomaly/TASK.md and carry it out exactly as written.
codex
I’ll read the case instructions first, then inspect only the inputs they direct me to and execute the task accordingly.
exec
/bin/zsh -lc "sed -n '1,240p' examples/cases/quality-anomaly/TASK.md" in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 0ms:
# Task: Line 3 quality anomaly response report for 2026-08-27 night shift

You are the manufacturing quality-analysis assistant. Prepare the auditable anomaly evidence summary and response report for **incident_date=2026-08-27**, **line=3**, **shift=night** for review by the Quality Engineer.

Rules (from `behaviors/`): use the supplied thresholds as the sole numeric rule authority; independently verify the bound MES anomaly before analysis; align sensor evidence only to the bound line and supplied overnight incident window; evaluate calibration by measure at measurement time and never use an overdue sensor to support causation; make only evidence-bounded candidate-cause claims; and leave every remediation pending with the exact statement **“requires Quality Engineer approval”**. Use `examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md` only as a format example, never as evidence. Assumptions adopted while the requester was unavailable are recorded in `examples/cases/quality-anomaly/ASSUMPTIONS.md`.

Do the work with auditable shell commands (`cat`, `mkdir -p`, and `python3` using CSV/YAML/date/JSON handling) from the repository root. Do not modify anything under `examples/cases/quality-anomaly/materials/`.

1. **Bind the run and inspect authority files** — set and print the per-run bindings **incident_date=2026-08-27**, **line=3**, **shift=night**, **MES=examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv**, **SENSORS=examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv**, **CALIBRATION=examples/cases/quality-anomaly/materials/data/calibration-log.csv**, **THRESHOLDS=examples/cases/quality-anomaly/materials/data/thresholds.yaml**, and **OUTPUT_DIR=build/quality-anomaly**. Read `examples/cases/quality-anomaly/materials/memo.md`, `examples/cases/quality-anomaly/materials/notes.txt`, the four data files, and `examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md`. Create `build/quality-anomaly/` with `mkdir -p`.
2. **Verify the MES anomaly mechanically** — with `python3`, parse `examples/cases/quality-anomaly/materials/data/thresholds.yaml` and `examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv`; filter by all three bound keys (`date`, integer `line`, and `shift`); require exactly one row; recompute `100 * defects / units` and verify it agrees with `defect_rate_pct` within 0.05 percentage point; classify an anomaly only when the recorded rate is strictly greater than `defect_rate_pct_threshold`. Print the selected row, recomputed rate, threshold, and verdict. Stop without finalizing either deliverable if the row is missing/ambiguous, internally inconsistent, or not anomalous.
3. **Extract time-aligned sensor exceedances mechanically** — with `python3`, parse `examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv`; keep only integer `line == 3` and the supplied continuous overnight rows from **2026-08-27T20:00 through 2026-08-28T03:00 inclusive**. Do not infer a broader corporate shift schedule. For `temp_c` and `vibration_mm_s`, compare each value strictly (`>`) with its configured maximum, record every exceedance timestamp/value, group consecutive hourly exceedances into inclusive intervals, and record each peak and peak timestamp. Print the filtered window and derived exceedances.
4. **Gate evidence by calibration mechanically** — with `python3`, parse `examples/cases/quality-anomaly/materials/data/calibration-log.csv` and join each measure to the unique calibration row whose `measure` matches (`temp_c` or `vibration_mm_s`), regardless of the row-level `sensor_id` in the sensor CSV. At every relevant measurement timestamp, compute whole elapsed days since `last_calibrated`; classify the measure `trusted` when age is at most `calibration_interval_days` and `untrusted` when older. Record the calibration sensor ID, date, ages, status, and `eligible_for_causal_use`. An untrusted measure's observed exceedances must remain disclosed but must not enter causal support. Stop for human review if a measure has zero/multiple calibration records, a future calibration date, or inconsistent trust status across its relevant interval.
5. **Write the structured evidence first** — create `build/quality-anomaly/anomaly-2026-08-27.json` containing: `incident` (`date`, `line`, `shift`, `observed_sensor_window`); `sources` (all input paths); `thresholds`; `mes` (selected row, recomputed rate, and `is_anomaly`); `sensor_evidence` keyed by measure (unit, maximum, exceedance samples, contiguous intervals, peak, calibration record/ages/status, and `eligible_for_causal_use`); `candidate_root_cause` (`status`, `statement`, `supporting_trusted_measures`, and `limitations`); `remediation` as a list of items each with `action`, `approval_required: true`, `approval_authority: "Quality Engineer"`, and `approval_status: "pending"`; and `validation`. The cause must be `undetermined` if no trustworthy evidence supports a bounded candidate. Do not assert a specific failed component without supplied evidence.
6. **Render the response report from the JSON** — write `build/quality-anomaly/anomaly-report-2026-08-27.md` in the concise English format of `examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md`, using exactly these sections: title, `## Anomaly`, `## Sensor evidence`, `## Root cause (candidate)`, and `## Remediation (requires Quality Engineer approval)`. Include the selected production facts and threshold; each measure's exceedance interval/peak and calibration trust basis; explicit `untrusted` wording and exclusion from causal judgment where applicable; a correlation-bounded candidate or `undetermined`; and `Approval: pending`. Every remediation item must include the exact statement **“requires Quality Engineer approval”** and must not claim execution or approval.
7. **Validate both artifacts mechanically** — parse the JSON with `python3 -m json.tool`; use `python3` to recompute the selected MES result, exceedance samples/intervals/peaks, calibration ages/statuses, and causal eligibility directly from the four data files; compare them with JSON; then verify that every material numeric fact, trust label, candidate-cause limitation, remediation action, approval authority/status, and source incident in Markdown agrees with JSON. Confirm that no untrusted measure appears in `supporting_trusted_measures`, no unrelated shift appears, and both filenames match **2026-08-27**. Set `validation.status` to `passed` only after all checks pass and re-run `python3 -m json.tool` after the update.
8. **Do not perform remediation** — this task produces analysis artifacts only. Do not contact people, change manufacturing systems, issue work orders, recalibrate sensors, or state that any approval or action occurred.

Reply with a short summary containing the verified incident and defect-rate verdict, which measures were trusted/untrusted, the candidate-cause status, the pending Quality Engineer approval status, and these two paths:

- `build/quality-anomaly/anomaly-2026-08-27.json`
- `build/quality-anomaly/anomaly-report-2026-08-27.md`

codex
The task’s gate is clear: I’ll bind and print the exact run inputs, inspect every required authority/source file, then mechanically verify the anomaly before creating either deliverable.
exec
/bin/zsh -lc "python3 - <<'PY'
bindings = {
    'incident_date': '2026-08-27',
    'line': 3,
    'shift': 'night',
    'MES': 'examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv',
    'SENSORS': 'examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv',
    'CALIBRATION': 'examples/cases/quality-anomaly/materials/data/calibration-log.csv',
    'THRESHOLDS': 'examples/cases/quality-anomaly/materials/data/thresholds.yaml',
    'OUTPUT_DIR': 'build/quality-anomaly',
}
for key, value in bindings.items():
    print(f'{key}={value}')
PY
mkdir -p build/quality-anomaly
cat examples/cases/quality-anomaly/materials/memo.md
cat examples/cases/quality-anomaly/materials/notes.txt
cat examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv
cat examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv
cat examples/cases/quality-anomaly/materials/data/calibration-log.csv
cat examples/cases/quality-anomaly/materials/data/thresholds.yaml
cat examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md
cat examples/cases/quality-anomaly/ASSUMPTIONS.md" in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 0ms:
incident_date=2026-08-27
line=3
shift=night
MES=examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv
SENSORS=examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv
CALIBRATION=examples/cases/quality-anomaly/materials/data/calibration-log.csv
THRESHOLDS=examples/cases/quality-anomaly/materials/data/thresholds.yaml
OUTPUT_DIR=build/quality-anomaly
# 품질팀장 메모

3라인 불량률 튈 때마다 보고서 써왔는데, 순서는 이래:
1. MES 불량률(mes-defects csv)에서 임계치(thresholds.yaml) 넘은 교대(shift) 찾기
2. 그 시간대 센서 csv(temp, vibration)에서 임계치 넘는 구간 찾기
3. 센서 보정 로그(calibration-log) 확인 — 보정 기한 지난 센서면 그 센서 값은 "신뢰 불가"로 표시하고 원인 판정에서 빼기 (이거 안 하고 보고했다가 크게 혼남)
4. 원인 후보 정리 + 개선안. 개선안은 반드시 "품질 엔지니어 승인 필요"로 표기, 우리가 실행 지시 못 함
5. 보고서는 previous 폴더 형식. 원자료 요약 json도 같이.
- 이번 건: 2026-08-27 3라인 야간 교대 불량률 급증
- 파일명: anomaly-report-<날짜>.md, anomaly-<날짜>.json
date,line,shift,units,defects,defect_rate_pct
2026-08-25,3,day,4200,63,1.5
2026-08-25,3,night,4100,70,1.7
2026-08-26,3,day,4250,68,1.6
2026-08-26,3,night,4050,77,1.9
2026-08-27,3,day,4300,73,1.7
2026-08-27,3,night,3900,215,5.5
timestamp,line,sensor_id,temp_c,vibration_mm_s
2026-08-27T20:00,3,S3-TEMP-1,71.2,3.1
2026-08-27T21:00,3,S3-TEMP-1,72.0,3.2
2026-08-27T22:00,3,S3-TEMP-1,79.4,3.3
2026-08-27T23:00,3,S3-TEMP-1,81.9,3.4
2026-08-28T00:00,3,S3-TEMP-1,82.5,5.1
2026-08-28T01:00,3,S3-TEMP-1,80.7,5.4
2026-08-28T02:00,3,S3-TEMP-1,76.3,4.9
2026-08-28T03:00,3,S3-TEMP-1,73.0,3.6
sensor_id,measure,last_calibrated,technician
S3-TEMP-1,temp_c,2026-07-30,K. Han
S3-VIB-1,vibration_mm_s,2026-04-12,J. Cho
line: 3
defect_rate_pct_threshold: 2.5      # shift defect rate above this = anomaly
sensors:
  temp_c: {max: 78.0}
  vibration_mm_s: {max: 4.5}
calibration_interval_days: 90        # sensor calibration older than this = untrusted
# Line 3 Quality Anomaly Report — 2026-06-14 (day shift)

## Anomaly
Defect rate 3.1% (threshold 2.5%), 4,180 units, 130 defects.

## Sensor evidence
Temperature exceeded 78 °C from 10:00 to 13:00 (peak 80.2 °C). Vibration within limits. Sensor S3-TEMP-1 calibrated 2026-05-02 (within 90 days) → trusted.

## Root cause (candidate)
Coolant flow restriction on station 3B raised die temperature.

## Remediation (requires Quality Engineer approval)
Flush coolant lines, re-run 200-unit trial. Approval: pending.
# Assumptions: manufacturing line quality anomaly response reports

The requester was unavailable for an interactive interview. Each grilling round below therefore records the frontier questions, the recommended answer adopted from the supplied materials, and why it was chosen. These are reviewable assumptions, not new source facts; the requester can correct them before the first run.

## Round 1 — Outcome and scope

1. **What is the single-sentence goal, and who consumes the result?**
   - **Chosen answer:** Produce an auditable Line 3 quality-anomaly response report and structured evidence summary for the Quality Engineer, so they can review a detected shift-level defect spike, its trustworthy sensor evidence, candidate cause, and proposed remediation.
   - **Why:** `materials/memo.md` describes the recurring report, requires Quality Engineer approval for improvements, and says both a report and raw-data summary JSON are required. The prior report is written for operational quality review.

2. **Which incident is in scope for this run?**
   - **Chosen answer:** **2026-08-27**, **Line 3**, **night shift** only.
   - **Why:** `materials/notes.txt` names exactly this incident. No other line or shift was requested.

3. **Should the task scan for all anomalies or merely assume the noted incident is anomalous?**
   - **Chosen answer:** Bind the run to the noted line/date/shift, but independently verify that it exceeds the authoritative defect-rate threshold; do not report unrelated shifts.
   - **Why:** The memo's first required step is to find shifts exceeding the threshold, while the notes identify “this case.” This preserves verification without broadening the deliverable.

4. **What language and presentation style should the deliverable use?**
   - **Chosen answer:** Use English and follow the headings and concise operational style of `materials/previous/anomaly-report-2026-06-14.md`.
   - **Why:** The memo is Korean, but the repository and prior finished deliverable are English. The project instructions require English artifacts.

## Round 2 — Inputs, authority, and boundaries

5. **Which files are authoritative for facts and rules?**
   - **Chosen answer:** Use `materials/data/thresholds.yaml` for thresholds and calibration interval, `materials/data/mes-defects-2026-08.csv` for shift production/defect facts, `materials/data/sensor-2026-08-27.csv` for measurements, and `materials/data/calibration-log.csv` for calibration status. Use `materials/memo.md` and `materials/notes.txt` for process/scope, and the prior report only for format.
   - **Why:** These roles are stated directly in the memo and reflected by the file contents. The previous report is an example, not evidence for this incident.

6. **Which values should be treated as per-run parameters?**
   - **Chosen answer:** `incident_date=2026-08-27`, `line=3`, `shift=night`, the four input paths, and `output_dir=build/quality-anomaly/` are explicit run bindings. A future run may replace them.
   - **Why:** The notes bind the first three values, while the requested task paths bind the inputs and output location. Making them explicit supports later parameter discovery.

7. **What time window defines the night shift?**
   - **Chosen answer:** Use all sensor rows supplied for the bound incident and line, spanning `2026-08-27T20:00` through `2026-08-28T03:00` inclusive; record this observed window in JSON rather than inventing a corporate shift schedule.
   - **Why:** The sensor file contains exactly that continuous overnight window and the MES record labels the incident “night.” No formal shift timetable was supplied.

8. **How is the strict threshold boundary interpreted?**
   - **Chosen answer:** A value is anomalous only when it is strictly greater than the configured maximum (`>`), not equal to it.
   - **Why:** `thresholds.yaml` says “above this = anomaly,” and the memo says “넘은” (exceeded).

9. **At what date is calibration age evaluated, and how is expiry handled?**
   - **Chosen answer:** Evaluate each measure's calibration age at the timestamp of each relevant measurement; it is trusted when age is at most 90 whole days and untrusted when older than 90 days. Record the dates and computed ages.
   - **Why:** The memo says an overdue sensor must be marked untrustworthy and excluded from causal judgment. Incident-time evaluation avoids using the later workflow execution date. The “older than” wording makes day 90 inclusive/trusted.

10. **How should calibration records map to a sensor CSV that has one `sensor_id` but both temperature and vibration columns?**
    - **Chosen answer:** Map calibration status by the `measure` field: `temp_c` to the calibration row for `temp_c`, and `vibration_mm_s` to the row for `vibration_mm_s`. Preserve both calibration sensor IDs in JSON. Do not apply `S3-TEMP-1` calibration to vibration merely because it appears in the sensor row.
    - **Why:** `calibration-log.csv` has distinct sensor IDs per measure, while every sensor-data row is labeled `S3-TEMP-1` despite carrying both values. Measure-based mapping is the only interpretation consistent with the calibration log and the memo's per-sensor trust rule.

## Round 3 — Analysis and judgment

11. **What is the ordered process, and which parts are mechanical versus judgment?**
    - **Chosen answer:** Mechanically load bindings and thresholds; select and verify the MES row; filter the observed sensor window; find strict exceedances and contiguous intervals; join calibration by measure and compute trust; serialize JSON; then use judgment only to phrase a bounded candidate cause and approval-gated remediation from trustworthy evidence; render Markdown from JSON and validate consistency.
    - **Why:** This follows the memo's five-step order and makes calculations reproducible while isolating the genuinely interpretive steps.

12. **May an overdue sensor's exceedance appear in the report?**
    - **Chosen answer:** Yes, disclose its observed values and exceedance interval, label it exactly **“untrusted”**, state why, and exclude it from causal support.
    - **Why:** The memo requires overdue sensor values to be marked “신뢰 불가” (untrusted) and removed from causal determination—not silently discarded.

13. **How strong may the root-cause claim be?**
    - **Chosen answer:** Label it a **candidate**, tie it only to trusted evidence, distinguish correlation from confirmation, and do not name a specific failed component unless the supplied evidence identifies one.
    - **Why:** The memo asks for cause candidates, and the prior report labels the section “Root cause (candidate).” The current files contain measurements, not inspection evidence proving a component failure.

14. **What remediation may be proposed?**
    - **Chosen answer:** Recommend investigation/containment steps proportionate to the trusted evidence (for example, inspect the thermal process and run a controlled verification trial), plus recalibration/verification of any overdue sensor; every action must say **“requires Quality Engineer approval”** and remain pending.
    - **Why:** The memo forbids execution instructions without Quality Engineer approval. The evidence supports investigation, not autonomous maintenance action.

15. **What happens if the MES row does not exceed the threshold, inputs are missing/ambiguous, or no trustworthy causal evidence remains?**
    - **Chosen answer:** Stop normal report finalization and surface the condition for human review. If the anomaly is verified but causal evidence is insufficient, the report may still be produced, but the cause must be `undetermined` and remediation limited to approval-gated investigation/data recovery.
    - **Why:** Inventing a cause or silently selecting ambiguous evidence would violate the memo's trust rule. A verified quality event still needs a response report even when causation is unresolved.

## Round 4 — Deliverables, completeness, and failure checks

16. **What exact files must be produced?**
    - **Chosen answer:** `build/quality-anomaly/anomaly-2026-08-27.json` first, then `build/quality-anomaly/anomaly-report-2026-08-27.md` rendered from it. No source materials are modified.
    - **Why:** `materials/notes.txt` specifies both filename patterns, and the requester requires outputs under `build/quality-anomaly/`.

17. **What must the JSON contain?**
    - **Chosen answer:** Run bindings and source paths; threshold values; selected MES row and anomaly verdict; sensor window; per-measure exceedance timestamps/intervals/peaks; calibration ID/date/age/status; whether each measure is eligible for causal use; candidate-cause statement with supporting trusted measures and limitations; approval-gated remediation items; and validation status.
    - **Why:** This is the minimum structured evidence needed to audit every memo-required decision and keep the Markdown traceable to raw data.

18. **What must the Markdown contain?**
    - **Chosen answer:** The prior report's sections—title, `Anomaly`, `Sensor evidence`, `Root cause (candidate)`, and `Remediation (requires Quality Engineer approval)`—with source-grounded values, explicit trust labels, causal limitations, and approval status `pending`.
    - **Why:** The memo explicitly requires the previous-folder format, and the previous deliverable supplies these headings and approval wording.

19. **What exact acceptance checks define done?**
    - **Chosen answer:** Both files exist and parse; filenames match the bound incident date; all reported numeric facts reproduce from the selected rows and configured thresholds; strict boundaries and contiguous intervals are correct; calibration is evaluated by measure at incident time; untrusted measures never support the cause; remediation explicitly requires Quality Engineer approval and remains pending; Markdown and JSON agree; only the requested incident is reported.
    - **Why:** These checks cover the requested output, all memo rules, and the main data trap.

20. **Which known or feared failure modes require explicit prevention?**
    - **Chosen answer:** Using the prior report as incident evidence; trusting vibration under the temperature sensor ID; evaluating calibration at execution time; hiding or causally using overdue sensor values; treating equality as exceedance; inventing shift boundaries, component failures, or approvals; issuing remediation as an order; mismatching JSON/Markdown; and processing unrelated shifts.
    - **Why:** The memo identifies missed calibration as a serious prior failure. The remaining risks follow directly from the supplied schemas, example, and requested dual outputs.

## Deferred confirmations

Before generalizing this workflow beyond the supplied fixture, the requester should confirm the official shift schedule, whether calibration validity is day- or timestamp-granular, the canonical JSON schema, and the organization-approved remediation vocabulary. None of these unknowns prevents a bounded first run under the assumptions above.

exec
/bin/zsh -lc "python3 - <<'PY'
import csv, yaml
from decimal import Decimal
thresholds_path='examples/cases/quality-anomaly/materials/data/thresholds.yaml'
mes_path='examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv'
with open(thresholds_path) as f: thresholds=yaml.safe_load(f)
with open(mes_path, newline='') as f: rows=list(csv.DictReader(f))
selected=[r for r in rows if r['date']=='2026-08-27' and int(r['line'])==3 and r['shift']=='night']
if len(selected)"'!=1: raise SystemExit(f'"'STOP: expected exactly one MES row, found {len(selected)}')
r=selected[0]
recomputed=Decimal(100)*Decimal(r['defects'])/Decimal(r['units'])
recorded=Decimal(r['defect_rate_pct'])
threshold=Decimal(str(thresholds['defect_rate_pct_threshold']))
consistent=abs(recomputed-recorded)<=Decimal('0.05')
anomaly=recorded>threshold
print('selected_row=',r)
print('recomputed_rate_pct=',float(recomputed))
print('threshold_pct=',float(threshold))
print('rate_consistent_within_0.05_pp=',consistent)
print('verdict=', 'ANOMALY' if anomaly else 'NOT_ANOMALY')
if not consistent or not anomaly: raise SystemExit('STOP: MES verification gate failed')
PY
python3 - <<'PY'
import csv, yaml
from datetime import datetime
from collections import defaultdict
sensor_path='examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv'
thresholds_path='examples/cases/quality-anomaly/materials/data/thresholds.yaml'
with open(thresholds_path) as f: t=yaml.safe_load(f)
with open(sensor_path,newline='') as f: rows=list(csv.DictReader(f))
start=datetime.fromisoformat('2026-08-27T20:00'); end=datetime.fromisoformat('2026-08-28T03:00')
window=[r for r in rows if int(r['line'])==3 and start<=datetime.fromisoformat(r['timestamp'])<=end]
print('filtered_window=')
for r in window: print(r)
for measure in ('temp_c','vibration_mm_s'):
    maximum=float(t['sensors'][measure]['max'])
    ex=[(r['timestamp'],float(r[measure])) for r in window if float(r[measure])>maximum]
    intervals=[]
    for ts,val in ex:
        dt=datetime.fromisoformat(ts)
        if not intervals or (dt-intervals[-1]['end']).total_seconds()"'!=3600:
            intervals.append({'"'start':dt,'end':dt})
        else: intervals[-1]['end']=dt
    peak=max(ex,key=lambda x:x[1]) if ex else None
    print(measure,'maximum=',maximum,'exceedances=',ex)
    print(measure,'intervals=',[(x['start'].isoformat(timespec='minutes'),x['end'].isoformat(timespec='minutes')) for x in intervals])
    print(measure,'peak=',peak)
PY
python3 - <<'PY'
import csv
from datetime import datetime
sensor_path='examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv'
cal_path='examples/cases/quality-anomaly/materials/data/calibration-log.csv'
with open(sensor_path,newline='') as f: rows=list(csv.DictReader(f))
with open(cal_path,newline='') as f: cals=list(csv.DictReader(f))
start=datetime.fromisoformat('2026-08-27T20:00'); end=datetime.fromisoformat('2026-08-28T03:00')
window=[r for r in rows if int(r['line'])==3 and start<=datetime.fromisoformat(r['timestamp'])<=end]
for measure in ('temp_c','vibration_mm_s'):
    matches=[c for c in cals if c['measure']==measure]
    if len(matches)"'!=1: raise SystemExit(f'"'STOP: {measure} calibration count {len(matches)}')
    c=matches[0]; calibrated=datetime.fromisoformat(c['last_calibrated'])
    ages=[]
    for r in window:
        measured=datetime.fromisoformat(r['timestamp'])
        if calibrated>measured: raise SystemExit(f'STOP: future calibration for {measure}')
        ages.append((r['timestamp'],(measured-calibrated).days))
    statuses=['trusted' if age<=90 else 'untrusted' for _,age in ages]
    if len(set(statuses))"'!=1: raise SystemExit(f'"'STOP: inconsistent trust for {measure}')
    print(measure,'calibration_sensor_id=',c['sensor_id'],'last_calibrated=',c['last_calibrated'],'ages=',ages,'status=',statuses[0],'eligible_for_causal_use=',statuses[0]=='trusted')
PY" in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 0ms:
selected_row= {'date': '2026-08-27', 'line': '3', 'shift': 'night', 'units': '3900', 'defects': '215', 'defect_rate_pct': '5.5'}
recomputed_rate_pct= 5.512820512820513
threshold_pct= 2.5
rate_consistent_within_0.05_pp= True
verdict= ANOMALY
filtered_window=
{'timestamp': '2026-08-27T20:00', 'line': '3', 'sensor_id': 'S3-TEMP-1', 'temp_c': '71.2', 'vibration_mm_s': '3.1'}
{'timestamp': '2026-08-27T21:00', 'line': '3', 'sensor_id': 'S3-TEMP-1', 'temp_c': '72.0', 'vibration_mm_s': '3.2'}
{'timestamp': '2026-08-27T22:00', 'line': '3', 'sensor_id': 'S3-TEMP-1', 'temp_c': '79.4', 'vibration_mm_s': '3.3'}
{'timestamp': '2026-08-27T23:00', 'line': '3', 'sensor_id': 'S3-TEMP-1', 'temp_c': '81.9', 'vibration_mm_s': '3.4'}
{'timestamp': '2026-08-28T00:00', 'line': '3', 'sensor_id': 'S3-TEMP-1', 'temp_c': '82.5', 'vibration_mm_s': '5.1'}
{'timestamp': '2026-08-28T01:00', 'line': '3', 'sensor_id': 'S3-TEMP-1', 'temp_c': '80.7', 'vibration_mm_s': '5.4'}
{'timestamp': '2026-08-28T02:00', 'line': '3', 'sensor_id': 'S3-TEMP-1', 'temp_c': '76.3', 'vibration_mm_s': '4.9'}
{'timestamp': '2026-08-28T03:00', 'line': '3', 'sensor_id': 'S3-TEMP-1', 'temp_c': '73.0', 'vibration_mm_s': '3.6'}
temp_c maximum= 78.0 exceedances= [('2026-08-27T22:00', 79.4), ('2026-08-27T23:00', 81.9), ('2026-08-28T00:00', 82.5), ('2026-08-28T01:00', 80.7)]
temp_c intervals= [('2026-08-27T22:00', '2026-08-28T01:00')]
temp_c peak= ('2026-08-28T00:00', 82.5)
vibration_mm_s maximum= 4.5 exceedances= [('2026-08-28T00:00', 5.1), ('2026-08-28T01:00', 5.4), ('2026-08-28T02:00', 4.9)]
vibration_mm_s intervals= [('2026-08-28T00:00', '2026-08-28T02:00')]
vibration_mm_s peak= ('2026-08-28T01:00', 5.4)
temp_c calibration_sensor_id= S3-TEMP-1 last_calibrated= 2026-07-30 ages= [('2026-08-27T20:00', 28), ('2026-08-27T21:00', 28), ('2026-08-27T22:00', 28), ('2026-08-27T23:00', 28), ('2026-08-28T00:00', 29), ('2026-08-28T01:00', 29), ('2026-08-28T02:00', 29), ('2026-08-28T03:00', 29)] status= trusted eligible_for_causal_use= True
vibration_mm_s calibration_sensor_id= S3-VIB-1 last_calibrated= 2026-04-12 ages= [('2026-08-27T20:00', 137), ('2026-08-27T21:00', 137), ('2026-08-27T22:00', 137), ('2026-08-27T23:00', 137), ('2026-08-28T00:00', 138), ('2026-08-28T01:00', 138), ('2026-08-28T02:00', 138), ('2026-08-28T03:00', 138)] status= untrusted eligible_for_causal_use= False

codex
The MES gate passed: the bound row is unique, internally consistent (5.5128% recomputed vs. 5.5% recorded), and strictly exceeds 2.5%. Temperature is trusted at 28–29 days; vibration is untrusted at 137–138 days and will be disclosed but excluded from causal support. I’m now writing JSON first and rendering Markdown only from that JSON.
exec
/bin/zsh -lc "python3 - <<'PY'
import csv, json, yaml
from datetime import datetime
from decimal import Decimal
from pathlib import Path
base=Path('examples/cases/quality-anomaly')
paths={
 'memo':str(base/'materials/memo.md'),
 'notes':str(base/'materials/notes.txt'),
 'mes':str(base/'materials/data/mes-defects-2026-08.csv'),
 'sensors':str(base/'materials/data/sensor-2026-08-27.csv'),
 'calibration':str(base/'materials/data/calibration-log.csv'),
 'thresholds':str(base/'materials/data/thresholds.yaml'),
 'format_example':str(base/'materials/previous/anomaly-report-2026-06-14.md'),
 'assumptions':str(base/'ASSUMPTIONS.md'),
}
with open(paths['thresholds']) as f: thresholds=yaml.safe_load(f)
with open(paths['mes'],newline='') as f: mes_rows=list(csv.DictReader(f))
selected=[r for r in mes_rows if r['date']=='2026-08-27' and int(r['line'])==3 and r['shift']=='night']
if len(selected)"'!=1: raise SystemExit('"'MES selection gate failed')
r=selected[0]; recomputed=Decimal(100)*Decimal(r['defects'])/Decimal(r['units'])
if abs(recomputed-Decimal(r['defect_rate_pct']))>Decimal('0.05') or not Decimal(r['defect_rate_pct'])>Decimal(str(thresholds['defect_rate_pct_threshold'])): raise SystemExit('MES anomaly gate failed')
with open(paths['sensors'],newline='') as f: sensor_rows=list(csv.DictReader(f))
with open(paths['calibration'],newline='') as f: cal_rows=list(csv.DictReader(f))
start=datetime.fromisoformat('2026-08-27T20:00'); end=datetime.fromisoformat('2026-08-28T03:00')
window=[x for x in sensor_rows if int(x['line'])==3 and start<=datetime.fromisoformat(x['timestamp'])<=end]
evidence={}
for measure,unit in [('temp_c','°C'),('vibration_mm_s','mm/s')]:
    maximum=float(thresholds['sensors'][measure]['max'])
    samples=[{'timestamp':x['timestamp'],'value':float(x[measure])} for x in window if float(x[measure])>maximum]
    intervals=[]
    for sample in samples:
        dt=datetime.fromisoformat(sample['timestamp'])
        if not intervals or (dt-datetime.fromisoformat(intervals[-1]['end'])).total_seconds()"'!=3600:
            intervals.append({'"'start':sample['timestamp'],'end':sample['timestamp']})
        else: intervals[-1]['end']=sample['timestamp']
    peak=max(samples,key=lambda x:x['value']) if samples else None
    matches=[c for c in cal_rows if c['measure']==measure]
    if len(matches)"'!=1: raise SystemExit(f'"'Calibration cardinality gate failed for {measure}')
    c=matches[0]; cal_dt=datetime.fromisoformat(c['last_calibrated'])
    ages=[]
    for x in window:
        dt=datetime.fromisoformat(x['timestamp'])
        if cal_dt>dt: raise SystemExit(f'Future calibration gate failed for {measure}')
        ages.append({'timestamp':x['timestamp'],'age_days':(dt-cal_dt).days})
    statuses=['trusted' if a['age_days']<=int(thresholds['calibration_interval_days']) else 'untrusted' for a in ages]
    if len(set(statuses))"'!=1: raise SystemExit(f'"'Inconsistent calibration trust gate failed for {measure}')
    status=statuses[0]
    evidence[measure]={
      'unit':unit,'maximum':maximum,'exceedance_samples':samples,'contiguous_intervals':intervals,'peak':peak,
      'calibration':{'sensor_id':c['sensor_id'],'measure':c['measure'],'last_calibrated':c['last_calibrated'],'technician':c['technician'],'interval_days':int(thresholds['calibration_interval_days']),'measurement_ages':ages,'age_days_min':min(a['age_days'] for a in ages),'age_days_max':max(a['age_days'] for a in ages),'status':status},
      'eligible_for_causal_use':status=='trusted'
    }
data={
 'incident':{'date':'2026-08-27','line':3,'shift':'night','observed_sensor_window':{'start':'2026-08-27T20:00','end':'2026-08-28T03:00','inclusive':True}},
 'sources':paths,
 'thresholds':{'defect_rate_pct_threshold':float(thresholds['defect_rate_pct_threshold']),'sensors':{'temp_c':{'max':float(thresholds['sensors']['temp_c']['max'])},'vibration_mm_s':{'max':float(thresholds['sensors']['vibration_mm_s']['max'])}},'calibration_interval_days':int(thresholds['calibration_interval_days'])},
 'mes':{'selected_row':{'date':r['date'],'line':int(r['line']),'shift':r['shift'],'units':int(r['units']),'defects':int(r['defects']),'defect_rate_pct':float(r['defect_rate_pct'])},'recomputed_rate_pct':float(recomputed),'rate_tolerance_percentage_points':0.05,'rate_is_consistent':True,'is_anomaly':True},
 'sensor_evidence':evidence,
 'candidate_root_cause':{
   'status':'candidate',
   'statement':'Elevated process temperature is a candidate contributor correlated with the Line 3 night-shift defect anomaly.',
   'supporting_trusted_measures':['temp_c'],
   'limitations':['Correlation does not establish causation.','The supplied evidence does not identify or confirm a specific failed component.','Vibration exceedances are untrusted because calibration was overdue and are excluded from causal judgment.']
 },
 'remediation':[
   {'action':'Inspect the Line 3 thermal process and temperature-control conditions.','approval_required':True,'approval_authority':'Quality Engineer','approval_status':'pending'},
   {'action':'Run a controlled verification trial after approved thermal-process inspection.','approval_required':True,'approval_authority':'Quality Engineer','approval_status':'pending'},
   {'action':'Recalibrate or independently verify the vibration measurement channel before causal use.','approval_required':True,'approval_authority':'Quality Engineer','approval_status':'pending'}
 ],
 'validation':{'status':'pending','checks':[]}
}
out=Path('build/quality-anomaly/anomaly-2026-08-27.json')
out.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\\n')
print(out)
PY
python3 - <<'PY'
import json
from pathlib import Path
p=Path('build/quality-anomaly/anomaly-2026-08-27.json')
d=json.loads(p.read_text())
i=d['incident']; m=d['mes']; t=d['thresholds']; se=d['sensor_evidence']; cause=d['candidate_root_cause']
def interval_text(x):
    return f\"{x['start']} through {x['end']} inclusive\"
def ages_text(c):
    return str(c['age_days_min']) if c['age_days_min']==c['age_days_max'] else f\"{c['age_days_min']}–{c['age_days_max']}\"
temp=se['temp_c']; vib=se['vibration_mm_s']
lines=[
 f\"# Line {i['line']} Quality Anomaly Report — {i['date']} ({i['shift']} shift)\",'',
 '## Anomaly',
 f\"Defect rate {m['selected_row']['defect_rate_pct']}% (threshold {t['defect_rate_pct_threshold']}%), {m['selected_row']['units']:,} units, {m['selected_row']['defects']} defects; recomputed rate {m['recomputed_rate_pct']:.4f}%. Verified anomaly: yes.\",'',
 '## Sensor evidence',
 f\"Temperature exceeded {temp['maximum']} {temp['unit']} from {interval_text(temp['contiguous_intervals'][0])} (peak {temp['peak']['value']} {temp['unit']} at {temp['peak']['timestamp']}). Calibration sensor {temp['calibration']['sensor_id']} was calibrated {temp['calibration']['last_calibrated']}; measurement age {ages_text(temp['calibration'])} whole days within the {temp['calibration']['interval_days']}-day interval → trusted and eligible for causal use.\",
 f\"Vibration exceeded {vib['maximum']} {vib['unit']} from {interval_text(vib['contiguous_intervals'][0])} (peak {vib['peak']['value']} {vib['unit']} at {vib['peak']['timestamp']}). Calibration sensor {vib['calibration']['sensor_id']} was calibrated {vib['calibration']['last_calibrated']}; measurement age {ages_text(vib['calibration'])} whole days exceeds the {vib['calibration']['interval_days']}-day interval → untrusted and excluded from causal judgment.\",'',
 '## Root cause (candidate)',
 f\"Status: {cause['status']}. {cause['statement']} Supporting trusted measure: {', '.join(cause['supporting_trusted_measures'])}. Limitations: {' '.join(cause['limitations'])}\",'',
 '## Remediation (requires Quality Engineer approval)'
]
for item in d['remediation']:
    lines.append(f\"- {item['action']} requires Quality Engineer approval. Approval: {item['approval_status']}.\")
Path('build/quality-anomaly/anomaly-report-2026-08-27.md').write_text('\\n'.join(lines)+'\\n')
print('build/quality-anomaly/anomaly-report-2026-08-27.md')
PY
python3 -m json.tool build/quality-anomaly/anomaly-2026-08-27.json" in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 0ms:
build/quality-anomaly/anomaly-2026-08-27.json
build/quality-anomaly/anomaly-report-2026-08-27.md
{
    "incident": {
        "date": "2026-08-27",
        "line": 3,
        "shift": "night",
        "observed_sensor_window": {
            "start": "2026-08-27T20:00",
            "end": "2026-08-28T03:00",
            "inclusive": true
        }
    },
    "sources": {
        "memo": "examples/cases/quality-anomaly/materials/memo.md",
        "notes": "examples/cases/quality-anomaly/materials/notes.txt",
        "mes": "examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv",
        "sensors": "examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv",
        "calibration": "examples/cases/quality-anomaly/materials/data/calibration-log.csv",
        "thresholds": "examples/cases/quality-anomaly/materials/data/thresholds.yaml",
        "format_example": "examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md",
        "assumptions": "examples/cases/quality-anomaly/ASSUMPTIONS.md"
    },
    "thresholds": {
        "defect_rate_pct_threshold": 2.5,
        "sensors": {
            "temp_c": {
                "max": 78.0
            },
            "vibration_mm_s": {
                "max": 4.5
            }
        },
        "calibration_interval_days": 90
    },
    "mes": {
        "selected_row": {
            "date": "2026-08-27",
            "line": 3,
            "shift": "night",
            "units": 3900,
            "defects": 215,
            "defect_rate_pct": 5.5
        },
        "recomputed_rate_pct": 5.512820512820513,
        "rate_tolerance_percentage_points": 0.05,
        "rate_is_consistent": true,
        "is_anomaly": true
    },
    "sensor_evidence": {
        "temp_c": {
            "unit": "\u00b0C",
            "maximum": 78.0,
            "exceedance_samples": [
                {
                    "timestamp": "2026-08-27T22:00",
                    "value": 79.4
                },
                {
                    "timestamp": "2026-08-27T23:00",
                    "value": 81.9
                },
                {
                    "timestamp": "2026-08-28T00:00",
                    "value": 82.5
                },
                {
                    "timestamp": "2026-08-28T01:00",
                    "value": 80.7
                }
            ],
            "contiguous_intervals": [
                {
                    "start": "2026-08-27T22:00",
                    "end": "2026-08-28T01:00"
                }
            ],
            "peak": {
                "timestamp": "2026-08-28T00:00",
                "value": 82.5
            },
            "calibration": {
                "sensor_id": "S3-TEMP-1",
                "measure": "temp_c",
                "last_calibrated": "2026-07-30",
                "technician": "K. Han",
                "interval_days": 90,
                "measurement_ages": [
                    {
                        "timestamp": "2026-08-27T20:00",
                        "age_days": 28
                    },
                    {
                        "timestamp": "2026-08-27T21:00",
                        "age_days": 28
                    },
                    {
                        "timestamp": "2026-08-27T22:00",
                        "age_days": 28
                    },
                    {
                        "timestamp": "2026-08-27T23:00",
                        "age_days": 28
                    },
                    {
                        "timestamp": "2026-08-28T00:00",
                        "age_days": 29
                    },
                    {
                        "timestamp": "2026-08-28T01:00",
                        "age_days": 29
                    },
                    {
                        "timestamp": "2026-08-28T02:00",
                        "age_days": 29
                    },
                    {
                        "timestamp": "2026-08-28T03:00",
                        "age_days": 29
                    }
                ],
                "age_days_min": 28,
                "age_days_max": 29,
                "status": "trusted"
            },
            "eligible_for_causal_use": true
        },
        "vibration_mm_s": {
            "unit": "mm/s",
            "maximum": 4.5,
            "exceedance_samples": [
                {
                    "timestamp": "2026-08-28T00:00",
                    "value": 5.1
                },
                {
                    "timestamp": "2026-08-28T01:00",
                    "value": 5.4
                },
                {
                    "timestamp": "2026-08-28T02:00",
                    "value": 4.9
                }
            ],
            "contiguous_intervals": [
                {
                    "start": "2026-08-28T00:00",
                    "end": "2026-08-28T02:00"
                }
            ],
            "peak": {
                "timestamp": "2026-08-28T01:00",
                "value": 5.4
            },
            "calibration": {
                "sensor_id": "S3-VIB-1",
                "measure": "vibration_mm_s",
                "last_calibrated": "2026-04-12",
                "technician": "J. Cho",
                "interval_days": 90,
                "measurement_ages": [
                    {
                        "timestamp": "2026-08-27T20:00",
                        "age_days": 137
                    },
                    {
                        "timestamp": "2026-08-27T21:00",
                        "age_days": 137
                    },
                    {
                        "timestamp": "2026-08-27T22:00",
                        "age_days": 137
                    },
                    {
                        "timestamp": "2026-08-27T23:00",
                        "age_days": 137
                    },
                    {
                        "timestamp": "2026-08-28T00:00",
                        "age_days": 138
                    },
                    {
                        "timestamp": "2026-08-28T01:00",
                        "age_days": 138
                    },
                    {
                        "timestamp": "2026-08-28T02:00",
                        "age_days": 138
                    },
                    {
                        "timestamp": "2026-08-28T03:00",
                        "age_days": 138
                    }
                ],
                "age_days_min": 137,
                "age_days_max": 138,
                "status": "untrusted"
            },
            "eligible_for_causal_use": false
        }
    },
    "candidate_root_cause": {
        "status": "candidate",
        "statement": "Elevated process temperature is a candidate contributor correlated with the Line 3 night-shift defect anomaly.",
        "supporting_trusted_measures": [
            "temp_c"
        ],
        "limitations": [
            "Correlation does not establish causation.",
            "The supplied evidence does not identify or confirm a specific failed component.",
            "Vibration exceedances are untrusted because calibration was overdue and are excluded from causal judgment."
        ]
    },
    "remediation": [
        {
            "action": "Inspect the Line 3 thermal process and temperature-control conditions.",
            "approval_required": true,
            "approval_authority": "Quality Engineer",
            "approval_status": "pending"
        },
        {
            "action": "Run a controlled verification trial after approved thermal-process inspection.",
            "approval_required": true,
            "approval_authority": "Quality Engineer",
            "approval_status": "pending"
        },
        {
            "action": "Recalibrate or independently verify the vibration measurement channel before causal use.",
            "approval_required": true,
            "approval_authority": "Quality Engineer",
            "approval_status": "pending"
        }
    ],
    "validation": {
        "status": "pending",
        "checks": []
    }
}

exec
/bin/zsh -lc "python3 - <<'PY'
import csv, json, yaml
from datetime import datetime
from decimal import Decimal
from pathlib import Path
jp=Path('build/quality-anomaly/anomaly-2026-08-27.json')
mp=Path('build/quality-anomaly/anomaly-report-2026-08-27.md')
d=json.loads(jp.read_text()); md=mp.read_text()
checks=[]
def check(condition,name):
    if not condition: raise AssertionError(name)
    checks.append(name)
check(jp.name=='anomaly-2026-08-27.json' and mp.name=='anomaly-report-2026-08-27.md','filenames_match_incident_date')
check(d['incident']=={'date':'2026-08-27','line':3,'shift':'night','observed_sensor_window':{'start':'2026-08-27T20:00','end':'2026-08-28T03:00','inclusive':True}},'source_incident_binding_matches')
with open(d['sources']['thresholds']) as f: t=yaml.safe_load(f)
with open(d['sources']['mes'],newline='') as f: mes=list(csv.DictReader(f))
rows=[r for r in mes if r['date']==d['incident']['date'] and int(r['line'])==d['incident']['line'] and r['shift']==d['incident']['shift']]
check(len(rows)==1,'mes_unique_bound_row')
r=rows[0]; rr=Decimal(100)*Decimal(r['defects'])/Decimal(r['units'])
expected_row={'date':r['date'],'line':int(r['line']),'shift':r['shift'],'units':int(r['units']),'defects':int(r['defects']),'defect_rate_pct':float(r['defect_rate_pct'])}
check(d['mes']['selected_row']==expected_row,'mes_selected_row_recomputed')
check(abs(d['mes']['recomputed_rate_pct']-float(rr))<1e-12 and abs(rr-Decimal(r['defect_rate_pct']))<=Decimal('0.05'),'mes_rate_recomputed_and_consistent')
check(d['mes']['is_anomaly'] is (Decimal(r['defect_rate_pct'])>Decimal(str(t['defect_rate_pct_threshold']))),'mes_strict_anomaly_verdict')
check(d['thresholds']=={'defect_rate_pct_threshold':float(t['defect_rate_pct_threshold']),'sensors':{'temp_c':{'max':float(t['sensors']['temp_c']['max'])},'vibration_mm_s':{'max':float(t['sensors']['vibration_mm_s']['max'])}},'calibration_interval_days':int(t['calibration_interval_days'])},'thresholds_match_authority')
with open(d['sources']['sensors'],newline='') as f: sensors=list(csv.DictReader(f))
with open(d['sources']['calibration'],newline='') as f: cals=list(csv.DictReader(f))
start=datetime.fromisoformat(d['incident']['observed_sensor_window']['start']); end=datetime.fromisoformat(d['incident']['observed_sensor_window']['end'])
window=[x for x in sensors if int(x['line'])==3 and start<=datetime.fromisoformat(x['timestamp'])<=end]
check(len(window)==8 and all(int(x['line'])==3 for x in window),'sensor_window_bound_line_and_time')
for measure in ('temp_c','vibration_mm_s'):
    e=d['sensor_evidence'][measure]; maximum=float(t['sensors'][measure]['max'])
    samples=[{'timestamp':x['timestamp'],'value':float(x[measure])} for x in window if float(x[measure])>maximum]
    check(e['exceedance_samples']==samples,f'{measure}_strict_exceedance_samples')
    intervals=[]
    for s in samples:
        dt=datetime.fromisoformat(s['timestamp'])
        if not intervals or (dt-datetime.fromisoformat(intervals[-1]['end'])).total_seconds()"'!=3600: intervals.append({'"'start':s['timestamp'],'end':s['timestamp']})
        else: intervals[-1]['end']=s['timestamp']
    check(e['contiguous_intervals']==intervals,f'{measure}_contiguous_intervals')
    check(e['peak']==(max(samples,key=lambda x:x['value']) if samples else None),f'{measure}_peak')
    matches=[c for c in cals if c['measure']==measure]
    check(len(matches)==1,f'{measure}_unique_calibration_by_measure')
    c=matches[0]; cal_dt=datetime.fromisoformat(c['last_calibrated'])
    ages=[]
    for x in window:
        dt=datetime.fromisoformat(x['timestamp']); check(cal_dt<=dt,f'{measure}_no_future_calibration')
        ages.append({'timestamp':x['timestamp'],'age_days':(dt-cal_dt).days})
    statuses=['trusted' if x['age_days']<=int(t['calibration_interval_days']) else 'untrusted' for x in ages]
    check(len(set(statuses))==1,f'{measure}_consistent_trust_status')
    cal=e['calibration']
    check(cal['sensor_id']==c['sensor_id'] and cal['last_calibrated']==c['last_calibrated'] and cal['measurement_ages']==ages and cal['age_days_min']==min(x['age_days'] for x in ages) and cal['age_days_max']==max(x['age_days'] for x in ages) and cal['status']==statuses[0],f'{measure}_calibration_ages_and_status')
    check(e['eligible_for_causal_use']==(statuses[0]=='trusted'),f'{measure}_causal_eligibility')
support=d['candidate_root_cause']['supporting_trusted_measures']
check(all(d['sensor_evidence'][m]['calibration']['status']=='trusted' and d['sensor_evidence'][m]['eligible_for_causal_use'] for m in support),'no_untrusted_supporting_measure')
check('vibration_mm_s' not in support,'untrusted_vibration_excluded_from_support')
headings=[line for line in md.splitlines() if line.startswith('#')]
check(headings==['# Line 3 Quality Anomaly Report — 2026-08-27 (night shift)','## Anomaly','## Sensor evidence','## Root cause (candidate)','## Remediation (requires Quality Engineer approval)'],'markdown_exact_sections')
mesd=d['mes']; check(f\"Defect rate {mesd['selected_row']['defect_rate_pct']}% (threshold {d['thresholds']['defect_rate_pct_threshold']}%), {mesd['selected_row']['units']:,} units, {mesd['selected_row']['defects']} defects; recomputed rate {mesd['recomputed_rate_pct']:.4f}%. Verified anomaly: yes.\" in md,'markdown_mes_numeric_facts_match_json')
for measure,label in [('temp_c','Temperature'),('vibration_mm_s','Vibration')]:
    e=d['sensor_evidence'][measure]; c=e['calibration']; iv=e['contiguous_intervals'][0]; age=str(c['age_days_min']) if c['age_days_min']==c['age_days_max'] else f\"{c['age_days_min']}–{c['age_days_max']}\"
    check(f\"{label} exceeded {e['maximum']} {e['unit']} from {iv['start']} through {iv['end']} inclusive (peak {e['peak']['value']} {e['unit']} at {e['peak']['timestamp']}).\" in md,f'markdown_{measure}_interval_peak_match_json')
    check(c['sensor_id'] in md and c['last_calibrated'] in md and f'measurement age {age} whole days' in md and c['status'] in md,f'markdown_{measure}_calibration_trust_match_json')
cause=d['candidate_root_cause']
check(f\"Status: {cause['status']}. {cause['statement']} Supporting trusted measure: {', '.join(cause['supporting_trusted_measures'])}. Limitations: {' '.join(cause['limitations'])}\" in md,'markdown_candidate_and_limitations_match_json')
for item in d['remediation']:
    check(item['approval_required'] is True and item['approval_authority']=='Quality Engineer' and item['approval_status']=='pending','json_remediation_approval_gate')
    check(f\"- {item['action']} requires Quality Engineer approval. Approval: pending.\" in md,'markdown_remediation_action_authority_status_match_json')
check(md.count('requires Quality Engineer approval')==len(d['remediation'])+1,'every_remediation_has_exact_approval_statement')
check('day shift' not in md and '(day)' not in md,'no_unrelated_shift_in_markdown')
check('Approval: approved' not in md and 'Approval: pending' in md,'no_approval_or_execution_claim')
d['validation']={'status':'passed','checks':checks}
jp.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\\n')
print('validation.status=passed')
for name in checks: print('PASS',name)
PY
python3 -m json.tool build/quality-anomaly/anomaly-2026-08-27.json
cat build/quality-anomaly/anomaly-report-2026-08-27.md" in /Users/hongmartin/orca/projects/open-workflow
 succeeded in 0ms:
validation.status=passed
PASS filenames_match_incident_date
PASS source_incident_binding_matches
PASS mes_unique_bound_row
PASS mes_selected_row_recomputed
PASS mes_rate_recomputed_and_consistent
PASS mes_strict_anomaly_verdict
PASS thresholds_match_authority
PASS sensor_window_bound_line_and_time
PASS temp_c_strict_exceedance_samples
PASS temp_c_contiguous_intervals
PASS temp_c_peak
PASS temp_c_unique_calibration_by_measure
PASS temp_c_no_future_calibration
PASS temp_c_no_future_calibration
PASS temp_c_no_future_calibration
PASS temp_c_no_future_calibration
PASS temp_c_no_future_calibration
PASS temp_c_no_future_calibration
PASS temp_c_no_future_calibration
PASS temp_c_no_future_calibration
PASS temp_c_consistent_trust_status
PASS temp_c_calibration_ages_and_status
PASS temp_c_causal_eligibility
PASS vibration_mm_s_strict_exceedance_samples
PASS vibration_mm_s_contiguous_intervals
PASS vibration_mm_s_peak
PASS vibration_mm_s_unique_calibration_by_measure
PASS vibration_mm_s_no_future_calibration
PASS vibration_mm_s_no_future_calibration
PASS vibration_mm_s_no_future_calibration
PASS vibration_mm_s_no_future_calibration
PASS vibration_mm_s_no_future_calibration
PASS vibration_mm_s_no_future_calibration
PASS vibration_mm_s_no_future_calibration
PASS vibration_mm_s_no_future_calibration
PASS vibration_mm_s_consistent_trust_status
PASS vibration_mm_s_calibration_ages_and_status
PASS vibration_mm_s_causal_eligibility
PASS no_untrusted_supporting_measure
PASS untrusted_vibration_excluded_from_support
PASS markdown_exact_sections
PASS markdown_mes_numeric_facts_match_json
PASS markdown_temp_c_interval_peak_match_json
PASS markdown_temp_c_calibration_trust_match_json
PASS markdown_vibration_mm_s_interval_peak_match_json
PASS markdown_vibration_mm_s_calibration_trust_match_json
PASS markdown_candidate_and_limitations_match_json
PASS json_remediation_approval_gate
PASS markdown_remediation_action_authority_status_match_json
PASS json_remediation_approval_gate
PASS markdown_remediation_action_authority_status_match_json
PASS json_remediation_approval_gate
PASS markdown_remediation_action_authority_status_match_json
PASS every_remediation_has_exact_approval_statement
PASS no_unrelated_shift_in_markdown
PASS no_approval_or_execution_claim
{
    "incident": {
        "date": "2026-08-27",
        "line": 3,
        "shift": "night",
        "observed_sensor_window": {
            "start": "2026-08-27T20:00",
            "end": "2026-08-28T03:00",
            "inclusive": true
        }
    },
    "sources": {
        "memo": "examples/cases/quality-anomaly/materials/memo.md",
        "notes": "examples/cases/quality-anomaly/materials/notes.txt",
        "mes": "examples/cases/quality-anomaly/materials/data/mes-defects-2026-08.csv",
        "sensors": "examples/cases/quality-anomaly/materials/data/sensor-2026-08-27.csv",
        "calibration": "examples/cases/quality-anomaly/materials/data/calibration-log.csv",
        "thresholds": "examples/cases/quality-anomaly/materials/data/thresholds.yaml",
        "format_example": "examples/cases/quality-anomaly/materials/previous/anomaly-report-2026-06-14.md",
        "assumptions": "examples/cases/quality-anomaly/ASSUMPTIONS.md"
    },
    "thresholds": {
        "defect_rate_pct_threshold": 2.5,
        "sensors": {
            "temp_c": {
                "max": 78.0
            },
            "vibration_mm_s": {
                "max": 4.5
            }
        },
        "calibration_interval_days": 90
    },
    "mes": {
        "selected_row": {
            "date": "2026-08-27",
            "line": 3,
            "shift": "night",
            "units": 3900,
            "defects": 215,
            "defect_rate_pct": 5.5
        },
        "recomputed_rate_pct": 5.512820512820513,
        "rate_tolerance_percentage_points": 0.05,
        "rate_is_consistent": true,
        "is_anomaly": true
    },
    "sensor_evidence": {
        "temp_c": {
            "unit": "\u00b0C",
            "maximum": 78.0,
            "exceedance_samples": [
                {
                    "timestamp": "2026-08-27T22:00",
                    "value": 79.4
                },
                {
                    "timestamp": "2026-08-27T23:00",
                    "value": 81.9
                },
                {
                    "timestamp": "2026-08-28T00:00",
                    "value": 82.5
                },
                {
                    "timestamp": "2026-08-28T01:00",
                    "value": 80.7
                }
            ],
            "contiguous_intervals": [
                {
                    "start": "2026-08-27T22:00",
                    "end": "2026-08-28T01:00"
                }
            ],
            "peak": {
                "timestamp": "2026-08-28T00:00",
                "value": 82.5
            },
            "calibration": {
                "sensor_id": "S3-TEMP-1",
                "measure": "temp_c",
                "last_calibrated": "2026-07-30",
                "technician": "K. Han",
                "interval_days": 90,
                "measurement_ages": [
                    {
                        "timestamp": "2026-08-27T20:00",
                        "age_days": 28
                    },
                    {
                        "timestamp": "2026-08-27T21:00",
                        "age_days": 28
                    },
                    {
                        "timestamp": "2026-08-27T22:00",
                        "age_days": 28
                    },
                    {
                        "timestamp": "2026-08-27T23:00",
                        "age_days": 28
                    },
                    {
                        "timestamp": "2026-08-28T00:00",
                        "age_days": 29
                    },
                    {
                        "timestamp": "2026-08-28T01:00",
                        "age_days": 29
                    },
                    {
                        "timestamp": "2026-08-28T02:00",
                        "age_days": 29
                    },
                    {
                        "timestamp": "2026-08-28T03:00",
                        "age_days": 29
                    }
                ],
                "age_days_min": 28,
                "age_days_max": 29,
                "status": "trusted"
            },
            "eligible_for_causal_use": true
        },
        "vibration_mm_s": {
            "unit": "mm/s",
            "maximum": 4.5,
            "exceedance_samples": [
                {
                    "timestamp": "2026-08-28T00:00",
                    "value": 5.1
                },
                {
                    "timestamp": "2026-08-28T01:00",
                    "value": 5.4
                },
                {
                    "timestamp": "2026-08-28T02:00",
                    "value": 4.9
                }
            ],
            "contiguous_intervals": [
                {
                    "start": "2026-08-28T00:00",
                    "end": "2026-08-28T02:00"
                }
            ],
            "peak": {
                "timestamp": "2026-08-28T01:00",
                "value": 5.4
            },
            "calibration": {
                "sensor_id": "S3-VIB-1",
                "measure": "vibration_mm_s",
                "last_calibrated": "2026-04-12",
                "technician": "J. Cho",
                "interval_days": 90,
                "measurement_ages": [
                    {
                        "timestamp": "2026-08-27T20:00",
                        "age_days": 137
                    },
                    {
                        "timestamp": "2026-08-27T21:00",
                        "age_days": 137
                    },
                    {
                        "timestamp": "2026-08-27T22:00",
                        "age_days": 137
                    },
                    {
                        "timestamp": "2026-08-27T23:00",
                        "age_days": 137
                    },
                    {
                        "timestamp": "2026-08-28T00:00",
                        "age_days": 138
                    },
                    {
                        "timestamp": "2026-08-28T01:00",
                        "age_days": 138
                    },
                    {
                        "timestamp": "2026-08-28T02:00",
                        "age_days": 138
                    },
                    {
                        "timestamp": "2026-08-28T03:00",
                        "age_days": 138
                    }
                ],
                "age_days_min": 137,
                "age_days_max": 138,
                "status": "untrusted"
            },
            "eligible_for_causal_use": false
        }
    },
    "candidate_root_cause": {
        "status": "candidate",
        "statement": "Elevated process temperature is a candidate contributor correlated with the Line 3 night-shift defect anomaly.",
        "supporting_trusted_measures": [
            "temp_c"
        ],
        "limitations": [
            "Correlation does not establish causation.",
            "The supplied evidence does not identify or confirm a specific failed component.",
            "Vibration exceedances are untrusted because calibration was overdue and are excluded from causal judgment."
        ]
    },
    "remediation": [
        {
            "action": "Inspect the Line 3 thermal process and temperature-control conditions.",
            "approval_required": true,
            "approval_authority": "Quality Engineer",
            "approval_status": "pending"
        },
        {
            "action": "Run a controlled verification trial after approved thermal-process inspection.",
            "approval_required": true,
            "approval_authority": "Quality Engineer",
            "approval_status": "pending"
        },
        {
            "action": "Recalibrate or independently verify the vibration measurement channel before causal use.",
            "approval_required": true,
            "approval_authority": "Quality Engineer",
            "approval_status": "pending"
        }
    ],
    "validation": {
        "status": "passed",
        "checks": [
            "filenames_match_incident_date",
            "source_incident_binding_matches",
            "mes_unique_bound_row",
            "mes_selected_row_recomputed",
            "mes_rate_recomputed_and_consistent",
            "mes_strict_anomaly_verdict",
            "thresholds_match_authority",
            "sensor_window_bound_line_and_time",
            "temp_c_strict_exceedance_samples",
            "temp_c_contiguous_intervals",
            "temp_c_peak",
            "temp_c_unique_calibration_by_measure",
            "temp_c_no_future_calibration",
            "temp_c_no_future_calibration",
            "temp_c_no_future_calibration",
            "temp_c_no_future_calibration",
            "temp_c_no_future_calibration",
            "temp_c_no_future_calibration",
            "temp_c_no_future_calibration",
            "temp_c_no_future_calibration",
            "temp_c_consistent_trust_status",
            "temp_c_calibration_ages_and_status",
            "temp_c_causal_eligibility",
            "vibration_mm_s_strict_exceedance_samples",
            "vibration_mm_s_contiguous_intervals",
            "vibration_mm_s_peak",
            "vibration_mm_s_unique_calibration_by_measure",
            "vibration_mm_s_no_future_calibration",
            "vibration_mm_s_no_future_calibration",
            "vibration_mm_s_no_future_calibration",
            "vibration_mm_s_no_future_calibration",
            "vibration_mm_s_no_future_calibration",
            "vibration_mm_s_no_future_calibration",
            "vibration_mm_s_no_future_calibration",
            "vibration_mm_s_no_future_calibration",
            "vibration_mm_s_consistent_trust_status",
            "vibration_mm_s_calibration_ages_and_status",
            "vibration_mm_s_causal_eligibility",
            "no_untrusted_supporting_measure",
            "untrusted_vibration_excluded_from_support",
            "markdown_exact_sections",
            "markdown_mes_numeric_facts_match_json",
            "markdown_temp_c_interval_peak_match_json",
            "markdown_temp_c_calibration_trust_match_json",
            "markdown_vibration_mm_s_interval_peak_match_json",
            "markdown_vibration_mm_s_calibration_trust_match_json",
            "markdown_candidate_and_limitations_match_json",
            "json_remediation_approval_gate",
            "markdown_remediation_action_authority_status_match_json",
            "json_remediation_approval_gate",
            "markdown_remediation_action_authority_status_match_json",
            "json_remediation_approval_gate",
            "markdown_remediation_action_authority_status_match_json",
            "every_remediation_has_exact_approval_statement",
            "no_unrelated_shift_in_markdown",
            "no_approval_or_execution_claim"
        ]
    }
}
# Line 3 Quality Anomaly Report — 2026-08-27 (night shift)

## Anomaly
Defect rate 5.5% (threshold 2.5%), 3,900 units, 215 defects; recomputed rate 5.5128%. Verified anomaly: yes.

## Sensor evidence
Temperature exceeded 78.0 °C from 2026-08-27T22:00 through 2026-08-28T01:00 inclusive (peak 82.5 °C at 2026-08-28T00:00). Calibration sensor S3-TEMP-1 was calibrated 2026-07-30; measurement age 28–29 whole days within the 90-day interval → trusted and eligible for causal use.
Vibration exceeded 4.5 mm/s from 2026-08-28T00:00 through 2026-08-28T02:00 inclusive (peak 5.4 mm/s at 2026-08-28T01:00). Calibration sensor S3-VIB-1 was calibrated 2026-04-12; measurement age 137–138 whole days exceeds the 90-day interval → untrusted and excluded from causal judgment.

## Root cause (candidate)
Status: candidate. Elevated process temperature is a candidate contributor correlated with the Line 3 night-shift defect anomaly. Supporting trusted measure: temp_c. Limitations: Correlation does not establish causation. The supplied evidence does not identify or confirm a specific failed component. Vibration exceedances are untrusted because calibration was overdue and are excluded from causal judgment.

## Remediation (requires Quality Engineer approval)
- Inspect the Line 3 thermal process and temperature-control conditions. requires Quality Engineer approval. Approval: pending.
- Run a controlled verification trial after approved thermal-process inspection. requires Quality Engineer approval. Approval: pending.
- Recalibrate or independently verify the vibration measurement channel before causal use. requires Quality Engineer approval. Approval: pending.

codex
Verified Line 3 night shift on 2026-08-27: 5.5% recorded defect rate (5.5128% recomputed), exceeding the 2.5% threshold.

- Temperature: trusted
- Vibration: untrusted and excluded from causal support
- Candidate cause: elevated process temperature, correlation only
- Remediation: pending; requires Quality Engineer approval
- Mechanical validation: passed

Artifacts:

- [anomaly-2026-08-27.json](/Users/hongmartin/orca/projects/open-workflow/build/quality-anomaly/anomaly-2026-08-27.json)
- [anomaly-report-2026-08-27.md](/Users/hongmartin/orca/projects/open-workflow/build/quality-anomaly/anomaly-report-2026-08-27.md)
tokens used
54,488
Verified Line 3 night shift on 2026-08-27: 5.5% recorded defect rate (5.5128% recomputed), exceeding the 2.5% threshold.

- Temperature: trusted
- Vibration: untrusted and excluded from causal support
- Candidate cause: elevated process temperature, correlation only
- Remediation: pending; requires Quality Engineer approval
- Mechanical validation: passed

Artifacts:

- [anomaly-2026-08-27.json](/Users/hongmartin/orca/projects/open-workflow/build/quality-anomaly/anomaly-2026-08-27.json)
- [anomaly-report-2026-08-27.md](/Users/hongmartin/orca/projects/open-workflow/build/quality-anomaly/anomaly-report-2026-08-27.md)
