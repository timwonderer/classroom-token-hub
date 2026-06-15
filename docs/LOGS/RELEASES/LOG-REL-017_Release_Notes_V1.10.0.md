# Release Notes - Version 1.10.0 — Version 1 Final Release

| Reference Number | Version | Effective Date | Supersedes  | Authority Level |
|------------------|---------|----------------|-------------|-----------------|
| LOG-REL-017      | 1.0     | 2026-06-14     | LOG-REL-016 | Informative     |

**Release Date**: June 14, 2026
**Focus**: Final Version 1 release. Bundles all work shipped since v1.9.0 (March 4, 2026) and formally closes out the Version 1 branch. No further v1 patches or features are planned.

---

## What This Release Represents

Version 1.10.0 is the closing chapter of Classroom Token Hub Version 1. Since its first stable release in November 2024, Version 1 grew from a small classroom-banking prototype into a full-featured educational-economy platform spanning automated payroll, rent systems with itemized privileges, tiered insurance, hall passes, a virtual store with collective goals, a real-time economy health dashboard, passkey authentication, structured Gunicorn logging, and a deterministic runtime invariant health-check system.

This release bundles all work that has been shipping continuously on `main` since v1.9.0. There are no breaking changes relative to v1.9.x deployments. The codebase is production-stable.

Active development now moves to **Version 2** — a full architectural rebuild with a ground-up join-code-centric schema, a new API, stronger privacy invariants, and significantly less PII stored.

---

## Highlights

- **Insurance Recurring Billing (Phases 2–4)** — Manual-pay billing banners, student pay-now route with idempotency guard, and bundle discounts applied correctly at purchase time.
- **DOB Privacy Remediation (Phase 1)** — Date-of-birth removed from usernames and logs; one-time `/migrate-username` flow; post-migration PII cleanup.
- **Runtime Invariant Health Checks** — `GET /health/invariants` continuously validates six ledger and economic invariants; `transfer_correlation_id` links transfer pairs.
- **V1 Rent Stabilization** — Centralized payment validation, atomic transaction boundary, pre-insert guard against race conditions, and anomaly logging.
- **Economy Policy Mode and Rebalancer** — `Tight` / `Default` / `Comfortable` profiles drive CWI-guided rebalance across rent, store, insurance, and payroll settings.
- **Tiered Insurance Setup** — Preset, advanced, and custom configuration modes with spec-compliant lock-in workflow and economy snapshot pricing.
- **V1 Sunset Transition Gate** — In-app transition page guiding existing users toward v2 preparation.
- **Dependency Maintenance** — Final dependabot sweep: OpenTelemetry 1.41.1, gunicorn 25.3.0, Werkzeug 3.1.7, cryptography 46.0.7, and related packages.

---

## Added

