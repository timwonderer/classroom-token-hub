# SOP-DB-004: Live-v2 Migration and Semantic-Versioning Contract

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DB-004 | 1.0 | 2026-10-06 | — | Normative |

> [!IMPORTANT]
> **Draft pending owner confirmation of §VII.** Section VII states the strict reading of the owner
> prohibition on compatibility bridges and helpers. It is the default until the owner rules
> otherwise, and it is the only section whose text depends on an unresolved authority conflict
> (see §VII.4). Everything else in this document stands without that ruling.

## I. Purpose

Production holds real classroom data. This document fixes, before any change to that state is
written, how a change is classified, what it may and may not do to existing production data, what
evidence must exist before, during and after cutover, how rollback is decided, and how a release
is numbered. It binds humans and agents who plan, review, approve and release changes; it does not
define application behavior.

## II. Scope

Every change released to the production database after the effective date: Alembic migrations,
data rewrites, code that changes how persisted rows are written or read, and the release that
carries them. It applies prospectively only (§V.3).

It does not replace `SOP-DB-001` (how a migration file is written and tested), `SOP-DB-003` (the
PR-blocking Schema Change Gate), `SOP-DEP-001` (live-test rehearsal) or `SOP-DEP-002` (production
transition). It adds the classification, history, evidence and versioning rules those documents do
not state, and where it is stricter it says so (§XII).

## III. Authority Level

Normative (SOP Tier), subordinate to `INV-CORE-000` and `INV-CORE-001`. Under `SOP-CORE-000` an SOP
cannot dictate architectural behavior, and nothing here decides what a persisted record *means*:
that belongs to the governing `INV-*`/`DOM-*` document. This SOP decides only who must rule, and
what is not permitted until they have.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `INV-ARC-017_GENERAL_TESTING_INVARIANTS.md`
- `DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md`
- `SOP-DB-001_Migration_Specifications.md`
- `SOP-DB-003_Schema_Change_Proposals.md`
- `SOP-DEP-001_Live_Test_Runbook.md`
- `SOP-DEP-002_Production_Transition_Runbook.md`

## V. Definitions and Boundary

1. **Live-v2.** The production database and application from the v2.0.0 release (2026-09-26)
   onward. Its history is the frozen baseline (`migrations/baseline/0001_baseline_schema.sql`, see
   `SOP-DB-001` §V.B) plus the Alembic chain to the deployed head.
2. **Production state** has five parts, and a change names every part it touches:
   - **Structure**: tables, columns, constraints, triggers, indexes.
   - **Rows**: existing data in unprotected tables.
   - **Protected rows**: rows whose lawfulness rests on the audit chain (`INV-ARC-016`,
     `DOM-OPS-002` §5.4), and append-only or immutable economic records.
   - **Policy rows**: the owning domains' append-only policy tables.
   - **External state**: anything outside the database that behavior depends on (Cloudflare Access
     policy, the student-setup memory store, environment variables).
3. **Prospective only.** This contract classifies changes made after its effective date. It does
   not reclassify, renumber or re-open any release already shipped. A tag, once published, is never
   moved.
4. **Bridge.** Any code, column, alias, fallback, dual-read, dual-write, flag or helper whose
   purpose is to let current code interpret a superseded representation, or superseded code
   interpret the current one, beyond the single execution of the migration that changes it. A
   migration run once is not a bridge; a runtime path that outlives the migration is.
5. **Forward-only revision.** An Alembic revision whose `downgrade()` raises, or does nothing for
   the schema or data it changed. Merge revisions that change nothing are not forward-only in this
   sense. The list in `SOP-DEP-001` §XIV is a register of known cases, not the definition; the
   definition is the revision's own `downgrade()`.
6. **Rollback boundary.** The first revision in a release whose `downgrade()` is not both defined
   and rehearsed (`SOP-DB-003` §VII.5). Past it, recovery is snapshot restore or a reviewed
   fix-forward, never a downgrade.

## VI. Classification

Each change carries three values, recorded where the change is planned (issue) and repeated in the
PR description. Where a value cannot yet be assessed it is written `Pending assessment`, and a
change with any pending value is not released.

### VI.1 Migration Class

| Class | Meaning | `SOP-DB-003` classification |
|-------|---------|-----------------------------|
| `M0 NONE` | No structure, row, or persisted-meaning change. | none (gate does not apply) |
| `M1 EXPAND` | Additive structure only; previous release still runs on the result. | EXPAND |
| `M2 DATA` | One-time rewrite or backfill of existing rows, structure unchanged. | not classified by the gate; treated as EXPAND for review and as `M4` for rollback (§IX.4) when the rewrite cannot be reversed |
| `M3 CONTRACT-CODE` | Code stops reading or writing an element; structure unchanged. | CONTRACT (CODE ONLY) |
| `M4 CONTRACT-DATABASE` | Removes or narrows structure or data, or contains a forward-only revision. | CONTRACT (DATABASE) |

