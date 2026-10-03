# FEAT-PROD-004: Complete Payroll Cycle

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-PROD-004 | 1.4 | 2026-10-03 | 1.3 | Normative |

> [!NOTE]
> **1.2 (2026-09-30), operator ruling.** The CLASS activation step is removed. It activated pending rows of the class-wide `policy_versions` / `policy_transitions` tables, which were never authorized as canonical and are retired (`DOM-CLASS-003` §V). A change saved for the next cycle is a row of its owning domain's table carrying its own effective date, in force from that date with nothing to activate (`DOM-CLASS-003` §VII). The run now coordinates PROD and ITR only.

---

## I. Purpose

This FEAT is the **canonical class-level payroll-run orchestrator** and the sole coordination point for the economic-cycle boundary defined in `DOM-PROD-001` §XV.

It exists so that a completed payroll run — the moment the class's open economic cycle closes — produces its lawful downstream side effects through a single declared, auditable, idempotent orchestration, rather than through direct domain-to-domain calls (`INV-ARC-021` §V.1–§V.2).

Both payroll execution paths converge on this FEAT:

- manual payroll initiated by the teacher, and
- automatic payroll initiated by a scheduled run.

This FEAT does not itself write `payroll_event` rows; it owns the run identity and the cross-domain choreography. Per-seat settlement is performed through PROD domain commands governed by `FEAT-PROD-003`; this orchestrator never executes another FEAT. Corrections do not close cycles.

---

## II. Scope

Class-level payroll completion only. Per-seat terminal interval correction and residual recovery are non-boundary operations; neither runs this completion orchestration.

## III. Authority Level

Normative, subordinate to INV-CORE-000 §III.1–6, INV-CORE-001 §III, VIII, DOM-PROD-001 §XV, INV-ARC-021 §V, VII, and FEAT-CORE-000 §II–V.

## IV. Dependencies