- **Insurance recurring billing — Phases 2–4** (PR #1172):
  - `bill_preview_days` teacher setting on policies (migration `f9a8b7c6d5e4`).
  - Student billing-status banners on `/student/insurance` (Paid / Upcoming / Pay Now).
  - Manual-pay route `POST /student/insurance/pay/<enrollment_id>` with 30-second idempotency guard and atomic DB writes.
  - Bundle discounts applied at purchase time; `frozen_premium` overwritten with discounted rate for correct future billing.
- **Student DOB Privacy Remediation (Phase 1)** (PR #1142):
  - `dob_sum` removed from username generation; new format is `{adj}{word}{4digits}{initials}`.
  - `seat_dob_sum` and `provided_dob_sum` stripped from failed-claim warning logs.
  - One-time `/migrate-username` flow for students with legacy DOB-derived usernames.
  - `username_migrated` boolean on `Student` (migration `b1c2d3e4f5a6`).
  - Privacy audit document: `docs/AUDITS/PRIVACY_AUDIT_DOB_HANDLING_2026-04-12.md`.
- **Runtime Invariant Health Check System (V2-INV-001)** (PR #1138, #1139):
  - `GET /health/invariants` — Returns `200` on pass, `500` with sanitized report on failure.
  - Six invariant categories: ledger↔BalanceCache consistency, idempotency key uniqueness, balance rules, transaction state validity, temporal integrity, money supply.
  - `transfer_correlation_id` (String 36, nullable, indexed) on `transaction`; all transfer call sites updated.
  - `scripts/reconcile_balance_cache.py` for one-time reconciliation of stale `BalanceCache` entries.
- **V1 Sunset Transition Gate** (PR #1201):
  - In-app transition page explaining v1 end-of-life timeline and next steps for users.
  - Consistent styling and back-link navigation.
- **Admin: Reverse misapplied rent late fees** — New `POST /admin/rent/reverse-cycle-penalties` route and Corrections tab on Rent Settings page.
- **Tiered insurance setup and guidance** (PR #1090–#1096): Simple, advanced, and custom modes; preset-mode state fixes; variable approval cap correction; economy snapshot pricing.
- **Sysadmin escalated issue "In Review" status** — New `DEV_IN_REVIEW` status for active investigation.

---

## Changed

- **V1 Store lifecycle stabilization** — Rejected delayed-use redemptions issue refunds as `PENDING` ledger entries; refunded purchases blocked from admin void to prevent double compensation.
- **Regular item overdraft transfer settlement** — Overdraft protection legs now enter ledger as `PENDING`, matching the full settlement-based balance flow.
- **Privacy policy accuracy updates** — Corrected DOB description, hashing description (Scrypt/PBKDF2), PIN length range, error-log retention (90 → 14 days), recovery description, and breach notification method.
- **OpenTelemetry tracing rollout** (PR #1122) — Full OTel tracing wired with lockstep package versions.
- **Economy policy scheduling refinement** — Policy application evaluates scheduling correctness before committing; CWI health thresholds are configurable per class.
- **Gunicorn structured JSON access logging** — Machine-readable JSON logs with configurable timezone; Grafana economy-health dashboard added.
- **Demo session routes removed** — Admin API for minting demo student sessions and the student demo-login route removed; v1 no longer exposes demo-session creation paths.
- **Template design system unification** — `bi-*` icons replaced with Material Symbols; `bg-opacity-*` replaced with `bg-*-subtle`; token-driven theming normalized across all shells.
- **Dependency updates** — OpenTelemetry 1.41.1, gunicorn 25.3.0, Werkzeug 3.1.7, cryptography 46.0.7, redis 7.4.0, requests 2.33.0, pytz, qrcode, Pygments 2.20.0.

---

## Fixed

- **Block deletion rent FK cleanup** — `/admin/students/delete-block` no longer fails with `ForeignKeyViolation` when `rent_items` rows reference the deleted block's `RentSettings`; dependent rows deleted in correct FK order.
- **Partial rent payment rate lock** — First partial installment no longer overwrites the class-wide locked rate; `rent_amount_snapshot` recorded per `RentPayment` row (migration `a8b9c0d1e2f3`).
- **Rent waivers honored** — `RentWaiver` records now consulted during coverage-period paid checks via `_has_active_rent_waiver`; waiver creation scoped to `join_code`.
- **Rent waiver UI class switching** — Waiver form reloads data for the newly selected class.
- **Rent full-payment mode** — Fixed regression blocking already-paid students from accessing rent-linked perks.
- **Rent cycle rate lock** — `_get_locked_rent_amount_for_join_code_cycle` now uses timestamp-based matching instead of a non-existent `transaction_id` column.
- **Docs: GitHub-style alert rendering** — `[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]` callouts now render as styled alert boxes.
- **Docs: Unordered list display** — Explicit `list-style-type` and `display: list-item` rules fix missing bullets in documentation pages.
- **Authenticated-route cache sysadmin endpoint correction** — Cached lookups now resolve against the correct system-admin route.
- **Invariant ledger totals scoped to class economy** — Money-supply invariant no longer inflates delta metrics with cross-class totals.
- **Insurance claim time-limit gate** — Deadline evaluated against filing timestamp, not wall-clock time; teacher override available per claim.
- **Collective goal progress reset on reactivation** — Reactivating a deactivated collective goal starts progress at zero.
- **Docs link check: exclude GitHub Actions expressions** — `lychee.toml` excludes `${{` patterns so Actions syntax in doc examples no longer fails CI link checks.
- **CI: Production SSH via Tailscale** — Deploy workflow routes SSH through the Tailscale overlay network.

---

## Security

- **Student DOB Privacy Remediation (Phase 1)** — DOB-derived component removed from all new usernames; existing DOB-based usernames migrated on next login; `dob_sum` nulled post-migration; detailed audit document added.
- **Demo session exposure removed** — Demo student session creation and login routes removed from v1 surface area.

---

## Upgrade Notes

This release is a standard rolling update from v1.9.x. No destructive schema changes relative to existing v1.9.x deployments.

1. Pull latest code:
   ```bash
   git pull origin main
   ```

2. Run pending migrations:
   ```bash
   flask db upgrade
   ```

3. Verify invariant health:
   ```bash
   curl http://your-domain/health/invariants
   ```

4. Confirm single migration head:
   ```bash
   flask db heads
   ```

---

## V1 End-of-Life Notice

With this release, **Version 1 is officially retired**. Existing v1 deployments will continue to operate — this is a stable, production-ready build — but no further patches, security backports, or features will be developed for the v1 branch.

Users running v1 in production should plan to evaluate v2 when it reaches release. Because v2 is a full architectural rebuild, no automatic data migration from v1 is planned. Classroom data export tooling will be evaluated as a v2 release-time priority.

The complete v1 development history is preserved in:
- [CHANGELOG.md](../../../CHANGELOG.md) — All changes across every v1 release
- [DEVELOPMENT.md](../../../DEVELOPMENT.md) — Development priorities and completed-feature archive
- [docs/LOGS/AUDITS/LOG-ARC-031_Project_History.md](../AUDITS/LOG-ARC-031_Project_History.md) — Project philosophy and evolution
- [docs/LOGS/AUDITS/LOG-ARC-039_Project_Timeline.md](../AUDITS/LOG-ARC-039_Project_Timeline.md) — Interactive timeline of all v1 eras

---

## V1 by the Numbers

| Metric | Value |
|--------|-------|
| First stable release | November 29, 2024 |
| Final release | June 14, 2026 |
| Major versions | 1.0 through 1.10 |
| Database migrations | 85+ |
| Test files | 110+ |
| Database models | 55+ |
| P0 incidents resolved | 3 (same-teacher data leak, duplicate auto-tapout payroll overpayment, rent wrong-period payment under bill preview) |
| Security audits | Multiple (multi-tenancy, class deletion, PII/DOB, passkey) |

---

*Version 1 of Classroom Token Hub is dedicated to all of the young pentesters who are relentless in testing the stability of the system and validating the invariants embedded in all the features.*
