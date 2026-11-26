# FEAT-CORE-000: Feature Execution Constitutional Directive

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-CORE-000 | 1.4 | 2026-11-26 | 1.3 | Constitutional. Subordinate to `INV-CORE-000`, `INV-CORE-001`, and `INV-ARC-006`. |

---

## I. Purpose

This document defines the mandatory execution contract for all Feature Execution (FEAT) units.

A FEAT is the only legal mechanism by which:
* state is mutated
* money is moved
* identity is bound
* cross-domain coordination occurs


Any behavior outside this contract is considered non-compliant.

This directive additionally governs lawful orchestration of constitutional economic policy evolution: each change is a new row in its owning domain's table, carrying the instant from which it governs (`DOM-CLASS-003` §V, §VII). *(1.1, operator ruling 2026-09-30: there is no policy transition or activation step; the class-wide lineage tables that held them are retired.)*

---

## II. Definition of a FEAT

A FEAT is an atomic orchestration unit that:
1. Resolves identity context
2. Validates intent across domains
3. Executes state mutations within a single transaction boundary
4. Emits an auditable execution trace

A FEAT:
* **MAY** call Domains (guards, queries, commands)
* **MUST NOT** call another FEAT executor (no FEAT-to-FEAT execution; see §V.1)
* **MUST NOT** be bypassed by routes, jobs, or scripts

Monetary FEATs that move funds MUST, inside their own single FEAT context,
construct an intended ledger plan and resolve/apply it through the Ledger
**domain commands** (`build_intended_ledger_plan` / `resolve_intended_ledger_plan`
/ `apply_resolved_ledger_plan` — plain domain functions, not FEAT executors). A
money-moving FEAT does **not** execute a separate "FEAT-LED-000" / "FEAT-LED-001"
(that would be forbidden FEAT-to-FEAT execution; see §V.1).

---

## III. Core Execution Requirements

### 1. Context-First Execution (MANDATORY)
A FEAT **MUST** resolve:
* `user_id`
* `seat_id`
* `class_id`

before any domain interaction occurs, unless its contract declares one of the
exceptions in §III.1.A.

**Failure Contract:**
If context cannot be resolved:
* execution **MUST** abort
* no state mutation is allowed
* an audit event **MUST** be emitted via DOM-OPS

### 1.A Declared Execution Exceptions (MANDATORY)

*(1.2, owner ruling 2026-11-15.)* Seat scope is the rule. A FEAT may run without a
resolved `seat_id`, or without a principal, only when its contract declares exactly
one of the classes below, names the operation, and cites the governing INV or DOM
section that makes a seat or a principal impossible or forbidden for it. Each class
is limited to the operations it lists. Adding an operation to a class amends this
directive.

1. **Identity establishment.** Student claim (`DOM-IDEN-005` §VII, §VIII), student
   account recovery (`DOM-IDEN-002` §IX), teacher account provisioning
   (`DOM-IDEN-005` §VI; `DOM-IDEN-003` §VII), and teacher account recovery
   (`DOM-IDEN-003` §IX). The FEAT:
   * requires the absence of an authenticated principal wherever `DOM-IDEN-005`
     §VII requires it;
   * at ingress, before any capability exists, performs only the initial proof and
     lookups its governing section defines (student claim: join code to
     `class_id`, then the roster fingerprint within that class, `DOM-IDEN-002`
     §VIII; teacher recovery: the single knowledge-proof precheck, `DOM-IDEN-003`
     §IX);
   * after ingress, resolves only what the capability token it holds names
     (`INV-ARC-019` §XI), and acts on a `class_id` or seat the request supplies
     only when that capability binds it;
   * performs no lookup its governing section forbids (student recovery: no seat,
     class or profile lookup, `DOM-IDEN-002` §IX).

   Additional classroom creation by an existing teacher (`DOM-IDEN-005` §VI;
   `FEAT-CLASS-001` §III) is the one establishment operation with an authenticated
   principal. `DOM-IDEN-005` §VI requires it to occur outside an existing class
   scope, so it runs with the authenticated teacher `user_id` and no `class_id` or
   `seat_id`, and it provisions the new class and the teacher's administrative seat
   in one transaction.
2. **Session boundary.** Sign-in and sign-out. Sign-in writes the `users` session
   fields on success and the class context is restored afterwards (`DOM-IDEN-002`
   §VII; `DOM-IDEN-003` §VII; `DOM-IDEN-006`). Sign-out does not require a
   resolvable class or seat, because revoking a session removes authority and no
   principal may be held in a session because its context cannot be resolved; it
   verifies the session's own token before revoking it. The FEAT writes only
   `users` fields and nothing class-scoped: the session fields, the class context
   pointers sign-in restores, and, on a successful teacher sign-in,
   `last_signed_in_at` under the User row lock (`DOM-IDEN-003` §IX.A).
