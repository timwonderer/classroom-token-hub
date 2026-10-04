# Classroom Token Hub - Development Priorities

**Last Updated:** 2026-10-04
**Current Released Version:** 2.1.1 (`2bdfac65e`), the latest tag, deployed to production 2026-10-04. v2.0.0 launched 2026-09-26
**Engineering State:** v2 in production; post-launch hardening
**Active Integration Branch:** `main`

## Quick Links

- **[Post-Launch Tracker](docs/TRACKING/POST_LAUNCH_TRACKER_2026.md)** - The tracker of record: operator follow-ups, surfaces not yet exercised in production, code hygiene, dependencies, deferred features
- **[CHANGELOG](CHANGELOG.md)** - What changed, by release
- **[Core Invariants](docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md)** - Non-negotiable system laws
- **[Capability-Based Architecture and Authority Model](docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md)** - System design, the `INV → DOM → FEAT` hierarchy, and where authority lives
- **[Documentation Index](docs/STANDARD_OPERATING_PROCEDURES/SOP-DOC-001_DOCUMENTATION_INDEX.md)** - Every registered document by namespace
- **[Production Transition Runbook](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-002_Production_Transition_Runbook.md)** - How a release reaches production
- **[Release records](docs/ops/audits/)** - One dated record per production release
- **[Design Principles & Project History](docs/PRINCIPLES/PROJECT_PHILOSOPHY/PRN-PHL-001_Design_Principles_And_Project_History.md)** - Why the system is shaped the way it is

> [!NOTE]
> The pre-launch ship tracker (`PRODUCTION_READINESS_2026-09.md`) and the other launch-era working
> documents were archived on 2026-09-28 to `docs/archive/v2-tracking-2026/`. They are history, not
> status. Their open items were re-verified against the code and carried into the post-launch
> tracker.

## Branch and Database Truth

- `main` is the active protected branch and carries v2. It is the same branch that older
  documents and CHANGELOG entries call `codex/v2.0` and then `CTH_v2.0`; both names were
  retired and no ref by either exists locally or on the remote. Read historical references
  accordingly rather than looking for a second branch.
- The v1 `main` that preceded this was renamed on 2026-09-07 and now lives at
  `main_legacy_v1.10.0`. The separate `legacy_v1.10.0` ref no longer exists; its tip
  (`1f7bfeb40`) is contained in `main_legacy_v1.10.0`, so **`main_legacy_v1.10.0` is the single
  ref carrying the v1 line**. All `v1.*` tags remain. CHANGELOG entries that say "never merge to
  `main`" describe the former v1 branch, not this one.
- Tests run against a real PostgreSQL database named by `TEST_DATABASE_URL`, and `conftest.py`
  rebuilds it through the migration chain. The full suite (about 3,900 tests) takes over an hour
  and runs nightly in `full-suite.yml`.
- New databases build step 0 from the frozen baseline `migrations/baseline/0001_baseline_schema.sql`
  (2026-09-28); model changes no longer reach the bootstrap.

## Git Hooks

Run once after clone:

```bash
./scripts/setup-hooks.sh
```

`hooks/post-checkout` rewrites `DATABASE_URL` in `.env` on every checkout. Check it before relying
on a custom database URL.

## Current State (2026-10-04)

### In production

- **v2.0.0** (`26d1792b5`) launched 2026-09-26 on a wiped database, after a live-test campaign on
  the same host (2026-09-19 → 2026-09-26).
- **v2.0.1** (`ad64a473f`, 2026-09-28) is a security release. Each passkey now signs in only the
  account it was registered to, and `users.id` is a random UUID. It also fixes teacher support
  tickets, runs the scheduler in exactly one process, and removes 19 unused routes.
