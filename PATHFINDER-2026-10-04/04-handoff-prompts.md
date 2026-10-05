# Pathfinder 2026-10-04 — `/make-plan` Handoff Prompts

> Each block below is a ready-to-paste `/make-plan` prompt. All of them share the same ground rules,
> which are repeated inside each prompt so it can run on its own.
>
> **Recommended order:**
> - First, the low-coupling units: U4, U5, U8, U9, U11.
> - Then U3, then U1, then U2. U2 needs U1's reversal path.
> - U7 and U10 are independent of the others.
> - U6 is applied inside every unit, and a final U6 sweep runs last.
> - U13 (document catch-up) should land before or alongside U2 and U12, because their rulings run
>   ahead of the documents.
> - U14 (badge build) runs only after U13 has landed the badge documents.
>
> **Owner rulings (2026-10-04), recorded in `02-duplication-report.md`:**
> - R1: insurance purchase is STORE; the recurring payment is OBL.
> - R2: using a hall pass writes no STORE table; it is PROD's. The request queue stays in Store's
>   `pending_actions` and is removed on approval or rejection.
> - R3: the bug reward becomes badge-only; the ledger posting is retired.
> - R4: the documents catch up.

---

### U1 — Monetary posting through FEAT-LED-000

```
/make-plan Unify all Ledger postings onto the FEAT-LED-000 plan → resolve → apply path.

GROUND RULES: Normative docs are the authority (INV → DOM → FEAT/SPEC/SOP); code, docs/MAP, CHANGELOG and .claude/ are descriptive. Read FEAT-LED-000 (§V, §VII.2, §VIII.3, §XII.1, §XII.5), FEAT-LED-001, SPEC-LED-002 (§V, §VI.2–6.3), DOM-LED-001 (§VII.1, INV-LED-012, INV-LED-015), DOM-PROD-001 §XII, FEAT-PROD-003/004 §VI.2 BEFORE planning. Evidence: PATHFINDER-2026-10-04/01-flowcharts/ledger.md, productivity-payroll.md, store-entitlements.md; 02-duplication-report.md Part A §1 and §9; 03-unified-proposal.md U1.

TARGET: one posting path. Add a credit-plan constructor next to the debit-only builder in app/services/ledger_resolution_service.py (L70-72 raises on credits — the single root cause). Reservation via ledger_command_service.create_reserved_effects; locks via ledger_recovery_service.lock_recovery_scope / lock_ledger_seats.

CALL SITES TO REWRITE:
- app/feats/prod.py:405 (payroll/manual credit) — also derive the per-seat key from the run idempotency_key + seat, not app/services/payroll/settlement.py:209's random cycle id (FEAT-PROD-004 §VI.2)
- app/feats/insurance_claim_feat.py:1984-2000 (reimbursement; drop original_transaction_id that ITR reads as a reversal)
- app/services/ledger_interest_service.py:378-389 (+ remove its CLASS imports L13-23; directive is a plan input)
- app/feats/transaction_void_feat.py:244-257 zero-amount void_item_removed row → delete
- app/services/ledger_transfer_service.py:46-72 hand-rolled reservation → create_reserved_effects
- open-coded seat locks: transfer_feat.py:48, store_purchase_feat.py:166, rent_payment_feat.py:289, purchase_insurance_feat.py:130, insurance_premium_payment_feat.py:135, insurance_coverage_renewal_feat.py:340, direct_entitlement_grant_feat.py:183 (currently unscoped by class), ledger_posting_service.py:20
- app/routes/system_admin.py:1297 bug reward — RETIRE the ledger posting (owner ruling R3: rewards become badge-only). Do not build the badge system here; it needs its governing document first (U13).

ANTI-PATTERNS TO REJECT: a new "posting service" layer; keeping create_pending_transaction as a public alternative; a flag to choose old vs new path; changing posted amounts. Historical ledger rows are immutable — no data migration. Each touched site must also carry its documented FEAT id (U6).

TESTS: per SOP-TEST-003 / INV-ARC-017 — replay of a failed-then-retried payroll run posts once per seat; a concurrent duplicate transfer reports a reservation conflict, not a generic error; watch each regression test fail before the fix.
```

---

### U2 — Entitlement termination: one writer, one reversal entry

