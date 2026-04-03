# LOG-DOC-002: User Guide Accuracy Audit

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| LOG-DOC-002      | 1.0     | 2026-04-02     | N/A        | Informative     |

---

## Audit Scope

**Branch audited:** `fix-user-guide`
**Directories examined:** `docs/user-guides/`, `templates/`, `app/routes/`
**Method:** Cross-reference of every user-guide document against actual Jinja2 templates and Flask route handlers to validate UI claims, navigation paths, button labels, and workflow descriptions.

---

## Summary

The audit identified a total of **14 distinct issues** across three categories: critical content errors (documented UI or features that do not exist or are deprecated), navigation label mismatches, and student-facing inaccuracies. No major unordered-list rendering defects were found; all files use proper `- item` syntax. Frontmatter `related:` path inconsistencies were found in three files.

---

## Critical Content Errors

### 1. Hall Pass Terminal Workflow — Documented as Current; System Is Deprecated (HTTP 410)

**Files affected:**
- `docs/user-guides/diagnostics/teacher/hall-pass.md`
- `docs/user-guides/diagnostics/student/hall-pass.md`
- `docs/user-guides/features/teacher/classroom/hall-pass.md`

**Evidence:** All three terminal API routes in `app/routes/api.py` return HTTP 410 Gone:
- `POST /api/hall-pass/terminal/lookup` → 410
- `POST /api/hall-pass/terminal/use` → 410, message: *"Hall pass terminal checkout is deprecated. Students must check out from their dashboard."*
- `POST /api/hall-pass/terminal/return` → 410

The current self-service routes are `/api/hall-pass/checkout` and `/api/hall-pass/checkin`, triggered from the student dashboard.

**Specific problems per file:**
- `diagnostics/teacher/hall-pass.md` — Describes a "terminal scan" troubleshooting workflow that references a physically unavailable endpoint.
- `diagnostics/student/hall-pass.md` — States *"A pass only works at a terminal after it is approved."* This is the opposite of the current system. Students self-checkout from their own dashboard after approval.
- `features/teacher/classroom/hall-pass.md` — Step-by-step instructions include a terminal scan step that does not exist.

---

### 2. Wrong Button Labels in Hall Pass Teacher Guide

**File:** `docs/user-guides/features/teacher/classroom/hall-pass.md`

**Evidence:** `templates/admin_hall_pass.html` defines tabs (Pending, Approved, Out, History) and button labels.

| Document Says | Actual UI |
|---------------|-----------|
| **Deny** | **Reject** |
| **Close** | **Returned** |
| Passes move to "Closed" state | Passes appear in the **History** tab |

---

### 3. "Economy > Transactions" Navigation Path Does Not Exist

**File:** `docs/user-guides/features/teacher/economy/transactions.md`

**Doc says:** *"Navigate to **Economy > Transactions**"*

**Evidence:** `app/routes/admin.py` — the `/admin/transactions` route is an explicit redirect to `/admin/banking` with the comment: *"Redirect to banking page - transactions now under banking."* The Economy sidebar section in `templates/layout_admin.html` contains: Economy Health, Payroll, Store, Banking, Analytics. There is no "Transactions" item. Transactions are a tab within the Banking page.

---

### 4. "Settings > Account Recovery" Does Not Exist in Navigation

**File:** `docs/user-guides/features/teacher/settings/account-recovery.md`

**Doc says:** *"Navigate to **Settings > Account Recovery**"*

**Evidence:** `templates/layout_admin.html` — Settings sidebar contains only: Personalization, Passkey, Economy Features, Account Deletion. No "Account Recovery" item exists. Account recovery is surfaced as a prompt on the Dashboard, handled by `app/routes/admin.py` at `/admin/setup-recovery`.

---

### 5. "Itemization" Tab Does Not Exist in Rent Settings

**File:** `docs/user-guides/features/teacher/bills/rent-itemization.md`

**Doc says:** *"open the **Itemization** tab"*

**Evidence:** `templates/admin_rent_settings.html` — tabs are: Overview, Settings, Waivers, Corrections. No "Itemization" tab exists. Rent itemization is a section *within* the Settings tab, labeled "Rent Itemization (Optional)." The step-by-step instructions in this file describe a tab interaction that does not exist in the UI.

---

### 6. Broken File Paths in Economy Guide

**File:** `docs/user-guides/economy_guide.md`

The "For developers and tooling" section references three relative paths that do not resolve from `docs/user-guides/`:
- `../DOMAINS/ECONOMY_DESIGN/DOM-ECON-001_Economy_Balance_Checker.md`
- `../DOMAINS/ECONOMY_DESIGN/DOM-ECON-002_Economy_Specification.md`
- `../FEATURES/ECONOMY/FEAT-ECON-001_Policy_Mode_and_Rebalancer.md`

