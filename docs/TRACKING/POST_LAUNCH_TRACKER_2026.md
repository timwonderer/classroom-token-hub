# CTH v2 Post-Launch Tracker

| Field | Value |
|---|---|
| Status | **ACTIVE — canonical tracker** |
| Opened | 2026-09-28, after the v2.0.1 release |
| Baseline commit | `c42f882` (`main`) |
| Production | `v2.0.1` = `ad64a473f`, released 2026-09-28 |
| Supersedes | `PRODUCTION_READINESS_2026-09.md`, the pre-launch ship tracker, archived at `docs/archive/v2-tracking-2026/` once launch closed its purpose |

This file carries the open work that survived launch. Every item was checked against the code on
the date shown. Where an item is marked *verified*, the cited file and line held the described state
on that date; re-check before acting, because this file is descriptive and can drift. Normative
authority stays with `INV-*`, `DOM-*`, `FEAT-*`, `SPEC-*` and `SOP-*`.

---

## I. Release state

| Release | Commit | Date | Record |
|---|---|---|---|
| v2.0.0 | `26d1792b5` | 2026-09-26 | [TRANSITION_2026-09-26_26d1792b5.md](../ops/audits/TRANSITION_2026-09-26_26d1792b5.md) |
| (untagged) | `4f9854fca` | 2026-09-27 | [DEPLOY_2026-09-27_4f9854fca.md](../ops/audits/DEPLOY_2026-09-27_4f9854fca.md) |
| (untagged) | `efdf09eda` | 2026-09-27 | Covered by the v2.0.1 record |
| v2.0.1 (security) | `ad64a473f` | 2026-09-28 | [DEPLOY_2026-09-28_ad64a473f.md](../ops/audits/DEPLOY_2026-09-28_ad64a473f.md) |

---

## II. Operator follow-ups from the v2.0.1 release

- [ ] **Lift the Cloudflare Access window** and post the resolved status update. The update should
  say that everyone was signed out once and that passkeys must be registered again. Passkey
  registration and sign-in are verified, so nothing blocks this.
- [ ] **Publish the security advisory** (drafted on GitHub; CVSS v4.0 9.2; CWE-304 with CWE-386 and
  CWE-459), then link it from the `[2.0.1]` section of `CHANGELOG.md`.
- [ ] **Check public routes** once the window lifts. They were not verified at release because the
  gate was in place.
- [ ] **FEAT-IDEN-003 `ACT-IDEN-003` audit event** is not implemented. It needs an identity
  audit-event design first; see #1427.
- [x] **`production-docs-smoke` and `markdown-web-links`** are fixed on branch
  `claude/repo-maintenance-ci-fixes-uq01eh` (2026-09-28). Optional: create a Cloudflare Access
  service token and store it as the `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET` repository
  secrets, so the production docs crawl can run during a maintenance window instead of failing.

---

## III. Not yet exercised in production

Evidence that was run is not coverage that was inferred (INV-ARC-017).

- **Signed-in flows other than teacher passkeys** have not been repeated on production since the
  launch wipe. They run for the first time when teachers start using the app.
- **Rent payment.** Rent reconciliation, genesis, advance and policy binding were exercised during
  live test, but payment was not. The live-test class's preview window opens 2026-09-29.
- **Daylight-saving and midnight transitions.** Class-timezone handling is tested, but no live
  daylight-saving change has happened since launch.
- **Load.** Concurrent settlement, payroll batches and scheduled jobs have not been tested under load.
- **Browser accessibility beyond axe.** Keyboard, focus and contrast behaviour across the whole app
  still need a person using a real browser. The signed-in insurance buy and cancel dialogs have not
  had an axe audit.

---

## IV. Code hygiene (carried from the pre-launch non-blocking findings)

Each item was verified on 2026-09-28 unless it says otherwise.

| Area | Item | Where |
|---|---|---|
| Class Configuration | `replace_enabled_class_features` is imported and never used | `app/routes/admin.py:96` |
| Identity | The `Seat.block` read-through property onto `ClassEconomy.section` remains for legacy admin rendering. `block` is display metadata only (INV-ARC-014) | `app/models.py:293-300` |
| Identity | `app/utils/deletion.py` has no importer in `app/` or `scripts/`. Only a test docstring and a migration comment mention it; `app/utils/student_deletion.py` is the live module | `app/utils/deletion.py` |
| Obligations | `get_active_rent_waivers_for_class` is marked DEPRECATED ("'active waiver' is not a lawful concept", DOM-OBL-001 §V.6) and has no caller. Neither does its `RentWaiverView` projection | `app/services/obligations_service.py:1266` |
| Obligations | `_count_rent_waiver_periods` has no caller | `app/routes/admin.py:859` |
| Obligations | Waiver-history expansion still steps periods from policy settings (display only) | follow-up from insurance slice 3 |
| Ledger | `Transaction.join_code` remains as a nullable, indexed column documented as ingress/display metadata. No domain query may filter on it | `app/models.py:478` |
| Productivity | `AttendanceReasonCode` has no `daily_limit` member (`hall_pass`, `done_for_day`, `start_work`). Confirm whether the daily-limit auto tap-out needs one before adding it | `app/models.py:72-76` |
| Productivity | Payroll reversal correlation is heuristic | not re-verified |
| Access policy | `assert_can_void_transaction` has no caller and reads `transaction.teacher_id`, a column `Transaction` does not have. Delete it, or rewrite it on `class_id` before any use | `app/services/access_policy_service.py:91-104` |
| Scripts | `verify_runtime_session_attacks.py` imports the retired `Student` model and cannot run | `scripts/adversarial/verify_runtime_session_attacks.py:13` |

