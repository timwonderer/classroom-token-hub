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

**Observed mismatch / disclosure correction:** credential activation and
`classroom_setup.create_student_user_for_seat` retain roster-name hashes. The old
public promise of erasing all claim material on completion is inaccurate.

**Normative conflict/ambiguity:** `FEAT-IDEN-001` §III.B.3 and §IV.3 require clearing
claim hashes and the distinguishing code. `main.verify_hall_pass` currently uses
the same hash columns. These are two uses of one representation in the current
code, not evidence that hall-pass verification must inherently retain claim
artifacts. A separately authorized verification representation might have a
different lifecycle. This audit does not choose that design or declare one use
intrinsically privacy-violating. Resolve the claim/lookup requirements under
Identity authority before changing the code.

### 2. Roster notes, support payloads, and identity categories

**Observed behavior / disclosure correction:** `IdentityProfile.notes` is an
encrypted field accepted by roster provisioning. `issue_helpers.create_context_snapshot`
records URL, IP address, user-agent, balances, and transaction context.
`system_admin._issue_to_view` includes snapshot and submission content.

**Normative inventory question:** `INV-ARC-018` §VI does not list the encrypted
notes field, and §VII prohibits PII in ungoverned/free-text columns. This needs a
field-purpose/inventory reconciliation. The presence of the field does not prove
that actual notes contain prohibited PII; no production content was inspected.

**Disclosure conclusion:** classify names, technical identifiers, free text, and
pseudonymous economic records separately. Opaque actor references do not sanitize
free text, but seat-linked amounts do not become direct identifiers solely
because the application can associate them with a student. The previous blanket
PII/security-problem framing is withdrawn. A violation for a particular payload
requires its field content, storage rule, and disclosure boundary to be established.

### 3. Student recovery: separate representation, context, and consumption

- **Observed behavior / disclosure correction:** `User.reset_code` stores a raw
  eight-character code; the public form accepts that code without join code or
  name. Expiry and credential replacement are implemented in the inspected path.
- **Normative representation question:** `SPEC-SEC-001` §V.4 requires a
  non-reversible verifier unless recoverability is explicitly required;
  `DOM-IDEN-002` describes a user-owned stored reset code. Reconcile that exception
  and storage representation. Raw storage is observed, not a demonstrated leak.
- **Observed context-selection mismatch / security candidate:**
  `validate_recovery_code` selects the first seat by ID after identifying the user.
  User-owned credential recovery and class-local operational authority are
  distinct. Determine whether this seat selection violates the intended setup
  context and can affect another class; do not equate account-wide credential
  replacement with unauthorized classroom mutation.
- **Source-level security control mismatch:** the read-then-clear sequence lacks
  the locked, conditional single-winner consumption required by
  `FEAT-IDEN-004` §III.A. A concurrent replay regression should establish impact.
  This audit did not execute concurrent redemption or demonstrate a takeover.

### 4. Teacher recovery: initial conclusion withdrawn

**Exact higher-level authority:** `DOM-IDEN-003` §IX, core invariant 4, says:

> All classes must be represented. One student per active class period must participate. Partial coverage is rejected.

Its recovery flow says:

> One pair is required per active class.

The domain schema declares one pending request per user and one code row per
selected student seat. The user's clarified canonical decision is one selected
student confirmation per **class_id** under the teacher's **user_id**. Class/period
labels do not define scope.

**Exact conflicting FEAT wording:** `FEAT-IDEN-103` §IV.1 says:

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

### 5. Deletion: four independent verdicts

| Boundary | Evidence | Verdict |
|---|---|---|
| Authoritative application class data | Hard-delete commands and membership/orphan handling exist. Prior tests were inspected; no deletion was executed in this audit. | Implemented paths observed; complete runtime deletion NOT_EVALUATED here. Backup uncertainty is not evidence these paths fail. |
| Ancillary application artifacts | `ActorRequestTrace.class_id` has `ON DELETE SET NULL`; deletion command does not explicitly remove traces; `tlcp` prunes by count/probabilistic TTL. | Concrete deletion-closure candidate. Test whether references survive before declaring a confirmed closure defect. |
| Automatic stale-class purge | `INV-CORE-000` §III.5 requires purge; no corresponding job or 180-day mechanism was located in the inspected application. | Observed implementation-evidence gap; remove the public 180-day guarantee. No conclusion about an uninspected external scheduler. |
| Infrastructure backups and external logs | No live retention configuration inspected. | Operational UNKNOWN, separate from application hard deletion. |

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

**Disclosure correction:** remove the old per-record-salt assertion. Any digest
migration must follow the Identity authority; it is not part of this copy task.

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
