# District and privacy page implementation audit

Date: 2026-09-15

Source reviewed: `main` at `1cc526049fb7c3217825360ad898fd47978e2d84`.
Documentation branch: `codex/public-privacy-docs`.

## Outcome and scope

Revised every content section of `github-pages/district.html` and
`github-pages/privacy.html`, including contents labels, review date, and footer
claims. Existing section IDs, page layout, and shared styles are preserved.
The pages now distinguish implemented behavior, intended requirements, and
unverified deployment practices. They do not certify v2 launch readiness.

Review correction: the initial audit conflated disclosure accuracy, normative
conflicts, security findings, and operational unknowns. The classifications below
supersede the initial blanket description of these items as unresolved privacy
requirements. In particular, the teacher-recovery quorum conclusion is withdrawn.

This is a public-documentation audit, not a backend remediation or production
security assessment. Runtime code, canonical specifications, and public HTML were
inspected; no production database, secrets, hosting settings, or external account
was inspected. Other public pages, including `terms.html`, were not substantively
rewritten. Their claims need a separate audit before describing the entire public
site as reconciled. The accessibility test also covers those pages, but does not
validate their factual content.

## Governing authority

- `INV-CORE-000` §§III.1–7: isolation, minimal PII, monetary history, principal
  authority, hard deletion, membership, and accessible supported use.
- `INV-ARC-004`: single active-class scope; narrowly defined hall-pass exception.
- `INV-ARC-005`, `INV-ARC-018`, and `INV-ARC-019`: execution-layer PII,
  permitted stored fields, and identity/credential ownership.
- `INV-ARC-012`: hard deletion; `INV-ARC-020`: accessible public wording and UI.
- `DOM-IDEN-001/002/003/005`: account, participation, authentication, and lifecycle.
- `FEAT-IDEN-001/002/004/007/103`: claim, credentials, student recovery,
  teacher destruction, and teacher recovery.
- `DOM-SUP-001`: support submissions and diagnostic snapshots.
- `SPEC-SEC-001`: cryptographic primitives and recovery/lookup requirements.
- `SPEC-OPS-004`: current operator console description, subject to the unresolved
  scope-definition question below; it does not override INV requirements.
- `SOP-TEST-002`: targeted structural and rendered accessibility checks.

Disagreements were not resolved by changing authority documents or adding
compatibility behavior. A lower-level description is not authorization to weaken
an invariant. Implementation changes at the disputed boundaries are stopped for
review; this documentation change only discloses observed behavior and removes
unsupported promises.

## Claim-by-claim reconciliation

The first column summarizes the old wording or its implication; it is not a list
of verbatim quotations. These are public-copy dispositions, not defect verdicts.

