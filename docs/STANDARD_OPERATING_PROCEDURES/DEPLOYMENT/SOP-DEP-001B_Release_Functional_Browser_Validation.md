# SOP-DEP-001B: Release Functional Browser Validation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DEP-001B     | 1.0     | 2026-10-22     | SOP-DEP-001 §XI (2.9), as applied to releases | Normative |

## I. Purpose

Define the browser validation for a release to a host that has already passed `SOP-DEP-001A`. A release
browser-checks the features it changes, the features connected to those changes, and features with a known
problem. The release's full test suite, not the browser, covers everything else.

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

## VI. Mechanism: the checks

1. Exercise each in-scope feature in a real browser, behind the Access gate where the release keeps it restricted.
2. Use a test class created for the check where the feature writes data, never a live class (`SOP-DEP-001` §XI.A).
   A test class destroyed by the check (a deletion test) needs no cleanup.
3. Where one action evidences several features, say so; a separate step per feature is not required.
4. Server-side evidence counts: a request in the access log, a row in the database, a FEAT entry in the journal.

## VII. Results and the decision to open

Each in-scope feature takes one result from `SOP-DEP-001A` §VII: *evidenced*, *in part*, *failed*, *blocked* or
*not exercised*.

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

| Feature | Why in scope | Result | Owner | Time (UTC) | Evidence or defect |
|---|---|---|---|---|---|
| | Direct / Connected / Known problem, naming the change | | | | |

## IX. Amendment

Revisions require incrementing the version, updating the effective date, and populating the Supersedes field.
A claim about codebase behaviour in this document must be verifiable against the release artifact at the time of
revision; where they disagree, the code wins and this document is corrected.

### Revision History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-10-22 | Extracted from `SOP-DEP-001` §XI (2.9) as the release template: scope from the release diff (directly changed, connected, known problem); out-of-scope features need no row; results recorded during or after the checks; known risks recorded without an ordering rule. Owner rulings, 2026-10-22. |