```
/make-plan Make entitlement_service.revoke_entitlement the only REVOKED writer and FEAT-LED-002 the only purchase-reversal entry.

GROUND RULES: Normative docs are the authority; code is descriptive. Read DOM-STORE-001 (§VI, §VIII.E, L203), FEAT-STOR-002 (L102, L113, L178), FEAT-STOR-004, FEAT-LED-002 (§VI, L66, L82), DOM-SUP-001 (§I, §VII, §VIII), INV-ARC-021 §V.1–V.6 first. Evidence: 01-flowcharts/store-entitlements.md, support.md, ledger.md; 02-duplication-report.md Part A §2 and §8, Part B SE-1..SE-5; 03-unified-proposal.md U2. DEPENDS ON U1.

TARGET: write = app/services/entitlement_service.py:565 revoke_entitlement; reversal = FEAT-LED-002; read = entitlement_read_service.get_entitlement_lineage_terminal_event (L269, add ordering); coverage read = one function in insurance_coverage_service.

CALL SITES TO REWRITE:
- app/routes/admin.py:10640-10681 support resolve: inline reverse_transaction + db.session.add(EntitlementEvent REVOKED) → invoke FEAT-LED-002; Support records the resolution action only; lock the issue row like escalate (L10763)
- app/feats/transaction_void_feat.py:173-242: StoreProduct read + inline REVOKED → Store query + revoke_entitlement
- two eligibility rules: ledger_correction_service.py:34-90 vs transaction_void_feat.py:140-206 → keep the one FEAT-LED-002 states, delete the other
- entitlement_read_service.py:722 entitlement_terminal_event (no class_id) and inline lookups at insurance_coverage_service.py:176, insurance_claim_service.py:111, collective_goal_expiry_feat.py:80, insurance_coverage_renewal_feat.py:462, api.py:437 → class-scoped read
- terminal-event set re-declared at ledger_correction_service.py:22, insurance_claim_service.py:47, collective_goal_expiry_feat.py:45, transaction_void_feat.py:197, admin.py:3190, entitlement_service.py:69, entitlement_read_service.py:123,166 → one constant
- entitlement_service.py:349 hall-pass bulk revoke (any provenance, student as actor) → revoke_entitlement, direct-grant provenance only, teacher actor
- active-coverage copies: entitlement_read_service.py:415 ≡ :460, student.py:2108, insurance_claim_feat.py:1118 → one coverage read
- GRANTED-per-unit loops: store_purchase_feat.py:476, direct_entitlement_grant_feat.py:316 (stores quantity — forbidden by DOM-STORE-001 L203), entitlement_service.py:177, :253 → one appender, no quantity

IN SCOPE (owner ruling R2: using a hall pass writes no STORE table): delete the Store CONSUMED write prod.py:232 → entitlement_service.consume_hall_pass (:418). Store's hall-pass balance = GRANTED − (EXPIRED + REVOKED) − PROD consumptions referencing the grant (hall_pass_logs.hall_pass_id), read via a PROD query. Historical grants have BOTH a Store CONSUMED row and a log with the same entitlement_id — count each entitlement once; add a regression test on a seat with pre-change history. Keep pending_actions as is: the request is a queued use of a Store entitlement, removed on approval/rejection (owner clarification). Land with U13's DOM-STORE-001 L471 amendment.
Do NOT change the bulk hall-pass grant path (admin.py:8467) except its idempotency key — it works in production; the per-student form admin.py:3747 is the broken one.

ANTI-PATTERNS: keeping the inline writers "as fallback"; a generic "entitlement mutation service" above entitlement_service; Support executing corrective effects itself.
```

---

### U3 — Policies: one read surface, one write surface (FEAT-POL-001)

