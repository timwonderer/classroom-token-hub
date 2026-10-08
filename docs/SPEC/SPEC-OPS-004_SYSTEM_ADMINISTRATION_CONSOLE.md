# SPEC-OPS-004: System Administration Console

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-OPS-004 | 1.4 | 2026-10-07 | SPEC-OPS-004 v1.3 | Normative |

> [!NOTE]
> Renumbered from `SPEC-OPS-003` on 2026-09-06. This document and
> `SPEC-OPS-003_APPLICATION_OBSERVABILITY_CONTRACT.md` were authored in parallel on separate
> branches and both claimed `SPEC-OPS-003`, which made the reference number ambiguous as a citation
> handle. The `OPS` sequence now runs in dependency order: `002` the external status persistence
> model, `003` the observability contract that produces the signal, `004` the console that surfaces
> it. Citations of `SPEC-OPS-003` dated before 2026-09-06 that concern the console refer to this
> document.

## I. Purpose

Define the operator-facing surface of the System Administration Console: which capabilities it exposes, what each capability may read or mutate, and the boundary between platform operation and classroom domain truth.

This specification is developer and operator documentation. The console is not a user-facing product surface and is deliberately excluded from the user guide corpus (see §IX).

## II. Scope

Governs the `sysadmin` blueprint (`/sysadmin`) and its rendered pages. It does not govern teacher or student surfaces, and it does not define health evaluation, incident lifecycle, or audit lineage — those belong to `DOM-OPS-001` and `DOM-OPS-002`.

## III. Authority Level

Normative (SPEC Tier). Subordinate to `INV-CORE-000`, `INV-ARC-004`, `INV-ARC-007`, `INV-ARC-009`, `DOM-OPS-001`, and, for the Support surface, `DOM-SUP-001` and `FEAT-SUP-001`.

## IV. Dependencies

- `docs/DOMAIN/DOM-OPS-001_OPERATIONS_DOMAIN.md`
- `docs/DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md`
- `docs/DOMAIN/DOM-SUP-001_SUPPORT_DOMAIN.md`
- `docs/FEATURE-EXECUTION/FEAT-SUP-001_ISSUE_SUBMISSION_AND_ESCALATION.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-004_CROSS_TENANT_ISOLATION.md`
- `docs/SPEC/SPEC-OPS-001_REVERSAL_AND_VOID.md`

## V. Access Control

Every console route is gated by `system_admin_required`. Sysadmin authentication is independent of teacher and student authentication and grants no classroom authority: a sysadmin session is not a teacher session and cannot act inside a class.

Authentication factors supported by the console:

- password with TOTP second factor;
- passkey (WebAuthn) registration and assertion.

Passkey self-service lives at `/sysadmin/passkey/settings`. Registration, listing, and deletion act only on the authenticated sysadmin's own credentials. The console exposes no surface for creating, deleting, or resetting the credentials of another operator; that provisioning is out-of-band.

## VI. Console Surface

### 6.1 Navigation

The console navigation exposes exactly four destinations plus sign-out:

| Destination | Route | Purpose |
| --- | --- | --- |
| Dashboard | `/sysadmin/dashboard` | Platform-wide counts |
| Support | `/sysadmin/support` | Teacher issues and developer-escalated issues |
| Passkeys | `/sysadmin/passkey/settings` | The operator's own WebAuthn credentials |

Routes outside this set are reachable by direct URL only and MUST NOT be treated as supported operator surfaces.

### 6.2 Dashboard

A pure read (`INV-ARC-007`). It reports:

- teacher account count, seat count with student role, and sysadmin count;
- open ticket count, defined as open teacher-submitted tickets plus tickets escalated to developer review that are not yet resolved. Only tickets visible under §6.3 are counted;
- the sysadmin roster, rendered as display view objects rather than raw models.

The dashboard is display-only. It exposes no account administration action.

### 6.3 Support

#### Visibility

The console sees a ticket only when one of the following holds:

- **Teacher-submitted.** The ticket's `actor_public_id` is a teacher seat in the ticket's own class. A teacher's direct report is addressed to system support from submission (DOM-SUP-001 §X).
- **Escalated.** The class-owning teacher escalated it (`escalated_at` is set). It stays visible after it leaves `ESCALATED_TO_DEV`.

A student ticket its teacher has not escalated is not visible. This includes one the teacher closed without escalating. DOM-SUP-001 §VIII assigns every transition before escalation to the teacher or the system, and FEAT-SUP-001 makes escalation the act that grants system support access. The ticket's category and `issue_type` play no part: a student's general ticket is still a student ticket. The correlation pack plays no part either. It records the same authorship, but correlation evidence grants no ticket access.

Every console read of `issues` applies this rule first: lists, counts, per-status tallies, the detail page, the reporter's ticket count, and every mutation. The rule is one server-side predicate, `app/services/support_operator_access.py`. A ticket outside it answers with the same 404 as a reference to a ticket that does not exist.

#### Tabs

Two tabs over the single `Issue` record type:

- **Teacher issues**: visible teacher-submitted tickets, filterable by status. Per-status counts come from the same set.
- **Escalated issues**: escalated tickets in a developer-review state, partitioned into pending, in review, and resolved.

Issues are addressed by opaque reference, never by primary key, in both URLs and templates. Detail, update, start-review, and resolve actions operate on a single issue resolved from that reference.

#### Actions

