# Release record (draft): v2.1.1, `c57dadf`

> **Draft, prepared before deployment.** Sections marked *To record at release* are empty on purpose: they hold
> evidence that only exists once the operator deploys. At release, fill them in and rename this file to
> `DEPLOY_<YYYY-MM-DD>_c57dadfc3.md`, matching the other records in this directory.

**Type:** Tagged release under `SOP-DEP-002`. No migrations. It tags as v2.1.1 everything merged to `main` from
v2.1.0 through #1476, and ships to production the changes merged after the untagged 2026-10-03 release
(`ad9574334`). It is cut from `c57dadf`, the last commit before #1477, so the four forward-only attendance
correction migrations in #1477 are not part of it.

## Release identity

| | |
|---|---|
| Release SHA | `c57dadfc3e39b0a7a85d1ecbb797dd7dcfe0e5e1` (merge of #1476), to be tagged `v2.1.1` |
| GitHub release | *To record at release* |
| Branch / lineage | `main` (`lineage_ref=main`). `c57dadf` is an ancestor of `main` (`66343d1`, merge of #1477). |
| Previous deployed SHA | `ad9574334d72fd92cc93402e851ab0ebc22aaad9` (untagged), Alembic revision `a4b50fee84c3`; record [DEPLOY_2026-10-03_ad9574334.md](DEPLOY_2026-10-03_ad9574334.md) |
| Release run | *To record at release* |
| Triggered by | *To record at release* |
| Verifier | *To record at release* |

### Why this release

Two fixes from 2026-10-02 production observations are merged and not yet live:

- **Student names in the application log (#1472, Security).** Bulk hall-pass adjustments wrote each adjusted
  student's full name to the journal at INFO. Every day the release waits, new adjustments add names.
- **Store redemptions cannot be decided (#1473).** Approving a delayed-use redemption, and every immediate-use
  redemption through `/api/use-item`, answers 500 and the request stays waiting.

### Contents since `ad9574334`

Every PR below is merged, and its merge commit is an ancestor of `c57dadf` and not of `ad9574334`.

| PR | Change |
|---|---|
| #1471 | Documentation: the 2026-10-03 deployment record. |
| #1472 | No student names in application logs (bulk hall-pass adjustment logs `seat_id` and `class_id` only, plus a structural guard); each log line is written once instead of twice. |
| #1473 | Economy > Store gets one Redemptions tab; a request can be decided Accept, Deny or Return, each final (DOM-STORE-001 5.4 §VIII.E.4); immediate-use purchases queue a *Mark as complete* reminder. |
| #1474 | Store bundles are removed; a pack is a purchase quantity at a bulk price. Code only: the two `store_products` columns stay. |
| #1475 | The payroll page renders one Run Payroll button, so its id is unique (INV-ARC-020). |
| #1476 | Login page notice posted or cleared from the manual **Login page notice** workflow. |

Two commits outside a PR: `69bc370` adds `.codex/environments/environment.toml` and a `.gitignore` line (developer
tooling, not deployed behavior), and `7658d12` merges it.

Application paths changed: `app/__init__.py`, `app/feats/collective_goal_expiry_feat.py`,
`app/feats/entitlement_lifecycle_feat.py`, `app/feats/store_purchase_feat.py`, `app/feats/transaction_void_feat.py`,
`app/forms.py`, `app/models.py`, `app/routes/admin.py`, `app/routes/api.py`, `app/routes/student.py`,
`app/services/entitlement_read_service.py`, `app/services/entitlement_service.py`,
`app/services/redemption_query_service.py` (new), `app/services/store/builders.py`,
`app/services/store/form_contract.py`, `app/services/store_policy_resolver.py`, `app/services/store_service.py`,
`app/services/view_model_builders.py`, `app/utils/login_notice.py` (new), `static/css/style.css`,
`static/js/store_item_type_gating.js`, and the templates `admin_dashboard.html`, `admin_edit_item.html`,
`admin_login.html`, `admin_payroll.html`, `admin_store.html`, `macros/login_notice.html` (new),
`student_detail.html`, `student_login.html`, `student_shop.html`. Workflow added: `.github/workflows/login-notice.yml`.

### Not part of this release

- **#1477, attendance interval invalidation and historical payroll correction.** Merged to `main` after `c57dadf`,
  with four forward-only migrations (`d6b1e0c4a825`, `e7c2a9d4f610`, `f8b2d6e0a410`, `f9a3c7d1e620`) that need a
  read-only production preflight. It goes in a later release.
- **The sysadmin logout change** (logout by POST with CSRF). Not merged when this candidate was cut; it lands on
  top of #1477 and ships with it.
- Carried from earlier records: the status service and host sampler from #1467, and the nginx snippet from #1446.

## §VI pre-release checks

| Check | Result |
|---|---|
| Release SHA on `main`, descendant of the running release | PASS (checked 2026-10-04 with `git merge-base --is-ancestor`): `ad9574334` is an ancestor of `c57dadf`, and `c57dadf` is an ancestor of `origin/main`. |
| Running release before dispatch | *To record at release* (expected host `HEAD` `ad9574334`) |
| Migrations changed since the running release | None. `git diff ad9574334 c57dadf -- migrations/` is empty; production and `c57dadf` share head `a4b50fee84c3`. |
| `requirements.txt` changed | No |
| New configuration | `LOGIN_NOTICE_PATH` (optional; unset means `instance/login_notice.json`). Nothing to set for this release. |
| Student-setup memory store (§VI item 6) | *To record at release* |
| Full suite on the release SHA | *To record at release.* Not run while preparing this draft. |
| CI on the release commit | Push runs on `c57dadf`: Policy Guardrails, Lint Workflows, Deploy GitHub Pages Site and Documentation Link Checks passed. |
| Backup | *To record at release.* No migration runs, so the schema does not change; whether a fresh dump is taken is the operator's call, as on 2026-10-03. |

## Release run

*To record at release.*

## §VIII post-release verification

*To record at release.* Beyond the standard host checks (revision, service, health, scheduler, database revision
`a4b50fee84c3` unchanged, errors since start), this release has these specific checks:

- **#1472:** service journal lines appear once each, with no `INFO:app:` duplicates after the first passkey sign-in.
- **#1473:** Economy > Store shows the Redemptions tab; a waiting redemption in a real class can be decided without
  a 500.
- **#1476:** the student and teacher login pages render with no notice file present.
- **Carried over:** the first automatic payday, 2026-10-10; hall-pass reject and cancel in production; #1469's
  `TLCP-SURFACE-PRINCIPAL-MISMATCH` line not yet observed.

## Rollback

Release `ad9574334` through the same workflow. No migration separates the two revisions, so no database step is
needed. Two data effects survive a rollback, both display only:

- An item a teacher **denied** under v2.1.1 carries a `REVOKED` event. The previous code counts it out of the
  student's remaining units, so the item stays gone, but labels it as used.
- An **immediate-use reminder** (`pending_actions` row written through FEAT-STOR-002 for an immediate-use purchase)
  matches the previous code's pending-redemption queries (`authoritative_feat = 'FEAT-STOR-002'`, no `outcome`), so
  it would show on the old dashboard and store page as a pending redemption the old buttons cannot resolve.
