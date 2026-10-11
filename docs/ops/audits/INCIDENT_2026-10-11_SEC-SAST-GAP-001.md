# Incident record: SEC-SAST-GAP-001, SAST tooling gap behind S1/S4 (2026-10-11)

**Status:** Closed. The underlying vulnerabilities (S1, S4) were fixed and deployed in v2.2.2
(`61b509b7fd8ad680691ba733a467f2cc66bd65b0`, 2026-10-11 00:23 UTC) before this record was
written; see GHSA-7fxj-gpw3-23g3 for the vulnerability advisory. This record covers the
tooling-process finding only: why neither automated SAST tool blocked these two sinks before a
manual audit found them, and the resulting change to scanning configuration.

All times are UTC.

## 1. Summary

Two independent XSS sinks (S1: hall-pass destination rendered unescaped; S4: `nl2br_filter`
wrapping raw text in `Markup()`) existed in production for up to ~11 months before a manual
repository audit on 2026-10-10 found them. Checking the record after the fact:

- **CodeQL** (GitHub's managed "default setup," `query_suite: default`, active since
  2025-12-13) never flagged either sink. 126 code-scanning alerts exist for this repository's
  history; none touch `templates/admin_hall_pass.html`, `templates/student_dashboard.html`,
  `app/__init__.py`, or the announcement templates. The one rule built for this exact bug class,
  `js/xss-through-dom`, fired 7 times elsewhere in the codebase (all since fixed) but never on
  the S1 sink.
- **Aikido** (SAST, free tier) *did* flag the S1 client-side sink —
  `templates/admin_hall_pass.html` lines 537 and 603-610 (`tbody.innerHTML = ...`), both rated
  High, with the first AI-upgraded to "likely exploitable." It did not flag S4 or the second S1
  sink (the Jinja-side `attendance_state_json|safe` sink in `student_dashboard.html`).

Neither tool's finding reached a merge-blocking gate. Aikido was removed from the project on
2026-10-11 as a result (see §4). CodeQL remains, and this record's action item is to broaden its
query suite (see §5).

## 2. Timeline

| Time | Event |
|---|---|
| 2025-11-22 | PR #288 introduces the S1 client-side sink (`admin_hall_pass.html`, hall-pass history render). CodeQL is not yet wired into the repository; Aikido's check on that PR shows no finding for it. |
| 2025-12-13 | CodeQL ("default setup") becomes active on the repository. |
| 2025-12-26 | S4's sink (`nl2br_filter` in `app/__init__.py`) ships with the announcement feature, ~2.5 hours after PR #732 ("Fix: Remediate XSS Vulnerability in Redirect Logic") fixes an unrelated, different-pattern XSS. |
| 2026-07-21 | The second S1 sink (`student_dashboard.html`, `attendance_state_json|safe`) ships. CodeQL has been active for seven months at this point. |
| 2026-10-10 | Manual repository audit (37 findings, S/F/O/C categories) identifies S1 and S4 independently of either scanning tool. |
| 2026-10-11 00:23 | Fix deployed to production as v2.2.2 (`61b509b7f`); see `docs/ops/audits/` release record. |
| 2026-10-11 ~02:14 | Owner checks Aikido's dashboard directly and finds the pre-existing High-severity finding for the S1 client-side sink, still open, never surfaced as a failing PR check. |
| 2026-10-11 ~02:49 | Root cause confirmed: Aikido's PR check is diff-scoped only (confirmed via PR #1535's final-commit check output, "No new issues were introduced. No issues were solved."). It does not re-evaluate pre-existing findings in files a PR doesn't touch, so every PR after #288 showed green regardless of the open finding. Owner decides to remove Aikido from the repository. |

## 3. Root cause

Two independent, non-overlapping gaps, not one:

1. **Aikido (S1 client-side sink only): detection without routing.** The scanner correctly
   identified the sink and rated it High/likely-exploitable at some point after 2025-11-22. But
   its free-tier PR check only diffs the changed lines of each PR against known issues in those
   same lines — it does not gate on, or even surface, pre-existing findings in files a given PR
   leaves untouched. Because no PR after #288 touched line 537 until the fix PR itself, every
   intervening PR's Aikido check reported clean. The finding sat in Aikido's own dashboard queue,
   visible only to someone who opened it directly — which nothing in the repository's workflow
   required anyone to do.
2. **CodeQL (both S1 sinks, plus S4): no coverage, not a routing failure.** CodeQL's default
   query suite has no rule for a value that reaches Jinja output through the `safe` filter or a
   custom filter wrapping `Markup()` — a cross-language (Python-to-Jinja) taint flow that generic
   DOM-XSS/reflected-XSS queries don't model. This explains the dashboard sink (S1) and S4 fully.
   It does not fully explain the client-side sink CodeQL's own `js/xss-through-dom` rule *does*
   model and caught 7 other times in this codebase — the taint flow there crosses a
   `fetch().then(r => r.json())` → `.map()` → template-literal boundary that none of the other 7
   catches needed to cross, which is the most likely reason that specific instance was missed
   even though the rule class exists.

## 4. Action taken

- Aikido removed from the repository (owner action, 2026-10-11). A scanner whose merge-blocking
  check reports green regardless of its own dashboard backlog is a worse signal than no scanner:
  the green checkmark reads as "nothing found" when it means "nothing new in this diff."

## 5. Follow-ups

- [ ] Switch CodeQL's `code-scanning/default-setup` query suite from `default` to
      `security-extended` (owner action in Settings → Code security — not changeable from a PR).
      Tracked alongside this record; see the accompanying PR adding an advanced-setup
      `codeql.yml` workflow for the alternative of moving to a checked-in, reviewable
      configuration instead of the Settings-managed default.
- [ ] Establish a recurring (not purely PR-triggered) review of any SAST tool's full dashboard
      backlog, not just its PR-time pass/fail, so a pre-existing finding in untouched code has a
      scheduled point where it gets looked at.
- [ ] Consider a small custom CodeQL query, or at minimum a standing code-review checklist item,
      for the two patterns this incident showed are under-modeled here: (a) a function registered
      into `jinja_env.filters[...]` that calls `Markup()` without escaping first, and (b) a
      `fetch(...).then(...)` response assigned into `.innerHTML` in a template's inline script.