The directories `DOMAINS/` and `FEATURES/` do not exist at `docs/DOMAINS/` or `docs/FEATURES/`. These documents reside under `docs/DOMAINS/ECONOMY_DESIGN/` and `docs/FEATURES/`, which would require paths beginning with `../../` from `docs/user-guides/`.

---

## Navigation Label Mismatches

These files reference a menu item by an incorrect label. The nav item exists but is named differently in the actual template.

| File | Document Says | Actual Label in Template |
|------|---------------|--------------------------|
| `features/student/work/attendance-history.md` | "Open **Payroll** from the student navigation" | **Work & Pay** (`layout_student.html`) |
| `features/teacher/settings/feature-toggles.md` | "Navigate to **Settings > Features**" | **Economy Features** (`layout_admin.html`) |
| `features/sysadmin/teacher-management.md` | "Navigate to **Manage Teachers**" | **Teacher Management** (`layout_system_admin.html`) |
| `features/sysadmin/dashboard-overview.md` | References "**System Logs**" and "**Error Logs**" as separate nav items | Single **Logs** item; no "Error Logs" item (`layout_system_admin.html`) |
| `diagnostics/teacher/students.md` | Student claim requires "first initial" | Claim form in `templates/admin_students.html` requires full **First Name** |

---

## Student-Facing Inaccuracies

### 7. Dashboard Balance Location Is Wrong

**File:** `docs/user-guides/features/student/account/dashboard-overview.md`

**Doc says:** *"look at the top section to see your current checking and savings balances"*

**Evidence:** `templates/student_dashboard.html` — actual layout order:
1. Greeting + Weekly Stats (Days Tapped In, Minutes This Week, Earned/Spent This Week)
2. Attendance card (Start Work / Break / Done)
3. **Account Balances** (Checking Account, Savings Account cards)
4. Recent Activity

Balances are third in the layout, not at the top.

---

### 8. "Break / Done" Is One Combined Button, Not Two Separate Actions

**File:** `docs/user-guides/features/student/work/start-end-work.md`

**Doc says:** *"click **Done** (or **Break**)"* — framed as two separate, interchangeable actions.

**Evidence:** `templates/student_dashboard.html` — a single button is labeled **"Break / Done"**. There is one control, not two distinct buttons.

---

### 9. Login Setup: Wrong PIN Length, Missing Passphrase Step

**File:** `docs/user-guides/features/student/account/login-setup.md`

**Doc says:** *"secure 4-digit PIN"*

**Evidence:** The student account creation flow accepts a PIN of **4–8 digits**, not strictly 4. Additionally, the guide omits the **passphrase** setup step entirely. Students must set a passphrase (used for purchases and transfers) during account setup; this is a required part of the onboarding experience that the guide does not mention.

---

## Frontmatter `related:` Path Issues

Three files contain `related:` entries in their YAML frontmatter that may not resolve correctly depending on the rendering context.

- `features/teacher/classroom/attendance-approvals.md` — `related:` entries use paths beginning with `user-guides/` (e.g., `user-guides/features/student/work/start-end-work`), suggesting an absolute path from the `docs/` root rather than a relative path from the file's location.
- `features/teacher/classroom/attendance-corrections.md` — Same pattern: `user-guides/features/teacher/classroom/attendance-approvals` and `user-guides/diagnostics/teacher/attendance-payroll`.
- `features/student/work/attendance-history.md` — Same pattern. Also, `user-guides/diagnostics/student-attendance` appears to reference a file that does not exist; the correct path is likely `diagnostics/student/attendance`.

---

## Files Reviewed with No Issues Found

The following files were read and cross-referenced with no discrepancies identified:

- `features/teacher/classroom/attendance-approvals.md` — Describes Classroom > Attendance with class block toggles and the filter panel accurately.
- `features/teacher/classroom/attendance-corrections.md` — Correctly describes the append-only attendance log and diagnosis workflow.
- `features/student/support/report-issues.md` — Describes the report icon next to attendance events; matches template behavior.
- `diagnostics/teacher/attendance-payroll.md` — Content is accurate to the actual attendance and payroll workflow.

---

## Priority Index

| Priority | Issue | Affected Files |
|----------|-------|----------------|
| P0 | Hall pass terminal docs describe a deprecated (HTTP 410) system | 3 |
| P0 | Wrong button labels in hall pass teacher guide (Deny/Close vs Reject/Returned) | 1 |
| P1 | "Economy > Transactions" nav path does not exist | 1 |
| P1 | "Settings > Account Recovery" nav path does not exist | 1 |
| P1 | "Itemization" tab does not exist in Rent Settings | 1 |
| P1 | Student dashboard balance location described incorrectly | 1 |
| P1 | Broken relative paths in economy_guide.md developer section | 1 |
| P2 | Nav label mismatches (Work & Pay, Economy Features, Teacher Management, Logs) | 5 |
| P2 | PIN described as 4-digit only; passphrase step omitted | 1 |
| P2 | "Break / Done" described as two separate buttons | 1 |
| P3 | Frontmatter `related:` path format inconsistencies | 3 |
