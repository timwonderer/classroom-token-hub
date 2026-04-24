# FEAT-CORE-000: Feature Execution Constitutional Directive (Normative)

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-CORE-000 | 1.0 | 2026-04-23 | N/A | Normative |

---

## I. Purpose

This document defines the mandatory execution contract for all Feature Execution (FEAT) units.

A FEAT is the only legal mechanism by which:
* state is mutated
* money is moved
* identity is bound
* cross-domain coordination occurs

Any behavior outside this contract is considered non-compliant.

---

## II. Definition of a FEAT

A FEAT is an atomic orchestration unit that:
1. Resolves identity context
2. Validates intent across domains
3. Executes state mutations within a single transaction boundary
4. Emits an auditable execution trace

A FEAT:
* **MAY** call Domains
* **MAY** call approved Core FEATs
* **MUST NOT** be bypassed by routes, jobs, or scripts

---

## III. Core Execution Requirements

### 1. Context-First Execution (MANDATORY)
A FEAT **MUST** resolve:
* `user_id`
* `seat_id`
* `class_id`

before any domain interaction occurs.

**Failure Contract:**
If context cannot be resolved:
* execution **MUST** abort
* no state mutation is allowed
* an audit event **MUST** be emitted via DOM-OPS

### 2. Single Transaction Boundary (MANDATORY)
A FEAT **MUST** execute within a single atomic transaction.

The transaction **MUST** include:
* all ledger entries
* all domain state mutations derived from the action
* all correlation identifiers linking them

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

### 4. Audit Logging & Correlation (MANDATORY)
Every FEAT execution **MUST** emit an audit record via DOM-OPS containing:
* FEAT identifier
* actor (`user_id`, `seat_id`, `class_id`)
* `correlation_id`: A unique identifier that MUST be generated and propagated for all multi-step, linked, or reversible operations.
* input payload (sanitized)
* result (success/failure)
* timestamp

**Failure to log = non-compliant execution**

---

## IV. Domain Interaction Rules

### 1. Domain Isolation (MANDATORY)
Domains:
* **MUST NOT** call other domains
* **MUST NOT** orchestrate workflows
* **MUST NOT** initiate ledger writes outside their scope

All cross-domain coordination **MUST** occur inside a FEAT.

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

### 1. Core FEATs
Certain FEATs are designated as Core Orchestrators:
* `FEAT-PAY-POST`
* `FEAT-IDEN-LOGIN` (context restoration only)

Core FEATs:
* **MAY** be called by other FEATs
* **MUST NOT** open a new transaction boundary when called internally

### 2. FEAT-to-FEAT Calls (RESTRICTED)
A FEAT **MAY** call another FEAT only if:
* the called FEAT is a Core FEAT
* no nested transaction boundary is created
* idempotency is preserved

All other orchestration **MUST** occur within the calling FEAT.

---

## VI. Side-Effect Governance

### 1. Explicit Side Effects Only (MANDATORY)
No FEAT may trigger hidden or implicit side effects.

All side effects **MUST** be:
* explicitly declared
* executed within the transaction boundary
* traceable via audit logs

**Example (Prohibited):**
* Payroll triggering economy rebalance implicitly

**Correct Pattern:**
* FEAT emits event → separate FEAT handles rebalance

### 2. Post-Execution Events (ALLOWED)
FEATs **MAY** emit events for downstream processing:
* analytics
* rebalancing
* notifications

These **MUST**:
* be emitted **ONLY AFTER** a successful transaction commit.
* not mutate core state within the originating transaction.
* be idempotent and replay-safe.

---

## VII. Identity Authority Rules

### 1. Seat as Execution Context (MANDATORY)
All FEAT execution **MUST** be scoped to a resolved `seat_id`.

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
6. Context-less execution (no `seat_id`)
7. Reconstruction of authoritative state from non-authoritative sources (e.g., using ledger as attendance truth)

---

## IX. Compliance Requirements

All FEAT implementations **MUST**:
* declare required context inputs
* define transaction boundary scope
* specify idempotency mechanism
* emit audit logs
* pass invariant checks post-execution

**CI SHOULD enforce:**
* no direct domain-to-domain calls
* no route-level multi-domain mutation
* presence of audit logging
* presence of idempotency handling

---

## X. Execution Boundary Enforcement (MANDATORY)

All state mutation **MUST** originate from a FEAT.

The following are prohibited from performing direct mutations:
* Routes (Flask handlers)
* Background jobs
* CLI scripts

These **MUST** invoke a FEAT instead to interact with domain state.

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
