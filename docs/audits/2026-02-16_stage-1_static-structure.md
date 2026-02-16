# Stage 1 Audit Report: Static Structural Analysis

## Summary
- **Total Findings:** 1953
- **By Severity:**
  - High: 40
  - Medium: 1624
  - Low: 289
- **By Category:**
  - Structural Smell: 971
  - Complexity: 703
  - Dead Code: 265
  - Risk Pattern: 14

## Known Limitations
- **Unused Code Detection:** Uses simple string matching. High false positive rate for public APIs and dynamic calls.
- **Inconsistent Returns:** Does not perform type inference, only checks for presence/absence of return values.
- **Commented-out Code:** Heuristic-based, may miss some blocks or flag documentation.
- **Reachability:** Only checks simple control flow after return/raise/break/continue.
- **Scope:** Excludes tests and migrations.

## Detailed Findings

**Severity:** High
**File:** `./app/__init__.py`
**Line Range:** 151
**Category:** Complexity
**Description:** Function `create_app` has cyclomatic complexity of 49.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/auth.py`
**Line Range:** 59
**Category:** Complexity
**Description:** Function `login_required` has cyclomatic complexity of 33.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/auth.py`
**Line Range:** 68
**Category:** Complexity
**Description:** Function `decorated_function` has cyclomatic complexity of 33.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/admin.py`
**Line Range:** 1058
**Category:** Complexity
**Description:** Function `signup` has cyclomatic complexity of 31.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/admin.py`
**Line Range:** 1303
**Category:** Complexity
**Description:** Function `recover` has cyclomatic complexity of 24.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/admin.py`
**Line Range:** 1849
**Category:** Complexity
**Description:** Function `_build_rent_privileges_by_block` has cyclomatic complexity of 25.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/admin.py`
**Line Range:** 2073
**Category:** Complexity
**Description:** Function `students` has cyclomatic complexity of 37.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/admin.py`
**Line Range:** 2431
**Category:** Complexity
**Description:** Function `edit_student` has cyclomatic complexity of 44.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/admin.py`
**Line Range:** 3320
**Category:** Complexity
**Description:** Function `store_management` has cyclomatic complexity of 53.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/admin.py`
**Line Range:** 3916
**Category:** Complexity
**Description:** Function `rent_settings` has cyclomatic complexity of 99.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/admin.py`
**Line Range:** 4531
**Category:** Complexity
**Description:** Function `insurance_management` has cyclomatic complexity of 21.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/admin.py`
**Line Range:** 4950
**Category:** Complexity
**Description:** Function `process_claim` has cyclomatic complexity of 53.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/admin.py`
**Line Range:** 5181
**Category:** Complexity
**Description:** Function `void_transaction` has cyclomatic complexity of 57.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/admin.py`
**Line Range:** 5807
**Category:** Complexity
**Description:** Function `payroll` has cyclomatic complexity of 24.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/admin.py`
**Line Range:** 6867
**Category:** Complexity
**Description:** Function `upload_students` has cyclomatic complexity of 26.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/api.py`
**Line Range:** 1111
**Category:** Complexity
**Description:** Function `handle_hall_pass_action` has cyclomatic complexity of 21.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/api.py`
**Line Range:** 2197
**Category:** Complexity
**Description:** Function `handle_tap` has cyclomatic complexity of 49.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/api.py`
**Line Range:** 224
**Category:** Complexity
**Description:** Function `purchase_item` has cyclomatic complexity of 101.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/api.py`
**Line Range:** 773
**Category:** Complexity
**Description:** Function `use_item` has cyclomatic complexity of 30.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/api.py`
**Line Range:** 966
**Category:** Complexity
**Description:** Function `reject_redemption` has cyclomatic complexity of 29.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/docs.py`
**Line Range:** 201
**Category:** Complexity
**Description:** Function `view_doc` has cyclomatic complexity of 27.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/docs.py`
**Line Range:** 386
**Category:** Complexity
**Description:** Function `search` has cyclomatic complexity of 29.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/student.py`
**Line Range:** 1091
**Category:** Complexity
**Description:** Function `dashboard` has cyclomatic complexity of 51.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/student.py`
**Line Range:** 1509
**Category:** Complexity
**Description:** Function `transfer` has cyclomatic complexity of 34.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/student.py`
**Line Range:** 1702
**Category:** Complexity
**Description:** Function `apply_savings_interest` has cyclomatic complexity of 32.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/student.py`
**Line Range:** 1923
**Category:** Complexity
**Description:** Function `purchase_insurance` has cyclomatic complexity of 21.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/student.py`
**Line Range:** 2107
**Category:** Complexity
**Description:** Function `file_claim` has cyclomatic complexity of 39.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/student.py`
**Line Range:** 2366
**Category:** Complexity
**Description:** Function `shop` has cyclomatic complexity of 29.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/student.py`
**Line Range:** 2797
**Category:** Complexity
**Description:** Function `rent` has cyclomatic complexity of 29.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/student.py`
**Line Range:** 2987
**Category:** Complexity
**Description:** Function `rent_pay` has cyclomatic complexity of 71.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/student.py`
**Line Range:** 3412
**Category:** Complexity
**Description:** Function `login` has cyclomatic complexity of 22.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/student.py`
**Line Range:** 543
**Category:** Complexity
**Description:** Function `claim_account` has cyclomatic complexity of 25.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/routes/student.py`
**Line Range:** 878
**Category:** Complexity
**Description:** Function `add_class` has cyclomatic complexity of 36.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/utils/banking.py`
**Line Range:** 10
**Category:** Complexity
**Description:** Function `settle_balances` has cyclomatic complexity of 31.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./app/utils/overdraft.py`
**Line Range:** 37
**Category:** Complexity
**Description:** Function `charge_overdraft_fee_if_needed` has cyclomatic complexity of 21.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 80
**Category:** Complexity
**Description:** Function `analyze_migrations` has cyclomatic complexity of 35.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 114
**Category:** Complexity
**Description:** Function `migrate_legacy_students` has cyclomatic complexity of 23.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./scripts/inspect_join_code_columns.py`
**Line Range:** 54
**Category:** Complexity
**Description:** Function `inspect_database_schema` has cyclomatic complexity of 24.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./scripts/validate-migrations.py`
**Line Range:** 235
**Category:** Complexity
**Description:** Function `validate_migrations` has cyclomatic complexity of 42.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** High
**File:** `./scripts/verify_chain.py`
**Line Range:** 42
**Category:** Complexity
**Description:** Function `verify_migration_chain` has cyclomatic complexity of 33.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 151-740
**Category:** Complexity
**Description:** Function `create_app` is 590 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 303
**Category:** Complexity
**Description:** Function `show_maintenance_page` has cyclomatic complexity of 11.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 398
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 406
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 440
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 529
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 538
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 556
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 593
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 609
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 636
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:636, ./scripts/add-security-headers.py:16
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 637
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:637, ./scripts/add-security-headers.py:17
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 638
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:638, ./scripts/add-security-headers.py:18
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 638-729
**Category:** Complexity
**Description:** Function `set_security_headers` is 92 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 639
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:639, ./scripts/add-security-headers.py:19
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 640
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:640, ./scripts/add-security-headers.py:20
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 641
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:641, ./scripts/add-security-headers.py:21
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 642
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:642, ./scripts/add-security-headers.py:22
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 643
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:643, ./scripts/add-security-headers.py:23
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 644
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:644, ./scripts/add-security-headers.py:24
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 645
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:645, ./scripts/add-security-headers.py:25
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 646
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:646, ./scripts/add-security-headers.py:26
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 647
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:647, ./scripts/add-security-headers.py:27
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 648
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:648, ./scripts/add-security-headers.py:28
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 649
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:649, ./scripts/add-security-headers.py:29
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 663
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:663, ./scripts/add-security-headers.py:34
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 671
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:671, ./scripts/add-security-headers.py:41
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 676
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:676, ./scripts/add-security-headers.py:50
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 677
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:677, ./scripts/add-security-headers.py:51
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 715
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:715, ./scripts/add-security-headers.py:69
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 716
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:716, ./scripts/add-security-headers.py:70
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 717
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:717, ./scripts/add-security-headers.py:71
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 718
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:718, ./scripts/add-security-headers.py:72
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 719
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:719, ./scripts/add-security-headers.py:73
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 720
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:720, ./scripts/add-security-headers.py:74
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 721
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:721, ./scripts/add-security-headers.py:75
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 722
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:722, ./scripts/add-security-headers.py:76
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 723
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:723, ./scripts/add-security-headers.py:77
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/__init__.py`
**Line Range:** 724
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/__init__.py:724, ./scripts/add-security-headers.py:78
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 121
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/attendance.py:121, ./app/attendance.py:163
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 122
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/attendance.py:122, ./app/attendance.py:164
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 123
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/attendance.py:123, ./app/attendance.py:165
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 124
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/attendance.py:124, ./app/attendance.py:166
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 125
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/attendance.py:125, ./app/attendance.py:167
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 126
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/attendance.py:126, ./app/attendance.py:168
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 127
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/attendance.py:127, ./app/attendance.py:169
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 128
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/attendance.py:128, ./app/attendance.py:170
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 129
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/attendance.py:129, ./app/attendance.py:171
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 130
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/attendance.py:130, ./app/attendance.py:172
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 131
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/attendance.py:131, ./app/attendance.py:173
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 134
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/attendance.py:134, ./app/attendance.py:176
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 135
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/attendance.py:135, ./app/attendance.py:177
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 136
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 136
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/attendance.py:136, ./app/attendance.py:178
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 137
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/attendance.py:137, ./app/attendance.py:179
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 178
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 220-307
**Category:** Complexity
**Description:** Function `get_all_block_statuses` is 88 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 30
**Category:** Complexity
**Description:** Function `calculate_unpaid_attendance_seconds` has cyclomatic complexity of 16.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 57
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/attendance.py:57, ./app/attendance.py:132, ./app/attendance.py:174
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 58
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/attendance.py:58, ./app/attendance.py:133, ./app/attendance.py:175
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 59
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 91
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/attendance.py`
**Line Range:** 93
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 106
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/auth.py:106, ./app/auth.py:163
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 107
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/auth.py:107, ./app/auth.py:164, ./app/auth.py:180
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 117
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 126
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 129
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/auth.py:129, ./app/auth.py:169, ./app/auth.py:185
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 130
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/auth.py:130, ./app/auth.py:186
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 165
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/auth.py:165, ./app/auth.py:181
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 166
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/auth.py:166, ./app/auth.py:182
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 167
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/auth.py:167, ./app/auth.py:183
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 168
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/auth.py:168, ./app/auth.py:184
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 199
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 208
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/auth.py:208, ./app/auth.py:220
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 213
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 225
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 238
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 279
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 308
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 59-245
**Category:** Complexity
**Description:** Function `login_required` is 187 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 68-244
**Category:** Complexity
**Description:** Function `decorated_function` is 177 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/auth.py`
**Line Range:** 72
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/cli_commands.py`
**Line Range:** 38
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/cli_commands.py:38, ./app/routes/admin.py:631
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/cli_commands.py`
**Line Range:** 39
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/cli_commands.py:39, ./app/routes/admin.py:632
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/cli_commands.py`
**Line Range:** 40
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/cli_commands.py:40, ./app/routes/admin.py:633
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/cli_commands.py`
**Line Range:** 41
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/cli_commands.py:41, ./app/routes/admin.py:634
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/cli_commands.py`
**Line Range:** 42
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/cli_commands.py:42, ./app/routes/student.py:596, ./app/routes/student.py:993...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/cli_commands.py`
**Line Range:** 43
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/cli_commands.py:43, ./app/routes/admin.py:636
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/cli_commands.py`
**Line Range:** 44
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/cli_commands.py:44, ./app/routes/admin.py:637
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/cli_commands.py`
**Line Range:** 45
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/cli_commands.py:45, ./app/routes/admin.py:638
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/cli_commands.py`
**Line Range:** 46
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/cli_commands.py:46, ./app/routes/admin.py:639
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/cli_commands.py`
**Line Range:** 54
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/cli_commands.py:54, ./app/routes/admin.py:648
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/cli_commands.py`
**Line Range:** 55
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/cli_commands.py:55, ./app/routes/admin.py:649
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/cli_commands.py`
**Line Range:** 56
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/cli_commands.py:56, ./app/routes/student.py:648, ./app/routes/admin.py:650
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/cli_commands.py`
**Line Range:** 57
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/cli_commands.py:57, ./app/routes/admin.py:651
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/cli_commands.py`
**Line Range:** 58
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/cli_commands.py:58, ./app/routes/admin.py:652
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/cli_commands.py`
**Line Range:** 59
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/cli_commands.py:59, ./app/routes/admin.py:653
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/cli_commands.py`
**Line Range:** 60
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/cli_commands.py:60, ./app/routes/admin.py:654
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/forms.py`
**Line Range:** 375
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/forms.py:375, ./app/forms.py:406
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/forms.py`
**Line Range:** 376
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/forms.py:376, ./app/forms.py:407
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/forms.py`
**Line Range:** 377
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/forms.py:377, ./app/forms.py:408
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 314
**Category:** Complexity
**Description:** Function `get_checking_balance` has cyclomatic complexity of 11.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 314-409
**Category:** Complexity
**Description:** Function `get_checking_balance` is 96 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 317
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:317, ./app/models.py:414, ./app/models.py:495
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 318
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:318, ./app/models.py:415, ./app/models.py:496
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 319
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:319, ./app/models.py:416, ./app/models.py:497
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 320
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:320, ./app/models.py:417, ./app/models.py:498
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 327
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:327, ./app/models.py:424
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 328
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:328, ./app/models.py:425
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 329
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:329, ./app/models.py:426
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 330
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:330, ./app/models.py:427
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 331
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:331, ./app/models.py:428
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 332
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:332, ./app/models.py:429
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 333
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:333, ./app/models.py:430
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 334
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:334, ./app/models.py:431
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 335
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:335, ./app/models.py:432
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 336
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:336, ./app/models.py:433
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 337
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:337, ./app/models.py:434
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 338
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:338, ./app/models.py:435
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 339
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:339, ./app/models.py:436
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 340
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:340, ./app/models.py:437
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 341
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:341, ./app/models.py:438
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 342
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:342, ./app/models.py:439
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 355
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:355, ./app/models.py:452
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 362
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:362, ./app/models.py:459
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 363
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:363, ./app/models.py:460
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 364
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:364, ./app/models.py:461
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 365
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:365, ./app/models.py:462
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 372
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:372, ./app/models.py:469
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 373
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:373, ./app/models.py:470
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 374
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:374, ./app/models.py:471
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 375
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:375, ./app/models.py:472
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 376
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:376, ./app/models.py:473
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 411
**Category:** Complexity
**Description:** Function `get_savings_balance` has cyclomatic complexity of 11.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 411-490
**Category:** Complexity
**Description:** Function `get_savings_balance` is 80 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 42
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 47
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 492
**Category:** Complexity
**Description:** Function `get_total_earnings` has cyclomatic complexity of 17.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 676
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:676, ./app/models.py:1642
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 677
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:677, ./app/models.py:1643
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 678
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:678, ./app/models.py:1644
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 679
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:679, ./app/models.py:1645
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 680
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:680, ./app/models.py:1646
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/models.py`
**Line Range:** 963
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/models.py:963, ./app/models.py:1255
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 100
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 104
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/payroll.py:104, ./app/payroll.py:123
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 122
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 137
**Category:** Complexity
**Description:** Function `calculate_payroll_breakdown` has cyclomatic complexity of 12.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 137-227
**Category:** Complexity
**Description:** Function `calculate_payroll_breakdown` is 91 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 188
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 191
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 210
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 221
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 285-370
**Category:** Complexity
**Description:** Function `_get_batch_attendance_events` is 86 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 33
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/payroll.py:33, ./app/payroll.py:77
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 34
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/payroll.py:34, ./app/payroll.py:78
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 35
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/payroll.py:35, ./app/payroll.py:79
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 352
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 372
**Category:** Complexity
**Description:** Function `_calculate_seconds_in_memory` has cyclomatic complexity of 14.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 391
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 403
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 405
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 435
**Category:** Complexity
**Description:** Function `get_cached_payroll_with_meta` has cyclomatic complexity of 12.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 435-517
**Category:** Complexity
**Description:** Function `get_cached_payroll_with_meta` is 83 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 48
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/payroll.py:48, ./app/payroll.py:90
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 481
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 49
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/payroll.py:49, ./app/payroll.py:91
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 50
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/payroll.py:50, ./app/payroll.py:92
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 59
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/payroll.py:59, ./app/payroll.py:112
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 60
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/payroll.py:60, ./app/payroll.py:113
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/payroll.py`
**Line Range:** 74
**Category:** Complexity
**Description:** Function `get_daily_limit_seconds` has cyclomatic complexity of 13.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1029
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1058-1298
**Category:** Complexity
**Description:** Function `signup` is 241 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1090
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1106
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1113
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1133
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1140
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1146
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1154
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1165
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1184
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1184, ./app/routes/admin.py:1213
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1185
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1185, ./app/routes/admin.py:1214
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1186
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1186, ./app/routes/admin.py:1215
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1187
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1187, ./app/routes/admin.py:1216
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1188
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1188, ./app/routes/admin.py:1217
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1189
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1189, ./app/routes/admin.py:1218, ./app/routes/admin.py:1254
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1190
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1190, ./app/routes/admin.py:1219, ./app/routes/admin.py:1255
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1191
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1191, ./app/routes/admin.py:1220, ./app/routes/admin.py:1256
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1192
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1192, ./app/routes/admin.py:1221, ./app/routes/admin.py:1257
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1193
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1193, ./app/routes/admin.py:1222
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1194
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1194, ./app/routes/admin.py:1223
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1208
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1211
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1211, ./app/routes/admin.py:1246
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1212
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1212, ./app/routes/admin.py:1247
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1242
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1248
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1248, ./app/routes/admin.py:1580
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 129
**Category:** Risk Pattern
**Description:** Empty except block detected.
**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1303-1458
**Category:** Complexity
**Description:** Function `recover` is 156 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1316
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1336
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1339
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1358
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 136
**Category:** Risk Pattern
**Description:** Empty except block detected.
**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1398
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1404
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1465
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1465, ./app/routes/admin.py:1511, ./app/routes/admin.py:1680
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1466
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1466, ./app/routes/admin.py:1512, ./app/routes/admin.py:1681
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1506
**Category:** Complexity
**Description:** Function `reset_credentials` has cyclomatic complexity of 15.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1506-1605
**Category:** Complexity
**Description:** Function `reset_credentials` is 100 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1513
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1513, ./app/routes/admin.py:1682
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1514
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1514, ./app/routes/admin.py:1683
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1515
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1515, ./app/routes/admin.py:1684
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1516
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1516, ./app/routes/admin.py:1685
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1551
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1849-1990
**Category:** Complexity
**Description:** Function `_build_rent_privileges_by_block` is 142 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1972
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1986
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 1993
**Category:** Complexity
**Description:** Function `_get_rent_privileges_for_student` has cyclomatic complexity of 13.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2056
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2073-2262
**Category:** Complexity
**Description:** Function `students` is 190 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2096
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2148
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2159
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2174
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2196
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2202
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2202, ./app/routes/admin.py:6924
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2238
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2238, ./app/routes/admin.py:6933
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2248
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2288
**Category:** Complexity
**Description:** Function `student_detail` has cyclomatic complexity of 19.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2288-2409
**Category:** Complexity
**Description:** Function `student_detail` is 122 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2384
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2431-2678
**Category:** Complexity
**Description:** Function `edit_student` is 248 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2478
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2487
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 258-419
**Category:** Complexity
**Description:** Function `_hard_delete_join_code_scope` is 162 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2614
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2616
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2616, ./app/routes/admin.py:3107, ./app/routes/admin.py:3273
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2617
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2617, ./app/routes/admin.py:3108, ./app/routes/admin.py:3274
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2618
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2618, ./app/routes/admin.py:3109, ./app/routes/admin.py:3275
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2619
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2619, ./app/routes/admin.py:3110, ./app/routes/admin.py:3276
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2620
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2620, ./app/routes/admin.py:3111, ./app/routes/admin.py:3277
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2621
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2621, ./app/routes/admin.py:3112, ./app/routes/admin.py:3278
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2622
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2622, ./app/routes/admin.py:3113, ./app/routes/admin.py:3279
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2623
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2623, ./app/routes/admin.py:3114, ./app/routes/admin.py:3280
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2624
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2624, ./app/routes/admin.py:3115, ./app/routes/admin.py:3281
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2632
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2667
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2736
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2917
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2934
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2934, ./app/routes/admin.py:2981
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2935
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2935, ./app/routes/admin.py:2982
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2936
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2936, ./app/routes/admin.py:2983
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2995
**Category:** Complexity
**Description:** Function `add_individual_student` has cyclomatic complexity of 15.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 2995-3143
**Category:** Complexity
**Description:** Function `add_individual_student` is 149 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3005
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3005, ./app/routes/admin.py:3166
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3006
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3006, ./app/routes/admin.py:3167
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3007
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3007, ./app/routes/admin.py:3168
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3008
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3008, ./app/routes/admin.py:3169
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3009
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3009, ./app/routes/admin.py:3170
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3010
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3010, ./app/routes/admin.py:3171
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3011
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3011, ./app/routes/admin.py:3172
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3012
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3012, ./app/routes/admin.py:3173
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3013
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3013, ./app/routes/admin.py:3174
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3014
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3014, ./app/routes/admin.py:3175
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3015
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3015, ./app/routes/admin.py:3176
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3016
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3016, ./app/routes/admin.py:3177
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3017
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3017, ./app/routes/admin.py:3178, ./app/routes/admin.py:6979
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3018
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3018, ./app/routes/admin.py:3179
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3019
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3019, ./app/routes/admin.py:3180
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3020
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3020, ./app/routes/admin.py:3181
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3021
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3021, ./app/routes/admin.py:3182
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3022
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3022, ./app/routes/admin.py:3183
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3037
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3039
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3039, ./app/routes/admin.py:3198
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3040
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3040, ./app/routes/admin.py:3199
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3041
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3041, ./app/routes/admin.py:3200
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3042
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3042, ./app/routes/admin.py:3201
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3043
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3043, ./app/routes/admin.py:3202
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3044
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3044, ./app/routes/admin.py:3203
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3045
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3045, ./app/routes/admin.py:3204
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3046
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3046, ./app/routes/admin.py:3205
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3047
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3047, ./app/routes/admin.py:3206
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3048
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3048, ./app/routes/admin.py:3207
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3049
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3049, ./app/routes/admin.py:3208
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3050
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3050, ./app/routes/admin.py:3209
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3082
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3082, ./app/routes/admin.py:3232
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3083
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3083, ./app/routes/admin.py:3233
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3084
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3084, ./app/routes/admin.py:3234
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3085
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3085, ./app/routes/admin.py:3235
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3094
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3094, ./app/routes/admin.py:3260
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3095
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3095, ./app/routes/admin.py:3261
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3096
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3096, ./app/routes/admin.py:3262
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3097
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3097, ./app/routes/admin.py:3263
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3098
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3098, ./app/routes/admin.py:3264
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3099
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3099, ./app/routes/admin.py:3265
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3100
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3100, ./app/routes/admin.py:3266
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3101
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3101, ./app/routes/admin.py:3267
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3102
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3102, ./app/routes/admin.py:3268
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3103
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3103, ./app/routes/admin.py:3269
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3104
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3104, ./app/routes/admin.py:3270
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3105
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3105, ./app/routes/admin.py:3271
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3106
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3106, ./app/routes/admin.py:3272
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3110
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3120
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3120, ./app/routes/admin.py:3289
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3121
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3121, ./app/routes/admin.py:3290
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3122
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3122, ./app/routes/admin.py:3291
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3123
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3123, ./app/routes/admin.py:3292, ./app/routes/admin.py:6992
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3124
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3124, ./app/routes/admin.py:3293, ./app/routes/admin.py:6993
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3125
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3125, ./app/routes/admin.py:3294, ./app/routes/admin.py:6994
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3133
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3133, ./app/routes/admin.py:3303
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3134
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3134, ./app/routes/admin.py:3304
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3148
**Category:** Complexity
**Description:** Function `add_manual_student` has cyclomatic complexity of 18.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3148-3313
**Category:** Complexity
**Description:** Function `add_manual_student` is 166 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3196
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3276
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3320-3651
**Category:** Complexity
**Description:** Function `store_management` is 332 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3432
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3460
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3469
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3548
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3561
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3589
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3593
**Category:** Risk Pattern
**Description:** Empty except block detected.
**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3596
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3600
**Category:** Risk Pattern
**Description:** Empty except block detected.
**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3661
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3661, ./app/routes/admin.py:4733
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3662
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3662, ./app/routes/admin.py:4734
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3687
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3687, ./app/routes/admin.py:3706
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3688
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3688, ./app/routes/admin.py:3707
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3737
**Category:** Complexity
**Description:** Function `_sync_rent_items_to_store` has cyclomatic complexity of 19.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3737-3859
**Category:** Complexity
**Description:** Function `_sync_rent_items_to_store` is 123 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3760
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3779
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3785
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3797
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3830
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3840
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3895
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3907
**Category:** Risk Pattern
**Description:** Empty except block detected.
**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3916-4409
**Category:** Complexity
**Description:** Function `rent_settings` is 494 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3921
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3921, ./app/routes/admin.py:4535, ./app/routes/admin.py:7521
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3922
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3922, ./app/routes/admin.py:4536
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3923
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3923, ./app/routes/admin.py:4537
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3924
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3924, ./app/routes/admin.py:4538
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3925
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3925, ./app/routes/admin.py:4539
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3950
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3958
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3970
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3979
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 3991
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4008
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4015
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4019
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4026
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4032
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4039
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4060
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4086
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4094
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4104
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4122
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4170
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4184
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4239
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4279
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4281
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4288
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4299
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4303
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4307
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4310
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4330
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4343
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4371
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4414
**Category:** Complexity
**Description:** Function `add_rent_waiver` has cyclomatic complexity of 12.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4440
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4531-4719
**Category:** Complexity
**Description:** Function `insurance_management` is 189 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4595
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4621
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4726
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:4726, ./app/routes/admin.py:4794, ./app/routes/admin.py:4815...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4747
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4950-5166
**Category:** Complexity
**Description:** Function `process_claim` is 217 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 4968
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5101
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5108
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5111
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5114
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5130
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5150
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5181-5423
**Category:** Complexity
**Description:** Function `void_transaction` is 243 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5200
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5200, ./app/routes/admin.py:6460
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5201
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5201, ./app/routes/admin.py:6461
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5218
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5229
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5232
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5235
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5242
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5247
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5252
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5261
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5267
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5271
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5285
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5291
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5291, ./app/routes/admin.py:5325, ./app/routes/admin.py:5372
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5292
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5292, ./app/routes/admin.py:5326, ./app/routes/admin.py:5373
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5293
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5293, ./app/routes/admin.py:5327, ./app/routes/admin.py:5374
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5294
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5294, ./app/routes/admin.py:5328, ./app/routes/admin.py:5375
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5295
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5295, ./app/routes/admin.py:5329, ./app/routes/admin.py:5376
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5296
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5296, ./app/routes/admin.py:5330, ./app/routes/admin.py:5377...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5297
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5297, ./app/routes/admin.py:5331, ./app/routes/admin.py:5378...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5298
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5298, ./app/routes/admin.py:5332, ./app/routes/admin.py:5379...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5299
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5299, ./app/routes/admin.py:5333, ./app/routes/admin.py:5380...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5300
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5300, ./app/routes/admin.py:5334, ./app/routes/admin.py:5381...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5306
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5323
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5323, ./app/routes/admin.py:5370
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5324
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5324, ./app/routes/admin.py:5371
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5490
**Category:** Complexity
**Description:** Function `economy_health` has cyclomatic complexity of 20.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5490-5649
**Category:** Complexity
**Description:** Function `economy_health` is 160 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5574
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5599
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5599, ./app/routes/admin.py:8860
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5749
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5807-6065
**Category:** Complexity
**Description:** Function `payroll` is 259 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 5861
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6070
**Category:** Complexity
**Description:** Function `payroll_settings` has cyclomatic complexity of 13.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6070-6236
**Category:** Complexity
**Description:** Function `payroll_settings` is 167 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 613
**Category:** Complexity
**Description:** Function `_normalize_claim_credentials_for_admin` has cyclomatic complexity of 11.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6162
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6214
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6218
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6259
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6265
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6265, ./app/routes/admin.py:6287
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6266
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6266, ./app/routes/admin.py:6288
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6267
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6267, ./app/routes/admin.py:6289
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6268
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6268, ./app/routes/admin.py:6290
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6282
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6328
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6328, ./app/routes/admin.py:6373
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6341
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6341, ./app/routes/admin.py:6386, ./app/routes/admin.py:6822
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6472
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6472, ./app/routes/admin.py:6527
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6473
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6473, ./app/routes/admin.py:6528
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6474
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6474, ./app/routes/admin.py:6529
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6475
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6475, ./app/routes/admin.py:6530
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6476
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6476, ./app/routes/admin.py:6531
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6477
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6477, ./app/routes/admin.py:6532
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6478
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6478, ./app/routes/admin.py:6533
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6479
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6479, ./app/routes/admin.py:6534
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6480
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6480, ./app/routes/admin.py:6535
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6481
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6481, ./app/routes/admin.py:6536
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6482
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6482, ./app/routes/admin.py:6537
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6483
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6483, ./app/routes/admin.py:6538
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6484
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6484, ./app/routes/admin.py:6539
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6485
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6485, ./app/routes/admin.py:6540
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6486
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6486, ./app/routes/admin.py:6541
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6525
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6569
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6569, ./app/routes/admin.py:6618
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6570
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6570, ./app/routes/admin.py:6619
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6578
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6578, ./app/routes/admin.py:6630, ./app/routes/admin.py:6739
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6579
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6579, ./app/routes/admin.py:6631, ./app/routes/admin.py:6740
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6580
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6580
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6580, ./app/routes/admin.py:6632, ./app/routes/admin.py:6741
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6581
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6581, ./app/routes/admin.py:6633, ./app/routes/admin.py:6742
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6582
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6582, ./app/routes/admin.py:6634, ./app/routes/admin.py:6743
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6583
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6583, ./app/routes/admin.py:6635, ./app/routes/admin.py:6744
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6584
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6584, ./app/routes/admin.py:6636, ./app/routes/admin.py:6745
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6614-6710
**Category:** Complexity
**Description:** Function `payroll_apply_fine` is 97 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6627
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6627, ./app/routes/admin.py:6736
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6628
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6628, ./app/routes/admin.py:6737
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6629
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6629, ./app/routes/admin.py:6738
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6632
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6657
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6657, ./app/routes/admin.py:6768
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6658
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6658, ./app/routes/admin.py:6769
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6659
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6659, ./app/routes/admin.py:6770
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6660
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6660, ./app/routes/admin.py:6771
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6715
**Category:** Complexity
**Description:** Function `payroll_manual_payment` has cyclomatic complexity of 15.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6715-6825
**Category:** Complexity
**Description:** Function `payroll_manual_payment` is 111 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6723
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6739
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6813
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6815
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6867-7033
**Category:** Complexity
**Description:** Function `upload_students` is 167 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 687
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6904
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6912
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6952
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6971
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 6976
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7023
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7078
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7133
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 715-894
**Category:** Complexity
**Description:** Function `dashboard` is 180 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7187
**Category:** Complexity
**Description:** Function `tap_out_students` has cyclomatic complexity of 19.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7187-7329
**Category:** Complexity
**Description:** Function `tap_out_students` is 143 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7217
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7220
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7220, ./app/routes/admin.py:7248, ./app/routes/admin.py:7369
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7221
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7221, ./app/routes/admin.py:7249, ./app/routes/admin.py:7370
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7222
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7222, ./app/routes/admin.py:7250, ./app/routes/admin.py:7371
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7223
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7223, ./app/routes/admin.py:7251, ./app/routes/admin.py:7372
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7224
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7224, ./app/routes/admin.py:7252, ./app/routes/admin.py:7373
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7225
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7225, ./app/routes/admin.py:7253, ./app/routes/admin.py:7374
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7226
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7226, ./app/routes/admin.py:7254, ./app/routes/admin.py:7375
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7227
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7227, ./app/routes/admin.py:7255, ./app/routes/admin.py:7376
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7228
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7228, ./app/routes/admin.py:7377
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7236
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7236, ./app/routes/admin.py:7357, ./app/routes/admin.py:7462
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7237
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7237, ./app/routes/admin.py:7358, ./app/routes/admin.py:7463
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7238
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7238, ./app/routes/admin.py:7359, ./app/routes/admin.py:7464
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7239
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7239, ./app/routes/admin.py:7360
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7240
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7240
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7240, ./app/routes/admin.py:7361
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7241
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7241, ./app/routes/admin.py:7362
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7242
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7242, ./app/routes/admin.py:7363
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7243
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7243, ./app/routes/admin.py:7364
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7244
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7244, ./app/routes/admin.py:7365
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7245
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7245, ./app/routes/admin.py:7366
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7246
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7246
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7246, ./app/routes/admin.py:7367
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7247
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7247, ./app/routes/admin.py:7368
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7261
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7283
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7312
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7312, ./app/routes/admin.py:7411
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7334
**Category:** Complexity
**Description:** Function `tap_in_students` has cyclomatic complexity of 12.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7334-7428
**Category:** Complexity
**Description:** Function `tap_in_students` is 95 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7355
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7355, ./app/routes/admin.py:7460
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7356
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7356, ./app/routes/admin.py:7461
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7361
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7367
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7382
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7433
**Category:** Complexity
**Description:** Function `bulk_update_hall_passes` has cyclomatic complexity of 14.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7433-7511
**Category:** Complexity
**Description:** Function `bulk_update_hall_passes` is 79 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7466
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7471
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7518
**Category:** Complexity
**Description:** Function `banking` has cyclomatic complexity of 19.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7518-7704
**Category:** Complexity
**Description:** Function `banking` is 187 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7591
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7709
**Category:** Complexity
**Description:** Function `banking_settings_update` has cyclomatic complexity of 17.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7725
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7749
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7760
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7772-7874
**Category:** Complexity
**Description:** Function `deletion_requests` is 103 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7795
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7800
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7883
**Category:** Dead Code
**Description:** Unreachable code detected after return/raise/break/continue.
**Why This Matters:** Unreachable code clutters the codebase and may indicate logic errors.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7944
**Category:** Complexity
**Description:** Function `feature_settings` has cyclomatic complexity of 16.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7944-8079
**Category:** Complexity
**Description:** Function `feature_settings` is 136 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7978
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7980
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7980, ./app/routes/admin.py:8043
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7981
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7981, ./app/routes/admin.py:8044
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 7982
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7982, ./app/routes/admin.py:8045
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8003
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8003, ./app/routes/admin.py:8024
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8004
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8004, ./app/routes/admin.py:8025
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8113
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8137
**Category:** Complexity
**Description:** Function `copy_feature_settings` has cyclomatic complexity of 12.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8137-8216
**Category:** Complexity
**Description:** Function `copy_feature_settings` is 80 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8182
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8190
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8195
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8230
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8230, ./app/routes/admin.py:8287
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8231
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8231, ./app/routes/admin.py:8288
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8232
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8232, ./app/routes/admin.py:8289
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8233
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8233, ./app/routes/admin.py:8290
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8234
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8234, ./app/routes/admin.py:8291
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8235
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8235, ./app/routes/admin.py:8292
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8236
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8236, ./app/routes/admin.py:8293
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8237
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8237, ./app/routes/admin.py:8294
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8238
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8238, ./app/routes/admin.py:8295
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8239
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8239, ./app/routes/admin.py:8296
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8240
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8240, ./app/routes/admin.py:8297
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8320
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8335
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8360
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8360, ./app/routes/admin.py:8416, ./app/routes/admin.py:8449
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8361
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8361, ./app/routes/admin.py:8417, ./app/routes/admin.py:8450
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8362
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8362, ./app/routes/admin.py:8418, ./app/routes/admin.py:8451
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8363
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8363, ./app/routes/admin.py:8419, ./app/routes/admin.py:8452
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8364
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8364, ./app/routes/admin.py:8420, ./app/routes/admin.py:8453
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8365
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8365, ./app/routes/admin.py:8421, ./app/routes/admin.py:8454
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8366
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8366, ./app/routes/admin.py:8422
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8367
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8367, ./app/routes/admin.py:8423
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8368
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8368, ./app/routes/admin.py:8424
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8483
**Category:** Complexity
**Description:** Function `onboarding_status` has cyclomatic complexity of 14.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8483-8603
**Category:** Complexity
**Description:** Function `onboarding_status` is 121 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8510
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8545
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8649
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8649, ./app/routes/admin.py:8678
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8792-8905
**Category:** Complexity
**Description:** Function `api_economy_analyze` is 114 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8807
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8807, ./app/routes/admin.py:8939
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8808
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8808, ./app/routes/admin.py:8940
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8809
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8809, ./app/routes/admin.py:8941
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8810
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8810, ./app/routes/admin.py:8942
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8811
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8811, ./app/routes/admin.py:8943
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8812
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8812, ./app/routes/admin.py:8944
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8813
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8813, ./app/routes/admin.py:8945
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8814
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8814, ./app/routes/admin.py:8946
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8815
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8815, ./app/routes/admin.py:8947
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 8910-9013
**Category:** Complexity
**Description:** Function `api_economy_validate` is 104 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 899-1008
**Category:** Complexity
**Description:** Function `give_bonus_all` is 110 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 9167
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 9301
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:9301, ./app/routes/admin.py:9330, ./app/routes/admin.py:9405
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 9344
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 9359
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 944
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:944, ./app/routes/admin.py:6753
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 945
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:945, ./app/routes/admin.py:6754
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 946
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:946, ./app/routes/admin.py:6755
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 947
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:947, ./app/routes/admin.py:6645, ./app/routes/admin.py:6756
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 948
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:948, ./app/routes/admin.py:6646, ./app/routes/admin.py:6757
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 949
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:949, ./app/routes/admin.py:6647, ./app/routes/admin.py:6758
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 950
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:950, ./app/routes/admin.py:6648, ./app/routes/admin.py:6759
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 951
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 951
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:951, ./app/routes/admin.py:6649, ./app/routes/admin.py:6760
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 952
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:952, ./app/routes/admin.py:6650, ./app/routes/admin.py:6761
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 953
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:953, ./app/routes/admin.py:6651, ./app/routes/admin.py:6762
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 954
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:954, ./app/routes/admin.py:6652, ./app/routes/admin.py:6763
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 955
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:955, ./app/routes/admin.py:6653, ./app/routes/admin.py:6764
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 956
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:956, ./app/routes/admin.py:6654, ./app/routes/admin.py:6765
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 957
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:957, ./app/routes/admin.py:6655, ./app/routes/admin.py:6766
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 958
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:958, ./app/routes/admin.py:6656, ./app/routes/admin.py:6767
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 978
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:978, ./app/routes/admin.py:6677, ./app/routes/admin.py:6788
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 979
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:979, ./app/routes/admin.py:6678, ./app/routes/admin.py:6789
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 980
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:980, ./app/routes/admin.py:6679, ./app/routes/admin.py:6790
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 981
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:981, ./app/routes/admin.py:6680, ./app/routes/admin.py:6791
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 982
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:982, ./app/routes/admin.py:6681, ./app/routes/admin.py:6792
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 985
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:985, ./app/routes/admin.py:6684, ./app/routes/admin.py:6795
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 986
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:986, ./app/routes/admin.py:6685, ./app/routes/admin.py:6796
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 987
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:987, ./app/routes/admin.py:6686, ./app/routes/admin.py:6797
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 988
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:988, ./app/routes/admin.py:6687, ./app/routes/admin.py:6798
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 989
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:989, ./app/routes/admin.py:6688, ./app/routes/admin.py:6799
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 990
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:990, ./app/routes/admin.py:6689, ./app/routes/admin.py:6800
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 991
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:991, ./app/routes/admin.py:6690, ./app/routes/admin.py:6801
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/admin.py`
**Line Range:** 992
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/admin.py:992, ./app/routes/admin.py:6691, ./app/routes/admin.py:6802
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/analytics.py`
**Line Range:** 120
**Category:** Complexity
**Description:** Function `get_rent_cycle_days` has cyclomatic complexity of 12.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/analytics.py`
**Line Range:** 180
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/analytics.py`
**Line Range:** 212
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/analytics.py:212, ./app/routes/analytics.py:418, ./app/routes/analytics.py:462
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/analytics.py`
**Line Range:** 213
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/analytics.py:213, ./app/routes/analytics.py:419, ./app/routes/analytics.py:463
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/analytics.py`
**Line Range:** 214
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/analytics.py:214, ./app/routes/analytics.py:420, ./app/routes/analytics.py:464
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/analytics.py`
**Line Range:** 223
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/analytics.py:223, ./app/routes/analytics.py:291
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/analytics.py`
**Line Range:** 224
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/analytics.py:224, ./app/routes/analytics.py:292
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/analytics.py`
**Line Range:** 234
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/analytics.py:234, ./app/routes/analytics.py:355
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/analytics.py`
**Line Range:** 235
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/analytics.py:235, ./app/routes/analytics.py:356
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/analytics.py`
**Line Range:** 454
**Category:** Complexity
**Description:** Function `student_drill_down` has cyclomatic complexity of 11.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/analytics.py`
**Line Range:** 454-570
**Category:** Complexity
**Description:** Function `student_drill_down` is 117 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/analytics.py`
**Line Range:** 83
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1011
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1029
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1036
**Category:** Risk Pattern
**Description:** Empty except block detected.
**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1056
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1111-1211
**Category:** Complexity
**Description:** Function `handle_hall_pass_action` is 101 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 113
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1133
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1149
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 115
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1158
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1165
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1173
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1180
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1180, ./app/routes/api.py:1443, ./app/routes/api.py:1567
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1215-1300
**Category:** Complexity
**Description:** Function `get_active_hall_passes` is 86 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1237
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1237, ./app/routes/api.py:1664
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1238
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1238, ./app/routes/api.py:1665
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1239
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1239, ./app/routes/api.py:1666
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1240
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1240, ./app/routes/api.py:1667
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1241
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1241, ./app/routes/api.py:1668
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1242
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1242, ./app/routes/api.py:1669
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1243
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1243, ./app/routes/api.py:1670
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1244
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1244, ./app/routes/api.py:1671
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1245
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1245, ./app/routes/api.py:1672
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1246
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1246, ./app/routes/api.py:1673
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1247
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1247
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1247, ./app/routes/api.py:1674
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1255
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1255, ./app/routes/api.py:1707
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1315
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1315, ./app/routes/api.py:1740
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1316
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1316, ./app/routes/api.py:1741
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1417
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1417, ./app/routes/api.py:1468
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1418
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1418, ./app/routes/api.py:1469
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1419
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1419, ./app/routes/api.py:1470
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1420
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1420, ./app/routes/api.py:1471
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1421
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1421, ./app/routes/api.py:1472
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1422
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1422, ./app/routes/api.py:1473
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1428
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1428, ./app/routes/api.py:1552
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1429
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1429, ./app/routes/api.py:1553
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1430
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1430, ./app/routes/api.py:1554
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1431
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1431, ./app/routes/api.py:1555
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1432
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1432, ./app/routes/api.py:1556
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1433
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1433, ./app/routes/api.py:1557
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1434
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1434, ./app/routes/api.py:1558
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1435
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1435, ./app/routes/api.py:1559
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1436
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1436, ./app/routes/api.py:1560
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1437
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1437, ./app/routes/api.py:1561
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1438
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1438, ./app/routes/api.py:1562
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1439
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1439, ./app/routes/api.py:1563
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1440
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1440, ./app/routes/api.py:1564
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1441
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1441, ./app/routes/api.py:1565
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1442
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1442, ./app/routes/api.py:1566
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1444
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1444, ./app/routes/api.py:1568
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1445
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1445, ./app/routes/api.py:1569
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1446
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1446, ./app/routes/api.py:1570
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1447
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1447, ./app/routes/api.py:1571
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1448
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1448, ./app/routes/api.py:1572
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1449
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1449, ./app/routes/api.py:1573
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1481
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1481, ./app/routes/api.py:1609
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1482
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1482, ./app/routes/api.py:1610
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1483
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1483, ./app/routes/api.py:1611
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1484
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1484, ./app/routes/api.py:1612
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1485
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1485, ./app/routes/api.py:1613
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1486
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1486, ./app/routes/api.py:1614
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1487
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1487, ./app/routes/api.py:1615
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1488
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1488, ./app/routes/api.py:1616
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1489
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1489, ./app/routes/api.py:1617
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1490
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1490, ./app/routes/api.py:1618
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1491
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1491, ./app/routes/api.py:1619
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1492
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1492, ./app/routes/api.py:1620
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1493
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1493, ./app/routes/api.py:1621
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1494
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1494, ./app/routes/api.py:1622
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1495
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1495, ./app/routes/api.py:1623
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1496
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1496, ./app/routes/api.py:1624
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1516
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1516, ./app/routes/api.py:1545, ./app/routes/api.py:1600
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1538
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1538, ./app/routes/api.py:1593
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1539
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1539, ./app/routes/api.py:1594
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1540
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1540, ./app/routes/api.py:1595
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1541
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1541, ./app/routes/api.py:1596
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1542
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1542, ./app/routes/api.py:1597
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1543
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1543, ./app/routes/api.py:1598
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1544
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1544, ./app/routes/api.py:1599
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1640
**Category:** Complexity
**Description:** Function `get_hall_pass_queue` has cyclomatic complexity of 13.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1640-1765
**Category:** Complexity
**Description:** Function `get_hall_pass_queue` is 126 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1778
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1778, ./app/routes/api.py:2314
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1779
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1779, ./app/routes/api.py:2315
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1780
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1780, ./app/routes/api.py:2316
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1781
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1781, ./app/routes/api.py:2317
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1782
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1782, ./app/routes/api.py:2318
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1783
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1783, ./app/routes/api.py:2319
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1792
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1792, ./app/routes/api.py:1816
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1825
**Category:** Complexity
**Description:** Function `hall_pass_history` has cyclomatic complexity of 11.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1825-1929
**Category:** Complexity
**Description:** Function `hall_pass_history` is 105 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1835
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1835, ./app/routes/api.py:2075
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1836
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1836, ./app/routes/api.py:2076
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1861
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1861, ./app/routes/api.py:2096
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1863
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1868
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1868, ./app/routes/api.py:2103
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1869
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1869, ./app/routes/api.py:2104
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1870
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1870, ./app/routes/api.py:2105
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1872
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1882
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1882, ./app/routes/api.py:2123
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1883
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1883, ./app/routes/api.py:2124
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1884
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1884, ./app/routes/api.py:2125
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1892
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1895
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1916
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1916, ./app/routes/api.py:2177
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1917
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1917, ./app/routes/api.py:2178
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1918
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1918, ./app/routes/api.py:2179
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1919
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1919, ./app/routes/api.py:2180
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1920
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1920, ./app/routes/api.py:2181
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1921
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1921, ./app/routes/api.py:2182
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1922
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:1922, ./app/routes/api.py:2183
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1959
**Category:** Complexity
**Description:** Function `save_hall_pass_setup` has cyclomatic complexity of 16.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 1991
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2064
**Category:** Complexity
**Description:** Function `attendance_history` has cyclomatic complexity of 14.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2064-2190
**Category:** Complexity
**Description:** Function `attendance_history` is 127 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2098
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2107
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2144
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2156
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2197-2573
**Category:** Complexity
**Description:** Function `handle_tap` is 377 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 224-768
**Category:** Complexity
**Description:** Function `purchase_item` is 545 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2258
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:2258, ./app/routes/admin.py:7284
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2308
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2315
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2333
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2343
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2384
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2429
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2455
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:2455, ./app/routes/api.py:2554
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2456
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:2456, ./app/routes/api.py:2555
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2478
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2513
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2538
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2577
**Category:** Complexity
**Description:** Function `get_tap_entries` has cyclomatic complexity of 11.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2581
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:2581, ./app/routes/api.py:2652
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2582
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:2582, ./app/routes/api.py:2653
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2583
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:2583, ./app/routes/api.py:2654
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2623
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2631
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2688
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:2688, ./app/routes/api.py:3182
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2719
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:2719, ./app/routes/api.py:3217
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2735
**Category:** Complexity
**Description:** Function `check_and_auto_tapout_if_limit_reached` has cyclomatic complexity of 14.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2735-2888
**Category:** Complexity
**Description:** Function `check_and_auto_tapout_if_limit_reached` is 154 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2787
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2797
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2921
**Category:** Complexity
**Description:** Function `set_timezone` has cyclomatic complexity of 20.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2929
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:2929, ./app/routes/api.py:2946
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 293
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2930
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:2930, ./app/routes/api.py:2947
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2931
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2931
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:2931, ./app/routes/api.py:2948
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2936
**Category:** Risk Pattern
**Description:** Empty except block detected.
**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2948
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2953
**Category:** Risk Pattern
**Description:** Empty except block detected.
**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2964
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2969
**Category:** Risk Pattern
**Description:** Empty except block detected.
**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 2996-3122
**Category:** Complexity
**Description:** Function `create_demo_student` is 127 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 3143
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:3143, ./app/routes/api.py:3198
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 3144
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:3144, ./app/routes/api.py:3199
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 3165
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 320
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 3213
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 401
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 418
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 435
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 437
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 471
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 474
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 482
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 502
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 552
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:552, ./app/routes/api.py:679
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 553
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 553
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:553, ./app/routes/api.py:680
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 554
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:554, ./app/routes/api.py:681
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 555
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:555, ./app/routes/api.py:682
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 556
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:556, ./app/routes/api.py:683
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 557
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:557, ./app/routes/api.py:684
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 566
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:566, ./app/routes/api.py:692
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 567
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:567, ./app/routes/api.py:693
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 577
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:577, ./app/routes/api.py:702
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 578
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:578, ./app/routes/api.py:703
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 599
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 625
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 632
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:632, ./app/routes/api.py:648, ./app/routes/api.py:663
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 633
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:633, ./app/routes/api.py:649, ./app/routes/api.py:664
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 645
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 650
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:650, ./app/routes/api.py:665
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 682
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 726
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 731
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 754
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 773-909
**Category:** Complexity
**Description:** Function `use_item` is 137 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 843
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 846
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 850
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 896
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 915
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:915, ./app/routes/api.py:967
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 916
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:916, ./app/routes/api.py:968
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 917
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:917, ./app/routes/api.py:969
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 918
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:918, ./app/routes/api.py:970
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 919
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:919, ./app/routes/api.py:971
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 920
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:920, ./app/routes/api.py:972
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 921
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:921, ./app/routes/api.py:973
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 922
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:922, ./app/routes/api.py:974
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 923
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:923, ./app/routes/api.py:975
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 924
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:924, ./app/routes/api.py:976
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 925
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:925, ./app/routes/api.py:977
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 926
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:926, ./app/routes/api.py:978
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 927
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:927, ./app/routes/api.py:979
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 928
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:928, ./app/routes/api.py:980
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 929
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:929, ./app/routes/api.py:981
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 930
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/api.py:930, ./app/routes/api.py:982
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/api.py`
**Line Range:** 966-1104
**Category:** Complexity
**Description:** Function `reject_redemption` is 139 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/docs.py`
**Line Range:** 201-382
**Category:** Complexity
**Description:** Function `view_doc` is 182 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/docs.py`
**Line Range:** 240
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/docs.py`
**Line Range:** 245
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/docs.py`
**Line Range:** 252
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/docs.py`
**Line Range:** 266
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/docs.py`
**Line Range:** 276
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/docs.py`
**Line Range:** 325
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/docs.py`
**Line Range:** 335
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/docs.py`
**Line Range:** 338
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/docs.py`
**Line Range:** 356
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/docs.py`
**Line Range:** 386-536
**Category:** Complexity
**Description:** Function `search` is 151 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/docs.py`
**Line Range:** 413
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/main.py`
**Line Range:** 36
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/recovery.py`
**Line Range:** 120
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/recovery.py`
**Line Range:** 142
**Category:** Complexity
**Description:** Function `verify_identity` has cyclomatic complexity of 17.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/recovery.py`
**Line Range:** 142-246
**Category:** Complexity
**Description:** Function `verify_identity` is 105 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1010
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1040
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1091-1425
**Category:** Complexity
**Description:** Function `dashboard` is 335 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1149
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:1149, ./app/routes/api.py:2906
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1156
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:1156, ./app/routes/student.py:1455
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1157
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:1157, ./app/routes/student.py:1456
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1213
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1239
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1247
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:1247, ./app/routes/student.py:2914
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1255
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1260
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1329
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1509-1699
**Category:** Complexity
**Description:** Function `transfer` is 191 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1531
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1547
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1551
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1557
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:1557, ./app/routes/student.py:2003, ./app/routes/student.py:3176
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1558
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:1558, ./app/routes/student.py:2004, ./app/routes/student.py:3177
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1559
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:1559, ./app/routes/student.py:2005, ./app/routes/student.py:3178
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1560
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:1560, ./app/routes/student.py:2006, ./app/routes/student.py:3179
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1561
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:1561, ./app/routes/student.py:2007, ./app/routes/student.py:3180
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1649
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1671
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1702-1801
**Category:** Complexity
**Description:** Function `apply_savings_interest` is 100 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1759
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1773
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1776
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1779
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1808
**Category:** Complexity
**Description:** Function `insurance_marketplace` has cyclomatic complexity of 16.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1808-1918
**Category:** Complexity
**Description:** Function `insurance_marketplace` is 111 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1820
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:1820, ./app/routes/student.py:2376
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1848
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:1848, ./app/routes/student.py:1943
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1849
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:1849, ./app/routes/student.py:1944
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1850
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:1850, ./app/routes/student.py:1945
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1861
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:1861, ./app/routes/student.py:1955
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1867
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1890
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1923-2082
**Category:** Complexity
**Description:** Function `purchase_insurance` is 160 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 197
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:197, ./app/routes/admin.py:541
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1970
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 198
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:198, ./app/routes/admin.py:542
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 199
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:199, ./app/routes/admin.py:543
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1998
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:1998, ./app/routes/student.py:3171
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 1999
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:1999, ./app/routes/student.py:3172
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2000
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2000, ./app/routes/student.py:3173
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2001
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2001, ./app/routes/student.py:3174
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2002
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2002, ./app/routes/student.py:3175
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2008
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2008, ./app/routes/student.py:3181, ./app/routes/api.py:469
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2009
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2009, ./app/routes/student.py:3182, ./app/routes/api.py:470
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2054
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2054, ./app/routes/student.py:3251
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2061
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2061, ./app/routes/student.py:3258
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2062
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2062, ./app/routes/student.py:3259, ./app/routes/admin.py:983...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2063
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2063, ./app/routes/student.py:3260, ./app/routes/admin.py:984...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2064
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2064, ./app/routes/student.py:3261, ./app/routes/api.py:564...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2071
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2071, ./app/routes/student.py:3268
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2072
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2072, ./app/routes/student.py:3269, ./app/routes/admin.py:993...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2073
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2073, ./app/routes/student.py:3270, ./app/routes/admin.py:994...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2074
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2074, ./app/routes/admin.py:995, ./app/routes/admin.py:6694...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2075
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2075, ./app/routes/admin.py:996, ./app/routes/admin.py:6695...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2089
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2089, ./app/routes/student.py:2336
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2090
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2090, ./app/routes/student.py:2337
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2091
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2091, ./app/routes/student.py:2338
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2107-2329
**Category:** Complexity
**Description:** Function `file_claim` is 223 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2133
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2133, ./app/routes/admin.py:4967
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2134
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2134
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2134, ./app/routes/admin.py:4968
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2135
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2135, ./app/routes/admin.py:4969
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2136
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2136, ./app/routes/admin.py:4970
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2137
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2137, ./app/routes/admin.py:4971
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2138
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2138, ./app/routes/admin.py:4972
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2139
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2139, ./app/routes/admin.py:4973
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2140
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2140, ./app/routes/admin.py:4974
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2141
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2141, ./app/routes/admin.py:4975
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2142
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2142, ./app/routes/admin.py:4976
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2143
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2143, ./app/routes/admin.py:4977
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2144
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2144, ./app/routes/admin.py:4978
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2145
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2145, ./app/routes/admin.py:4979
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2146
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2146, ./app/routes/admin.py:4980
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2183
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2183, ./app/routes/admin.py:5057
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2230
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2235
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2241
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2252
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2266
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2270
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 229-325
**Category:** Complexity
**Description:** Function `calculate_scoped_balances` is 97 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2366-2563
**Category:** Complexity
**Description:** Function `shop` is 198 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2417
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2422
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2422, ./app/routes/api.py:284
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2423
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2423, ./app/routes/api.py:285
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2432
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2432, ./app/routes/student.py:3060
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2436
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2436, ./app/routes/api.py:293
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2437
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2437, ./app/routes/api.py:294
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2460
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2460, ./app/routes/admin.py:2032
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2476
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2476, ./app/routes/api.py:360
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2489
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2508
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2543
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2574
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2574, ./app/routes/api.py:211
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2575
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2575, ./app/routes/api.py:212
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2576
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2576, ./app/routes/api.py:213
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2577
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2577, ./app/routes/api.py:214
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2578
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2578, ./app/routes/api.py:215
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2579
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2579, ./app/routes/api.py:216
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2585
**Category:** Complexity
**Description:** Function `_calculate_rent_deadlines` has cyclomatic complexity of 16.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2585-2666
**Category:** Complexity
**Description:** Function `_calculate_rent_deadlines` is 82 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2610
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2636
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2643
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2650
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2651
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2651, ./app/routes/student.py:2659
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2680
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2680, ./app/routes/api.py:65
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2707
**Category:** Complexity
**Description:** Function `_filter_valid_rent_payments` has cyclomatic complexity of 12.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2744
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2746
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2748
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2797-2982
**Category:** Complexity
**Description:** Function `rent` is 186 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2804
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2804, ./app/routes/student.py:2989
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2805
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2805, ./app/routes/student.py:2990
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2806
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2806, ./app/routes/student.py:2991
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 281
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:281, ./app/routes/student.py:307
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2858
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2858, ./app/routes/student.py:3053
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2859
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2859, ./app/routes/student.py:3054
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2860
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2860, ./app/routes/student.py:3055
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2861
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2861, ./app/routes/student.py:3056
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2862
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2862, ./app/routes/student.py:3057
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2863
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2863, ./app/routes/student.py:3058
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2864
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2864, ./app/routes/student.py:3059
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2869
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2899
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2899, ./app/routes/student.py:3093
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2907
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2907, ./app/routes/student.py:3102
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2908
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2908, ./app/routes/student.py:3103
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2909
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2909, ./app/routes/student.py:3104
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2910
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:2910, ./app/routes/student.py:3105
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 294
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:294, ./app/routes/student.py:315
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 2987-3405
**Category:** Complexity
**Description:** Function `rent_pay` is 419 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3150
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3153
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3262
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:3262, ./app/routes/api.py:565, ./app/routes/api.py:691
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3271
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:3271, ./app/routes/api.py:574, ./app/routes/api.py:699
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3272
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:3272, ./app/routes/api.py:575, ./app/routes/api.py:700
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3273
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:3273, ./app/routes/api.py:576, ./app/routes/api.py:701
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3301
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3314
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3320
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3333
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3351
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3361
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3396
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3412-3506
**Category:** Complexity
**Description:** Function `login` is 95 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3422
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3436
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3452
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3455
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3461
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3467
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3474
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3511
**Category:** Complexity
**Description:** Function `demo_login` has cyclomatic complexity of 12.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3511-3600
**Category:** Complexity
**Description:** Function `demo_login` is 90 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3539
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3616
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3713
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:3713, ./app/routes/student.py:3745, ./app/routes/student.py:3791...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3714
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:3714, ./app/routes/student.py:3746, ./app/routes/student.py:3792...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3715
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:3715, ./app/routes/student.py:3747, ./app/routes/student.py:3793...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 373
**Category:** Complexity
**Description:** Function `complete_profile` has cyclomatic complexity of 15.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 373-537
**Category:** Complexity
**Description:** Function `complete_profile` is 165 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3742
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:3742, ./app/routes/student.py:3844
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3743
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:3743, ./app/routes/student.py:3845
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3744
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:3744, ./app/routes/student.py:3846
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3810
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:3810, ./app/routes/student.py:3866
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3811
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:3811, ./app/routes/student.py:3867
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3812
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:3812, ./app/routes/student.py:3868
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3813
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:3813, ./app/routes/student.py:3869
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3814
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:3814, ./app/routes/student.py:3870
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3910
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:3910, ./app/routes/student.py:3980
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 3911
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:3911, ./app/routes/student.py:3981
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 422
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 425
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 429
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 434
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 454
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:454, ./app/routes/student.py:528
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 455
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:455, ./app/routes/student.py:529
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 473
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 543-789
**Category:** Complexity
**Description:** Function `claim_account` is 247 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 559
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:559, ./app/routes/student.py:948
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 560
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:560, ./app/routes/student.py:949
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 566
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:566, ./app/routes/student.py:956, ./app/routes/admin.py:1105...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 567
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 574
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:574, ./app/routes/student.py:978
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 575
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:575, ./app/routes/student.py:979
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 576
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:576, ./app/routes/student.py:980
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 594
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:594, ./app/routes/student.py:991
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 595
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:595, ./app/routes/student.py:992
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 597
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:597, ./app/routes/student.py:994
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 598
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:598, ./app/routes/student.py:995
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 599
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:599, ./app/routes/student.py:996
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 600
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:600, ./app/routes/student.py:997
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 601
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:601, ./app/routes/student.py:998
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 602
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:602, ./app/routes/student.py:999
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 603
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:603, ./app/routes/student.py:1000
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 604
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:604, ./app/routes/student.py:1001
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 621
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 622
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:622, ./app/routes/student.py:1011
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 646
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 679
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 682
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:682, ./app/routes/student.py:744
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 689
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 729
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 878-1084
**Category:** Complexity
**Description:** Function `add_class` is 207 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 905
**Category:** Complexity
**Description:** Function `_get_return_target` has cyclomatic complexity of 11.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 922
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 928
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 936
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 943
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 953
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:953, ./app/routes/admin.py:1312
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 954
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:954, ./app/routes/admin.py:1313
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 955
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/student.py:955, ./app/routes/admin.py:1314
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/student.py`
**Line Range:** 957
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1017
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1017, ./app/routes/system_admin.py:1101
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1044
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1083-1172
**Category:** Complexity
**Description:** Function `delete_teacher` is 90 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1140
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1140, ./app/routes/system_admin.py:1148
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1266
**Category:** Complexity
**Description:** Function `send_reward_to_reporter` has cyclomatic complexity of 11.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1266-1349
**Category:** Complexity
**Description:** Function `send_reward_to_reporter` is 84 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1402
**Category:** Complexity
**Description:** Function `grafana_proxy` has cyclomatic complexity of 16.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1402-1570
**Category:** Complexity
**Description:** Function `grafana_proxy` is 169 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 142
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:142, ./app/routes/system_admin.py:1371
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1480
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1480, ./app/routes/system_admin.py:1528
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1481
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1481, ./app/routes/system_admin.py:1513, ./app/routes/system_admin.py:1529
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1482
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1482, ./app/routes/system_admin.py:1514, ./app/routes/system_admin.py:1530
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1618
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1618, ./app/routes/system_admin.py:1675
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1619
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1619, ./app/routes/system_admin.py:1676
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1620
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1620, ./app/routes/system_admin.py:1677
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1621
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1621, ./app/routes/system_admin.py:1678
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1622
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1622, ./app/routes/system_admin.py:1679
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1623
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1623, ./app/routes/system_admin.py:1680
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1624
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1624, ./app/routes/system_admin.py:1681
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1625
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1625, ./app/routes/system_admin.py:1682
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1626
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1626, ./app/routes/system_admin.py:1683
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1629
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1638
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1638, ./app/routes/admin.py:8324
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1639
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1639, ./app/routes/admin.py:8325
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1666
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1666, ./app/routes/system_admin.py:1718
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1667
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1667, ./app/routes/system_admin.py:1719
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1668
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1668, ./app/routes/system_admin.py:1720
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1686
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1693
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1693, ./app/routes/admin.py:8386
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1694
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1694, ./app/routes/admin.py:8387
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1695
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1695, ./app/routes/admin.py:8388
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1696
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1696, ./app/routes/admin.py:8389
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1717
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1717, ./app/routes/system_admin.py:1745
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1725
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1725, ./app/routes/admin.py:8429
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 173
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1751
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1751, ./app/routes/admin.py:8460
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1752
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1752, ./app/routes/admin.py:8461
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1753
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1753, ./app/routes/admin.py:8462
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1754
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1754, ./app/routes/admin.py:8463
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1755
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1755, ./app/routes/admin.py:8464
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1756
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1756, ./app/routes/admin.py:8465
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1757
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1757, ./app/routes/admin.py:8466
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1758
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1758, ./app/routes/admin.py:8467
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1759
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1759, ./app/routes/admin.py:8468
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1760
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1760, ./app/routes/admin.py:8469
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 1871
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 204
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:204, ./app/routes/admin.py:9020
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 205
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:205, ./app/routes/admin.py:9021
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 206
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:206, ./app/routes/admin.py:9022
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 219
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:219, ./app/routes/admin.py:9037
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 220
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:220, ./app/routes/admin.py:9038
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 221
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:221, ./app/routes/admin.py:9039
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 222
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:222, ./app/routes/admin.py:9040
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 223
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:223, ./app/routes/admin.py:9041
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 224
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:224, ./app/routes/system_admin.py:300, ./app/routes/admin.py:9042...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 225
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:225, ./app/routes/system_admin.py:301, ./app/routes/admin.py:9043...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 226
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:226, ./app/routes/admin.py:9044
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 227
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:227, ./app/routes/admin.py:9045
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 228
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:228, ./app/routes/admin.py:9046
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 229
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:229, ./app/routes/admin.py:9047
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 237
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:237, ./app/routes/admin.py:9055
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 238
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:238, ./app/routes/admin.py:9056
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 239
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:239, ./app/routes/admin.py:9057
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 249
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:249, ./app/routes/admin.py:9067
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 257
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:257, ./app/routes/admin.py:9075
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 258
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:258, ./app/routes/admin.py:9076
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 259
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:259, ./app/routes/admin.py:9077
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 260
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:260, ./app/routes/admin.py:9078
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 261
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:261, ./app/routes/admin.py:9079
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 262
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:262, ./app/routes/admin.py:9080
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 263
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:263, ./app/routes/admin.py:9081
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 264
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:264, ./app/routes/admin.py:9082
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 265
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:265, ./app/routes/admin.py:9083
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 266
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:266, ./app/routes/admin.py:9084
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 267
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:267, ./app/routes/admin.py:9085
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 274
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:274, ./app/routes/admin.py:9092
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 275
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:275, ./app/routes/admin.py:9093
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 276
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:276, ./app/routes/admin.py:9094
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 277
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:277, ./app/routes/admin.py:9095
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 278
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:278, ./app/routes/admin.py:9096
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 279
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:279, ./app/routes/admin.py:9097
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 280
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:280, ./app/routes/admin.py:9098
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 281
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:281, ./app/routes/admin.py:9099
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 282
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:282, ./app/routes/admin.py:9100
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 283
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:283, ./app/routes/admin.py:9101
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 284
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:284, ./app/routes/admin.py:9102
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 296
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:296, ./app/routes/admin.py:9114
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 297
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:297, ./app/routes/admin.py:9115
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 298
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:298, ./app/routes/admin.py:9116
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 299
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:299, ./app/routes/admin.py:9117
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 302
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:302, ./app/routes/admin.py:9120
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 303
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:303, ./app/routes/admin.py:9121
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 304
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:304, ./app/routes/admin.py:9122
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 305
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:305, ./app/routes/admin.py:9123
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 312
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:312, ./app/routes/admin.py:9130
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 313
**Category:** Complexity
**Description:** Function `passkey_auth_finish` has cyclomatic complexity of 12.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 313
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:313, ./app/routes/admin.py:9131
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 314
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:314, ./app/routes/admin.py:9132
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 315
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:315, ./app/routes/admin.py:9133
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 316
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:316, ./app/routes/admin.py:9134
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 317
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:317, ./app/routes/admin.py:9135
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 318
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:318, ./app/routes/admin.py:9136
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 319
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:319, ./app/routes/admin.py:9137
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 320
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:320, ./app/routes/admin.py:9138
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 321
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:321, ./app/routes/admin.py:9139
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 322
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:322, ./app/routes/admin.py:9140
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 341
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:341, ./app/routes/admin.py:9159
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 342
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:342, ./app/routes/admin.py:9160
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 349
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 370
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:370, ./app/routes/admin.py:9184
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 371
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:371, ./app/routes/admin.py:9185
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 391
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:391, ./app/routes/admin.py:9207
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 405
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:405, ./app/routes/admin.py:9221
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 406
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:406, ./app/routes/admin.py:9222
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 413
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:413, ./app/routes/admin.py:9229
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 414
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:414, ./app/routes/admin.py:9230
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 415
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:415, ./app/routes/admin.py:9231
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 487
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 532
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:532, ./app/routes/system_admin.py:593
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 861
**Category:** Complexity
**Description:** Function `teacher_overview` has cyclomatic complexity of 13.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 861-986
**Category:** Complexity
**Description:** Function `teacher_overview` is 126 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 943
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 965
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/routes/system_admin.py`
**Line Range:** 991-1078
**Category:** Complexity
**Description:** Function `delete_period` is 88 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 107
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 12
**Category:** Complexity
**Description:** Function `enforce_daily_limits_job` has cyclomatic complexity of 12.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 151
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:151, ./scripts/cleanup_orphaned_store_blocks.py:18
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 152
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:152, ./scripts/cleanup_orphaned_store_blocks.py:19
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 153
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:153, ./scripts/cleanup_orphaned_store_blocks.py:20
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 154
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:154, ./scripts/cleanup_orphaned_store_blocks.py:21
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 155
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:155, ./scripts/cleanup_orphaned_store_blocks.py:22
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 156
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:156, ./scripts/cleanup_orphaned_store_blocks.py:23
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 157
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:157, ./scripts/cleanup_orphaned_store_blocks.py:24
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 158
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:158, ./scripts/cleanup_orphaned_store_blocks.py:25
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 159
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:159, ./scripts/cleanup_orphaned_store_blocks.py:26
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 160
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:160, ./scripts/cleanup_orphaned_store_blocks.py:27
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 161
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:161, ./scripts/cleanup_orphaned_store_blocks.py:28
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 162
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:162, ./scripts/cleanup_orphaned_store_blocks.py:29
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 163
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:163, ./scripts/cleanup_orphaned_store_blocks.py:30
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 164
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:164, ./scripts/cleanup_orphaned_store_blocks.py:31
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 165
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:165, ./scripts/cleanup_orphaned_store_blocks.py:32
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 166
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:166, ./scripts/cleanup_orphaned_store_blocks.py:33
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 167
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:167, ./scripts/cleanup_orphaned_store_blocks.py:34
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 168
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:168, ./scripts/cleanup_orphaned_store_blocks.py:35
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 169
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:169, ./scripts/cleanup_orphaned_store_blocks.py:36
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 179
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:179, ./scripts/cleanup_orphaned_store_blocks.py:57
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 180
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:180, ./scripts/cleanup_orphaned_store_blocks.py:58
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 181
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:181, ./scripts/cleanup_orphaned_store_blocks.py:59
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 182
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:182, ./scripts/cleanup_orphaned_store_blocks.py:60
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 183
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:183, ./scripts/cleanup_orphaned_store_blocks.py:61
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 184
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:184, ./scripts/cleanup_orphaned_store_blocks.py:62
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 185
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:185, ./scripts/cleanup_orphaned_store_blocks.py:63
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 30
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:30, ./app/routes/admin.py:681
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 33
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 38
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:38, ./app/routes/admin.py:687
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 39
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:39, ./app/routes/admin.py:688
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 40
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:40, ./app/routes/admin.py:689
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/scheduled_tasks.py`
**Line Range:** 42
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:42, ./app/routes/admin.py:7138
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/analytics_engine.py`
**Line Range:** 13
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/utils/analytics_engine.py:13, ./app/utils/analytics_engine.py:441
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/analytics_engine.py`
**Line Range:** 313
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/analytics_engine.py`
**Line Range:** 315
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/analytics_engine.py`
**Line Range:** 537-658
**Category:** Complexity
**Description:** Function `create_snapshot` is 122 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/analytics_engine.py`
**Line Range:** 638
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 10-224
**Category:** Complexity
**Description:** Function `settle_balances` is 215 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 106
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/utils/banking.py:106, ./app/routes/student.py:308
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 120
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/utils/banking.py:120, ./app/routes/student.py:316
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 144
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 160
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 163
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 168
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 183
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/utils/banking.py:183, ./app/utils/banking.py:201
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 184
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 184
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/utils/banking.py:184, ./app/utils/banking.py:202
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 185
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/utils/banking.py:185, ./app/utils/banking.py:203
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 186
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/utils/banking.py:186, ./app/utils/banking.py:204
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 196
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 198
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 202
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 31
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/utils/banking.py:31, ./app/utils/banking.py:51
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 42
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 68
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/utils/banking.py:68, ./app/utils/banking.py:88
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 79
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/utils/banking.py:79, ./app/utils/banking.py:131
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 80
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/utils/banking.py:80, ./app/utils/banking.py:132
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 81
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/utils/banking.py:81, ./app/utils/banking.py:133
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 82
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/utils/banking.py:82, ./app/utils/banking.py:134
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/banking.py`
**Line Range:** 83
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/utils/banking.py:83, ./app/utils/banking.py:135
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 136
**Category:** Complexity
**Description:** Function `_normalize_to_weekly` has cyclomatic complexity of 11.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 242
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/utils/economy_balance.py:242, ./app/utils/economy_balance.py:312, ./app/utils/economy_balance.py:451...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 243
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/utils/economy_balance.py:243, ./app/utils/economy_balance.py:313, ./app/utils/economy_balance.py:452...
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 306
**Category:** Complexity
**Description:** Function `check_insurance_balance` has cyclomatic complexity of 16.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 306-443
**Category:** Complexity
**Description:** Function `check_insurance_balance` is 138 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 341
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 352
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 385
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 438
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 440
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 475
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 486
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 544
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 561
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 586
**Category:** Complexity
**Description:** Function `validate_rent_value` has cyclomatic complexity of 16.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 586-697
**Category:** Complexity
**Description:** Function `validate_rent_value` is 112 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 638
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 699
**Category:** Complexity
**Description:** Function `validate_insurance_value` has cyclomatic complexity of 14.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 699-819
**Category:** Complexity
**Description:** Function `validate_insurance_value` is 121 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 724
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 782
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 786
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 886
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 960
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 983
**Category:** Complexity
**Description:** Function `analyze_economy` has cyclomatic complexity of 11.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/economy_balance.py`
**Line Range:** 983-1062
**Category:** Complexity
**Description:** Function `analyze_economy` is 80 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/help_content.py`
**Line Range:** 116
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./app/utils/help_content.py:116, ./app/utils/help_content.py:204
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/helpers.py`
**Line Range:** 40
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/helpers.py`
**Line Range:** 44
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/ip_handler.py`
**Line Range:** 127
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/ip_handler.py`
**Line Range:** 198
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/issue_helpers.py`
**Line Range:** 99-175
**Category:** Complexity
**Description:** Function `create_issue` is 77 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/overdraft.py`
**Line Range:** 37-126
**Category:** Complexity
**Description:** Function `charge_overdraft_fee_if_needed` is 90 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/overdraft.py`
**Line Range:** 72
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/overdraft.py`
**Line Range:** 79
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/overdraft.py`
**Line Range:** 86
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/turnstile.py`
**Line Range:** 13
**Category:** Complexity
**Description:** Function `verify_turnstile_token` has cyclomatic complexity of 11.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./app/utils/turnstile.py`
**Line Range:** 13-88
**Category:** Complexity
**Description:** Function `verify_turnstile_token` is 76 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./cleanup_duplicate_tapouts.py`
**Line Range:** 130
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./cleanup_duplicate_tapouts.py`
**Line Range:** 82
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./fix_db_version.py`
**Line Range:** 1
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./fix_db_version.py:1, ./scripts/setup_migration_db.py:4
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./fix_db_version.py`
**Line Range:** 2
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./fix_db_version.py:2, ./scripts/setup_migration_db.py:5
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/add-github-actions-to-firewall.py`
**Line Range:** 107
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/add-github-actions-to-firewall.py`
**Line Range:** 50
**Category:** Complexity
**Description:** Function `main` has cyclomatic complexity of 11.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/add-github-actions-to-firewall.py`
**Line Range:** 50-130
**Category:** Complexity
**Description:** Function `main` is 81 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/add-pulsetic.py`
**Line Range:** 22
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/add-pulsetic.py:22, ./scripts/add-github-actions-to-firewall.py:49
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/add-pulsetic.py`
**Line Range:** 23
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/add-pulsetic.py:23, ./scripts/add-github-actions-to-firewall.py:50
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/add-pulsetic.py`
**Line Range:** 24
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/add-pulsetic.py:24, ./scripts/add-github-actions-to-firewall.py:51
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/add-pulsetic.py`
**Line Range:** 25
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/add-pulsetic.py:25, ./scripts/add-github-actions-to-firewall.py:52
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/add-pulsetic.py`
**Line Range:** 26
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/add-pulsetic.py:26, ./scripts/add-github-actions-to-firewall.py:53
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/add-pulsetic.py`
**Line Range:** 27
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/add-pulsetic.py:27, ./scripts/add-github-actions-to-firewall.py:54
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 102
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/analyze_migrations.py:102, ./scripts/verify_chain.py:66
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 103
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/analyze_migrations.py:103, ./scripts/verify_chain.py:67
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 104
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/analyze_migrations.py:104, ./scripts/verify_chain.py:68
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 105
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/analyze_migrations.py:105, ./scripts/verify_chain.py:69
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 106
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 14
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/analyze_migrations.py:14, ./scripts/verify_chain.py:8
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 147
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 15
**Category:** Complexity
**Description:** Function `parse_migration_file` has cyclomatic complexity of 14.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 15
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/analyze_migrations.py:15, ./scripts/verify_chain.py:9
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 161
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 166
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 200
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 215
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/analyze_migrations.py:215, ./scripts/verify_chain.py:175
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 39
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 53
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 56
**Category:** Risk Pattern
**Description:** Empty except block detected.
**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 63
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 66
**Category:** Risk Pattern
**Description:** Empty except block detected.
**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 80-212
**Category:** Complexity
**Description:** Function `analyze_migrations` is 133 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/backfill_join_codes.py`
**Line Range:** 115
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/backfill_join_codes.py`
**Line Range:** 38
**Category:** Complexity
**Description:** Function `backfill_join_codes` has cyclomatic complexity of 12.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/backfill_join_codes.py`
**Line Range:** 38-123
**Category:** Complexity
**Description:** Function `backfill_join_codes` is 86 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/backfill_join_codes.py`
**Line Range:** 66
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/backfill_join_codes.py`
**Line Range:** 84
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/backfill_join_codes.py`
**Line Range:** 98
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/check_migration.py`
**Line Range:** 29
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_duplicates_flask.py`
**Line Range:** 100
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_duplicates_flask.py`
**Line Range:** 124
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_duplicates_flask.py`
**Line Range:** 27
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:27, ./scripts/cleanup_duplicates_flask.py:92
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_duplicates_flask.py`
**Line Range:** 28
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:28, ./scripts/cleanup_duplicates_flask.py:93
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_duplicates_flask.py`
**Line Range:** 29
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:29, ./scripts/cleanup_duplicates_flask.py:94
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_duplicates_flask.py`
**Line Range:** 30
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:30, ./scripts/cleanup_duplicates_flask.py:95
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_duplicates_flask.py`
**Line Range:** 31
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:31, ./scripts/cleanup_duplicates_flask.py:96
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_duplicates_flask.py`
**Line Range:** 32
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:32, ./scripts/cleanup_duplicates_flask.py:97
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_duplicates_flask.py`
**Line Range:** 33
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:33, ./scripts/cleanup_duplicates_flask.py:98
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_duplicates_flask.py`
**Line Range:** 34
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:34, ./scripts/cleanup_duplicates_flask.py:99
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_duplicates_flask.py`
**Line Range:** 35
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_duplicates_flask.py`
**Line Range:** 35
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:35, ./scripts/cleanup_duplicates_flask.py:100
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_duplicates_flask.py`
**Line Range:** 36
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:36, ./scripts/cleanup_duplicates_flask.py:101
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_duplicates_flask.py`
**Line Range:** 37
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:37, ./scripts/cleanup_duplicates_flask.py:102
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_duplicates_flask.py`
**Line Range:** 38
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:38, ./scripts/cleanup_duplicates_flask.py:103
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_duplicates_flask.py`
**Line Range:** 39
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:39, ./scripts/cleanup_duplicates_flask.py:104
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_duplicates_flask.py`
**Line Range:** 61
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_duplicates_flask.py`
**Line Range:** 90
**Category:** Complexity
**Description:** Function `delete_duplicates` has cyclomatic complexity of 17.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_duplicates_flask.py`
**Line Range:** 90-198
**Category:** Complexity
**Description:** Function `delete_duplicates` is 109 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/cleanup_invite_codes.py`
**Line Range:** 25
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 114-277
**Category:** Complexity
**Description:** Function `migrate_legacy_students` is 164 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 138
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:138, ./scripts/comprehensive_legacy_migration.py:638
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 139
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:139, ./scripts/comprehensive_legacy_migration.py:639
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 201
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 229
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:229, ./scripts/comprehensive_legacy_migration.py:345
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 230
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:230, ./scripts/comprehensive_legacy_migration.py:346
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 231
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:231, ./scripts/comprehensive_legacy_migration.py:347
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 232
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:232, ./scripts/comprehensive_legacy_migration.py:348
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 233
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:233, ./scripts/comprehensive_legacy_migration.py:349
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 234
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:234, ./scripts/comprehensive_legacy_migration.py:350
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 235
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 235
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:235, ./scripts/comprehensive_legacy_migration.py:351
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 236
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:236, ./scripts/comprehensive_legacy_migration.py:352
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 237
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:237, ./scripts/comprehensive_legacy_migration.py:353
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 238
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:238, ./scripts/comprehensive_legacy_migration.py:354
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 239
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:239, ./scripts/comprehensive_legacy_migration.py:355
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 240
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:240, ./scripts/comprehensive_legacy_migration.py:356
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 241
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:241, ./scripts/comprehensive_legacy_migration.py:357
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 242
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 242
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:242, ./scripts/comprehensive_legacy_migration.py:358
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 243
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:243, ./scripts/comprehensive_legacy_migration.py:359
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 244
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:244, ./scripts/comprehensive_legacy_migration.py:360
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 245
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:245, ./scripts/comprehensive_legacy_migration.py:361
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 254
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 280
**Category:** Complexity
**Description:** Function `backfill_teacher_block_join_codes` has cyclomatic complexity of 14.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 280-373
**Category:** Complexity
**Description:** Function `backfill_teacher_block_join_codes` is 94 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 329
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 351
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 358
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 491
**Category:** Complexity
**Description:** Function `backfill_related_tables` has cyclomatic complexity of 14.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 491-619
**Category:** Complexity
**Description:** Function `backfill_related_tables` is 129 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 536
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 545
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 552
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 593
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 608
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 622-699
**Category:** Complexity
**Description:** Function `verify_migration` is 78 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 654
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 739
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/comprehensive_legacy_migration.py`
**Line Range:** 752
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create-github-actions-firewall.py`
**Line Range:** 10
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create-github-actions-firewall.py:10, ./scripts/add-github-actions-to-firewall.py:10
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create-github-actions-firewall.py`
**Line Range:** 103
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create-github-actions-firewall.py`
**Line Range:** 114
**Category:** Complexity
**Description:** Function `main` has cyclomatic complexity of 11.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create-github-actions-firewall.py`
**Line Range:** 147
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create-github-actions-firewall.py`
**Line Range:** 16
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create-github-actions-firewall.py:16, ./scripts/add-github-actions-to-firewall.py:17
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create-github-actions-firewall.py`
**Line Range:** 43
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create-github-actions-firewall.py:43, ./scripts/add-github-actions-to-firewall.py:43
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create-github-actions-firewall.py`
**Line Range:** 44
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create-github-actions-firewall.py:44, ./scripts/add-github-actions-to-firewall.py:44
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 163
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 174
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 197
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 203
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 48
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:48, ./scripts/create_admin.py:105
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 55
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:55, ./scripts/create_admin.py:112
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 56
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:56, ./scripts/create_admin.py:113
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 63
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:63, ./scripts/create_admin.py:120
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 64
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:64, ./scripts/create_admin.py:121
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 65
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:65, ./scripts/create_admin.py:122
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 66
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:66, ./scripts/create_admin.py:123
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 67
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:67, ./scripts/create_admin.py:124
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 68
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:68, ./scripts/create_admin.py:125
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 75
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:75, ./scripts/create_admin.py:132
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 76
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:76, ./scripts/create_admin.py:133
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 77
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:77, ./scripts/create_admin.py:134
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 78
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:78, ./scripts/create_admin.py:135
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 79
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:79, ./scripts/create_admin.py:136
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 80
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:80, ./scripts/create_admin.py:137
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 81
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:81, ./scripts/create_admin.py:138
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 82
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:82, ./scripts/create_admin.py:139
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 89
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:89, ./scripts/create_admin.py:146
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 90
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:90, ./scripts/create_admin.py:147
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 91
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:91, ./scripts/create_admin.py:148
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/create_admin.py`
**Line Range:** 92
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:92, ./scripts/create_admin.py:149
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/debug_student_state.py`
**Line Range:** 100
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/debug_student_state.py`
**Line Range:** 138
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/debug_student_state.py`
**Line Range:** 15
**Category:** Complexity
**Description:** Function `debug_student_state` has cyclomatic complexity of 13.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/debug_student_state.py`
**Line Range:** 15-173
**Category:** Complexity
**Description:** Function `debug_student_state` is 159 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/debug_student_state.py`
**Line Range:** 77
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/debug_student_state.py`
**Line Range:** 79
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/debug_student_state.py`
**Line Range:** 98
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/diagnose_migrations.py`
**Line Range:** 11
**Category:** Complexity
**Description:** Function `check_migration_files` has cyclomatic complexity of 11.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/diagnose_migrations.py`
**Line Range:** 110
**Category:** Complexity
**Description:** Function `main` has cyclomatic complexity of 12.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/diagnose_migrations.py`
**Line Range:** 147
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/diagnose_migrations.py`
**Line Range:** 32
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/diagnose_migrations.py`
**Line Range:** 44
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/diagnose_migrations.py`
**Line Range:** 58
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/diagnose_migrations.py`
**Line Range:** 95
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database.py`
**Line Range:** 48
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 10
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:10, ./scripts/dev-utilities/reset_database.py:10
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 105
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:105, ./scripts/dev-utilities/reset_database.py:88
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 106
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:106, ./scripts/dev-utilities/reset_database.py:89
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 107
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:107, ./scripts/dev-utilities/reset_database.py:90
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 108
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:108, ./scripts/dev-utilities/reset_database.py:91
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 109
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:109, ./scripts/dev-utilities/reset_database.py:92
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 11
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:11, ./scripts/dev-utilities/reset_database.py:11
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 110
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:110, ./scripts/dev-utilities/reset_database.py:93
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 111
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:111, ./scripts/dev-utilities/reset_database.py:94
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 112
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:112, ./scripts/dev-utilities/reset_database.py:95
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 113
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:113, ./scripts/dev-utilities/reset_database.py:96
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 114
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:114, ./scripts/dev-utilities/reset_database.py:97
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 115
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:115, ./scripts/dev-utilities/reset_database.py:98
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 116
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:116, ./scripts/dev-utilities/reset_database.py:99
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 117
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:117, ./scripts/dev-utilities/reset_database.py:100
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 118
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:118, ./scripts/dev-utilities/reset_database.py:101
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 119
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:119, ./scripts/dev-utilities/reset_database.py:102
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 12
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:12, ./scripts/dev-utilities/reset_database.py:12
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 120
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:120, ./scripts/dev-utilities/reset_database.py:103
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 121
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:121, ./scripts/dev-utilities/reset_database.py:104
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 122
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:122, ./scripts/dev-utilities/reset_database.py:105
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 123
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:123, ./scripts/dev-utilities/reset_database.py:106
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 124
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:124, ./scripts/dev-utilities/reset_database.py:107
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 125
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:125, ./scripts/dev-utilities/reset_database.py:108
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 126
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:126, ./scripts/dev-utilities/reset_database.py:109
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 127
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:127, ./scripts/dev-utilities/reset_database.py:110
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 128
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:128, ./scripts/dev-utilities/reset_database.py:111
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 129
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:129, ./scripts/dev-utilities/reset_database.py:112
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 13
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:13, ./scripts/dev-utilities/reset_database.py:13
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 130
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:130, ./scripts/dev-utilities/reset_database.py:113
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 131
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:131, ./scripts/dev-utilities/reset_database.py:114
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 132
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:132, ./scripts/dev-utilities/reset_database.py:115
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 133
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:133, ./scripts/dev-utilities/reset_database.py:116
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 134
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:134, ./scripts/dev-utilities/reset_database.py:117
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 135
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:135, ./scripts/dev-utilities/reset_database.py:118
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 136
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:136, ./scripts/dev-utilities/reset_database.py:119
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 137
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:137, ./scripts/dev-utilities/reset_database.py:120
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 138
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:138, ./scripts/dev-utilities/reset_database.py:121
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 14
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:14, ./scripts/dev-utilities/reset_database.py:14
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 15
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:15, ./scripts/dev-utilities/reset_database.py:15
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 16
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:16, ./scripts/dev-utilities/reset_database.py:16
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 17
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:17, ./scripts/dev-utilities/reset_database.py:17
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 18
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:18, ./scripts/dev-utilities/reset_database.py:18
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 19
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:19, ./scripts/dev-utilities/reset_database.py:19
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 20
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:20, ./scripts/dev-utilities/reset_database.py:20
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 30
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:30, ./scripts/dev-utilities/reset_database.py:29
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 31
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:31, ./scripts/dev-utilities/reset_database.py:30
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 32
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:32, ./scripts/dev-utilities/reset_database.py:31
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 33
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:33, ./scripts/dev-utilities/reset_database.py:32
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 34
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:34, ./scripts/dev-utilities/reset_database.py:33
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 52
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 62
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 69
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:69, ./scripts/dev-utilities/reset_database.py:61
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 70
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:70, ./scripts/dev-utilities/reset_database.py:62
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 71
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:71, ./scripts/dev-utilities/reset_database.py:63
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 72
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:72, ./scripts/dev-utilities/reset_database.py:64
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 73
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:73, ./scripts/dev-utilities/reset_database.py:65
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 74
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:74, ./scripts/dev-utilities/reset_database.py:66
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 89
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:89, ./scripts/dev-utilities/reset_database.py:77
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 9
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:9, ./scripts/dev-utilities/reset_database.py:9
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 90
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:90, ./scripts/dev-utilities/reset_database.py:78
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 91
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:91, ./scripts/dev-utilities/reset_database.py:79
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 92
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:92, ./scripts/dev-utilities/reset_database.py:80
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/dev-utilities/reset_database_no_schema.py`
**Line Range:** 93
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:93, ./scripts/dev-utilities/reset_database.py:81
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 10
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:10, ./scripts/pulsetic_firewall.py:10
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 131
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:131, ./scripts/pulsetic_firewall.py:135
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 132
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:132, ./scripts/pulsetic_firewall.py:136
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 133
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:133, ./scripts/pulsetic_firewall.py:137
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 134
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:134, ./scripts/pulsetic_firewall.py:138
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 135
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:135, ./scripts/pulsetic_firewall.py:139
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 136
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:136, ./scripts/pulsetic_firewall.py:140
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 137
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:137, ./scripts/pulsetic_firewall.py:141
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 175
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:175, ./scripts/pulsetic_firewall.py:164
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 176
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:176, ./scripts/pulsetic_firewall.py:165
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 177
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:177, ./scripts/pulsetic_firewall.py:166
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 178
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:178, ./scripts/pulsetic_firewall.py:167
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 187
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:187, ./scripts/pulsetic_firewall.py:180
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 188
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:188, ./scripts/pulsetic_firewall.py:181
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 189
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:189, ./scripts/pulsetic_firewall.py:182
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 190
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:190, ./scripts/pulsetic_firewall.py:183
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 191
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:191, ./scripts/pulsetic_firewall.py:184
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 192
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:192, ./scripts/pulsetic_firewall.py:185
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 193
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:193, ./scripts/pulsetic_firewall.py:186
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 217
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:217, ./scripts/pulsetic_firewall.py:205
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 218
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:218, ./scripts/pulsetic_firewall.py:206
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 22
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:22, ./scripts/pulsetic_firewall.py:26
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 23
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:23, ./scripts/pulsetic_firewall.py:27
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 24
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:24, ./scripts/pulsetic_firewall.py:28
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 25
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:25, ./scripts/pulsetic_firewall.py:29
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 26
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:26, ./scripts/pulsetic_firewall.py:30
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 27
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:27, ./scripts/pulsetic_firewall.py:31
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 28
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:28, ./scripts/pulsetic_firewall.py:32
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 29
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:29, ./scripts/pulsetic_firewall.py:33
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 30
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:30, ./scripts/pulsetic_firewall.py:34
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 31
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:31, ./scripts/pulsetic_firewall.py:35
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 32
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:32, ./scripts/pulsetic_firewall.py:36
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 33
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:33, ./scripts/pulsetic_firewall.py:37
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 34
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:34, ./scripts/pulsetic_firewall.py:38
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 41
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:41, ./scripts/pulsetic_firewall.py:51
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 8
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:8, ./scripts/pulsetic_firewall.py:8
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/firewall_complete.py`
**Line Range:** 9
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:9, ./scripts/pulsetic_firewall.py:9
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/fix_alembic_version.py`
**Line Range:** 22
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/fix_missing_student_teacher_associations.py`
**Line Range:** 46
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/fix_teacher_id_nulls.py`
**Line Range:** 58
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/fix_teacher_id_nulls.py`
**Line Range:** 66
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/inspect_join_code_columns.py`
**Line Range:** 102
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/inspect_join_code_columns.py`
**Line Range:** 113
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/inspect_join_code_columns.py`
**Line Range:** 124
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/inspect_join_code_columns.py`
**Line Range:** 135
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/inspect_join_code_columns.py`
**Line Range:** 153
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/inspect_join_code_columns.py`
**Line Range:** 164
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/inspect_join_code_columns.py`
**Line Range:** 179
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/inspect_join_code_columns.py`
**Line Range:** 188
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/inspect_join_code_columns.py`
**Line Range:** 54-198
**Category:** Complexity
**Description:** Function `inspect_database_schema` is 145 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/inspect_join_code_columns.py`
**Line Range:** 76
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/lint_migrations.py`
**Line Range:** 147
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/lint_migrations.py`
**Line Range:** 208
**Category:** Complexity
**Description:** Function `main` has cyclomatic complexity of 20.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/lint_migrations.py`
**Line Range:** 208-336
**Category:** Complexity
**Description:** Function `main` is 129 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/lint_migrations.py`
**Line Range:** 276
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/lint_migrations.py`
**Line Range:** 280
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/lint_migrations.py`
**Line Range:** 305
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/lint_migrations.py`
**Line Range:** 307
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/lint_migrations.py`
**Line Range:** 312
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/lint_migrations.py`
**Line Range:** 314
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/manage_invites.py`
**Line Range:** 120
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/manage_invites.py`
**Line Range:** 32
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/manage_invites.py:32, ./scripts/manage_invites.py:80
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/manage_invites.py`
**Line Range:** 35
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/manage_invites.py`
**Line Range:** 63
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/manage_invites.py`
**Line Range:** 68
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/manage_invites.py`
**Line Range:** 83
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/pulsetic_firewall.py`
**Line Range:** 67
**Category:** Complexity
**Description:** Function `load_token` has cyclomatic complexity of 13.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/pulsetic_firewall.py`
**Line Range:** 86
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/seed_multi_tenancy_test_data.py`
**Line Range:** 125
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/seed_multi_tenancy_test_data.py:125, ./scripts/seed_multi_tenancy_test_data.py:134
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/seed_multi_tenancy_test_data.py`
**Line Range:** 283
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/seed_multi_tenancy_test_data.py`
**Line Range:** 309
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/seed_multi_tenancy_test_data.py`
**Line Range:** 321
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/seed_multi_tenancy_test_data.py`
**Line Range:** 361
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/seed_multi_tenancy_test_data.py`
**Line Range:** 368
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/seed_multi_tenancy_test_data.py`
**Line Range:** 518
**Category:** Complexity
**Description:** Function `seed_database` has cyclomatic complexity of 15.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/seed_multi_tenancy_test_data.py`
**Line Range:** 518-792
**Category:** Complexity
**Description:** Function `seed_database` is 275 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/seed_multi_tenancy_test_data.py`
**Line Range:** 610
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/seed_multi_tenancy_test_data.py`
**Line Range:** 658
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/seed_multi_tenancy_test_data.py`
**Line Range:** 736
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/validate-migrations.py`
**Line Range:** 122
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/validate-migrations.py`
**Line Range:** 127
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/validate-migrations.py`
**Line Range:** 135
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/validate-migrations.py`
**Line Range:** 235-394
**Category:** Complexity
**Description:** Function `validate_migrations` is 160 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/validate-migrations.py`
**Line Range:** 251
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/validate-migrations.py`
**Line Range:** 257
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/validate-migrations.py`
**Line Range:** 288
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/validate-migrations.py`
**Line Range:** 307
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/validate-migrations.py`
**Line Range:** 332
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/validate-migrations.py`
**Line Range:** 47
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/validate-migrations.py`
**Line Range:** 78
**Category:** Complexity
**Description:** Function `check_idempotency` has cyclomatic complexity of 16.
**Why This Matters:** High complexity indicates hard-to-test logic.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/validate-migrations.py`
**Line Range:** 78-170
**Category:** Complexity
**Description:** Function `check_idempotency` is 93 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/validate-migrations.py`
**Line Range:** 98
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/validate_students_hash.py`
**Line Range:** 2
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/validate_students_hash.py:2, ./scripts/fix_teacher_id_nulls.py:7
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/validate_students_hash.py`
**Line Range:** 3
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/validate_students_hash.py:3, ./scripts/fix_teacher_id_nulls.py:8
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/verify_chain.py`
**Line Range:** 120
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/verify_chain.py`
**Line Range:** 126
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/verify_chain.py`
**Line Range:** 150
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/verify_chain.py`
**Line Range:** 159
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/verify_chain.py`
**Line Range:** 26
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/verify_chain.py`
**Line Range:** 42-172
**Category:** Complexity
**Description:** Function `verify_migration_chain` is 131 lines long (max 75).
**Why This Matters:** Long functions are harder to read, test, and maintain.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/verify_chain.py`
**Line Range:** 70
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/verify_chain.py`
**Line Range:** 90
**Category:** Structural Smell
**Description:** Duplicated logic block detected in: ./scripts/verify_chain.py:90, ./scripts/verify_chain.py:124
**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.
**Confidence Level:** High
---
**Severity:** Medium
**File:** `./scripts/verify_chain.py`
**Line Range:** 94
**Category:** Complexity
**Description:** Nesting depth > 3 detected.
**Why This Matters:** Deep nesting reduces readability and increases complexity.
**Confidence Level:** High
---
**Severity:** Low
**File:** `./app/__init__.py`
**Line Range:** 53
**Category:** Structural Smell
**Description:** Found TODO/FIXME marker: # TODO: [DEPENDABOT PR #463] MarkupSafe 3.x introduces breaking changes:
**Why This Matters:** Incomplete code markers should be addressed or tracked.
**Confidence Level:** Medium
---
**Severity:** Low
**File:** `./app/attendance.py`
**Line Range:** 104
**Category:** Dead Code
**Description:** Potential unused definition: `calculate_period_attendance`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/attendance.py`
**Line Range:** 185
**Category:** Dead Code
**Description:** Potential unused definition: `get_session_status`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/auth.py`
**Line Range:** 432
**Category:** Dead Code
**Description:** Potential unused definition: `can_access_student_routes`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/auth.py`
**Line Range:** 7
**Category:** Dead Code
**Description:** Potential unused definition: `urllib.parse`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/demo_cleanup.py`
**Line Range:** 7
**Category:** Dead Code
**Description:** Potential unused definition: `cleanup_demo_student_records`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/extensions.py`
**Line Range:** 13
**Category:** Structural Smell
**Description:** Found TODO/FIXME marker: # TODO: [DEPENDABOT PR #648] Flask-Limiter 4.x introduces breaking changes:
**Why This Matters:** Incomplete code markers should be addressed or tracked.
**Confidence Level:** Medium
---
**Severity:** Low
**File:** `./app/forms.py`
**Line Range:** 57
**Category:** Dead Code
**Description:** Potential unused definition: `validate_bundle_quantity`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/forms.py`
**Line Range:** 62
**Category:** Dead Code
**Description:** Potential unused definition: `validate_bulk_discount_quantity`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/forms.py`
**Line Range:** 67
**Category:** Dead Code
**Description:** Potential unused definition: `validate_bulk_discount_percentage`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/forms.py`
**Line Range:** 75
**Category:** Dead Code
**Description:** Potential unused definition: `validate_collective_goal_type`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/forms.py`
**Line Range:** 80
**Category:** Dead Code
**Description:** Potential unused definition: `validate_collective_goal_target`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/models.py`
**Line Range:** 1260
**Category:** Dead Code
**Description:** Potential unused definition: `blocks_list`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/models.py`
**Line Range:** 1529
**Category:** Dead Code
**Description:** Potential unused definition: `get_student_visible_status`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/models.py`
**Line Range:** 1541
**Category:** Dead Code
**Description:** Potential unused definition: `is_locked`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/models.py`
**Line Range:** 2004
**Category:** Dead Code
**Description:** Potential unused definition: `mark_step_completed`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/models.py`
**Line Range:** 2013
**Category:** Dead Code
**Description:** Potential unused definition: `is_step_completed`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/models.py`
**Line Range:** 2019
**Category:** Dead Code
**Description:** Potential unused definition: `complete_onboarding`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/models.py`
**Line Range:** 2032
**Category:** Dead Code
**Description:** Potential unused definition: `needs_onboarding`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/models.py`
**Line Range:** 2045
**Category:** Dead Code
**Description:** Potential unused definition: `is_widget_task_completed`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/models.py`
**Line Range:** 2128
**Category:** Dead Code
**Description:** Potential unused definition: `should_display`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/models.py`
**Line Range:** 2132
**Category:** Dead Code
**Description:** Potential unused definition: `get_priority_class`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/models.py`
**Line Range:** 2142
**Category:** Dead Code
**Description:** Potential unused definition: `get_priority_icon`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/models.py`
**Line Range:** 283
**Category:** Dead Code
**Description:** Potential unused definition: `full_name`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/models.py`
**Line Range:** 543
**Category:** Dead Code
**Description:** Potential unused definition: `total_earnings`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/models.py`
**Line Range:** 552
**Category:** Dead Code
**Description:** Potential unused definition: `recent_deposits`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/models.py`
**Line Range:** 570
**Category:** Dead Code
**Description:** Potential unused definition: `amount_needed_to_cover_bills`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/models.py`
**Line Range:** 744
**Category:** Dead Code
**Description:** Potential unused definition: `_sync_transaction_amount_cents`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Medium
---
**Severity:** Low
**File:** `./app/models.py`
**Line Range:** 968
**Category:** Dead Code
**Description:** Potential unused definition: `blocks_list`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 1015
**Category:** Dead Code
**Description:** Potential unused definition: `login`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 1058
**Category:** Dead Code
**Description:** Potential unused definition: `signup`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 130
**Category:** Structural Smell
**Description:** `pass` statement detected.
**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.
**Confidence Level:** High
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 1303
**Category:** Dead Code
**Description:** Potential unused definition: `recover`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 137
**Category:** Structural Smell
**Description:** `pass` statement detected.
**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.
**Confidence Level:** High
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 1462
**Category:** Dead Code
**Description:** Potential unused definition: `recovery_status`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 1506
**Category:** Dead Code
**Description:** Potential unused definition: `reset_credentials`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 1676
**Category:** Dead Code
**Description:** Potential unused definition: `save_recovery_progress`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 1723
**Category:** Dead Code
**Description:** Potential unused definition: `resume_credentials`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 1764
**Category:** Dead Code
**Description:** Potential unused definition: `setup_recovery`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 1838
**Category:** Dead Code
**Description:** Potential unused definition: `logout`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 2267
**Category:** Dead Code
**Description:** Potential unused definition: `set_current_class`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 2288
**Category:** Dead Code
**Description:** Potential unused definition: `student_detail`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 2414
**Category:** Dead Code
**Description:** Potential unused definition: `set_hall_passes`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 2431
**Category:** Dead Code
**Description:** Potential unused definition: `edit_student`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 2576
**Category:** Dead Code
**Description:** Potential commented-out code detected.
**Why This Matters:** Commented-out code rots and confuses readers. Use version control instead.
**Confidence Level:** Medium
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 2684
**Category:** Dead Code
**Description:** Potential unused definition: `delete_student`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 2724
**Category:** Dead Code
**Description:** Potential unused definition: `bulk_delete_students`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 2753
**Category:** Dead Code
**Description:** Potential unused definition: `delete_block`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 2803
**Category:** Dead Code
**Description:** Potential unused definition: `delete_join_code`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 2831
**Category:** Dead Code
**Description:** Potential unused definition: `delete_pending_student`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 2886
**Category:** Dead Code
**Description:** Potential unused definition: `bulk_delete_pending_students`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 2948
**Category:** Dead Code
**Description:** Potential unused definition: `bulk_delete_legacy_unclaimed_students`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 2995
**Category:** Dead Code
**Description:** Potential unused definition: `add_individual_student`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 3148
**Category:** Dead Code
**Description:** Potential unused definition: `add_manual_student`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 3320
**Category:** Dead Code
**Description:** Potential unused definition: `store_management`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 3594
**Category:** Structural Smell
**Description:** `pass` statement detected.
**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.
**Confidence Level:** High
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 3601
**Category:** Structural Smell
**Description:** `pass` statement detected.
**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.
**Confidence Level:** High
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 3656
**Category:** Dead Code
**Description:** Potential unused definition: `edit_store_item`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 3685
**Category:** Dead Code
**Description:** Potential unused definition: `delete_store_item`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 3704
**Category:** Dead Code
**Description:** Potential unused definition: `hard_delete_store_item`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 3909
**Category:** Structural Smell
**Description:** `pass` statement detected.
**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.
**Confidence Level:** High
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 4043
**Category:** Structural Smell
**Description:** `pass` statement detected.
**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.
**Confidence Level:** High
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 4414
**Category:** Dead Code
**Description:** Potential unused definition: `add_rent_waiver`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 4483
**Category:** Dead Code
**Description:** Potential unused definition: `remove_rent_waiver`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 4531
**Category:** Dead Code
**Description:** Potential unused definition: `insurance_management`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 4724
**Category:** Dead Code
**Description:** Potential unused definition: `edit_insurance_policy`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 4792
**Category:** Dead Code
**Description:** Potential unused definition: `deactivate_insurance_policy`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 4808
**Category:** Dead Code
**Description:** Potential unused definition: `delete_insurance_policy`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 4879
**Category:** Dead Code
**Description:** Potential unused definition: `mass_remove_policy`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 4926
**Category:** Dead Code
**Description:** Potential unused definition: `view_student_policy`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 4950
**Category:** Dead Code
**Description:** Potential unused definition: `process_claim`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 515
**Category:** Dead Code
**Description:** Potential unused definition: `_get_feature_settings`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Medium
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 5181
**Category:** Dead Code
**Description:** Potential unused definition: `void_transaction`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 5481
**Category:** Dead Code
**Description:** Potential unused definition: `hall_pass_setup`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 5490
**Category:** Dead Code
**Description:** Potential unused definition: `economy_health`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 553
**Category:** Dead Code
**Description:** Potential unused definition: `_get_or_create_onboarding`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Medium
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 5732
**Category:** Dead Code
**Description:** Potential unused definition: `run_payroll`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 5807
**Category:** Dead Code
**Description:** Potential unused definition: `payroll`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 6241
**Category:** Dead Code
**Description:** Potential unused definition: `update_expected_weekly_hours`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 6320
**Category:** Dead Code
**Description:** Potential unused definition: `payroll_add_reward`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 6349
**Category:** Dead Code
**Description:** Potential unused definition: `payroll_delete_reward`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 6365
**Category:** Dead Code
**Description:** Potential unused definition: `payroll_add_fine`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 6394
**Category:** Dead Code
**Description:** Potential unused definition: `payroll_delete_fine`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 6410
**Category:** Dead Code
**Description:** Potential unused definition: `payroll_edit_reward`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 6433
**Category:** Dead Code
**Description:** Potential unused definition: `payroll_edit_fine`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 6456
**Category:** Dead Code
**Description:** Potential unused definition: `void_payroll_transaction`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 6506
**Category:** Dead Code
**Description:** Potential unused definition: `void_transactions_bulk`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 6565
**Category:** Dead Code
**Description:** Potential unused definition: `payroll_apply_reward`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 6614
**Category:** Dead Code
**Description:** Potential unused definition: `payroll_apply_fine`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 6715
**Category:** Dead Code
**Description:** Potential unused definition: `payroll_manual_payment`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 6832
**Category:** Dead Code
**Description:** Potential unused definition: `attendance_log`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 6867
**Category:** Dead Code
**Description:** Potential unused definition: `upload_students`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 7038
**Category:** Dead Code
**Description:** Potential unused definition: `download_csv_template`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 7048
**Category:** Dead Code
**Description:** Potential unused definition: `export_students`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 7113
**Category:** Dead Code
**Description:** Potential unused definition: `enforce_daily_limits`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 715
**Category:** Dead Code
**Description:** Potential unused definition: `dashboard`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 7187
**Category:** Dead Code
**Description:** Potential unused definition: `tap_out_students`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 7334
**Category:** Dead Code
**Description:** Potential unused definition: `tap_in_students`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 7433
**Category:** Dead Code
**Description:** Potential unused definition: `bulk_update_hall_passes`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 7518
**Category:** Dead Code
**Description:** Potential unused definition: `banking`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 7709
**Category:** Dead Code
**Description:** Potential unused definition: `banking_settings_update`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 7772
**Category:** Dead Code
**Description:** Potential unused definition: `deletion_requests`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 7879
**Category:** Dead Code
**Description:** Potential unused definition: `help_support`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 8084
**Category:** Dead Code
**Description:** Potential unused definition: `update_period_feature_settings`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 8137
**Category:** Dead Code
**Description:** Potential unused definition: `copy_feature_settings`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 8282
**Category:** Dead Code
**Description:** Potential unused definition: `announcement_create`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 8357
**Category:** Dead Code
**Description:** Potential unused definition: `announcement_edit`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 8414
**Category:** Dead Code
**Description:** Potential unused definition: `announcement_delete`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 8447
**Category:** Dead Code
**Description:** Potential unused definition: `announcement_toggle`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 8483
**Category:** Dead Code
**Description:** Potential unused definition: `onboarding_status`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 8620
**Category:** Dead Code
**Description:** Potential unused definition: `onboarding_skip`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 8638
**Category:** Dead Code
**Description:** Potential unused definition: `onboarding_skip_task`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 8673
**Category:** Dead Code
**Description:** Potential unused definition: `onboarding_dismiss_widget`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 8702
**Category:** Dead Code
**Description:** Potential unused definition: `onboarding_undismiss_widget`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 8733
**Category:** Dead Code
**Description:** Potential unused definition: `api_calculate_cwi`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 8792
**Category:** Dead Code
**Description:** Potential unused definition: `api_economy_analyze`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 8910
**Category:** Dead Code
**Description:** Potential unused definition: `api_economy_validate`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 899
**Category:** Dead Code
**Description:** Potential unused definition: `give_bonus_all`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 9021
**Category:** Dead Code
**Description:** Potential unused definition: `passkey_register_start`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 9056
**Category:** Dead Code
**Description:** Potential unused definition: `passkey_register_finish`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 9093
**Category:** Dead Code
**Description:** Potential unused definition: `passkey_auth_start`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 9131
**Category:** Dead Code
**Description:** Potential unused definition: `passkey_auth_finish`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 9193
**Category:** Dead Code
**Description:** Potential unused definition: `passkey_list`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 9216
**Category:** Dead Code
**Description:** Potential unused definition: `passkey_delete`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 9239
**Category:** Dead Code
**Description:** Potential unused definition: `passkey_settings`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 9254
**Category:** Dead Code
**Description:** Potential unused definition: `issues_queue`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 9298
**Category:** Dead Code
**Description:** Potential unused definition: `view_issue`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 9323
**Category:** Dead Code
**Description:** Potential unused definition: `resolve_issue`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/admin.py`
**Line Range:** 9398
**Category:** Dead Code
**Description:** Potential unused definition: `escalate_issue`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/analytics.py`
**Line Range:** 203
**Category:** Dead Code
**Description:** Potential unused definition: `dashboard`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/analytics.py`
**Line Range:** 277
**Category:** Dead Code
**Description:** Potential unused definition: `api_snapshot`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/analytics.py`
**Line Range:** 333
**Category:** Dead Code
**Description:** Potential unused definition: `api_alerts`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/analytics.py`
**Line Range:** 385
**Category:** Dead Code
**Description:** Potential unused definition: `acknowledge_alert`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/analytics.py`
**Line Range:** 454
**Category:** Dead Code
**Description:** Potential unused definition: `student_drill_down`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 1037
**Category:** Structural Smell
**Description:** `pass` statement detected.
**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.
**Confidence Level:** High
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 1111
**Category:** Dead Code
**Description:** Potential unused definition: `handle_hall_pass_action`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 1215
**Category:** Dead Code
**Description:** Potential unused definition: `get_active_hall_passes`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 1304
**Category:** Dead Code
**Description:** Potential unused definition: `lookup_hall_pass`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 1415
**Category:** Dead Code
**Description:** Potential unused definition: `hall_pass_terminal_use`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 1466
**Category:** Dead Code
**Description:** Potential unused definition: `hall_pass_terminal_return`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 1513
**Category:** Dead Code
**Description:** Potential unused definition: `cancel_hall_pass`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 1536
**Category:** Dead Code
**Description:** Potential unused definition: `checkout_hall_pass`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 158
**Category:** Dead Code
**Description:** Potential unused definition: `get_tips`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 1591
**Category:** Dead Code
**Description:** Potential unused definition: `checkin_hall_pass`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 1640
**Category:** Dead Code
**Description:** Potential unused definition: `get_hall_pass_queue`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 1825
**Category:** Dead Code
**Description:** Potential unused definition: `hall_pass_history`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 1934
**Category:** Dead Code
**Description:** Potential unused definition: `get_hall_pass_setup`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 1959
**Category:** Dead Code
**Description:** Potential unused definition: `save_hall_pass_setup`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 2035
**Category:** Dead Code
**Description:** Potential unused definition: `get_available_hall_pass_types`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 2064
**Category:** Dead Code
**Description:** Potential unused definition: `attendance_history`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 2197
**Category:** Dead Code
**Description:** Potential unused definition: `handle_tap`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 224
**Category:** Dead Code
**Description:** Potential unused definition: `purchase_item`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 2300
**Category:** Structural Smell
**Description:** `pass` statement detected.
**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.
**Confidence Level:** High
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 2336
**Category:** Structural Smell
**Description:** `pass` statement detected.
**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.
**Confidence Level:** High
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 2577
**Category:** Dead Code
**Description:** Potential unused definition: `get_tap_entries`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 2648
**Category:** Dead Code
**Description:** Potential unused definition: `delete_tap_entry`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 2685
**Category:** Dead Code
**Description:** Potential unused definition: `update_student_block_settings`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 2893
**Category:** Dead Code
**Description:** Potential unused definition: `student_status`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 2921
**Category:** Dead Code
**Description:** Potential unused definition: `set_timezone`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 2937
**Category:** Structural Smell
**Description:** `pass` statement detected.
**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.
**Confidence Level:** High
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 2954
**Category:** Structural Smell
**Description:** `pass` statement detected.
**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.
**Confidence Level:** High
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 2970
**Category:** Structural Smell
**Description:** `pass` statement detected.
**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.
**Confidence Level:** High
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 2996
**Category:** Dead Code
**Description:** Potential unused definition: `create_demo_student`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 3127
**Category:** Dead Code
**Description:** Potential unused definition: `get_block_tap_settings`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 3178
**Category:** Dead Code
**Description:** Potential unused definition: `update_block_tap_settings`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 3245
**Category:** Dead Code
**Description:** Potential unused definition: `view_as_student_status`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 462
**Category:** Structural Smell
**Description:** `pass` statement detected.
**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.
**Confidence Level:** High
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 773
**Category:** Dead Code
**Description:** Potential unused definition: `use_item`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 861
**Category:** Structural Smell
**Description:** `pass` statement detected.
**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.
**Confidence Level:** High
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 914
**Category:** Dead Code
**Description:** Potential unused definition: `approve_redemption`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/api.py`
**Line Range:** 966
**Category:** Dead Code
**Description:** Potential unused definition: `reject_redemption`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/docs.py`
**Line Range:** 195
**Category:** Dead Code
**Description:** Potential unused definition: `index`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/docs.py`
**Line Range:** 201
**Category:** Dead Code
**Description:** Potential unused definition: `view_doc`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/main.py`
**Line Range:** 133
**Category:** Dead Code
**Description:** Potential unused definition: `privacy`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/main.py`
**Line Range:** 139
**Category:** Dead Code
**Description:** Potential unused definition: `terms`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/main.py`
**Line Range:** 145
**Category:** Dead Code
**Description:** Potential unused definition: `offline`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/main.py`
**Line Range:** 152
**Category:** Dead Code
**Description:** Potential unused definition: `service_worker`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/main.py`
**Line Range:** 164
**Category:** Dead Code
**Description:** Potential unused definition: `hall_pass_terminal`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/main.py`
**Line Range:** 170
**Category:** Dead Code
**Description:** Potential unused definition: `hall_pass_verification`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/main.py`
**Line Range:** 176
**Category:** Dead Code
**Description:** Potential unused definition: `hall_pass_queue`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/main.py`
**Line Range:** 184
**Category:** Dead Code
**Description:** Potential unused definition: `debug_filters`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/main.py`
**Line Range:** 190
**Category:** Dead Code
**Description:** Potential unused definition: `switch_view`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/main.py`
**Line Range:** 207
**Category:** Dead Code
**Description:** Potential unused definition: `debug_admin_db_test`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/main.py`
**Line Range:** 46
**Category:** Dead Code
**Description:** Potential unused definition: `health_check`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/main.py`
**Line Range:** 57
**Category:** Dead Code
**Description:** Potential unused definition: `health_check_deep`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/recovery.py`
**Line Range:** 142
**Category:** Dead Code
**Description:** Potential unused definition: `verify_identity`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/recovery.py`
**Line Range:** 36
**Category:** Dead Code
**Description:** Potential unused definition: `generate_reset_code`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/recovery.py`
**Line Range:** 75
**Category:** Dead Code
**Description:** Potential unused definition: `landing`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/recovery.py`
**Line Range:** 82
**Category:** Dead Code
**Description:** Potential unused definition: `account_lookup`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 1091
**Category:** Dead Code
**Description:** Potential unused definition: `dashboard`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 1430
**Category:** Dead Code
**Description:** Potential unused definition: `payroll`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 1509
**Category:** Dead Code
**Description:** Potential unused definition: `transfer`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 152
**Category:** Dead Code
**Description:** Potential unused definition: `get_current_join_code`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 1808
**Category:** Dead Code
**Description:** Potential unused definition: `insurance_marketplace`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 1923
**Category:** Dead Code
**Description:** Potential unused definition: `purchase_insurance`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 2087
**Category:** Dead Code
**Description:** Potential unused definition: `cancel_insurance`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 2107
**Category:** Dead Code
**Description:** Potential unused definition: `file_claim`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 2334
**Category:** Dead Code
**Description:** Potential unused definition: `view_policy`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 2366
**Category:** Dead Code
**Description:** Potential unused definition: `shop`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 2690
**Category:** Dead Code
**Description:** Potential unused definition: `_add_rent_period`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Medium
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 2987
**Category:** Dead Code
**Description:** Potential unused definition: `rent_pay`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 331
**Category:** Risk Pattern
**Description:** Function `check_legacy_profile` has inconsistent return statements (mixed value/no-value).
**Why This Matters:** Inconsistent returns can lead to type errors and confusing behavior.
**Confidence Level:** Medium
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 331
**Category:** Dead Code
**Description:** Potential unused definition: `check_legacy_profile`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 3412
**Category:** Dead Code
**Description:** Potential unused definition: `login`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 3511
**Category:** Dead Code
**Description:** Potential unused definition: `demo_login`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 3605
**Category:** Dead Code
**Description:** Potential unused definition: `logout`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 3635
**Category:** Dead Code
**Description:** Potential unused definition: `switch_class`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 3671
**Category:** Dead Code
**Description:** Potential unused definition: `switch_period`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 3710
**Category:** Dead Code
**Description:** Potential unused definition: `help_support`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 373
**Category:** Dead Code
**Description:** Potential unused definition: `complete_profile`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 3740
**Category:** Dead Code
**Description:** Potential unused definition: `submit_general_issue`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 3786
**Category:** Dead Code
**Description:** Potential unused definition: `report_transaction_issue`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 3842
**Category:** Dead Code
**Description:** Potential unused definition: `report_tap_event_issue`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 3901
**Category:** Dead Code
**Description:** Potential unused definition: `verify_recovery`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 3972
**Category:** Dead Code
**Description:** Potential unused definition: `dismiss_recovery`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 543
**Category:** Dead Code
**Description:** Potential unused definition: `claim_account`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 793
**Category:** Dead Code
**Description:** Potential unused definition: `create_username`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 837
**Category:** Dead Code
**Description:** Potential unused definition: `setup_pin_passphrase`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/student.py`
**Line Range:** 878
**Category:** Dead Code
**Description:** Potential unused definition: `add_class`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 1083
**Category:** Dead Code
**Description:** Potential unused definition: `delete_teacher`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 1179
**Category:** Dead Code
**Description:** Potential unused definition: `user_reports`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 1219
**Category:** Dead Code
**Description:** Potential unused definition: `view_user_report`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 1233
**Category:** Dead Code
**Description:** Potential unused definition: `update_user_report`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 1266
**Category:** Dead Code
**Description:** Potential unused definition: `send_reward_to_reporter`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 128
**Category:** Dead Code
**Description:** Potential unused definition: `auth_check`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 1354
**Category:** Dead Code
**Description:** Potential unused definition: `grafana_auth_check`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 1402
**Category:** Dead Code
**Description:** Potential unused definition: `grafana_proxy`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 159
**Category:** Dead Code
**Description:** Potential unused definition: `login`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 1610
**Category:** Dead Code
**Description:** Potential unused definition: `announcement_create`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 1660
**Category:** Dead Code
**Description:** Potential unused definition: `announcement_edit`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 1715
**Category:** Dead Code
**Description:** Potential unused definition: `announcement_delete`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 1743
**Category:** Dead Code
**Description:** Potential unused definition: `announcement_toggle`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 1800
**Category:** Dead Code
**Description:** Potential unused definition: `view_escalated_issue`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 1823
**Category:** Dead Code
**Description:** Potential unused definition: `start_review_escalated_issue`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 1850
**Category:** Dead Code
**Description:** Potential unused definition: `resolve_escalated_issue`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 190
**Category:** Dead Code
**Description:** Potential unused definition: `logout`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 205
**Category:** Dead Code
**Description:** Potential unused definition: `passkey_register_start`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 238
**Category:** Dead Code
**Description:** Potential unused definition: `passkey_register_finish`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 275
**Category:** Dead Code
**Description:** Potential unused definition: `passkey_auth_start`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 313
**Category:** Dead Code
**Description:** Potential unused definition: `passkey_auth_finish`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 379
**Category:** Dead Code
**Description:** Potential unused definition: `passkey_list`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 400
**Category:** Dead Code
**Description:** Potential unused definition: `passkey_delete`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 423
**Category:** Dead Code
**Description:** Potential unused definition: `passkey_settings`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 438
**Category:** Dead Code
**Description:** Potential unused definition: `dashboard`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 474
**Category:** Dead Code
**Description:** Potential unused definition: `logs`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 517
**Category:** Dead Code
**Description:** Potential unused definition: `error_logs`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 556
**Category:** Dead Code
**Description:** Potential unused definition: `logs_testing`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 577
**Category:** Dead Code
**Description:** Potential unused definition: `network_activity`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 632
**Category:** Dead Code
**Description:** Potential unused definition: `test_error_400`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 639
**Category:** Dead Code
**Description:** Potential unused definition: `test_error_401`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 646
**Category:** Dead Code
**Description:** Potential unused definition: `test_error_403`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 653
**Category:** Dead Code
**Description:** Potential unused definition: `test_error_404`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 660
**Category:** Dead Code
**Description:** Potential unused definition: `test_error_500`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 669
**Category:** Dead Code
**Description:** Potential unused definition: `test_error_503`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 678
**Category:** Dead Code
**Description:** Potential unused definition: `manage_admins`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 710
**Category:** Dead Code
**Description:** Potential unused definition: `reset_teacher_totp`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 755
**Category:** Dead Code
**Description:** Potential unused definition: `delete_admin`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 826
**Category:** Dead Code
**Description:** Potential unused definition: `manage_teachers`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 861
**Category:** Dead Code
**Description:** Potential unused definition: `teacher_overview`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/routes/system_admin.py`
**Line Range:** 991
**Category:** Dead Code
**Description:** Potential unused definition: `delete_period`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/utils/claim_credentials.py`
**Line Range:** 8
**Category:** Dead Code
**Description:** Potential unused definition: `annotations`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/utils/economy_balance.py`
**Line Range:** 1120
**Category:** Dead Code
**Description:** Potential unused definition: `format_warnings_for_display`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/utils/economy_balance.py`
**Line Range:** 699
**Category:** Risk Pattern
**Description:** Function `validate_insurance_value` has inconsistent return statements (mixed value/no-value).
**Why This Matters:** Inconsistent returns can lead to type errors and confusing behavior.
**Confidence Level:** Medium
---
**Severity:** Low
**File:** `./app/utils/encryption.py`
**Line Range:** 26
**Category:** Dead Code
**Description:** Potential unused definition: `process_bind_param`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/utils/encryption.py`
**Line Range:** 33
**Category:** Dead Code
**Description:** Potential unused definition: `process_result_value`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/utils/helpers.py`
**Line Range:** 17
**Category:** Structural Smell
**Description:** Found TODO/FIXME marker: # TODO: [DEPENDABOT PR #463] MarkupSafe 3.x introduces breaking changes:
**Why This Matters:** Incomplete code markers should be addressed or tracked.
**Confidence Level:** Medium
---
**Severity:** Low
**File:** `./app/utils/ip_handler.py`
**Line Range:** 16
**Category:** Dead Code
**Description:** Potential unused definition: `urllib.request`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/utils/ip_handler.py`
**Line Range:** 167
**Category:** Structural Smell
**Description:** `pass` statement detected.
**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.
**Confidence Level:** High
---
**Severity:** Low
**File:** `./app/utils/ip_handler.py`
**Line Range:** 17
**Category:** Dead Code
**Description:** Potential unused definition: `urllib.error`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/utils/ip_handler.py`
**Line Range:** 214
**Category:** Dead Code
**Description:** Potential unused definition: `get_request_info`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/utils/join_code.py`
**Line Range:** 54
**Category:** Dead Code
**Description:** Potential unused definition: `is_valid_join_code_format`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/utils/money_guard.py`
**Line Range:** 1
**Category:** Dead Code
**Description:** Potential unused definition: `annotations`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/utils/money_guard.py`
**Line Range:** 8
**Category:** Dead Code
**Description:** Potential unused definition: `check_financial_cooldown`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/utils/name_utils.py`
**Line Range:** 101
**Category:** Dead Code
**Description:** Potential unused definition: `fuzzy_match_last_name`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/utils/turnstile.py`
**Line Range:** 7
**Category:** Dead Code
**Description:** Potential unused definition: `urllib.request`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./app/utils/turnstile.py`
**Line Range:** 8
**Category:** Dead Code
**Description:** Potential unused definition: `urllib.parse`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./scripts/add-github-actions-to-firewall.py`
**Line Range:** 15
**Category:** Dead Code
**Description:** Potential unused definition: `urllib.request`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 57
**Category:** Structural Smell
**Description:** `pass` statement detected.
**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.
**Confidence Level:** High
---
**Severity:** Low
**File:** `./scripts/analyze_migrations.py`
**Line Range:** 67
**Category:** Structural Smell
**Description:** `pass` statement detected.
**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.
**Confidence Level:** High
---
**Severity:** Low
**File:** `./scripts/create-github-actions-firewall.py`
**Line Range:** 15
**Category:** Dead Code
**Description:** Potential unused definition: `urllib.request`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./scripts/firewall_complete.py`
**Line Range:** 10
**Category:** Dead Code
**Description:** Potential unused definition: `annotations`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./scripts/lint_migrations.py`
**Line Range:** 120
**Category:** Dead Code
**Description:** Potential unused definition: `has_helper_function`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./scripts/pulsetic_firewall.py`
**Line Range:** 10
**Category:** Dead Code
**Description:** Potential unused definition: `annotations`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./scripts/validate-migrations.py`
**Line Range:** 106
**Category:** Structural Smell
**Description:** `pass` statement detected.
**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.
**Confidence Level:** High
---
**Severity:** Low
**File:** `./scripts/validate-migrations.py`
**Line Range:** 113
**Category:** Dead Code
**Description:** Potential unused definition: `visit_Call`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./scripts/validate-migrations.py`
**Line Range:** 139
**Category:** Dead Code
**Description:** Potential unused definition: `visit_If`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./scripts/validate-migrations.py`
**Line Range:** 144
**Category:** Dead Code
**Description:** Potential unused definition: `visit_FunctionDef`
**Why This Matters:** Unused code adds noise and cognitive load.
**Confidence Level:** Low
---
**Severity:** Low
**File:** `./scripts/validate-migrations.py`
**Line Range:** 235
**Category:** Risk Pattern
**Description:** Function `validate_migrations` has inconsistent return statements (mixed value/no-value).
**Why This Matters:** Inconsistent returns can lead to type errors and confusing behavior.
**Confidence Level:** Medium
---
**Severity:** Low
**File:** `./scripts/validate-migrations.py`
**Line Range:** 259
**Category:** Structural Smell
**Description:** `pass` statement detected.
**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.
**Confidence Level:** High
---
