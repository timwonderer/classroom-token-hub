# CTH v2 Post-Launch To-Do

| Field | Value |
|---|---|
| Status | **ACTIVE — canonical post-launch backlog** |
| Created | 2026-09-14 |
| Verified against | `main` @ `f0b00d3cb` — every item below was re-checked against the code on 2026-09-14, not copied forward |
| Launch target | 2026-09-17 ([`PRODUCTION_READINESS_2026-09.md`](PRODUCTION_READINESS_2026-09.md)) |
| Authority | Descriptive. Normative authority is `INV-CORE → INV-ARC → DOM → FEAT`; where this file and a normative document disagree, the document wins and this file is corrected |

---

## How to use this document

- **Scope.** Work deliberately deferred past launch. Launch blockers are **not** tracked here — they
  live in the launch checklist in `PRODUCTION_READINESS_2026-09.md` §V. If an item here turns out to
  block launch, move it there and strike it here.
- **One home for status.** The post-ship findings in `PRODUCTION_READINESS_2026-09.md` §V and the
  backlog in §VI are tracked to closure here. Their reasoning stays there; do not duplicate it.
- **Closing an item.** Strike it through and append the date and closing commit SHA, e.g.
  `~~PL-OBL-01 …~~ **Closed 2026-10-02 (`abc1234`)**`. Do not delete rows. When every item is closed,
  archive this file per [`README_DOMAIN_TRACKING.md`](README_DOMAIN_TRACKING.md) rule 3.
- **Before starting an item**, read its governing normative document, and re-verify the evidence —
  line numbers here are a snapshot. Architecture refactors follow the order in
  `SOP-DEV-001` §VI.B (identity → scope → enforcement → services → interface).
- **IDs are stable.** New items take the next number in their area.

Priority: **P1** — schedule in the first post-launch cycle. **P2** — schedule when the area is next
touched or capacity allows. **Watch** — no work unless the stated trigger fires.

---

## 1. CI and repository automation

| ID | Pri | Item | Evidence | Next step |
|---|---|---|---|---|
| PL-CI-01 | P1 | **Constitutional CI secrets fix is written but not merged.** Every Dependabot PR fails Constitutional CI because Dependabot runs receive no Actions or environment secrets and the empty `ENCRYPTION_KEY` crashes conftest. | Branch `claude/serene-lalande-e14b1d` (`08cbe99`, merged with `main` at `127117c`); dispatched run 34922923925 green. Safe to land before launch. | Open the PR and merge. Then: delete the now-unreferenced `testing` environment secrets (`AUDIT_HMAC_KEY`, `ENCRYPTION_KEY`, `PEPPER_KEY`, `SECRET_KEY`), and comment `@dependabot rebase` on one open Dependabot PR to confirm it goes green. |
| PL-CI-02 | P1 | **Classifier drops unknown paths when any other path matches.** `select_families()` runs its unknown-path fallback (CI-ARC-EXEC, CI-SCOPE, CI-VALIDATION) only `if not selected`. #1383 bumped SQLAlchemy, psycopg2 and cryptography alongside two workflow files and ran CI-VALIDATION alone. | `scripts/ci_classifier.py` `select_families`; run 34922891023 artifact. `SPEC-INV-001` §IX lists no dependency-change class, so this is not a MUST violation — the fallback is permitted over-selection that behaves inconsistently. | Decide, then do one: (a) fallback per unmatched path, or (b) give `requirements.txt` an explicit `path_rules` entry in `.ci/invariant_families.yml`. Consider adding a dependency-change class to `SPEC-INV-001` §IX. Regression test with a mixed-path diff. |
| PL-CI-03 | P2 | **Actions pinned to Node 20 majors** (runs are force-migrated to Node 24 with a deprecation annotation). | `actions/checkout@v4`: `constitutional-ci.yml`, `github-pages-transition.yml`, `deploy-status.yml` ×2. `actions/setup-python@v5`: `constitutional-ci.yml`, `deploy-status.yml`, `policy-guardrails.yml` ×2. The rest of the repo is on `checkout@v7` / `setup-python@v6`. | Bump in one PR, and check why Dependabot has not proposed these. |
| PL-CI-04 | P2 | **Evidence families declare uncovered subclaims.** Most concrete: CI-TEMPORAL does not cover timezone immutability, prohibited API scans or historical non-reinterpretation; CI-PERSIST lacks AuditEvent lineage and PII-deletion evidence. | `known_limits` in `.ci/invariant_families.yml` (all 8 families declare one). | Per `SPEC-INV-001` §VI, a material gap is partial evidence. Add evidence for CI-TEMPORAL and CI-PERSIST first. |
| PL-CI-05 | P2 | **Stale FEAT-bypass scaffolding.** The autouse `FEATBypass` fixture is gone (flag day done), but `pytest.ini:7` still describes `enforce_feat` as opting out of it, and two files link to the deleted plan. | `pytest.ini:7`; `tests/conftest.py:15`; `tests/_feat_bypass_audit.py:384-385`; plan deleted in `fbc46d8b7`. `enforce_feat` is used only in `tests/dom/operation/test_feat_enforcement.py`. | Decide whether the marker still means anything; fix the description or remove the marker, and drop the dead links. |
| PL-CI-06 | P2 | **actionlint `info` findings** (CI fails only on `error`, so these do not block). | `check-migrations.yml:88` SC2086; `release-v2.yml:86` and `toggle-maintenance.yml:82` SC2029. | Quote the variable; confirm the two SC2029 client-side expansions are intended. |

