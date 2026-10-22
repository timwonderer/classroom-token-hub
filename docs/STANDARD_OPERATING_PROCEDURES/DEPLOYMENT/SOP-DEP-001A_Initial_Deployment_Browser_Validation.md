# SOP-DEP-001A: Initial Deployment Browser Validation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DEP-001A     | 1.0     | 2026-10-22     | SOP-DEP-001 §XI (2.9) | Normative |

## I. Purpose

Define the browser validation that a first deployment must pass before its Access gate opens: every item in
§VI, exercised in a real browser and evidenced. A first deployment has no earlier validated build to fall back
on, so nothing is left to inference.

## II. Scope

Applies to:

- the first deployment of the v2 application onto a host;
- a rehearsal host, or any host started from a fresh database;
- a release the owner designates as a full validation.

Every other release follows `SOP-DEP-001B`. The template is extracted from `SOP-DEP-001` §XI, which until
version 2.10 applied the full list to every release (owner ruling, 2026-10-22).

## III. Authority Level

Normative (SOP Tier). Subordinate to INV-CORE-000. Used with `SOP-DEP-001` (the live-test runbook) and
`SOP-DEP-002` (production transition).

## IV. Dependencies

- `SOP-DEP-001`: §XI.A (how to exercise the adversarial items), §XIII (roles and the solo-operator exception),
  §XV (record storage).
- `SOP-DEP-002`: the release procedure this validation sits inside.
- `INV-ARC-011`, `INV-ARC-019`: class isolation and identity, which items 8 to 12 exercise.
- `INV-ARC-020`: accessibility, item 17.

## V. Mechanism

1. Run every item in §VI in a real browser while the Cloudflare Access gate is restricted.
2. Give each item exactly one result from §VII, with its evidence.
3. **Every item must be *evidenced* before the gate opens.** Any other result keeps the gate closed until the item
   is evidenced, or until the owner records, in the deployment record and before opening, that the gate opens with
   that item outstanding and why.
4. Adversarial items (those asserting something *cannot* happen) are exercised as `SOP-DEP-001` §XI.A describes,
   including its rule that no deliberate cross-scope attempt is made on a host serving live classes.

## VI. Checklist

1. `/admin/login` renders and submits.
2. `/student/login` renders and submits.
3. `/docs` renders.
4. Passwordless enrollment and authentication with deployment credentials.
5. Turnstile renders on every configured route and real verification succeeds.
6. Teacher creates or accesses a class boundary.
7. Student seat claim, then a student session.
8. Teacher current-class switching via `POST /admin/current-class`.
9. Student add-class via `/student/add-class`, and switch-class via `POST /student/switch-class/<class_id>`. The
   route takes the canonical `class_id`; a `join_code` in that position is the retired alias form.
10. Selected-class export via `/admin/export-students`. The export scopes to the session's active class (a query
    parameter does not choose the class) and lists claimed seats only.
11. Hall-pass verification via `/verify/hallpass/<teacher_public_token>`.
12. Class-scoped admin actions cannot cross the selected class boundary.
13. Attendance, productivity, payroll, obligations, ledger and store paths load and execute through their canonical
    routes.
14. Audit/lineage records are produced for protected mutations.
15. Export and support/operations surfaces load without 500 responses.
16. No PII appears in URLs, logs, errors, or browser-visible diagnostics.
17. Accessibility smoke checks cover the public, login, teacher and student surfaces reached in this test
    (INV-ARC-020).

## VII. Results

Every item takes exactly one of these five results:

- *Evidenced*: the features the operator exercised ran through the item and it behaved as the item asserts,
  whether or not it was a separate step. A student sign-in that passes Turnstile's server-side check could not have
  done so unless the widget rendered and issued a token.
- *In part*: an item with several parts, some of which ran and behaved as asserted while no exercised feature
  reached the others. The evidence names both.
- *Failed*: the item ran and did not behave as it asserts. The row links the defect.
- *Blocked*: the item could not be run, for a reason outside the application under test (a missing credential, an
  unavailable dependency, the Access gate). The row names the blocker.
- *Not exercised*: nothing the operator ran reached the item, and nothing prevented it.

## VIII. Recording

Results may be recorded as the checks run or afterward, from contemporaneous evidence: the request log, the
database, the operator's notes or the session transcript. A row may not assert a result its evidence does not show.
A row's evidence names what ran (route, action, status, the build it ran on), not a verdict. Because §V.3 makes
every item a condition of opening, the table is complete before the gate opens.

The deployment record under `docs/ops/audits/` carries one row per item, in §VI order:

| # | Item | Result | Owner | Time (UTC) | Evidence or defect |
|---|---|---|---|---|---|
| 1 | `/admin/login` renders and submits | | | | |
| … | … | | | | |

## IX. Amendment

Revisions require incrementing the version, updating the effective date, and populating the Supersedes field.
A claim about codebase behaviour in this document must be verifiable against the release artifact at the time of
revision; where they disagree, the code wins and this document is corrected.

### Revision History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-10-22 | Extracted from `SOP-DEP-001` §XI (2.9) as the initial-deployment template: every item evidenced before the gate opens. Results may be recorded during or after the checks from contemporaneous evidence. Owner rulings, 2026-10-22. |
