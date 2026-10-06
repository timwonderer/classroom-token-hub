# P0B production-state reconnaissance and baseline, 2026-10-06

Read-only reconnaissance for the Architecture Convergence units U1–U14 (P0B, issue #1495). It records what
production holds, who writes it, and what each unit's change would touch. It changes nothing. It is evidence
under `SOP-DB-004` §IX.1.7 and `INV-ARC-017` §V.5/§VII, not a normative document, and it does not classify any
change: each unit records its own `SOP-DB-004` §VI values in its issue. Where this record names a candidate
value, the unit's issue decides.

Two kinds of finding are kept apart throughout:

- **Observed (production).** Results of the queries in
  [`evidence/2026-10-06_p0b-recon/recon_readonly.sql`](evidence/2026-10-06_p0b-recon/recon_readonly.sql), cited by
  query id (Q0–Q14).
- **Repository.** Code at `28193df5a` (`main`), cited by `file:line`. Production runs `381a12d49`
  ([release record](DEPLOY_2026-10-04_381a12d49.md)); the repository finding applies to production only where the
  code is unchanged between the two. No migration was added after `381a12d49`: both are at Alembic head
  `f9a3c7d1e620`.

## Method and limits

- **Surface.** The operator's TablePlus "Production" connection (SSH to the production host, database
  `classroom_economy`), through its read-only query tool, which rejects anything but reads. Fourteen SELECT
  statements, 2026-10-06 06:08:34Z to 06:11:30Z, plus Q13 after them and Q14 after the owner's ruling on §5.1. No write, no DDL, no lock, no session
  setting change. The application was running; each statement is its own snapshot, so totals across statements
  can differ by writes made between them. None was observed: Q1, Q2 and Q12 agree.
- **PII.** No query selects a name, free text (descriptions, notes, explanations, titles, messages, hall-pass
  destinations), a credential, hash, token or join code. Classes are named by the first eight characters of
  `class_id`. Free-text columns were not read even in aggregate.
- **Repository inventory.** Four read-only searches across the domain clusters, with the load-bearing claims
  re-checked by hand at `28193df5a` (`ledger_provenance_query_service.py:58-74`, `system_admin.py:1297-1308`,
  `admin_settings_service.py:60-82`, `audit_verifier.py:295-303`, `models.py:629-634`, `feats/prod.py:139`).
- **Not covered.** External state (`SOP-DB-004` §V.2: Cloudflare Access, the student-setup memory store,
  environment) was not inspected. No query read `interpretation_cycle_record` JSON, `pending_actions.payload`
  beyond `kind`/`outcome`, or `summary_json`/`receipt_json`. No test was run: nothing here changes runtime
  behavior.

## 1. Authority

| Concern | Governing document |
|---|---|
| What P0B must produce; production-state parts; H-values; versioned vs heuristic interpretation; baseline | `SOP-DB-004` v1.2 §V.2, §VI.2, §VII.3, §VII.7, §IX.1.7 |
| No PII in evidence | `INV-ARC-005`, `INV-ARC-018`; `SOP-DB-004` §IX |
| Protected rows and signature versions | `INV-ARC-016`; `DOM-OPS-002` §5.4 (ledger v1/v2/v3, `payroll_event`, `attendance_interval_invalidation`) |
| Ledger immutability and `feat_code` | `DOM-LED-001` §VII, §VII.2 |
| Canonical table set | `DOM-CORE-002` v1.16 §V |
| Evidence reporting | `INV-ARC-017` v1.3 §V.5, §V.8, §VII |
| Production is not changed without separate go-ahead | `SOP-DB-004` §IX.3.1; `SOP-DEP-002` §VI |

**Authority conflicts found** (flagged, not resolved here):

1. `DOM-CORE-002` §V names tables that do not exist in production or at head (Q0): `obligation_satisfaction`
   (§V.4); `incident_events`, `incident_summary`, `alert_events`, `invariant_run_events`, `job_events`,
   `health_check_events` (§V.7); `payroll_rewards` and `payroll_fines` (§V.2, §V.11, dropped by
   `7c3d4e5f6a7b`). `user_invite_tokens` and `user_recovery_tokens` are already marked extinct there. Either the
   document or the schema is behind. It bears on U8 (where integrity status persists) and U3 (the payroll policy
   family).
