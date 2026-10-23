# Classroom Token Hub - Development Priorities

**Last Updated:** 2026-10-22 UTC
**Current Released Version:** 2.3.0 (`339c775cd`), deployed 2026-10-22 UTC. v2.0.0 launched 2026-09-26
**Engineering State:** v2 in production; post-launch hardening
**Active Integration Branch:** `main`

## Quick Links

- **[CTH Backlog](https://github.com/users/timwonderer/projects/6)** - The backlog: every open bug, operator follow-up, production check, dependency, cleanup and deferred feature is an issue on this project
- **[CHANGELOG](CHANGELOG.md)** - What changed, by release
- **[Core Invariants](docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md)** - Non-negotiable system laws
- **[Capability-Based Architecture and Authority Model](docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md)** - System design, the `INV → DOM → FEAT` hierarchy, and where authority lives
- **[Documentation Index](docs/STANDARD_OPERATING_PROCEDURES/SOP-DOC-001_DOCUMENTATION_INDEX.md)** - Every registered document by namespace
- **[Production Transition Runbook](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-002_Production_Transition_Runbook.md)** - How a release reaches production
- **[Release records](docs/ops/audits/)** - One dated record per production release
- **[Design Principles & Project History](docs/PRINCIPLES/PROJECT_PHILOSOPHY/PRN-PHL-001_Design_Principles_And_Project_History.md)** - Why the system is shaped the way it is

> [!NOTE]
> There is no tracker file. The pre-launch ship tracker (`PRODUCTION_READINESS_2026-09.md`) was archived
> on 2026-09-28, and the post-launch tracker (`POST_LAUNCH_TRACKER_2026.md`) on 2026-10-22, both to
> `docs/archive/v2-tracking-2026/`. They are history, not status. The post-launch tracker's open items
> were re-verified against `main` and filed as issues #1635–#1659.

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

## Current State (2026-10-22)

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
- **v2.1.1** (`2bdfac65e`, deployed 2026-10-04): attendance correction
  (#1477, with three forward-only migrations), store redemption decisions (#1473), the POST-only sysadmin
  logout (#1482) and the #1478/#1479 performance fixes. See the `[2.1.1]` section of the CHANGELOG and
  `docs/ops/audits/DEPLOY_2026-10-04_2bdfac65e.md`; the same window updated the host kernel and took the
  first restore-verified backups. Two checks are still open: hall passes in a real class on one worker,
  and the first automatic payday on 2026-10-10. Restoring two workers waits on the first (SOP-DEP-001 v2.6).
- **Untagged releases, 2026-10-05 and 2026-10-06.** `381a12d49` (#1485, #1486, #1488;
  `docs/ops/audits/DEPLOY_2026-10-04_381a12d49.md`), `35bad089a` (#1489) and `1cdbf03da` (#1491). The last
  two have no release record.
- **v2.2.0** (`5ebae62db`, deployed 2026-10-09): a store purchase needs the
  money and a collective goal is one buy-in per student (#1526), collective-goal purchases and the NSF fee
  can be reversed (#1526), hall passes require teacher settings (#1522), the per-render cross-class payroll
  query is gone (#1527), and the sysadmin log viewers are removed (#1528). No migration. See the `[2.2.0]`
  section of the CHANGELOG and `docs/ops/audits/DEPLOY_2026-10-09_5ebae62db.md`.
- **v2.2.1** (`f98d8a206`, deployed 2026-10-10). Purchased hall passes can be
  reversed, using a pass writes only the hall-pass log, a pass with a request waiting is reserved, and an item
  with a request waiting can't be reversed (#1530). Migration `35a9a0d3ab93` makes a pass spendable once. See
  the `[2.2.1]` section of the CHANGELOG and `docs/ops/audits/DEPLOY_2026-10-10_f98d8a206.md`. Next: the NSF
  fee machinery is retired in a later release.
- **v2.2.2** (`61b509b7f`, deployed 2026-10-11): stored XSS in hall passes and announcements fixed (#1535,
  GHSA-7fxj-gpw3-23g3), on top of the untagged `c2f16fb11` hotfix (#1532). No migration. See
  `docs/ops/audits/DEPLOY_2026-10-11_61b509b7f.md`.
- **v2.2.3** (`5d29abb41`, deployed 2026-10-12): the 2026-10-10 audit remediation (security S3, S5, S7–S10;
  financial F1–F10; operational O1–O5, O8) and the CodeQL `security-extended` backlog fixes. Migration
  `6a01dc7a606b` makes obligation assessment replay-safe. See the `[2.2.3]` section of the CHANGELOG and
  `docs/ops/audits/DEPLOY_2026-10-12_5d29abb41.md`.
- **v2.2.4** (`68ead4230`, deployed 2026-10-16): insurance descriptions before purchase, marketing badges and the
  Economic Engine premium suggestion (#1587); editing a policy moves its holders to the new version at renewal,
  and hiding or retiring one ends coverage at the boundary (#1588). Includes the untagged `79cbb2615` (#1559,
  #1564). Migrations `e5b7c9d1f3a4` and `f6c8d0e2a4b5` add two nullable insurance-policy columns. See the
  `[2.2.4]` section of the CHANGELOG and `docs/ops/audits/DEPLOY_2026-10-16_68ead4230.md`.
- **Untagged `03a6feed2`** (deployed 2026-10-16): the insurance premium suggestion shows monthly rent as billed
  on a monthly policy, not rescaled over 30 days (#1592), found by the v2.2.4 browser checks. No migration. See
  `docs/ops/audits/DEPLOY_2026-10-16_03a6feed2.md`.
- **v2.3.0** (`339c775cd`, deployed 2026-10-22): in-app dialogs replace the browser's own, and the delete safety
  gate is readable by screen readers (#1626); Delete Class works again and the status page no longer reports a
  false outage (#1624); Ledger provenance by mechanism and a closed transaction type vocabulary (#1596 to #1600);
  contextual-help corrections (#1619 to #1622). Migration `a4d7e9c2f1b6` adds a `NOT VALID` CHECK constraint on
  `ledger_transaction.type`. See the `[2.3.0]` section of the CHANGELOG and
  `docs/ops/audits/DEPLOY_2026-10-22_339c775cd.md`.
- All ten domains (Identity, Class Configuration, Ledger, Productivity & Payroll, Obligations,
  Store & Entitlements, Operations, Interpretation, Policies, Support) run on the v2 model:
  `User` → `Seat` → `IdentityProfile`, with `ClassEconomy.class_id` as the tenant boundary and
  every mutation through a FEAT.

### Next

The [CTH Backlog](https://github.com/users/timwonderer/projects/6) project is the working list; this section only names what is most pressing.

1. **Identity sessions against DOM-IDEN.** Logout must end the server-side session and no auth page may change
   the session on GET (#1635); the teacher session is a 10-minute idle timeout where DOM-IDEN-003 requires a
   fixed 60 minutes (#1636).
2. **Production checks before they bite.** DST ends 2026-11-01 (#1657); off-host backups are still manual
   (#1639).
3. **Ledger correctness.** The settlement/FEAT lock-order deadlock and its effect on interest (#1640).
4. **Architecture convergence.** The U-series issues (#1496–#1510).

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
- Open work is an issue on the CTH Backlog project, closed by the PR that resolves it. A release record
  links its follow-up issues rather than describing open work in prose. When a document stops describing
  live work, archive it with a reason; don't delete it.
- Suite-green is not a launch signal on its own. The live-test campaign found defects in a real
  browser that no test was written to catch. Changes to user-facing flows get a browser pass.
