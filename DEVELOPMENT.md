# Classroom Token Hub - Development Priorities

**Last Reviewed:** 2026-11-03 UTC
**Latest Recorded Application Deployment:** [v2.4.4 (`f530954`)](docs/ops/audits/DEPLOY_2026-11-08_f530954.md), 2026-11-08 UTC. This is release-record evidence, not a live production check
**Engineering State:** v2 in production; post-launch hardening
**Integration Target:** `main` (feature branches and worktrees may differ)

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
> were re-verified against `main` and filed as issues #1635–#1659 (two folded into #1505 and #1507).

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
  rebuilds it through the migration chain. Check previous results in `pytest_result/`, then run a targeted selection.
  The full suite runs nightly in [full-suite.yml](.github/workflows/full-suite.yml); request an
  owner-run full suite when broader validation is needed. Always set `TEST_DATABASE_URL` to a
  disposable local test database; see [CONTRIBUTING.md](CONTRIBUTING.md).
- New databases build step 0 from the frozen baseline `migrations/baseline/0001_baseline_schema.sql`
  (2026-09-28); model changes no longer reach the bootstrap.

## Git Hooks

Install the repository hooks once after clone:

```bash
./scripts/setup-hooks.sh
```

`hooks/post-checkout` rewrites `DATABASE_URL` in `.env` on every checkout. Check it before relying
on a custom database URL.

## Current State (2026-11-03)

### Released baseline

The latest application deployment record is [v2.4.4](docs/ops/audits/DEPLOY_2026-11-08_f530954.md).
It is a hotfix release: payroll runs again in the three classes it had refused since 2–3 November,
store items now expire, My Items lists only items a student can still use, and a double-clicked
purchase charges once. The record distinguishes what was verified at release from the student-side
store checks still awaiting live observation.

Recent releases also delivered Copy Configuration between classes, canonical temporal resolution,
Hugo + Hextra developer documentation, and the host-side production release gate. The application,
public/developer sites and status service have separate deployment workflows; the application
release record does not establish the deployed version of those other services.

Use [CHANGELOG.md](CHANGELOG.md) for the full version history and [deployment records](docs/ops/audits/)
for release-specific validation. Earlier releases' follow-ups are historical evidence, not a current
priority list. The six missing early release records remain tracked in
[#1650](https://github.com/timwonderer/classroom-token-hub/issues/1650).

### Open work

The [CTH Backlog](https://github.com/users/timwonderer/projects/6) is the working list. The following
issues were open when checked on 2026-11-03; this is a navigation snapshot, not a replacement for
issue status or an assertion that every proposed fix is implemented.

| Area | Open work |
| --- | --- |
| Latest release follow-ups | [#1698](https://github.com/timwonderer/classroom-token-hub/issues/1698): observe hall-pass day closure in live use; [#1699](https://github.com/timwonderer/classroom-token-hub/issues/1699): review the identified attendance record before payroll |
| Identity and sessions | [#1635](https://github.com/timwonderer/classroom-token-hub/issues/1635): GET/authentication and server-side logout; [#1636](https://github.com/timwonderer/classroom-token-hub/issues/1636): fixed teacher-session lifetime; [#1637](https://github.com/timwonderer/classroom-token-hub/issues/1637): identity-page authentication epoch |
| Financial correctness | [#1640](https://github.com/timwonderer/classroom-token-hub/issues/1640): settlement/FEAT lock order and interest dependency; [#1646](https://github.com/timwonderer/classroom-token-hub/issues/1646): simple-interest behavior; [#1667](https://github.com/timwonderer/classroom-token-hub/issues/1667): bill-cycle succession race |
| Operations and live verification | [#1639](https://github.com/timwonderer/classroom-token-hub/issues/1639): scheduled off-host backups; [#1657](https://github.com/timwonderer/classroom-token-hub/issues/1657): DST, load and rent checks (the November 1 DST transition has passed; verification remains open); [#1665](https://github.com/timwonderer/classroom-token-hub/issues/1665): Tailscale updates and node-key expiry |
| Retired behavior and documentation debt | [#1647](https://github.com/timwonderer/classroom-token-hub/issues/1647): remove NSF fee machinery; [#1678](https://github.com/timwonderer/classroom-token-hub/issues/1678): remove the retained bug-reward eligibility column; [#1651](https://github.com/timwonderer/classroom-token-hub/issues/1651): reconcile the documented Redis version requirement |
| Feature backlog | [#1701](https://github.com/timwonderer/classroom-token-hub/issues/1701): teacher-applied fine/deduction path; [#1510](https://github.com/timwonderer/classroom-token-hub/issues/1510): badges after architecture/documentation convergence |

The architecture convergence U-series (#1496–#1510) also remains open. Its scope includes identity,
monetary posting, domain ownership, presentation builders, deletion and normative-document
reconciliation. The architecture below describes the governing target; it is not a claim that
all conformance work is finished.

## v2 Technical Direction

- `users.id` (a UUID since v2.0.1) is the authentication principal.
- `seats.id` plus `classes.class_id` is the class-scoped runtime authority.
- `join_code` is a public class alias and must resolve to `class_id` before authority-sensitive work.
- Class-scoped reads and writes are seat/class-gated, never gated by teacher ownership alone, by
  `block`/`section`, or by any v1 identifier.
- Public actor identity uses UUID-encoded `Seat.public_id`.
- Adding students from a pasted roster provisions an unclaimed class-local `Seat`, a seat-bound `IdentityProfile`
  and seat-owned claim artifacts, without a `User` binding. Claim/setup later creates or binds the
  authentication principal. [INV-ARC-019 §XII](docs/INVARIANT/ARCHITECTURE/INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md)
  governs this distinction.
- Cloudflare Access gates application ingress during maintenance (DOM-OPS-001). The separate
  [host-side release gate](infra/release-gate/README.md) admits deployment only with the Access
  gate closed and fresh signed backup/restore evidence under
  [SOP-DEP-002](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-002_Production_Transition_Runbook.md).
- Use `db.session.get(Model, id)`, not `Model.query.get(id)`. `Query.get()` is banned in new
  development.

## Validation and Documentation

- Start with the relevant INV, DOM and FEAT contracts; SPEC requirements bind runtime behavior
  when incorporated by those contracts. Root README/development files summarize and do not
  establish new authority ([SOP-DOC-000](docs/STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md)).
- Use the canonical classroom initializer and `tests/helpers/temporal.py` for test setup and time
  ([SPEC-TEST-001](docs/SPEC/SPEC-TEST-001_CANONICAL_TEST_INITIALIZER.md)).
- For edits to these two root documents, check local links with
  `lychee --offline README.md DEVELOPMENT.md` and whitespace with `git diff --check`.
- Application help lives in `docs/user-guides/` and is served at `/docs`. Developer documentation
  is built from the allowlisted canonical tree by `docs-generator-proof/`; see its
  [build instructions](docs-generator-proof/README.md).

## Working Agreements

- Normative documents define the target state. When code and an `INV`/`DOM`/`FEAT` document
  disagree, the gap is a finding against the code.
- Every production release gets a dated record in `docs/ops/audits/` and a CHANGELOG section.
- Open work is an issue on the CTH Backlog project, closed by the PR that resolves it. A release record
  links its follow-up issues rather than describing open work in prose. When a document stops describing
  live work, archive it with a reason; don't delete it.
- Suite-green is not a launch signal on its own. The live-test campaign found defects in a real
  browser that no test was written to catch. Changes to user-facing flows get a browser pass.