3. **Principal lifecycle.** Teacher account deletion only (FEAT-IDEN-007), by one
   of two authorities. Deletion is a principal-level operation; the active class or
   seat is not its authority boundary.
   * **Manual deletion:** the FEAT authenticates and authorizes the signed-in
     principal, including the step-up `DOM-IDEN-003` §VII requires before the last
     class, and with it the identity, is destroyed.
   * **Scheduled destruction:** the hourly lifecycle sweep of `DOM-IDEN-003` §IX.A.
     Its authority is the retention policy, rechecked under the User row lock
     before execution; it is neither a signed-in principal, a sysadmin session nor
     impersonation, and interactive authentication and step-up do not apply to it.

   Either way the FEAT resolves every affected association through the owning
   domain's authority and applies the destruction, retention and audit rules in
   every affected class. No active class selection is required.
4. **System administration.** Operations of a principal whose `user_role` is
   `SYSADMIN`, which `INV-CORE-000` §III.4 forbids from holding class context.
   Not available to teacher or student principals.
5. **Out-of-band operator.** The operator bootstrap command (FEAT-IDEN-008), run
   under host authority from the command line (`SPEC-OPS-004` §V: operator
   provisioning is out-of-band). The new system principal has no class or seat.

6. **Principal credential maintenance.** Teacher or sysadmin initial/additional passkey enrollment,
   TOTP replacement, selected-passkey replacement and removal (DOM-IDEN-003 §VII.A)
   resolve explicit principal context without a Seat or Class. Fresh purpose-bound
   authorization, current generation and applicable session binding remain required.
7. **Credential reconciliation.** FEAT-IDEN-108 runs from a recorded principal
   operation or scheduled system authority (INV-ARC-019 §VI; DOM-IDEN-003 §VII.A).
   It uses current Identity/provider state, never fabricated classroom context or
   an expired session as authority. It cannot establish local authority from provider
   inventory or access classroom data.

No teacher operation outside these declared categories may run without a teacher
Seat in the active class. Principal ownership does not by itself authorize mutation.

Two operations resolve a *target* seat rather than the active one, and need no
exception: class selection, and authenticated class binding. Each resolves the
target seat from the principal's own seats, or from the claim, under the chosen
`class_id`, and meets §III.1 with it.

A declared exception relaxes only §III.1, §VII.1 and §VIII.6. Every other
requirement of this directive applies, including §III.2, §III.3, §III.4 and §V.1.

### 2. Single Transaction Boundary (MANDATORY)
A FEAT **MUST** execute within a single atomic transaction.

The sole exception is a credential-provider workflow (§IV.6): it is a sequence of
local atomic transactions under one FEAT identifier and correlation id, with the
provider call made between them and no transaction open. Each local transaction
commits or rolls back whole; a provider effect is never rolled back by the database,
and a later local failure leaves the durable committed operation state to be resumed or
reconciled as SPEC-IDEN-002 defines.

The transaction **MUST** include:
* all ledger entries
* all domain state mutations derived from the action
* all correlation identifiers linking them
* every economic policy row the action records

**Failure Behavior:**
* partial writes are forbidden
* any failure **MUST** trigger full rollback

### 3. Idempotency (MANDATORY)
Every FEAT **MUST** be safe to retry.

**Requirements:**
* an `idempotency_key` **MUST** be accepted or generated.
* duplicate executions **MUST NOT** produce duplicate effects.
* **Scope:** Idempotency MUST apply to identity binding, entitlement creation, and obligation state transitions, in addition to ledger entries.
* ledger duplication **MUST** be prevented at the database level.
* replayed economic policy changes MUST NOT record a policy row twice.

### 4. Audit Logging & Correlation (MANDATORY)
Every FEAT execution **MUST** emit an audit record via DOM-OPS containing:
* FEAT identifier
* actor (`user_id`, `seat_id`, `class_id`)
* `correlation_id`: A unique identifier that MUST be generated and propagated for all multi-step, linked, or reversible operations.
* input payload (sanitized)
* result (success/failure)
* timestamp

The actor fields are those the FEAT's scope resolves. Under a declared exception
(§III.1.A), a field the scope does not resolve is recorded as absent; it is never
inferred, defaulted or substituted from another identifier. Where the record is
held and how a principal reference is represented in it are governed by DOM-OPS.

**Failure to log = non-compliant execution**

### 5. Workflows