```
/make-plan Route every policy read through policy_reference_service (exact version, class-scoped) and every policy write through FEAT-POL-001.

GROUND RULES: Normative docs are the authority. Read DOM-POL-001 (§VI, §VI.0, §VI.1, §VI.2, §VII, §X), DOM-POL-001A (§V.E), FEAT-POL-001, DOM-OBL-001 §V.7, INV-ARC-021 §V.1 first. Any policy_versions / policy_transitions concept is illegitimate — each domain's settings table (policy_uuid, append-only, effective_date) is the authority. Evidence: 01-flowcharts/policies.md, obligations.md, productivity-payroll.md; 02-duplication-report.md Part A §6, Part B OB-1, PO-1, PO-2, PR-3; 03-unified-proposal.md U3.

TARGET:
- read: add get_rent_terms(policy_uuid, *, class_id) beside get_insurance_recurring_terms in app/services/policy_reference_service.py — exact version, one_or_none, NO fallback to current
- in-force: hall pass = class_configuration_query_service.get_hall_pass_settings (newest IN_USE); payroll already via services/payroll/settings.py
- write: FEAT-POL-001 with one supersede(current, successor) (retire-then-insert) and one availability validator (RETIRED terminal)

CALL SITES:
- rent terms: obligations_service.py:225,236; obligation_view_model.py:204; reconcile_rent_feat.py:299 (unscoped), :324; rent_payment_feat.py:350-356 (delete fallback-to-current); student.py:581,605; admin.py:1768,1787,5156
- hall pass in force: feats/prod.py:86-94 and :205-213 (effective-date, ignores availability) → read once, pass in; delete feats/attendance.py:9-25; prod.py:139 "default" placeholder id → explicit refusal
- supersede ×4: admin_settings_service.py:49-81, feats/attendance.py:98-111, store_service.py:304-322, feat_class_003…py:466-480
- availability ×2: store_service.py:325-331, insurance_definition_service.py:180
- FEAT ids: FEAT-SETTINGS-001 (admin.py:4618,4926,5015,5256; feats/attendance.py:71,115), FEAT-ADMN-001 (admin.py:7858), insurance writes under FEAT-CLASS-003, rebalance policy writes under FEAT-CLASS-005 (admin.py:6687) → FEAT-POL-001
- collective_goal_expiry_feat.py:220 writes store_products.availability_state → FEAT-POL-001 call

ANTI-PATTERNS: a policy "version pointer" or version table (DOM-POL-001 §VI.0); a generic multi-family policy repository class; keeping the fallback-to-current "for safety". Every new read takes class_id.
```

---

### U4 — CWI: one derivation, with as-of

```
/make-plan Make economic_engine.resolve_base the single CWI derivation and give it an as_of parameter.

GROUND RULES: Normative docs are the authority. Read SPEC-ECON-003 (§1, §2, §3, §4.1, §5.6), DOM-CLASS-001 §X, DOM-CLASS-003, DOM-ITR-001 (§II, §VII, §IX), INV-ITR-004 first. Evidence: 01-flowcharts/class-configuration.md, interpretation.md; 02-duplication-report.md Part A §4, Part B CC-1, CC-3; 03-unified-proposal.md U4.

TARGET: app/services/economic_engine.py:286 resolve_base(class_id, *, as_of=None), as_of backed by the existing economic_engine_effective_at.

CALL SITES:
- class_configuration_query_service.py:423-456 calculate_cwi (float) → delete; get_banking_directive (L757, L772) uses resolve_base. NOTE: this shifts the progressive overdraft fee by up to one cent (worked example in Part A §4) — surface it in the plan and CHANGELOG
- class_configuration_economic_service.py:43-56 → delete
- utils/economy_balance.py:256-320 → thin breakdown over resolve_base
- interpretation/reference_configuration.py:62-71 → resolve_base(class_id, as_of=cycle_completed_at) (fixes mixed as-of)
- class_configuration_view_models.py:202 (float) vs :238 (resolve_base) — same page shows two CWIs
- policy-mode readers: economy_policy.py:389-400 (user-keyed FeatureSettings — delete), :403-419, class_configuration_query_service.py:467-490 → resolve_base(...).economy_policy_mode

ANTI-PATTERNS: keeping a float path; a "CWI service" wrapper over resolve_base; ITR computing anything CLASS owns. Hours = 0 yields "not ready" (None), not $0.00.
```

---

### U5 — Attendance intervals and hall-pass lifecycle

```
/make-plan Make list_attendance_interval_evidence the only live pairing rule and resolve_hall_pass_lifecycle_status the only hall-pass lifecycle read.

GROUND RULES: Normative docs are the authority. Read DOM-PROD-001 (L116, L667, §683, §VIII.2), SPEC-PROD-001, FEAT-PROD-001/002, DOM-IDEN-002 §VIII.2 first. Evidence: 01-flowcharts/productivity-payroll.md, store-entitlements.md; 02-duplication-report.md Part A §5, Part B PR-1, PR-2, PR-4, PR-7; 03-unified-proposal.md U5.

TARGET: app/services/attendance_service.py:252 list_attendance_interval_evidence; resolve_hall_pass_lifecycle_status (used at api.py:1083).

CALL SITES:
- attendance_service.py:504-529 / :532-559 via _pair_active_intervals (:111) → clip list_attendance_intervals to the day window (mirror payroll/corrections.py _worked_seconds_in_window); _today calls _for_date. Affects insurance lost-time payouts (insurance_claim_feat.py:917,1002,1460,1478) and "Time Today" (api.py:1742,1752,1806) — state the behaviour change
- app/attendance.py:51-148 → delete (no app callers; update tests/dom/attendance/test_attendance.py)
- teacher leave/return api.py:891-921, student checkout api.py:1000-1013 → pass-scoped resolver; idempotency keys deterministic (remove secrets.token_hex)
- seat-latest-event query inlined at api.py:767,887,912,1001,1737,1792; admin.py:8259; attendance_service.py:~628 → one latest_attendance_event(seat_id, class_id)
- payroll recompute ×3: settlement.py:196-203, prod.py:354-357, pricing.py:147 → compute once
- api.py:1196-1316 hall-pass history: add claimed-seat filter, share window/pagination with api.py:1522-1669

KEEP: services/payroll/corrections.py:128 legacy replay (DOM-PROD-001 §683). The Store CONSUMED removal (owner ruling R2) is done in U2; U5 provides the PROD read "consumptions referencing grant X" that U2's balance needs.

ANTI-PATTERNS: a pairing "strategy" parameter; keeping the legacy helper for display; any change to historical correction replay.
```

