# LOG-DOC-002: User Guide Accuracy Audit

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| LOG-DOC-002      | 1.2     | 2026-04-02     | N/A        | Informative     |

**v1.0** — Initial audit completed. 14 issues identified.
**v1.1** — Resolution recheck completed. All 14 issues confirmed resolved.
**v1.2** — Post-resolution upgrade completed. Hall pass guides now include audience-specific retirement/privacy notices, and user-guide release-version references were removed.

---

## Audit Scope

**Branch audited:** `fix-user-guide`
**Directories examined:** `docs/user-guides/`, `templates/`, `app/routes/`
**Method:** Cross-reference of every user-guide document against actual Jinja2 templates and Flask route handlers to validate UI claims, navigation paths, button labels, and workflow descriptions.

---

## Summary

The audit identified a total of **14 distinct issues** across three categories: critical content errors (documented UI or features that do not exist or are deprecated), navigation label mismatches, and student-facing inaccuracies. No major unordered-list rendering defects were found; all files use proper `- item` syntax. Frontmatter `related:` path inconsistencies were found in three files.

**All 14 issues have been resolved and verified.**

---

## Resolution Status

| Priority | Issue | Affected Files | Status |
|----------|-------|----------------|--------|
| P0 | Hall pass terminal docs describe a deprecated (HTTP 410) system | 3 | ✅ Resolved |
| P0 | Wrong button labels in hall pass teacher guide (Deny/Close vs Reject/Returned) | 1 | ✅ Resolved |
| P1 | "Economy > Transactions" nav path does not exist | 1 | ✅ Resolved |
| P1 | "Settings > Account Recovery" nav path does not exist | 1 | ✅ Resolved |
| P1 | "Itemization" tab does not exist in Rent Settings | 1 | ✅ Resolved |
| P1 | Student dashboard balance location described incorrectly | 1 | ✅ Resolved |
| P1 | Broken relative paths in economy_guide.md developer section | 1 | ✅ Resolved |
| P2 | Nav label mismatches (Work & Pay, Economy Features, Teacher Management, Logs) | 5 | ✅ Resolved |
| P2 | PIN described as 4-digit only; passphrase step omitted | 1 | ✅ Resolved |
| P2 | "Break / Done" described as two separate buttons | 1 | ✅ Resolved |
| P3 | Frontmatter `related:` path format inconsistencies | 3 | ✅ Resolved |

---

## Original Findings

### Critical Content Errors

#### 1. Hall Pass Terminal Workflow — Documented as Current; System Is Deprecated (HTTP 410)

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
- `diagnostics/teacher/hall-pass.md` — Described a "terminal scan" troubleshooting workflow referencing a physically unavailable endpoint.
- `diagnostics/student/hall-pass.md` — Stated *"A pass only works at a terminal after it is approved."* This is the opposite of the current system.
- `features/teacher/classroom/hall-pass.md` — Step-by-step instructions included a terminal scan step that does not exist.

**Resolution:** All three files updated to describe the student self-checkout flow from the dashboard. Terminal references removed entirely.

---

#### 2. Wrong Button Labels in Hall Pass Teacher Guide

**File:** `docs/user-guides/features/teacher/classroom/hall-pass.md`

**Evidence:** `templates/admin_hall_pass.html` defines tabs (Pending, Approved, Out, History) and button labels.

| Document Said | Actual UI |
|---------------|-----------|
| **Deny** | **Reject** |
| **Close** | **Returned** |
| Passes move to "Closed" state | Passes appear in the **History** tab |

**Resolution:** Button labels corrected to Approve/Reject and Returned. Tab states updated to Pending, Approved, Out, History.

---

#### 3. "Economy > Transactions" Navigation Path Does Not Exist

**File:** `docs/user-guides/features/teacher/economy/transactions.md`

**Evidence:** `/admin/transactions` is an explicit redirect to `/admin/banking`. No "Transactions" item exists in the Economy sidebar. Transactions are a tab within the Banking page.

**Resolution:** Navigation instruction updated to **Economy > Banking**.

---

#### 4. "Settings > Account Recovery" Does Not Exist in Navigation

**File:** `docs/user-guides/features/teacher/settings/account-recovery.md`

**Evidence:** Settings sidebar contains only: Personalization, Passkey, Economy Features, Account Deletion. Account recovery is surfaced as a Dashboard prompt via `/admin/setup-recovery`.

**Resolution:** Guide updated to direct teachers to the Dashboard prompt rather than a Settings nav item.

---

#### 5. "Itemization" Tab Does Not Exist in Rent Settings

**File:** `docs/user-guides/features/teacher/bills/rent-itemization.md`

