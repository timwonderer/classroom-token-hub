# ARC-IDEN-001: Admin Identity Handling

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-IDEN-001     | 3.0     | 2026-04-12     | 2.0        | Constitutional  |

## I. Purpose

This document defines the architectural rules for admin-side actor identity in
Classroom Token Hub.

It governs how teacher and system-admin actors are identified, authenticated, exposed to
other layers, and constrained at runtime so identity handling does not leak into tenant
authority or feature-local authorization logic.

## II. Scope

This document applies to:

- teacher identity
- system-admin identity
- public teacher references
- admin authentication anchors
- admin actor representation inside request context

This document does not define feature workflows or support procedures.

## III. Authority Level

Constitutional (ARC Tier). Subordinate to:

- `docs/development/v2_restructure_doc/INV-CORE-000_Core_Invariants.md`
- `docs/development/v2_restructure_doc/INV-CORE-001_Capability_Based_Architecture_and_Authority_Model.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md`

## IV. Dependencies

- `docs/development/v2_restructure_doc/ARCHITECTURE/OPERATIONS/ARC-OPS-015_Multi_tenancy_and_Join_Code_Interface.md`

## V. Actor Types

The admin-side actor types are:

- teacher
- system administrator

These are distinct architectural actors with distinct authority boundaries.

Identity commonality does not imply authority commonality.

## VI. Identity Rules

### Authentication Identity

Authentication identity must be stable, non-plaintext, and limited to the minimum data
needed to bind the actor to a valid account.

Architectural rules:

- authentication identifiers must not be reused as public authority identifiers
- authentication material must not be treated as display identity
- authentication success does not itself authorize tenant actions

### Public Teacher Identity

Teachers require a public-facing identity for flows that must reference the teacher
without exposing internal keys.

Architectural rules:

- teacher public identity must be stable
- teacher public identity may be used for public routing or verification flows where the
  architecture explicitly permits it
- teacher public identity must not be treated as tenant scope by itself

Public teacher identity identifies the teacher actor, not the class boundary.

### Internal Actor Identity

Internal actor identity is used to populate request context and evaluate authority.

Architectural rules:

- actor identity must enter request context explicitly
- actor identity must remain separate from tenant identity
- actor identity must not be inferred from display labels or route conventions

## VII. Authority Boundaries

Identity does not grant authority by default.

### Teacher Authority Boundary

A teacher actor may act only inside tenant boundaries they are explicitly associated
with.

Teacher identity alone must not authorize:

- cross-tenant reads
- cross-tenant writes
- global student access
- teacher-global shortcuts where class-scoped validation is required

### System Admin Authority Boundary

A system-admin actor is a platform actor, not a tenant actor.

System-admin identity must not authorize:

- access to tenant-scoped student data
- execution of teacher actions inside class scope
- hidden impersonation of teacher or student actors
- mutation of tenant-scoped data as an administrative convenience

If a support workflow needs tenant information, it must be satisfied through aggregate,
non-tenant-invasive architecture defined elsewhere.

## VIII. Request Context Representation

Admin-side request context must represent actor identity explicitly.

Minimum actor fields:

- `actor_id`
- `actor_type`

Where relevant, request context may also include public identity references, but those
must not substitute for actor identity or tenant context.

## IX. Public Versus Display Identity

The system must maintain clean separation between:

- authentication identity
- public identity
- display identity

Architectural requirements:

- display identity is presentation only
- public identity is routing-safe but not authority-granting
- authentication identity is private and non-display

No layer may collapse these into a single concept for convenience.

## X. Prohibited Patterns

The following are forbidden:

- plaintext identity as architectural dependency
- treating teacher identity as equivalent to class scope
- deriving authority from display names or labels
- hidden impersonation or silent role substitution
- feature-local identity rules that bypass ARC-defined actor handling

## XI. Architectural Consequences For Later Layers

This document constrains the rest of the system as follows:

- ARC docs must keep actor identity separate from tenant scope
- DOM docs must accept actor context explicitly where capability checks require it
- FEAT docs must orchestrate actor-aware requests without inventing their own identity
  models

## XII. Amendment

Revisions to this document require a version increment, an updated Effective Date, and
continued consistency with the locked invariant and foundation documents named above.