## 2. Dependencies

| ID | Pri | Item | Evidence | Next step |
|---|---|---|---|---|
| PL-DEP-01 | P1 | **Deferred dependency batch.** `alembic` 1.19.2, `Mako` 1.4.1, `gunicorn` 26.2.0, `redis` 8.1.0, `google-auth` 2.58.0, `google-cloud-firestore` 2.30.0, `google-github-actions/auth` and `setup-gcloud` v3. None closes a vulnerability this deployment is exposed to. | PR #1384 (draft, "merge after launch"), branch `claude/deps-risky-upgrades`, one commit per bump. | Merge piecemeal after launch; the migration-tooling pair (`alembic`, `Mako`) with a full upgrade/downgrade rehearsal. |
| PL-DEP-02 | P2 | **Dependabot is not pointed at `docs-site/`.** It declares only `pip` and `github-actions` at `/`, so it can never open a PR for the manifest its security alerts are about. | `.github/dependabot.yml`; `PRODUCTION_READINESS_2026-09.md` §V "Cross-cutting". | Add an `npm` ecosystem for `/docs-site`. |
| PL-DEP-03 | Watch | **`image-size` advisories dismissed on reachability.** | CHANGELOG 2026-09-12; guard `tests/test_docs_site_image_advisory_guard.py` fails if an image enters `docs-site/`. | Reassess when Docusaurus or `image-size` publishes a fixed dependency, or if the guard fires. |

## 3. Identity

| ID | Pri | Item | Evidence | Next step |
|---|---|---|---|---|
| PL-IDEN-01 | P2 | **Teardown commands live in the route module.** They are proper FEAT/domain commands but sit in `app/routes/admin.py`. | `_destroy_class_scope_rows` `app/routes/admin.py:1158`; `FEAT-IDEN-007` entry `:1458`. | Move under `app/feats/`; behavior-preserving. |
| PL-IDEN-02 | P2 | **Debug `print()` calls in the context resolver.** | 7 × `print("DEBUG: …")` before raises, `app/services/context_resolver.py:108-134`. | Replace with structured logging or remove. |
| PL-IDEN-03 | P2 | **`Seat.block` compatibility property.** No seat `.block` reads remain in `app/` or templates. | `app/models.py:280-290`. | Remove the property. |
| PL-IDEN-04 | P2 | **Seat bound to a variable named `student`.** Low value on its own — `.claude/CLAUDE.md` documents the convention — so only when touching the code. | `app/routes/student.py:685`, `:829`. | Rename in passing. |

