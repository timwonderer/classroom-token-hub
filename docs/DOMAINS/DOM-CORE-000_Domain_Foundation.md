# Domain Architecture Foundation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-CORE-000      | 1.0     | 2026-03-01     | N/A        | Constitutional            |

## I. Purpose
To define the structural boundaries, responsibilities, and data access patterns of independent business domains within the system (e.g., Bank, Store, Payroll).

## II. Scope
All internally segregated units of business logic supporting the Classroom Token Hub.

## III. Authority Level
Authoritative. 

## IV. Domain Rules

### 1. Logical vs Physical Isolation
Domains (such as PAY, BANK, RENT, INS, STORE) represent **logical boundaries** for specification and business logic. Physically, the application utilizes a unified, monolithic ORM (`app/models.py`) and persona-driven routing (`student.py`, `admin.py`, `system_admin.py`). 
Domain logic must be contextually grouped within these routing files and centralized services (like `balance_service.py`) without requiring separate physical micro-databases.

### 2. The `join_code` Anchor
Regardless of the domain, every financial operation, claim, or configuration MUST be firmly anchored to a `join_code` context. Cross-domain logic (e.g., Store purchasing impacting Banking balances) must perform checks against the same `join_code` for the executing user.

### 3. Shared Ledgers
Domains do not maintain isolated ledgers. All financial mutations across domains (payroll, rent, store purchases) converge on the unified `Transaction` log to ensure a deterministic financial history. Any domain generating a state mutation must emit a clearly annotated `Transaction` record.
