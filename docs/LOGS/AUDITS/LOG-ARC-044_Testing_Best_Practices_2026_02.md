---
title: Testing Best Practices (Historical Snapshot)
category: logs
roles: [developer]
description: Historical testing guidance migrated from the legacy development planning tree.
---

# LOG-ARC-044: Testing Best Practices

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| LOG-ARC-044 | 1.0 | 2026-03-08 | N/A | Informative |

## I. Purpose

Preserve a historical snapshot of project testing guidance that originally lived in `docs/development/`.

## II. Scope

This document is retained as historical engineering guidance. It is not the canonical testing policy for current work.

## III. Historical Context

**Last Updated:** 2026-02-19

This document outlines best practices for writing robust tests in the Classroom Economy codebase, particularly for compatibility with stricter database environments (Postgres) and future library versions (SQLAlchemy 2.0).

---

## 1. Strict Foreign Key Constraints

When running tests against Postgres (or a properly configured SQLite), Foreign Key constraints are strictly enforced. This means you **cannot** create child records without their parents existing.

### The `ClassEconomy` Root
The `ClassEconomy` table is the root of the multi-tenancy tree. Almost all other entities (`TeacherBlock`, `Student`, `Transaction`) eventually link back to it via `join_code`.

**Rule:** Always create a `ClassEconomy` record *before* creating any record that references a `join_code`.

**Bad Pattern (Fails in Postgres):**
```python
# Fails because 'TEST123' doesn't exist in class_economies
block = TeacherBlock(join_code='TEST123', ...)
db.session.add(block)
```

**Good Pattern:**
```python
# Create the root economy first
if not db.session.get(ClassEconomy, 'TEST123'):
    economy = ClassEconomy(join_code='TEST123', status='active')
    db.session.add(economy)
    db.session.flush()

# Now create the child
block = TeacherBlock(join_code='TEST123', ...)
db.session.add(block)
```

### Lazy Fixtures
Be careful with pytest fixtures that "lazily" create data. If a fixture creates a `TeacherBlock`, it MUST ensure the underlying `ClassEconomy` exists.

---

## 2. SQLAlchemy 2.0 Compatibility

We are preparing for SQLAlchemy 2.0. Avoid deprecated methods.

### `Query.get()` vs `Session.get()`
The `Model.query.get(id)` pattern is deprecated. Use `db.session.get(Model, id)` instead.

**Deprecated:**
```python
user = User.query.get(user_id)
```

**Recommended:**
```python
from app import db
user = db.session.get(User, user_id)
```

This applies to both application code and test code.

---

## 3. Data Cleanup

Tests should be self-contained. While `pytest-flask` handles transaction rollbacks, creating excessive global state (like sticking random data in the DB without proper relationships) can cause `IntegrityError`s in subsequent tests or teardowns if constraints are strict.

---

## 4. Environment Consistency

Tests should pass in both:
1.  **Local SQLite**: Fast, forgiving (often).
2.  **CI/Postgres**: Strict, production-like.

If a test fails only in CI or when switching DB drivers, it is 99% likely a missing Foreign Key relationship that SQLite was ignoring.