---

### U6 — FEAT identity matches the FEAT documents (final sweep)

```
/make-plan Align feats/base.py FEAT_REGISTRY and every FEATContext/requires_feat_context call with the documents in docs/FEATURE-EXECUTION/.

GROUND RULES: Normative docs are the authority. Read FEAT-CORE-000, DOM-LED-001 §VII.1, SPEC-ITR-001 §6.3/§6.6/§10.2, and the title/scope of every FEAT-* doc first. Owner ruling R1: insurance purchase is STORE (FEAT-STOR-001); the recurring payment is OBL. FEAT-OBL-004/005 are removed by U12. Evidence: 02-duplication-report.md Part A §3; every 01-flowcharts/*.md "Deviations" section; 03-unified-proposal.md U6. Run LAST, after U1–U5 have corrected the sites they touch.

TARGET: app/feats/base.py:196 FEAT_REGISTRY — one entry per FEAT document, title = document title; ledger_provenance_query_service.py:58-74 SYSTEM_ORIGINATED_FEAT_CODES and interpretation/income_origin.py:64-75 sets reviewed against those titles.

CHANGES:
- delete undocumented ids: FEAT-SETTINGS-001, FEAT-ADMN-001, FEAT-OBLI-001 (assess_obligation_feat.py:111), FEAT-OBL-004/005 (removed by U12 under R1); stop honouring FEAT-BYPASS-LEGACY in prod code (models.py:709, base.py:522-549)
- FEAT-OPS-001 = audit emission only: move sysadmin login (system_admin.py:144), passkey routes (admin.py:10118,10195,10252; system_admin.py:265,348,404), support update/resolve (system_admin.py:894,1231), scheduled_tasks.py:139
- FEAT-IDEN-001 = unauthenticated student claim only: move student login/switch (student.py:2901,3135), teacher login/set-class (admin.py:2204,2597,3080,3278), cli_commands.py:141
- rent payment FEAT-OBL-001 → FEAT-OBL-003; student transfer (student.py:1624) not system-originated; insurance premium self-payment classified like rent; class creation runs execute_create_class_boundary (FEAT-CLASS-001) instead of classroom_setup.create_class under a route-opened context
- where behaviour has no FEAT doc (e.g. FEAT-IDEN-005 class binding): list it as a DOCUMENTATION GAP for the owner — do not invent an id

CAVEAT: ledger rows are immutable; classifiers must keep recognising legacy feat_code values on historical rows (read-side mapping, no data migration).

ANTI-PATTERNS: inventing ids to fill gaps; a dynamic registry; renaming docs to match code.
```

---

### U7 — Principal session and context

```
/make-plan Consolidate principal session establishment into auth.establish_*_session and remove alternate CanonicalContext constructors.

GROUND RULES: Normative docs are the authority; .claude/rules/security.md is NOT (it describes a 10-minute teacher idle timeout; DOM-IDEN-003 §VII's fixed session window governs and the .claude text is what gets corrected). Read DOM-IDEN-003 (§Session Establishment L187-192, §VII step-up), DOM-IDEN-006 (§IX, §XII), INV-ARC-019 first. Evidence: 01-flowcharts/identity-teacher.md, identity-student.md; 02-duplication-report.md Part A §10, §14, §15, Part B IT-2, IS-5, PR-6; 03-unified-proposal.md U7.

TARGET: app/auth.py:390 establish_teacher_session / establish_sysadmin_session own the full sequence (clear, nonce, current_session_started_at/expires_at, timestamps).

CALL SITES:
- teacher TOTP admin.py:2595-2613, teacher passkey admin.py:10219-10234, sysadmin TOTP system_admin.py:181-187, sysadmin passkey system_admin.py:374-381 (does not clear)
- app/__init__.py:787-792 builds a CanonicalContext for another class → display read taking class_id
- admin.py:855 _get_teacher_seat_for_class (8 sites) → g.canonical_context.seat_id
- scheduler synthetic contexts scheduled_tasks.py:75-80, :317-322, payroll/settlement.py:80-93, insurance_coverage_service.py:63, insurance_coverage_renewal_feat.py:120 → one helper beside identity_service.resolve_teacher_seat_for_class
- teacher-seat authority predicate: feat_class_004:228,436; feat_class_005:269; feat_class_008:75; identity_service.py:120; announcement_service.py:8; identity_feat.py:143,422,691,755 → one Identity helper
- add step-up for passkey register/remove and account deletion (admin.py:8894) per DOM-IDEN-003 §VII

KEEP SEPARATE: teacher vs sysadmin passkey route sets (different principals; passkey_service already shared).

ANTI-PATTERNS: a "session manager" class; a second context resolver; storing class context for sysadmins.
```

