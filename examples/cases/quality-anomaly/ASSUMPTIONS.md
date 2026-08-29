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
