# ARC-IDEN-001: Admin Identity Handling Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-IDEN-001     | 1.2     | 2026-03-08     | 1.1        | Constitutional  |

## I. Purpose
Define the current v2 admin identity model, including authentication identity, public teacher identity, passkey authentication capabilities, and transitional compatibility fields.

## II. Scope
Applies to identity models, login properties, and public display identifiers for System Admins and Teachers (Admins).

## III. Authority Level
Constitutional (ARC Tier). Subordinate to INV-CORE-000.

## IV. Dependencies
- `INV-CORE-000_Core_Invariants.md`

## V. Canonical Identity Fields

Teacher/admin (`teachers`):
- `username` - legacy plaintext username, nullable, transitional only
- `username_hash` - hashed auth username
- `username_lookup_hash` - deterministic lookup hash for login
- `salt` - per-account salt for username hashing
- `teacher_public_id` - canonical public teacher identifier
- `public_id` - ORM synonym alias for `teacher_public_id`
- `display_name` - teacher-managed app-facing label
- `hall_pass_verify_token` - older public verification capability token
- App-mapped `passkey_credentials` for WebAuthn support

System admin (`system_admins`):
- hashed login fields remain canonical
- plaintext `username` may still exist on legacy rows during compatibility windows
- Passkey (WebAuthn) support available for secure passwordless login

## VI. Identity Semantics

### Authentication Identity
- Primary login relies on `username_lookup_hash` (or WebAuthn passkey verification).
- WebAuthn passkeys are heavily integrated for sysadmin/admin roles to support secure passwordless sign-in.
- Legacy plaintext username support exists only as transitional compatibility behavior.
- Public product flows must not use authentication usernames as public identity.

### Public Teacher Identity
- `teacher_public_id` is the canonical public teacher identifier.
- `Admin.public_id` is the stable runtime alias for the same value.
- Public teacher references in v2 documentation should use `public_id` / `teacher_public_id`, never numeric teacher ID.

### Display Identity
- Student-facing and teacher-facing displays use `display_name` if set.
- If `display_name` is absent, the app falls back to `teacher_public_id`.
- Sysadmin views should prefer `teacher_public_id` rather than auth usernames.

## VII. v2 Public-Facing Contract
- Public hall-pass verification flows identify teachers by public teacher identity.
- Current class scope for public verification is derived from teacher-owned `ClassMembership`, not numeric teacher IDs.
- Numeric teacher IDs are internal-only.

## VIII. Transitional Compatibility
These remain in code but are not intended as the long-term v2 public contract:
- `hall_pass_verify_token` capability-token flow
- legacy plaintext `username` fields
- compatibility fallbacks required only to preserve older rows or flows during transition

Documentation must describe these as compatibility surfaces, not preferred runtime behavior.

## IX. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field. Any new authentication mechanism (such as passkeys) must be declared here.