## 4. Class Configuration

| ID | Pri | Item | Evidence | Next step |
|---|---|---|---|---|
| PL-CLASS-01 | P2 | **`customizations()` writes class fields under an identity FEAT.** `ClassEconomy.display_name` and `section` are edited inside `FEAT-IDEN-001`. | `app/routes/admin.py:3737` (handler), `:3756` (context), `:3778-3784` (writes). | Route through the Class Configuration FEAT that owns those fields (`DOM-CLASS-001`). |
| PL-CLASS-02 | P2 | **`replace_enabled_class_features` is dead.** Defined and imported, never called. | `app/utils/economy_policy.py:294`; import `app/routes/admin.py:96`. | Delete both. |
| PL-CLASS-03 | P2 | **`ClassEconomy.status` pseudo-lifecycle shim.** Always returns `"active"`; setter is a no-op. Membership is existence-based (`INV-ARC-013`/`014`). | `app/models.py:328-333`. | Confirm no readers, then remove. |

## 5. Ledger

| ID | Pri | Item | Evidence | Next step |
|---|---|---|---|---|
| PL-LED-01 | P2 | **Residual `user_id` and `join_code` on `ledger_transaction`.** `join_code` also leads the `ix_transaction_seat_ledger` index. | `app/models.py:460`, `:465`, `:535`. | Schema contraction (`CONTRACT (DATABASE)`), with an index replacement keyed on `class_id`/`seat_id`. |
| PL-LED-02 | P2 | **Payroll reversal still finds its original by heuristic.** Picks the latest row by `correlation_id`; the reversal it writes carries no `original_transaction_id`. Ledger's own `reverse_transaction` was fixed on 2026-09-14. | `app/feats/prod.py:570-596`, `:622-633`; `record_payroll_reversal` (`:672`) has no callers. | Either delete the unused path or give it the explicit link `reverse_transaction` uses. |
| PL-LED-03 | Watch | **Interest reservations accepted under fingerprint v1** replay only while the recomputed amount is unchanged. Deliberately not worked around. | CHANGELOG 2026-09-14, "Replayed Ledger commands are compared under the fingerprint version they were accepted with". | Self-expires once the first post-deploy month's interest reservations close. No action unless a v1 mismatch is reported. |

## 6. Productivity and Payroll

| ID | Pri | Item | Evidence | Next step |
|---|---|---|---|---|
| PL-PROD-01 | P2 | **No `daily_limit` attendance reason.** Daily-limit auto tap-out records `DONE_FOR_DAY`; the limit survives only in free text. | `AttendanceReasonCode` `app/models.py:73-77`; `app/scheduled_tasks.py:204`, `:236`. | Add the enum value (migration) and record it on auto tap-out. |

## 7. Store, Entitlements and Insurance