---

### U8 — Operations integrity

```
/make-plan Collapse audit chain verification to one strict walk, error persistence to operational_event_service, and protected-field lists to one registry.

GROUND RULES: Normative docs are the authority. Read DOM-OPS-001 (§5, §8.1, INV-OPS-009), DOM-OPS-002 (L86, L262, L363, INV-OPS-019, §2.3/§6.3), FEAT-OPS-001, SPEC-OPS-003 first. Evidence: 01-flowcharts/operations-audit.md; 02-duplication-report.md Part A §13, §16, Part B OA-1..OA-3; 03-unified-proposal.md U8.

TARGET: app/utils/audit_verifier.py one _walk_chain applying all checks (class_id + hmac_signature == event_hash); app/services/operational_event_service.py sole error sink; audit_verifier.LEDGER_FIELDS_BY_VERSION sole field registry.

CALL SITES:
- chain walks audit_verifier.py:117 (verify_chain, currently weakest), :569, :725
- audit_service.py:386-436 stub delegators with ImportError fallbacks → delete
- app/__init__.py:155-189 and tlcp.py:53 target dropped error_events → operational_event_service
- ledger_posting_service.py:8-13 field list → import registry; drop stale "transaction" key in PROTECTED_FIELDS_BY_TABLE
- audit_protected fails open on ImportError (feats/base.py:590) → fail closed

NOT IN SCOPE (needs a DOM-OPS-002 decision, flag to owner): where integrity_status persists now that the table was dropped; /health/status invariant_verification always UNKNOWN.

ANTI-PATTERNS: re-creating dropped tables without a DOM-CORE-002 entry; a verifier "mode" flag.
```

---

### U9 — Domain-owned presentation builders

```
/make-plan Delete services/view_model_builders.py and move its live builders into their domains' builders modules.

GROUND RULES: Normative docs are the authority. Read SPEC-UI-001 (§VIII, §IX, §XIV), INV-ARC-021 §V.5, INV-ARC-022 first. Evidence: 02-duplication-report.md Part A §12; 03-unified-proposal.md U9.

CALL SITES:
- build_identity_profile_view (admin.py:1267, 3343) → services/identity/builders.py
- build_store_management_view (admin.py:4787) → services/store/builders.py
- build_entitlement_list_view, build_purchase_history_view, build_policy_list_view (no app callers) → delete
- obligation_view_model.py → services/obligations/builders.py, reading rent terms via U3 (do after U3, or leave the rent read for U3)

ANTI-PATTERNS: a shared "base builder"; moving domain queries into templates.
```

---

### U10 — Obligations internals

```
/make-plan Consolidate Obligations-internal duplication: class-scoped latest-cycle read, one untouched-assessments query, one payment settlement routine.

GROUND RULES: Normative docs are the authority. Read DOM-OBL-001 (ratified v3.x: §V.7, §V.8, §VIII, §IX.15, §IX.16, §158, §160), FEAT-OBL-001/002/003 first. FEAT-OBL-004 is an unratified draft — not authority. Evidence: 01-flowcharts/obligations.md; 02-duplication-report.md Part A §11, Part B OB-2..OB-5; 03-unified-proposal.md U10.

CALL SITES:
- obligations_service.py:577 get_latest_bill_cycle(internal_ref) (no class_id, 9 callers) → (class_id, internal_ref); inline copies :772-777, :812-822; admin.py:1785, 5149 use "latest" as "current" → current-period read (§158)
- terminate_bill_cycle_feat.py:108-129 and feat_class_004_feature_enablement.py:163-187 (RENT-only, queries OBL tables directly) → one Obligations query; CLASS-004 keeps coordinating (§IX.15)
- rent_payment_feat.py:289-316,407-432 vs insurance_premium_payment_feat.py:83-148 (double recovery lock; hard-coded "FEAT-OBL-003" in replay) → generalise settle_insurance_premium into settle_obligation_payment; feat code from get_active_feat_name()
- waiver check admin.py:5659 → obligations_service.check_idempotency_satisfaction (:644)

SEPARATE DEFECTS FOUND (plan as their own items, not consolidation): rent disable stops accrual on surviving debts (scheduled_tasks.py:206, §IX.16); unresolvable amount reads as SATISFIED (obligations_service.py:211-253, 486; §VIII); ACT-OBL-001 never emitted.

ANTI-PATTERNS: an obligation "type registry"; OBL reading policy tables (use U3's reads).
```