| Original claim or omission | Evidence in current source | Public-page disposition |
|---|---|---|
| Teacher email/password with TOTP two-factor login | `app/routes/admin.py:login`, `signup`, passkey endpoints; `app/forms.py:AdminLoginForm` | Username + time-based one-time password (TOTP), or enrolled passkey; avoid calling username/TOTP two-factor authentication. |
| Teachers provide only display/class labels | `admin.signup`, `AdminClassSetupForm` | Include username, two-part display name, time zone, optional section, authenticator and optional passkey metadata. |
| Student first name + last initial | `student.claim_account`, `StudentClaimAccountForm`, `identity_feat.resolve_seat_claim` | First and last fields as rostered, full or partial; distinguish code comes from the teacher. |
| PIN signs students in | `student.login`, `FEAT-IDEN-002` credential matrix | Username/passphrase sign-in; PIN for attendance, transfers, and hall passes; passphrase for listed expense/entitlement actions. |
| bcrypt with application pepper | `app/hash_utils.py:PASSWORD_KDF`, `hash_password`; `activate_student_credentials` | Salted scrypt; application lookup secret is not a password input. |
| Per-record-salted claiming HMAC | `hash_username_lookup`, `classroom_setup._set_claim_hashes` | Keyed HMAC-SHA256 without unsupported per-record-salt or domain-separation claims. |
| Claiming information erased after setup | `classroom_setup.create_student_user_for_seat`, `identity_feat.activate_student_credentials`, `bind_authenticated_student_to_class` | Disclose retained roster matching hashes; separately flag the incompatible claim-lifecycle and verification requirements. |
| No identity across classes | `User`, `Seat`, `student.add_class`, `bind_authenticated_student_to_class` | One authenticated account may join multiple classes; classroom activity remains separate. |
| Names never sent to students | Identity profiles, student display views, `main.verify_hall_pass` | Own-name display plus teacher roster and explicit verification disclosure. |
| Only student and teacher can ever see student information | `main.verify_hall_pass`; operator support views | Explain shared-link disclosure and support review exceptions. |
| No application-level system administration | `system_admin.dashboard`, `combined_logs`, `support_tickets`, `_issue_to_view` | Describe actual console, content and intended authority limits, without certifying isolation. |
| No export tools | `admin.export_class_roster`, `export_students` | Disclose teacher exports and school responsibility for downloaded copies. |
| Infrastructure cannot decrypt names | `PIIEncryptedType.process_result_value`, `ENCRYPTION_KEY` runtime dependency | Data plus key permits decryption; key custody is an operational control. |
| All potentially identifying/sensitive information encrypted | `IdentityProfile`, `Issue`, `Transaction`, `User.reset_code`, session interface | Name specific encrypted fields; disclose ordinary text, readable recovery code and signed-cookie limits. |
| Activity records are non-personally-identifiable | Seat-linked ledger, attendance, hall-pass and support models | Distinguish direct identifiers, pseudonymous student-related records, and anonymous data; seat linkage alone does not make an amount a direct identifier. |
| No behavioral or disciplinary data | Bonuses/fines, attendance, destinations, notes and support content | Do not promise content cannot describe behavior; discourage unnecessary sensitive free text. |
| All data removed when term ends or after 180 days | `app/scheduled_tasks.py`; repository search for stale-class cleanup | No established scheduled class purge; explicit deletion needed, no fixed retention promise. |
| Deleting any class deletes the student's entire account | Shared `User`/`Seat`; student removal and class destruction paths | Distinguish class membership removal from other surviving memberships. |
| Deletion instantly removes every copy | `_destroy_class_scope_rows`, account deletion; no verified infrastructure evidence | Describe hard-deletion workflows and separate backup/log/export retention uncertainty. |
| Student recovery needs join code + code | `app/routes/recovery.py:account_lookup`, `identity_feat.validate_recovery_code` | Code only, ten-minute expiry, new credential setup; shared-account effect disclosed. |
| Teacher recovery omitted | `admin.recover`, `reset_credentials`, `confirm_reset`, student verification routes | One selected student confirmation per class_id under the teacher user_id, matching DOM-IDEN-003 §IX; five-day window. Stale FEAT wording is a separate documentation conflict. |
| No identifiable information in logs | `issue_helpers.create_context_snapshot`, `Issue.context_snapshot`, `_issue_to_view`, `tlcp.persist_request_trace` | Disclose URLs, IP/browser details, activity snapshots and pseudonymous references; assess individual fields against policy rather than declaring every snapshot field PII. |
| No third-party processing or tracking of any kind | Public HTML font/CDN links, `main._marketing_site_redirect`, `turnstile.verify_turnstile_token` | List GitHub Pages, Google Fonts, jsDelivr and conditional Turnstile; distinguish ads from technical provider requests. |
| No analytics/aggregation of any kind | Interpretation/class economic views; operational monitoring | Disclose class summaries, support diagnostics and monitoring; no cross-class educational aggregation guarantee. |
| SSO unsupported by default; forks described as open-source | Current auth routes; repository license | No implemented district SSO/SIS integration; source available under PolyForm Noncommercial terms, no OSI/open-source implication. |
| FERPA/COPPA/state-law assurances | Source is insufficient to establish institutional arrangements or live controls | Replace with bounded institutional review guidance and primary-source links. |
| WCAG AA only wherever practical | `INV-ARC-020`, `SOP-TEST-002` | State project requirement, scope of checks, and no whole-product certification. |
| Secure cookies/HTTPS always, unspecified idle timeout | `app.__init__`, `auth.py`, `session_lifetime.py` | Secure flag conditional on production; student absolute vs teacher idle timeout; TLS configuration requires live verification. |
| No contact details processed at all | Account forms versus published mailto contacts | No account contact fields; separately explain sender/message data when emailing support. |

## Classification rules and evidence limits

Each observation gets a classification independently of its severity. Categories
may be linked, but none automatically implies the next:

| Category | Meaning and required evidence | Appropriate action |
|---|---|---|
| Observed runtime mismatch | Source shows different behavior from a named statement. Source inspection is not an executed reproduction. | Correct the descriptive statement; separately determine applicable authority. |
| Normative conflict/ambiguity | Exact authority texts disagree, or the applicability of a rule to a representation/boundary is unresolved. | Resolve the documentation hierarchy or boundary definition before implementation. |
| Privacy disclosure correction | Public wording omitted or overstated a data practice. | Describe the practice accurately, without inventing a defect verdict. |
| Security defect | A specific violated security control is established; exploitation and impact require their own evidence. A suspected path remains a candidate. | Targeted security verification/remediation under the owning authority. |
| Operational unknown | Deployment evidence was not inspected. | Inspect the actual service configuration; do not infer PASS or FAIL from absence of evidence. |

No production security defect or exploit was demonstrated in this audit. Some
source-level control mismatches are established below; those are not equivalent
to a demonstrated account takeover or a completed security assessment.

### Data terminology used throughout

- **Direct identifiers:** names and other values that directly identify a person.
  Field encryption changes their stored representation, not their identity purpose.
- **Pseudonymous student-related records:** an amount, timestamp, or attendance
  event associated with an opaque participant reference, with identity mapping
  available separately inside the application. Not anonymous, but not therefore
  a direct identifier in every field.
- **Anonymous data:** information that cannot reasonably be linked back to a person,
  including through combination with other available information. No claim of anonymization is established for seat-linked rows.
- **Technical identifiers and free text:** IP addresses, URLs, browser details,
  and submitted text require field-specific and contextual assessment. Their
  presence does not prove that every snapshot contains a student's name.

These are descriptive engineering distinctions, not a legal classification of
all records. Do not infer permission to publish pseudonymous records merely from
the absence of names.

## Reclassified findings

### 1. Claim retention and verification representation

**Original observed mismatch / disclosure correction:** credential activation
retained roster-name hashes despite the claim-completion deletion contract.
Hall-pass verification and additive roster import also reused those hashes.

**Disposition: remedied in prelaunch branch (user decision, 2026-09-15).** Successful claim clears both
name hashes, the roster fingerprint, and the distinguishing code. Recovery uses
the recovery-code flow, not a second claim. Additive imports create a new student
for every accepted row; existing names are never a matching/deduplication source.
Only duplicate names within the submitted batch require teacher resolution.
Teacher and student name edits write IdentityProfile only.