**Closed since the pre-launch list:** the teardown helpers left `app/routes/admin.py` for
`app/services/teacher_destruction.py`, `context_resolver.py` has no `print()` calls left,
`StoreItem` is gone (single `StoreProduct` catalog), and `update_user_report` is gone.

---

## IV-A. Contract gaps and decisions (found 2026-09-28, amending FEAT-IDEN-001/002)

- [ ] **`ACT-IDEN-001` / `ACT-IDEN-002` audit events are not emitted.** FEAT-CORE-000 §III.4 requires an
  audit record for every FEAT execution. FEAT-IDEN-001 v3.0 §VI and FEAT-IDEN-002 §VII specify them;
  `app/feats/identity_feat.py` emits neither. This is the same gap as `ACT-IDEN-003` (#1427); design them
  together.
- [ ] **Decision: student login credential.** DOM-IDEN-002 §VII (Constitutional) says students log in with
  username and **PIN**. The code (`student.login`) and FEAT-IDEN-002's credential table ("fixed and
  normative") use the **passphrase**. Either amend DOM-IDEN-002 §VII to the passphrase, or change the code.
  FEAT-IDEN-002 §IV.1 still says "username and PIN" and is left for this decision.
- [ ] **Decision: tier of `docs/REFERENCE/`.** SOP-DOC-000 v3.3 leaves it unassigned. `REF-TERM-001` and
  `REF-TERM-002` declare themselves Normative; `REF-API-001` and `REF-DES-001` are descriptive.

---

## V. Tests to confirm

The rent-disablement list ratified on 2026-09-24 is mostly covered by
`tests/dom/obligations/test_rent_disablement_surviving_state.py`. There are eight tests: untouched
advance withdrawal, perks for a period paid in advance, reconciliation creating nothing while rent
is disabled, late fees continuing, paying off surviving rent not re-enabling rent, the rent page
reachable or absent, and late fees following the frozen policy. No test was found by name for
these two cases:

- [ ] disabling rent during a **partly paid** preview period (the committed part stays, the
  remainder is payable, late fees continue);
- [ ] a **policy-B preview change does not move a cycle created under policy A** (mutation-tested).

---

## VI. Architecture

- [ ] **Frozen migration baseline, reconstruction.** On 2026-09-28 the freeze landed:
  `0001_bootstrap` executes `migrations/baseline/0001_baseline_schema.sql`, and model changes no
  longer reach step 0. What remains is a baseline that reconstructs the schema each historical
  migration was written against. Until then, the two `SOP-DB-001` §V.B Bootstrap-Replay Corrections
  (`3a69db4907b4`, `8f1a2c3d4b5e`) are load-bearing. Evidence:
  [BASELINE_FREEZE_2026-09-28.md](../ops/audits/BASELINE_FREEZE_2026-09-28.md).

---

## VII. Dependencies

- [ ] **Dependabot has no `npm` entry for `/docs-site`.** `.github/dependabot.yml` declares only
  `pip` and `github-actions` at `/`, so the alerts raised against `docs-site/package-lock.json` can
  never become update PRs. That lock file is build tooling for the developer docs site; it is not
  shipped with the application.
- [ ] **Open Dependabot PRs.** They were reviewed on 2026-09-28 and all kept. The suggested merge order
  is:
  1. low-risk: #1416 packaging, #1415 SQLAlchemy/greenlet patch, #1417 playwright, #1414 actionlint
     action, #1413 setup-node;
  2. #1381 redis;
  3. #1419 alembic with #1374 Mako. Rehearse `flask db upgrade` and `flask db downgrade <rev>` first;
  4. #1380 gunicorn. Since 26.1 it rejects duplicate Host/Content-Type headers with a 400, so watch the
     400 rate;
  5. #1378 google-auth with #1418 firestore (status service; merging deploys it);
  6. #1371 with #1372, the GCP actions v3 pair (the first deploy after merge is the real test).

  CI on pip bumps does not run the application test suite, so a green PR is not evidence that the
  app works with the new pin. Closed as superseded or obsolete: #1382, #1384, #1391 and #1411.

---

## VIII. Deferred features

- **Bug-hunter badge system.** Design only (`DOM-OPS-003`, two badge SPECs, nine SVGs), preserved at
  tag `archive/bug-hunter-badges-20260914`. Before it can land, the badge SPECs must be renumbered,
  because `SPEC-OPS-001` is already `SPEC-OPS-001_REVERSAL_AND_VOID.md`.
- **Support-content registry.** Would move user-facing help text out of templates into versioned
  content files (INV-CORE-000 §III.7). It touches every template, so it belongs with the
  accessibility work.

---

## IX. Maintenance

Amend this file when an item changes state, and record each closure with its commit SHA. Dated
snapshots of finished work belong in `docs/archive/v2-tracking-2026/` (archived material). Release
and audit records belong in `docs/ops/audits/`.
