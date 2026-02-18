# Template Audit Report

**Date:** 2026-02-17
**Scope:** `templates/` directory
**Goal:** Identify unification status of all templates.

## Summary

| Category | Count | Description |
|---|---|---|
| **Total Templates** | ~60 | Estimated based on file count |
| **Fully Modernized** | ~40 | Converted to tokens, no legacy icons/colors |
| **Partially Updated** | ~15 | mostly updated, but retain some legacy patterns |
| **Legacy / Unaudited** | ~5 | Standalone or less visited pages |

## Outstanding Issues

### 1. Legacy Icons (Bootstrap `bi-`)
The following templates still contain `<i class="bi ...">` tags, mostly in mobile navigation or specific widgets. These should be replaced with `<span class="material-symbols-outlined">`.

-   `templates/layout_admin.html` (Mobile Bottom Nav)
-   `templates/sysadmin_user_report_detail.html`
-   `templates/admin_dashboard.html` (some tooltips/icons might be missed?)
-   (Grep indicated usage in `admin_feature_settings.html`, `admin_students.html`)

### 2. Output Opacity Hacks (`bg-opacity-*`)
While `bg-opacity-10` was systematically removed, other opacity levels remain, particularly for "white-on-color" overlays.

-   `templates/admin_dashboard.html`: Uses `bg-white bg-opacity-25` for the "Active Students" card icon.
-   `templates/admin_students.html`: Likely similar usage.
-   `templates/student_insurance_marketplace.html`

**Recommendation:** Evaluate if these should use transparency tokens (e.g., `--white-25`) or if the design should shift to opaque "subtle" colors.

### 3. Inline Hex Colors (`style="...#..."`)
Specific templates still use inline styles with hex codes, which violates the "Semantic Over Hardcoded" principle.

-   `templates/maintenance.html`
-   `templates/admin_students.html` (Likely conditional formatting in tables)
-   `templates/admin_edit_insurance_policy.html`
-   `templates/system_admin_dashboard.html`
-   `templates/hall_pass_queue.html` (Often has custom status colors)

## Detailed File Status

### Admin Core
-   `layout_admin.html`: **PARTIAL**. Sidebar updated, Mobile Nav needs update.
-   `admin_dashboard.html`: **PARTIAL**. Cards updated, but intro icon uses opacity hack.
-   `admin_students.html`: **PARTIAL**. Needs check for inline hex and opacity.
-   `admin_payroll.html`: **UPDATED**.
-   `admin_store.html`: **UPDATED**.

### Student Core
-   `layout_student.html`: **UPDATED**.
-   `student_dashboard.html`: **UPDATED**.
-   `student_login.html`: **UPDATED**.
-   `student_insurance_*.html`: **UPDATED** (mostly, checked marketplace).

### Sysadmin Core
-   `layout_system_admin.html`: **UPDATED**.
-   `system_admin_dashboard.html`: **PARTIAL** (Check inline hex).
-   `sysadmin_user_reports.html`: **PARTIAL**.

### Standalone
-   `privacy.html`: **UPDATED**.
-   `tos.html`: **UPDATED**.
-   `maintenance.html`: **LEGACY** (Needs token update).
-   `error_*.html`: **LEGACY** (Likely standard Bootstrap, needs verification).

## Next Steps for Developer

1.  **Icon Sweep:** Replace all `bi-*` references in `layout_admin.html` mobile nav.
2.  **Opacity Decision:** Decide on a standard pattern for "Icon on Primary Background" (currently `bg-white bg-opacity-25`).
3.  **Hex Eradication:** Inspect the "Inline Hex" list and move these colors to `tokens.css` or use standard utilities.
