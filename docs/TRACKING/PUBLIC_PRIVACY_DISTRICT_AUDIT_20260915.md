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
  hierarchy conflict below; it does not override INV requirements.
- `SOP-TEST-002`: targeted structural and rendered accessibility checks.

Disagreements were not resolved by changing authority documents or adding
compatibility behavior. A lower-level description is not authorization to weaken
an invariant. Implementation changes at the disputed boundaries are stopped for
review; this documentation change only discloses observed behavior and removes
unsupported promises.

## Claim-by-claim reconciliation

| Original claim or omission | Evidence in current source | Public-page disposition |
|---|---|---|
| Teacher email/password with TOTP two-factor login | `app/routes/admin.py:login`, `signup`, passkey endpoints; `app/forms.py:AdminLoginForm` | Username + authenticator code, or enrolled passkey; avoid calling username/TOTP two-factor authentication. |
| Teachers provide only display/class labels | `admin.signup`, `AdminClassSetupForm` | Include username, two-part display name, time zone, optional section, authenticator and optional passkey metadata. |
| Student first name + last initial | `student.claim_account`, `StudentClaimAccountForm`, `identity_feat.resolve_seat_claim` | First and last fields as rostered, full or partial; distinguish code comes from the teacher. |
| PIN signs students in | `student.login`, `FEAT-IDEN-002` credential matrix | Username/passphrase sign-in; PIN for attendance, transfers, and hall passes; passphrase for listed expense/entitlement actions. |
| bcrypt with application pepper | `app/hash_utils.py:PASSWORD_KDF`, `hash_password`; `activate_student_credentials` | Salted scrypt; application lookup secret is not a password input. |
| Per-record-salted claiming HMAC | `hash_username_lookup`, `classroom_setup._set_claim_hashes` | Keyed HMAC-SHA256 without unsupported per-record-salt or domain-separation claims. |
| Claiming information erased after setup | `classroom_setup.create_student_user_for_seat`, `identity_feat.activate_student_credentials`, `bind_authenticated_student_to_class` | Disclose retained roster matching hashes; flag required cleanup. |
| No identity across classes | `User`, `Seat`, `student.add_class`, `bind_authenticated_student_to_class` | One authenticated account may join multiple classes; classroom activity remains separate. |
| Names never sent to students | Identity profiles, student display views, `main.verify_hall_pass` | Own-name display plus teacher roster and explicit verification disclosure. |
| Only student and teacher can ever see student information | `main.verify_hall_pass`; operator support views | Explain shared-link disclosure and support review exceptions. |
| No application-level system administration | `system_admin.dashboard`, `combined_logs`, `support_tickets`, `_issue_to_view` | Describe actual console, content and intended authority limits, without certifying isolation. |
| No export tools | `admin.export_class_roster`, `export_students` | Disclose teacher exports and school responsibility for downloaded copies. |
| Infrastructure cannot decrypt names | `PIIEncryptedType.process_result_value`, `ENCRYPTION_KEY` runtime dependency | Data plus key permits decryption; key custody is an operational control. |
| All potentially identifying/sensitive information encrypted | `IdentityProfile`, `Issue`, `Transaction`, `User.reset_code`, session interface | Name specific encrypted fields; disclose ordinary text, readable recovery code and signed-cookie limits. |
| Activity records are non-personally-identifiable | Seat-linked ledger, attendance, hall-pass and support models | Identify these as student-related records; opaque IDs do not make them anonymous. |
| No behavioral or disciplinary data | Bonuses/fines, attendance, destinations, notes and support content | Do not promise content cannot describe behavior; discourage unnecessary sensitive free text. |
| All data removed when term ends or after 180 days | `app/scheduled_tasks.py`; repository search for stale-class cleanup | No established scheduled class purge; explicit deletion needed, no fixed retention promise. |
| Deleting any class deletes the student's entire account | Shared `User`/`Seat`; student removal and class destruction paths | Distinguish class membership removal from other surviving memberships. |
| Deletion instantly removes every copy | `_destroy_class_scope_rows`, account deletion; no verified infrastructure evidence | Describe hard-deletion workflows and separate backup/log/export retention uncertainty. |
| Student recovery needs join code + code | `app/routes/recovery.py:account_lookup`, `identity_feat.validate_recovery_code` | Code only, ten-minute expiry, new credential setup; shared-account effect disclosed. |
| Teacher recovery omitted | `admin.recover`, `reset_credentials`, `confirm_reset`, student verification routes | Class roster challenge and student codes; five-day window; no guaranteed recovery. |
| No identifiable information in logs | `issue_helpers.create_context_snapshot`, `Issue.context_snapshot`, `_issue_to_view`, `tlcp.persist_request_trace` | Disclose URLs, IP/browser details, activity snapshots and pseudonymous references; flag policy mismatch. |
| No third-party processing or tracking of any kind | Public HTML font/CDN links, `main._marketing_site_redirect`, `turnstile.verify_turnstile_token` | List GitHub Pages, Google Fonts, jsDelivr and conditional Turnstile; distinguish ads from technical provider requests. |
| No analytics/aggregation of any kind | Interpretation/class economic views; operational monitoring | Disclose class summaries, support diagnostics and monitoring; no cross-class educational aggregation guarantee. |
| SSO unsupported by default; forks described as open-source | Current auth routes; repository license | No implemented district SSO/SIS integration; source available under PolyForm Noncommercial terms, no OSI/open-source implication. |
| FERPA/COPPA/state-law assurances | Source is insufficient to establish institutional arrangements or live controls | Replace with bounded institutional review guidance and primary-source links. |
| WCAG AA only wherever practical | `INV-ARC-020`, `SOP-TEST-002` | State project requirement, scope of checks, and no whole-product certification. |
| Secure cookies/HTTPS always, unspecified idle timeout | `app.__init__`, `auth.py`, `session_lifetime.py` | Secure flag conditional on production; student absolute vs teacher idle timeout; TLS configuration requires live verification. |
| No contact details processed at all | Account forms versus published mailto contacts | No account contact fields; separately explain sender/message data when emailing support. |

