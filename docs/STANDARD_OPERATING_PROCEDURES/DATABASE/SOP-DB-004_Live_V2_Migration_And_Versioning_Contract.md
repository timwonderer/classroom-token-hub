# SOP-DB-004: Live-v2 Migration and Semantic-Versioning Contract

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DB-004 | 1.2 | 2026-10-06 | 1.1 | Normative |

> [!NOTE]
> §VII and §VIII record the owner ruling of 2026-10-06 on compatibility: physical schema coexistence
> during expand/contract is permitted; dual-write, fallback, heuristic interpretation and competing
> semantic authorities are prohibited; historical rows may keep an explicit semantic version and be
> interpreted by that immutable version.

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
4. **Prohibited compatibility.** Any dual-write, fallback (try the new form, else the old),
   heuristic interpretation (inferring what a row means from its content, timestamps or shape),
   competing semantic authority (two components that each decide what the same row means), or flag
   or helper whose purpose is any of those. A migration run once is not one; a runtime path that
   outlives it is.
   **Versioned interpretation** is not prohibited compatibility: a read-side interpreter that is
   selected only by a historical row's explicit, immutable semantic version (§VII.3).
5. **Forward-only revision.** An Alembic revision whose `downgrade()` raises, or does nothing for
   the schema or data it changed. Merge revisions that change nothing are not forward-only in this
   sense. The complete list is `migrations/forward_only_register.txt`, which
   `tests/test_forward_only_revision_register.py` holds equal to the set derived from each
   revision's own `downgrade()`. A PR that adds a forward-only revision adds it to the register;
   a missing or stale entry fails the test.
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
| `M0 NONE` | No structure, row, or persisted-meaning change, including no new semantic version written. | none (gate does not apply) |
| `M1 EXPAND` | Additive structure only; previous release still runs on the result. | EXPAND |
| `M2 DATA` | Persisted meaning changes with structure unchanged: a one-time rewrite or backfill of existing rows, or code that begins writing a new explicit semantic version into an existing column or document with no DDL (the writer cutover of §VII.4). | not classified by the gate; treated as EXPAND for review, and as `M4` for rollback (§IX.4) when a rewrite cannot be reversed or the previous release cannot read rows written under the new version |
| `M3 CONTRACT-CODE` | Code stops reading or writing an element; structure unchanged. | CONTRACT (CODE ONLY) |
| `M4 CONTRACT-DATABASE` | Removes or narrows structure or data, or contains a forward-only revision. | CONTRACT (DATABASE) |

A change takes the highest class it contains. It may not be split across releases to lower the
class of either half.

### VI.2 Historical State

What happens to rows that already exist, answered per table touched.

| Value | Meaning |
|-------|---------|
| `H0 UNAFFECTED` | No existing row is read differently, rewritten or removed. |
| `H1 PRESERVED` | Existing rows keep their stored meaning and the current reader understands them as stored; no new semantic version exists. |
| `H2 VERSIONED` | Existing rows keep an explicit semantic version and are interpreted by that version (§VII.3). Applies to protected rows, which are not rewritten. |
| `H3 REWRITTEN` | A migration rewrites existing rows once, to the new representation. Allowed only for unprotected rows, with the evidence in §IX.2, and only if rollback does not require rewriting them back (§VII.6). |
| `H5 UNRESOLVED` | Existing rows have no explicit semantic version and their meaning would have to be inferred. Blocked for an owner ruling (§VII.7). |
| `H4 RETIRED` | Existing rows are deleted, within a lifetime an `INV-*` or `DOM-*` document authorizes (cite it). |

### VI.3 Risk

`Low`, `Medium` or `High`, assigned by the strictest applicable row. A rationale sentence is
required for any value other than the row's minimum.

| Risk | At least this when… |
|------|---------------------|
| Medium | `M2`, `M3`, or any change touching Policy rows or External state. |
| High | `M4`; `H2`, `H3`, `H4` or `H5`; any change touching Protected rows; or any change whose rollback is restore (§IX.4). |

## VII. History, Versioned Interpretation and Compatibility

1. **Prohibited.** No change may introduce dual-write, fallback, heuristic interpretation, or a
   competing semantic authority (§V.4). "For safety", "temporarily" and "behind a flag" do not
   change that. Compatibility on the read side must not provide an alternate path for creating
   new state.
2. **Permitted.** Physical schema coexistence during expand/contract (old and new columns,
   tables or constraints existing together), and versioned interpretation of lawful historical
   state (§VII.3).