*(1.2.)* A FEAT contract may define a **workflow**: ordered steps performed by one
actor under one authority grant.

1. Each step is one execution: one request, one command path, and one transaction
   under §III.2 (`INV-ARC-000` §V, §VIII.2).
2. Authority carries from one step to the next only as a capability token defined by
   an INV or DOM contract (`INV-ARC-019` §XI). Each step re-validates the token
   against the owning domain's current state, under lock, before it mutates. An
   earlier request's allow decision is never carried forward (`INV-CORE-001`
   §VIII.2; `INV-ARC-010` §V).
3. The whole workflow uses one FEAT identifier and one `correlation_id`.
4. A change of actor or of authority source starts a different FEAT.

---

### 6. External credential-provider effects

A credential workflow is not a distributed atomic transaction. Each local step has
one atomic transaction; external calls and retry delays SHALL occur with no database
transaction or database row lock held open. Commit exact intent/operation authority
first, perform the provider interaction, then re-evaluate current principal existence,
generation, supersession and stage in a new local transaction. Provider effects cannot
be rolled back by PostgreSQL. Use durable operation state and explicit serialization,
not a long-running database transaction, to coordinate competing work.

A reconciliation continuation uses FEAT-IDEN-108 because its authority differs from
the initiating user. Initiating FEATs compose the shared Identity commands; they do
not call the reconciliation FEAT executor. A job invokes FEAT-IDEN-108 separately.
The account-destruction provider-failure exception is limited to DOM-IDEN-003 §VII.A;
it never permits partial classroom/database destruction or omitted mandatory audit.

Credential lifecycle audit fields use DOM-OPS-002 §2.5 rather than retaining resolved
principal identifiers in durable observability. This does not weaken any financial
protected-row lineage requirement.

## IV. Domain Interaction Rules

### 1. Domain Isolation (MANDATORY)
Domains:
* **MUST NOT** call other domains
* **MUST NOT** orchestrate workflows
* **MUST NOT** initiate ledger writes outside their scope

All cross-domain coordination **MUST** occur inside a FEAT.

This includes lawful orchestration of economic policy changes through their owning commands.

### 2. Validation vs Mutation Separation (MANDATORY)
Domains **MAY**:
* validate conditions
* return eligibility / constraint responses

Domains **MUST NOT**:
* mutate state during validation
* trigger side effects implicitly

**Ordering Guarantee:**
A FEAT **MUST NOT** perform any state mutation until all validation phases (across all involved domains) complete successfully.

**Example (Prohibited):**
* Store validation triggering overdraft fee before purchase success is guaranteed.

**Correct Pattern:**
* FEAT performs validation → FEAT performs mutation explicitly.

### 3. Guard Pattern Standardization (MANDATORY)
To ensure consistent cross-domain enforcement, all "Domain Guards" MUST follow a standardized interface:

**Pattern:**
`DOM-[DOMAIN].check_[CONDITION](context_id) -> { allowed: bool, reason: enum, metadata: dict }`

**Requirements:**
* Guards MUST be read-only.
* Guards MUST return a machine-readable `reason` code (Enum).
* FEATs MUST handle both `allowed: true` and `allowed: false` outcomes explicitly.
* Guards MUST NOT throw exceptions for business-level rejections; they must return `allowed: false`.

### 3. Ledger Authority (MANDATORY)
All money movement **MUST** be executed through DOM-LED.

No domain may:
* create implicit financial effects
* bypass ledger recording
* simulate balance changes

---

## V. FEAT Composition Rules

### 1. No FEAT-to-FEAT Execution

A FEAT executor **MUST NOT** invoke another FEAT executor — directly or
indirectly, and regardless of correlation-ID equality. This holds for **every**
FEAT; there is **no Core-FEAT carve-out**. The earlier "Core FEATs MAY be called
by other FEATs" allowance (`FEAT-PAY-POST`, `FEAT-IDEN-LOGIN`, `FEAT-LED-000`) is
**removed** — it is superseded by the higher-authority execution model:

* INV-ARC-000 §VIII.2 — *exactly one command path executes per request*;
* INV-ARC-021 §V.2 — the FEAT is the **only** construct permitted to compose
  logic across domains, **within a single execution path**;
* INV-ARC-006 — all mutation occurs inside explicit **domain commands**.

Shared functionality is invoked through domain-level guards, queries, and
commands (plain domain functions / services), never through another FEAT. For
example, a money-moving FEAT composes the Ledger **domain commands**
(`resolve_intended_ledger_plan` / `apply_resolved_ledger_plan`, which are plain
domain functions, not FEAT executors) inside its own single context — it does not
execute a "FEAT-LED-000".

