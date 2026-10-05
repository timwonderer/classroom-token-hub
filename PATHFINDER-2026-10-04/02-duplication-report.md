# Pathfinder 2026-10-04 — Duplication Report

> Descriptive analysis, not a normative document. Every verdict is decided by cited
> INV/DOM/FEAT/SPEC text; code is evidence of what IS, never of what SHOULD BE.
> All locations re-read in source at `main` @ 381a12d49 on 2026-10-04.

## Orchestrator synthesis

**Part A** (cross-feature, 16 confirmed concerns) and **Part B** (within-feature, 50 findings, 32 already
diverged in behaviour) were produced independently and overlap where a concern lives both inside
one domain and across domains. Overlaps are reported once in Part A and pointed to from Part B:
CC-1 ≡ A§4 (CWI), OB-1 ≡ A§6a (rent terms), PR-1 ≡ A§5 (interval pairing), PR-3 ≡ A§6b (hall-pass
settings), PR-6 ≡ A§10 (synthetic contexts), LG-1/LG-3 ≡ A§9, SE-2/SE-4 ≡ A§2/A§8, OA-2 ≡ A§16, IT-2 ≡ A§15.

**Disagreements resolved by the orchestrator**

1. *Passkey routes (B IT-3 vs A§15).* B proposes one role-parameterised implementation; A judges the
   teacher/sysadmin route split LEGITIMATE (different principals; DOM-IDEN-003 §VII excludes sysadmin
   from teacher step-up rules; `passkey_service` is already shared). **Ruling: A.** Keep two route
   sets; consolidate only the session-establishment tail and add the step-up DOM-IDEN-003 §VII requires
   on the teacher side.
2. *Audit chain walks (B OA-1 vs A refuted).* A refuted it as cross-feature only because it lives inside
   Operations. B shows the copies have diverged and the canonical `verify_chain` is the *weakest*
   (DOM-OPS-002 L86). **Ruling: B stands** as a within-feature correctness finding.

**Root causes (why duplication happened, from git history in A)**

- *The canonical path was incomplete, so callers routed around it:* FEAT-LED-000's plan builder
  is debit-only (A§1); `policy_reference_service` has no rent-terms read (A§6a); `resolve_base` has no
  as-of parameter (A§4); FEAT-POL-001 was never wired (A§3/§6).
- *The canonical component landed after its callers and they were never migrated:*
  `revoke_entitlement` 2026-10-03 vs inline writers 2026-09 (A§2); `list_attendance_interval_evidence`
  2026-10-03 vs day-read helpers 2026-07 (A§5); per-domain builders 2026-08-07 vs generic file
  2026-08-03 (A§12).
- *FEAT ids drifted away from their documents:* the `FEAT_REGISTRY` descriptions predate the
  renumbered FEAT docs (A§3).

**Owner rulings (given 2026-10-04, in chat — recorded here; the normative docs still need amending, see U13)**

- **R1 — Insurance acquisition.** The *purchase* (the first payment, which gains the insurance
  entitlement) is **STORE** (FEAT-STOR-001). *Establishing the recurring payment* (the bill cycle)
  is **OBL**. FEAT-OBL-004's purchase role is therefore void; ratified FEAT-STOR-001 v3.1
  (L28-32, L332), which routes insurance to FEAT-OBL-004, must be amended.
- **R2 — Hall-pass use.** Using a hall pass **does not write any STORE table**; it is owned by PROD.
  The PROD `hall_pass_logs` row is the consumption record. The Store `CONSUMED` write in
  `prod.py:232` → `entitlement_service.consume_hall_pass` (L418) is removed, and DOM-STORE-001 L471
  ("…and consumes the pass…") must be amended to match §VIII.E.6.
  The request queue is unaffected: a request is a queued use of an entitlement, so it stays in
  Store's `pending_actions` and is removed on approval or rejection (owner clarification, 2026-10-04).
  Grant = Store entitlement; request = Store pending action; use = PROD state change.
- **R3 — Sysadmin bug reward.** This is moving to a **badge-only** system (9 badges: 6 categorical
  plus 3 engineering milestones at 2/4/6, owner-confirmed). The ledger posting at `system_admin.py:1297` is retired, not unified. No
  normative document covers badges yet (a grep of INV/DOM/FEAT/SPEC/SOP finds only UI-badge
  mentions). **Owner:** badges are an operational concern granted by the sysadmin, not a business
  domain, so they belong to Operations (DOM-OPS-001 / SPEC-OPS-004). They need that governing text
  before they are built.
- **R4 — Docs behind the code.** Confirmed: DOM-ITR-001 v1.7 / SPEC-ITR-001 §16 (writer is built),
  DOM-IDEN-003 §V (`recovery_class_challenges`) and §IX (code hashing) must catch up.

**Correction applied:** the per-student hall-pass form (`admin.py:3747`) is broken; the bulk grant
path (`admin.py:8467`) works in production (owner-confirmed). The repeat-bulk-add no-op is PLAUSIBLE.

---

# Part A — Cross-feature duplication


---

## 1. Monetary posting: two idioms, with every credit outside FEAT-LED-000 — ACCIDENTAL (authority)

**Concern.** FEAT-LED-000 says every monetary action becomes a plan, is resolved, and only then is posted. Its §V
list includes payroll, admin adjustment, interest payout and savings transfer, and §XII.1/§XII.5 say "Plan Before
Posting" and "Single Posting Authority". SPEC-LED-002 §V says "Every new canonical effect MUST reference its command
reservation". The code uses two posting idioms:

- **Plan → resolve → apply (reserved):** `feats/rent_payment_feat.py:412-413`, `feats/store_purchase_feat.py:424`,
  `feats/insurance_premium_payment_feat.py:88-90`, `feats/insurance_coverage_renewal_feat.py:297`,
  `feats/attendance_interval_invalidation_feat.py:97,258,376,388`.
- **Direct `create_pending_transaction*`, with no plan and no reservation:**
  - `feats/prod.py:405`: payroll and manual credit. DOM-PROD-001 §XII says PROD never calls Ledger; FEAT-PROD-003 §VI.2 requires reservations.
  - `routes/system_admin.py:1297-1308`: bug reward posted from a route under FEAT-OPS-001. `actor_seat_id` is the student.
  - `feats/insurance_claim_feat.py:1984-2000`: insurance reimbursement. It also sets
    `original_transaction_id=source_transaction.id`, which the SPEC-ITR-001 §6.3 classifier reads as a
    **Reversal** (PLAUSIBLE misclassification).
  - `services/ledger_interest_service.py:378-389`: interest, run under `FEAT-LED-001` with `mechanism="self"`.
  - `feats/transaction_void_feat.py:244-257`: a zero-amount `void_item_removed` row.
- **Hand-rolled reservation:** `services/ledger_transfer_service.py:46-72` (see §9).

**Why they diverged (evident in code).** The plan builder accepts debits only. `ledger_resolution_service.py:70-72`
raises "Charge plans require a nonnegative canonical-account debit". So no credit can go through FEAT-LED-000, and
each credit-producing feature falls back to the low-level poster.

**Verdict.** ACCIDENTAL. Sources: FEAT-LED-000 §V, §VII.2, §XII.1, §XII.5; SPEC-LED-002 §V; DOM-PROD-001 §XII;
SPEC-OPS-004 §VII (sysadmin console "does not create … any ledger record").

**Owner and canonical component.** Ledger (DOM-LED-001). The canonical components are
`ledger_resolution_service.build/resolve` + `apply_resolved_ledger_plan` and the reservation in
`ledger_command_service.create_idempotent_transaction` (L140-185). The missing piece is a credit-plan builder.

---

## 2. Entitlement termination and purchase reversal written in three places — ACCIDENTAL (authority)

**Concern.** Store owns `entitlement_events` (DOM-STORE-001). FEAT-LED-002 L66 and L82 require Ledger to resolve linked
entitlements "through their owning-domain query" and, for REVERSE, to "invoke the Store domain command to append
`REVOKED`". FEAT-STOR-002 L178 adds: "A route or teacher action SHALL NOT directly revoke an ordinary purchased
entitlement independently of Ledger reversal authority."

**`REVOKED` writers.**

| Location | Domain/layer | Terminal-state guard |
|---|---|---|
| `routes/admin.py:10664-10681` (support resolve, `db.session.add` in route, under FEAT-SUP-001) | route | none, and no row lock on the issue (two concurrent resolves can both insert) |
| `feats/transaction_void_feat.py:186-242` (FEAT-LED-002) | Ledger FEAT writing a Store table | its own inline query (L189-198) |
| `services/entitlement_service.py:565-603` `revoke_entitlement` | Store command (canonical) | `get_entitlement_lineage_terminal_event` |
| `services/entitlement_service.py:349-394` hall-pass bulk revoke | Store, under FEAT-STOR-004 | FIFO over any provenance (store-entitlements D4) |

