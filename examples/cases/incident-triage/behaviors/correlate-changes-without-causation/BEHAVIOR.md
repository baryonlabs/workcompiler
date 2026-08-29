# BEHAVIOR: correlate-changes-without-causation

## 1. Intent
Identify relevant operational context using a precise same-host, preceding-24-hour window while preventing an unsupported correlation from becoming a causal claim.

## 2. Evidence
The trajectory reads `materials/data/change-log.csv`, prints the UTC interval `[alert time - 24 hours, alert time]`, filters by exact alert host and inclusive timestamps, and carries the qualifying source rows into both outputs as possible correlation.

## 3. Decision
- `true`: Every included change has the exact alert host and falls within the inclusive preceding 24-hour interval, every qualifying change is included, and the output states possibility rather than causation.
- `false`: The window is anchored to the reference date or execution time, a future/out-of-window/wrong-host change is included, a qualifying change is omitted, or causation is asserted.
- `na`: Change history or a usable alert host/time is unavailable and the evidence problem is explicitly escalated.

## 4. Execution
Parse alert and change timestamps as UTC, compute the lower bound from the alert timestamp, filter exact-host rows inclusively, preserve their source details, and label only `change_correlation_possible`.

## 5. Recovery
Recompute the interval from the selected alert, rerun the host/time predicate, synchronize both outputs, and replace causal wording with evidence-bounded correlation language.

## 6. Failure Modes
Using calendar-day proximity, comparing against “today,” ignoring time zones, fuzzy host matching, selecting a later change, claiming a deployment or credential rotation caused the alert, or disagreeing across Markdown and JSON.