Enforcement: the runtime `FEATContext` guard rejects entering any FEAT context
while another is active (regardless of feat_name/correlation), and a structural CI
check forbids a FEAT module from importing another FEAT's executor.

*(1.2.)* One request executes at most one FEAT. Two FEAT executions in one request
are prohibited even when they are sequential and not nested (`INV-ARC-000`
§VIII.2). This is not prohibited: a route renders a form or redirects, and a later
request invokes a FEAT. That is two requests and two command paths. A contract may
name the step that follows it (§III.5); it never invokes it.

---

## VI. Side-Effect Governance

### 1. Explicit Side Effects Only (MANDATORY)
No FEAT may trigger hidden or implicit side effects.

All side effects **MUST** be:
* explicitly declared
* executed within the transaction boundary
* traceable via audit logs

**Example (Prohibited):**
* Payroll implicitly mutating economic policy state

**Correct Pattern:**
* FEAT emits event → separate FEAT handles rebalance
* A change for a later boundary is recorded now as a row dated to that boundary; nothing activates it

### 2. Post-Execution Events (ALLOWED)
FEATs **MAY** emit events for downstream processing:
* analytics
* policy-governance analysis
* notifications

These **MUST**:
* be emitted **ONLY AFTER** a successful transaction commit.
* not mutate core state within the originating transaction.
* be idempotent and replay-safe.

---

## VII. Identity Authority Rules

### 1. Seat as Execution Context (MANDATORY)
All FEAT execution **MUST** be scoped to a resolved `seat_id`, except under a
declared exception (§III.1.A).

No FEAT may operate using:
* raw `user_id` alone
* `join_code` as authority
* global identity lookups

### 2. Binding Integrity (MANDATORY)
Identity binding operations **MUST**:
* occur only within `FEAT-IDEN-*`
* be atomic
* not leak intermediate states

---

## VIII. Prohibited Patterns

The following are explicitly forbidden:
1. Route-level business logic that mutates multiple domains
2. Domain calling another domain
3. Ledger mutation during validation phase
4. Partial state updates without ledger correlation
5. Hidden entitlement creation without ledger trace (unless explicitly zero-value and declared)
6. Context-less execution (no `seat_id`) outside a declared exception (§III.1.A)
7. Reconstruction of authoritative state from non-authoritative sources (e.g., using ledger as attendance truth)
8. Direct mutation of constitutional economic policy state instead of appending a row to the owning table
9. Hidden delayed economic mutation that is not a visible, effective-dated row
10. Operational domains rewriting a policy row

---

## IX. Compliance Requirements

All FEAT implementations **MUST**:
* declare required context inputs: seat scope, or exactly one exception class from §III.1.A with its governing citation
* define transaction boundary scope
* specify idempotency mechanism
* emit audit logs
* pass invariant checks post-execution
* record economic governance changes as new rows of the owning table

**CI SHOULD enforce:**
* no direct domain-to-domain calls
* no route-level multi-domain mutation
* presence of audit logging
* presence of idempotency handling
* prohibition against in-place mutation of an economic policy row

---

## X. Execution Boundary Enforcement (MANDATORY)

All state mutation **MUST** originate from a FEAT.

The following are prohibited from performing direct mutations:
* Routes (Flask handlers)
* Background jobs
* CLI scripts

These **MUST** invoke a FEAT instead to interact with domain state.

Constitutional economic policy evolution MUST occur through FEAT-orchestrated execution of the owning domain's command.

Direct mutation of an economic policy row outside FEAT execution is prohibited.

### 1. Technical Enforcement Mechanisms (RECOMMENDED)
To ensure compliance, the implementation SHOULD utilize:
* **Context Decorators**: `@requires_feat_context` on domain mutation methods.
* **DB Assertions**: A database wrapper that asserts a valid `FEAT_EXECUTION_CONTEXT` is present before committing.
* **Linting Rules**: CI checks to detect `db.session.add/commit` calls outside the `/app/features/` directory.

---

## XI. Relationship to Other Documents

* `INV-CORE-*` defines system invariants (higher authority)
* `DOM-*` defines domain rules and data ownership
* `FEAT-*` defines concrete execution units governed by this directive
* `MAP-*` provides non-normative mappings and guidance

---

## XII. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`

**2026-11-26 amendment:** Scope item 6 covers sysadmin principals as well as teachers (DOM-IDEN-003 §VII.A).

**2026-11-23 amendment:** Records the owner-approved credential lifecycle scope, activation, reconciliation and retention boundaries. Class isolation and foundational lifecycle requirements remain unchanged.
