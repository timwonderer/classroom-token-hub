# v2 Production Transition Runbook

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DEP-002 | 1.15 | 2026-10-22 | 1.14 | Normative |

> [!IMPORTANT]
> **v1.11 (2026-10-14), documentation modernization.** §VIII and §X's verification checklist cited verification routes by `join_code`: `/admin/export-students?join_code=<owned-join-code>` and `POST /student/switch-class/<join_code>`. Checked against the live routes — `/admin/export-students` takes no query parameter at all (the class comes from the admin's session/sidebar context via `_resolve_admin_class_context`), and `/student/switch-class/<class_id>` takes `class_id` as its path parameter, not `join_code`. Corrected both to match, bringing this document in line with `SOP-DEP-001` §XI, which already states the canonical route takes `class_id` and that `join_code` there is the retired alias form.

## I. Purpose

Provide the explicit operator workflow for moving the current v2 branch from live-test candidate to production transition.

## II. Scope

Production transition work for `main` after successful live testing, including Cloudflare Access gating, migration execution, post-deploy verification, rollback decision points, and operator sign-off.

## III. Authority Level

Normative (SOP Tier). Subordinate to `INV-CORE-000`.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `SOP-DB-004_Live_V2_Migration_And_Versioning_Contract.md`
- `SOP-DEP-001_Live_Test_Runbook.md`

## V. Preconditions

- `main` is the approved deployment branch.
- Live-test runbook has been executed successfully.
- Migration compliance status has been reviewed.
- Backup, maintenance window, and rollback contacts are confirmed.
- Team-owned production and pre-production database targets are identified before any migration step begins.
- Named production operator, independent verifier, and rollback approver are assigned before the maintenance window starts.

### V.1 Single-maintainer limitation

This project has one maintainer. The GitHub `production` environment therefore has **no required reviewers**: its
only protection is a deployment branch policy that limits deploys to `main` (verified 2026-10-13). A release
dispatch is not gated by a second person's approval in GitHub. Where this runbook refers to environment
approval (§IX.1), it means the environment's branch policy plus the operator's own go-ahead, recorded under the
solo-operator exception (`SOP-DEP-001` §XIII); it is not independent review. Each release record states this.
When a second maintainer joins, add them as required reviewers on the `production` environment and remove this
subsection.

## VI. Pre-Production Checklist

1. Enable Cloudflare Access gating if the deployment requires a protected window.
2. Verify current production backup or snapshot and test restore instructions.
3. Confirm migration head state and target revision.
4. Confirm operator sign-off from engineering and operations.
5. Reconfirm smoke checklist and escalation path.
6. Confirm the student-setup memory store is running on the production host. The username-retention check
   (FEAT-IDEN-002, SPEC-IDEN-001; memory-only under INV-ARC-018 §IX) has needed it since release `29b99b14`
   (2026-09-29). On a new or rebuilt host, provision and verify it per `infra/student-setup/README.md`, set
   `STUDENT_SETUP_REDIS_URL` in the application environment, and restart the workers. There is no fallback: without the store, student claim and
   recovery setup fail closed with a 503. After the release, exercise claim and recovery setup as that
   README's step 6 describes.

Current branch verification references:

- access gate: Cloudflare Zero Trust policy for the application hostname
- release workflow: `.github/workflows/release-v2.yml` (manual exact-SHA release)
- deployment transport: GitHub Actions connects to the production host through
  Tailscale using `PRODUCTION_TAILSCALE_HOST`; public-IP SSH is not the
  approved deployment path;
- transport smoke test: `.github/workflows/tailscale-ssh-smoke-test.yml`
- migration safety check: `bash scripts/check-migrations.sh`

The production release lineage is configured as the protected environment
variable `V2_RELEASE_LINEAGE_REF`. A release request MUST provide a full
40-character commit SHA that is an ancestor of that approved lineage. A branch
name or moving branch tip is not itself a release artifact.

### Cloudflare Access gate verification

Before a restricted work window, confirm an unauthenticated browser reaches Access,
an unauthorized identity cannot enter, and an authorized operator can reach the
normal application sign-in. Verify the origin cannot be reached around Cloudflare.
Public health probes require authorized service-token headers; host-local probes
do not traverse Access. Never record tokens in logs or deployment evidence.

At the end of the window, change the Access policy only when public access is
intended and release checks have passed. Deploying the app does not change that
policy. Remove obsolete `MAINTENANCE_*` settings from deployment configuration;
there is no application flag, sysadmin bypass, or query-token alternative.

## VII. Upgrade Flow

1. Restrict the application hostname using Cloudflare Access.
2. Confirm the Access login is shown to an unauthenticated visitor, unauthorized admission is denied, and authorized operator access works.
3. Confirm migration head state and run the migration safety check.
4. Apply migrations.
5. Deploy application code.
6. Run post-deploy smoke checks before reopening the app.

