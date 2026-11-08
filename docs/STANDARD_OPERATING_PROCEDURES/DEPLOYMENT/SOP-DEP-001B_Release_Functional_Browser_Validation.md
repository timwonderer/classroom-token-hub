# SOP-DEP-001B: Release Functional Browser Validation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DEP-001B     | 1.2     | 2026-11-08     | 1.1 | Normative |

## I. Purpose

Define the browser validation for a release to a host that has already passed `SOP-DEP-001A`. A release
browser-checks the features it changes, the features connected to those changes, and features with a known
problem. The release's full test suite, not the browser, covers everything else. Validation is carried out by
development and operations alone (§V.A).

## II. Scope

Applies to every tagged or untagged release under `SOP-DEP-002` onto a host already validated by `SOP-DEP-001A`,
unless the owner designates that release a full validation (then `SOP-DEP-001A` applies).

## III. Authority Level

Normative (SOP Tier). Subordinate to INV-CORE-000. Used with `SOP-DEP-002` (§VII.A step 10 and §VIII).

## IV. Dependencies

- `SOP-DEP-001A`: the full checklist, used here as the vocabulary for scoped features.
- `SOP-DEP-001`: §XI.A (how to exercise adversarial items; no deliberate cross-scope attempt on a host serving live
  classes) and §XIII (roles and the solo-operator exception).
- `SOP-DEP-002`: the release procedure.
- `INV-ARC-017`: testing invariants; §V.5–§V.6 and §VII govern how a row reports its evidence and coverage.
- `INV-ARC-020`: accessibility, for features whose rendered interface the release changes.

## V. Mechanism: deriving the scope

Work out the scope from the release diff, `git diff <previous deployed SHA> <release SHA>`, before the checks. A
feature is in scope when any of these holds:

1. **Directly changed.** The release changes the feature's route, template, page script or stylesheet, its service
   or FEAT, or the migration behind the table it writes.
2. **Connected.** The feature runs through something the release changes without being its subject: a shared
   layout, component, macro, script or stylesheet; a shared service, model or table; a dependency that the feature
   specifically uses (a payment, export or rendering library); or a new constraint on a table it writes.

   A **platform-wide** dependency, one every request passes through (the WSGI server, the database driver, the
   session or cryptography library, the cache client), does not pull every feature into scope. It is evidenced
   representatively: any feature the release exercises on that build ran through it. Record it as one row, with
   the requests that evidence it. A platform dependency puts a particular feature in scope only when its changelog
   names a change that feature relies on.
3. **Known problem.** The feature has an open defect report or support ticket, or the release fixes a reported
   defect in it.

Every in-scope feature gets a row. A feature outside the scope needs no row and is neither a known risk nor a
deviation. Name the checklist item from `SOP-DEP-001A` §VI where one fits; a feature with no matching item is named
in plain words.

## V.A Validation responsibility

1. Release validation is a development and operations responsibility. The operator, in the roles of `SOP-DEP-001`
   §XIII, runs every check this template requires, using test classes and test accounts created for the check.
   AI assistance is advisory there and here.
2. Teachers and students take no part in release validation. No check expects, requests or waits for an action by
   a teacher or a student, and the absence of such an action is never a gap, a known risk or a deviation.
3. Live classroom activity is never orchestrated to satisfy a release gate. No live class is used for a check, and
   no teacher or student is asked, prompted, scheduled or timed to act so that a release produces evidence. This
   holds when the operator also teaches a class: what the operator does in a live class as its teacher is classroom
   activity, not a check.
4. Classroom activity that happens in its own course is evidence like any other request on the release build. It
   may satisfy a required server-side check (§VI.5) for what it shows, labelled as live-class activity. It
   establishes no browser behaviour, and it is never arranged to produce evidence (§V.A.3). An operator who teaches
   and watches the tables or logs while doing so is still teaching: the activity is the class's, and any teacher's
   would show the same.

## VI. Mechanism: the checks

1. Where the release changes what a browser observes in an in-scope feature (its template, page script or
   stylesheet, or what a page renders or sends), exercise that feature in a real browser, behind the Access gate
   where the release keeps it restricted. The operator runs the check (§V.A).
2. Use a test class created for the check where the feature writes data, never a live class (`SOP-DEP-001` §XI.A).
   A test class destroyed by the check (a deletion test) needs no cleanup.
3. Where one action evidences several features, say so; a separate step per feature is not required.
4. Server-side evidence counts for what it shows: a request in the access log, a row in the database, a FEAT entry
   in the journal, a scheduled job's record. It establishes server behaviour only: that a request arrived, a row was
   written, a job ran. It does not establish what a page rendered, what a page's script sent or did, or how the
   interface behaved; those take a browser check.
