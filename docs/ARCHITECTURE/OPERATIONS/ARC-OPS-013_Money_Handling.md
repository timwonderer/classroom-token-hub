
---
title: Money Handling
category: technical-reference
roles: [developer]
description: Authoritative rules for Decimal-safe money and cashflow handling.
---

# Money Handling

## I. Purpose

TBD
## II. Scope

TBD
## III. Authority Level
Constitutional. Subordinate to CORE invariant definitions.
## IV. Dependencies
None specified.
## V. Core Rule

All money values must be represented and calculated as `Decimal`, never `float`.

## VI. Storage

- Database money columns must use `Numeric(..., scale=2)` (or integer cents where specified).
- Ledger rows are the source of truth for money movement.
- Balance cache stores cents as integers to avoid floating-point drift.

## VII. Arithmetic

- Use `Decimal` operands for all adds/subtracts/multiplies/divides.
- Normalize user input to `Decimal` before any arithmetic.
- Quantize currency values to 2 decimal places before persistence and comparisons.
- Do not mix `Decimal` and `float` in expressions.

## VIII. Defaults and Fallbacks

- Use `Decimal('0.00')` for monetary zero defaults.
- Avoid `0.0`/`0` for monetary fallback values in money paths.

## IX. Serialization Boundaries

- JSON/API responses may convert `Decimal` to string or float for display/transport.
- Internal business logic must convert back to `Decimal` immediately when values are reused for arithmetic.
- Cached payroll/balance payloads should store exact currency strings where possible.

## X. Forms and Input

- Treat float-form inputs as untrusted numeric text.
- Convert and quantize at route/service boundaries before writing to models.

## XI. Review Checklist

- No `float` arithmetic in money or cashflow logic.
- No `or 0.0` defaults for monetary fields.
- Money math always quantized before compare/store.
- Ledger writes and reversals preserve exact cents.
## XII. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field. Subordinate to CORE changes.