### VII.A Tagged release procedure

Every tagged release follows these steps in order, whether or not it carries a migration. A step is skipped only
where this section says so, and the release record says which step and why. Commands run from the operator's Mac
at the repository root; database reads use read-only, aggregate-only queries with class ids, never names.

Roles are those of §V. A single operator may hold all three under the solo-operator exception (`SOP-DEP-001`
§XIII), whose conditions the record must show met or name as a deviation. Checks run by an AI assistant are
advisory and are recorded as such, never as the independent verifier.

**Before the window**

1. **Release PR.** Move `[Unreleased]` in `CHANGELOG.md` under `## [X.Y.Z] - <UTC date> — <title>`, and check that
   every PR merged since the previous tag has an entry (`git log --merges vPREV..origin/main`) and that every entry
   in the section belongs to a PR in that range (`git merge-base --is-ancestor <merge> vPREV` is false). Subsections
   appear only from this list, in this order, each once: Added, Changed, Deprecated, Removed, Fixed, Security,
   Investigated, no code change. Each entry also names its release-notes section in an invisible tag after its
   bullet, `- <!-- notes: fixed|security-reliability|accessibility|internal[, highlight] --> **Headline** ...`
   (step 13). Required checks green and review threads resolved; merge. The merge commit, now
   the tip of `main`, is the release SHA.