Hall-pass verification resolves join_code to class_id, validates the external
capability for that class, and compares names in class-scoped IdentityProfiles.
This is **not an exception to INV-ARC-019**: external verification of a same-day
entry is not economic actor resolution. Disclosure remains scoped to supplied-name
presence and same-day hall-pass metadata; no roster or historical disclosure.

Implementation is isolated on `codex/claim-identity-remediation`. A data migration
clears retained material on already-bound student seats in existing development
or test databases. This is prelaunch implementation work; no live-production
remediation is involved.

**Validation:** 44 targeted tests passed across claim lifecycle, hall-pass
verification, PII deletion, and student recovery. A final run passed 9 tests
covering the migration, repeated same-name imports, profile-only name edits,
same-day filtering, foreign-capability rejection, and rendered form accessibility.
The migration test uses an isolated database fixture: running upgrade twice and
downgrade retains the cleanup while preserving unclaimed and teacher rows.
Compilation and `git diff --check` also passed. No full suite was run.
Evidence: `pytest_result/20260916_pytest_test_claim_lifecycle_summary.md` and
`pytest_result/20260916_pytest_test_claim_artifact_migration_summary.md`.

### 2. Roster notes and teacher-authorized support disclosure

**Disposition (2026-09-15): notes retained and governed; support disclosure and lifecycle remedied on the prelaunch branch.**
`IdentityProfile.notes` is encrypted teacher-entered, class-scoped contextual
information about a seat. It is free text. CTH does not inspect or classify its
contents, and makes no claim about what it contains. The permitted-field inventory
now expressly governs this existing field. It is not attached to support snapshots.

Preserve the correlation pack, route information, IP address, and browser details.
Require independent, unchecked teacher permissions to disclose balances, the
reported transaction, recent transactions, the student's report, and the class
name. Grants apply to one ticket's saved context, not live classroom authority.
Server-side projections withhold unselected and unknown data from all operator
surfaces. The original immutable student snapshot remains available to its teacher.
Direct teacher submissions share the text the teacher submits; they no longer
silently embed the class name and canonical class ID in that text. The existing
correlation builder returned data without persisting it; submission now attaches
that pack in the same transaction for both student and teacher tickets.

**Lifecycle clarification:** captured values are frozen at submission and never
refreshed during escalation or operator reads. All tickets, including teacher-submitted tickets, now reference their originating seat using its canonical
public ID with database cascading deletion. Removing the seat/account removes
the support issue and its pack/history/resolution rows; immutability does not
exempt the snapshot from deletion. All tickets are seat-scoped and
therefore class-scoped, including a teacher reporting a problem about themselves.
The account-level scope selector has been removed; submission topic cannot remove
or change canonical class scope.

**Validation:** 25 targeted tests passed for disclosure, rendered consent controls,
correlation persistence, seat/account deletion, and migration upgrade/downgrade.
Three final checks passed for the teacher form and frozen class metadata after a
class rename. Earlier targeted support/recovery-context tests also passed. The PII
storage allowlist, compilation, and `git diff --check` passed. No full suite was run.
Evidence: `pytest_result/20260916_pytest_test_support_permissions_summary_6.md`
and `pytest_result/20260916_pytest_test_support_permissions_summary_7.md`.
The originating-seat migration validates existing references; it does not guess
identity, silently re-scope tickets, or delete rows to make constraints pass.

This separates technical diagnostics, pseudonymous economic records, and
unclassified free text. It does not classify all support data as direct PII or
assert that diagnostic observation grants economic mutation authority.

### 3. Student recovery: separate representation, context, and consumption

- **Intentional representation / retained:** `User.reset_code` stores a readable
  eight-character code. DOM-IDEN-002 §IX explicitly permits plaintext for this
  ten-minute teacher-to-student handoff and permits teacher redisplay. This
  satisfies SPEC-SEC-001 §V.4's explicit recoverability exception. The earlier
  representation question is withdrawn; raw storage alone is not a defect.
- **Observed scope mismatch / remedied:** teacher issuance resolves the selected
  student Seat to its bound User, where the code is stored. Student redemption
  and credential replacement now resolve only that User, with no Seat, class,
  or IdentityProfile lookup. Removed first-seat selection and recovery writes to
  `claimed_at`/claim artifacts. Recovery clears stale initial-claim session state;
  setup rejects mixed seat/user references. Authority: INV-ARC-019 §VI and
  DOM-IDEN-002 §IX's explicit prohibition of additional recovery lookup.
  FEAT-IDEN-004 and FEAT-IDEN-002 now distinguish these paths.
- **Consumption/session lifecycle / remedied under the owner's revised decision:**
  accepting the recovery code consumes it immediately and atomically creates a
  unique session capability. The User row holds its nonce verifier and original
  ten-minute deadline. Every setup request checks that server record; possession
  of a User reference or a signed session cookie alone does not authorize setup.
  A new session cannot reuse the consumed code. Lost/expired recovery requires a
  newly issued teacher code. Both teacher issuance routes revoke any outstanding
  recovery-session authority.
- **Credential transaction / remedied:** accepting a code preserves all existing
  credentials. Completion locks and reloads the User, rechecks nonce/expiry,
  replaces all credential fields, rotates the authentication-session nonce, and
  clears the recovery nonce verifier/deadline in one transaction. Concurrent
  completion has one winner. A username conflict rolls back replacement without
  discarding the authorized session. Recovery never reads or mutates participation.