2. `DOM-OPS-002` §6.2A says integrity conditions "MUST be surfaced in `IntegrityStatus`"; the `integrity_status`
   table was dropped (`7c3d4e5f6a7b:220`). This is the open U8/U13 decision already named in the proposal.
3. FEAT ids whose document and runtime meaning differ (repository; U6): `FEAT-LED-001` (document "post ledger
   transaction", runtime savings interest), `FEAT-OBL-001` (document "assess obligation", runtime rent payment),
   `FEAT-OPS-001` (document "audit-protected emission", runtime logins, passkeys, issue updates and bug reward).
   `FEAT-LED-003` (settlement sweep) has no document. All four appear on production rows (Q4, Q5).

## 2. Production identity and baseline

**Q0.** Revision `f9a3c7d1e620`, PostgreSQL 14.24, 45 base tables, the same name set as a database migrated to
head. No `error_events`, `integrity_status`, `policy_versions`, `policy_transitions`, `user_reports` or badge
table exists.

**Q1, row counts (06:08:47Z).**

| Table | Rows | Table | Rows | Table | Rows |
|---|---:|---|---:|---|---:|
| actor_request_trace | 4478 | hall_pass_settings | 5 | operational_events | 0 |
| announcements | 8 | identity_profiles | 261 | passkey_credentials | 3 |
| assessment_events | 164 | insurance_claim_productivity_dates | 0 | payroll_cycle_completion | 26 |
| attendance_interval_invalidation | 4 | insurance_claims | 0 | payroll_event | 625 |
| attendance_sessions | 1260 | insurance_policies | 0 | payroll_settings | 9 |
| audit_events | 997 | interpretation_cycle_record | 26 | pending_actions | 3 |
| bill_cycles | 5 | issue_categories | 15 | recovery_class_challenges | 0 |
| chain_heads | 7 | issue_resolution_actions | 1 | recovery_requests | 0 |
| class_features | 121 | issue_status_history | 18 | rent_settings | 8 |
| classes | 10 | issues | 7 | seats | 261 |
| economic_engine | 32 | ledger_balance_snapshot | 276 | store_item_visibility | 0 |
| entitlement_events | 619 | ledger_command_reservation | 782 | store_products | 15 |
| feature_settings | 3 | ledger_transaction | 974 | student_recovery_codes | 0 |
| hall_pass_logs | 16 | obligation_command_reservation | 5 | teacher_signup_attempts | 0 |
| | | | | ticket_correlation_pack | 7 |
| | | | | users | 207 |

**Q2, money baseline (06:08:53Z).** Ledger sum equals posted snapshot sum in every class and account. No row
has a NULL `amount_cents`. Seven of ten classes have ledger activity.

| Class | Account | Ledger rows | Ledger cents | Snapshots | Snapshot cents | Max posting seq |
|---|---|---:|---:|---:|---:|---:|
| `1da9085a` | checking | 134 | 238877 | 28 | 238877 | 193 |
| `1da9085a` | savings | 60 | 213502 | 17 | 213502 | 194 |
| `41e5092b` | checking | 132 | 400230 | 30 | 400230 | 185 |
| `41e5092b` | savings | 54 | 282898 | 12 | 282898 | 186 |
| `6eda1262` | checking | 20 | 176250 | 17 | 176250 | 23 |
| `6eda1262` | savings | 6 | 15021 | 3 | 15021 | 26 |
| `bfe8cfc4` | checking | 126 | 335985 | 29 | 335985 | 170 |
| `bfe8cfc4` | savings | 45 | 203257 | 16 | 203257 | 171 |
| `c393fd39` | checking | 123 | 434792 | 31 | 434792 | 163 |
| `c393fd39` | savings | 41 | 90639 | 12 | 90639 | 164 |
| `d478db0f` | checking | 93 | 676035 | 28 | 676035 | 112 |
| `d478db0f` | savings | 20 | 82791 | 8 | 82791 | 113 |
| `da5ef035` | checking | 81 | 315277 | 30 | 315277 | 119 |
| `da5ef035` | savings | 39 | 189456 | 15 | 189456 | 120 |

**Q12, per-class row counts (06:11:30Z).** The repeatable baseline for class-scoped tables.

| Table | Per class | Total |
|---|---|---:|
| assessment_events | 1da9085a=32 41e5092b=34 bfe8cfc4=33 c393fd39=32 da5ef035=33 | 164 |
| attendance_interval_invalidation | 41e5092b=1 d478db0f=2 da5ef035=1 | 4 |
| attendance_sessions | 1da9085a=208 41e5092b=194 6eda1262=64 8af5d987=112 bfe8cfc4=190 c393fd39=156 d478db0f=162 da5ef035=174 | 1260 |
| audit_events | 1da9085a=194 41e5092b=206 6eda1262=26 bfe8cfc4=171 c393fd39=164 d478db0f=115 da5ef035=121 | 997 |
| bill_cycles | 1da9085a=1 41e5092b=1 bfe8cfc4=1 c393fd39=1 da5ef035=1 | 5 |
| class_features | 1da9085a=14 34294790=10 41e5092b=9 6eda1262=22 72041438=2 8af5d987=2 bfe8cfc4=12 c393fd39=10 d478db0f=14 da5ef035=26 | 121 |
| economic_engine | 1da9085a=5 34294790=3 41e5092b=3 6eda1262=5 72041438=1 8af5d987=1 bfe8cfc4=3 c393fd39=3 d478db0f=3 da5ef035=5 | 32 |
| entitlement_events | 1da9085a=87 41e5092b=95 6eda1262=58 bfe8cfc4=98 c393fd39=100 d478db0f=85 da5ef035=96 | 619 |
| hall_pass_logs | 41e5092b=2 6eda1262=1 bfe8cfc4=2 c393fd39=6 d478db0f=2 da5ef035=3 | 16 |
| hall_pass_settings | 1da9085a=4 c393fd39=1 | 5 |
| interpretation_cycle_record | 1da9085a=5 41e5092b=4 6eda1262=1 bfe8cfc4=4 c393fd39=5 d478db0f=4 da5ef035=3 | 26 |
| ledger_balance_snapshot | 1da9085a=45 41e5092b=42 6eda1262=20 bfe8cfc4=45 c393fd39=43 d478db0f=36 da5ef035=45 | 276 |
| ledger_command_reservation | 1da9085a=149 41e5092b=143 6eda1262=23 bfe8cfc4=138 c393fd39=133 d478db0f=100 da5ef035=96 | 782 |
| ledger_transaction | 1da9085a=194 41e5092b=186 6eda1262=26 bfe8cfc4=171 c393fd39=164 d478db0f=113 da5ef035=120 | 974 |
| payroll_cycle_completion | 1da9085a=5 41e5092b=4 6eda1262=1 bfe8cfc4=4 c393fd39=5 d478db0f=4 da5ef035=3 | 26 |
| payroll_event | 1da9085a=123 41e5092b=103 6eda1262=17 bfe8cfc4=116 c393fd39=133 d478db0f=78 da5ef035=55 | 625 |
| payroll_settings | one each in 1da9085a 34294790 41e5092b 6eda1262 8af5d987 bfe8cfc4 c393fd39 d478db0f da5ef035 | 9 |
| pending_actions | c393fd39=1 d478db0f=2 | 3 |
| rent_settings | 1da9085a=4 41e5092b=1 bfe8cfc4=1 c393fd39=1 da5ef035=1 | 8 |
| seats | 1da9085a=32 34294790=1 41e5092b=37 6eda1262=29 72041438=1 8af5d987=29 bfe8cfc4=35 c393fd39=34 d478db0f=30 da5ef035=33 | 261 |
| store_products | 1da9085a=5 c393fd39=5 d478db0f=5 | 15 |

## 3. Observed persisted semantics

### 3.1 Ledger (Q3, Q5, Q9)

Two cohorts, split exactly by signature version:

| Cohort | Rows | Dates | Stored `feat_code` | Creation audit `feat_id` |
|---|---:|---|---|---|
| `lineage_version = 1` | 854 | 2026-09-28 → 2026-10-03 | `FEAT-LED-003` on **every** row | LED-000 322 (161 Deposit + 161 Withdrawal), PROD-004 402 (payroll), PROD-003 85 (84 manual_payment + 1 payroll), LED-001 36 (Interest), OBL-001 6 (rent_payment), STOR-001 3 (purchase) |
| `lineage_version = 3` | 120 | 2026-10-05 | equals audit `feat_id` on every row | LED-000 62, LED-001 37, PROD-004 19, OBL-001 2 |

- Every one of the 974 rows has exactly one creation audit event and `lineage_event_id` points to it. Every row
  has a command reservation. The 854 v1 rows all have NULL `compensation_amount_cents`, which `DOM-OPS-002` §5.4
  permits on historical rows only.
- **The v1 `feat_code` is a settlement restamp, already recorded.**
  [`HISTORICAL_ATTENDANCE_PHASE4_PROOF_REVIEW_20261003`](../../TRACKING/HISTORICAL_ATTENDANCE_PHASE4_PROOF_REVIEW_20261003.md)
  observed the same 854 FEAT differences and traced them to `_enforce_transaction_integrity`, which until
  `81ea0fff5` (first released in `2bdfac65e`, 2026-10-04) stamped `feat_code` on UPDATE as well as INSERT, so the
  settlement sweep (`FEAT-LED-003`) overwrote it. This record adds the per-type split above and the post-fix
  evidence: no v3 row differs. The migration that made ledger rows immutable left `feat_code` free on purpose
  (`f1a9c3e60b72`; CHANGELOG, 2026-09-10).
- Types present: `Deposit`, `Withdrawal`, `Interest`, `manual_payment`, `payroll`, `purchase`, `rent_payment`.
  **Absent:** `REVERSAL`, `insurance_reimbursement`, `insurance_premium`, `bug_reward`, `void_item_removed`,
  `overdraft_fee`, `payroll_correction`, legacy `refund`/`issue_*`/`VOID`. No row is zero-amount, none sets
  `original_transaction_id`, `reversal_transaction_id`, `policy_id`, `compensation_subtype` or `join_code`.
- Key shapes (Q9): v1 transfer legs have NULL keys (161 + 161; their reservations carry the key, by original
  writer design per the Phase 4 review); purchases and v3 transfers embed a random uuid4; payroll, manual
  payments and interest embed a uuid4; rent keys are deterministic. 36 v1 `Interest` keys are the legacy shape
  and 37 v3 are weekly. Reservations use fingerprint versions 3 (v1 cohort) and 5 (v3 cohort); none is unused.
- Snapshots: no `join_code`, no `reconciled_through_transaction_id`, no NULL cursor.

### 3.2 Other protected and PROD records (Q4, Q6, Q8)

- `payroll_event`: 606 of 625 rows have NULL lineage. These are all rows recorded before 2026-10-05
  (payroll 521, manual_credit 84, reversal 1). The 19 payroll rows of 2026-10-05 are linked (signature v1).
  Under `DOM-OPS-002` §5.4 and `INV-ARC-016` §VI, NULL linkage denotes UNVERIFIED, so this is expected. Of the
  84 manual credits, 79 are the `SYSTEM` correction top-ups of 2026-09-29 (keys
  `payroll-correction:…`), and 5 are teacher credits with random `token_hex` keys.
- `attendance_interval_invalidation`: 4 rows (`INVALID_ATTENDANCE`, 2026-10-04), all linked.
- Audit chain: 997 events, all `signer_key_id = v1`, every `hmac_signature = event_hash`, none without
  `class_id`; 7 `class:` chain heads and no `system` head; head counts and sequences match the events. Only
  three tables are audited: `ledger_transaction`, `payroll_event`, `attendance_interval_invalidation`.
- `payroll_cycle_completion`: 26 rows, all `manual-payroll:` keys. Scheduled payroll has never completed a cycle.
  `interpretation_cycle_record`: 26, one per completion.
- Attendance (Q8): 1260 sessions. Hall-pass legs carry `hall_pass_id` (14 leaves, 13 returns).

### 3.3 Store and entitlements (Q7, Q8, Q13)

| Event | Type | Acquisition | Source | Rows | Classes |
|---|---|---|---|---:|---:|
| GRANTED | HALL_PASS | GRANT | `grant_hall_passes` (`hpent_` ids) | 600 | 7 |
| CONSUMED | HALL_PASS | GRANT | `consume_hall_pass` | 16 | 6 |
| GRANTED | DELAYED_USE | PURCHASE | (none; `policy_uuid` in payload) | 3 | 2 |

- No `REVOKED` or `EXPIRED` event exists, no insurance entitlement, no outcome-bearing payload.
- **Hall-pass double record (U2, R2).** All 16 hall-pass logs carry a `hall_pass_id`, each matching exactly one
  `CONSUMED` event, one to one. No log lacks a `CONSUMED` event and no `hall_pass_id` repeats.
- **`"default"` hall-pass policy reference.** 14 of 16 `hall_pass_logs` store `policy_uuid = 'default'`, which
  resolves to no policy row. Q13: 10 are in five classes that have never had a hall-pass policy, and 4 are in
  `c393fd39` before its first policy (2026-09-28 22:42Z). The latest is 2026-10-05, so the writer is live. The 2
  resolving logs are in `c393fd39`, after its policy took effect. Writer: `feats/prod.py:139`. I found no
  earlier record of this.
- `pending_actions`: 3, all `FEAT-STOR-002`, `kind` NULL (redemption requests), about 3 days old, lineage not
  terminal, no legacy `outcome`.
- Insurance: 0 policies, 0 claims, 0 insurance entitlements, 0 insurance bill cycles.

### 3.4 Policies and class configuration (Q10, Q11a)

- Rent: five classes; exactly one `IN_USE` row each (`1da9085a` also has 3 `RETIRED`). Hall pass: two classes,
  one `IN_USE` each (`1da9085a` has 3 `RETIRED`). Payroll: one row each in nine classes. Store: 15 products in
  three classes, all `IN_USE`, one version per lineage. Nothing is effective in the future, nothing is
  `RETIRED` without `retired_at`, and nothing is resurrected.
- Economic engine: 32 versions in 10 classes, all `economy_policy_mode = default`, none future-dated.
  `feature_settings`: 3 rows, mode `default`, alignment status NULL, `economy_policy_updated_at` set,
  `economy_last_rebalanced_at` NULL. `class_features`: 121 rows, none with NULL `economic_version_id`.
- Obligations: 5 rent bill cycles (one per rent class), none terminal, each with a `schedule_next_bill_cycle`
  reservation, each resolving to a rent policy of the same class. Assessments: 156 `ASSESSMENT`/`RENT`, all
  resolving within their class (127 to the current policy, 29 to a retired version). 8 `PAYMENT`/`RENT` carry no
  `policy_uuid`, and each links a ledger row.

### 3.5 Identity, support, operations (Q11b)

- Users: 203 student, 3 teacher, 1 sysadmin; none provisioning. Seats: 230 claimed student seats (user and
  `claimed_at` set), 21 unclaimed (both NULL), 10 teacher seats. No seat has a user without `claimed_at`, or the
  reverse, among student seats. No class has more than one teacher seat. Profiles: 261, all bound.
- Issues: 7, all **canonical** statuses (3 `CLOSED`, 3 `DEV_RESOLVED`, 1 `OPEN`); history 18 rows, all canonical.
  Only 6 issues have an initial `→ OPEN` history row; one does not.
- `ticket_correlation_pack`: 7, version 1. `operational_events`: 0. `actor_request_trace`: 4478.
  Passkeys: 3. Recovery tables: empty.

## 4. Impact on each unit

Repository findings are at `28193df5a`. "Candidate" values are inputs to the unit's own `SOP-DB-004` §VI
classification, not classifications.

| Unit | Production rows touched | Repository writers and readers that matter | Historical-state candidate |
|---|---|---|---|
| **U1** ledger posting | 974 ledger rows; types listed in §3.1. No reimbursement, bug-reward, void-item or interest-v1-key row would be rewritten | Credits bypass the plan builder: `feats/prod.py:404-415`, `ledger_interest_service.py:378-389`, `insurance_claim_feat.py:1984-1999` (sets `original_transaction_id`). Bug reward `system_admin.py:1297-1308` posts with `idempotency_key=get_idempotency_key()`, outside a reservation. Zero-amount `void_item_removed` at `transaction_void_feat.py:244-257`. Hand-rolled transfer reservation `ledger_transfer_service.py:46-73`. Settlement cycle id from `uuid4` in `payroll/cycle_completion.py:87` | `H1` for ledger rows: none of the retired row shapes exists in production. The writer changes are prospective |
| **U2** entitlement termination | 619 entitlement events; 16 hall-pass `CONSUMED` + 16 matching logs | Sole `CONSUMED` writer for hall passes `entitlement_service.consume_hall_pass` via `feats/prod.py:232`. `REVOKED` writers: `revoke_entitlement` (deny only), `remove_hall_passes` (records the student as actor), inline in `transaction_void_feat.py:226-242` and `routes/admin.py:10671-10683`. Balance reader `entitlement_read_service.get_entitlement_balance` counts terminal events only | `H2`-shaped requirement for the 16 grants: the new balance must count each entitlement once (Store `CONSUMED` OR PROD log), or it subtracts all 16 twice. No `REVOKED`/`EXPIRED` row exists to reinterpret |
| **U3** policy surface | 8 rent, 5 hall, 9 payroll, 15 store, 0 insurance rows; 14 `"default"` hall-pass logs | Rent supersede inserts then retires, without a lock, and there is no one-`IN_USE` index (`admin_settings_service.py:60-82`; `models.py:1805`). Store and insurance availability allow `RETIRED → IN_USE` (`store_service.py:327-334`, `insurance_definition_service.py:180-211`). Collective-goal expiry writes availability directly (`collective_goal_expiry_feat.py:220`). Rent fallbacks to current (`rent_payment_feat.py:349-356`; `routes/admin.py:1767-1798`; `routes/student.py:580-605`). `"default"` writer `feats/prod.py:139` | Policy rows `H0`/`H1`: no duplicate `IN_USE`, no resurrected row, no orphan reference. `hall_pass_logs.policy_uuid = 'default'`: prospective writer forbidden by owner ruling (§5.2: gate on feature + settings row); 14 historical rows preserved, terms unavailable (owner ruling) |
| **U4** CWI | 32 engine versions, 3 feature_settings rows; 26 ITR records whose `reference_configuration` was computed under current-time CWI | `get_active_policy_mode(user_id, …)` (`utils/economy_policy.py:389`) reads a column nothing writes after its default; production holds only `default` | `H0` for engine and settings rows. Whether the 26 materialized ITR records keep their as-computed reference configuration is the unit's question; this record did not read their JSON |
| **U5** attendance / hall pass | 1260 sessions, 16 logs | Random `secrets.token_hex(12)` keys at `api.py:906/929/1022/1105/1774` and `admin.py:8338/8432`. The writer persists no key, so nothing stored depends on them | `H0`: no persisted idempotency column to reinterpret |
| **U6** FEAT identity | 854 v1 ledger rows storing `FEAT-LED-003`; 997 audit events with originating FEATs | `SYSTEM_ORIGINATED_FEAT_CODES` (`ledger_provenance_query_service.py:58-74`) contains `FEAT-LED-003` and `FEAT-LED-000`, so every v1 row, and every transfer, is read as system-originated. ITR `income_origin.py` sets classify by `feat_code` | `H2` per owner ruling (§5.1): origin from the linked `INSERT` event's `feat_id`, selected by `lineage_version = 1`; actor attribution unavailable from audit context |
| **U7** sessions | 207 users; no persisted session semantics change | Establishment sequences listed in the proposal; sysadmin and teacher passkey routes run under `FEAT-OPS-001` | `H0` |
| **U8** operations | 997 audit events (v1 signer, 3 tables), 0 operational events, no `error_events`/`integrity_status` | `app/__init__.py:165-189` and `tlcp.py:53` gate on the dropped `error_events`; dead in production. Verifier handles ledger signature v1 as DEGRADED (`audit_verifier.py:295`) before the version lookup at `:303` | `H0`. The `integrity_status` persistence decision is open (§1, item 2) |
| **U10** obligations | 5 bill cycles, 164 assessments, 5 obligation reservations | `bill_cycles` uniqueness is `(internal_ref, cycle_number)`, without `class_id` | `H1`: every reference resolves within its class; no terminal or insurance cycle exists |
| **U11** local deletions | 7 issues, 18 history rows, 261 seats | `LEGACY_TO_CANONICAL_STATUS` (`models.py:2365`) and literal legacy checks at `system_admin.py:466-467, 793-803` and `admin.py:10425-10443`. Claimability: claim verify uses `user_id IS NULL` (`identity_feat.py:196`), bind uses both columns (`:538-539`) | Precondition met **at observation time**: zero legacy status values in `issues` and `issue_status_history`. All 251 student seats agree under either claimability predicate. One issue lacks its `→ OPEN` history row |
| **U12** insurance | none (0 policies, claims, insurance entitlements, insurance cycles) | `purchase_insurance_feat.py:91`, `cancel_insurance_feat.py:86` | `H0`: no historical insurance state exists |
| **U13** documents | none | — | — |
| **U14** badges | no badge table, no `bug_reward` ledger row | — | `H0` |

U9 (presentation builders) persists nothing and is not listed.

## 5. Items that needed an owner ruling (§5.1 and §5.2 ruled 2026-10-06)

`SOP-DB-004` §VII.7: these rows carry no explicit version that fixes the meaning a reader needs, so the dependent
change stops until the owner rules in the governing document. Nothing here proposes or applies a rewrite.

### 5.1 Originating FEAT of the 854 signature-v1 ledger rows (U6, also U1 and ITR)

- **Rows.** `ledger_transaction` with `lineage_version = 1` (854, all classes with ledger activity).
- **Ambiguity.** The stored `feat_code` is `FEAT-LED-003` on all of them. The originating FEAT is recorded
  in the immutable creation audit event (`audit_events.feat_id`, reachable through the row's own
  `lineage_event_id`). Readers that classify by `feat_code` (`SYSTEM_ORIGINATED_FEAT_CODES`, ITR income-origin
  sets) currently treat every v1 row as system-originated.
- **Governing clauses.** `DOM-LED-001` §VII (row immutability; `feat_code` left mutable by `f1a9c3e60b72`),
  `DOM-OPS-002` §5.4 (signature v1 "retains its original field definition"; no rewrite, no replacement
  signature), `SOP-DB-004` §VII.3 (versioned interpretation must be selected by an explicit, immutable version).
- **Owner ruling (2026-10-06, in the P0B session).** The creation audit event is authoritative for the historical
  originating FEAT. `FEAT-LED-003` on these rows identifies the later updater (the settlement sweep), not who
  created the effect. For these rows:
  1. Origin is attributed from the `feat_id` of the correctly scoped, linked `INSERT` audit event.
  2. Actor attribution is derived separately, from that event's actor context. A settlement label cannot turn a
     student transfer or purchase into a system-originated effect.
  3. Where creation evidence is missing, ambiguous or fails authentication, attribution is reported
     **unavailable**. It is never defaulted to system.
  4. Evidence grade: the Phase 4 review established structural linkage, not production HMAC and complete-chain
     authentication. The recorded origin is therefore *available*; calling it *cryptographically verified*
     requires that verification. The v1 HMAC binds `feat_id` through `actor_context_json`
     (`audit_service.py:294-312`), though it gives no modern full monetary proof.
  5. This is read-side interpretation of retained creation evidence (`DOM-OPS-002` §6.2A). It rewrites no row and
     upgrades no signature. A blanket "origin unknown" is unwarranted, and a blanket "system-originated" is
     incorrect.
- **Production consequence (Q14, `recon_readonly.sql`).** All 974 ledger rows link to an `INSERT` event whose
  `class_id`, `chain_scope` (`class:<class_id>`) and `lineage_token = hmac_signature` agree with the row. Origin is
  therefore available for all 854 v1 rows, and none is ambiguous. The HMAC of each is not yet authenticated.
- **Actor attribution is unavailable from audit actor context, for every row.** `actor_type` and `actor_id_hash`
  are NULL on all 974 linked creation events (v1 and v3). The bound `actor_context_json` carries `feat_id` and
  `correlation_id` but no actor identity. The cause is in the repository: no `audit_protected` caller passes
  them (`ledger_posting_service.py:95`, `feats/prod.py:402`, `attendance_interval_invalidation_feat.py:344-431`),
  and `DOM-OPS-002` §4 allows NULL. The unbound `audit_events.seat_id` equals the row's `actor_seat_id` only for
  `self` rows. For v1 rows the signed payload's `actor_seat_id` and `mechanism` cannot be authenticated either,
  because the payload includes the retired `status` (DEGRADED, `DOM-OPS-002` §5.4). Under ruling item 3,
  actor attribution is therefore reported unavailable. Two questions remain for the owner:
  - May v3 rows take actor from their authenticated nineteen-field payload (`actor_seat_id`, `mechanism`)?
  - Should new creation events populate `actor_type`/`actor_id_hash`?

  **Unresolved by owner direction.** Both are architectural rulings for the governing audit contract, and P0B
  holds no normative authority to answer them.
- **Normative recording deferred to U13.** Under `SOP-DB-004` §VII.7 the ruling belongs in the governing `DOM-*`
  document (`DOM-OPS-002` §6.2A, with a `DOM-LED-001` cross-reference). The owner directed that P0B not amend
  `DOM-OPS-002`, so U6 must not rely on the ruling until U13 records it.

### 5.2 `hall_pass_logs.policy_uuid = 'default'` (U3, also U2 and U5)

- **Rows.** 14 of 16 `hall_pass_logs`, in six classes (Q13), and the writer is still live.
- **Ambiguity.** The value is explicit but names no policy row. What it means (built-in pass types and limits
  at the time, per `HallPassSettings.get_default_pass_types`, `models.py:1264`) is not defined by `DOM-POL-001`/`DOM-PROD-001`. U3 turns "no settings" into
  a refusal, so these rows would have no current writer and no defined reading.
- **Governing clauses.** `DOM-POL-001` §VII (no substitution of a version), `DOM-PROD-001` (hall-pass log as the
  consumption record under R2), `SOP-DB-004` §VII.3, §VII.7.
- **Owner ruling (2026-10-06, in the P0B session).** There is no default hall-pass policy. Hall-pass use is
  gated until the class has the hall-pass feature turned on **and** the teacher has saved a hall-pass settings
  row. Without both, a request is refused; nothing falls back to built-in pass types or writes `'default'`.
- **Repository gap against the ruling.** With no settings row, `feats/prod.py:95` uses
  `HallPassSettings.get_default_pass_types()` (`models.py:1264`) and `feats/prod.py:139` returns `'default'`.
  The live writer therefore contradicts the ruling until the gate lands (U3/U5). The feature gate alone does not
  close it: Q10 and Q13 show `hall_pass` enabled in classes that have never saved a settings row.
- **Historical rows (owner ruling, 2026-10-06).**
  - The 14 existing rows are preserved exactly as historical facts.
  - Their policy terms are **unavailable**. No later policy UUID is retrofitted, no row is rewritten, and no
    claim is made about which settings governed them.
  - A historical operation that needs terms which cannot be established reports that the terms cannot be
    resolved. It does not manufacture them.
- **Live writer.** The owner directed a standalone corrective fix now, outside U3/U5: refuse the operation when no
  settings row exists. The five classes with the feature on and no settings receive that refusal until their
  teacher establishes settings; no settings row is created for them. Fix: #1522 (not deployed as of this record).

### 5.3 Not blocking, recorded for the units

- 606 pre-rollout `payroll_event` rows are UNVERIFIED by NULL linkage. That is lawful as defined
  (`INV-ARC-016` §VI) and needs no ruling. Units must not treat these rows as creation-proven.
- No scheduled payroll has completed (26/26 manual). Any unit relying on the scheduled path has no production
  history for it.

## 6. Rerun

For the post-change comparison in `SOP-DB-004` §IX.5.2, rerun Q1, Q2 and Q12 (and the query of any table the
change touches) and compare by query id. Every difference must be explained by the change.