2. **Full suite on the release SHA**, locally (about four hours; CI's run times out). It passes before dispatch.
   Exception: a security or data-integrity fix may be dispatched first and the suite run afterwards; the release
   record says so and later records the result.
3. **Configuration and migration checks.**
   - `flask db heads` shows one head; `bash scripts/check-migrations.sh` reports "Safe to deploy".
   - `git diff vPREV <SHA> -- requirements.txt migrations/versions` lists what is new.
   - Read the CHANGELOG for new required settings, and confirm by name only (never values) that production's
     `/root/classroom-economy/.env` has them.
   - For each new migration, run any pre-check its docstring names against production, read-only.
   - Host: `ssh root@cth 'cd /root/classroom-economy && git rev-parse HEAD && git status --porcelain && systemctl
     is-active cth-student-setup redis-server'`. HEAD is the previous release; the tree is clean apart from
     `venv.old/`.

**In the window**

4. **Restrict access** with Cloudflare Access (§VI gate verification).
5. **Backup.** `bash infra/db-backup/prerelease.sh backup` stops the application, takes one point into
   `~/cth-backup/prerelease-<UTC date>/` and verifies it. The source URL comes from `~/cth-backup/source_url`; no
   one types a credential. The application stays stopped until the release workflow restarts it.
6. **Point against live.** `bash infra/db-backup/prerelease.sh counts` must report `manifest == live`.
7. **Restore check.** The owner copies the `age` key to the clipboard and runs
   `umask 077; pbpaste > ~/cth-backup/identity.txt`. Then `bash infra/db-backup/prerelease.sh restore` checks
   the key against `recipients.txt`, restores into the in-memory database, runs the manifest and no-resurrection
   checks, deletes the identity with `rm -P`, closes the SSH tunnel to production, and stops the verify container.
   Both checks must PASS. A run abandoned before `restore` closes the tunnel with `prerelease.sh close-tunnel`.
8. **Balance baseline**, read with the application stopped. Each snapshot is compared only with the ledger rows
   at or below its `reconciled_through_posting_sequence` (`DOM-LED-001` §VIII.2); later rows are pending and are
   reported apart:

   ```sql
   WITH s AS (SELECT class_id, seat_id, account_type, posted_balance_cents, reconciled_through_posting_sequence AS cursor
              FROM ledger_balance_snapshot),
   l AS (SELECT t.class_id, t.account_type, count(*) AS txns,
           coalesce(sum(t.amount_cents) FILTER (WHERE t.posting_sequence <= s.cursor), 0) AS ledger_posted_cents,
           coalesce(sum(t.amount_cents) FILTER (WHERE s.cursor IS NULL OR t.posting_sequence IS NULL
                                                      OR t.posting_sequence > s.cursor), 0) AS pending_cents
         FROM ledger_transaction t
         LEFT JOIN s ON s.class_id = t.class_id AND s.seat_id = t.seat_id AND s.account_type = t.account_type
         GROUP BY 1, 2),
   ss AS (SELECT class_id, account_type, count(*) AS snapshots, sum(posted_balance_cents) AS snapshot_cents
          FROM s GROUP BY 1, 2)
   SELECT coalesce(l.class_id, ss.class_id) AS class_id, coalesce(l.account_type, ss.account_type) AS account,
          l.txns, l.ledger_posted_cents, ss.snapshots, ss.snapshot_cents, l.pending_cents,
          l.ledger_posted_cents IS NOT DISTINCT FROM ss.snapshot_cents AS posted_matches
   FROM l FULL JOIN ss ON ss.class_id = l.class_id AND ss.account_type = l.account_type
   ORDER BY 1, 2;
   ```

   `posted_matches` is true in every row; keep the table, including `pending_cents`, for the record.
9. **Tag and dispatch.** `git tag -a vX.Y.Z <SHA> -m "vX.Y.Z" && git push origin vX.Y.Z`, then
   `gh workflow run release-v2.yml -f revision=<full SHA> -f lineage_ref=main`. Dispatch once only: a second
   dispatch races the first. Watch the run through its health step.

**After the release**

10. **§VIII verification.** Host HEAD is the release SHA; the service is active; `127.0.0.1:8000/health` answers
    `ok`; `/docs` followed to its final response is 200 (`curl -L`), not just its 308; the scheduler has started; the journal has no `ERROR`, `CRITICAL`, `Traceback` or `WORKER TIMEOUT` lines
    since the restart; `alembic_version` is the single head; the step 8 query matches the baseline, apart from
    what the release itself is meant to change. The operator runs the browser checks in §VIII.
11. **Reopen** by changing the Access policy (§VI).
12. **Release record PR.** `docs/ops/audits/DEPLOY_<UTC date>_<short SHA>.md`, in the shape of the previous one:
    identity table, contents, migrations, §VI checks (backup stem, `taken_at`, revision, `artifact_sha256`, both
    restore results), baseline, release run, §VIII results, rollback, follow-ups. Each follow-up is an issue on the
    [CTH Backlog](https://github.com/users/timwonderer/projects/6) project, opened before the record merges, and the record links it rather than
    describing open work in prose. In the same PR, update the
    version in `README.md` and `DEVELOPMENT.md`, and make the first line of the CHANGELOG section exactly:

    ```text
    Released as `<short SHA>` on <YYYY-MM-DD> at <HH:MM> UTC by release run [<run id>](<run url>). No migration.|Migration `<rev>`. Record: <record link>.
    ```

    `<record link>` is a Markdown link whose text is the record's file name and whose target is
    `docs/ops/audits/DEPLOY_<date>_<sha>.md`, relative to the repository root.

    Further sentences may follow on that line; nothing goes before it.
13. **GitHub release**, after step 12's CHANGELOG is final. The notes are generated, never hand-written:

    ```bash
    python3 scripts/release_notes.py X.Y.Z > /tmp/notes.md
    gh release create vX.Y.Z --verify-tag --title "$(python3 scripts/release_notes.py X.Y.Z --title)" --notes-file /tmp/notes.md
    ```

    The notes are grouped for readers: Highlights (entries tagged `highlight`), then Fixed, Security & Reliability,
    Accessibility and Internal Changes, each listing one headline per entry with the full entries collapsed, and
    the deployment record and release run linked at the end (owner, 2026-10-22). The script refuses a section out
    of shape (heading, `Released as` line, subsection names and order), an entry without a known notes tag, and a
    tag that does not point at the `Released as` SHA. Fix the CHANGELOG, not the notes. `--raw` prints the section
    verbatim.

Untagged hotfixes follow steps 3-12 and record any step they skip; they have no tag, so no step 13.

## VIII. Post-Migration Verification

Verify on the host:

- app boots normally
- `/admin/login`, `/student/login` and `/docs` load
- no unexpected migration head drift is present

Then the browser validation: `SOP-DEP-001B` for a release (the features the release changes, features connected
to those changes, and features with a known problem), or `SOP-DEP-001A` for a first deployment or a release the
owner designates as full. Features outside a release's scope are covered by the release suite, not checked in the
browser.

## IX. Rollback Policy

- If migration fails before app reopen, rollback to the pre-deploy backup/snapshot.
- If post-deploy smoke checks fail and cannot be corrected within the maintenance window, rollback.
- If migration is structurally successful but business behavior is incorrect, keep Cloudflare Access restricted until rollback or fix-forward is approved.

### IX.1 Exact-SHA Release Failure Handling

The release workflow does not automatically downgrade production. A failed
release MUST remain in an operator-controlled state until the production
operator and rollback approver select rollback or fix-forward.

| Failure point | Required action |
|---|---|
| Lineage, SHA, environment approval, Tailscale, or SSH preflight | No production mutation is authorized; correct the release request or transport configuration. |
| Migration fails before restart | Keep the existing service running if possible, keep the maintenance window controlled, capture migration output, and stop for operator review. Do not retry blindly. |
| Migration succeeds but restart fails | Keep the environment controlled, inspect service logs/status, and restore service using the approved operator procedure. Do not run an automatic downgrade. |
| Restart succeeds but `/health` fails | Keep Cloudflare Access restricted, capture the exact deployed SHA and health/service evidence, then choose approved fix-forward or restore-from-backup. |
| Non-backward-compatible migration requires rollback | Rollback MUST use the verified backup/restore procedure and named rollback approval; `alembic downgrade` is not an automatic production recovery mechanism. |

Every failure record MUST include the requested SHA, approved lineage ref,
migration result, service state, health result, and operator decision.

## X. Transition Record Template

Use this template for the production transition record:

```text
Production Transition Record
Date:
Branch:
Commit SHA:
Production operator:
Independent verifier:
Rollback approver:
Maintenance window:

Pre-window confirmation
- Backup/snapshot reference:
- Restore procedure verified:
- flask db heads:
- flask db current:
- bash scripts/check-migrations.sh:

Cloudflare Access gate
- Enable action:
- Access login, denial, and operator admission verified:

Deployment
- Migration result:
- Application deploy result:

Post-deploy verification
- /admin/login:
- /student/login:
- /docs:
- POST /admin/current-class:
- /student/add-class:
- POST /student/switch-class/<class_id>:
- /admin/export-students:
- /verify/hallpass/<teacher_public_token>:

Outcome
- Reopen time:
- Go/no-go:
- Rollback needed:
- Operator sign-off:
- Independent verifier sign-off:
- Rollback approver sign-off:
```

## XI. Sign-Off Record

Record:

- deployment time
- operator
- branch SHA
- migration result
- smoke-check status
- reopen time
- rollback decision

## XII. Deferral Boundary

- This runbook is limited to launch-critical transition steps and operator records.
- Broader operational taxonomy changes and route-family cleanup are outside this runbook and are tracked as issues on the [CTH Backlog](https://github.com/users/timwonderer/projects/6) project.
- Version 1.5 deferred them until after two documents. One, `SPECS/V2_ADMIN_ROUTE_REFACTOR.md`, was never written. The other, `MAP-CLASS-002` (archived 2026-09-28), described the `class_id`-first model that INV-ARC-019 and DOM-IDEN-001 now govern. Version 1.6 changes no procedure in this runbook.



## XIII. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field. Subordinate to CORE changes.

**Version 1.15 (2026-10-22):** §VII.A step 12: each release-record follow-up is filed as an issue on the CTH Backlog project and linked from the record; §XII names the project instead of the archived post-launch tracker. Owner, 2026-10-22: the backlog moved to GitHub Issues.

**Version 1.14 (2026-10-22):** §VII.A steps 1 and 13: each CHANGELOG entry carries an invisible release-notes tag (`fixed`, `security-reliability`, `accessibility`, `internal`, optionally `highlight`); `scripts/release_notes.py` renders Highlights, Fixed, Security & Reliability, Accessibility and Internal Changes with full entries collapsed and the deployment record linked last, and refuses an untagged entry. Owner, 2026-10-22: the verbatim notes were unreadable. Follows 1.13 (#1632).

**Version 1.13 (2026-10-22):** §VII.A step 7: `prerelease.sh restore` also closes the SSH tunnel to production, and an abandoned run closes it with `prerelease.sh close-tunnel`. The tunnel had never been closed: the v2.2.4 one was still listening six days later and blocked the v2.3.0 backup.

**Version 1.12 (2026-10-22):** §VIII's fixed browser list is replaced by `SOP-DEP-001B` for releases and `SOP-DEP-001A` for a first deployment or a release the owner designates as full; the host checks stay. Owner rulings, 2026-10-22 (v2.3.0).

**Version 1.10 (2026-10-13):** adds §V.1, the single-maintainer limitation: the `production` environment has no
required reviewers, and environment approval means the branch policy plus the operator's recorded go-ahead under
the solo-operator exception. Owner decision of 2026-10-13 (Semgrep triage, priority 4). No procedure changes.

**Version 1.9 (2026-10-12):** adds §VII.A, the step-by-step tagged release procedure, and
`infra/db-backup/prerelease.sh`, which it runs. Owner rulings 2026-10-12: every tagged release takes the backup
and restore check, with or without a migration; the full suite passes before dispatch unless a security or
data-integrity fix goes first. Release notes come only from the CHANGELOG section, generated by
`scripts/release_notes.py` in a fixed shape (owner request 2026-10-12; the first conforming section is `[2.2.3]`).
v2.0.0 through v2.2.3 each followed a different variant of this procedure.

**Version 1.8 (2026-10-06):** §IV dependencies: archived `SOP-DB-009` is replaced by `SOP-DB-004` (classification, evidence and rollback rules), and `SOP-DEP-016`, which does not exist, is removed; rollback decisions are `SOP-DEP-001` §XIV and `SOP-DB-004` §IX.4. No procedure changes.

**Version 1.7 (2026-09-30):** §VI adds item 6, the student-setup memory store that the username-retention
check (#1442, released 2026-09-29) requires on every production host.
