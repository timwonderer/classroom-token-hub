---
title: Deprecated Symbols Machine Registry (Legacy Snapshot)
category: logs
roles: [developer]
description: Historical snapshot of the legacy machine-enforced deprecated-symbol notes migrated from docs/development.
---

# LOG-DB-013: Deprecated Symbols Machine Registry (Legacy Snapshot)

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| LOG-DB-013 | 1.0 | 2026-03-08 | N/A | Informative |

## I. Purpose

Preserve the contents of the former `docs/development/DEPRECATED_SYMBOLS.txt` file as a historical record.

## II. Scope

This document is not the canonical active registry. Use `SOP-DB-014_Deprecated_Symbols_Registry.md` for maintained policy.

## III. Historical Snapshot

```text
Deprecated symbols (machine-enforced)
One symbol per line. Literal strings only.
CI fails if any of these appear in app/ code.

NOTE: The generic "teacher_id" was previously listed here but is too broad.
Many models legitimately use teacher_id columns (TeacherBlock, Transaction, etc.)

ACTUALLY DEPRECATED:
- Student.teacher_id column (dropped in migration 1e07c37d3c7c)
- Any code that sets Student(teacher_id=...) or queries Student.filter_by(teacher_id=...)

NOT DEPRECATED (still valid):
- TeacherBlock.teacher_id
- Transaction.teacher_id
- PayrollSettings.teacher_id
- BankingSettings.teacher_id
- StoreItem.teacher_id
- InsurancePolicy.teacher_id
- HallPassSettings.teacher_id
- RentSettings.teacher_id
- FeatureSettings.teacher_id
- And other models that legitimately reference the admins table via teacher_id

The student-teacher relationship is now EXCLUSIVELY managed via:
1. StudentTeacher table (for linking students to teachers)
2. TeacherBlock table (for class period/seat management)
```