| ID | Pri | Item | Evidence | Next step |
|---|---|---|---|---|
| PL-STORE-01 | P2 | **`InsuranceClaim.status` is updated in place.** Double decisions are refused (`ClaimAlreadyDecided`), but the decision has no append-only record. | `app/models.py:1825`; `app/services/insurance_claim_service.py:255`. | Check `DOM-STORE-001` / `FEAT-STOR-003` for whether the decision must be an event. A claim is an entity — do not collapse it into an event table. |
| PL-STORE-02 | P2 | **Class destruction relies on FK cascade for insurance claims** and their productivity-date rows; everything else in the Store is torn down explicitly. | `_destroy_class_scope_rows` `app/routes/admin.py:1158-1315`; cascade `app/models.py:1815`. | Add explicit teardown alongside PL-IDEN-01. |
| PL-STORE-03 | P2 | **`app/utils/deletion.py` is dead and cannot import.** No importers; imports `Entitlement` and `EntitlementConsumption`, which `models.py` records as deleted. | `app/utils/deletion.py:8-13`; `app/models.py:1341-1346`. | Delete. |
| ~~PL-STORE-04~~ | — | **Moved to pre-launch 2026-09-14 (owner decision).** The card is built on its own branch and integrated before launch, and is now tracked in the launch checklist in `PRODUCTION_READINESS_2026-09.md` §V. Keep `insurance/recommendation-card` as reference until the card lands. The original entry follows, struck. | | |
| ~~PL-STORE-04~~ | ~~P2~~ | *(Superseded by the row above; kept for the record.)* **Decide whether the policy form gets an Economic Engine recommendation card.** `recommend_insurance_terms` has no consumer: it is imported into the admin routes and called only by a test. The form shows only a footnote, and teachers see insurance ranges only on the Economic Engine page and in the rebalance preview's out-of-band notice. Local branch `insurance/recommendation-card` @ `84b677b7f` built the card, but that branch is otherwise superseded. Its tier-group picker, grouped marketplace and cancel-by-`policy_uuid` all landed on `main` independently, with the same four tests. | Form footnote `templates/admin_edit_insurance_policy.html:185`; import `app/routes/admin.py:126`; existing surfaces `:2321` (rebalance preview), `:7247` (Economic Engine page). The branch conflicts with `main` in 7 files and adds inline styles the `SPEC-DES-001` template gate rejects. | Either rebuild the card on `main` by consuming `recommend_insurance_terms` rather than the branch's route-local `_insurance_recommendations`, or drop the idea and delete the dead import. Do not merge the branch. Once decided, delete the branch; its three card tests are the only part worth keeping as reference. |

## 8. Obligations

| ID | Pri | Item | Evidence | Next step |
|---|---|---|---|---|
| PL-OBL-01 | P2 | **Dead rent-waiver code.** `RentWaiverView` and `get_active_rent_waivers_for_class` have no callers; `_count_rent_waiver_periods` is orphaned and reads attributes `DOM-OBL-001` v2.5 removed. | `app/services/obligations_service.py:748`, `:764`; `app/routes/admin.py:876`. | Delete all three. |

## 9. Interpretation

| ID | Pri | Item | Evidence | Next step |
|---|---|---|---|---|
| PL-ITR-01 | P2 | **Stale "partial payload" language.** The compute core is 17/17, but module and function docstrings, and the names `compute_partial_payload` / `compute_partial_observations`, still say partial. The package docstring cites `app/services/analytics` and `app/utils/analytics_engine.py`, both removed. | `app/services/interpretation/compute.py:16`, `:46`, `:85`, `:88`; `app/services/interpretation/__init__.py:1-8`. | Correct the docstrings. Rename together with its callers: `app/feats/complete_payroll_cycle.py`, `tests/test_complete_payroll_cycle.py` (which monkeypatches the name as a string) and `tests/test_interpretation_compute_q1a_q1b.py`. |

## 10. Operations and observability