- **Authority reconciliation:** DOM-IDEN-002 §IX, FEAT-IDEN-002/003/004, and
  SPEC-SEC-001/SOP-SEC-001 now describe the same two-stage lifecycle. This explicitly
  supersedes both the old validation-time credential clearing and the prior
  completion-time code consumption. Readable teacher handoff codes remain an
  intentional permitted representation; server nonce verifiers are separate.

**Verification:** 34 targeted tests passed across student recovery and claim
lifecycle, including separate PostgreSQL connections racing code acceptance and
credential completion (one winner each), cross-session code rejection, expiry,
reissuance, duplicate-code rejection, username collision rollback, and no
participation SQL during the end-to-end flow. The additive migration is
`f4d4e5f6a7b8`. Follow-up checks passed for server-side revocation on both
setup pages, injected credential-transaction rollback, migration upgrade/downgrade
preserving an existing User, and PII storage validation (17 checks). A separate
7-test issuance rerun passed after correcting the teacher-edit path to compose
the shared Identity domain command instead of nesting FEAT execution. Compilation
and `git diff --check` on the recovery changes passed. An unrelated concurrent
edit to `github-pages/district.html` was left untouched. This is scoped local evidence, not an assertion that every recovery
control or production infrastructure has been assessed. No full suite or
production execution.

### 4. Teacher recovery: initial conclusion withdrawn

**Exact higher-level authority:** `DOM-IDEN-003` §IX, core invariant 4, says:

> All classes must be represented. One student per active class period must participate. Partial coverage is rejected.

Its recovery flow says:

> One pair is required per active class.

The domain schema declares one pending request per user and one code row per
selected student seat. The user's clarified canonical decision is one selected
student confirmation per **class_id** under the teacher's **user_id**. Class/period
labels do not define scope.

**Prior conflicting FEAT wording (corrected in the reconciliation below):** `FEAT-IDEN-103` §IV.1 says:

> Teacher recovery requires verification from students. All students must provide recovery codes.

It attributes this to `DOM-IDEN-003 §IV`, but §IV is the dependencies section and
does not contain that rule. FEAT §IV.6 also requires separate requests per class,
while §IV.3 permits only one active request per teacher. The stale FEAT cannot
supersede its governing domain.

**Verdict: normative document conflict, not a runtime quorum defect.**
`admin.recover` resolves the owned class set, rejects missing/extra/duplicate
class submissions, and selects one student seat per class; the recovery service
creates a user-owned request with those selected seat/class pairs. That selection
pattern agrees with the domain and the user's decision. The initial statement
that it failed a stronger all-students quorum was wrong. This finding makes no
claim that every other stage of teacher recovery has passed end-to-end testing.
No change to the quorum or runtime is authorized by this audit correction.

**Disposition: remedy the specification.** FEAT-IDEN-103 now requires one
User-owned request and exact coverage of existing teacher-owned class IDs, with
one selected student Seat per class. It no longer requires all roster students
or a separate request for each class. FEAT-IDEN-104/105 participant references
now use those selected seat/class rows, not a nonexistent request-level class or
whole-roster quorum. INV-CORE-000 §III.6 prohibits interpreting "active" as an
extra class lifecycle state. No runtime or public-page edits are part of this
correction; no new runtime tests were necessary for these documentation changes.

**Separate review identified at the quorum checkpoint:** the downstream FEATs also contained older code
format/hashing, consumed-state, and credential-completion language. This quorum
reconciliation does not certify those other contracts or their runtime. They
must be checked against DOM-IDEN-003 §IX and incorporated SPEC-SEC-001 before any
implementation changes; do not use the stale FEAT text to infer another quorum
or a demonstrated security defect.


### 5. Deletion: four independent verdicts

| Boundary | Evidence | Verdict |
|---|---|---|
| Authoritative application class data | Hard-delete commands and membership/orphan handling exist. Prior tests were inspected; no deletion was executed in this audit. | Implemented paths observed; complete runtime deletion NOT_EVALUATED here. Backup uncertainty is not evidence these paths fail. |
| Ancillary application artifacts | Regression tests confirmed request traces survived both class and seat deletion. Seat and class FKs now cascade; class ownership is required; the trace writer rejects deleted or mismatched context. | Confirmed application deletion defect, remedied for `ActorRequestTrace`; this is not a claim about every ancillary artifact. |
| Automatic stale-class purge | `INV-CORE-000` §III.5 requires purge; no corresponding job or 180-day mechanism was located in the inspected application. | Observed implementation-evidence gap; remove the public 180-day guarantee. No conclusion about an uninspected external scheduler. |
| Infrastructure backups and external logs | No live retention configuration inspected. | Operational UNKNOWN, separate from application hard deletion. |

**Request-trace remediation:** authority is INV-CORE-000 §III.5, INV-ARC-012,
Identity seat/User lifetime, and DOM-SUP-001's deletion closure. The existing
class/account destruction paths inherit the database cascades; they need no
separate ad hoc trace sweep. Source traces remain useful during their owning
seat/class lifetime, subject to existing count/TTL pruning. Frozen ticket packs
remain governed by their own seat-scoped deletion cascade.

Migration `a5e5f6a7b8c9` removes traces whose seat or class is already gone, rather
than retaining detached records. It rejects mismatched references to live
seat/class owners for explicit reconciliation; it never guesses a new owner.
The request writer checks that the original seat/class/role still exists before
capturing a trace. Foreign keys prevent a late insert from retaining a deleted
owner if deletion races the writer.