---

### U11 — Local deletions and consolidations

```
/make-plan Apply the low-coupling within-domain deletions and consolidations from Pathfinder 2026-10-04 (identity, class configuration, support, ledger, interpretation).

GROUND RULES: Normative docs are the authority. For each item read the cited doc section before changing code. Evidence: 02-duplication-report.md Part B (IS-*, IT-1, IT-4, CC-2, CC-4..CC-6, SU-*, LG-2, LG-4, IN-*); 03-unified-proposal.md U11.

ITEMS:
- identity: delete teacher_destruction.py:229-303 dead residual helpers + duplicate PendingAction block (:191-203); delete classroom_setup.create_student, update_or_create_roster_seat, feat_class_002 execute_modify_student; one _match_unclaimed_seat for identity_feat.py:182-246 and :513-584; one seat_is_claimable (user_id IS NULL AND claimed_at IS NULL; DOM-IDEN-002 §VIII) for student.py:448,525,771 and identity_feat.py:341; one clear_onboarding_session (student.py:765,949,2949; recovery.py:69,78,94); shared destruction gate (admin.py:1212 / 8917); delete dead DOB code (utils/claim_credentials.py; admin.py:639,798 — DOM-IDEN-002 §XI)
- class config: interest/compound coupling into feat_class_005 _validate_engine_field (SPEC-ECON-003 §5.6), delete route copy admin.py:8809-8827; shared CLASS-004/005 preamble and _parse_effective_at_timestamp; enabled_features(class_id) + ClassFeature.feature_names() for admin.py:9300; conditional pointer clear (admin.py:4008 vs 4200)
- support: create_support_ticket (issue_service.py:7-51) shares create_issue core incl. OPEN history (DOM-SUP-001 L190); one fail-closed class-scoped issue lookup (admin.py:10504,10574,10836 fail open); status aliases from LEGACY_TO_CANONICAL_STATUS (fix system_admin.py:802 developer_review bucket); opaque refs only (admin.py:10388 accepts numeric ids); update_issue_status at system_admin.py:1273,1329
- ledger: delete get_pending_balance_delta (ledger_balance_query_service.py:70; INV-LED-015); allocate_reconstructed_shares reuses _share_cents
- interpretation: compute shared reads once per pass in compute.py; reference_configuration._money → canonical_decimal

ANTI-PATTERNS: bundling these into a "utils" module; behaviour changes beyond the cited doc requirement. Each item gets its own regression test where behaviour changes.
```

---

### U12 — Insurance acquisition split along R1