## Unresolved launch findings requiring review

These findings are source evidence or authority conflicts, not newly executed
end-to-end demonstrations. They are not fixed by publishing the revised pages.

### 1. Claim retention and hall-pass matching conflict

`FEAT-IDEN-001` §III.B.3 and §IV.3 require erasing claim name hashes and the
distinguishing code after claiming. `classroom_setup.create_student_user_for_seat`
and the credential activation/binding paths retain them. Public hall-pass
verification in `main.verify_hall_pass` matches against those same hashes.
Blindly clearing them would break that lookup. Resolve the permitted matching
representation and lifecycle under Identity authority before modifying either
path. The public pages disclose retention and verification instead of claiming
scrubbing has occurred.

### 2. PII field inventory and support diagnostics

`INV-ARC-018` §VI lists permitted identity fields without `IdentityProfile.notes`;
§VII prohibits PII in free text, JSON, and other ungoverned columns. The model and
roster provisioning currently accept encrypted notes. `issue_helpers` also builds
support snapshots with the request URL, IP address, user-agent and recent
transactions. `system_admin._issue_to_view` exposes the snapshot and submission
text to the operator view. Opaque actor IDs and class-label consent do not sanitize
that content. Decide permitted data and storage under INV before implementing a
remediation. Never describe these snapshots as anonymous or necessarily PII-free.

### 3. Recovery representation, scope, and atomicity

`User.reset_code` and `generate_teacher_reset_code` store an eight-character raw
code. `validate_recovery_code` finds a user by it, then chooses the first seat by ID,
without a teacher-issued class binding. It clears the code after reading, without
the conditional locked-consumption sequence required by `FEAT-IDEN-004` §III.A.
`SPEC-SEC-001` §V.4, incorporated by `INV-ARC-019`, requires non-reversible
verification unless recoverability is expressly required, bound authority, and
atomic consumption. Reconcile the older user-owned raw-code language in
`DOM-IDEN-002` with those requirements; do not invent a new recovery scheme in a
copy change. No concurrent-replay safety claim is made by the new pages.

Teacher recovery also needs reconciliation: `FEAT-IDEN-103` describes a
class-scoped request and all eligible students providing codes, whereas
`admin.recover` currently selects one student from each owned class and
`recovery_service.create_recovery_request_with_seats` creates an account-level
request. Do not claim the stronger quorum/scope contract is already implemented.

### 4. Automatic purge and complete deletion evidence

`INV-CORE-000` §III.5 requires stale-class purge and complete removal of linked
records, including orphaned principals. The inspected scheduled-task module has
no stale-class purge job and no code establishes the public 180-day promise.
Existing delete endpoints do not prove deployed deletion or backup erasure.

A concrete additional verification target: `ActorRequestTrace.class_id` uses
`ON DELETE SET NULL`; `tlcp.persist_request_trace` prunes by count and probabilistic
TTL. `_destroy_class_scope_rows` does not explicitly remove these traces. Test
whether detached actor references survive class deletion and reconcile their
lifecycle before certifying complete deletion. Production backup/log settings
remain NOT_EVALUATED. No account or class was deleted during this audit.

### 5. Operator authority hierarchy conflict

`SPEC-OPS-004` §VI.3 calls the console exempt from class scoping.
`INV-CORE-000` §III.4 prohibits system-admin access or alteration of class-scoped
instances; `INV-ARC-004` §V.3 names hall-pass verification as the sole permitted
teacher-wide exception. Support snapshots contain classroom facts. The lower
spec cannot authorize a broader exception. Stop implementation changes to this
boundary pending authoritative resolution; the public pages describe observed
access and explicitly withhold a compliance claim.

### 6. Lookup construction

`SPEC-SEC-001` §V.2, incorporated by `INV-ARC-018/019`, requires canonical
normalization and field/domain separation. `hash_username_lookup` hashes raw
encoded input with no separation label; roster callers normalize separately.
Do not preserve the old per-record-salt assertion or imply full compliance with
the lookup contract. Identity owners must resolve this before any digest migration.

### 7. Browser and infrastructure exposure

The Flask session uses `SecureCookieSessionInterface` via the role-scoped
subclass. Cookie contents are signed, not encrypted; display metadata and staged
signup display fields can be stored there. Do not describe database field
encryption as protection of every on-device copy. No deployment provider
inventory, off-host log sanitization, backup retention, key access audit, or TLS
inspection was performed. Provider requests visible in source are disclosed;
provider-side or injected analytics remain UNKNOWN.

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

Current targeted checks:

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
