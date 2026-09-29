# Incident record: PROD-PAY-001, unpaid open sessions (2026-09-28)

**Status:** Resolved. The defect was fixed in production at 03:11 UTC on 2026-09-29. The teacher
approved the lost pay at 04:21–04:25 UTC, and the rest is paid automatically at each class's next
payroll run (see §5).

**Summary:** payroll runs made while students were clocked in left the rest of those sessions
unpaid. That came to 79 students and $1,947.40 across four classes, plus about $999 that the fixed
payroll pays at the next run. No student was overpaid, and no data outside payroll was affected.

All times are UTC. Every production figure below comes from read-only queries.

## 1. Timeline

| Time | Event |
|---|---|
| 2026-09-28 16:14 | AP CSP (`1da9085a`): Run Payroll submitted three times within 3 s while 18 students were clocked in |
| 17:29, 20:56 | Chemistry `TMUC5U` (`41e5092b`): runs 1 and 2 |
| 19:22, 19:33 | Chemistry `ZDMKFB` (`bfe8cfc4`): runs 1 and 2; the second paid 1 of 24 students |
| 22:15, 22:37, 22:44 | Chemistry `S65LQG` (`c393fd39`): runs 1–3; students paid per run went 22 → 3 → 0 |
| after class | The teacher reported that a second run "didn't produce the amount expected" |
| 2026-09-29 03:11 | Fix released: `bc5c07a2e` (#1439), [run 36516000067](https://github.com/timwonderer/classroom-token-hub/actions/runs/36516000067), health passed |
| 04:08 | Correction tool released: `eaca2a7ef` (#1440), [run 36520218616](https://github.com/timwonderer/classroom-token-hub/actions/runs/36520218616), health passed |
| 04:21–04:25 | Teacher reviewed each class and approved the corrections |

## 2. Root cause

`_calculate_attendance_seconds_since` in `app/feats/prod.py` loaded only the attendance rows at
or after the student's last payroll event. A session still running at that payroll lost its
`active` row, so its later `inactive` row paired with nothing and counted as zero. The time after
a mid-session payroll was lost, even after the student clocked out.

**Contributing defects:**

- **The teacher's preview disagreed with the run.** Three separate unpaid-time calculations existed. The teacher's preview counted time across a payroll correctly, so it showed minutes accumulating that the run never paid.
- **A repeated clock-in restarted the session.** A second `active` row dropped the time before it.
- **Rapid resubmission.** Nothing stopped the three submissions within 3 s.

## 3. Fix (#1439)

A session now counts in the payroll window where it closes (DOM-PROD-001 §VI.3).

- **Closed sessions only.** Each run pays sessions that closed after the student's last payroll, in full. An open session is never paid and never split.
- **One reader.** `calculate_seat_payroll_attendance` is the only unpaid-time calculation; the run and every preview read it.
- **Nothing to pay is refused.** A run with nothing payable is refused with "Nothing to pay yet", which also absorbs repeated clicks. Automatic payroll waits for the first clock-out.
- **Marked events.** New payroll events carry `summary_json.settlement_rule = "closed_sessions"`.

## 4. Correction (#1440)

**Calculation.** For each run settled by the earlier rule, the tool replays what the run paid and
compares it with the time worked inside its window. The replay must match the ledger; a student
where it does not is marked "Needs review" and cannot be approved. No student was marked.

**Attribution** (decision recorded for this incident):

| Field | Value |
|---|---|
| Actor | the approving teacher's `seat_id` |
| Event type | `manual_credit` (not a payroll boundary) |
| Mechanism | `SYSTEM`: the platform calculated the amount; it carries no authority to post without the teacher |
| Idempotency | `payroll-correction:PROD-PAY-001:<class_id>:<seat_id>`, one per student |
| Student-facing text | "Payroll correction: unpaid work time from Sep 28 (system-calculated)" |

**Verification before approval.** Each class's review page was compared with an independent
per-student SQL calculation.

| Class | Page | SQL (fractional seconds) | Result |
|---|---|---|---|
| AP CSP `V4JTT6` (`1da9085a`) | 18 × $0.05 = $0.90 | 18 students; the 2.3 s between the first two submissions | Match |
| Chemistry `TMUC5U` (`41e5092b`) | 16 × $64.00 = $1,024.00 | 16 students at $64.01–$64.05, plus 8 at $0.01–$0.02 | Match |
| Chemistry `ZDMKFB` (`bfe8cfc4`) | 23 × $9.88 = $227.24 | 23 students at $9.89–$9.92, plus 2 below $0.01 | Match |
| Chemistry `S65LQG` (`c393fd39`) | 22 students, $695.26 | 22 students, each 1–7¢ higher | Match |

Every difference is the page rounding down: it counts whole seconds, as the payroll run does, and
rounds each payroll window separately. The SQL's extra sub-cent "students" are fractional-second
remainders that neither the run nor the tool pays.

**Posted (verified in production after approval).** There are 79 `manual_credit` events, one per
student, totalling $1,947.40. Every event is mechanism `SYSTEM`, with a single actor (the teacher's
seat) and the class payroll policy recorded. Each has a matching ledger row with the incident
description, `PENDING` at the time of this record.

## 5. Paid automatically at the next payroll run

The correction covers each student's time up to their last earlier-rule payroll. Where a session
was still open then and closed later, the fixed payroll pays the remainder at the class's next run,
counted only from that last run. This was measured read-only before approval.

| Class | Students | Minutes | Amount |
|---|---|---|---|
| AP CSP (`1da9085a`) | 18 | 630.7 | ~$946.10 |
| Chemistry `TMUC5U` (`41e5092b`) | 1 | 35.0 | ~$52.53 |

This means AP CSP's real loss was about 631 minutes. The "under 1 minute" figure given during the
incident counted only the 2.3 s between submissions, because no later run had yet happened in that
class.

## 6. Follow-ups

- [ ] At the next payroll run in any class, confirm new events carry `settlement_rule` and that AP CSP and `TMUC5U` receive the amounts in §5.
- [ ] Remove the correction tool after 2026-10-31: `app/services/payroll/corrections.py`, the `/admin/payroll/correction` route, its template, and the banner flags and include.
- [ ] Advanced-mode time rounding is applied only by the unused `calculate_payroll_breakdown`, never by the real run (tracked separately).
- [ ] "Time Today" can count a session left open from a previous day as running into today (tracked separately).
- [ ] `test_history_reports_returned_and_ignores_an_unrelated_stray_active_row` uses the UTC date against a class-local endpoint and fails between 00:00 UTC and local midnight (tracked separately).