```
/make-plan Split insurance acquisition per owner ruling R1: the purchase (first payment that gains the entitlement) runs under FEAT-STOR-001; establishing the recurring payment (bill cycle) is OBL; delete FEAT-OBL-004/005.

GROUND RULES: Normative docs are the authority, BUT owner ruling R1 (2026-10-04) runs ahead of ratified FEAT-STOR-001 v3.1 L28-32/L332, which still routes insurance to FEAT-OBL-004 — that text is being amended in U13; land together. Read DOM-OBL-001 (§II.B, §V, bill-cycle succession: one succession command schedule_next_bill_cycle), DOM-STORE-001 (§I, §VIII.E.1 coverage lifecycle; insurance is NON-revocable), FEAT-STOR-001, FEAT-STOR-002 (§IX.C, §XIV), FEAT-STOR-007, INV-ARC-021 first. FEAT-OBL-004 is a draft — not authority. Evidence: 01-flowcharts/store-entitlements.md, obligations.md; 03-unified-proposal.md U12.

TARGET: store_purchase_feat (FEAT-STOR-001) performs the insurance purchase (first payment via FEAT-LED-000 debit plan + GRANTED) and coordinates OBL's bill-cycle establishment through an OBL command; later premiums stay with insurance_coverage_renewal_feat (FEAT-STOR-007) settling via OBL.

CALL SITES:
- app/feats/purchase_insurance_feat.py:91 (FEAT-OBL-004) reached from app/routes/student.py:1876 → FEAT-STOR-001 path; delete the module
- app/feats/cancel_insurance_feat.py:86 (FEAT-OBL-005, no doc) reached from student.py:1922 → cancel = stop-renewal: OBL terminal bill cycle (terminate_bill_cycle_feat; next_assessment_at NULL) + Store EXPIRED at the cycle boundary. No revoke, no refund, no early expiry; the cooldown is a future-purchase gate only
- the interim insurance-only establish_bill_cycle: confirm against DOM-OBL-001 which OBL command establishes the first cycle; do not add a second succession path
- purchase_insurance_feat.py:130 open-coded seat lock and :142 GRANTED query → U1 lock helper / U2 coverage read

ANTI-PATTERNS: Store writing bill_cycles or assessment_events; OBL writing entitlement_events; an insurance-specific posting path; keeping FEAT-OBL-004 as an alias.
TESTS: purchase creates exactly one GRANTED + one first-payment ledger effect + one bill cycle; replay is idempotent; cancel leaves coverage active until the boundary then EXPIRED; watch each test fail first.
```

---

### U13 — Normative documents catch up (R1–R4)

```
/make-plan Amend the normative documents to match owner rulings R1–R4 from Pathfinder 2026-10-04, following SOP-DOC-000 (versioning, amendment record) — documentation only, no code.

GROUND RULES: Only docs/INVARIANT, docs/DOMAIN, docs/FEATURE-EXECUTION, docs/SPEC, docs/STANDARD_OPERATING_PROCEDURES are normative; amend them per SOP-DOC-000 and keep authority order (DOM outranks FEAT). Do not cite .claude/, MAP, CHANGELOG or this Pathfinder output as authority — cite the owner ruling date (2026-10-04) in each amendment record. Evidence: 02-duplication-report.md "Owner rulings"; 03-unified-proposal.md U13.

AMENDMENTS:
- R1: FEAT-STOR-001 (L28-32, L332) owns insurance purchase (first payment → entitlement) and states the hand-off to OBL for establishing the recurring bill cycle; retire draft FEAT-OBL-004; check DOM-OBL-001 §II.B and FEAT-STOR-007 for consistency.
- R2: DOM-STORE-001 L471 — approval writes the PROD hall_pass_logs record; no Store CONSUMED row (consistent with §VIII.E.6); align FEAT-PROD-002 and FEAT-STOR-002 (L102, L113); state how Store's hall-pass balance reads PROD consumption. Keep §IX's pending_actions removal on approval/rejection (request = queued use of an entitlement; owner clarification 2026-10-04).
- R3: badges are an OPERATIONAL concern granted by the sysadmin, not a business domain (owner, 2026-10-04) → govern them under Operations (DOM-OPS-001 section or SPEC-OPS-004 extension): 6 categorical + 3 milestone definitions, tables (DOM-CORE-002 entry), awarding FEAT, sysadmin as the only awarder. Badges create no ledger, entitlement or class-economic state. Amend SPEC-OPS-004 to remove the ledger-reward path (§6.3 vs §VII). START FROM THE ARCHIVE, do not draft from scratch: an existing design is preserved at annotated tag `archive/bug-hunter-badges-20260914` → `3cdb1294` (DOM-OPS-003_BADGE_SYSTEM.md, SPEC-OPS-001/002 badge SPECs, 9 SVGs under app/static/badges/; tracked as PL-OPS-04 in docs/TRACKING/POST_LAUNCH_TRACKER_2026.md). Port the badge files only — never merge 3cdb1294 (the rest predates main). Both SPEC numbers are taken on main (SPEC-OPS-001 = reversal/void, SPEC-OPS-002 = external status), so renumber; DOM-OPS-003 is still free. The design already matches the rulings: Operations-owned, non-monetary (§V forbids any ledger effect), recipient anchored to the reporter's seat_id with only seats.public_id exposed, awarded only by the Operations issue-resolution FEAT, not teacher-configurable. Catalog CONFIRMED by owner 2026-10-04: 9 badges = 6 categorical + 3 engineering milestones (Uptime ≥2, System ≥4, Architecture = all 6), as archived. CERTIFICATE SURVIVAL (owner, still to build): a student must be able to validate a badge after their seat is destroyed, without exposing identity. SPEC §IX already defines a detached certificate record (no FK, no class_id/seat_id/user_id; holds a certificate-code lookup digest + first/last-name match digest). What the docs must add before code: (a) explicit authorization for that name-match digest to outlive the seat — INV-ARC-018 requires seat PII deleted with the seat and says an artifact must not outlive its identity 'absent an explicitly authorized, separately scoped requirement', so the requirement must be stated (DOM-OPS-003 + an INV-ARC-018 cross-reference), and INV-ARC-012/013 must treat the certificate as unanchored rather than residue; (b) a PEPPER_KEY rotation strategy for these digests (SOP-SEC-001 §V.2a: rotation cannot reproduce existing digests); (c) how an award is invalidated while the seat exists (e.g. a one-way award→certificate pointer) and that after destruction the certificate is immutable. Port via `git show 3cdb1294:<path>` (fetch tags first: git fetch origin 'refs/tags/archive/*:refs/tags/archive/*').
- R4: DOM-ITR-001 v1.7 (§V, §VIII, §IX, §XIII) and SPEC-ITR-001 §16 — materialization writer is live (complete_payroll_cycle.py:112-119); DOM-IDEN-003 §V add recovery_class_challenges; reconcile §IX on recovery-code hashing with the implementation or flag which is wrong.
- Gaps surfaced by U6/U8 — list for the owner rather than inventing: FEAT-IDEN-005 (class binding, DOM-IDEN-005 §VIII), FEAT-ITR-001 (registered, no contract), where DOM-OPS-002 integrity status persists after integrity_status was dropped.

ANTI-PATTERNS: editing docs to match code where no ruling exists; amending a DOM doc through a FEAT doc; silent edits without an amendment record.
```

