# SPEC-CLASS-001: Configuration Portability

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| SPEC-CLASS-001 | 1.1 | 2026-10-28 | 1.0 | Normative |

## I. Purpose

Temporary teacher-bound transfer of configuration values between separately authorized
class contexts. This is not restoration, class cloning or synchronization.

## II. Scope

One source per export and one destination per import. All groups default selected;
store, insurance and hall-pass entries can be selected individually. Export confirmation refuses a changed source inventory so file-local selection positions cannot silently refer to different entries.

## III. Authority Level

Incorporated by DOM-CLASS-001, DOM-POL-001, DOM-IDEN-003 and FEAT-CLASS-009/010/011.

## IV. Dependencies

FEAT-CORE-000; SPEC-TIME-001; SPEC-STORE-001; SPEC-ECON-001/003; SPEC-TEST-001/002.

## V. Artifact

UTF-8 `.cthconfig`, signed readable JSON using installed itsdangerous Serializer,
HMAC-SHA256, dedicated CONFIGURATION_EXPORT_KEY, separate export/confirmation salts.
A missing/blank key disables issuance and verification, never falls back to another
key. Rotation invalidates artifacts; no fallback keys. Format 1 only. Envelope binds
format, random 256-bit export reference, issued_at/expires_at and groups. Server UTC
expiry is exactly five days; current reference must match the authenticated principal.
No teacher ID, class ID, source policy/group/lineage IDs, audit fields or source
lifecycle metadata appear in the artifact. Group membership is structural within the
file. Dates are source-class calendar dates, interpreted in the destination timezone.

Maximum file size 1 MiB, 1,000 total catalog entries, nesting depth 20. Export enforces
the same limits as upload. Reject duplicate JSON keys, unknown fields, nonfinite or
ill-typed values and invalid nested structures. Decimal inputs use decimal strings.
No archives, dynamic dispatch, ORM serialization or historical format conversion.

## VI. Inventory

Current effective economic mode/weekly hours and banking fields; families with no configured capacity or interest rate are absent. Nullable banking terms retain their unset values, including the nullable overdraft-protection flag; current effective
payroll SETTING_FIELDS (excluding retired rounding_mode); current IN_USE rent settings
excluding satisfaction_benefits and source timestamps; current IN_USE hall-pass queue
limit and selected pass entries; selected IN_USE store definitions, rent-linked ones included,
excluding source identities, rent-product links and collective instance codes; selected IN_USE insurance
terms excluding succession/attribution/identity. No hidden, retired or pending version
picker. A current product's future sale date remains a portable calendar input.
No stock remainder, claim usage, balances, seat visibility or operational history.
Rent-product links stay in the origin (owner ruling 2026-10-28): an imported product is
not rent-linked until the teacher links it again using the destination Store. A product
that is not directly purchasable is imported HIDDEN with its terms unchanged, since an
unlinked product on sale must be directly purchasable (SPEC-STORE-001). Existing
destination rent-product relationships are preserved.

## VII. Schedules and preview

Per applicable singleton family: destination schedule, exported schedule, or teacher
entry. Payroll: pay_schedule_type/first_pay_date. Rent: frequency_type,
custom_frequency_value/unit, first_rent_due_date/due_day_of_month. Banking: interest
calculation type and accrual/compound/payout frequencies (validate the complete choice).
Absent destination schedules cannot be selected. Independent products have no inferred
destination counterpart: use exported calendar dates or teacher entry. Store date
inputs are activation, delisting and goal deadline; insurance cadence is a product term.
All other durations remain ordinary definition values, not invented activation dates.

Preview/confirmation displays actual calendar dates and times with the destination
timezone; date-only inputs stay date-only. Recurrences show their next occurrence when
defined. Show effective dates separately; never relative-only time. Dates remain editable
through normal settings. Payroll effective_date is computed by the receiving command
before incorporating the newly selected schedule; never an import override.

## VIII. Execution and retry

Preview binds file digest, destination, actor seat, schedule choices, relevant destination
state and random operation ID in a server-authenticated confirmation. Token expiry cannot
exceed export expiry. No database staging payload is needed.

Confirmation locks Identity export state, then the destination class, retaining locks
through commit/rollback. Refresh state after waiting. Independently recheck current
session/principal, seat/ownership, current reference and both expiries BEFORE receipt
lookup. Changed authority denies even a historically successful request. Changed
material preview state requires a new preview for an unaccepted operation. This includes
the receiving payroll policy/boundary and current rent assessment boundary; crossing
a boundary after preview must not silently change the reviewed timing.

Reserve (class_id, operation_id) with a database unique constraint before configuration
writes. Matching valid retries return the accepted result; changed fingerprint denies.
A new deliberate import gets a fresh operation ID. One FEAT composes domain commands
in one transaction, with receipt and audit. No independent commit, nested executor or
swallowed failure. Any failure leaves neither partial definitions nor accepted receipt.

Disabled destination features are skipped and shown, never enabled. Hall-pass settings
replace, not merge. Store products, policy UUIDs, group IDs and collective instance IDs
are newly generated. Insurance import has no successor link to destination policies.

Receipts contain operation ID, class, actor seat, fingerprint, minimal result and expiry;
no configuration/file. Expiry matches the export. Explicit logged cleanup may remove
expired receipts; token expiry remains authoritative regardless of receipt existence.
Class destruction cascades receipts. Audit history has its independent retention rules.

## IX. Acceptance

Test exact/changed/concurrent retries, rotation races, waiting-request expiry and revoked
authority, locks through commit, failure rollback, receipt cleanup, class teardown,
independent same-name insurance groups and predecessor coverage exclusion before renewal.
Verify every imported family uses the same domain semantics as manual submission;
existing payroll cycles/obligations/claims retain their terms. Targeted PostgreSQL tests
only. Migration rehearsal must preserve original insurance payloads and refusal on
ambiguous live succession. No deployment is authorized by this specification.

## X. Amendment

Increment version and effective date; do not relax the approved execution guarantees.