A change takes the highest class it contains. It may not be split across releases to lower the
class of either half.

### VI.2 Historical State

What happens to rows that already exist, answered per table touched.

| Value | Meaning |
|-------|---------|
| `H0 UNAFFECTED` | No existing row is read differently, rewritten or removed. |
| `H1 PRESERVED` | Existing rows keep their stored meaning and the canonical reader needs no translation to understand them. |
| `H2 PROTECTED` | Existing rows are protected or immutable and the change alters how they would be read. Requires an owner ruling (§VII.3) before implementation. |
| `H3 REWRITTEN` | A migration rewrites existing rows once, to the new representation. Allowed only for unprotected rows, with the evidence in §IX.2. |
| `H4 RETIRED` | Existing rows are deleted, within a lifetime an `INV-*` or `DOM-*` document authorizes (cite it). |

### VI.3 Risk

`Low`, `Medium` or `High`, assigned by the strictest applicable row. A rationale sentence is
required for any value other than the row's minimum.

| Risk | At least this when… |
|------|---------------------|
| Medium | `M2`, `M3`, or any change touching Policy rows or External state. |
| High | `M4`; `H2`, `H3` or `H4`; any change touching Protected rows; or any change whose rollback is restore (§IX.4). |

## VII. History and the No-Bridge Rule

1. **No new bridge.** No change may add a bridge (§V.4). This covers compatibility columns,
   aliases, dual reads or writes, "fall back to the old form" branches, and helper functions whose
   job is to translate between representations. A bridge added "for safety", "temporarily" or
   "behind a flag" is still a bridge.
2. **Allowed ways to meet existing history.** A change reaches existing data only through one of:
   1. `H0` or `H1`: nothing needs translating, because the new reader understands the old rows
      as stored.
   2. `H3`: a single forward migration rewrites the rows. Once it has run, no code reads the old
      representation.
   3. `H4`: the rows are deleted within an authorized lifetime.
3. **Anything else is blocked for a ruling.** If neither 2.1 nor 2.2 nor 2.3 fits, in particular
   when protected rows cannot be rewritten and the new meaning would require reading them
   differently (`H2`), the change stops. Its issue records the conflict, names the governing
   clauses, and waits for an owner ruling recorded in the governing `INV-*`/`DOM-*` document.
   An agent never resolves it by choosing a bridge.
4. **Existing authority is not precedent.** Historical interpretation that already exists under
   owner-ruled documents (for example `DOM-OPS-002` §6.2A and `SPEC-PROD-002`, which diagnose old
   audit coverage without rewriting it, and the "approved bridge code" allowance in `INV-ARC-008`
   §VI) is unchanged by this document and is not authority for a new bridge. Whether those
   provisions and `SOP-DB-001` §VIII Phase 1 ("application supports both") are consistent with
   the no-bridge rule is an open authority conflict for the owner; until it is ruled, §VIII
   states the stricter reading.

## VIII. Expand and Contract Under This Contract

`SOP-DB-001` §VIII remains the phase vocabulary. Under the strict reading in §VII:

1. **Structure may coexist, code may not.** Old and new structure may exist together only for the
   span of one release, inside a controlled window (§IX.3). During that span the running code
   reads and writes one representation, the new one.
2. **No release depends on old code and new schema both running.** A release whose previous
   version must keep running against the new schema (the premise of code-only rollback) must
   prove that, per §IX.4, and is `M1` at most.
3. **Contract in two releases at most.** A removal follows the `M3` release by one `M4` release.
   The `M4` release contains no unrelated code (`SOP-DB-003` §VII.1).

## IX. Rollback and Cutover Evidence

Evidence is produced by execution, never by argument, and is reported with its exact command and
scope (`INV-ARC-017` §V.5, §V.8). Evidence contains no PII and no secrets (`INV-ARC-005`).

### IX.1 Before the window

1. Exact release SHA, and its ancestry of the approved lineage (`SOP-DEP-002` §VI).
2. `flask db heads` (exactly one) and `flask db current` for the target database.
3. Classification (§VI) for every change in the release, and the rollback boundary (§V.6).
4. A restorable snapshot reference and proof the restore procedure works
   (`SOP-DEP-002` §VI.2; `docs/ops/DATABASE_BACKUP_PLAN.md`).
5. Rehearsal on a production-like clone: upgrade, and downgrade or an explicit declaration that
   the revision is forward-only (`SOP-DB-003` §VII.5).
6. Targeted checks named by the change, chosen by inspecting the `pytest_result` artifact of the
   most recent relevant run. The agent does not run the full suite (`INV-ARC-017` §V.4); the full
   suite runs as its own gate (`SOP-DEP-001` §XV).
