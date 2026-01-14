# Deprecated Symbols Registry

This document describes symbols that are **explicitly prohibited** from appearing in application code.

The authoritative, machine-enforced list lives in:

`docs/development/deprecated_symbols.txt`

CI will fail any pull request that introduces one of the listed symbols into `app/`.

---

## Purpose

Deprecated symbols represent schema or model elements that have entered the **Contract phase** of the Expand / Contract lifecycle.

Their presence in application code indicates:
- Hidden runtime coupling
- Incomplete schema contraction
- High risk of production regression

This registry exists to convert past incidents into permanent guardrails.

---

## Rules

- Symbols must be listed as **literal strings**, exactly as they would appear in code
- One symbol per line in `deprecated_symbols.txt`
- No regex, wildcards, or glob patterns
- Symbols may be removed **only after** full database contraction has been completed

---

## Current Deprecated Symbols

| Symbol | Reason | Status |
|------|--------|--------|
| `teacher_id` | Legacy single-tenant coupling replaced by StudentTeacher association | Active |

---

## Relationship to Schema Policy

This registry derives its authority from:
- **Schema Contraction & Destructive Migration Policy**
- **Schema Change Gate (PR-Blocking Checklist)**

Violation of this registry constitutes a schema gate failure.

---

**Status:** Active
