# SPEC-OPS-001: Bug Hunter Badge System

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-OPS-001     | 1.0     | 2026-08-30     | N/A        | Normative       |

## I. Purpose

Define the concrete catalog and unlock rules for the non-monetary Bug Hunter Badge
System owned by `DOM-OPS-003`.

## II. Dependencies

- `DOM-OPS-003_BADGE_SYSTEM.md`
- `DOM-OPS-001_OPERATIONS_DOMAIN.md`
- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-ARC-001_SCOPED_REQUEST_CONTEXT.md`
- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md`
- `FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`

## III. Canonical Badge Identifiers

The six fixed issue-discovery badge identifiers and student-facing names are:

1. **Home Invasion**
2. **Hidden Imposter**
3. **The Price Is Right**
4. **I Got The Receipt**
5. **It's Called Fashion**
6. **For Us All**

The badge identifier is the category key. No second, undocumented category taxonomy
may be introduced. These names are not runtime identity or class scope.

An issue badge is awarded only for a validated discovery resolved through the authorized
issue workflow. Submission, escalation, duplicate filing, or a report that cannot be
reproduced is insufficient.

## IV. Bug Hunter Eligibility Boundary

A Bug Hunter badge may be awarded only for a defect that is discoverable through
supported use of the running application. The discovery must be demonstrated through
observable product behavior, such as a reproducible actual result that conflicts with
the expected result.

Discoveries that require repository inspection, privileged implementation knowledge, or
source-code access are outside the Bug Hunter badge program. They must not be tested
against the public application using that private knowledge. The student should report:

- non-sensitive repository findings through the project's normal issue process;
- security-sensitive findings through the project's private vulnerability-reporting
  process.

Repository contribution recognition is separate from Bug Hunter badge recognition. The
same six issue badges apply to eligible runtime discoveries; a second set of badges for
repository discovery methods is not defined by this specification.

## V. Discovery Evidence and Authority

An awardable discovery MUST have:

- one resolved issue record;
- an explicit issue badge selection by the authorized resolver;
- evidence that the reported behavior is a real defect or invariant-relevant failure;
- a recorded resolution decision and correlation identifier;
- one canonical class-scoped operational actor as the recipient.

The Operations-owned issue-resolution FEAT is the only lawful award initiator. Teacher
actions, routes, templates, background jobs, and direct database writes must not award
badges independently. Teacher issue-review authority does not include Bug Hunter badge
grant or revocation authority. Badge recognition is a system-level feature and cannot
be disabled or hidden by a teacher.

## VI. Engineering Badges

Engineering badges measure distinct issue-discovery badges held by one actor:

| Badge | Unlock condition |
|---|---|
| **Uptime Engineer** | At least 2 distinct issue-discovery badges |
| **System Engineer** | At least 4 distinct issue-discovery badges |
| **Architecture Engineer** | All 6 issue-discovery badges |

Repeated discoveries in one category do not satisfy distinct-category requirements.
Architecture Engineer may remain unawarded when the platform has not produced a
validated discovery in every category.

## VII. Award, Collection, and Monetary Rules

- Awards are attributed internally to one class-scoped `seat_id`.
- External surfaces use `seats.public_id`; internal `class_id`, `seat_id`, and `user_id`
  are never exposed.
- Awards are idempotent per actor, badge, and validated discovery. Repeated reports or
  repeated resolution requests cannot create duplicate awards.
- Engineering badges are derived from distinct awarded issue badges, never raw issue
  counts or unvalidated submissions.
- Awards and unlocks require auditable FEAT correlation.
- A failed or reversed issue resolution must not award a badge. If an authoritative
  correction invalidates an award, the correction must be recorded explicitly and the
  collection projection recomputed from the surviving lawful awards.
- Badge recognition creates no ledger transaction, balance credit, reward amount, or
  other monetary compensation.

## VIII. State and Projection

Issue-badge awards are authoritative operational records. Engineering badges are
derived state over the actor's distinct surviving issue-badge awards. A read projection
may be used for performance but must never become an independent source of truth.

Badge state is class-scoped. The same authenticated user may hold separate collections
for separate seats and classes; awards must not leak or aggregate across class
boundaries.

## IX. Certificate Verification Artifact

Each earned badge may have one detached certificate record for public verification. The
record must not contain foreign keys or stored `class_id`, `seat_id`, `user_id`, or
recoverable identity data. It may contain:

- a certificate-code lookup digest;
- a first-and-last-name match digest;
- the badge identifier and earned state;
- the award date;
- an optional sysadmin-authored public-safe discovery description.

The certificate code locates the candidate record. It is not an authorization token and
does not grant account, class, seat, or administrative access. The submitted name pair
confirms whether the requester is referring to the intended certificate record.

The optional public description is separate from internal issue explanations, reviewer
notes, diagnostic evidence, exploit details, vulnerability reports, and operational
logs. It must be intentionally safe for public display.

## X. Amendment

Revisions must increment the version number, update the effective date, and preserve
the six named issue badges and 2/4/6 progression unless governing authority changes.