3. **Versioned interpretation.** A historical row may retain an explicit semantic version, stored
   with the row (or fixed by a recorded, immutable boundary the owning domain defines) and never
   changed afterward. The interpreter is chosen only by that value. Each version's meaning is
   defined by one authority, the owning domain's `DOM-*` document. Only lawful historical state
   is interpreted this way (`INV-ARC-016`); a row of unknown lawfulness is not made lawful by
   being read.
4. **Writer cutover.** There is one cutover point, inside one release. After it every new write
   uses only the current semantic version; before it, writers use only the previous one. No
   release writes both.
5. **Retirement.** Every expand/contract artifact (a column, trigger, constraint or interpreter)
   has an explicit retirement condition recorded in its issue and release record, stating what
   must be true for it to be removed and in which release. The only exemption is an artifact
   permanently required to interpret retained historical records; it says so and cites the
   authority that requires the records to be kept.
6. **Rollback.** Rollback must not require rewriting historical rows into a different semantic
   version. A change whose recovery would need such a rewrite recovers by snapshot restore or
   fix-forward (§IX.4), and is classified accordingly.
7. **Unversioned or ambiguous history is blocked.** When existing rows carry no explicit version
   and would have to be interpreted by inference (`H5`), the change stops. Its issue records the
   rows, the governing clauses and the ambiguity, and waits for an owner ruling recorded in the
   governing `INV-*`/`DOM-*` document. An agent never resolves it by inferring.
8. **Existing provisions.** `INV-ARC-008` v1.2 §VI no longer allows "approved bridge code".
   `DOM-OPS-002` v1.11 §6.2A and `SPEC-PROD-002` v1.4 describe read-side interpretation of
   retained history that creates no state, as §VII.3 requires. None of them is authority for new
   compatibility code; any new reliance on them goes through §VII.3 or §VII.7.

## VIII. Expand and Contract Under This Contract

`SOP-DB-001` §VIII remains the phase vocabulary, read as follows.

1. **Coexistence is physical.** In Phase 1 the schema supports both forms. The application writes
   one, the current form, and reads history only as §VII.3 allows.
2. **Prior release may keep running only if proven.** A release whose previous version must run
   against the new schema (code-only rollback) must prove it per §IX.4, and is `M1` at most.
3. **Contract in two releases at most.** A removal follows the `M3` release by one `M4` release,
   unless an artifact is exempt under §VII.5. The `M4` release contains no unrelated code
   (`SOP-DB-003` §VII.1).

## IX. Rollback and Cutover Evidence

Evidence is produced by execution, never by argument, and is reported with its exact command and
scope (`INV-ARC-017` §V.5, §V.8). Evidence contains no PII and no secrets (`INV-ARC-005`).

### IX.1 Before the window

1. Exact release SHA, and its ancestry of the approved lineage (`SOP-DEP-002` §VI).
2. `flask db heads` (exactly one) and `flask db current` for the target database, and the
   release's forward-only revisions named from `migrations/forward_only_register.txt`.
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

### IX.2 For `H2` and `H3` changes

All of §IX.1, plus, for `H2`: a test that the interpreter selected by each historical version yields the meaning the owning domain defines for a seeded sample of rows of that version, and that the new writer emits only the current version. For `H3`: the rewrite is run against the clone, and a before/after comparison of the
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
| Release is `M0`, or `M1` and the previous SHA is shown (before the window) to boot and pass `/health` against the upgraded schema | Redeploy the previous SHA, which must also interpret every row written after cutover without any row being rewritten. |
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
   | MAJOR | The meaning of retained data changes in a way a user would observe in existing records (a new semantic version changes what existing historical records mean to the user), or the identity, tenancy or authority model changes, or a capability users depend on is removed. |
   | MINOR | A capability is added or changed, or the release contains any `M2` or `M4` change, including any forward-only revision or a new semantic version written, or an `M1` change that fails §IX.4's first row. |
   | PATCH | The release is `M0`, or only `M1` changes that add no capability and pass §IX.4's first row. Nothing else is PATCH. |

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

- `SOP-DB-001` §VIII Phase 1 is read as §VIII here states (v1.7 of that document records this).
- `SOP-DB-003` remains the PR gate. `M2 DATA` has no box in its classification; this document is
  the only place a data rewrite is classified, and the PR description cites it.
- `SOP-DEP-001` §XIV defers to `migrations/forward_only_register.txt` for the complete list of
  forward-only revisions; §V.5 gives the definition.
- `SOP-DEP-002` is unchanged. §IX adds evidence to its checklist; it removes none.

## XIII. Amendment

Revisions require incrementing the version, updating the Effective Date, and populating the
Supersedes field, and must remain consistent with `INV-CORE-000`. Any change to §VII requires an owner ruling, which the new version cites.