- `docs/DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md`
- `docs/FEATURE-EXECUTION/FEAT-PROD-003_RECORD_PAYROLL_EVENT.md`
- `docs/DOMAIN/DOM-ITR-001_INTERPRETATION_DOMAIN.md`
- [DOM-LED-001](../DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md) §VII.1 — Ledger-owned amounts, reservations, and posting.
- [DOM-IDEN-006](../DOMAIN/DOM-IDEN-006_CANONICAL_CONTEXT_RESOLUTION.md) §VII–XI — current canonical actor/target context.
- [DOM-CLASS-001](../DOMAIN/DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md) §VII, X and [DOM-CLASS-002](../DOMAIN/DOM-CLASS-002_CLASS_ECONOMY_GOVERNANCE.md) §V, VII — configuration facts and shared funding contract.
- [DOM-OPS-002](../DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md) §5 — protected audit evidence.
- [FEAT-LED-000](FEAT-LED-000_CANONICAL_MONETARY_RESOLUTION_WORKFLOW.md) §VII, XI and [FEAT-LED-001](FEAT-LED-001_POST_LEDGER_TRANSACTION.md) — incorporated monetary domain-command resolution and posting contracts, never nested executors.
- [SPEC-PROD-001](../SPEC/SPEC-PROD-001_ATTENDANCE_INTERVAL_ELIGIBILITY_AND_PAYROLL_CORRECTION.md) §V–VII and [SPEC-LED-002](../SPEC/SPEC-LED-002_COMMAND_IDEMPOTENCY_RESERVATION_AND_ENFORCEMENT.md) §III–VIII — incorporated settlement provenance, serialization, and monetary command reservation requirements.
- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/DOMAIN/DOM-CLASS-003_ECONOMIC_POLICY.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`
- `docs/SPEC/SPEC-ECON-002_ECONOMIC_POLICY_VISIBILITY_AND_DISCLOSURE.md`
- `app/services/context_resolver.py`
- `docs/SPEC/SPEC-TIME-001_CANONICAL_TEMPORAL_RESOLVER.md`
- `app/utils/canonical_temporal_resolver.py`


## V. Execution Context

### 1. Required Inputs

- `ctx`: `CanonicalContext` — carries the class boundary and lawful actor seat
- `run_mechanism`: `TEACHER` | `SYSTEM` — records which path initiated the run. It is stamped as `mechanism` on every `payroll` event of the run and is never inferred: the automatic schedule passes `SYSTEM`, the teacher's run passes `TEACHER`. Only `SYSTEM` runs anchor the next payroll date (`DOM-PROD-001` §XV.5)
- `scheduled_occurrence`: required when `run_mechanism = SYSTEM` — the scheduled payroll date the run settles, recorded on each `payroll` event so the schedule does not drift with the run's wall-clock time
- `idempotency_key`: replay guard for the class-level completion command
- `reference_time_utc`: optional explicit timestamp for deterministic evaluation

### 2. Generated Identity

- `payroll_cycle_id`: a fresh UUID **allocated only for a genuinely new run**. It is the durable economic-period identity for the run and is stamped, unchanged, onto every `payroll` event written during the run.

**Replay resolves before allocation.** The persistent completion anchor (`DOM-PROD-001` §XV; `payroll_cycle_completion`) is consulted first: if this class-level `idempotency_key` already resolves to a completed run, the FEAT returns that run's original `payroll_cycle_id` and performs no downstream work. Only when no completed run resolves does the FEAT allocate a new `payroll_cycle_id`. A replay therefore never allocates a second cycle identity, never re-reads or recaptures the (possibly since-advanced) governing configuration, and never re-invokes settlement or interpretation.

`payroll_cycle_id` MUST NOT be derived from `idempotency_key`, `correlation_id`, or any per-command replay nonce. See `DOM-PROD-001` §XV.2.

### 3. Canonical Authority

- `ctx.class_id` provides the class isolation boundary.
- `ctx.seat_id` / `ctx.actor_role` establish lawful authority for the run.
- The FEAT MUST fail closed if the initiating actor is not lawful for the class.

---

## VI. Orchestration Contract

This FEAT coordinates Identity, Class Configuration, Productivity, Ledger, Operations, and Interpretation through their owning queries/commands in a fixed, lawful order. Each cross-domain effect is a declared side effect of this contract, auditable via `request_id` and the originating FEAT code, and idempotent on replay (`INV-ARC-021` §V.8).

### Execution steps

0. **Resolve replay (FIRST).** Consult the persistent completion anchor for `(class_id, idempotency_key)`. If a completed run resolves, return its original `payroll_cycle_id` immediately — before any configuration read, cycle-id allocation, timestamp resolution, eligible-seat query, `reference_configuration` capture, or ITR invocation. This step is the sole protection of the historical-configuration seam and MUST precede every other operation.
1. **Open the cycle (new run only).** Confirm the actor is lawful for the class. Allocate a fresh `payroll_cycle_id` (UUID). Consume the caller-supplied lawful closed-cycle window / evaluation time (this FEAT does not derive boundary legality).
2. **Settle the closing cycle (PROD + Ledger + Operations).** Resolve targets through Identity and consume Class Configuration facts through its queries. Serialize target seats in stable identifier order before eligibility evaluation, using the common target-seat → ClassEconomy → original-credit → pending/snapshot-source lock order. For each eligible seat, consume PROD's authoritative business/pricing inputs, including original setting shares and version-1 interval provenance (`DOM-PROD-001` §XV.3). Inside this same `FEAT-PROD-004` context, compose Ledger's `build_intended_ledger_plan`, `resolve_intended_ledger_plan`, and `apply_resolved_ledger_plan` / posting domain commands, invoke PROD's `record_payroll_event(...)` domain command with `payroll_event_type = payroll`, the run's `payroll_cycle_id` and `run_mechanism`, and emit all protected audit evidence through Operations commands. `FEAT-PROD-003` supplies the per-seat settlement contract only; no executor is invoked and PROD never calls Ledger. The governing configuration is NOT re-read or re-interpreted after this step.

   Every per-seat monetary command uses `(class_id, FEAT-PROD-004, per_seat_intent_key)` as its Ledger reservation identity. The deterministic `per_seat_intent_key` is a versioned canonical encoding of the class-level run's `idempotency_key` and target seat identifier; it must distinguish every seat intent within the class without expanding Ledger's reservation identity tuple. Propagate `FEAT-PROD-004` as the active originating code and the key unchanged to its PROD event and Ledger reservation; never claim a nested `FEAT-PROD-003` execution. Reservation, all monetary effects, business records, and audit evidence share the run transaction; a failed run leaves no accepted per-seat command.
3. **Materialize interpretation (ITR).** Invoke Interpretation domain compute + materialize commands governed by `FEAT-ITR-001` and its materialization contract, never its FEAT executor, for the just-closed cycle, passing `class_id` and `payroll_cycle_id`. Interpretation produces one durable, immutable `interpretation_cycle_record` bound permanently to this `payroll_cycle_id` and the economic reference values in effect for the closed cycle (`DOM-ITR-001` §VIII–§IX). Interpretation is read-only over economic truth and MUST NOT mutate PROD, Ledger, or Policy state.
4. **Record completion (LAST before commit).** Write the persistent completion anchor for `(class_id, idempotency_key)` binding it to this run's `payroll_cycle_id`. This is the final step before commit: the anchor means "this entire economic-cycle transition completed", so it MUST NOT be written early as an in-progress marker. Because it is last and shares the one transaction, a completed-run identity survives **iff** settlement and interpretation both committed.
5. **Commit.** The owning FEAT transaction commits exactly once. On any step failure, the whole run fails closed and no partial cross-domain state — including the completion anchor — is committed, so a retry is a genuinely fresh attempt under the still-current closing-cycle configuration.

### Ordering guarantees

- Interpretation is materialized against the configuration that governed the **closing** cycle, and only after PROD settlement completes.
- Nothing is activated at the boundary. A change saved during the closing cycle is dated to the next boundary by its owning domain, so the next cycle — not the closing one — is the first it governs (`INV-ARC-015` §VI.7, `DOM-CLASS-003` §VII).

---

## VII. Temporal Rules

- The class-level run uses a single class-local evaluation time resolved once at step 1 and reused for all seats in the run.
- This FEAT does not reinterpret prior payroll boundaries; it consumes PROD's boundary derivation as-is.
- The materialized interpretation record is bound to the closed cycle and is never recomputed by any later run (`DOM-ITR-001` §VII).

---

## VIII. Invariants

1. `payroll_cycle_id` is generated exactly once per class-level run and stamped identically on every `payroll` event in the run.
2. The FEAT is the sole cross-domain orchestrator for payroll completion; no domain calls Interpretation directly.
3. Interpretation materialization is a declared, auditable, idempotent side effect of this FEAT.
4. Configuration governing the closing cycle is never mutated mid-run; the FEAT writes no configuration at all.
5. The run fails closed; partial cross-domain effects are never committed.
6. Replay under the same `idempotency_key` produces no duplicate settlement and no duplicate interpretation record.

---

## IX. Amendment

Version 1.3 (2026-10-03) supersedes the nested-FEAT wording of v1.2 with owning domain commands under FEAT-CORE-000 §V.1 and declares serialization shared with interval invalidation/recovery, including explicit Ledger/Identity/Class Configuration/Operations coordination and the actual originating monetary command namespace. Cycle completion authority and original historical configuration are preserved. Runtime implementation is not included. Revisions must increment version/date and preserve governing invariants.

### Version 1.4: prospective provenance foundation (2026-10-03)

Supersedes 1.3's exclusive writer wording only for canonical due system closure. Incorporates DOM-PROD-001 §XV.7–8 and [SPEC-PROD-001](../SPEC/SPEC-PROD-001_ATTENDANCE_INTERVAL_ELIGIBILITY_AND_PAYROLL_CORRECTION.md) §VI: preserve pair IDs, freeze version-1 settlement inputs, protect complete payroll summaries, and expose pure evidence queries. Every attendance writer locks its class/target seat before selection. New payroll composes `close_due_attendance_intervals` within one FEAT transaction before pricing; class completion resolves completed-run replay first and locks eligible seats in stable order. Audit linkage initializes once within creation and cannot change after commit. No nested FEAT, historical backfill, or correction button is authorized by this foundation.