- The **update** form (`OPEN`, `DEV_RESOLVED`, `CLOSED`, plus operator notes) acts only on a teacher-submitted ticket that has not been escalated.
- On an escalated ticket, the console's only transition is `ESCALATED_TO_DEV` → `DEV_RESOLVED`, recorded through the resolve action, which may also issue a bug reward (DOM-SUP-001 §VIII). The teacher closes the ticket.

Issue records carry `actor_public_id` and `class_public_id`. The console reads across tenants by design — it is the one surface exempt from class scoping — and therefore MUST NOT surface identifying student or teacher data beyond those opaque references.

Support views MUST apply DOM-SUP-001 §X per-category teacher permissions before
constructing any operator-facing payload. Technical correlation diagnostics remain
available; consent to disclose a frozen snapshot grants no live class authority.

### 6.4 Logs

The console has no log viewer (owner ruling 2026-10-07). Application logs, error events and request activity are read in Grafana (§6.5). Version 1.4 removed `/sysadmin/combined-logs`, `/sysadmin/logs`, the redirects `/sysadmin/error-logs`, `/sysadmin/logs-testing` and `/sysadmin/network-activity`, and the dashboard's recent-errors panel. The `operational_events` table and its writer are unchanged; only the console's reading of it was removed.

### 6.5 Grafana proxy

`/sysadmin/grafana/<path>` proxies an upstream Grafana instance behind sysadmin authentication. The proxy carries no CTH domain authority; it neither reads nor writes domain state.

### 6.6 Error-handler probes

`/sysadmin/test-errors/<code>` deliberately raises the named HTTP error to exercise error handlers. These are diagnostic probes, not operator features.

## VII. Mutation Boundary

The console MUST NOT mutate classroom domain truth. Specifically it does not create, modify, or delete:

- classes, class configuration, or economic policy versions;
- balances, transactions, or any ledger record;
- obligations, entitlements, attendance facts, or store catalog entries;
- teacher or student accounts.

Permitted mutations are confined to Operations-owned records: issue status and reviewer annotation on tickets visible under §6.3 and only by the transitions §6.3 allows, and the operator's own passkey credentials.

Any capability that would reach into class state — deleting a class period, deleting a teacher account, adjusting a student balance, broadcasting to classroom dashboards — is outside this specification and MUST NOT be added to the console without a domain-owning FEAT and an amendment here.

## VIII. Historical Non-Conformance Record

These findings were recorded during the initial console reconciliation. They are
retained as evidence, not as intended behavior or current open work:

1. **Resolved 2026-09-08:** `/sysadmin/error-logs`, `/sysadmin/logs-testing`,
   and `/sysadmin/network-activity` no longer render hardcoded empty result
   sets. The superseded routes redirect to the supported
   `/sysadmin/combined-logs` surface. (All of these were removed in 1.4.)
2. **Resolved 2026-09-08:** `update_user_report` now runs under
   `FEAT-OPS-001`, uses the canonical issue-status/history helper, records
   Operations-owned review metadata, and commits the mutation atomically.
3. **Resolved 2026-09-29:** student tickets reached the console before any
   teacher escalation. On 2026-07-16 the teacher-report query was ported from
   v1's separate report table to `issue_type == 'general'`, which also matches
   every general student ticket. The same change made the dashboard count every
   `OPEN`/`TEACHER_REVIEW` ticket. The detail page and update form had no
   visibility check. System support could therefore read a student ticket's
   page URL, IP address, browser, category, and seat reference as soon as it
   was filed. It could also close the ticket before the teacher saw it. §6.3
   now defines visibility, and the console enforces it everywhere.

## IX. Documentation Placement

The console is documented here, in the developer corpus under `/docs`, and not in `docs/user-guides/`.

Rationale: the user guide corpus is audience-isolated at the docs route — a reader in the `user` audience sees only `user-guides/`, and the `devops` audience sees everything except it. Operator documentation placed under `user-guides/` was reachable by neither audience in a useful way, and mixed platform operation into a corpus whose stated separation forbids internal implementation detail (`SOP-DOC-000`).

The prior guides at `docs/user-guides/features/sysadmin/` and `docs/user-guides/sysadmin_manual.md` are superseded by this specification.

## X. Change Notes

**Version 1.4 (2026-10-07):**
- Removed log reading from the console (owner ruling 2026-10-07: logs are read in Grafana). §VI no
  longer lists a Logs destination, §6.2 drops the recent-errors list, and §6.4 states that the console
  has no log viewer. `/sysadmin/logs` read the application log file but displayed nothing in
  production; the combined-logs network tab only repeated the error rows.

**Version 1.3 (2026-09-29):**
- §6.2 and §6.3 conform to DOM-SUP-001 and FEAT-SUP-001. Version 1.2's text for them was written
  on 2026-09-05, after the regression recorded in §VIII.3, and described that regressed runtime:
  a "Teacher issues" tab of `issue_type` `general` and an open count including every new or
  teacher-review ticket. That text was never the intended behavior. DOM-SUP-001 and FEAT-SUP-001
  govern, and this specification follows them.
- §6.3 adds the visibility rule, its single enforcement point, the fail-closed 404, and the
  limits on console actions. §VII scopes the permitted issue mutations to that rule.
- Added DOM-SUP-001 and FEAT-SUP-001 to §III and §IV.

## XI. Amendment

Revisions increment the version and effective date, add a change note, and stay consistent with
the documents listed in §III.
