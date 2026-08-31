# SPEC-OPS-002: Bug Hunter Badge User Experience

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-OPS-002     | 1.0     | 2026-08-30     | N/A        | Normative       |

## I. Purpose

Define how the Bug Hunter Badge System is presented to students, teachers, and
sysadmins. This specification governs presentation only; badge truth and award
authority remain defined by `DOM-OPS-003` and `SPEC-OPS-001`.

## II. Dependencies

- `DOM-OPS-003_BADGE_SYSTEM.md`
- `SPEC-OPS-001_BUG_HUNTER_BADGE_SYSTEM.md`
- `INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md`
- `INV-ARC-020_ACCESSIBILITY_REQUIREMENTS_AND_TEMPLATE_CONTRACT.md`

## III. Student Experience

Students may see:

- earned and unearned badge names and icons;
- progress toward Uptime Engineer, System Engineer, and Architecture Engineer;
- plain-language unlock requirements;
- the date an earned badge was awarded, where available.

Students must not see internal issue evidence, reviewer notes, `class_id`, `seat_id`,
`user_id`, private diagnostic content, or another actor's identity.

The six issue badges are displayed by name:

- Home Invasion
- Hidden Imposter
- The Price Is Right
- I Got The Receipt
- It's Called Fashion
- For Us All

Progress copy must state that badges require validated discoveries. It must not imply
that submitting reports guarantees an award or that every badge is currently
obtainable.

## IV. Discovery Boundary

The Bug Hunter program evaluates the running application, not the repository. User
guidance must state clearly that badges require defects discoverable through supported
application use and observable runtime evidence.

Students who identify a possible defect by reading source code must not exploit it in
the application to seek a badge. They should submit non-sensitive findings through the
project issue process and security-sensitive findings through the private
vulnerability-reporting process. Repository findings do not create a second badge set
and do not qualify for the six Bug Hunter badges unless independently discovered and
demonstrated through supported application use.

## V. Teacher Experience

Teachers may see Bug Hunter badge names, icons, award state, and collection progress for
students in the currently selected class. This visibility is system-controlled and is
not a teacher-configurable feature.

Teachers must not have controls to grant, revoke, disable, or hide badges. Teacher
issue-review workflows remain separate from Operations-owned badge awarding.

## VI. Sysadmin Experience

Sysadmin views may show operational badge records and external actor references using
`seats.public_id`. They must not expose `class_id`, `seat_id`, `user_id`, internal
database identifiers, or private student identity fields.

Sysadmin views must not create monetary rewards or imply that badge recognition is a
ledger operation.

## VII. Empty and Unobtainable States

The interface must distinguish:

- **Not yet earned**: the actor has not met the requirement.
- **No validated discoveries yet**: no qualifying issue badge exists for the actor.
- **Not currently observed**: the platform has no validated discovery for a badge
  category; this is not an error or a promise that the badge can be obtained.

Architecture Engineer may display as unearned indefinitely when one or more of the six
issue badges has no validated discovery. The interface must not encourage students to
create defects or submit fabricated reports to complete the collection.

## VIII. Accessibility and Presentation

- Every badge icon must have meaningful alternative text when it conveys state or
  identity; decorative repetition must be hidden from assistive technology.
- Badge names and progress must not rely on color, shape, or icon alone.
- Earned/unearned state must be available as text.
- Progress requirements must be readable, keyboard accessible, and understandable
  without hover-only interactions.
- The layout must remain usable at enlarged text sizes and on narrow screens.

## IX. Certificate Verification Portal

The public portal has one purpose: verify a presented certificate claim. The requester
submits the certificate code, first name, and last name. The system uses the code to
locate the candidate record and the supplied name pair to validate the match.

For a valid match, the portal may show only:

- the confirmed certificate name;
- the badge name;
- the award date;
- the optional public-safe discovery description.

For any mismatch, the portal must return one generic unsuccessful-verification result
without identifying which input failed. The portal must not expose class, seat, user,
issue, reviewer, diagnostic, vulnerability, or internal database information.

The certificate code is a locator, not a bearer capability. Rate limiting may be used
for operational abuse protection, but certificate verification is intentionally a
public read-only function and is not an account-authentication flow.

## X. Amendment

Revisions must increment the version number, update the effective date, preserve the
identity and privacy boundary, and remain consistent with `SPEC-OPS-001`.