| ID | Pri | Item | Evidence | Next step |
|---|---|---|---|---|
| PL-OPS-01 | P1 | **`DOM-OPS-001` event tables are not built.** None of the eight in §5 exists: `operational_events`, `audit_log`, `invariant_run_events`, `incident_events`, `incident_summary`, `alert_events`, `job_events`, `health_check_events`. Telemetry still goes to application logs. | `docs/DOMAIN/DOM-OPS-001_OPERATIONS_DOMAIN.md` §5; `app/services/operational_event_service.py:26-50`; `app/services/tlcp.py:86`. The sysadmin crash this causes is a **launch** item, tracked in the readiness launch checklist. | Build per §5, then retire the log-file reads in the sysadmin views. |
| PL-OPS-02 | P2 | **Sysadmin network-activity tab is a stub.** It re-displays the error rows with empty IP and stats fields. | `app/routes/system_admin.py:571-578`. | Build on PL-OPS-01's tables, or remove the tab. |
| PL-OPS-03 | P2 | **Thin sysadmin test coverage.** About 7 of 33 sysadmin routes are exercised; the log views and user-report update have none. The only dashboard test uses an expired session. | `tests/dom/operation/`, `tests/dom/support/`, `tests/dom/interpretation/test_sysadmin_issue_rewards.py`. | Add authenticated render tests for every GET route first — that alone would have caught the launch-checklist crash. |
| PL-OPS-04 | P2 | **Port the bug-hunter badge system design.** Design only, no implementation: `DOM-OPS-003_BADGE_SYSTEM.md`, `SPEC-OPS-001_BUG_HUNTER_BADGE_SYSTEM.md`, `SPEC-OPS-002_BUG_HUNTER_BADGE_USER_EXPERIENCE.md`, and nine award SVGs under `app/static/badges/`. Preserved 2026-09-14; before that its only copy was an unreferenced commit. | Annotated tag `archive/bug-hunter-badges-20260914` → `3cdb1294`, pushed to `origin`. `PRODUCTION_READINESS_2026-09.md` §VI. | Port the badge files only — never merge the commit, the rest of it predates `main`. Renumber both specs first: `SPEC-OPS-001` and `SPEC-OPS-002` are now taken on `main`. Implementation sits on PL-OPS-01's event tables. |

## 11. Support content

| ID | Pri | Item | Evidence | Next step |
|---|---|---|---|---|
| PL-SUP-01 | P2 | **Support-content registry must be rebuilt, not ported.** Its source (`support-text-extraction` @ `fe3e3e0d`) no longer exists locally or on `origin`. | `PRODUCTION_READINESS_2026-09.md` §VI "Support-content registry" describes the design. | Re-scope against the current templates, paired with PL-A11Y. |

## 12. Accessibility (`INV-CORE-000` §III.7)

Accessibility is a functional requirement, not polish. These are post-launch only by the explicit
"pass with follow-up risk" disposition in [`ACCESSIBILITY_REVIEW_2026-09-03.md`](ACCESSIBILITY_REVIEW_2026-09-03.md).

| ID | Pri | Item | Evidence | Next step |
|---|---|---|---|---|
| PL-A11Y-01 | P1 | **No rendered axe audit of any signed-in page.** The axe test is real now, but covers only the four static `github-pages/` files, and the accessibility gate does not run it. | `tests/test_axe_compliance.py:38-43`; `.github/workflows/accessibility-gate.yml` runs `tests/test_accessibility.py` only. | Extend axe to authenticated teacher and student routes, and run it in the gate. |
| PL-A11Y-02 | P1 | **No browser verification of focus order, contrast, zoom/reflow, reduced motion or error recovery.** Current checks are source-string assertions. | `tests/test_layout_accessibility_contract.py`. | Browser-level tests per feature page. |
| PL-A11Y-03 | P2 | **No interaction tests for pagination and dynamic-row controls.** | `tests/test_layout_accessibility_contract.py:173-186` (string checks only). | Playwright interaction tests. |

## 13. Migrations and schema

| ID | Pri | Item | Evidence | Next step |
|---|---|---|---|---|
| PL-MIG-01 | P2 | **The base migration materializes today's ORM.** `0001_bootstrap` builds the baseline from current metadata, so deleting a model retroactively changes the base schema and can break a fresh-database build at a later migration. Worked around case by case; tracked nowhere. | `migrations/versions/0001_bootstrap.py:93-97` (its own docstring), workarounds `:106-140`. | Design decision: freeze the baseline as an explicit schema snapshot, and record the rule alongside the migration SOPs. |

## 14. Documentation