- **Untagged releases, 2026-09-29.** `bc5c07a2` fixes the payroll incident of 2026-09-28: each run pays
  finished work sessions only, each exactly once (#1439). `eaca2a7e` adds a one-time payroll correction
  that teachers review, open until 2026-10-31 (#1440). `29b99b14` and `00166e56` add the username
  retention check, with setup state held only in a dedicated, non-persistent Redis (#1442, #1443).
  None of these has a release record yet.
- **Untagged release, 2026-09-30.** `314158d53` pays savings interest at the teacher's configured
  cadence by the daily balance method (#1449), with #1438 and #1451.
  See `docs/ops/audits/DEPLOY_2026-09-30_314158d53.md`.
- **v2.1.0** (`5ac05ea6f`, deployed 2026-10-02). It collects everything since v2.0.1, including the
  untagged releases above; see the `[2.1.0]` section of the CHANGELOG and
  `docs/ops/audits/DEPLOY_2026-10-02_5ac05ea6f.md`.
- **Untagged releases, 2026-10-03 and 2026-10-04.** `ad9574334` (#1470 and the changes merged after
  v2.1.0; `docs/ops/audits/DEPLOY_2026-10-03_ad9574334.md`) and the hotfix `4c2fc4bc4` (#1476, off `main`).
- **v2.1.1** (`2bdfac65e`, deployed 2026-10-04). Production runs this release: attendance correction
  (#1477, with three forward-only migrations), store redemption decisions (#1473), the POST-only sysadmin
  logout (#1482) and the #1478/#1479 performance fixes. See the `[2.1.1]` section of the CHANGELOG and
  `docs/ops/audits/DEPLOY_2026-10-04_2bdfac65e.md`; the same window updated the host kernel and took the
  first restore-verified backups. Two checks are still open: hall passes in a real class on one worker,
  and the first automatic payday on 2026-10-10. Restoring two workers waits on the first (SOP-DEP-001 v2.6).
- All ten domains (Identity, Class Configuration, Ledger, Productivity & Payroll, Obligations,
  Store & Entitlements, Operations, Interpretation, Policies, Support) run on the v2 model:
  `User` → `Seat` → `IdentityProfile`, with `ClassEconomy.class_id` as the tenant boundary and
  every mutation through a FEAT.

### Next

The post-launch tracker is the working list. In priority order:

1. **Operator follow-ups.** Record the 2026-09-29 releases contained in v2.1.0, apply the Grafana nginx
   snippet, check the remaining public routes, and work through the follow-ups in the v2.1.1 record. The
   student-setup Redis host settings were confirmed on 2026-10-04.
2. **First real use.** Signed-in flows other than teacher passkeys, rent payment (its preview
   window opens 2026-09-29), daylight-saving transitions and load have not yet run in production.
3. **Dependencies.** Twelve open Dependabot PRs have been reviewed, with a suggested merge order. CI
   on a pip bump does not run the application suite, so run it before merging.
4. **Hygiene.** Dead imports and deprecated waiver helpers, the `Seat.block` shim, an unused
   `app/utils/deletion.py`, and two rent-disablement tests still to confirm.
5. **Architecture.** Reconstruct the historical migration baseline so the two `SOP-DB-001` §V.B
   corrections are no longer load-bearing.
6. **Deferred features.** The bug-hunter badge system (needs SPEC renumbering) and the
   support-content registry (pairs with accessibility work).

## v2 Technical Direction

- `users.id` (a UUID since v2.0.1) is the authentication principal.
- `seats.id` plus `classes.class_id` is the class-scoped runtime authority.
- `join_code` is a public class alias and must resolve to `class_id` before authority-sensitive work.
- Class-scoped reads and writes are seat/class-gated, never gated by teacher ownership alone, by
  `block`/`section`, or by any v1 identifier.
- Public actor identity uses UUID-encoded `Seat.public_id`.
- Roster upload provisions an inactive `User`, a class-local `Seat`, a seat-bound
  `IdentityProfile` and seat-owned claim artifacts. It does not create an authenticated student.
- Cloudflare Access, not the application, gates access during maintenance (DOM-OPS-001).
- Use `db.session.get(Model, id)`, not `Model.query.get(id)`. `Query.get()` is banned in new
  development.

## Working Agreements

- Normative documents define the target state. When code and an `INV`/`DOM`/`FEAT` document
  disagree, the gap is a finding against the code.
- Every production release gets a dated record in `docs/ops/audits/` and a CHANGELOG section.
- Update the post-launch tracker in place and record each closure with its commit SHA. When a
  document stops describing live work, archive it with a reason; don't delete it.
- Suite-green is not a launch signal on its own. The live-test campaign found defects in a real
  browser that no test was written to catch. Changes to user-facing flows get a browser pass.