**Purchase-reversal eligibility, two rule sets.**
- `services/ledger_correction_service.py:34-90` `resolve_purchase_resolution_eligibility` (issue path). Any purchase whose grants are all still active.
- `feats/transaction_void_feat.py:140-206` (void path). Delayed-use items only; it raises `ImmediatePurchaseNotVoidable`.

**Terminal-event set re-declared.** `ledger_correction_service.py:22`, `insurance_claim_service.py:47`,
`collective_goal_expiry_feat.py:45`, `transaction_void_feat.py:197`, `routes/admin.py:3190`,
`entitlement_service.py:69`, `entitlement_read_service.py:123,166`. The canonical read is
`entitlement_read_service.get_entitlement_lineage_terminal_event` (L269) / `get_entitlement_status` (L362).

**Why they diverged.** `git log -S` shows the inline writers came first: `transaction_void_feat` in 2d2ace33f on
2026-09-07 and the support route in 8564ac75b on 2026-09-13. The canonical `revoke_entitlement` arrived later, in
766de17be on 2026-10-03 (#1473), and the older writers were never migrated to it.

**Verdict.** ACCIDENTAL. Sources: FEAT-LED-002 §VI (L66, L82); FEAT-STOR-002 L178; DOM-SUP-001 §I/§VII (Support does
not execute effects); INV-ARC-021 §V.1-V.2.

**Owner and canonical component.** Store. `entitlement_service.revoke_entitlement`, invoked by a FEAT. Support and void
should share one Ledger reversal entry (FEAT-LED-002).

---

## 3. FEAT-code identity misattribution feeding two provenance classifiers — ACCIDENTAL (correctness)

**Concern.** DOM-LED-001 §VII.1 (L104-106) says `feat_code` "identifies the originating command family". Ledger stamps
`feat_code=get_active_feat_name()` (`ledger_resolution_service.py:288,301`, `ledger_recovery_service.py:253`,
`ledger_fee_service.py:24`). Two consumers classify rows by `feat_code`:
- `services/ledger_provenance_query_service.py:58-74`: `SYSTEM_ORIGINATED_FEAT_CODES` (SPEC-ITR-001 §6.3).
- `services/interpretation/income_origin.py:64-75`: `TEACHER_ADMIN_FEAT_CODES` and `INTEREST_ACCRUAL_FEAT_CODES` (SPEC-ITR-001 §10.2).

Both classifiers are keyed to `FEAT_REGISTRY` (`feats/base.py:196-263`). Its descriptions contradict the FEAT
documents:

| FEAT id | Registry description | Document title |
|---|---|---|
| FEAT-LED-001 | "Overdraft Fee Application" | Post Ledger Transaction |
| FEAT-OBL-001 | "Rent Payment" | Assess Obligation |
| FEAT-OBL-003 | "Scheduled Insurance Cycle" | Satisfy Obligation |
| FEAT-OPS-001 | "Maintenance/Cleanup" | Audit Protected Emission |

**Confirmed consequences.**
- `insurance_premium_payment_feat.py:114` runs student self-payments (`mechanism="self"`, L70) under `FEAT-OBL-003`.
  That id is in `SYSTEM_ORIGINATED_FEAT_CODES` as "Scheduled Insurance Cycle", so student premium payments count as
  system-originated. Rent self-payment (FEAT-OBL-001) is excluded from the set, so the two obligation payments are
  classified differently.
- Student transfers run under `FEAT-LED-000` (`student.py:1624-1626`), which is in the system set. Its own comment
  (L56-57) says transfers are "deliberately excluded".
- Interest posts under `FEAT-LED-001` (`scheduled_tasks.py:718`). `INTEREST_ACCRUAL_FEAT_CODES` is empty
  (`income_origin.py:72`), so ITR category 2 can never fire.

**Catch-all ids spanning domains.**
- `FEAT-OPS-001`, 10 sites:
  - sysadmin login (`system_admin.py:144`)
  - teacher and sysadmin passkey routes (`admin.py:10118,10195,10252`; `system_admin.py:265,348,404`)
  - support update and resolve (`system_admin.py:894,1231`)
  - `scheduled_tasks.py:139`
- `FEAT-IDEN-001`, 7 sites: student login/switch (`student.py:2901,3135`), teacher login and set-class
  (`admin.py:2204,2597,3080,3278`), and sysadmin creation (`cli_commands.py:141`).
- `FEAT-SETTINGS-001`: Policies writes at `admin.py:4618,4926,5015,5256` and `feats/attendance.py:71,115`. No
  document exists for this id.
- `FEAT-ADMN-001`: `admin.py:7858`, registered to the "Logistics" domain.
- `FEAT-POL-001` has **zero** call sites, although DOM-POL-001 §VI.1 L133 says "FEAT-POL is the only surface".
- `FEAT-OBL-005` (no document) at `cancel_insurance_feat.py:86`, and the unratified `FEAT-OBL-004` at
  `purchase_insurance_feat.py:91`.

**Why they diverged.** The registry descriptions predate the renumbered FEAT documents. The comment at `base.py:249-254`
records the OBL/OBLI split, and FEAT-CLASS-007 is reserved for FEAT-SETTINGS-001's successor at L233-234.

**Verdict.** ACCIDENTAL. Sources: DOM-LED-001 §VII.1; SPEC-ITR-001 §6.3 (L174), §10.2; DOM-POL-001 §VI.1; FEAT-OPS-001
title and scope.

**Owner.** Each FEAT document owns its id. Ledger owns the provenance set (SPEC-ITR-001 §6.6 defers the enumeration to
the implementer).

---

## 4. CWI derived in five places, with different numeric rules — ACCIDENTAL (money)

| Site | Arithmetic | Hours = 0 | As-of |
|---|---|---|---|
| `services/economic_engine.py:286-325` `resolve_base` (declared canonical) | Decimal, CWI quantized to cents | `cwi=None` (L314 guard) | current |
| `services/class_configuration_query_service.py:423-456` `calculate_cwi` | float, unquantized | 0.0 | current |
| `utils/economy_balance.py:256-320` `CWIBalanceChecker.calculate_cwi` | Decimal, quantized | 0 | current or override |
| `services/class_configuration_economic_service.py:43-56` `_compute_cwi_from_payroll` | float | 0.0 | current |
| `services/interpretation/reference_configuration.py:62-71` | Decimal, unquantized | 0 | payroll row as-of the boundary, **engine current** |

The two `economy_balance` and `class_configuration_economic_service` docstrings call themselves "a pre-existing
duplicate formula site". `class_configuration_view_models.py` uses both `calculate_cwi` (L202) and `resolve_base`
(L238) in one module.

**Money impact (PLAUSIBLE).** `get_banking_directive` feeds the float CWI to Ledger:
`class_configuration_query_service.py:757,772` → `ledger_resolution_service.py:141`
`_quantize_currency(directive.cwi * rate)`, used for the progressive overdraft fee. A quick arithmetic check
reproduced a one-cent difference. With pay_rate 0.0125/min, 6.33 hours and rate 0.10, the float path gives a fee of
$0.47 and the `resolve_base` path gives $0.48. Hours = 0 also gives a $0 CWI rather than "not ready".

**Why they diverged.** `resolve_base` arrived in 02d412e6b (2026-08-28) and the older sites were kept "during the
conservative migration". ITR could not call it because `resolve_base` has no as-of parameter. ITR needs the engine and
pay rate in force at the cycle boundary (DOM-ITR-001 §VII/§IX), and the engine-current read is itself a deviation
(interpretation flowchart, deviation 1).

**Verdict.** ACCIDENTAL. Sources: SPEC-ECON-003 §1 ("single canonical technical source"), §2 ("CWI derivation"), §4.1;
DOM-ITR-001 §II L56 (CWI derivation is "under CLASS authority"); INV-ITR-004.

**Owner and canonical component.** Class Configuration. `economic_engine.resolve_base`, which needs an as-of variant.

---

## 5. Attendance interval pairing: live reads use the legacy rule — ACCIDENTAL (correctness, reaches Store)

**Canonical pairing.** `services/attendance_service.py:252-314` `list_attendance_interval_evidence`. A repeated
`active` continues the session, and each interval is capped at its own class-day end. Payroll uses it
(`calculate_seat_payroll_intervals` L381, settlement, pricing).

**Legacy pairing on live paths.** `attendance_service.py:111-139` `_pair_active_intervals` restarts on every `active`
and clips only to the queried day window. A still-open session from an earlier day is counted from today's start.
Its callers are `calculate_worked_attendance_seconds_for_date` (L504-529) and `…_today` (L532-559). Store uses the
first for insurance lost-time compensation: `feats/insurance_claim_feat.py:917,1002,1460,1478`. Insurance payouts and
the student "Time Today" figure therefore use a different pairing than payroll.

**Repeated `active` rows can occur.** Writers read state before taking the lock (productivity flowchart, deviation 8),
so the two rules can disagree on real rows.

**Other copies.**
- `app/attendance.py:51` `_calculate_active_seconds_for_range` is dead in `app/` (only
  `tests/dom/attendance/test_attendance.py:9` imports it) and uses UTC days.
- `services/payroll/corrections.py:128` `_replayed_paid_seconds` is a **legitimate** copy. It reproduces the pinned
  legacy rule for historical correction, which DOM-PROD-001 §683 requires ("The pinned legacy repeated-active restart …
  must be reproduced").

**Why they diverged.** `_pair_active_intervals` dates from db7079c7d (2026-07-21). The canonical pairing landed in
81ea0fff5 (2026-10-03), and the day-read helpers were not migrated.

**Verdict.** ACCIDENTAL for the live helpers. Sources: DOM-PROD-001 L116 ("An interval is the canonical completed …
pair … The domain pairs its ordered timeline") and L667 (legacy clipping "is not a compatibility path for new
payroll").

**Owner.** PROD, `list_attendance_interval_evidence`.

---

## 6. Policy reads and writes outside Policies: frozen lookups, "current" selection, and supersede — ACCIDENTAL

**(a) Rent terms by `policy_uuid`, hand-rolled at 10 sites.**
- `obligations_service.py:225,236`
- `obligation_view_model.py:204`
- `reconcile_rent_feat.py:299` (no `class_id`) and `:324` (class-scoped)
- `rent_payment_feat.py:350-356`: falls back to the *current* settings when the uuid does not resolve.
- `routes/student.py:581,605`
- `routes/admin.py:1768,1787,5156`

The canonical module `services/policy_reference_service.py` resolves exact versions class-scoped with `one_or_none`
(`get_bill_preview_days` L149-175, `get_insurance_recurring_terms` L111). It exposes **no rent-terms read**, which is
the evident reason the callers hand-roll one.

Sources:
- DOM-POL-001 §VII L170: "MUST NOT substitute a newer, active, latest … version". `rent_payment_feat`'s fallback
  breaks this.
- DOM-POL-001A §V.E L156: "Obligations does not open `rent_settings` … and does not branch on the family".
- INV-ARC-021 §V.1.

**(b) "Current hall-pass policy", two selection rules.**
- In force = newest `IN_USE`: `feats/attendance.py:9-25` and `class_configuration_query_service.py:388-415`
  (identical bodies). `api.py:1146` delegates to the latter.
- In force = newest `effective_date ≤ t`, ignoring availability: `feats/prod.py:86-94` and `:205-213` (twice in one call).

DOM-POL-001 §VI.1-§VI.2 make time-based selection exclusive to `payroll_settings`. `hall_pass_settings` is
availability-selected, so the PROD rule is the defect.

**(c) "Current rent for a class", two orders.** `student.py:568-605` takes the current cycle first and falls back to
the latest. `admin.py:1766-1795` takes the latest policy first; its uuid and cycle branches after `latest_policy` are
effectively dead. The two answer different questions: what students face now, versus guidance on the latest
configuration (comment L1774-1778). Separate helpers are LEGITIMATE. The duplicated frozen lookup inside them is not.

**(d) Supersede written four ways** under four non-POL FEAT ids:
- `admin_settings_service.py:49-81`: rent, insert then retire.
- `feats/attendance.py:98-111`: hall pass, retire, flush, then insert.
- `store_service.py:304-322`: store, retire then publish.
- `feat_class_003…py:466-480`: insurance, retire, guard, then insert.

Two availability state machines exist with no RETIRED→IN_USE guard: `store_service.py:325-331` and
`insurance_definition_service.py:180`. Source: DOM-POL-001 §VI.1 (FEAT-POL is the only surface; RETIRED is permanent).

**Payroll is the counter-example.** `payroll_settings` is read only through `services/payroll/settings.py:43,237`,
which satisfies the §VI.2 "One resolver" rule.

**Owner.** Policies. `policy_reference_service` for frozen reads, and FEAT-POL-001, which is unused, for writes.

---

## 7. Hall-pass exercise recorded twice (Store `CONSUMED` + PROD `hall_pass_logs`) — ACCIDENTAL (duplicated state), owner check advised

`feats/prod.py:228-240` (FEAT-PROD-002) calls `entitlement_service.consume_hall_pass` (L418-448), which inserts a Store
`CONSUMED` event, in the same transaction as the `hall_pass_logs` row. Store's hall-pass balance is derived as
GRANTED − (CONSUMED + EXPIRED + REVOKED) (`entitlement_read_service.py:81,123`). That derivation is the evident reason
the duplicate exists.

**Verdict.** ACCIDENTAL. Sources:
- DOM-STORE-001 §VIII.E.6 L445: "not create a duplicate Store-and-Entitlements `CONSUMED` row when another domain is
  the authoritative consumer".
- FEAT-STOR-002 L102 and L113: "No duplicate Store-owned consumption row is created".

Because the docs forbid the duplicate, the hall-pass balance would have to be derived from a PROD read instead.
DOM-STORE-001 L471 ("approval writes the `hall_pass_logs` record and consumes the pass") can be read as calling for
the Store row. Read alongside L436-445 it fits "the log is the consumption", but the owner should confirm that reading.

This item concerns consumption only. The bulk hall-pass **grant** path (`admin.py:8467` → `execute_hall_pass_adjustment`) works
in production; only the per-student form at `admin.py:3747` is broken, and the repeat-bulk-add no-op is PLAUSIBLE, not
confirmed.

---

## 8. "Seat has active insurance coverage" defined three or more ways — ACCIDENTAL

- `entitlement_read_service.py:415-457` `has_active_insurance_coverage`: GRANTED for the policy and no EXPIRED/REVOKED.
- `entitlement_read_service.py:460-499` `get_active_insurance_grant`: the same, plus an Obligations
  `get_default_payment_target` check.
- `routes/student.py:2108-2121` `_active_insurance_entitlement_id`: a route-level re-derivation with no premium check.
- `insurance_coverage_service.py` usability (`InsuranceUsability`, L208): grant, terminal, coverage period and premium.
- Related: `cancel_insurance_feat.py:70-83` derives lineages from OBL assessments, and `purchase_insurance_feat.py:142`
  runs its own GRANTED query.

**Verdict.** ACCIDENTAL. Sources: DOM-STORE-001 §VIII.E.1 (the coverage lifecycle is Store's); INV-ARC-021 §V.5
(consumers must not re-derive).

**Owner.** Store. One coverage read in `insurance_coverage_service`.

---

## 9. Seat-lock serialization and reservation replay open-coded — ACCIDENTAL (one SPEC breach, otherwise maintenance)

**Locks.** INV-LED-015 (DOM-LED-001 L75) fixes the lock order: seat, then ClassEconomy, then transactions. The seat
lock is open-coded in nine FEATs:
- `transfer_feat.py:48-53`
- `store_purchase_feat.py:166-170`
- `rent_payment_feat.py:289-291`
- `purchase_insurance_feat.py:130-132`
- `insurance_premium_payment_feat.py:135`
- `insurance_coverage_renewal_feat.py:340-342`
- `direct_entitlement_grant_feat.py:183-189`: locks `Seat` **by id with no class filter** before checking class.
- `prod.py:384-385`, via `lock_attendance_seat` (`attendance_service.py:322`) plus ClassEconomy.
- `ledger_posting_service.py:20-21`, which repeats on every effect.

Ledger exposes `lock_ledger_seats` and `lock_recovery_scope` (`ledger_recovery_service.py:288-313`).

**Reservation replay.**
- `ledger_command_service.py:147-183` handles the uniqueness conflict with a savepoint and an IntegrityError
  lookup-and-compare.
- `ledger_transfer_service.py:46-61` does a plain `.first()` then `add`, with no savepoint and no IntegrityError path.
  A concurrent duplicate surfaces as a generic error. **This breaches SPEC-LED-002 §6.2-§6.3** ("A uniqueness conflict
  MUST NOT be reported as a generic duplicate").
- `ObligationCommandReservation` (`schedule_next_bill_cycle_feat.py:204-223`, `obligations_service.py:1008`) is
  **LEGITIMATE**. It is a separate Obligations-owned table under DOM-OBL-001 §V.7, and only the algorithm shape is shared.

**Owner.** Ledger, `ledger_command_service` and `ledger_recovery_service` lock helpers.

---

## 10. Context fabrication and teacher-seat re-resolution — mixed

**Synthetic teacher `CanonicalContext` for system jobs, three copies.** `scheduled_tasks.py:75-80` (daily limit),
`:317-322` (auto payroll) and `services/payroll/settlement.py:80-93`. DOM-IDEN-006 governs authenticated request
runtime, and `identity_service.resolve_teacher_seat_for_class` (L12-18) is documented as "the Identity-owned operation
for scheduled/system transitions". The pattern is therefore **LEGITIMATE**. Only the triplication is accidental
maintenance.

**Alternate constructor in authenticated runtime.** `app/__init__.py:787-792` builds a `CanonicalContext` for
*another* class to fetch display metadata. This is **ACCIDENTAL** under DOM-IDEN-006 §XII ("alternate constructors for
`canonicalContext`" are prohibited). The impact is display-only.

**Request-time re-resolution.** `routes/admin.py:855` `_get_teacher_seat_for_class` wraps
`resolve_teacher_seat_for_class` for request handlers (8 call sites in admin.py), even though `g.canonical_context.seat_id`
already is the teacher seat. **ACCIDENTAL** under DOM-IDEN-006 §IX ("re-resolve context inside helper functions") and the
resolver's own docstring.

---

## 11. Withdraw untouched future rent assessments: CLASS-004 re-implements the Obligations selection — PARTLY ACCIDENTAL

- `feats/terminate_bill_cycle_feat.py:108-129` (OBL): selects future cycles and withdraws unsatisfied assessments.
- `feat_class_004_feature_enablement.py:163-187` (CLASS): the same selection, querying `BillCycle` and
  `ObligationAssessment` directly. It filters `obligation_type="RENT"` only, while OBL takes all types.

**Verdict.**
- That CLASS-004 coordinates the withdrawals is **LEGITIMATE**: DOM-OBL-001 §IX.15 says "The disabling FEAT coordinates
  the withdrawals", and it calls OBL's `withdraw_assessment`.
- That it **selects** from Obligations tables itself is **ACCIDENTAL**: INV-ARC-021 §V.1 and §V.4.

**Owner.** Obligations needs one "untouched assessments at or after instant" query.

---

## 12. Generic presentation builder alongside domain builders — ACCIDENTAL

`services/view_model_builders.py` holds Identity and Store builders. The live ones are `build_identity_profile_view`
(called at `admin.py:1267,3343`) and `build_store_management_view` (`admin.py:4787`). `build_entitlement_list_view`,
`build_purchase_history_view` and `build_policy_list_view` have no app callers.

Domain-local builders already exist in `services/identity/builders.py` and `services/store/builders.py`.
`obligation_view_model.py` is Obligations-local but is placed outside `obligations/builders.py`, and it reads
`rent_settings` directly (§6a).

**Why they diverged.** The generic file dates from 2026-08-03/04 (#1294, #1302). The per-domain organization arrived
on 2026-08-07 (#1315), and the generic file was not migrated.

**Verdict.** ACCIDENTAL. Sources: SPEC-UI-001 §IX ("Cross-domain pages SHALL compose domain-owned builders rather than
replacing them with generic presentation builders"); INV-ARC-021 §V.5 ("MUST NOT centralize domain presentation into a
single generic builder").

---

## 13. Error persistence split across two raw-engine writers — ACCIDENTAL

- `app/__init__.py:155-189` inserts into `error_events`, behind an `inspector.has_table` guard.
- `services/operational_event_service.py:91-110` inserts into `operational_events`.
- `tlcp.py:53` also gates on `error_events`.

Migration `7c3d4e5f6a7b_drop_all_unauthorized_tables.py:202-205` dropped `error_events` with the note "absorbed into
operational_events (DOM-OPS-001)". The unhandled-exception path therefore writes nothing. The sysadmin "recent errors"
view reads `operational_events` at ERROR or above (L140-171), whose only writers log `warning`.

**Verdict.** ACCIDENTAL. Source: INV-OPS-009 (failure visibility), via DOM-OPS-001.

**Owner.** Operations, `operational_event_service`.

---

## 14. Teacher-seat authority predicate at four strengths — ACCIDENTAL (low; the context is trusted)

| Location | Checks |
|---|---|
| `feat_class_004…py:228-240`, `:436`; `feat_class_005…py:269` | `actor_role` + `seat.class_id` |
| `feat_class_008…py:75-86` | `verify_teacher_owns_class` + seat role + `user_id` |
| `identity_service.py:120-131` `resolve_teacher_target_seat` | role + `user_id` + class |
| `announcement_service.py:8-10` | role + class, no user |
| `identity_feat.py:143,422,691,755` | four further inline copies |

**Owner.** Identity (INV-ARC-019; DOM-IDEN-006 §VII `actor_role`). Low risk while every caller receives a
resolver-built context. §10 shows that is not universal.

---

## 15. Principal session establishment, four copies with three clearing behaviours — ACCIDENTAL (low)

| Path | Location | Clearing |
|---|---|---|
| Teacher TOTP | `admin.py:2566-2568` (login entry), `:2596-2614` | pops `user_id`, nonce and `last_activity` only |
| Teacher passkey | `admin.py:10222-10234` | `session.clear()` |
| Sysadmin TOTP | `system_admin.py:181-187` | `session.clear()` |
| Sysadmin passkey | `system_admin.py:374-381` | no clear |

`auth.establish_*_session` (`auth.py:390-410`) sets keys only and does not own principal replacement. Any stale keys
would be ignored for sysadmins, because the resolver keys sysadmins off `user_role` (`context_resolver.py:106-111`), so
there is no class-context leak. The concern is session hygiene. **PLAUSIBLE.**

The teacher and sysadmin passkey **routes** are near line-for-line copies (`admin.py:10081-10274` vs
`system_admin.py:227-429`), but they serve different principals. DOM-IDEN-003 §VII excludes sysadmin, and
`passkey_service` is already shared, so the route split is **LEGITIMATE**. Only the session tail is accidental.

---

## 16. Ledger protected-field list: emitter copy versus verifier registry — ACCIDENTAL (maintenance; equal today)

- Emitter: `ledger_posting_service.py:8-13` (`_TRANSACTION_AUDIT_FIELDS[_V2]`).
- Verifier: `utils/audit_verifier.py:42-46` (`PROTECTED_FIELDS_BY_TABLE["ledger_transaction"]`) and `:50-61`
  (`LEDGER_FIELDS_BY_VERSION`).

The PROD emitters read the verifier registry (`prod.py:401-402`; `attendance_interval_invalidation_feat.py:344,353`).
Ledger keeps its own copy. The lists match by inspection today, but parity depends on manual sync.

**Verdict.** ACCIDENTAL. Source: DOM-OPS-002 INV-OPS-019 and L262 ("register these exact fields in its emitter and
verifier").

---

## Refuted candidates

- **#6 Temporal "now" and "later-than" wrappers.** All of them (`obligations_service.py:532,677,686`,
  `obligation_view_model.py:39`, `reconcile_rent_feat.py:237`, `schedule_next_bill_cycle_feat.py:114`,
  `insurance_coverage_service.py:200`, `insurance_coverage_renewal_feat.py:124`, `payroll/pricing.py:153`) delegate
  to `canonical_temporal_resolver`. This is adapter boilerplate, about 33 `SimpleNamespace(class_id=…)` contexts in 19
  files, not re-implementation.
  - Raw `utc_now()` at `reconcile_rent_feat.py:355` is a single deviation, not duplication.
  - Rent-period steppers by raw UTC delta (`api.py:145-191`, `student.py:2593-2616` via `admin.py:867`) duplicate
    `rent_schedule_service.advance_due_date`, but are **dead**: neither `_calculate_due_dates` nor
    `_count_rent_waiver_periods` has a caller.
- **#7 `prod.py:61`.** `_latest_hall_pass_attendance_state` derives hall-pass state; it is not interval pairing.
  `corrections.py:128` is a legitimate historical replay (DOM-PROD-001 §683).
- **#12 Issue view helpers.** `admin._issue_to_view` (L10325) and `system_admin._issue_to_view` (L667) differ by
  design. The sysadmin view enforces public-id-only identification and consent-gated class labels (DOM-SUP-001
  §VI/§VII). LEGITIMATE. The issue-ref resolvers are one-line wrappers.
- **#14 "Enabled features" listing ×4** (`admin.py:6531,7917,8844`; `economy_rebalance.py:190`). These are identical
  one-line comprehensions over the canonical `is_feature_enabled`, all inside Class Configuration. Trivial and not
  cross-feature.
- **#15 Missing audit emission (ACT-IDEN, ACT-OBL).** The only call sites of `audit_protected`/`emit_audit_event` are
  row-level, in Ledger and PROD. No feature implements its own command-level audit, so this is absence, not divergent
  duplication. The only `ACT-` string in `app/` is `ACT-OBLI-001`, in a deferral comment.
- **#5 (part) Obligation versus Ledger command reservations.** These are separate domain-owned tables. LEGITIMATE (see §9).
- **#11 (part) Audit chain walk and HMAC ×3** (`audit_verifier.py:117,569,725`). This sits inside Operations. The
  primitives are imported from `audit_service`, and `audit_service.verify_chain` is a delegator. It is maintenance
  duplication within one feature, not cross-feature.
- **Payroll-settings readers.** The single resolver is respected (`payroll/settings.py:43,237`).
- **#8 (part) Synthetic contexts in scheduler jobs.** LEGITIMATE as a mechanism (see §10).

---

# Part B — Within-feature duplication


## F1 class-configuration

### CC-1 [D] CWI formula — 4 in-feature copies, 3 numeric behaviours
- `app/services/economic_engine.py:286-325` `resolve_base` — Decimal, `_money` ROUND_HALF_UP, **CWI = None when hours ≤ 0** (declared canonical in its own and its siblings' docstrings).
- `app/services/class_configuration_query_service.py:423-456` `calculate_cwi` — float, unrounded, returns `0.0` when hours = 0.
- `app/services/class_configuration_economic_service.py:43-56` `_compute_cwi_from_payroll` — float, unrounded, `0.0` at hours = 0.
- `app/utils/economy_balance.py:256-320` `EconomyBalanceChecker.calculate_cwi` — quantizes **hours** to cents *before* multiplying, reads the engine itself (not via `resolve_expected_weekly_hours`), swallows engine exceptions and returns None.
- Divergence: hours = 0 → `None` (canonical) vs `0.0` (two float copies); rounding differs (cents vs none vs pre-rounded hours). Callers: `class_configuration_view_models.py:202` uses the float copy while `:238` in the same module uses `resolve_base` — one page can show two CWIs.
- Doc: SPEC-ECON-003 §1 ("single canonical technical source") + §4.1. `resolve_base` is the copy the two non-canonical copies themselves name as authority.
- Target: **delete** the three copies; callers read `resolve_base(class_id).cwi` (economy_balance keeps only its notes/breakdown wrapper over `resolve_base`).
- Cross-feature pointer: a 5th copy in interpretation (`interpretation/reference_configuration.py:62-71`) also reads `expected_weekly_hours` *now* while reading pay rate *as of* `cycle_completed_at` — DOM-ITR-001 §242 requires inputs "in effect for the cycle". Use `economic_engine_effective_at(class_id, cycle_completed_at)`.

### CC-2 [D] Interest/compound validation — route vs FEAT disagree
- `app/routes/admin.py:8809-8827` (route) couples `simple ⇒ never` and `compound ⇒ daily|weekly|monthly`.
- `app/feats/class_configuration/feat_class_005_economic_engine_evolution.py:49-85` `_validate_engine_field` validates each field independently: accepts `compound` + `never`, and `simple` + `daily`.
- Doc: SPEC-ECON-003 §5.6 — `never` *is* "simple interest". The route matches; the FEAT (the only lawful write surface) does not, so any other FEAT-CLASS-005 caller (rebalance, transition) can persist a contradictory pair.
- Target: move the coupling check into `_validate_engine_field` (cross-field pass) and delete the route copy.

### CC-3 [D] Economic policy-mode readers — 4 implementations, one reads a retired source
- `app/services/economic_engine.py:131` `_normalize_mode` (via `resolve_base`).
- `app/utils/economy_policy.py:403-419` `get_active_policy_mode_for_class` (engine in force, normalized, default on miss).
- `app/services/class_configuration_query_service.py:467-490` `get_policy_mode` (raw, un-normalized, **None if payroll feature disabled**).
- `app/utils/economy_policy.py:389-400` `get_active_policy_mode(user_id, …)` reads **`FeatureSettings.economy_policy_mode`** (`models.py:2747`) — user-keyed, not class-scoped. Reached from `economy_balance.py:149` whenever `EconomyBalanceChecker` is built without a `class_id` (admin.py 6602/6789/9880/9996 pass `getattr(payroll_settings,"class_id",None)`, i.e. None when no payroll row).
- Doc: DOM-CLASS-003 / SPEC-ECON-003 §3 — the Economic Engine version in force owns the mode; `class_id` is the only scope.
- Target: keep `resolve_base(...).economy_policy_mode`; delete `get_active_policy_mode` and the FeatureSettings fallback; `get_policy_mode` becomes a thin read of `resolve_base`.

### CC-4 [S] FEAT-CLASS-004/005 preamble copied 3× (~45 + ~30 lines each)
- Context/teacher-seat/class validation: `feat_class_004_feature_enablement.py:209-255`, `:408-455`; `feat_class_005_economic_engine_evolution.py:241-288` — byte-identical except result class and message.
- `effective_at` parse + not-in-past: `feat_class_004…:308-345`, `:482-519`; `feat_class_005…:346-383` — identical.
- `_parse_effective_at_timestamp`: `feat_class_004…:41` and `feat_class_005…:124` — identical.
- Target: one private helper module in `app/feats/class_configuration/` returning `(error_code, message)`; no behaviour change.

### CC-5 [S] "Enabled feature list" comprehension ×4 + hardcoded valid set
- `admin.py:6531-6532`, `:7917-7918`, `:8844-8845`; `economy_rebalance.py:190-193`. Hardcoded `{'payroll',…}` at `admin.py:9300` duplicates `ClassFeature.feature_names()` (`models.py:2666`).
- Target: one `enabled_features(class_id)` in `class_configuration_query_service`; replace the literal set with `ClassFeature.feature_names()`.

### CC-6 [D, low] Pointer clear after class destruction
- `admin.py:4008-4010` clears `last_active_*` unconditionally; `admin.py:4200-4203` clears only if the pointer names the destroyed class. INV-ARC-012 §V asks only that the destroyed class not survive as a pointer — the conditional copy is the precise one.
- Target: one helper with the conditional form.

Dropped: "engine in force now" wrapper (`admin.py:1800`, a 3-line pass-through); timezone canonicalization (callers already share `canonicalize_class_timezone`); rebalance loop `admin.py:6639/6672` (2 × 8 lines, consistent); `_owner_for_change` (same function called 3×, not a copy).

---

## F2 identity-student

### IS-1 [D] Seat + IdentityProfile builders — 4 copies, 3 behaviours, 2 dead
- `app/services/classroom_setup.py:159` `create_student` — `profile_type="student_claimed"/"student_unclaimed"`; **tests only**.
- `:254` `create_student_seat_with_profile` — sets claim hashes, no `roster_fingerprint`, `profile_type="student"`; live via `identity_feat.py:153`.
- `:294` `update_or_create_roster_seat` — renames profile **without touching claim hashes and without a claimed check**; only caller is `feat_class_002…:219` `execute_modify_student`, which is exported but has no app caller (admin rename goes through `admin.py:3770-3835`).
- `:330` `create_roster_student_seat` — caller supplies hashes/fingerprint; live via `identity_feat.py:721`.
- Doc: DOM-IDEN-005 "Why the display name moves with the claim key" + DOM-IDEN-002 §VIII.7. `update_or_create_roster_seat` would violate it if reached (its caller guards at feat_class_002:187, so the helper itself is the unsafe copy).
- Target: delete `create_student`, `update_or_create_roster_seat` and `execute_modify_student`; make `create_student_seat_with_profile` delegate to `create_roster_student_seat`.

### IS-2 [D] Join-code → unclaimed seat → hash match → dedupe, copied
- `app/feats/identity_feat.py:182-246` (FEAT-IDEN-001 claim) vs `:513-584` (FEAT-IDEN-005 bind) — ~55 duplicated lines.
- Divergence: bind filters `claimed_at IS NULL` and locks class/principal/seats; claim filters only `user_id IS NULL`, unlocked. Claim is verification-only (bind re-checks generation later), so the gap is latent, but DOM-IDEN-002 §VIII defines *unclaimed* as both NULL — the bind copy matches.
- Target: one `_match_unclaimed_seat(class_row, first, last, dedupe, lock=bool)` used by both.

### IS-3 [D, low] "Seat still unclaimed at this generation" ×4
- `student.py:448-449` (checks `claimed_at`), `student.py:525` and `:771` (omit `claimed_at`), `identity_feat.py:341-342` (checks both, under lock).
- Doc: DOM-IDEN-002 §VIII unclaimed = `user_id IS NULL AND claimed_at IS NULL`.
- Target: a `seat_is_claimable(seat, generation)` predicate in `identity_service`.

### IS-4 [D, low] Onboarding session-key cleanup ×6, different key sets
- `student.py:765-769`, `:949-954`, `:2949-2953`; `recovery.py:69-71`, `:78-86`, `:94`. `recovery.py:80-86` pops `username_generation_id` / `username_retention_*` by hand; the student copies call `_clear_username_retention_state()`; `theme_*` popped in only some.
- Target: one `clear_onboarding_session()` in `student.py` next to `_clear_username_retention_state`.

### IS-5 [D, low] Teacher-seat-in-class authorization ×6, two strengths
- With ownership check (`classroom.teacher_user_id == user_id`): `identity_feat.py:422-426`, `:691-696`, `:755-758`.
- Seat-only: `identity_feat.py:143-145`, `identity_service.py:120-122`.
- No co-teachers exist, so not exploitable today; still two definitions of the same authority.
- Target: `verify_teacher_owns_class` (`class_configuration_query_service`) + seat check in one helper.

Dropped: claim-code alphabet (two constants, two purposes, one line); claimed-seat rename (covered by IS-1); `last_active_*` setters (2-line idiom); seat removal (two deliberately different scopes).

---

## F3 identity-teacher

### IT-1 [D] Teacher account teardown: 5 "residual" helpers are dead after the class loop
- `app/services/teacher_destruction.py:229-303` — `_delete_teacher_residual_ownership_rows`, `…settings_activity_and_audit_rows`, `…rent_rows`, `…insurance_rows` (literally `_ = class_ids_subq`), `…issue_rows` — each rebuilds `ClassEconomy.teacher_user_id == user_id` (5×).
- `_destroy_teacher_account_rows` (`:369-380`) calls them **after** looping `_destroy_class_scope_rows`, which deletes the `ClassEconomy` row (`:213`). Every subquery is therefore empty; the helpers delete nothing.
- They also diverge from the class-scope copy they shadow: issue teardown deletes `IssueStatusHistory` at `:298-300` but the live path `:163-166` does not (FK `ondelete=CASCADE`, `models.py:2423`, so harmless). PendingAction purchase subquery is built twice in `_destroy_class_scope_rows` (`:111-136`, `:191-203`).
- Doc: DOM-IDEN-003 / FEAT-IDEN-007 — the class universe is destroyed through `_destroy_class_scope_rows`; residue is credentials/recovery/users only.
- Target: **delete** the five helpers and the second PendingAction block; keep `_delete_teacher_recovery_and_credentials_rows`.

### IT-2 [D] Sign-in session establishment ×2 teacher (+×2 sysadmin), already diverged
- Teacher TOTP `admin.py:2595-2613`: pops 3 keys only (`:2481-2483`), FEAT-IDEN-001, display cache = seat profile name.
- Teacher passkey `admin.py:10219-10234`: `session.clear()`, FEAT-OPS-001, display cache = username, sets `permanent` twice.
- Sysadmin passkey `system_admin.py:376-381` does **not** clear the session; sysadmin TOTP `:181-187`.
- Doc: DOM-IDEN-003 §"Session Establishment" (L187-192): `current_session_started_at` and `current_session_expires_at` written at sign-in. **No copy writes them** (only `student.py:2961-2962` does). Consolidating fixes it once.
- Target: extend `establish_teacher_session` / `establish_sysadmin_session` (`auth.py:390-401`) to do the whole sequence (clear, nonce, started/expires, timestamps).

### IT-3 [D] Passkey routes teacher vs sysadmin (~190 lines, 91 diff lines)
- `admin.py:10081-10274` vs `system_admin.py:227-429`. Divergences: register-finish identity failure 404 vs 409; auth-finish session clear (IT-2); `next` redirect honoured only for sysadmin.
- Both omit step-up for register/remove — DOM-IDEN-003 §VII "Step-Up Authentication" lists "Registering or removing passkey credentials".
- Target: one role-parameterised implementation in `passkey_service` with thin blueprint wrappers. (DOM-IDEN-003 L76: one unified passkey store for both roles.)

### IT-4 [S] Destruction gate ×2 (~25 lines)
- `admin.py:1212-1241` `_validate_destruction_gate` (JSON) vs inline `admin.py:8917-8940` (flash) — same thresholds.
- Target: factor the predicate to return an error string; both callers render it.

Dropped: TOTP seed verify (2 call sites of one library call); student passphrase verify for recovery (route pre-check + FEAT — FEAT is authority); username availability (different contexts); staleness predicate (intentional SQL+Python pair); nonce digests (2-line helpers); active-attempt predicate (short); dead imports noted by flowchart remain valid.

---

## F4 ledger

### LG-1 [D] Command reservation + replay — 5 copies; the transfer copy lacks the conflict path
- `ledger_transfer_service.py:46-61` (transfer pair), `ledger_command_service.py:147-159`, `:171-183` (post-IntegrityError), `:213-244` (`replay_reserved_charge`), `:258-279` (`replay_reserved_reversal`).
- Divergence: only `create_reserved_effects` creates the reservation in `begin_nested()` and, on uniqueness conflict, re-reads and compares; the transfer copy does a plain `add/flush` and has no key-length validation. It is safe today only because `transfer_feat.py:48-53` happens to take the seat lock first.
- Doc: SPEC-LED-002 §VI.2–6.3 — a uniqueness conflict MUST be resolved by reservation lookup + fingerprint comparison, never surface as a generic duplicate.
- Effect-key tuple re-declared at `ledger_command_service.py:56-66`, `:236-241`, `:265-268` (the latter two hard-code v5 keys).
- Target: `create_transfer_pair` calls `create_reserved_effects`; replays share one `_effect_keys(version)`.

### LG-2 [D, low] Balance sums — 4 implementations; one dead copy breaks INV-LED-015
- `ledger_balance_query_service.py:57-75` (separate posted + pending statements), `:78-118` (single-statement expression, the #1364 fix), `:138-177` (batch), `ledger_settlement_service.py:100-110` (`_posted_history_cents`, cursor-bounded, correct for its purpose).
- `get_pending_balance_delta` (`:70-75`) has **no callers**; used with `get_posted_balance` it is the two-statement read INV-LED-015 (DOM-LED-001 L75) forbids for available balance.
- Target: delete `get_pending_balance_delta`; make `_get_posted_balance_fallback` reuse the expression's `posted_sum`.

### LG-3 [S] Seat → ClassEconomy lock ×5+
- `transfer_feat.py:48-53`, `ledger_posting_service.py:17-18` (every effect), `ledger_settlement_service.py:125-129`, `ledger_recovery_service.py:288-298`, `:300-313`; `lock_recovery_scope` runs 3× on positive-credit reversal (`ledger_proof_inputs.py:30`, `ledger_correction_service.py:183`, `:209`). Order is consistent (seat → class, INV-LED-015).
- Target: `lock_recovery_scope` (existing) everywhere; P: drop the redundant re-locks.

### LG-4 [S] Historical share pricing ×2 (~22 lines)
- `ledger_historical_reconstruction.py:140-170` `_share_cents` vs inline `:184-210` in `allocate_reconstructed_shares` (inline adds `cents <= 0 → deny`; `_share_cents` callers filter `> 0`, so equivalent).
- Target: `allocate_reconstructed_shares` calls `_share_cents`.

Dropped: funding-transfer vs transfer leg construction (2 × ~10 lines, different serializers on purpose); seat-in-class scope checks (3-line idiom).

---

## F5 obligations

### OB-1 [D] Rent terms by `policy_uuid` opened directly — 9 sites, 2 scoping variants
- Class-scoped: `rent_payment_feat.py:350-351`, `reconcile_rent_feat.py:324-325`.
- Unscoped (`policy_uuid` only): `obligations_service.py:225`, `:236`; `reconcile_rent_feat.py:299`; `student.py:581`, `:605`; `admin.py:1768`, `:1787`, `:5156`.
- `policy_uuid` is globally unique (`models.py:1717`), so no leak today, but it breaks the class_id-scoping rule and the scoped/unscoped split is accidental.
- Doc: DOM-POL-001A §V.E "Policies read": "Obligations does not open `rent_settings` or `insurance_policies`". Every OBL copy is off-doc; `policy_reference_service.get_bill_preview_days(policy_uuid, class_id=…)` shows the lawful shape.
- Target: add a scoped rent-terms read beside `get_insurance_recurring_terms` in `policy_reference_service`; delete the inline queries. (Also listed by the policies flowchart — one fix.)

### OB-2 [D] Latest-cycle query ×3 variants
- `obligations_service.py:577-584` `get_latest_bill_cycle(internal_ref)` — **no class_id**; 9 callers.
- `:772-777` inline, class-scoped; `:812-822` terminal-only, class-scoped.
- Also DOM-OBL-001 §158: "The highest cycle number … MUST NOT be used as a proxy for the current cycle" — `admin.py:5149` and `admin.py:1785` use the latest cycle as "enforced"/current.
- Target: `get_latest_bill_cycle(class_id, internal_ref)`; replace the `:772` inline copy with it.

### OB-3 [D, low] Payment orchestration rent vs insurance
- Rent `rent_payment_feat.py:289-316, 407-432`; insurance `insurance_premium_payment_feat.py:135-148, 83-100`.
- Divergence: insurance takes `lock_recovery_scope` twice (`:142`, then `:84` inside `settle_insurance_premium`); replay uses hard-coded `"FEAT-OBL-003"` while rent uses `get_active_feat_name()` — the insurance replay would miss a reservation written under any other active FEAT.
- Target: one `settle_obligation_payment(...)` (generalise `settle_insurance_premium`), feat code from `get_active_feat_name()`.

### OB-4 [S] `later_than` / `current_time` resolver wrappers ×5 / ×4
- `obligations_service.py:686` `_is_later`; `reconcile_rent_feat.py:237`; `schedule_next_bill_cycle_feat.py:114`; `rent_payment_feat.py:138-152`; inline `withdraw_obligation_feat.py:75-82`. `current_time`: `obligations_service.py:532` and `:677` (same file), `schedule_next_bill_cycle_feat.py:162`, `withdraw_obligation_feat.py:69`.
- Boundary-equality semantics differ (`rent_payment` treats boundary==now as begun; `withdraw` treats it as not begun) — both match DOM-OBL-001 (§158 current period vs §160 "at or after the termination instant"), so keep the call shapes but share the wrapper.
- Target: keep `obligations_service._is_later` / `_reference_now`, delete `_current_reference` and the FEAT-local copies.

### OB-5 [S] Waiver-exists check ×3
- `admin.py:5659-5669` (route, domain query in route), `satisfy_obligation_feat.py:110-123`, `obligations_service.py:644` `check_idempotency_satisfaction`.
- Target: route calls `check_idempotency_satisfaction`.

Dropped: assessments-of-a-cycle (short filter_by); rent lineage string (2-line f-strings). Cross-feature pointer: the "withdraw untouched future assessments" loop is copied from `terminate_bill_cycle_feat.py:108-129` into CLASS at `feat_class_004_feature_enablement.py:151-187`.

---

## F6 policies

### PO-1 [S] Supersede (retire predecessor + insert successor) ×4, 3 orderings
- Rent `admin_settings_service.py:49-81` (insert, then retire, single flush — relies on UoW update-before-insert ordering); hall pass `feats/attendance.py:98-111` (retire, flush, insert); store `store_service.py:304-322` (retire via `set_availability`, sets `retired_at`); insurance `feat_class_003…:466-480` (retire, guard, insert).
- Only store stamps `retired_at`. Doc: DOM-POL-001 §VI / §VI.1 (availability is a projection; one IN_USE per lineage).
- Target: one `supersede(model, current, successor)` in POL that always retires-then-inserts under the partial unique index.

### PO-2 [S] Availability state machine ×2
- `store_service.py:65-67, 325-331` and `insurance_definition_service.py:46-49, 180-211` — identical constants, neither guards transitions (`RETIRED → IN_USE` allowed). DOM-POL-001 §VI.1 L148-149: RETIRED is permanent.
- Target: one validator shared by both; add the RETIRED-is-terminal guard.

Dropped: insurance type taxonomy (two short constants); store form `get_rent_settings` double-call (P, one expression); hall-pass payload validation route+FEAT (FEAT is authority, route pre-check acceptable); `get_rent_settings_for_context` vs `_resolve_rent_settings_for_class_id` (deliberately different questions, commented). Hall-pass reader divergence is reported under PROD-3; rent-terms lookup under OB-1.

---

## F7 productivity-payroll

### PR-1 [D] Attendance interval pairing — superseded rule still live
- Canonical: `services/attendance_service.py:252-312` `list_attendance_interval_evidence` (repeated `active` continues the session; sessions bounded at class-local day end).
- `services/attendance_service.py:111-140` `_pair_active_intervals` — a second `active` **restarts** the session; no day-end bound (an unclosed session from yesterday counts from today's start to now). Live in `calculate_worked_attendance_seconds_for_date` (`:504-529`) → `insurance_claim_feat.py:917, 1002, 1460, 1478` (PRODUCTIVITY claims), and `…_today` (`:532-559`) → student "Time Today" (`api.py:1742, 1752, 1806`, `attendance_service.py:634`).
- `app/attendance.py:51-98` `_calculate_active_seconds_for_range` — same superseded rule; its wrappers `calculate_period_attendance` / `…_utc_range` (`:101-148`) have **no app callers**.
- `services/payroll/corrections.py:128` `_replayed_paid_seconds` is the old rule **on purpose** (legacy replay) and its sibling `_worked_seconds_in_window` (`:150-165`) documents the current rule — keep it.
- Doc: DOM-PROD-001 §116 ("The domain pairs its ordered timeline; a caller cannot choose arbitrary endpoints"), SPEC-PROD-001 (incorporated at §69).
- Target: `…_for_date` / `…_today` clip `list_attendance_intervals(...)` to the day window (exactly as `_worked_seconds_in_window` does); delete `_pair_active_intervals`, `_calculate_active_seconds_for_range`, `calculate_period_attendance*`. `_for_date`/`_today` bodies are themselves duplicates (`:504-529` vs `:532-559`) — `_today` should call `_for_date`.

### PR-2 [D] Hall-pass leave/return/checkout/checkin decision ×4, only one pass-scoped
- Pass-scoped (fixed): student checkin `api.py:1083-1090` via `resolve_hall_pass_lifecycle_status`, with a comment that the seat-latest read "made checkin silently no-op and leave the pass stuck".
- Still seat-latest-event: teacher leave `api.py:891-899`, teacher return `api.py:913-921` (the same no-op read the checkin comment describes), student checkout `api.py:1000-1013`. Teacher paths also use `secrets.token_hex` in the idempotency key, so replays are never deduplicated.
- The seat-latest query itself is inlined ≥8× (`api.py:767, 887, 912, 1001, 1737, 1792`; `admin.py:8259`; `attendance_service.py:~628`).
- Doc: no § states the hall-pass lifecycle read explicitly; the pass-scoped resolver is the domain's own correction of this bug class (DOM-PROD-001 §116 pairing is domain-owned).
- Target: `resolve_hall_pass_lifecycle_status` for all four decisions; one `latest_attendance_event(seat_id, class_id)` in `attendance_service` for the remaining displays.

### PR-3 [D] Hall-pass settings in force — 2 readers in prod.py, different rule from POL
- `feats/prod.py:86-94` and `:205-213` — identical, back-to-back in one call; select `effective_date ≤ t`, **ignoring `availability_state`**.
- POL readers `feats/attendance.py:9-25` and `class_configuration_query_service.py:388-415` (identical to each other) select newest `IN_USE`.
- Doc: DOM-POL-001 §VI (L88 "availability state determines whether the definition may be used for new work"); only payroll is effective-dated (§VI.2 L153). The IN_USE readers match; prod.py can enforce a HIDDEN/RETIRED row.
- Target: prod.py reads `get_hall_pass_settings` once and passes it to `_enforce_hall_pass_settings`; delete `feats/attendance.py:_current_hall_pass_settings` in favour of the query-service reader.

### PR-4 [D] Teacher history endpoints: hall-pass history shows unclaimed seats
- `api.py:1196-1316` (hall-pass history) vs `api.py:1522-1669` (attendance history) — same pagination/date-filter scaffold (~40 lines duplicated).
- Attendance history joins `Seat` and filters `role='student'`, `claimed_at IS NOT NULL`; hall-pass history does not, and resolves names/class with 2 queries per row.
- Doc: DOM-IDEN-002 §VIII.2 (L234) — an unclaimed seat SHALL NOT appear outside roster management.
- Target: shared date-window/pagination helper; add the claimed-seat filter to hall-pass history.

### PR-5 [S] Historical settlement composition ×2 (~30 lines)
- `feats/attendance_interval_invalidation_feat.py:50-83` `_compose_historical_settlement` vs `feats/historical_attendance_proof_feat.py:64-93` (differ in `as_of_utc` and exception type).
- The "modern business row" predicate appears 3×; `attendance_interval_invalidation_feat.py:408` uses a narrower form (`lineage_event_id` or `allocation_version==1`, omitting `correction_intent_locator`/`command_receipt`) to decide `_lock_original`.
- Target: parameterise `_compose_historical_settlement(as_of_utc=…)`; one `_is_modern_business_row`.

### PR-6 [S] Synthetic teacher `CanonicalContext` ×3
- `services/payroll/settlement.py:80-93` `_build_teacher_context` (checks `teacher_user_id`), `scheduled_tasks.py:75-81`, `:317-322` (no check).
- Target: scheduled tasks call `_build_teacher_context`. Cross-feature pointer: insurance has its own `_ctx` (`insurance_coverage_service.py:63`, `insurance_coverage_renewal_feat.py:120`).

### PR-7 [P] Per-seat payroll recomputes intervals 3×
- `services/payroll/settlement.py:196-203` (`close_due`, `calculate_seat_payroll_intervals`, `calculate_payable_attendance_seconds`) then `feats/prod.py:354-357` (`close_due` again, `price_payable_attendance` → `calculate_seat_payroll_intervals` again, `pricing.py:147`).
- Target: compute once, pass the priced result into the FEAT.

Dropped: `_elapsed_seconds` wrapper ×2 (short); idempotency-key length check in route+FEAT (FEAT authoritative); seat-name lookup in tap routes (3 × 4 lines).

---

## F8 store-entitlements

### SE-1 [D] GRANTED-per-unit loops ×4; direct-grant payload stores quantity
- `store_purchase_feat.py:476-517`, `direct_entitlement_grant_feat.py:316-345`, `entitlement_service.py:177-196`, `:253-277`.
- Divergence: direct grant writes `payload={"unit_index", "quantity_total", …}`; store purchase deliberately does not (comment cites the rule). `entitlement_id` is `uuid4` in the FEATs, `hpent_<token>` in `entitlement_service` (`:41`).
- Doc: DOM-STORE-001 L203 — "`entitlement_events` SHALL NOT contain quantity". Store purchase matches; direct grant is off-doc.
- Target: one `entitlement_service._append_grants(...)` used by all four; drop `unit_index`/`quantity_total`.
- (Per coordinator correction: no claim is made here that any hall-pass grant path is broken.)

### SE-2 [D] Terminal-event lookup — 2 service variants + inline copies
- `entitlement_read_service.py:269-297` `get_entitlement_lineage_terminal_event` — class-scoped, unordered `.first()`.
- `entitlement_read_service.py:722-732` `entitlement_terminal_event` — **no class_id**, ordered; used by `api.py:437`, `entitlement_read_service.py:767`.
- Inline: `insurance_coverage_service.py:176`, `insurance_claim_service.py:111`, `collective_goal_expiry_feat.py:80-91`, `insurance_coverage_renewal_feat.py:462`.
- Target: keep the scoped one (add the ordering); delete `entitlement_terminal_event`.

### SE-3 [D] Insurance GRANTED lookup inside one FEAT disagrees
- `insurance_claim_feat.py:57-74` `_resolve_claim_grant` filters `entitlement_type="INSURANCE"`; `insurance_claim_feat.py:1118-1128` (claim submit step 2) does not. Other copies: `insurance_claim_service.py:92-101`, `insurance_coverage_service.py:162`, `entitlement_service.py:311`, `purchase_insurance_feat.py:142`, `student.py:2087`.
- Target: step 2 calls `_resolve_claim_grant`.

### SE-4 [S] Active-insurance-grant derivation ×4
- `entitlement_read_service.py:415-457` `has_active_insurance_coverage` ≡ `:460-499` `get_active_insurance_grant` (identical bodies); `student.py:2108-2121`; `cancel_insurance_feat.py` resolves the same via `get_active_insurance_grant` (`:117`).
- Target: `has_active_insurance_coverage = get_active_insurance_grant(...) is not None`; route calls `get_active_insurance_grant`.

### SE-5 [D, low] Terminal write commands ×4 (~30 lines each)
- `entitlement_service.py:456` consume, `:504` expire, `:565` revoke, `:418` consume_hall_pass. Expire is idempotent on same-type replay; consume/revoke fail closed on replay.
- Target: one `_record_terminal(event_type, idempotent_same_type=…)`.

### SE-6 [S] Seat → policy → scope-mismatch validation ×2 (~90 lines)
- `store_purchase_feat.py:150-246` ≈ `direct_entitlement_grant_feat.py:156-257`.
- Target: shared validator in `store_policy_resolver`.

Cross-feature pointers: REVOKED rows are hand-built outside `revoke_entitlement` at `admin.py:10665-10681` (support) and `transaction_void_feat.py:224-242` (ledger), both skipping the terminal pre-check. `_reference_now` duplicated `insurance_coverage_service.py:200` / `insurance_coverage_renewal_feat.py:124`.

---

## F9 support

### SU-1 [D] Issue creation ×2 — teacher path writes no status history
- `utils/issue_helpers.py:125-214` `create_issue` (student) records `None → OPEN` via `record_status_change`, sets `submitted_at/created_at/updated_at`, `issue_type` from category.
- `services/issue_service.py:7-51` `create_support_ticket` (teacher, `admin.py:9216`) records **no** history row, hard-codes `issue_type='general'`, builds its own context snapshot (`:33-36` vs `issue_helpers.py:67-72`).
- Doc: DOM-SUP-001 L190-191 / L308 — every status transition produces a history row atomically. The student path matches.
- Target: `create_support_ticket` delegates the insert + history to a shared core.

### SU-2 [D] Class-scoped issue lookup ×4, three fail open
- `admin.py:10504-10509`, `:10574-10579`, `:10836-10842`: if `class_row` is falsy the query is **unscoped by class**; no ownership check.
- `admin.py:10759-10763` (escalate): `verify_teacher_owns_class` and 403 — fail closed.
- Reachability is low (`admin_required` forces class context on these endpoints, `auth.py:152-220`), but INV multi-tenancy requires the escalate form.
- Target: one `_issue_in_active_class(issue_ref, lock=False)` using the escalate logic.

### SU-3 [D] Legacy status aliases hand-copied in 7 gates
- `admin.py:10417-10441`, `:10583-10590`, `:10768-10773`, `:10843-10846`; `system_admin.py:789-803`, `:1222`, `:1240`. Canonical map: `models.py:2365-2372`.
- Divergence: `system_admin.py:802` buckets `'developer_review'` as "in review", while the model map and `system_admin.py:1222/1240` treat it as `ESCALATED_TO_DEV`.
- Doc: DOM-SUP-001 L122 lists only `OPEN|TEACHER_REVIEW|ESCALATED_TO_DEV|DEV_RESOLVED|TEACHER_FINAL_REVIEW|CLOSED` — legacy strings are not lawful values.
- Target: confirm no legacy rows remain, then delete every alias list; until then derive from `LEGACY_TO_CANONICAL_STATUS`.

### SU-4 [D, low] Issue ref resolver ×2
- `admin.py:10388-10391` accepts raw numeric ids (`isdigit`); `system_admin.py:663` accepts opaque refs only.
- Target: `resolve_opaque_ref` only (internal ids stay out of URLs).

### SU-5 [D, low] Status change + history ×2
- `issue_helpers.update_issue_status` (`:277-292`, sets `updated_at`) vs manual `issue.status = …` + `record_status_change` at `system_admin.py:1273/1329` (no `updated_at`).
- Target: call `update_issue_status`.

### SU-6 [S] Repeated route boilerplate
- `help_support` error re-render (query + 15-arg render) `admin.py:9098-9123`, `9126-9151`, `9187-9210`; student submit routes `student.py:3218`, `3273`, `3338`.
- Target: one render helper / one submit helper per blueprint.

Dropped: `_issue_to_view` admin vs sysadmin (deliberately different disclosure surfaces, DOM-SUP-001 §VI/§VII); teacher public-id resolution (call sites of one helper). Dead: `issue_categories.init_default_categories`.

---

## F10 operations-audit

### OA-1 [D] Audit chain walk + HMAC recompute ×3, different strictness
- `utils/audit_verifier.py:117-236` `verify_chain`; `:569-640` `_creation_evidence_batch`; `:725-850` `_diagnose_historical_audit_coverages`.
- Only the third also checks `item.class_id == class_id` and `item.hmac_signature == item.event_hash`.
- Doc: DOM-OPS-002 L86 (`hmac_signature` is a copy of `event_hash`) and L363 (proof = digest match + continuous chain walk). The strictest copy is right; the canonical `verify_chain` is the weakest.
- Target: one `_walk_chain(scope, …)` generator applying all checks; the three callers consume it.

### OA-2 [S] Ledger protected-field list ×3
- `ledger_posting_service.py:8-13`, `audit_verifier.py:42-46` (`PROTECTED_FIELDS_BY_TABLE["ledger_transaction"]`), `:50-61` (`LEDGER_FIELDS_BY_VERSION`). Identical today; `PROTECTED_FIELDS_BY_TABLE` also keeps a stale `"transaction"` entry.
- Doc: DOM-OPS-002 INV-OPS-019 (L187-189) — exact parity between emitter and verifier, maintained by hand today.
- Target: emitter imports `LEDGER_FIELDS_BY_VERSION[3]`; derive the other two.

### OA-3 [S] `audit_service.verify_chain` / `verify_row_lineage` stub delegators
- `services/audit_service.py:386-436` with ImportError fallbacks duplicating `audit_verifier.py:117` / `:255`.
- Target: delete the stubs; import the verifier.

Dropped: `SELECT 1` probe ×2; two raw-engine error writers (different tables, different purposes); INVALID_CLASS_SCOPE block `admin.py:9853/9962` (2 × 11 lines, consistent); status_service collector pair (2 short copies); escalated filter (folded into SU-3).

---

## F11 interpretation

### IN-1 [P] Repeated reads per compute
- `interpret_obligations` twice (`obligation_observation.py:56`, `resilience_observation.py:110`); `get_inbound_ledger_rows` twice (`income_composition.py:45`, `resilience_observation.py:89`); enrolled-seat population ~6×; `get_posted_balances_as_of` checking ×4 / savings ×5; Q9 recomputes the Q1a-C2 and Q6 distributions (`resilience_observation.py:72-77, 118-141` vs `participation.py:36-57`, `resource_distribution.py:64-73`).
- Same helpers, same results — no divergence. Target: compute these once in `compute.py` and pass them down.

### IN-2 [D, low] Decimal → string helpers ×4
- `observation_builders.py:43` `canonical_decimal` (HALF_EVEN, normalises −0); `reference_configuration.py:36-47` `_money`/`_num` (no −0 normalisation); `presentation.py:177` `_money`, `:331` `_dollars` (display).
- Target: `reference_configuration._money` → `canonical_decimal(value, Decimal("0.01"))`.

Dropped: payroll-window → FEAT-PROD-004 scaffold (admin vs scheduler; cross-feature trigger, differs by key); latest-record query ×2 (short). The CWI copy is reported under CC-1.

---

## Counts

| Feature | Kept | Diverged |
|---|---|---|
| F1 class-configuration | 6 | 4 |
| F2 identity-student | 5 | 5 |
| F3 identity-teacher | 4 | 3 |
| F4 ledger | 4 | 2 |
| F5 obligations | 5 | 3 |
| F6 policies | 2 | 0 |
| F7 productivity-payroll | 7 | 4 |
| F8 store-entitlements | 6 | 4 |
| F9 support | 6 | 5 |
| F10 operations-audit | 3 | 1 |
| F11 interpretation | 2 | 1 |
| **Total** | **50** | **32** |
