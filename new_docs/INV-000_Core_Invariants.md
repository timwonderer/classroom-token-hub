# Core Invariants of Classroom Token Hub
| Reference Number | Version | Effective Date |  Supercedes |Authorative?|
|------------------|---------|----------------|-----------|--------------|
| ARC-INV-000      | 1.0     |                 |N/A        |YES    |

## I. Purpose
This document defines the core invariants, or underlying principles, that drives the design of this application. Any future development of this application must stay within the boundaries of these invariants.

## II. Scope
The invariants in this document applies to:

- All services
- All routes
- All migrations
- All background jobs
- All domains, features, and visual elements

## III. Core Invariants
The following invariants shall be interpreted as hard boundaries that must be observed at all time. Invariants in this section are cumulative and non-negotiable. A valid implementation must satisfy all invariants simultaneously.

### 1. `join_code` Centric Isolation

#### Statement
All data access and mutation operations must be scoped to a single `join_code`. `join_code` defines the instance in which users reside.

#### Constraints
- No user may query `join_code` that is not assigned to them.
- No financial operation may be performed without explicit `join_code` assignment
- All domain services must accept `join_code` as an explicit parameter.
- No global settings, attributes, logs, or ledgers are allowed within the application.
- Scoped data associated with a `join_code` must not survive its deletion unless explicitly re-scoped under a separate `join_code` context.

#### Prohibited Action
- Any operation that accesses or mutates data across `join_code` boundaries not assigned to the user explicitly.

- Any role or privilege that allows for cross-tenant action.

### 2. Minimal Use and Storage of PII

#### Statement
The system stores only the minimum personally identifiable information required for functional identity binding. Any stored PII must be one-way hashed unless recovery of original content is required (e.g. display name for greeting).

#### Constraints
- No raw DOB storage of any kind
- No full name storage beyond initial claim
- PII must be nullified or deleted immediately after fulfillment of its identity-binding purpose unless explicitly required by invariant-defined functionality.
- No contact method of any kind can be stored, processed, or requested.

#### Prohibited Action
- Retention of PII beyond its defined functional purpose.
- PII stored as plaintext.

### 3. Deterministic and Traceable Financial Logic

#### Statement
All finance-related actions must be immutably logged and traceable. Financial outcomes must be deterministically reproducible from ledger state and configuration at time of execution

#### Constraints
- Any edits of finance-related log entry must be visibile to students and teachers
- Reversal action creates new counter-entry, not removal of previous action
- Full financial history within the `join_code` scope must be fully traceable
- Changes to financial configuration shall not retroactively alter prior ledger outcomes

#### Prohibited Action
- Deletion or silent mutation of financial ledger entries.

### 4. Role-Bound Authority

#### Statement
Authority is strictly scoped to defined roles. No role may exercise cross-tenant or cross-domain privileges beyond its invariant-defined scope. 

#### Constraints
- Teacher users must only be able to view `join_code` created by themselves
- Role transition must require explicit context change and re-authentication where applicable.
- System administrator must not be able to access or alter any `join_code` scoped instances
- Student demo account must behave identically to regular student account. 

#### Prohibited Action
- Any mechanism that enables privilege escalation or hidden impersonation within the application domain.