**Verification:** the two original class/seat deletion regressions failed before
the fix. After the fix, 12 focused checks passed for class/seat deletion, sibling
isolation, valid trace capture, stale/wrong-class rejection, and canonical actor
resolution. Four further checks passed for User-to-seat-to-trace deletion, database
rejection of late inserts, migration cleanup/cascades/downgrade, and rejection of
mismatched live owners. Compilation and scoped `git diff --check` passed.
This is local application evidence; no production system or infrastructure backup
retention was examined. Automatic stale-class purge remains a separate open item.

**Teacher exports:** `export_class_roster` and `export_students` provide downloads.
This corrects the old “no export tools” implication. A downloaded CSV is a
school-controlled copy outside CTH's application deletion boundary. This audit
found no evidence that CTH retains the downloaded copy; do not count it as CTH
retention. The public pages explain the school's handling responsibility.

### 6. Operator observation versus application authority

**Exact invariant:** `INV-CORE-000` §III.4 says:

> System administrator must not be able to access or alter any `class_id` scoped instances.

This literally includes access, not only mutation. However, whether a particular
Support-owned diagnostic representation is access to a class-scoped domain
instance must still be established; its subject matter alone does not answer that.

**Exact lower-level statement:** `SPEC-OPS-004` §VI.3 says:

> The console reads across tenants by design — it is the one surface exempt from class scoping

The same spec §VII forbids mutation of classroom domain truth. `DOM-SUP-001` §VI
explicitly defines immutable support snapshots and operator review fields; its
resolution-action rules say a cross-domain reference does not transfer Ledger
ownership. Those are relevant boundaries, not permission to silently override INV.

| Plane | Observed or stated capability | Audit conclusion |
|---|---|---|
| Classroom operation | Teacher/student class-scoped workflows | Distinct from operator support review. |
| Diagnostic observation | Console reads reports, snapshots, and operational records | Observed; disclose what the operator receives. Classroom facts in a snapshot alone do not prove domain authority. |
| Live domain-record read access | Would require tracing an operator request to the authoritative record and its authorization | NOT_ESTABLISHED by the snapshot finding. |
| Economic mutation authority | SPEC-OPS-004 prohibits it; Support action records declare outcomes rather than own Ledger effects | No unauthorized economic mutation demonstrated by this audit. |

**Verdict: normative boundary ambiguity and potentially conflicting scope
language; not a confirmed cross-class security defect.** Clarify the lawful
observational plane and inspect individual payload/read paths against it. Retain
the literal INV wording in review; do not reduce it to a mutation-only rule, and
do not infer a security violation solely from the existence of support snapshots.

### 7. Lookup construction

**Observed source-level contract mismatch:** `SPEC-SEC-001` §V.2, incorporated by
`INV-ARC-018/019`, requires canonical normalization and field/domain separation.
`hash_username_lookup` has no separation label and receives caller-normalized
values. This is a concrete control mismatch for focused security verification;
no resulting collision, identity disclosure, or exploit was demonstrated here.

**Disclosure correction:** remove the old per-record-salt assertion.

**Subsequent disposition: remedied by pre-launch replacement.** The user confirmed
there is no existing data to preserve. Username lookup, salted username representation,
claim first/last-name matching, and roster fingerprints now use distinct purpose
labels and structured HMAC input. Claim digests include canonical class_id.
Normalization is centralized (NFKC and edge trimming; names lowercase, usernames
case-sensitive), including import duplicate checks and class-scoped in-memory
hall-pass comparison. Writers/readers/fixtures changed together; no migration,
old-hash fallback or compatibility bridge was added. Display profiles remain
unchanged. SPEC-SEC-001 §V.2 records the exact encoding under INV-ARC-018/019.
Teacher-recovery code/resume-capability representation remains the separate
finding #4 follow-up; this lookup change does not certify those contracts.

### 8. Authentication and cookies

**Disclosure corrections, not automatic defects:** teacher sign-in uses username
plus a **time-based one-time password (TOTP)**, or an enrolled passkey. In the
inspected TOTP route the username identifies the account; no separate password
factor is verified. Thus “email/password plus TOTP 2FA” was false, while the
mechanism remains TOTP. This audit does not infer the factor properties of all
passkey authenticators or all deployments.

Session cookies use a `SecureCookieSessionInterface` subclass: signed, not
encrypted. Display/setup values may reside in them. That is an observed storage
property requiring accurate disclosure, not by itself a demonstrated compromise.
Assess particular cookie contents against applicable storage rules separately.

### 9. External services and infrastructure

**Disclosure correction:** source identifies external font/CDN requests and
conditional Turnstile integration. These are not synonymous with advertising
tracking. **Operational UNKNOWN:** provider-side or deployment-injected analytics,
TLS, key custody, backup retention, external-log sanitization, and the live provider
inventory were not inspected. Unknown does not mean absent, insecure, or defective.

## Legal source checks

The public district page links directly to:

- [U.S. Department of Education: Responsibilities of Third-Party Service Providers under FERPA](https://studentprivacy.ed.gov/resources/responsibilities-third-party-service-providers-under-ferpa).
- [FTC: Complying with COPPA — Frequently Asked Questions](https://www.ftc.gov/business-guidance/resources/complying-coppa-frequently-asked-questions).

Reviewed through web search on 2026-09-15. Used for bounded review guidance only;
no legal conclusion about this service's compliance was made.

## Validation

Prior evidence inspected first: `pytest_result/20260914_pytest_specific_summary.md`
and its results CSV reported a passing published-page axe check at `2cfdd8452`,
but the combined run had three unrelated failures. Historical results do not
certify the revised pages.

Initial revision targeted checks (before the classification correction):

- `ACCESSIBILITY_TEMPLATE_PATHS` restricted to these two HTML files, running
  `venv/bin/pytest -q tests/test_accessibility.py tests/test_axe_compliance.py`:
  **4 passed, 1 skipped**; browser execution unavailable in sandbox.
- Retried `venv/bin/pytest -q -rs tests/test_axe_compliance.py` with local-browser
  access: **2 passed**, including rendered axe WCAG 2 A/AA across all four
  currently published HTML pages.
- Desktop/mobile inspection reuses this repository's existing Python Playwright
  harness. The optional CLI wrapper could not fetch its npm package because DNS
  was unavailable; no package or production configuration was changed.
- Visual artifacts and final desktop/mobile checks: see
  `output/playwright/public-privacy-audit-20260915/results.json` in the isolated
  worktree. These are local review artifacts, not production observations.
- Desktop/mobile results: both pages passed at 1440×1000 and 390×844, with zero WCAG 2 A/AA and 2.1 AA axe violations, no horizontal overflow or page-script errors, all 26 contents links clickable at both sizes, and visible initial keyboard focus. Relative file and fragment links resolved. Full-page screenshots were inspected.
- Tested HTML was byte-compared with the isolated worktree before restoring the original checkout; no page content changed during transfer.
- `git diff --check`: passed.

No full test suite was run. No new implementation-mirroring tests were added.
No backend code, deployment configuration, or authoritative specification changed.

### Classification-review validation

- Re-read DOM-IDEN-003 §IX and FEAT-IDEN-103 in full, the exact INV-CORE-000
  §III.4 wording, SPEC-OPS-004 §§VI–VII, DOM-SUP-001 snapshot/action rules,
  and the relevant runtime selection and payload code.
- Re-ran `tests/test_accessibility.py` restricted to the two revised pages, plus
  `tests/test_axe_compliance.py`: **5 passed in 5.14s**. The existing suite rendered
  all four published pages. Artifact: `pytest_result/20260915_pytest_test_accessibility_summary_1.md`.
- Used an in-memory test configuration for application import; selected tests
  are static/public-page checks, with no database fixtures or production access.
  An initial placeholder configuration was rejected by the test-name guard
  before collection; no database was contacted and no guard was disabled.
- All 37 local links and fragment targets resolved on the revised pages.
- `git diff --check`: passed. Previous screenshots remain evidence for the
  initial revision only; no new desktop/mobile screenshot claim is made here.
- Runtime code and canonical specifications remain unchanged. The stale
  teacher-recovery FEAT is identified for reconciliation, not silently amended.

### Public-copy scope correction

At the user's direction, removed internal-review narration, prior-copy comparisons,
release/test/certification commentary, and discussions of unfinished controls from
both public pages. No replacement claim promises automatic inactivity purge,
post-claim erasure, complete deletion closure, recovery-code protection, or
verified infrastructure retention. Add such claims only after the corresponding
behavior is corrected and verified. The findings and their classifications above
remain internal evidence; omitting a public claim does not resolve a finding.
Current collection and access disclosures (including support diagnostics, external
providers, cookies, and school-controlled exports) remain factual public content.
Earlier screenshots reflect previous copy, not this revision.

Validation for this public-copy correction: targeted structural checks returned
4 passed and 1 browser skip in sandbox; local Chromium retry of
`tests/test_axe_compliance.py` returned 2 passed in 5.81s. All 37 relative links
and fragment targets resolved; `git diff --check` passed. Results are recorded
in `pytest_result/20260916_pytest_test_accessibility_summary.md` and
`pytest_result/20260916_pytest_test_axe_compliance_summary.md` (UTC artifact date).

### Release blocker: principal references in classroom records

Owner decision: authentication principal references are permitted only on Seat
bindings, class ownership, passkey credentials, and authentication recovery requests.
This is a runtime/schema mismatch under INV-ARC-019, not an infrastructure finding.

Removed from the shipping model and migration head:

| Record | Removed reference | Canonical replacement |
| --- | --- | --- |
| Ledger transaction | `user_id` | Existing class, target/actor Seat anchors |
| Attendance session | `target_user_id` | Existing class and target Seat |
| Payroll event | `target_user_id` | Existing class and target/actor Seats |
| Store product | `user_id` | Existing class and `created_by_seat_id` |
| Announcement | `user_id` | Class-scoped `created_by_seat_id` |
| Policy transition | `created_by` User FK | Class-scoped `created_by_seat_id` |
| Support issue | `sysadmin_id` | External reviewer role and review metadata; no principal/participant binding |
| Audit event | `teacher_id` User alias | Existing class/Seat metadata; signed inputs unchanged |

Writers, selectors, fixture interfaces, Ledger plans, and bulk-command fingerprints
now follow these anchors. No ignored compatibility User arguments remain on the
Ledger or Store publishing interfaces. Operational event logging uses a scoped Seat,
and TLCP actor context carries only its existing public actor reference.

The optional Seat→User binding now uses RESTRICT, and the User ORM relationship
no longer cascades Seat destruction. Identity must explicitly detach or destroy
Seats before deleting a principal. Orphan cleanup removes authentication-owned
artifacts only; it neither deletes attendance nor rewrites surviving Ledger rows.
Class destruction uses one database class cascade for Seats and policy lineage.

Migration `c7a7b8c9d0e1` maps old authors only when the exact teacher Seat can be
established within the stored class. Invalid mappings fail closed. It removes all
eight references and rebuilds the Ledger immutability guard without weakening any
other protected field. Two historical migrations were made tolerant of this
repository's current-metadata bootstrap; existing upgrade behavior remains intact.

Fingerprint version 3 removes User material from bulk effect plans. Accepted digests
are never rewritten. Existing single-command and verified internal-transfer replay
remain usable. An old bulk-effect reservation requiring the removed principal
material blocks migration until an explicit pre-launch data-disposition decision;
no database reset or history deletion has been performed. Downgrade cannot recreate
removed principal bindings and is deliberately unsupported.

Validation includes the physical PostgreSQL schema allowlist, detached-principal
record survival, rebinding, cross-class author rejection, exact migration author
mapping, incompatible bulk-history rejection, unchanged transfer digests, unchanged
audit signatures, Ledger immutability, teacher/class destruction and retention,
attendance/payroll, support review, and transfers. Final verification covered 94 distinct targeted tests; each has a passing
latest result across the focused runs (initial failures were corrected and rerun). No full suite or deployment was run.

At this checkpoint, the distinct teacher-facing Unclaim command and UI remained
the next implementation step. Those checks verified its Seat-lifetime prerequisite;
see the subsequent Unclaim implementation entry below. Public disclosures remain separate from this internal release record.

Principal-reference cleanup verification artifacts:

- `pytest_result/20260916_pytest_test_seat_owned_records_summary.md`
- `pytest_result/20260916_pytest_test_seat_owned_records_summary_1.md`
- `pytest_result/20260916_pytest_specific_summary_3.md`
- `pytest_result/20260916_pytest_test_seat_owned_records_summary_5.md`
- `pytest_result/20260916_pytest_test_tlcp_actor_context_resolution_summary.md`

Python compilation and scoped `git diff --check` passed.


## Explicit Unclaim implementation (2026-09-15)

FEAT-IDEN-006 now owns a separate teacher Unclaim command and roster modal.
Re-entered first/last names regenerate temporary claim hashes only; existing
IdentityProfile display names and encrypted notes remain unchanged. Detach the
User, preserve the Seat and its class-owned records, and delete the principal only
when no remaining Seat or class ownership references it. Unclaiming the last
student does not delete the class or teacher.

Migration d8b8c9d0e1f2 adds a server-stored Seat claim generation. Unclaim increments
it; initial credential setup and Unclaim forms reject stale generations. Both
ordinary claim and authenticated binding can reclaim the preserved Seat. Unclaim
also cancels unfinished teacher-recovery requests dependent on that Seat and
removes the previous claimant's confirmation material. This is an Identity
lifecycle change under INV-ARC-019, DOM-IDEN-005/007 and FEAT-IDEN-001/002/006.

Validation: 48 distinct targeted tests have passing latest results: 17 Unclaim
cases and 31 existing student-recovery cases. A recovery test's classroom setup
was corrected and rerun. Artifacts: `pytest_result/20260916_pytest_test_student_unclaim_summary_1.md`
(first 14 passing cases; includes the superseded fixture failure) and
`pytest_result/20260916_pytest_specific_summary_4.md` (remaining 34 passing cases).
Python compilation, Unclaim JavaScript syntax, and scoped diff checks passed.
UI verification covers server-rendered controls; interactive browser behavior
has not been tested. No full suite, commit, deployment, or production migration.

## Lookup encoding verification (2026-09-15)

37 focused tests passed for purpose/class separation, structured-field ambiguity,
Unicode normalization, duplicate-name batch rejection, initial/authenticated claim,
Unclaim, principal sign-in, student recovery completion and hall-pass normalization.
The added fixed HMAC encoding vector also passed on rerun (one of those 37 tests).
Artifacts: `pytest_result/20260916_pytest_test_lookup_hash_contract_summary.md`
and `pytest_result/20260916_pytest_test_lookup_hash_contract_summary_1.md`.
Python compilation and scoped diff checks passed. No full suite, data migration,
old-digest fallback, commit or deployment was performed. Unused obsolete claim/name
calculations were removed from the manual-add route; teacher-recovery capability
hashing/lifecycle remains a distinct follow-up, not certified by these checks.


## Teacher recovery completion remediation (2026-09-15)

Reconciled FEAT-IDEN-103/104/105/106 against DOM-IDEN-003 §IX and incorporated
SPEC-SEC-001. Preserve one selected student per owned class, six-digit numeric
confirmation codes, a five-day total window, and saved partial progress. The old
FEAT bcrypt/alphanumeric-code instructions and consumed-at-generation interpretation
were stale specification conflicts; generation records student confirmation, while
successful full submission consumes the code verifiers into a server-owned setup grant.

Registered FEAT commands now serialize initiation, confirmation, submission and
completion through the teacher User and request locks. Submission checks exact
nonempty class coverage and the full multiset of generated codes; failures clear
all confirmations and saved/setup material. Recovery codes and resume PINs use
separate purpose labels; confirmation digests are request-bound. Ambiguous resume
PIN lookups fail closed. Saved codes and username are encrypted, with no plaintext
fallback. A saved-progress route/service naming collision was removed.

Migration e9c9d0e1f2a3 adds server-held setup authorization: nonce verifier,
encrypted pending TOTP seed and encrypted pending username. The signed session
contains the nonce and request reference only. Completion checks live pending state,
original expiry, nonce, current participant/class coverage and the newly enrolled
TOTP. Credential replacement, all passkey deletion, login-session revocation,
completion state and clearing saved/setup material commit atomically. It uses
canonical User fields rather than the removed User.salt/username attributes.
Enrollment can be redisplayed through the same valid nonce for a mistyped TOTP;
request IDs and resume PINs never independently authorize credential replacement.

This is application remediation and specification reconciliation. It does not
certify provider infrastructure or unrelated authenticated TOTP-rotation UI.

Verification: final focused run passed 22 tests in 153.06 seconds, covering successful
completion and replay, expiry/cancellation/wrong nonce, missing participants, generic
all-code invalidation, encrypted progress/resume, setup-cookie contents, one-time and
concurrent issuance, concurrent completion, repeated-code multiplicity, initiation
coverage/reuse, enrollment retry, username collision, injected transaction rollback,
Unclaim cancellation and student recovery regression. Artifact:
`pytest_result/20260916_pytest_test_teacher_recovery_completion_summary_3.md`.
The initial run exposed missing FEAT registry entries, which were registered and
retested. Python compilation and scoped diff checks passed. No full suite,
interactive browser assessment, commit, deployment or production migration.

## Teacher recovery protocol revision: hidden witnesses and aggregate feedback

This revision supersedes the nominated-recipient and saved-code behavior described
in the preceding remediation entry. DOM-IDEN-003 IX and FEAT-IDEN-103–106 now
separate User-owned attempt coordination from individual class-scoped proof,
selection, issuance and confirmation commands.

Each class has two randomly selected eligible claimed student seats (one when
only one is eligible), simultaneously notified and hidden from the teacher.
Selection is frozen for the five-day attempt. Each student can regenerate their
own 30-minute code without changing recipients; new issuance replaces that
student's previous code. Either code privately confirms the class and invalidates
both outstanding codes. Accepted class proofs survive ordinary code expiration
and resume for the remainder of the attempt.

Code-entry responses and teacher status disclose receipt only. Correct and
incorrect inputs have identical response bodies and status-page output. Only the
complete set receives an aggregate result. Failed aggregate verification advances
the submission round, invalidating all prior-round codes and confirmations without
rerolling recipients or sweeping across class records. Resume rotates the attempt
nonce; credential completion retains the server nonce and atomic replacement
checks. Browser responses use public class references instead of internal IDs.
Unclaim removes only that seat's participation; the other fixed recipient remains
eligible and an already accepted class proof persists.

Migration f0d0e1f2a3b4 adds the class challenge records, access nonce verifier,
selection/confirmation state and separate code-expiration/submission-round fields.
No production migration has been performed.

Verification: 23 targeted tests passed in 169.24 seconds, including concurrent
confirmation/completion, rollback, expiry/regeneration, fixed selection, one-seat
classes, generic feedback, resume, Unclaim and student reset regression.
After the public-reference response adjustment, both affected route tests passed
again (2 tests, 13.56 seconds), including identical validity-independent rendered
status and malformed JSON handling. Artifacts:
- pytest_result/20260916_pytest_test_teacher_recovery_completion_summary_5.md
- pytest_result/20260916_pytest_test_teacher_recovery_completion_summary_6.md

Python compilation and scoped diff checks passed. The concurrent district.html
edit remains untouched. No full suite, interactive browser assessment, commit or
deployment was performed for this revision.

## Authentication cookie contents: initial teacher signup (2026-09-16)

Disposition: remedied in the prelaunch branch. Initial signup previously placed
teacher display names, class metadata, username and the pending TOTP seed in the
signed browser session. That is a storage/disclosure issue; it does not establish
an exploit or a production incident.

INV-ARC-018 now explicitly governs temporary encrypted signup storage;
DOM-IDEN-003 and FEAT-IDEN-101 define its lifecycle. A random 256-bit browser
nonce addresses a server row through a purpose-separated SHA-256 verifier.
The row contains encrypted class/display metadata, username and pending seed,
with a fixed 30-minute deadline. It has no User or Seat reference and grants no
participation authority. Each step checks server state. Restart deletes the old
attempt; an hourly job deletes expired attempts. Username changes replace the
pending seed without extending the deadline.

Final completion locks the attempt, rechecks username and TOTP, creates User,
Class, Seat and IdentityProfile together, and deletes staging in the same
transaction. Failure preserves the attempt and rolls back new identity records.
Cookies contain the nonce and ordinary session controls, not the staged values.
Migration a1e1f2a3b4c5 introduces the staging table.

Eight targeted tests passed (6 in 22.65 seconds and 2 in 11.34 seconds): cookie
contents and encrypted database representation, normal completion/replay,
restart/expiry/purge, wrong nonce/username/TOTP, username replacement without
deadline extension, cross-browser rejection, injected class-creation rollback,
concurrent completion, username collision and migration creation/repetition.
Artifacts:
- pytest_result/20260916_pytest_test_teacher_signup_staging_summary.md
- pytest_result/20260916_pytest_test_teacher_signup_staging_summary_1.md

Python compilation and scoped diff checks passed. The existing PII storage
validator also passed; its static inventory does not inspect the new encrypted
payload, whose stored representation is exercised by the targeted test.
The separate district.html edit remains untouched. No full suite, interactive
browser assessment, commit, deployment or production migration was performed.
This closes initial signup staging only; it does not certify all other cookie
contents, authenticated credential changes or hosting configuration.