**Evidence:** `templates/admin_rent_settings.html` tabs are: Overview, Settings, Waivers, Corrections. Rent itemization is a section within the Settings tab, labeled "Rent Itemization (Optional)."

**Resolution:** Instructions updated to navigate to the Settings tab and scroll to the Rent Itemization section.

---

#### 6. Broken File Paths in Economy Guide

**File:** `docs/user-guides/economy_guide.md`

**Evidence:** Developer section used `../DOMAINS/` and `../FEATURES/` paths that resolved one directory level too high, placing them outside the `docs/` tree.

**Resolution:** Paths corrected to `../../docs/DOMAINS/ECONOMY_DESIGN/` and `../../docs/FEATURES/ECONOMY/`. All three target files confirmed present on disk.

---

### Navigation Label Mismatches

These files referenced a menu item by an incorrect label.

| File | Document Said | Actual Label | Resolution |
|------|---------------|--------------|------------|
| `features/student/work/attendance-history.md` | "Open **Payroll**" | **Work & Pay** | ✅ Updated to "Work & Pay" |
| `features/teacher/settings/feature-toggles.md` | "**Settings > Features**" | **Economy Features** | ✅ Updated to "Economy Features" |
| `features/sysadmin/teacher-management.md` | "**Manage Teachers**" | **Teacher Management** | ✅ Updated to "Teacher Management" |
| `features/sysadmin/dashboard-overview.md` | "**System Logs**" / "**Error Logs**" as separate items | Single **Logs** item | ✅ Consolidated to "Logs"; note added explaining grouping |
| `diagnostics/teacher/students.md` | Claim requires "first initial" | Requires full **First Name** | ✅ Updated to full first name and last name |

---

### Student-Facing Inaccuracies

#### 7. Dashboard Balance Location Is Wrong

**File:** `docs/user-guides/features/student/account/dashboard-overview.md`

**Evidence:** `templates/student_dashboard.html` — balances appear third in the layout, below Weekly Stats and the Attendance card.

**Resolution:** Guide updated to direct students to scroll to the Account Balances section after reviewing stats and attendance.

---

#### 8. "Break / Done" Is One Combined Button

**File:** `docs/user-guides/features/student/work/start-end-work.md`

**Evidence:** `templates/student_dashboard.html` — a single button labeled **"Break / Done"**, not two separate controls.

**Resolution:** Guide updated to consistently refer to the single **Break / Done** button.

---

#### 9. Login Setup: Wrong PIN Length, Missing Passphrase Step

**File:** `docs/user-guides/features/student/account/login-setup.md`

**Evidence:** PIN accepts 4–8 digits, not strictly 4. Passphrase setup is a required step that was omitted entirely.

**Resolution:** Guide updated to specify **4-8 digit PIN** and now includes the passphrase creation step.

---

### Frontmatter `related:` Path Issues

Three files used a `user-guides/` prefix and dash-separated subdirectory paths in `related:` frontmatter entries, causing potential resolution failures.

| File | Original Entry | Corrected Entry |
|------|---------------|-----------------|
| `features/teacher/economy/transactions.md` | `user-guides/diagnostics/teacher-transactions-banking` | `diagnostics/teacher/transactions-banking` |
| `features/teacher/settings/account-recovery.md` | `user-guides/diagnostics/teacher-login` | `diagnostics/teacher/login` |
| `features/teacher/settings/feature-toggles.md` | `user-guides/diagnostics/teacher-onboarding` | `diagnostics/teacher/onboarding` |
| `features/teacher/classroom/attendance-approvals.md` | `user-guides/features/student/work/start-end-work` | `features/student/work/start-end-work` |
| `features/teacher/classroom/attendance-corrections.md` | `user-guides/features/teacher/classroom/attendance-approvals` | `features/teacher/classroom/attendance-approvals` |
| `features/student/work/attendance-history.md` | `user-guides/diagnostics/student-attendance` | `diagnostics/student/attendance` |

**Resolution:** All six entries corrected to use proper relative paths without the `user-guides/` prefix.

---

## Files Reviewed with No Issues Found

The following files were read and cross-referenced with no discrepancies identified:

- `features/teacher/classroom/attendance-approvals.md` — Describes Classroom > Attendance with class block toggles and the filter panel accurately.
- `features/teacher/classroom/attendance-corrections.md` — Correctly describes the append-only attendance log and diagnosis workflow.
- `features/student/support/report-issues.md` — Describes the report icon next to attendance events; matches template behavior.
- `diagnostics/teacher/attendance-payroll.md` — Content is accurate to the actual attendance and payroll workflow.