7. A **read-only baseline**, timestamped: per affected table and class, row counts and (for money)
   aggregate ledger totals, taken before the window so the same query can be repeated after. It
   identifies classes by `class_id` and contains no names.

### IX.2 For `H3` changes

All of §IX.1, plus: the rewrite is run against the clone, and a before/after comparison of the
baseline queries shows exactly the intended differences and no others; the rewrite is repeatable
without further change (idempotent per `SOP-DB-001` §VI).

### IX.3 During the window

1. Production is changed only after the owner's explicit go-ahead for that release. Merging does
   not deploy (`SOP-DEP-002` §VI).
2. A release whose recovery is restore (§IX.4) stops application writes from before the snapshot
   until health is verified, so a restore loses nothing. A release that cannot stop writes
   declares the data-loss window and has it approved before the window opens.
3. The migration and the deploy run through the exact-SHA release workflow. No downgrade is run
   automatically (`SOP-DEP-002` §IX.1).
4. A person who is not the change author observes the cutover, and the observation is recorded.
   AI output is advisory and is not independent verification (`SOP-DEP-001` §XIII).

### IX.4 Rollback decision

| Condition | Permitted recovery |
|-----------|--------------------|
| Release is `M0`, or `M1` and the previous SHA is shown (before the window) to boot and pass `/health` against the upgraded schema | Redeploy the previous SHA. |
| Anything else, including every release containing a forward-only revision or an `M2` rewrite that cannot be reversed | Snapshot restore, or a reviewed fix-forward. `flask db downgrade` is never an automatic recovery. |

The record states which row applies and names the rollback boundary before the window opens.

### IX.5 After the window

1. `/health` and the smoke routes in `SOP-DEP-002` §VIII, with results.
2. The baseline queries from §IX.1.7 rerun at a recorded time and compared with the original; every
   difference is explained by the change or investigated before reopening.
3. `flask db current` equals the expected head.
4. The release record (§XI) is written to `docs/ops/audits/` and is immutable once finalized.

## X. Semantic Versioning

1. **What a version identifies.** A version `MAJOR.MINOR.PATCH` identifies a release of the
   application together with the set of Alembic revisions it carries. It is recorded as the Git tag
   `vMAJOR.MINOR.PATCH` on the release SHA, a `CHANGELOG.md` section of the same number, and the
   release record (§XI).
2. **Contract surface.** For this system the contract with users and operators is the persisted
   data and its meaning, plus what a teacher or student is able to do. Source structure is not part
   of it.
3. **Rules.** A release takes the highest level any of its changes requires.

   | Level | Required when |
   |-------|---------------|
   | MAJOR | The meaning of retained data changes in a way a user would observe in existing records (`H2` resolved by ruling), or the identity, tenancy or authority model changes, or a capability users depend on is removed. |
   | MINOR | A capability is added or changed, or the release contains any `M1`, `M2` or `M4` change, including any forward-only revision. |
   | PATCH | The release is `M0`, or only `M1` changes that add no capability and pass §IX.4's first row. |

4. **Untagged releases.** A release with no migration (`M0`) may ship untagged as a hotfix from an
   approved lineage ref. The next tagged release's record names it. A release containing any
   migration is tagged.
5. **No retroactive renumbering.** Releases shipped before this document keep their numbers, and
   the rules apply from the next tag. Under §X.3 the v2.1.1 release, which carried forward-only
   revisions (`docs/ops/audits/DEPLOY_2026-10-04_2bdfac65e.md`), would have been a MINOR; that is
   recorded as a deviation, not corrected.
6. **Where the number is used.** The version lives in the tag, the changelog and the release
   record. The application does not report one at runtime, and this contract does not require it
   to.

## XI. Release Record Additions

The dated record under `docs/ops/audits/` (`DEPLOY_<date>_<sha>.md`) adds, for any release with a
migration: the classification table (§VI) with each change's class, historical state and risk; the
rollback boundary and the §IX.4 row chosen; the baseline timestamps and comparison result (§IX.5);
the named independent observer; and the version assigned under §X with the level that required it.

## XII. Relationship to Existing Procedures

- `SOP-DB-001` is unchanged. Its §VIII expand/contract applies as §VIII here restricts it.
- `SOP-DB-003` remains the PR gate. `M2 DATA` has no box in its classification; this document is
  the only place a data rewrite is classified, and the PR description cites it.
- `SOP-DEP-001` §XIV's list of forward-only revisions is a register of known cases. The
  definition in §V.5 governs where they differ.
- `SOP-DEP-002` is unchanged. §IX adds evidence to its checklist; it removes none.

## XIII. Amendment

Revisions require incrementing the version, updating the Effective Date, and populating the
Supersedes field, and must remain consistent with `INV-CORE-000`. Confirming or replacing §VII after
the owner's ruling is a version increment that cites the ruling.