---

### U14 — Build the badge system and destruction-surviving certificate verification (after U13)

```
/make-plan Implement the Bug Hunter badge system (Operations) and its public certificate verification, which must keep working after the recipient's seat — or their whole class or teacher account — is destroyed, without exposing identity.

GROUND RULES: Normative docs are the authority. This unit runs ONLY after U13 has landed DOM-OPS-003 and the renumbered badge SPECs on main (ported from tag archive/bug-hunter-badges-20260914 → 3cdb1294; never merge that commit). Read those, plus DOM-OPS-001, INV-ARC-012, INV-ARC-013, INV-ARC-018 (incl. the incorporated SPEC-SEC-001 §V.2), SOP-SEC-001 §V.2–§V.2a, INV-ARC-019, DOM-IDEN-006, FEAT-CLASS-006, FEAT-IDEN-007, DOM-SUP-001 first. Owner rulings 2026-10-04: badges are an operational, sysadmin-granted concern; 9 badges = 6 categorical + 3 engineering milestones (2/4/6); no monetary effect (the ledger bug reward at app/routes/system_admin.py:1297 is retired in U1).

TARGET:
- award: the Operations issue-resolution FEAT is the only award initiator; awards anchored to the recipient's seat_id + class_id (cease with the seat per INV-ARC-013); engineering badges derived, never stored as truth
- certificate: one detached record per earned badge, written in the same FEAT transaction as the award; no FK and no class_id/seat_id/user_id; certificate-code lookup digest + first/last-name match digest built via SPEC-SEC-001 normalization and HMAC with a dedicated domain-separation label; optional sysadmin-authored public-safe description
- verify: public endpoint takes certificate code + first/last name; uniform response for "no such code" vs "name mismatch" (no enumeration); rate-limited (app/extensions.py limiter) and Turnstile-protected; grants no access; GET is pure (INV-ARC-007)
- invalidation: while the seat exists, an authoritative correction marks the certificate invalid through the award→certificate pointer; after destruction the certificate is immutable

MUST PROVE (tests, each watched failing first):
- FEAT-CLASS-006 class destruction, seat removal and FEAT-IDEN-007 teacher account destruction (app/services/teacher_destruction.py) delete awards but leave certificates, and a certificate still verifies afterwards
- no certificate row or verification response contains or can join back to class_id, seat_id, user_id, public_id, join_code or a decrypted name
- a wrong name for a valid code is indistinguishable from an unknown code
- PEPPER_KEY behaviour matches the rotation strategy U13 recorded
- structural guard (SOP-TEST-003 §IX.A, with a mutation proof): destruction code paths never touch the certificate table, and the certificate model declares no ForeignKey

ANTI-PATTERNS: storing a seat/user reference "for convenience"; soft-deleting awards to keep certificates linked; encrypting (recoverable) names into the certificate; letting teachers award, hide or revoke badges; any ledger or entitlement write.
```