| ID | Pri | Item | Evidence | Next step |
|---|---|---|---|---|
| PL-DOC-01 | P2 | **`DEVELOPMENT.md` is stale.** Names retired `codex/v2.0` as where work lands, cites a merge migration that does not exist, archived audit paths, a nonexistent `docs/SPECS/` path, and an archived reconciliation tracker. | `DEVELOPMENT.md:57-58`, `:66-69`, `:96`, `:101`. Same class: `SOP-DB-009` cites removed `LOG-ARC-050` (`:31`, `:55`) and the missing migration (`:38`); `SOP-DEP-023` §XII uses `../../SPECS/`. | Rewrite `DEVELOPMENT.md` against current state; fix the SOP references. |
| PL-DOC-02 | P2 | **The ops-doc restructuring gate cannot open.** It waits on `V2_ADMIN_ROUTE_REFACTOR.md` (now archive-only) and `MAP-CLASS-002` (informative, "not an active implementation plan"). | `DEVELOPMENT.md` "Operations Doc Boundaries"; `SOP-DEP-023` §XII. | Re-decide whether the restructuring is wanted; replace the gate either way. |
| PL-DOC-03 | P2 | **Docs platform roadmap.** Remaining: v1 archive triage (Phase 1), v2 rewrite of the user guides plus a sysadmin manual (Phase 2), `docs-site/` not built or deployed by any workflow (Phase 3A), role-aware in-app help (Phase 3B). | [`DOCS_PLATFORM_ROADMAP.md`](DOCS_PLATFORM_ROADMAP.md) owns the detail; [`USER_GUIDE_INVENTORY_2026-09.md`](USER_GUIDE_INVENTORY_2026-09.md). | Work from the roadmap; record closures here. |

## 15. Compatibility shims

| ID | Pri | Item | Evidence | Next step |
|---|---|---|---|---|
| PL-SHIM-01 | P2 | **`money_guard` always permits.** Kept "for call-site compatibility"; a guard that never refuses reads as protection. | `app/utils/money_guard.py:12`. | Remove it and its call sites, or give it a real rule from a governing doc. |
| PL-SHIM-02 | P2 | **Remaining compatibility wrappers.** | `app/feats/class_configuration/feat_class_005_economic_engine_evolution.py:18`, `:207`; `app/routes/admin.py:1130`; `app/utils/opaque_refs.py:51` (legacy tokens). | Remove once callers are on the canonical path. |

---

## Appendix — dropped during verification (2026-09-14)

Carried in earlier trackers, re-checked, and **not** added because they are already resolved or their
premise no longer exists. Recorded so they are not re-added from those sources.

| Former item | Source | Why dropped |
|---|---|---|
| Identity tests nest `initialize()` inside a test-owned `FEATContext` | Readiness §V | Remaining wrappers use `FEAT-TEST-SETUP`, which the nesting guard exempts (`app/feats/base.py:241-252`) |
| Dead FEAT-bypass branch in `economy_policy` | Readiness §V | Not present; `app/services/economy_policy.py` never existed |
| Dual `StoreItem` / `StoreProduct` catalog | Readiness §V | Consolidated by `b7c41e9a2f30` |
| Dead comment in `analytics_engine.py` | Readiness §V | File removed (`8b2c9a469`); the remaining stale reference is PL-ITR-01 |
| `update_user_report` dead or incorrect | Readiness §V | Live and guarded (`364657994`) |
| Announcement creation skips ownership check | Readiness §V | Verified via `_resolve_admin_class_context` → `verify_teacher_owns_class` (`app/routes/admin.py:452-461`) |
| Empty `content/` / ghost `app/content/` | Readiness §VI | Gone |
| Badge specs collide with `SPEC-OPS-001` | Readiness §VI | Specs no longer in tree; preservation is PL-OPS-04 |
| Internal scoping `join_code` → `class_id` | `DEVELOPMENT.md` | Done; residue is PL-LED-01 |
| Ledger rebuild to `class_id + seat_id + account_type` | `DEVELOPMENT.md` | Done (`ledger_balance_query_service.get_available_balance`) |
| FEAT-bypass default flip | Deleted plan (`fbc46d8b7`) | Enforcement is default; residue is PL-CI-05 |
| Axe test is a placeholder | Accessibility review | Now a real audit, public pages only — see PL-A11Y-01 |