5. Where the release changes a feature only on the server (a service, FEAT, scheduled job, guard or migration) and
   nothing a browser observes, the required check is server-side evidence, from the release build, of the changed
   behaviour itself: not only that a request arrived or a job ran, but that it took the path the release changed and
   produced the result the release asserts. Such a feature needs no browser check, and none is recorded as missing.
   A feature the release changes in both places needs both checks.
6. A row may also name the release-suite tests that cover the feature, with their result on the recorded suite run
   (`INV-ARC-017` §V.5). Suite evidence never makes a required browser or server-side check evidenced.

## VII. Results and the decision to open

A row keeps three things apart: who validated (always development and operations, §V.A), the type of evidence
(*browser*, *server-side*, *suite*), and the result. The required check follows what the release changed in the
feature: a browser check for what a browser observes (§VI.1), server-side evidence for what changed only on the
server (§VI.5), both where it changed both. Each in-scope feature takes
one result:

- *Evidenced*: the required check ran on the release build and the feature behaved as the release asserts.
- *In part*: some of what the release changes in the feature was evidenced and some was not. The row names which
  part each type of evidence covers, and what no evidence reached.
- *Failed*: the check ran and the feature did not behave as asserted. The row links the defect.
- *Blocked*: the required check could not be run, for a reason outside the application under test (a missing
  credential, an unavailable dependency, the Access gate). The row names the blocker.
- *Not exercised*: a required check the operator could have run and did not. A check this template does not
  require, including any action by a teacher or student, is never recorded as *not exercised*.

- A *failed* feature keeps the gate closed until it is fixed forward, rolled back, or the owner records why it opens
  anyway.
- *In part*, *blocked* and *not exercised* are recorded as known risks in the release record, with what covers them
  instead (a named test, a later check). Whether they are written before or after the gate opens does not matter:
  the operator knows what was exercised when deciding, and the order of recording changes neither the decision nor
  the outcome (owner ruling, 2026-10-22).

## VIII. Recording

Results may be recorded as the checks run or afterward, from contemporaneous evidence: the request log, the
database, the operator's notes or the session transcript. A row may not assert a result its evidence does not show,
and names what ran (route, action, status, build), not a verdict. The table is complete before the release record
merges. The release record under `docs/ops/audits/` carries:

| Feature | Why in scope | Evidence type | Result | Operator | Time (UTC) | Evidence or defect |
|---|---|---|---|---|---|---|
| | Direct / Connected / Known problem, naming the change | Browser / Server-side / Suite | | | | |

*Operator* names who ran the check, a development and operations role (§V.A). Live-class activity cited under
§V.A.4 is labelled as such in the evidence, with no operator.

## IX. Amendment

Revisions require incrementing the version, updating the effective date, and populating the Supersedes field.
A claim about codebase behaviour in this document must be verifiable against the release artifact at the time of
revision; where they disagree, the code wins and this document is corrected.

### Revision History

| Version | Date | Change |
|---------|------|--------|
| 1.2 | 2026-11-08 | The required check follows what the release changed, not what the feature has: a browser check where the release changes what a browser observes (§VI.1); server-side evidence of the changed behaviour itself, from the release build, where it changes the feature only on the server (§VI.5); both where it changes both. Server-side evidence must show the changed path and its result, not only that a request arrived. §V.A.4: classroom activity in its own course may satisfy a server-side check for what it shows; an operator who teaches while watching tables or logs is still teaching. Owner ruling, 2026-11-08 (v2.4.4 payroll). |
| 1.1 | 2026-11-08 | §V.A: release validation is a development and operations responsibility; teachers and students take no part, and live classroom activity is never orchestrated to satisfy a gate. §VI: a browser check for each in-scope feature with a browser surface; server-side evidence establishes server behaviour only, checks a feature with no browser surface, and never stands in for a browser check; suite tests may be named but never make a check evidenced. §VII: a row separates responsibility, evidence type and result; the result definitions are this template's own; *not exercised* is kept for a required check the operator could have run and did not. §VIII: an *Evidence type* column; *Owner* becomes *Operator*. Owner ruling, 2026-11-08 (v2.4.4). |
| 1.0 | 2026-10-22 | Extracted from `SOP-DEP-001` §XI (2.9) as the release template: scope from the release diff (directly changed, connected, known problem); out-of-scope features need no row; results recorded during or after the checks; known risks recorded without an ordering rule. Owner rulings, 2026-10-22. |
